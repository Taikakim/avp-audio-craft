#!/bin/bash
# Last edited: THE-FINN 2026-11-03 — root-variable paths updated for the __theme sorting
# Last edited: THE-FINN 2026-11-03 — paths updated for the sa3_control_runs/__theme reorganisation
# Stage 1 LATCH-OFF cells only (E baseline, A FusionCC) — valid regardless of which
# guidance head walks (the onset_envelope operating-point probe failed 2026-07-03;
# EMA retrain in flight). F/B run later with the revived head.
# Detached run:  setsid nohup Misc/run_composed_stage1_offcells.sh > logs/composed_offcells.log 2>&1 &
set -u
SAO=/home/kim/Projects/SAO
Q="$SAO/composed_eval_queue"
OUT=/run/media/kim/Mantu/sa3_control_runs/__misc/composed_sweep
RUNS=/run/media/kim/Mantu/sa3_control_runs
MIRPY=/home/kim/Projects/mir/mir/bin/python
SRVPY="$SAO/stable-audio-3/.venv/bin/python"
note() { "$SAO/Misc/worklog_note.sh" composed-sweep "$@" || true; }

boot_server() {
  setsid nohup env FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 \
    "$SRVPY" "$SAO/onnx/control_eval_server.py" \
    --dit-onnx "$1/ctrl_fp16.onnx" --cond-npz "$1/ctrl.cond.npz" \
    --decoder-onnx "$SAO/stable-audio-3/same_decoder_L128_fp16.onnx" \
    --queue-root "$Q" --threads 12 \
    > "$SAO/logs/composed_server_$2.log" 2>&1 &
  for i in $(seq 1 60); do [ -f "$Q/.server_ready" ] && return 0; sleep 5; done
  echo "[fatal] server $2 never became ready"; exit 1
}

mkdir -p "$OUT" "$SAO/logs"
echo "=== Stage 1 off-cells start $(date '+%F %T') ==="

[ -f "$Q/.server_ready" ] || boot_server "$RUNS/__onsets/onset_Fusion_lr1e-4_randomcrop" baseline
"$MIRPY" "$SAO/Misc/composed_sweep_eval.py" --queue-root "$Q" --out "$OUT/E_fusion" \
  --condition E_fusion --run onset_Fusion_lr1e-4_randomcrop \
  --notes "Stage 1 anchor cell E (adapter only)"
note "composed Stage1 E_fusion done ($(date +%H:%M))"

pkill -f "control_eval_server.py --dit-onnx" || true
rm -f "$Q/.server_ready"; sleep 3
boot_server "$RUNS/__onsets/onset_FusionCC_lr1e-4_randomcrop" cc
"$MIRPY" "$SAO/Misc/composed_sweep_eval.py" --queue-root "$Q" --out "$OUT/A_cc" \
  --condition A_cc --run onset_FusionCC_lr1e-4_randomcrop \
  --notes "Stage 1 cell A (FusionCC adapter only)"
note "composed Stage1 A_cc done — off-cells COMPLETE ($(date +%H:%M))"

pkill -f "control_eval_server.py --dit-onnx" || true
rm -f "$Q/.server_ready"
echo "=== Stage 1 off-cells complete $(date '+%F %T') ==="
