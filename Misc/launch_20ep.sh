#!/usr/bin/env bash
# wait for the Lehto->Mantu move, then for the GPU to go idle, then launch AdamW 20ep
while ! grep -q MOVE_DONE /tmp/move_sa3.log 2>/dev/null; do sleep 60; done
echo "[20ep] move done $(date +%H:%M); waiting for GPU idle..."
f=0
while [ $f -lt 3 ]; do
  n=$(rocm-smi --showpids 2>/dev/null | sed -n '/KFD process/,/End/p' | grep -cE '^[0-9]')
  if [ "${n:-0}" -eq 0 ]; then f=$((f+1)); else f=0; fi
  sleep 60
done
echo "[20ep] GPU idle $(date +%H:%M); launching AdamW 20ep -> Mantu"
cd /home/kim/Projects/SAO/stable-audio-tools/avp_sa3
SAVE_ROOT=/run/media/kim/Mantu/sa3_control_runs STEPS=108000 SAVE_EVERY=5400 BATCH=1 \
  ./run_control_train.sh onset_AdamW_lr7.5e-5_randomcrop_20ep 7.5e-5 adamw --random-crop
echo "[20ep] AdamW 20ep launched $(date +%H:%M)"
