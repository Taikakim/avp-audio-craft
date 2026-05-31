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
  crop↔track mapping, 256 frames @ 21.53 Hz); whole-track `Lehto/timeseries/*.npz`
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

beat-activations head (waveform-diff confirmed not a usable control); `beat_weighted`
smoothing (worse than plain gaussian); scaling dim past 256. (LATCH_RESULTS §9, §2, §3/§22.)
