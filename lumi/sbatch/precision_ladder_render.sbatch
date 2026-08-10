#!/bin/bash
# precision_ladder_render.sbatch — render matched cells from the (already-trained) precision
# ladder so it gets auditionable clips + feeds the whitened-chroma PREC A/B (CONTINUITY
# 2026-08-06). The ladder sbatch only TRAINS (no render tail), so the 3 arms have ckpts but
# zero clips. This renders each arm's FINAL ckpt, cfg{1,7,16} @ strength 1.0 (fullft collapses
# strength to 1.0), into renders/matrix_cells with labels precision_ladder_t256_{fp32,bf16mixed,
# fp16mixed} — so they land on the audit board grouped as the precision family.
#
# CRITICAL: the ladder trained --use-ema, so render the EMA SHADOW (diffusion_ema.ema_model.*),
# NOT the online weights — render_matrix_cells --use-ema does that; --fullft forces the whole-
# model load path (labels don't start with 'fullft_'). 3 arms, one GCD each, ~fast.
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=3
#SBATCH --ntasks-per-node=3
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=02:00:00
#SBATCH --job-name=sa3_prec_render
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}
FRAMES=${FRAMES:-256}
SNAP=${CODE}/lumi/matrix_prompts_snapshot.json
ROUT=${SCRATCH}/renders/matrix_cells
CFGS=${CFGS:-1,7,16}

[ -n "${SIF}" ] || { echo "[prec-render] FATAL: no multitorch image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[prec-render] FATAL: ${VENV} missing"; exit 1; }
[ -f "${SNAP}" ] || { echo "[prec-render] FATAL: prompt snapshot missing: ${SNAP}"; exit 1; }
mkdir -p "${ROUT}"

PRECS=(fp32 bf16mixed fp16mixed)

run_arm () {
  local GCD=$1 PRECN=$2
  local NAME=precision_ladder_t${FRAMES}_${PRECN}
  local RUN=${SCRATCH}/runs/precision_ladder/${NAME}
  # LAST fat ckpt (highest epoch); skip the .weights.ckpt siblings
  local CK; CK=$(ls "${RUN}"/epoch=*.ckpt 2>/dev/null | grep -v "\.weights\.ckpt$" | sort -V | tail -1 || true)
  [ -n "${CK}" ] || { echo "[prec-render] arm ${GCD} ${NAME}: NO ckpt in ${RUN} — skipping"; return 0; }
  local EP; EP=$(basename "${CK}" | grep -oE "epoch=[0-9]+" | grep -oE "[0-9]+")
  echo "[prec-render] arm ${GCD} ${NAME}: render ep${EP} (EMA) from ${CK}"
  ROCR_VISIBLE_DEVICES=${GCD} srun --exclusive -N1 -n1 --gpus=1 --cpus-per-task=7 \
    singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -euo pipefail
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; CODE=${PROJ}/code
source '"${VENV}"'/bin/activate
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor${PYTHONPATH:+:${PYTHONPATH}}
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-'"${GCD}"' MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-'"${GCD}"'
export TRITON_CACHE_DIR=/tmp/triton-'"${GCD}"' PYTORCH_TUNABLEOP_ENABLED=0
rm -rf /tmp/miopen-'"${GCD}"' /tmp/triton-'"${GCD}"'; mkdir -p /tmp/miopen-'"${GCD}"' /tmp/triton-'"${GCD}"'
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True
python ${CODE}/lumi/render_matrix_cells.py \
    --label '"${NAME}"' --tag ep'"${EP}"' \
    --ckpt "'"${CK}"'" --fullft --use-ema \
    --prompts '"${SNAP}"' --out '"${ROUT}"' \
    --only-cfgs '"${CFGS}"' --strengths 1.0 --frames '"${FRAMES}"' \
  || echo "[prec-render] arm '"${GCD}"' render FAILED (non-fatal)"
' &
}

echo "[prec-render] image=${SIF}  T=${FRAMES} cfgs=${CFGS}  out=${ROUT}"
gcd=0
for p in "${PRECS[@]}"; do run_arm ${gcd} "${p}"; gcd=$((gcd + 1)); done
wait

echo "[prec-render] done. cells per arm:"
for p in "${PRECS[@]}"; do
  n=$(ls "${ROUT}"/precision_ladder_t${FRAMES}_${p}__* 2>/dev/null | wc -l)
  echo "  precision_ladder_t${FRAMES}_${p}: ${n} files"
done
# SUCCESS = 3 arms each with cells (cfgs x prompts). Feed the cfg7/w1 cells to melody_wall_analysis.py
# for the whitened-chroma recurrence A/B -> PREC= verdict (fp32 vs bf16-mixed vs fp16-mixed).
