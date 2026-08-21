#!/bin/bash
# morph_render.sbatch — first LISTEN of the D12 morph-contour bracket (21439456 pitch L2/L3/L4,
# 21439457 IOI): every arm's riffer_final.pt conditioned on REAL contour streams (lumi/render_morph.py:
# 8 seeded sidecar crops per alphabet, 512-frame max-coverage window, gains 1.0/2.0 + a null-stream
# control, cfg7, 24 steps) with the ORIGINAL latent window decoded as the paired reference.
# Vocab + FT backbone are read from each ckpt's saved args. 16 arms / 8 ranks.
# RUN: sbatch lumi/sbatch/morph_render.sbatch
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --gpus-per-task=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=03:00:00
#SBATCH --job-name=morph_render
#SBATCH --output=%x-%j.out
#SBATCH --no-requeue
set -uo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${PROJ}/containers/sa3.sif
ROUT=${SCRATCH}/renders/morph
UNITS=${ROUT}/units.txt
mkdir -p ${ROUT}
[ -f "${CODE}/lumi/render_morph.py" ] || { echo "[mr] FATAL: render_morph.py not rsynced"; exit 1; }
: > ${UNITS}.tmp
for CK in $(ls ${SCRATCH}/runs/morphcond/*/riffer_final.pt 2>/dev/null | sort); do
  NAME=$(basename $(dirname ${CK}))
  case "${NAME}" in
    morph_L*) L=$(echo ${NAME} | sed -E 's/morph_L([0-9]).*/\1/'); MDIR=${SCRATCH}/latents_sa3_morphL${L} ;;
    morph_IOI3*) MDIR=${SCRATCH}/latents_sa3_morphIOI3 ;;
    *) echo "[mr] skip unknown arm ${NAME}"; continue ;;
  esac
  [ -d "${MDIR}" ] || { echo "[mr] FATAL: ${MDIR} missing"; exit 1; }
  echo "${NAME}|${CK}|${MDIR}" >> ${UNITS}.tmp
done
mv ${UNITS}.tmp ${UNITS}
NU=$(wc -l < ${UNITS}); echo "[mr] ${NU} arms:"; cat ${UNITS}
[ "${NU}" -gt 0 ] || { echo "[mr] FATAL: no finished morph arms (riffer_final.pt)"; exit 1; }

srun --nodes=1 --ntasks=8 --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -uo pipefail
R=${SLURM_PROCID}
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; FLASH=/flash/project_465003186
CODE=${PROJ}/code
echo "[r${R}] alive $(hostname) $(date -Is)"
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor:${CODE}/lumi
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
export MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_DISABLE_CACHE=1
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-${R} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-${R}
export TRITON_CACHE_DIR=/tmp/triton-${R}
rm -rf /tmp/miopen-${R} /tmp/triton-${R}; mkdir -p /tmp/miopen-${R} /tmp/triton-${R}
UNITS=${SCRATCH}/renders/morph/units.txt
N=0
while IFS="|" read -r NAME CK MDIR; do
  N=$((N+1)); [ $(( (N-1) % 8 )) -eq ${R} ] || continue
  echo "[r${R}] ARM ${NAME}"
  python ${CODE}/lumi/render_morph.py --ckpt "${CK}" --label ${NAME} --melody-dir ${MDIR} \
    --latent-dir ${FLASH}/latents_sa3 --caption-sidecar ${CODE}/lumi/goa_longform_sidecar.json \
    --out ${SCRATCH}/renders/morph/${NAME} --n-refs 8 --gains 1.0,2.0 --cfg 7 --steps 24 \
    || echo "[r${R}] ${NAME} FAILED (continuing)"
done < "${UNITS}"
echo "[r${R}] done"
'
echo "[mr] clips now: $(ls ${ROUT}/*/*.wav 2>/dev/null | wc -l) (+ refs $(ls ${ROUT}/*/refs/*.wav 2>/dev/null | wc -l))"
