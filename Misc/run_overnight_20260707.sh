#!/bin/bash
# Overnight chain 2026-07-07 (Kim's brief before sleep):
#   A) goa r16 Fusion comparison with the NEW dataset stack (vs HoF x20b3ygb)
#   B) avp (Kim's music, full-mix crops only) r16 DoRA, 8 ep, normal LR
#   C) avp r128 ADJUSTED (rsLoRA alpha=45 ~ alpha/sqrt(r) matched to r16) 8 ep
#   D) avp r16 + familiarity-normalized loss (only if marker file exists =
#      implementation landed + tested; gated so an unfinished feature can't
#      burn a night of GPU)
# Sequential; each stage worklog-noted. MUST be a file (pkill self-match lesson).
set -u
SAO=/home/kim/Projects/SAO
SA3=$SAO/stable-audio-3
PY=$SA3/.venv/bin/python
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2
export PYTHONPATH=$SA3:$SA3/scripts:$SAO/control
cd "$SA3" || exit 1
FT=$SAO/../mir/data/feature_tables
RUNS=/run/media/kim/Mantu1/sa3_lora_runs

note() { "$SAO/Misc/worklog_note.sh" overnight-0707 "$1 ($(date +%H:%M))"; }

# ---- A: goa r16 new-stack comparison -------------------------------------
note "A START — goa r16 fusion, new dataset stack (tiered captions + TrackType 0.5), 8ep"
$PY scripts/train_lora.py \
  --model medium-base \
  --encoded_dir /home/kim/Projects/latents_sa3 \
  --caption-sidecar "$FT/goa/captions.json" --caption_probs 0.6,0.3,0.1 \
  --track_type_prob 0.5 \
  --adapter_type dora-rows --rank 16 --lora_alpha 16 \
  --optimizer fusion --lr 2e-4 \
  --epochs 8 --batch_size 4 --duration 47 --beat-aware-crop \
  --checkpoint_every_epochs 1 --gradient_clip_val 1.0 \
  --base_precision bf16 --no_demos --num_workers 6 --seed 42 \
  --save_dir "$RUNS/dora16_goa_newstack_8ep" \
  --name dora16_goa_newstack --logger csv \
  > "$SAO/logs/dora16_goa_newstack.log" 2>&1
note "A done -> dora16_goa_newstack_8ep (exit $?)"

# ---- B: avp r16, normal LR ------------------------------------------------
note "B START — avp r16 dora-rows fusion lr2e-4 8ep (trigger prompts, full-mix crops)"
$PY scripts/train_lora.py \
  --model medium-base \
  --encoded_dir /home/kim/Projects/latents_avp \
  --adapter_type dora-rows --rank 16 --lora_alpha 16 \
  --optimizer fusion --lr 2e-4 \
  --epochs 8 --batch_size 4 --duration 47 --beat-aware-crop \
  --accumulate_grad_batches 2 \
  --checkpoint_every_epochs 1 --gradient_clip_val 1.0 \
  --base_precision bf16 --no_demos --num_workers 6 --seed 42 \
  --save_dir "$RUNS/dora16_avp_8ep" \
  --name dora16_avp --logger csv \
  > "$SAO/logs/dora16_avp.log" 2>&1
note "B done -> dora16_avp_8ep (exit $?)"

# ---- C: avp r128 adjusted (rsLoRA alpha) ----------------------------------
note "C START — avp r128 ADJUSTED (alpha 45 = rsLoRA alpha/sqrt(r) matched to r16) 8ep"
$PY scripts/train_lora.py \
  --model medium-base \
  --encoded_dir /home/kim/Projects/latents_avp \
  --adapter_type dora-rows --rank 128 --lora_alpha 45 \
  --optimizer fusion --lr 2e-4 \
  --epochs 8 --batch_size 4 --duration 47 --beat-aware-crop \
  --accumulate_grad_batches 2 \
  --checkpoint_every_epochs 1 --gradient_clip_val 1.0 \
  --base_precision bf16 --no_demos --num_workers 6 --seed 42 \
  --save_dir "$RUNS/dora128adj_avp_8ep" \
  --name dora128adj_avp --logger csv \
  > "$SAO/logs/dora128adj_avp.log" 2>&1
note "C done -> dora128adj_avp_8ep (exit $?)"

# ---- D: avp r16 + familiarity-normalized loss (gated) ----------------------
if [ -f "$SAO/.familiarity_ready" ]; then
  note "D START — avp r16 + familiarity-normalized loss, 8ep (otherwise = B)"
  $PY scripts/train_lora.py \
    --model medium-base \
    --encoded_dir /home/kim/Projects/latents_avp \
    --adapter_type dora-rows --rank 16 --lora_alpha 16 \
    --optimizer fusion --lr 2e-4 \
    --epochs 8 --batch_size 4 --duration 47 --beat-aware-crop \
    --accumulate_grad_batches 2 \
    --familiarity_beta 1.0 \
    --checkpoint_every_epochs 1 --gradient_clip_val 1.0 \
    --base_precision bf16 --no_demos --num_workers 6 --seed 42 \
    --save_dir "$RUNS/dora16_avp_familiarity_8ep" \
    --name dora16_avp_familiarity --logger csv \
    > "$SAO/logs/dora16_avp_familiarity.log" 2>&1
  note "D done -> dora16_avp_familiarity_8ep (exit $?)"
else
  note "D SKIPPED — familiarity implementation marker absent"
fi
note "OVERNIGHT CHAIN COMPLETE"
