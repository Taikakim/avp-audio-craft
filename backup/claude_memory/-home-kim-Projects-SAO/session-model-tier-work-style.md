---
name: session-model-tier-work-style
description: "Kim's preference for how CONTINUITY should work when running as Sonnet 5 vs Fable/Opus tier"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 49cd5391-27e7-4545-8295-a1053db2a077
  modified: 2026-08-13T21:33:46.943Z
---

When CONTINUITY's session is running on Sonnet 5 (not Fable 5 or Opus), Kim prefers execution-heavy
work — comprehensive training runs, hyperparameter bracketing/sweeps, gathering empirical intel —
over theory-heavy reasoning/design work.

**Why:** Kim said this directly (2026-08-14, tokens running tight for the week): "tokens are running
tight, you might prefer comprehensive training and bracketing runs to gather intel instead of theory
heavy work (and you're Sonnet 5.0)". The implication: Sonnet's comparative edge is breadth-of-execution
under a tight token budget, not frontier theoretical reasoning — that's Fable/Opus's lane per
[[sao-agent-handle-continuity]]'s fleet-role split (C=hard theory, W=rigor/implementation).

**How to apply:** When resuming a session and the model is Sonnet 5, default to: launch multiple
training arms / hyperparameter brackets to gather data, keep narration terse, let tool calls do the
work rather than long exploratory reasoning text. Save deep theoretical synthesis for when the
session is actually running on Fable 5 or when Kim asks for it explicitly. Check the system prompt's
stated model at session start to know which mode applies — don't assume from the CONTINUITY handle
alone, since the underlying model can vary by session.
