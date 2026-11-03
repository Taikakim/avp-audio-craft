#!/usr/bin/env bash
# Last edited: THE-FINN 2026-11-03 — paths updated for the sa3_control_runs/__theme reorganisation
ADIR="/run/media/kim/Mantu/sa3_control_runs/__onsets/onset_AdamW_lr7.5e-5_randomcrop_20ep"
while [ ! -f "$ADIR/riffer_step108000.pt" ]; do
  if ! pgrep -f onset_AdamW_lr7.5e-5_randomcrop_20ep >/dev/null; then
    sleep 30; [ -f "$ADIR/riffer_step108000.pt" ] && break
    echo "[fusion] AdamW exited WITHOUT final ckpt $(date +%H:%M) - NOT launching Fusion; needs attention"; exit 1
  fi
  sleep 120
done
echo "[fusion] AdamW 20ep done $(date +%H:%M); launching Fusion 20ep -> Mantu"
cd /home/kim/Projects/SAO/stable-audio-tools/avp_sa3
SAVE_ROOT=/run/media/kim/Mantu/sa3_control_runs STEPS=108000 SAVE_EVERY=5400 BATCH=1 \
  ./run_control_train.sh onset_Fusion_lr1e-4_randomcrop_20ep 1e-4 fusion --random-crop
echo "[fusion] Fusion 20ep launched $(date +%H:%M)"
