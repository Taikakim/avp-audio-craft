#!/usr/bin/env bash
# Owner: WINTERMUTE (created 2026-11-03)
# run_e13_fix.sh -- E13 baselines without expandable_segments, re-score, report. The page is rebuilt separately. About 6 min.
set -u
SAO=/home/kim/Projects/SAO
OUT=/home/kim/evals_aac/control_runs/chroma_e13_20261028
MIRPY=/home/kim/Projects/mir/mir/bin/python
exec >> "$OUT/run_fix.log" 2>&1
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2
cd /tmp || exit 1
until KIND=batch NOTE="E13 baseline fix, about 6 min" "$SAO/Misc/gpu_guard.sh" acquire WINTERMUTE $$ >/dev/null 2>&1; do sleep 60; done
trap '"$SAO/Misc/gpu_guard.sh" release WINTERMUTE >/dev/null 2>&1' EXIT
"$SAO/.venv/bin/python" -u "$SAO/eval/e13_fix_baselines.py"
echo "$(date '+%F %T') render rc=$?"
"$MIRPY" "$SAO/control/sa3_control/clip_metrics.py" --roots control_runs/chroma_e13_20261028 --workers 8
"$MIRPY" "$SAO/control/sa3_control/clip_metrics_audiobox.py" --roots control_runs --pattern chroma_e13_20261028
echo "$(date '+%F %T') scoring rc=$?"
"$SAO/Misc/gpu_guard.sh" release WINTERMUTE >/dev/null 2>&1
trap - EXIT
cp "$OUT/report.json" "$OUT/report_before_baseline_fix.json"
"$MIRPY" "$SAO/eval/chroma_e13_report.py"
echo "$(date '+%F %T') ALL DONE"
