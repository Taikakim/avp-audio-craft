# Flash Attention 2 (CK backend) on AMD RDNA4

How to build and install `flash-attn` against AMD's **Composable Kernel** path
for **RDNA4 GPUs** (gfx1201 — RX 9070 / 9070 XT; gfx1200 — RX 9060). Verified on
**EndeavourOS / Arch** with kernel 6.x and ROCm 7.2+. Ubuntu notes near the
bottom (untested by us).

The CK build gives you **compiled `fwd` / `varlen_fwd` kernels** for RDNA4
matrix instructions (WMMA), bypassing the Triton-AMD path (`aiter` Python
wrapper) and its version-skew gotchas. As of writing it requires two surgical
patches on top of the current ROCm/flash-attention branches — they're cheap and
the build itself succeeds cleanly.

> **Status (2026-05-31).** Official AMD support for RDNA4 FA is rolling out:
> ROCm 7.13 preview ships FA for **RDNA3** in the release notes; RDNA4 codegen
> is in mainline `composable_kernel` already (the `KernelComponentFactoryGfx12`
> factory + `__gfx1201__` guards) but not yet announced as official. So for now
> the right move is: take the ROCm-maintained `rdna_fmha_gfx1100_gfx1201`
> branch + patch its glue from the `rocking/update_ck` branch.

---

## 1. Hardware + distro prereqs

You need:
- An RDNA4 GPU (gfx1201 / gfx1200). Check with `rocminfo | grep gfx`.
- Linux kernel with `amdgpu`. Any current rolling-release kernel (6.10+) works.
- A **system ROCm install** that provides `hipcc` + the AMD clang toolchain
  (the build uses the system compiler — the wheels bundle the *runtime*).

### Arch / EndeavourOS

```bash
# Two main routes — both work. Pick one.
# (a) Official repos (rocm-hip-sdk pulls in hipcc, clang, llvm, runtime libs).
sudo pacman -S rocm-hip-sdk rocm-llvm rocm-opencl-runtime rocminfo

# (b) AUR / TheRock prebuilds — sometimes newer than the repos. Either is fine
#     as long as `which hipcc` works and gives you AMD clang 18+ (22+ ideal).
```

Verify:

```bash
which hipcc                          # /opt/rocm/bin/hipcc
hipcc --version                      # HIP version 7.x; AMD clang 22.x ideal
rocm-smi --showproductname           # shows your RX 9070 / 9070 XT
rocminfo | grep -i gfx               # gfx1201 (or gfx1200)
```

Build deps (everything the flash-attn extension needs at compile time):

```bash
sudo pacman -S base-devel ninja cmake git python python-pip
# python: 3.13 (matches TheRock's wheels; see §3). Use uv (recommended) or a
# direct python3.13.
yay -S uv     # or: curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Ubuntu (untested)

Should be the same shape — install ROCm from AMD's repo per their docs
(<https://rocm.docs.amd.com/projects/install-on-linux/>), `apt install rocm-hip-sdk
rocm-llvm`, then `build-essential ninja-build cmake git python3.13 python3-pip`.
Wheels in §3 are arch-neutral (`linux_x86_64`); the build commands are the same.
The only thing likely to bite you is whether your Ubuntu ROCm is recent enough
to have a clang that generates gfx1201 code — needs AMD clang 18+, prefer 22+.

---

## 2. Create an isolated venv

Don't mix this stack with an existing torch venv. The wheels are a complete
torch + ROCm replacement (TheRock bundles its own `rocm-sdk-device-gfx1201`).

```bash
mkdir -p ~/projects/fa-rdna4-test && cd ~/projects/fa-rdna4-test
uv venv --python 3.13 .venv
# Helper for the rest of this doc:
PY=$PWD/.venv/bin/python
```

---

## 3. Install torch + ROCm + triton from TheRock

AMD's TheRock project publishes ROCm-bundled PyTorch wheels with explicit
gfx-arch extras. The nightly **multi-arch index** is the one you want:

| Index | URL | Notes |
|---|---|---|
| Multi-arch (recommended) | `https://rocm.nightlies.amd.com/whl-multi-arch/` | One wheel set, you pick the device extra (`torch[device-gfx1201]`). |
| Per-family (legacy) | `https://rocm.nightlies.amd.com/v2/gfx120X-all/` | Older layout. Works but harder to combine devices. |

```bash
uv pip install --python $PY \
  --index-url https://rocm.nightlies.amd.com/whl-multi-arch/ \
  "torch[device-gfx1201]" "torchvision[device-gfx1201]" torchaudio
```

> ⚠️ **Critical**: only `--index-url`, do NOT add `--extra-index-url
> https://pypi.org/simple/`. uv's resolver will happily pick PyPI's CUDA torch
> over the rocm wheel (pulling in `nvidia-cublas`, `nvidia-cuda-runtime`, etc.).
> Confirm what's installed with `uv pip list | grep -iE 'torch|triton|nvidia'` —
> there should be **zero** `nvidia-*` packages.

What you'll get (as of 2026-05-31):

| Package | Version |
|---|---|
| `torch` | `2.12.0+rocm7.14.0a20260529` |
| `torchvision` | `0.27.0+rocm7.14.0a20260529` |
| `torchaudio` | `2.11.0+rocm7.14.0a20260529` |
| `triton` | `3.7.0+git…rocm7.14.0a20260529` |
| `rocm-sdk-device-gfx1201` | `7.14.0a20260529` (the bundled runtime) |
| `amd-torch-device-gfx1201` | `2.12.0+rocm7.14.0a20260529` |

Verify the GPU is visible:

```bash
$PY -c "
import torch
print(torch.__version__, '|', torch.version.hip)
print(torch.cuda.is_available(), torch.cuda.get_device_name(0))
print(torch.cuda.get_device_properties(0).gcnArchName)
"
# expected: 2.12.0+rocm7.14.0a... | 7.13.60850
#           True AMD Radeon RX 9070 XT
#           gfx1201
```

The first warning you might see — `W-001h rocSHMEM Could not open libibverbs.
Disabled.` — is harmless for single-GPU workstation use (RDMA library missing).

---

## 4. Clone ROCm/flash-attention (RDNA branch)

ROCm maintains a flash-attention fork with several branches. For RDNA4 the
purpose-built one is `rdna_fmha_gfx1100_gfx1201` — only RDNA3/4 in
`allowed_archs`, auto-enables `-DCK_USE_WMMA -DCK_TILE_USE_WMMA=1` for
gfx11/gfx12 targets.

```bash
git clone --depth 1 --branch rdna_fmha_gfx1100_gfx1201 \
  https://github.com/ROCm/flash-attention.git
cd flash-attention
git submodule update --init --recursive --depth 1
# Pulls csrc/composable_kernel (~1 GB), csrc/cutlass, third_party/aiter
```

Sanity:

```bash
grep allowed_archs setup.py
# allowed_archs = ["native", "gfx1201", "gfx1100"]
grep -c "CK_USE_WMMA" setup.py
# 1 (auto-enabled for gfx11/gfx12)
git -C csrc/composable_kernel rev-parse HEAD
# 08792e0b31b936b9e7baa05fb8b03dce8c21241a   (or newer if updated upstream)
```

---

## 5. Patch the glue (upstream skew workaround)

The rdna branch's `csrc/flash_attn_ck/` C++ glue is **older than the CK
submodule it pins** — CK added `sink_ptr`/`d_sink_ptr`/seq-pointer fields to
`fmha_bwd_args` and the glue's brace-list never caught up. The build fails at
~99% with `error: type 'float' cannot be narrowed to 'ck_tile::index_t'`. The
fix lives on a sibling branch `rocking/update_ck` (commit `d81a98630` —
literally titled *"Add sink_ptr/d_sink_ptr to fmha_bwd_args to match updated CK
submodule"*). Pull three files:

```bash
# from inside the flash-attention checkout
for f in mha_bwd.cpp mha_varlen_bwd.cpp flash_common.hpp; do
  cp csrc/flash_attn_ck/$f csrc/flash_attn_ck/$f.orig 2>/dev/null
  gh api "repos/ROCm/flash-attention/contents/csrc/flash_attn_ck/$f?ref=rocking/update_ck" \
    --jq '.content' | base64 -d > csrc/flash_attn_ck/$f
done

# Regenerate the matching _hip.hpp (hipify normally does this; do it by hand
# so the build doesn't choke if your hipify version differs).
sed -E 's|flash_common\.hpp|flash_common_hip.hpp|g;
        s|mask\.hpp|mask_hip.hpp|g;
        s|fmha_fwd\.hpp|fmha_fwd_hip.hpp|g;
        s|fmha_bwd\.hpp|fmha_bwd_hip.hpp|g' \
    csrc/flash_attn_ck/flash_common.hpp \
  | (printf '// !!! This is a file automatically generated by hipify!!!\n#include "hip/hip_runtime.h"\n'; cat) \
  > csrc/flash_attn_ck/flash_common_hip.hpp
```

Verify the three `flash::` helpers and the brace-list fields are now present:

```bash
grep -E "is_gfx1x_arch|check_gfx1x_bwd_supported|ParsePhiloxCudaState" \
  csrc/flash_attn_ck/flash_common.hpp | head
grep -c "sink_ptr" csrc/flash_attn_ck/mha_bwd.cpp     # should print 2
grep -c "sink_ptr" csrc/flash_attn_ck/mha_varlen_bwd.cpp  # should print 2
```

If/when ROCm merges `rocking/update_ck` into the rdna branch this step goes
away. Track the rdna branch tip or watch for a release tag.

### 5b. Patch the Python autograd backward (TRAINING only)

The rdna branch adds a 13th forward arg (`layout`) to `flash_attn.FlashAttnFunc`
but leaves its `backward` returning only **12** gradients → **forward works, but any
backprop through `flash_attn_func` dies** with:

```
RuntimeError: function FlashAttnFuncBackward returned an incorrect number of gradients (expected 13, got 12)
```

You won't hit this on **inference** or **forward-only training** (e.g. fitting a
LatCH *head* on encoded latents — the DiT runs forward-only). You WILL hit it
training anything that backprops through the DiT's flash attention (LoRA / control
adapter). Fix = one `None` in `flash_attn/flash_attn_interface.py`,
`FlashAttnFunc.backward`:

```python
# return dq, dk, dv, None, None, None, None, None, None, None, None, None        # 12 (broken)
  return dq, dk, dv, None, None, None, None, None, None, None, None, None, None  # 13 (q,k,v + 10 non-tensor args)
```

`FlashAttnVarlenFunc` is already correct (17/17). Patch BOTH the **source** checkout
(survives a rebuild) and the installed `site-packages` copy (no rebuild needed — the
`.so` is unchanged). Verified 2026-06-18: `sa3_control` adapter training runs
end-to-end on 7.14 with CK flash after this patch.

---

## 6. Install build prerequisites (PyPI, into the venv)

```bash
uv pip install --python $PY --index-url https://pypi.org/simple/ \
  pip packaging ninja pybind11 psutil wheel setuptools
```

Pure-Python utility packages; they don't touch torch.

---

## 7. Build

```bash
GPU_ARCHS=gfx1201 FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE MAX_JOBS=6 \
  uv pip install --python $PY --no-build-isolation --no-deps -v .
```

Key flags:
- `GPU_ARCHS=gfx1201` — what setup.py reads. Use `gfx1200` for RX 9060.
- `FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE` — forces the CK path. With this
  unset, setup.py builds the Triton-AMD shim instead (skips the CK kernels you
  spent an hour compiling — the whole point of being here).
- `MAX_JOBS=N` — ninja parallelism. **Each ninja job spawns two clang
  processes** (one for the host pass, one for amdgcn). On a 12-core / 24-thread
  CPU (Ryzen 9 9900X) `MAX_JOBS=6` uses 12 threads (6 cores, leaves 6 free).
  Scale to your machine. Each clang can hit several GB of RSS during CK
  template instantiation — keep an eye on memory if you go above `MAX_JOBS=8`
  on 16 GB systems.
- `--no-build-isolation` — uses the active venv (so the build sees your TheRock
  torch headers).
- `--no-deps` — **critical**. Without it, pip pulls flash-attn's declared
  `triton` dep from PyPI (currently `3.5.1`) which **clobbers your ROCm
  `triton 3.7.0+rocm`** and breaks the whole stack. If this happens, recover
  with:
  ```bash
  uv pip install --python $PY --index-url https://rocm.nightlies.amd.com/whl-multi-arch/ \
    --force-reinstall triton
  ```

Build time: there are **~2400 CK kernel files** to compile. On a Ryzen 9 9900X
at `MAX_JOBS=6` expect **70–90 min**. Ninja is incremental — if you kill the
build (Ctrl-C the parent `uv pip install`), already-compiled `.o` files stay in
`build/temp.linux-*-cpython-*/build/` and the next run picks up where it left off.

---

## 8. Use it (the runtime knob)

The Python wrapper auto-detects HIP and routes through `aiter`'s Triton-AMD
backend unless you tell it otherwise. To use the CK kernels you just built:

```bash
export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE
```

…**before** `import flash_attn` in any Python process. In a script:

```python
import os
os.environ["FLASH_ATTENTION_TRITON_AMD_ENABLE"] = "FALSE"  # MUST be set first

import torch  # noqa: E402
from flash_attn import flash_attn_func, flash_attn_varlen_func  # noqa: E402
# flash_attn_2_cuda (your CK .so) is what flash_attn_gpu now points at.
```

If you forget the env var on a clean venv you'll see
`ModuleNotFoundError: No module named 'aiter'` — that's the wrapper falling
through to the Triton-AMD path that *would* need aiter installed.

---

## 9. Verify (varlen smoke test)

```python
# verify_fa.py
import os
os.environ["FLASH_ATTENTION_TRITON_AMD_ENABLE"] = "FALSE"
import torch, time, flash_attn
from flash_attn import flash_attn_varlen_func

print(f"flash_attn {flash_attn.__version__}, torch {torch.__version__}")
print(f"device: {torch.cuda.get_device_name(0)}")

device, dtype = "cuda", torch.float16
seqlens = [128, 96]
total, h, d = sum(seqlens), 8, 64
q = torch.randn(total, h, d, device=device, dtype=dtype)
k = torch.randn(total, h, d, device=device, dtype=dtype)
v = torch.randn(total, h, d, device=device, dtype=dtype)
cu = torch.tensor([0, seqlens[0], total], device=device, dtype=torch.int32)

torch.cuda.synchronize(); t0 = time.time()
out = flash_attn_varlen_func(q, k, v, cu_seqlens_q=cu, cu_seqlens_k=cu,
                             max_seqlen_q=max(seqlens), max_seqlen_k=max(seqlens),
                             dropout_p=0.0, softmax_scale=None, causal=False)
torch.cuda.synchronize()
print(f"varlen_fwd OK  shape={tuple(out.shape)}  dtype={out.dtype}  "
      f"finite={bool(torch.isfinite(out).all())}  {(time.time()-t0)*1000:.0f} ms")

# vs SDPA reference
q0 = q[:seqlens[0]].transpose(0,1).unsqueeze(0).float()
k0 = k[:seqlens[0]].transpose(0,1).unsqueeze(0).float()
v0 = v[:seqlens[0]].transpose(0,1).unsqueeze(0).float()
ref = torch.nn.functional.scaled_dot_product_attention(q0, k0, v0).squeeze(0).transpose(0,1)
print(f"max abs diff vs SDPA: {(out[:seqlens[0]].float()-ref).abs().max().item():.2e}")
```

Run:

```bash
$PY verify_fa.py
# expected (on RX 9070 XT):
#   flash_attn 2.8.4, torch 2.12.0+rocm7.14.0a...
#   varlen_fwd OK  shape=(224, 8, 64)  dtype=torch.float16  finite=True  ~400 ms
#   max abs diff vs SDPA: 2.89e-04
```

400 ms includes first-call codegen + autotune. Subsequent calls drop to
single-digit ms once kernels are cached.

---

## 10. Common pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| `nvidia-cublas` in `uv pip list` | Used `--extra-index-url https://pypi.org/simple/` with TheRock index, uv picked PyPI CUDA torch | Reinstall with only `--index-url` to the rocm-nightlies multi-arch URL |
| `triton 3.5.1` after a `uv pip install` | flash-attn build pulled PyPI triton because you forgot `--no-deps` | `uv pip install --index-url <rocm> --force-reinstall triton` |
| `ModuleNotFoundError: aiter` at `import flash_attn` | Forgot `FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE`; wrapper auto-routed to Triton-AMD path | Set the env var BEFORE `import flash_attn` |
| `error: type 'float' cannot be narrowed to 'ck_tile::index_t'` at ~2390/2397 | The §5 glue patches were skipped or partial | Run §5 again; verify with the `grep -c sink_ptr` checks |
| `error: no member named 'is_gfx1x_arch' in namespace 'flash'` | Same skew, different file — the `flash_common.hpp` patch is missing | Run the `flash_common.hpp` part of §5; also regenerate `flash_common_hip.hpp` |
| `urllib.error.HTTPError: HTTP Error 404` after a real compile error | Downstream noise from uv looking up build info | Ignore — fix the real `error:` lines higher in the log |
| Build OOMs / clang killed | `MAX_JOBS` too high for your RAM. Each clang can hit ~5 GB during CK template instantiation | Drop to `MAX_JOBS=4` (or 2) and retry — ninja resumes from `.o` files on disk |
| TunableOp prints version-mismatch warnings and tunes from scratch every run | Tunings CSV from a different torch / ROCm version | Use a fresh `PYTORCH_TUNABLEOP_FILENAME` for this venv; don't share with other torch installs |

---

## 11. Version compatibility matrix

What we've actually verified end-to-end (2026-05-31, RX 9070 XT):

| Component | Version | Source |
|---|---|---|
| **OS** | EndeavourOS, kernel 6.x | rolling |
| **System ROCm** | 7.2.53211 (AMD clang 22) | `pacman -S rocm-hip-sdk` |
| **Python** | 3.13.13 | TheRock requires 3.13 cp wheels |
| **torch** | `2.12.0+rocm7.14.0a20260529` | TheRock multi-arch nightly |
| **triton** | `3.7.0+...rocm7.14.0a20260529` | TheRock multi-arch nightly |
| **flash-attention source** | branch `rdna_fmha_gfx1100_gfx1201` @ `4c775d0` | github.com/ROCm/flash-attention |
| **CK submodule pin (in branch)** | `08792e0` | included as flash-attention submodule |
| **Glue patches from** | branch `rocking/update_ck` (`d81a98630`) | mha_bwd.cpp, mha_varlen_bwd.cpp, flash_common.hpp |
| **flash-attn built** | `2.8.4` (CK backend, fwd + varlen + bwd for gfx1201/WMMA) | from source per §7 |

Cross-version notes:
- The TheRock wheels are **self-contained** (bundle their own ROCm runtime via
  `rocm-sdk-device-gfx1201`). You don't need a matching system ROCm — only one
  recent enough to provide `hipcc` that targets gfx1201.
- AMD clang **18+** can codegen gfx1201; **22+** has better diagnostics. Older
  Ubuntu LTS may ship a too-old clang — install AMD's via their repo.
- A `triton` version mismatch between flash-attn's compiled CK kernels and the
  torch-bundled triton **does not matter** for the CK path (kernels are
  compiled into the `.so`, not Triton-JIT'd). It does matter for
  `torch.compile` / inductor, which is a separate concern.

---

## 12. Versions of "where to find wheels"

In case the multi-arch index moves or you want the longer story:

- **TheRock landing**: <https://github.com/ROCm/TheRock> — releases page links the
  current indexes per release.
- **Wheel index (multi-arch)**: `https://rocm.nightlies.amd.com/whl-multi-arch/`
  — has `device-gfx<N>` extras. The list of supported devices is in TheRock's
  `RELEASES.md` (or browse the index — `device-gfx1201` is "AMD RX 9070 / XT").
- **Per-family index**: `https://rocm.nightlies.amd.com/v2/gfx120X-all/` — older
  layout, still works.
- **flash-attention**: <https://github.com/ROCm/flash-attention> — branches we
  care about for RDNA4:
  - `rdna_fmha_gfx1100_gfx1201` — RDNA-only, CK build, recommended (§4)
  - `rocking/update_ck` — has the glue fix you patch in (§5)
  - `main` — has the API-aligned glue **but** pins a different CK rev; would
    invalidate all ~2400 `.o` files on a switch
  - `main_perf` — performance work, watch for landing
- **Issue to track for status**: `ROCm/flash-attention#161` — the
  CK-on-RDNA4 community thread.

---

## 13. After it works

Things this build unlocks for your project:
- `flash_attn_func` and `flash_attn_varlen_func` both fast and correct on
  RDNA4 (the varlen path was the historical block, see the SA3 worklog entries
  for the aiter-version-skew that this CK build sidesteps).
- `torch.compile` + inductor on top of TheRock 7.14 / triton 3.7 — works for
  small models (verified on a 7 M-param LatCH head; 1.5× over eager).
- A **separate** TunableOp / MIOpen / Triton cache (point them at a path under
  this venv, **don't share** with a torch 2.10 / ROCm 7.2.3 venv — the
  validator will reject the entries and `TUNING=1` will overwrite the file).

What you still need a separate fix for:
- Models that need very-recent flash-attn features (sliding window past a
  certain size, paged-kv, etc.) — check that the rdna branch's pinned CK has
  the codegen factory for it before counting on it.
- Backward pass on **deterministic** mode for gfx12 — the patched
  `check_gfx1x_bwd_supported` raises on `deterministic=True`. Train with
  `deterministic=False`.
