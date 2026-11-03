#!/usr/bin/env bash
# Owner: CONTINUITY (created 2026-11-03)
# run_e25b.sh -- EXPERIMENTS E25b. Waits its turn on the GPU, renders the clips still missing, lock released between models, then scores. Resumable.
#   setsid nohup bash eval/run_e25b.sh </dev/null >/dev/null 2>&1 &
set -u
SAO=/home/kim/Projects/SAO
OUT=/home/kim/evals_aac/control_runs/e25b_caption_words_20261103
MIRPY=/home/kim/Projects/mir/mir/bin/python
mkdir -p "$OUT"; exec >> "$OUT/run.log" 2>&1
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2
vram_free() { ! rocm-smi --showpids 2>/dev/null | awk '/^[0-9]+[[:space:]]/ && $4 >= 1073741824 {f=1} END {exit !f}'; }
lock() { until vram_free && KIND=batch NOTE="$1" "$SAO/Misc/gpu_guard.sh" acquire CONTINUITY $$ >/dev/null 2>&1; do sleep 60; done; }
unlock() { "$SAO/Misc/gpu_guard.sh" release CONTINUITY >/dev/null 2>&1; }
trap unlock EXIT
cd "$SAO" || exit 2
for m in base goa; do
  lock "E25b caption-word renders, $m, about 25 min"
  echo "$(date '+%F %T') GPU acquired: $m"
  for attempt in 1 2 3; do .venv/bin/python eval/e25b_caption_words.py --model "$m"; rc=$?; echo "$(date '+%F %T') $m attempt $attempt rc=$rc"; [ "$rc" -eq 0 ] && break; sleep 30; done
  unlock; sleep 20
done
"$MIRPY" eval/e25b_score.py; echo "$(date '+%F %T') scores rc=$?"
lock "E25b Audiobox scoring"
"$MIRPY" control/sa3_control/clip_metrics_audiobox.py --roots control_runs --pattern e25b_caption_words_20261103; echo "$(date '+%F %T') audiobox rc=$?"
unlock
echo "$(date '+%F %T') ALL DONE"
