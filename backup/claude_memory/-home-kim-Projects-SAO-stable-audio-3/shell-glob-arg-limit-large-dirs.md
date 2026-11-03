---
name: shell-glob-arg-limit-large-dirs
description: Never use a bare shell glob (ls/rm DIR/*.ext) on a directory with tens of thousands of files — use find instead
metadata: 
  node_type: memory
  type: feedback
  originSessionId: b46bac88-6902-4ad2-a9ea-d4df3a96ae04
  modified: 2026-08-17T06:14:15.070Z
---

Never use a bare shell glob (`ls DIR/*.json`, `rm -f DIR/*.json`, etc.) against a directory
holding tens of thousands of files. Bash expands the glob into individual filename arguments
*before* invoking the command; with ~20k+ matches this can exceed the exec argument-length limit
(ARG_MAX). The failure mode is easy to miss: `bash: ls: Argument list too long` goes to stderr,
stdout stays empty, and `| wc -l` on that empty pipe silently reports **0** — reading as "directory
is empty" when it's actually full. `rm -f DIR/*.ext` fails the same way and silently deletes
nothing, while looking like it ran fine.

**Why:** this exact bug caused three wasted goa Granite-revision resubmits in one session
(2026-08-17, LUMI `goa_archive_captions/granite/`, 23,232 files) — a verification check
(`ls .../*.json | wc -l`) falsely reported 0 files present, and the original `rm -f .../*.json`
clear command had *also* silently failed the same way, so every "fixed" resubmit kept finding the
old (buggy) output already present and skipped all real work, undetected for hours.

**How to apply:** for any directory that might hold more than a few thousand files (large
corpora, matrix_cells/eval renders, LUMI scratch dirs), always use `find`-based commands instead,
which walk the directory without shell glob expansion:
- Count: `find DIR -name "*.ext" | wc -l` (never `ls DIR/*.ext | wc -l`)
- Clear: `find DIR -name "*.ext" -delete` (never `rm -f DIR/*.ext`)

A quick sanity check when a large-directory glob-based command looks suspiciously fast or reports
suspiciously round/simple numbers (especially 0): re-verify with `find` before trusting it.
See also [[nested-repo-git-log-scope]] — another case where a plausible-looking-but-wrong check
silently misled the same session.
