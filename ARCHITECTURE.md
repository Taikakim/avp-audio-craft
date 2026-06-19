# ARCHITECTURE — what's where (1-page map)

Brief orientation. Detail lives in `MASTER.md` (cross-cutting facts) and `docs/`.

## The pipeline, end to end

```
  AUDIO (Mantu)                 MIR (mir/)                    LATENTS (Lehto)              MODELS (SAO/)
  ┌────────────┐    extract     ┌──────────────┐   encode    ┌──────────────┐   train     ┌──────────────┐
  │ Goa tracks │ ─────────────► │ .INFO + beat │ ──────────► │ .npy latents │ ──────────► │ SA Open Small│
  │  + stems   │   features,    │ grids, time- │  per-VAE     │ + .json +    │  LoRA /     │ SA3 medium   │
  │            │   beat grids   │ series (100Hz)│  grids       │ .TIMESERIES  │  LatCH heads│ (DiT)        │
  └────────────┘                └──────────────┘             └──────────────┘             └──────────────┘
        │                                                            │                            │
        └── source of truth                          targets for ◄──┘          LatCH guidance ◄──┘
            (4470 full tracks, 4829 crops)           LatCH heads               steers generation
```

## Repos (see MASTER §1 for venvs)

- **`mir/`** (`/home/kim/Projects/mir`) — extracts MIR features → `.INFO` sidecars,
  beat/downbeat/onset grids, whole-track 100 Hz timeseries, Audiobox aesthetics.
  The "what does this audio contain" engine. Feeds everything downstream.
- **`SAO/stable-audio-tools/`** — the "audio-tools-AVP" fork. **LatCH heads**
  (training-free guidance), **FusionOpt**, SAO-Small training/finetune, audition
  renders. The LatCH research hub; `LATCH_RESULTS.txt` is its lab notebook.
  Also hosts **`avp_sa3/`** — SA3 tooling (runs on the SA3 .venv, **no SA3-fork
  changes**): `sa3_control/` (control-adapter training on `latents_sa3` + timeseries
  = the similarity riffer) and `scripts/` (`sa3_flowsep`/`sa3_zerosep_rf` generative
  separation, `stem_score`). See `avp_sa3/ARCHITECTURE.md`.
- **`SAO/stable-audio-3/`** — SA3 medium model (1.5 B DiT), LoRA finetune, SA3
  LatCH (phase 1). The bigger/newer generation. **Kept upstream-syncable** — tooling
  lives in `audio-tools-avp`, only SA3-side interface code (LatCH, ROCm) here.
- **`SAO/sa3-rocm7.13-test/`** — the **ROCm 7.14 / CK flash-attn stack** (torch
  2.12+rocm7.14, `.venv` + `flash-attention` rdna branch built with CK kernels for
  gfx1201). CK FA validated for `sa3_control` **training** (2026-06-18) after the
  backward grad-count patch. Enable per `docs/flash-attn-ck-rdna4.md`
  (`FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE` + §5b patch). The 2× vs Triton FA2 is
  still to be pilot-measured. See also `docs/venvs.md`.
- **`SAO/torchcodec/`**, **`SAO/my_wheels/`** — custom torch+ROCm wheel/codec builds.

## Data (both drives removable; see MASTER §2 for the full table)

- **Mantu** (`/run/media/kim/Mantu`) — source audio. `ai-music/Goa_Separated`
  (full tracks + stems + grids), `goa_crops` (older 11.9 s crops).
- **Lehto** (`/run/media/kim/Lehto`) — derived. `latents` (SAO-Small 64-d),
  `latents_sa3` (SA3 256-d, T=4096), `timeseries` (100 Hz whole-track), `latents_stems`.

## Reusable plumbing — check here before building

Already built across the repos; **reuse, don't rebuild.** Keep this list current —
it's the "check what we already have" index any instance reads first.

- **bungee time-stretch / pitch-shift** — `bungee_python` 0.2.1 binding built in
  `mir/pitch_venv` (py3.14) from `mir/repos/bungee`; A/B comparison GUI
  `mir/pitch_shifter_gui.py` (bungee · rubberband · pedalboard · sox).
  `from bungee_python import bungee; bungee.Bungee(sr, ch).time_stretch / .pitch_shift`.
- **MIR features + 100 Hz whole-track timeseries** — `mir/`; window consumer
  `stable-audio-tools/scripts/whole_track_target_source.py`.
- **pre-encoded SA3 latents + grid-aligned controls** — `Lehto/latents_sa3`
  (`.npy`+`.json`+`.TIMESERIES.npz`, 21 fields @ T=4096); loader
  `stable-audio-tools/avp_sa3/sa3_control/dataset.py`.
- **SA3 generative separation / riffer + stem scoring** —
  `stable-audio-tools/avp_sa3/scripts/` (`sa3_flowsep`, `sa3_zerosep_rf`, `stem_score`)
  + control-adapter trainer `avp_sa3/sa3_control/`.
- **Inference recipes** (validated technique + param sets: separation / riffer / steering /
  guidance / eval) — `stable-audio-tools/avp_sa3/recipes/inference_recipes.yaml`. Check here
  before re-tuning; consumed by the CLI tools and (planned) the mir explorer's recipe picker.
- **LatCH heads + guidance** — `stable-audio-tools` (`LATCH_RESULTS.txt`);
  `stable-audio-3/stable_audio_3/inference/latch_guided.py`. Load any head with
  `stable_audio_3.models.latch.load_latch_from_checkpoint(path, device)` — it
  auto-detects dim/depth/num_heads/t_injection (handles both head families); the
  **same-l production heads are `stable-audio-3/latch_weights_sa3_medium/*_best.pt`**
  (adaln_zero, standardized, depth 4). Don't hardcode the architecture.
- **SA3 latent explorer (viewer + decode/mix/steer player)** — `mir/plots/explorer_sa3/`
  (Dash viewer, mir venv) + `mir/scripts/latent_server_sa3.py` (SAME-L decode player,
  SA3 venv, port 7892; `/decode /source /mix /steer`). GPU-validated. Reviews SAME-L
  encoder quality on `latents_sa3` + latent-space DJ mixing + LatCH-head auditioning.
  See `mir/plots/explorer_sa3/README.md`. (mir branch `sa3-latent-explorer`.)
- **SAME → ONNX for AMD inference (ORT + MIGraphX)** — `stable-audio-3/scripts/export_same_onnx.py`
  (fixed-chunk export of the SAME decoder/encoder; CPU-validated cos≈0.9999) +
  `decode_onnx.py` (host chunk-loop runner, MIGraphX>ROCm>CPU). Low-VRAM decode that runs
  without the torch stack / alongside training. Gotchas (FlexAttention, opset 18) +
  how-to: `stable-audio-3/docs/onnx-amd-inference.md`. GPU/seam test pending.
- **Audiobox aesthetics scorer** — `mir/src/timbral/audiobox_aesthetics.py` (mir venv, single-file).
- **CK flash-attn (RDNA4 / ROCm 7.14, faster than Triton FA2)** — built in
  `SAO/sa3-rocm7.13-test/` (its `.venv` + `flash-attention` rdna branch). Use
  `FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE` before `import flash_attn`; for TRAINING
  apply the one-line backward grad-count patch. Recipe + patch: `docs/flash-attn-ck-rdna4.md`.

## Doc map

| File | Purpose |
|---|---|
| `ARCHITECTURE.md` (this) | 1-page what's-where |
| `MASTER.md` | cross-cutting facts always loaded into every session |
| `WORKLOG.md` | append-only session log |
| `docs/venvs.md` | the venvs + the CK-flash-attn build |
| `docs/commands.md` | the commands that actually get run |
| `docs/latch.md` | what LatCH is + how heads are trained |
| `docs/training-findings.md` | recipes, params, **why latents are T=4096** |
| `docs/lessons-learned.md` | mistakes to not repeat |
| `docs/todos.md` | open work |
