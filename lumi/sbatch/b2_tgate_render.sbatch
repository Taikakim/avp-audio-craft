#!/bin/bash
# b2_tgate_render.sbatch — render-only catch-up for the B2 R2(t)-gated melody arm
# (CONTINUITY 2026-08-21). F's coverage audit: subloss_v3sel_k5_tgate has 3 trained ckpts
# and ZERO clips — its training job (21416096) TIMEOUTed after training, before the render
# tail. This reproduces the SIBLING arms' render config exactly (matrix snapshot, cfg7,
# strengths 1.0/1.5/2.0/3.0, every ckpt) so the k2/k5/k12-vs-tgate melody A/B is valid.
# RUN: sbatch lumi/sbatch/b2_tgate_render.sbatch
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --gpus-per-task=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=02:00:00
#SBATCH --job-name=b2_render
#SBATCH --output=%x-%j.out
#SBATCH --no-requeue
set -uo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${PROJ}/containers/sa3.sif
RUN=${SCRATCH}/runs/subspace_loss_v3sel_grid_mt/subloss_v3sel_k5_tgate
[ -d "${RUN}" ] || RUN=$(ls -d ${SCRATCH}/runs/*/subloss_v3sel_k5_tgate 2>/dev/null | head -1)
[ -n "${RUN}" ] && [ -d "${RUN}" ] || { echo "[b2] FATAL: tgate run dir not found"; exit 1; }

srun --nodes=1 --ntasks=8 --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -uo pipefail
R=${SLURM_PROCID}
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186
CODE=${PROJ}/code
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor
export MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_DISABLE_CACHE=1
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-${R} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-${R}
export TRITON_CACHE_DIR=/tmp/triton-${R}
rm -rf /tmp/miopen-${R} /tmp/triton-${R}; mkdir -p /tmp/miopen-${R} /tmp/triton-${R}
RUN='"${RUN}"'
mapfile -t CKS < <(ls ${RUN}/epoch=*.ckpt 2>/dev/null | grep -v "\.weights\.ckpt$" | sort -V)
[ ${R} -lt ${#CKS[@]} ] || { echo "[r${R}] no ckpt for this rank"; exit 0; }
CK=${CKS[${R}]}
EP=$(basename "${CK}" | grep -oE "epoch=[0-9]+" | grep -oE "[0-9]+")
echo "[r${R}] RENDER subloss_v3sel_k5_tgate ep${EP} (sibling-matched grid)"
python ${CODE}/lumi/render_matrix_cells.py --label subloss_v3sel_k5_tgate --tag ep${EP} \
  --ckpt "${CK}" --prompts ${CODE}/lumi/matrix_prompts_snapshot.json --out ${SCRATCH}/renders/matrix_cells \
  --only-cfgs 7 --strengths 1.0,1.5,2.0,3.0
rc=${PIPESTATUS[0]:-$?}
echo "[r${R}] done rc=${rc}"
'
echo "[b2] cells: $(ls ${SCRATCH}/renders/matrix_cells/subloss_v3sel_k5_tgate_*__cfg7__*.wav 2>/dev/null | wc -l)"
