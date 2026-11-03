---
name: stable-audio-3-rs-mnn
description: "Reference — cgisky1980/stable-audio-3-rs, a Rust SA3-Small inference runtime via MNN INT8 (proven ONNX/MNN export of SAME)"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 085d95f2-1875-4707-ac4d-9d05b552b676
---

`https://github.com/cgisky1980/stable-audio-3-rs` (cloned to `/home/kim/Projects/stable-audio-3-rs`).
Rust runtime for **SA3 Small** (`sm-music`/`sm-sfx`) via Alibaba **MNN** INT8 + ORT, CUDA/Windows+Linux.
RTF 10–33×, ~1.09 GB models, constant ~1.6 GB VRAM (chunked decode, chunk_size=256 latents ≈ 23.8 s).

Conversion is NOT in the repo (pre-converted models at HF `cgisky/stable-audio-3-mnn`; MNN fork
`cgisky1980/MNN` with Softmax + MatMul patches). But it **proves SAME → ONNX → MNN export works**
(ships `decoder_q8.onnx`, `dit_*_fp16_f32io.onnx`, `encoder_int8.mnn`).

Reusable engineering ideas: **WeightNorm pre-fusion** (fold Conv1d weight_norm before convert →
fp16/int8 decode stays stable); **T5 must run on CPU** (MNN CUDA T5 max-diff 50.68 → wrong text
cond); chunked decode for constant VRAM; reverse-engineered `SoftNormBottleneck` (`bottleneck_params.json`)
for music-to-music.

Relevance to our AMD/ROCm SA3 work: it's CUDA-only as shipped, and it's SAME-**Small**, not the
SAME-L of our `latents_sa3`. The transferable path for us is ONNX (not MNN) + ORT-MIGraphX — see
[[sa3-onnx-amd-inference]].
