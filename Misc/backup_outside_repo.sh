#!/usr/bin/env bash
# Owner: THE-FINN (created 2026-11-03)
# Copy what lives outside every repo into backup/ so it is tracked: page builders and tools in $HOME,
# the systemd units, agent definitions, and every project's auto-memory. Re-runnable; run from the weekly routine.
# Scan new material for credentials before committing. ~/.config/aavepyora.conf and SSH keys are deliberately NOT copied.
set -eu
B=/home/kim/Projects/SAO/backup; H=/home/kim; mkdir -p "$B"/home_scripts "$B"/home_bin "$B"/systemd_user "$B"/claude_agents "$B"/claude_memory
cp -p "$H"/*.py "$B"/home_scripts/ 2>/dev/null || true
find "$H/bin" -maxdepth 1 -type f -exec cp -p {} "$B"/home_bin/ \;
cp -p "$H"/.config/systemd/user/sao-* "$H"/.config/systemd/user/mirror-* "$B"/systemd_user/ 2>/dev/null || true
cp -p "$H"/.claude/agents/*.md "$B"/claude_agents/ 2>/dev/null || true
for d in "$H"/.claude/skills/*/; do [ -L "${d%/}" ] || { mkdir -p "$B/claude_skills/$(basename "$d")"; cp -rp "$d". "$B/claude_skills/$(basename "$d")/"; }; done
cp -p "$H"/.claude/settings.json "$B"/claude_settings.json 2>/dev/null || true
for d in "$H"/.claude/projects/*/memory "$H"/.claude/agent-memory; do
  [ -d "$d" ] || continue
  n=$(basename "$(dirname "$d")"); [ "$(basename "$d")" = agent-memory ] && n=_agent-memory
  mkdir -p "$B/claude_memory/$n"; cp -rp "$d"/. "$B/claude_memory/$n/"
done
du -sh "$B" | cut -f1
