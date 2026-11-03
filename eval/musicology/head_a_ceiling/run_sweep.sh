#!/bin/bash
# Head A ceiling sweep — holds .gpu.lock with this script's live pid throughout.
cd /home/kim/Projects/SAO/eval/musicology/head_a_ceiling || exit 1
PY=/home/kim/Projects/SAO/.venv/bin/python
LOCK=/home/kim/Projects/SAO/.gpu.lock
python3 /home/kim/Projects/SAO/Misc/filelock.py acquire "$LOCK" \
  --handle CONTINUITY-heada --pid-aware --pid $$ --timeout 21600 || exit 1
trap 'python3 /home/kim/Projects/SAO/Misc/filelock.py release "$LOCK" --handle CONTINUITY-heada' EXIT

set -x
# 1. clean-z0 ceiling variants (folded target)
for v in lin_ctx0 lin_ctx1 lin_ctx2 mlp_ctx1 mlp_ctx2 mlp_ctx4; do
  $PY train_readout.py --variant "$v" --target y8 --epochs 40
done
# 2. directional 14-class on the MLP archs (needed for acceptance decoding)
$PY train_readout.py --variant mlp_ctx2 --target y14 --epochs 40
$PY train_readout.py --variant mlp_ctx4 --target y14 --epochs 40
# 3. noise robustness: t-conditioned, init from clean mlp_ctx2
$PY train_readout.py --variant mlp_ctx2 --target y8 --noise --epochs 40 \
    --init_from readout_mlp_ctx2_y8.pt
echo SWEEP_DONE
