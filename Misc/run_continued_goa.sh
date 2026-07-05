#!/bin/bash
# Continued goa-newcaptions DoRA: 3 more epochs on the epoch-4 adapter (Kim's
# "continue first" run, deferred until the everything-chain freed the GPU).
# Runs in stable-audio-3/.venv (torch 2.10 + G's from-source CK) = matches the
# original newcaptions run's venv AND the comparison baseline, now fast.
# Weights-continuation via --lora_checkpoint (reliable): the existing ckpt
# predates the on_save_checkpoint fix, so full optimizer-state resume isn't
# available on it; optimizer re-warms in a few steps (negligible over 3 epochs).
# MUST be a file (inline bash -c pkill self-kill lesson).
set -u
SAO=/home/kim/Projects/SAO
SA3=$SAO/stable-audio-3
PY=$SA3/.venv/bin/python            # stable venv, now has CK
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2
export PYTHONPATH=$SA3:$SA3/scripts:$SAO/control
cd "$SA3" || exit 1
FT=$SAO/../mir/data/feature_tables
CKPT=/run/media/kim/Mantu/sa3_lora_runs/dora128_47s_newcaptions_5ep/epoch=4-step=6750.ckpt

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
  --lora_checkpoint "$CKPT" \
  --save_dir /run/media/kim/Mantu/sa3_lora_runs/dora128_newcap_continued_3more \
  --name dora128_newcap_cont3 --logger csv \
  > "$SAO/logs/dora128_newcap_continued3.log" 2>&1
"$SAO/Misc/worklog_note.sh" continued-goa "done — 3 more epochs -> dora128_newcap_continued_3more (now 8ep total) ($(date +%H:%M))"
