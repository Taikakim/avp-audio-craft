#!/usr/bin/env bash
# Start / stop / inspect the Latent Forge dev render server (this worktree) on :8056.
# The server is the ONLY model process; it announces itself on the GPU lock as KIND=server.
set -euo pipefail
WT="$(cd "$(dirname "$0")/../.." && pwd)"
SAO=/home/kim/Projects/SAO
PY=$SAO/.venv/bin/python
FORK=/home/kim/Projects/sa3-fork-forge
PORT=8056
LOG="${FORGE_SERVER_LOG:-$HOME/.cache/latent-forge/server.log}"
mkdir -p "$(dirname "$LOG")"

pids() { pgrep -f "eval/explorer_render_server.py --port $PORT" || true; }

case "${1:-status}" in
  status)
    p="$(pids)"
    echo "pids: ${p:-none}"
    for x in $p; do echo "  $x cwd=$(readlink /proc/"$x"/cwd)"; done
    if curl -sf "localhost:$PORT/status" >/dev/null; then echo "http: up"; else echo "http: down"; fi
    ;;
  stop)
    for x in $(pids); do kill "$x"; done
    for _ in $(seq 1 60); do [ -z "$(pids)" ] && break; sleep 0.5; done
    if [ -n "$(pids)" ]; then echo "still running: $(pids)"; exit 1; fi
    (cd "$SAO" && Misc/gpu_guard.sh release WINTERMUTE) || true
    echo "stopped"
    ;;
  start)
    if [ -n "$(pids)" ]; then echo "already running: $(pids) — run '$0 stop' first"; exit 1; fi
    if ! (cd "$SAO" && python3 Misc/filelock.py check "$SAO/.gpu.lock") | grep -q "unlocked"; then
      echo "GPU lock is held — run: (cd $SAO && Misc/gpu_guard.sh who WINTERMUTE)"; exit 1
    fi
    envs=(FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2)
    if [ -d "$FORK" ]; then envs+=("PYTHONPATH=$FORK"); fi
    cd "$WT"
    setsid nohup env "${envs[@]}" "$PY" eval/explorer_render_server.py --port "$PORT" </dev/null >"$LOG" 2>&1 &
    spid=$!
    disown
    for _ in $(seq 1 240); do curl -sf "localhost:$PORT/status" >/dev/null && break; sleep 1; done
    if ! curl -sf "localhost:$PORT/status" >/dev/null; then echo "did not come up — last log lines:"; tail -20 "$LOG"; exit 1; fi
    (cd "$SAO" && KIND=server NOTE="latent-forge dev server :$PORT from $WT — ask to yield" Misc/gpu_guard.sh acquire WINTERMUTE "$spid")
    echo "up pid=$spid log=$LOG"
    ;;
  *) echo "usage: $0 start|stop|status"; exit 2 ;;
esac
