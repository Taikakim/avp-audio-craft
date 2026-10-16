#!/bin/bash
# Owner: WINTERMUTE (created 2026-10-16)
# run_after_bracket_render.sh -- the rest of today's queue, restarted after my anchor runner stopped GHOST-NOTE's render server mid-grid
# (14:00). Waits until BOTH clients of :8056 are done (my FiLM bracket render, eval/film_bracket_density_check.py, and GHOST-NOTE's
# eval/bass_head_grid.py); stops the server only if I started it; builds + publishes film_bracket_check.html; then the chroma retrain
# (latch/run_chroma_retrain.sh) and the optimizer timing (control/time_film_optimizers.sh), in that order.
#   bash eval/run_after_bracket_render.sh        (run in background)
set -u
SAO=/home/kim/Projects/SAO
DEST_FILE=/tmp/claude-1000/-home-kim-Projects-mir/b207d8c1-afa9-47b8-bbe0-60db9d0c4899/scratchpad/dest
cd "$SAO" || exit 2
while pgrep -f "eval/film_bracket_density_check\.py" >/dev/null || pgrep -f "eval/bass_head_grid\.py" >/dev/null; do
    echo "$(date +%H:%M) server clients still running"; sleep 60
done
echo "$(date +%H:%M) cells: $(wc -l < /run/media/kim/Mantu/sa3_control_runs/film_bracket_density_check_20261016/cells.jsonl) / 412"
grep -qs "^WINTERMUTE" "$HOME/.cache/latent-forge/server.8056.holder" && eval/forge/dev_server.sh stop
python3 Misc/build_film_bracket_check_page.py && [ -f "$DEST_FILE" ] && D=$(cat "$DEST_FILE") && \
    rsync -a "$HOME/evals_aac/film_bracket_check" "$D" && rsync -a "$HOME/evals_aac/film_bracket_check.html" "$D" && echo "$(date +%H:%M) page published"
bash latch/run_chroma_retrain.sh
bash control/time_film_optimizers.sh
echo "$(date +%H:%M) ALL DONE"
