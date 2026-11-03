#!/bin/bash
# Last edited: THE-FINN 2026-11-03 — paths updated for the __theme sorting of sa3_lora_runs and latch_sweep
# Continue the "everything" 0.5x-LR DoRA for 5 MORE epochs (Kim 2026-07-14:
# "continue the last .5x DoRA for 5 more epochs").
#
# WARM-START (not --resume_ckpt): these run ckpts store a LoRA-adapter state_dict
# (keys rooted at model.*/conditioner.*, saved via get_lora_state_dict) — NOT a
# full-wrapper state_dict — so trainer.fit(ckpt_path=) strict-rejects them
# (wants diffusion.model.model.*). --warm_start_ckpt loads the adapter weights via
# self.diffusion.model.load_state_dict(strict=False) (the model.* keys match at
# that root) AND restores the FusionOpt Schedule-Free optimizer state (684 param
# states) via the OptimizerWarmStart callback. FusionOpt is constant-LR (SF), so
# the only thing lost is the epoch/step counter + shuffle position (cosmetic).
#
# Because the epoch counter resets to 0, --epochs 5 == five MORE epochs, and the
# new ckpts (epoch=0..4) go to a NEW save_dir so they don't overwrite the original
# run's epoch=0..7. These 5 epochs are training-epochs 8..12 of the 0.5x adapter.
# Recipe otherwise IDENTICAL to run_everything_lr0.5x.sh (dora-rows r128, fusion
# lr 1e-4, --duration 47 --beat-aware-crop, bf16, seed 42, 5 corpora). Crop kept
# at duration-47 to match the distribution the adapter trained on.
# MUST be a file (inline bash -c pkill self-kill lesson).
set -u
SAO=/home/kim/Projects/SAO
SA3=$SAO/stable-audio-3
PY=$SAO/.venv/bin/python          # torch 2.14/ROCm 7.15 + compiled CK flash-attn (fast path)
export PYTHONPATH=$SA3:$SA3/scripts:$SAO/control
MANTU=/run/media/kim/Mantu
FT=$SAO/../mir/data/feature_tables
LOG=$SAO/logs
SRC=$MANTU/sa3_lora_runs/__finetunes/dora128_everything_8ep_lr0.5x
WARM=$SRC/epoch=7-step=12216.ckpt
OUT=$MANTU/sa3_lora_runs/__finetunes/dora128_everything_8ep_lr0.5x_cont5
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2
cd "$SA3" || exit 1

DIRS=/run/media/kim/Kosmos/latents/latents_sa3,/home/kim/Projects/latents_organic_dance,/home/kim/Projects/latents_chill,/home/kim/Projects/latents_prog_trance_melodic_techno,/home/kim/Projects/latents_prog_psytechno
SIDE=$FT/goa/captions.json,$FT/organic_dance/captions.json,$FT/chill/captions.json,$FT/prog_trance_melodic_techno/captions.json,$FT/prog_psytechno/captions.json

[ -f "$WARM" ] || { echo "ABORT: warm-start ckpt not found: $WARM" >&2; exit 1; }
mkdir -p "$OUT"

# Pre-flight: refuse if another job holds >3GB VRAM (sub-3GB = ROCm driver residual).
VRAM_USED=$(rocm-smi --showmeminfo vram --json 2>/dev/null | $PY -c "
import json,sys
d=json.load(sys.stdin)
print(int(next(iter(d.values()))['VRAM Total Used Memory (B)']))" 2>/dev/null || echo 0)
if [ "$VRAM_USED" -gt 3221225472 ]; then
  echo "ABORT: GPU busy (${VRAM_USED} bytes VRAM in use)" >&2
  exit 1
fi

echo "[everything_lr0.5x_continue5] START warm=$WARM  +5 epochs -> $OUT  ($(date +%H:%M))"
$PY scripts/train_lora.py \
  --model medium-base \
  --encoded_dir "$DIRS" --caption-sidecar "$SIDE" \
  --adapter_type dora-rows --rank 128 --lora_alpha 128 \
  --optimizer fusion --lr 1e-4 \
  --epochs 5 --batch_size 4 \
  --duration 47 --beat-aware-crop \
  --checkpoint_every_epochs 1 --gradient_clip_val 1.0 \
  --base_precision bf16 --no_demos --num_workers 6 --seed 42 \
  --exclude seconds_total \
  --warm_start_ckpt "$WARM" \
  --save_dir "$OUT" \
  --name "dora128_everything_lr0.5x_continue5" --logger csv \
  > "$LOG/dora128_everything_lr0.5x_continue5.log" 2>&1
echo "[everything_lr0.5x_continue5] done ($(date +%H:%M))"
