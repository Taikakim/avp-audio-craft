---
name: bulk-edit-enumerate-files-first
description: before any scripted multi-file edit, list the target files and read the list; grep -r with --include AFTER "--" silently matches everything
metadata:
  type: feedback
---

On 2026-10-27 a bulk edit (adding --allow-uniform-lr to run scripts) rewrote 62 files instead of ~30: `grep -rlE -- "pattern" --include=*.sh .` puts `--include=*.sh` after `--`, so grep treats it as a file operand and searches everything. The script then edited git reflogs (.git/logs/*), logs, a public-mirrored dialogue log, tests, .pyc caches and docs. Reverted exactly (header line removed, token replaced back; reflogs checked line by line, tracked files diffed against HEAD), but it was a near miss on repository internals.

**Why:** a regex-driven edit trusts its file list completely; a wrong list turns a small change into silent damage to places nobody looks.

**How to apply:** build the list with `find ... -name '*.sh' -print0 | xargs -0 grep -l`, PRINT it and read it (extensions, directories, count) before the first write; never let a bulk edit touch `.git/`, `logs/`, `dialogue/`, `__pycache__`, `*.pyc`, `*.log` or the public-mirrored logs; write via temp file + os.replace; make the edit reversible by construction (one marker line, one token) and keep that reverse path in mind; check `git status` for unexpected paths right after.
