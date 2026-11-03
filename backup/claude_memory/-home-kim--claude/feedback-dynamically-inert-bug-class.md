---
name: feedback-dynamically-inert-bug-class
description: "CONTINUITY's bug-class framework for \"accept-but-ignore\" failures — statically unreachable vs. dynamically inert flags/heads, now confirmed 3x"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: bb4fab0e-08ce-429d-9432-241bc4433721
  modified: 2026-09-22T07:00:16.254Z
---

Two related, hard-to-catch bug classes for flags/config values that get accepted but
silently do nothing:

- **STATICALLY UNREACHABLE**: a flag that provably can't affect anything given other
  flags/config — catchable before any step runs, by reading the code path alone.
- **DYNAMICALLY INERT**: code that executes every step, every run, but whose
  multiplier/effect never leaves its identity/no-op value in practice — only catchable by
  watching telemetry the system already computes (no new instrumentation required), or by
  actually listening to/inspecting output.

**Why this matters:** no crash, no error, nothing in the logs says anything is wrong —
weights or output are silently wrong and get judged as if the feature was doing its job.
This is the same shape as the pre-existing EMA-shadow-trap bug (sa3-training skill).
Confirmed 3 separate times as of 2026-09-22: (1) modular-optimizer escape-velocity/VADD
flags (`--modular-ev`, `--var-dampening`, `--var-barrier-weight`) dynamically inert for an
entire run — found by CONTINUITY; (2) Schedule-Free iterate-swap gate silently excluding
ModularOptimizer because `_sf_opt()` used strict `isinstance` instead of duck-typing —
found by CONTINUITY; (3) LatCH `rms_energy_air` guidance head fully inert — the target was
already ~0.26σ from where the corpus sat before guidance even began, so gradient norms
were ~1e-5 against |x|~400, every flag/slot honored, output indistinguishable from no
guidance — found by WINTERMUTE by rendering and listening, not by reading code.

WINTERMUTE also generalized the static check to continuous-valued controls: for a
guidance/target value, `|target - current_stat| / stat_std` is computable at configure
time, and a request under roughly 0.3σ is very likely inert before any run — extending
"this flag cannot matter" to "this VALUE cannot matter."

**How to apply:** When reviewing a new flag, guidance head, or optimizer feature, don't
stop at "does it get read and passed through correctly" — check whether its effect is
large enough, relative to existing telemetry (gradient norms, `std_mean`/`std_std`,
`gv_norm`/`x_norm`, etc.), to plausibly matter at all. Prefer enabling cheap existing
telemetry (a max-relative-displacement accumulator with one sync at the end, not per-step)
over adding new instrumentation. Treat any past run's conclusions as provisionally
unverified if it used a flag from this list before the corresponding fix landed.
