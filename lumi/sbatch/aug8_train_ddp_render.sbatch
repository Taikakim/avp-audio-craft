#!/bin/bash
# aug8_train_ddp_render.sbatch -- RENDER-ONLY pass for the aug8_train_ddp lane (Kim asked
# 2026-08-06 why the aug8 models have no clips on run_audit_board.html; CONTINUITY confirmed
# 2026-08-05 no auto-render hook ever existed and no manual render pass was ever run for this
# lane -- clips genuinely never made, not merely un-pulled). Modeled on efp_adamw_render.sbatch
# (same 8-arms-one-GCD-each pattern) + fullft_cells_hq.sbatch's slim-then-fat ckpt selection.
#
# SCOPE -- aug8_train_ddp ONLY. Two things this does NOT cover, flagged rather than guessed at:
#   (1) aug8_train.sbatch (the ORIGINAL 8-arms-in-parallel, non-DDP lane, RUNROOT
#       ${SCRATCH}/runs/aug8_train, dirs aug8_${DSTAG}_${MODE}_${PREC}_t${T}_bs${BS}) -- zero
#       mentions anywhere in AGENT_DIALOGUE.md/WORKLOG.md/journals of it ever being submitted,
#       and it has no entry in build_run_audit_board.py's LUMI_RUNS. If it DID run, it needs its
#       own render pass (different dir-naming scheme) -- check `ls ${SCRATCH}/runs/aug8_train/`
#       once you have LUMI access; don't assume this script's ARMS table applies to it.
#   (2) "aug3" -- this is NOT a run. Grepped the whole tree: it only appears as a proposed
#       CHEAPER variant-count option (3 augs instead of 8, to cut encode wall-time) in
#       docs/goa-archive-buildout-plan.md + lumi/profile_encode.py's comments, and
#       KIM-TASKLIST.md's carried-forward "aug8 redo-vs-aug3 (encode profile unmeasured,
#       parked)" item. No aug3 sbatch, no aug3 latents, no aug3 checkpoints exist. Nothing to
#       render.
#
# WHAT: one task per REAL aug8_train_ddp arm (8; excludes the ddp_smoke/ddp_smoke_dora
# mechanics-only smoke arms -- not worth eval compute) -- LAST epoch ckpt only (bump to
# last+midpoint like efp_adamw_render.sbatch if more than one snapshot per arm is wanted once
# you see how many epochs actually landed). Renders the standard 18-prompt x cfg{1,7,16} x w1.0
# grid via the unmodified render_matrix_cells.py, into the SAME shared OUTDIR every other
# campaign uses -- joins the board via the usual (model, ckpt, cfg, strength, prompt_id) key.
#
# LABELING (matters for correctness, not just cosmetics): render_matrix_cells.py branches its
# checkpoint-loading code path on `label.startswith("fullft_")` (raw full-state-dict load vs
# model.load_lora()) -- so fullft arms MUST keep a "fullft_" prefix or they'll silently try (and
# fail) the LoRA loader on a full-model checkpoint. Labels here are "fullft_aug8ddp_<rest>" /
# "dora_aug8ddp_<rest>" -- distinct from the existing "fullft_*" render family (which would
# otherwise bucket these into the WRONG run on the audit board -- aug8 is a separate 15-epoch
# augmented-corpus lane, not the earlier plain fullft campaign). Paired PREFIX_TO_RUN entries
# (fullft_aug8ddp_ / dora_aug8ddp_ -> aug8_train_ddp) added to build_run_audit_board.py in the
# same change as this file, so once real clips land here the audit board attributes them
# automatically -- no further code change needed, just re-run the board builder.
#
# PREREQ: at least one arm dir under ${SCRATCH}/runs/aug8_train_ddp/aug8ddp_<armname>/ with an
# epoch=*.ckpt or epoch=*.weights.ckpt. Per-arm skip (not a hard fail) if a dir/ckpt is missing
# -- CONTINUITY's read is that these may not exist at all yet; this script finds out for real
# and renders whatever's actually there, arm by arm.
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=04:00:00
#SBATCH --job-name=sa3_aug8_render
#SBATCH --output=%x-%j.out

set -euo pipefail
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
FLASH=/flash/project_465003186
CODE=${PROJ}/code
SIF=${PROJ}/containers/sa3.sif
MODELS=${PROJ}/models
RUNROOT=${SCRATCH}/runs/aug8_train_ddp

srun --nodes=1 --ntasks=8 --gpus-per-task=1 --cpus-per-task=7 \
  singularity exec --bind ${PROJ},${SCRATCH},${FLASH},/tmp "${SIF}" bash -c '
set -euo pipefail
ARM=${SLURM_PROCID}
PROJ=/project/project_465003186
SCRATCH=/scratch/project_465003186
CODE=${PROJ}/code
RUNROOT=${SCRATCH}/runs/aug8_train_ddp

export HF_HOME='"${MODELS}"' HF_HUB_OFFLINE=1
export PYTHONPATH=${CODE}/stable-audio-3:${CODE}/control:${CODE}/lumi/vendor
export MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_DISABLE_CACHE=1
export OMP_NUM_THREADS=7 MKL_NUM_THREADS=7
export MIOPEN_USER_DB_PATH=/tmp/miopen-${ARM} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-${ARM}
export TRITON_CACHE_DIR=/tmp/triton-${ARM}
rm -rf "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"; mkdir -p "${MIOPEN_USER_DB_PATH}" "${TRITON_CACHE_DIR}"

# ── arm table: IDENTICAL arm names to aug8_train_ddp.sbatch (dir must match to find the
#    ckpts) -- the 8 REAL arms only, ddp_smoke*/ddp_smoke_dora excluded ──
case ${ARM} in
  0) ARMNAME=dora_goa_aug8_fp32;   MODE=dora   ;;
  1) ARMNAME=dora_goa_aug8_bf16;   MODE=dora   ;;
  2) ARMNAME=fullft_goa_aug8_fp32; MODE=fullft ;;
  3) ARMNAME=fullft_goa_aug8_bf16; MODE=fullft ;;
  4) ARMNAME=dora_avp_fp32;        MODE=dora   ;;
  5) ARMNAME=dora_avp_bf16;        MODE=dora   ;;
  6) ARMNAME=fullft_avp_fp32;      MODE=fullft ;;
  7) ARMNAME=fullft_avp_bf16;      MODE=fullft ;;
  *) echo "[arm ${ARM}] no assignment"; exit 0 ;;
esac
RUN=${RUNROOT}/aug8ddp_${ARMNAME}
if [ "${MODE}" = "fullft" ]; then
  LABEL="fullft_aug8ddp_${ARMNAME#fullft_}"
else
  LABEL="dora_aug8ddp_${ARMNAME#dora_}"
fi

if [ ! -d "${RUN}" ]; then
  echo "[arm ${ARM}] ${ARMNAME}: NO RUN DIR at ${RUN} -- arm never trained (or ARMS list never included it), skipping"; exit 0
fi

# slim (weights-only) preferred, fat as fallback -- matches the fullft_cells_hq.sbatch precedent
CK=$(ls "${RUN}"/epoch=*.weights.ckpt 2>/dev/null | sort -V | tail -1)
[ -n "${CK}" ] || CK=$(ls "${RUN}"/epoch=*.ckpt 2>/dev/null | sort -V | tail -1)
if [ -z "${CK}" ]; then
  echo "[arm ${ARM}] ${ARMNAME}: run dir exists but NO epoch ckpt in ${RUN} -- still training or never checkpointed, skipping"; exit 0
fi
EP=$(basename "${CK}" | grep -oE "epoch=[0-9]+" | grep -oE "[0-9]+")

SNAP=${CODE}/lumi/matrix_prompts_snapshot.json
ROUT=${SCRATCH}/renders/matrix_cells; mkdir -p "${ROUT}"
echo "[arm ${ARM}] ${LABEL} ep${EP}: rendering 18-prompt grid, cfg{1,7,16}, from ${CK}"
python ${CODE}/lumi/render_matrix_cells.py --label ${LABEL} --tag ep${EP} \
  --ckpt "${CK}" --prompts ${SNAP} --out ${ROUT} \
  || echo "[arm ${ARM}] ${LABEL} ep${EP} render FAILED -- see stderr above"
echo "[arm ${ARM}] ${LABEL} render pass done"
'
echo "[aug8-render] all arms finished. cells written to ${SCRATCH}/renders/matrix_cells:"
# ls on a no-match glob exits 2 even though wc -l (reading the empty stdin) exits 0 --
# under pipefail that made a fully-successful run (0 real arms trained -> 0 cells, exactly
# as designed) report sbatch state FAILED/exit 2 (job 20792735). find never errors on zero
# matches, so it can't trip this.
find ${SCRATCH}/renders/matrix_cells/ -maxdepth 1 \( -name 'fullft_aug8ddp_*.wav' -o -name 'dora_aug8ddp_*.wav' \) 2>/dev/null | wc -l
# SUCCESS = up to 8 arms x 54 cells = 432 aug8ddp *.wav cells (fewer per arm that was
# never trained / has no ckpt yet -- read the per-arm skip lines above, never just the
# sbatch rc). Kim pulls the renders dir; standard ingest (transcode + manifest append +
# board rebuild) picks these up via the fullft_aug8ddp_/dora_aug8ddp_ prefixes.
