#!/bin/bash
# Owner: CONTINUITY (created 2026-10-28)
# EXPERIMENTS E21 second run, end to end: GPU lock -> own :8056 -> 238 renders (eval/e21b_transposition_server.py) -> stop server
# -> bungee positive control (pitch venv) -> score -> page (~/evals_aac/e21_transposition.html). Resumable (cells.jsonl).
#   setsid nohup bash eval/run_e21b_20261028.sh </dev/null >/dev/null 2>&1 &
set -u
SAO=/home/kim/Projects/SAO; cd "$SAO" || exit 2
OUT=/run/media/kim/Mantu/sa3_control_runs/e21b_transposition_canon_20261028
LOG=/home/kim/sao_runs/e21b_20261028.log
exec >>"$LOG" 2>&1
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4
# free = no process holds >= 1 GiB of VRAM (W's E18 rule), AND nobody holds a plain `flock /tmp/gpu.lock` (a 2026-10-28 grain_sim job
# took the card that way and the guard could not see it), AND the team guard lets us in.
vram_free() { ! rocm-smi --showpids 2>/dev/null | awk '/^[0-9]+[[:space:]]/ && $4 >= 1073741824 {f=1} END {exit !f}'; }
flock_free() { flock -n /tmp/gpu.lock true 2>/dev/null; }
until vram_free && flock_free && KIND=batch NOTE="CONTINUITY E21b: own :8056 + 238 chroma renders (~2 h)" \
      Misc/gpu_guard.sh acquire CONTINUITY $$ >/dev/null 2>&1; do sleep 60; done
SRV=
cleanup() { [ -n "$SRV" ] && kill "$SRV" 2>/dev/null; Misc/gpu_guard.sh release CONTINUITY >/dev/null 2>&1; }
trap cleanup EXIT
echo "$(date +%H:%M) GPU acquired"
if ! curl -sf -m 5 http://127.0.0.1:8056/status >/dev/null; then
    setsid nohup .venv/bin/python eval/explorer_render_server.py > /home/kim/sao_runs/e21b_render_server.log 2>&1 &
    SRV=$!
    for _ in $(seq 90); do curl -sf -m 5 http://127.0.0.1:8056/status >/dev/null && break; sleep 10; done
fi
curl -sf -m 5 http://127.0.0.1:8056/status >/dev/null || { echo "server not up"; exit 1; }
echo "$(date +%H:%M) server up (pid ${SRV:-external})"
.venv/bin/python eval/e21b_transposition_server.py render
echo "$(date +%H:%M) render done; cells: $(wc -l < "$OUT/cells.jsonl") / 238"
[ -n "$SRV" ] && kill "$SRV" && SRV=
Misc/gpu_guard.sh release CONTINUITY >/dev/null 2>&1
/home/kim/Projects/mir/pitch_venv/bin/python eval/e21_bungee_posctl.py --out "$OUT" --glob "*__k0__g2048.wav" | tail -1
.venv/bin/python eval/e21b_transposition_server.py score
.venv/bin/python Misc/build_e21_transposition_page.py
echo "$(date +%H:%M) ALL DONE"
