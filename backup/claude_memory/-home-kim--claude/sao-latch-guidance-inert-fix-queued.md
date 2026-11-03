---
name: sao-latch-guidance-inert-fix-queued
description: "WINTERMUTE found LatCH's rms_energy_air guidance head fully inert; ~30-line telemetry fix designed but not yet implemented (2026-09-22)"
metadata: 
  node_type: memory
  type: project
  originSessionId: bb4fab0e-08ce-429d-9432-241bc4433721
  modified: 2026-09-22T07:07:12.503Z
---

WINTERMUTE found (2026-09-22) that LatCH's `rms_energy_air` guidance head — meant to damp
harsh high end on post-trained medium — was completely inert: the target (`std_mean`, a
~0.26σ request) was nearly satisfied before guidance even began, so gradient norms were
~1e-5 against |x|~400. Every flag/slot was honored; output was indistinguishable from no
guidance at all. Found by rendering and listening, not by reading code. Same bug family as
[[feedback-dynamically-inert-bug-class]] — third confirmed instance.

The telemetry to catch this already exists (`latch_guided.py`'s `gv_norm`/`x_norm`
computation, gated behind `log_norms=False` at `model.py:595`) but nobody enables it
because of per-step sync cost. WINTERMUTE designed but had **not yet implemented** (as of
2026-09-22, explicitly deferred rather than editing near CONTINUITY's in-flight work) a
~30-line fix: accumulate `max(‖grad‖/‖x‖)` as a tensor with no per-step sync, take one
`.item()` sync at the very end of sampling, and emit an "guidance was inert" warning by
default when the max never crosses a threshold.

WINTERMUTE also generalized the static-unreachability check to continuous values: for any
guidance/target, `|target - current_stat| / stat_std` is computable at configure time, and
a request under ~0.3σ is very likely inert before any run.

**How to apply:** check whether this fix has landed before relying on LatCH guidance
output from before 2026-09-22, or before assuming `rms_energy_air` guidance is doing
anything in older runs. If picking up loose ends in LatCH, this is a ready-to-implement,
well-specified fix — no need to re-derive the design.
