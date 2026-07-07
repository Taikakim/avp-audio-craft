#!/bin/bash
# pack_data.sh — build the transfer tarballs for LUMI (run LOCALLY, before access lands).
# Doubles as the COLD BACKUP of the single-copy latents (the standing CONTINUITY risk):
# the same tarballs are the backup — write them to Mantu1, ship them to LUMI-O later.
#
# Usage:  ./pack_data.sh [/run/media/kim/Mantu1/lumi_staging]
#
# Transfer (once project number exists):
#   - big tarballs → LUMI-O object storage (rclone / s3cmd, keys from LUMI web UI),
#     then on LUMI: extract into /project/<proj>/data/
#   - code + configs → plain rsync to lumi.csc.fi:/project/<proj>/
set -euo pipefail

DEST=${1:-/run/media/kim/Mantu1/lumi_staging}
mkdir -p "$DEST"
cd /home/kim/Projects

manifest() {  # name dir — tar with a printed manifest line
    local name=$1 dir=$2
    echo "== $name: $(find "$dir" -type f | wc -l) files, $(du -sh "$dir" | cut -f1)"
    tar -cf "$DEST/${name}.tar" "$dir"
    sha256sum "$DEST/${name}.tar" >> "$DEST/SHA256SUMS"
}

# Campaign A+B inputs (latents = SOLE copies, this IS the backup)
manifest latents_sa3  latents_sa3      # ~13G: 5401 npy + json + TIMESERIES.npz (T=4096 grid)
manifest latents_avp  latents_avp      # avp corpus: 2393 latents + companions

# Code snapshot (repos are private; LUMI gets tarballs, not git remotes)
for repo in SAO/stable-audio-3 SAO/stable-audio-tools; do
    name=$(basename "$repo")
    git -C "/home/kim/Projects/$repo" archive --format=tar --prefix="${name}/" HEAD \
        > "$DEST/${name}-code.tar"
    git -C "/home/kim/Projects/$repo" rev-parse HEAD > "$DEST/${name}.commit"
done
cp -r /home/kim/Projects/SAO/lumi "$DEST/lumi-scripts"

echo "Staged in $DEST:"
ls -lh "$DEST"
echo "NOTE: pre-stage HF weights separately from a login node (internet there):"
echo "  T5-Gemma (gated!) + SA3 medium-base → HF_HOME=/project/<proj>/models/hf"
echo "  Gated-model auth + HF_HUB_DISABLE_XET=1 (Xet stalls, MASTER §5)."
