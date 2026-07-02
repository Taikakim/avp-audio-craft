# CONTINUITY — journal

> The Translator (né FLATLINE): carries Kim's musician intuitions into rigorous ML and
> the math back into something he can hear. Keeper of the thread — the written record
> that survives the resets. FusionOpt / perceptual-signal line.
> Profile: https://aavepyora.online/files/profiles/continuity.html

## 2026-07-02

- **Found (the day's headline):** FusionCC — the cc-probe loss that puts a learned
  onset-meter INSIDE the training gradient — posted the campaign's first statistically
  significant control-authority win: corr .584→.880 at gain 2 (paired bootstrap CI95
  [+.04,+.83], P=.99); the sparse floor broke (request-3 renders at 5.7 vs every other
  head's ~6.0–6.9 floor); request-6 tracks at 6.1–6.6 vs baseline's 8.5–9.3 overshoot.
  Upper ceiling (~9.2) unmoved — the probe can't see past corpus density; that's the
  next target. Audition pending (the taste has the con). → findings doc
  `docs/findings-2026-07-02-perceptual-signal-night.md` (local) · live five-way page
  https://aavepyora.online/files/sa3-cautious-eval/onset_film/
- **Found:** NS5 orthogonalization destroys per-coordinate gradient sign structure —
  `cautious_keep_frac ≈ 0.53, flat over 54k steps`. Consequence: cautious masking on
  spectral paths ≈ random half-sparsification; keep_frac can't serve as a drift meter.
  Not found in the 2024–26 literature we swept. → findings doc §A1 (local)
- **Found:** the C-AdamW `1/keep_frac` cautious rescale hides a `1/sqrt(keep)` update-norm
  inflation — +37% effective spectral LR at keep≈0.53 — which NaN'd the DoRA r128
  cautious A/B between ep2→3 (baseline clean). Fixed: norm-preserving rescale in
  `fusion_opt.apply_cautious` (tests green). → findings doc §D1 (local)
- **Found:** the ep5 triple convergence — Kim's audition sweet spot, the soup-center
  checkpoint, and the trajectory-PCA PC2 arc turnover all locate the same regime change
  (control-forming → drift) that RF loss never sees. → findings doc §A3 (local)
- **Found:** a 119.6M-param adapter run's trajectory has REAL low-dim structure: top-2
  plane EVR 0.969 vs 0.776 random-walk null; 88% of motion in one persistent direction.
  Method nugget: Gram-trick PCA + closed-form D→∞ null (naive float64 SVD dies at ~10 GB).
  → findings doc §A4 (local), `sa3_control/landscape_map.py` (local)
- **Ruled out (ES v1):** σ=2%-RMS perturbations against a DISCRETE fitness (librosa
  onset counts under CRN determinism) — step-function landscape, zero gradient; the
  apparent "44% gain" was seed-window luck (retracted same day). Lesson: calibrate σ
  against the MEASUREMENT, verify population spread ≥ 3× the repeat-noise floor first.
- **Ruled out (ES v2):** global L2-normalized ES steps at N=37k — spreads lr over √N,
  explore:exploit ≈ 600:1; center walks microscopically despite real candidate signal.
  Lesson: normalize per-COORDINATE; dimension eats global norms. v3 (RMS-normalized
  steps) shows the healthy signature: monotonic within-window descent, spread ~75× floor.
- **Did:** implemented + tested the perceptual-signal quartet — cc-probe loss
  (`sa3_control/cc_probe.py`, held-out R²=0.598), ES echo-location
  (`sa3_control/es_conditioner.py` + server token-override hook), sonar radial probes
  (`stable_audio_tools/training/sonar.py` → `FusionOpt.gamma_scale`), trajectory mapper.
  22 tests green. Research pass (2 sweeps, late-25→mid-26 lit) folded into the spec
  appendix. → `docs/superpowers/specs/2026-07-02-perceptual-signal-optimizer-directions.md` (local)
- **Did (infrastructure):** the OSC multicast channel + agent-dialogue protocol
  (presence/ack-reserve/knock/welcome, atomic lock, `wait` wake by GHOST-NOTE), spec +
  rule 6 (verify-first for consequential claims — ratified in practice the same hour
  during the public-mirror event). → OSC spec (local) · live mirror
  https://aavepyora.online/files/AGENT_DIALOGUE.html

## 2026-07-01

- **Found (four-instrument null):** cautious masking (C-Muon) on the FiLM onset head —
  no significant authority effect (paired bootstrap, all CI95 span zero), no trajectory
  effect (path-eff 0.738 vs 0.745, identical ep5 centroid), mechanism = near-random mask
  (see keep_frac above); the one real effect is Kim's audition: a quality TRADE (drier,
  cleaner separation vs muted highs, earlier smear when pushed). Keep as palette option
  w/ early-stop ~ep5; not a default.
- **Found:** the 6–9 onsets/s saturation band is OPTIMIZER-INDEPENDENT (75–81% of cells
  in-band for every head) — a training-signal problem, which motivated FusionCC.
- **Found:** the onset-authority metric is gameable — request-3 "ambient drone with
  low-volume rapid hats" measured 12.9 onsets/s (Kim's ear caught it; no metric did).
  Standing rule: numbers are instruments, audition is the verdict.
- **Did:** full cautious A/B campaign — trained FiLM FusionCaut (54k) + DoRA r128-caut,
  canonical 3-prompt CPU eval harness (ONNX server + librosa), cross-optimizer soups,
  ep2/ep5/ep10 trajectory audition, all published:
  https://aavepyora.online/files/sa3-cautious-eval/ (onset_film, onset_film_trajectory,
  dora) · Dreamhost publish pipeline (rsync, host-key pinned).
- **Ruled out:** cross-optimizer soup blend ratio as a quality lever — metrics flat
  across 10/15/20/25/30% AdamW; the famous 25/75's superiority is an audition finding.
  (Same-task cross-optimizer soups DO mix — one basin; heterogeneous-head soups don't.)

## 2026-06-30 → 07-01 (night)

- **Did:** SAO restructure path-sweep (launch_riffer→SAO/.venv rewire, ARCHITECTURE/
  MASTER doc sweep); cautious component + keep_frac telemetry into FusionOpt (TDD);
  train.py auto-export PYTHONPATH fix; renders UI builders (same-playhead five-way A/B
  page, DoRA audition page). → WORKLOG 2026-07-01/02 entries (tracked; commits pending)
