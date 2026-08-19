# WaveFreqAnchor — Wave-Structural Anchoring and Frequency Correction Diffusion for Training-Free Face Restoration (2608.06717v1) — deep-read

Du, Li, Wang, Li, Wang, Gao (NJUPT/BUPT/NJUST/ECNU), Aug 2026. PDF in papers/ root. **Read in full by C
2026-08-19.** Kim's framing on arrival: "face reconstruction is a bit like a2a" — yes, with the sharpening
below. An external Claude analysis Kim relayed was checked against the PDF and holds on every number.

## What it does (DDPM/DPS on a frozen unconditional FFHQ prior, no training)
- **Init** from the forward-noised observation at t_s (SDEdit-style, eq. 1), then DPS-style guided
  posterior updates with a **normalised gradient** `ḡ = ∇L / max(‖∇L‖₂, 1)` (eq. 3 — a soft clamp, only
  shrinks large gradients).
- **ASWG** (anchor-space wave-structural guidance): project x̂0|t to a low-res anchor space A(·);
  `L_pixel = ‖u_t − u_y‖₂` + **`L_wave = ‖φ(u_t) − φ(u_y)‖₂`** where φ is a FIXED untrained damped
  anisotropic wave operator: `v0 = ∇²u` (3×3 Laplacian), `U=F(u), V=F(v0)`, `ω_d = √(v_x²k_x² + v_y²k_y² −
  (α/2)²)`, `φ(u) = F⁻¹[e^{−ατ/2}(U cos ω_dτ + (V+αU/2)/(ω_d+ε) sin ω_dτ)]` (eqs. 6–8) — i.e. a fixed,
  direction-dependent, multi-scale band-pass in Fourier space with knobs τ (scale), α (damping), v_x/v_y
  (anisotropy). φ(u_y) precomputed; guidance stopped at late timesteps. Ablation (Table 4): Laplacian init +
  anisotropic propagation gives the best ID/landmark balance; isotropic slightly better landmarks, worse ID.
- **MWFI**: J-level Haar DWT of x̂0|t; keep the LL subband's predicted AMPLITUDE, **replace its Fourier PHASE
  with the observation's** (eqs. 12–14), re-noise to t, recombine with the high-frequency subbands from the
  guided update; only in a middle timestep window. Table 5: LL-only PSNR 25.03→25.84, LPIPS .156→.148.
- **SHE** (real-world only): bounded (`clip ±k`), elliptically-masked, linearly-annealed boost of the
  predicted high-frequency subbands. A **frequency-ratio router** `r_y = E1/(E3+ε)` picks one of two
  preset configurations; no trainable parts.
- **Results:** synthetic CelebA-HQ SR wins LPIPS/ID/LMD at 4–8× but loses PSNR to SubDAPS++ at every
  scale and is behind on PSNR/SSIM at 16×; **real-world (LFW/WIDER/WebPhoto) wins every metric** while
  posterior-sampling baselines collapse (DPS NIQE 11.34 on WIDER). Strength = the unknown-operator regime.
  Ablation Table 3: pixel anchor ID .553 → +ASWG .574 → +MWFI .585.

## FOR US — mine it, don't adopt it
- **a2a is the paper's REAL-WORLD branch, stronger.** In synthetic SR they know D_s; real-world they
  don't; in a2a there is no degradation operator at all — the reference is a different rendering of the
  same musical content. The recipe still transfers because it is really: (1) anchor consistency in a
  reduced space where the constraint is trustworthy, (2) keep-phase / regenerate-amplitude on the
  reliable band, (3) bounded refinement on the unreliable band — and WHERE the band split sits is the
  design decision, not part of the content.
- **ASWG = our readout-space guidance, already built** (`inference/latch_guided.py` TFG with the
  chroma-loss zoo, `chroma_guided_generator.py`, the chroma-guided sampler T2). Two stabilisers to lift:
  the soft-clamped normalised gradient, and stop-late with the window derived from OUR R²(t) curve
  (`eval/melody_r2_vs_t.py`), not theirs. Reliability weighting per band falls out of Tier-2: air gets
  weight, bass does not.
- **The genuinely new idea: the wave operator on the CHROMA PLANES.** On a 1-D time axis anisotropy is
  meaningless (collapses to a damped band-pass); on the SAME chroma `(128, T)` per band it is 2-D with
  oriented structure: rising line = diagonal ridge, sustained chord = horizontal, chord change/transient =
  vertical. With **128 bins/octave ÷ 12 = 10.667 bins/semitone and 92.9 ms frames, slope 1 bin/frame ≈
  1 semitone/second**, so `v_pitch/v_time` literally selects a glide rate: pad glide ~1 st/s (near-
  horizontal), goa 16ths at 140 BPM with ~4-st jumps ~37 st/s (near-vertical), vibrato steep+oscillating.
  Arps and pads sit at opposite ends of the orientation space — the "static bass + free melody"
  discrimination from a fixed filter with one ratio. **Build it as THREE (128,T) planes, not one (384,T)**
  (the band seams mean nothing); pitch axis is genuinely circular (FFT periodicity is physically right),
  time axis is not (pad T). Harmonics move WITH the fundamental, so ridge orientation is band-invariant →
  one anisotropy setting for all bands, and cross-band orientation agreement is itself a melody detector
  (a route to rescuing mid). Transposition-equivariant by construction; response energy is
  transposition-invariant — the "what shape of motion" complement to TIV's "what harmony".
  **Our addition the external reader missed: run it on WHITENED/demeaned chroma** — the documented
  chroma-trap (raw chroma matched≈null, identity lives in the corpus-demeaned residual; `melody_wall
  whitening`, Tier-2 2026-08-11) means a raw-plane "horizontal ridge" is mostly the genre-generic mean.
  Composes with `contour_loss.py` (1-D per pitch along time): the diagonal ridge IS the contour.
- **MWFI → temporal-phase anchoring for a2a.** DWT/FFT along the latent's TIME axis: low-frequency-in-
  time = slow structure; Fourier phase along time = WHEN events happen. Keep the reference's timing/groove,
  regenerate content — and it anchors on the one thing our latent represents robustly (rhythm is the
  noise-invariant emergent; beat R² 0.80 at L14, harmony degrades). **⚠️ This is the phase of the TEMPORAL
  FFT of the LATENT trajectory, NOT STFT phase of the waveform** (SAME is waveform-native; waveform phase
  lives inside the decoder). Risk: a hard phase swap across 256 correlated channels can go off-manifold
  — do it on reduced coordinates (top-k PCs / TIV), as a soft guidance term, or on the lowest temporal
  frequencies only. Implementable as a per-step sampler callback (sampling.py exposes {x,t,denoised}).
- **Skip SHE** (face-specific); keep the clip-±k stabiliser and the router pattern (audio analogue: key a
  preset off transient density / flatness).
- **Caveats:** DDPM/DPS — the RF port is mechanical (x̂0|t = z_t − t·v̂; re-noise z_t=(1−t)z0+tε) but a
  port; needs many steps (a "middle window") = base many-step, which is what we run; faces, 256², not audio.

## Order (cheap first, each gates the next)
1. **Survival curves under SDEdit:** encode a reference, sweep t_s, measure how much of its (a) temporal
   phase and (b) TIV survives into the output — where to put the band split. An afternoon on existing
   a2a machinery (`eval/a2a_fulltrack.py`, breathing_a2a); doubles as a trajectory-level check of
   rhythm-is-noise-invariant.
2. **Offline wave-operator test on reference chromagrams** (no diffusion): sweep (v_pitch, v_time, τ, α)
   on a handful of tracks, on whitened per-band planes; does the response separate pad / glide / 16th-arp?
   Hours, CPU, pure DSP.
3. If both pass: MWFI-style temporal-phase injection as a soft callback on reduced coordinates; `L_wave`
   on the air band as a guidance term (mid conditionally, once E1/E2 says mid's readout is trustworthy).
