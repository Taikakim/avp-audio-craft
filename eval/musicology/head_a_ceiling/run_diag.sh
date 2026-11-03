#!/bin/bash
# Head A diagnostics: (a) global-shift alignment sweep, (b) capacity probe.
# Chained after run_sweep.sh (waits for its lock to clear via acquire).
cd /home/kim/Projects/SAO/eval/musicology/head_a_ceiling || exit 1
PY=/home/kim/Projects/SAO/.venv/bin/python
LOCK=/home/kim/Projects/SAO/.gpu.lock
python3 /home/kim/Projects/SAO/Misc/filelock.py acquire "$LOCK" \
  --handle CONTINUITY-heada --pid-aware --pid $$ --timeout 21600 || exit 1
trap 'python3 /home/kim/Projects/SAO/Misc/filelock.py release "$LOCK" --handle CONTINUITY-heada' EXIT

set -x
# (a) alignment: short mlp_ctx1 runs at target shifts; shift 0 rerun = baseline
for s in 0 -3 -2 -1 1 2 3; do
  $PY train_readout.py --variant mlp_ctx1 --target y8 --epochs 10 --patience 10 --shift $s
done
# (b) capacity: deeper+wider MLP
$PY train_readout.py --variant mlp2_ctx2 --target y8 --hidden 1024 --epochs 40
echo DIAG_DONE
