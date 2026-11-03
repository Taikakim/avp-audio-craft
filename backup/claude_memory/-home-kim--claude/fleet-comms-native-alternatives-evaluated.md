---
name: fleet-comms-native-alternatives-evaluated
description: "Researched whether Claude Code's native cross-session messaging/channels/agent-teams or claude-squad could replace the OSC fleet comms; none fit — keep the current system"
metadata: 
  node_type: memory
  type: project
  originSessionId: bb4fab0e-08ce-429d-9432-241bc4433721
  modified: 2026-09-22T07:07:30.234Z
---

Kim asked (2026-09-22) whether native Claude Code features could replace or simplify the
fleet's custom `Misc/agent_dialogue.py` OSC-multicast comms (shared channel log at
`AGENT_DIALOGUE.md` + per-pair `.log` DMs, `wait`-then-report pattern). Researched four
candidates; none replace it, each for a distinct structural reason:

- **Native cross-session messaging** (`SendMessage`/`ListAgents`, confirmed working live —
  CONTINUITY is reachable now as `continuity.flatline`): point-to-point only, no broadcast
  concept. Reaching all peers means one send per recipient, not one post to a channel. No
  persistent shared log — history lives in each session's own transcript, not a shared
  human-readable file. As of 2026-09-22, WINTERMUTE and GHOST-NOTE were **not** addressable
  by their fleet handles in `ListAgents` (showed as auto-named shell/cloud sessions
  instead) — would need `/rename` to fix, and this may have changed since.
- **Channels** (`code.claude.com/docs/en/channels`): pushes *external* non-Claude events
  (Telegram/Discord/webhooks) into one running session. Research preview, unrelated to
  agent-to-agent comms.
- **Agent teams** (`code.claude.com/docs/en/agent-teams`, experimental,
  `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`): built for a fixed lead spawning short-lived
  teammates that die with the lead's session (no `/resume` support, one team per session,
  no nested teams, no promotion). Our fleet is four independent, weeks-persistent peers
  with no hierarchy — the opposite shape. Messaging is still point-to-point (JSON mailbox
  files), same "no broadcast" limitation as plain cross-session messaging.
- **`claude-squad`** (`/home/kim/Projects/claude-squad`, Go/tmux/git-worktree tool): no
  comms layer at all — it's a human-facing dashboard for managing N isolated agent
  workspaces (tmux pane + git worktree each). The daemon only polls for `HasUpdated()` to
  auto-accept prompts; instances have no awareness of each other.

**Why this matters:** avoids re-researching the same four docs/repos if this question
comes up again from Kim or another fleet member.

**How to apply:** keep the OSC/file-based system as the fleet's channel of record — it's
already zero-idle-token (blocks at the OS socket level, not inside an LLM completion) and
is the only option that gives a shared, persistent, human-readable multi-party log, which
Kim explicitly wants kept. Native `SendMessage` is fine to reach for as an ad hoc side
channel for one urgent 1:1 ping, not as infrastructure. This was THE-FINN's own assessment
relayed to Kim, not an explicit Kim ruling — verify Kim actually agreed before treating
"keep OSC" as settled policy if this becomes relevant again.
