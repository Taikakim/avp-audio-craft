# LatCH — Latent-Control Heads

**What:** a small bidirectional transformer that predicts a per-frame MIR feature
(bass RMS, spectral flatness, onset density, key, …) from a *noisy* diffusion latent.
At inference it's used as **training-free guidance (TFG)**: backprop the head's
prediction-vs-target error into the latent and nudge it, steering generation toward a
requested feature curve — without retraining the base model. (Novack et al.,
"Low-Resource Guidance for Controllable Latent Audio Diffusion".)

**Spans all three repos:** mir extracts the features (targets); stable-audio-tools trains
the heads and is the research hub; both SAT and SA3 run LatCH-guided sampling at inference.

## Data flow

```
mir features ──► targets ──► train head ──► guided sampling
  .INFO /         per-crop DB (fixed crops)    SAT: scripts/train_latch.py
  timeseries      OR whole-track npz           SA3: stable_audio_3/inference/latch_guided.py
                  (arbitrary windows)
```

- **Targets, two stores** (MASTER §2/§4): legacy per-crop `mir/data/timeseries.db` (fixed
  crop↔track mapping, 256 frames @ 21.53 Hz); whole-track `Kosmos/timeseries/*.npz`
  (100 Hz, sliced+resampled to any window/T via
  `stable-audio-tools/scripts/whole_track_target_source.py`).
- **Two latent grids** — heads are grid-specific. SAO-Small: 64-d @ 21.53 Hz, T=256. SA3:
  256-d @ 10.767 Hz, T=4096. A head trained on one grid does not transfer to the other.

## Architecture & training

- Head: `dim`/`depth`/`heads` transformer with RoPE + an FA-priority SDPA. **t-injection**
  ∈ {concat (legacy, T+1), film, **adaln_zero** (DiT-style per-block modulators, the
  quality winner)}. adaln_zero also enables the inference-time `TimeConditioningCache`.
- **Ship recipe** (validated, LATCH_RESULTS §21): SF-NorMuon optimizer + d256/dp4 + bf16 +
  `--compile` + adaln_zero. Full numbers + the sweep in `training-findings.md` and
  `LATCH_RESULTS.txt`.
- **FusionOpt** (`stable_audio_tools/training/fusion_opt.py`): bifurcated
  Muon(NS5)+MONA+KL-Shampoo (spectral 2-D matrices) + ScheduleFree-AdamW (scalar params).
  Production subset = `ns5,normuon,sf` ("SF-NorMuon"); full set rarely worth +50 % time.
  Design: `docs/FUSION_SHAREABLE.md` (in SAT).

## SA3 status (phase 1)

Ported to SA3, verified controlling bass RMS on `small-music-base`: requested −50/−30/−10 dB
→ measured −58.6/−26.6/−15.0, **corr 0.965, monotonic** (10 ep, 3000 same-s crops, gain 8,
window [0.4,1.0], 50-step Euler, **fp32 guidance**). Branch `latch-sa3-phase1`. SA3 LatCH
model code mirrors SAT's — keep them in sync (note merges in WORKLOG).

## Whole-track timeseries fields (the LatCH target menu)

20 fields @ 100 Hz per track (+ `relative_position_ts` on SA3 crops): beat/downbeat
activations (raw madmom soft probs), onset envelopes (full + per stem), RMS (4 bands +
per stem), spectral (flatness/flux/skew/kurtosis), HPCP (12-ch). Producer:
`mir/src/spectral/whole_track_timeseries.py`.

## Known dead ends (don't retry)

beat-activations head **on SAO-Small/SA1** (waveform-diff confirmed not a usable control)
— but this is **latent-specific, NOT a universal dead end**: on SA3 SAME, `beat_activation`
probes STRONG (R²=0.62, 2026-06-01), so it's a live candidate there; `beat_weighted`
smoothing (worse than plain gaussian); scaling dim past 256. (LATCH_RESULTS §9, §2, §3/§22.)

## SA3 medium = a SEMANTIC latent (SAME) → the controllable menu MOVED (2026-05-31)

SA3's autoencoder is **SAME (Semantically-Aligned Music autoEncoder)** — a transformer AE
(patching + Transformer-Resampling-Blocks, differential attention + RoPE), **deterministic**
(soft-norm bottleneck, not variational — closer to a Representation Autoencoder), 4096×
downsampling → 256-dim @ 10.76 Hz, frozen during diffusion training. SAME-S (108M, small),
**SAME-L (852M, medium/large = our latents)**. Trained with 5 losses: multi-res STFT recon,
relativistic GAN, **diffusion-alignment** (jointly-trained DiT pushes latent geometry to be
diffusion-smooth → also makes LatCH/TFG gradients well-behaved), **semantic regression**
(linear chroma + ILD heads — chroma is literally supervised in), **contrastive alignment**
(critic on latent↔audio↔**T5Gemma-text** triplet → latent organized around text-describable
content). Paper §2.1, `stable-audio-3/`.

**Consequence:** the latent is semantic + recon-faithful + diffusion-smooth, NOT a linear
image of low-level acoustics. So LatCH decodes well for semantic/high-level features and
fails for low-level ones the compression discards. **Ridge decodability probe** (clean
latent, track-disjoint, §1 method; `/tmp/ridge_probe.py`), test R² over all 21 latents_sa3
features (N=400, SEED=0):

  STRONG : spectral_flux 0.90, spectral_flatness 0.78, beat_activation 0.62,
           spectral_skewness 0.61, onset_envelope_drums 0.57, onset_envelope 0.56,
           rms_drums 0.54
  viable : hpcp 0.48 (SAME supervises chroma → that's why), spectral_kurtosis 0.33,
           downbeat_activation 0.31
  weak   : rms_other/bass 0.21-0.24, rms_energy_air/mid 0.15-0.16, onset_other/bass 0.14
  DEAD   : rms_energy_bass 0.10, rms_energy_body 0.08, relative_position 0.03,
           onset_envelope_vocals -0.04, rms_vocals -0.08

**Headline shifts vs SAO:**
- `rms_energy_bass` was the SAO FLAGSHIP (corr 0.965) but is DEAD on SAME (0.10) — SAO's
  acoustic conv-VAE linearly exposed band energy; SAME buries it for semantics. The
  per-band-RMS heads are mostly gone; per-STEM (drums) + spectral + harmony are the menu.
- **relative_position is dead** (local probe 0.03, global-pooled 0.08, sanity flux 0.98) —
  position is a whole-track narrative property the local latent can't carry, and the target
  is ill-posed from content. Don't ship the GUI position slider.
- **`beat_activation` is STRONG on SAME (0.62), reversing the SAO-Small "beat dead" call**
  (§9 — different latent). SAME's contrastive/semantic training apparently encodes metrical
  structure linearly (likely riding partly on the same drum-transient signal as
  onset_drums 0.57 / rms_drums 0.54); downbeat viable (0.31). Both are now **live control
  candidates** — decodability predicts controllability (2026-06-01 gain sweep) — pending a
  closed-loop verify, with the caveat that a sparse spike-train target may steer differently
  than a smooth feature.

**Better-fit control directions for a semantic latent** (vs hand-crafted MIR heads):
(1) target only the decodable semantic features; (2) use SAME's built-in chroma + **ILD**
(stereo-image!) linear readouts directly; (3) **text-aligned latent steering** (CLIP-style
direction pushes — but SAME aligns via a critic, not a shared linear space, so needs a
learned text→latent bridge); (4) division of labour: text for "what", LatCH for "when/how-
much over time" of the decodable temporal features.
