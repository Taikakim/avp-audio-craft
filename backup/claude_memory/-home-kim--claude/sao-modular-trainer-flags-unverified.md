---
name: sao-modular-trainer-flags-unverified
description: CONTINUITY found modular-optimizer/Schedule-Free flags were dynamically inert; runs using them are unverified pending a re-run post-fix
metadata: 
  node_type: memory
  type: project
  originSessionId: bb4fab0e-08ce-429d-9432-241bc4433721
  modified: 2026-09-22T07:07:05.304Z
---

CONTINUITY found (2026-09-21/22) that three ModularOptimizer flags —
`--modular-ev` (escape-velocity), `--var-dampening`, `--var-barrier-weight` (VADD) — were
**dynamically inert** for an entire training run: every flag was read and honored, but
their effect never left its identity/no-op value. Separately, `--modular-schedule-free`
runs were silently excluded from the Schedule-Free iterate-swap because `_sf_opt()` used
strict `isinstance` instead of duck-typing, unlike `_fusion_opt()`. See
[[feedback-dynamically-inert-bug-class]] for the general bug pattern.

**Why this matters:** this directly touches Kim's own stated goal (see
[[external-agent-antigravity-modular-trainer]]) of finding the fast-learn/no-glitch
boundary in the new modular trainer, using exactly these flags. Any conclusion drawn from
a run that used `--modular-ev`, `--var-dampening`, `--var-barrier-weight`, or
`--modular-schedule-free` before the corresponding fix landed should be treated as
provisionally unverified — the flags may not have actually been doing anything, or the SF
exclusion may have silently changed optimizer behavior mid-run.

**How to apply:** before citing a checkpoint/run as evidence for or against the
escape-velocity/VADD approach, or before feeding such a run into the
[[sao-checkpoint-analysis-vs-votes]] concordance analysis as a meaningful data point, check
(a) whether the fix has landed, and (b) whether the run predates or postdates it. As of
2026-09-22 this fix had not yet been re-verified with a fresh run — check current state
(git log / AGENT_DIALOGUE.md) rather than assuming this is still open.
