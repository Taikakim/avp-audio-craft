#!/usr/bin/env bash
# Owner: KUANG (created 2026-10-30)
# run_mood_prep.sh -- mood LatCH head, plan steps 2 and 1: add the mood fields to the crop
# companions, then run the census that proposes the tag vocabulary and writes the target specs.
# CPU only. Training (step 4) is NOT started here: read the census table first.
#
# Background: effnet_moodtheme_ts (56 MTG-Jamendo tags, ~1 Hz) and va_deam_ts / va_emomusic_ts
# (valence/arousal, ~1.075 Hz) exist in the whole-track stores (Kosmos/timeseries for goa, beside
# each track for avp) but not in the crops' .TIMESERIES.npz. sa3_encode_from_manifest.py
# --companion-only --additive slices them at their own (derived) rate and MERGES them into each
# companion, keeping every existing field and never touching a latent: the same path that added the
# four f0 fields to latents_sa3 in August. Writes are atomic (stable-audio-3 feature/sa3-drum-sep).
#
# Size: the 56-tag field is (4096, 56) fp32 ~0.9 MB per crop, so ~7 GB on Kosmos for both corpora.
#
# Steps:
#   0. refuse if a train_latch run is active (it may be reading these companions)
#   1. back up the existing companions (tar, skipped if the backup already exists; NO_BACKUP=1 skips)
#   2. add the fields to latents_sa3 and latents_avp; print per-corpus coverage
#   3. census over both corpora with the SAME --val-* settings the training run will use
set -uo pipefail   # the census is piped through tee; its failure must stop the script
SAO=/home/kim/Projects/SAO
SA3=$SAO/stable-audio-3
PY=$SAO/.venv-rocm10-amd/bin/python
KOSMOS=/run/media/kim/Kosmos
CORPORA=("$KOSMOS/latents/latents_sa3" "$KOSMOS/latents/latents_avp")
TS_ROOT=$KOSMOS/timeseries
FIELDS=effnet_moodtheme_ts,va_deam_ts,va_emomusic_ts
LABELS=/home/kim/Projects/mir/models/essentia/mtg_jamendo_moodtheme-discogs-effnet-1.json
BACKUP=/run/media/kim/Mantu/companion_backup_20261030
OUT=/run/media/kim/Mantu/latch_sweep/mood_census_20261030
VAL="--val-frac 0.05 --val-seed 0 --val-group-by song"   # the training run must use exactly these

cd "$SA3" || exit 1
mkdir -p "$OUT"

if pgrep -f "scripts/latch/train_latch.py|scripts.latch.train_latch" >/dev/null; then
    echo "$(date +%H:%M) a train_latch run is active; it may read these companions. Stop it or wait."; exit 1
fi
free_gb=$(df -BG --output=avail "$KOSMOS" | tail -1 | tr -dc 0-9)
if [ "${free_gb:-0}" -lt 12 ]; then
    echo "$(date +%H:%M) only ${free_gb} GB free on $KOSMOS; the mood fields need ~7 GB plus margin"; exit 1
fi

if [ "${NO_BACKUP:-0}" != 1 ]; then
    mkdir -p "$BACKUP"
    for c in "${CORPORA[@]}"; do
        tarf="$BACKUP/$(basename "$c")_TIMESERIES.tar"
        if [ -s "$tarf" ]; then echo "$(date +%H:%M) backup exists: $tarf"; continue; fi
        echo "$(date +%H:%M) backing up $c companions -> $tarf"
        (cd "$c" && find . -maxdepth 1 -name '*.TIMESERIES.npz' -print0 | tar --null -cf "$tarf" -T -) \
            || { echo "backup failed"; exit 1; }
    done
fi

for c in "${CORPORA[@]}"; do
    echo "$(date +%H:%M) adding $FIELDS to $c"
    $PY scripts/sa3_encode_from_manifest.py --companion-only --additive --fields "$FIELDS" \
        --timeseries-root "$TS_ROOT" --out "$c" </dev/null 2> "$OUT/$(basename "$c").skips.log" \
        || { echo "companion run failed on $c (see $OUT/$(basename "$c").skips.log)"; exit 1; }
    $PY - "$c" <<'EOF'
import sys, glob, numpy as np
fs = sorted(glob.glob(sys.argv[1] + "/*.TIMESERIES.npz"))
n = {"effnet_moodtheme_ts": 0, "va_deam_ts": 0, "va_emomusic_ts": 0}
for f in fs:
    with np.load(f) as z:
        for k in n:
            n[k] += k in z.files
print(f"  coverage {sys.argv[1]}: {len(fs)} companions; " + ", ".join(f"{k} {v}" for k, v in n.items()))
EOF
done

echo "$(date +%H:%M) census -> $OUT"
$PY -m scripts.latch.mood_census --latent-dirs "${CORPORA[@]}" --labels "$LABELS" $VAL \
    --out-dir "$OUT" </dev/null | tee "$OUT/census.txt" || { echo "census failed"; exit 1; }

cat <<EOF

$(date +%H:%M) Done. Read $OUT/census.txt, edit mood_spec.json if needed (drop entries from
indices/names/mean/std together), then step 4 (GPU), e.g. the chroma C3 recipe with MSE:

  $PY $SA3/scripts/latch/train_latch.py --feature effnet_moodtheme --target-source npz \\
    --target-spec $OUT/mood_spec.json --latent-dir ${CORPORA[0]},${CORPORA[1]} $VAL --loss mse \\
    --optimizer modular --allow-uniform-lr --mod-whitening shampoo --mod-muon-all --mod-wd-overtraining \\
    --mod-warmup-epochs 1 --mod-radial-brake 0.8 --grad-clip 1.0 --ema-halflife-epochs 1 \\
    --depth 8 --dim 512 --batch-size 8 --grad-accum 4 --lr 1e-3 --epochs 12 --save-every-epoch \\
    --save-dir <dir>

The trainer refuses the spec if its split differs from the census's (same roots, order, --val-*).
EOF
