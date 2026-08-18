#!/bin/bash
# Shard the 5401 crop ids into 50-crop shard files + the shards list for the sbatch.
set -euo pipefail
CODE=$(dirname "$0")
LAT=${1:-/home/kim/Projects/latents_sa3}   # dir of <id>.npy; on LUMI pass $FLASH/<set>
PREFIX=${2:-}                              # path root written INTO the list (must resolve on LUMI)
SET=${3:-}                                 # name tag; shards land in muscriptor_shards_<SET>/
PER=${PER:-50}                             # crops per shard

# NAME THE SHARD SET (2026-08-18). Originally this clobbered ONE muscriptor_shards/ dir and ONE
# muscriptor_shards.txt, which is fine for a single corpus and silently destructive the moment you
# shard a second one — the goa run would overwrite suomisoundi's list and both jobs would transcribe
# the same crops. Per-set names make them coexist.
[ -n "$SET" ] || SET=$(basename "$LAT")
SH=$CODE/muscriptor_shards_$SET
LIST=$CODE/muscriptor_shards_$SET.txt
[ -n "$PREFIX" ] || PREFIX=$SH
rm -rf "$SH"; mkdir -p "$SH"

N=$(ls "$LAT" | grep -c '\.npy$' || true)
[ "$N" -gt 0 ] || { echo "FATAL: no .npy under $LAT"; exit 1; }
ls "$LAT" | grep '\.npy$' | sed 's/\.npy$//' | sort | split -l "$PER" -d -a 3 - "$SH/shard_"
ls "$SH" | sed "s|^|$PREFIX/|" > "$LIST"
echo "[shards] set=$SET  crops=$N  per-shard=$PER  shards=$(wc -l < "$LIST")  -> $LIST"
echo "[shards] at the measured ~1.5 GCD-min/crop that is ~$(( N * 15 / 600 )) GCD-hours of work"
