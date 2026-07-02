#!/usr/bin/env bash
# Append a note to WORKLOG.md and ping the OSC coordination channel in one atomic habit.
#   Misc/worklog_note.sh <session-tag> <text...>
set -eu
SESSION="$1"; shift
printf -- "- [%s] %s %s\n" "$(date +%F\ %H:%M)" "($SESSION)" "$*" >> /home/kim/Projects/SAO/WORKLOG.md
python3 /home/kim/Projects/SAO/Misc/osc_worklog.py send --session "$SESSION" --note "$*"
