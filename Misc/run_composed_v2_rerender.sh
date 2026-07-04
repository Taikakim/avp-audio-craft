#!/bin/bash
# Clip-fixed re-render of Stage 1 (E_fusion_v2, A_cc_v2) for ear verdicts.
# MUST live as a file: an inline `bash -c` version self-killed at launch because
# pkill -f "control_eval_server" matched the script text embedded in its own cmdline.
set -u
SAO=/home/kim/Projects/SAO
Q="$SAO/composed_eval_queue"
RUNS=/run/media/kim/Mantu/sa3_control_runs
OUT=$RUNS/composed_sweep

boot() {
  setsid nohup env FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 \
    "$SAO/stable-audio-3/.venv/bin/python" "$SAO/onnx/control_eval_server.py" \
    --dit-onnx "$1/ctrl_fp16.onnx" --cond-npz "$1/ctrl.cond.npz" \
    --decoder-onnx "$SAO/stable-audio-3/same_decoder_L128_fp16.onnx" \
    --queue-root "$Q" --threads 12 > "$SAO/logs/composed_server_$2.log" 2>&1 &
  for i in $(seq 1 60); do [ -f "$Q/.server_ready" ] && return 0; sleep 5; done
  echo "[fatal] server $2 not ready"; exit 1
}
stop() { pkill -f "control_eval_server.py --dit"; rm -f "$Q/.server_ready"; sleep 3; }

stop
boot "$RUNS/onset_Fusion_lr1e-4_randomcrop" baseline_v2
/home/kim/Projects/mir/mir/bin/python "$SAO/Misc/composed_sweep_eval.py" --queue-root "$Q" \
  --out "$OUT/E_fusion_v2" --condition E_fusion_v2 --run onset_Fusion_lr1e-4_randomcrop \
  --notes "Stage 1 cell E re-render, CLIP-FIXED writer (normalize-down), for ear verdicts"
"$SAO/Misc/worklog_note.sh" composed-sweep "E_fusion_v2 (clip-fixed) done ($(date +%H:%M))"

stop
boot "$RUNS/onset_FusionCC_lr1e-4_randomcrop" cc_v2
/home/kim/Projects/mir/mir/bin/python "$SAO/Misc/composed_sweep_eval.py" --queue-root "$Q" \
  --out "$OUT/A_cc_v2" --condition A_cc_v2 --run onset_FusionCC_lr1e-4_randomcrop \
  --notes "Stage 1 cell A re-render, CLIP-FIXED writer, for ear verdicts"
"$SAO/Misc/worklog_note.sh" composed-sweep "A_cc_v2 (clip-fixed) done — clean Stage1 audition sets ready ($(date +%H:%M))"
stop
