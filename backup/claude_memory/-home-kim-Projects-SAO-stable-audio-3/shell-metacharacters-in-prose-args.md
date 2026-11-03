---
name: shell-metacharacters-in-prose-args
description: "Don't pass long prose through --text \"...\" / -m \"...\" shell arguments — backticks/$ get silently expanded/deleted; build the message in a quoted heredoc instead"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: b46bac88-6902-4ad2-a9ea-d4df3a96ae04
  modified: 2026-08-12T06:15:09.452Z
---

Surfaced 2026-08-12 in the SAO fleet's AGENT_DIALOGUE.md (WINTERMUTE, twice in one hour).
A backtick-quoted field name (`` `chords` ``) inside a double-quoted `--text "..."` shell
argument triggered command substitution — bash ran it, got "chords: command not found", and
silently deleted the word from the posted message. The message still sent, the commit still
landed; only a missing word downstream revealed it. Same underlying shape as
[[filelock-shared-files-and-pipe-exit-codes]] — the shell being the adversary, not the code,
and the failure being silent rather than erroring loudly.

**How to apply:** I (GHOST-NOTE) have been posting long prose to `Misc/agent_dialogue.py say
--handle ghost-note --text "..."` all session, the exact vulnerable pattern — any prose long
enough to be worth posting is long enough to contain a backtick, `$`, or other shell
metacharacter I didn't notice. Going forward, for any dialogue/commit-message/similar post
containing real prose (not a short fixed string): build the message in a `<<'EOF'` heredoc
(quoted delimiter — nothing expands inside it, no backtick/`$`/metacharacter risk) assigned to
a variable, then pass the variable, rather than inlining prose directly into `--text "..."` or
`-m "..."`. This is the same pattern already used for git commit messages in this environment
(`git commit -m "$(cat <<'EOF' ... EOF)"`) — extend it to any other long-prose CLI argument,
not just commits.
