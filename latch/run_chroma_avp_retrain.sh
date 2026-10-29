#!/usr/bin/env bash
# run_chroma_avp_retrain.sh -- Retrain the new 384-d SAME-chroma conditioning head
# under the ModularOptimizer on the AVP augmented dataset and Goa+AVP combined dataset.
# Architecture: DiT conditioning head on SA3 latents, dim 512, depth 8.
# Optimizer: Modular + Schedule-Free, Shampoo, Muon on all 2-D, lr 1e-3, radial brake 0.8.
#
# Arms:
#   1. C3_avp_aug: latents_avp (2,393 crops)
#   2. C3_goa_avp_combined: latents_sa3 + latents_avp (7,300 crops with stem chroma)
#
# Usage:
#   bash latch/run_chroma_avp_retrain.sh
set -u
SAO=/home/kim/Projects/SAO
OUT=/run/media/kim/Mantu/latch_sweep/chroma_retrain_avp_20261029
PY=$SAO/.venv-rocm10-amd/bin/python
TRAIN=$SAO/stable-audio-3/scripts/latch/train_latch.py

export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0 WANDB_MODE=offline WANDB_DIR=$OUT

COMMON="--feature same_chroma --target-source chroma --chroma-key other --val-frac 0.05 --val-seed 0 --val-group-by source_track --seed 0 --num-workers 8 --loss cosine --save-every-epoch --save-online --optimizer modular --allow-uniform-lr --mod-whitening shampoo --mod-muon-all --mod-wd-overtraining --mod-warmup-epochs 1 --mod-radial-brake 0.8 --grad-clip 1.0 --ema-halflife-epochs 1 --ema-extra-halflife-epochs 0.25 --epochs 12 --depth 8 --dim 512 --batch-size 8 --grad-accum 4 --lr 1e-3 --wandb --wandb-project sa3-latch-chroma --log-every 20 --layer-every 100"

ARMS=(
"C3_avp_aug|--chroma-dir /run/media/kim/Lehto/latents_avp_chroma --latent-dir /run/media/kim/Kosmos/latents/latents_avp $COMMON"
"C3_goa_avp_combined|--chroma-dir /run/media/kim/Kosmos/latents/latents_sa3_stem_chroma,/run/media/kim/Lehto/latents_avp_chroma --latent-dir /run/media/kim/Kosmos/latents/latents_sa3,/run/media/kim/Kosmos/latents/latents_avp $COMMON"
)

mkdir -p "$OUT"
touch "$OUT/SUMMARY.tsv"
cd /tmp || exit 1

until "$SAO/Misc/gpu_guard.sh" acquire ANTIGRAVITY $$ >/dev/null 2>&1; do
    echo "$(date +%H:%M) Waiting for GPU lock..."
    sleep 30
done
trap '"$SAO/Misc/gpu_guard.sh" release ANTIGRAVITY >/dev/null 2>&1' EXIT

echo "$(date +%H:%M) GPU acquired; smoke test on Arm 1 (20 steps)"
$PY "$TRAIN" ${ARMS[0]#*|} --max-steps 20 --save-dir "$OUT/_smoke" --run-name avp_smoke > "$OUT/smoke.log" 2>&1
rc=$?
if [ $rc -ne 0 ]; then
    echo "$(date +%H:%M) SMOKE FAILED rc=$rc, see $OUT/smoke.log"
    exit 1
fi
echo "$(date +%H:%M) Smoke passed cleanly. Starting training arms..."

for a in "${ARMS[@]}"; do
    name=${a%%|*}
    rest=${a#*|}
    if grep -q "^${name}	" "$OUT/SUMMARY.tsv"; then
        echo "$(date +%H:%M) $name already completed in SUMMARY.tsv, skipping"
        continue
    fi
    mkdir -p "$OUT/$name"
    t0=$(date +%s)
    echo "$(date +%H:%M) Launching $name"
    # shellcheck disable=SC2086
    $PY "$TRAIN" $rest --save-dir "$OUT/$name" --run-name "$name" > "$OUT/$name/train.log" 2>&1
    rc=$?
    t1=$(date +%s)
    last=$(grep -oE "val=[0-9.na]+" "$OUT/$name/train.log" | tail -1 | cut -d= -f2)
    best=$(grep -oE "val=[0-9.]+" "$OUT/$name/train.log" | cut -d= -f2 | sort -g | head -1)
    printf '%s\t%s\t%s\t%s\trc=%s\n' "$name" "$((t1 - t0))" "${best:-NA}" "${last:-NA}" "$rc" >> "$OUT/SUMMARY.tsv"
    echo "$(date +%H:%M) $name finished rc=$rc (time: $((t1 - t0))s, best val: ${best:-NA})"
    if [ $rc -ne 0 ]; then
        echo "$(date +%H:%M) Error: $name exited with $rc"
        exit $rc
    fi
done

echo "$(date +%H:%M) ALL TRAINING ARMS COMPLETED SUCCESSFULLY"
