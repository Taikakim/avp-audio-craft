# Triage — "Higher-Order Topology and Spectral Geometry of Learned Model Spaces" (Gemini)

> **Provenance.** Second Gemini run on the model-space-topology brief
> (`briefs/2026-07-31-model-space-topology-brief.md`), received 2026-08-01 (Kim), PDF in
> uploads. Triage: CONTINUITY same day.
> **Citation verification (2026-08-01): 12/13 REAL + substantially accurate** — the
> strongest base of the three runs. Corrections: ARIA (2605.16181) real but the report's
> SVD-mechanism framing is an overlay (paper = reliability diagnostics, not
> "isolates generative factors"); k-fold ensembles (2405.01727) core holds, the broken-
> SO(3) detail is beyond the abstract; "Dimension-Corrected Hitting Times" (ResearchGate)
> UNVERIFIED (no footprint; adjacent real work 2406.04657 exists). Bonus: two items the
> report cited as non-arXiv ARE on arXiv (MTop-Div 2106.04024; MAPCA 2604.14249).

## What it changes for us (actionables, ranked)

1. **E1c design law (MAPCA, 2604.14249, verified):** W-MSE/Barlow-Twins/VICReg are
   implicit metric choices Σ⁻¹/Σ/diagonal — output-whitening pressure forces isotropy,
   which for OUR latent would EXPAND the giant degenerate shells and destroy the
   functionally-necessary 1/f tail. E1c is therefore locked to **capped noise-floor
   compensation only** (w_i ≈ (λ_i+1)/λ_i, clipped) — never spectrum flattening. VICReg-
   style variance-preserving penalties are the safe family if a regularizer is ever added.
2. **HTSR α monitoring (Martin&Mahoney, real):** per-layer heavy-tail exponent of weight
   ESDs as a training-health readout — α≈2 ideal, α≥5 underfit layers, rank-collapse =
   anti-grokking. CHEAP (CPU, weightwatcher-style) → add to the standing
   checkpoint-trajectory-stats practice; priority target = the winning+40ep continuation
   (over-training watch is exactly its risk).
3. **OTAD (2605.05554, verified real+accurate):** learned Riemannian ground metric + OT
   replaces FAD's Euclidean cost; fixes the invariance-set blindness (artifacts orthogonal
   to PCs at near-zero distance) and rank-1 dilution — the PRINCIPLED version of our
   DSP disintegration gate (which catches exactly that artifact class by hand-built
   features). Candidate eval-stack addition; needs the paper read for compute cost.
4. **MTop-Div (2106.04024, NeurIPS'21, real):** non-parametric topological gen-vs-real
   divergence; candidate board metric where FAD/Gaussian assumptions fail. Lower priority
   than OTAD (TDA cost, subsample sensitivity — the report's own Q5 honesty applies).
5. **Theory shelf:** Wigner Cat Phases (2512.22169, real) — the intermediate
   non-ergodic regime is where our GOE-but-structured spectrum may actually live (r=0.526
   with giant degenerate shells is NOT pure GOE — the shells are exactly "suppressed
   spectral mixing" islands); k-fold ensembles (2405.01727) = the formal frame for
   shells-as-irreps; energy-information optimality (2407.16215 + PNAS, real) upgrades the
   α≈1 story: our −1.12 sits at the measured biological/theoretical optimum.

## Assessment
Less costume than the physics PDF, more depth than run 1. The report's conclusion
("representation at the threshold of theoretical limits") is flattering — treat as
hypothesis; the α≈1.12 + GOE + shells triple is now, per two Gemini sweeps plus our own
verification, apparently unmeasured territory in the literature. Novelty claims stay
gated until human-checked, but the experiment set they motivate (E1a running, E1c
hardened, shell-splitting readout designed) is sound regardless of priority questions.
