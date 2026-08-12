#!/bin/bash
# fullft_avp_dronesweep.sbatch — CONTINUITY 2026-08-12 (Kim direct: the clean AVP fp32 full-FT
# drone-recipe A/B). Settles the drone fix + optimizer choice for deliverable-1 (great AVP model)
# BEFORE the goa-big-set production run gets the winner. T=1024 (Kim: 2x the epochs/GPU-hour vs
# T4096 for the same recipe read; length is a secondary axis settled later).
#
# 4 RECIPES x 2 SEEDS = 8 GCDs, 1 arm/GCD (full-FT of 1.4B fits 1 GCD at T1024/bs4 — the mem_probe
# confirmed T2048 fits, T1024 is smaller). The 2 seeds are the synthesis's "sweep->replicate in one
# job" (don't crown a winner off one seed). GATE on Kim's ears + disintegration DSP, NOT z0-std alone.
#
# RECIPES (all: fp32 unless noted, FusionOpt/AdamW per arm, EMA 0.9999, grad-clip 1.0, CFG-dropout 0.1
#   inherited from the training wrapper = SA1's 10%, caption tiers per sidecar, NO tag-shuffle (T5-Gemma
#   sentences), --weight_decay 0.1 = the drone-fix spectral WD, NOT the too-weak 0.01 default):
#   plain       = FusionOpt(all-on) + wd0.1                         (the bounded-runaway baseline)
#   force_scalar= FusionOpt + wd0.1 + Muon-OFF on output-proj+AdaLN (SA3-base's OWN recipe; the clean cure)
#   adamw_fair  = AdamW, own LR 2e-4                                (the strategic null: no runaway, ~1.1x gap)
#   bf16_plain  = plain but bf16                                    (settle the fp32-vs-bf16 COST axis, matched)
#
# PINNING: ROCR_VISIBLE_DEVICES=$SLURM_PROCID ALONE (never +HIP). ENV: sa3.sif or the multitorch image.
# RUN ORDER: SMOKE=1 sbatch ... (steps-capped, ~15min, verify [gpu-assign] ROCR 0..7 distinct + no crash)
#            then sbatch ...   (full run)
#
#SBATCH --account=project_465003186
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
#SBATCH --mem=0
#SBATCH --time=48:00:00
#SBATCH --job-name=fullft_avp_dronesweep
#SBATCH --output=%x-%j.out
set -euo pipefail
PROJ=/project/project_465003186; SCRATCH=/scratch/project_465003186; FLASH=/flash/project_465003186
CODE=${CODE:-$PROJ/code}; SIF=${SIF:-$PROJ/containers/sa3.sif}
SAVE_ROOT=$SCRATCH/runs/avp_dronesweep; mkdir -p "$SAVE_ROOT"
SMOKE=${SMOKE:-}
BS=${BS:-4}; FRAMES=${FRAMES:-1024}; EPOCHS=${EPOCHS:-20}; CKEVERY=${CKEVERY:-2}; WD=${WD:-0.1}
FORCE_SCALAR_RE='project_out|postprocess_conv|to_scale_shift_gate'   # output-proj + AdaLN (SA3-base recipe)

[ -d "$FLASH/latents_avp" ] || { echo "[sweep] FATAL: $FLASH/latents_avp missing — ship the AVP latents first"; exit 1; }
[ -f "$CODE/stable-audio-3/scripts/train_lora.py" ] || { echo "[sweep] FATAL: train_lora not in code refresh"; exit 1; }
grep -q -- "--force-scalar" "$CODE/stable-audio-3/scripts/train_lora.py" || { echo "[sweep] FATAL: train_lora missing --force-scalar"; exit 1; }
echo "[sweep] prereqs OK: FRAMES=$FRAMES BS=$BS EPOCHS=$EPOCHS WD=$WD SMOKE=${SMOKE:-0}"

srun --overlap --cpu-bind=none --mpi=none --nodes=1 --ntasks=8 --cpus-per-task=7 \
  singularity exec --bind "$PROJ","$SCRATCH","$FLASH",/tmp "$SIF" bash -c '
set -euo pipefail
ARM=${SLURM_PROCID}
export ROCR_VISIBLE_DEVICES=${ARM}
echo "[gpu-assign] arm=${ARM} ROCR=${ROCR_VISIBLE_DEVICES:-} STEP_GPUS=${SLURM_STEP_GPUS:-}"
export HF_HUB_OFFLINE=1 HF_HOME='"$PROJ"'/models
export PYTHONPATH='"$CODE"'/stable-audio-3:'"$CODE"'/control:'"$CODE"'/lumi/vendor
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE MIOPEN_FIND_MODE=2 PYTORCH_TUNABLEOP_ENABLED=0
export MIOPEN_USER_DB_PATH=/tmp/miopen-sweep-${ARM} MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-sweep-${ARM}; mkdir -p "${MIOPEN_USER_DB_PATH}"
FLASH='"$FLASH"'; SAVE_ROOT='"$SAVE_ROOT"'; CODE='"$CODE"'
FRAMES='"$FRAMES"'; BS='"$BS"'; EPOCHS='"$EPOCHS"'; CKEVERY='"$CKEVERY"'; WD='"$WD"'; FSRE='"'"$FORCE_SCALAR_RE"'"'
SMOKEARG=""; [ -n "'"${SMOKE:-}"'" ] && { EPOCHS=1; SMOKEARG="--steps 120 --checkpoint_every 60"; CKEVERY=1; }
# recipe/seed per GCD: 4 recipes x 2 seeds
case ${ARM} in
  0) R=plain;        SEED=1; OPT="--optimizer fusion --weight_decay ${WD}"; PREC=fp32 ;;
  1) R=force_scalar; SEED=1; OPT="--optimizer fusion --weight_decay ${WD} --force-scalar ${FSRE}"; PREC=fp32 ;;
  2) R=adamw_fair;   SEED=1; OPT="--optimizer adamw --lr 2e-4"; PREC=fp32 ;;
  3) R=bf16_plain;   SEED=1; OPT="--optimizer fusion --weight_decay ${WD}"; PREC=bf16 ;;
  4) R=plain;        SEED=2; OPT="--optimizer fusion --weight_decay ${WD}"; PREC=fp32 ;;
  5) R=force_scalar; SEED=2; OPT="--optimizer fusion --weight_decay ${WD} --force-scalar ${FSRE}"; PREC=fp32 ;;
  6) R=adamw_fair;   SEED=2; OPT="--optimizer adamw --lr 2e-4"; PREC=fp32 ;;
  7) R=bf16_plain;   SEED=2; OPT="--optimizer fusion --weight_decay ${WD}"; PREC=bf16 ;;
  *) echo "[sweep] arm ${ARM} unassigned"; exit 0 ;;
esac
LR_DEFAULT="--lr 8e-5"; case "${OPT}" in *"--lr "*) LR_DEFAULT="";; esac
RUN="${SAVE_ROOT}/${R}_s${SEED}"; mkdir -p "${RUN}"
echo "[sweep] arm ${ARM} -> ${R} seed${SEED}: prec=${PREC} opt=[${OPT}] -> ${RUN}"
if python ${CODE}/stable-audio-3/scripts/train_lora.py \
    --model medium-base --full-finetune \
    --encoded_dir ${FLASH}/latents_avp --save_dir "${RUN}" \
    ${OPT} ${LR_DEFAULT} --use-ema --ema-beta 0.9999 \
    --base_precision ${PREC} --gradient_clip_val 1.0 \
    --batch_size ${BS} --frames ${FRAMES} --beat-aware-crop \
    --epochs ${EPOCHS} --checkpoint_every_epochs ${CKEVERY} ${SMOKEARG} \
    --num_workers 6 --seed ${SEED} --no_demos --logger csv \
    --name avp_dronesweep_${R}_s${SEED} 2>&1 | tee -a "${RUN}"/train_rank${ARM}.log; then
  echo "[sweep] arm ${ARM} (${R} s${SEED}) DONE"
else
  echo "[sweep] arm ${ARM} (${R} s${SEED}) FAILED — see ${RUN}/train_rank${ARM}.log (siblings unaffected)"
fi
'
set +e
echo "[sweep] ===== per-arm ckpt count ====="
for d in "$SAVE_ROOT"/*/; do n=$(ls "$d"epoch=*.ckpt 2>/dev/null | grep -cv weights); echo "  $(basename "$d"): ${n} ckpts"; done
