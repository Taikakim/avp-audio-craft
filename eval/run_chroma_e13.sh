#!/bin/bash
# Owner: WINTERMUTE (created 2026-10-28)
# EXPERIMENTS E13 eval: wait for the GPU lock, render the chroma-head screen + gain ladder (eval/chroma_e13_render.py),
# score texture (CPU) and Audiobox (GPU) into clip_metrics.db, release the lock, write the report.
# Log: /home/kim/evals_aac/control_runs/chroma_e13_20261028/run.log
set -u
SAO=/home/kim/Projects/SAO
OUT=/home/kim/evals_aac/control_runs/chroma_e13_20261028
MIRPY=/home/kim/Projects/mir/mir/bin/python
mkdir -p "$OUT"
exec >> "$OUT/run.log" 2>&1
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2
echo "$(date '+%F %T') waiting for the GPU lock"
until KIND=batch NOTE="E13 chroma head eval, ~3 h" "$SAO/Misc/gpu_guard.sh" acquire WINTERMUTE $$ >/dev/null 2>&1; do sleep 120; done
trap '"$SAO/Misc/gpu_guard.sh" release WINTERMUTE >/dev/null 2>&1' EXIT
echo "$(date '+%F %T') GPU acquired"
cd /tmp || exit 1
# resumable: retry up to 5 times (the first attempt OOMed after 142 clips, 2026-10-28)
for attempt in 1 2 3 4 5; do
  "$SAO/.venv/bin/python" "$SAO/eval/chroma_e13_render.py" "$@"
  rc=$?
  echo "$(date '+%F %T') render attempt $attempt rc=$rc"
  [ $rc -eq 0 ] && break
  sleep 60
done
"$MIRPY" "$SAO/control/sa3_control/clip_metrics.py" --roots control_runs/chroma_e13_20261028 --workers 12
echo "$(date '+%F %T') texture metrics rc=$?"
"$MIRPY" "$SAO/control/sa3_control/clip_metrics_audiobox.py" --roots control_runs --pattern chroma_e13_20261028
echo "$(date '+%F %T') audiobox rc=$?"
"$SAO/Misc/gpu_guard.sh" release WINTERMUTE >/dev/null 2>&1
trap - EXIT
echo "$(date '+%F %T') GPU released"
if [ -f "$SAO/eval/chroma_e13_report.py" ]; then
  "$MIRPY" "$SAO/eval/chroma_e13_report.py"
  echo "$(date '+%F %T') report rc=$?"
fi
echo "$(date '+%F %T') ALL DONE"
