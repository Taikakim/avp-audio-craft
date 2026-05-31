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

- **SA3 training dataset COMPLETE + ready.** `/run/media/kim/Lehto/latents_sa3/`:
  **5400 beat-aligned crops, T=4096, 0 failures**, 13 GB. Each crop = `.npy`
  (256×4096 fp16) + `.json` (full source `.INFO` + §3.5 prompt + crop offsets +
  rel_pos) + `.TIMESERIES.npz` (21 fields: 20 MIR @ resampled-to-4096 + the new
  `relative_position_ts` ramp). Next: SA3 LoRA retrain against this (rank 16
  dora-rows bf16 `--compile`, `MIOPEN_FIND_MODE=2`).
- **GPU coordination note:** the encode held ~14 GB VRAM (SAME-L + 380 s fp16
  activations) → hard-blocked the parallel **CK-FA validation** instance (needs
  VRAM for SA3 medium + FA). Encode finished ~`<time>`; VRAM released to 1.5 GB.
  **CK-FA build status: BUILT, NOT YET VALIDATED** — `flash_attn-2.8.4-cp313`
  compiled from source in `SAO/sa3-rocm7.13-test/` on a SEPARATE experimental
  stack (`amd-torch 2.12.0+rocm7.14.0a`, gfx1201 device wheels), NOT the prod
  7.2.3 stack. Numerical validation (scripts 02–05) pending on the other instance.
- **Created the docs layer:** `MASTER.md`, this `WORKLOG.md`, `ARCHITECTURE.md`,
  and `docs/{venvs,commands,latch,training-findings,lessons-learned,todos}.md`.
  Wired `@import MASTER.md` into the 3 project CLAUDE.mds (created one for
  stable-audio-tools, which had none). `git init`'d `SAO/` to version just these
  coordination docs (`.gitignore` ignores all nested repos/artifacts).
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
