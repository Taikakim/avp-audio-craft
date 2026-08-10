#!/bin/bash
# flac_bitrate_ab.sbatch — MP3-bitrate SOURCE-QUALITY A/B (staged 2026-08-05).
# Does the source bitrate of the training audio change SA3 full-FT output quality?
# FIVE arms, one per GCD, on the SAME verified-lossless Goa Dataset tracks encoded at
# {flac, mp3_320, mp3_256, mp3_192, mp3_128}. IDENTICAL seed / captions / recipe /
# frames / precision — the ONLY thing that differs is the source bitrate of the audio
# each arm trains on. Verified-lossless subset comes from the Goa provenance scan
# (goa_dataset_verified_lossless.txt); the FLAC arm is genuine Tidal lossless (Kim
# confirmed), so it is the clean reference the ladder is measured against.
#
# Structure copied EXACTLY from precision_ladder.sbatch (the working multi-GCD
# independent-trainer pattern): each arm is a standalone 1-GCD trainer; the
# SLURM_JOB_NAME=bash + distinct MASTER_PORT=$((29500+GCD)) trick stops the arms
# colliding on one derived DDP rendezvous port (EADDRINUSE); per-GCD /tmp MIOpen +
# Triton dirs stop cache cross-talk. Unlike precision_ladder this uses --data_dir
# (live-encode) because each arm has a DIFFERENT audio corpus — captions are the
# per-clip .txt siblings written by eval/flac_bitrate_transcode.py.
#
# SCALE / COST: 5 arms x full-FT T256 20ep. This is a controlled A/B; a subset
# (~1200 tracks, DESIGN cap) is fine and keeps the 5x transcode + transfer sane.
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=24:00:00
#SBATCH --job-name=sa3_flac_bitrate_ab
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}

# BIGSET_DIR holds the 5 corpus arms produced by flac_bitrate_transcode.py:
#   ${BIGSET_DIR}/flac/  mp3_320/  mp3_256/  mp3_192/  mp3_128/
# each with per-clip .txt captions. rsync it to scratch first (see DESIGN.md).
BIGSET_DIR=${BIGSET_DIR:-${SCRATCH}/data/goa_bitrate_ab}

FRAMES=${FRAMES:-256}; EPOCHS=${EPOCHS:-20}; LR=${LR:-8e-5}; BS=${BS:-4}; SEED=${SEED:-1}

[ -n "${SIF}" ] || { echo "[bitrate] FATAL: no multitorch image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[bitrate] FATAL: ${VENV} missing"; exit 1; }
[ -d "${BIGSET_DIR}" ] || { echo "[bitrate] FATAL: ${BIGSET_DIR} missing (rsync the 5 arms first)"; exit 1; }

# GCD 0..4 -> one bitrate arm each; GCDs 5..7 idle (only 5 arms).
ARM_DIRS=(flac mp3_320 mp3_256 mp3_192 mp3_128)

run_arm () {
  local GCD=$1 ARMDIR=$2
  local NAME=flac_bitrate_ab_t${FRAMES}_${ARMDIR}
  local RUN=${SCRATCH}/runs/flac_bitrate_ab/${NAME}
  local DATA=${BIGSET_DIR}/${ARMDIR}
  [ -d "${DATA}" ] || { echo "[bitrate] WARN: ${DATA} missing, skipping ${ARMDIR}"; return; }
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
# INDEPENDENT 1-GCD trainer: force LightningEnvironment (single-process), not
# SLURMEnvironment which derives ONE DDP port from the shared SLURM_JOB_ID -> all
# arms collide (EADDRINUSE). SLURMEnvironment.detect() returns False when
# SLURM_JOB_NAME is "bash"; distinct MASTER_PORT is the belt-and-suspenders backup.
export SLURM_JOB_NAME=bash MASTER_ADDR=127.0.0.1 MASTER_PORT=$((29500 + '"${GCD}"'))
python ${CODE}/stable-audio-3/scripts/train_lora.py \
    --model medium-base --full-finetune \
    --data_dir "'"${DATA}"'" \
    --save_dir "'"${RUN}"'" \
    --optimizer fusion \
    --use-ema --ema-beta 0.9999 \
    --base_precision fp32 \
    --lr '"${LR}"' --batch_size '"${BS}"' \
    --frames '"${FRAMES}"' --beat-aware-crop \
    --epochs '"${EPOCHS}"' --checkpoint_every_epochs 4 \
    --num_workers 6 --seed '"${SEED}"' --no_demos --logger csv \
    --name '"${NAME}"' 2>&1 | tee -a "'"${RUN}"'"/train.log
' &
}

# ARMS override: rerun a subset after a crash, e.g. ARMS="mp3_192 mp3_128".
ARMS="${ARMS:-flac mp3_320 mp3_256 mp3_192 mp3_128}"
echo "[bitrate] image=${SIF}  bigset=${BIGSET_DIR}  T=${FRAMES} ep=${EPOCHS} lr=${LR} bs=${BS} seed=${SEED}  arms=${ARMS}"
gcd=0
for arm in ${ARMS}; do
  run_arm ${gcd} "${arm}"
  gcd=$((gcd + 1))
done
wait
echo "[bitrate] all arms done:"
ls -d ${SCRATCH}/runs/flac_bitrate_ab/*/ 2>/dev/null
# SUCCESS = 5 run dirs w/ epoch=*.ckpt (EMA weights ride as diffusion_ema.ema_model.*).
# Next: render matched (prompt,seed,cfg) cells from ALL 5 -> same-playhead A/B/X audition
# page; listen for HF detail / transient smear degrading down the bitrate ladder.
