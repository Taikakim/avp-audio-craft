#!/bin/bash
# fullft_mixed_render.sbatch — STANDARD (20s) render of the mixed avp+goa T4096 flagship run's
# latest ckpt (CONTINUITY 2026-08-15). Sibling of fullft_bigset_render.sbatch / fullft_avp_render.sbatch.
# fullft_mixed_avp_goa_t4096.sbatch TRAINS ONLY (no render tail), so its ckpts have no clips.
# This renders the newest fat ckpt into renders/matrix_cells as label `fullft_mixed_avp_goa_t4096`.
#
# ── CLIP-PROVENANCE / NO-MIX-UP (same rule as fullft_avp_render.sbatch, Kim direct 2026-08-09) ──
# THREE full-FTs now share renders/matrix_cells (goa big-FT `fullft_bigset`, AVP aug×8
# `fullft_avp_aug`, this mixed T4096 run). Cells are keyed only by LABEL prefix, so RUN + LABEL
# are HARD-PINNED here (not env-overridable) to prevent silent cross-run overwrite.
#
# CRITICAL: trained --use-ema → render the EMA SHADOW via --use-ema. --fullft forces the
# whole-model load path. STANDARD length = no --frames (=20s) — a quick ep0 sanity check, not
# the native T4096/380s pass.
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=02:00:00
#SBATCH --job-name=sa3_mixed_render
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}
RUN=${SCRATCH}/runs/fullft_mixed_avp_latents_sa3_t4096
SNAP=${CODE}/lumi/matrix_prompts_snapshot.json
ROUT=${SCRATCH}/renders/matrix_cells
CFGS=${CFGS:-1,7,16}
LABEL=fullft_mixed_avp_goa_t4096   # HARD-PINNED — do NOT make env-overridable (no cross-corpus mislabel)
NLAST=${NLAST:-1}   # render the newest N fat ckpts (bump to backfill a tail)
FORCE=${FORCE:-}    # FORCE=1 -> re-render cells even if the .wav exists (changed code/ckpt)

[ -n "${SIF}" ] || { echo "[mixed-render] FATAL: no multitorch image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[mixed-render] FATAL: ${VENV} missing"; exit 1; }
[ -f "${SNAP}" ] || { echo "[mixed-render] FATAL: prompt snapshot missing: ${SNAP}"; exit 1; }
mapfile -t CKPTS < <(ls "${RUN}"/epoch=*.ckpt 2>/dev/null | grep -v "\.weights\.ckpt$" | sort -V | tail -n "${NLAST}")
[ "${#CKPTS[@]}" -gt 0 ] || { echo "[mixed-render] FATAL: no fat ckpt in ${RUN}"; exit 1; }
mkdir -p "${ROUT}"
echo "[mixed-render] rendering ${#CKPTS[@]} ckpt(s) as label=${LABEL}: ${CKPTS[*]}"

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
  echo "[mixed-render] ep${EP} (EMA) <- ${CK}"
  python ${CODE}/lumi/render_matrix_cells.py \
      --label '"${LABEL}"' --tag ep${EP} \
      --ckpt "${CK}" --fullft --use-ema '"${FORCE:+--force}"' \
      --prompts '"${SNAP}"' --out '"${ROUT}"' \
      --only-cfgs '"${CFGS}"' --strengths 1.0 \
    || echo "[mixed-render] ep${EP} render FAILED (non-fatal)"
done
'
echo "[mixed-render] done. cells:"; ls "${ROUT}"/${LABEL}__* 2>/dev/null | wc -l
