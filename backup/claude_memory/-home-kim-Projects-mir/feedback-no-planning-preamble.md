---
name: feedback-no-planning-preamble
description: "Don't narrate \"Privately, what I need next:\" planning preambles before tool calls — just make the calls"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: a4a15b31-e36b-4d5b-b659-2a6c3fd9871b
  modified: 2026-09-16T20:23:59.716Z
---

Kim (2026-09-16): "I don't need to see the messages flagged as 'Privately, what I need next:'"

Do not emit the planning/needs-list preamble before tool calls. Make the calls and
report the outcome.

**Why:** the preamble restates intent the tool calls and their results already carry,
so it is pure duplication in his terminal view — and it recurs on *every* turn, so the
cost compounds across a session. Same family as [[feedback_osc_monitor_silent_rearm]]
(don't narrate a status line when there is nothing to say) and
[[feedback-sparse-agent-output]] (one status line, never prose).

**How to apply:** batch independent tool calls as always — that part is unchanged and
still wanted — but issue them without the preceding inventory. Reasoning that changes
what he'd *do* still belongs in the response: a diagnosis, a refuted hypothesis, a
decision that needs his call, a flagged risk. The thing to cut is the bookkeeping list
of what I'm about to fetch, not the substance of what I found.
