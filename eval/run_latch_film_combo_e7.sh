#!/bin/bash
# Owner: WINTERMUTE (created 2026-10-15)
# run_latch_film_combo_e7.sh -- EXPERIMENTS E7 end to end: wait for the render server :8056, render the 204-cell
# LatCH x FiLM grid through it (the server owns the GPU, so this script never takes the GPU lock), encode, score.
# Scoring stays OFF the GPU while the resident server holds it: clip_metrics is CPU anyway, Audiobox is forced to
# CPU, CLAP drift runs on CPU. Resumable (finished cells are skipped).
#   bash eval/run_latch_film_combo_e7.sh        (run in background; exit = done)
set -u
SAO=/home/kim/Projects/SAO
OUT=/run/media/kim/Mantu2/sa3_control_runs/latch_film_combo_e7_20261015
STAGE=$HOME/evals_aac/latch_film_combo_e7
MIR_PY=/home/kim/Projects/mir/mir/bin/python
cd "$SAO" || exit 2

until curl -sf -m 5 http://127.0.0.1:8056/status >/dev/null; do
    echo "$(date +%H:%M) render server down, waiting"; sleep 120
done
echo "$(date +%H:%M) server up"

"$SAO/.venv/bin/python" eval/latch_film_combo_e7.py render
rc=$?
echo "$(date +%H:%M) render rc=$rc; cells written: $(wc -l < "$OUT/cells.jsonl") / 204"

mkdir -p "$STAGE"
for w in "$OUT"/*/*.wav; do
    sub=$(basename "$(dirname "$w")"); mkdir -p "$STAGE/$sub"
    d="$STAGE/$sub/$(basename "$w" .wav).m4a"
    [ -f "$d" ] || echo "$w $d"
done | xargs -r -P 12 -n 2 sh -c 'ffmpeg -nostdin -y -loglevel error -i "$0" -c:a aac -b:a 128k "$1"'
"$MIR_PY" control/sa3_control/clip_metrics.py --roots latch_film_combo_e7 --workers 12 2>&1 | tail -1
"$MIR_PY" -c "
import runpy, sys, torch
torch.cuda.is_available = lambda: False      # the render server holds the GPU
torch.set_num_threads(12)
sys.argv = ['clip_metrics_audiobox.py', '--roots', 'latch_film_combo_e7']
runpy.run_path('control/sa3_control/clip_metrics_audiobox.py', run_name='__main__')" 2>&1 | tail -1
"$SAO/stable-audio-tools/sat-venv/bin/python" eval/latch_film_combo_e7.py clap 2>&1 | tail -1
echo "$(date +%H:%M) ALL DONE"
