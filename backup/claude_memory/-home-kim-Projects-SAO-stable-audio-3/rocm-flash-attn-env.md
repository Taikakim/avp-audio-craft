---
name: rocm-flash-attn-env
description: "Kim's AMD/ROCm stack for Stable Audio 3 (RDNA4 gfx1201) and the flash-attn/aiter varlen situation + CK-on-RDNA4 lead"
metadata: 
  node_type: memory
  type: project
  originSessionId: a76bbe73-5250-4a70-accd-5324dfe52aa8
---

Kim runs Stable Audio 3 on **AMD, ROCm — not CUDA**. Hardware: **RX 9070 XT, gfx1201 (RDNA4)**,
ROCm 7.2.3. The torch stack is custom **local ROCm wheels** in the SA3 repo root
(`torch`/`torchaudio`/`torchvision`/`triton` all `2.10.0+rocm7.2.3...`, cp313), wired via
`[tool.uv.sources]`; `torchcodec` is built from `~/Projects/SAO/torchcodec`. Python 3.13.

**Why it matters / how to apply:**
- **Never suggest changing torch or Python version** — it invalidates the whole custom ROCm wheel
  set. PyPI prebuilt flash-attn wheels are CUDA-only and useless here.
- `uv sync` strips manually-installed packages (flash-attn, etc.); always use **`uv sync --inexact`**.
  When hand-installing flash-attn, use **`--no-deps`** or it drags PyPI `triton` over the ROCm wheel.
- The repo has a YAML-driven ROCm env system: `rocm_env.yaml` + `stable_audio_3/rocm_env.py`
  (applies `inference`/`training` profiles before torch import; sets TunableOp, MIOpen, Triton cache,
  `FLASH_ATTENTION_TRITON_AMD_ENABLE=TRUE`).

**flash-attn on ROCm reality:** flash-attn delegates to the **Triton-AMD backend via `aiter`** (no
compiled `.so`; `flash_attn_gpu` = `aiter...flash_attn_triton_amd.flash_attn_2`). SA3 only uses the
**varlen** path when a padding mask is present.
- The `fa4-v4.0.0.beta14` checkout (`~/Projects/SAO/flash-attention`) is **internally inconsistent**:
  its wrapper calls `varlen_fwd(..., num_splits)` but the pinned aiter `b4b7516` (and every aiter
  release tag) lacks that param — only aiter `main` has it. → varlen crashes:
  `varlen_fwd() takes 20-21 positional args but 22 were given`.
- The `v2.8.4.1-cktile` checkout (`~/Projects/fa2-test/flash-attention`) is **consistent** (21-arg
  varlen, no `num_splits`) and is what's installed into the SA3 venv. Standard (non-varlen) flash
  works regardless — that's what image workflows use.
- Escape hatches added to SA3: env `SA3_DISABLE_FLASH_ATTN=1` (all FA off → SDPA) and
  `SA3_DISABLE_FLASH_VARLEN=1` (keep standard FA, drop only varlen); `run_gradio.py` flags
  `--no-flash-attn` / `--no-flash-varlen`. FA is only *required* for `medium`; small models don't need it.

**Lead (noted 2026-05-27, not yet done):** the **CK (Composable Kernel)** flash-attn *can* be
compiled for **RDNA4/gfx1201** — ROCm/flash-attention issue #161. A CK build yields compiled
`fwd`/`varlen_fwd` ops, bypassing the aiter/Triton `num_splits` version-skew entirely. Likely the
real fix vs. the cktile-Triton workaround; worth trying when there's time. See [[latch-sa3-phase1]].

Concrete recipe from a user in issue #161 (proof-of-concept, NOT official):
- Build command: `GPU_ARCHS="gfx1201" FLASH_ATTENTION_TRITON_AMD_ENABLE="FALSE" python setup.py install`
  (Triton OFF forces the CK path; builds compiled kernels from source — long.)
- Patch essentials:
  - Point the `csrc/composable_kernel` submodule at branch **`streamhpc/fmha-wmma`** (commit
    `6ac2092d`) instead of `amd-master`. This is the actual enabler — an unmerged contractor branch
    adding a **WMMA** FMHA path (RDNA's matrix ISA; CK's default FMHA targets CDNA MFMA/XDL).
  - `setup.py`: add `gfx1201` to `allowed_archs`; pass `--targets gfx12` to CK's
    `01_fmha/generate.py`; add defines `-DCK_USE_WMMA -DCK_TILE_USE_WMMA -DCK_USE_WMMA_FP8
    -DCK_USE_OCP_FP8`.
  - `mha_fwd.cpp` / `mha_varlen_fwd.cpp`: add `nullptr` args to match the WMMA branch's changed
    `fmha_fwd_args` signature (cu_seqlen / seqstart_padded pointers).
  - (The PoC also hardcodes `sccache` compiler launchers — drop those; user-specific.)

**Why AMD didn't ship it by default (as of the streamhpc PoC):** depended on an unmerged third-party
CK branch; RDNA4 WMMA is a separate kernel path from the tuned CDNA one; consumer RDNA is best-effort
vs Instinct/CDNA. **"Compiles" ≠ correct or fast** — always numerically validate + benchmark vs the
Triton-AMD backend before trusting a CK build.

**UPDATE (2026-05-31): CK gfx1201 build works, verified end-to-end.** Test venv at
`~/Projects/SAO/sa3-rocm7.13-test/.venv`. **Concrete reproducible recipe:**

1. **Torch + ROCm + triton** via TheRock multi-arch nightly:
   ```bash
   uv pip install --index-url https://rocm.nightlies.amd.com/whl-multi-arch/ \
     "torch[device-gfx1201]" "torchvision[device-gfx1201]" torchaudio
   ```
   → `torch 2.12.0+rocm7.14.0a`, `triton 3.7.0+rocm`, `rocm-sdk-device-gfx1201`. Use only `--index-url`
   (NO `--extra-index-url pypi` — uv's resolver will pick PyPI CUDA torch over rocm torch).

2. **flash-attention CK source**: clone `ROCm/flash-attention` branch `rdna_fmha_gfx1100_gfx1201`
   (gfx1201/gfx1100 allowed_archs + auto `-DCK_USE_WMMA -DCK_TILE_USE_WMMA=1` for gfx12). But this
   branch's `csrc/flash_attn_ck/` glue is older than the CK rev it pins (`08792e0`). **Replace 3 files
   from `rocking/update_ck` branch** before build (the rdna branch never got the CK API alignment
   commit `d81a98630 "Add sink_ptr/d_sink_ptr to fmha_bwd_args"`):
   - `csrc/flash_attn_ck/mha_bwd.cpp`
   - `csrc/flash_attn_ck/mha_varlen_bwd.cpp`
   - `csrc/flash_attn_ck/flash_common.hpp` (adds `is_gfx1x_arch()`, `check_gfx1x_bwd_supported()`)
   ```bash
   for f in mha_bwd.cpp mha_varlen_bwd.cpp flash_common.hpp; do
     gh api "repos/ROCm/flash-attention/contents/csrc/flash_attn_ck/$f?ref=rocking/update_ck" \
       --jq '.content' | base64 -d > csrc/flash_attn_ck/$f
   done
   ```
   Also regenerate `flash_common_hip.hpp` by sed-renaming the `.hpp` includes (`flash_common.hpp`→
   `_hip.hpp`, `mask.hpp`→`mask_hip.hpp`, etc.) and prepending the hipify banner.

3. **Build** (long — 2397 CK kernel files, MAX_JOBS=6 ≈ 6 cores → ~70-80 min on Ryzen 9 9900X):
   ```bash
   GPU_ARCHS=gfx1201 FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE MAX_JOBS=6 \
     uv pip install --no-build-isolation --no-deps -v .
   ```
   `--no-deps` is critical — otherwise pip picks up PyPI triton 3.5.1 and clobbers the ROCm triton.
   Each hipcc → 2 clang-22 processes; MAX_JOBS=N uses 2N cores.

4. **Runtime use**: set `FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE` BEFORE `import flash_attn` (or the
   Python wrapper auto-routes to aiter on HIP, and aiter isn't installed in this test venv).

5. **Verified results (2026-05-31, gfx1201/RX 9070 XT):**
   - varlen smoke: 426 ms first call, output fp16 finite, max abs diff vs SDPA = 2.89e-04
   - SA3 small-music-base generation: warmup 88 s (TunableOp+MIOpen tune), cached 0.23 s (383× speedup)
   - LatCH 1-step training w/ FusionOpt (SF-NorMuon): warmup 4.4 s, cached 21 ms
   - torch.compile on LatCH head: eager 3.18 ms, compiled 2.04 ms (1.56×), max diff 2.4e-07

6. **TunableOp tunings cache**: use a SEPARATE directory from your main SA3 venv (torch 2.10 / ROCm
   7.2.3). The validator in this 2.12/7.14 venv will reject the 7.2.3 tunings *and* TUNING=1 would
   overwrite the file. Test setup uses
   `PYTORCH_TUNABLEOP_FILENAME=~/Projects/SAO/sa3-rocm7.13-test/tunings/tunableop_results0.csv`
   and matching `TRITON_CACHE_DIR` / `MIOPEN_*` subdirs.

7. **Runtime dep install for the test venv** (after the torch install): from PyPI with `--no-deps` to
   protect the TheRock stack:
   ```bash
   uv pip install --index-url https://pypi.org/simple/ --no-deps \
     tqdm einops einops-exts safetensors "tokenizers>=0.22.0,<=0.23.0" transformers soundfile \
     librosa scipy psutil pyyaml huggingface-hub httpx httpcore h11 anyio sniffio audioread joblib \
     decorator lazy-loader msgpack pooch platformdirs scikit-learn soxr standard-aifc standard-chunk \
     standard-sunau threadpoolctl llvmlite numba cffi requests certifi charset-normalizer urllib3 \
     idna pillow matplotlib pandas accelerate
   uv pip install --no-deps -e /home/kim/Projects/SAO/stable-audio-3
   uv pip install --no-deps -e /home/kim/Projects/SAO/stable-audio-tools
   ```
   Note: transformers 5.9 wants `tokenizers<=0.23.0`, so pin tokenizers explicitly.

**Original context (kept for reference) — UPSTREAMING:** WMMA FMHA work is now first-class in
mainline composable_kernel on the **`therock-7.13`** branch of `ROCm/rocm-libraries`
(`projects/composablekernel/example/ck_tile/01_fmha/codegen/`):
- `ops/fmha_fwd.py` has a kernel guard `defined(__gfx1200__) || defined(__gfx1201__) || ...`, a real
  `KernelComponentFactoryGfx12(arch=ArchTrait("gfx12"))`, and `if target.startswith("gfx12")` dispatch.
- gfx12/wmma present across fwd, bwd, fwd_splitkv, appendkv, batch_prefill, pagedkv_prefill.
So the contractor patch is largely obsolete. Cleaner path:
1. Point flash-attention's `csrc/composable_kernel` submodule at a **mainline CK rev that has
   `KernelComponentFactoryGfx12`** (the 7.13 one does) + add `gfx1201` to setup.py arch allow-list +
   build with `GPU_ARCHS="gfx1201" FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE`.
2. **Likely no ROCm upgrade needed** — flash-attn's CK backend compiles CK *from source* into its
   extension, so what matters is the CK submodule source revision, not the system ROCm (7.2.3's
   toolchain can codegen gfx1201). Match the flash-attn `csrc/flash_attn_ck` glue to the CK API rev used.
Note: ROCm 7.13.0-preview release notes (2026-05-15) state official FA/FMHA for **RDNA 3**; RDNA 4
(gfx1201) FA isn't explicitly called out in the notes even though the CK codegen supports it — verify
the FMHA supported-arch matrix before assuming a 7.13 *prebuilt* flash_attn covers gfx1201.
