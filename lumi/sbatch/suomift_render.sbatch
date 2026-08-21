#!/bin/bash
# suomift_render.sbatch — render the two suomi FULL-FT warm-start ladders (fullft_suomi_warm.sbatch:
# suomift_warm_avpaug19 / suomift_warm_goaft, 8 EMA ckpts each) on the SUOMI prompt set, same grid
# as stack_suomi (cfg7, 20 s, suomi_full_prompts.json) so the three answers to "can suomi be
# reproduced" sit on ONE board: adapter-on-base (B8), adapter-on-fullFT (stack_suomi), fullFT
# warm-started (this). The two bare backbones render too (ckpt none) as the zero-point.
# RUN: sbatch lumi/sbatch/suomift_render.sbatch
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --gpus-per-task=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=03:00:00
#SBATCH --job-name=suomift_render
#SBATCH --output=%x-%j.out
#SBATCH --no-requeue
set -uo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${PROJ}/containers/sa3.sif
ROUT=${SCRATCH}/renders/suomift_warm
UNITS=${ROUT}/units.txt
mkdir -p ${ROUT}

# units: LABEL|TAG|STATE_CKPT  (fat ckpts; loader prefers the EMA shadow)
: > ${UNITS}.tmp
for ARM in avpaug19 goaft; do
  D=$(ls -d ${SCRATCH}/runs/suomift_warm/suomift_warm_${ARM}_* 2>/dev/null | head -1)
  [ -n "${D}" ] || { echo "[sfr] FATAL: no run dir for ${ARM}"; exit 1; }
  for CK in $(ls ${D}/epoch=*.ckpt | grep -v "\.weights\.ckpt$" | sort -t= -k2 -V); do
    EP=$(basename ${CK} | sed -E 's/epoch=([0-9]+).*/\1/')
    echo "suomift_${ARM}|ep${EP}|${CK}" >> ${UNITS}.tmp
  done
done
# zero-point backbones
echo "bb_avpaug19|ep19|${SCRATCH}/runs/fullft_fleet/fullft_avpaug_t1024_fp32_lr1e-4_s1/epoch=19-step=5980-v1.ckpt" >> ${UNITS}.tmp
mapfile -t GCKS < <(ls ${SCRATCH}/runs/*/fullft_goa_t4096/epoch=*.ckpt ${SCRATCH}/runs/fullft_goa_t4096/epoch=*.ckpt 2>/dev/null | grep -v "\.weights\.ckpt$" | sort -t= -k2 -V)
GMID=${GCKS[$((${#GCKS[@]}/2))]}
echo "bb_goaft|ep$(basename ${GMID} | sed -E 's/epoch=([0-9]+).*/\1/')|${GMID}" >> ${UNITS}.tmp
mv ${UNITS}.tmp ${UNITS}
NU=$(wc -l < ${UNITS}); echo "[sfr] ${NU} units:"; cat ${UNITS}
[ "${NU}" -ge 10 ] || { echo "[sfr] FATAL: too few units"; exit 1; }

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
UNITS=${SCRATCH}/renders/suomift_warm/units.txt
ROUT=${SCRATCH}/renders/suomift_warm
N=0
while IFS="|" read -r LABEL TAG CK; do
  N=$((N+1)); [ $(( (N-1) % 8 )) -eq ${R} ] || continue
  echo "[r${R}] UNIT ${LABEL} ${TAG} ($(basename ${CK}))"
  python ${CODE}/lumi/render_matrix_cells.py --label ${LABEL} --tag ${TAG} --ckpt none \
    --base-state-ckpt "${CK}" --prompts ${CODE}/lumi/suomi_full_prompts.json --out ${ROUT} --only-cfgs 7 \
    || echo "[r${R}] ${LABEL} ${TAG} FAILED (continuing)"
done < "${UNITS}"
echo "[r${R}] done"
'
echo "[sfr] cells now: $(ls ${ROUT}/*.wav 2>/dev/null | wc -l)"
