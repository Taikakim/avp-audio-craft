# Muon with Spectral Guidance: Efficient Optimization for Scientific Machine Learning — SpecMuon (2602.16167v1) — read by CONTINUITY 2026-10-21, LOW RELEVANCE

Lu, Zhang, Lin (Purdue: Electrical and Computer Engineering, Mathematics, Mechanical Engineering). v1 dated 18-19 Feb 2026, unreviewed.
PDF: `reviewed-low-relevance/arxiv-2602.16167 - Muon with Spectral Guidance ... (SpecMuon).pdf`. **Read:** pp. 1–15 (method, theory, toy regression, Burgers PINN, DeepONet). **NOT read:** pp. 16–19 (fPINN-DeepONet table, conclusion, references).

## What it contains
- **SpecMuon:** take the top-k singular directions of the gradient (k = `r_top`, 6 for the PINN, 8 for the DeepONet) and give each a scalar auxiliary variable (the relaxed scalar-auxiliary-variable, RSAV, trick from gradient-flow numerics) tied to the
  global loss through `E = sqrt(f + kappa)`; the rest of the spectrum gets the ordinary Muon update. Each step needs a (truncated) SVD, the current loss value, and a small quadratic solve per mode.
- **Theory (deterministic):** a modified energy dissipates every step (Thm 2.2, 3.1), the auxiliaries stay positive, the loss decreases for a small enough step, and linear convergence holds under the Polyak-Lojasiewicz condition (Thm 3.6).
  The theory covers the bare update, without the momentum and gradient normalisation the practical Algorithm 1 adds.
- **Experiments:** toy least squares; 1D viscous Burgers PINN (10,000 epochs): final loss Adam 5.88e-4, Muon 3.39e-4, SpecMuon **1.55e-4**; MSE 1.25e-3 (Muon) vs 5.06e-4; time 149 s vs 180 s. DeepONet on Burgers shows the same ordering. `r_top = 1` is clearly worst, so keeping several modes matters.

## FOR US — why it is low relevance
1. **Wrong regime.** Small PINN and DeepONet networks, deterministic or collocation-point losses, 10k epochs, a stiff-PDE conditioning problem. Nothing about minibatch noise, audio, flow-matching, or fine-tuning. The guarantees are for exact gradients.
2. **It needs the loss VALUE every step.** In our trainers that value swings with the sampled noise level t (and the half-batch), so `E` would track sampling noise, not progress. The energy argument has no stochastic version here.
3. **The baseline looks mis-tuned.** Table 1/3: Muon's momentum grid is `{0.0, 0.02, 1e-3, 1e-4, 5e-4}` (best 0.02 / 1e-4), no value near the usual 0.95, while SpecMuon's grid includes 0.9 and picks it. Muon is run essentially without momentum and SpecMuon with. The headline gap is not attributable to the spectral mechanism.
4. **Per-step SVD and extra state** for a gain measured on tiny problems, with no seeds beyond the training-loss column (MSE has no interval).
- **What is faintly useful:** the `r_top` ablation says treating the leading modes separately mattered there, a cousin of the HTMuon (E15) and NAMO-D (E16) question of whether the weak tail should get less weight. Our own probes (E17, test-plan sec. P) answer that on our gradients.
- **Verdict:** skip; no experiment registered. Filed so nobody re-reads it.
