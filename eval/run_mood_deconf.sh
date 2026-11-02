#!/usr/bin/env bash
# Owner: WINTERMUTE (created 2026-11-03)
# run_mood_deconf.sh -- eval/mood_deconf_render.py over every model and prompt, in chunks of 5 prompts. The GPU lock is released
# between chunks so a waiting job can take the card. Then CPU texture metrics, Audiobox (GPU, locked) and mood scores (CPU).
# Passes no secrets. Resumable: rerun it and finished clips are skipped.
set -u
SAO=/home/kim/Projects/SAO
OUT=/home/kim/evals_aac/control_runs/mood_deconf_20261103
MIRPY=/home/kim/Projects/mir/mir/bin/python
mkdir -p "$OUT"
exec >> "$OUT/run.log" 2>&1
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2

lock() {  # note
  until KIND=batch NOTE="$1" "$SAO/Misc/gpu_guard.sh" acquire WINTERMUTE $$ >/dev/null 2>&1; do sleep 60; done
}
unlock() { "$SAO/Misc/gpu_guard.sh" release WINTERMUTE >/dev/null 2>&1; }
trap unlock EXIT

cd /tmp || exit 1
PROMPTS=(rb_common_0,rb_common_1,rb_common_2,rb_mid_3,rb_mid_4 rb_mid_5,rb_rare_6,rb_rare_7,rb_rare_8,kl_0 kl_1,kl_2,rb_bracket_0,kl_bracket_0,prompt_dark)
for model in base adamw goa combo_fusion_goa; do
  for chunk in "${PROMPTS[@]}"; do
    lock "mood deconf render, chunk of about 25 min, lock released between chunks"
    echo "$(date '+%F %T') GPU acquired: $model $chunk"
    for attempt in 1 2 3; do
      "$SAO/.venv/bin/python" "$SAO/eval/mood_deconf_render.py" --model "$model" --prompts "$chunk"
      rc=$?
      echo "$(date '+%F %T') $model attempt $attempt rc=$rc"
      [ "$rc" -eq 0 ] && break
      [ "$rc" -eq 4 ] && { echo "disk floor, stopping"; exit 4; }
      sleep 30
    done
    unlock
    sleep 20
  done
done

"$MIRPY" "$SAO/control/sa3_control/clip_metrics.py" --roots control_runs/mood_deconf_20261103 --workers 12
echo "$(date '+%F %T') texture metrics rc=$?"
lock "mood deconf Audiobox scoring"
"$MIRPY" "$SAO/control/sa3_control/clip_metrics_audiobox.py" --roots control_runs --pattern mood_deconf_20261103
echo "$(date '+%F %T') audiobox rc=$?"
unlock
"$MIRPY" "$SAO/eval/mood_deconf_score.py"
echo "$(date '+%F %T') mood scores rc=$?"
echo "$(date '+%F %T') ALL DONE"
