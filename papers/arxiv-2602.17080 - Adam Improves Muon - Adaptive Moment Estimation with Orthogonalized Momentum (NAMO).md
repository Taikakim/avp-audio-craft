# Adam Improves Muon: Adaptive Moment Estimation with Orthogonalized Momentum — NAMO / NAMO-D (2602.17080v2) — read by CONTINUITY 2026-10-21

Zhang, Liu, Schaeffer (UCLA Mathematics; NSF DMS 2502561). v2 dated 20 Feb 2026. A small applied-maths group, not an industry lab.
Code: github.com/minxin-zhg/namo (MIT, last commit 2026-09-05; `src/namo.py`; sweeps also list GPT-2 large, which this v2 PDF does not report).
PDF: `arxiv-2602.17080 - Adam Improves Muon - Adaptive Moment Estimation with Orthogonalized Momentum (NAMO).pdf`.
**Read:** pp. 1–14 (all of the main text, theorems, experiments, conclusion). **NOT read:** the proofs in appendices A–E (pp. 15–39). Venue not stated in the PDF.

## What it contains
- **NAMO:** Muon's orthogonalised momentum times ONE scalar `alpha_t = ||M_hat_t||_F / sqrt(v_hat_t)`, where `v` is an EMA (mu2 = 0.99) of the squared gradient Frobenius norm.
  It is Adam's signal-to-noise ratio computed at matrix-norm level, and it shrinks the step when gradients are noisy or near stationary. Weight decay is scaled by the same alpha.
  The repo clamps alpha at 1 and uses the Nesterov-mixed gradient in the numerator.
- **NAMO-D:** right-multiplies the orthogonalised update by a diagonal, one entry per column (neuron), from the same ratio on column norms, clamped into `[c*mean, mean/c]`. This is not NorMuon:
  NorMuon equalises the rows of the update, NAMO-D weights neurons by their own gradient SNR (entries bounded by `sqrt((1-mu1)/(1-mu2))`, 2.24 at 0.95/0.99).
- **Theory:** optimal O(T^-1/2) deterministic and O(T^-1/4) stochastic rates, with the stochastic bound needing batch `b = Omega(sigma^2 sqrt(T))` to be optimal. At our batch sizes (16–64) that
  condition is far from met, so the theory says little about us.
- **Results:** GPT-2 124M and 355M on OpenWebText (nanoGPT, 4xH100, 491k tokens per step, weight decay 0.01, 2000-step warm-up then CONSTANT lr).
  Validation loss, Muon / NAMO / NAMO-D: 124M at 50K steps 3.0435 / 3.0351 / 3.0246 (AdamW 3.0643); 355M at 10K steps 2.9684 / 2.9516 / 2.9507 (AdamW 2.9914).
  Gains are 0.008–0.019 nats. Best learning rates: Muon 0.0013 (124M) and 0.0009 (355M); NAMO 0.012 and 0.007; NAMO-D 0.009. Grids bracket each optimum, unlike the HTMuon paper's Muon grid.

## FOR US — what it says, what to doubt
1. **It is the SNR gate we already have, with a theory.** Our `ModularOptimizer` SNR gate (`_snr_gate_step`, per-element `|EMA(G)|/sqrt(EMA(G^2))`) is the same family. `docs/TRAINING.md` F27 measured it
   at its own pure-noise floor (0.183) on our gradients: an uncalibrated ~x0.2 lr cut at small batch. NAMO's pure-noise floor with momentum 0.95 is `sqrt((1-0.95)/(1+0.95)) = 0.16` (my arithmetic).
   So expect NAMO to behave like Muon at ~0.16–0.2x the learning rate on our heads (batch 16–64), until the signal share genuinely rises.
2. **Its optimum learning rate is 7–9x Muon's** (0.012 / 0.0013 and 0.007 / 0.0009), which is what a mean alpha around 0.11–0.14 would produce: consistent with the gate sitting near its noise floor
   even at 491k tokens per step. The gain therefore cannot be cleanly separated from a learning-rate rescale plus a built-in step decay (inference, untested).
3. **The protocol is constant lr, no decay.** A step that shrinks automatically as gradients turn noisy acts like a learning-rate decay, which a constant-lr Muon lacks. With a decay schedule (we use SF or
   cosine) the gap may shrink or vanish. This is the control the paper lacks: Muon with a proper decay, or NAMO's alpha logged and replayed as a schedule.
4. **Train gains do not transfer.** At 124M / 50K steps (about 2.7 epochs of OpenWebText) training loss improves by 0.10 (3.0265 → 2.9272) but validation by 0.008. NAMO's validation curve oscillates by about
   that much (Fig. 2). No seeds or error bars anywhere. At 355M NAMO-D's best c is 0.9 (nearly uniform scaling), so NAMO-D ≈ NAMO there (2.9507 vs 2.9516); at 124M c was fixed at 0.1, not swept.
5. **Regime:** GPT-2 pretraining only. Nothing on fine-tuning, small heads, audio, or batch below 480 sequences.
- **Verdict:** a clean, theory-backed SNR-scaled Muon whose evidence is thin (0.01–0.02 nats, one seed, constant lr). It restates a component we already carry. Parked as **EXPERIMENTS E16**: no new optimizer before test-plan sec. P/N;
  the cheap check is to log NAMO's `alpha_t` on an existing arm and compare it with the SNR-gate telemetry (`comp/snr_gate`).
