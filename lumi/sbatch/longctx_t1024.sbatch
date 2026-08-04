#!/bin/bash
# longctx_t1024.sbatch — task #50 goa long-context arm, T=1024 (95.108 s). Standard train_lora
# on the goa latents (latents_sa3), LoRA rank 128 / alpha 128 (s=1), lr 1e-4, 8 epochs.
# The LOCAL box tops out here (crop 94s ≈ T1012 was the local arm); LUMI runs the exact
# multiple-of-256 T=1024 and the T=2048 sibling the local card can't hold.
#
# HYPOTHESIS: a longer training crop teaches longer-range musical structure than the T=512
# grid — the adapter should carry phrase/section coherence the short-crop runs miss. Paired
# with longctx_t2048 to trace how the structure horizon scales with crop length.
#
# FRAMES RULE (Kim DIRECT 2026-07-13, MASTER §5): crops are specified in FRAMES = multiples of
# 256, NOT seconds — --frames dodges the seconds->ds-ratio rounding that made T ragged.
# T=1024 = 95.108 s exactly. VERIFY the trainer logs T=1024 (not 1023/1025) on the first batch
# before letting it run the night.
#
# ── run knobs (override via --export=ALL,KEY=VAL) ────────────────────────────────
#   ENC      encoded latent dir under ${SA3_DATA} (default latents_sa3 = goa)
#   RANK     LoRA rank (default 128)
#   ALPHA    lora_alpha (default 128 = rank → s=1)
#   LR       learning rate (default 1e-4)
#   EPOCHS   epochs (default 8; ckpt every epoch — compare across the run, MASTER §4)
#   BS       batch size (default 16; T=1024 is 2× the T=512 seq → half the T512 batch of 32)
#   NAME     run name / save subdir (default longctx_t1024_r${RANK})
#
# WALLCLOCK ESTIMATE: ~5400 goa crops / BS 16 ≈ 337 steps/epoch × 8 ≈ 2700 steps at T=1024
# (~1.5–2 s/step on 1 GCD) ≈ 1–1.5 h + model load. --time 10:00:00 for MIOpen-compile headroom.
# INDEPENDENT of the arc_* jobs — can run concurrently on another GCD.
#
# NOTE (air-gap): medium-base + T5-Gemma PRE-STAGED under ${SA3_MODELS} (HF_HUB_OFFLINE=1).
#
#SBATCH --account=project_465003186
#SBATCH --partition=small-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=60G
#SBATCH --time=10:00:00
#SBATCH --job-name=longctx-t1024
#SBATCH --output=%x-%j.out

# PORTED 2026-07-16 to the proven smoke/fp32 deployment: cotainr sa3.sif, /code tree,
# vendored FusionOpt, MIOPEN_DISABLE_CACHE + /tmp bind. Was written 07-13 against a
# sa3-train.sif/env_lumi.sh layout that never materialized. dora-rows + fusion (not plain
# lora) to match the validated goa recipe + the reverb-clean baseline sa3-goa-dora-47s-r128-fusion.
set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
SIF=${PROJ}/containers/sa3.sif
MODELS=${PROJ}/models

ENC=${ENC:-latents_sa3}
RANK=${RANK:-128}
ALPHA=${ALPHA:-128}
LR=${LR:-1e-4}
EPOCHS=${EPOCHS:-8}
BS=${BS:-16}
NAME=${NAME:-longctx_t1024_r${RANK}}
RUN=${SCRATCH}/runs/${NAME}
DATA=${FLASH}/${ENC}
mkdir -p "${RUN}"

# stage goa latents to NVMe once (idempotent; the fp32 campaign likely already staged these)
if [ ! -d "${DATA}" ]; then
  mkdir -p "${DATA}"
  tar -xzf "${SCRATCH}/${ENC}.tar.gz" -C "${DATA}" --strip-components=1
fi
echo "[longctx] ${ENC} latents: $(ls ${DATA}/*.npy 2>/dev/null | wc -l)"

srun --nodes=1 --ntasks=1 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c "
  set -euo pipefail
  export HF_HOME=${MODELS} HF_HUB_OFFLINE=1
  export PYTHONPATH=${CODE}/stable-audio-3:${CODE}/lumi/vendor
  # MIOpen kernel-cache SQLite open fails on every LUMI filesystem -> disable it. /tmp bound above.
  export MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_DISABLE_CACHE=1
  export MIOPEN_USER_DB_PATH=/tmp/miopen-\${SLURM_JOB_ID:-0} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-\${SLURM_JOB_ID:-0}
  rm -rf \${MIOPEN_USER_DB_PATH}; mkdir -p \${MIOPEN_USER_DB_PATH}
  export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
  python -c 'import torch; print(\"[longctx] GPU:\", torch.cuda.is_available(), \"count:\", torch.cuda.device_count())'
  cd ${CODE}/stable-audio-3
  python scripts/train_lora.py \
    --model medium-base \
    --encoded_dir ${DATA} \
    --save_dir ${RUN} \
    --adapter_type dora-rows --rank ${RANK} --lora_alpha ${ALPHA} \
    --optimizer fusion \
    --lr ${LR} --batch_size ${BS} \
    --frames 1024 --beat-aware-crop \
    --epochs ${EPOCHS} --checkpoint_every_epochs 1 \
    --num_workers 6 --seed 1 --no_demos --logger csv \
    --name ${NAME} \
    2>&1 | tee ${RUN}/train.log
"
echo "[longctx] DONE" && ls -la "${RUN}"
