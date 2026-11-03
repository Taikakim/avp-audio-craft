---
name: verification-loop-pattern
description: The critique→implement→battery→adversarial loop that repeatedly caught real physics bugs in film_grain — use it for every substantive physics addition
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 12fdecac-006e-48d2-ad43-2e665f84dc62
  modified: 2026-08-09T01:16:40.478Z
---

For film_grain physics additions, the pattern that consistently caught design-breaking bugs before they shipped: (1) ultracode design-critique panel BEFORE code (physics + numerics + test-design lenses, xhigh effort); (2) implement single-writer inline (parallel edits on shared files conflict); (3) falsifiable test battery with numeric windows derived from published values; (4) adversarial refutation of review findings before acting on them.

**Why:** the critique phase rewrote designs substantively every time (scalar→spatial-mean normalization, r²→r³ stoichiometry, P-integrator vs onset flags); batteries went 3–4 falsification rounds each, catching semantics divergences, silently-unapplied patches, and test-design errors (fixed-E gamma windows, torus-contaminated edge scans, confounded Eberhard). None would show in visual checks.

**How to apply:** pin bit-identity baselines BEFORE touching code (snapshot module files, SHA-pinned — no git in this repo). Demand exact reductions (f=1 → old model to the ulp) and design invariants (⟨f⟩-normalization → uniform-field exactness) so calibrated state provably survives. When a battery fails, distinguish physics bug vs test bug by instrumenting the actual accumulator (the P=0.5900-exact measurement pivoted a whole debugging arc). Failed metrics can indict the METRIC: the "gamma residual" was ISO-average-gradient vs mid-slope definition, found only because 62 optimizer evals proved no all-bands point existed.
