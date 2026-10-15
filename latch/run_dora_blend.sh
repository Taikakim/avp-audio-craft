#!/usr/bin/env bash
# Owner: GHOST-NOTE (created 2026-10-15) -- DoRA block-blend bracket (eval/dora_blend_bracket.py). Runs right after run_air_lowlr.sh (waits for /tmp/air_lowlr.done), restarts the render server so it
# loads the dora.block_strengths patch, renders 4 seeds x 10 arms, writes /tmp/air_dora_blend.done. run_air_big.sh waits for that file.
SAO=/home/kim/Projects/SAO
until [ -f /tmp/air_lowlr.done ]; do sleep 60; done
"$SAO/eval/forge/dev_server.sh" stop > /dev/null 2>&1
"$SAO/eval/forge/dev_server.sh" start GHOST-NOTE > /dev/null 2>&1
until curl -s localhost:8056/info >/dev/null 2>&1; do sleep 15; done
mkdir -p /run/media/kim/Mantu2/latch_sweep/dora_blend_2026-10-15
"$SAO/.venv/bin/python" "$SAO/eval/dora_blend_bracket.py" > /run/media/kim/Mantu2/latch_sweep/dora_blend_2026-10-15/run.log 2>&1
echo DORA BLEND DONE > /tmp/air_dora_blend.done
