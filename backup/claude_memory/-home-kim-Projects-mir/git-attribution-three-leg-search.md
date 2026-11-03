---
name: git-attribution-three-leg-search
description: How to find who authored an uncommitted change in the shared multi-agent tree — search symbols, not filenames
metadata:
  type: reference
---

Attributing orphaned uncommitted work in the shared repos (mir / SAO / stable-audio-3 /
stable-audio-tools) — the fleet all edit one checkout, so files outlive their author's
session. Three search legs, weakest to strongest:

1. **File basename in logs** — WEAK. Blind to anything discussed by any other name.
   Returns garbage if run as a global mention count (whoever talks most wins).
2. **Spec citations inside the diff** — BETTER. Grep the diff's added lines for spec
   names, paper ids, `docs/` paths; then read that spec's `Owner:` header. Specced work
   is discussed by SPEC name ("E2", "reality-structured"), never by filename.
3. **Symbols the diff INTRODUCES** — BEST. Grep the logs for new env vars, class names,
   constants (e.g. `SA3_ENABLE_CROSS_ATTN_MASK`, `AdapterShapeError`). **Prefer
   `WORKLOG.md` hits: WORKLOG entries carry an explicit `(handle)` author tag; dialogue
   entries do not.** A new symbol is coined once, by its author, and survives in whatever
   they wrote about the work.

**Confounds, both observed live:**
- **Policy origin is not code authorship.** A guard implementing a constraint someone
  else relayed will point at the constraint's author. Cost three rounds on
  `sa3_encode_from_manifest.py`.
- **A date in a code comment is not an authorship date.** Reading one and inferring an
  author misassigned `model.py`.
- **Intra-hunk mixing:** two authors inside ONE hunk. `git add -p` (unavailable anyway —
  interactive git flags are blocked here) and hunk-splitting both fail. Method that
  works: `git show HEAD:file` > base, apply the single edit, `git hash-object -w`,
  `git update-index --cacheinfo`; verify the staged blob compiles and greps clean of the
  other author's symbols. The tell: your lines reference a symbol the other author introduces.

**The prior that matters:** an empty search is evidence the instrument cannot see the
link, NOT evidence the work is unowned. Six files were nearly escalated as orphaned
"pre-handle" work on 2026-09-01; all six had owners.

Related: [[feedback-sparse-agent-output]]
