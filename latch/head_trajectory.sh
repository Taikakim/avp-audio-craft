#!/usr/bin/env bash
# head_trajectory.sh — weight-space path of a LatCH head run saved with SAVE_ALL=1 (per-epoch ckpts).
# Reuses control/sa3_control/checkpoint_trajectory_stats.py (velocity, path efficiency, step cosine,
# per-layer movement); it wants files named *_step<N>.pt, so epochs are symlinked as step = epoch*STEPS_PER_EPOCH.
# usage: bash latch/head_trajectory.sh <arm_dir> [steps_per_epoch=743]   -> checkpoint-stats/<arm>_trajectory.{json,md,png}
set -euo pipefail
ARM=$(readlink -f "$1"); SPE=${2:-743}
NAME=$(basename "$ARM"); TMP=$(mktemp -d)
for f in "$ARM"/latch_sa3_*_ep*.pt; do
  e=$(basename "$f" .pt); e=${e##*_ep}
  ln -s "$f" "$TMP/head_step$((e * SPE)).pt"
done
cd /tmp && /home/kim/Projects/SAO/.venv/bin/python /home/kim/Projects/SAO/control/sa3_control/checkpoint_trajectory_stats.py \
  --ckpt-dir "$TMP" --label "latchD_$NAME" --glob 'head_step*.pt' --epoch-steps "$SPE" \
  --out-dir /home/kim/Projects/SAO/checkpoint-stats
rm -rf "$TMP"
