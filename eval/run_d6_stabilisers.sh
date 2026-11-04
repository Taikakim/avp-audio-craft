#!/usr/bin/env bash
# Owner: WINTERMUTE (created 2026-11-04)
# run_d6_stabilisers.sh -- EXPERIMENTS D6, one GPU lock hold. CAPS="clipA=0.02,clipB=0.005" sets the soft caps. STAGE=probe prints step sizes and exits. AFTER_PID waits for that pid first. About 25 min.
set -u
SAO=/home/kim/Projects/SAO
OUT=/home/kim/evals_aac/control_runs/chroma_stabilisers_d6_20261104
NAME=$(basename "$OUT")
MIRPY=/home/kim/Projects/mir/mir/bin/python
STAGE=${STAGE:-render}
mkdir -p "$OUT"
exec >> "$OUT/run.log" 2>&1
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2
export PYTHONPATH="$SAO/stable-audio-3:$SAO/control:${PYTHONPATH:-}"
cd /tmp || exit 1
python3 "$SAO/Misc/run_record.py" snapshot "$OUT" "$SAO/eval/run_d6_stabilisers.sh" "$SAO/eval/d6_stabilisers.py"
while [ -n "${AFTER_PID:-}" ] && kill -0 "$AFTER_PID" 2>/dev/null; do sleep 30; done
until KIND=batch NOTE="D6 chroma stabilisers, $STAGE" "$SAO/Misc/gpu_guard.sh" acquire WINTERMUTE $$ >/dev/null 2>&1; do sleep 30; done
trap '"$SAO/Misc/gpu_guard.sh" release WINTERMUTE >/dev/null 2>&1' EXIT
if [ "$STAGE" = probe ]; then
  "$SAO/.venv/bin/python" -u "$SAO/eval/d6_stabilisers.py" --stage probe
  rc=$?
  echo "$(date '+%F %T') probe rc=$rc"
  exit 0
fi
for attempt in 1 2 3 4; do
  "$SAO/.venv/bin/python" -u "$SAO/eval/d6_stabilisers.py" --stage render ${CAPS:+--clips "$CAPS"}
  rc=$?
  echo "$(date '+%F %T') render attempt $attempt rc=$rc"
  [ "$(wc -l < "$OUT/cells.jsonl" 2>/dev/null || echo 0)" -ge 390 ] && break
  sleep 20
done
"$MIRPY" "$SAO/control/sa3_control/clip_metrics.py" --roots "control_runs/$NAME" --workers 8
"$MIRPY" "$SAO/control/sa3_control/clip_metrics_audiobox.py" --roots control_runs --pattern "$NAME"
"$SAO/Misc/gpu_guard.sh" release WINTERMUTE >/dev/null 2>&1
trap - EXIT
"$MIRPY" "$SAO/eval/d6_stabilisers.py" --stage report
rc=$?
echo "$(date '+%F %T') report rc=$rc"
echo "$(date '+%F %T') ALL DONE"
