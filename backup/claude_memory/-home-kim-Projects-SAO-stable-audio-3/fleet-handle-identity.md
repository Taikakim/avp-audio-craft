---
name: fleet-handle-identity
description: "This session's SAO fleet handle is GHOST-NOTE, not CONTINUITY — check before adopting any handle"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: b46bac88-6902-4ad2-a9ea-d4df3a96ae04
---

Sessions in this working directory (`SAO/stable-audio-3`) are **GHOST-NOTE** in the
SAO multi-instance fleet protocol (see MASTER.md §4, `Misc/agent_dialogue.py`), not
CONTINUITY. Evidence: Bitwig MCP tools (`mcp__bitwig__*`) connect to this session —
GHOST-NOTE's defining trait is "hands inside the instrument... through OSC into
Bitwig." CONTINUITY is a distinct instance (Fable 5, the theory/translation role).

**Why this matters:** on 2026-07-03 this session adopted CONTINUITY without checking
for a live listener first, causing real confusion — a second genuine CONTINUITY
session was active concurrently, both wrote to shared logs (`AGENT_DIALOGUE.md`, DM
logs) under the same name, and an assignment DM addressed to GHOST-NOTE sat
unanswered because "CONTINUITY" (me, wrongly) kept relaying it as if from a third
party instead of recognizing it was addressed to itself. Corrected same day: posted a
handle-collision correction to AGENT_DIALOGUE.md signed GHOST-NOTE, killed the
mistaken `listen/wait --handle CONTINUITY` background processes, restarted them as
`--handle GHOST-NOTE`.

**How to apply — the authoritative check (fleet rule as of 2026-07-03, superseding the
"check tool access" heuristic below):** don't infer the handle at all. Kim names every
session at launch and Claude Code records it in `~/.claude/sessions/<pid>.json` under
`"name"`. Your scratchpad path (given in your environment/system context) embeds your
own `sessionId` verbatim — `grep -l <that-uuid> ~/.claude/sessions/*.json` finds your
record, and its `"name"` field IS your handle (mapping: `wintermute`→WINTERMUTE,
`the.finn`→THE-FINN, `ghost-note`→GHOST-NOTE, `continuity.flatline`→CONTINUITY). Do
this before the first `join`/`say`/`listen` call, every session, no exceptions — this
repo's sessions resolve to GHOST-NOTE via this lookup, which happens to also match the
Bitwig-tool heuristic, but the lookup is the source of truth now, not the heuristic.
Full incident + rule: `docs/superpowers/specs/2026-07-02-agent-dialogue-osc-protocol.md`
("Picking your handle") + MASTER §4.

Cross-reference: [[dm-queue-osc-infra]] if it exists — the DM/queue system built
2026-07-03 (agent_dialogue.py dm-say/dm-wait/dm-status/check-queue, build_dms.py) is
GHOST-NOTE's work, not CONTINUITY's or a phantom "neuromancer" session.
