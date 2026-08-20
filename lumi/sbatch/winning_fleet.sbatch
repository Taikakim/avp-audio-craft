#!/bin/bash
# winning_fleet.sbatch — CONTINUITY 2026-08-20, Kim direct: "copy winning_avp_t1024_a45_fp32 with the
# suomisoundi and big goa sets, and the mix set" — the bread-and-butter AdamW production fleet.
#
# RECIPE (copied from the run_meta of winning_avp_t1024_a45_fp32, reconstructed from its ckpt args):
#   medium-base · DoRA-rows rank 128, alpha 45 · AdamW, lr 1e-4, CONSTANT (no scheduler exists for
#   AdamW in train_lora.py — judge by SOUPS/centroid, not the terminal ckpt; sanity16 rule) ·
#   fp32 base (⇒ NO FA2 — FA2 refuses fp32; sdpa-math, as the original ran) · T=1024 frames (95.11 s)
#   · 20 epochs (original terminal ep19) · ckpt every 2 epochs (deadline-truncation insurance).
# DIFFERENCE from the original, on purpose: 8-GCD single-node DDP (Pattern 2) instead of 1 GCD, with
#   BS=1 per rank ⇒ effective batch 8 vs the original's 4. Closest reachable at 8-way; recorded in
#   run_meta so the comparison can't be misread. The avp dataset IS the original corpus = the control
#   arm that isolates the 1-GCD→8-GCD change.
#
# ONE DATASET PER JOB, single node, 8 GCDs — multi-node DDP is UNSOLVED (two silent 8-way groups;
# skill 🔴 2026-08-15). The fleet is N independent jobs; small short jobs backfill fastest.
#
# RUN (one line per job):
#   DATASET=suomi  SEED=1 sbatch lumi/sbatch/winning_fleet.sbatch
#   DATASET=biggoa SEED=1 sbatch lumi/sbatch/winning_fleet.sbatch
#   DATASET=mix3   SEED=1 sbatch lumi/sbatch/winning_fleet.sbatch
#   DATASET=avp    SEED=1 sbatch lumi/sbatch/winning_fleet.sbatch     (control: original corpus)
#   ... and the same four with SEED=2.
# VERIFY DDP before trusting anything: grep -h "LOCAL_RANK\|rank:" <out> | sort -u -> ranks 0..7 once
#   each, ckpts UN-versioned (no -vN), steps/epoch = n_latents / 8.
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=8
#SBATCH --gpus-per-task=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=24:00:00
#SBATCH --job-name=winning_fleet
#SBATCH --output=%x-%j.out
#SBATCH --no-requeue

set -uo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}

DATASET=${DATASET:?set DATASET=suomi|biggoa|mix3|avp}
SEED=${SEED:-1}
LR=${LR:-1e-4}
BS=${BS:-1}                # per rank; global = 8*BS (original global batch was 4 on 1 GCD)
EPOCHS=${EPOCHS:-20}
CKEVERY=${CKEVERY:-2}
RANK=${RANK:-128}
ALPHA=${ALPHA:-45}
NAME=wfleet_${DATASET}_t1024_a${ALPHA}_fp32_s${SEED}
RUN=${SCRATCH}/runs/winning_fleet/${NAME}

# ── dataset registry (dirs under $SCRATCH; sidecars aligned 1:1; per-source caption probs) ──────
case "${DATASET}" in
  suomi)  DIRS="suomisoundi_latents";           SIDES="${CODE}/lumi/suomisoundi_caption_sidecar.json"; PROBS="0,0.9,0.1" ;;
  biggoa) DIRS="latents_goa_bigset";            SIDES="${CODE}/lumi/goa_bigset_hinted_bylatent.json";   PROBS="0,0,1" ;;
  avp)    DIRS="latents_avp";                   SIDES="${CODE}/lumi/avp_captions_tiered.json";         PROBS="0,0.9,0.1" ;;
  mix3)   DIRS="latents_goa_bigset,suomisoundi_latents,latents_avp"
          SIDES="${CODE}/lumi/goa_bigset_hinted_bylatent.json,${CODE}/lumi/suomisoundi_caption_sidecar.json,${CODE}/lumi/avp_captions_tiered.json"
          PROBS="0,0,1;0,0.9,0.1;0,0.9,0.1" ;;
  *) echo "[wfleet] FATAL: unknown DATASET ${DATASET}"; exit 1 ;;
esac

[ -n "${SIF}" ] || { echo "[wfleet] FATAL: no multitorch image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[wfleet] FATAL: ${VENV} missing"; exit 1; }
grep -q 'set_device' ${CODE}/stable-audio-3/scripts/train_lora.py \
  || { echo "[wfleet] FATAL: train_lora.py lacks the LOCAL_RANK set_device fix"; exit 1; }
IFS=',' read -ra DD <<< "${DIRS}"; IFS=',' read -ra SS <<< "${SIDES}"
for s in "${SS[@]}"; do [ -f "$s" ] || { echo "[wfleet] FATAL: sidecar missing: $s"; exit 1; }; done

# stage every source to /flash (node-local) once
FDIRS=""
for d in "${DD[@]}"; do
  if [ ! -d "${FLASH}/${d}" ]; then
    echo "[wfleet] staging ${d} -> flash"; mkdir -p "${FLASH}/${d}"
    cp "${SCRATCH}/${d}"/*.npy "${FLASH}/${d}/" 2>/dev/null
    cp "${SCRATCH}/${d}"/*.json "${FLASH}/${d}/" 2>/dev/null || true
  fi
  N=$(ls "${FLASH}/${d}"/*.npy 2>/dev/null | wc -l)
  [ "${N}" -gt 0 ] || { echo "[wfleet] FATAL: no latents staged for ${d}"; exit 1; }
  echo "[wfleet]   ${d}: ${N} latents"
  FDIRS="${FDIRS:+${FDIRS},}${FLASH}/${d}"
done
SIDE_ARG=$(IFS=','; echo "${SS[*]}")

mkdir -p "${RUN}"
echo "[wfleet] CONFIG NAME=${NAME} DATASET=${DATASET} SEED=${SEED} LR=${LR} BS=${BS}/rank (global $((8*BS))) EPOCHS=${EPOCHS} CKEVERY=${CKEVERY} rank=${RANK} alpha=${ALPHA} fp32 T1024 PROBS=${PROBS}"
cat > "${RUN}/run_meta.json" <<META
{"run": "${NAME}", "created": "$(date -Iseconds)", "slurm_job": "${SLURM_JOB_ID:-unset}",
 "purpose": "Kim direct 2026-08-20: copy the winning_avp_t1024_a45_fp32 recipe onto ${DATASET}. Bread-and-butter AdamW production fleet (4 datasets x 2 seeds, 8x 1-node 8-GCD jobs).",
 "recipe": {"adapter": "dora-rows", "rank": ${RANK}, "alpha": ${ALPHA}, "optimizer": "adamw",
            "lr": "${LR}", "lr_schedule": "NONE (constant; no AdamW scheduler exists in train_lora) -- judge by soups/centroid",
            "precision": "fp32 (no FA2 possible)", "frames": 1024, "batch_per_rank": ${BS},
            "gpus": 8, "effective_batch": $((8*BS)), "epochs": ${EPOCHS}, "seed": ${SEED},
            "delta_vs_original": "8-GCD DDP effective batch $((8*BS)) vs original 1-GCD batch 4; avp arm is the control for exactly this"},
 "dataset": {"name": "${DATASET}", "dirs": "${DIRS}", "caption_probs": "${PROBS}"},
 "script": "lumi/sbatch/winning_fleet.sbatch", "result": null, "kim_feedback": null}
META

srun --nodes=1 --ntasks=8 --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -uo pipefail
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; FLASH=/flash/project_465003186
CODE=${PROJ}/code
VENV='"${VENV}"'
source ${VENV}/bin/activate
export PYTHONPATH=${VENV}/lib/python3.12/site-packages:${CODE}/stable-audio-3:${CODE}/stable-audio-tools:${CODE}/lumi/vendor${PYTHONPATH:+:${PYTHONPATH}}
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-${SLURM_PROCID} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-${SLURM_PROCID}
export MIOPEN_DISABLE_CACHE=1 MIOPEN_FIND_MODE=2
export TRITON_CACHE_DIR=/tmp/triton-${SLURM_PROCID} PYTORCH_TUNABLEOP_ENABLED=0
mkdir -p /tmp/miopen-${SLURM_PROCID} /tmp/triton-${SLURM_PROCID}
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True
ulimit -n 65536
python ${CODE}/stable-audio-3/scripts/train_lora.py \
  --model medium-base --base_precision fp32 \
  --adapter_type dora-rows --rank '"${RANK}"' --lora_alpha '"${ALPHA}"' \
  --optimizer adamw --lr '"${LR}"' \
  --encoded_dir '"${FDIRS}"' --caption_sidecar '"${SIDE_ARG}"' --caption_probs "'"${PROBS}"'" \
  --frames 1024 --batch_size '"${BS}"' --num_workers 4 --seed '"${SEED}"' \
  --epochs '"${EPOCHS}"' --checkpoint_every_epochs '"${CKEVERY}"' \
  --no_demos --logger csv --name '"${NAME}"' \
  --save_dir '"${RUN}"' \
  2>&1 | sed "s/^/[r${SLURM_PROCID}] /"
'
rc=$?
echo "[wfleet] srun rc=${rc}; ckpts: $(ls ${RUN}/*.ckpt 2>/dev/null | wc -l)"
echo "[wfleet] VERIFY DDP: grep -h \"LOCAL_RANK\" ${SLURM_JOB_NAME}-${SLURM_JOB_ID}.out | sort -u  (want 0..7)"
exit ${rc}
