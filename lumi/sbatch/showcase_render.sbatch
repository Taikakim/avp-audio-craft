#!/bin/bash
# showcase_render.sbatch — Kim direct 2026-08-21: "one more render run: t2048 and t4096 clips
# at cfg 5/7/9, w 0.8/1.0/1.2 randomly on known good checkpoints (W's list), prompts from the
# training captions at random. 50 steps, ptm = 8 steps cfg 1. ~128 renders, 1 node x 8 GPUs.
# Record params + prompt + checkpoint per file" — the fun run: a long playlist of our results.
#
# Checkpoint list: lumi/genre_fusion_checkpoints.txt (W top-12-by-PQ, G-transcribed, goa
# families pinned to best-PQ epochs). Units drawn ONCE (fixed rng 20260821) by
# render_showcase.py build; per-clip .json sidecar + fp16 .z0.npy next to every wav.
# Idempotent: re-run to fill gaps (builder skips if units.jsonl exists — same draw).
# RUN: sbatch lumi/sbatch/showcase_render.sbatch
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --gpus-per-task=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=04:00:00
#SBATCH --job-name=showcase
#SBATCH --output=%x-%j.out
#SBATCH --no-requeue
set -uo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${PROJ}/containers/sa3.sif

ROUT=${SCRATCH}/renders/showcase
UNITS=${ROUT}/units.jsonl
mkdir -p ${ROUT}

# build the unit list ONCE (stdlib-only; deterministic — a refill run reuses the same draw)
if [ ! -s "${UNITS}" ]; then
  singularity exec --bind ${PROJ},${SCRATCH},/tmp "${SIF}" \
    python3 ${CODE}/lumi/render_showcase.py build \
      --checkpoints ${CODE}/lumi/genre_fusion_checkpoints.txt \
      --scratch-runs ${SCRATCH}/runs \
      --captions-dir ${CODE}/lumi \
      --out ${UNITS} --n 128 --ranks 8 \
    || { echo "[show] FATAL: unit build failed"; exit 1; }
else
  echo "[show] units.jsonl exists ($(wc -l < ${UNITS}) units) — refill mode"
fi

srun --nodes=1 --ntasks=8 --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -uo pipefail
R=${SLURM_PROCID}
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186
CODE=${PROJ}/code
echo "[r${R}] alive $(hostname) $(date -Is)"
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor
export MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_DISABLE_CACHE=1
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-${R} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-${R}
export TRITON_CACHE_DIR=/tmp/triton-${R}
rm -rf /tmp/miopen-${R} /tmp/triton-${R}; mkdir -p /tmp/miopen-${R} /tmp/triton-${R}
python ${CODE}/lumi/render_showcase.py render \
  --units ${SCRATCH}/renders/showcase/units.jsonl --rank ${R} \
  --out ${SCRATCH}/renders/showcase \
  || echo "[r${R}] render pass FAILED (siblings unaffected)"
echo "[r${R}] done"
'
echo "[show] clips now: $(ls ${ROUT}/show__*.wav 2>/dev/null | wc -l) / $(wc -l < ${UNITS})"
