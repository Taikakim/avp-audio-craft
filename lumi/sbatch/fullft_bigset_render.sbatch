#!/bin/bash
# fullft_bigset_render.sbatch — STANDARD (20s) render of the big-FT #68 run's latest ckpt
# (CONTINUITY 2026-08-07). fullft_bigset.sbatch TRAINS ONLY (no render tail), so #68's ckpts
# have no clips. This renders the newest fat ckpt into renders/matrix_cells as label
# `fullft_bigset` so it lands on the audit board next to the other fullft_* models. Re-run this
# whenever a newer ckpt lands (every 4 ep) to audition training progress.
#
# CRITICAL: #68 trained --use-ema → render the EMA SHADOW (diffusion_ema.ema_model.*), not the
# online weights → render_matrix_cells --use-ema. --fullft forces the whole-model load path
# (label isn't 'fullft_*'... it IS here, but pass it explicitly to be safe). STANDARD length =
# no --frames (=20s, DURATION); --frames is NATIVE/long-form mode, a separate pass.
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=02:00:00
#SBATCH --job-name=sa3_bigset_render
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}
RUN=${SCRATCH}/runs/fullft_bigset
SNAP=${CODE}/lumi/matrix_prompts_snapshot.json
ROUT=${SCRATCH}/renders/matrix_cells
CFGS=${CFGS:-1,7,16}
LABEL=${LABEL:-fullft_bigset}
NLAST=${NLAST:-1}   # render the newest N fat ckpts (bump to backfill a tail)

[ -n "${SIF}" ] || { echo "[bigset-render] FATAL: no multitorch image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[bigset-render] FATAL: ${VENV} missing"; exit 1; }
[ -f "${SNAP}" ] || { echo "[bigset-render] FATAL: prompt snapshot missing: ${SNAP}"; exit 1; }
mapfile -t CKPTS < <(ls "${RUN}"/epoch=*.ckpt 2>/dev/null | grep -v "\.weights\.ckpt$" | sort -V | tail -n "${NLAST}")
[ "${#CKPTS[@]}" -gt 0 ] || { echo "[bigset-render] FATAL: no fat ckpt in ${RUN}"; exit 1; }
mkdir -p "${ROUT}"
echo "[bigset-render] rendering ${#CKPTS[@]} ckpt(s): ${CKPTS[*]}"

srun --exclusive -N1 -n1 --gpus=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -euo pipefail
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; CODE=${PROJ}/code
source '"${VENV}"'/bin/activate
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor${PYTHONPATH:+:${PYTHONPATH}}
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-r MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-r
export TRITON_CACHE_DIR=/tmp/triton-r PYTORCH_TUNABLEOP_ENABLED=0
rm -rf /tmp/miopen-r /tmp/triton-r; mkdir -p /tmp/miopen-r /tmp/triton-r
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True
for CK in '"${CKPTS[*]}"'; do
  EP=$(basename "${CK}" | grep -oE "epoch=[0-9]+" | grep -oE "[0-9]+")
  echo "[bigset-render] ep${EP} (EMA) <- ${CK}"
  python ${CODE}/lumi/render_matrix_cells.py \
      --label '"${LABEL}"' --tag ep${EP} \
      --ckpt "${CK}" --fullft --use-ema \
      --prompts '"${SNAP}"' --out '"${ROUT}"' \
      --only-cfgs '"${CFGS}"' --strengths 1.0 \
    || echo "[bigset-render] ep${EP} render FAILED (non-fatal)"
done
'
echo "[bigset-render] done. cells:"; ls "${ROUT}"/${LABEL}__* 2>/dev/null | wc -l
