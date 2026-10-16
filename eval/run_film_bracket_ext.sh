#!/bin/bash
# Owner: WINTERMUTE (created 2026-10-16)
# run_film_bracket_ext.sh -- the E12 FiLM bracket density check extended to per-arm gain ladders x requests 3/5/7/9/12 (258 new renders,
# ~35 min) after the first listen ("the density seems to have little effect, mostly it coming from weight"). Waits for the E12 night chain
# and the anchor-sweep extension to exit, then for a free GPU; starts the render server under WINTERMUTE, renders the missing cells
# (eval/film_bracket_density_check.py is resumable), stops the server, rebuilds + publishes film_bracket_check.html.
#   bash eval/run_film_bracket_ext.sh        (run in background)
set -u
SAO=/home/kim/Projects/SAO
OUT=/run/media/kim/Mantu/sa3_control_runs/film_bracket_density_check_20261016
DEST_FILE=/tmp/claude-1000/-home-kim-Projects-mir/b207d8c1-afa9-47b8-bbe0-60db9d0c4899/scratchpad/dest
cd "$SAO" || exit 2
while pgrep -f "^bash (/home/kim/Projects/SAO/)?eval/run_(film_e12_night|anchor_sweep_ext)\.sh$" >/dev/null; do
    echo "$(date +%H:%M) waiting for the night chain / anchor extension"; sleep 300
done
vram_free() { ! rocm-smi --showpids 2>/dev/null | grep -qE '^[0-9]+[[:space:]]'; }
until curl -sf -m 5 http://127.0.0.1:8056/status >/dev/null || { vram_free && eval/forge/dev_server.sh start WINTERMUTE >/dev/null 2>&1; }; do
    echo "$(date +%H:%M) GPU busy, waiting"; sleep 120
done
until curl -sf -m 5 http://127.0.0.1:8056/status >/dev/null; do sleep 20; done
echo "$(date +%H:%M) server up: FiLM bracket extension"
"$SAO/.venv/bin/python" eval/film_bracket_density_check.py > "$OUT/ext.log" 2>&1
echo "$(date +%H:%M) cells written: $(wc -l < "$OUT/cells.jsonl") / 632"
# only my own server (2026-10-16: an unconditional stop killed GHOST-NOTE's server mid-grid)
grep -qs "^WINTERMUTE" "$HOME/.cache/latent-forge/server.8056.holder" && eval/forge/dev_server.sh stop
python3 Misc/build_film_bracket_check_page.py && [ -f "$DEST_FILE" ] && D=$(cat "$DEST_FILE") && \
    rsync -a "$HOME/evals_aac/film_bracket_check" "$D" && rsync -a "$HOME/evals_aac/film_bracket_check.html" "$D" && echo "$(date +%H:%M) page published"
echo "$(date +%H:%M) ALL DONE"
