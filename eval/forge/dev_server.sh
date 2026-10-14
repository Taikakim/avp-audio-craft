#!/usr/bin/env bash
# Start / stop / inspect the Latent Forge dev render server (this worktree) on :8056.
# The server is the ONLY model process; it announces itself on the GPU lock as KIND=server.
# Owner: Electro-Sheep 1 (created 2026-10-01)
# Last edited: WINTERMUTE 2026-10-12 — dropped the sa3-fork-forge PYTHONPATH override
# Last edited: WINTERMUTE 2026-10-13 — census files (overrides, cleaned_checkpoints) from the main checkout
# Last edited: WINTERMUTE 2026-10-14 — the GPU lock names whoever STARTS the server (start <HANDLE>), not
#   always WINTERMUTE; stop releases under the recorded holder
#
#   eval/forge/dev_server.sh start <HANDLE>     # or FORGE_HANDLE=<HANDLE> ... start
#   eval/forge/dev_server.sh stop               # anyone; releases the lock under the holder's handle
#   eval/forge/dev_server.sh status
set -euo pipefail
WT="$(cd "$(dirname "$0")/../.." && pwd)"
SAO=/home/kim/Projects/SAO
PY=$SAO/.venv/bin/python
# stable_audio_3 comes from the main SA3 checkout (SAO/stable-audio-3, the venv's editable
# install). The Forge hooks (init_latents/inpaint_latents, guided scale_phi) are merged into
# latch-sa3-phase1 (c597447, 2026-10-12), so the separate sa3-fork-forge checkout is retired.
PORT=8056
LOG="${FORGE_SERVER_LOG:-$HOME/.cache/latent-forge/server.log}"
mkdir -p "$(dirname "$LOG")"
# Who started the running server, so `stop` releases the lock under THEIR handle. Until 2026-10-14
# every start was recorded as WINTERMUTE, so a server another instance had started looked like
# W's and nobody could tell whom to ask to yield.
HOLDER="$(dirname "$LOG")/server.$PORT.holder"

# Anchored to the python process itself: an unanchored `pgrep -f` also matched any shell whose
# command line merely MENTIONED the server, and `stop` then killed that shell.
pids() { pgrep -f "^[^ ]*python[^ ]* eval/explorer_render_server\.py --port $PORT( |$)" || true; }

case "${1:-status}" in
  status)
    p="$(pids)"
    echo "pids: ${p:-none}"
    for x in $p; do echo "  $x cwd=$(readlink /proc/"$x"/cwd)"; done
    if curl -sf "localhost:$PORT/status" >/dev/null; then echo "http: up"; else echo "http: down"; fi
    [ -s "$HOLDER" ] && echo "started by: $(cat "$HOLDER")"
    ;;
  stop)
    for x in $(pids); do kill "$x"; done
    for _ in $(seq 1 60); do [ -z "$(pids)" ] && break; sleep 0.5; done
    if [ -n "$(pids)" ]; then echo "still running: $(pids)"; exit 1; fi
    # The recorded holder; for a server started before the holder file existed, the handle in the
    # lock sidecar whose cmd is this server.
    h="$(awk '{print $1}' "$HOLDER" 2>/dev/null || true)"
    if [ -z "$h" ]; then
      h="$(grep -l "explorer_render_server.py --port $PORT" /tmp/gpu.lock.* 2>/dev/null \
           | head -1 | xargs -r sed -n 's/^handle=//p' || true)"
    fi
    if [ -n "$h" ]; then (cd "$SAO" && Misc/gpu_guard.sh release "$h") || true
    else echo "no record of who held the lock for this server; nothing released"; fi
    rm -f "$HOLDER"
    echo "stopped${h:+ (released the lock held as $h)}"
    ;;
  start)
    who="$(echo "${2:-${FORGE_HANDLE:-}}" | tr 'a-z' 'A-Z')"
    if ! [[ "$who" =~ ^[A-Z][A-Z0-9-]{1,31}$ ]]; then
      echo "usage: $0 start <HANDLE>   (or FORGE_HANDLE=<HANDLE>): the GPU lock records who started the server"
      exit 2
    fi
    if [ -n "$(pids)" ]; then echo "already running: $(pids) — run '$0 stop' first"; exit 1; fi
    if ! (cd "$SAO" && python3 Misc/filelock.py check "$SAO/.gpu.lock") | grep -q "unlocked"; then
      echo "GPU lock is held — run: (cd $SAO && Misc/gpu_guard.sh who $who)"; exit 1
    fi
    # The census files are the main checkout's, not this worktree's copies: MODEL NOTES writes
    # there, and the good/broken flags read the list Kim actually maintains.
    envs=(FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2
          SA3_MODEL_OVERRIDES="$SAO/Misc/models_index_overrides.json"
          SA3_CLEANED_CKPTS="$SAO/eval/cleaned_checkpoints.txt")
    cd "$WT"
    setsid nohup env "${envs[@]}" "$PY" eval/explorer_render_server.py --port "$PORT" </dev/null >"$LOG" 2>&1 &
    spid=$!
    disown
    for _ in $(seq 1 240); do curl -sf "localhost:$PORT/status" >/dev/null && break; sleep 1; done
    if ! curl -sf "localhost:$PORT/status" >/dev/null; then echo "did not come up — last log lines:"; tail -20 "$LOG"; exit 1; fi
    (cd "$SAO" && KIND=server NOTE="latent-forge dev server :$PORT from $WT — ask to yield" Misc/gpu_guard.sh acquire "$who" "$spid")
    echo "$who pid=$spid" >"$HOLDER"
    echo "up pid=$spid holder=$who log=$LOG"
    ;;
  *) echo "usage: $0 start <HANDLE>|stop|status"; exit 2 ;;
esac
