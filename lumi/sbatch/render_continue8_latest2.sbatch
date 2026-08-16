#!/bin/bash
# render_continue8_latest2.sbatch — CONTINUITY 2026-08-16 (Kim direct): "let's render with the
# two latest checkpoints for each model on LUMI, pull and see if things have improved" —
# checking whether the weight_decay/EMA/AGC fixes (2026-08-15/16) actually stopped the drone-
# runaway recurrence, now that job 21172226 has pushed all 8 continue8 arms further.
#
# One node, 8 GPUs, one arm per GPU — SAME arm table as continue_8runs_openended.sbatch (must
# stay in sync if that script's arms ever change). Each arm renders its NEWEST 2 fat checkpoints
# via render_matrix_cells.py (NLAST=2, already supported there), same 18-prompt/3-cfg snapshot
# used by every other matrix_cells render this campaign, so cells land side-by-side on the board
# under each arm's own NAME as label (no cross-arm mislabeling — same discipline as
# fullft_avp_render.sbatch's hard-pinned LABEL).
#
# fullft arms (6,7) trained with --use-ema -> MUST render the EMA shadow (--fullft --use-ema),
# same as fullft_avp_render.sbatch. DoRA arms (0-5) never use EMA (train_lora.py force-disables
# it for adapters) -> plain --strengths 1.0 load.
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=06:00:00
#SBATCH --job-name=sa3_render_c8
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
CODE=${PROJ}/code
MODELS=${PROJ}/models
SIF=${MTSIF:-$(ls -d /appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif 2>/dev/null | sort | tail -1)}
VENV=${TRAIN_VENV:-${SCRATCH}/sa3_train_venv_mt}
SNAP=${CODE}/lumi/matrix_prompts_snapshot.json
ROUT=${SCRATCH}/renders/matrix_cells
CFGS=${CFGS:-1,7,16}
NLAST=${NLAST:-2}

[ -n "${SIF}" ] || { echo "[render-c8] FATAL: no lumi-multitorch-full image"; exit 1; }
[ -f "${VENV}/bin/activate" ] || { echo "[render-c8] FATAL: ${VENV} missing"; exit 1; }
[ -f "${SNAP}" ] || { echo "[render-c8] FATAL: prompt snapshot missing: ${SNAP}"; exit 1; }
mkdir -p "${ROUT}"

srun --nodes=1 --ntasks=8 --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},/tmp "${SIF}" bash -c '
set -euo pipefail
ARM=${SLURM_PROCID}
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
CODE=${PROJ}/code

VENV='"${VENV}"'; source ${VENV}/bin/activate
export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${VENV}/lib/python3.12/site-packages:${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor${PYTHONPATH:+:${PYTHONPATH}}
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-r${ARM} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-r${ARM}
export TRITON_CACHE_DIR=/tmp/triton-r${ARM} PYTORCH_TUNABLEOP_ENABLED=0
rm -rf "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"; mkdir -p "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True

# ── SAME arm table as continue_8runs_openended.sbatch — keep in sync ──
case ${ARM} in
  0) NAME=fp32cmp_avp_t4096_bs4_lr1e4; RUN=${SCRATCH}/runs/fp32_compare/fp32cmp_avp_t4096_bs4_lr1e4; FULLFT=0 ;;
  1) NAME=fp32cmp_goa_t4096_bs4_lr1e4; RUN=${SCRATCH}/runs/fp32_compare/fp32cmp_goa_t4096_bs4_lr1e4; FULLFT=0 ;;
  2) NAME=fp32cmp_avp_t4096_bs1_lr1e4; RUN=${SCRATCH}/runs/fp32_compare/fp32cmp_avp_t4096_bs1_lr1e4; FULLFT=0 ;;
  3) NAME=fp32cmp_goa_t4096_bs1_lr1e4; RUN=${SCRATCH}/runs/fp32_compare/fp32cmp_goa_t4096_bs1_lr1e4; FULLFT=0 ;;
  4) NAME=winning_avp_t512_a128_fp32;  RUN=${SCRATCH}/runs/fp32_winning/winning_avp_t512_a128_fp32; FULLFT=0 ;;
  5) NAME=winning_goa_t512_a128_fp32;  RUN=${SCRATCH}/runs/fp32_winning/winning_goa_t512_a128_fp32; FULLFT=0 ;;
  6) NAME=fullft_avp_t256; RUN=${SCRATCH}/runs/fullft/fullft_avp_t256; FULLFT=1 ;;
  7) NAME=fullft_goa_t256; RUN=${SCRATCH}/runs/fullft/fullft_goa_t256; FULLFT=1 ;;
  *) echo "[arm ${ARM}] no assignment"; exit 0 ;;
esac
[ -d "${RUN}" ] || { echo "[arm ${ARM}] FATAL: ${RUN} missing"; exit 1; }

mapfile -t CKPTS < <(ls "${RUN}"/epoch=*.ckpt 2>/dev/null | grep -v "\.weights\.ckpt$" | sort -V | tail -n '"${NLAST}"')
[ "${#CKPTS[@]}" -gt 0 ] || { echo "[arm ${ARM}] FATAL: no fat ckpt in ${RUN}"; exit 1; }
echo "[arm ${ARM}] ${NAME}: rendering ${#CKPTS[@]} ckpt(s): ${CKPTS[*]}"

FF_ARGS=()
[ "${FULLFT}" = "1" ] && FF_ARGS=(--fullft --use-ema)

for CK in "${CKPTS[@]}"; do
  EP=$(basename "${CK}" | grep -oE "epoch=[0-9]+" | grep -oE "[0-9]+")
  echo "[arm ${ARM}] ${NAME} ep${EP} <- ${CK}"
  python ${CODE}/lumi/render_matrix_cells.py \
      --label ${NAME} --tag ep${EP} \
      --ckpt "${CK}" "${FF_ARGS[@]}" \
      --prompts '"${SNAP}"' --out '"${ROUT}"' \
      --only-cfgs '"${CFGS}"' --strengths 1.0 \
    || echo "[arm ${ARM}] ${NAME} ep${EP} render FAILED (non-fatal)"
done
echo "[arm ${ARM}] ${NAME} done"
'
echo "[render-c8] all arms finished. cell counts:"
for N in fp32cmp_avp_t4096_bs4_lr1e4 fp32cmp_goa_t4096_bs4_lr1e4 fp32cmp_avp_t4096_bs1_lr1e4 fp32cmp_goa_t4096_bs1_lr1e4 \
         winning_avp_t512_a128_fp32 winning_goa_t512_a128_fp32 fullft_avp_t256 fullft_goa_t256; do
  echo "  ${N}: $(ls ${ROUT}/${N}__*.wav 2>/dev/null | wc -l) wavs"
done
