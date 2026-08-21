#!/bin/bash
# fullft_fleet.sbatch — CONTINUITY 2026-08-21, Kim direct: "AdamW versions of the fullFT fp32 —
# big goa, avp aug, suomisoundi, mix. Land on t1024. lr 1e-4 (Zach's number)."
#
# THIS IS THE MATCHED CONTROL THE DRONE FAMILY NEVER HAD (EXPERIMENTS A4, paper 2605.10468):
# every previous full-FT was Fusion (NS5 norm-runaway → drone; the ep59+ collapse W measured) or
# constant-LR AdamW judged at the terminal ckpt. Kim's fp32-collapse worry is answered by the
# forensics: the collapse mechanism was the OPTIMIZER (Fusion norm growth), not fp32 — the
# fp32/bf16 trajectory twins walk the same path to 3 significant figures.
#
# RECIPE: medium-base FULL fine-tune · AdamW lr 1e-4 (constant — no AdamW scheduler exists; judge
# by EMA weights + soups, sanity16 rule) · fp32 (PRECISION overridable: Kim liked fp16's sound in
# the precision-ladder listens — PRECISION=fp16 twins are one submit, and fp16 also enables FA2)
# · T=1024 · 20 epochs · ckpt every 2 · **BS=2/rank + GA=4 = effective batch 64** — the ONLY
# proven-safe full-FT batch pattern (two EMA+full-FT OOMs incl. fp32+T1024+bs4; skill rule:
# bs2 + accumulate, never a bigger raw batch) · **--use-ema ON** (the EMA copy is what makes a
# constant-LR checkpoint listenable; render path must load the EMA weights).
#
# ONE DATASET PER JOB, single node, 8 GCDs, Pattern-2 DDP (multi-node is UNSOLVED).
# RUN:  DATASET=biggoa sbatch lumi/sbatch/fullft_fleet.sbatch     (and avpaug | suomi | mix3)
#       PRECISION=fp16 DATASET=biggoa sbatch ...                  (the fp16-sound twin)
# VERIFY: LOCAL_RANK 0..7 once each; ckpts UN-versioned; loss lines advancing.
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=56
#SBATCH --mem=0
#SBATCH --time=24:00:00
#SBATCH --job-name=fullft_fleet
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

DATASET=${DATASET:?set DATASET=biggoa|avpaug|suomi|mix3}
SEED=${SEED:-1}
LR=${LR:-1e-4}
PRECISION=${PRECISION:-fp32}     # fp32 | fp16 | bf16 (fp16/bf16 = downcast base; -mixed variants also valid)
BS=${BS:-2}                      # per rank — DO NOT RAISE; use GA (proven full-FT+EMA pattern)
GA=${GA:-4}                      # accumulate_grad_batches; effective batch = 8*BS*GA = 64 default
EPOCHS=${EPOCHS:-20}
CKEVERY=${CKEVERY:-2}
EMA=${EMA:-1}
NAME=fullft_${DATASET}_t1024_${PRECISION}_lr${LR}_s${SEED}
RUN=${SCRATCH}/runs/fullft_fleet/${NAME}

case "${DATASET}" in
  suomi)  DIRS="suomisoundi_latents";  SIDES="${CODE}/lumi/suomisoundi_caption_sidecar.json"; PROBS="0,0.9,0.1" ;;
  biggoa) DIRS="latents_goa_bigset";   SIDES="${CODE}/lumi/goa_bigset_hinted_bylatent.json";   PROBS="0,0,1" ;;
  avpaug) DIRS="latents_avp";          SIDES="${CODE}/lumi/avp_captions_tiered.json";         PROBS="0,0.9,0.1" ;;
  mix3)   DIRS="latents_goa_bigset,suomisoundi_latents,latents_avp"
          SIDES="${CODE}/lumi/goa_bigset_hinted_bylatent.json,${CODE}/lumi/suomisoundi_caption_sidecar.json,${CODE}/lumi/avp_captions_tiered.json"
          PROBS="0,0,1;0,0.9,0.1;0,0.9,0.1" ;;
  *) echo "[fullft] FATAL: unknown DATASET ${DATASET}"; exit 1 ;;
esac

[ -n "${SIF}" ] || { echo "[fullft] FATAL: no multitorch image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[fullft] FATAL: ${VENV} missing"; exit 1; }
grep -q 'set_device' ${CODE}/stable-audio-3/scripts/train_lora.py \
  || { echo "[fullft] FATAL: train_lora.py lacks the LOCAL_RANK set_device fix"; exit 1; }
IFS=',' read -ra DD <<< "${DIRS}"; IFS=',' read -ra SS <<< "${SIDES}"
for s in "${SS[@]}"; do [ -f "$s" ] || { echo "[fullft] FATAL: sidecar missing: $s"; exit 1; }; done

FDIRS=""
for d in "${DD[@]}"; do
  if [ ! -d "${FLASH}/${d}" ]; then
    echo "[fullft] staging ${d} -> flash"; mkdir -p "${FLASH}/${d}"
    cp "${SCRATCH}/${d}"/*.npy "${FLASH}/${d}/" 2>/dev/null
    cp "${SCRATCH}/${d}"/*.json "${FLASH}/${d}/" 2>/dev/null || true
  fi
  N=$(ls "${FLASH}/${d}"/*.npy 2>/dev/null | wc -l)
  [ "${N}" -gt 0 ] || { echo "[fullft] FATAL: no latents staged for ${d}"; exit 1; }
  echo "[fullft]   ${d}: ${N} latents"
  FDIRS="${FDIRS:+${FDIRS},}${FLASH}/${d}"
done
SIDE_ARG=$(IFS=','; echo "${SS[*]}")
EMA_ARG=""; [ "${EMA}" = "1" ] && EMA_ARG="--use-ema"

mkdir -p "${RUN}"
echo "[fullft] CONFIG NAME=${NAME} DATASET=${DATASET} SEED=${SEED} LR=${LR} PRECISION=${PRECISION} BS=${BS}/rank GA=${GA} (effective $((8*BS*GA))) EPOCHS=${EPOCHS} EMA=${EMA} PROBS=${PROBS}"
cat > "${RUN}/run_meta.json" <<META
{"run": "${NAME}", "created": "$(date -Iseconds)", "slurm_job": "${SLURM_JOB_ID:-unset}",
 "purpose": "Kim direct 2026-08-21: AdamW full-FT of ${DATASET} at T1024 fp32 — the MATCHED-OPTIMIZER control the Fusion drone family never had (EXPERIMENTS A4; 2605.10468 mismatch case). LR 1e-4 per Zach.",
 "recipe": {"mode": "FULL fine-tune", "optimizer": "adamw", "lr": "${LR}",
            "lr_schedule": "NONE (constant) -- judge by EMA weights + soups/centroid",
            "precision": "${PRECISION}", "frames": 1024, "batch_per_rank": ${BS},
            "accumulate_grad_batches": ${GA}, "gpus": 8, "effective_batch": $((8*BS*GA)),
            "epochs": ${EPOCHS}, "seed": ${SEED}, "ema": ${EMA},
            "notes": "bs2+GA is the only proven-safe full-FT batch pattern (2 prior OOMs incl fp32+T1024+bs4). RENDERING MUST LOAD THE EMA WEIGHTS (diffusion_ema.ema_model.*). fp32 => no FA2; PRECISION=fp16 twin enables FA2."},
 "dataset": {"name": "${DATASET}", "dirs": "${DIRS}", "caption_probs": "${PROBS}"},
 "script": "lumi/sbatch/fullft_fleet.sbatch", "result": null, "kim_feedback": null}
META

# TORCHRUN (converted 2026-08-21): the old srun --ntasks=8 --gpus-per-task=1 pattern
# NEVER formed a DDP group on these jobs — confirmed live (eight LOCAL_RANK:0, colliding
# -vN ckpts, per-rank full-dataset step counts). All pre-conversion arms of this script
# trained as 8 independent single-GPU copies.
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
export MIOPEN_USER_DB_PATH=/tmp/miopen-fullft MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-fullft
export MIOPEN_DISABLE_CACHE=1 MIOPEN_FIND_MODE=2
export TRITON_CACHE_DIR=/tmp/triton-fullft PYTORCH_TUNABLEOP_ENABLED=0
rm -rf /tmp/miopen-fullft /tmp/triton-fullft; mkdir -p /tmp/miopen-fullft /tmp/triton-fullft
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True
ulimit -n 131072 2>/dev/null || ulimit -n 65536
torchrun --standalone --nnodes=1 --nproc-per-node=8 \
  ${CODE}/stable-audio-3/scripts/train_lora.py \
  --model medium-base --full-finetune --base_precision '"${PRECISION}"' \
  --optimizer adamw --lr '"${LR}"' \
  --encoded_dir '"${FDIRS}"' --caption_sidecar '"${SIDE_ARG}"' --caption_probs "'"${PROBS}"'" \
  --frames 1024 --batch_size '"${BS}"' --accumulate_grad_batches '"${GA}"' \
  --num_workers 4 --seed '"${SEED}"' \
  --epochs '"${EPOCHS}"' --checkpoint_every_epochs '"${CKEVERY}"' \
  '"${EMA_ARG}"' \
  --no_demos --logger csv --name '"${NAME}"' \
  --save_dir '"${RUN}"' \
  2>&1
'
rc=$?
echo "[fullft] srun rc=${rc}; ckpts: $(ls ${RUN}/*.ckpt 2>/dev/null | wc -l)"
echo "[fullft] VERIFY DDP: grep -h LOCAL_RANK ${SLURM_JOB_NAME}-${SLURM_JOB_ID}.out | sort -u  (want 0..7)"
echo "[fullft] REMEMBER: the fat ckpt holds BOTH online and EMA weights -- render/audition loads the EMA set."
exit ${rc}
