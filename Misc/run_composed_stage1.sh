#!/bin/bash
# Stage 1 of the composed control x LatCH sweep (spec 2026-07-03): the 2x2 core —
# {baseline Fusion, FusionCC} x {LatCH off, on} = 4 x 162 = 648 renders, all CPU.
# Run DETACHED (kill-wave-proof):  setsid nohup Misc/run_composed_stage1.sh <RHO_MU> \
#     > logs/composed_stage1.log 2>&1 &
# Assumes the composed server is ALREADY UP on the BASELINE graph (E/F run first);
# the script then swaps the server to the FusionCC graph for A/B.
set -u
RHO_MU="${1:?usage: run_composed_stage1.sh <rho_mu from calibration>}"
SAO=/home/kim/Projects/SAO
Q="$SAO/composed_eval_queue"
OUT=/run/media/kim/Mantu/sa3_control_runs/composed_sweep
RUNS=/run/media/kim/Mantu/sa3_control_runs
MIRPY=/home/kim/Projects/mir/mir/bin/python
SRVPY="$SAO/stable-audio-3/.venv/bin/python"
DRIVER="$SAO/Misc/composed_sweep_eval.py"
note() { "$SAO/Misc/worklog_note.sh" composed-sweep "$@" || true; }

boot_server() {  # $1 = run dir (adapter graph), $2 = log tag
  setsid nohup env FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 \
    "$SRVPY" "$SAO/onnx/control_eval_server.py" \
    --dit-onnx "$1/ctrl_fp16.onnx" --cond-npz "$1/ctrl.cond.npz" \
    --decoder-onnx "$SAO/stable-audio-3/same_decoder_L128_fp16.onnx" \
    --queue-root "$Q" --threads 12 \
    > "$SAO/logs/composed_server_$2.log" 2>&1 &
  for i in $(seq 1 60); do [ -f "$Q/.server_ready" ] && return 0; sleep 5; done
  echo "[fatal] server $2 never became ready"; exit 1
}

kill_server() {
  pkill -f "control_eval_server.py --dit-onnx" || true
  rm -f "$Q/.server_ready"; sleep 3
}

run_cond() {  # $1 = condition tag, $2 = run label, $3 = extra driver args
  "$MIRPY" "$DRIVER" --queue-root "$Q" --out "$OUT/$1" --condition "$1" \
    --run "$2" --rho-mu "$RHO_MU" $3 \
    --notes "Stage 1 composed sweep; spec 2026-07-03-composed-control-latch-sweep"
  note "composed Stage1 $1 done ($(date +%H:%M))"
}

mkdir -p "$OUT" "$SAO/logs"
echo "=== Stage 1 start $(date '+%F %T')  rho_mu=$RHO_MU ==="

# E/F on the baseline graph (server assumed up; boot if not)
[ -f "$Q/.server_ready" ] || boot_server "$RUNS/onset_Fusion_lr1e-4_randomcrop" baseline
run_cond E_fusion       onset_Fusion_lr1e-4_randomcrop   ""
run_cond F_fusion_latch onset_Fusion_lr1e-4_randomcrop   "--latch"

kill_server
boot_server "$RUNS/onset_FusionCC_lr1e-4_randomcrop" cc
run_cond A_cc       onset_FusionCC_lr1e-4_randomcrop  ""
run_cond B_cc_latch onset_FusionCC_lr1e-4_randomcrop  "--latch"

kill_server
echo "=== Stage 1 complete $(date '+%F %T') ==="
note "composed sweep STAGE 1 COMPLETE — 4 conditions x 162 cells at $OUT"
