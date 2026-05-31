# MASTER — Audio Generation Pipeline (mir + Stable Audio)

**Single source of truth for facts that span repos.** Each project's `CLAUDE.md`
imports this file. When you discover something that affects more than one repo —
a path, a venv quirk, a cross-cutting gotcha — update **this file**, not just your
local `CLAUDE.md`. Append a dated line to `WORKLOG.md` (sibling) for anything you
ran, built, or learned this session.

> Why this exists: Claude Code's auto-memory is siloed per working directory, so a
> fact learned while working in `mir/` is invisible to an agent working in
> `stable-audio-3/`. This file is the shared layer. (2026-05-31)

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

---

## 6. Work log

Reverse-chronological, append-only: **`WORKLOG.md`** (sibling of this file). Read it at
session start if you're picking up cross-project work; append an entry when you finish
something that another agent would want to know.
