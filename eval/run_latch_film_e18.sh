#!/bin/bash
# Owner: WINTERMUTE (created 2026-10-25)
# run_latch_film_e18.sh -- EXPERIMENTS E18 (smooth FiLM -> LatCH hand-off) end to end.
#   1 waits for the stratified-t training (eval/run_strat_t_20261025.sh) to finish and the card to be free, takes the lock
#   2 starts the render server :8056 (needs the E18 fades: /info "fades"), renders 108 cells, stops the server
#   3 encodes AAC 192k, clip_metrics + Audiobox (CPU), CLAP drift (CPU), releases the GPU
#   setsid nohup bash eval/run_latch_film_e18.sh </dev/null >/dev/null 2>&1 &     (resumable)
set -u
SAO=/home/kim/Projects/SAO
OUT=/run/media/kim/Mantu/sa3_control_runs/latch_film_e18_20261025
STAGE=$HOME/evals_aac/latch_film_e18
MIR_PY=/home/kim/Projects/mir/mir/bin/python
LOG=/home/kim/sao_runs/latch_film_e18_20261025.log
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
cd "$SAO" || exit 2
exec >>"$LOG" 2>&1

echo "$(date +%H:%M) waiting for the stratified-t training"
while pgrep -f "^bash (/home/kim/Projects/SAO/)?eval/run_strat_t_20261025\.sh$" >/dev/null; do sleep 120; done
vram_free() { ! rocm-smi --showpids 2>/dev/null | grep -qE '^[0-9]+[[:space:]]'; }
until vram_free && KIND=batch NOTE="WINTERMUTE E18 hand-off renders: own :8056 + 108 cells (~1 h)" \
      Misc/gpu_guard.sh acquire WINTERMUTE $$ >/dev/null 2>&1; do sleep 60; done
SRV=
cleanup() { [ -n "$SRV" ] && kill "$SRV" 2>/dev/null; Misc/gpu_guard.sh release WINTERMUTE >/dev/null 2>&1; }
trap cleanup EXIT
echo "$(date +%H:%M) GPU acquired"

if ! curl -sf -m 5 http://127.0.0.1:8056/status >/dev/null; then
    setsid nohup .venv/bin/python eval/explorer_render_server.py > /home/kim/sao_runs/e18_render_server.log 2>&1 &
    SRV=$!
    for _ in $(seq 60); do curl -sf -m 5 http://127.0.0.1:8056/status >/dev/null && break; sleep 10; done
fi
curl -sf -m 5 http://127.0.0.1:8056/info | grep -q '"fades": *true' || { echo "server not up or without the E18 fades"; exit 1; }
echo "$(date +%H:%M) server up (pid ${SRV:-external})"

.venv/bin/python eval/latch_film_e18.py render
echo "$(date +%H:%M) render done; cells written: $(wc -l < "$OUT/cells.jsonl") / 108"
[ -n "$SRV" ] && kill "$SRV" && SRV=
Misc/gpu_guard.sh release WINTERMUTE >/dev/null 2>&1

mkdir -p "$STAGE"
for w in "$OUT"/*/*.wav; do
    sub=$(basename "$(dirname "$w")"); mkdir -p "$STAGE/$sub"
    d="$STAGE/$sub/$(basename "$w" .wav).m4a"
    [ -f "$d" ] || echo "$w $d"
done | xargs -r -P 12 -n 2 sh -c 'ffmpeg -nostdin -y -loglevel error -i "$0" -c:a aac -b:a 192k "$1"'
"$MIR_PY" control/sa3_control/clip_metrics.py --roots latch_film_e18 --workers 12 2>&1 | tail -1
"$MIR_PY" -c "
import runpy, sys, torch
torch.cuda.is_available = lambda: False
torch.set_num_threads(12)
sys.argv = ['clip_metrics_audiobox.py', '--roots', 'latch_film_e18']
runpy.run_path('control/sa3_control/clip_metrics_audiobox.py', run_name='__main__')" 2>&1 | tail -1
"$SAO/stable-audio-tools/sat-venv/bin/python" eval/latch_film_e18.py clap 2>&1 | tail -1
echo "$(date +%H:%M) ALL DONE"
