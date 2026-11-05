#!/usr/bin/env bash
# Owner: WINTERMUTE (created 2026-11-04)
# run_chroma_turn_strong.sh -- EXPERIMENTS B6b: July's melody-turning test with the strong chroma head, and D15's invented melodies through guidance. About 195 clips, 25 min under one GPU lock hold.
set -u
SAO=/home/kim/Projects/SAO
OUT=/home/kim/evals_aac/control_runs/chroma_turning_strong_20261104
NAME=$(basename "$OUT")
MIRPY=/home/kim/Projects/mir/mir/bin/python
N=${N:-195}
mkdir -p "$OUT"
exec >> "$OUT/run.log" 2>&1
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2
export PYTHONPATH="$SAO/stable-audio-3:$SAO/control:$SAO/stable-audio-3/scripts:${PYTHONPATH:-}"
cd /tmp || exit 1
python3 "$SAO/Misc/run_record.py" snapshot "$OUT" "$SAO/eval/run_chroma_turn_strong.sh" "$SAO/eval/chroma_turn_strong.py"
until KIND=batch NOTE="B6b chroma melody turning, about 25 min" "$SAO/Misc/gpu_guard.sh" acquire WINTERMUTE $$ >/dev/null 2>&1; do sleep 30; done
trap '"$SAO/Misc/gpu_guard.sh" release WINTERMUTE >/dev/null 2>&1' EXIT
for attempt in 1 2 3 4; do
  "$SAO/.venv/bin/python" -u "$SAO/eval/chroma_turn_strong.py" --stage render
  rc=$?
  echo "$(date '+%F %T') render attempt $attempt rc=$rc"
  [ "$(wc -l < "$OUT/cells.jsonl" 2>/dev/null || echo 0)" -ge "$N" ] && break
  sleep 20
done
"$SAO/.venv/bin/python" -u "$SAO/eval/chroma_turn_strong.py" --stage score
rc=$?
echo "$(date '+%F %T') score rc=$rc"
"$MIRPY" "$SAO/control/sa3_control/clip_metrics.py" --roots "control_runs/$NAME" --workers 8
"$MIRPY" "$SAO/control/sa3_control/clip_metrics_audiobox.py" --roots control_runs --pattern "$NAME"
"$SAO/Misc/gpu_guard.sh" release WINTERMUTE >/dev/null 2>&1
trap - EXIT
"$MIRPY" "$SAO/eval/chroma_turn_strong.py" --stage gate
rc=$?
echo "$(date '+%F %T') gate rc=$rc"
echo "$(date '+%F %T') ALL DONE"
