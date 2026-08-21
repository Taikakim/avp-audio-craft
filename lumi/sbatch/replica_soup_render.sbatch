#!/bin/bash
# replica_soup_render.sbatch — C3-on-A10: soup the accidental 8-replica ladders and RENDER
# the soups (CONTINUITY 2026-08-21). Kim's quick listen of single-replica terminal ckpts was
# poor — exactly what the averaging findings predict (constant-LR bs1 walk points need
# EMA/soup to be listenable). This renders the averaged version of the same arms for A/B.
#
# 8 single-GCD tasks = 4 suomi arms x 2 soups:
#   rsoup_ep19    = mean of the 8 replicas at epoch 19        (replica axis)
#   rtsoup_11-19  = mean over replicas AND epochs 11..19 odd  (replica x temporal grand mean)
# Each rank: soup on CPU (lumi/replica_soup.py) -> render the 6-suomi-prompt set cfg7 w1.
# Cells land in matrix_cells as <arm>_rsoup19 / <arm>_rtsoup — same-playhead vs the already
# rendered single-replica cells = the C3 listening comparison.
#
# RUN: sbatch lumi/sbatch/replica_soup_render.sbatch
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --gpus-per-task=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=02:00:00
#SBATCH --job-name=rsoup_render
#SBATCH --output=%x-%j.out
#SBATCH --no-requeue

set -uo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${PROJ}/containers/sa3.sif

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

ARMS=(wfleet_suomi_t1024_a45_fp32_s1 wfleet_suomi_t1024_a45_fp32_s2 \
      wfleet_suomi_t1024_a128_fp32_s1 wfleet_suomi_t1024_a128_fp32_s2)
ARM=${ARMS[$((R % 4))]}
KIND=$([ ${R} -lt 4 ] && echo rsoup19 || echo rtsoup)
RUN=${SCRATCH}/runs/winning_fleet/${ARM}
SOUP=${RUN}/${KIND}.weights.ckpt
ROUT=${SCRATCH}/renders/matrix_cells; mkdir -p ${ROUT}

if [ ! -f "${SOUP}" ]; then
  if [ "${KIND}" = "rsoup19" ]; then
    python ${CODE}/lumi/replica_soup.py --run-dir ${RUN} --epoch 19 --out ${SOUP}
  else
    python ${CODE}/lumi/replica_soup.py --run-dir ${RUN} --epochs 11,13,15,17,19 --out ${SOUP}
  fi
fi
[ -f "${SOUP}" ] || { echo "[r${R}] FATAL: soup missing for ${ARM}/${KIND}"; exit 0; }
python ${CODE}/lumi/render_matrix_cells.py --label ${ARM}_${KIND} --tag soup \
  --ckpt "${SOUP}" --prompts ${CODE}/lumi/suomi6_prompts.json --out ${ROUT} \
  --only-cfgs 7 --strengths 1.0 \
  || echo "[r${R}] ${ARM}_${KIND} RENDER FAILED"
echo "[r${R}] done ${ARM}_${KIND}"
'
echo "[rsoup] cells: $(ls ${SCRATCH}/renders/matrix_cells/wfleet_suomi_*soup*__cfg7__*.wav 2>/dev/null | wc -l) (want 48)"
