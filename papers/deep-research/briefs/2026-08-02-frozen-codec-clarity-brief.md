# Gemini deep-research brief — recovering high-frequency clarity DOWNSTREAM of a FROZEN small-latent audio codec

*(CONTINUITY 2026-08-02, for Kim to pass to Gemini. Fact-dense, anchored in OUR
measurements so answers stay grounded and falsifiable. Paste whole as the query.)*

## Framing — what we do NOT want
We have already read three good survey passes on audio-clarity / phase / anti-aliasing, and
we have the Stable Audio 3 + SAME papers (arXiv:2605.17991, 2605.18613). **Do not restate
the SAME architecture, the phase-wrapping problem, IFGD, BigVGAN/AMP, or the generic
LDM pipeline — assume all of it.** We need DECISION-GRADE answers to the questions those
surveys left open, under one hard constraint they mostly ignored: **the codec is FROZEN.**
We do not and will not retrain SAME. Every proposed intervention must be classified as
either (a) requires retraining the autoencoder/codec → **disqualified for us**, or (b) a
downstream / bolt-on / diffusion-side change we can actually deploy.

## Our measured ground truth (do NOT re-derive; use as the anchor)
- SAME-L latent: 256-ch @10.77 Hz, 4096×, stereo, **frozen**. Diffusion is a rectified-flow
  DiT (medium, 1.4B) trained on top.
- **Round-trip (encode→decode) codec ceiling, measured by us:** >8 kHz magnitude retention
  0.925 but **phase coherence 0.045 (near-random)**; air-band (≈8–16 kHz) envelope-corr 0.54,
  crest 1.81, spectral-flatness Δ +0.038. For comparison on the SAME clips: **128 kbps MP3
  air-band env-corr 0.97; 320 kbps 0.997.** → the treble/"clarity" ceiling is the
  codec+latent, NOT the diffusion model. This is our central problem.
- Phase is stored in the latent as approximate 2-plane SO(2) rotations up to ~7 kHz
  (sample-shift + circular-roll probes); band-dependent phase-accuracy nulls at ~5.2 / 6.7 /
  10.5 / 15.5 kHz; mean phase accuracy above 7 kHz ≈ 0.58.
- Latent covariance: ~786× anisotropic, 1/f slope α≈−1.12, GOE level-repulsion r=0.526,
  and **188/256 eigendirections lie BELOW the velocity-target unit-noise floor** (i.e. the
  velocity/flow target's isotropic floor swamps the low-variance directions — which are the
  HF/detail directions).
- We are training a supervised **audio→audio Snake-conv post-net** (~2.5M params, full
  resolution, no up/downsampling) mapping SAME-decoded audio → original. Planned arms: ADAA
  anti-aliased SnakeBeta; IF+GD phase-derivative loss.
- Compute: one consumer GPU + LUMI (MI250X) bursts. Corpus: electronic/psytrance, highly
  homogeneous (caveat: our "low-variance directions" are partly corpus-conditioned).

## Questions (real citations only; a confirmed GAP is a valuable answer)

**Q1 — The information question (the crux). Restoration vs generation.**
When a codec has *discarded* high-band phase coherence at ENCODE (our >7 kHz phase-coh
0.045), is that coherence RECOVERABLE post-hoc, or only plausibly HALLUCINATED? Separate,
with measured audio evidence: (i) deterministic restoration (info still present, recoverable
by a regression post-net) vs (ii) generative synthesis (info absent → must be sampled).
What is the demonstrated ceiling of a regression post-net on already-decoded audio for
perceptual HF clarity, and where does a generative approach measurably exceed it?

**Q2 — Latent Bridge Models / generative bandwidth-extension on a FROZEN codec.**
Anchor: "Audio Super-Resolution with Latent Bridge Models" (arXiv:2509.17609, any-to-48/192
kHz, latent-to-latent). Does the LBM (or any latent-bridge / flow-matching SR) operate on a
FROZEN pretrained autoencoder, or does it need its own trained latent? Could an LBM-style
bridge be trained to map {SAME-decoded-degraded latent or audio} → {clean target} on OUR
frozen SAME latent, and is there evidence bridges recover phase coherence a regression
post-net cannot? Compare LBM vs diffusion-post-filter vs GAN-vocoder-refiner for the
"restore HF on frozen small latent" task specifically, with metrics (LSD, ViSQOL, MUSHRA).

**Q3 — Loss design for a RESTORATION post-net (not a codec).**
For a post-net operating on already-decoded audio whose input phase is ALREADY incoherent:
does adding IF+GD or anti-wrapping (AW-IP/AW-GD/AW-IAF) phase-derivative loss measurably
help, or does the magnitude/harmonic restoration do the perceptual work while phase loss is
inert (because the coherent phase target is unreachable from an incoherent input)? Evidence
for real/imaginary (RI) spectral loss vs phase-derivative loss vs multi-res-STFT-magnitude
in a POST-NET (as opposed to a full codec) setting. Rank by measured perceptual gain.

**Q4 — Diffusion target/schedule for a FIXED latent (audio evidence only).**
We measure 188/256 latent directions below the velocity target's noise floor. Is there
AUDIO evidence (not image-only) that x0-prediction, v-prediction, or zero-terminal-SNR
schedules measurably recover the low-variance / HF latent directions that the velocity
target swamps — for a FIXED (already-trained) latent space? Does v-pred+ztSNR improve HF
detail/dynamic range on music specifically, and by how much? Is K-RNR relevant if we are
NOT doing inversion/editing (pure text-to-audio generation)?

**Q5 — Post-hoc latent reshaping (no codec retrain).**
Channel-span masking / LAFA induce a power-law channel spectrum during codec pretraining.
Is there any POST-HOC latent transform — whitening, per-channel rescaling, a learned
reparameterization applied between encoder and DiT — that induces the power-law / improves
the DiT's HF capacity allocation WITHOUT retraining SAME? Or is this strictly a pretraining
intervention? (A firm "no, pretraining-only" is a valuable answer.)

**Q6 — Complex-valued as an affordable BOLT-ON, not a rewrite.**
Any audio result where a complex-valued POST-NET or a small complex head (Wirtinger /
Cardioid), bolted onto a real-valued frozen codec, improved phase coherence — as opposed to
a full complex-valued codec retrain? What is the smallest complex-valued intervention with a
measured phase-coherence gain on music?

**Q7 — Anti-aliasing a full-resolution post-net.**
For a post-net with NO up/downsampling (the only alias source is the nonlinearity itself),
how much does ADAA / oversampled anti-aliased Snake (2× vs 4× oversampling) actually buy in
measured HF aliasing suppression vs a raw Snake, at ~2–5M-param post-net scale? Is
anti-aliasing the activation worthwhile when there is no resampling stage?

## Anti-play-acting constraints (mandatory)
- Verifiable citations only (arXiv IDs / venues). **A confirmed gap is a valuable answer** —
  say "no audio result exists" rather than inventing one.
- Separate every claim into (a) established, (b) contested, (c) your synthesis.
- **Prefer results DEMONSTRATED ON AUDIO with measured deltas** (LSD, ViSQOL, MUSHRA, FAD).
  When a mechanism is borrowed from image/speech and UNTESTED on music, say so explicitly.
- For EVERY proposed intervention, state: **does it require retraining the frozen codec?**
  (If yes, it is disqualified for us — but still say so.)
- Flag known dead-ends and WHY. Give a FALSIFIABLE prediction + the metric that would
  confirm or refute it for our setup (frozen SAME, >7 kHz phase-coh 0.045, music).
- Do NOT restate the SAME architecture or the generic phase-wrapping/IFGD background.
