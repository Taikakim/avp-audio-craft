#!/bin/bash
# Migrate fleet listeners to persistent systemd --user services. COORDINATED cutover:
# each session must STOP self-launching `listen` once its service is enabled (else two
# listeners for one handle = the collision bug). Sessions keep arming only `wait`/Monitor.
set -e
U="$HOME/.config/systemd/user"; mkdir -p "$U"
cp /home/kim/Projects/SAO/Misc/sao-listen@.service "$U/"
systemctl --user daemon-reload
for H in CONTINUITY WINTERMUTE THE-FINN GHOST-NOTE; do
  echo "== $H: kill session listener, enable service =="
  pkill -f "agent_dialogue.py listen --handle $H" 2>/dev/null || true
  systemctl --user enable --now "sao-listen@${H}"
done
systemctl --user status 'sao-listen@*' --no-pager | grep -E "sao-listen@|Active:" | head
