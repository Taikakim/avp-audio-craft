#!/bin/bash
# efp_base_native_grid.sbatch — native-length (T=4096 / 380s) reference grids for the two
# UN-adapted models (Kim direct 2026-07-24). The 20s grids for base + base_ptm already exist
# on the board; this adds their NATIVE-length counterparts, which cannot render on the local
# 16GB display card (T>=2048 crash rule) -> LUMI.
#
#   base      (medium-base):  cfg {1,7,16} x weight {1.0,1.5,2.0}  steps 24   = 9 cells x 18 prompts
#   base_ptm  (post-trained "medium", rf_denoiser/ping-pong): cfg 1 x weight {1,1.5,2} steps 8
#                                                              (PT-native config) = 3 cells x 18 prompts
#   => 162 + 54 = 216 native clips @ T=4096 (380.4s).
#
# Renderer: lumi/render_matrix_cells.py (extended 2026-07-24 with --frames/--steps/--pt-medium/
# --only-cfgs). --frames 4096 pins sample_size=4096*4096 so generate() renders the FULL native
# context, NOT the 120s/1292-frame default (the LUMI 2026-07-22 native-cell bug). Filenames carry
# __d380 (+__st8 for ptm) so they land as SIBLINGS of the 20s cells, never overwrites.
#
# 8 GCDs filled by splitting (model, cfg, strength) — no prompt-sharding needed:
#   0 base cfg1  w1.0        4 base cfg16 w1.0
#   1 base cfg1  w1.5,2.0    5 base cfg16 w1.5,2.0
#   2 base cfg7  w1.0        6 base_ptm cfg1 w1.0,1.5   (--pt-medium --steps 8)
#   3 base cfg7  w1.5,2.0    7 base_ptm cfg1 w2.0       (--pt-medium --steps 8)
#
# PREREQ: SIF + models + code on ${PROJ}; matrix_prompts_snapshot.json on ${CODE}/lumi. No latents.
# Ships with the extended render_matrix_cells.py (refresh code first). Plan: chat 2026-07-24.
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=06:00:00
#SBATCH --job-name=sa3_base_native_grid
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
CODE=${PROJ}/code
SIF=${PROJ}/containers/sa3.sif
MODELS=${PROJ}/models
ROUT=${SCRATCH}/renders/native_cells
mkdir -p "${ROUT}"

srun --nodes=1 --ntasks=8 --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},/tmp "${SIF}" bash -c '
set -euo pipefail
ARM=${SLURM_PROCID}
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
CODE=${PROJ}/code
ROUT=${SCRATCH}/renders/native_cells

export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${CODE}/stable-audio-3:${CODE}/lumi/vendor:${CODE}/control
# ^ control/ is REQUIRED: render_matrix_cells imports sa3_control.audio_io. Eval-render jobs
# died on ModuleNotFoundError: sa3_control when it was missing (LUMI job 20190736). The renderer
# now also self-adds ../control, but keep it here as belt-and-suspenders.
export MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_DISABLE_CACHE=1
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-${ARM} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-${ARM}
export TRITON_CACHE_DIR=/tmp/triton-${ARM}   # keep torch.compile cache OFF ~/.triton (home inode quota killer)
rm -rf "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"; mkdir -p "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"

SNAP=${CODE}/lumi/matrix_prompts_snapshot.json
COMMON=(--label base --tag base --ckpt none --prompts ${SNAP} --out ${ROUT} --frames 4096)

# (model, cfg, strengths) split across 8 GCDs
case ${ARM} in
  0) ARGS=(--only-cfgs 1  --strengths 1.0) ;;
  1) ARGS=(--only-cfgs 1  --strengths 1.5,2.0) ;;
  2) ARGS=(--only-cfgs 7  --strengths 1.0) ;;
  3) ARGS=(--only-cfgs 7  --strengths 1.5,2.0) ;;
  4) ARGS=(--only-cfgs 16 --strengths 1.0) ;;
  5) ARGS=(--only-cfgs 16 --strengths 1.5,2.0) ;;
  6) COMMON=(--label base --tag base --ckpt none --prompts ${SNAP} --out ${ROUT} --frames 4096 --pt-medium --steps 8)
     ARGS=(--only-cfgs 1 --strengths 1.0,1.5) ;;
  7) COMMON=(--label base --tag base --ckpt none --prompts ${SNAP} --out ${ROUT} --frames 4096 --pt-medium --steps 8)
     ARGS=(--only-cfgs 1 --strengths 2.0) ;;
  *) echo "[arm ${ARM}] no assignment"; exit 0 ;;
esac

echo "[arm ${ARM}] render_matrix_cells ${COMMON[*]} ${ARGS[*]}"
python ${CODE}/lumi/render_matrix_cells.py "${COMMON[@]}" "${ARGS[@]}" \
  || echo "[arm ${ARM}] FAILED (siblings unaffected)"
'
echo "[native-grid] done. cells in:" && ls "${ROUT}" | grep -c "__d380" || true
# SUCCESS = count __d380 cells (NEVER the sbatch rc): expect 162 base + 54 base_ptm = 216 wav
# (+ .z0.npy + .mmline.json each). W pulls native_cells -> transcodes/ingests -> board.
