#!/bin/bash
# Persistent per-handle SAO listeners as systemd --user services (Linger=yes).
# Explicit units (NOT a template) — file name is hyphen-free, the real handle is
# hardcoded in ExecStart, so there is NO systemd instance-name escaping to get wrong.
# This script only WRITES + reloads the units; it does NOT enable/start them.
# Roll out per-handle, COORDINATED, one at a time (never a live fleet-wide cutover):
#   systemctl --user enable --now sao-listen-<name>
# and the owning session must then stop self-launching its own `listen`.
set -e
U="$HOME/.config/systemd/user"; mkdir -p "$U"
# name(hyphen-free)  ->  real handle
map="continuity:CONTINUITY wintermute:WINTERMUTE thefinn:THE-FINN ghostnote:GHOST-NOTE"
for pair in $map; do
  name="${pair%%:*}"; H="${pair##*:}"
  cat > "$U/sao-listen-$name.service" <<UNIT
[Unit]
Description=SAO fleet listener — $H
After=default.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /home/kim/Projects/SAO/Misc/agent_dialogue.py listen --handle $H --queue-file /home/kim/Projects/SAO/.osc-queue.jsonl
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
UNIT
done
systemctl --user daemon-reload
echo "wrote sao-listen-{continuity,wintermute,thefinn,ghostnote}.service (NOT enabled)."
