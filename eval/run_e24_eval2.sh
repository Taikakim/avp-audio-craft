#!/usr/bin/env bash
# Owner: WINTERMUTE (created 2026-11-03)
# run_e24_eval2.sh <run dir> <pack C|B> <out name> -- EXPERIMENTS E24 second eval: 24 crops x 5 arms + references, MuScriptor, metrics, gate. About 35 min under one GPU lock hold.
set -u
SAO=/home/kim/Projects/SAO
RUN=$1; PACK=$2; NAME=$3
OUT=/home/kim/evals_aac/control_runs/$NAME
MIRPY=/home/kim/Projects/mir/mir/bin/python
mkdir -p "$OUT"
exec >> "$OUT/run.log" 2>&1
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2
cd /tmp || exit 1
until KIND=batch NOTE="E24 eval 2, about 35 min" "$SAO/Misc/gpu_guard.sh" acquire WINTERMUTE $$ >/dev/null 2>&1; do sleep 60; done
trap '"$SAO/Misc/gpu_guard.sh" release WINTERMUTE >/dev/null 2>&1' EXIT
ARGS=(--run "$RUN" --pack "$PACK" --out "$OUT")
for attempt in 1 2 3 4; do
  "$SAO/.venv/bin/python" -u "$SAO/eval/e24_eval2.py" --stage render "${ARGS[@]}"
  rc=$?
  echo "$(date '+%F %T') render attempt $attempt rc=$rc"
  [ "$(wc -l < "$OUT/cells.jsonl" 2>/dev/null || echo 0)" -ge 144 ] && break
  sleep 20
done
"$SAO/.venv/bin/python" -u "$SAO/eval/e24_eval2.py" --stage score "${ARGS[@]}"
rc=$?
echo "$(date '+%F %T') score rc=$rc"
"$MIRPY" "$SAO/control/sa3_control/clip_metrics.py" --roots "control_runs/$NAME" --workers 8
"$MIRPY" "$SAO/control/sa3_control/clip_metrics_audiobox.py" --roots control_runs --pattern "$NAME"
"$SAO/Misc/gpu_guard.sh" release WINTERMUTE >/dev/null 2>&1
trap - EXIT
"$MIRPY" "$SAO/eval/e24_eval2.py" --stage gate "${ARGS[@]}"
rc=$?
echo "$(date '+%F %T') gate rc=$rc"
echo "$(date '+%F %T') ALL DONE"
