#!/bin/bash
# Regenerate the LUMI vendor shim from the stable-audio-tools fork.
# Copies ONLY the self-contained Fusion optimizer modules (torch-only imports —
# verify with: grep "^import\|^from" on each file before adding anything new).
set -euo pipefail
SRC=$(dirname "$0")/../stable-audio-tools/stable_audio_tools/training
DST=$(dirname "$0")/vendor/stable_audio_tools/training
cp "$SRC/fusion_opt.py" "$DST/fusion_opt.py"
cp "$SRC/fusion_groups.py" "$DST/fusion_groups.py"
echo "vendored: fusion_opt.py fusion_groups.py -> $DST"
