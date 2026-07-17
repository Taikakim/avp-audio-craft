# Discovering and Steering Interpretable Concepts in Large Generative Music Models (2505.18186) — full read

Singh (Dartmouth), Cherep, Maes (MIT Media Lab), ICLR 2026. Demo: musicdiscovery.media.mit.edu
PDF: `2505.18186v3-DISCOVERING AND STEERING INTERPRETABLE CON-_CEPTS IN LARGE GENERATIVE MUSIC MODELS.pdf`.
First application of sparse autoencoders (SAEs) to a music generator: unsupervised concept
discovery on MusicGen's residual stream, automated labeling at scale, and proof-of-concept
**activation-addition steering** that listeners reliably perceive.

## What it contains
- **Pipeline**: feed ~160k CC-licensed clips (MusicSet = MTG-Jamendo + MusicCaps + MusicBench)
  through frozen MusicGen-Small (1024d) / -Large (2048d); extract residual-stream activations at 5
  depths (~5/25/50/75/~100%); train k-sparse SAEs (k∈{32,100}, expansion factor ∈{4,32});
  filter features to an activation-rate band (fires on 1%–25% of tracks — kills dead, ubiquitous,
  and ultra-rare features); label each survivor from its top-10 max-activating examples.
- **Automated labeling**: Gemini Flash 1.5 proposes open-ended concept labels from concatenated
  audio; Essentia classifiers propose taxonomy tags; CLAP scores label↔audio alignment. Human
  study (80 raters, 400 features): Essentia tags more trusted (3.96/5) than Gemini labels (3.19/5).
  Amusing side-finding: Flash 1.5 beat Flash 2.0/2.5/Pro 2.5 on CLAP alignment.
- **Discovered concepts**: canonical (taiko drums, hardstyle techno, baroque harpsichord, rock
  guitar solos) AND coherent-but-uncodified ones (electronic "beeps and boops", single-instrument-
  single-note "texture atoms", oscillating bell-like timbres, romantic-poppy MIDI piano —
  production-practice categories with no clean theory name).
- **Layer/scale findings**: deeper layers → more interpretable features (CLAP label alignment rises
  with depth; mirrors Ma & Xia probing). Larger model → more layer-differentiated features (a probe
  predicts a feature's layer-of-origin at 50.3% for MGL vs 40.5% for MGS) — scale sharpens the
  division of representational roles across depth, it doesn't just add features.
- **Steering** (§3.7/4.6): x' = x + α·β·W_d,j — add the SAE decoder column for feature j to the
  residual stream at the hook layer, β = feature's max empirical activation, α∈(0,1]. On MGL
  mid/late layers (24/36/46): **15–35% of discovered features are positively steerable** (CLAP
  alignment to the feature's exemplars improves vs unsteered baseline, prompt+seed held fixed).
  Listening study (10×10 sets): raters matched SAE-steered audio to the steering target 66/100 vs
  17 baseline / 17 random-direction-matched-norm (χ²=48, p<.0001) — the effect is clearly audible.
- **Honest caveats they cite**: AxBench (Wu et al. 2025) — for LLMs, simple supervised baselines
  (diff-in-means, probes) often beat SAE steering; Arad et al. 2025 — SAEs steer well only if you
  select the right features. Their claim is existence, not optimality.

## What this means for us
- **Not a duplicate** of anything in SAO, and it's the *complement* of what we built: our LatCH
  heads + the DiT layer×feature activation extraction + the 21-feature×256-channel xcorr are all
  *supervised* ("do we encode X?"); this is the *unsupervised* direction ("what do we encode?").
  Our activation-dump infra (night-shift task #25) is exactly their step 1 — SAE training on top of
  it is a bolt-on, not a new pipeline.
- **The transferable prize is the steering op, not the SAEs.** Activation-addition at a DiT block
  is a training-free, per-concept steering knob — orthogonal to everything we currently steer with
  (DoRA strength, per-layer LoRA interleave, CFG, SDEdit nl, prompt arcs). One direction vector per
  concept, no adapter training. Their mid/late-layer steerability finding is a concrete place to
  start hooks in the SA3 DiT.
- **AxBench shortcut for us**: we don't need SAEs to try this. We have labeled MIR features (37
  scalar + 32 frame-level fields, DATASET_STATS.md) and the activation dataset — supervised
  **diff-in-means concept directions** (high-hardness vs low-hardness crops, high vs low onset
  density, etc.) are the cheap first experiment, and per AxBench likely the *stronger* baseline.
  Cheap follow-up: compute directions from existing dumps, inject at mid/late DiT blocks over a
  timestep window, listen.
- **The gap the paper can't answer for us**: MusicGen is autoregressive — no noise-level axis. In a
  diffusion DiT every steering direction must answer "at which denoising timesteps?" Our
  layer-feature-noise-invariance doc is directly the missing piece and an asset the paper lacks —
  features whose readout is noise-invariant are the natural candidates for timestep-robust steering
  directions.
- **Tension worth testing**: their depth story (deep = more interpretable/steerable, incl. genre
  concepts) vs our staggered-LoRA design intuition (shallow = structure first, deep = timbre lags).
  Not necessarily a contradiction (interpretable ≠ structural), but the per-layer steering
  experiments would adjudicate where style really lives in the SA3 DiT.
- Their filtering recipe (1–25% activation-rate band) and top-10-exemplar + CLAP-scored labeling
  are directly reusable if we ever do train SAEs on the SA3 dumps.
- Net: **medium-high relevance; actionable.** Verdict: keep; spawned the "concept-direction
  steering for SA3" idea + a Deep Research question handed to Kim 2026-07-11.
