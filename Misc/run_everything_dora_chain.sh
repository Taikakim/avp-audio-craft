#!/bin/bash
# "Everything we got" DoRA chain (Kim 2026-07-05): two 8-epoch runs on ALL 5
# corpora (goa + 4 new), new tiered captions, at normal (2e-4) and 3x (6e-4) LR.
# MUST be a file (inline bash -c pkill self-kill lesson, see run_composed_v2_rerender.sh).
# Natural per-crop proportions (goa ~88%); source_weights left default — flagged to Kim.
set -u
SAO=/home/kim/Projects/SAO
SA3=$SAO/stable-audio-3
# SAO/.venv = torch 2.14 / ROCm 7.15 with the COMPILED CK flash-attn .so (the fast
# path). stable-audio-3/.venv lacks the .so -> Triton fallback (~2x slower). Per
# MASTER venv-per-task: SA3 training belongs in SAO/.venv. stable_audio_3 isn't
# pip-installed there, so PYTHONPATH resolves it.
PY=$SAO/.venv/bin/python
export PYTHONPATH=$SA3:$SA3/scripts:$SAO/control
MANTU=/run/media/kim/Mantu
FT=$SAO/../mir/data/feature_tables
LOG=$SAO/logs
note() { "$SAO/Misc/worklog_note.sh" everything-dora "$1 ($(date +%H:%M))"; }

export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2
cd "$SA3" || exit 1

DIRS=/home/kim/Projects/latents_sa3,/home/kim/Projects/latents_organic_dance,/home/kim/Projects/latents_chill,/home/kim/Projects/latents_prog_trance_melodic_techno,/home/kim/Projects/latents_prog_psytechno
SIDE=$FT/goa/captions.json,$FT/organic_dance/captions.json,$FT/chill/captions.json,$FT/prog_trance_melodic_techno/captions.json,$FT/prog_psytechno/captions.json

run() {  # $1=lr  $2=tag
  $PY scripts/train_lora.py \
    --model medium-base \
    --encoded_dir "$DIRS" --caption-sidecar "$SIDE" \
    --adapter_type dora-rows --rank 128 --lora_alpha 128 \
    --optimizer fusion --lr "$1" \
    --epochs 8 --batch_size 4 \
    --duration 47 --beat-aware-crop \
    --checkpoint_every_epochs 1 --gradient_clip_val 1.0 \
    --base_precision bf16 --no_demos --num_workers 6 --seed 42 \
    --exclude seconds_total \
    --save_dir "$MANTU/sa3_lora_runs/dora128_everything_8ep_$2" \
    --name "dora128_everything_$2" --logger csv \
    > "$LOG/dora128_everything_$2.log" 2>&1
}

note "chain START — everything (5 corpora, 6110 crops), 2 runs 8ep @ 2e-4 and 6e-4"
run 2e-4 lr1x
note "run 1/2 done (lr 2e-4) -> dora128_everything_8ep_lr1x"
run 6e-4 lr3x
note "run 2/2 done (lr 6e-4 = 3x) -> dora128_everything_8ep_lr3x — chain COMPLETE"
