#!/bin/bash
# precision_ladder.sbatch — the fp32 / bf16-mixed / fp16-mixed FORMAT ladder (CONTINUITY 2026-08-04).
# All 3 keep an fp32 MASTER (FusionOpt Schedule-Free clones z/x to .float()), so the F/Gemini
# weight round-away NEVER occurs here — Stochastic Rounding is moot on this optimizer (it's the
# separate DESKTOP deliverable). What actually varies is COMPUTE precision, so we test FORMATS:
#
# THREE-RUNG FORMAT LADDER (see stable-audio-3/CLAUDE.md precision section + WORKLOG 2026-08-04):
#   fp32       (32-true)  : fp32 compute + fp16 attention core (10 mantissa bits) — quality ceiling
#   bf16-mixed (16-mixed?): fp32 master + bf16 AUTOCAST compute + bf16 attn core (7 bits)
#   fp16-mixed (16-mixed) : fp32 master + fp16 AUTOCAST compute + fp16 attn core (10 bits) + GradScaler
# Why fp16-mixed is the interesting rung: the WINNING fp32 arm's attention was already fp16 (the flash
# cast) — so fp16-mixed MATCHES the winner's attention precision AND upgrades all compute to 10 mantissa
# bits (8x finer than bf16's 7). If the audible fp32>bf16 gap is the bf16-attn (Qiu 2510.04212) bias,
# fp16-mixed should recover most of it at 16-bit cost. Forward is proven fine in fp16 (our whole eval
# corpus renders in fp16); the only fp16 risk is small-gradient UNDERFLOW, which Lightning's 16-mixed
# GradScaler (loss-scaling) handles automatically. fp16-mixed vs bf16-mixed = directly "is fp16 or bf16
# better for us"; fp16-mixed vs fp32 = "does the more-precise 16-bit format recover the fp32 sound".
#
# 3 arms, one per GCD, IDENTICAL seed/data/caption — ONLY --base_precision differs. Modest per Kim's
# lightweight-first method: full-FT, T256, 10 epochs, FusionOpt (KL-Shampoo OFF), EMA on. Pre-encoded
# latents (no live-encode aug) = clean precision contrast. Score: melody-recurrence + Kim's ear.
# SCALE-UP: promote each arm to its own 8-GCD DDP node at the big-FT config (T2048/40ep) if the probe
# shows a real gap — same args, --export the FRAMES/EPOCHS + move to 3 nodes (fullft_bigset pattern).
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=3
#SBATCH --ntasks-per-node=3
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=12:00:00
#SBATCH --job-name=sa3_precision_ladder
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}
# goa_longform_sidecar.json = the STEM-keyed sidecar (000000 -> t1/t2/t3) that matches the numeric
# latents_sa3 filenames (proven by the melody-wall grids). The new 23k goa_caption_sidecar.json is
# RELPATH-keyed for the --data_dir live-encode big-FT (#68), so it does NOT match --encoded_dir here.
# Caption regime is irrelevant to a precision ISOLATE (identical across all 3 arms); t1/t2/t3 at 0.3/0.4/0.3.
SIDECAR=${SIDECAR:-${CODE}/lumi/goa_longform_sidecar.json}
PROBS=${PROBS:-0.3,0.4,0.3}
FRAMES=${FRAMES:-256}; EPOCHS=${EPOCHS:-10}; LR=${LR:-8e-5}; BS=${BS:-4}; SEED=${SEED:-1}

[ -n "${SIF}" ] || { echo "[prec] FATAL: no multitorch image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[prec] FATAL: ${VENV} missing"; exit 1; }

# stage pre-encoded latents to FLASH (fast local NVMe) once, like the melody-wall grids
if [ ! -d "${FLASH}/latents_sa3" ]; then
  mkdir -p "${FLASH}/latents_sa3"
  tar -xzf "${SCRATCH}/latents_sa3.tar.gz" -C "${FLASH}/latents_sa3" --strip-components=1
fi

# arm 0 -> fp32 (32-true) ; arm 1 -> bf16-mixed ; arm 2 -> fp16-mixed (10-bit + GradScaler)
PRECS=(fp32 bf16-mixed fp16-mixed)

run_arm () {
  local GCD=$1 PREC=$2
  local NAME=precision_ladder_t${FRAMES}_${PREC/-/}
  local RUN=${SCRATCH}/runs/precision_ladder/${NAME}
  mkdir -p "${RUN}"
  ROCR_VISIBLE_DEVICES=${GCD} srun --exclusive -N1 -n1 --gpus=1 --cpus-per-task=7 \
    singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -euo pipefail
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; FLASH=/flash/project_465003186; CODE=${PROJ}/code
source '"${VENV}"'/bin/activate
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor${PYTHONPATH:+:${PYTHONPATH}}
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-'"${GCD}"' MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-'"${GCD}"'
export TRITON_CACHE_DIR=/tmp/triton-'"${GCD}"' PYTORCH_TUNABLEOP_ENABLED=0
rm -rf /tmp/miopen-'"${GCD}"' /tmp/triton-'"${GCD}"'; mkdir -p /tmp/miopen-'"${GCD}"' /tmp/triton-'"${GCD}"'
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True
# Each arm is an INDEPENDENT 1-GCD trainer. Force Lightning to use LightningEnvironment (single-
# process), NOT SLURMEnvironment — which derives ONE DDP rendezvous port from the shared SLURM_JOB_ID,
# so all 3 arms collide on it (EADDRINUSE). PL SLURMEnvironment.detect() returns False when
# SLURM_JOB_NAME is "bash"/"interactive"; distinct MASTER_PORT is a belt-and-suspenders backup.
export SLURM_JOB_NAME=bash MASTER_ADDR=127.0.0.1 MASTER_PORT=$((29500 + '"${GCD}"'))
python ${CODE}/stable-audio-3/scripts/train_lora.py \
    --model medium-base --full-finetune \
    --encoded_dir ${FLASH}/latents_sa3 \
    --caption_sidecar "'"${SIDECAR}"'" --caption_probs "'"${PROBS}"'" \
    --save_dir "'"${RUN}"'" \
    --optimizer fusion \
    --use-ema --ema-beta 0.9999 \
    --base_precision '"${PREC}"' \
    --lr '"${LR}"' --batch_size '"${BS}"' \
    --frames '"${FRAMES}"' --beat-aware-crop \
    --epochs '"${EPOCHS}"' --checkpoint_every_epochs 2 \
    --num_workers 6 --seed '"${SEED}"' --no_demos --logger csv \
    --name '"${NAME}"' 2>&1 | tee -a "'"${RUN}"'"/train.log
' &
}

# ARMS override: rerun a subset after a crash, e.g. ARMS="bf16-mixed fp16-mixed". Default = all 3.
ARMS="${ARMS:-fp32 bf16-mixed fp16-mixed}"
echo "[prec] image=${SIF}  T=${FRAMES} ep=${EPOCHS} lr=${LR} bs=${BS} seed=${SEED}  arms=${ARMS}"
gcd=0
for prec in ${ARMS}; do
  run_arm ${gcd} "${prec}"
  gcd=$((gcd + 1))
done
wait
echo "[prec] both arms done:"
ls -d ${SCRATCH}/runs/precision_ladder/*/ 2>/dev/null
# SUCCESS = 2 run dirs w/ epoch=*.ckpt (EMA weights ride as diffusion_ema.ema_model.*).
# NOTE: this script TRAINS ONLY — it does NOT render clips. To get auditionable cells + the PREC
# A/B, run  lumi/sbatch/precision_ladder_render.sbatch  after (renders each arm's final ckpt with
# render_matrix_cells --fullft --use-ema; EMA is mandatory since the arms trained --use-ema).
# Next: those cells -> melody_wall_analysis.py whitened-chroma recurrence A/B -> PREC= verdict.
