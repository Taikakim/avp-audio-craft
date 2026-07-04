#!/bin/bash
# Weight-garden free-rein chain (Kim 2026-07-04: "generate clips at various
# parameters... try with style/density guidance... 5EP LoRA on a glitched model
# at 2x normal LR"). Serial GPU stages; each stage logs a WORKLOG note.
# MUST live as a file (inline bash -c self-kill lesson, see run_composed_v2_rerender.sh).
set -u
SAO=/home/kim/Projects/SAO
SA3=$SAO/stable-audio-3
PY=$SA3/.venv/bin/python
MANTU=/run/media/kim/Mantu
GARDEN=$MANTU/sa3_mutated_checkpoints
LOG=$SAO/logs
note() { "$SAO/Misc/worklog_note.sh" weight-garden "$1 ($(date +%H:%M))"; }

export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2

# ---- stage 0: wait for the running tour to finish
while pgrep -f "mutate_weights.py --tour" >/dev/null; do sleep 20; done
note "tour done -> $GARDEN/weight_garden_tour"

# ---- stage 1: extended parameter exploration (18 conditions, 2 prompts)
cd "$SA3" || exit 1
$PY scripts/mutate_weights.py \
  --conditions scripts/conditions_explore_batch1.json \
  --out-dir "$GARDEN/weight_garden_explore1" \
  --prompt "aggressive upbeat goa trance" \
  --prompt "sparse ambient soundscape, evolving granular textures, no drums" \
  --seed 1234 --life-generations 6 \
  > "$LOG/weight_garden_explore1.log" 2>&1
note "explore batch1 done ($(grep -c '\[render\]' "$LOG/weight_garden_explore1.log") renders) -> $GARDEN/weight_garden_explore1"

# ---- stage 2: glitched base x full guidance stack (DoRA + onset + style)
GLITCH_A='{"name":"drift_attn_06","ops":[{"op":"drift","amount":0.06}],"target":"attn","decay_rate":0.3,"mutation_seed":777}'
GLITCH_B='{"name":"tilt_tail_08","ops":[{"op":"tilt","amount":0.8}],"decay_rate":0.3,"mutation_seed":777}'
for PAIR in "A|$GLITCH_A|driftattn" "B|$GLITCH_B|tilttail"; do
  IFS='|' read -r _ RECIPE TAG <<< "$PAIR"
  $PY "$SAO/control/sa3_control/multi_adapter_onset_eval.py" \
    --dora-ckpt "$MANTU/sa3_lora_runs/soups_dora/r128f_expasc.ckpt" \
    --onset-ckpt "$MANTU/sa3_control_runs/onset_FUSION_lr2e5_40epoch/soup_exppeak.pt" \
    --style-ckpt "$MANTU/sa3_control_runs/style_fpC_genrecc/riffer_final.pt" \
    --reference-latent /home/kim/Projects/latents_sa3/003231.npy \
    --densities 7 --onset-gains 2.2 --style-gains 0.25,0.5 \
    --glitch "$RECIPE" \
    --notes "glitched-base ($TAG) x DoRA+onset+style stack — does guidance survive weight mutation?" \
    --out-dir "$MANTU/sa3_lora_runs/sa3_multihead_glitch_$TAG" \
    > "$LOG/multihead_glitch_$TAG.log" 2>&1
done
note "glitch x guidance grids done -> sa3_multihead_glitch_{driftattn,tilttail}"

# ---- stage 3: healing experiment — 5ep DoRA at 2x normal LR on glitched base
# normal = launch_dora recipe (dora-rows r16 a16 bs8 ga16 lr1e-4); here lr 2e-4, 5 epochs.
GLITCH_TRAIN='{"name":"glitch_drift005_late03","ops":[{"op":"drift","amount":0.05}],"decay_rate":0.3,"mutation_seed":777}'
$PY scripts/train_lora.py \
  --model medium-base \
  --encoded_dir /run/media/kim/Lehto/latents_sa3_lora300 \
  --adapter_type dora-rows --rank 16 --lora_alpha 16 \
  --epochs 5 --batch_size 8 --accumulate_grad_batches 16 \
  --checkpoint_every_epochs 1 --gradient_clip_val 1.0 \
  --lr 2e-4 --base_precision bf16 --no_demos \
  --duration 120 --num_workers 6 --seed 42 \
  --exclude seconds_total \
  --glitch "$GLITCH_TRAIN" \
  --save_dir "$MANTU/sa3_lora_runs/dora16_glitchheal_5ep_2xlr" \
  --name dora16_glitchheal --logger csv \
  > "$LOG/dora16_glitchheal.log" 2>&1
note "glitch-heal training done (5ep 2xLR on drift_x005 base) -> sa3_lora_runs/dora16_glitchheal_5ep_2xlr"
