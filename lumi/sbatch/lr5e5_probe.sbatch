#!/bin/bash
# lr5e5_probe.sbatch — THE KILL GATE for the A12 arms (Kim 2026-08-22: "I'm more worried about
# burning GPU hours for nothing"). Renders whatever ladder rungs currently exist under
# runs/lr5e5_allsets/*, at the cells that DISCRIMINATE, so the decision to keep or scancel an
# 18-hour run is made on ears at ~45 minutes instead of on hope at hour 18.
#
# WHY THESE CELLS: the property being selected for is not "sounds good at cfg7", it is "survives
# cfg16 at weight 2 without melting" — the thing that separated 5e-5 from 1e-4/2e-4 in
# renders/length_variant. So the probe renders cfg {7,16} x weight {1.0,2.0}: cfg7/w1 says the
# model works at all, cfg16/w2 says whether the healthy structure came along. A probe that only
# rendered cfg7 could not fire the kill criterion it exists to test.
#
# READ IT AS: warm arm rung 1 is the strongest early signal — it STARTS from the weights Kim
# liked, so if IT already melts at cfg16/w2, the effective-batch-8 regime is the suspect, not the
# corpus mix and not the schedule. That single cell is worth the whole probe.
#
# Cheap and idempotent by design — rerun it as each new rung lands; existing cells are skipped.
# ~10 min per rung-set on one node. RUN: sbatch lumi/sbatch/lr5e5_probe.sbatch
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --gpus-per-task=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=01:00:00
#SBATCH --job-name=lr5e5_probe
#SBATCH --output=%x-%j.out
#SBATCH --no-requeue
set -uo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${PROJ}/containers/sa3.sif
ROUT=${SCRATCH}/renders/lr5e5_probe
UNITS=${ROUT}/units.txt
mkdir -p ${ROUT}
SNAP=${CODE}/lumi/matrix_prompts_snapshot.json

# every rung of every arm; NEWEST FIRST so a short walltime still covers the informative end
: > ${UNITS}.tmp
for D in ${SCRATCH}/runs/lr5e5_allsets/*/; do
  NAME=$(basename ${D})
  for CK in $(ls ${D}/epoch=*.ckpt 2>/dev/null | grep -v "\.weights\.ckpt$" | sort -t= -k2 -Vr); do
    EP=$(basename ${CK} | sed -E 's/epoch=([0-9]+).*/\1/')
    echo "${NAME}|ep${EP}|${CK}" >> ${UNITS}.tmp
  done
done
mv ${UNITS}.tmp ${UNITS}
NU=$(wc -l < ${UNITS}); echo "[probe] ${NU} rungs:"; cat ${UNITS}
[ "${NU}" -ge 1 ] || { echo "[probe] no rungs yet — the arms have not reached their first checkpoint (every 2 epochs); rerun later"; exit 0; }

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
ROUT=${SCRATCH}/renders/lr5e5_probe
N=0
while IFS="|" read -r LABEL TAG CK; do
  N=$((N+1)); [ $(( (N-1) % 8 )) -eq ${R} ] || continue
  echo "[r${R}] RUNG ${LABEL} ${TAG}"
  python ${CODE}/lumi/render_matrix_cells.py --label ${LABEL} --tag ${TAG} \
    --ckpt "${CK}" --prompts '"${SNAP}"' --out ${ROUT} \
    --only-cfgs 7,16 --strengths 1.0,2.0 \
    || echo "[r${R}] ${LABEL} ${TAG} FAILED (continuing)"
done < "${SCRATCH}/renders/lr5e5_probe/units.txt"
echo "[r${R}] done"
'
echo "[probe] cells now: $(ls ${ROUT}/*.wav 2>/dev/null | wc -l)"
