# Muon Under Gradient Noise and the Limits of Orthogonalization Near Optima (2609.32861v1) — read by CONTINUITY 2026-10-21

Xiaohui Xie (UC Irvine, Computer Science), single author, v1 dated 26 Sep 2026, unreviewed. PDF: `arxiv-2609.32861 - Muon Under Gradient Noise and the Limits of Orthogonalization Near Optima.pdf`.
**Read:** pp. 1–16 (all of the main text, experiments, discussion). **NOT read:** appendices A–D (pp. 17–30: proofs, Hermite constants, Gaussian table).
This is the "September 2026 preprint" an external summary cited for "Muon raises the late-training noise floor"; it exists and says roughly that, but with magnitudes the summary omitted.

## What it contains
- **Near a noise-dominated optimum, Muon is a gradient step in the mean** (Prop. 3.1): `E[P(Y + sigma Z)] ≈ (c/sigma) Y`, so Muon acts as SGD with rate `eta_M * c / sigma`. Verified by Monte Carlo within 0.8%.
- **After matching that mean response, a nonlinear residual remains**, uncorrelated with the noise and adding covariance (Thm 4.1). One-step covariance ratio to matched SGD, R0: pi/2 for scalars, 1.39 for large square matrices.
- **Momentum shrinks the residual but not to zero** (Thm 5.1, Cor. 5.2). At beta = 0.95 the long-window ratio falls from 1.394 to **1.080** for 64x64 exact polar; for the reference implementation (NS5 plus Nesterov, beta 0.95) 1.509 to **1.067**.
- **Loss gap in a surrogate** (Thm 6.1/6.2): the stationary EXCESS loss of Muon exceeds that of matched momentum SGD at every stable step size. Simulated full recursion on quadratics: ratios 1.04–1.13 (Table 1). Real frozen-transformer gradients (batch 64, 6 matrices, Tiny Shakespeare):
  attention matrices 1.14–1.19 at beta 0.95 (1.42–1.45 without momentum), MLP matrices 1.02–1.05. bf16 and fp32 agree within 0.03.
- **Regime indicator** `delta_beta = ||Y||_F / (sigma_beta sqrt(d))`, mean norm over buffer-noise norm. Small means the theory applies; the paper gives no threshold. On its transformer: 1.0–1.7 at step 400, 8–11 at step 100.
- **Honest limits, stated by the author:** no experiment trains a network with a switched optimizer; the switching rule (detect the regime, choose a threshold, estimate the matched rate) is explicitly left open; Gaussian-noise and scalar-response assumptions.

## FOR US — is it useful?
1. **It sizes the "Muon amplifies noise" worry, and the size is small.** At beta 0.95 the extra stationary fluctuation is about 7–8% (isotropic) to 14–19% (attention, real noise), as a ratio of EXCESS loss over the optimum, not of total loss.
   That lowers the case for noise-motivated variants (HTMuon E15, NAMO-D E16, a late switch to AdamW/SGD) as a fix for a big problem. It does not say they cannot help.
2. **Our evaluation uses averaged weights** (EMA, Schedule-Free). The analysis is about the iterates; averaging is not analysed, so a late switch cannot be justified from this paper for our runs. Also our gradients may sit in the paper's regime from early on
   (TRAINING.md F27: SNR gate at its noise floor), unlike its step-100 reading.
3. **Where our half-batch logs map onto its indicator (my derivation, not in the paper):** for two independent half-batch gradients `G = Y + n`, `cos(G1,G2) ≈ delta_h^2/(1+delta_h^2)`, so `delta_h = sqrt(c/(1-c))`. A full-batch step has `delta_g = sqrt(2) * delta_h`, and the momentum buffer
   improves it by `sqrt((1+beta)/(1-beta))` = 6.2 at beta 0.95, so `delta_beta ≈ 8.8 * sqrt(c/(1-c))`. For `delta_beta` below about 0.5 (noise-dominated) a matrix's half-batch cosine must be under about 0.003; c = 0.1 gives `delta_beta` ≈ 2.9, the transition region.
   So `docs/modular-opt-test-plan-2026-10-17.md` sec. N already produces what is needed to say which of our matrices are in this regime.
   **W's correction (2026-10-21):** our default momentum is 0.9, so the factor is `sqrt2*sqrt(19) = 6.2`, not 8.8, and the threshold is `c < ~0.006`; treat the figure as an upper bound when the mean rotates within the horizon. On measured EB64 values W gets `delta_beta` about 1.9-4.7, i.e. not noise-dominated. See EXPERIMENTS E17.
4. **A second, independent use (my derivation, tentative):** in the noise-dominated regime Muon's signal step is `eta c / sigma` with `sigma ∝ 1/sqrt(B)`, which is Adam-like (update normalised by the noise), so the square-root learning-rate rule for batch scaling should hold for Muon there. That is consistent with
   the sqrt(kappa) rule in `eval/run_overnight_dpo_batch_20261021.sh` job B; it would not hold for matrices with high signal share.
- **Verdict:** a careful theory note with no training test. Useful as a calibration of the noise worry and as a source for two cheap diagnostics (the covariance ratio on stored gradients, and `delta_beta` from sec. N). Not an action item. Registered as **EXPERIMENTS E17**.
- **Leads it cites, unchecked:** Li et al. "Denoise first, orthogonalize later" (2606.03899) and Choudhury et al. on Nesterov Muon under heavy-tailed noise (2605.06884).
