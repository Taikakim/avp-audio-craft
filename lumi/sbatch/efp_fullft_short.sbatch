#!/bin/bash
# efp_fullft_short.sbatch — Kim FULL fine-tune campaign, short-context arms (2026-07-17).
# One standard-g node, 8 GCDs, 8 independent single-GCD training arms driven by
# SLURM_PROCID. Paste-ready for the EFP Workflows UI (Job Scripts -> workflow).
# Adapted from efp_fp32_compare.sbatch: same cotainr sa3.sif deployment, /code tree,
# PYTHONPATH, MIOpen env, bind set, HF_HUB_OFFLINE, latent staging, arm table, and
# longform-sidecar default. See that file for the full deployment rationale.
#
# DESIGN (Kim direct): FULL fine-tune of the whole 1.4B DiT (--full-finetune: unfreezes
# model.model, injects NO adapter, FusionOpt trains the entire DiT). bf16 (NO
# --base_precision), --optimizer fusion, lr 1e-4, 8 epochs, ckpt every epoch. PER-DATASET
# (never combined): each arm trains ONE dataset via --encoded_dir. Arms sweep context
# length T at a fixed batch 4 (fits per the VRAM table below); crops are beat-aware from
# the stored T=4096 latents. Arms:
#   PROCID 0: avp  T=256   BS=4  lr 1e-4
#   PROCID 1: goa  T=256   BS=4  lr 1e-4
#   PROCID 2: avp  T=512   BS=4  lr 1e-4
#   PROCID 3: goa  T=512   BS=4  lr 1e-4
#   PROCID 4: avp  T=1024  BS=4  lr 1e-4
#   PROCID 5: goa  T=1024  BS=4  lr 1e-4
#   PROCID 6: avp  T=2048  BS=4  lr 1e-4
#   PROCID 7: goa  T=2048  BS=4  lr 1e-4
#
# VRAM (bf16 full-ft, 64 GB GCD): batch 4 fits T=256/512/1024/2048 with headroom. T=4096
# batch 4 is tight (~55 GB) so it lives in the sibling script efp_fullft_t4096.sbatch
# (small-g, batch 2 + grad-accum 2). No batch probe here — batch 4 is fixed and known-good
# for these lengths, so each arm trains directly.
#
# CAPTIONS (Kim direct 2026-07-14, inherited from fp32): DEFAULT = the definitive longform
# sidecars (SIDECAR=${CODE}/lumi/${DSTAG}_longform_sidecar.json), PROBS=0,0,1 trains
# pure-longform. To train on the datasets stored prompts instead, submit with
# CAPTIONS=stored.
#
# EPOCHS/WALLTIME: 8 epochs, ckpt every epoch. The T=2048 arms are the slow ones; per-epoch
# checkpoints make partial completion useful if an arm hits the 47 h wall. BILLING: whole
# node x walltime; arms that finish early idle their GCD (acceptable for one campaign).
#
# PREREQS: code+SIF+models pre-staged PLUS latents_avp.tar.gz and latents_sa3.tar.gz on
# ${SCRATCH} (Kim rsync) and the code tarball refreshed so scripts/train_lora.py carries
# the --full-finetune flag.
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=47:00:00
#SBATCH --job-name=sa3_fullft_short
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
echo "[fullft-short] avp latents: $(ls ${FLASH}/latents_avp/*.npy 2>/dev/null | wc -l)  goa latents: $(ls ${FLASH}/latents_sa3/*.npy 2>/dev/null | wc -l)"

# per-arm launcher: everything below runs once per task inside the container.
# --nodes pinned: the EFP form controls the allocation and can oversize it;
# all 8 arms must land on ONE node 8 GCDs.
srun --nodes=1 --ntasks=8 --gpus-per-task=1 --cpus-per-task=7 \
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
  0) DS=latents_avp; T=256  ;;
  1) DS=latents_sa3; T=256  ;;
  2) DS=latents_avp; T=512  ;;
  3) DS=latents_sa3; T=512  ;;
  4) DS=latents_avp; T=1024 ;;
  5) DS=latents_sa3; T=1024 ;;
  6) DS=latents_avp; T=2048 ;;
  7) DS=latents_sa3; T=2048 ;;
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
    --lr 1e-4 --batch_size 4 \
    --frames ${T} --beat-aware-crop \
    --epochs 8 --checkpoint_every_epochs 1 \
    --num_workers 6 --seed 1 --no_demos --logger csv \
    --name fullft_${DSTAG}_t${T} \
    "${sc_args[@]}" "$@"
}

RUN=${RUNROOT}/fullft_${DSTAG}_t${T}
mkdir -p "${RUN}"
echo "[arm ${ARM}] TRAIN full-ft ${DSTAG} T=${T} BS=4 lr=1e-4 bf16 -> ${RUN}"
if train "${RUN}" 2>&1 | tee ${RUN}/train.log; then
  echo "[arm ${ARM}] DONE"
else
  echo "[arm ${ARM}] TRAIN FAILED — see ${RUN}/train.log (siblings unaffected)"
fi
'
echo "[fullft-short] all arms finished:" && ls -la "${RUNROOT}"
# SUCCESS: each arm prints its resolved config, the [full-finetune] trainable-params line,
# loss lines tick, one FULL-MODEL ckpt per epoch lands under ${RUNROOT}/fullft_*/.
