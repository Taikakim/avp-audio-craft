---
name: sa3-onnx-amd-inference
description: "Plan for exporting the SAME (SA3) autoencoder to ONNX for low-VRAM AMD inference via ORT+MIGraphX — fixed-chunk, not varlen"
metadata: 
  node_type: memory
  type: project
  originSessionId: 085d95f2-1875-4707-ac4d-9d05b552b676
---

Goal: a low-VRAM SAME decoder/encoder for the RX 9070 XT that can run alongside a
training job (the torch `/decode` uses ~5 GB; a quantized ONNX path targets the
~1.6 GB the cgisky MNN port achieves). Motivated by [[stable-audio-3-rs-mnn]]
(reference: cgisky1980/stable-audio-3-rs — proven SA3-Small ONNX/MNN export).

Key technical findings (from the SAME autoencoder source):
- SAME encoder/decoder are **transformer-based** (`TransformerResamplingBlock`), and
  fold the sequence into chunks whose count depends on input length → a single
  dynamic-axis ONNX graph over arbitrary T is fragile. **Fix: export one fixed-size
  chunk, loop + overlap-stitch on the host.** `AudioAutoencoder.decode_audio(chunked=True)`
  already does exactly that (calls `decode()` on fixed chunks + overlap-add), so the
  exportable unit already exists.
- Export prep, all in `stable-audio-3/scripts/export_same_onnx.py` (decoder export
  **VALIDATED 2026-06-20** on CPU: chunk-32 SAME-L decode, ORT-CPU vs torch
  mean|Δ|=7e-4, cos=0.99988, max|Δ|=3e-2 single-sample outlier): fold `weight_norm`
  into conv weights (`remove_weight_norm`/`remove_parametrizations`); disable gradient
  checkpointing; export static shapes (MIGraphX prefers static). Two non-obvious gotchas:
  - **`SA3_DISABLE_FLASH_ATTN=1` is NOT enough** — with flash off, SAME's sliding-window
    layers fall to **FlexAttention** (a torch.compile HOP), which the dynamo ONNX exporter
    can't translate (dies on the mask_mod `bitwise_and` graph output). Must ALSO disable flex:
    `transformer.flex_attention_available=False; transformer.flex_attention_compiled=None`
    → drops to `_sliding_window_chunked_halo_sdpa` (math-equivalent masked SDPA, exports clean).
  - **opset must be >=18.** The dynamo exporter implements these ops at opset 18; requesting
    17 forces a lossy down-convert that emits an invalid `Split(num_outputs)` ORT rejects.
- torch's modern `torch.onnx.export` needs `onnxscript`+`onnx` (uv pip install onnxscript,
  purely additive — does NOT bump the pinned ROCm torch/numpy). `onnxruntime` for --validate.
- **AMD runtime is already in hand:** ORT + **MIGraphX EP** ships in the mir stack
  (`onnxruntime_migraphx` wheel, used for Essentia classifiers). No MNN/Vulkan build.
- **FP16 is the safe target; INT8 on MIGraphX is a stretch** (MASTER §5 "INT8
  non-functional on ROCm" is the torch path, but MIGraphX INT8 coverage is uneven).
- Encoding is feasible by the same fixed-chunk method (encoder is the same block type;
  cgisky shipped an `encoder_int8.mnn`). Caveat: the export wrapper skips the
  auto-resample/length-pad that produced the stored `latents_sa3/*.npy` — cross-check
  encoder output against a real `.npy` before trusting it.

Status 2026-06-20: **GPU-VERIFIED.** Decoder runs 100% on the MIGraphX EP (zero CPU fallback,
`--report-placement`), cos=0.999998 vs torch, RTF ~39× post-compile → ONNX inference on AMD
works. **Catch: ~9-min MIGraphX AOT compile per session** (CPU-bound; not exhaustive-tune nor chunk
size — the masked-SDPA graph is just slow to compile). ORT compiled-model caching is **NOT
exposed** in this `onnxruntime_migraphx` 1.23.2 build (`migraphx_save/load_compiled_model` +
`_model_name`/`_model_path` all rejected → silent CPU fallback; `decode_onnx.py` detects &
retries on bare GPU EP). Mitigate: **long-lived server compiles once at boot** (latent_server
pattern) or a newer ORT-ROCm build. `migraphx_fp16_enable` IS valid. MIGraphX EP is only in the **mir venv**
(`onnxruntime_migraphx` 1.23.2); SA3 venv `onnxruntime` 1.27 is CPU-only. Decoder+encoder also
CPU-validated (decoder L128 cos=0.99998, encoder L128 cos=0.999996). Tooling committed in `stable-audio-3` (branch
`latch-sa3-phase1`, commit 3e5a9eb): `scripts/export_same_onnx.py` (export+validate),
`scripts/decode_onnx.py` (host chunk-loop runner: port of `decode_audio(chunked=True)` over an
ORT session, provider MIGraphX>ROCm>CPU, `--compare-torch` to set overlap). Doc:
`stable-audio-3/docs/onnx-amd-inference.md`. Generated `.onnx`/`.onnx.data` are gitignored.
**Seam test PASSES** (2026-06-20, overlap=16, validated on CPU since the stitch is EP-independent):
ONNX-chunked vs torch-UNCHUNKED cos=0.999997, no per-boundary spikes; torch chunked≈unchunked
(cos=1.0) confirms overlap=16 ≥ receptive field. → **full ONNX-on-AMD decode path verified
end-to-end.** Wired into [[sa3-latent-explorer-tool]] as a low-VRAM decode (latent_server_onnx.py).

**DiT export started (2026-06-21):** `stable-audio-3/scripts/export_dit_onnx.py` exports
`DiffusionTransformer._forward` (CFG-free core) at a fixed length, **DiT-only load** (build
`DiTWrapper(**diffusion.config)` + the `model.model.*` safetensors keys — NO T5-Gemma; text
is precached). medium-base L256 CPU-validated vs torch **cos=1.000000**; same recipe as the
AE (flash-off + opset 18), DiT was structurally friendlier (no chunk-folding, global attn).
Runner `scripts/dit_onnx_infer.py` (mir venv): rectified-flow Euler + velocity-space CFG
`v=v_unc+cfg*(v_cond-v_unc)`, schedule=linspace(1,0,steps+1) (Flux shift = identity for
medium-base, alpha=1), feeds precached cond/uncond npz (cross_attn_cond[seq,768]+mask+
global_embed[768]) → DiT-onnx → decoder-onnx. **Ladder: T∈{256,512,1024,2048,4096}** (one
onnx+compile per rung; ~5.5GB fp32/rung → export fp16). **GPU-VERIFIED END-TO-END 2026-06-23 (commits e310a4b, a3e165f):**
- **CRITICAL FIX — DiT needs `local_add_cond`:** medium-base DiT takes a 257-ch local_add_cond
  = cat(inpaint_mask[1], inpaint_masked_input[256]). For text-to-audio it's all-zeros BUT the DiT
  projects it with a BIAS → `None ≠ zeros` (cos 0.98, max|Δ| 0.74). First export wrongly omitted it
  (falsely validated cos=1.0 None-vs-None). Export now takes local_add_cond[1,257,T]; runner feeds zeros.
- Corrected DiT: ONNX vs torch _forward cos=1.0; **MIGraphX vs CPU cos=1.000000, 100% on-EP, 191ms/call,
  ~13min compile**; **full 8-step real-prompt gen ONNX z0 vs torch z0 cos=0.999944** → text→audio on AMD
  reproduces torch. Real audio structured/musical. **Ladder exported: L∈{256,512,1024,2048,4096}** (each
  8.8MB graph + 5.8GB weights, ~29GB total — weights not shared yet, dedup TODO).
- **t5gemma `google/t5gemma-b-b-ul2` (0.6B, gated):** referenced not bundled; HF Xet protocol STALLS at
  ~134MB → download via `HF_HUB_DISABLE_XET=1` or `curl -C-` the resolve URL (worked). Precache tool
  `scripts/precache_dit_cond.py` (prompt+duration→cond/uncond npz). Build the DiT itself from the cached
  safetensors only (no t5gemma).
- DiT exported static **batch=1** → CFG = two batch-1 calls/step (batch=2 export = efficiency option).
- **Perf: DiT-only RTF ≈7.8×** (L256, 16 calls×191ms). **⚠ VRAM: don't co-resident fp32 DiT (~5.8GB) +
  fp32 decoder on the 16GB card** — decoder compile with the DiT resident maxes VRAM (16.5GB → GTT) and
  THRASHES (31min vs 9min). **FIX = fp16-EXPORTED onnx files** (`export_dit_onnx.py --fp16` via
  `convert_float_to_float16_model_path`+external-data; >2GB DiT overflows the in-memory protobuf). fp16
  loads directly: DiT 2.9GB + decoder 0.9GB = 3.8GB resident, fp16-vs-fp32 cos=0.999992. **NOT
  `migraphx_fp16_enable`** — that loads fp32 then quantizes at init → co-residency **OOMs HARDER** (HIP
  OOM, measured twice). Or separate processes.
- **Follow-up tooling (commits …8fe4f9d fork / ac1978c main):** `--batch 2` export (one DiT call/step,
  cos 1.0); `bench_dit_onnx.py` (ONNX-vs-torch gen benchmark, `dit_loop_s` = fair number) +
  `latent_server_dit_onnx.py` (low-VRAM gen server, CPU-smoke passed). 
- **BENCHMARK VERDICT (2026-06-24): ONNX/MIGraphX is a VRAM/deployment win, NOT speed.** L256/8-step DiT
  loop: **torch eager cuda-fp16 0.707s (44ms/call, RTF 33.6×)** vs **ONNX-fp16 MIGraphX 2.314s (144ms/call,
  RTF 10.3×)** → eager torch **~3.3× faster** (MIGraphX doesn't beat torch's rocBLAS/MIOpen). Quality
  identical (z0 cos 0.9993). ONNX buys **3.8GB resident + zero torch dependency** (coexists w/ training).
  fp16 ~25% faster than fp32 MIGraphX. Use ONNX for low-VRAM, torch for speed. Details:
  stable-audio-3/docs/onnx-amd-inference.md.
- **Control adapters bake into the DiT ONNX (2026-06-27, commit 6e46ec5).** A trained `sa3_control` adapter
  (avp_sa3; decoupled cross-attn per DiT block + scalar FiLM conditioner) is a pure FORWARD mod (no autograd,
  unlike a LatCH guidance head) → folds into the graph with `control_tokens[1,16,768]`+`gain` inputs.
  `export_dit_control_onnx.py` (wrap 24 cross-attns + load adapter.{i}/conditioner + export; thread the
  adapter module-global as explicit forward inputs → traces through torch.export) + `dit_control_onnx_infer.py`
  (cond=enc((target−mean)/std), uncond=zeros=trained null → control rides CFG; numpy FiLM in a .cond.npz, no
  runtime torch). Validated CPU: ONNX vs controlled-torch **cos=1.0**; end-to-end onset 3→4.88/11→11.15
  onsets/sec (monotonic). Ckpt example: onset_FUSION_lr2e5_40epoch/soup_exppeak.pt (field=onset_density).
  **GPU-VERIFIED (MIGraphX 2026-06-27):** cos=1.0 vs CPU, 100% on-EP, 294ms/call (vs plain 144ms — 24 adapters
  add ~50%); on-GPU steering onset 3→5.00/11→11.19, ~4s/gen. **⚠ fp16-export of the control-DiT is BROKEN**
  (convert_float_to_float16_model_path → invalid graph: a ConstantOfShape from the adapter PE
  (add_fractional_positions) lands fp16 where fp32 expected; path converter lacks op_block_list). **fp16 FIXED
  (commit 18c3aa7):** the bad ConstantOfShape was the adapter PE (add_fractional_positions) → moved host-side
  (export position_encoding=False + numpy PE in runner; equivalent cos=1.0, gated). --fp16 converts → 3.1GB,
  stamped; npz host_pe=True + onnx metadata stamp + runner assert guard a mismatched .cond.npz/.onnx pair.
- **CPU-ONLY is the recommended eval path (frees the GPU for training).** Ryzen 9 9900X: onset-steered gen
  ~10s (8-step)+decode, ~2× realtime, steers identically to GPU (11→11.19). --threads 12 (physical cores, ~25%
  faster than 24 SMT). INT8 CPU: 1.4–1.7× but cos 0.95 (audition; needs value_info-strip + MatMul-only to dodge
  a missing ConvInteger kernel) → fp32 already fast, INT8 only for VST latency. precache_dit_cond.py broken on
  the SA3 fork (cuda/cpu split + KeyError inpaint_mask). NOTE: the box's GPU is often busy with the riffer bracket
(`/tmp/bracket_doof.py`, sa3-rocm7.13-test venv) — check `rocm-smi --showpids` before heavy GPU runs.

**fp16 control-DiT GPU measured (2026-06-27).** AOT compile 2391 s (DiT) / 2438 s (decoder) — ~40 min each
(longer than fp32 ~18 min; host-PE graph change adds ops). Per call: 169 ms (fp32: 294 ms; ~43% faster). Cos
vs CPU: 0.9999 (fp16 floor). 100% on-EP. Eval math: 30-clip 8-step grid = ~5.4 min CPU (674 ms/call, no
compile) vs ~42 min GPU (compile-dominated). CPU is the correct DEFAULT for control-evals; GPU only wins for
a resident VST. Compile-cache is a MISSING EP FEATURE: migraphx_save/load_compiled_model rejected by ORT
1.23.2, falls back to CPU silently (decode_onnx.py:_augment_migraphx + retry guard); not a config gap.

**New tooling (2026-06-27, on disk):**
- `stable-audio-3/scripts/sa3_control_onnx.py` — shared numpy/ORT gen-core (`generate_z0`,
  `make_control_tokens`, `resolve_host_pe`).
- `avp_sa3/sa3_control/train.py --export-onnx-on-finish` (default True) — auto-exports `riffer_final.pt`
  → fp16 ONNX + `.cond.npz` at L256 into the run dir on training finish (non-fatal).
- `scripts/control_eval_server.py` + `scripts/submit_control_job.py` — all-CPU long-lived file-drop
  eval server (resident T5-Gemma + ONNX DiT/decoder; queue `SAO/control_eval_queue`; atomic
  claim/publish; frames from the DiT graph) + cross-venv submitter. E2E-verified 2026-06-27 (CPU):
  boot ~16 s, 8-step job ≈20 s, steering onset 3→5.17 / 11→10.43 onsets/s; shared-core z0 bit-exact.
