#!/usr/bin/env bash
# Owner: WINTERMUTE (created 2026-11-03)
# run_e24_contourB.sh -- EXPERIMENTS E24 arm B: goa DoRA fine-tune with K&P L3 contour shapes from the MuScriptor notes, through the mir_ctrl per-block inlet (blocks 12-23).
# The same recipe, steps and seed-free setup as run_e24_contourC.sh, so the two arms compare directly; only the pack differs. About 2.4 h.
# SMOKE=1 runs 20 steps into a throwaway dir. Stops if the drive has under 15 GB free at launch.
set -u
SAO=/home/kim/Projects/SAO
cd "$SAO" || exit 1
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
OUT=/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/sa3_lora_runs   # 4.4 GB per checkpoint, Mantu is nearly full
if [ "${SMOKE:-0}" = "1" ]; then NAME=_e24b_smoke; STEPS=20; MILES="20"; EVERY=10; else NAME=e24_contourB_r128_2026-11-03; STEPS="${STEPS:-2400}"; MILES="800 1600 2400"; EVERY=200; fi
[ "$(df --output=avail -BG "$OUT" | tail -1 | tr -dc 0-9)" -ge 15 ] || { echo "under 15 GB free"; exit 2; }
mkdir -p "$OUT/$NAME"
until KIND=batch NOTE="E24 arm B fine-tune, about 2.4 h, ask if you need the card" Misc/gpu_guard.sh acquire WINTERMUTE $$ >/dev/null 2>&1; do sleep 60; done
trap 'Misc/gpu_guard.sh release WINTERMUTE >/dev/null 2>&1' EXIT
.venv/bin/python stable-audio-3/scripts/train_lora_modular.py \
  --encoded_dir /run/media/kim/Kosmos/latents/latents_sa3 --caption_probs '0,0.9,0.1' \
  --frames 256 --model medium-base --rank 128 --lora_alpha 128 --adapter_type dora-rows \
  --modular-magnitude-update multiplicative --var-dampening 1.15 --var-barrier-weight 0.08 --var-damp-opt \
  --modular-radial-brake 0.8 --modular-beta1 0.9 --modular-snr-gate \
  --mir_ctrl_pack contour_l3 --mir_ctrl_source ctrl --mir_ctrl_dir /run/media/kim/Lehto/latents-all-backup/latents_sa3_contourB \
  --mir_ctrl_blocks 12-23 --mir_ctrl_dropout 0.2 --mir_ctrl_ablation_every "$EVERY" \
  --name "$NAME" --output-dir "$OUT" --batch-size 16 --num-workers 10 --lr 3e-4 --warmup-steps 300 \
  --optimizer modular --allow-uniform-lr --modular-lmo-poly cubic5 --modular-whitening shampoo \
  --modular-schedule-free --modular-sf-c-warmup 300 --modular-sf-r 1.0 --modular-wd 0.02 --modular-wd-overtraining \
  --eval_demos --no-inline-demos --steps "$STEPS" --eval_milestones $MILES --checkpoint_every 200000 \
  --purpose 'E24 arm B: do K&P L3 contour shapes follow when they come from notes and enter through the per-block inlet? Every earlier morph run used Melodia streams and the cross-attention adapter.' \
  --hypothesis 'If the morph lane failed because of its route or source, L3 from MuScriptor notes through this inlet beats shuffled streams on the gated instrument. If it stays flat where arm C follows, the symbols themselves are the problem.' \
  >> "$OUT/$NAME/train.log" 2>&1
rc=$?
echo "exit rc=$rc" >> "$OUT/$NAME/train.log"
