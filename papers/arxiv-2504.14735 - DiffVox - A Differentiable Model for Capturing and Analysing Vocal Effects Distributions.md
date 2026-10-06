# DiffVox: A Differentiable Model for Capturing and Analysing Vocal Effects Distributions (2504.14735v2) — deep-read

Yu, Martínez-Ramírez, Koo, Hayes, Liao, Fazekas, Mitsufuji (QMUL C4DM; Sony AI). DAFx25 (Ancona), 11 pages.
Code + dataset: github.com/SonyResearch/diffvox (435 fitted vocal presets + 20 test presets). **Read in full
by W 2026-10-07.**

## What it shows
- **Model.** A fixed vocal chain, mono in / stereo out: 6-band parametric EQ (2 peak, low/high shelf, LP, HP;
  RBJ biquads) -> feed-forward compressor + expander (with look-ahead via truncated sinc) -> dry path + send
  path: ping-pong delay (frequency-sampled damped-sinusoid approximation with an LP in the feedback) and a
  6-line stereo FDN reverb with frequency-dependent decay (49 sampled attenuation points + a tone-correction
  EQ), delay -> reverb send. 152 parameters total. Recursive filters run with a GPU parallel scan
  (associative formulation of the biquad recursion; one complex one-pole per biquad).
- **Fitting.** Per track, by gradient descent on paired dry/processed stems (MedleyDB 70 tracks, private
  "Internal" 365); 12 s segments, 2k Adam steps, lr 0.01, 20–40 min per track on an RTX 3090. Inputs
  normalised to -18 LUFS.
- **Loss.** Multi-scale STFT (auraloss, A-weighted) + **MLDR (Multi-resolution Loudness Dynamic Range)**:
  LDR(x, t_short, t_long) = log(RMS_short / RMS_long), compared L1 at several scales (t, t/20), on L/R and M/S.
  Built to match microdynamics (compression, envelopes) that spectral losses miss.
- **Ablation (MedleyDB, Table 2).** Without delay+reverb the spectral loss is fine but microdynamics fail
  (MLDR m/s 1.17 vs 0.45 full model) — the spatial effects carry the dynamics match.
- **Analysis.** Spearman correlations of the fitted parameter logits (e.g. delay time vs delay feedback -0.58,
  compressor threshold vs make-up -0.55, LP cutoff vs reverb HF attenuation +0.60); effect-level clustering
  (spatial / low-end HP+LS / the rest); PCA: PC1 = spaciousness (delay + reverb, longer HF decay), PC2 =
  bandwidth ("telephone" band-pass) — linked to McAdams timbre dimensions. Multivariate normality rejected
  (Royston, Henze-Zirkler) -> a Gaussian/PCA prior is not adequate; a stronger generative model is needed.

## Caveats
1. **Fit quality only, no held-out test.** The presets are optimisation outcomes, not ground truth.
2. **Several parameters look non-identifiable:** the delay-time histogram has a tall spike exactly at its
   400 ms initial value, and send / delay gains pile up at their bounds (Fig. 4). Correlations involving
   them (e.g. the -0.58) partly reflect where the optimiser got stuck, not engineering practice. The figure
   marks the initial value; the text does not discuss it.
3. **The datasets disagree.** MedleyDB's top correlations mostly do not match Internal's (Table 3); the
   conclusions rest on the private 365 tracks.
4. Needs paired dry and processed stems; 8% / 1.3% of tracks excluded as non-fitting (distortion, modulation).

## Relevance to us
- **MLDR** is an off-the-shelf envelope/dynamics loss for our envelope-knob work: candidate replacement for
  the RMS-envelope cosine in `synth_inversion/refine.py`'s objective, and a second meter beside
  `h4_gate_envelope_meter.py`. Logged as **H8** in `EXPERIMENTS.md`.
- **A differentiable FX stage after the synth** (DiffVox-style delay / reverb / EQ) could fit the FX part of a
  real stem by gradient descent once the dry synth patch is inverted — getting FX back without Surge's FX
  (which leaks state across renders, so we switched it off). Logged as **H9**.
- Same analysis method as our H4 parameter matrices (correlation -> clustering -> PCA); its caveat 2 applies to
  any prior fitted by optimisation or drawn from a narrow preset set, including our 17/105-preset bass prior.
