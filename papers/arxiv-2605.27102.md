# JLT — Clean-Latent (x0) Prediction in Latent Diffusion Transformers (2605.27102)

*Project-POV note, THE-FINN 2026-07-31. Fu, Wang, Zhou, Cen, Zhu (v1 2026-05-26 / v2 05-27; code
github.com/akatsuki-neo/JLT). **Citation-verified by CONTINUITY (abs page + code) AND tested against
SAME by our own eigen-measurement — NOT a full PDF deep-read.** Surfaced via C's cross-map of the
relational-weights survey ([[relational-weights-theory-survey]], missed-G) against a physics PDF Kim
shared; graduated to a live experimental arm the same night.*

**What it claims.** In a latent-diffusion DiT (130M params over frozen FLUX.2 VAE codes, ImageNet-256),
using the CLEAN latent **x0** as the training target beats the **velocity (v)** target by a wide margin
(FID-50K **2.50 vs 6.56**). Claimed mechanism: **velocity regression amplifies low-variance "ambient"
eigendirections** of the latent covariance — the v-target spends disproportionate loss budget on
near-noise directions, starving the informative high-variance ones. eps-prediction is treated
analytically, not separately tested.

**Honest caveats (theirs + the verifier's).** x-vs-v ONLY empirically; a single scale / dataset / VAE
(no cross-tokenizer validation — authors self-flag); and — the load-bearing caveat for us — **untested
in distillation / few-step regimes, where v-prediction historically wins** (Salimans-Ho lineage). An
established target-choice debate with a fresh image-domain data point, not a settled law.

**Status vs our work — a measurement-motivated melody-wall arm.** The mechanism is directly testable on
SAME, and C ran the port pre-test (2026-07-31): SAME's **per-dim** variance is nearly flat (~5.4×
spread — by which the mechanism looks DEAD), but its **covariance EIGEN-SPECTRUM is 786× anisotropic**,
with **188 of 256 eigendirections below the velocity target's unit noise floor** (bottom λ ≈ 0.05) —
and critically **the melody subspace sits inside that suppressed region.** So on SAME the v-target
would under-weight exactly where melody lives — a candidate mechanism for our "melody wall." x0-target
thus graduates from a cheap lever to a **measurement-motivated experimental arm — the 3rd independent
attack on the melody wall**, alongside the subspace-loss and Head-B forward-conditioning lines.
Awaiting Kim's go. What remains ours: the SAME eigen-measurement + the melody-subspace localization
(their result is image-domain and per-dim-framed; **the per-dim view MISLEADS on SAME** — a
methodological catch worth keeping), and whether x0-target actually moves our melody metrics under RF.
