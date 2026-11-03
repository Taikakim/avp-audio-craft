---
name: no-amend-shared-tree
description: Never git commit --amend on the SAO tree; four instances commit to one branch and HEAD moves between your commands
metadata:
  type: feedback
---
Never `git commit --amend` on the shared SAO tree: fix a wrong message with a follow-up commit.

**Why:** 2026-11-02, GHOST-NOTE committed between my commit and my amend, so the amend rewrote their commit's message. Restored with `git update-ref HEAD <theirs> <amended>` after checking the trees matched. Full note: `docs/GIT-PROTOCOL.md` end of §6b.

**How to apply:** also check who else is active before starting routine work: `ls -t *.log | head` and the newest DM lines, since Kim may ask several instances at once ([[post-to-chat-on-milestones]]). THE-FINN owns the weekly routine.
