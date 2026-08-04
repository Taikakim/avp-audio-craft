#!/bin/bash
# chroma_steer_driver.sh — polite, verify-first driver for the extended chroma-steering
# render (Kim ask 2026-07-19). Run DETACHED (setsid) so the harness can't reap it.
#
# It does NOT stomp the GPU: waits for a free card first (yields to Kim's running scalar
# LatCH sweep + anything else, MASTER G-first rule), then:
#   1) verify-one — render ONE hpcp clip + baseline; the harness exits 0 only if the
#      chroma actually MOVED vs baseline (the engine's on-GPU behaviour was never
#      validated — chroma_guided_generator was STUB-THIS-PASS).
#   2) pilot — ONLY if verify-one passed. ~24 clips (hpcp x 3 instruments x {1 key,
#      1 progression} x gain ladder x 1 seed) + baselines.
#   3) STOP. The full 3456-clip grid is Kim's call (trim seeds/prompts first) — this
#      driver never fires it.
# Launch:  setsid bash eval/chroma_steer_driver.sh >/tmp/chroma_steer_driver.log 2>&1 &
set -uo pipefail
cd /home/kim/Projects/SAO
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2 \
       OMP_NUM_THREADS=4 MKL_NUM_THREADS=4
PY=/home/kim/Projects/SAO/.venv/bin/python

wait_gpu() {  # block until VRAM used < 3 GB (no one else training/rendering), max ~10h
  for _ in $(seq 1 1200); do
    used=$(rocm-smi --showmeminfo vram 2>/dev/null | grep -oiP "used memory \(b\): \K[0-9]+" | head -1)
    if [ -n "${used:-}" ] && [ "$used" -lt 3000000000 ]; then return 0; fi
    sleep 30
  done
  echo "[driver] wait_gpu timed out after ~10h — GPU stayed busy; leaving for Kim."; return 1
}

echo "[driver] $(date +%H:%M) waiting for a free GPU (yielding to the running scalar sweep)"
wait_gpu || exit 0

echo "[driver] $(date +%H:%M) GPU free — verify-one (go/no-go)"
if ${PY} eval/chroma_steer_render.py --verify-one; then
  echo "[driver] $(date +%H:%M) verify PASSED — rendering pilot"
  wait_gpu || exit 0
  ${PY} eval/chroma_steer_render.py --pilot
  echo "[driver] $(date +%H:%M) pilot DONE — full grid left for Kim's greenlight (trim first)"
else
  rc=$?
  echo "[driver] $(date +%H:%M) verify did NOT move the chroma (rc=$rc) — STOPPING before the pilot."
  echo "[driver] the engine (chroma_guided_generator target_raw path) needs a rho/mu tune;"
  echo "[driver] do not run the grid until a verify clip moves. See /tmp/chroma_steer_driver.log."
fi
echo "[driver] $(date +%H:%M) exit"
