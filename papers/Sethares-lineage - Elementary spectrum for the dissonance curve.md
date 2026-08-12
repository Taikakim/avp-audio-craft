# Elementary spectrum for the dissonance curve: from biophysics to number theory of musical harmony (Guillet, HAL-05124442, 2025)

*Project-POV abstract, CONTINUITY 2026-08-12 (reading-sweep 5/5, Kim's pick; deep-read pp.1-19).
Guillet (Max Planck Inst. for Physics of Complex Systems). The **Sethares/Helmholtz dissonance-curve** lineage,
recast in number theory (Riemann ζ + Minkowski's ?-function). Read under Kim's CORRECTED criterion — "does it
NAME a musically meaningful quantity we could extract from audio and steer?" — and the answer is a clear YES:
sensory dissonance/roughness is a control dimension, a prediction target, and a per-frame time series.*

## What it contains
Recasts **Helmholtz's dissonance curve** `D(λ)` — the sensation of roughness of an interval `λ=f₂/f₁`, built
as a weighted sum of roughness contributions over every pair of partials of two simultaneous notes — into a
clean number-theoretic form. Three moving parts:
1. **Timbre = Riemann ζ.** A harmonic timbre with partial amplitudes `aₙ=n^{-σ}` has its (Mellin-Fourier)
   spectrum = `ζ(σ+iτu)`. `σ` = timbre richness dial (σ→∞ = pure "beep"; σ→½ = critically rich = pink/1/f
   noise, the musically representative limit). Interval+timbre factorize: `note1 ⋆ note2 = interval * timbre`.
2. **Dissonance/consonance = a "sonance" measure** built as a statistical-mechanics "arithmetic gas": Boltzmann
   weights `e^{−βH(q)}` over just intervals `q=a/b`, with disharmonicity `H(a/b)=log(ab)` (Tenney height). `β`
   = inverse-temperature/**sonance exponent**: `β>1` → a *consonance* measure (mass on simple rationals), `β<1`
   → a *dissonance* measure; the max-entropy case `β=0` is exactly **Minkowski's ?-function** — "the simplest
   dissonance measure." These are singular **fractal** measures on ℚ⁺.
3. **Dissonance spectrum** `D̂(u) = |ζ(½+iτu)|² · ?̃₀(u)` (Eq.19): timbre (ζ on the critical line) × sonance
   (Minkowski). Its **deep minima = the consonant intervals** (unison, octave 2/1, fifth 3/2, fourth 4/3,
   thirds…), and **large spectral peaks at u≈5,7,12,19,31 per octave predict the sizes of widely-used scales**
   (pentatonic→12-TET→microtonal) — from first principles, across genres/cultures.
- **`Q` = hearing quality factor = the RESOLUTION DIAL.** The ideal curve is a singular fractal; a real ear
  low-passes it with finite `Q~f/Δf` (they use Q=80 for a trained ear). **Higher Q → more just intervals AND
  quadratic irrationals (φ, √2, √3) register as sharp minima/maxima**; lower Q = a coarser, less-trained ear.
  Sethares' classic practical point survives intact: **the dissonance curve depends on the TIMBRE** — the same
  interval is more/less rough depending on the sound's partials → scale should be matched to timbre.

## What this gives us / what stays ours
- **Sensory dissonance/roughness = a first-class CONTROL DIMENSION & PREDICTION TARGET** (passes Kim/W's 3-part
  test cleanly): (1) computable from a rendered clip — it's a spectral roughness integral over partial pairs,
  and mir/Essentia already ship a `dissonance`/`roughness` descriptor; (2) askable by ear — "rougher / smoother
  / more consonant / more tense" is exactly the kind of "more-X" Kim would request; (3) a **per-frame time
  series** at any rate → a candidate new field in the whole-track timeseries AND a candidate FiLM/LatCH
  conditioner or readout target. This is the strongest *directly-actionable* item in my 5 — not theory scaffold
  (contour/signatures) but a scalar we can extract today.
- **Timbre-dependence is the design constraint we must respect.** Because `D` depends on the actual partials
  (σ / the real spectrum), a dissonance control/target must be measured **on the rendered audio spectrum**, not
  inferred from pitch/chroma alone — the SAME point our chroma work learned (read the property off the signal,
  don't assume it). Pairs with the L-parsing/read-from-latent theme (Anatomica): measure `D` from the decoded
  (or partially-decoded) spectrum.
- **Reconciles with Tymoczko (my #4) — the two consonance theories Kim flagged.** Tymoczko: consonance =
  near-**even division** of the octave = distance from orbifold **center** (log-frequency geometry). Guillet/
  Sethares: consonance = **spectral roughness minimum** = commensurability of partials (timbre-dependent). They
  are the *even-division* vs *spectral-roughness* accounts, and this paper even notes Helmholtz→scales; a fused
  "harmonic-tension" signal could combine geometric-center distance (pitch-only, cheap, differentiable via the
  chroma circle) with spectral-roughness (timbre-aware, from the render). Candidate eval: does an a2a output
  preserve the input's consonance/tension contour?
- **`Q` / `β` = the resolution dial AGAIN** — the fifth independent sighting of the theme (Polansky n-ary; raw↔
  demeaned↔whitened chroma; signature aug/depth; Tymoczko quotient choice; here Q=ear-resolution & β=sonance-
  exponent). Strongly suggests the "n-ary sweet-spot" isn't an artifact of one representation — it's structural:
  every music descriptor has a resolution at which discrimination peaks, and finding it is a first-class tuning
  step for any conditioner/target we build.
- **STAYS OURS / caveats:** (1) the paper is **descriptive number theory**, not a learned model or code — the
  ζ/Minkowski machinery is a beautiful *derivation* of the dissonance curve, not something we'd port; what we
  port is the **quantity** (sensory dissonance/roughness, timbre-aware) + the **Q-resolution** discipline. (2)
  It **ignores time** entirely (harmony only — melody/rhythm explicitly set aside); the per-frame-timeseries
  use is *our* extension, not theirs. (3) `D` is a pairwise/interval quantity; turning it into a single per-frame
  scalar for a clip means integrating the roughness over the frame's spectrum (Essentia's dissonance already
  does a version of this) — a modest but real design choice. (4) 2nd-wave relative to the melody/chroma head
  sweep, but the CHEAPEST new descriptor to add — Essentia already computes it, so a corpus roughness-timeseries
  is nearly free to try as a conditioner/target.

**knowledge.md row** (hand to F): *Elementary spectrum for the dissonance curve (Guillet, HAL-05124442, 2025;
Sethares/Helmholtz lineage) — recasts the dissonance curve D(λ) as timbre(=Riemann ζ on the critical line) ×
sonance(=Minkowski ?-function, β=sonance exponent); minima=consonant intervals, spectral peaks at u≈5/7/12/19/31
predict scale sizes; Q=hearing-resolution dial sharpens which intervals register; dissonance is TIMBRE-dependent
(Sethares). FOR US (under Kim's corrected criterion): sensory dissonance/roughness = a first-class CONTROL DIM /
PREDICTION TARGET / new per-frame timeseries — computable today (Essentia `dissonance`/`roughness`), askable by
ear, time-series-able; must be measured on the rendered spectrum not pitch alone. Reconciles w/ Tymoczko as the
spectral-roughness account of consonance vs his even-division/orbifold-center account (→ fused harmonic-tension
signal). Q/β = the resolution-dial theme's 5th sighting → 'n-ary sweet spot' is structural. Descriptive number
theory (no code); cheapest new descriptor to try as conditioner/target.*
