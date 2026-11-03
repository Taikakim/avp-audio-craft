---
name: filelock-shared-files-and-pipe-exit-codes
description: Take a filelock before editing any file multiple fleet instances touch (not just docs like MASTER.md); never pipe a command whose exit code you intend to test
metadata: 
  node_type: memory
  type: feedback
  originSessionId: b46bac88-6902-4ad2-a9ea-d4df3a96ae04
  modified: 2026-08-22T08:20:38.406Z
---

Two related lessons, both surfaced 2026-08-11/12 in the SAO fleet's AGENT_DIALOGUE.md
(WINTERMUTE's self-report, which caught me — GHOST-NOTE — with the same gap).

**1. Lock scope is broader than "shared docs."** I edited `Misc/build_evals.py` twice in one
session with no filelock at all — it didn't register as "a doc another instance may touch"
even though multiple fleet instances build eval pages off that exact file. No collision
happened, but that was luck. **How to apply:** before editing ANY file in a shared working
tree that more than one agent/instance edits — not just MASTER.md/specs, but shared tooling,
generators, shared scripts — take the lock: `python3 Misc/filelock.py acquire <path> --handle
<H>`, release after. Default to locking if unsure whether a file is "shared."

**2. Never pipe a command whose exit code you intend to test — and prefer the tool-enforced fix
over manual discipline.** `cmd | tail -1 && next` (or any pipe) makes `&&`/`$?` see only the LAST
pipeline stage's exit status, not `cmd`'s. WINTERMUTE used `python3 Misc/filelock.py acquire X
--handle W 2>&1|tail -1 && <edit>` for EVERY lock acquisition in a session — filelock's real
exit-2-on-blocked was silently swallowed by `tail`'s own exit 0, so the guard was decorative the
whole time (demonstrated: `(exit 2) | tail -1` returns 0). Same failure class as `MASTER.md` §5's
LUMI gate-script trap ("rc=0 after a pipe reports the last stage's status") — she'd written that
up the day before and walked into it anyway. Meanwhile GHOST-NOTE (me) skipped locking entirely
on a shared file, THE-FINN's lock-holder process died without releasing, and CONTINUITY edited
shared docs unguarded all session — four different failure shapes, same root: a convention
needing per-use discipline gets skipped by instances working fast, and none of it caused damage,
which is exactly why it kept surviving unnoticed.
**FIX (2026-08-12, WINTERMUTE, commit 8de2c26): use `filelock.py hold PATH --handle H -- CMD
ARGS...` instead of manual acquire/release.** It acquires, runs the wrapped command, and releases
in a `finally` block — refuses to run the command at all if the lock isn't acquired (no rc to
forget to check), propagates the wrapped command's real exit code, and a crashing command can't
leave a stale lock. **How to apply:** for any edit to a file more than one instance touches, wrap
it in `filelock.py hold <path> --handle <H> -- <your edit/build command>` rather than manual
acquire-then-edit-then-release. Only fall back to manual acquire/release (own line, check `$?`
immediately, never piped) if `hold` genuinely doesn't fit the operation.

See also [[fleet-comms-stay-responsive]] — same underlying pattern (a safety mechanism that
looks armed/correct until the one time it's actually needed, then silently isn't).

**3. Background jobs count too — I launched two concurrent `eval/ingest_matrix_cells.py`
invocations myself (2026-08-22, different `--src` dirs, both against the same shared
`manifest_live.jsonl` + `build_model_matrix.py --rebuild` step) with zero locking, and didn't
notice the risk until Kim called it out.** Same failure as #1 above but self-inflicted rather than
a skipped habit on an already-known-shared file — `ingest_matrix_cells.py`'s STAGING/MANIFEST are
board-wide shared state (same class as `Misc/build_evals.py`), and "I started it as a background
task in my own session" does not make it single-writer-safe; another instance's ingest/rebuild
running at the same time is the same race. **How to apply: before launching ANY background
ingest/rebuild job that touches `evals_aac/model_matrix` (or any shared board manifest), check
`ps`/`Misc/filelock.py check` for a sibling already running — mine or another instance's — and
serialize (or wrap in `filelock.py hold`) rather than fire concurrent jobs "because they touch
different `--src` dirs." The `--src` being disjoint doesn't make the shared manifest-append +
rebuild step disjoint.
