# Understanding Gradient Orthogonalization for Deep Learning via Non-Euclidean Trust-Region Optimization (2503.12645v2) — deep-read

Dmitry Kovalev (Yandex Research). arXiv preprint, v2 8 Apr 2025. PDF beside this note. **Read by C
2026-09-26 (§1–§4 and Appendix B in full; proofs skimmed).**

## What it shows
- **Muon = a first-order trust-region method** with the trust region in the spectral norm: each step
  minimises the linear model inside a spectral-norm ball of radius η. The stochastic version with
  momentum recovers Muon, normalized SGD and signSGD-with-momentum as special cases (different norms).
- Convergence rates, state of the art for the setting: non-convex, star-convex (with weight decay:
  1/ε³), second-order smooth (with extrapolation), constrained and composite problems. Assumes unbiased
  gradients with **bounded variance** (A1).
- **Parameter choice (eq. 17):** the momentum weight α (= 1 − β) and the step η both shrink as the noise σ
  grows: α = O(min{1, ε²/(ρ²σ²)}). Noisier gradients call for a slower momentum buffer and smaller steps.
- **Appendix B, why Muon beats Orthogonal-SGDM** (which orthogonalises the gradient and then averages):
  momentum accumulates independent, zero-mean noise terms whose weighted sum has reduced variance (a
  "batching effect"); the averaging must happen BEFORE the non-linear orthogonalisation, and the
  trust-region step is naturally fed the momentum ("orthogonalised momentum", not "momentum of
  orthogonals").
- **Weight decay** = shifting the trust-region centre toward zero, which keeps iterates bounded; explains
  why it matters for large LLMs and less for small ones.
- **Theory only: no training experiments.** "Good results" = convergence rates.

## FOR US / what stays ours
- **Supports a slower momentum buffer for our very noisy DiT gradients** (eq. 17), consistent with
  LionMuon's dual-EMA (β2 = 0.99; `arxiv-2605.19811`). Also says the step should shrink with noise, i.e.
  the ×0.2 the SNR gate imposed was directionally sensible and should be an explicit, honest lr.
- **Averaging before the non-linearity** is why any spike defence must act on the raw gradient BEFORE it
  enters momentum (AdaGC-style clipping), never on the final orthogonalised update (cautious masking
  fails this). Our ModularOptimizer has the Muon order: momentum (optimizer.py:421) → whitening → LMO.
- **Found while checking that order (2026-09-26): a second spike pathway.** The Shampoo preconditioner
  accumulates the RAW gradient (`preconditioner.update_accumulators(grad)`, optimizer.py ~434). It
  averages G Gᵀ, so a 42× spike enters at ~1764× and distorts the whitening for >100 steps at β_precond
  = 0.95. A spike clip must run before BOTH the momentum and the preconditioner updates.
- Its bounded-variance assumption is what our spikes violate; LionMuon's κ-moment (heavy-tail) analysis
  is the more realistic model.
