#!/usr/bin/env bash
# Owner: WINTERMUTE (created 2026-11-03)
# run_d5.sh -- EXPERIMENTS D5 under the GPU lock, then texture metrics and Audiobox. About 20 min.
set -u
SAO=/home/kim/Projects/SAO
OUT=/home/kim/evals_aac/control_runs/d5_adaptive_grid_20261103
MIRPY=/home/kim/Projects/mir/mir/bin/python
mkdir -p "$OUT"
exec >> "$OUT/run.log" 2>&1
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2
cd /tmp || exit 1
until KIND=batch NOTE="D5 adaptive grid, about 15 min" "$SAO/Misc/gpu_guard.sh" acquire WINTERMUTE $$ >/dev/null 2>&1; do sleep 60; done
trap '"$SAO/Misc/gpu_guard.sh" release WINTERMUTE >/dev/null 2>&1' EXIT
"$SAO/.venv/bin/python" -u "$SAO/eval/d5_adaptive_grid.py"
echo "$(date '+%F %T') render rc=$?"
"$MIRPY" "$SAO/control/sa3_control/clip_metrics.py" --roots control_runs/d5_adaptive_grid_20261103 --workers 8
"$MIRPY" "$SAO/control/sa3_control/clip_metrics_audiobox.py" --roots control_runs --pattern d5_adaptive_grid_20261103
echo "$(date '+%F %T') scoring rc=$?"
"$SAO/Misc/gpu_guard.sh" release WINTERMUTE >/dev/null 2>&1
trap - EXIT
echo "$(date '+%F %T') ALL DONE"
