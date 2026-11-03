---
name: nested-repo-git-log-scope
description: "Check whether a fix landed by running git log inside the SPECIFIC nested repo (stable-audio-3, mir, muscriptor, stable-audio-tools), not from the outer SAO meta-repo — the outer repo doesn't track their commit history"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: b46bac88-6902-4ad2-a9ea-d4df3a96ae04
  modified: 2026-08-14T22:32:14.557Z
---

Surfaced 2026-08-15: I concluded a bug ("crop_timeseries rate-mismatch" in
`sa3_encode_from_manifest.py`, flagged by WINTERMUTE) was still unfixed based on
`git -C /home/kim/Projects/SAO log -- stable-audio-3/scripts/sa3_encode_from_manifest.py`
returning nothing. Wrong conclusion — the fix had landed two days earlier. The command was
scoped to the wrong repository: `stable-audio-3` (like `stable-audio-tools`, `mir`, `muscriptor`)
is a separately-cloned nested repo under `SAO/` with its own `.git`, not a path the outer SAO
meta-repo's history tracks. Querying the outer repo's log for a path inside a nested repo can
silently return nothing even when the nested repo has real, recent commits.

**How to apply:** to check whether a fix/change landed in any of the nested repos under
`/home/kim/Projects/SAO/` (`stable-audio-3/`, `stable-audio-tools/`, `mir/` if nested,
`muscriptor/`, etc.), run `git log` with `-C` pointed at the SPECIFIC nested repo's own
directory — `git -C /home/kim/Projects/SAO/stable-audio-3 log -- scripts/foo.py` — never from
the outer SAO repo. A "no commits found" result from the wrong scope looks identical to a
genuine "not fixed yet," so this is an easy false negative to walk into confidently. When in
doubt about which repo a file actually belongs to, `git -C <dir> rev-parse --show-toplevel`
from the file's own directory reveals the real repo root.
