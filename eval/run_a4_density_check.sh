#!/bin/bash
# Owner: WINTERMUTE (created 2026-10-20)
# run_a4_density_check.sh -- density check for test-plan arm A4 (FiLM, modular lr 3e-4, fp32 optimizer state): 60 renders (gains
# 0.5-2.5 x requests 3/5/7/9/12 x seeds 1234/77, ~10 min), the same grid as its bf16 twin lr3e-4 on film_bracket_check.html, so the
# two sit side by side. Waits for the test-plan stream and its A5 rerun to exit, then for a free GPU; starts the render server under
# WINTERMUTE, renders (eval/film_bracket_density_check.py is resumable), stops only its own server, rebuilds + publishes the page.
#   setsid nohup bash eval/run_a4_density_check.sh > <OUT>/a4.log 2>&1 < /dev/null &
set -u
SAO=/home/kim/Projects/SAO
OUT=/run/media/kim/Mantu/sa3_control_runs/film_bracket_density_check_20261016
DEST_FILE=/tmp/claude-1000/-home-kim-Projects-mir/b207d8c1-afa9-47b8-bbe0-60db9d0c4899/scratchpad/dest
cd "$SAO" || exit 2
while pgrep -f "^bash (/home/kim/Projects/SAO/)?eval/run_kuang_plan_(stream|a5_rerun)\.sh$" >/dev/null; do sleep 300; done
vram_free() { ! rocm-smi --showpids 2>/dev/null | grep -qE '^[0-9]+[[:space:]]'; }
until curl -sf -m 5 http://127.0.0.1:8056/status >/dev/null || { vram_free && eval/forge/dev_server.sh start WINTERMUTE >/dev/null 2>&1; }; do
    echo "$(date +%H:%M) GPU busy, waiting"; sleep 120
done
until curl -sf -m 5 http://127.0.0.1:8056/status >/dev/null; do sleep 20; done
echo "$(date +%H:%M) server up: A4 density check"
"$SAO/.venv/bin/python" eval/film_bracket_density_check.py > "$OUT/a4_render.log" 2>&1
echo "$(date +%H:%M) A4 cells: $(grep -c '"arm": "fp32_lr3e-4"' "$OUT/cells.jsonl") / 60"
grep -qs "^WINTERMUTE" "$HOME/.cache/latent-forge/server.8056.holder" && eval/forge/dev_server.sh stop
python3 Misc/build_film_bracket_check_page.py && [ -f "$DEST_FILE" ] && D=$(cat "$DEST_FILE") && \
    rsync -a "$HOME/evals_aac/film_bracket_check" "$D" && rsync -a "$HOME/evals_aac/film_bracket_check.html" "$D" && echo "$(date +%H:%M) page published"
echo "$(date +%H:%M) ALL DONE"
