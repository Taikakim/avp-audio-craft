#!/usr/bin/env bash
# Train the SA3 audio-reference (riffer) control adapter on pre-encoded latents.
#
#   bash eval/launch_riffer.sh                 # default: bf16, crop 2048, 20k steps
#   CROP=4096 STEPS=40000 bash eval/launch_riffer.sh
#
# Perf notes (this box / ROCm):
#  - bf16 base + adapters (the supported ROCm path). TunableOp OFF — negligible on 7.14.
#  - Runs from the consolidated SAO/.venv, whose flash_attn 2.8.4 IS the native CK
#    (Composable Kernel) build — validated end-to-end incl. a DoRA training run on CK FA
#    (docs/consolidated-venv-setup.md, docs/flash-attn-ck-rdna4.md). The CK path requires
#    FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE (else it routes to the absent aiter-Triton).
#  - Do NOT set MIOPEN_FIND_MODE=6 — it crashes SA3-medium's DiT (mode 2 is fine).
#  - DiT gradient checkpointing stays ON; our module-global control-token holder survives it.
#  - Only ~4.8% of params train (the adapters + ref conditioner); the 2.3B base is frozen.
set -u
cd /home/kim/Projects/SAO || exit 1                  # editable sao_tooling resolves sa3_control here

PY=/home/kim/Projects/SAO/.venv/bin/python
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE       # CK kernels, not aiter-Triton (see header)
export PYTORCH_TUNABLEOP_ENABLED=0                    # negligible on 7.14

SAVE_DIR="${SAVE_DIR:-/run/media/kim/Mantu/sa3_control_runs/riffer}"
# CHECKPOINT=0 disables DiT gradient checkpointing (faster bwd; needs the VRAM headroom).
CK_ARG=""; [ "${CHECKPOINT:-1}" = "0" ] && CK_ARG="--no-checkpoint"
WB_ARGS=""                                            # wandb on by default; WANDB=0 disables
if [ "${WANDB:-1}" != "0" ]; then
  WB_ARGS="--wandb --wandb-project ${WANDB_PROJECT:-sa3-riffer} --run-name ${RUN_NAME:-$(basename "$SAVE_DIR")-$(date +%m%d-%H%M)}"
  mkdir -p "$SAVE_DIR"                                 # write wandb run data to the save-dir (Mantu),
  export WANDB_DIR="$SAVE_DIR"                         # not under the repo where it could shadow imports
fi

"$PY" -m sa3_control.train \
  --encoded_dir /home/kim/Projects/latents_sa3 \
  --model medium-base --precision bf16 \
  --crop-frames "${CROP:-2048}" --batch "${BATCH:-1}" \
  --lr "${LR:-1e-4}" --steps "${STEPS:-20000}" \
  ${SUBSET:+--subset-tracks "$SUBSET"} $WB_ARGS $CK_ARG \
  ${MAX_HOURS:+--max-hours "$MAX_HOURS"} ${WARMUP:+--warmup-steps "$WARMUP"} ${OPTIMIZER:+--optimizer "$OPTIMIZER"} \
  ${NO_PREENCODE:+--no-preencode-text} ${TIMESTEP:+--timestep-sampler "$TIMESTEP"} ${RESUME:+--resume "$RESUME"} \
  ${CONTROL_MODE:+--control-mode "$CONTROL_MODE"} ${SCALAR_FIELD:+--scalar-field "$SCALAR_FIELD"} \
  --control-dim 768 --n-tokens 256 --cfg-dropout 0.1 \
  --save-dir "$SAVE_DIR" \
  --save-every "${SAVE_EVERY:-1000}" --num-workers 4 --seed 42
