#!/bin/bash
# Owner: WINTERMUTE (created 2026-10-16)
# run_film_e12_night.sh -- the E12 night chain, after GHOST-NOTE's air queue:
#   1. wait until the air queue is really done: /tmp/air_nosf.done AND no air driver / LatCH trainer process left
#      (2026-10-15 a done marker was written after a 2-s death, so the marker alone is not trusted);
#   2. render server up (start under WINTERMUTE if none), the density check of the three bracket arms + the shipped
#      FiLM (eval/film_bracket_density_check.py, 34 renders, ~5 min) -> pick.json; build + publish its page;
#   3. stop the server, run the 54k full run at the picked lr (control/run_film_modular_full.sh, ~6.5 h).
#   bash eval/run_film_e12_night.sh        (run in background)
set -u
SAO=/home/kim/Projects/SAO
OUT=/run/media/kim/Mantu/sa3_control_runs/film_bracket_density_check_20261016
DEST_FILE=/tmp/claude-1000/-home-kim-Projects-mir/b207d8c1-afa9-47b8-bbe0-60db9d0c4899/scratchpad/dest
cd "$SAO" || exit 2

air_busy() { pgrep -f "latch/run_air_|scripts/latch/train_latch.py" >/dev/null; }
until [ -f /tmp/air_nosf.done ] && ! air_busy; do echo "$(date +%H:%M) waiting for GHOST-NOTE's air queue"; sleep 300; done
echo "$(date +%H:%M) air queue done"
if ! curl -sf -m 5 http://127.0.0.1:8056/status >/dev/null; then
    echo "$(date +%H:%M) starting the render server"
    eval/forge/dev_server.sh start WINTERMUTE
    until curl -sf -m 5 http://127.0.0.1:8056/status >/dev/null; do sleep 20; done
fi
"$SAO/.venv/bin/python" eval/film_bracket_density_check.py
echo "$(date +%H:%M) density check rc=$?"
LR=$(python3 -c "import json; print(json.load(open('$OUT/pick.json'))['lr'])" 2>/dev/null || echo 1e-3)
echo "$(date +%H:%M) picked lr $LR"
python3 Misc/build_film_bracket_check_page.py && [ -f "$DEST_FILE" ] && D=$(cat "$DEST_FILE") && \
    rsync -a "$HOME/evals_aac/film_bracket_check" "$D" && rsync -a "$HOME/evals_aac/film_bracket_check.html" "$D" && \
    echo "$(date +%H:%M) page published"
eval/forge/dev_server.sh stop
sleep 20
bash control/run_film_modular_full.sh "$LR"
echo "$(date +%H:%M) ALL DONE"
