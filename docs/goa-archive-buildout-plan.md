# Goa archive build-out — 4-day unattended run (CONTINUITY, started 2026-07-29)

Kim away 2026-07-29 → ~08-02. Turn the uncurated **`/run/media/kim/Mantu/goa_archive_extracted`**
(297 GB, **23,232** full-mix tracks — mostly MP3, 54 FLAC; by-year `Goa.PsyTrance.Collection.*`)
into a curated, feature-rich, stem-separated, captioned corpus. Any CONTINUITY session (post-
compaction or on Kim's return) picks up HERE.

## Kim's directives (verbatim intent)
- **Similarity clustering, NOT bit-dedup.** Same track across compilations = different mastering =
  *real* augmentation to KEEP. Cluster by embedding cosine (MERT/MAEST), keep distinct masters,
  drop only true near-identical. Also flag overlap with the existing `Goa_Separated` corpus.
- **Prefer FLAC for the ENCODE stage** (lossy→latent is quality-poor). MP3 fine for features/captions.
- **Music Flamingo is slow** → do the full MIR run FIRST, then BENCHMARK MF **+ Granite** for real
  rates, caption as much as leftover GPU allows.
- **BS-RoFormer stem separation is slow** (~30-60 s/track → 23k ≈ 200+ h) → SUBSET only. Save stems
  as **192 kbps mp3/m4a** (compressed).
- Output drive = **UUID `/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/`** (1.5 T free).

## Pipeline + STATE
Data root: `/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/goa_archive_features/`

- [x] **Stage 0 — MIR features (CPU, backbone). LAUNCHED 2026-07-29 20:35, detached.**
  `mir/src/tools/goa_archive_mir.py` (mir venv), 3 workers, ~9 h, resumable/fail-soft.
  → `npz/<sha1>.npz` (24 expanded fields) + `index.jsonl` (path, dur, loudness, **maest_vec 768-d**).
  Progress: `grep '/s  eta' <data>/mir.log | tail`. Resume (idempotent): re-run the same command.
  Launch cmd: `cd mir && setsid nohup mir/bin/python src/tools/goa_archive_mir.py --archive
  /run/media/kim/Mantu/goa_archive_extracted --out <data> --workers 3 > <data>/mir_stdout.log 2>&1 &`
- [x] **Stage 1 — similarity clustering + curation: BUILT + VALIDATED on the partial index
      (2026-07-30).** `mir/src/tools/goa_archive_curate.py` (mir venv, CPU, idempotent over the
      growing index): MAEST-cosine components at 0.97 = same-work clusters; tighter 0.995
      union-find inside = true near-identicals (best copy kept: FLAC > tier > bitrate; rest
      dropped); everything else in a cluster = master_variant KEPT (Kim's deluxe-augmentation
      class). Goa_Separated overlap via pooled `maest_embed_ts` (cached:
      `goa_sep_maest_pooled.npz`, 5031×768). Partial-index run (5,885): 2,999 unique / 905
      dup-best / 1,454 dup-dropped (~25% — year-collections re-release heavily) / 527 master
      variants / 1,641 Goa_Separated overlaps (28%); encode gate 3,684 (62.6%). SPOT-CHECKED
      CLEAN: Hallucinogen-LSD 13-member cluster splits edits/vinyl (kept) from redundant rips
      (dropped); tier-C rip dropped for tier-A Best-Of; overlaps match by name. → `curated.jsonl`
      + `clusters_summary.json`. **FINAL RUN = one re-invocation after the MIR pass completes.**
- [x] **Stage 0b — quality audit COMPLETE (2026-07-30, full 23,232).** Final tiers:
      **A near-lossless 4,804 (20.7%) · B 256-320k 15,030 (64.7%) · C ~192k 2,138 (9.2%) ·
      D ≤128k/transcode 1,259 (5.4%)** (400-sample estimate held). Formats: 23,178 mp3 + 54 flac.
      **Encode gate (tier ≥ B): 19,834 tracks (85.4%).** → `quality/quality.jsonl`. Curation
      gates the ENCODE stage on tier ≥ B + FLAC-preferred.
- [ ] **Stages 2-4 — PIVOTED TO LUMI, FULL ARCHIVE (Kim 2026-07-29):** 8 GCDs chew all 23k instead
      of a local curated subset. Built + syntax-clean, awaiting staging (see FIRE ORDER below):
      * `lumi/build_offload_venv.sh` (uan18, one-time): scratch venv w/ SIF torch — `audio-separator
        --no-deps` (mir's separator imports the model class from audio_separator.uvr_lib_v5, NOT
        lucidrains' pkg) + lashahub transformers fork (MusicFlamingoForConditionalGeneration) +
        static ffmpeg if SIF lacks it + MF weights download + fail-loud import verification.
      * `lumi/goa_sep_task.py` + `lumi/sbatch/goa_sep.sbatch` — BS-RoFormer
        **jarredou-BS-ROFO-SW-Fixed-drums** (master_pipeline.yaml operative model = what made
        Goa_Separated; 6-stem, guitar+piano downmixed→other = 4-stem corpus convention), stems as
        ~source-bitrate m4a → `$SCRATCH/goa_archive_stems/`, `.sep_done` markers, resumable.
      * `lumi/goa_caption_task.py` + `lumi/sbatch/goa_caption.sbatch` — MF **transformers bf16**
        (GGUF dropped per Kim: VRAM allows, quality better), default prompt `full` (~24h/8GCD),
        `PROMPT_TYPES=full,genre_mood` env to extend → `$SCRATCH/goa_archive_captions/json/<sha1(rel)>.json`
        — **sha1(rel) keys match the local goa_archive_features index** (captions join features by key).
      * BOTH sbatches have `--export=ALL,PROBE=1` probe mode (2 tracks/rank) — RUN PROBES FIRST.
      * FIRE ORDER: (1) Kim's 4 rsyncs [archive → scratch; mir/src → code/mir-src; jarredou model →
        models/bs-roformer; SAO lumi/ files → code], (2) `bash code/lumi/build_offload_venv.sh` on
        uan18, (3) probe sbatches, (4) full sbatches. Sep may need 1-2 resubmits past 47h; resumable.
      * STATE 2026-07-30 (evening): **ARCHIVE RSYNC COMPLETE. FULL CAPTION RUN SUBMITTED** —
        23k tracks, 8 GCDs, MF bf16 + **FLASH-ATTENTION 2** on the official lumi-multitorch-full
        image (Kim's call; FA2 = the officially-documented MF path, killed the long-track OOMs
        that eager/sdpa-math hit at 600s). Uses MAINLINE transformers
        (AudioFlamingo3ForConditionalGeneration) + goa_offload_venv_mt (build_offload_venv_mt.sh,
        ALL GREEN). CAPTION_MAX_SEC=600 = the model's own design cap. Sep validated (~30s/track,
        all 8 ranks, m4a, 0 flac) — full sep run submit pending/confirm. Remaining pulls: adamw
        board cells + fp32cmp ep14 terminals (5/8 arms; goa_t4096 stragglers at ep9-11, optional
        finisher resubmit). All setup gotchas → lumi-ops skill.
- [ ] **Stage 5 — pre-encode curated subset to SAME latents (GPU), FLAC-preferred sources.**
      Only if GPU time remains; needs beat-grid→T4096 crop pipeline (`pre_encode_dataset.py`).

## Coordination
- Stage 0/1 are CPU (won't block the fleet GPU). Stages 2-5 need `SAO/.gpu.lock` — G-first, pid-aware.
- Fleet heads-up posted; the aug8/aug3 thread (W) and headb confusion re-run are separate open items.
