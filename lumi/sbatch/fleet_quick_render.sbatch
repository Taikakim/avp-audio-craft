#!/bin/bash
# fleet_quick_render.sbatch — quick listen pass over LAST NIGHT'S fleet checkpoints
# (CONTINUITY 2026-08-21, Kim direct: "check the checkpoints we have from last night so far,
# and render clips, let's go with the three again, except for the suomisoundi make six").
#
# Per arm: LATEST epoch ckpt only, cfg 7, w 1.0, 20 s cells, steps 24 — the 3 rb_common board
# prompts (lumi/quickeval3_prompts.json); suomi arms get 6 (lumi/suomi6_prompts.json: +t1
# genre-anchor, +modal phrasing "suomisoundi, 2000s, hypnotic, ...", +seeded random corpus
# prompt). fullft arms render with --fullft --use-ema (EMA weights are the listenable set).
# Idempotent per cell; output joins the standard matrix_cells board flow.
#
# RUN:  sbatch lumi/sbatch/fleet_quick_render.sbatch
# VERIFY: count cells, never rc:  ls ${SCRATCH}/renders/matrix_cells/{wfleet,fullft}_*__cfg7__*.wav | wc -l
#   expect ~(8 wfleet-nonsuomi... see table) up to 14 arms: 10 wfleet (4 suomi x 6 prompts,
#   6 others x 3) + 4 fullft x 3 = 66 cells max (fewer if an arm has no ckpt yet).
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=03:00:00
#SBATCH --job-name=fleet_qrender
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
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
CODE=${PROJ}/code
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor
export MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_DISABLE_CACHE=1
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-${R} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-${R}
export TRITON_CACHE_DIR=/tmp/triton-${R}
rm -rf ${MIOPEN_USER_DB_PATH} ${TRITON_CACHE_DIR}; mkdir -p ${MIOPEN_USER_DB_PATH} ${TRITON_CACHE_DIR}

# arm table: 14 arms over 8 ranks (rank r takes arms r and r+8)
ARMS=(
  "wfleet wfleet_suomi_t1024_a45_fp32_s1  suomi"
  "wfleet wfleet_suomi_t1024_a45_fp32_s2  suomi"
  "wfleet wfleet_suomi_t1024_a128_fp32_s1 suomi"
  "wfleet wfleet_suomi_t1024_a128_fp32_s2 suomi"
  "wfleet wfleet_avp_t1024_a45_fp32_s1    std"
  "wfleet wfleet_avp_t1024_a45_fp32_s2    std"
  "wfleet wfleet_mix3_t1024_a45_fp32_s1   std"
  "wfleet wfleet_mix3_t1024_a45_fp32_s2   std"
  "wfleet wfleet_biggoa_t1024_a45_fp32_s1 std"
  "wfleet wfleet_biggoa_t1024_a45_fp32_s2 std"
  "fullft fullft_suomi_t1024_fp32_lr1e-4_s1  suomi"
  "fullft fullft_avpaug_t1024_fp32_lr1e-4_s1 std"
  "fullft fullft_biggoa_t1024_fp32_lr1e-4_s1 std"
  "fullft fullft_mix3_t1024_fp32_lr1e-4_s1   std"
)
ROUT=${SCRATCH}/renders/matrix_cells; mkdir -p ${ROUT}
for IDX in ${R} $((R+8)); do
  [ ${IDX} -lt ${#ARMS[@]} ] || continue
  read -r FAM NAME KIND <<< "${ARMS[${IDX}]}"
  RUN=${SCRATCH}/runs/${FAM}_fleet/${NAME}
  [ "${FAM}" = "wfleet" ] && RUN=${SCRATCH}/runs/winning_fleet/${NAME}
  CK=$(ls ${RUN}/epoch=*.ckpt 2>/dev/null | sort -V | tail -1)
  if [ -z "${CK}" ]; then echo "[r${R}] ${NAME}: no ckpts yet, skip"; continue; fi
  EP=$(basename "${CK}" | grep -oE "epoch=[0-9]+" | grep -oE "[0-9]+")
  PR=${CODE}/lumi/quickeval3_prompts.json
  [ "${KIND}" = "suomi" ] && PR=${CODE}/lumi/suomi6_prompts.json
  EXTRA=""
  [ "${FAM}" = "fullft" ] && EXTRA="--fullft --use-ema"
  [ "${FAM}" = "wfleet" ] && EXTRA="--strengths 1.0"
  echo "[r${R}] RENDER ${NAME} ep${EP} ($(basename ${PR})) ${EXTRA}"
  python ${CODE}/lumi/render_matrix_cells.py --label ${NAME} --tag ep${EP} \
    --ckpt "${CK}" --prompts ${PR} --out ${ROUT} --only-cfgs 7 ${EXTRA} \
    || echo "[r${R}] ${NAME} ep${EP} RENDER FAILED (continuing)"
done
echo "[r${R}] done"
'
echo "[qrender] cells now present:"
ls ${SCRATCH}/renders/matrix_cells/{wfleet,fullft}_*__cfg7__*.wav 2>/dev/null | wc -l
