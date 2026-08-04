#!/bin/bash
# Shard the 5401 crop ids into 50-crop shard files + the shards list for the sbatch.
set -euo pipefail
CODE=$(dirname "$0")
LAT=${1:-/home/kim/Projects/latents_sa3}       # run locally pre-copy; on LUMI pass $FLASH/latents_sa3
PREFIX=${2:-$SH}                                # path root written into shards.txt (LUMI: $CODE/lumi/muscriptor_shards)
SH=$CODE/muscriptor_shards; rm -rf "$SH"; mkdir -p "$SH"
ls "$LAT" | grep '\.npy$' | sed 's/\.npy$//' | sort | split -l 50 -d -a 3 - "$SH/shard_"
ls "$SH" | sed "s|^|$PREFIX/|" > "$CODE/muscriptor_shards.txt"
echo "shards: $(wc -l < "$CODE/muscriptor_shards.txt")"
