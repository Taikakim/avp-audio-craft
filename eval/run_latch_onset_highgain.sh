#!/bin/bash
# Owner: WINTERMUTE (created 2026-10-15)
# run_latch_onset_highgain.sh -- wait for the GPU lock, render CONTINUITY's eval/latch_onset_highgain.py (99e4410) at
# requests 7/3/0 x gains 4608..8192 step 512 x EMA/online x seed 1234 (48 clips), encode, score, release.
# The unguided clips are reused from the matrix dir (latch_onset_matrix_ema_20261015/base). Resumable.
#   bash eval/run_latch_onset_highgain.sh        (run in background; exit = done)
set -u
SAO=/home/kim/Projects/SAO
OUT=/run/media/kim/Mantu2/sa3_control_runs/latch_onset_highgain_20261015
STAGE=$HOME/evals_aac/latch_onset_highgain
export ROCR_VISIBLE_DEVICES=0 FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
cd "$SAO" || exit 2

# The lock alone is not enough (15:25 2026-10-15): a script can release it and start the resident server without
# re-announcing, so a free lock met a full card and this run OOM'd. Require no KFD process holding VRAM as well.
vram_free() { ! rocm-smi --showpids 2>/dev/null | grep -qE '^[0-9]+[[:space:]]'; }
until vram_free && KIND=batch NOTE="WINTERMUTE onset LatCH high-gain sweep (48 x 20 s renders + PQ), ~10 min" \
      Misc/gpu_guard.sh acquire WINTERMUTE $$ >/dev/null 2>&1; do
    echo "$(date +%H:%M) GPU busy, waiting"; sleep 120
done
echo "$(date +%H:%M) GPU acquired"
trap 'Misc/gpu_guard.sh release WINTERMUTE >/dev/null 2>&1' EXIT

"$SAO/.venv/bin/python" eval/latch_onset_highgain.py --targets 7,3,0
echo "$(date +%H:%M) render rc=$?; cells written: $(wc -l < "$OUT/cells.jsonl") / 48"

mkdir -p "$STAGE"
for w in "$OUT"/*/*.wav; do
    sub=$(basename "$(dirname "$w")"); mkdir -p "$STAGE/$sub"
    d="$STAGE/$sub/$(basename "$w" .wav).m4a"
    [ -f "$d" ] || echo "$w $d"
done | xargs -r -P 12 -n 2 sh -c 'ffmpeg -nostdin -y -loglevel error -i "$0" -c:a aac -b:a 128k "$1"'
/home/kim/Projects/mir/mir/bin/python control/sa3_control/clip_metrics.py --roots latch_onset_highgain --workers 12 2>&1 | tail -1
/home/kim/Projects/mir/mir/bin/python control/sa3_control/clip_metrics_audiobox.py --roots latch_onset_highgain 2>&1 | tail -1
echo "$(date +%H:%M) ALL DONE"
