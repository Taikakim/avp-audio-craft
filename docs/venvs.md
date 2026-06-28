# Venvs & the ROCm/flash-attn situation

Three Python versions → the venvs **cannot** be merged. Always call a venv by its
absolute python path. See MASTER §3 for the per-task quick table.

## Production venvs

| Repo | Python interpreter | Py | torch | Notes |
|---|---|---|---|---|
| **mir** | `/home/kim/Projects/mir/mir/bin/python` | 3.12 | ROCm 7.2 | numpy 1.26, **essentia + madmom** present. The canonical mir runtime. |
| mir (do-not-use) | `mir/.venv/bin/python` | 3.12 | — | numpy 2.x, **no essentia**, madmom silently → librosa. Avoid. |
| **stable-audio-tools** | `sat-venv/bin/python` | 3.10 | 2.10.0+rocm7.2.3 | LatCH, FusionOpt, audition. |
| **stable-audio-3** | `.venv/bin/python` | 3.13 | 2.10.0+rocm7.2.3 | SA3 inference, LoRA, pre-encode. Custom local ROCm wheels wired via `[tool.uv.sources]`. |

**Hardware:** AMD RX 9070 XT (RDNA4, **gfx1201**, 16 GB) + Ryzen 9 9900X. ROCm 7.2.x.

### uv gotchas (SA3, py3.13, custom wheels)
- **Never** change torch/Python version in SA3 — it invalidates the custom ROCm wheel set.
  PyPI flash-attn wheels are CUDA-only and useless here.
- `uv sync` strips hand-installed packages → use **`uv sync --inexact`**.
- Hand-installing flash-attn: **`--no-deps`** or it drags PyPI `triton` over the ROCm wheel.
- Missing deps seen this session in SA3 `.venv`: `dill`, `pytorch-lightning`, `wandb` (the
  trainer needs them; `pip install` into `.venv` as needed — they weren't in pyproject).

## ROCm env system

- `stable-audio-tools/rocm_env.yaml` + `stable_audio_tools/rocm_env.py` is the canonical
  config (common + `inference`/`training` profiles, `${tunings_root}` interpolation).
  SA3 mirrors it (`stable_audio_3/rocm_env.py`). mir has its **own** `src/core/rocm_env.py`.
- Applied via **`setdefault`** before `import torch` → **shell exports win.** A terminal
  that `source`d the deleted old `rocm_env.sh` silently pins wrong tunings/profile. First
  thing to check when tunings look wrong: `env | grep -iE 'tunableop|miopen|triton_cache'`.
- Tunings caches are **torch/ROCm-version-specific** (TunableOp's validator rejects
  cross-version entries, so they MUST stay separate):
  - **`~/pytorch-tunings-7.2.3`** — prod stack (torch 2.10 / ROCm 7.2.3). Canonical;
    accumulates via the training profile (TUNING=1). Has `tunableop_results0.csv` +
    `miopen/` + `triton_cache/` + `inductor_cache/`.
  - **`~/pytorch-tunings-7.14`** — experimental stack (torch 2.12 / ROCm 7.14, the
    `sa3-rocm7.13-test` venv + CK flash-attn). Persistent home for that stack; same
    substructure. Point `PYTORCH_TUNABLEOP_FILENAME` / `TRITON_CACHE_DIR` /
    `MIOPEN_CUSTOM_CACHE_DIR` / `MIOPEN_USER_DB_PATH` here when running on 2.12.
  - `~/pytorch-tunings-7.2.2` is for torch 2.9.1 and **fails** the `PT_VERSION` validator
    under 2.10 — stale.
- Profiles: inference `MIOPEN_FIND_MODE=2`; training `=6` — **but mode 6 crashes the SA3
  medium DiT** (use 2 there; see lessons-learned).

## flash-attn on ROCm — current reality

> **UPDATE (2026-06-23): native CK flash-attn is now BUILT, VALIDATED, and the recommended
> path on all three torch-2.10/2.12 ROCm venvs** (`sat-venv`, `stable-audio-3/.venv`,
> `sa3-rocm7.13-test`), which ship a **CK-backend `flash_attn 2.8.4`** for RDNA4/gfx1201
> (30–100% faster than the Triton-AMD path). It is **INACTIVE by default** — the wrapper
> auto-routes to the `aiter` Triton path unless you
> `export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE` **before `import torch`/`flash_attn`**
> (forgetting it → `No module named 'aiter'` + "flash_attn not installed" → SDPA/Triton
> fallback). Set it for *every* train and inference run. mir's own rocm-7.2 venv stays on
> Triton FA2 (`TRUE`) until the unified rocm-7.13 venv. The CK-vs-Triton "production path"
> framing and the "BUILT, NOT YET VALIDATED" status below are **superseded** — kept for
> troubleshooting context. Full recipe + verify: **`SAO/docs/flash-attn-ck-rdna4.md`** (and
> MASTER §5).

**Production path (works today):** flash-attn delegates to the **Triton-AMD backend via
`aiter`** (no compiled `.so`). SA3 uses the **varlen** path only when a padding mask is
present. The `v2.8.4.1-cktile` checkout is the consistent one installed in SA3's venv;
standard (non-varlen) FA works regardless. Escape hatches in SA3: `SA3_DISABLE_FLASH_ATTN=1`,
`SA3_DISABLE_FLASH_VARLEN=1`, `run_gradio.py --no-flash-attn / --no-flash-varlen`. FA is
only *required* for `medium`.

**Known bug:** the `fa4-v4.0.0.beta14` checkout calls `varlen_fwd(..., num_splits)` but the
pinned aiter lacks that param → `varlen_fwd() takes 20-21 args but 22 given`. Use cktile.

### Experimental: native CK (Composable Kernel) flash-attn for RDNA4

`SAO/sa3-rocm7.13-test/` — building flash-attn with the **CK backend** (compiled `fwd`/
`varlen_fwd` ops) instead of aiter/Triton, which would bypass the aiter version-skew
entirely. RDNA4 (gfx1201) needs the **WMMA** FMHA path (CK's default targets CDNA MFMA);
that work is now upstream in composable_kernel's `therock-7.13` branch
(`KernelComponentFactoryGfx12`), so the old contractor patch (`streamhpc/fmha-wmma`) is
largely obsolete.

**Status (2026-05-31): BUILT, NOT YET VALIDATED.**
- `flash_attn-2.8.4-cp313` **compiled from source + installed** (`build_fa_ck.log`).
- On a **separate experimental stack**: `amd-torch 2.12.0+rocm7.14.0a` + gfx1201 device
  wheels — **NOT** the production 7.2.3 stack.
- Numerical validation + benchmark vs the Triton backend (scripts `02_flash_attn_varlen_smoke`,
  `03_sa3_generate`, `04_latch_train_step`, `05_compile_latch`) **pending** (was blocked on
  GPU/VRAM held by the SA3 encode; freed 2026-05-31). **"Compiles" ≠ correct or fast** —
  do not adopt until validated.
- Build recipe (from issue #161 / upstream): point `csrc/composable_kernel` at a mainline
  CK rev with `KernelComponentFactoryGfx12`, add `gfx1201` to setup.py arch allow-list,
  build with `GPU_ARCHS="gfx1201" FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE`. Likely no system
  ROCm upgrade needed (CK compiles from source into the extension). Full detail: SA3 memory
  `rocm-flash-attn-env.md`.
