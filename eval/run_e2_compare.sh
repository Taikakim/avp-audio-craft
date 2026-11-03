#!/usr/bin/env bash
# Owner: WINTERMUTE (created 2026-11-03)
# run_e2_compare.sh -- EXPERIMENTS E2 steering comparison: render under the GPU lock (retries resume), score, measure. About 20 min.
set -u
SAO=/home/kim/Projects/SAO
OUT=/home/kim/evals_aac/control_runs/e2_f0_compare_20261103
MIRPY=/home/kim/Projects/mir/mir/bin/python
mkdir -p "$OUT"
exec >> "$OUT/run.log" 2>&1
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2
cd /tmp || exit 1
until KIND=batch NOTE="E2 steering comparison, about 15 min" "$SAO/Misc/gpu_guard.sh" acquire WINTERMUTE $$ >/dev/null 2>&1; do sleep 60; done
trap '"$SAO/Misc/gpu_guard.sh" release WINTERMUTE >/dev/null 2>&1' EXIT
for attempt in 1 2 3 4 5; do
  "$SAO/.venv/bin/python" -u "$SAO/eval/e2_f0_compare.py" --stage render
  echo "$(date '+%F %T') render attempt $attempt rc=$?"
  [ "$(wc -l < "$OUT/cells.jsonl" 2>/dev/null || echo 0)" -ge 432 ] && break
  sleep 20
done
"$MIRPY" "$SAO/control/sa3_control/clip_metrics.py" --roots control_runs/e2_f0_compare_20261103 --workers 8
"$MIRPY" "$SAO/control/sa3_control/clip_metrics_audiobox.py" --roots control_runs --pattern e2_f0_compare_20261103
"$SAO/Misc/gpu_guard.sh" release WINTERMUTE >/dev/null 2>&1
trap - EXIT
"$MIRPY" "$SAO/eval/e2_f0_compare.py" --stage measure
echo "$(date '+%F %T') measure rc=$?"
echo "$(date '+%F %T') ALL DONE"
