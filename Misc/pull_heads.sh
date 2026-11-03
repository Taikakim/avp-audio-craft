#!/bin/bash
# Pull the two melody/morph lanes that were never in the keep-set (C, 2026-09-03, Kim: "pull
# everything"). ftstack_heads (B9: Head-B on the full-FT backbone + 6 LatCH heads) and
# morph_head_sweep (SWEEP-1) were LUMI-ONLY with the scratch purge ~2026-11-20 ahead.
#
# SMALLEST-FIRST on purpose: the six LatCH heads are 0.55 GiB per arm and the highest
# value-per-byte in the set, so they land even if the drive fills. ONE ControlMaster
# connection for the whole pull -- a reconnect per file trips LUMI's throttle
# (lumi-ops SKILL, "Bulk PULLS").
set -u
DEST=/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/runs/
LIST=$(dirname "$0")/todo_HEADS.sorted.txt
HOST=akekim@efp.lumi.csc.fi
SRC=$HOST:/scratch/project_465003186/runs/
CP=/tmp/ssh-lumi-heads.sock
BASE="ssh -i $HOME/.ssh/id_EFP -o BatchMode=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=4"
MUX="$BASE -o ControlMaster=auto -o ControlPath=$CP -o ControlPersist=1800"

timeout 60 $MUX -N -f "$HOST" 2>/dev/null
echo "[heads] master: $($BASE -o ControlPath=$CP -O check "$HOST" 2>&1)"

total=$(grep -c . "$LIST"); n=0; ok=0; fail=0
while IFS= read -r rel; do
  [ -z "$rel" ] && continue
  n=$((n+1))
  # stop before filling the drive: keep 8 GiB headroom
  free_gb=$(df -BG --output=avail "$DEST" | tail -1 | tr -dc '0-9')
  if [ "${free_gb:-0}" -lt 8 ]; then
    echo "[heads] STOP at $n/$total: only ${free_gb}G free, keeping 8G headroom"; break
  fi
  for attempt in 1 2 3; do
    printf '%s\n' "$rel" > /tmp/.pull_head_$$
    rsync -a --partial --append-verify --timeout=900 \
          --files-from=/tmp/.pull_head_$$ -e "$MUX" "$SRC" "$DEST"
    rc=$?
    if [ $rc -eq 0 ]; then
      echo "[heads $n/$total] OK $(date +%H:%M:%S) ${free_gb}G free  $rel"; ok=$((ok+1)); break
    fi
    echo "[heads $n/$total] rc=$rc try $attempt: $rel"
    [ "$attempt" = 3 ] && { echo "[heads $n/$total] GAVE UP: $rel"; fail=$((fail+1)); }
    sleep 120
  done
done < "$LIST"
rm -f /tmp/.pull_head_$$
$BASE -o ControlPath=$CP -O exit "$HOST" 2>/dev/null
echo "[heads] DONE ok=$ok fail=$fail of $total"
