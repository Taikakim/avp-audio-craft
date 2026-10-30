#!/usr/bin/env bash
# Owner: ANTIGRAVITY (created 2026-10-30)
# run_chroma_avp_songsplit.sh -- retrain the AVP chroma heads with a LEAK-FREE val split.
#
# Why: latents_avp = 151 real songs x up to 9 variants (orig, pitch +-1/+-2, tempo +-5/+-10).
# Each variant carries its own source_track ("Song/pitch+1"), so the 2026-10-29 runs'
# --val-group-by source_track put pitch/tempo copies of every val song into train. The
# AVP head's best val 0.0205 is therefore leaked; it most likely memorised 151 songs, which
# fits its weak steering on Goa prompts (half the chroma lift per unit gain of goa_e13).
# Fix: --val-group-by song (parent_track, falling back to source_track; latch_dataset.py).
#
# Arms (same C3 recipe as run_chroma_avp_retrain.sh otherwise):
#   1. C3_avp_song       latents_avp, val-frac 0.10 (~15 songs), 20 epochs  (~35 min)
#   2. C3_goa_avp_song   latents_sa3 + latents_avp, val-frac 0.05, 12 epochs (~65 min)
# Epoch choice for rendering comes from the honest val curve, not the last epoch.
set -u
SAO=/home/kim/Projects/SAO
OUT=/run/media/kim/Mantu/latch_sweep/chroma_retrain_avp_songsplit_20261030
PY=$SAO/.venv-rocm10-amd/bin/python
TRAIN=$SAO/stable-audio-3/scripts/latch/train_latch.py

export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0 WANDB_MODE=offline WANDB_DIR=$OUT

COMMON="--feature same_chroma --target-source chroma --chroma-key other --val-seed 0 --val-group-by song --seed 0 --num-workers 8 --loss cosine --save-every-epoch --save-online --optimizer modular --allow-uniform-lr --mod-whitening shampoo --mod-muon-all --mod-wd-overtraining --mod-warmup-epochs 1 --mod-radial-brake 0.8 --grad-clip 1.0 --ema-halflife-epochs 1 --ema-extra-halflife-epochs 0.25 --depth 8 --dim 512 --batch-size 8 --grad-accum 4 --lr 1e-3 --wandb --wandb-project sa3-latch-chroma --log-every 20 --layer-every 100"

ARMS=(
"C3_avp_song|--chroma-dir /run/media/kim/Lehto/latents_avp_chroma --latent-dir /run/media/kim/Kosmos/latents/latents_avp --val-frac 0.10 --epochs 20 $COMMON"
"C3_goa_avp_song|--chroma-dir /run/media/kim/Kosmos/latents/latents_sa3_stem_chroma,/run/media/kim/Lehto/latents_avp_chroma --latent-dir /run/media/kim/Kosmos/latents/latents_sa3,/run/media/kim/Kosmos/latents/latents_avp --val-frac 0.05 --epochs 12 $COMMON"
)

mkdir -p "$OUT"
touch "$OUT/SUMMARY.tsv"
cd /tmp || exit 1

until "$SAO/Misc/gpu_guard.sh" acquire ANTIGRAVITY $$ </dev/null >/dev/null 2>&1; do
    echo "$(date +%H:%M) Waiting for GPU lock..."
    sleep 30
done
trap '"$SAO/Misc/gpu_guard.sh" release ANTIGRAVITY </dev/null >/dev/null 2>&1' EXIT

echo "$(date +%H:%M) GPU acquired; smoke test on Arm 1 (20 steps)"
$PY "$TRAIN" ${ARMS[0]#*|} --max-steps 20 --save-dir "$OUT/_smoke" --run-name avp_song_smoke </dev/null > "$OUT/smoke.log" 2>&1
rc=$?
if [ $rc -ne 0 ]; then
    echo "$(date +%H:%M) SMOKE FAILED rc=$rc, see $OUT/smoke.log"
    exit 1
fi
grep -m1 "Val split" "$OUT/smoke.log"
echo "$(date +%H:%M) Smoke passed. Starting arms..."

for a in "${ARMS[@]}"; do
    name=${a%%|*}
    rest=${a#*|}
    if grep -q "^${name}	" "$OUT/SUMMARY.tsv"; then
        echo "$(date +%H:%M) $name already in SUMMARY.tsv, skipping"
        continue
    fi
    mkdir -p "$OUT/$name"
    t0=$(date +%s)
    echo "$(date +%H:%M) Launching $name"
    # shellcheck disable=SC2086
    $PY "$TRAIN" $rest --save-dir "$OUT/$name" --run-name "$name" </dev/null > "$OUT/$name/train.log" 2>&1
    rc=$?
    t1=$(date +%s)
    last=$(grep -oE "val=[0-9.na]+" "$OUT/$name/train.log" | tail -1 | cut -d= -f2)
    best=$(grep -oE "val=[0-9.]+" "$OUT/$name/train.log" | cut -d= -f2 | sort -g | head -1)
    printf '%s\t%s\t%s\t%s\trc=%s\n' "$name" "$((t1 - t0))" "${best:-NA}" "${last:-NA}" "$rc" >> "$OUT/SUMMARY.tsv"
    echo "$(date +%H:%M) $name finished rc=$rc (time: $((t1 - t0))s, best val: ${best:-NA})"
    [ $rc -ne 0 ] && exit $rc
done
echo "$(date +%H:%M) ALL ARMS COMPLETED"
