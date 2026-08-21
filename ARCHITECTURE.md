# ARCHITECTURE — what's where (1-page map)

Brief orientation. Detail lives in `MASTER.md` (cross-cutting facts) and `docs/`.

## The pipeline, end to end

```
  AUDIO (Mantu)                 MIR (mir/)                    LATENTS (NVMe)              MODELS (SAO/)
  ┌────────────┐    extract     ┌──────────────┐   encode    ┌──────────────┐   train     ┌──────────────┐
  │ Goa tracks │ ─────────────► │ .INFO + beat │ ──────────► │ .npy latents │ ──────────► │ SA3 medium   │
  │  + stems   │   features,    │ grids, 46-fld│  SAME (SA3)  │ + .json +    │  DoRA /     │ (1.5B DiT)   │
  │  + avp     │   beat grids   │ timeseries   │  64-d (SA1)  │ .TIMESERIES  │  LatCH/FiLM │ SA-Small     │
  └────────────┘                └──────────────┘             └──────────────┘             └──────────────┘
        │                                                            │                            │
        └── source of truth                          targets for ◄──┘          LatCH guidance ◄──┘
            (goa 4470 + avp own-music)                LatCH heads               steers generation
```

## Where things live — the folder & drive map

**Read this before asking "where is X" or spelunking with `find`.** Built from a live
`ls`/`du` sweep (THE-FINN, 2026-08-18), not memory — if a path here 404s, the drive is
probably unmounted (all three are removable), not gone; see Data & drives below. Sizes
are a snapshot and will drift.

### SAO/ top-level (this repo)

| Path | ~Size | What | Detail |
|---|---|---|---|
| `stable-audio-tools/`, `stable-audio-3/` | 64G / 16G | the two model thin-forks | Repos § below |
| `onnx/` | ~0 (symlinked out) | ONNX export/inference suite; large `.onnx.data` exports live on the UUID drive, see Data below | §D |
| `control/` | 2M | `sa3_control` adapter training + recipes + findings | §B |
| `latch/` | 524K | LatCH head **training code** (SA3-side) | §B |
| `eval/` | 14G | scoring/audition/page-gen tooling **+** `eval/musicology/` corpus study (13.5G of it is MIDI/soundfont renders behind small feature-extraction outputs — regeneratable, not source data) | §C |
| `lumi/` | 68M | sbatch templates + LUMI toolchain scripts (the code that gets rsync'd to the cluster) | §E |
| `Misc/` | 154M | site builder, model-index tooling, fleet comms protocol (`agent_dialogue.py`), patrol scripts | §C / §F |
| `docs/` | 1.5M | depth docs + `docs/superpowers/specs/` (the running per-subsystem source of truth) | Doc map below |
| `papers/` | 781M | external prior-art index (`knowledge.md`) + paper PDFs/POV notes | §F |
| `profiles/` | 47M | per-agent journals, task logs, daily digests — the comms/patrol record | §F |
| `dialogue/` | 1.1M | **weekly-archived** `AGENT_DIALOGUE.md` rollups; the LIVE log is `AGENT_DIALOGUE.md` at repo root | §F |
| `site/` | 4M | BUILT output of `Misc/build_site.py` — public site staging; don't hand-edit, rebuild instead | §F |
| `web/` | 28K | PHP backend (`comment.php`, `ratings.php`) deployed alongside the public site | §F |
| `blog/` | 40K | Kim's week-in-review draft posts | — |
| `latch_weights_ema_onset/` | 377M | ONE specific LatCH head family (onset-envelope EMA variant) — **not** the same set as `stable-audio-3/latch_weights_sa3_medium/` | §B |
| `checkpoint-stats/` | 6.9M | training-trajectory stats output (`checkpoint_trajectory_stats.py`) | §B |
| `runs/` | 112K | small **local** (non-LUMI) experiment outputs | — |
| `my_wheels/` | 82M | built custom torch/ROCm/flash-attn `.whl` files | §D |
| `torchcodec/` | 419M | custom codec build | §D |
| `flash-attention/` | 1.3G | the CK flash-attn build **source tree** (gfx1201/RDNA4 branch) that produces `my_wheels/` | §D, `docs/flash-attn-ck-rdna4.md` |
| `control_eval_queue/` | 225M | CPU control-adapter eval-server queue (`inbox`/`processing`/`outbox`) | §D |
| `composed_eval_queue/` | 2.7G | composed-render eval-server queue, same inbox/processing/outbox pattern | §D |
| *(`latch_eval_queue/` — referenced in §D, not currently present)* | — | created **on demand** by `latch_eval_server.py --queue-root` when a job is submitted; absence just means none are queued right now, not a broken path | §D |
| `renders_pull/` | 1.5G | LUMI renders pulled to desktop for listening/audit (e.g. `dronesweep`) | — |
| `riffer-evals/` | 822M | **its own git repo** (`github.com:Taikakim/riffer-evals`, separate remote) — public riffer eval site | — |
| `Gemini/` | 8K | Gemini deep-research handoff notes/templates — see the Gemini-brief convention (feed problem+phenomenology only, never code/files) | — |
| `music/` | 188K | small reference-audio folder (`goa-ibiza`) | — |
| `.render_root_aliases/` | — | symlink farm aliasing renamed render-root dirs (e.g. `subloss_goa_k2`) so old paths keep resolving | — |
| `wandb/` | 1.4M | local W&B run cache | — |
| `logs/` | 45M | assorted process logs, not curated — ephemeral | — |
| `.venv/` | 11G | SAO's own default venv — see MASTER §3 for which task uses which venv | MASTER §3 |

**Symlinks at repo root:** `Mantu` → `/run/media/kim/Mantu` (convenience link to the drive,
see below) · `evals` → `/home/kim/.cache/evals_aac` (AAC-transcoded render cache backing
the public eval pages — NOT where source renders live).

**Repo-root logs/`.log*` clutter and stray `~`-backup files** (e.g. `.fp32_matrix_render.log*`,
`EVAL_NOTES.txt~`) are leftover process output, not documentation — ignore unless actively
debugging the job that made them; periodic cleanup is patrol's job, not yours to chase.

### mir/ (`/home/kim/Projects/mir`, sibling project)
Has its own `ARCHITECTURE.md` — don't re-derive its internal layout here. Top-level:
`src/` (the extraction code, §A above documents the pieces we actually call), `data/`,
`models/` (Music Flamingo GGUF etc.), `plots/` (the SAME latent explorer), `repos/`
(vendored `bungee` build), `pitch_venv/` (bungee's own venv).

## Repos (see MASTER §1 for venvs)

- **`mir/`** (`/home/kim/Projects/mir`) — extracts MIR features → `.INFO` sidecars,
  beat/downbeat/onset grids, whole-track 100 Hz timeseries, Audiobox aesthetics.
  The "what does this audio contain" engine. Feeds everything downstream.
- **`SAO/stable-audio-tools/`** — the "audio-tools-AVP" **thin fork** (editable;
  `stable_audio_tools` package deltas only): **LatCH heads** (training-free guidance),
  **FusionOpt**, `rocm_env`, the FA backward patch. `LATCH_RESULTS.txt` is the LatCH lab
  notebook. The first-party *tooling* that imports it now lives in the master repo:
  LatCH head training + auditions in **`latch/`** (`train_latch`, dataset/model, probes),
  and SA3 control-adapter tooling in **`control/`** (`sa3_control/` riffer trainer on
  `latents_sa3` + timeseries; `scripts/` `sa3_flowsep`/`sa3_zerosep_rf` generative
  separation, `stem_score`). See `control/ARCHITECTURE.md`.
- **`SAO/stable-audio-3/`** — SA3 medium model (1.5 B DiT), LoRA finetune, SA3
  LatCH (phase 1). The bigger/newer generation. **Kept upstream-syncable thin fork** —
  tooling moved to the master repo (`onnx/`, `control/`, `eval/`, `latch/`); only
  SA3-side package code (LatCH, ROCm, attn/APG patches) stays here.
- **`SAO/sa3-rocm7.13-test/`** — the **ROCm 7.14 / CK flash-attn stack** (torch
  2.12+rocm7.14, `.venv` + `flash-attention` rdna branch built with CK kernels for
  gfx1201). CK FA validated for `sa3_control` **training** (2026-06-18) after the
  backward grad-count patch. Enable per `docs/flash-attn-ck-rdna4.md`
  (`FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE` + §5b patch). The 2× vs Triton FA2 is
  still to be pilot-measured. See also `docs/venvs.md`.
- **`SAO/torchcodec/`**, **`SAO/my_wheels/`** — custom torch+ROCm wheel/codec builds.

## Data & drives (all removable; see MASTER §2 for the historical detail)

All three drives also hold Kim's non-project files (games, personal media, torrents) —
not enumerated here, only the project-relevant paths are.

- **NVMe** (`/home/kim/Projects/`) — the live SA3 latents. `latents_sa3` (14 G; 5401
  `.npy`+`.json`+`.TIMESERIES.npz`, 256-d, T=4096, 10.767 Hz) + `latents_avp` (6 G, own-music).
  **Backup:** a second copy at `/run/media/kim/Mantu/sa3-latents_backup/latents_sa3/`
  (verified in parity 07-12; sync is **manual**, keep it current). `Lehto/latents_sa3`
  was removed 07-04 — do not look there.
- **Mantu** (`/run/media/kim/Mantu`) — source audio + checkpoints + the latents backup.
  `ai-music/Goa_Separated` (4470 full tracks + stems + grids) · `goa_archive_extracted`
  (the RAW archive `goa_archive_features`/`goa_archive_captions` were built FROM) ·
  `sa3_lora_runs` + `sa3_control_runs` (checkpoints/eval runs, moved off Lehto 07-04) ·
  `sa3-latents_backup` (the NVMe latents mirror, above) · `sa3_mutated_checkpoints`,
  `latch_sweep`, `lumi_runs` (an early **partial** LUMI grab, superseded — see UUID drive).
- **Lehto** (`/run/media/kim/Lehto`) — **training data only**. `timeseries` (37 G, the
  **46-field** whole-track set), `latents` (SA-Small 64-d), `latents_stems`,
  `latents_sa3_lora300`, `latents_sa3_stem_chroma`, `sa3-latch-latents`.
- **UUID drive** (`/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d`) — **canonical
  target for ALL LUMI content** (Kim 2026-08-17 drive-layout ruling; MASTER §2). 481G
  free/88% used as of 2026-08-17 — margin is tight, verify before a large pull. Project-relevant
  top-level paths:
  - `lumi_runs/` — the canonical rsync/grab target (`runs/`, `renders/`, `analysis/`,
    `logs/`, the public `RUN_AUDIT_BOARD*.html`/`dora_table_public.html`).
  - `sao_models/` — **where W's 2026-08-17 models-move landed** (`onnx_exports/`,
    `sa3_onnx/`, `sat_models/`), symlinked back into the SAO repo at `onnx/exports`,
    `stable-audio-3/*.onnx*`, `stable-audio-tools/models` respectively — don't `rm -rf`
    the repo-side path expecting to free space, it's a symlink now.
  - `goa_archive_features/` — the goa big-set feature index (`index.jsonl`, 23,231 tracks:
    key/path/loudness/`maest_vec` 768-d) + `npz/<sha1>.npz` fuller sidecars. Feeds
    `eval/build_goa_archive_sidecar.py`'s caption-text build. Full doc: `docs/goa-archive-buildout-plan.md`.
  - `goa_archive_captions/`, `suomisoundi_{by_track,captions,features,latents,stems,timeseries}` —
    per-corpus caption/feature/latent staging for the two active big-set corpora.
    ⚠️ **`goa_archive_captions/` also exists nested under `lumi_runs/goa_archive_captions/`
    — two different directories, same name, NOT a symlink** (checked directly, 2026-08-18).
    The `lumi_runs/` copy has the fresher content (a `granite_pre_v5_backup/` from tonight's
    fix) — flagging, not resolving; check both before assuming staleness either way.
  - `Models/`, `comfyui/`, `Heroic_Games/`, `torrents/`, etc. — **not SAO's**, Kim's other uses of the drive.
- **The eval-metrics DB** `eval/clip_metrics.db` (~43 k clips × 14 metrics incl. GPU-costly
  Audiobox CE/PQ) is NOT a latent sidecar and NOT in the latents backup — snapshotted to
  Mantu 07-19; recurring backup is a TODO (`docs/open-threads.md`).

### LUMI cluster (`akekim@efp.lumi.csc.fi`, project `465003186`) — see `.claude/skills/lumi-ops/SKILL.md`
- **`/project/project_465003186/code/`** — the rsync'd mirror of this repo's `control/`,
  `eval/`, `latch/`, `lumi/`, `Misc/`, `mir-src/`, `stable-audio-3/` (plus `job-*/` — ~109
  leftover per-job dirs, and stray `*.out` logs that accumulate there rather than in `/scratch`).
  `/project/.../containers/sa3.sif` is the legacy training container.
- **`/scratch/project_465003186/`** — the actual working set: `goa_archive{,_captions,_features,_stems}`,
  `suomisoundi_{archive,captions,latents,stems}`, the offload venvs (`goa_offload_venv{,_mt}`,
  `sa3_train_venv_mt`, `bungee_venv`), `hf_cache`/`hf_offload`, source checkouts (`avp_src`,
  `goa_src`), and stray `slurm-*.out` from ad-hoc srun probes.
- Container images: `/appl/local/laifs/containers/lumi-multitorch-*/lumi-multitorch-full-*.sif`
  — resolve with `sort | tail -1` (unpinned, drifts — see `docs/writing-lumi-sbatches.md`).

## Reusable plumbing — the internal reuse index (check here before building)

Already built across the repos; **reuse, don't rebuild.** This is the *internal* reuse
index; `papers/knowledge.md` is the *external* prior-art index, and `docs/open-threads.md`
tracks open/dropped work. Paths are SAO-relative unless a repo is named. Last full
inventory sweep: 2026-07-20 (4 agents across mir/SAO); **top-up 2026-08-05 (doc-oversight)** — see
the block below for tools built since. Add new reusable building blocks here as they land — a stale
index is how repeat work happens.

**Built since the 07-20 sweep (doc-oversight 2026-08-05, not yet filed into A–F below):**
`eval/build_run_audit_board.py` (run-audit board) · `eval/melody_wall_analysis.py` (whitened-chroma
melodic-recurrence metric — raw chroma saturates on tonal goa) · `eval/precision_injection_ab.py` +
`stable-audio-3/stable_audio_3/training/stochastic_rounding.py` (precision A/B + SR residual writes) ·
`eval/cross_attn_mask_ab.py` (cross-attn mask A/B) · `eval/build_hf_repair_pairs.py` +
`eval/train_hf_repair.py` + `eval/eval_hf_repair.py` (HF reconstruction-filter pipeline) ·
`eval/build_clap_hyperparam_table.py` · `eval/build_clip_scores_export.py`. A full re-sweep is still owed.
· **B7 MIR-conditioner training stack (2026-08-21, C)** — `stable-audio-3/scripts/mir_control.py`
(36-ch field registry over every .TIMESERIES field; packs = channel subsets; crop-exact control
slicing; per-BLOCK zero-init projections into the DiT's native `modular_local_cond` inlet — it is
per-TransformerBlock, NOT global; in-training control-ablation meter + self-writing report.md) +
`build_ctrl_packs.py` (prebuilt `<latent_dir>_ctrl/` SIBLING dirs — ⚠️ co-located .ctrl.npy gets
recursively globbed AS LATENTS by PreEncodedDataset) + `train_lora --mir_ctrl_*` +
`lumi/sbatch/mirctrl_bracket.sbatch`. EXPERIMENTS B7.
· **Top-100-by-PQ page pipeline (2026-08-21, C)** — `eval/build_top100.py` (3 resumable stages:
per-frame-length PQ-top candidate pools from `clip_metrics.db` → MERT-v1-330M embeddings (rhythm
layers 3-6 + melody layer 23, cached) → select with two-pass dedup: hard name-level (one clip per
(model,ep,prompt,seed) knob-group, ≤3 epochs per take-family) then greedy MERT-cosine with a CAPPED
calibrated threshold — in a homogeneous corpus the dup/distinct cosine distributions overlap near
1.0, a threshold alone cannot do this) + `Misc/build_top100_page.py` (renders → `evals/top100.html`,
same-playhead, full recipe columns, three-audience explainer). Ranking is PQ ALONE per W's 668-vote
preference fit.

### A · MIR features & audio analysis (`mir/`, `mir/bin/python`)
- **bungee time-stretch / pitch-shift** — `bungee_python` 0.2.1 (built in `mir/pitch_venv` from `mir/repos/bungee`); A/B GUI `mir/pitch_shifter_gui.py`. `bungee.Bungee(sr,ch).time_stretch/.pitch_shift`.
- **MIR base pipeline + whole-track timeseries** — `mir/src/spectral/whole_track_timeseries.py`; window consumer `stable-audio-tools/scripts/whole_track_target_source.py`. **Now 46 fields** (20 legacy @100 Hz + 26 expanded @ native rates). The expanded extractor is **`mir/src/spectral/whole_track_expanded.py`** (`FeatureExtractor`: MAEST 768-d embeds `_maest`, genre/mood/instrument curves, DEAM/emoMusic V-A, attack-transient family, stereo width/corr `_stereo_fields`, Bark/ERB, NNLS→chroma_linmap, chords, EBU-R128, dyn-complexity; TF pinned CPU-only). **Consumers must read the sidecar `field_rates` — not everything is 100 Hz.** Incremental backfill: `whole_track_timeseries.py --add-fields`.
  **THIS is the current SA3 pipeline (2026-08-15, Kim confirmed) — do not confuse with `mir/master_pipeline.py` / `mir/USER_MANUAL.md`'s `.INFO`/`.BEATS_GRID` framework, which is an OLDER system (pre-dates the SAO spec, not yet updated to it) producing a DIFFERENT on-disk format that `sa3_encode_from_manifest.py` does not consume.** `whole_track_timeseries.py --expanded` needs a per-track-folder root (`<track>/full_mix.*`, matching `find_full_mix()`) — for a flat corpus, hardlink (not symlink — Kim's call, symlinks "mix things up" for some consumers; not copy — wastes disk on a large corpus) each file into `<out>/<track_name>/full_mix.<ext>` first. Output `.TIMESERIES.npz` uses `__meta__` (double underscore) as the JSON metadata key with a `field_rates` sub-dict — a DIFFERENT key than `goa_archive_mir.py`'s own `meta` (single, no field_rates), which is a separate, INCOMPATIBLE packaging built for a different purpose (goa captioning/stats/clustering feed) reusing the same underlying `ExpandedExtractor` — don't use it as a `.TIMESERIES.npz` source without a conversion pass.
- **Loop / longform meter** — `mir/src/tools/recurrence_meter.py` (v3 whitened-patch loopiness/novelty + `calibrate_source`, now + corr-dim + soft-DET/RQA). **The loop-metric core — import `novelty_curve(x,fps)`, don't re-derive.** Also: `tempo_iqr.py` (within-clip tempo instability), `section_extractor.py` (Foote SSM boundaries + energy arcs → `.sections.json`), `melodic_movement_ladder.py` (chroma-flux/pc-transition U-shape scorer).
- **Timbral extractors** — `mir/src/tools/extract_timbral_hdb.py` (AudioCommons hardness/depth/booming, tracks + per-crop) · `extract_reverb_depth.py` (RT60/depth, the one *safe* wrapper of the hang-prone reverb feature, SIGALRM-guarded).
- **Essentia classifier suite** — `mir/src/classification/` (`effnet_onnx` embedding backbone, `gmi_onnx` genre/mood/instrument heads, `vggish_onnx`, `essentia_features{,_optimized}`) + `src/tools/` (`crop_genre`, `classify_new_corpus` for onboarding a new corpus, `measure_genre` eval scorer, `build_feature_table` the join layer, `genre_vocab`); provision with `scripts/download_essentia_models.py`.
- **Audiobox aesthetics scorer** — `mir/src/timbral/audiobox_aesthetics.py` (single-file, mir venv).
- **Music captioning (Music Flamingo + Granite)** — `mir/src/classification/music_flamingo.py` + `granite_revision.py`, feeds `stable-audio-3/scripts/caption_tools.py`. **Check mir FIRST for any audio-understanding capability** (re-scouted the hard way 07-08).
- **T1/T2/T3 caption sidecars (`--caption_sidecar` training input)** — `eval/build_goa_archive_sidecar.py` (goa, **live-encode** `--data_dir` path, keyed on audio `rel`path — needs a custom `key_fn` at the `train_lora.py` call site) and its sibling `eval/build_suomisoundi_sidecar.py` (Suomisoundi, **pre-encoded** `--encoded_dir` path, keyed on the opaque shard-prefixed **latent filename stem** — `make_caption_sampler`'s *default* key resolution, no `key_fn` override; T1 = the known genre-hint text directly, no effnet classifier needed). **The two are keyed differently on purpose** — live-encode vs pre-encoded latents resolve `custom_metadata_fn`'s `info` dict differently; copying one script's key scheme onto the other's training mode silently drops every caption (2026-08-17). AVP's own builder is **`eval/granite_avp_pass.py`** (`--sidecar-only` rebuilds from the `granite_t2` already cached in the `.INFO`s — pure stdlib, no GGUF/GPU); its crops resolve captions through the **parent track**, since an augmented crop's `source_track` is `"<track>/<variant>"` and keying on the raw value covered originals only (284/2394 → 2353/2394 when fixed, 2026-08-17).
- **🔍 AUDIT A CAPTION TIER BEFORE TRAINING ON IT — TWO COMPLEMENTARY TOOLS, RUN BOTH.** They were
  built independently the same night (2026-08-18) and overlap only on the genre scan; each catches a
  fault class the other is blind to, so neither replaces the other.
  · **`eval/caption_sidecar_audit.py`** (W) — is the tier *informative and consistent*: how many
  DISTINCT prompts it really carries (goa's t2 is 23203/23231 unique strings but has only **345
  distinct 3-word openings, an 898-word vocabulary, and "intricate" in 93% of captions** — unique
  strings, one template, near-identical conditioning), whether tiers AGREE about the same track
  (tempo is the cheap tell), and the genre profile. Also records the corollary that decides re-run
  scope: **re-running Granite fixes t2 and does NOTHING for t3**, so a corpus "fixed" by re-revising
  alone still carries MF's mislabels — and scripts passing `--caption_probs 0,0,1` train on t3 ALONE.
  · **`eval/audit_caption_sidecar.py`** (C) — is the tier *grounded and correct*: Measures whether a granite/short tier actually reflects each track's own Music Flamingo prose (directed containment + IDF-restricted rare-term recall, paired vs shuffled). Tonight's numbers: suomisoundi **16.2×** (grounded), AVP **3.8×** (grounded, anchor-dominated), goa bigset Aug-4 build **1.24×** = chance — that tier was generated from FOLDER NAMES (`goa_granite_task.py::read_mf()` passed the path, not the nested `captions.prompt_type` text; G fixed in `63546e6`, regenerated as v5 job 21255037). **Two checks that FALSELY clear a contaminated tier, don't rely on them:** exact-duplicate rate (the bad tier was 99.8% distinct strings — the template just slot-fills word swaps + a BPM) and symmetric Jaccard (a 10-word tag vs a 100-word paragraph scores ~0.03 either way). Run this after ANY caption regeneration, and note the sidecar is a *derivative* — regenerating granite does nothing until the sidecar is rebuilt from it. **⚠️ The staleness trap bit again anyway, live, the very next day (C, 2026-08-18):** Kim's own audit run read the OLD contaminated numbers because the sidecar hadn't been rebuilt from the regenerated captions — see the general pattern in `docs/lessons-learned.md` § Process/coordination ("a derivative does not know its source changed"). **GROUNDING ≠ CORRECTNESS, a distinct failure this tool cannot see:** it measures whether a tag reflects its OWN track's MF prose, not whether that prose is true — v5 scored 19.24× grounded while the underlying MF genre text was itself ~99% wrong (goa corpus captioned with `genre_hint` defaulted EMPTY, MF guessed techno/industrial for 23,231 goa tracks; suomisoundi's real hint scored 97.4% correct on the same measure). **Check `genre_hint`/`GENRE_HINT_FILE` was actually populated before trusting a tier's genre content** — pair the grounding audit with a genre-content scan (first ~200 chars, or against the T1 effnet classifier below), don't run grounding alone. Detail + the fix: `docs/lessons-learned.md` § Data/latents.
  · **`eval/build_caption_hint_map.py`** (C, 2026-08-18) — per-track caption hints from real ID3/release
    metadata (mir's `{metadata}` idea, applied to the captioner). Emits `{sha1(relpath): "…release year:
    1996; genres: Goa Trance."}` for `goa_caption_task.py --genre-hint-map`, where it **composes with**
    (never replaces) the corpus-level `--genre-hint`. Use it whenever a corpus is NOT era-uniform: a single
    global hint asserts one era for everyone, which is right for the goa big-set (100% 1990s) and wrong for
    Goa_Separated (47% 90s, the rest 00s/10s/20s). Match audio with `--audio-stem full_mix`, not one
    extension — that corpus is 71% flac / 16% mp3 / 11% ogg / m4a / wav / aiff, and an extension filter
    silently drops 29% of it while reporting a clean count. `--rel-prefix` when the remote tree is deeper
    than the local one (rsync -R); `--verify-against` proves the keys hit before you ship the map.
    **Wrong-match guards are on by default** — mir fills these by fuzzy release lookup and gets a tail
    badly wrong (tracks dated before goa existed; "black metal" on a goa track; label so unreliable it is
    off by default). A wrong hint CONTRADICTS the global one it composes with, which is worse than silence.
  · **`eval/audit_caption_era_grounding.py`** (C, 2026-08-18) — did the year hint actually STEER the
  · **`eval/compare_trajectory_stats.py`** (C, 2026-08-18) — many runs' weight trajectories side by
    side, with convergence flags (RISING-VEL / LOW-EFF / HIGH-EFF / NORM-BLOWUP). Consumes the
    `*_trajectory.json` that `control/sa3_control/checkpoint_trajectory_stats.py` emits (per-run) and
    answers the comparative question instead: *do the arms that render broken look different in
    WEIGHT space from the arms that render fine?* Worth reaching for because it is independent of
    every audio metric — it cannot be confounded by a saturated measure, a mis-tokenised prompt, or a
    caption problem, all three of which bit us on 2026-08-18 alone. Empirical healthy band from 19
    completed runs: velocity ratio vN/v0 0.44-0.55, path efficiency 0.65-0.75, and every one of those
    19 falls inside it. Pass several dirs; duplicate labels across dirs are reported, not silently
    overwritten.
    captioner, or is it merely attached? Buckets captions by the decade in their own `genre_hint` and
    measures era-vocabulary lift per bucket. Complements `audit_caption_sidecar.py`: that one asks whether
    a tier reflects its track's MF prose (grounding) and whether the genre is true (correctness); this one
    asks whether a per-track hint changed the output at all. **A flat table is the finding** — hint loaded,
    hint recorded, fluent caption, era ignored, and every other artifact still looks perfect.
- **Which caption tier is actually genre-correct (C, 2026-08-18, measured on the v5 goa sidecar):** T1 (effnet `genre400` classifier ON THE AUDIO, not MF-derived) 70.4% goa/psy — the clean one, immune to MF's hint-dependence. T2 (Granite) 48.0% — better than T3 but still inherits ~half its source's error. T3 (raw MF prose) 1.2% when unhinted. If a re-caption isn't affordable, weight T1/T2 over T3, not the reverse.
- **Per-source caption tiers** — `train_lora.py --caption_probs` takes ONE tuple for all sources or **semicolon-separated per-source tuples** in `--encoded_dir` order (`"0,0.9,0.1;0,0.9,0.1;0,0,1"`). Exists because caption quality differs BY CORPUS (see the audit entry above): a corpus whose granite tier failed the audit must ride its MF tier while the good corpora use granite, and one global tuple cannot express that. `_parse_caption_probs` raises on a count mismatch rather than recycling; each source logs its resolved tiers. Also mind that a **missing tier falls back to t1 silently** — and a t1 that is one constant corpus label (Suomisoundi) trains that constant instead of anything per-track.

### B · Model control, guidance & steering (`stable-audio-3/.../inference/`, `control/sa3_control/`)
- **LatCH heads + guidance** — `stable-audio-3/.../inference/latch_guided.py` `sample_flow_euler_multi_latch_guided` (Selective-TFG, **multiple guides**, `rho/mu/gamma/n_iter`, `band_hinge` + chroma/scalar/cosine/bce loss zoo). Load any head with `stable_audio_3.models.latch.load_latch_from_checkpoint(path, device)` (auto-detects arch — don't hardcode); production heads `stable-audio-3/latch_weights_sa3_medium/*_best.pt`. Phase-tolerant chroma losses: `inference/chroma_losses.py` (canonical twin `control/sa3_control/chroma_losses.py` — keep in sync).
- **🚨 LatCH head training has a HELD-OUT VALIDATION path now — use it, and distrust any head that predates it** (C, 2026-08-18). Until then `scripts/latch/train_latch.py` had no val set at all: `_best.pt` was the epoch with the lowest TRAINING loss, i.e. the most-memorised one, so **all 14 production `*_best.pt` heads and the f0 melody pilot are train-selected and have no generalisation evidence whatsoever**. Opt in with **`--val-frac 0.15 --val-group-by source_track`**; the checkpoint then carries `val_loss` / `val_split` / `selected_on` so a consumer can tell a val-selected head from a train-selected one instead of assuming. **The split MUST be by source track, not by crop** — in `latents_sa3` every one of the 2676 tracks contributes ≥2 crops, so a crop-level split leaks a sibling crop of nearly every val track into train, and sibling goa crops share key, lead patch and often literal repeated loop material. `--val-group-by none` gives the crop-level split and is LEAKY by construction; a crop missing the group field is a hard error rather than a silent per-crop fallback. Split helper `train_latch.split_indices` + `LatCHDataset.group_keys` (10 tests, `tests/test_latch_val_split.py`); `--val-frac 0` reproduces every earlier run byte-for-byte. Read the curves with **`latch/summarize_val_arms.py`** (best-val epoch, overfit ratio, train/val gap; flags STILL-IMPROVING vs turned-over vs MEMORISING). Melody-head arms: `latch/run_melody_val_arms.sh`.
- **Weight-space forensics kit for adapter checkpoints (C, 2026-08-18 — Kim's "outliers vs eigendirections" ask).** All CPU, all on the DoRA-EXACT `ΔW_eff = m ⊙ rownorm(W+BA) − W` (or plain B·A), all rank-agnostic. `eval/task_vector_gram.py` — Gram matrix over any set of same-base checkpoints (labels `good:`/`bad:`, `--ladder` expands a run's epochs): pairwise cosines, cos-to-good-consensus, per-site/per-block, ladder step-cosines + path efficiency (validated against `checkpoint_trajectory_stats` to 3 digits); builds a per-model **factor cache** on the NVMe (`SAO/.cache/task_vector_factors/`, reused by the others; the in-RAM version was OOM-killed on the shared box). `eval/task_vector_spike.py` — top singular directions per matrix and whether a family's spikes AGREE across runs / form a global direction / are channel outliers. `eval/spectral_repair_lora.py` — remove / keep-only / shrink the top-k singular components of B·A per matrix, re-factored at the same rank (loads with the standard loader), optional DoRA-magnitude reset — the "mask the outliers out and make a new model" in the right geometry (5 tests). `eval/soup_ladder.py` — temporal soups (`uniform/asc/expasc/bell_late/bell_end`) over ONE run's ladder for any Lightning LoRA/DoRA run; refuses cross-run input (B·A gauge freedom — cross-run soups must average ΔW_eff). **Finding it was built on (2026-08-18 goa):** the AdamW-sweep arms Kim hears as broken share ~nothing with the healthy runs (bad-good cos 0.03–0.12 vs good consensus 0.72), carry 20–30 % of every matrix's delta energy in ONE singular direction (healthy runs: 2 %, flat at every epoch/config), and that direction is the SAME across the four arms (|cos| 0.25, chance 0.026), strongest in `ff_in`/`out`, strongest at the smallest LR. Caveat that reframes it: the healthy twins were **Fusion** (NS5 flattens spectra by construction) and the broken arms AdamW — optimizer and batch are confounded in the archive; the trajectory arms below separate them. Report + probes: `lumi_runs/analysis/task_vector_gram_goa_2026-08-18/` (UUID drive).
- **Longform / loop-attractor toolchain** (`.../inference/`) — `longform.py` (`LongFormRenderer`, `SDEditReanchor`, `DriftMonitor`, `CrossfadeStitcher`, slerp + SaFa `swap_join`) · `fifo_infinite.py` (Rolling-Diffusion/Diffusion-Forcing per-token (B,T) timesteps, guarded monkey-patch) · `recurrence_potential.py` (`RecurrenceHead` anti-loop guide, band_hinge) · `rope_jitter.py` (per-head RoPE base-freq, reversible ctx-mgr) · `incantation_mask.py` (zeros text cross-attn on clamped history). Wrappers in `control/sa3_control/`: `steered_longform.py`, `development_renderer.py` (clamp/sdedit/crossfade selector, never edits longform.py), `density_schedule.py` (`ControlSchedule` + ridge_gain).
- **Guidance / sampling seams** — `.../inference/sampling.py` (`build_schedule` dist-shift-aware + sampler zoo, each exposing a per-step `callback({x,t,sigma,i,denoised})`) · `models/dit.py` native **limited-interval CFG** (`cfg_interval`, ~L479) + per-LoRA `interval`/`layer_filter` sigma-gating — **ships off by default `(0,1)`** · `models/transformer.py` `SA3_SDPA_CAST_BF16` env (fp32→bf16 attention island; the flash-attn path silently casts fp32→fp16, ~L718).
- **Control-adapter kit** (`control/sa3_control/`) — `adapters.py` (`ControlledCrossAttention`, decoupled/IP-Adapter pattern, zero-init no-op) + `inject.py` (`install_adapters`, runtime wrap+freeze) + `conditioner.py`/`es_conditioner.py` (token encoders incl. 384-ch chroma; gradient-free OpenAI-ES refiner) + `cc_probe.py` (frozen differentiable onset-density training-consistency loss) + `chroma_guided_generator.py` (chord→chroma progression driver).
- **Steering / interpretability** — `control/sa3_control/layer_patch_map.py` (**Axis-1 causal localizer** — which block/module carries an attribute; routes rank, doesn't mask) · `checkpoint_trajectory_stats.py` (**run on every finished run** — path/curvature/soup-center) · `landscape_map.py` (trajectory-PCA + planarity null) · `telemetry.py` (training telemetry → wandb) · `mert_selector.py` (best-of-N continuation scorer) · `eval/concept_directions.py` + `eval/steer_concept_direction.py` (diff-in-means SA3 activation steering, CFG-conditional-only injection rule) · **per-block weight-delta profilers** `eval/dora_layer_delta_profile.py` (where a DoRA changes the model — ‖ΔW_eff‖/‖W_base‖ per block) + `eval/pt_layer_shift_profile.py` (which layers ARC post-training rewrote) — the "where does this training actually write" tools (found style-training falls with depth + conditioning-pathway dominance; DoRA-vs-ARC per-block anticorrelation is the base→PT-transplant mechanism).
- **SA3 generative separation / riffer** — `control/scripts/` (`sa3_flowsep`, `sa3_zerosep_rf`, `stem_score`) + trainer `control/sa3_control/`. **Inference recipes** (validated param sets): `control/recipes/inference_recipes.yaml` — check before re-tuning.

### C · Eval & site tooling (`Misc/`, `eval/`)
- **Page engine** — `Misc/eval_grid.py` (rich sortable grid/table/compare renderer; the core any eval table builds on) · `Misc/build_evals.py` (site index + the shared **`WAVEFORM_CSS`/`WAVEFORM_JS`** same-playhead player — import for any player page — + `_resolve_mantu()` drive resolver).
- **Models index/matrix** — `Misc/build_model_index.py` (`collect_models()` = canonical run-label source, imported by the matrix) · `build_model_matrix.py` (manifest-driven self-populating board) · `models_index_overrides.json` (per-label recipe/note override layer — edit to annotate without code) · producer `eval/model_matrix_gen.py` + `eval/interval_schedule_bracket.py` (frac→sigma via the exact `build_schedule`) both append the shared `manifest.jsonl`.
- **🆔 MODEL IDENTITY — `model_index.md` is the thing to CHECK BEFORE working with any model** (Kim direct 2026-08-17: *"everyone should check what's there for a model they're about to work with — only for the synonym issues, if nothing else"*). Regenerate with `Misc/build_model_index_page.py`. **A LABEL IS NOT AN IDENTITY: 75 of 297 labels are synonyms of another model** — 61 `_ptm` (same checkpoint re-rendered on `medium-base`, the deliberate base-mismatch control), 7 `_repr`, 7 `_repr_ptm`, plus **7 run dirs reachable under two names via `sa3_lora_runs` symlinks where nothing in the name says so** (`readlink` is the only tell). So every distinct model now carries a **stable random ID** `M-XXXXXX`, printed in `model_index.md` with an "also known as" line. Registry `Misc/model_ids.json` + assigner `Misc/assign_model_ids.py` (`--report` / `--assign` / `--self-test`). **Assign-once is the contract:** an ID is never changed, reused, or recycled; the assigner only ADDs and aborts on collision. IDs are random ON PURPOSE — name-derived would change on rename (the case we need to survive) and content-derived is unstable across re-saves/prunes. Quote the ID in journals, pull commands and chat when the label could be ambiguous.
- **Report generators (content/build split — edit the `*_data.json`, re-run the builder)** — `Misc/build_kaq.py`, `build_paper_verdicts.py`, `build_stats_page.py` (queries `clip_metrics.db`), per-page drivers `build_{goa_musicology,layer_map,e1_pilot,latch_sa3_matrix,disentangle,mp_crossmodel}_page.py`.
- **Corpus-analysis pipelines** — `eval/musicology/` (C, 2026-07-22) goa transcription musicology study: `phase1_features.py` → `phase2_clustering.py` (substyles) → `phase3_motifs.py` (motif catalog + `hook_melodic_ratio` memorability quantifier). This is CORPUS analysis, not a per-render scorer. `hook_melodic_ratio` (hook-contour repeat-count; ~0 = the measurable signature of the models' missing-melody failure) is *proposed* as a render eval-column — **G/W-owned adoption, not yet a scorer**; if it graduates it gets its own Meters entry. Report + curation subset (259 hooky-leads) + melody-contour LatCH head spec: `eval/musicology/REPORT-2026-07-22.md`.
- **Comment/feedback** — `Misc/comment_notes_block.py` (generator-side widget, clip/ckpt/model scopes) + `inject_comment_widget.py` (idempotent injector for legacy pages) + `comment_targets.json`. **`merge_comments.py` is RETIRED — the comment system is WRITE-ONLY fleet-wide** (public text = injection surface; Kim reads raw + relays).
- **Meters / scorers (`eval/`)** — `width_metric.py` (canonical stereo width; standard column) · `stereo_phase_meter.py` · `reverb_table_measure.py` · `envelope_fidelity.py` (source-vs-output envelope + pad-fill) · `structure_stability.py` (tempo-IQR/key/recurrence) · `latent_dim_feature_xcorr.py`+`latent_noise_fragility.py` (in `Misc/`, not `eval/`; CPU encodability probe — ENCODED/EMERGENT/DEGRADED) · `latent_bend.py` (deterministic latent ops) · `score_loopy_manifest.py`+`corpus_bands.py` (loop-meter validation + quantile bands) · **`control_head_disintegration_eval.py` — MANDATORY gate before any control-head "works/usable-range" claim** (Kim direct 2026-07-20; every steered clip vs its OWN baseline — dead heads pass, buzz heads can score high authority, a usable head clears both; bounds whitening/hf-blowout/noise/beat-loss/CE-drift; reads `clip_metrics.db`, no re-render; supersedes `latch_bracket_quality_gate.py`. Spec: `docs/superpowers/specs/2026-07-20-control-head-disintegration-gate.md` + MASTER control-eval §) · `drift_prediction_analysis.py` · **`clap_score.py`** (W, commit a02c46e — CLAP prompt-ADHERENCE axis, real job = genre-degeneration detector "psytrance must not collapse to drone/noise"; use the ABSOLUTE score and its DROP, NOT fine intra-genre ranking; also a cheap decode-per-iter train-side early-stop/degeneration monitor. Design + prototype numbers: `docs/superpowers/specs/2026-07-22-eval-quality-and-training-signal-design.md`).
  - ⚠ **Axis-blindness of the whole clip_metrics/CLAP/disintegration stack (structural, permanent):** these score genre-adherence + DSP-buzz + Audiobox CE/PQ — NOT fine fidelity, stereo-separation, HF-noise, or punch. Do **not** retire a training arm on a fidelity/separation axis by metric alone (e.g. "fp32≈bf16 by CLAP" does NOT overturn Kim's 07-20 fp32>bf16 *by-ear* verdict — different axes, both true). Ear owns the axes the meters can't see. Fuller treatment: the eval spec's "what these metrics cannot see" caveat.
- **DAWproject ground-truth (`eval/musicology/`, C 2026-08-12)** — `dawp_align.py` (Bitwig `.dawproject` → stem↔track↔clip↔**section** alignment; resolves flat-stem group ambiguity from the track tree; per-section element presence) + `dawp_to_frames.py` (notes → tick-exact **(T,88) key-roll + gate** duty-cycle @10.77 Hz, **loop-expanded**; DAW-truth counterpart to `prep_notegrid88.py`). The reference/gotchas doc is master-level **`DAWPROJECT.md`** — read it before parsing a `.dawproject` (clips LOOP; `playStart≠loopStart` edge case; 88 keys suffice). Feeds the z→88 register ceiling, the repetition-structure label, and `nspace` gate calibration.
- **Render/eval harnesses (`eval/`)** — `rarity_gen.py`+`rarity_lite_score.py` (production-invariant MERT-kNN rarity) · `chroma384_eval.py`+`chroma_steer_targets.py` (shared renderer↔page contract) · `section_boundary_validate.py` · `muscriptor_decode_gate.py` · `decoder_haze_probe.py`+`gate_a_noise_injection.py`.
- **Shared data assets** — `eval/clip_metrics.db` (~43 k clips × 14 metrics — **query it, don't re-score**) · `eval/mp_checkpoint_recipes.json` · `eval/kimlong_pool.json` (detailed-prompt pool).

### D · Inference infra (`onnx/`, `mir/`) — AMD / CPU deployment
- **SA3 → ONNX for AMD (ORT + MIGraphX)** — full text→audio, all in `onnx/`. AE `export_same_onnx.py`+`decode_onnx.py`; DiT `export_dit_onnx.py`+`dit_onnx_infer.py`+`precache_dit_cond.py`+`latent_server_dit_onnx.py`; control-adapter bake `export_dit_control_onnx.py`+`dit_control_onnx_infer.py`. **Verdict: a VRAM/deployment win, NOT speed** (eager torch ~3.3× faster/call; ONNX buys 3.8 GB + zero torch dep). Cos≈1.0 vs torch. Gotchas + writeup: `stable-audio-3/docs/onnx-amd-inference.md`.
- **CPU control-adapter eval path (the default, GPU-freeing)** — `onnx/sa3_control_onnx.py` core + `control_eval_server.py` (resident T5-Gemma + ONNX DiT/decoder, queue `SAO/control_eval_queue`) + `submit_control_job.py`. 8-step grid ≈5.4 min CPU vs ~42 min GPU. See MASTER §5.
- **CPU LatCH-guidance eval path** — `onnx/sa3_latch_onnx.py` + `latch_eval_server.py` (queue `SAO/latch_eval_queue`) + `submit_latch_job.py` + `latch_validate.py`. Autograd through the ~5-7 M head only, DiT stays ORT. **Device gotcha:** `device="cpu"` but keep GPU *visible* (do NOT set `HIP_VISIBLE_DEVICES=""`). See MASTER §5.
- **SA3 latent explorer** — `mir/plots/explorer_sa3/` (Dash viewer) + `mir/scripts/latent_server_sa3.py` (SAME-L decode/mix/steer player, port 7892). mir branch `sa3-latent-explorer`.
- **CK flash-attn (RDNA4/ROCm 7.14, faster than Triton FA2)** — built in `SAO/sa3-rocm7.13-test/`. `FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE` before import; TRAINING needs the 1-line backward grad-count patch. Recipe: `docs/flash-attn-ck-rdna4.md`.

### E · LUMI & training toolchain (`lumi/`, project `465003186`)
- **🚨 `MIOPEN_DISABLE_CACHE=1` + `--bind …,/tmp` is MANDATORY on gfx90a** — the MIOpen kernel-cache SQLite open fails on every LUMI filesystem; without it training dies at the first conv. Also `MIOPEN_FIND_MODE=2`, `PYTORCH_TUNABLEOP_ENABLED=0`.
- **Container/env** — `lumi/sa3-env.yml` (cotainr → `.sif`; match `--index-url` ROCm to the base image; torch pinned 2.4–2.6, NOT the local 2.10/gfx1201 wheels) · `env_lumi.sh` (gfx90a profile) · `make_vendor.sh` (FusionOpt vendor shim for `--optimizer fusion`).
- **The proven deployment skeleton** = the `lumi/sbatch/efp_*` scripts (canonical body: SIF at `/project/…/containers/sa3.sif`, code from source + vendored fusion, stage latents to `/flash` once per node, multi-arm via `SLURM_PROCID` case table). **Start new jobs from `efp_fp32_compare.sbatch`, not the older `latch_*`/`dora_*`/`arc_*` templates** (those reference a never-materialized layout — their *recipes* are reusable, the wrapper isn't; `longctx_*` shows the port).
- **Job templates** — `hello_world` (day-0 gate) · `latch_parity` (campaign gate) · `latch_all_features` (`--array=0-19`) · `dora_run` (bracket = for-loop of sbatch; header has the avp-DoRA lessons) · `arc_rollout`+`arc_train` (**2-step, `--dependency=afterok`**) · `longctx_t1024/t2048` · `efp_fp32_compare`+`efp_bf16_twin` (8-arm precision matrix, fp32-SDPA + batch-size probes) · `efp_fullft_t4096` · `ctrl_matrix_hq` (HyperQueue packs a whole node — use for >20 short single-node tasks, GCD-pin via `ROCR_VISIBLE_DEVICES=$SLURM_PROCID`).
- **🚨 MULTI-GPU DDP: use `srun --ntasks=1` + `torchrun --standalone --nproc-per-node=N`, NOT `--gpus-per-task=1` + Lightning's SLURMEnvironment auto-detect** (2026-08-17). The old pattern SILENTLY fails to form a DDP group — every rank reports `LOCAL_RANK: 0` and you get N uncoordinated single-GPU trainers writing colliding `-vN` checkpoints (job 21161065: genuinely diverged weights, 521/522 tensors differ). Adding `--devices N` does NOT fix it, it crashes (cgroup isolation → each process sees 1 GPU). Reference: CSC's own `~/Projects/llm-fine-tuning-examples`; converted example: `lumi/sbatch/fullft_mixed_avp_goa_t4096.sbatch`; two-groups-per-node example (per-arm rdzv port + explicit `ROCR_VISIBLE_DEVICES`): `lumi/sbatch/dora256_mixed_2x4gpu.sbatch`. Requires `train_lora.py`'s `torch.cuda.set_device(LOCAL_RANK)`. **Verify every multi-GPU run with `grep -h LOCAL_RANK <log> | sort -u` (want 0..N-1, not N zeros)**; unmigrated scripts are unverified. Full detail: `.claude/skills/lumi-ops/SKILL.md` §Multi-GPU DDP.
- **Step-resolution trajectory recorder + reader (C, 2026-08-18, Kim: "save every step ... there's a compressed way to store movement").** `stable-audio-3/scripts/trajectory_sketch.py` (Lightning callback; `train_lora.py --traj-sketch-dir DIR [--traj-ckpt-every 5 --traj-ckpt-dense-until 1000]`): per OPTIMIZER step, a **CountSketch** (4 hashes × 1024 buckets = 4096-d, inner products preserved to ~1.6 %) of the update AND the raw gradient of all trainable params + per-tensor norms + a raw coordinate subsample + trainable-only bf16 ckpts on a grid. Every trajectory statistic is a Gram function, so ~4 KB/step keeps all of them; fixed shared seed ⇒ arms comparable in the sketched space. Reader `eval/trajectory_sketch_analyze.py <traj> [<traj2>..]`: multiscale path efficiency vs the 1/√w random-walk line, update/grad autocorrelation vs Adam's 0.9^τ, gradient window-SNR vs 1/w, update–grad alignment, per-site/block energy, B·A spectra over saved ckpts, cross-run cosines (5 known-answer tests). LUMI job: `lumi/sbatch/traj_sketch_arms.sbatch` (bs1/accum8/bs8 × AdamW + bs1/bs8 × Fusion, sanity16 recipe on goa); local: `lumi/local_traj_sketch{,_fusion}.sh` → `SAO/runs/traj_sketch/`. **First read (local bs1 AdamW, 4482 steps): update autocorrelation = 0.9^τ to 3 digits then exactly 0; gradient window-SNR = 1/w to 3 digits up to w=1024 (repeatable gradient component < 0.1 % of energy); zero drift; loss flat; yet B·A top-1 fraction climbs 0.33→0.56.**
- **Pre-encoding a raw-audio corpus** — `stable-audio-3/scripts/pre_encode_dataset.py` (`--shard I/N` for parallel GCD-pinned shards with collision-free ids; **`--no_caption_check` when the corpus has no per-file `.txt`** — without it every file is `__reject__`ed after ~100 wasted full-track decodes each, which reads as a memory leak). Fine-grained + process-restart driver: `lumi/sbatch/preencode_bigset_finegrained.sbatch`. **The latent ids are synthetic** (`{shard}{batch}{i}`), so a relpath-keyed caption sidecar will NOT resolve — re-key it with **`lumi/build_bigset_caption_sidecar.py`** (`--report-only` measures coverage first; counts exact-vs-fallback matches separately).
- **Data/ckpt utils** — `lumi/pack_data.sh` (tar-over-ssh staging + **doubles as latents cold backup**; target is **LUMI-O** `lumi-465003186-private`, NOT Allas) · `lumi/prune_optimizer_states.py` (fat `.ckpt` → slim `.weights.ckpt`, **keeps both for the final epoch — dedup when counting**, no optimizer state in the slim) · `lumi/ckpt_dup_delta.py` (diffs `-vN` duplicate checkpoints via `torch.load(mmap=True)` so 36 GB fats don't load fully; `--only-key` scopes to one group).
- **Bounded-norm full-FT arms (the runaway-fix comparison)** — `lumi/sbatch/fullft_3src_t512_fp32_bounded.sbatch`: 3 sources (avp aug×8 + suomisoundi + goa) at T512/fp32/EMA, `MODE={hyperball,edm2,both}` × `LR={3e-5,1e-4}`, 8 GPUs via torchrun, per-source caption tiers. **`--hyperball` exists and is tested; EDM2 forced-weight-norm does NOT** — the preflight refuses `MODE=edm2/both` with an explicit message rather than misconfiguring. Context that keeps this in proportion: the latent-scale runaway is **already bounded by `--weight_decay`** (wd-fixed full-FT measures ep7 z0 std **1.134**, 0/256 channels >2.0, vs the runaway's 5.6 and 166/256), so these arms test the *finer* question of whether a slower LR finds different minima at a bounded norm. **Warmup/EMA/AdaGC cannot substitute** — all three shape the path, none bounds ‖W‖ (AdaGC clips against recent-history EMA, so it catches spikes and misses sustained drift). Paper grounding: `papers/CONTINUITY-drone-optimizer-synthesis-2026-08-11.md`.
- **DRIVE LAYOUT / consolidation** — `Misc/drive_rebalance_20260817.sh` (copy → verify → separate explicit delete; `scan` phase finds corrupt checkpoints by zero-byte / 1970-mtime / **runt-vs-siblings** — the size test MUST be sibling-relative, an absolute "<100 MB is truncated" rule flagged 83 false positives because `dora16` adapters are legitimately ~86 MB where a rank-128 is ~666 MB). Intended roles (Kim 2026-08-17): **UUID drive `9a410a1d-…` = ALL LUMI content** (`lumi_runs/`), **Mantu = non-LUMI bulk + the `model_matrix` cell archive + `sa3_lora_runs`**, **Lehto = captions/latents/timeseries (many small files, what local training random-reads)**. ⚠️ **Never merge trees with a bare `rsync -a`** — its size+mtime check overwrote a good 666 MB checkpoint with a truncated 25.6 MB fragment (mtime 1970, unloadable) because a filename match was mistaken for a content match; use `--checksum --backup-dir`. ⚠️ **144 files hardcode `/run/media/kim/...` paths and 9 point at the nonexistent `Mantu1`** — retire these into config as you touch them (Kim standing directive).
- **Conventions** — crops in **FRAMES = multiples of 256** (`--frames`; T512/1024/2048/4096, verify exact T) · compare ckpts **across the whole run** (stability window; prefer r128/r256 @ lr~1e-4) · 1 GCD/run, the win is parallelism (`standard-g` bills whole nodes) · **ACCESS MODEL: direct `sbatch` works now** (since 07-15; the EFP-WebUI-only banner in `lumi/README.md` is superseded — see `docs/lumi-throughput-workflow-guide.md`).

### F · Fleet comms & patrol infra (`Misc/`, `docs/`, `papers/`, `profiles/`)
- **Comms** — `Misc/agent_dialogue.py` (instance-to-instance chat/DM protocol over `osc_worklog.py` multicast; `say`/`dm-say`/`wait`/`listen`) — **protocol SPEC: `docs/superpowers/specs/2026-07-02-agent-dialogue-osc-protocol.md`** (two-layer listener/wake design, wake-arming via harness-tracked bg task, the presence/deaf gap, heartbeat upkeep) · `Misc/filelock.py` (advisory locks for shared files — **use before editing MASTER.md/specs**; **`--pid-aware` = a long-held-resource mutex** that breaks a foreign lock only when its PID is dead, not on the 15-min mtime timer — the **GPU mutex** — **canonical path `SAO/.gpu.lock` (repo root), the SAME for all instances** — so a live multi-hour job is never stolen but a crashed/rebooted one reclaims instantly. `acquire SAO/.gpu.lock --handle H --pid-aware --pid $$` (the `$$` records the wrapping shell as the persistent holder — NOT the transient CLI) before any render/train/eval, `release` after; prevents the concurrent-GPU overlap that hard-crashed the box twice 2026-07-21. **⚠️ A NON-TEAM instance shares this box and is SUPPOSED to honor `/tmp/gpu.lock`, NOT our `SAO/.gpu.lock` (Kim 2026-08-07) — but it demonstrably runs the GPU WITHOUT writing that lock (verified live 2026-08-07: foreign `grain_sim.py` held 9.7 GB with `/tmp/gpu.lock` ABSENT). A lockfile is a CLAIM; occupied VRAM is a FACT. ORDER MATTERS: (1) `rocm-smi --showpids` is GROUND TRUTH, checked FIRST — foreign VRAM present = do not start, no matter what the lockfiles say (skip our own pid + sub-512 MB idle contexts); (2) `/tmp/gpu.lock` is the FOREIGN channel — honor it (present w/ live pid = taken; reclaim only if its pid is DEAD) and MIRROR our pid into it on acquire / remove on release (only if it's ours — never delete a foreign lock) so the foreign instance sees us; (3) `SAO/.gpu.lock` (`--pid-aware`) is OURS. Don't hand-roll the order — use `Misc/gpu_guard.sh` (W, commit 2284917): `gpu_guard.sh acquire HANDLE PID` returns 0 to proceed / 1 to stand down, `release HANDLE PID` when done; it does the whole dance in the right order.** C stomped the GPU 2026-08-07 trusting only `SAO/.gpu.lock` + a sloppy rocm-smi; a lucky foreign pause saved it — a lockfile-first check would have stomped the still-running foreign job. **Second near-miss, same principle, 2026-08-19:** a per-clip render loop (G's soup-scoring pass) spawns a fresh subprocess per clip, so the GPU looks briefly idle and the DRIVER pid can look dead BETWEEN clips even though the loop is still running — C reclaimed it once by mistake. Confirms the existing rule rather than adding a new one: hold the lock with the wrapping loop/shell's pid, never a per-clip transient's.) · `worklog_note.sh` (log+notify).
- **Site** — `Misc/build_site.py` (profiles/journals → public site) · `Misc/build_dms.py` + `mirror_dialogue.py` (DM/dialogue → redacted HTML; DMs are public-mirrored — the no-secrets rule applies).
- **Patrol ledgers (the anti-repeat-work backbone)** — `papers/knowledge.md` (external prior-art index) · this `ARCHITECTURE.md` (internal reuse index) · **`docs/open-threads.md`** (standing open/dropped-thread ledger — check before flagging, strike when fixed) · `profiles/daily/` (daily digests) · `paper_verdicts.html`/`Misc/paper_verdicts_data.json` (which papers were tested) + `docs/paper-gap-audit-2026-07-18.md` (what we under-applied).

## Doc map

| File | Purpose |
|---|---|
| `ARCHITECTURE.md` (this) | 1-page what's-where |
| `MASTER.md` | cross-cutting facts always loaded into every session |
| `WORKLOG.md` | append-only session log |
| `EXPERIMENTS.md` | **planned / running / potential experiments registry with the findings behind each** — the forward-looking twin of `DISCOVERIES.md` (Kim 2026-08-19); check before proposing, add when planning, move to Done when landed |
| **`DAWPROJECT.md`** | parsing Bitwig `.dawproject` exports → **tick-exact ground truth** (note-grids/gate/sections); the **loop-expansion gotcha** (clips loop a short pattern → naive parse undercounts ~2.6×); stem/group naming; tools `eval/musicology/dawp_align.py` + `dawp_to_frames.py` |
| **`docs/superpowers/specs/`** | **design specs — the running source-of-truth per subsystem** (eval-tables human-first, agent-dialogue **comms protocol**, control-head disintegration gate, eval-quality/training-signal, metrical-tree PE, reality-structured experiments, **full-FT regularization A/B — AGC + output-std penalty vs weight-decay, `2026-08-10-fullft-regularization-ab.md`** (the follow-up to the full-FT latent-scale-runaway/drone fix; targeted regularizers that bound the runaway without dulling detail), …). No per-spec index yet → a NEW spec MUST get a one-line pointer here or in the relevant §A–F entry (discoverability rule, CLAUDE.md §5). |
| `docs/venvs.md` | the venvs + the CK-flash-attn build |
| `docs/commands.md` | the commands that actually get run |
| `docs/latch.md` | what LatCH is + how heads are trained |
| `docs/training-findings.md` | recipes, params, **why latents are T=4096** |
| `docs/lessons-learned.md` | mistakes to not repeat |
| `docs/todos.md` | open work (+ IDEAS-POOL) |
| **`docs/open-threads.md`** | standing open/dropped-thread ledger + standing gotchas |
| `docs/onset-density-control-narrative.md` | the onset-density control story (§3 verdict) |
| `docs/research-synopsis-longform-continuation.md` + `docs/paper-gap-audit-2026-07-18.md` | longform loop-attractor theory + what we've under-applied from the papers |
| `docs/lumi-transition-plan.md` · `docs/lumi-throughput-workflow-guide.md` · `docs/csc-data-guidelines-guide.md` · `lumi/README.md` | LUMI: bring-up, throughput/HyperQueue, data-movement/LUMI-O backup, the bundle |
| `docs/fleet-audit-2026-07-19.md` | last dropped-thread audit (folded into open-threads) |
| **`docs/goa-captioning-status-2026-08-18.md`** | **consolidated status of the goa big-set captioning saga** (root causes, timeline, who-did-what, what's open) — Kim's ask 2026-08-18 after it got sprawling across chat; the input doc for W's forthcoming canonical metadata-creation spec |
| **`docs/cost-log.md`** | **standing GPU-hours / encode-price / VRAM / bungee-augmentation cost log** — real measured numbers, one entry per pass, template included (Kim's ask, 2026-08-10) |
| `profiles/daily/` | daily digests (one page/day, Kim's catch-up) |
| `papers/knowledge.md` | the *external* prior-art reuse index (companion to this) |

- **Music captioning (Music Flamingo + Granite) — lives in mir, ALREADY BUILT.**
  `mir/MUSIC_FLAMINGO.md` + `mir/src/classification/music_flamingo.py` (GGUF Q6_K via
  llama-mtmd-cli, ~4 s/track, 5–9 GB VRAM, models in `mir/models/music_flamingo/`) +
  `granite_revision.py` (GraniteReviser, granite-4.0-h-tiny GGUF, condenses to short
  tags). Feeds `stable-audio-3/scripts/caption_tools.py` tiers (T2=Granite-compressed,
  T3=raw Flamingo). Re-discovered the hard way 2026-07-08 (scouted HF before checking
  mir) — check mir FIRST for any audio-understanding capability. (CONTINUITY)
