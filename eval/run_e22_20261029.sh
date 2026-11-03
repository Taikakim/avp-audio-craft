#!/bin/bash
# Last edited: THE-FINN 2026-11-03 — paths updated for the sa3_control_runs/__theme reorganisation
# Owner: CONTINUITY (created 2026-10-29)
# EXPERIMENTS E22 root-locked chroma steering (Kim 2026-10-29): GPU lock -> own :8056 (loads the new cosine_rotinv loss)
# -> 224 renders (eval/e22_root_locked_chroma.py) -> stop server -> score. Resumable (cells.jsonl).
#   setsid nohup bash eval/run_e22_20261029.sh </dev/null >/dev/null 2>&1 &
set -u
SAO=/home/kim/Projects/SAO; cd "$SAO" || exit 2
LOG=/home/kim/sao_runs/e22_20261029.log
exec >>"$LOG" 2>&1
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4
vram_free() { ! rocm-smi --showpids 2>/dev/null | awk '/^[0-9]+[[:space:]]/ && $4 >= 1073741824 {f=1} END {exit !f}'; }
until vram_free && KIND=batch NOTE="CONTINUITY E22: own :8056 + 224 chroma renders (~45 min)" \
      Misc/gpu_guard.sh acquire CONTINUITY $$ >/dev/null 2>&1; do sleep 60; done
SRV=
cleanup() { [ -n "$SRV" ] && kill "$SRV" 2>/dev/null; Misc/gpu_guard.sh release CONTINUITY >/dev/null 2>&1; }
trap cleanup EXIT
echo "$(date +%H:%M) GPU acquired"
# a server started before cosine_rotinv existed would reject the loss: always use our own fresh one
if curl -sf -m 5 http://127.0.0.1:8056/status >/dev/null; then echo "a :8056 server is already running; refusing (it may predate cosine_rotinv)"; exit 1; fi
setsid nohup .venv/bin/python eval/explorer_render_server.py > /home/kim/sao_runs/e22_render_server.log 2>&1 &
SRV=$!
for _ in $(seq 90); do curl -sf -m 5 http://127.0.0.1:8056/status >/dev/null && break; sleep 10; done
curl -sf -m 5 http://127.0.0.1:8056/status >/dev/null || { echo "server not up"; exit 1; }
echo "$(date +%H:%M) server up (pid $SRV)"
.venv/bin/python eval/e22_root_locked_chroma.py render
echo "$(date +%H:%M) render done; cells: $(wc -l < /run/media/kim/Mantu/sa3_control_runs/__chroma/e22_root_locked_chroma_20261029/cells.jsonl) / 238"
kill "$SRV"; SRV=
Misc/gpu_guard.sh release CONTINUITY >/dev/null 2>&1
.venv/bin/python eval/e22_root_locked_chroma.py score
echo "$(date +%H:%M) ALL DONE"
