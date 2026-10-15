#!/bin/bash
# Owner: WINTERMUTE (created 2026-10-15)
# run_latch_film_e8.sh -- EXPERIMENTS E8 (timestep-gated FiLM) end to end, as a client of the render server :8056.
# Waits for E7's runner to finish first (E7's punch context loads a DoRA; interleaving the two would rebuild the
# model on every request), then for the server; renders 84 cells, encodes, scores on CPU (the server holds the GPU).
#   bash eval/run_latch_film_e8.sh        (run in background; exit = done; resumable)
set -u
SAO=/home/kim/Projects/SAO
OUT=/run/media/kim/Mantu2/sa3_control_runs/latch_film_e8_20261015
STAGE=$HOME/evals_aac/latch_film_e8
MIR_PY=/home/kim/Projects/mir/mir/bin/python
cd "$SAO" || exit 2

# Anchored: a chain whose own command line merely MENTIONS the E7 runner must not count (that kept E8 waiting forever, 16:18).
while pgrep -f "^bash (/home/kim/Projects/SAO/)?eval/run_latch_film_combo_e7\.sh$" >/dev/null; do
    echo "$(date +%H:%M) E7 still running, waiting"; sleep 120
done
until curl -sf -m 5 http://127.0.0.1:8056/status >/dev/null; do
    echo "$(date +%H:%M) render server down, waiting"; sleep 120
done
echo "$(date +%H:%M) server up"

"$SAO/.venv/bin/python" eval/latch_film_e8.py render
echo "$(date +%H:%M) render rc=$?; cells written: $(wc -l < "$OUT/cells.jsonl") / 84"

mkdir -p "$STAGE"
for w in "$OUT"/*/*.wav; do
    sub=$(basename "$(dirname "$w")"); mkdir -p "$STAGE/$sub"
    d="$STAGE/$sub/$(basename "$w" .wav).m4a"
    [ -f "$d" ] || echo "$w $d"
done | xargs -r -P 12 -n 2 sh -c 'ffmpeg -nostdin -y -loglevel error -i "$0" -c:a aac -b:a 128k "$1"'
"$MIR_PY" control/sa3_control/clip_metrics.py --roots latch_film_e8 --workers 12 2>&1 | tail -1
"$MIR_PY" -c "
import runpy, sys, torch
torch.cuda.is_available = lambda: False      # the render server holds the GPU
torch.set_num_threads(12)
sys.argv = ['clip_metrics_audiobox.py', '--roots', 'latch_film_e8']
runpy.run_path('control/sa3_control/clip_metrics_audiobox.py', run_name='__main__')" 2>&1 | tail -1
"$SAO/stable-audio-tools/sat-venv/bin/python" eval/latch_film_e8.py clap 2>&1 | tail -1
echo "$(date +%H:%M) ALL DONE"
