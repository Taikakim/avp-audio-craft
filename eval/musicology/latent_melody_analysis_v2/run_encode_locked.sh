#!/bin/bash
# One GPU-lock window around the v2 encode. Run in background; logs to .encode.log.
set -u
cd /home/kim/Projects/SAO
/usr/bin/python3 Misc/filelock.py acquire /home/kim/Projects/SAO/.gpu.lock \
  --handle CONTINUITY-melenc2 --pid-aware --pid $$ --timeout 14400 || exit 1
.venv/bin/python eval/musicology/latent_melody_analysis_v2/encode_test_midis_v2.py \
  >> eval/musicology/latent_melody_analysis_v2/.encode.log 2>&1
rc=$?
/usr/bin/python3 Misc/filelock.py release /home/kim/Projects/SAO/.gpu.lock --handle CONTINUITY-melenc2
echo "encode rc=$rc"
exit $rc
