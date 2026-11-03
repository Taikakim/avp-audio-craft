---
name: attribute-branches-milestone
description: "Next SA3-control milestone after the LR/optimizer bracket — explicit time-varying MIR-feature control (the actual novel contribution), not more riffer tuning."
metadata: 
  node_type: memory
  type: project
  originSessionId: 59a68846-fc80-40ca-8060-59dc171ea761
---

**VALIDATED 2026-06-20** on the first feature: an explicit **onset-density** scalar head
(`ScalarAttributeEncoder`, FiLM-modulated tokens, `--control-mode scalar`) **steers output onset
density at corr +0.90** (gain 1, the trained operating point): requested sparse→dense maps
measured 4.3→8.3 onsets/sec; gain 0 = flat 7.2 (control off). Overdriving (gain 2/4) breaks into
incoherence. This is the proof the riffer never gave — explicit conditioning works where the opaque
reference (MERIT ≈ 0, pure noise) failed → the riffer's failure was the **opaque signal**, plumbing
was always sound. Heads: `Lehto/sa3_control_runs/onset_density_400trk_crop1024/`. Eval:
`avp_sa3/sa3_control/onset_eval.py`. Caveats: compressed range (shifts ±2 around prompt's natural
density, not exact targets), gain≈1 only, 5 points/1 seed.

The **next milestone after the 200-track LR/optimizer bracket** is the **attribute branches**:
explicit, time-varying feature control of SA3 — condition generation on **rhythm/melody/dynamics
curves** from the mir `.TIMESERIES.npz`. Decided 2026-06-19.

Full design (agent-executable): `SAO/stable-audio-tools/avp_sa3/sa3_control/ATTRIBUTE_BRANCHES.md`.

**Why:** the riffer (audio-reference) is the proven MVP / "style mode", but conditioning on an
opaque reference latent is a weak signal (it mode-collapsed; only worked gain-conditioned at
lr1e-4). The recent LR/optimizer bracketing is *generic recipe-finding* (underfit territory), not
invention. The differentiator is **explicit MIR-feature control** — it leverages the unique
97-feature/per-frame mir pipeline that nobody else has, and explicit features are a *stronger,
measurable* signal than the opaque reference.

**How to apply:** after the bracket lands a non-collapsing recipe (best LR/opt, likely
`--timestep-sampler log_snr` + short crop), (1) probe SA3 DiT `modular_local_cond` support, (2) add
a time-aligned `AttributeEncoder` (no pooling, position-encoded) reusing the validated decoupled
cross-attn adapter, (3) `controls=("dynamics","rhythm","melody")` in train.py. **Eval is
measurable** (decode→re-extract feature→correlate with the input curve — the control IS the
target). Align with `mir/plots/explorer_sa3` (same data; its Player/LatCH `/steer` = the eval
harness + the training-free twin; chroma is steerable today → start there). See
[[sa3-riffer-findings]] for the metric lessons (cross-ref-diff, not chroma).
