# DRAFT — ROCm bug report: non-deterministic results and GPU instruction-fetch page faults on RX 9070 XT (gfx1201)

*Status: draft, not filed (CONTINUITY, 2026-09-25). Evidence and history: `docs/training-findings.md` 13e.
Target: github.com/ROCm/ROCm issues (or ROCm/TheRock, since two of the three stacks are TheRock
nightlies). Before filing, do the three TODOs at the bottom — in particular, the repro must not ship our
adapter weights (they were trained on commercial music and are never published).*

---

## Title

gfx1201 (RX 9070 XT): identical PyTorch inference returns NaN / garbage after shape-changing calls, and
processes die with `GCVM_L2_PROTECTION_FAULT` from `SQC (inst)` in unrelated kernels — reproduces on
ROCm 7.2.3, 7.15-alpha and 10.1-alpha

## Summary

Running the same fixed-seed inference repeatedly in one process on an RX 9070 XT:

- The **first** call in a fresh process is always correct and bit-reproducible across processes.
- Once calls of **different tensor shapes** have run in between (batch 1 vs batch 2, a decoder pass),
  later calls with **identical inputs** return NaN, values of 1e7–1e18, or results slightly off the
  correct ones. Which call fails varies from run to run.
- Some runs abort with a GPU memory fault. The fault client is always **`SQC (inst)`**, the
  instruction cache, so the GPU is fetching *shader code* from an unmapped address. The kernel named
  in the HIP error differs every time: a hipBLASLt bf16 GEMM, a PyTorch fp32 elementwise multiply,
  `torch.cat`, `exponential_`.
- **Setting `PYTORCH_NO_CUDA_MEMORY_CACHING=1` makes it disappear completely** (bit-exact across
  every call). So it depends on device memory being *reused*, not on the arithmetic.

Our reading: something writes to, or unmaps, device memory it no longer owns, below the level of any
single library. Data buffers get corrupted, and so, sometimes, does the GPU's view of code memory.

## System

| | |
|---|---|
| GPU | AMD Radeon RX 9070 XT, gfx1201, PCI `1002:7550` rev `c0`, subsystem `e490`, VBIOS `113-1E490TX-US5` |
| Display | on the CPU iGPU (Raphael, gfx1036) since 2026-09-25; the 9070 XT is compute-only. The bug reproduces **both** ways (it also did while the 9070 XT drove the display) |
| CPU | AMD Ryzen 9 9900X |
| OS | EndeavourOS (Arch), kernel `7.2.6-zen2-1-zen`; also reproduced on `7.2.6-arch2-1` |
| Firmware | `linux-firmware-amdgpu` 20260910 **and** 20260916 (reproduced on both, rebooted after the update) |
| Device selection | `ROCR_VISIBLE_DEVICES=0` (only the 9070 XT visible to the process) |

ROCm / PyTorch stacks — **all three reproduce it**:

| PyTorch | ROCm / HIP runtime | Source |
|---|---|---|
| `2.14.0a0+rocm7.15.0a20260628` | HIP 7.14.60850 | TheRock nightly wheels |
| `2.10.0+rocm7.2.3.git1a270074` | HIP 7.2.53211 | ROCm 7.2.3 release wheels |
| `2.15.0a0+rocm10.1.0a20260822` | HIP 7.16.26332 | TheRock nightly wheels |

## What triggers it

A 1.4 B-parameter diffusion transformer (Stable Audio 3 `medium-base`, bf16) with a **DoRA adapter
applied as a live `torch.nn.utils.parametrize` parametrization** on its linear layers. On every forward
pass each adapted weight is rebuilt: `W = mag · (W0 + B·A) / ‖W0 + B·A‖` (fp32 intermediates, the
largest 12288×1536, cast to bf16). That produces a steady churn of large short-lived allocations.

- Same model, **no adapter**: deterministic on the identical call sequence.
- Same adapter **merged into the weights once** (`remove_parametrizations(..., leave_parametrized=True)`):
  deterministic and correct.
- Live adapter: fails as described, typically within 2–3 calls.

The adapter code is byte-identical to the upstream Stability AI reference implementation (checked).

## Repro (current form — see TODO 1)

`diag_dora_render_determinism.py --mode live --sdpa` (attached). It runs, in one process:

1. cfg 1 render (batch 1, 24 sampler steps, fixed seed) → records the latent std
2. cfg 7 render (batch 2) + decoder pass
3. cfg 1 render again, twice
4. `torch.cuda.empty_cache()`, cfg 1 render
5. cfg 7 render + decode, cfg 1 render

It exits 0 if every cfg 1 render equals the first bit for bit, else 1.

Typical failing output (SDPA attention path; the correct value is `0.9581015706062317`):

```
live fresh cfg1: finite 1.0000 std 0.9581015706062317
live render+decode #1 (cfg7): finite 1.0000 std 1.2034927606582642     (correct: 1.204555630683899)
live cfg1 after decode: finite 0.0000 std None                         (all NaN)
live cfg1 again: finite 1.0000 std 0.9581015706062317
live cfg1 after empty_cache: finite 1.0000 std 0.8864685297012329
live render+decode #2 (cfg7): finite 1.0000 std 1.204555630683899
live cfg1 after decode #2: finite 1.0000 std 0.9581015706062317
live: MISMATCH over 5 cfg-1 renders
```

Other runs of the same script produced stds of 7e11, 5.9e18 and 1.66e10 on the cfg 1 renders.

## A crash, as the kernel reports it

```
amdgpu 0000:03:00.0: [gfxhub] page fault (src_id:0 ring:208 vmid:8 pasid:34)
amdgpu 0000:03:00.0:  Process python pid 5386 thread python pid 5386
amdgpu 0000:03:00.0:   in page starting at address 0x00007f09a2b76000 from client 10
amdgpu 0000:03:00.0: GCVM_L2_PROTECTION_FAULT_STATUS:0x008013A1
amdgpu 0000:03:00.0:          Faulty UTCL2 client ID: SQC (inst) (0x9)
amdgpu 0000:03:00.0:          MORE_FAULTS: 0x1  WALKER_ERROR: 0x0  PERMISSION_FAULTS: 0xa  MAPPING_ERROR: 0x1  RW: 0x0
```
HIP side, same second: `Memory access fault by GPU node-1 ... on address 0x7f09a2b76000. Reason: Unknown.`
with the faulting kernel reported as `CatArrayBatchedCopy_contig`. Other crashes: `Reason: Page not
present or supervisor privilege.`, with the faulting kernel reported as
`Cijk_Alik_Bljk_BBS_BH_Bias_HA_S_SAV_UserArgs_MT128x128x32_..._ISA1201` (hipBLASLt),
`elementwise_kernel_manual_unroll<... MulFunctor<float> ...>` and
`distribution_elementwise_grid_stride_kernel<... exponential_kernel ...>`. All `from client 10` (SQC).

## What we ruled out (each tested, still fails)

| Variable | Result |
|---|---|
| ROCm/PyTorch version | 7.2.3, 7.15-alpha, 10.1-alpha all fail |
| Kernel build | `-zen` and `-arch` both fail |
| GPU firmware | 20260910 and 20260916 both fail |
| Display on the same GPU vs on the iGPU | both fail |
| Allocator mode | default and `expandable_segments:True` both fail |
| BLAS library | hipBLASLt (default) and rocBLAS (`preferred_blas_library("cublas")`) both fail |
| Attention | CK flash-attention, SDPA default, SDPA math-only, FlexAttention disabled: all fail |
| Kernel serialisation | `HIP_LAUNCH_BLOCKING=1` / `CUDA_LAUNCH_BLOCKING=1` still fail; `AMD_SERIALIZE_KERNEL=3` crashed |
| Reads of never-written memory | filling free cached memory with NaN before a call does **not** trigger it |
| The adapter maths itself | rebuilding the most-affected weight in isolation 600× is bit-exact |
| VRAM cells | a 6-pass write/verify pattern test over 11.9 GB, with GEMM load between write and verify: 0 errors |
| Unsafe tensor ops in our code | none in the render path (`as_strided`, `set_`, `untyped_storage`, `data_ptr`, C++ extensions) |

**The only thing that removes it: `PYTORCH_NO_CUDA_MEMORY_CACHING=1`.** A per-layer checksum trace
(exact process vs normal process) shows the first divergence at the rebuilt adapter weight of the first
feed-forward layer, and that tensor's checksum **changes between two hooks that read the same tensor**:
it is overwritten after it was produced.

## When it started: a likely regression window (linux 7.1.3 → 7.1.5)

A retroactive scan of every latent our eval renderer saved (all ages scanned alike, so detection is not
time-biased) shows **zero NaN outputs in 48,606 renders before 2026-07-27, and a 2.6–7 % NaN rate on
adapter checkpoints after it; full fine-tunes (no adapter) stayed at 0 % throughout.** Renders before
07-27 included many rank-128 adapter checkpoints, the class that fails now. The first NaN output is
dated **2026-07-29**. On **2026-07-27** the kernel moved `linux-zen 7.1.3 → 7.1.5` (and `linux 7.1.3 →
7.1.5`). Nothing else compute-relevant changed: the other upgrades that day were Mesa/Vulkan and system
LLVM, which the self-contained ROCm wheels do not use; the PyTorch/ROCm stack was the same ROCm 7.2.3
venv until 08-02; our renderer and adapter code had no commits between 07-21 and 07-30. So this looks
like an **amdgpu regression between kernel 7.1.3 and 7.1.5**, still present in 7.2.6. Not yet proven:
see TODO 2.

## Related public reports (read 2026-09-26)

- **ROCm/rocm-libraries PR #8909** (merged to develop 2026-08-14), "fix(tensilelite): bound GLTr
  transpose-load to tensor end": on RDNA4, `global_load_tr` for DirectToVgpr operands has no hardware
  bounds check, so a GEMM whose free dim or K-tail does not fill the macro tile reads past the tensor
  end, faulting when it abuts unmapped pages. Fixes #7992 and legacy-rocm-build #6413. **Our first crash
  kernel was of this class:** `Cijk_Alik_Bljk_BBS_BH_Bias_HA_S_SAV_UserArgs_MT128x128x32_..._DTVA0_DTVB1_..._ISA1201`.
  An unbounded read of neighbouring memory would explain the history dependence, the NaNs (K-tail
  garbage enters real outputs), the faults, and why disabling allocator caching hides it.
- **ROCm/rocm-libraries #7992** (open, 06-03): gfx1201 Tensile GEMM MT64x64x64 computes an OOB address
  on a column-major B operand (`DTVB1`); rocBLAS falls back to the same kernel, which fits our rocBLAS
  test failing too. Kernel 7.0.10, i.e. before our suspected 07-27 window.
- **ROCm/legacy-rocm-build #6413** (07-14, "fix submitted" via #8909): gfx1201 page fault + GPU reset
  during PyTorch LoRA fine-tuning of a large diffusion transformer.
- **pytorch/pytorch #195202** (open, 08-28, assigned to an AMD maintainer): gfx1201 bf16 training goes
  NaN at step 1, "a state/history-dependent allocator defect", avoided by NOT using expandable_segments.
  Possibly the same root cause under a different memory layout.
- **ROCm/rocm-libraries #6166** (closed): rocBLAS `dot_ex` page-faults on gfx1201, `MAPPING_ERROR: 0x1`.

Open questions this raises: (a) does our ROCm 10.1 alpha (built 2026-08-22) contain #8909? It still
fails; either it lacks the fix, or the fix does not cover our kernel variant (MT128x128x32 with fused
bias vs the narrow tiles #8909 names). (b) If #8909 is the cause, the 07-27 kernel update may have
EXPOSED it (changed memory placement) rather than caused it; `linux-lts` separates the two.
**Better route than a new issue: add our data to #7992 or pytorch #195202.**

## Suspected area

amdgpu VM / HIP runtime memory management on gfx1201: memory handed back and reused (or unmapped)
while still referenced by in-flight or later work. The SQC instruction-fetch faults suggest code-object
or page-table mappings are affected too, not only data buffers.

---

## TODO before filing

1. **Weight-free repro.** Replace the trained adapter with a synthetic one (random `A`, small random
   `B`, `mag = ‖W0‖`) on the public `medium-base` checkpoint, and confirm it still fails. Our adapter
   weights cannot be attached. Better still, reduce it further: a stack of large `nn.Linear` layers
   with a live parametrization, alternating batch sizes, no Stable Audio code at all.
2. **Driver test.** Boot `linux-lts` (6.18.53, i.e. before the suspected 7.1.3 → 7.1.5 window) and
   rerun. Clean there ⇒ a kernel regression, reportable to the amdgpu kernel tracker
   (gitlab.freedesktop.org/drm/amd) with the version window, which matters more than the ROCm report.
3. Attach `rocminfo`, `dmesg` for one crash, and the repro script. Scrub local paths and checkpoint
   names.
