---
name: feedback-sparse-agent-output
description: Background/subagents must return machine-terse output only — no prose, summaries, or narration
metadata:
  type: feedback
---

Background agents and subagents should return **sparse, non-human-readable output** —
a single status line or minimal structured result. No prose summaries, no bullet
recaps, no file excerpts, no explanation of what they did. This applies to background
agents in general, not just one task type.

**Why:** the agent's report is not shown to the user anyway — it lands in the
dispatcher's context and is re-read on every subsequent turn. Narrative reports are
pure context cost with zero delivery value, and on long multi-agent runs (the public-log
attribution sweep, ~180-200k tokens per agent) that cost compounds against a spend cap.

**How to apply:** put an explicit OUTPUT CONTRACT at the end of every Agent prompt
specifying the exact single-line return format, e.g.
`DONE edits=<N> remaining=<M>`, followed by "No prose, no summary, no explanation.
One line only." Verify the result by inspecting the artifact (git diff, grep counts)
rather than by asking the agent to describe its work.

Related: [[fleet-wait-arming]], [[long-lived-servers-daemonize]]
