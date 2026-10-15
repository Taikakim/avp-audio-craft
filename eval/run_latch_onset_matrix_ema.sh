#!/bin/bash
# Owner: WINTERMUTE (created 2026-10-15)
# run_latch_onset_matrix_ema.sh -- wait for the GPU, retrain the Phase E E04 onset head WITH EMA (+ online weights saved
# every epoch, one trajectory), then render the alpha 0-1 target x gain matrix with both weight sets, encode, score, release.
# Resumable: training is skipped if its _best.pt exists; the matrix skips finished cells.
#   bash eval/run_latch_onset_matrix_ema.sh        (run in background; exit = done)
set -u
SAO=/home/kim/Projects/SAO
PY=$SAO/.venv/bin/python
HEAD_DIR=/run/media/kim/Mantu2/latch_sweep/modular_2026-09-30/phaseE/E04ema_b32_ep20
OUT=/run/media/kim/Mantu2/sa3_control_runs/latch_onset_matrix_ema_20261015
STAGE=$HOME/evals_aac/latch_onset_matrix_ema
export ROCR_VISIBLE_DEVICES=0 FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
cd "$SAO" || exit 2

until KIND=batch NOTE="WINTERMUTE: E04 onset head retrain with EMA (~55 min) then 626-clip onset matrix (~50 min)" \
      Misc/gpu_guard.sh acquire WINTERMUTE $$ >/dev/null 2>&1; do
    echo "$(date +%H:%M) GPU busy, waiting"; sleep 120
done
echo "$(date +%H:%M) GPU acquired"
trap 'Misc/gpu_guard.sh release WINTERMUTE >/dev/null 2>&1' EXIT

BEST=$HEAD_DIR/latch_sa3_onset_per_beat_ts_best.pt
if [ ! -f "$BEST" ]; then
    mkdir -p "$HEAD_DIR"
    # E04 recipe verbatim (phaseE/SUMMARY.tsv) + EMA half-life 0.5 epoch (the air A2 setting) + online weights per epoch
    "$PY" stable-audio-3/scripts/latch/train_latch.py --feature onset_per_beat_ts \
        --latent-dir /run/media/kim/Kosmos/latents_goa_bigset --val-group-by relpath --epochs 20 --val-frac 0.05 \
        --val-seed 0 --seed 0 --standardize --num-workers 16 --optimizer modular --mod-whitening shampoo --lr 1e-2 \
        --mod-warmup 500 --batch-size 32 --mod-radial-brake 0.8 --mod-escape-velocity \
        --ema-halflife-epochs 0.5 --save-online --save-every-epoch --save-best-only \
        --save-dir "$HEAD_DIR" --run-name E04ema_b32_ep20 > "$HEAD_DIR/train.log" 2>&1
    echo "$(date +%H:%M) train rc=$? (teardown aborts after saving are known)"
fi
[ -f "$BEST" ] || { echo "no _best.pt -- training failed, see $HEAD_DIR/train.log"; exit 3; }
EP=$("$PY" -c "import torch;print(torch.load('$BEST',map_location='cpu',weights_only=False)['epoch'])")
ONLINE=$HEAD_DIR/latch_sa3_onset_per_beat_ts_ep${EP}_online.pt
[ -f "$ONLINE" ] || { echo "missing $ONLINE"; exit 3; }
echo "$(date +%H:%M) best epoch $EP: EMA=$BEST online=$ONLINE"

"$PY" eval/latch_onset_matrix_ema.py --ema "$BEST" --online "$ONLINE"
echo "$(date +%H:%M) render rc=$?"
n=$(wc -l < "$OUT/cells.jsonl"); echo "cells written: $n / 626"

mkdir -p "$STAGE"
for w in "$OUT"/*/*.wav; do
    sub=$(basename "$(dirname "$w")"); mkdir -p "$STAGE/$sub"
    d="$STAGE/$sub/$(basename "$w" .wav).m4a"
    [ -f "$d" ] || echo "$w $d"
done | xargs -r -P 12 -n 2 sh -c 'ffmpeg -nostdin -y -loglevel error -i "$0" -c:a aac -b:a 128k "$1"'
/home/kim/Projects/mir/mir/bin/python control/sa3_control/clip_metrics.py --roots latch_onset_matrix_ema --workers 12 2>&1 | tail -1
/home/kim/Projects/mir/mir/bin/python control/sa3_control/clip_metrics_audiobox.py --roots latch_onset_matrix_ema 2>&1 | tail -1
echo "$(date +%H:%M) ALL DONE"
