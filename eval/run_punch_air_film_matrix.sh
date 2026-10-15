#!/bin/bash
# Owner: WINTERMUTE (created 2026-10-15)
# run_punch_air_film_matrix.sh -- render eval/punch_air_film_matrix.py (148 cells) through the render server :8056,
# encode, score on CPU (the server holds the GPU). Takes no GPU lock itself. Resumable.
#   bash eval/run_punch_air_film_matrix.sh
set -u
SAO=/home/kim/Projects/SAO
OUT=/run/media/kim/Mantu2/sa3_control_runs/punch_air_film_matrix_20261015
STAGE=$HOME/evals_aac/punch_air_film_matrix
MIR_PY=/home/kim/Projects/mir/mir/bin/python
cd "$SAO" || exit 2

until curl -sf -m 5 http://127.0.0.1:8056/status >/dev/null; do
    echo "$(date +%H:%M) render server down, waiting"; sleep 120
done
"$SAO/.venv/bin/python" eval/punch_air_film_matrix.py render
echo "$(date +%H:%M) render rc=$?; cells written: $(wc -l < "$OUT/cells.jsonl") / 148"

mkdir -p "$STAGE"
for w in "$OUT"/*.wav; do
    d="$STAGE/$(basename "$w" .wav).m4a"
    [ -f "$d" ] || echo "$w $d"
done | xargs -r -P 12 -n 2 sh -c 'ffmpeg -nostdin -y -loglevel error -i "$0" -c:a aac -b:a 128k "$1"'
"$MIR_PY" control/sa3_control/clip_metrics.py --roots punch_air_film_matrix --workers 12 2>&1 | tail -1
"$MIR_PY" -c "
import runpy, sys, torch
torch.cuda.is_available = lambda: False      # the render server holds the GPU
torch.set_num_threads(12)
sys.argv = ['clip_metrics_audiobox.py', '--roots', 'punch_air_film_matrix']
runpy.run_path('control/sa3_control/clip_metrics_audiobox.py', run_name='__main__')" 2>&1 | tail -1
echo "$(date +%H:%M) ALL DONE"
