---
name: project-interpreters
description: "Which Python venv to use for the MIR pipeline — mir/ has all deps, .venv does not"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 59a68846-fc80-40ca-8060-59dc171ea761
---

The repo has multiple venvs at the project root. **Use `mir/bin/python`** for any
pipeline / feature-extraction work:

- `mir/bin/python` — numpy **1.26.4**; has essentia, librosa, madmom (working), soundfile, torch/ROCm. This is the canonical runtime.
- `.venv/bin/python` — numpy **2.3.5**; **lacks essentia** and **madmom fails to import** (numpy 2.x removed `np.float`; py3.12 removed `collections.MutableSequence`). librosa works. Do NOT use for the pipeline.
- `pitch_venv/bin/python` — pitch-shifter GUI only.

**Why it matters:** running with `.venv` silently degrades — `beat_grid.py` catches the madmom ImportError and falls back to librosa beats, and essentia features (HPCP, genre/mood/instrument) are skipped entirely. Symptoms look like missing features, not an env error.

**madmom compat shim:** `src/spectral/whole_track_timeseries.py:_patch_madmom_compat()` restores `collections.abc` names + `np.float/int/bool` so madmom 0.16.1 imports under either env. See [[whole-track-timeseries]].

**GPU stacks in `mir/` venv (verified 2026-05-27):** both work and see the RX 9070 XT:
- `tensorflow_rocm 2.20.0.dev0+selfbuilt` (cp312) — `is_built_with_rocm()=True`, lists `GPU:0`. The `libcudart`/`cuInit UNKNOWN ERROR 303` warnings on import are a harmless vestigial NVIDIA-CUDA stub probe, NOT a failure. `essentia-tensorflow` pulls TF in transitively; we only use CPU HPCP, so it's silenced via `TF_CPP_MIN_LOG_LEVEL=3` + `CUDA_VISIBLE_DEVICES=""`. Do NOT install other tensorflow_rocm wheels — would break the essentia-tensorflow ABI pairing.
- `torch 2.9.1+rocm7.2.0` (HIP 7.2) — `torch.cuda.is_available()=True`, device "AMD Radeon RX 9070 XT".
