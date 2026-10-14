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
    old `sa3-rocm7.13-test` venv, now `SAO/.venv`, + CK flash-attn). Persistent home for that stack; same
    substructure. Point `PYTORCH_TUNABLEOP_FILENAME` / `TRITON_CACHE_DIR` /
    `MIOPEN_CUSTOM_CACHE_DIR` / `MIOPEN_USER_DB_PATH` here when running on 2.12.
  - `~/pytorch-tunings-7.2.2` is for torch 2.9.1 and **fails** the `PT_VERSION` validator
    under 2.10 — stale.
- Profiles: inference `MIOPEN_FIND_MODE=2`; training `=6` — **but mode 6 crashes the SA3
  medium DiT** (use 2 there; see lessons-learned).

## flash-attn on ROCm — current reality

> **SUPERSEDED IN PART (2026-10-14): the "30–100% faster" claim below holds only against SDPA's math fallback or Triton FA2. Against the native SDPA of torch 2.14 CK ties on forward and is ~1.45x SLOWER on a training step. See the 2026-10-13/14 section at the end of this file.**

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

`SAO/sa3-rocm7.13-test/` (no longer on disk; superseded by `SAO/.venv` and `.venv-rocm10-amd`) — building flash-attn with the **CK backend** (compiled `fwd`/
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

## 2026-10-13/14 — AMD-index ROCm 10.1 venv, native CK vs SDPA, FP8, full-FT memory (GHOST-NOTE)

Written after a day of measurement; every number below is from `~/staging/attn-bench/` (JSONs + `trace/`
rocprofv3 CSVs) unless marked untested. Scripts: `eval/bench_attention_256.py` (ANTIGRAVITY's CK-vs-SDPA
proxy), `eval/trace_dit_step.py` (rocprofv3 workload, `--mode dit|fwd|ckraw`), `eval/bench_fp8_dit.py`,
`eval/fp8_linear.py`, `eval/render_fp8_clips.py`, `eval/bench_fullft_vram.py`.

### Native CK flash-attn vs native SDPA — the corrected picture
- **Rendering (forward only): CK = SDPA.** T=512 64.0 vs 64.3 ms, T=2048 171.9 vs 170.7 ms on the 7.14 venv;
  the 7.2.3 venv is within 3-6% either way. Forward kernels are 32 us (CK) vs 34 us (SDPA `flyc_attn_fwd`).
- **Training (backward): CK is much SLOWER.** Same DiT proxy step, T=512, 48 trainable `to_out`: **CK 293 ms vs
  SDPA 203 ms** (7.14). The whole gap is one kernel: CK `FmhaBwdDQDKDVKernel` 845 us/call (31% of all GPU time)
  vs SDPA `flyc_bwd_dkdv` + `flyc_bwd_dq` ~83 us/call. GEMMs, layer norms, copies are identical within 1%.
- **Same on every stack tried** (7.2.3/torch 2.10, 7.14/torch 2.14, AMD-index 10.1): CK step ~278-293 ms, and the
  CK .so files are three different builds, so this is the kernel, not a regression. The old "CK is 30-100% faster"
  / "2-4x" statements compared CK against SDPA's MATH fallback (CK is ~2.0-2.3x faster than math only) or against
  Triton FA2, and mostly measured the STACK (7.14 vs 2.10 ~1.66x with TunableOp on both), not the flash kernel
  (1.18x). **Unreproduced:** the 1.39x CK-over-SDPA case on torch 2.12 (that venv no longer exists).
  ⇒ the line in `CLAUDE.md`/the sections below saying CK is 30-100% faster is TRUE only against the fallback.
  Do not use CK for training backward on this card; for rendering it is harmless, not helpful.
- **Reproducing the trace:** `rocprofv3 --kernel-trace --stats -d OUT -- <venv>/python eval/trace_dit_step.py
  --attn ck|native` from a scratch cwd. A profiled process that forks deadlocks (`platform.architecture()` forks
  `file`); the script stubs it. Exit-time "corrupted double-linked list" is a known teardown segfault.

### AMD-index venv (`SAO/.venv-rocm10-amd`, py3.13, torch 2.14.0+rocm10.1.0)
Recipe that worked (index `https://stable.repo.amd.com/rocm/whl-next/`):
1. Install BOTH `amd-torch-device-gfx1201` AND the family package `amd-torch-device-gfx12-0` (the latter holds
   `aotriton.images`). Without it flash/mem-efficient SDPA fail with `hipErrorInvalidImage`; it looks like a 10.1 bug, it is not.
2. To compile anything (flash-attn): install `rocm[devel]`, run `rocm-sdk init` (expands `_rocm_sdk_devel`), and use
   `rocm-sdk path --root` as `ROCM_PATH`. The shell's `ROCM_PATH=/opt/rocm` (7.2.4) is a tripwire.
3. **torchvision must be the MATCHING build, and `pip index versions` hides it: it is a prerelease.** TheRock's
   compatibility matrix: torch 2.14 / torchaudio 2.11 / torchvision **0.29**; 2.13/0.28; 2.12/0.27; 2.11/0.26.
   torchvision declares a bare `Requires-Dist: torch`, so a mismatch (0.27/0.28 with torch 2.14) installs and
   imports, then dies with `torchvision::nms does not exist` (undefined `c10::cuda` symbol in `_C.so`). Fix:
   `uv pip install --prerelease=allow --no-deps --index-url <index> "torchvision==0.29.0a0+rocm10.1.0"`.
   (`rocm-cli`'s `install sdk --version 10.1.0 --family gfx1201` automates this check: it resolves torch, torchvision and
   torchaudio together and refuses unless all carry the same ROCm build id. Not built here yet.)
4. Resolver trouble (dctorch numpy cap, protobuf): install from a freeze with `--no-deps`.
- **As an `sat-venv` replacement (py3.10, 20 GB):** `stable_audio_tools`, its LatCH model/training modules,
  `fusion_optimiser` (editable from `/home/kim/Projects/fusion-optimiser`), torchdiffeq, torchsde, torchmetrics,
  torchlibrosa, `laion_clap` import fine; bungee: `pip install --no-deps bungee-python==0.2.1`, import as
  `from bungee_python import bungee`. NOT done: `bitsandbytes` (not functional on ROCm), `onnxruntime-migraphx`.
  UNTESTED at time of writing: a real LatCH step, `eval_latch.py`, guided generation, CLAP scoring end to end.
  **Correction (2026-10-14):** an earlier draft of this note said the training data was gone. It is not: it moved
  (Kosmos, `/run/media/kim/Kosmos/`, see MASTER §2 / ARCHITECTURE). What failed was running the WRONG script:
  `stable-audio-tools/scripts/train_latch.py` (SAO-Small) still defaults to removed Lehto/Mantu paths; the SA3
  head trainer is `stable-audio-3/scripts/latch/train_latch.py` (default `--latent-dir /home/kim/Projects/latents_sa3`).
  Kosmos is 95% full (14 GB free of 233 GB): plan any further moves accordingly.
- **Decision (Kim, 2026-10-14): keep `.venv-rocm10-amd` as THE ROCm 10.1 venv and start moving to it** (torch 2.14
  release, freshly built native CK flash-attn, sat deps). **Deleted 2026-10-14:** `SAO/.venv-rocm10` (torch 2.16
  nightly, no CK; its measurements are in WORKLOG 10-13 12:16/12:28), `SAO/sa3-rocm10-test` (torch 2.15 alpha),
  `stable-audio-tools/.venv` (empty stub), `fa2-test/flash-attention/.venv`, `Projects/torchcodec/.venv`, and the
  build leftovers `SAO/flash-attention-rocm10` and `my_wheels/rocm10.1`. **Kept:** `SAO/.venv` (7.14) and
  `stable-audio-3/.venv` (7.2.3, the parity reference: the 61k eval corpus was rendered on it and a same-seed render
  on another stack correlates 0.985-0.999, not 1.0) until a 10.1 render passes a check against that corpus.
  `stable-audio-tools/sat-venv` (20 GB) goes after guided generation passes on the amd venv (CLAP already checked:
  matched cosine 0.315 vs 0.319 on 20 clips); then ~18 docs plus `latch/eval_latch.py`, `latch_sweep.py`,
  `render_audition*.py`, `eval/clap_score.py`, `clap_trainsim.py` need their python path edited in the same session.
  The mir venv (`Projects/mir/mir`, essentia-tensorflow, madmom) stays: it cannot be merged into any of these.

- **Added to `.venv-rocm10-amd` 2026-10-14 (each dry-run first; torch, numpy, protobuf untouched):**
  `stable-audio-tools` and `sao-tooling` editable `--no-deps` (note `sao-tooling` provides the modules
  `sa3_control` and `latch`, there is NO module called `sao_tooling`; an import check by that name always fails),
  `muscriptor` editable from `/home/kim/Projects/muscriptor` WITH deps (adds only httptools, python-dotenv, uvloop,
  watchfiles, websockets), `onnxruntime-migraphx 1.27.1` (providers MIGraphX + CPU; the ~9-40 min AOT compile per
  session still applies, untested here), and the `torchcodec-0.18.0a0` wheel (was `my_wheels/rocm10.1`, deleted after install; decode,
  `torchaudio.load/save` work on torch 2.14). Verified: `muscriptor transcribe -m medium` on a 12 s clip wrote a MIDI
  (8 s, weights from the HF cache, `HF_HUB_OFFLINE=1`).

### torchcodec and ffmpeg (pointers, not repeated here)
`SAO/torchcodec/` source clone shadows the real package when python runs from the SAO root (MASTER §5); mir's
torchcodec needs the `ffmpeg8-compat` SONAME shim (MASTER §5); the multitorch demo callback needs torchcodec
(`--no_demos`, lumi-ops skill). One more trap seen today: do not benchmark from the SAO root for that same reason.

### FP8 / BF8 (RDNA4 has the instructions; `torch._scaled_mm` runs them)
- E4M3 forward / E5M2 input-gradient on FROZEN linears, dynamic per-tensor scale: **1.05-1.08x per DiT step**, not
  worth it for speed; 1.8 s vs 1.56 s for a 20 s render (slower). Waveform cosine vs bf16 for same-seed renders
  0.75-0.99 (diffusion drift decorrelates waveforms; listening is the real test; clips in `~/staging/fp8-clips/`).
- `_scaled_mm` needs contiguous operands and its output dtype must equal the input dtype (model_half is fp16).
  `-DCK_ENABLE_FP8/BF8` in the CK build are generic setup.py flags; the CK glue does not use FP8 attention.
- **FP8 does not help full fine-tuning:** it shrinks matmul operands, not weights, gradients or optimizer state.

### Full fine-tune peak VRAM, medium-base, T=512, activation checkpointing (`eval/bench_fullft_vram.py`)
| weights | optimizer | state | peak | |
|---|---|---|---|---|
| bf16 | Lion | bf16 | 10.6 GiB | fits |
| bf16 | Lion | fp32 | 13.3 | fits |
| bf16 | AdamW | bf16 | 13.3 | fits |
| bf16 | AdamW | fp32 | >14.8 | OOM |
| fp32 | Lion | fp32 | 15.0 | OOM (2nd step) |
| fp32 | AdamW | fp32 | >14.9 | OOM |
~2.2 GiB of the baseline is the text encoder + autoencoder, which a real run can keep off the card. Memory only:
untested whether plain bf16 updates at lr 1e-6 move the weights (needs stochastic rounding / compensation). T=1024 untested.

### GPU etiquette learned the hard way
`Misc/gpu_guard.sh` refuses if any process holds >512 MB; the filelock handle is re-entrant per handle (two scripts of
one handle overlapped once); resident servers (`kind=server`) can be asked to yield by DM. Serialise your own chained
runs by PID, not by lock alone.
