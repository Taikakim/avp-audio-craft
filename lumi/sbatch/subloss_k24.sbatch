#!/bin/bash
# subloss_k24.sbatch — SUBSPACE-WEIGHTED trainer, K=24, four corpora (Kim direct 2026-08-21:
# "rerun the subspace weighed trainer. DoRA, 8e-5, rank 128, BF16, K 24 instead of the last
# max of 12, batch 8, one run each: avp aug, suomisoundi, goa bigset, goa bigset+goa
# (upweight the FLAC sources), 64 epochs").
#
# LANE CONTEXT: continues the v3sel grid (K=2/5/12 + k5_tgate, trained ep19, rendered — the
# tgate arm's 240 catch-up cells landed 2026-08-21, verdict pending Kim's ears). K here =
# --subspace-loss-weight, the multiplier on the RF error's melody-subspace share; basis stays
# melody_subspace15_selective_v3.npz (whitened-CSP, 15-dim, held-out melody/codec SNR 5.1x).
# Lane conventions kept for comparability: dora-rows r128 ALPHA 128, T512 --beat-aware-crop,
# AdamW CONSTANT LR (the k-grid + lreq baseline are constant-LR; a WSD variant would confound
# the K axis — run one later if K=24 wins). Kim's overrides: lr 8e-5, bs8/rank (x8 DDP =
# eff 64 vs the grid's 4 — recorded in meta), 64 epochs, ckpt every 8.
#
# RUN (4 jobs):
#   DATASET=avpaug sbatch lumi/sbatch/subloss_k24.sbatch
#   DATASET=suomi  sbatch lumi/sbatch/subloss_k24.sbatch
#   DATASET=biggoa sbatch lumi/sbatch/subloss_k24.sbatch
#   DATASET=bigmix sbatch lumi/sbatch/subloss_k24.sbatch   # bigset + old goa (FLAC upweight by inclusion)
# VERIFY: LOCAL_RANK 0..7 once each; UN-versioned ckpts; steps/ep = n/(8*8).
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=56
#SBATCH --mem=0
#SBATCH --time=10:00:00
#SBATCH --job-name=subloss_k24
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

DATASET=${DATASET:?set DATASET=avpaug|suomi|biggoa|bigmix}
K=${K:-24}
LR=${LR:-8e-5}
BS=${BS:-8}
EPOCHS=${EPOCHS:-64}
CKEVERY=${CKEVERY:-8}
SEED=${SEED:-1}
BASIS=${CODE}/lumi/melody_subspace15_selective_v3.npz
case "${DATASET}" in
  avpaug) DIRS="latents_avp";          SIDES="${CODE}/lumi/avp_captions_tiered.json";        PROBS="0,0.9,0.1" ;;
  suomi)  DIRS="suomisoundi_latents";  SIDES="${CODE}/lumi/suomisoundi_caption_sidecar.json"; PROBS="0.25,0.45,0.30" ;;
  biggoa) DIRS="latents_goa_bigset";   SIDES="${CODE}/lumi/goa_bigset_hinted_bylatent.json";  PROBS="0,0,1" ;;
  bigmix) DIRS="latents_goa_bigset,latents_sa3"
          SIDES="${CODE}/lumi/goa_bigset_hinted_bylatent.json,${CODE}/lumi/goa_longform_sidecar.json"
          PROBS="0,0,1;0.6,0.3,0.1" ;;
  *) echo "[k24] FATAL: unknown DATASET"; exit 1 ;;
esac
NAME=subloss_k${K}_${DATASET}_t512_bf16_s${SEED}
RUN=${SCRATCH}/runs/subloss_k24/${NAME}

[ -n "${SIF}" ] || { echo "[k24] FATAL: no multitorch image"; exit 1; }
[ -f "${BASIS}" ] || { echo "[k24] FATAL: basis missing"; exit 1; }
IFS=',' read -ra SS <<< "${SIDES}"
for s in "${SS[@]}"; do [ -f "$s" ] || { echo "[k24] FATAL: sidecar missing: $s"; exit 1; }; done

FDIRS=""
IFS=',' read -ra DD <<< "${DIRS}"
for d in "${DD[@]}"; do
  LOCKDIR=${FLASH}/.stage_${d}.lock
  if [ "$(ls ${FLASH}/${d}/*.npy 2>/dev/null | wc -l)" -eq 0 ]; then
    if mkdir "${LOCKDIR}" 2>/dev/null; then
      echo "[k24] staging ${d} -> flash (lock held)"; mkdir -p "${FLASH}/${d}"
      cp ${SCRATCH}/${d}/*.npy "${FLASH}/${d}/" 2>/dev/null
      cp ${SCRATCH}/${d}/*.json "${FLASH}/${d}/" 2>/dev/null || true
      rmdir "${LOCKDIR}"
    else
      echo "[k24] waiting on staging lock for ${d}"; while [ -d "${LOCKDIR}" ]; do sleep 20; done
    fi
  fi
  if [ "$(ls ${FLASH}/${d}/*.json 2>/dev/null | wc -l)" -eq 0 ]; then
    cp ${SCRATCH}/${d}/*.json "${FLASH}/${d}/" 2>/dev/null || true
  fi
  N=$(ls ${FLASH}/${d}/*.npy 2>/dev/null | wc -l); NJ=$(ls ${FLASH}/${d}/*.json 2>/dev/null | wc -l)
  [ "${N}" -gt 0 ] || { echo "[k24] FATAL: no latents for ${d}"; exit 1; }
  [ "${NJ}" -gt 0 ] || { echo "[k24] FATAL: no json metas for ${d} (rsync from local first)"; exit 1; }
  echo "[k24]   ${d}: ${N} latents, ${NJ} metas"
  FDIRS="${FDIRS:+${FDIRS},}${FLASH}/${d}"
done
SIDE_ARG=$(IFS=','; echo "${SS[*]}")

mkdir -p "${RUN}"
echo "[k24] CONFIG NAME=${NAME} K=${K} LR=${LR} BS=${BS}/rank (eff $((BS*8))) EPOCHS=${EPOCHS}"
cat > "${RUN}/run_meta.json" <<META
{"run": "${NAME}", "created": "$(date -Iseconds)", "slurm_job": "${SLURM_JOB_ID:-unset}",
 "hypothesis": "K=24 melody-subspace upweighting (2x the previous max K=12), per-corpus (Kim direct 2026-08-21). bigmix arm upweights FLAC sources by including latents_sa3 alongside bigset.",
 "arm_K": ${K}, "subspace": "melody_subspace15_selective_v3.npz (15-dim whitened-CSP)",
 "recipe": {"adapter": "dora-rows r128 a128 (lane convention)", "optimizer": "adamw wd0.01 CONSTANT LR (lane comparability; judge by soups)",
            "lr": "${LR}", "precision": "bf16", "frames": 512, "beat_aware": true,
            "batch_per_rank": ${BS}, "gpus": 8, "ddp": "torchrun", "effective_batch": $((BS*8)),
            "delta_vs_grid": "eff batch 64 vs the k-grid's 4; lr 8e-5 vs 1e-4; 64 ep vs 20",
            "epochs": ${EPOCHS}, "ckpt_every": ${CKEVERY}, "seed": ${SEED}},
 "dataset": {"name": "${DATASET}", "dirs": "${DIRS}", "caption_probs": "${PROBS}"},
 "baseline": "subloss_v3sel_k12 (goa) + per-corpus dorlor A11 arms (K=1 at matched DDP)",
 "script": "lumi/sbatch/subloss_k24.sbatch", "kim_feedback": null}
META

srun --nodes=1 --ntasks=1 --cpus-per-task=56 \
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
export MIOPEN_USER_DB_PATH=/tmp/miopen-k24 MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-k24
export MIOPEN_DISABLE_CACHE=1 MIOPEN_FIND_MODE=2
export TRITON_CACHE_DIR=/tmp/triton-k24 PYTORCH_TUNABLEOP_ENABLED=0
rm -rf /tmp/miopen-k24 /tmp/triton-k24; mkdir -p /tmp/miopen-k24 /tmp/triton-k24
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True
ulimit -n 131072 2>/dev/null || ulimit -n 65536
torchrun --standalone --nnodes=1 --nproc-per-node=8 \
  ${CODE}/stable-audio-3/scripts/train_lora.py \
  --model medium-base --base_precision bf16 \
  --adapter_type dora-rows --rank 128 --lora_alpha 128 \
  --optimizer adamw --lr '"${LR}"' \
  --encoded_dir '"${FDIRS}"' --caption_sidecar '"${SIDE_ARG}"' --caption_probs "'"${PROBS}"'" \
  --frames 512 --beat-aware-crop --batch_size '"${BS}"' \
  --subspace-loss-basis '"${BASIS}"' --subspace-loss-weight '"${K}"' \
  --num_workers 4 --seed '"${SEED}"' \
  --epochs '"${EPOCHS}"' --checkpoint_every_epochs '"${CKEVERY}"' \
  --no_demos --logger csv --name '"${NAME}"' \
  --save_dir '"${RUN}"' \
  2>&1
'
rc=$?
echo "[k24] srun rc=${rc}; ckpts: $(ls ${RUN}/*.ckpt 2>/dev/null | wc -l)"
grep -h "LOCAL_RANK" ${SLURM_JOB_NAME}-${SLURM_JOB_ID}.out 2>/dev/null | sort | uniq -c | head -10
exit ${rc}
