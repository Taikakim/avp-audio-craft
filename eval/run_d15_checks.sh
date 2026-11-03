#!/usr/bin/env bash
# Owner: WINTERMUTE (created 2026-11-03)
# run_d15_checks.sh -- EXPERIMENTS D15: both-branches, second seed, EMA and second-seed-checkpoint checks on the invented melodies. 192 clips, about 25 min under one GPU lock hold.
set -u
SAO=/home/kim/Projects/SAO
NAME=pianoroll_checks_goa_t256_20261103
OUT=/home/kim/evals_aac/control_runs/$NAME
MIRPY=/home/kim/Projects/mir/mir/bin/python
mkdir -p "$OUT"
exec >> "$OUT/run.log" 2>&1
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2
cd /tmp || exit 1
python3 "$SAO/Misc/run_record.py" snapshot "$OUT" "$SAO/eval/run_d15_checks.sh" "$SAO/eval/d15_checks.py"
until KIND=batch NOTE="D15 checks, about 25 min" "$SAO/Misc/gpu_guard.sh" acquire WINTERMUTE $$ >/dev/null 2>&1; do sleep 60; done
trap '"$SAO/Misc/gpu_guard.sh" release WINTERMUTE >/dev/null 2>&1' EXIT
for attempt in 1 2 3 4; do
  "$SAO/.venv/bin/python" -u "$SAO/eval/d15_checks.py" --stage render
  rc=$?
  echo "$(date '+%F %T') render attempt $attempt rc=$rc"
  [ "$(wc -l < "$OUT/cells.jsonl" 2>/dev/null || echo 0)" -ge 192 ] && break
  sleep 20
done
"$SAO/.venv/bin/python" -u "$SAO/eval/d15_checks.py" --stage score
rc=$?
echo "$(date '+%F %T') score rc=$rc"
"$MIRPY" "$SAO/control/sa3_control/clip_metrics.py" --roots "control_runs/$NAME" --workers 8
"$MIRPY" "$SAO/control/sa3_control/clip_metrics_audiobox.py" --roots control_runs --pattern "$NAME"
"$SAO/Misc/gpu_guard.sh" release WINTERMUTE >/dev/null 2>&1
trap - EXIT
"$MIRPY" "$SAO/eval/d15_checks.py" --stage gate
rc=$?
echo "$(date '+%F %T') gate rc=$rc"
echo "$(date '+%F %T') ALL DONE"
