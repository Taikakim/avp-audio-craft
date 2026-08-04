#!/bin/bash
# efp_adamw_render.sbatch — RENDER-ONLY resubmit of job 20190736's lost eval renders
# (CONTINUITY 2026-07-28). The adamw sweep TRAINED fine (all 8 arm dirs carry their
# epoch ckpts) but every arm's eval-render tail died on `ModuleNotFoundError: sa3_control`
# — the training sbatch's PYTHONPATH was `stable-audio-3:lumi/vendor`, missing `control/`,
# and render_matrix_cells.py imports `sa3_control.audio_io.save_audio`.
#
# FIX (belt + suspenders): (1) render_matrix_cells.py now self-adds control/ to sys.path
# (line ~29, shipped); (2) this sbatch ALSO puts ${CODE}/control on PYTHONPATH. Either alone
# unblocks it — both so a stale copy of the .py on LUMI can't re-break it.
#
# NO TRAINING. Per arm: reuse the SAME name→ckpt-dir map as efp_adamw_bf16_sweep.sbatch,
# select LAST + MIDPOINT epoch ckpt, render the standard 18-prompt × cfg{1,7,16} grid
# (strength 1.0 — matches the other campaigns' auto-tail convention) via the fixed
# render_matrix_cells.py. Idempotent per cell (skips any that already exist), so a partial
# pre-crash render just fills the gaps. Output -> the shared board dir; W's ingest joins by
# (model, ckpt, cfg, strength, prompt_id) as usual.
#
# PREREQ: ${SCRATCH}/runs/adamw_bf16_sweep/adamw_*/epoch=*.ckpt present (they are — job
#   20190736 COMPLETED); code refreshed on LUMI (this sbatch + render_matrix_cells.py).
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=04:00:00
#SBATCH --job-name=sa3_adamw_render
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
SIF=${PROJ}/containers/sa3.sif
MODELS=${PROJ}/models
RUNROOT=${SCRATCH}/runs/adamw_bf16_sweep

srun --nodes=1 --ntasks=8 --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -euo pipefail
ARM=${SLURM_PROCID}
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
CODE=${PROJ}/code
RUNROOT=${SCRATCH}/runs/adamw_bf16_sweep

export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor  # +control: the fix
export MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_DISABLE_CACHE=1
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-${ARM} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-${ARM}
export TRITON_CACHE_DIR=/tmp/triton-${ARM}   # keep torch.compile cache OFF ~/.triton (home inode quota killer)
rm -rf "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"; mkdir -p "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"

# ── arm table: DS BS LR — IDENTICAL to efp_adamw_bf16_sweep.sbatch (name must match to
#    resolve the right ckpt dir) ──
case ${ARM} in
  0) DS=latents_avp; BS=4; LR=1e-4 ;;
  1) DS=latents_sa3; BS=4; LR=1e-4 ;;
  2) DS=latents_avp; BS=1; LR=1e-4 ;;
  3) DS=latents_sa3; BS=1; LR=1e-4 ;;
  4) DS=latents_avp; BS=4; LR=2e-4 ;;
  5) DS=latents_sa3; BS=4; LR=2e-4 ;;
  6) DS=latents_avp; BS=4; LR=5e-5 ;;
  7) DS=latents_sa3; BS=4; LR=5e-5 ;;
  *) echo "[arm ${ARM}] no assignment"; exit 0 ;;
esac
T=512
DSTAG=$([ "${DS}" = latents_avp ] && echo avp || echo goa)
LRTAG=$(echo ${LR} | tr -d ".-")
NAME=adamw_${DSTAG}_t${T}_bs${BS}_lr${LRTAG}
RUN=${RUNROOT}/${NAME}

SNAP=${CODE}/lumi/matrix_prompts_snapshot.json
ROUT=${SCRATCH}/renders/matrix_cells; mkdir -p "${ROUT}"

mapfile -t CKS < <(ls ${RUN}/epoch=*.ckpt 2>/dev/null | sort -V)
if [ ${#CKS[@]} -eq 0 ]; then
  echo "[arm ${ARM}] FATAL: no epoch ckpts in ${RUN} — arm skipped (nothing to render)"; exit 0
fi
SEL=("${CKS[$(( ${#CKS[@]} - 1 ))]}")                             # last
[ ${#CKS[@]} -gt 3 ] && SEL+=("${CKS[$(( ${#CKS[@]} / 2 ))]}")    # + midpoint
echo "[arm ${ARM}] ${NAME}: ${#CKS[@]} ckpts, rendering ${#SEL[@]} (last+midpoint)"

for CK in "${SEL[@]}"; do
  EP=$(basename "${CK}" | grep -oE "epoch=[0-9]+" | grep -oE "[0-9]+")
  echo "[arm ${ARM}] EVAL RENDER ${NAME} ep${EP} (18-prompt grid, cfg{1,7,16})"
  python ${CODE}/lumi/render_matrix_cells.py --label ${NAME} --tag ep${EP} \
    --ckpt "${CK}" --prompts ${SNAP} --out ${ROUT} \
    || echo "[arm ${ARM}] eval render ep${EP} FAILED — see stderr above"
done
echo "[arm ${ARM}] ${NAME} render pass done"
'
echo "[adamw-render] all arms finished. cells written to ${SCRATCH}/renders/matrix_cells:"
ls ${SCRATCH}/renders/matrix_cells/adamw_*.wav 2>/dev/null | wc -l
# SUCCESS = ~8 arms × ≤2 ckpts × 18 prompts × 3 cfg = up to 864 adamw_*.wav cells (fewer if an
# arm has ≤3 ckpts → last only). VERIFY by the count above, never the sbatch rc.
