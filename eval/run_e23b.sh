#!/usr/bin/env bash
# Owner: WINTERMUTE (created 2026-11-03)
# run_e23b.sh -- EXPERIMENTS E23 (b): two checkpoints, one fresh process each, lock released between. About 25 min.
set -u
SAO=/home/kim/Projects/SAO
OUT=/home/kim/evals_aac/control_runs/e23b_morph_synth_20261103
MIRPY=/home/kim/Projects/mir/mir/bin/python
mkdir -p "$OUT"
exec >> "$OUT/run.log" 2>&1
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0 PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2
cd /tmp || exit 1
for ck in step4000 step10000; do
  until KIND=batch NOTE="E23b morph conditioner on synthetic contours, about 12 min per checkpoint" "$SAO/Misc/gpu_guard.sh" acquire WINTERMUTE $$ >/dev/null 2>&1; do sleep 60; done
  for attempt in 1 2 3 4; do
    "$SAO/.venv/bin/python" -u "$SAO/eval/e23b_morph_synth.py" --stage render --ck "$ck"
    echo "$(date '+%F %T') $ck attempt $attempt rc=$?"
    [ "$(grep -c "\"ck\": \"$ck\"" "$OUT/cells.jsonl" 2>/dev/null || echo 0)" -ge 66 ] && break
    sleep 20
  done
  "$SAO/Misc/gpu_guard.sh" release WINTERMUTE >/dev/null 2>&1
  sleep 20
done
"$MIRPY" "$SAO/eval/e23b_morph_synth.py" --stage measure
echo "$(date '+%F %T') measure rc=$?"
echo "$(date '+%F %T') ALL DONE"
