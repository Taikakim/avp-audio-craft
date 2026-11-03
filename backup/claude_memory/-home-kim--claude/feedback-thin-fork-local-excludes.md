---
name: feedback-thin-fork-local-excludes
description: "For a thin-fork repo (stable-audio-3 over Stability-AI), put machine-local junk in .git/info/exclude, never .gitignore"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: bb4fab0e-08ce-429d-9432-241bc4433721
  modified: 2026-09-22T06:59:57.948Z
---

For a THIN FORK repo (`stable-audio-3` over Stability-AI, per MASTER §1), machine-local
debris (caches, local run artifacts, per-clone junk) belongs in `.git/info/exclude`, not
a tracked `.gitignore`.

**Why:** `.git/info/exclude` is per-clone and invisible to upstream — it produces no
tracked-file diff. A tracked `.gitignore` entry becomes a diff against upstream that
re-conflicts on every future merge from Stability-AI. WINTERMUTE used this distinction
during the 2026-09-21/22 tree-sync sweep to clean stable-audio-3 from 45 dirty entries
down to 2 legitimate ones, decomposing what looked like one big mess into 7 real edits +
38 harmless debris, without adding upstream-merge friction.

**How to apply:** Before adding anything to a fork's `.gitignore`, check whether the repo
is a thin fork of an actively-upstreamed project (see MASTER §1 for the fork list). If so,
default to `.git/info/exclude` instead. Regular (non-fork) repos under the fleet's control
can still use tracked `.gitignore` normally.
