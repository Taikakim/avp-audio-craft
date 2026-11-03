---
name: latch-recipe
description: Validated LatCH training recipe + dead-end findings — points to the canonical LATCH_RESULTS.txt
metadata: 
  node_type: memory
  type: project
  originSessionId: 59a68846-fc80-40ca-8060-59dc171ea761
---

**Canonical source:** `/home/kim/Projects/SAO/stable-audio-tools/LATCH_RESULTS.txt` (632 lines, consolidated 2026-05-27→28). Read it before making LatCH training recommendations; this file is the headline takeaways only.

## Ship recipe (the validated baseline, §16-18)
`AdamW 3e-4`, dim 256 / depth 6 / heads 8, **batch 64**, **40 ep**, **full data**, **`--seed 1`** (shootout winner — best-seed pick is reliable from epoch 1), `--standardize` for regression heads, **`--compile`** (+43% throughput, val unchanged, warm cache doubles items/Wh), **`--t-injection adaln_zero`** (chosen over FiLM/concat on quality: val 0.1682 vs 0.1696/0.1726), `--smooth-kind gaussian --smooth-width 3` for sparse rhythmic targets. Power cap **212 W** = efficient operating point (overhead-bound at this dim). `run-final-retrain.sh` defaults to compile + adaln_zero.

**Why:** see [[whole-track-timeseries]] for the per-stem extension. The legacy DB has full-mix only; the whole-track npz unlocks `onset_envelope_{stem}` and `rms_{stem}` per-stem heads.

**How to apply:** start any new head with this recipe. For a quick sanity, run the 3-epoch shootout first — the best seed at ep1 wins at ep3 (§15).

## Hard don'ts (verified dead ends — don't re-propose)
- **Don't train a beat-activations head expecting it to be a usable control** (§9). Closed-loop waveform-diff confirmed beat guidance moves output ~5-13% of seed scale and ignores target BPM. Deliberately skipped from ship retrain. (Per-stem drum-onset density is a different question — still untested.)
- **Don't use `beat_weighted` smoothing** (§2). Worst of the four kinds — on-beat boost made the target harder, not easier.
- **Don't scale `dim`** (§3). 256 wins; 512/768/1024 are monotonically worse AND slower (~6.5× slower at 1024). The task doesn't need >4.9M params.
- **Don't trust subset_frac ≤ 0.3 rankings** (§14). Cross-seed std at 30% (0.032) > the entire optimizer spread (0.146-0.153). Use ≥0.6 (ideally 1.0) for production heads.
- **Don't trust runs that spanned system suspend/resume** (header). Overnight matrix was corrupted once.

## Soft tips
- Top optimizers all within ~5%: Prodigy (LR-free) / schedule-free 60ep / Lion 1e-5 / AdamW 3e-4. AdamW 3e-4 = best speed/quality/energy default. Cosine helps only when LR was too high.
- `--seed N` is bit-reproducible (§16) across cap/governor changes — seeded runs don't need repeats for reproducibility validation.
- HPCP at full data has SQLite-contention preload storm with `num_workers=16`; use `num_workers=4` for 12-ch targets (§18 fix).

## Heads inventory (2026-05-28, corrected raw-MAE picture)
- **ship_s1** (compile + adaln_zero, 40ep, full data, seed=1): 4 rms_energy bands, 4 spectral, onsets_activations, hpcp. **First-pass val_median table was misleading** (v2 vs ship in different loss units: v2 standardize OFF / beta=0.5·std, ship standardize ON / beta=1.0). Real result in raw MAE: 6 small wins (RMS×4 = −3 to −10%, spectral_flux ~parity, spectral_kurtosis **−23% real win**), **2 mild regressions** (spectral_flatness +11.5%, spectral_skewness +9.9% — diagnosed as the standardize change, not architecture; fix = retrain those two **without** `--standardize` to match v2's regime, not yet run). hpcp uses cosine loss — different metric, not raw-MAE-comparable; −36% val_median taken at face value pending per-bin cosine-sim.
- **v2_best** (legacy concat, 30ep, mixed subsets): same 10 + **tonic_strength** + **beat_activations** (both v2-only carryovers; beat_activations deliberately skipped from ship as a dead control).
- **Architecture lesson:** compile/adaln_zero/FA = clear infra win (+43–57% it/s, ~2× perf/Wh), but quality gains are modest single-digit-to-mid-teens %, not dramatic. Whole-track work's value is unlocking **new per-stem control classes**, not boosting existing heads.
- **Not yet trained, probe-promising:** `downbeat_activations`, `tonic`.
- **Whole-track-only candidates (no v2 equivalent possible):** `onset_envelope_{drums,bass,other,vocals}`, `rms_{drums,bass,other,vocals}` — the per-stem family the legacy DB can't provide.

## Methodology rule (key)
- Don't compare val_median across runs with different `--standardize` and/or `huber_beta`. **Convert to raw MAE first** (SmoothL1 inverse: `err²/(2β)` if `err<β` else `|err|−β/2`; then multiply by `std_std` for standardized heads). Headline percentage deltas in val_median can be wildly misleading otherwise (§18 case: a 347% "catastrophe" became a 12% mild regression).
