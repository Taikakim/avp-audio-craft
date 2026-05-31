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

## 2026-05-31 — Kim + Opus 4.8 — Attention backend benchmark: CK vs Triton vs SDPA vs math

Head-to-head: one 50-step LatCH-guided SA3 generation (small-music-base, the only trained
SA3 head = rms_energy_bass ep10), T=1292 (120 s), fp32, rho=mu=8, n_iter=6. TunableOp OFF,
warmup discarded, median of 2 timed. Harness `/tmp/bench_latch_attn.py`, runner
`/tmp/run_bench_matrix.sh`, raw `/tmp/bench_results.txt`. All 6 outputs match (out_mean
−0.0152) → every backend numerically correct.

| backend | venv/torch | 50-step wall | steps/s | vs same-venv SDPA |
|---|---|---|---|---|
| CK flash    | test / 2.12+rocm7.14 | 14.48 s | 3.45 | **1.39×** |
| SDPA        | test / 2.12 | 20.07 s | 2.49 | 1.00 (anchor) |
| math (none) | test / 2.12 | 19.00 s | 2.63 | 1.06× |
| Triton flash| prod / 2.10+rocm7.2.3 | 51.72 s | 0.97 | **1.10×** |
| SDPA        | prod / 2.10 | 56.80 s | 0.88 | 1.00 (anchor) |
| math (none) | prod / 2.10 | 63.66 s | 0.79 | 0.89× |

- **CK vs Triton end-to-end = 3.57×.** Decomposed via the SDPA anchors: **stack
  (2.12/7.14 vs 2.10/7.2.3) = 2.83×** (dominant); **flash kernel (CK uplift 1.39 vs
  Triton 1.10) = 1.26×**. CK is the more effective flash backend AND it's on the faster stack.
- **CAVEAT — TunableOp OFF inflates the cross-stack gap.** The within-venv flash ratios
  (1.39×, 1.10×) are clean; the 2.83× stack gap is partly artifact (prod 2.10 normally uses
  its tuned GEMM cache). A TunableOp-on rerun is needed for realistic cross-stack absolutes.
- **Lower bound:** small-music-base, not medium. CK's uplift should be larger on the medium
  DiT at T=4096. VRAM: flash/SDPA 3.31 GB, math +0.4 GB (O(T²) attention matrix).
- **Takeaways:** (1) CK flash is a real ~1.4× over SDPA on its native stack — worth adopting.
  (2) The bigger prize is the 7.14 stack itself (~2.8×) — prioritise migrating prod SA3
  (.venv, torch 2.10) to the 7.14/official-CK path once CK is fully trusted.

## 2026-05-31 — Kim + Opus 4.7 — TheRock 7.14 + CK flash-attn for RDNA4: VALIDATED

Follow-up to the 4.8 entry below ("CK-FA build status: BUILT, NOT YET VALIDATED"). Validation
done; recipe + numbers below. Full recipe in SA3 auto-memory `rocm-flash-attn-env.md`.

- **flash-attn 2.8.4 CK build** for gfx1201/WMMA SUCCEEDED after two surgical patches on
  `ROCm/flash-attention` branch `rdna_fmha_gfx1100_gfx1201` (its `csrc/flash_attn_ck/` glue is
  older than its CK pin `08792e0`). Pulled `mha_bwd.cpp` + `mha_varlen_bwd.cpp` + `flash_common.hpp`
  from sibling branch `rocking/update_ck` (commit `d81a98630` "Add sink_ptr/d_sink_ptr to
  fmha_bwd_args"). Originals saved as `*.orig` in the checkout.
- **Verified end-to-end on `~/Projects/SAO/sa3-rocm7.13-test/.venv`** (torch 2.12.0+rocm7.14.0a,
  triton 3.7.0+rocm, gfx1201/RX 9070 XT 16 GB):
  - **varlen smoke** — `flash_attn_varlen_func` finite, max abs diff vs SDPA = **2.89e-04**
  - **SA3 small-music-base generation** — warmup **88 s** (TunableOp+MIOpen tune from scratch),
    cached **0.23 s** (~380× speedup); output fp16 finite, shape (1,2,264600)
  - **LatCH 1-step train with `FusionOpt(normuon, sf)`** — warmup 4.4 s, cached **21 ms**
  - **torch.compile + inductor on LatCH head** — eager 3.18 ms → compiled **2.04 ms** (1.56×),
    max abs diff = 2.4e-07
- **Critical runtime knob**: set `FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE` BEFORE `import flash_attn`
  — the Python wrapper auto-routes to aiter on HIP and aiter isn't installed in this test venv.
- **Tunings**: isolated to `~/Projects/SAO/sa3-rocm7.13-test/tunings/` so the 2.10/7.2.3 cache at
  `~/pytorch-tunings-7.2.3` is untouched (2.12 validator rejects 2.10 entries and TUNING=1 would
  otherwise overwrite). After warmup, TunableOp validator passes cleanly on the isolated cache
  (PT_VERSION=2.12.0, gfx1201, ROCBLAS_VERSION=5.5.0.62d3a262 all match).
- **Implication for the prod SA3 venv**: when ready to migrate the main `.venv` (torch 2.10/ROCm
  7.2.3) to the ROCm 7.14 / official-CK path for RDNA4, this is the known-working recipe.

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
