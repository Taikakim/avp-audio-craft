---
name: feedback-nan-permissive-guards
description: "Bare `x > threshold` comparisons are False for NaN in Python, so watchdogs built on them actively certify divergence as healthy"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: bb4fab0e-08ce-429d-9432-241bc4433721
  modified: 2026-09-22T07:07:36.664Z
---

A bare comparison like `x > threshold` evaluates to `False` when `x` is `NaN` in Python.
A watchdog/guard written as `if loss > threshold: flag_unhealthy()` therefore reports
"healthy" on divergence, not just silently — it *actively certifies* health while the run
is broken. Found by CONTINUITY during the 2026-09-21/22 audit (a NaN-permissive loss
guard), fixed via DM to GHOST-NOTE.

**Why this matters:** this is worse than a silent or dead meter, which at least gives no
signal — a NaN-permissive guard gives a false positive signal of correctness. Related
family to [[feedback-dynamically-inert-bug-class]] (both are "it ran, it looked fine,
nothing said otherwise" bugs), but the mechanism is specifically NaN's comparison
semantics rather than an effect being too small to matter.

**How to apply:** when reviewing any watchdog/guard/health-check built on a numeric
comparison, check what it does when the input is NaN — either add an explicit
`math.isnan()`/`torch.isnan()` check, or use a comparison form that's NaN-safe by
construction (e.g. `not (x <= threshold)` still misfires the same way; explicit NaN
checks are the only real fix).
