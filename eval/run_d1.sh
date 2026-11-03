#!/usr/bin/env bash
# Owner: WINTERMUTE (created 2026-11-03)
# run_d1.sh -- EXPERIMENTS D1, render under the GPU lock (retries resume), then measure on the mir venv (CPU). About 25 min.
set -u
SAO=/home/kim/Projects/SAO
OUT=/home/kim/evals_aac/control_runs/d1_sdedit_survival_20261103
mkdir -p "$OUT"
exec >> "$OUT/run.log" 2>&1
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2
cd /tmp || exit 1
until KIND=batch NOTE="D1 SDEdit survival, about 20 min" "$SAO/Misc/gpu_guard.sh" acquire WINTERMUTE $$ >/dev/null 2>&1; do sleep 60; done
trap '"$SAO/Misc/gpu_guard.sh" release WINTERMUTE >/dev/null 2>&1' EXIT
for attempt in 1 2 3 4; do
  "$SAO/.venv/bin/python" -u "$SAO/eval/d1_sdedit_survival.py" --stage render
  rc=$?
  echo "$(date '+%F %T') render attempt $attempt rc=$rc"
  [ "$(wc -l < "$OUT/cells.jsonl" 2>/dev/null || echo 0)" -ge 240 ] && break
  sleep 20
done
"$SAO/Misc/gpu_guard.sh" release WINTERMUTE >/dev/null 2>&1
trap - EXIT
/home/kim/Projects/mir/mir/bin/python "$SAO/eval/d1_sdedit_survival.py" --stage measure
echo "$(date '+%F %T') measure rc=$?"
echo "$(date '+%F %T') ALL DONE"
