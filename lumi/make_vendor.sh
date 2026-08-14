#!/bin/bash
# Regenerate the LUMI vendor shim from the stable-audio-tools fork.
# Copies ONLY self-contained modules (verify with: grep "^import\|^from" on each
# file before adding anything new -- for the Fusion optimizer that means torch-only
# imports; for crop_timeseries_resample.py it means stdlib+numpy only, no mir deps).
set -euo pipefail
ROOT=$(dirname "$0")/..
SRC=$ROOT/stable-audio-tools/stable_audio_tools/training
DST=$ROOT/lumi/vendor/stable_audio_tools/training
cp "$SRC/fusion_opt.py" "$DST/fusion_opt.py"
cp "$SRC/fusion_groups.py" "$DST/fusion_groups.py"
echo "vendored: fusion_opt.py fusion_groups.py -> $DST"

# 2026-08-15 (Kim relaying G's Stage-3 pre-encode blocker report): sa3_encode_from_manifest.py's
# _load_w_resampler() looks for this at lumi/vendor/crop_timeseries_resample.py as the fallback
# when the mir checkout isn't reachable (i.e. every real LUMI run) -- that fallback file never
# existed, so encoding on LUMI would ImportError immediately rather than silently mis-slice. Loud,
# not silent, but still a hard blocker until vendored.
cp "$ROOT/../mir/src/tools/crop_timeseries_resample.py" "$ROOT/lumi/vendor/crop_timeseries_resample.py"
echo "vendored: crop_timeseries_resample.py -> $ROOT/lumi/vendor/"
