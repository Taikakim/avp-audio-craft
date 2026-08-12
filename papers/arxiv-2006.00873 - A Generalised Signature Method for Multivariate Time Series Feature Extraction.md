# A Generalised Signature Method for Multivariate Time Series Feature Extraction (2006.00873)

*Project-POV abstract, CONTINUITY 2026-08-12 (reading-sweep, F-assigned; deep-read, full PDF + supplement).
Morrill, Fermanian, Kidger, **Lyons** (Oxford / Alan Turing). The authoritative signature-method group
(also `signatory`, Neural CDEs). Companion to my Kant&Polansky morphological note — the **analytic** sibling
of combinatorial contour.*

## What it contains
The **path signature**: interpret a multivariate timeseries `x=(x_1..x_n), x_i∈ℝ^d` as a continuous path
(piecewise-linear interp), then take `Sig^N(x)` = the vector of **iterated integrals** of the path against
itself up to depth N. Depth-1 = total displacement per channel (ΔX^i); depth-2 = signed (Lévy) areas;
higher = higher-order channel interactions. Three properties make it a strong feature set:
- **Length-independent size:** `(d^{N+1}−1)/(d−1)` — depends on channels `d` and depth `N`, **not on n**.
  Compute `O(n·d^N)`; N=3 usually enough. (Memory cost independent of series length — big for hi-freq.)
- **Uniqueness (Hambly–Lyons):** the full signature determines the path **up to translation +
  reparametrization**. A faithful encoding modulo those two invariances.
- **Universal nonlinearity:** **LINEAR** functionals on the signature are dense in continuous functions of
  the path. *"Signatures are a basis for FUNCTIONS OF the series, not the series itself."* → a **linear**
  readout on `Sig(x)` can approximate ANY (continuous) movement feature.
- **Reparametrization-invariant:** captures the ORDER/shape of movement, not its timing (speed-invariant).
  Expected signature characterizes the *law* of a stochastic process (a moment-generating-function analog).

**The "generalised" framework = 4 explicit knobs (this is the paper's contribution):**
- **Augmentations** (choose which invariances to keep/break): **time-aug** (append `t` → breaks
  reparam-invariance + guarantees uniqueness), **basepoint** (prepend 0 → breaks translation-invariance),
  **lead-lag** (captures quadratic variation), coordinate/random/learnt **projections** (dim reduction).
- **Windows**: global / sliding / expanding / **hierarchical-dyadic** (multi-scale, wavelet-analogue).
- **Transform**: signature vs **log-signature** (logsig = redundancy-removed, smaller, but **loses** the
  universal-nonlinearity property).
- **Rescaling** of the depth-k terms (they scale `1/k!`).
Empirical (26 datasets): signature > logsig; **time+basepoint** aug both usually matter; **hierarchical
dyadic windows > global/sliding**; lead-lag helps motion/action; N=3 enough. Canonical pipeline
(basepoint+time, dyadic window, sig depth N → any classifier) ≈ deep RNN/CNN on multivariate TS
classification, far cheaper.

## What this gives us / what stays ours
- **The analytic, universal, length-independent complement to Polansky contour.** Both encode the SHAPE of a
  path; contour is ordinal (invariant to monotone *value* transform), signature is analytic (invariant to
  *time* reparametrization) — **two invariance axes for movement**, and signature adds the
  universal-nonlinearity guarantee contour lacks. Strongest-founded **"movement as a control-head FEATURE"**
  candidate we have: fixed-dim, length-independent, universal, with a mature **differentiable-on-GPU** toolkit
  (`signatory`, Kidger).
- **Directly the design note's time-axis morph / dense-past encoding** (`MORPHOLOGICAL_SPACE_DESIGN_NOTE.md`
  §5.1(b), §6.2, E6). A **linear** head on `Sig(melodic-trajectory)` can compute any movement feature →
  satisfies the "keep the head linear" desideratum on the signature rather than raw chroma. Hierarchical
  dyadic windows = the multi-scale hierarchy Kim wanted (compare a 4-frame gesture to a 64-frame phrase).
- **The augmentation choice IS the invariance dial** we keep rediscovering (n-ary contour resolution;
  raw↔demeaned↔whitened chroma; here time-aug/basepoint decide reparam/translation invariance). Same theme,
  three frameworks: **choose the invariances deliberately.**
- **Length-independence → a natural a2a EVAL metric** (signature of input trajectory vs output = did the
  movement match) and a variable-length **conditioning** signal.
- **STAYS OURS / caveats:** (1) `O(d^N)` blowup — infeasible on the raw **256-d** SAME latent (N=2 → 65k
  terms). Apply to a **low-d derived stream** (pitch-centroid, a few chroma bands, a projected latent) —
  same "low-d/single-scalar" constraint contour had; use the projection augmentations first. (2)
  Reparam-invariance is likely **WRONG for music** (rhythm = timing) → use **time-aug** to keep timing; the
  framework lets us. (3) Feature-extraction only — the **generative** version is SigDiffusions (2406.10354,
  next in my 5). Pairs with: Polansky contour (combinatorial sibling), HiPPO (W's), SigDiffusions.

**knowledge.md row** (hand to F, index owner): *A Generalised Signature Method (2006.00873, Morrill/Lyons) —
path-signature features for multivariate TS: length-independent, universal-nonlinearity (linear readout =
any path-function), reparam-invariant; 4 knobs (aug/window/transform/rescale) = an explicit invariance dial.
FOR US: the analytic complement to Polansky contour; strongest movement-as-control-head-FEATURE candidate,
differentiable via `signatory`; use on a LOW-d derived stream (d^N blowup on raw 256-d latent) with time-aug
(keep rhythm). Design-note §5.1(b)/§6.2/E6.*
