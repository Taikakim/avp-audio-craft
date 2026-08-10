# Cost log — GPU-hours, encode price, VRAM, augmentation cost

Standing log of measured compute costs (Kim's ask, 2026-08-10 delegation via CONTINUITY —
"quantify + document augmentation/encode cost"). Real, directly-measured numbers only; every
entry states its hardware/venv so numbers aren't silently compared across incompatible setups.
Append a new entry per measurement pass rather than editing old ones — this is a log, not a
living summary (a summary can live in the entry that supersedes an old number, but don't erase
the record). Indexed in `ARCHITECTURE.md`'s Doc map.

---

## Entry template

```
## YYYY-MM-DD — <what was measured>
**Hardware/venv:** <e.g. local desktop RX 9070 XT 16GB, SAO/.venv ROCm 7.14 | LUMI MI250X GCD, sa3.sif>
**Method:** <script/command, sample size>
<numbers, as a table where possible>
**Caveat:** <anything that limits how far this generalizes>
```

---

## 2026-08-10 — Bungee augmentation timing (GHOST-NOTE)

**Hardware/venv:** local desktop (Ryzen 9 9900X, 24 threads), `mir/pitch_venv`,
`lumi/augment_goa_bungee.py` (8-variant pitch/tempo set), 10 real goa_archive crops from
`/home/kim/Projects/latents_sa3` (source audio off Mantu).

**Method:** timed wall-clock via file mtime span (first written → last written), two runs:
serial (`--jobs 1`) and parallel (`--jobs 8`), different 10-crop samples to avoid OS page-cache
skew between runs.

| mode | crops | variants rendered | wall time | s/variant |
|---|---|---|---|---|
| serial (`--jobs 1`) | 10 | 80 | 307.0s | 3.84 |
| parallel (`--jobs 8`) | 10 | 79* | 59.3s | 0.751 |

\* one variant deduplicated (capped-BPM tempo target collided with another variant — expected,
not an error, per the script's own dedup logic).

**Speedup at 8 workers: ~5.1×** (sub-linear — I/O contention reading source audio off Mantu, a
removable spinning drive, plus ProcessPoolExecutor overhead; not compute-bound scaling).

**Extrapolation to the full corpus** (23k tracks × 8 variants, using the parallel/production-
realistic rate): 184,000 variants × 0.751s = **~38.4 hours wall-clock** for a full one-time
augmentation pass at 8 parallel workers on this CPU. More workers (LUMI nodes have more cores;
HyperQueue can shard further) would cut this further — not measured, this is the 8-worker
number only.

**Caveat:** measured on the local desktop CPU, not LUMI. Bungee itself is CPU-only (no GPU
dependency), so the *relative* shape (near-linear-with-workers, I/O-contended against a slow
source drive) should transfer, but the absolute hours won't — LUMI's CPU count/generation and
source-audio staging path differ. Re-measure on LUMI directly before committing to a walltime
budget for the real 23k×8 job.

---

## 2026-08-10 — SAME encode price: T512 vs T4096, single vs batched (GHOST-NOTE)

**Hardware/venv:** local desktop, AMD RX 9070 XT (16 GB, RDNA4/gfx1201), `SAO/.venv`
(ROCm 7.14, native-CK flash-attn). SAME-L autoencoder, `stable_audio_3.AutoencoderModel`.

**Method:** `same_encode_cost_bench.py` (one-off, pattern adapted from `lumi/profile_encode.py`'s
proven MIOpen/TunableOp env setup). Loads SAME-L once, encodes real audio slices at the two
target durations, single-crop (×4, first = cold/compile, rest = warmed) then batched (bs=4,
matching the reg A/B's `--batch_size 4`). `torch.cuda.reset_peak_memory_stats()` before each
call isolates that call's incremental VRAM, not cumulative.

| | T512 (47.55s) | T4096 (380.44s) |
|---|---|---|
| single, first (cold) | 2.630s | 20.856s |
| single, warmed mean | **0.577s/crop** | **25.011s/crop** |
| batch×4 | 2.333s total = **0.583s/crop** | **OOM** (16GB card) |
| peak VRAM, single call | 4619 MB | 12248 MB |
| peak VRAM, batch×4 call | 7909 MB | — (OOM) |
| total resident (model 3461MB + peak) | ~11.4 GB | ~15.7 GB (single) / OOM (batch) |

**Batching gives ~0% speedup at T512** (0.577s vs 0.583s/crop) — the encode call is not
compute-bound enough at this length for batching to pay off on this card; it does buy VRAM
predictability, not speed.

**T4096 costs ~43× more wall-time per crop than T512** for 8× more audio (25.0s vs 0.577s) —
clearly super-linear, consistent with the encoder's self-attention scaling roughly with T².
**T4096 batched (bs=4) does not fit in 16 GB at all** — real OOM, not a slowdown. This
constrains any future *local* live-encode-at-T4096 experiment: bs=1 or nothing on this card.
LUMI's per-GCD VRAM (MI250X, ~64 GB) has much more headroom — not measured here, flagging as
the thing to verify before assuming T4096 live-encode "just works" on LUMI too.

**Caveat:** local RDNA4 desktop card, not LUMI's MI250X — different architecture, different
achievable throughput. Numbers here are a real reference point and the *ratios* (T4096 batch
OOMs before T512 does; encode dominates over I/O — see below) should hold directionally on
LUMI, but don't copy the absolute seconds/VRAM numbers onto a LUMI capacity-planning doc without
re-measuring there.

---

## 2026-08-10 — Live-encode vs pre-encoded: per-step cost + VRAM delta (GHOST-NOTE)

**Hardware/venv:** same run as the SAME-encode entry above (one combined benchmark).

**The actual question** (reg A/B context: T512, bs4, FusionOpt, `--augment` live-encode over
the goa_archive keep-set vs a hypothetical pre-encoded `--encoded_dir` run):

| step cost component (T512, per crop) | live-encode (`--data_dir --augment`) | pre-encoded (`--encoded_dir`) |
|---|---|---|
| disk read | ~27ms (raw FLAC decode) | ~0.1–0.5ms (`.npy` read, measured at T4096; T512 would be smaller still) |
| SAME encode | 577ms (warmed) | 0 (never runs — SAME isn't even loaded) |
| **total added cost / crop** | **~604ms** | **~0.1–0.5ms** |

**At batch_size=4 (the reg A/B's actual config): live-encode adds ~2.33s/step over what a
pre-encoded run would pay** (matches the directly-measured T512 batch×4 = 2.333s total encode
time — the disk-read component is comparatively negligible, ~46ms/step of that 2.33s, i.e.
**>98% of live-encode's per-step overhead is the SAME encode call itself, not the audio I/O.**)

**VRAM delta directly attributable to live-encode** (on top of whatever the DiT+optimizer
already needs, which is identical in both modes): SAME-L resident weights (3.46 GB) **+**
transient per-batch encode activation peak (7.9 GB at bs4/T512) = **~11.4 GB extra**, vs. **0**
for pre-encoded (SAME never loads). This is the real cost of "unlimited variety" (Kim's stated
reason for preferring live `--augment` over a fixed offline aug×8 set) — it isn't free, and on
a VRAM-constrained card it's the difference between fitting a run and OOM-ing at model-load.

**Not measured (would need a real end-to-end train_lora.py smoke, not just isolated encode
calls):** whether the encode call and the DiT forward/backward can overlap on the same stream
in practice (if so, the effective wall-clock delta could be smaller than the raw 2.33s number
implies), and the exact aggregate hours over a full 10-epoch reg A/B run (depends on the real
corpus/step count, which I didn't have a verified exact number for at measurement time — the
sbatch's own header estimate, "10ep × 23k live-encode ~6-12h/arm," is the existing figure to
reconcile against, not something this entry re-derives from scratch).

**Bottom line for the offline-aug×8 vs live-augment decision:** offline pays the bungee cost
ONCE (~38.4h wall for the whole corpus, previous entry) then trains at pre-encoded speed
(negligible per-step read cost, no SAME-related VRAM overhead). Live-augment pays ~2.33s/step
and ~11.4 GB extra VRAM on *every* training run that uses it, in exchange for unlimited
variety (never repeating the same 8 fixed variants). Whether that trade is worth it is a
modeling-quality question (does live variety measurably help), not a pure cost question — this
entry only prices the "worth it" question's cost side.
