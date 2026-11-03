#!/bin/bash
# Last edited: THE-FINN 2026-11-03 — paths updated for the __theme sorting of sa3_lora_runs and latch_sweep
# Continue dora128_47s_newcaptions from ep5 (Kim 2026-07-12: "continue the
# dora128_47s_newcaptions from the ep5 where it's now, until I think of something else").
# ep5 = the _5ep run's last checkpoint (epoch=4-step=6750, 0-indexed epoch 4 = 5 epochs).
# Same recipe as the original 47s newcaptions run (rank128/fusion/lr2e-4/47s/beat-aware),
# TRUE continuation via --warm_start_ckpt (adapter + FusionOpt Schedule-Free state).
# Saves to a NEW dir (does not touch the existing continued_3more branch). Checkpoint every
# epoch so Kim can pick the sweet spot. MUST be a file (inline bash -c pkill self-kill lesson).
set -u
SAO=/home/kim/Projects/SAO
SA3=$SAO/stable-audio-3
PY=$SA3/.venv/bin/python
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2
export PYTHONPATH=$SA3:$SA3/scripts:$SAO/control
cd "$SA3" || exit 1
FT=$SAO/../mir/data/feature_tables
CKPT=/run/media/kim/Mantu/sa3_lora_runs/__finetunes/dora128_47s_newcaptions_5ep/epoch=4-step=6750.ckpt
# allow warm-starting from a later continuation checkpoint on relaunch (Monitor 1h chunks):
# pass $1 = an explicit ckpt path to override (the latest saved cont epoch).
[ $# -ge 1 ] && CKPT="$1"

# Pre-flight: refuse if someone else holds >1.5GB VRAM (the external-pressure OOM lesson).
VRAM_USED=$(rocm-smi --showmeminfo vram --json 2>/dev/null | $PY -c "
import json,sys
d=json.load(sys.stdin)
print(int(next(iter(d.values()))['VRAM Total Used Memory (B)']))" 2>/dev/null || echo 0)
# 2GB gate: catches a real competing job (multi-GB) but allows sub-2GB ROCm driver
# residual left after a prior GPU process exits (observed ~1.54GB, no process, 2026-07-12).
if [ "$VRAM_USED" -gt 2147483648 ]; then
  echo "ABORT: GPU busy (${VRAM_USED} bytes VRAM in use)" >&2
  exit 1
fi

echo "[cont47s] START warm_start=$CKPT ($(date +%H:%M))"
$PY scripts/train_lora.py \
  --model medium-base \
  --encoded_dir /run/media/kim/Kosmos/latents/latents_sa3 \
  --caption-sidecar "$FT/goa/captions.json" \
  --adapter_type dora-rows --rank 128 --lora_alpha 128 \
  --optimizer fusion --lr 2e-4 \
  --epochs 5 --batch_size 4 \
  --duration 47 --beat-aware-crop \
  --checkpoint_every_epochs 1 --gradient_clip_val 1.0 \
  --base_precision bf16 --no_demos --num_workers 6 --seed 42 \
  --exclude seconds_total \
  --warm_start_ckpt "$CKPT" \
  --save_dir /home/kim/Projects/sa3_local_runs/dora128_47s_cont_from5 \
  --name dora128_47s_cont5 --logger csv \
  > "$SAO/logs/dora128_47s_cont5.log" 2>&1
echo "[cont47s] done ($(date +%H:%M))"
