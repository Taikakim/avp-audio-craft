# WORKLOG — cross-project audio pipeline

Reverse-chronological. Append an entry (newest at top) when you finish or learn
something an agent in another repo would want to know. Keep entries short; move
durable facts into `MASTER.md`. Conventions:

```
## YYYY-MM-DD — <who/model> — <one-line title>
- bullet of what ran / landed / broke
- paths, commands, results worth reusing
```

---

## 2026-05-31 — Kim + Opus 4.8 — SA3 LoRA data pipeline + master docs

- **Created `MASTER.md` + this `WORKLOG.md`.** Wired `@import` into the 3 project
  CLAUDE.mds (created one for stable-audio-tools, which had none).
- **SA3 pre-encode, take 2 (beat-aligned, fixed T=4096).** First take used
  `pre_encode_dataset.py` default `--sample_size` (285 s, single random window/track)
  → cache thrash + lost ~38 % of each track. Pivoted to beat-aligned chunking:
  - `/tmp/sa3_beat_manifest.py` → `/tmp/sa3_crop_manifest.csv` (5400 crops / 2676
    tracks; dropped 471 sources < 380 s). Crop spec: first crop from song start, each
    next snaps back to downbeat-before-prev-end (overlap), final crop end-anchored.
  - `/tmp/sa3_encode_from_manifest.py` → `/run/media/kim/Lehto/latents_sa3/`. Per crop:
    `.npy` (256×4096 fp16, SAME-L) + `.json` (full source `.INFO` merged + §3.5 prompt +
    crop offsets) + `.TIMESERIES.npz` (whole-track sliced→4096 + `relative_position_ts`).
  - Encode running at finish of this session (~5400 crops, ~3.6 h). Post-pass
    `/tmp/sa3_add_relpos.py` ready (the in-flight run predates the rel_pos patch).
- **GOTCHA found: `MIOPEN_FIND_MODE=6` crashes SA3 medium DiT** → MASTER.md §5. Use mode 2.
- **GOTCHA found: batch=1 variable-length → kernel-cache thrash** → MASTER.md §5.
- **SA3 LoRA tuning runs** (10 steps each, warming caches): MIOpen(2) → +TunableOp →
  +torch.compile all OK. Added `--compile` and `--no_demos` flags to
  `stable-audio-3/scripts/train_lora.py`. First full run (rank 16 dora-rows bf16,
  5000 steps) killed at ~700 steps once the cache-thrash root cause was understood;
  re-launch pending against the new beat-aligned `latents_sa3`.
- **Whole-track timeseries** (21 G, 4461 npz @ 100 Hz) documented in `mir/CLAUDE.md`
  (new section) + MASTER.md §4. Producer `mir/src/spectral/whole_track_timeseries.py`,
  consumer `stable-audio-tools/scripts/whole_track_target_source.py`.

## (earlier — see per-repo memory + LATCH_RESULTS.txt)

- LatCH sweep / Fusion bake-off history: `stable-audio-tools/LATCH_RESULTS.txt` (§1–23).
- SA3 LatCH Phase-1 verification (bass RMS, corr 0.965): SA3 memory `latch-sa3-phase1.md`.
- SAO-Small finetune dev guidance (LR/batch/NaN): SAT memory `sao-finetune-dev-guidance.md`.
