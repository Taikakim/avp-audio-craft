# MASTER — Audio Generation Pipeline (mir + Stable Audio)

**Single source of truth for facts that span repos.** Each project's `CLAUDE.md`
imports this file. When you discover something that affects more than one repo —
a path, a venv quirk, a cross-cutting gotcha — update **this file**, not just your
local `CLAUDE.md`. Append a dated line to `WORKLOG.md` (sibling) for anything you
ran, built, or learned this session.

> Why this exists: Claude Code's auto-memory is siloed per working directory, so a
> fact learned while working in `mir/` is invisible to an agent working in
> `stable-audio-3/`. This file is the shared layer. (2026-05-31)

> **Before building anything, check what already exists.** `ARCHITECTURE.md` (sibling)
> is the **reuse index** — tools and plumbing already built across the three repos —
> kept current as a standing task. We keep rediscovering things already in place (e.g.
> a working **bungee** time-stretch binding + comparison GUI in `mir/`). Grep the repos
> and read `ARCHITECTURE.md` before writing new code; each sub-component also carries its
> own `ARCHITECTURE.md` + `CLAUDE.md`.

**Detailed docs** (this file is the summary; depth lives in `docs/`):
`ARCHITECTURE.md` (1-page map) · `docs/venvs.md` (venvs + CK flash-attn build) ·
`docs/commands.md` · `docs/latch.md` · `docs/training-findings.md`
(**recipes, params, why latents are T=4096**) · `docs/lessons-learned.md` · `docs/todos.md`.
The authoritative LatCH experiment log is `stable-audio-tools/LATCH_RESULTS.txt`.

---

## 1. Project map

| Repo | Path | Role | Canonical venv (py) |
|---|---|---|---|
| **mir** | `/home/kim/Projects/mir` | MIR feature extraction, audio I/O, Audiobox, whole-track timeseries | `mir/bin/python` (3.12, numpy 1.26, **essentia+madmom**) |
| **stable-audio-tools** ("audio-tools-AVP" fork) | `/home/kim/Projects/SAO/stable-audio-tools` | LatCH heads, FusionOpt, SAO-Small train/finetune, audition renders | `sat-venv/bin/python` (3.10, torch 2.10 ROCm) |
| **stable-audio-3** | `/home/kim/Projects/SAO/stable-audio-3` | SA3 medium model, LoRA finetune, SA3 LatCH (phase 1) | `.venv/bin/python` (3.13, torch 2.10 ROCm) |

Supporting (no canonical venv of note): `SAO/sa3-rocm7.13-test` (FA/ROCm 7.13 build test),
`SAO/torchcodec`, `SAO/my_wheels` (custom torch+ROCm wheels).

**Hardware:** AMD RX 9070 XT (RDNA4, gfx1201, 16 GB) + Ryzen 9 9900X. ROCm 7.2.x, torch 2.10 ROCm.

**Three Python versions (3.10 / 3.12 / 3.13) → the venvs cannot be merged.** Always
invoke a venv by **absolute path** in commands; never assume `python` is the right one.

---

## 2. Canonical data paths

Both data drives are **removable** — if a path 404s, the drive is unmounted, not gone.

### Source audio — Mantu (`/run/media/kim/Mantu`)
| Path | What | Used by |
|---|---|---|
| `ai-music/Goa_Separated` (4470) | **Full tracks** + stems + `.INFO` + `.BEATS_GRID`/`.DOWNBEATS`/`.ONSETS` | SA3 encode, whole-track timeseries |
| `goa_crops` (4829) | Older **11.9 s crop** corpus (`<Artist - Title>_N.flac`) | SAO-Small LatCH |

> ⚠️ Stale path in old memories: `Mantu/ai-music/Goa_Separated_crops` **no longer exists**.

### Derived data — Lehto (`/run/media/kim/Lehto`)
| Path | What | Grid | Used by |
|---|---|---|---|
| `latents` (15 G, 4808) | SAO-Small/SA1 latents, **64-dim** | 21.53 Hz, T=256 (11.9 s) | SAT LatCH |
| `latents_stems` (43 G) | Stem latents | 21.53 Hz | SAT |
| `latents_sa3` (~7 G, ~5400) | **SA3 SAME-L latents, 256-dim**; per crop: `.npy` + `.json` (merged `.INFO`+prompt+rel_pos) + `.TIMESERIES.npz` | **10.767 Hz, T=4096 (380 s)** | SA3 LoRA |
| `timeseries` (21 G, 4461) | **Whole-track MIR timeseries**, 20 fields | 100 Hz, full track | SAT LatCH, SA3 crop companions |
| `sa3_lora_runs` | SA3 LoRA checkpoints + demos | — | SA3 |
| (in `mir/`) `data/timeseries.db` (2.6 G, ~209k) | Legacy **per-crop** timeseries SQLite | 21.53 Hz, T=256 | SAT LatCH |

> ⚠️ Stale paths in old memories: `Lehto/goa-small`, `Lehto/goa-stems` **no longer exist**.

> 🚀 **Fast local mirror (non-removable):** a complete copy of `latents_sa3` —
> `/home/kim/Projects/latents_sa3` (13 G; 5401 `.npy` + 5400 `.json` + 5400
> `.TIMESERIES.npz`, `(1,256,4096)` fp16) — lives on the NVMe. Prefer it over the
> Lehto path for throughput-bound work (SA3 LoRA, pre-encode, FIFO seeding); Lehto
> stays the canonical/authoritative copy. (2026-06-19)

---

## 3. Venv-per-task (the #1 source of wasted time)

| Task | Use |
|---|---|
| MIR feature extraction, Audiobox scoring, whole-track timeseries | `/home/kim/Projects/mir/mir/bin/python` |
| LatCH head training (SAO-Small), FusionOpt, audition renders | `/home/kim/Projects/SAO/stable-audio-tools/sat-venv/bin/python` |
| SA3 inference, SA3 LoRA finetune, SA3 pre-encode | `/home/kim/Projects/SAO/stable-audio-3/.venv/bin/python` |

mir's `.venv` (3.12, numpy 2.x) **lacks essentia and silently degrades madmom→librosa** — do not use it; use `mir/bin/python`.

---

## 4. Cross-cutting topics

**LatCH (spans all three repos).** mir extracts features → SAT trains the heads →
both SAT and SA3 run LatCH-guided inference. Validated training recipe lives in
`stable-audio-tools/LATCH_RESULTS.txt` (§21: SF-NorMuon, d256/dp4, bf16, `--compile`,
adaln_zero). **Two latent grids, never mix:** SAO-Small heads target 21.53 Hz/T=256;
SA3 heads target 10.767 Hz/T=4096 (requires re-encoded latents). Targets come from
the per-crop DB (fixed crops) or the whole-track npz (arbitrary windows, via the
consumer below).

**Whole-track timeseries.** Producer: `mir/src/spectral/whole_track_timeseries.py`
(100 Hz, 20 fields incl. madmom beat/downbeat activations, per-stem onset envelopes,
RMS, spectral, HPCP). Consumer: `stable-audio-tools/scripts/whole_track_target_source.py`
— `resample_axis0()` slices `[start,end]` and resamples to any target T. Also see the
SA3 crop companions in `latents_sa3/*.TIMESERIES.npz` (sliced to T=4096 + a
`relative_position_ts` ramp = normalized position-in-source-track).

**ROCm env.** SAT `rocm_env.yaml` + `stable_audio_tools/rocm_env.py` is canonical;
SA3 mirrors it via `apply_profile`. mir has its **own** `src/core/rocm_env.py`
(`setup_rocm_env()`), independent. Tunings cache: `~/pytorch-tunings-7.2.3` (for torch
2.10; the `-7.2.2` dir is for 2.9.1 and **fails** TunableOp's validator under 2.10).
Profiles: inference = `MIOPEN_FIND_MODE=2`; training = `MIOPEN_FIND_MODE=6` —
**but see gotcha below for SA3 medium.** Shell exports override the YAML (`setdefault`).

**Rendering / audition.** SAT owns it: `scripts/render_audition*.py` → `renders/<set>/`
(+ `manifest.json` + `index.html` browser). Audited by mir's Audiobox Aesthetics
(`mir/src/timbral/audiobox_aesthetics.py`, run with **mir** venv; single-file mode —
batch mode OOMs WavLM at ~8 GB on 16 GB).

**Generative source separation / editing (SA3).** Text-prompted "separation" on SA3
`medium-base` (rectified flow). Two scripts in `stable-audio-3/scripts/`:
`sa3_flowsep.py` = inversion-free **FlowEdit/AUDEDIT** (difference-velocity field,
robust to high cfg, naturally anchored — the published SOTA-on-SA3 path);
`sa3_zerosep_rf.py` = true **RF-Solver** flow-inversion (Taylor reverse-Euler;
near-transparent, round-trip rel-err 0.23) + an **η faithfulness controller** (pull
predicted-clean `z0` toward the encoded mixture by η∈[0,1] for steps t≥τ; η=0
clean-but-untethered, **η≈0.3–0.5 = the separation sweet spot**, η≈0.7 rebuilds the
mix). Both are generative re-synthesis, **not masking** → for clean drum/bass stems use
mir Demucs/BS-RoFormer; the generative niche is **open-vocab** ("isolate the acid lead").
The old `mir-same-chroma/.../sa3_zerosep_lite.py` was plain SDEdit (no input tie — don't
use). Details: `WORKLOG.md` 2026-06-18.

---

## 5. Known cross-project gotchas (the stuff that bites)

- **`MIOPEN_FIND_MODE=6` CRASHES SA3 medium's DiT** (MIOpen `std::vector` assertion /
  coredump). Use `MIOPEN_FIND_MODE=2` for SA3 medium training. Mode 6 is fine for the
  tiny LatCH heads. *(2026-05-31)*
- **batch=1 + SA3 variable-length training thrashes the GEMM/Triton kernel cache** —
  every track's unique sequence length T is a new kernel shape. Fix: fixed **T=4096**
  beat-aligned crops (`latents_sa3`). *(2026-05-31)*
- **TFG / LatCH guidance must run fp32 on SA3** — fp16 (model_half default) clashes
  with backprop grad dtypes.
- **Mantu + Lehto are removable** — both must be mounted or work stalls.
- INT8/INT4 quantization is non-functional on ROCm (use bf16 + FA2).
- SA3 base model id is **`small-music-base`** / `medium-base` — there is no `small-base`.
- **SA3-medium LatCH guidance needs gain ≈ 48–96**, not the SAO-Small default of 8 (SAME-L's
  256-d latent is ~10× less gain-sensitive). At gain 8 heads steer the right way with ~2%
  authority — `corr=1.0` is a *mirage* (rank-corr ≠ magnitude); judge by spread. Probe R²
  predicts per-head control. `latch_guided.head_loss` now supports `smooth_l1`/`huber`/`l1`
  (was mse/bce_logits only — smooth_l1-trained heads previously raised `Unknown loss_type`). *(2026-06-01)*
- **SA3 generative separation/editing must use a `-base` checkpoint** (post-trained =
  stochastic ping-pong, non-invertible, cfg inert). **Invert at cfg≈1** — high cfg ruins
  recoverability. The RF-Inversion `(anchor−x)/(1−t)` controller has the **wrong sign and
  blows up at t→1 under SA3's descending-t Euler**; use the stable **z0-anchor**
  (mean-guidance) form instead. `env-corr↗mix` is a faithfulness proxy only for the
  **dominant** source — on a full arrangement every isolated source scores low. *(2026-06-18)*
- **SA3 LatCH head families differ — load via the canonical loader, never hardcode arch.**
  The same-l production heads are `stable-audio-3/latch_weights_sa3_medium/latch_sa3_<feat>_best.pt`
  (14 heads: `adaln_zero`, `standardized`, **depth 4**). The sibling `latch_weights_sa3/` holds
  epoch-numbered snapshots (`_ep<N>.pt`, simpler `concat` keys, **no `_best.pt`**). Constructing
  `LatCH(dim=256, depth=6, num_heads=8, default t_injection)` silently fails to load the medium
  heads (state-dict mismatch). Use `stable_audio_3.models.latch.load_latch_from_checkpoint(path,
  device)` — it auto-detects in/out channels, dim, depth, num_heads, t_injection and attaches
  `std_mean`/`std_std` as `head.metadata`. The SA3 latent explorer player defaults to the
  `_medium` dir for this reason. *(2026-06-19)*
- **Audio file writers CLIP fp16 / out-of-range float.** `torchaudio.save` (especially the
  new **torchcodec** backend) and most WAV writers expect samples in **[-1, 1]**; feeding
  **fp16** or SA3's raw **>1.0 peaks** clips/distorts (this bit the riffer auditions). Always
  **float32 → peak-normalize (or clamp) → int16 PCM** before writing — the SA gradio GUI fix
  (`stable_audio_tools/interface/gradio.py`). In `avp_sa3`, use the shared helper
  `sa3_control.audio_io.save_audio()` (never `torchaudio.save(x.float().cpu(), …)` raw). *(2026-06-19)*
- **Exporting SAME/SA3 to ONNX — two non-obvious blockers.** (1) `SA3_DISABLE_FLASH_ATTN=1`
  is necessary but NOT sufficient: with flash off, SAME's sliding-window layers fall to
  **FlexAttention** (a torch.compile HOP the ONNX dynamo exporter can't translate — dies on
  the mask_mod `bitwise_and` graph output). Also set
  `transformer.flex_attention_available=False; transformer.flex_attention_compiled=None`
  → math-equivalent masked-SDPA, exports clean. (2) **opset ≥ 18** (requesting 17 emits an
  invalid `Split(num_outputs)` ORT rejects). Export the **fixed-chunk** unit (`decode` on
  `[1,256,L]`) and loop on the host — never a dynamic-T graph (SAME folds length-dependently).
  Validated CPU: decoder/encoder L128 cos≈0.9999. `onnxscript`/`onnxruntime` install is
  additive (doesn't bump the ROCm torch/numpy). Tooling: `stable-audio-3/scripts/export_same_onnx.py`
  + `decode_onnx.py`; details `stable-audio-3/docs/onnx-amd-inference.md`. **GPU-verified**: the
  decoder runs 100% on the MIGraphX EP (no CPU fallback), cos=0.999998 vs torch, RTF ~39×. The
  MIGraphX EP is only in the **mir venv** (`onnxruntime_migraphx`); the SA3 venv's `onnxruntime`
  is CPU-only. **Catch: a ~9-min MIGraphX AOT compile per session** (CPU-bound; not tuning or chunk
  size). ORT compiled-model caching is **not exposed** in this `onnxruntime_migraphx` 1.23.2 build
  (save/load options rejected → silent CPU fallback). Mitigate by **compiling once in a long-lived
  server** (the latent_server pattern) or a newer ORT-ROCm build. *(2026-06-20)*

---

## 6. Work log

Reverse-chronological, append-only: **`WORKLOG.md`** (sibling of this file). Read it at
session start if you're picking up cross-project work; append an entry when you finish
something that another agent would want to know.

## 7. Install layer

This repo (`Taikakim/avp-audio-craft`) is the **meta-repo + install
orchestrator**. `./install.sh` clones the three forks (`projects.toml` lists
them) and runs each one's own `install.sh`. Each per-repo install script is
standalone — you can clone just one fork and run its `./install.sh` without
needing this meta-repo. See `README.md` for the standard new-machine flow and
`docs/flash-attn-ck-rdna4.md` for the RDNA4 / ROCm 7.14 / CK flash-attn recipe
that the SA3 install uses.
