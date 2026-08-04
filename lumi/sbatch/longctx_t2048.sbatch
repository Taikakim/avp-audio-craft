#!/bin/bash
# longctx_t2048.sbatch — task #50 goa long-context arm, T=2048 (190.216 s). LUMI-ONLY: the
# local 16 GB card cannot hold a T=2048 medium crop (the local arm stopped at T≈1012); the
# MI250X's 64 GB/GCD is what makes this rung reachable. Standard train_lora on goa latents
# (latents_sa3), LoRA rank 128 / alpha 128 (s=1), lr 1e-4, 8 epochs.
#
# HYPOTHESIS: T=2048 doubles the training horizon again — if section-level structure keeps
# improving from T=1024→2048, the adapter's coherence ceiling is crop-length-bound, not
# architecture-bound. If it plateaus, T=1024 is the sweet spot. This is the top of the ladder.
#
# FRAMES RULE (Kim DIRECT 2026-07-13, MASTER §5): --frames = multiples of 256, NOT seconds.
# T=2048 = 190.216 s exactly. VERIFY the trainer logs T=2048 (not 2047/2049) on the first batch.
#
# ── run knobs (override via --export=ALL,KEY=VAL) ────────────────────────────────
#   ENC      encoded latent dir under ${SA3_DATA} (default latents_sa3 = goa)
#   RANK     LoRA rank (default 128)
#   ALPHA    lora_alpha (default 128 = rank → s=1)
#   LR       learning rate (default 1e-4)
#   EPOCHS   epochs (default 8; ckpt every epoch — compare across the run, MASTER §4)
#   BS       batch size (default 8; T=2048 is 4× the T=512 seq → quarter the T512 batch of 32.
#            Watch the first-epoch VRAM high-water mark; drop to 4 if it nears 64 GB.)
#   NAME     run name / save subdir (default longctx_t2048_r${RANK})
#
# WALLCLOCK ESTIMATE: ~5400 goa crops / BS 8 ≈ 675 steps/epoch × 8 ≈ 5400 steps at T=2048
# (~2–3 s/step on 1 GCD, 4× attention vs T512) ≈ 3–4.5 h + model load. --time 16:00:00 for
# headroom. INDEPENDENT of the arc_* and t1024 jobs — can run concurrently on another GCD.
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
#SBATCH --time=16:00:00
#SBATCH --job-name=longctx-t2048
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
BS=${BS:-8}
NAME=${NAME:-longctx_t2048_r${RANK}}
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
    --frames 2048 --beat-aware-crop \
    --epochs ${EPOCHS} --checkpoint_every_epochs 1 \
    --num_workers 6 --seed 1 --no_demos --logger csv \
    --name ${NAME} \
    2>&1 | tee ${RUN}/train.log
"
echo "[longctx] DONE" && ls -la "${RUN}"
