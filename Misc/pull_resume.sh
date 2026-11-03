#!/bin/bash
# Resume the LUMI pull once auth recovers.
#
# The previous version opened a NEW ssh connection per file per retry -- 8 rapid
# reconnects on the first stall, which is what tripped LUMI's connection throttle
# ("Permission denied (publickey)" with a valid, agent-loaded key). Fix: ONE shared
# ControlMaster connection that every rsync reuses, so the whole remaining pull costs
# a single authentication instead of ~50.
set -u
DEST=/run/media/kim/Mantu/lumi_runs/runs/runs/
LIST=$(dirname "$0")/todo_MANTU.txt
HOST=akekim@efp.lumi.csc.fi
SRC=$HOST:/scratch/project_465003186/runs/
CP=/tmp/ssh-lumi-pull.sock
BASE="ssh -i $HOME/.ssh/id_EFP -o BatchMode=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=4"
MUX="$BASE -o ControlMaster=auto -o ControlPath=$CP -o ControlPersist=900"

# Waiting for the throttle to lift is done OUTSIDE this script (a long in-script sleep
# gets the background task reaped). Launch this only once ssh auth is confirmed back.

# ---- one master connection, reused by every rsync below

timeout 60 $MUX -N -f "$HOST" 2>/dev/null
echo "[resume] control master up: $($BASE -o ControlPath=$CP -O check "$HOST" 2>&1)"

total=$(grep -c . "$LIST"); n=0; ok=0; fail=0
while IFS= read -r rel; do
  [ -z "$rel" ] && continue
  n=$((n+1))
  for attempt in 1 2 3; do
    printf '%s\n' "$rel" > /tmp/.pull_one_$$
    rsync -a --partial --append-verify --timeout=900 \
          --files-from=/tmp/.pull_one_$$ -e "$MUX" "$SRC" "$DEST"
    rc=$?
    if [ $rc -eq 0 ]; then
      echo "[MANTU $n/$total] OK (try $attempt) $(date +%H:%M:%S)  $rel"; ok=$((ok+1)); break
    fi
    echo "[MANTU $n/$total] rc=$rc try $attempt: $rel"
    if [ "$attempt" = 3 ]; then echo "[MANTU $n/$total] GAVE UP: $rel"; fail=$((fail+1)); fi
    sleep 120                     # gentle: never a reconnect storm
  done
done < "$LIST"
rm -f /tmp/.pull_one_$$
$BASE -o ControlPath=$CP -O exit "$HOST" 2>/dev/null
echo "=== [MANTU] done: $ok ok, $fail failed, of $total @ $(date) ==="
echo "=== free: $(df -h "$DEST" | awk 'NR==2{print $4}') ==="
