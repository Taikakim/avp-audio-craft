#!/bin/bash
# gpu_guard.sh — one call that honours the whole local-GPU convention (Kim 2026-08-07).
#
#   Misc/gpu_guard.sh acquire <HANDLE> <PID>   # 0 = you may use the GPU, 1 = do not start
#   Misc/gpu_guard.sh release <HANDLE>
#
# WHY THIS EXISTS: the convention has three parts and the ORDER matters. A non-team instance
# shares this box and is supposed to honour /tmp/gpu.lock — but VERIFIED 2026-08-07, it was
# rendering with 9.7 GB of VRAM and had written NO lockfile. Checking /tmp/gpu.lock alone would
# have reported "free" and stomped it (the 07-21-class concurrent-GPU crash). So:
#   1. rocm-smi --showpids is GROUND TRUTH and is checked FIRST — a lockfile is a claim,
#      occupied VRAM is a fact.
#   2. /tmp/gpu.lock is the foreign instance's channel: honour it, and MIRROR ours into it so
#      they can see us.
#   3. SAO/.gpu.lock stays the fleet's own mutex (pid-aware).
set -u
ACTION="${1:-}"; HANDLE="${2:-WINTERMUTE}"; MYPID="${3:-$$}"
SAO=/home/kim/Projects/SAO
OURS=$SAO/.gpu.lock
FOREIGN=/tmp/gpu.lock
MIN_VRAM=$((512*1024*1024))     # ignore trivial/idle contexts; a real job holds far more

foreign_gpu_pids() {
  rocm-smi --showpids 2>/dev/null | awk -v min="$MIN_VRAM" '
    $1 ~ /^[0-9]+$/ && $4+0 > min { print $1 }'
}

case "$ACTION" in
  acquire)
    for pid in $(foreign_gpu_pids); do
      [ "$pid" = "$MYPID" ] && continue
      args=$(ps -o args= -p "$pid" 2>/dev/null)
      case "$args" in
        *Projects/SAO*|*Projects/mir*) owner="ours" ;;
        *) owner="FOREIGN" ;;
      esac
      echo "[gpu_guard] BUSY: pid $pid ($owner) holds the GPU — $(echo "$args" | cut -c1-70)"
      echo "[gpu_guard] refusing to start (rocm-smi is ground truth, lockfiles are only claims)"
      exit 1
    done
    if [ -e "$FOREIGN" ]; then
      fpid=$(cat "$FOREIGN" 2>/dev/null | tr -dc '0-9')
      if [ -n "$fpid" ] && ! kill -0 "$fpid" 2>/dev/null; then
        echo "[gpu_guard] /tmp/gpu.lock held by DEAD pid $fpid — reclaiming"; rm -f "$FOREIGN"
      else
        echo "[gpu_guard] BUSY: /tmp/gpu.lock present (pid ${fpid:-unknown})"; exit 1
      fi
    fi
    python3 "$SAO/Misc/filelock.py" acquire "$OURS" --handle "$HANDLE" --pid-aware --pid "$MYPID" || exit 1
    echo "$MYPID" > "$FOREIGN" 2>/dev/null || echo "[gpu_guard] WARN: could not mirror to $FOREIGN"
    echo "[gpu_guard] acquired (ours + mirrored to $FOREIGN, pid $MYPID)"
    ;;
  release)
    if [ -e "$FOREIGN" ] && [ "$(cat "$FOREIGN" 2>/dev/null | tr -dc '0-9')" = "$MYPID" ]; then
      rm -f "$FOREIGN"
    elif [ -e "$FOREIGN" ]; then
      echo "[gpu_guard] NOT removing $FOREIGN — it is not ours"
    fi
    python3 "$SAO/Misc/filelock.py" release "$OURS" --handle "$HANDLE"
    echo "[gpu_guard] released"
    ;;
  *)
    echo "usage: $0 {acquire|release} <HANDLE> [PID]"; exit 2 ;;
esac
