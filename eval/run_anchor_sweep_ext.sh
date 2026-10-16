#!/bin/bash
# Owner: WINTERMUTE (created 2026-10-16)
# run_anchor_sweep_ext.sh -- the punch air + FiLM anchor sweep extended to anchors 1.3 / 1.4 / 1.5 (54 renders, ~15 min) after the listening
# verdict that anchors below 1.2 drone and squash dynamics. Small slot: waits for the E12 night chain to exit, then for a free GPU, starts the
# render server :8056 under WINTERMUTE, renders the missing cells (eval/punch_air_film_anchor_sweep.py is resumable), encodes, scores on CPU,
# rebuilds + publishes punch_air_film.html, stops the server.
#   bash eval/run_anchor_sweep_ext.sh        (run in background)
set -u
SAO=/home/kim/Projects/SAO
OUT=/run/media/kim/Mantu/sa3_control_runs/punch_air_film_anchor_sweep_20261015
STAGE=$HOME/evals_aac/punch_air_film_anchor_sweep
MIR_PY=/home/kim/Projects/mir/mir/bin/python
DEST_FILE=/tmp/claude-1000/-home-kim-Projects-mir/b207d8c1-afa9-47b8-bbe0-60db9d0c4899/scratchpad/dest
cd "$SAO" || exit 2
while pgrep -f "^bash (/home/kim/Projects/SAO/)?eval/run_film_e12_night\.sh$" >/dev/null; do
    echo "$(date +%H:%M) E12 night chain still running"; sleep 300
done
vram_free() { ! rocm-smi --showpids 2>/dev/null | grep -qE '^[0-9]+[[:space:]]'; }
until curl -sf -m 5 http://127.0.0.1:8056/status >/dev/null || { vram_free && eval/forge/dev_server.sh start WINTERMUTE >/dev/null 2>&1; }; do
    echo "$(date +%H:%M) GPU busy, waiting"; sleep 120
done
until curl -sf -m 5 http://127.0.0.1:8056/status >/dev/null; do sleep 20; done
echo "$(date +%H:%M) server up: anchor sweep extension"
"$SAO/.venv/bin/python" eval/punch_air_film_anchor_sweep.py render
echo "$(date +%H:%M) cells written: $(wc -l < "$OUT/cells.jsonl") / 144"
# only my own server (2026-10-16: an unconditional stop here killed GHOST-NOTE's server mid-grid)
grep -qs "^WINTERMUTE" "$HOME/.cache/latent-forge/server.8056.holder" && eval/forge/dev_server.sh stop
mkdir -p "$STAGE"
for w in "$OUT"/*.wav; do
    d="$STAGE/$(basename "$w" .wav).m4a"; [ -f "$d" ] || echo "$w $d"
done | xargs -r -P 12 -n 2 sh -c 'ffmpeg -nostdin -y -loglevel error -i "$0" -c:a aac -b:a 128k "$1"'
"$MIR_PY" control/sa3_control/clip_metrics.py --roots punch_air_film_anchor_sweep --workers 12 2>&1 | tail -1
"$MIR_PY" -c "
import runpy, sys, torch
torch.cuda.is_available = lambda: False
torch.set_num_threads(12)
sys.argv = ['clip_metrics_audiobox.py', '--roots', 'punch_air_film_anchor_sweep']
runpy.run_path('control/sa3_control/clip_metrics_audiobox.py', run_name='__main__')" 2>&1 | tail -1
python3 Misc/build_punch_air_film_page.py && [ -f "$DEST_FILE" ] && D=$(cat "$DEST_FILE") && \
    rsync -a "$STAGE" "$D" && rsync -a "$HOME/evals_aac/punch_air_film.html" "$D" && echo "$(date +%H:%M) page published"
echo "$(date +%H:%M) ALL DONE"
