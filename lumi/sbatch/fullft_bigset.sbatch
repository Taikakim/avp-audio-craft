#!/bin/bash
# fullft_bigset.sbatch — the #68 big-set FULL FINETUNE (Kim's chosen single config, 2026-08-03/04).
# full-FT (all 1.4B DiT) + fp32 + T2048 + bs4 + FusionOpt(all-on) + EMA + lr 8e-5 + 40ep, on the
# curated big goa set via LIVE-ENCODE (--data_dir -> in-loop SAME encode) with per-batch waveform
# AUGMENTATION (--augment: sub-frame phase shift + gain + stereo). Multitorch image (ROCm7+FA2).
#
# ⛔ TWO BLOCKERS before this runs (both tracked):
#   1. CAPTION SIDECAR (G's corpus assembly): a T1/T2/T3 sidecar for the big set, keyed to the audio
#      paths, at ${BIGSET_SIDECAR}. Fed to train_lora's caption sampler (make_caption_sampler already
#      has dropout/case/shuffle/track_type + a key_fn for the --data_dir path).
#   2. CONFIG from fullft_mem_probe.sbatch: confirm fp32/T2048/bs4 FITS on 1 GCD. If it OOM'd, step
#      down here to match (batch_size / frames / base_precision) — the probe verdict sets these.
#   Plus: this uses 8-GCD DDP (one model, data-parallel) — VERIFY train_lora drives Lightning DDP
#   across 8 GCDs cleanly (the melody-wall grids ran N *independent* 1-GCD trainers; DDP is different).
#   Do a 1-epoch --steps 40 smoke first.
#
# Overridable: BIGSET_DIR (audio dir with filelist.txt), BIGSET_SIDECAR, BS, FRAMES, PREC, EPOCHS.
# The everything-vs-dedup comparison = swap BIGSET_DIR's filelist (all vs role-filtered); +kl-shampoo
# arm = add --fusion-shampoo on its own node; +sin-snake arm = separate (needs the config-flag wiring).
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=48:00:00
#SBATCH --job-name=sa3_fullft_bigset
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}
BIGSET_DIR=${BIGSET_DIR:-${SCRATCH}/goa_archive}                 # TODO: point at the curated keep-set (filelist.txt inside)
# Sidecar BUILT 2026-08-04 (23231 entries, RELPATH-keyed, t1/t2/t3). Stage the 54MB file to SCRATCH:
#   rsync .../goa_archive_features/goa_archive_caption_sidecar.json -> ${SCRATCH}/goa_caption_sidecar.json
# ⚠️ KEY CONTRACT (G to verify before the big run): the sidecar keys are FULL relpaths+.mp3, but the
# --data_dir caption path uses caption_metadata_fn (reads per-clip .txt), NOT make_caption_sampler with
# a relpath key_fn. A mismatch = ALL captions silently dropped -> caption-less training. Confirm the
# --data_dir sampler consults THIS sidecar via a relpath key_fn (matching BIGSET_DIR-relative paths).
BIGSET_SIDECAR=${BIGSET_SIDECAR:-${SCRATCH}/goa_caption_sidecar.json}
BS=${BS:-4}; FRAMES=${FRAMES:-2048}; PREC=${PREC:-fp32}; EPOCHS=${EPOCHS:-40}; CKEVERY=${CKEVERY:-4}
RUNTAG=${RUNTAG:-}
# SMOKE=1 -> --steps 40 (NOT a full epoch): verifies 8-GCD DDP + live-encode --data_dir + augment
# wire up in minutes before the ~1-day full run. train_lora ignores --steps when --epochs is set, so
# smoke passes ONLY --steps. Modest arm example: --export=ALL,FRAMES=256,EPOCHS=10,RUNTAG=t256_10ep
if [ "${SMOKE:-0}" = "1" ]; then
  RUNTAG="${RUNTAG:-smoke}"; EPOCHARG="--steps 40"; echo "[fullft] SMOKE MODE: --steps 40 (DDP+pipeline verify)"
else
  EPOCHARG="--epochs ${EPOCHS} --checkpoint_every_epochs ${CKEVERY}"
fi
NAME=fullft_bigset${RUNTAG:+_${RUNTAG}}
RUN=${SCRATCH}/runs/${NAME}
mkdir -p "${RUN}"

[ -n "${SIF}" ] || { echo "[fullft] FATAL: no lumi-multitorch-full image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[fullft] FATAL: ${VENV} missing"; exit 1; }
[ -d "${BIGSET_DIR}" ] || { echo "[fullft] FATAL: BIGSET_DIR ${BIGSET_DIR} missing"; exit 1; }
[ -f "${BIGSET_DIR}/filelist.txt" ] || { echo "[fullft] FATAL: ${BIGSET_DIR}/filelist.txt missing (curated audio list)"; exit 1; }
[ -f "${BIGSET_SIDECAR}" ] || { echo "[fullft] FATAL: caption sidecar ${BIGSET_SIDECAR} missing (BLOCKER #1 — G's corpus)"; exit 1; }
grep -q -- "--augment" "${CODE}/stable-audio-3/scripts/train_lora.py" || { echo "[fullft] FATAL: train_lora missing --augment (code refresh)"; exit 1; }

echo "[fullft] image=${SIF}  BS=${BS} FRAMES=${FRAMES} PREC=${PREC} EPOCHS=${EPOCHS}"
echo "[fullft] audio=${BIGSET_DIR} ($(wc -l < ${BIGSET_DIR}/filelist.txt) files)  sidecar=${BIGSET_SIDECAR}"

# 8-GCD DDP: one model data-parallel across the node. Lightning drives it from the SLURM env.
srun --nodes=1 --ntasks=8 --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -euo pipefail
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; CODE=${PROJ}/code
RUN='"${RUN}"'
VENV='"${VENV}"'
source ${VENV}/bin/activate
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${VENV}/lib/python3.12/site-packages:${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor${PYTHONPATH:+:${PYTHONPATH}}
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-${SLURM_PROCID} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-${SLURM_PROCID}
export TRITON_CACHE_DIR=/tmp/triton-${SLURM_PROCID} PYTORCH_TUNABLEOP_ENABLED=0
rm -rf /tmp/miopen-${SLURM_PROCID} /tmp/triton-${SLURM_PROCID}; mkdir -p /tmp/miopen-${SLURM_PROCID} /tmp/triton-${SLURM_PROCID}
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True

FATCKPT=$(ls "${RUN}"/epoch=*.ckpt 2>/dev/null | grep -v "\.weights\.ckpt$" | sort -V | tail -1 || true)
RESUME=""; [ -n "${FATCKPT}" ] && RESUME="--resume_ckpt ${FATCKPT}"

# shm-crash fix (2026-08-06): train_lora now uses the file_system tensor-sharing strategy
# (shares via /tmp, not /dev/shm) so 8 ranks x 6 workers x live-encode no longer exhaust
# /dev/shm; raise the open-file limit since file_system opens one fd per shared tensor.
ulimit -n 131072 2>/dev/null || ulimit -n 65536 2>/dev/null || true

python ${CODE}/stable-audio-3/scripts/train_lora.py \
    --model medium-base --full-finetune \
    --data_dir '"${BIGSET_DIR}"' \
    --caption_sidecar '"${BIGSET_SIDECAR}"' --caption_probs 0.3,0.4,0.3 \
    --augment \
    --save_dir "${RUN}" \
    --optimizer fusion \
    --use-ema --ema-beta 0.9999 \
    --base_precision '"${PREC}"' \
    --lr 8e-5 --batch_size '"${BS}"' \
    --frames '"${FRAMES}"' --beat-aware-crop \
    ${RESUME} \
    '"${EPOCHARG}"' \
    --num_workers 6 --seed 1 --no_demos --logger csv \
    --name '"${NAME}"' 2>&1 | tee -a ${RUN}/train.log
'
echo "[fullft] ckpts:"; ls "${RUN}"/epoch=*.ckpt 2>/dev/null | grep -cv weights || true
# SUCCESS = ckpt count + train_loss in csv. EMA weights ride the ckpt as diffusion_ema.ema_model.*
# (render must load the EMA set — see stable-audio-3/CLAUDE.md).
# RENDER: this script TRAINS ONLY. For standard 20s audition cells, run
#   lumi/sbatch/fullft_bigset_render.sbatch  (renders the newest ckpt with
#   render_matrix_cells --fullft --use-ema; re-run it as new ckpts land every 4 ep).
