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
#   2. The /tmp/gpu.lock foreign channel and our SAO/.gpu.lock mutex are BOTH handled by
#      filelock.py (it mirrors + refuses on a live foreign holder). This script does not touch
#      the mirror -- what it adds is the rocm-smi gate, which filelock deliberately does not do.
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
    # /tmp/gpu.lock is filelock.py's job since 2026-08-07 (C, Kim-directed): it refuses on a live
    # foreign holder, writes the mirror on acquire and clears it on release, in ITS format
    # (HANDLE pid=N ts=...). This script must NOT touch the file -- writing a bare pid here would
    # break filelock's own "clear only if it's ours" parse and strand a stale lock blocking everyone.
    python3 "$SAO/Misc/filelock.py" acquire "$OURS" --handle "$HANDLE" --pid-aware --pid "$MYPID" \
      --gpu-kind "${KIND:-batch}" --gpu-note "${NOTE:-}" || exit 1
    echo "[gpu_guard] acquired (filelock owns the $FOREIGN mirror + $FOREIGN.$(echo "$HANDLE" | tr 'A-Z' 'a-z') sidecar)"
    ;;
  release)
    python3 "$SAO/Misc/filelock.py" release "$OURS" --handle "$HANDLE"   # also clears the mirror
    echo "[gpu_guard] released"
    ;;
  who)
    # "who holds the GPU, and can they yield?" -- the question GHOST-NOTE could not
    # answer on 2026-08-26 while waiting 10.6 h on what turned out to be a resident
    # server rather than a batch job (Kim 2026-08-27: keep the lock EXCLUSIVE, make
    # the holder ASKABLE).
    echo "[gpu_guard] rocm-smi (ground truth):"
    rocm-smi --showpids 2>/dev/null | awk '$1 ~ /^[0-9]+$/ && $4+0 > 0 {printf "  pid %s  %s bytes\n", $1, $4}'
    echo "[gpu_guard] announced holders:"
    python3 "$SAO/Misc/filelock.py" gpu-who "$OURS" --handle "${HANDLE:-query}"
    ;;
  *)
    echo "usage: $0 {acquire|release|who} <HANDLE> [PID]"
    echo "  KIND=server NOTE='what it is' $0 acquire <HANDLE> <PID>   # resident, can yield"
    exit 2 ;;
esac
