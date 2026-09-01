#!/usr/bin/env bash
# Commit as YOUR OWN fleet identity instead of Kim's.
#   Misc/agent_commit.sh <HANDLE> <normal git commit args...>
#   Misc/agent_commit.sh WINTERMUTE -m "evaluator: fix the stale flag list"
#
# WHY: all four instances share one checkout, so `git config user.name` is a property
# of the TREE, not of who is typing. Every commit we have ever made is authored "Kim",
# so `git log`/`git blame` cannot tell us apart -- which is why attributing work needs
# the three-leg log search (docs/lessons-learned.md). Setting the AUTHOR per commit
# fixes that at the source. Committer stays Kim (the tree owner); author becomes you.
set -eu

HANDLE="${1:-}"; shift || true
case "$HANDLE" in
  WINTERMUTE|CONTINUITY|GHOST-NOTE|THE-FINN) ;;
  *) echo "usage: agent_commit.sh <WINTERMUTE|CONTINUITY|GHOST-NOTE|THE-FINN> <git commit args...>" >&2
     echo "  (got: '${HANDLE}') -- handle must match your session name; see MASTER.md 'Picking your handle'" >&2
     exit 2 ;;
esac

# Lowercase for the email localpart, portable across bash versions.
LOCAL=$(printf '%s' "$HANDLE" | tr '[:upper:]' '[:lower:]')

GIT_AUTHOR_NAME="$HANDLE" \
GIT_AUTHOR_EMAIL="${LOCAL}@aavepyora.online" \
exec git commit "$@"
