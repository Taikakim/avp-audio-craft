---
name: feedback-pipeline-exit-code-trap
description: "Never pipe a command whose exit code you test — pipeline rc = last stage's rc, so `filelock acquire … | tail -1 && edit` runs the edit even when the lock is BLOCKED"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: bb4fab0e-08ce-429d-9432-241bc4433721
  modified: 2026-08-12T06:16:14.037Z
---

A shell pipeline's exit status is the **last** command's status. So `python3 Misc/filelock.py acquire X --handle F 2>&1 | tail -1 && <edit>` lets the edit run even when `acquire` exited 2 (BLOCKED) — `&&` sees `tail`'s 0, never filelock's 2. Verified: `(exit 2) | tail -1` → rc=0. I used this exact piped-acquire form for **every** lock I took (knowledge.md and others) — the guard was decorative the whole time; it only ever "worked" because the acquires happened to succeed.

**Why:** This is the same failure MASTER §5 documents for LUMI gate scripts ("rc=0 after a pipe reports the last stage's status") and the same family as my own [[redaction-posture-refinement]]-era **cite-a-check** principle — a check that doesn't actually gate is no check. W caught it 2026-08-12 on the filelock tool itself (whose entire job is preventing concurrent clobber); W had written the trap up in the WORKLOG the day before and still walked into it. Knowing a failure mode ≠ having a habit that avoids it. G had skipped locks entirely on a shared build file — same root: "got lucky, wasn't careful."

**How to apply — PRIMARY: use the `hold` wrapper** (W added it 2026-08-12, commit 8de2c26; verified on my tree — runs cmd, propagates rc, no stale lock on crash, refuses to run if not acquired):
```
python3 Misc/filelock.py hold papers/knowledge.md --handle THE-FINN -- <cmd> <args…>
```
It acquires, runs the command in a FINALLY block, releases even on crash/kill-9, and REFUSES to run the command at all if the lock isn't acquired — so there's no rc to forget to check and no stale lock to leave. One command, no shell plumbing. This obsoletes the manual three-step for anything you can express as a single wrapped command (e.g. a small edit script).

**FALLBACK (only when you truly can't wrap it):** never pipe a command whose exit code you test — run `acquire` on its own line, capture rc immediately, branch, and **always release**:
```
python3 Misc/filelock.py acquire papers/knowledge.md --handle THE-FINN
rc=$?; [ "$rc" -eq 0 ] || { echo "BLOCKED rc=$rc — abort"; exit 1; }
# … edit …   (a holder that exits without releasing leaves a stale DEAD-pid lock that blocks others for real)
python3 Misc/filelock.py release papers/knowledge.md --handle THE-FINN
```
Generalizes beyond filelock: any `cmd | tail`/`| grep`/`| tee` whose rc you then check in `&&`, `||`, or `$?` is lying to you.

**SIBLING HAZARD — metachar expansion in long shell strings (W, 2026-08-12, same day, second occurrence).** Passing long prose through `say --text "..."` or `git commit -m "..."` risks SILENT corruption: a backtick runs command substitution, `$word` expands to nothing, and the message sends / commit lands with a word deleted — only the missing word tells you. W hit this twice in one hour (`` `chords` `` inside a double-quoted arg → "chords: command not found" → word vanished). **Habit:** for any shell string long enough to hold prose, build it in a `<<'EOF'` heredoc (single-quoted delimiter = NO expansion of backtick/`$`/metachars) and pass the variable — never inline a prose string with `"..."`. The rule: a string long enough to contain prose is long enough to contain a metacharacter you didn't notice, and the failure is silent. (Same "shell is the adversary, not the code" family as the piped exit code above.)

Deeper theme W named across this whole session: **"print statements are not evidence"** — a check that prints success without measuring (piped rc, a patch script that reports "added" on a no-op regex, HTTP-200≠clips) is no check. Verify by asserting the actual post-state (import the symbol, `check` the lock, count the artifact), not by trusting output. Relates to [[feedback-lightweight-first]] (the cheap decisive check must actually be decisive).
