#!/bin/bash
# morph_head_sweep.sbatch — 8-arm melody control-head sweep, one 8-GCD node. CONTINUITY 2026-08-12 (Kim-greenlit).
#
# THIS IS SWEEP-1 = the CONFIG-READY arms only: it varies the FIRST-ORDER levers we can drive with existing
# flags — INJECTION SITE (--adapter-layers, Head-A's pivot), OPTIMIZER (Fusion vs AdamW; Fusion was sovereign
# for onset density), CAPACITY (dora-rank), TARGET among existing modes (melody_contour vs hpcp-attribute),
# and CFG/melody DROPOUT (Zach's overfit knob). Base recipe = the proven headb_melody.sbatch, moved onto
# FusionOpt. The MORPHOLOGICAL arms (soft-rank/contour loss, k=3 temporal kernel, per-window rank-norm target,
# chroma384 attribute) need CODE + DATA that don't exist yet -> SWEEP-2, after C implements the flags.
#
# PINNING: ROCR_VISIBLE_DEVICES=$SLURM_PROCID ALONE + srun --overlap --cpu-bind=none (the proven
# aug8_encode/muscriptor pattern). Today's saga: --gpus-per-task=1 put all 8 arms on GCD0 -> OOM/collision.
# ENV: sa3.sif — the KNOWN-GOOD control-head env (headb note: local ROCm-7.15 pilot heap-corrupted; sa3.sif green).
#
# RUN ORDER (today's hard lesson — always smoke an 8-GCD node job first):
#   SMOKE=1 sbatch morph_head_sweep.sbatch     # ~10 min; confirm [gpu-assign] shows ROCR 0..7 DISTINCT, no crash
#   sbatch        morph_head_sweep.sbatch       # full 15-epoch run
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=12:00:00
#SBATCH --job-name=sa3_morph_head_sweep
#SBATCH --output=%x-%j.out
set -euo pipefail
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; FLASH=/flash/project_465003186
CODE=${CODE:-$PROJ/code}; SIF=${SIF:-$PROJ/containers/sa3.sif}
MELODY=$SCRATCH/latents_sa3_melody
SAVE_ROOT=$SCRATCH/runs/morph_head_sweep; mkdir -p "$SAVE_ROOT"
SMOKE=${SMOKE:-}
if [ -n "$SMOKE" ]; then STEPS=40; MAXEP=1; SAVEEVERY=20; else STEPS=15000; MAXEP=15; SAVEEVERY=660; fi

# --- prereqs (fail loud; a bad path otherwise trains on 0 crops) ---
[ -f "$SCRATCH/latents_sa3.tar.gz" ] || { echo "[morph] FATAL: latents_sa3.tar.gz missing"; exit 1; }
[ -d "$MELODY" ] || { echo "[morph] FATAL: $MELODY missing — ship latents_sa3_melody sidecars first"; exit 1; }
NMEL=$(ls "$MELODY"/*.melody8.npy 2>/dev/null | wc -l)
[ "$NMEL" -ge 2000 ] || { echo "[morph] FATAL: only $NMEL melody sidecars (<2000) — bad/partial ship"; exit 1; }
[ -f "$CODE/control/sa3_control/train.py" ] || { echo "[morph] FATAL: control/sa3_control not in code refresh"; exit 1; }
if [ ! -d "$FLASH/latents_sa3" ]; then mkdir -p "$FLASH/latents_sa3"; tar -xzf "$SCRATCH/latents_sa3.tar.gz" -C "$FLASH/latents_sa3" --strip-components=1; fi
echo "[morph] prereqs OK: $NMEL melody sidecars; SMOKE=${SMOKE:-0} STEPS=$STEPS MAXEP=$MAXEP"

srun --overlap --cpu-bind=none --mpi=none --nodes=1 --ntasks=8 --cpus-per-task=7 \
  singularity exec --bind "$PROJ","$SCRATCH","$FLASH",/tmp "$SIF" bash -c '
set -euo pipefail
ARM=${SLURM_PROCID}
export ROCR_VISIBLE_DEVICES=${ARM}   # pin THIS task to GCD=ARM (ROCR ALONE; never +HIP -> "No HIP GPUs")
echo "[gpu-assign] arm=${ARM} ROCR=${ROCR_VISIBLE_DEVICES:-} STEP_GPUS=${SLURM_STEP_GPUS:-}"
export HF_HUB_OFFLINE=1 HF_HOME='"$PROJ"'/models
export PYTHONPATH='"$CODE"'/stable-audio-3:'"$CODE"'/control
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
export MIOPEN_DISABLE_CACHE=1 MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0
export MIOPEN_USER_DB_PATH=/tmp/miopen-morph-${ARM} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-morph-${ARM}
mkdir -p "${MIOPEN_USER_DB_PATH}"
FLASH='"$FLASH"'; MELODY='"$MELODY"'; SAVE_ROOT='"$SAVE_ROOT"'; CODE='"$CODE"'
STEPS='"$STEPS"'; MAXEP='"$MAXEP"'; SAVEEVERY='"$SAVEEVERY"'
MEL="--control-mode melody_contour --melody-dir ${MELODY} --control-dim 768 --dora-rank 128 --melody-dropout 0.1"
case ${ARM} in
  0) LABEL=base_fusion; OPT=fusion;    MODE="${MEL}"; CFG=0.1 ;;
  1) LABEL=adamw;       OPT=adamw;     MODE="${MEL}"; CFG=0.1 ;;
  2) LABEL=site_L8_15;  OPT=fusion;    MODE="${MEL} --adapter-layers 8-15"; CFG=0.1 ;;
  3) LABEL=site_L13_15; OPT=fusion;    MODE="${MEL} --adapter-layers 13,14,15"; CFG=0.1 ;;
  4) LABEL=wide_r256;   OPT=fusion;    MODE="--control-mode melody_contour --melody-dir ${MELODY} --control-dim 768 --dora-rank 256 --melody-dropout 0.1"; CFG=0.1 ;;
  5) LABEL=hpcp_attr;   OPT=fusion;    MODE="--control-mode attribute --control-feature melody --control-dim 768 --dora-rank 128"; CFG=0.1 ;;
  6) LABEL=highdrop;    OPT=fusion;    MODE="--control-mode melody_contour --melody-dir ${MELODY} --control-dim 768 --dora-rank 128 --melody-dropout 0.3"; CFG=0.3 ;;
  7) LABEL=fusion_nm;   OPT=fusion_nm; MODE="${MEL}"; CFG=0.1 ;;
  *) echo "[morph] arm ${ARM} unassigned"; exit 0 ;;
esac
SAVE="${SAVE_ROOT}/${LABEL}"; mkdir -p "${SAVE}"
echo "[morph] arm ${ARM} -> ${LABEL}: opt=${OPT} cfg=${CFG} mode=[${MODE}] -> ${SAVE}"
if python ${CODE}/control/sa3_control/train.py \
    --encoded_dir ${FLASH}/latents_sa3 --model medium-base --precision bf16 \
    ${MODE} --cfg-dropout ${CFG} --optimizer ${OPT} \
    --crop-frames 512 --batch 4 --grad-accum 1 --lr 1e-4 \
    --warmup-steps 100 --steps ${STEPS} --max-epochs ${MAXEP} --save-every ${SAVEEVERY} \
    --num-workers 7 --seed 42 --no-export-onnx-on-finish --run-name morph_${LABEL} \
    --save-dir "${SAVE}" 2>&1 | tee -a "${SAVE}"/train.log; then
  echo "[morph] arm ${ARM} (${LABEL}) DONE"
else
  echo "[morph] arm ${ARM} (${LABEL}) FAILED — see ${SAVE}/train.log (siblings unaffected)"
fi
'
# --- best-effort telemetry (never mark the whole job FAILED on the probe tail) ---
set +e
echo "[morph] ===== per-arm checkpoint count ====="
for d in "$SAVE_ROOT"/*/; do
  n=$(ls "$d"riffer_step*.pt 2>/dev/null | wc -l); f=$([ -f "$d/riffer_final.pt" ] && echo yes || echo no)
  echo "  $(basename "$d"): ${n} step-ckpts, final=${f}"
done
