#!/bin/bash
# dora256_mixed_2x4gpu.sbatch — CONTINUITY 2026-08-17 (Kim direct, after the full-FT DDP-bug
# saga tonight: "with all the trouble we've having with full finetunes, let's also run... rank
# 256 DoRA, FP32, alpha 196" then corrected "why single GPU? Run on four. And another four with
# 5e-5 but alpha 128" then "EMA and warmup on, and Adagc"). Two DoRA arms on ONE 8-GPU node,
# 4 real DDP-synced GPUs each, same mixed avp+goa T4096 dataset as
# fullft_mixed_avp_goa_t4096.sbatch:
#   arm A (GPUs 0-3): rank=256 alpha=196 lr=1e-4
#   arm B (GPUs 4-7): rank=256 alpha=128 lr=5e-5
#
# GENUINELY NEW PATTERN, NEVER RUN BEFORE IN THIS CODEBASE (flagging plainly, not silently
# assuming it works): every proven DDP script this session runs ONE srun step spanning all 8
# GPUs (--devices 8, world_size=8). Splitting one node into TWO independent 4-GPU DDP groups
# needs each group to see its OWN scoped SLURM_NTASKS=4/SLURM_PROCID=0..3 (Lightning's
# SLURMEnvironment derives world_size/rank straight from those) -- a single srun --ntasks=8
# would put both arms in ONE confused 8-way "DDP" group instead of two real 4-way ones (the
# same class of bug as tonight's missing --devices, just from a different cause). Fix: TWO
# SEPARATE srun job STEPS, each --ntasks=4, each getting its own correctly-scoped SLURM_NTASKS
# -- the standard SLURM idiom for packing independent multi-GPU steps onto one allocation.
# --exclusive on each srun step tells SLURM's step scheduler not to let the two steps'
# GRES (GPU) allocations overlap, so arm A and arm B land on disjoint GPU sets automatically.
# Backgrounded (&) + a trailing `wait` so both arms actually run concurrently, not
# sequentially. UNTESTED end to end -- run SMOKE=1 FIRST and verify both arms actually see 4
# GPUs each (not 8, not 1) before trusting a full overnight run.
#
# EMA (Kim asked for it explicitly): train_lora.py FORCE-DISABLES EMA for DoRA/LoRA adapters
# regardless of the flag (full-finetune only) -- passing --use-ema here is a harmless no-op,
# not withheld, just doesn't do anything for this adapter type. Flagging so it isn't mistaken
# for silently working.
#
# ── ROUND 3, THE ONE THAT ACTUALLY WORKS (2026-08-17) ── migrated to the CSC/LUMI reference
# torchrun launch, after job 21251551 PROVED it on the sibling full-FT script: real DDP
# confirmed by LOCAL_RANK 0..7 (not eight 0s), ZERO -vN duplicate checkpoints, and
# 244 steps/epoch vs the broken run's 1948 (= 1948/8, i.e. genuine 8-way data sharding), in
# 3h41m instead of 1d8h. Per arm here: ONE srun --overlap task, explicit ROCR_VISIBLE_DEVICES
# (0-3 / 4-7), and `torchrun --nproc-per-node=4` with a PER-ARM rdzv port (two rendezvous
# servers on one node collide on a shared port). Requires train_lora.py's
# torch.cuda.set_device(LOCAL_RANK) fix (guarded in the preflight below).
#
# CORRECTION (2026-08-17): first version passed --devices 4 per arm, reasoning (wrongly) from
# fullft_mixed_avp_goa_t4096.sbatch's now-also-corrected claim that an explicit --devices was
# needed for real DDP under --gpus-per-task=1. It's not -- fullft_avp_aug.sbatch (job #68, the
# actual proven precedent) uses --gpus-per-task=1 with NO --devices flag and documents
# Lightning's SLURMEnvironment forming the DDP group correctly from SLURM_NTASKS alone.
# Passing --devices 4 here crashed both arms immediately (job 21245642.1,
# MisconfigurationException: "You requested gpu: [0,1,2,3] But your machine only has: [0]" --
# with cgroup-isolated GPUs each process only ever sees ONE device, so --devices N>1 fails
# outright). REMOVED --devices/--num_nodes below to match #68's proven form. The two-separate-
# exclusive-srun-steps split (each getting its own scoped SLURM_NTASKS=4) is UNCHANGED and
# still the part of this script that's genuinely untested -- that's what SMOKE=1 verifies.
#
# RUN: SMOKE=1 sbatch lumi/sbatch/dora256_mixed_2x4gpu.sbatch   (bounded ~20 steps/arm, verify
#      BOTH arms print world_size=4 with 4 distinct local GPUs, no crash/hang, ckpts appear)
#      then: sbatch lumi/sbatch/dora256_mixed_2x4gpu.sbatch      (full, open only after SMOKE passes)
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=48:00:00
#SBATCH --job-name=sa3_dora256_2x4
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}

GOA_DIR=${GOA_DIR:-latents_sa3}
FRAMES=${FRAMES:-4096}; PREC=${PREC:-fp32}; BS=${BS:-4}
EPOCHS=${EPOCHS:-8}; CKEVERY=${CKEVERY:-1}
WARMUP_EPOCHS=${WARMUP_EPOCHS:-0.5}
WARMUP_FRAC=$(awk -v w="${WARMUP_EPOCHS}" -v e="${EPOCHS}" 'BEGIN{printf "%.6f", w/e}')
SMOKE=${SMOKE:-0}
SIDECAR=${CODE}/lumi/goa_longform_sidecar.json
RUNROOT=${SCRATCH}/runs/dora256_mixed

[ -n "${SIF}" ] || { echo "[dora256] FATAL: no lumi-multitorch-full image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[dora256] FATAL: ${VENV} missing"; exit 1; }
grep -q -- 'LOCAL_RANK.*set_device\|set_device.*LOCAL_RANK' "${CODE}/stable-audio-3/scripts/train_lora.py" \
  || { echo "[dora256] FATAL: train_lora.py missing the LOCAL_RANK set_device fix (code refresh needed -- REQUIRED for torchrun, else all 4 ranks per arm land on the same GPU)"; exit 1; }
grep -q -- "--warmup-frac" "${CODE}/stable-audio-3/scripts/train_lora.py" \
  || { echo "[dora256] FATAL: train_lora.py missing --warmup-frac (code refresh needed)"; exit 1; }
[ -f "${SIDECAR}" ] || { echo "[dora256] FATAL: ${SIDECAR} not shipped"; exit 1; }
mkdir -p "${RUNROOT}" "${FLASH}"

for DS in latents_avp "${GOA_DIR}"; do
  if [ ! -d "${FLASH}/${DS}" ]; then
    [ -f "${SCRATCH}/${DS}.tar.gz" ] || { echo "[dora256] FATAL: ${SCRATCH}/${DS}.tar.gz missing"; exit 1; }
    mkdir -p "${FLASH}/${DS}"
    tar -xzf "${SCRATCH}/${DS}.tar.gz" -C "${FLASH}/${DS}" --strip-components=1
  fi
done
echo "[dora256] avp: $(ls ${FLASH}/latents_avp/*.npy 2>/dev/null | wc -l) crops  ${GOA_DIR}: $(ls ${FLASH}/${GOA_DIR}/*.npy 2>/dev/null | wc -l) crops  SMOKE=${SMOKE}  image=${SIF}"

run_arm() {
  local ARM_NAME=$1 RANK=$2 ALPHA=$3 LR=$4 PORT=$5 GPUS=$6
  local RUN=${RUNROOT}/${ARM_NAME}
  mkdir -p "${RUN}"
  local STEP_ARGS="--epochs ${EPOCHS}"
  [ "${SMOKE}" = "1" ] && STEP_ARGS="--steps 20"   # omitting --epochs caps max_steps=--steps (the
                                                     # trap from the continue8 bug, used
                                                     # deliberately here for a bounded smoke)
  # ONE srun task per arm (NOT --ntasks=4 --gpus-per-task=1): torchrun spawns the 4 worker
  # procs itself. GPU split is EXPLICIT via ROCR_VISIBLE_DEVICES (0-3 / 4-7) rather than
  # relying on SLURM's step-level GRES scheduler to hand out disjoint sets -- same explicit
  # pinning approach fullft_avp_dronesweep.sbatch already proved on this cluster, just 4 GPUs
  # per arm instead of 1. --overlap is REQUIRED for two steps to run concurrently on one
  # allocation. ROCR_VISIBLE_DEVICES alone, never +HIP_VISIBLE_DEVICES (MASTER §5).
  srun --overlap --nodes=1 --ntasks=1 --cpus-per-task=28 \
    singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -euo pipefail
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; FLASH=/flash/project_465003186
CODE=${PROJ}/code
RUN='"${RUN}"'
VENV='"${VENV}"'
export ROCR_VISIBLE_DEVICES='"${GPUS}"'
source ${VENV}/bin/activate
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${VENV}/lib/python3.12/site-packages:${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor${PYTHONPATH:+:${PYTHONPATH}}
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-'"${ARM_NAME}"' MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-'"${ARM_NAME}"'
export TRITON_CACHE_DIR=/tmp/triton-'"${ARM_NAME}"' PYTORCH_TUNABLEOP_ENABLED=0
rm -rf "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"; mkdir -p "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True
ulimit -n 131072 2>/dev/null || ulimit -n 65536 2>/dev/null || true

if python - <<PYEOF
import torch
from torch.nn.attention import sdpa_kernel, SDPBackend
q = torch.randn(1, 24, 2048, 64, device="cuda", dtype=torch.float32)
try:
    with sdpa_kernel([SDPBackend.FLASH_ATTENTION, SDPBackend.EFFICIENT_ATTENTION]):
        torch.nn.functional.scaled_dot_product_attention(q, q, q)
    print("fp32 fused SDPA: OK")
except Exception as e:
    print(f"fp32 fused SDPA unavailable: {e}")
    raise SystemExit(1)
PYEOF
then export SA3_SDPA_CAST_BF16=0; else export SA3_SDPA_CAST_BF16=1; fi

FATCKPT=$(ls "${RUN}"/epoch=*.ckpt 2>/dev/null | grep -v "\.weights\.ckpt$" | sort -V | tail -1 || true)
RESUME=""; [ -n "${FATCKPT}" ] && { RESUME="--resume_ckpt ${FATCKPT}"; echo "[dora256/'"${ARM_NAME}"'] resuming from ${FATCKPT}"; }

echo "[dora256/'"${ARM_NAME}"'] node=$(hostname) ROCR=${ROCR_VISIBLE_DEVICES} torchrun nproc=4 rdzv_port='"${PORT}"'"
torchrun --nnodes=1 --nproc-per-node=4 \
  --rdzv-backend=c10d --rdzv-endpoint=localhost:'"${PORT}"' --rdzv-id='"${ARM_NAME}"' \
  ${CODE}/stable-audio-3/scripts/train_lora.py \
  --model medium-base \
  --adapter_type dora-rows --rank '"${RANK}"' --lora_alpha '"${ALPHA}"' \
  --encoded_dir ${FLASH}/latents_avp,${FLASH}/'"${GOA_DIR}"' \
  --caption_sidecar ,'"${SIDECAR}"' --caption_probs 0,0,1 \
  --save_dir "'"${RUN}"'" \
  --optimizer fusion --base_precision '"${PREC}"' \
  --use-ema --ema-beta 0.9999 \
  --warmup-frac '"${WARMUP_FRAC}"' \
  --grad-clip-mode agc \
  --lr '"${LR}"' --batch_size '"${BS}"' \
  --frames '"${FRAMES}"' \
  '"${STEP_ARGS}"' --checkpoint_every_epochs '"${CKEVERY}"' \
  ${RESUME} \
  --num_workers 6 --seed 1 --no_demos --logger csv \
  --name '"${ARM_NAME}"' 2>&1 | tee -a ${RUN}/train.log
echo "[dora256/'"${ARM_NAME}"'] step finished"
' &
}

# distinct rdzv ports: two torchrun rendezvous servers on ONE node collide on a shared port.
# distinct ROCR sets: explicit 0-3 / 4-7 GPU split, not left to the step scheduler.
run_arm dora256_mixed_a196_lr1e4 256 196 1e-4 29511 0,1,2,3
run_arm dora256_mixed_a128_lr5e5 256 128 5e-5 29521 4,5,6,7
wait
echo "[dora256] both arms finished (or timed out) -- verify per-arm logs, never trust this script's own rc:"
for A in dora256_mixed_a196_lr1e4 dora256_mixed_a128_lr5e5; do
  echo "  ${A}: $(ls ${RUNROOT}/${A}/epoch=*.ckpt 2>/dev/null | grep -v weights | sort -V | tail -1)"
done
