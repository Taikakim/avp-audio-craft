#!/bin/bash
# efp_fullft_t4096.sbatch — Kim FULL fine-tune campaign, full-context T=4096 arms (2026-07-17).
# One small-g node, 2 GCDs, 2 independent single-GCD training arms driven by SLURM_PROCID.
# Paste-ready for the EFP Workflows UI (Job Scripts -> workflow). Adapted from
# efp_fp32_compare.sbatch: same cotainr sa3.sif deployment, /code tree, PYTHONPATH, MIOpen
# env, bind set, HF_HUB_OFFLINE, latent staging, arm table, and longform-sidecar default.
# See that file for the full deployment rationale.
#
# DESIGN (Kim direct): FULL fine-tune of the whole 1.4B DiT (--full-finetune: unfreezes
# model.model, injects NO adapter, FusionOpt trains the entire DiT). bf16 (NO
# --base_precision), --optimizer fusion, lr 1e-4, 8 epochs, ckpt every epoch. PER-DATASET
# (never combined). This is the full-context companion to efp_fullft_short.sbatch: T=4096
# on the FULL stored latent (NO beat-aware crop). Arms:
#   PROCID 0: avp  T=4096  BS=2  grad-accum 2 (eff 4)  lr 1e-4
#   PROCID 1: goa  T=4096  BS=2  grad-accum 2 (eff 4)  lr 1e-4
#
# VRAM (bf16 full-ft, 64 GB GCD): T=4096 batch 4 is tight (~55 GB), so batch 2 +
# accumulate_grad_batches 2 = effective batch 4 keeps the token-count parity with the short
# arms while halving the live activation memory. No batch probe (batch 2 is comfortable).
#
# CAPTIONS (Kim direct 2026-07-14, inherited from fp32): DEFAULT = the definitive longform
# sidecars (SIDECAR=${CODE}/lumi/${DSTAG}_longform_sidecar.json), PROBS=0,0,1 trains
# pure-longform. To train on the datasets stored prompts instead, submit with
# CAPTIONS=stored.
#
# EPOCHS/WALLTIME: 8 epochs, ckpt every epoch. T=4096 is the slowest context; per-epoch
# checkpoints make partial completion useful if an arm hits the 47 h wall. small-g bills
# per-GCD, so mem=120G is requested explicitly (not mem=0).
#
# PREREQS: code+SIF+models pre-staged PLUS latents_avp.tar.gz and latents_sa3.tar.gz on
# ${SCRATCH} (Kim rsync) and the code tarball refreshed so scripts/train_lora.py carries
# the --full-finetune flag.
#
#SBATCH --account=project_465003186
#SBATCH --partition=small-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=2
#SBATCH --ntasks-per-node=2
#SBATCH --cpus-per-task=7
#SBATCH --mem=120G
#SBATCH --time=47:00:00
#SBATCH --job-name=sa3_fullft_t4096
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
SIF=${PROJ}/containers/sa3.sif
MODELS=${PROJ}/models
RUNROOT=${SCRATCH}/runs/fullft
mkdir -p "${RUNROOT}" "${FLASH}"

# ── stage both datasets to NVMe once (idempotent, done by task 0 before srun) ──
for DS in latents_avp latents_sa3; do
  if [ ! -d "${FLASH}/${DS}" ]; then
    mkdir -p "${FLASH}/${DS}"
    tar -xzf "${SCRATCH}/${DS}.tar.gz" -C "${FLASH}/${DS}" --strip-components=1
  fi
done
echo "[fullft-t4096] avp latents: $(ls ${FLASH}/latents_avp/*.npy 2>/dev/null | wc -l)  goa latents: $(ls ${FLASH}/latents_sa3/*.npy 2>/dev/null | wc -l)"

# per-arm launcher: everything below runs once per task inside the container.
# --nodes pinned: the EFP form controls the allocation and can oversize it;
# both arms must land on ONE node 2 GCDs.
srun --nodes=1 --ntasks=2 --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -euo pipefail
ARM=${SLURM_PROCID}
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
RUNROOT=${SCRATCH}/runs/fullft

export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${CODE}/stable-audio-3:${CODE}/lumi/vendor   # source pkg + vendored FusionOpt shim
# MIOPEN_DISABLE_CACHE=1: the MIOpen user kernel-cache gfx90a6e.ukdb is a SQLite file whose
# open fails on LUMI on every filesystem -- proven on the smoke run 2026-07-16. Disabling the
# cache is the fix; kernels recompile per run. /tmp is bound above as host tmpfs. See smoke.
# NOTE: this arm script runs inside a single-quoted bash -c -- no apostrophes or backticks below.
export MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_DISABLE_CACHE=1
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-${ARM} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-${ARM}
export TRITON_CACHE_DIR=/tmp/triton-${ARM}   # keep torch.compile cache OFF ~/.triton (home inode quota killer)
rm -rf "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"; mkdir -p "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"

# ── arm table ────────────────────────────────────────────────────────────────
case ${ARM} in
  0) DS=latents_avp; T=4096 ;;
  1) DS=latents_sa3; T=4096 ;;
  *) echo "[arm ${ARM}] no assignment"; exit 0 ;;
esac
DSTAG=$([ "${DS}" = latents_avp ] && echo avp || echo goa)

# longform sidecar default (CAPTIONS=stored to disable; SIDECAR/PROBS override)
if [ "${CAPTIONS:-longform}" = "longform" ] && [ -z "${SIDECAR:-}" ]; then
  SIDECAR=${CODE}/lumi/${DSTAG}_longform_sidecar.json
  PROBS=${PROBS:-0,0,1}
fi

train() {  # train <savedir>
  local SAVE=$1; shift
  local sc_args=()
  if [ -n "${SIDECAR:-}" ]; then
    sc_args=(--caption_sidecar "${SIDECAR}" --caption_probs "${PROBS:-0.6,0.3,0.1}")
  fi
  python ${CODE}/stable-audio-3/scripts/train_lora.py \
    --model medium-base \
    --encoded_dir ${FLASH}/${DS} \
    --save_dir "${SAVE}" \
    --full-finetune \
    --optimizer fusion \
    --lr 1e-4 --batch_size 2 --accumulate_grad_batches 2 \
    --frames 4096 \
    --epochs 8 --checkpoint_every_epochs 1 \
    --num_workers 6 --seed 1 --no_demos --logger csv \
    --name fullft_${DSTAG}_t4096 \
    "${sc_args[@]}" "$@"
}

RUN=${RUNROOT}/fullft_${DSTAG}_t4096
mkdir -p "${RUN}"
echo "[arm ${ARM}] TRAIN full-ft ${DSTAG} T=4096 BS=2 ga=2 lr=1e-4 bf16 -> ${RUN}"
if train "${RUN}" 2>&1 | tee ${RUN}/train.log; then
  echo "[arm ${ARM}] DONE"
else
  echo "[arm ${ARM}] TRAIN FAILED — see ${RUN}/train.log (siblings unaffected)"
fi
'
echo "[fullft-t4096] all arms finished:" && ls -la "${RUNROOT}"
# SUCCESS: each arm prints its resolved config, the [full-finetune] trainable-params line,
# loss lines tick, one FULL-MODEL ckpt per epoch lands under ${RUNROOT}/fullft_*/.
