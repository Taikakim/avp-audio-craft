# SA3 Inference Speed Shootout

**Model:** `medium-base` (SA3 SAME-L, 256-d latents @ 10.767 Hz). **Hardware:** AMD RX 9070 XT
(RDNA4, gfx1201, 16 GB) + Ryzen 9 9900X. **Date:** 2026-06-30.

What this measures: **generation wall-time per clip** (DiT rectified-flow sampling loop **+ decode**),
**warm**, batch 1, fp16 where applicable, **excluding** model-load and the one-time ONNX AOT compile.
`RTF = generated_audio_seconds / wall_seconds` (so **>1 = faster than realtime**).

> ⚠️ **Read RTF by basis, not absolute.** The two **measured** torch-GPU cells are 16-step / 47 s clips
> (T≈512). Most **reused** cells come from prior sessions at **8 steps / L256 (≈23.8 s)** — their RTF is
> computed on *that* basis and noted per-cell. Per-step cost is what's comparable across backends; total
> s/clip scales ~linearly with step count. Don't cross-compare a 16-step number to an 8-step one without
> halving.

## Backends × Configs matrix

Cells: **s/clip · RTF · source** where source = **M** measured this session, **R** reused from
`MASTER.md §5` / `WORKLOG.md`, **N/A** infeasible (reason below). Step count noted where ≠ 16.

| Config \ Backend | (1) Torch-GPU<br>cuda fp16, CK-FA | (2) Torch-CPU<br>AVX512 fp32 | (3) ONNX-MIGraphX<br>GPU fp16 | (4) ONNX-CPU-EP<br>fp32, 12-thr |
|---|---|---|---|---|
| **A · base** (plain DiT t→a) | **1.8 s · 26× · M** | ~85 s · 0.55× · R | 2.31 s/8-step · 10.3× · R | ~20 s/16-step · ~2.4× · R |
| **B · +DoRA** (rank-128) | **4.1 s · 11.5× · M** | ~85–110 s · ~0.5× · R | **N/A** — merge+re-export | **N/A** — merge+re-export |
| **C · +LATCH** guidance | ~7 s · 6.7× · R *(flex-attn)* | **N/A** — use 4C | **N/A** — autograd ∉ EP graph | ~15–25 s/16-step · ~2× · R |
| **D · +FiLM/control** adapter | ~2–3 s · ~9× · est. | **N/A** — use 4D | ~4 s/8-step · ~6× · R *(169 ms/call)* | ~10 s/8-step · ~2.4× · R *(674 ms/call)* |

### Per-cell detail & provenance

| Cell | Backend / Config | s/clip (basis) | RTF | Src | Venv | Notes |
|---|---|---|---|---|---|---|
| 1A | Torch-GPU · base | **1.8 s** (16-step/47 s) | **26×** | **M** | `stable-audio-3/.venv` | Warm. 1st clip 90 s = one-time kernel compile (excluded). CK flash-attn (`FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE`). The speed king. |
| 1B | Torch-GPU · +DoRA r128 | **4.1 s** (16-step/47 s) | **11.5×** | **M** | `stable-audio-3/.venv` | ckpt `…r128-adamw/…step=10800.ckpt`. ~2.3× slower than base: DoRA-rows recomputes `W' = mag·V/‖V‖` over **229 parametrized DiT Linears** every forward (load+attach, not merged). |
| 1C | Torch-GPU · +LATCH | **0.81 s** (8-step/20 s, fp16) | **24.8×** | **M** | `stable-audio-3/.venv` | **Remeasured 2026-07-01: ≈ base.** Default `generate(latch_configs=…)` runs **fp16 + CK flash-attn, 62.9 ms/call, 0 flex calls** (DiT fwd is under `no_grad` → only the fp32 head needs grad). The old "~7 s / 6.7× / flex-attn" was the **fp32 verify path** (`model_half=False`) — ~8× slower, used only by `verify_latch.py`/`verify_medium_heads.py` for fidelity. fp16 steers correctly (~½ the authority of fp32, recover with higher gain). `rho=mu` gain ≈512. |
| 1D | Torch-GPU · +control adapter | **0.82 s** (8-step/20 s) | **24.3×** | **M** | `stable-audio-3/.venv` | **Measured 2026-07-01: 85.8 ms/call = base ×1.10** (ckpt `onset_FUSION_lr8e5_1p2ep`). Forward-only cross-attn add (24 blocks) is cheap on torch GPU. The earlier ~4 s / RTF 6× was the **ONNX-MIGraphX** path (169 ms/call) misread as "GPU". |
| 2A | Torch-CPU · base | **20.2 s** (8-step/T256/24 s, gen-only) | **1.18×** | **M** | `stable-audio-3/.venv` (`SA3_DISABLE_FLASH_ATTN=1`, math-SDPA, 12 thr) | **Remeasured 2026-07-01:** DiT loop 15.6 s + decode 4.6 s. (Old ~85 s was a 16-step/T512/47 s *full* render.) **RAM floor 10.5 GB**, load-transient 18.9 GB. |
| 2B | Torch-CPU · +DoRA | ~85–110 s | ~0.5× | R | as 2A | DoRA W' recompute adds CPU cost on top of base; same script `--ckpt`. |
| 2C | Torch-CPU · +LATCH | **N/A → 4C** | — | — | — | Pure-torch-CPU full DiT is impractical; the LATCH eval path **deliberately** runs DiT fwd on ORT-CPU + torch autograd on the tiny head → that's cell **4C**. |
| 2D | Torch-CPU · +control | **N/A → 4D** | — | — | — | Superseded by the baked-control ONNX-CPU path (**4D**); no reason to run the adapter in pure torch-CPU. |
| 3A | ONNX-MIGraphX-GPU · base | **2.31 s** (8-step/L256≈23.8 s) | 10.3× | R | **mir venv** (`onnxruntime_migraphx` 1.23.2) | WORKLOG 2026-06-24. fp16 DiT **144 ms/call**. ~9-min AOT compile/session (excluded; no compile-cache in ORT 1.23.2). |
| 3B | ONNX-MIGraphX · +DoRA | **N/A** | — | — | — | DoRA is a **weight edit**, not a forward add → each adapter needs a static merge + full re-export + ~15-min AOT recompile. Not built; infeasible per-adapter. |
| 3C | ONNX-MIGraphX · +LATCH | **N/A** | — | — | — | LATCH guidance needs **torch autograd through the head**; the MIGraphX-EP graph isn't differentiable. The head can't bake in (gradient method) → no GPU-ONNX path. |
| 3D | ONNX-MIGraphX · +control | ~4 s (8-step/L256) | ~6× | R | **mir venv** | WORKLOG 2026-06-27. Control-DiT **169 ms/call fp16** (294 ms fp32) — 24 baked adapters add ~50% over plain DiT's 144 ms. cos=1.0 vs CPU, 100% on-EP. ~13–18 min AOT compile/session (excluded). |
| 4A | ONNX-CPU-EP · base | **15.35 s** (8-step/T256/24 s, gen-only) | **1.55×** | **M** | `stable-audio-3/.venv` (onnxruntime 1.27 CPU EP, 12 thr) | **Remeasured 2026-07-01: 1.32× faster than torch-CPU** (DiT loop **1.70×** faster — MLAS AVX512 + graph fusion; decode 1.34× *slower* — ORT chunked overlap-recompute). 575 ms/DiT-call. **RAM floor 8.4 GB** (2.1 GB < torch). **Use fp32 — fp16 is a LOSS on CPU EP** (no fp16 kernels → up-converts to fp32 at load: slower, no RAM win). |
| 4B | ONNX-CPU-EP · +DoRA | **N/A** | — | — | — | Same merge+re-export blocker as 3B. |
| 4C | ONNX-CPU-EP · +LATCH | ~15–25 s (16-step) | ~2× | R | `stable-audio-3` (`sa3_latch_onnx.py` / `latch_eval_server.py`) | DiT fwd on ORT-CPU + torch autograd on the ~5–7 M-param head only. THE latch eval path (commit 020b6c3). 8-step ≈ control + head-backprop overhead. |
| 4D | ONNX-CPU-EP · +control | ~10 s (8-step) | ~2.4× | R | `control_eval_server.py` / `dit_control_onnx_infer.py` | WORKLOG 2026-06-27. **674 ms/call**, CFG=16 calls/clip. 30-clip 8-step grid ≈ **5.4 min on CPU-EP** vs ~42 min on **MIGraphX-GPU** (~40 min of which is one-time AOT compile, ~1.4 min actual gen) → CPU-EP wins a *one-off* ONNX grid, but **torch-GPU does it in ~2–3 min** and is the real fastest. |

**Measured (M):** 1A, 1B (16-step/47 s); **1C, 1D remeasured 2026-07-01** (8-step/20 s, warm median) — these two
correct the earlier mis-attributed numbers (1C was the fp32 verify path, 1D was the ONNX-MIGraphX path).
**Reused (R) from MASTER §5 / WORKLOG:** 2A, 2B, 3A, 3D, 4A, 4C, 4D.
**Flagged N/A:** 2C, 2D (→ use 4C/4D), 3B, 4B (DoRA merge+re-export), 3C (autograd ∉ EP).

## Headline takeaways

1. **Torch-eager GPU (CK flash-attn) is the speed king — nothing else is close.** Base **1.8 s/clip (RTF
   26×)** beats ONNX-fp16-MIGraphX on the same card (**~3.3× faster** at the per-call level: 44 ms torch vs
   144 ms MIGraphX). MIGraphX's compiled graph does **not** beat torch's tuned rocBLAS/MIOpen + CK-FA kernels.

2. **ONNX's value is VRAM/deployment, not speed.** The MIGraphX port buys **~3.8 GB resident + zero torch
   dependency** (coexists with a training job on the 16 GB card), same quality (z0 cos ≈0.999). You pay for
   it in throughput **and** a ~9–18 min AOT compile every session (ORT 1.23.2 has no compile-cache). Use ONNX
   only when VRAM is the constraint or for a resident VST that amortizes the compile.

3. **CPU-AVX512 is viable for control/LATCH evals *when the GPU is busy*, not for bulk torch generation.** Pure
   torch-CPU base is ~85 s/clip (RTF 0.55× — sub-realtime). But the **ONNX-CPU control & LATCH eval paths run
   ~2× realtime** (~10 s/8-step) and **free the GPU for training**. ⚠️ The "CPU wins" figure needs its caveat:
   a one-off 30-clip control grid is **~5.4 min on ONNX-CPU-EP vs ~42 min on ONNX-MIGraphX-GPU** — but that GPU
   "42 min" is **~40 min of one-time AOT compile + only ~1.4 min of actual generation**, NOT a slow GPU. The
   real ordering is **torch-GPU (~2–3 min, no compile — fastest) > ONNX-CPU-EP (~5 min) > one-off
   ONNX-MIGraphX-GPU (compile-bound)**. So CPU-EP is the right default only when the GPU is occupied (training)
   or for a single throwaway ONNX eval; a **resident** GPU ONNX server amortizes the compile and wins on
   throughput. None of these numbers is "vs CPU" — every RTF is vs realtime.

4. **DoRA roughly halves torch-GPU throughput (1.8 → 4.1 s/clip);** the cost is the per-forward `W'` recompute
   over 229 parametrized Linears, not the rank. **DoRA on any ONNX backend is N/A** — a weight edit needs a
   per-adapter static merge + full re-export + a fresh ~15-min AOT compile, so adapters can't ride the ONNX
   path the way the (forward-only) FiLM control adapter does. Net rule: **DoRA → torch only; FiLM control →
   torch *or* ONNX; LATCH → torch-GPU (fp16, CK flash-attn) or ONNX-CPU (autograd head), never ONNX-GPU.**

5. **The adapters are NOT slow on GPU — the earlier "small GPU-vs-CPU gap" was a measurement artifact, now corrected.**
   Both LATCH (fp16/CK-FA, **0.81 s**) and control (**0.82 s**) run at **≈ base speed on torch-GPU (RTF ~24×)**, so their
   GPU edge over the CPU eval paths is **~10–12×, same as base** — not the ~3× the first pass implied. That ~3× came from
   benchmarking the *wrong GPU backend*: LATCH's fp32 verify path (~8× slow) and control's ONNX-MIGraphX path (169 ms/call).
   **No code optimisation to apply** — fp16 + CK-FA is already the default in `generate()`; the slow numbers lived only in
   fidelity-check scripts (`verify_latch.py`, `verify_medium_heads.py`, intentionally fp32). One usable lever: run LATCH
   *evals* in fp16 (not the fp32 verify default) → **~8× faster**, still steers, recover ~½ the authority via higher gain.

6. **ONNX-CPU vs Torch-CPU (same basis, 8-step/T256, measured 2026-07-01): ONNX ~1.3× faster and ~2 GB lighter.**
   Gen **15.35 s (RTF 1.55×)** vs **20.2 s (RTF 1.18×)**. The DiT loop is **1.7× faster** on ONNX (MLAS AVX512 + fused
   const-folded graph vs torch-eager math-SDPA), while *decode* is 1.3× **slower** on ONNX (its chunked decoder recomputes
   the 16-frame overlap) — net win to ONNX since the DiT dominates. RAM floor **8.4 vs 10.5 GB**: the 2.1 GB is **not** the
   DiT/decoder (identical fp32 weights in both) — it's torch's unused AE **encoder** (1.7 GB dead weight for text→audio) +
   libtorch/autograd (~0.4 GB), both absent in ONNX. **fp16 ONNX is a LOSS on CPU** (CPU EP has no fp16 kernels → up-converts
   to fp32 at load: slower *and* no RAM saving) — fp16 helps only the MIGraphX **GPU** EP. **Footprint caveat:** these floors
   are with **precached text** — the T5-Gemma encoder is NOT resident in the gen path (in-model conditioner ≈ 0.2 M params).
   Encoding a prompt **live** (the eval-server path) adds T5-Gemma (~5.6 GB fp32) to **both** backends equally.

## Reproduce the measured cells

```bash
cd /home/kim/Projects/SAO/stable-audio-3
# 1A torch-GPU base
.venv/bin/python scripts/eval_dora_cpu.py --base --device cuda --steps 16 --duration 47 --out-dir /tmp/sh/base
# 1B torch-GPU +DoRA r128
.venv/bin/python scripts/eval_dora_cpu.py --device cuda --steps 16 --duration 47 \
  --ckpt /run/media/kim/Lehto/sa3_lora_runs/sa3-goa-dora-47s-r128-adamw/dq0egegi/checkpoints/epoch=7-step=10800.ckpt \
  --out-dir /tmp/sh/dora
# (warm = drop the first clip, which pays the one-time kernel compile)
```

Sources for the reused cells: `SAO/MASTER.md` §5 (ONNX/MIGraphX bullets) and `SAO/WORKLOG.md`
2026-06-24 (DiT ONNX benchmark), 2026-06-27 (control-DiT fp16 GPU + CPU calibration), 2026-06-28
(LATCH head sweep gain ≈512; CPU LATCH-guidance eval path).
