#!/bin/bash
# a13_render.sbatch — A13 (fullft_avp_subloss, 21448092) finished 64 epochs and wrote 8 rungs
# with NO render pass wired: I built the training job and forgot the audition, the same gap that
# left A11's 32 arms unheard for a week. This closes it.
#
# FULL-FT PATH: these ckpts are the whole DiT, not an adapter, so they render as
# --ckpt none --base-state-ckpt <ck> (the suomift_render pattern). Adapter --strengths do NOT
# apply to a full-FT, so the pushed axis here is cfg alone: the prompt set carries {7,16} and the
# grid is 20 prompts x 2 cfgs x 8 rungs = 320 cells. cfg16 is still the discriminating cell --
# Kim's whole selection criterion is which models stay musical when guidance is pushed.
# Idempotent per cell. RUN: sbatch lumi/sbatch/a13_render.sbatch
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --gpus-per-task=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=01:30:00
#SBATCH --job-name=a13_render
#SBATCH --output=%x-%j.out
#SBATCH --no-requeue
set -uo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${PROJ}/containers/sa3.sif
ROUT=${SCRATCH}/renders/a13_avp
UNITS=${ROUT}/units.txt
mkdir -p ${ROUT}
PR=${CODE}/lumi/matrix_prompts_snapshot.json
[ -f "${PR}" ] || { echo "[a13r] FATAL: prompts missing"; exit 1; }

: > ${UNITS}.tmp
for D in ${SCRATCH}/runs/fullft_avp_subloss/*/; do
  NAME=$(basename ${D})
  for CK in $(ls ${D}/epoch=*.ckpt 2>/dev/null | grep -v "\.weights\.ckpt$" | sort -t= -k2 -V); do
    EP=$(basename ${CK} | sed -E 's/epoch=([0-9]+).*/\1/')
    echo "${NAME}|ep${EP}|${CK}" >> ${UNITS}.tmp
  done
done
mv ${UNITS}.tmp ${UNITS}
NU=$(wc -l < ${UNITS}); echo "[a13r] ${NU} rungs:"; cat ${UNITS}
[ "${NU}" -ge 1 ] || { echo "[a13r] FATAL: no ckpts under runs/fullft_avp_subloss"; exit 1; }

srun --nodes=1 --ntasks=8 --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -uo pipefail
R=${SLURM_PROCID}
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186
CODE=${PROJ}/code
echo "[r${R}] alive $(hostname) $(date -Is)"
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor:${CODE}/lumi
export MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_DISABLE_CACHE=1
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-${R} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-${R}
export TRITON_CACHE_DIR=/tmp/triton-${R}
rm -rf /tmp/miopen-${R} /tmp/triton-${R}; mkdir -p /tmp/miopen-${R} /tmp/triton-${R}
ROUT=${SCRATCH}/renders/a13_avp
N=0
while IFS="|" read -r LABEL TAG CK; do
  N=$((N+1)); [ $(( (N-1) % 8 )) -eq ${R} ] || continue
  echo "[r${R}] RUNG ${LABEL} ${TAG}"
  python ${CODE}/lumi/render_matrix_cells.py --label ${LABEL} --tag ${TAG} --ckpt none \
    --base-state-ckpt "${CK}" --prompts '"${PR}"' --out ${ROUT} --only-cfgs 7,16 \
    || echo "[r${R}] ${LABEL} ${TAG} FAILED (continuing)"
done < "${SCRATCH}/renders/a13_avp/units.txt"
echo "[r${R}] done"
'
echo "[a13r] cells now: $(ls ${ROUT}/*.wav 2>/dev/null | wc -l)"
