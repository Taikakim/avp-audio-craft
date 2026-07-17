# Theory review — Gemini report + W's assessment (CONTINUITY, 2026-07-15)

*Answers to the four open questions in `gemini-report-assessment-2026-07-15.md` §Open-questions,
plus the lens-B check W asked for on the synopsis. Companion docs:
`research-synopsis-longform-continuation.md` (W), `research-brief-longform-continuation.md` (F).*

## Q1 — AID on rectified flow: adapt or derive?

**Derivation needed, but of a standard kind — and there is a cleaner route than porting AID's
proof.** The structural issue: AID's Gaussian-relaxation → deterministic-guidance bridge is
built on a *stochastic* (EDM/score-SDE) backbone, where tilted posteriors come for free via the
Feynman–Kac / Doob h-transform machinery — that machinery needs a driving noise. A rectified-flow
sampler is a deterministic transport: the terminal law is a pushforward of the initial noise, so
"tilting the posterior" has no path-space meaning until you re-introduce stochasticity.

Two ports, in order of preference:

1. **Stochastic-interpolant bridge (recommended).** Any CFM/RF model admits a family of SDE
   samplers with identical marginals — the score is affinely recoverable from the velocity for
   our linear interpolant, so we can run SA3 as an SDE with any diffusion coefficient ε ≥ 0.
   Apply AID's construction on the ε > 0 sampler (fully licensed), then take ε → 0 for
   deployment. **The one thing to check in the full paper: whether the Gaussian-relaxation
   variance is coupled to the backbone's diffusion coefficient.** If it is, the ε → 0 limit
   degenerates and we simply *keep* a small ε during guided sampling (same marginals, no loss).
   If the relaxation noise lives in the *policy* (control side) — which is the standard
   control-theory reading of the trick — the proof is backbone-agnostic and ports as-is.
2. **Don't port AID's math at all — amortize FK-Flow instead.** FK-Flow already derives
   energy-tilted sampling *natively for CFM* (our exact class). S2 can be formulated as
   "amortize FK-Flow's twisted targets into a <1% critic head": the RF-compatibility then comes
   from FK-Flow, and AID contributes only what we actually want from it — the engineering
   pattern (frozen backbone, tiny actor-critic module, offline training, optimizer-preserving
   deployment). This sidesteps the EDM-specific proof entirely.

F's finding (AID is image-inpainting under EDM, no FM/RF anywhere in it) supports route 2:
treat AID as the *architecture template*, FK-Flow as the *math*.

## Q2 — FK-Flow's stochasticity vs our sampler stack: practical interactions

Composable, with four practical rules:

- **Keep the go/no-go clean:** FK weighting is gradient-free (potentials only enter resampling
  weights). For the first test, run the recurrence potential ONLY through FK weights, with
  latch_guided's gradient guides OFF — otherwise the tilt attribution is confounded.
- **APG/CFG compose orthogonally:** they edit the velocity field; FK edits the *measure over
  particles*. Compute the potential on the post-APG intermediate state; no interaction beyond
  that ordering.
- **Resample only inside the structure window.** At high σ the potential is noise-dominated and
  resampling burns particle diversity for nothing. Restrict resampling to roughly σ ∈ [0.2, 0.7]
  — the same interval logic we already use for adapter gating. (TRI-TSMC's trust-region trick,
  per F = 2605.25123, is the fallback if weight degeneracy still bites in 256×T dims.)
- **Memory/fp16:** K particles = K full latents + K forwards/step (sequential is fine on a
  64 GB GCD; K 4–8 realistic at T=4096). The small Brownian injection is far below CFG-scale
  perturbations — no fp16/CK-flash-attn concern.

## Q3 — Correlation dimension: add it (it is nearly free and covers our blind spot)

Not redundant. The whitened-patch recurrence meter detects **content repetition** (patch A
recurs); correlation dimension measures **dynamical degeneracy** of the latent trajectory —
a limit cycle reads ~1, quasi-periodic wandering ~2, a real arrangement higher. It fires in
exactly the cases recurrence misses: timbral variation riding a one-dimensional loop skeleton,
or slow drift that never literally repeats a patch. And it is computationally parasitic on what
we already build: Grassberger–Procaccia is a slope fit of log C(r) vs log r **on the same
pairwise-distance matrix the recurrence meter computes.** Estimator hygiene: whole-trajectory
estimates (T=4096 is plenty), PCA-whitened space (match the recurrence meter), block bootstrap
for a CI, and report the scaling-region fit range alongside the number.

## Q4 — Operator-theoretic long shot: KoopmanFlow branch yes, Spectral Mean Flows shelf

**KoopmanFlow-style split is the right LUMI bet, and it is frozen-SA3-compatible.** Learn the
Koopman/SSM operator on SA3's *own* latent trajectories as an auxiliary **arrangement-skeleton
model** (low-freq macro-structure, NFE=1), and let frozen SA3 supply texture via the windowed
a2a/SDEdit path *conditioned on the evolved skeleton*. This attacks the root: in our current
longform, the anchor for each window is the previous window — the drift carrier. A skeleton
model replaces the anchor with exogenous low-frequency drive. No DiT retrain required; the
skeleton model is LatCH-scale-to-small and trains on latents we already have.

**Spectral Mean Flows** buys its "structural immunity to feedback" by being holistic and
non-autoregressive — i.e., a from-scratch long-sequence generative model that cannot reuse
frozen SA3 and gives up the continuation/a2a mode Kim actually uses. Paper-shelf, not a bet.

**The unifying read** (worth stating because it organizes every lever we have): the loop
attractor is what the RF prior does when *starved of exogenous low-frequency drive*. Every
intervention that has worked or shows promise supplies that drive — prompt-arc (hand-authored),
the Essentia arousal/valence curves (auto-derived, sweep #51), DriftMonitor-driven breathing
(feedback), FK/AID novelty tilt (statistical), Koopman skeleton (learned generative). The
solution families are one family.

## Lens-B check (synopsis §0, the p\* ∝ p_θ·exp(−λ D(R(z), R_data)) tilt)

The framing is sound (exponential tilt / maximum-entropy projection toward a statistic), with
one correction worth making before anyone tunes λ: **D should match the corpus recurrence
*distribution*, not a point value.** Penalizing deviation from a single target R_data turns the
tilt into a moment constraint whose optimum can sit at pathological extremes — push λ up and
the sampler buys novelty with incoherence (over-novelty is just the other wall). Use a
distributional/band form (e.g., quantile band of the corpus recurrence statistic, or
D = distance between the *distribution* of window-recurrences and the corpus distribution).
Same fix applies to the reward when S2 amortizes it.

## Verdict on W's reframed near-term path

Endorsed as-is, one theoretical footnote: step 1 (recurrence potential in `latch_guided`) is
the *gradient/TFG approximation* of the tilt; FK-SMC (step "S1 proper") is the *consistent
sampler* for the same p\*. Run the gradient version first — if it moves the meters, FK-SMC is
the correctness upgrade, and AID/S2 the amortization. If the gradient version does nothing,
check with a small FK-SMC run before declaring the tilt dead: gradient guidance can fail on a
potential whose gradients are uninformative (patch-similarity statistics plausibly are) while
the weighting form still works.
