#!/usr/bin/env bash
# Owner: GHOST-NOTE (created 2026-10-15) -- runs eval/latch_crosstalk.py in the next GPU gap (queues on the lock; the render server must be stopped by whoever holds it).
SAO=/home/kim/Projects/SAO; OUT=/run/media/kim/Mantu/latch_sweep/crosstalk_2026-10-15
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0
mkdir -p "$OUT"; cd /tmp || exit 1
until "$SAO/Misc/gpu_guard.sh" acquire GHOST-NOTE $$ >/dev/null 2>&1; do sleep 60; done
"$SAO/.venv/bin/python" "$SAO/eval/latch_crosstalk.py" run > "$OUT/run.log" 2>&1
"$SAO/Misc/gpu_guard.sh" release GHOST-NOTE >/dev/null 2>&1
/home/kim/Projects/mir/mir/bin/python "$SAO/eval/air_realised_levels.py" "$OUT/audit" > "$OUT/realised.log" 2>&1
"$SAO/.venv/bin/python" "$SAO/eval/latch_crosstalk.py" report > "$OUT/report.txt" 2>&1
echo CROSSTALK DONE > /tmp/air_crosstalk.done
