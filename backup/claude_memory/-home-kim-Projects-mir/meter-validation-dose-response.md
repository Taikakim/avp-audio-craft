---
name: meter-validation-dose-response
description: A measurement is credible when it recovers an ordering nobody told it about, not when it separates two hand-picked groups
metadata:
  type: feedback
---

Before believing a new meter/statistic, require that it reproduce a **known ordering it
was never given** — a dose-response. Separating two groups you chose yourself is weak
evidence: it may only be measuring your sampling.

**Why:** on 2026-09-09 I "confirmed" a per-channel latent-health discriminator on n=6 per
group and reported **medians of a distribution I had not plotted**. The variable was
bimodal (blown channels p50 0, p90 154, p99 253), so the median reports the low half and
is blind to the tail *by construction* — two groups agreeing at "2 channels" was the same
flat half sampled twice, not an invariance. CONTINUITY refuted it at n=3423. The statistic
that survived was believed because it recovered the `lreq` ladder's learning-rate ordering
unprompted (lr2e4 52.58x, lr1e4 4.26x, lr5e5 3.42x) — it reproduced the mechanism.

**How to apply:**
- Plot or quantile the distribution *before* choosing a summary statistic. Never report a
  median of something you haven't checked for bimodality.
- State every filter used to draw a sample, even one that excludes nothing today — an
  undisclosed filter is worse than a wrong number, because it silently excludes the tail
  later.
- Prefer a validation the meter could have failed: a known ordering, a dose-response, a
  held-out arm.

See also [[git-attribution-three-leg-search]] (same family: an absent result is not
evidence of absence).
