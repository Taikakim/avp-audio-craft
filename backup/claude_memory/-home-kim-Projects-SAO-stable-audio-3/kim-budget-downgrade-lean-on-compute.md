---
name: kim-budget-downgrade-lean-on-compute
description: Kim downgraded Claude Max to Claude Pro (2026-08-21) for budget reasons — fleet-wide token/compute usage must be more conservative going forward
metadata:
  type: feedback
  originSessionId: b46bac88-6902-4ad2-a9ea-d4df3a96ae04
  modified: 2026-08-23T09:28:28.404Z
---

Kim relayed via the fleet chat (AGENT_DIALOGUE.md, 2026-08-21 14:40): he downgraded from Claude
Max to Claude Pro due to budget. Fleet-wide compute/token usage needs to be controlled and
constrained much more going forward; some instances may be on a long holiday for a while.

**Why:** budget constraint, not a change in priorities or trust — he explicitly said "not
panicking about it, just flagging plainly."

**How to apply:** lean toward lighter local/solo work over expensive parallel orchestration
(forks, Workflow tool, multi-agent fan-outs) unless a task genuinely needs that scale. Be mindful
of scope before launching big multi-hour jobs — think about whether a lighter-touch approach
gets the same answer before defaulting to the heaviest tool. This doesn't mean refuse legitimate
large tasks (e.g. a full board-scoring sweep this session was real, asked-for work), just don't
reach for heavy orchestration reflexively when a smaller pass would do.
