# SAME: A Semantically-Aligned Music Autoencoder (2605.18613v1) — deep-read

Parker, Evans, Carr, Zukowski, Taylor, Rice, Pons (Stability AI), May 2026.
PDF: `2605.18613v1 SAME- A Semantically-Aligned Music Autoencoder.pdf`.
**This is OUR latent space** — SAME-L (852M) produces the 256-dim / 4096× / 10.76Hz
latents that `latents_sa3` and everything downstream runs on.

## What it contains
- **Architecture:** patching pretransform (P=256 → 256× downsampling, stereo interleaved
  into 512-d patch vectors) + Transformer Resampling Blocks (S=16 → total 4096×).
  Pre-norm blocks with differential attention, QK-norm, RoPE, DyT (tanh) normalisation,
  sinusoidal activations in the decoder's last 8 layers. SAME-L: dim 1536, 12+12 layers,
  sliding-window attention. SAME-S (108M, CPU): chunked attention + midpoint shift,
  distilled from SAME-L (cross-decoder-compatible latents).
- **Soft-normalisation bottleneck, NOT a VAE:** learnable per-channel affine + running-std
  division; dual-axis KL-like reg (per-timestep + 0.4×per-channel zero-mean/unit-var).
  **Gaussian noise added to latents at decode during training (5e-2; 1e-3 at inference)**
  → the decoder is noise-robust by construction.
- **The semantic shapers (the reason our latents behave):**
  1. **Generative alignment loss** — a 4-layer/768-d flow-matching DiT trained jointly ON
     the latent space, gradients flowing into the encoder → latent geometry pre-shaped
     for diffusion modelling.
  2. **Semantic regressors** — **3-band octave chroma, octave centres 1/5/9, widths
     1.0/1.5/1.0, 128 bins each = 384-d** (targets from an FFT-8192 spectrogram; the SAME
     octave centres ALSO appear as 3 chroma *discriminators* §3.2.2 → band-chroma pressed in
     twice) + interaural level difference, each decoded by a SINGLE 1×1 conv → **linear
     decodability is trained in, not emergent.**
     ⭐ **Conditioning implication (Kim + C, 2026-08-11):** the register-separated chroma we'd
     want as a melody/movement conditioner is ALREADY a trained-in LINEAR readout of our latent
     — oct1≈bass / oct5≈harmony / oct9≈melody. So (a) a LatCH chroma adapter is near-free — lift
     the SAME 1×1 conv weights directly, no training; (b) a per-band DFT-magnitude of the 128
     bins gives register-resolved **transposition-INVARIANT** movement = the anti-overfit
     bottleneck for Zach's melody prepend-cond; (c) it grounds #59's "melody subspace" in the
     oct-9 regressor's weight rows. Chroma is a property of the clean latent z0 → operates in
     x0-space (fits #59 / JLT 2605.27102).
  3. **Contrastive latent alignment** — 4-layer critic matches (latent, wavelet audio
     features, T5Gemma text emb) triplets → text semantics pressed into the latent.
  Ablation: these losses are why soft-norm beats VAE at 4096× (MuQEval 3.87 vs 3.19,
  FAD-CLAP 0.576 vs 0.724); soft-norm alone regresses.
- Reconstruction ≈ ε-ar-VAE quality at 2× speed (SAME-L RTF 561; SAME-S 2069, CPU-able);
  MUSHRA best-in-test 82.2.

## What this means for us (the paper ↔ our stack)
- **Latent arithmetic is friendly by design**: dual-axis normalisation + decoder noise-
  robustness explain why latent slerp/crossfades/bridges decode cleanly, and why LatCH
  linear probes work — chroma is *literally trained* to be one linear map away.
- **Localization caution (vs TADA 2602.11910):** TADA's semantic bottleneck was found on
  Stable Audio Open's acoustics-only conv-VAE (64-d, 2048×). SAME latents already carry
  linear semantics — SA3's DiT may need less internal semantic construction, so the
  bottleneck may be shallower/shifted/diffuse. Localize on SA3; don't transplant {12,13}.
- **A latent-space steering lane below the DiT**: concept edits by latent arithmetic are
  plausible (the space is text-aligned + linearly structured + decode-robust).
- Encoded-zero-waveform = the canonical silence latent (matches our silence.npy fix).
