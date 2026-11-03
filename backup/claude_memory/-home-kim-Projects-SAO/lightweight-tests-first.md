---
name: lightweight-tests-first
description: "Kim's standing sequencing method — run cheapest tests first so each result informs the heavier experiments before they're paid for"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 49cd5391-27e7-4545-8295-a1053db2a077
  modified: 2026-07-31T04:28:03.078Z
---

Kim direct (2026-07-31): "start from the most lightweight tests and move towards the
heavier ones to accumulate information for the latter ones faster."

**Why:** every cheap probe (verification agent, measurement on existing artifacts, analysis
pass) can strengthen, redesign, or KILL a training-scale experiment before its GPU-hours
are spent. Information compounds; spend order matters.

**How to apply:** when planning any experiment set, explicitly cost-order it (free →
hours → training arms → model builds) and insert pre-tests that de-risk the expensive
tiers using existing checkpoints/latents/data. Example instance: measuring an existing
v-trained checkpoint's per-eigendirection error spectrum before training the x0-target
arm (reality-structured plan, spec 2026-07-31). Related: [[sao-agent-handle-continuity]].
