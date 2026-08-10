# arXiv 2608.03721 — On the Geometry of Music Bandwidth Extension in Latent Spaces of Audio Codecs

Koops, Tan, Quinton (reads like UMG ML). **Indexed + TESTED by CONTINUITY 2026-08-08 (Kim ask).**

## Claim
For music **bandwidth extension** (HF restoration), a **single transport vector** — the difference
between clean and degraded latent **centroids** on a reference set, added to degraded latents and
decoded — rivals large conditional generative models (diffusion / Flow-Matching / Schrödinger bridge),
**on codecs whose latent space is "bandwidth-aligned."** Deterministic, ~0 learnable params, frozen
codec. Proposed as **the baseline** the field should measure learnable restorers against.

## Our-POV assessment — RELEVANT (HF/clarity-recovery: #62/#64/#65/#66) but NEGATIVE for SAME
Tested the transport-vector baseline directly in the SAME latent (GPU-free, existing
`mp3_latent_sensitivity` latents = FLAC vs mp3@{320,256,192,128}→SAME; probe:
`eval/transport_vector_probe.py`, out `eval/musicology/transport_vector_probe_2026-08-08/`):
- Held-out recovery is **negative and ≈ random** (−3.2 @320k … −0.8 @128k); the **per-track ORACLE
  constant vector recovers ~0%.** ⇒ **SAME is NOT bandwidth-aligned** — its HF loss is not a fixed
  latent direction (frame/content-dependent), so arithmetic latent transport cannot restore it.
- Consistent with our prior SAME findings: >7 kHz phase-coh ≈ 0 (info gone at encode), diffuse/
  near-full-rank HF/melody directions (interval-ladder, whitening probes).

## So what
- **Adopt as the mandatory baseline** for any learnable HF restorer (clarity-recovery plan) — but it
  **fails on SAME**, which is positive evidence that **generative restoration (#62) is justified, not
  overkill** (the cheap option is off the table for our codec).
- Decomposition it implies: a transport vector plausibly restores HF **magnitude/bandwidth** on aligned
  codecs; SAME isn't aligned even for magnitude here, matching our "magnitude restorable in principle,
  phase isn't" only on *aligned* codecs — SAME is neither via arithmetic.
- **Confirmatory step (GPU, when box free):** the SAME-OWN transport vector (original vs SAME-roundtrip,
  both re-encoded) + decode-verify env_corr. Proxy result already points clearly.

Ref: `eval/transport_vector_probe.py` · `docs/clarity-recovery-plan-2026-08-02.md`. (F: fold into
`papers/knowledge.md` as tested-negative.)
