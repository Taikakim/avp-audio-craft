#!/bin/bash
# Continued goa-newcaptions DoRA: 3 more epochs on the epoch-4 adapter (Kim's
# "continue first" run, deferred until the everything-chain freed the GPU).
# Runs in stable-audio-3/.venv (torch 2.10 + G's from-source CK) = matches the
# original newcaptions run's venv AND the comparison baseline, now fast.
# TRUE continuation via --warm_start_ckpt (scripts/warm_start.py): adapter
# weights + full FusionOpt state (Schedule-Free z/x iterates) restored from the
# old-format ckpt that trainer.fit(ckpt_path=...) rejects; only epoch/step
# numbering restarts, so --epochs 3 = the 3 additional epochs.
# MUST be a file (inline bash -c pkill self-kill lesson).
# History: attempt 1 (07-05) died on the ckpt_path KeyError; attempt 2 (07-06
# 01:11) died on HIP OOM from EXTERNAL VRAM pressure (only 7.1GB allocated on
# the 16GB card) — hence the pre-flight VRAM gate below.
set -u
SAO=/home/kim/Projects/SAO
SA3=$SAO/stable-audio-3
PY=$SA3/.venv/bin/python            # stable venv, now has CK
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2
export PYTHONPATH=$SA3:$SA3/scripts:$SAO/control
cd "$SA3" || exit 1
FT=$SAO/../mir/data/feature_tables
# Kim disconnected Mantu1 for a few hours (2026-07-06 evening) — ckpt copied to
# NVMe and outputs land there too; rsync results back to Mantu1/sa3_lora_runs
# when the drive returns.
CKPT=/home/kim/Projects/sa3_local_runs/epoch=4-step=6750.ckpt

# Pre-flight: refuse to start if someone else holds >1.5GB VRAM (the 01:11
# OOM lesson — this run needs most of the card).
VRAM_USED=$(rocm-smi --showmeminfo vram --json 2>/dev/null | $PY -c "
import json,sys
d=json.load(sys.stdin)
print(int(next(iter(d.values()))['VRAM Total Used Memory (B)']))" 2>/dev/null || echo 0)
if [ "$VRAM_USED" -gt 1610612736 ]; then
  "$SAO/Misc/worklog_note.sh" continued-goa "ABORT — GPU busy (${VRAM_USED}B VRAM in use), not starting ($(date +%H:%M))"
  echo "ABORT: GPU busy (${VRAM_USED} bytes VRAM in use)" >&2
  exit 1
fi

"$SAO/Misc/worklog_note.sh" continued-goa "START — 3 more epochs on newcaptions ep4 (stable/CK venv) ($(date +%H:%M))"
$PY scripts/train_lora.py \
  --model medium-base \
  --encoded_dir /home/kim/Projects/latents_sa3 \
  --caption-sidecar "$FT/goa/captions.json" \
  --adapter_type dora-rows --rank 128 --lora_alpha 128 \
  --optimizer fusion --lr 2e-4 \
  --epochs 3 --batch_size 4 \
  --duration 47 --beat-aware-crop \
  --checkpoint_every_epochs 1 --gradient_clip_val 1.0 \
  --base_precision bf16 --no_demos --num_workers 6 --seed 42 \
  --exclude seconds_total \
  --warm_start_ckpt "$CKPT" \
  --save_dir /home/kim/Projects/sa3_local_runs/dora128_newcap_continued_3more \
  --name dora128_newcap_cont3 --logger csv \
  > "$SAO/logs/dora128_newcap_continued3.log" 2>&1
"$SAO/Misc/worklog_note.sh" continued-goa "done — 3 more epochs -> dora128_newcap_continued_3more (now 8ep total) ($(date +%H:%M))"
