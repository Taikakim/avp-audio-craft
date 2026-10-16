#!/usr/bin/env bash
# Owner: GHOST-NOTE (created 2026-10-16)
# Bass-head weight x target matrices of the final epochs (owner 2026-10-16). Waits until W's FiLM full run is gone (no marker file exists on his side), then renders ~100 clips through :8056.
SAO=/home/kim/Projects/SAO
OUT=/run/media/kim/Mantu/latch_sweep/bass_lr_2026-10-16
busy() { ps -eo args | grep -E "run_film_modular_full|train_control|run_film_e12" | grep -vE "grep|run_bass_grid" | grep -q .; }
n=0; while true; do if busy; then n=0; else n=$((n+1)); fi; [ $n -ge 3 ] && break; sleep 120; done
cd /tmp || exit 1
until "$SAO/Misc/gpu_guard.sh" acquire GHOST-NOTE $$ >/dev/null 2>&1; do sleep 120; done
"$SAO/Misc/gpu_guard.sh" release GHOST-NOTE >/dev/null 2>&1
"$SAO/eval/forge/dev_server.sh" start GHOST-NOTE > /dev/null 2>&1
until curl -s localhost:8056/info >/dev/null 2>&1; do sleep 15; done
"$SAO/.venv/bin/python" "$SAO/eval/bass_head_grid.py" > "$OUT/grid.log" 2>&1
"$SAO/eval/forge/dev_server.sh" stop > /dev/null 2>&1
grep -q "GRID DONE" "$OUT/grid.log" && echo GRID DONE > /tmp/bass_grid.done
