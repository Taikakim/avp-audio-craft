#!/bin/bash
# Owner: WINTERMUTE (created 2026-10-15)
# run_after_air_queue.sh -- WINTERMUTE's GPU work once GHOST-NOTE's air queue is done (/tmp/air_nosf.done):
#   1. the seed-764 anchor test (eval/punch_air_film_anchor.py, 25 renders) and the 64 no-DoRA punch seeds
#      (eval/punch_nodora_seeds.py, ~11 min) through the render server :8056 --
#      starts the server under WINTERMUTE if the air queue did not leave one running; encode + CPU scoring;
#   2. stops the server (the bracket trains in-process and needs the whole card);
#   3. the FiLM modular LR bracket (control/run_film_modular_bracket.sh, EXPERIMENTS E12).
#   bash eval/run_after_air_queue.sh        (run in background)
set -u
SAO=/home/kim/Projects/SAO
MANTU=$(for p in /run/media/kim/Mantu /run/media/kim/Mantu2 /run/media/kim/Mantu1; do [ -d "$p/sa3_control_runs" ] && { echo "$p"; break; }; done)
OUT=$MANTU/sa3_control_runs/punch_air_film_anchor_20261015
STAGE=$HOME/evals_aac/punch_air_film_anchor
MIR_PY=/home/kim/Projects/mir/mir/bin/python
cd "$SAO" || exit 2

# 2026-10-15 19:50: the GPU came back free with GHOST-NOTE's queue stopped (drive remounted as Mantu), so the short
# server part runs NOW and only the 2 h bracket waits for the end of the air queue (run_film_modular_bracket.sh).
for i in $(seq 1 2); do curl -sf -m 5 http://127.0.0.1:8056/status >/dev/null && break; sleep 30; done
if ! curl -sf -m 5 http://127.0.0.1:8056/status >/dev/null; then
    echo "$(date +%H:%M) no server running: starting it"
    eval/forge/dev_server.sh start WINTERMUTE
    until curl -sf -m 5 http://127.0.0.1:8056/status >/dev/null; do sleep 20; done
fi
echo "$(date +%H:%M) server up: anchor test"
"$SAO/.venv/bin/python" eval/punch_air_film_anchor.py render
echo "$(date +%H:%M) anchor rc=$?; cells written: $(wc -l < "$OUT/cells.jsonl") / 25"
# the punch rating set's 64 seeds without the DoRA, for the seed-764 latent comparison (eval/punch_nodora_seeds.py)
"$SAO/.venv/bin/python" eval/punch_nodora_seeds.py
echo "$(date +%H:%M) no-DoRA renders rc=$?"
mkdir -p "$STAGE"
for w in "$OUT"/*.wav; do
    d="$STAGE/$(basename "$w" .wav).m4a"; [ -f "$d" ] || echo "$w $d"
done | xargs -r -P 12 -n 2 sh -c 'ffmpeg -nostdin -y -loglevel error -i "$0" -c:a aac -b:a 128k "$1"'
"$MIR_PY" control/sa3_control/clip_metrics.py --roots punch_air_film_anchor --workers 12 2>&1 | tail -1
"$MIR_PY" -c "
import runpy, sys, torch
torch.cuda.is_available = lambda: False
torch.set_num_threads(12)
sys.argv = ['clip_metrics_audiobox.py', '--roots', 'punch_air_film_anchor']
runpy.run_path('control/sa3_control/clip_metrics_audiobox.py', run_name='__main__')" 2>&1 | tail -1
echo "$(date +%H:%M) anchor test done; stopping the server for the bracket"
eval/forge/dev_server.sh stop
sleep 20
bash control/run_film_modular_bracket.sh
echo "$(date +%H:%M) ALL DONE"
