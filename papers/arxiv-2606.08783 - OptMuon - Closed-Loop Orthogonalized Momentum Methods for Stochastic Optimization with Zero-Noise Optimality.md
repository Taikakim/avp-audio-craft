# OptMuon: Closed-Loop Orthogonalized Momentum Methods for Stochastic Optimization with Zero-Noise Optimality (2606.08783v2) — deep-read

Ganzhao Yuan (single author). arXiv preprint, Jun 2026 (v2 26 Jun). PDF beside this note. **Read by C
2026-09-26 (algorithm §4 and conclusion in full; convergence proofs skimmed).**

## What it shows
- Muon-style polar-factor update with a **closed-loop scalar magnitude**:
  `X_{t+1} = X_t − θ γ_t ‖M_t‖_F Orth(M_t)`, direction from the polar factor, magnitude from a schedule.
- Coefficient `α_t = ρ_{t−1}`, `ρ_t = ((1 + max_i g_i²) / (1 + Σ_i g_i²))^q` with `g_i = ‖G_i‖_F`,
  q = 1/2 (Option A) or 2/3 (Option I, STORM-type momentum needing two gradients per step). An
  AdaGrad-Norm-style self-normalising schedule; the **running maximum in the numerator only stops the
  coefficient collapsing after an isolated spike**.
- Momentum `M_t = G_t + (1 − α_t) M_{t−1}` (Option A) takes the raw gradient in directly.
- Noise-adaptive convergence rates; recovers ~O(T^{−1/2}) in the zero-noise limit without retuning.
- **Theory only: no experiments.** Assumes exact orthogonalisation (no Newton–Schulz error) and an
  **almost-surely bounded stochastic gradient**.

## FOR US / what stays ours
- **Not a spike defence in our sense.** Its "spike protection" protects its own step coefficient from
  over-shrinking; it does nothing about a spike contaminating momentum, and because the step scales with
  ‖M_t‖_F a spike makes the step LARGER, the opposite of Muon/our normalised step.
- Its bounded-gradient assumption is exactly what spikes violate.
- Useful only as a reference for "decouple direction (polar factor) from a separately scheduled
  magnitude", which our stack already does (spectral LMO + lr schedule + Schedule-Free).
- The research report of 2026-09-26 rated it "theory-adjacent"; after reading, **low relevance**.
