#!/bin/bash
# dorlor_render.sbatch — the A11 factorial has 32 trained arms and ZERO renders. It is the
# experiment built to answer Kim's "I'm mystified why we are getting so bad results now again",
# and it has never been listened to. This renders every arm's TERMINAL checkpoint.
#
# GRID CHOICE — cfg {7,16} x adapter weight {1.0,2.0}, deliberately (Kim 2026-08-22): the
# discriminating observation on the 5e-5 run was not how it sounds at cfg7, it was that 1e-4 and
# 2e-4 "melt like the face of a Nazi when they open the wrong box" at cfg16/w2 while 5e-5 stayed
# musical. Robustness under guidance overdrive is the property being selected for, so it has to
# be IN the grid. A cfg7/w1-only board cannot see it (see EXPERIMENTS A12).
#
# PROMPTS follow the arm's corpus — a suomi model auditioned on goa prompts tells you nothing:
#   goa / biggoa / avpaug -> matrix_prompts_snapshot.json     (20 prompts, cfgs 1/7/16)
#   suomi                 -> suomisoundi_prompts_snapshot.json (20 prompts, cfgs 7/16)
# The two first-wave dirs with no corpus token in their name (dorlor_{dora,lora}_adamw_...) date
# from before DATASET entered the run name; they are the biggoa default.
#
# Adapter ckpts on medium-base => --ckpt (NOT --base-state-ckpt, that is the full-FT path).
# Idempotent per cell, so rerunning after the seed-2 arms finish picks up their new terminals.
# RUN: sbatch lumi/sbatch/dorlor_render.sbatch
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --gpus-per-task=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=04:00:00
#SBATCH --job-name=dorlor_render
#SBATCH --output=%x-%j.out
#SBATCH --no-requeue
set -uo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${PROJ}/containers/sa3.sif
ROUT=${SCRATCH}/renders/dorlor_ab
UNITS=${ROUT}/units.txt
mkdir -p ${ROUT}

SNAP=${CODE}/lumi/matrix_prompts_snapshot.json
SUOM=${CODE}/lumi/suomisoundi_prompts_snapshot.json
[ -f "${SNAP}" ] && [ -f "${SUOM}" ] || { echo "[dr] FATAL: prompt set missing"; exit 1; }

# units: LABEL|TAG|CKPT|PROMPTS   (terminal fat ckpt per arm; EMA-preferred by the loader)
: > ${UNITS}.tmp
for D in ${SCRATCH}/runs/dorlor_ab/*/; do
  NAME=$(basename ${D})
  CK=$(ls ${D}/epoch=*.ckpt 2>/dev/null | grep -v "\.weights\.ckpt$" | sort -t= -k2 -V | tail -1)
  [ -n "${CK}" ] || { echo "[dr] skip ${NAME}: no fat ckpt"; continue; }
  case "${NAME}" in
    dorlor_suomi_*)  PR=${SUOM} ;;
    *)               PR=${SNAP} ;;
  esac
  EP=$(basename ${CK} | sed -E 's/epoch=([0-9]+).*/\1/')
  echo "${NAME}|ep${EP}|${CK}|${PR}" >> ${UNITS}.tmp
done
mv ${UNITS}.tmp ${UNITS}
NU=$(wc -l < ${UNITS}); echo "[dr] ${NU} units:"; cat ${UNITS}
[ "${NU}" -ge 16 ] || { echo "[dr] FATAL: only ${NU} units — expected ~32"; exit 1; }

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
ROUT=${SCRATCH}/renders/dorlor_ab
N=0
while IFS="|" read -r LABEL TAG CK PR; do
  N=$((N+1)); [ $(( (N-1) % 8 )) -eq ${R} ] || continue
  echo "[r${R}] UNIT ${LABEL} ${TAG} ($(basename ${PR}))"
  python ${CODE}/lumi/render_matrix_cells.py --label ${LABEL} --tag ${TAG} \
    --ckpt "${CK}" --prompts ${PR} --out ${ROUT} \
    --only-cfgs 7,16 --strengths 1.0,2.0 \
    || echo "[r${R}] ${LABEL} ${TAG} FAILED (continuing)"
done < "${SCRATCH}/renders/dorlor_ab/units.txt"
echo "[r${R}] done"
'
echo "[dr] cells now: $(ls ${ROUT}/*.wav 2>/dev/null | wc -l)"
