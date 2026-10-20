#!/usr/bin/env bash
# Owner: GHOST-NOTE (created 2026-10-20)
# Waits for the GPU (Antigravity), starts a render server on post-trained medium, runs eval/mixtape_anchor_smoke.py, stops the server, releases the lock.
SAO=/home/kim/Projects/SAO
PY=$SAO/.venv/bin/python
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0
rm -f /tmp/mixtape_anchor_smoke.done
until "$SAO/Misc/gpu_guard.sh" acquire GHOST-NOTE $$ >/dev/null 2>&1; do sleep 120; done
cd "$SAO" && setsid nohup $PY eval/explorer_render_server.py --model medium > /tmp/mixtape_smoke_server.log 2>&1 &
SPID=$!
for i in $(seq 1 90); do curl -sf http://127.0.0.1:8056/status >/dev/null && break; sleep 10; done
cd /tmp && $PY "$SAO/eval/mixtape_anchor_smoke.py" > /tmp/mixtape_anchor_smoke.log 2>&1
rc=$?
kill $SPID 2>/dev/null; sleep 5; kill -9 $SPID 2>/dev/null
"$SAO/Misc/gpu_guard.sh" release GHOST-NOTE >/dev/null 2>&1
n=$(wc -l < /run/media/kim/Mantu/sa3_lora_runs/mixtape_anchor_smoke_2026-10-20/cells.jsonl 2>/dev/null)
[ "$rc" = 0 ] && [ "${n:-0}" -ge 25 ] && echo "DONE n=$n" > /tmp/mixtape_anchor_smoke.done
