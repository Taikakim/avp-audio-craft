#!/bin/bash
# sanity16_biggoa_ddp8.sbatch — CONTINUITY 2026-08-18, Kim direct:
#   "in parallel, train just big goa on 8x GPU, I want to see if that affects the outcome."
#
# The companion to sanity16_arms.sbatch's single-GCD `biggoa` arm. Identical recipe in every respect
# EXCEPT the GPU count, so the pair isolates one variable: does data-parallel scale change the
# outcome on this corpus? It should not, and if it does that is itself the finding.
#
# ⚠️ EFFECTIVE BATCH IS THE CONFOUND, AND IT IS NOT AVOIDABLE — ONLY CHOOSABLE.
#   8-way DDP at the same --batch_size multiplies the effective batch by 8 (8*8 = 64 vs 8), which is
#   a different optimisation problem, not the same one run faster. W's own table shows batch size
#   moving quality independently (fp32 avp bs4 7.24 > avp bs1 6.72), so leaving it uncontrolled
#   would confound "8 GPUs" with "8x the batch".
#   BS_MODE picks which comparison you want, and there is no third option that avoids the trade:
#     match_global (DEFAULT) — BS=1 per rank, effective batch 8, SAME as the 1-GPU arm. Same
#                    optimisation, 8x the throughput. This is the right default for "does 8x GPU
#                    affect the OUTCOME", because it is the only setting where the outcome CAN be
#                    compared. Costs per-GPU efficiency at bs1.
#     match_local  — BS=8 per rank, effective batch 64. Answers "is the usual 8-GPU recipe good",
#                    which is a different and also reasonable question, but its result is NOT
#                    comparable to the single-GCD arm.
#   Whichever you pick is written into run_meta.json, so the comparison can never be misread later.
#
# 🔴 DDP PATTERN: srun --ntasks=1 + torchrun --standalone --nproc-per-node=8. NOT
#   --gpus-per-task=1 + SLURMEnvironment auto-detect, which silently trains N uncoordinated
#   single-GPU copies (lumi-ops §"Multi-GPU DDP"; job 21161065 lost a day to exactly that).
#   VERIFY before trusting any result: grep -h LOCAL_RANK <log> | sort -u  ->  want 0..7, not 8x "0".
#
# Everything else matches the arms script: stock Stability path, plain LoRA/DoRA, AdamW, no EMA
# (upstream force-disables it for adapters), constant LR (no scheduler is ever wired — see the arms
# script header). Judge by the souped/centroid checkpoint, not the terminal one.
#
# RUN:
#   ADAPTER=lora sbatch lumi/sbatch/sanity16_biggoa_ddp8.sbatch
#   BS_MODE=match_local ADAPTER=lora sbatch ...
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=56
#SBATCH --mem=0
#SBATCH --time=24:00:00
#SBATCH --job-name=sanity16_ddp8
#SBATCH --output=%x-%j.out

set -uo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}

ADAPTER=${ADAPTER:-lora}
case "${ADAPTER}" in
  lora) ADAPTER_ARG="--adapter_type lora" ;;
  dora) ADAPTER_ARG="--adapter_type dora-rows" ;;
  *) echo "[ddp8] FATAL: ADAPTER must be lora|dora"; exit 1 ;;
esac

RANK=${RANK:-16}; ALPHA=${ALPHA:-16}; LR=${LR:-1e-4}
FRAMES=${FRAMES:-256}; EPOCHS=${EPOCHS:-60}; CKEVERY=${CKEVERY:-2}
NPROC=${NPROC:-8}
BS_MODE=${BS_MODE:-match_global}
case "${BS_MODE}" in
  match_global) BS=1 ;;
  match_local)  BS=8 ;;
  *) echo "[ddp8] FATAL: BS_MODE must be match_global|match_local"; exit 1 ;;
esac
EFF=$((BS * NPROC))
SMOKE=${SMOKE:-0}

LAT_DIR=${LAT_DIR:-latents_goa_bigset}
SIDECAR=${SIDECAR:-${CODE}/lumi/goa_bigset_sidecar_hinted.json}
RUN=${RUN:-${SCRATCH}/runs/sanity16_${ADAPTER}_ddp8/biggoa}

[ -n "${SIF}" ] || { echo "[ddp8] FATAL: no multitorch image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[ddp8] FATAL: ${VENV} missing"; exit 1; }
[ -f "${SIDECAR}" ] || { echo "[ddp8] FATAL: sidecar ${SIDECAR} missing"; exit 1; }
# the LOCAL_RANK device-pin fix is what makes this pattern work at all; without it every rank loads
# onto physical GPU 0 and the job OOMs or silently co-locates
grep -q 'LOCAL_RANK' ${CODE}/stable-audio-3/scripts/train_lora.py \
  || { echo "[ddp8] FATAL: train_lora.py lacks the LOCAL_RANK set_device fix -- rsync the code tree"; exit 1; }

if [ ! -d "${FLASH}/${LAT_DIR}" ]; then
  echo "[ddp8] staging ${LAT_DIR} -> ${FLASH}"
  mkdir -p "${FLASH}/${LAT_DIR}"
  cp "${SCRATCH}/${LAT_DIR}"/*.npy "${SCRATCH}/${LAT_DIR}"/*.json "${FLASH}/${LAT_DIR}/" 2>/dev/null || true
fi
NLAT=$(ls "${FLASH}/${LAT_DIR}"/*.npy 2>/dev/null | wc -l)
[ "${NLAT}" -gt 0 ] || { echo "[ddp8] FATAL: no latents staged from ${SCRATCH}/${LAT_DIR}"; exit 1; }

mkdir -p "${RUN}"
echo "[ddp8] ADAPTER=${ADAPTER} rank=${RANK} lr=${LR} T=${FRAMES} epochs=${EPOCHS}"
echo "[ddp8] BS_MODE=${BS_MODE}: per-rank BS=${BS} x ${NPROC} ranks = effective batch ${EFF}"
echo "[ddp8] latents=${NLAT} from ${LAT_DIR}   sidecar=$(basename ${SIDECAR})"
echo "[ddp8] comparable to the 1-GCD biggoa arm: $([ "${BS_MODE}" = match_global ] && echo YES || echo 'NO -- different effective batch')"

cat > "${RUN}/run_meta.json" <<META
{
  "run": "sanity16_${ADAPTER}_ddp8_biggoa",
  "created": "$(date -Iseconds)",
  "slurm_job": "${SLURM_JOB_ID:-unset}",
  "purpose": "Kim direct: 'train just big goa on 8x GPU, I want to see if that affects the outcome.' The 8-GPU twin of sanity16_arms.sbatch's single-GCD biggoa arm, identical in every respect except GPU count.",
  "hypothesis": "Data-parallel scale should not change the outcome at matched effective batch. If it does, that is the finding.",
  "dataset": {"name": "biggoa", "latents": "${LAT_DIR}", "n_latents": ${NLAT}, "pre_encoded": true,
              "caption_sidecar": "$(basename ${SIDECAR})"},
  "recipe": {"adapter": "${ADAPTER}", "rank": ${RANK}, "alpha": ${ALPHA}, "lr": "${LR}",
             "batch_size_per_rank": ${BS}, "gpus": ${NPROC}, "effective_batch": ${EFF},
             "bs_mode": "${BS_MODE}", "frames": ${FRAMES}, "epochs": ${EPOCHS},
             "optimizer": "adamw", "precision": "bf16", "lr_schedule": "NONE (constant)",
             "ema": "force-disabled upstream for adapters", "ddp": "torchrun --standalone"},
  "comparable_to_1gpu_arm": $([ "${BS_MODE}" = match_global ] && echo true || echo false),
  "known_gaps": ["Constant LR with plain AdamW does not converge -- judge by the souped/centroid checkpoint. VERIFY DDP with: grep -h LOCAL_RANK <log> | sort -u"],
  "script": "lumi/sbatch/sanity16_biggoa_ddp8.sbatch",
  "result": null,
  "kim_feedback": null
}
META

STEP_ARGS="--epochs ${EPOCHS}"
[ "${SMOKE}" = "1" ] && STEP_ARGS="--steps 20"

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
export MIOPEN_USER_DB_PATH=/tmp/miopen-ddp8 MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-ddp8
export TRITON_CACHE_DIR=/tmp/triton-ddp8 PYTORCH_TUNABLEOP_ENABLED=0
mkdir -p /tmp/miopen-ddp8 /tmp/triton-ddp8
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True
torchrun --standalone --nnodes=1 --nproc-per-node='"${NPROC}"' \
  ${CODE}/stable-audio-3/scripts/train_lora.py \
  --model medium-base --base_precision bf16 \
  '"${ADAPTER_ARG}"' --rank '"${RANK}"' --lora_alpha '"${ALPHA}"' \
  --optimizer adamw --lr '"${LR}"' \
  --encoded_dir '"${FLASH}"'/'"${LAT_DIR}"' --caption_sidecar '"${SIDECAR}"' \
  --frames '"${FRAMES}"' --batch_size '"${BS}"' --num_workers 4 \
  '"${STEP_ARGS}"' --checkpoint_every_epochs '"${CKEVERY}"' \
  --save_dir '"${RUN}"' \
  2>&1 | sed "s/^/[ddp8] /"
'
echo "[ddp8] done. checkpoints: $(ls ${RUN}/*.ckpt 2>/dev/null | wc -l)"
echo "[ddp8] VERIFY DDP ACTUALLY FORMED before reading anything into this run:"
echo "[ddp8]   grep -h LOCAL_RANK ${SLURM_JOB_NAME:-sanity16_ddp8}-${SLURM_JOB_ID:-JOBID}.out | sort -u"
echo "[ddp8]   want LOCAL_RANK 0 through $((NPROC-1)) -- eight copies of 'LOCAL_RANK: 0' means it trained"
echo "[ddp8]   8 uncoordinated single-GPU models and the comparison is void."
