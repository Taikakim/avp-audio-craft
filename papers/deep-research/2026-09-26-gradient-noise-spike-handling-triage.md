# Triage: "State-of-the-art assessment: gradient noise and spike handling" (CONTINUITY, 2026-09-26)

Source: `state_of_the_art_assessment_gradient_noise_and_spike_handling_20260926_191311.pdf` (13 pp,
M365 Copilot research agent), answering `2026-09-26-gradient-signal-vs-noise-brief.md`.

## Verdict: sound and usable. Math checked, key citations verified.

**Checked, correct:**
- Half-batch estimators with batch-mean gradients, b = 8: S = <G_A, G_B> unbiased for ||E G||^2;
  N_16 = 1/4 ||G_A - G_B||^2 unbiased for the full-batch-16 mean's covariance trace; per-example
  tr(Sigma) = (b/2) ||G_A - G_B||^2. The ratio is NOT unbiased; average numerator and denominator
  separately, never clamp negative cross-products before averaging.
- A scalar gain applied just before the polar/orthogonalisation map cancels (scale invariance);
  applied before momentum it re-weights the momentum history, so a noisy estimate steers the buffer.
- Momentum beta1 = 0.9: an isolated gradient's weight halves in ~6.6 steps, falls under 5% after ~28.
  Schedule-Free averaging damps the iterate but not the contaminated momentum buffer.
- Zero-init LoRA B: A's first gradient is zero; parameter-relative AGC needs a norm floor or must
  exclude B until it has scale.

**Citations verified against arXiv abstracts (load-bearing, post-cutoff):**
- 2602.03001, Naganuma et al. (Feb 2026, rev. Jul 2026): non-Euclidean gradient noise scales for
  signSGD/specSGD from their dual norms; used for ADAPTIVE BATCH SIZE, not gating. Direct to our family.
- 2602.22610, Huang et al. (Feb 2026): conditioning (AdaLN) induces heavy-tailed per-example gradients
  in diffusion; bounded re-parameterisation fixes it; DP time-series setting. Converges with our
  five-of-five conditioning-layer spikes, but one external result, different setting.
- 2606.08783, OptMuon (Jun 2026): adaptive coefficient for orthogonalised momentum with a
  running-maximum guard against isolated spikes. Theory-heavy, little application evidence.
Older citations (McCandlish 1812.06162, AdaScale 2007.05105, SOAP, Dion, ZClip, Kimi K2/MuonClip
2507.20534, LoRA+, rsLoRA, DoRA, NFNet/AGC, Min-SNR, Improved DDPM) are well-known and correctly
characterised. Not checked: NAMO 2602.17080, NorMuon 2510.05491, Stable Velocity 2602.05435,
VR-Sampling (OpenReview), PolarGrad 2505.21799, 2503.12645.

## What it changes for us
1. **Euclidean SNR as a live controller is a dead end** for a polar-map optimizer; keep it as a log.
   The right diagnostic is **post-transform agreement**: cosine between the two half-batch UPDATES
   after whitening + NS polynomial + NorMuon (is the direction reproducible?), plus principal-angle
   overlap of the halves' leading singular subspaces and the fraction of singular energy near the NS
   polynomial's low-singular-value transition. New to us, cheap, worth adding to the flight recorder.
2. **Ranked experiments** (all low cost), matching our plan:
   (1) effective-LR-matched gate ablation: gate at nominal lr vs no gate at lr x median gate;
   (2) pre-momentum per-tensor spike clip, g * min(1, k*m/||g||), m a lagged robust centre of the
       UNCLIPPED norms, k from the empirical 99.9th percentile, first on conditioning LoRA B only;
   (3) conditioning-path LR localisation: common lr vs 0.25x on conditioning adapters vs excluded.
   Kill criteria are stated in the PDF (p. 11-13).
3. Escalation for the conditioning path: targeted clip -> 0.25-0.5x lr -> exclude magnitudes/adapters
   from the affected projections -> bounded re-parameterisation (2602.22610) only then.
4. DoRA magnitudes under sign steps: no paper validates it; options are a separate much smaller lr,
   trust-ratio scaling, or m = softplus(u) + m_min (positivity by construction). Our multiplicative
   update already guarantees positivity.

## After reading the three papers in full (C, 2026-09-26, later the same day)
Notes: `papers/arxiv-2602.03001 …`, `arxiv-2602.22610 …`, `arxiv-2606.08783 …` (+ knowledge.md rows).
- **2602.03001:** as reported, but sharper: the Muon-geometry noise scale is the NUCLEAR-norm GNS, it
  controls batch size, and the authors list momentum as an open problem. Needs many independent
  sub-batches; our two half-batches are weak. Diagnostic only.
- **2602.22610:** as reported. The tail effect is visible without DP; 8-layer d=256 model from scratch;
  the fix changes the forward pass. Support for our finding, not a transferable fix.
- **2606.08783 (OptMuon): the report over-rated it.** Theory only, no experiments, assumes bounded
  gradients; its running max protects its own coefficient, not momentum, and its step scales with ‖M‖_F,
  so a spike makes the step larger. Low relevance.
- **The report missed a precedent we already hold: AdaGC (2502.11034)**, deep-read 2026-08-11 in the
  drone cluster (knowledge.md). Per-tensor clipping against an EMA (β 0.99) of each tensor's CLIPPED norm,
  global-clip warm-up, λ_rel = 1.04 by default; Muon-compatible; spike score → 0 on Llama-2 7B / Mixtral.
  It is exactly experiment #2 of the ranked list, with evidence at scale. Set aside in August because
  the drone was drift, not spikes; the shampoo run's failure mode is spikes, so it now applies.
