---
name: latch-verification
description: "How to verify a LatCH head actually controls its feature (closed-loop via mir extractor), and the pluggable torch/onnx decoder + benchmark"
metadata: 
  node_type: memory
  type: project
  originSessionId: ccd33273-2ad9-4e1a-a571-5a74da061b46
---

**Principle:** measure *control*, not *change*. A broken head still changes the output (dL2 grows with gain), so dL2-vs-baseline is NOT proof. The honest test is closed-loop.

## Closed-loop control check — `scripts/latch_verify_rms.py`
For several constant target levels: generate with guidance (`return_latents=True`) → decode → run mir's **real** extractor → check measured feature tracks the requested level (correlation, monotonic).
- mir's `rms_energy_bass_ts`: `_compute_multiband_rms_ts` in `/home/kim/Projects/mir/src/spectral/timeseries_features.py` — 20–120 Hz Butterworth order-5 bandpass (`sosfilt`), per-step RMS in dB (`20·log10(rms)`), 256 bins. Import path: `sys.path.insert(0,'/home/kim/Projects/mir/src'); from spectral.timeseries_features import _compute_multiband_rms_ts`.
- **Result (ep10, gain=5, window=[0.5,1.0]):** requested −50/−30/−10 dB → measured −73/−54/−34 dB; **corr=1.000, monotonic → controls bass RMS.** Relative tracking is perfect; absolute level is offset low (calibration tunable via gain/window or target standardization).

## Pluggable decoder — `scripts/latch_decode.py`
- `make_decoder(backend="torch"|"onnx")`. **torch is the safe default** (base model's own pretransform, guaranteed to match the latent space). **onnx is opt-in** (`models/exported_model/vae_decoder.onnx`, via onnxruntime MIGraphX), degrades gracefully if missing.
- `--compare` decodes real latents with both and reports agreement.
- **ONNX validated:** matches torch decode to rel diff **0.0017** (same VAE — the exported decoder IS the base model's pretransform).
- **Speed:** ONNX ~1.36× faster decode (uncontended: torch 127.6 / onnx 93.8 ms/clip), BUT **MIGraphX recompiles ~9 min per process** (cache doesn't persist) — worth it only for a long-lived decode server / batch, not one-shot.

## Other diagnostic tools (this session)
- `scripts/latch_trajectory_probe.py` — σ/α/s_t per objective (see [[latch-sigmas-schedule]]).
- `scripts/latch_sweep.py` — gain/window bracket, dL2-vs-baseline (change, not control).
- `scripts/latch_align_check.py` — target↔latent frame alignment (verified OK).
- `scripts/latch_roundtrip_check.py` — VAE provenance via decode→encode round-trip.

See [[latch-overview]], [[latch-sigmas-schedule]].
