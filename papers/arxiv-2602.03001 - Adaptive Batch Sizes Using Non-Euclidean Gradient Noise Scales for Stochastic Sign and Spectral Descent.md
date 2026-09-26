# Adaptive Batch Sizes Using Non-Euclidean Gradient Noise Scales for Stochastic Sign and Spectral Descent (2602.03001v2) — deep-read

Naganuma, Gupta, Briki, Mitliagkas, Rish, Raman, Shi (Mila / Université de Montréal / Meta). ICML 2026
(PMLR 306). v1 Feb 2026, v2 Jul 2026. PDF beside this note. **Read by C 2026-09-26 (main text pp.1–9 in
full, appendix skimmed), from the brief `deep-research/2026-09-26-gradient-signal-vs-noise-brief.md`.**

## What it shows
- **Euclidean gradient-noise scale (McCandlish) is the wrong geometry for sign and spectral optimizers.**
  For steepest descent in a norm, the step's error is governed by the gradient error in the DUAL norm
  (Lemma 3.1: E<∇L, p> ≥ ‖∇L‖* − E‖∇L − g‖*). ℓ∞ steps (signSGD/Signum) → ℓ1 GNS; spectral steps
  (specSGD/Muon, P = UVᵀ) → **nuclear-norm (S1) GNS**:
  `B_S1 = ‖C_row^{1/2}‖²_S1 / ‖∇L‖²_S1`, with C_row the row-wise gradient covariance (per 2-D matrix).
  Also: the step inner product is constant (r for a rank-r polar factor), so only the dual-norm error term
  matters.
- **Estimator:** uses the local mini-batch gradients on each data-parallel rank as independent samples,
  signal from the global gradient; noise N and signal M kept as separate EMAs (β_N, β_M), batch size set to
  N / (θ² M). Computed **before gradient clipping**. For S1 each rank forms the local Gram G Gᵀ.
- **Use:** adaptive BATCH SIZE (+ √B lr scaling). 160M Llama-3, 3.2B tokens, 8×H100: matches the constant
  small-batch validation loss with up to **66% fewer steps** for Signum and Muon; 1B: 31.8% / 12.1% fewer
  for signSGD / Signum; AdamW did not reach baseline with it.
- **Open, per the authors:** EMAs of gradients/second moments (i.e. Muon's momentum, AdamW), composite
  optimizers with different noise scales per module, general Hessians. For composite optimizers they only
  measure the 2-D (Muon) groups.

## FOR US / what stays ours
- **The right noise measure for our spectral groups is the S1 GNS, not per-element or Frobenius SNR.** It
  formalises why our SNR gate (per-element |EMA g| / √EMA g²) was the wrong quantity even before its
  noise-floor bug (the SNR-gate analysis with W, 2026-09-26).
- **It is a batch-size controller, not a step/momentum controller**, and momentum is explicitly unsolved.
  Nothing here licenses gating our steps or momentum on it.
- **Estimation on one GPU is weak.** Their estimator needs several independent sub-batches (ranks); we have
  two half-batches of 8, which the paper itself classes with "high variance, single-sample" estimators.
  Usable as an occasional DIAGNOSTIC with long averaging, not a live signal.
- **Cheap for LoRA factors:** C_row for B (12288×128) or A (128×1536) can be formed on the rank-128 side
  (128×128 Gram), so an S1 diagnostic per adapter pair is affordable.
- Batch size is our lever only loosely (16 fixed by VRAM; accumulation possible), so the paper's actual
  control use does not transfer directly.
