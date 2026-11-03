---
name: infinite-audio-fifo-sa3
description: "InfiniteAudio FIFO (diagonal denoising) prototype for SA3 — per-frame-timestep surgery, written + reviewed, UNTESTED on GPU"
metadata: 
  node_type: memory
  type: project
  originSessionId: a76bbe73-5250-4a70-accd-5324dfe52aa8
---

InfiniteAudio (arXiv:2506.03020) long-form generation ported to SA3 as a **research
prototype** on branch `latch-sa3-phase1` (2026-06-18). Files:
- `docs/INFINITE_AUDIO_FIFO.md` — spec (algorithm, surgery, risks, validation plan).
- `stable_audio_3/inference/fifo_infinite.py` — guarded per-frame-timestep monkeypatch +
  `FIFOConfig`/`sample_fifo_infinite` + `build_window_conditioning`.
- `scripts/fifo_infinite_smoke.py` — `--parity` (per-frame forward parity) + short FIFO gen.

**Key architectural finding:** SA3's DiT only takes a *scalar-per-batch* timestep
(`dit.py:239`, embedded into adaLN global cond). True FIFO needs *per-frame* σ `(B,T)`.
Verified live on small-music-base: `patch_size=1`, `timestep_cond_type=global`,
`global_cond_type=adaLN`, `num_memory_tokens=64`, `downsampling_ratio=4096`. So FIFO is
**not a sampler swap** — needs model surgery, and is **out-of-distribution** (untrained).
The surgery makes adaLN per-token via a guarded patch (3 injection points, delegates the
long methods; scalar path byte-identical). CFG done manually (2 unit-scale passes) because
the DiT's internal CFG assumes scalar sigma (`dit.py:466/473/479/577/581`).

**Status: written + adversarially reviewed (18 findings fixed), NOT run** — GPU was
occupied. First validation: `python scripts/fifo_infinite_smoke.py --parity` (gate on
*relative* err <5e-3; ROCm GEMM noise floor ~1e-3..1e-2 abs, not 1e-4), then the short
smoke (defaults window 64 / emit 32). **Biggest expected failure mode = rotary positional
drift** (FIFO content migrates through absolute positions; SA3 encodes the beat grid
positionally). If too OOD, documented fallback is **sliding-window inpaint-continuation**
(no surgery); real fix = finetune with shifted-content / per-frame-heterogeneous-noise.
LoRA is incompatible (fail-fast assert). Buffer-zone is disabled by default (the shipped
σ-pin is frozen-context, not the paper's clean anchor; real anchor = inpaint-clamp, v2).

Related: [[latch-sa3-phase1]]. forage-dj's "long-form" is just generate-fixed-tracks +
DJ-crossfade (nothing reusable for continuous diffusion). mir's `scripts/latent_server.py`
`beatmatch_crossfade_to_wav` (downbeat-grid tempo match + phase-lock + latent-space
crossfade) is **strictly more advanced** than forage-dj's equal-power fader.
