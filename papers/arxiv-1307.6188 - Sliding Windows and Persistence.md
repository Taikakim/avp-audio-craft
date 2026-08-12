# Sliding Windows and Persistence: An Application of Topological Methods to Signal Analysis

**arXiv 1307.6188v2** · Jose A. Perea, John Harer (Duke) · 34 pp · read 2026-08-12 (WINTERMUTE)
**Method name: SW1PerS** — Sliding Windows and 1-dimensional Persistence Scoring.

Read from the PDF, not from the abstract. Page cites below are to the v2 PDF.

---

## What it contains

**The construction (p.3).** The sliding-window (time-delay) embedding of a scalar signal `f`:

```
SW_{M,τ} f(t) = [ f(t), f(t+τ), f(t+2τ), …, f(t+Mτ) ]ᵀ  ∈ ℝ^{M+1}
```

Sweeping `t` gives a point cloud. The critical parameter is the **window size `Mτ`** — not `M`
and `τ` separately.

**The central geometric fact (pp.3–4), and it is exact, not asymptotic.** For `f(t) = cos(Lt)`
the embedding is a planar **ellipse**, and its shape is governed by the eigenvalues of an
explicit 2×2 matrix:

```
λ₁,₂ = [ (M+1) ± |sin(L(M+1)τ) / sin(Lτ)| ] / 2
```

The ellipse is **roundest when λ₂ is maximal**, which happens iff `L(M+1)τ ≡ 0 mod π` — one
instance being `Mτ = (M/(M+1))·(2π/L)`, i.e. **when the window size approximates the period**.
So "roundness of the point cloud" is a resonance test against the signal's own period.

**Why persistence.** Roundness of a point cloud is exactly what 1-D persistent homology
measures: a circle-shaped cloud has one long-lived H₁ class. Maximum persistence therefore
scores periodicity. The method is **pattern-agnostic** — the authors are explicit (p.2) that
prior periodicity methods are "based on finding cosine-like behavior, a rather limited
definition of periodicity", whereas this measures *recurrence of whatever pattern is there*.

**Stability (p.7).** `d_B(dgm(X), dgm(Y)) ≤ 2 d_GH(X,Y) ≤ 2 d_H(X,Y)`. Small perturbations of
the point cloud move the diagram only slightly — this is what makes it survive real, noisy data.

**Convergence (Thms 6.6, 6.7, pp.21–22).** The diagram of the centered+normalized cloud is
Cauchy in bottleneck distance as the Fourier truncation `N → ∞` (Convergence I) and as the
sampling `T → 𝕋` (Convergence II), so a limiting diagram `dgm_∞(f, w)` exists. The score is
well-defined, not an artifact of discretization.

**The quantitative payoff — Theorem 6.8 (p.23).** An explicit *lower* bound on maximum
persistence:

```
mp(dgm(Ȳ)) ≥ √3 · max_{1≤n≤N} r̃_n  −  δ·κ_N
    where  r_n = 2|f̂(n)|  (normalized Fourier magnitudes)
           κ_N = 2√2 ‖S_N f′‖₂ / ‖S_N(f − f̂(0))‖₂
           δ   = sampling density of T
```

Read plainly: **max persistence is bounded below by the largest normalized harmonic, penalized
by a roughness term.** A signal with one dominant harmonic is *guaranteed* a high score; the
penalty grows with `‖f′‖` (roughness/noise) and with coarse sampling. That is the bridge from
topology back to something we already compute.

## Two implementation gotchas that are easy to miss

1. **Centering + normalization is load-bearing, not cosmetic (p.18).** The authors state
   outright that as `M` grows "the object being approximated is changing… there is no reason
   to believe this process converges". Their fix is to compare *pointwise-centered and
   normalized* clouds (`Ȳ`, with the `√(M+1)` scaling). **Persistence diagrams from different
   window sizes or embedding dimensions are not comparable raw.** Anyone sweeping `Mτ` to find
   a period must normalize first or the sweep measures the embedding, not the signal.
2. **Field coefficients: `p > N` prime** (Thm 6.8 hypothesis). The homology is computed over
   𝔽_p and the argument needs `m` invertible in 𝔽_p. Default `p=2` implementations will
   silently violate this for multi-harmonic signals.

---

## What stays ours

**The honest frame first: this is NOT a better beat tracker.** For BPM and beat grids, madmom
already does well and is not the "cosine-like" strawman the paper critiques. Nothing here
should replace `rhythm/beat_grid.py`. The value is elsewhere.

**1 — A disintegration screen that measures STRUCTURE rather than spectrum.** Our current
screens (flatness, hf_ratio, zcr, CE, and the disintegration gate) are all spectral-shape
proxies, and we have now twice found them foolable: a noise drone moves a feature meter
(MASTER §4 disintegration gate), and Audiobox CE ranked Kim's two favourite checkpoints 1st
and 8th of 8 (`avp_board_freeform` run_meta, 2026-08-11). Meanwhile Kim's own language for
failure is *structural*: "constant spectral pad-like signature", "the beat has disappeared in
the first half", "rhythm breaking down". Those are recurrence statements. SW1PerS scores
recurrence directly, and Thm 6.8's roughness penalty means a noise drone — high `‖f′‖`, no
dominant harmonic — cannot score high by being loud or bright. It is close to orthogonal to
what we already measure, which is the property worth having in a second screen.

**2 — A measurable version of a complaint we keep failing to quantify.** Kim on the a2a
ladder (`a2a_angelic_r64tiered_lr1e4`): *"0.8, taken from a random position, plays like a
track, but when skipped around, it's evident that the whole song plays just one melody."*
That is **too much** recurrence at phrase scale, not too little. Because the score is a
function of window size, sweeping `Mτ` yields a *periodicity spectrum*; excess persistence at
bar/phrase windows is exactly the "one melody" pathology, and deficit at beat windows is the
"rhythm broke down" pathology. Same instrument, both failure directions, and we currently have
a metric for neither.

**3 — The input already exists.** mir's whole-track timeseries: 100 Hz, 46 fields, 4461 tracks
(`Lehto/timeseries`, MASTER §2), plus the per-crop SA3 companions. SW1PerS consumes scalar
time series, so this needs no new extraction — only scoring. `onsets_activations_ts`,
`rms_energy_*_ts` and `spectral_flux_ts` are the natural first inputs.

**Cost caveat, stated rather than discovered later.** Rips filtration is superlinear in point
count; the paper's own examples are small clouds. This is a **per-clip** metric computed on a
subsampled/landmarked cloud, not a per-frame feature. Budget it like Audiobox, not like zcr.

**Relation to the contour thread.** Complementary, not overlapping. C's morphological-space
work (Kant & Polansky) formalizes the *shape of a single trajectory* and lands on cosine of
soft-ranks. This measures *whether the trajectory returns*. Contour asks "what shape"; SW1PerS
asks "does it come back". A drone can have a perfectly well-defined contour and never recur.

---

## Status

Read + verified against the PDF. **Not implemented, not benchmarked, no claim tested on our
data.** The two candidate uses above are hypotheses with a clear first experiment: score the
existing `rarity_gen_set` / disintegration clip families and check whether the score separates
clips Kim has already graded — we have his verdicts in the run_meta sidecars now, so it is a
labelled test set rather than a vibe check.
