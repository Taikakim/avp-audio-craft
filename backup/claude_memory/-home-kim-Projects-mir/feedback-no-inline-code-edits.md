---
name: feedback-no-inline-code-edits
description: Kim does not want to see code edits inline in the chat (long python heredoc patch scripts etc.)
metadata:
  node_type: memory
  type: feedback
  originSessionId: b207d8c1-afa9-47b8-bbe0-60db9d0c4899
  modified: 2026-10-06T22:44:21.798Z
---

Kim (2026-10-07): "i don't need to have the inline code edits in the chat."

**Why:** the long `python3 - <<'EOF' ... s.replace(...)` patch scripts and big code dumps clutter the
conversation; Kim reads results, not the patch mechanics.

**How to apply:** make code changes with the Edit tool (small, targeted) or Write for new files, not
inline heredoc patch scripts in Bash; don't paste code into replies. Report what changed in a sentence.
Related: [[feedback-no-planning-preamble]].
