---
name: environment
description: "venv, AMD/ROCm hardware, and the rocm_env.yaml environment system (replaces rocm_env.sh)"
metadata: 
  node_type: memory
  type: project
  originSessionId: ccd33273-2ad9-4e1a-a571-5a74da061b46
---

- **venv:** `/home/kim/Projects/SAO/stable-audio-tools/sat-venv` (Python 3.10). Activate it, or call `sat-venv/bin/python` directly.
- **Hardware:** AMD RX 9070 XT (gfx1201) + ROCm 7.2.x. **Torch 2.10.0** ROCm wheel (upgraded from 2.9.1 on 2026-05-26).

**ROCm env is now config-driven (changed 2026-05-25):**
- All HIP/MIOpen/TunableOp/Triton vars live in `rocm_env.yaml` (repo root) — single source of truth, with `common` + `inference`/`training` profiles. `${tunings_root}` interpolation.
- `stable_audio_tools/rocm_env.py` reads it and applies a profile via `setdefault` (shell exports still win). The package `__init__` applies the **inference** profile on `import stable_audio_tools`, *before* any torch-importing submodule.
- `scripts/train_latch.py` loads `rocm_env.py` **standalone via importlib** (so the package `__init__`/torch don't run first) and applies the **training** profile.
- **`rocm_env.sh` was deleted** — no more manual `source`. Override the YAML path with `SAT_ROCM_ENV_YAML`, relocate caches via `tunings_root`.
- Why a standalone load in the trainer: env vars (allocator, TunableOp, MIOpen) only take effect *before* the first `import torch`, and importing the package pulls in torch.

**Tunings dir:** `/home/kim/pytorch-tunings-7.2.3` is now canonical (`tunings_root` in `rocm_env.yaml`), for **torch 2.10.0**. The old `-7.2.2` dir was for torch 2.9.1; its `tunableop_results0.csv` now fails TunableOp's validator under 2.10.0 (`PT_VERSION expect 2.9.1 to match 2.10.0`) — so 7.2.3 starts fresh and re-tunes on the first training run (`TUNING=1`). All six `latch_train*.yaml` configs had their hardcoded `amd:` blocks removed (2026-05-26) so they defer to `rocm_env.yaml` — no per-config path drift.

**Profiles:** inference = `MIOPEN_FIND_MODE=2` (FAST), `TUNABLEOP_TUNING=0`. training = `MIOPEN_FIND_MODE=6` (TRUST_VERIFY), `TUNABLEOP_TUNING=1`.

**GOTCHA — shell exports override the YAML (`setdefault`).** If `env | grep -iE 'tunableop|miopen_|triton_cache|pytorch-tunings'` shows values, THOSE win over `rocm_env.yaml` (the loader only fills *unset* vars). A terminal that `source`d the old `rocm_env.sh` (or predates its deletion) silently pins **7.2.2** AND inference values (`TUNING=0`/`FIND_MODE=2`) — which also disables tuning even in training runs. **First thing to check when a tunings path/version looks wrong: the live shell env.** Fix = fresh terminal (rc files are clean) or `unset` the vars. (Hit 2026-05-26 after the torch upgrade.)

**Triton needs a C compiler** to JIT the flash-attn AMD kernel; the interactive shell has `/usr/bin` on PATH so it's automatic (only a restricted sandbox PATH needs `CC=/usr/bin/gcc`).

`train.py` monkey-patches `audio_spectrogram_image` to a no-op PIL image to avoid a ROCm/matplotlib segfault.

See [[model-and-data]], [[latch-overview]].
