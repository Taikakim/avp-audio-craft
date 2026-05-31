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
- **`SAO/stable-audio-3/`** — SA3 medium model (1.5 B DiT), LoRA finetune, SA3
  LatCH (phase 1). The bigger/newer generation.
- **`SAO/sa3-rocm7.13-test/`** — experimental: native **CK (Composable Kernel)
  flash-attn** build for RDNA4. Separate ROCm 7.14-preview stack. See `docs/venvs.md`.
- **`SAO/torchcodec/`**, **`SAO/my_wheels/`** — custom torch+ROCm wheel/codec builds.

## Data (both drives removable; see MASTER §2 for the full table)

- **Mantu** (`/run/media/kim/Mantu`) — source audio. `ai-music/Goa_Separated`
  (full tracks + stems + grids), `goa_crops` (older 11.9 s crops).
- **Lehto** (`/run/media/kim/Lehto`) — derived. `latents` (SAO-Small 64-d),
  `latents_sa3` (SA3 256-d, T=4096), `timeseries` (100 Hz whole-track), `latents_stems`.

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
