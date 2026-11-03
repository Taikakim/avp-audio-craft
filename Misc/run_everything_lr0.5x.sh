#!/bin/bash
# Last edited: THE-FINN 2026-11-03 — paths updated for the __theme sorting of sa3_lora_runs and latch_sweep
# "Everything" DoRA at 0.5x LR (Kim 2026-07-12: "prioritize the 0.5x LR run next").
# Fills the gap in the everything LR sweep (had lr1x=2e-4, lr3x=6e-4; no low end).
# Motivated by the training-length finding: lr3x overtrains hard, lr1x declines mildly,
# so a HALVED LR (1e-4) should train slower/more stably and support longer training +
# longer crops. Identical recipe to run_everything_dora_chain.sh except lr + tag.
# MUST be a file (inline bash -c pkill self-kill lesson).
set -u
SAO=/home/kim/Projects/SAO
SA3=$SAO/stable-audio-3
PY=$SAO/.venv/bin/python          # torch 2.14/ROCm 7.15 + compiled CK flash-attn (fast path)
export PYTHONPATH=$SA3:$SA3/scripts:$SAO/control
MANTU=/run/media/kim/Mantu
FT=$SAO/../mir/data/feature_tables
LOG=$SAO/logs
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2
cd "$SA3" || exit 1

DIRS=/run/media/kim/Kosmos/latents/latents_sa3,/home/kim/Projects/latents_organic_dance,/home/kim/Projects/latents_chill,/home/kim/Projects/latents_prog_trance_melodic_techno,/home/kim/Projects/latents_prog_psytechno
SIDE=$FT/goa/captions.json,$FT/organic_dance/captions.json,$FT/chill/captions.json,$FT/prog_trance_melodic_techno/captions.json,$FT/prog_psytechno/captions.json

# Pre-flight: refuse if another job holds >2GB VRAM (sub-2GB = ROCm driver residual).
VRAM_USED=$(rocm-smi --showmeminfo vram --json 2>/dev/null | $PY -c "
import json,sys
d=json.load(sys.stdin)
print(int(next(iter(d.values()))['VRAM Total Used Memory (B)']))" 2>/dev/null || echo 0)
if [ "$VRAM_USED" -gt 3221225472 ]; then     # 3GB — sub-3GB is ROCm driver residual (no process)
  echo "ABORT: GPU busy (${VRAM_USED} bytes VRAM in use)" >&2
  exit 1
fi

echo "[everything_lr0.5x] START lr=1e-4 ($(date +%H:%M))"
$PY scripts/train_lora.py \
  --model medium-base \
  --encoded_dir "$DIRS" --caption-sidecar "$SIDE" \
  --adapter_type dora-rows --rank 128 --lora_alpha 128 \
  --optimizer fusion --lr 1e-4 \
  --epochs 8 --batch_size 4 \
  --duration 47 --beat-aware-crop \
  --checkpoint_every_epochs 1 --gradient_clip_val 1.0 \
  --base_precision bf16 --no_demos --num_workers 6 --seed 42 \
  --exclude seconds_total \
  --save_dir "$MANTU/sa3_lora_runs/__finetunes/dora128_everything_8ep_lr0.5x" \
  --name "dora128_everything_lr0.5x" --logger csv \
  > "$LOG/dora128_everything_lr0.5x.log" 2>&1
echo "[everything_lr0.5x] done ($(date +%H:%M))"
