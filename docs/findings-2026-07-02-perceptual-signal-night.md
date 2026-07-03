# Findings — cautious-masking verdict + the perceptual-signal night (2026-07-01/02)

Consolidated results of the FusionOpt v1.1 (cautious) A/B campaign and the v1.2
perceptual-signal implementation night. Companion docs: the design spec
`docs/superpowers/specs/2026-07-02-perceptual-signal-optimizer-directions.md` (plan +
research citations), WORKLOG 2026-07-01/02, published eval sets
`https://aavepyora.online/files/sa3-cautious-eval/`. Statistics:
`/run/media/kim/Mantu/sa3_control_runs/night_stats.json`,
`checkpoint-stats/{fusioncaut,fusion_baseline}_lr1e-4_trajectory.md`,
`.../onset_FusionCaut_lr1e-4_randomcrop/landscape/landscape_plane.json`.

---

## A. Genuinely new (not found in the literature we swept)

### A1. NS5 orthogonalization destroys per-coordinate gradient sign structure
**`cautious_keep_frac ≈ 0.53, flat for all 54k steps** (thirds 0.5285/0.5299/0.5309;
slope +0.0003/epoch; wandb `sa3-riffer/iu1bmlyj`). The Muon/NS5-orthogonalized update
agrees with the raw gradient's per-coordinate signs at barely above chance — from the
first step to the last. Consequences:
- **Cautious masking on a spectral (Muon-family) path is ~a random 47% sparsify+rescale**,
  not targeted wandering-suppression. C-AdamW intuitions (where update ≈ sign-consistent
  momentum and keep-fractions run high) do NOT transfer to orthogonalized updates.
- keep_frac cannot serve as a drift meter here (it lives at ≈0.5 permanently).
- If cautious is ever revisited on spectral paths: mask against the PRE-NS5 momentum,
  not the raw gradient.
We did not find this stated in the 2024–2026 cautious/Muon literature (two web sweeps).

### A2. Weight-space ES on a diffusion control conditioner, scored by real measurement
Setup appears novel (nearest published: DRAGON, arXiv:2504.15217 — sample-space rewards;
nothing evolves adapter/conditioner WEIGHTS): the FiLM conditioner runs host-side in
numpy on the CPU ONNX eval path, so OpenAI-ES (antithetic, sign-shaped, AWD-anchored,
CRN+rotation) evolves it with no gradients, no exports, no GPU — fitness = librosa
onset density measured on actual rendered audio.

**Pilot v1 verdict (CORRECTED): no real learning — a textbook calibration failure,
fully diagnosed.** Fitness varied ONLY between CRN seed-rotation windows (frozen to 3
decimals within windows); total weight movement over 40 generations = ~one lr-step
(max|Δ|=4e-4; tokens Δ0.01%); fresh-seed validation (96 renders, seeds never seen):
base == evolved to 0.01 on every aggregate. Root cause: σ=2% of per-tensor RMS is far
too small against a DISCRETE fitness (onset counts are a step function under CRN
determinism) → sign-shaping saw zero within-pair differences → zero gradient. The
prescribed precondition (population fitness spread ≥ 3× the repeat noise floor AT the
chosen σ) was stated and then not verified — the exact failure it exists to prevent.
**What survives:** the infrastructure is validated end-to-end (token-override path,
CRN determinism std=0.0091, fresh-seed harness), and the failure mode itself is a
transferable finding: *under CRN + discrete perceptual measurements, ES fitness
landscapes are step functions; σ must be calibrated to move the measurement, not the
weights.* v2: σ-calibration probe, continuous fitness (onset-strength envelope, not
counts), larger lr, best-tracking on a fixed holdout seed.

### A3. The ep5 triple convergence — regime change visible in weight space
Three independent instruments locate the same transition in the FusionCaut run:
1. **Audition** (Kim): ep10 sounds overtrained; ~ep5 is the sweet spot.
2. **Geometry**: the soup-center/centroid checkpoint = **epoch 5.0** (both cautious AND
   baseline runs).
3. **Trajectory-PCA**: PC2 (8.6% var) traces an ARC that apexes at ep4–5 and reverses
   (−5.5 → +3.7 → −3.8) while PC1 (88.2%) marches monotonically.
Reading: control-forming phase ends ≈ ep5; after that the run drifts (RF loss stays
flat throughout — it never sees the transition). Early-stop ≈ ep5 for BOTH recipes.

### A4. The trajectory of a 119.6M-param adapter run has REAL low-dim structure
Top-2 plane EVR **0.969 vs 0.776 for the matched random-walk null** (Antognini &
Sohl-Dickstein null — mandatory, since pure random walks also look low-dim in PCA).
88% of all weight motion is ONE persistent direction with smoothly decaying velocity.
Practical: the saved plane (`plane_basis.npz`) enables loss-grid rendering of BOTH the
RF loss and the CC (control) loss on the same plane — mapping the surface the training
loss is blind to; per the research sweep this is unpublished for diffusion-control
finetuning. (Method nugget: at D~1e8 use the Gram trick for trajectory PCA and the
closed-form D→∞ null — G_null[i,j] = Σ_{s≤min(i,j)} ‖Δθ_s‖²; naive float64 SVD + sampled
nulls needs tens of GB and dies.)

### A5. The onset-authority metric is gameable, quantified
A head can emit low-volume rapid hats over an ambient drone: requested 3 → measured
12.9 onsets/s (soup_caut g1/d3). High "authority" that is perceptually smear — invisible
to RF loss, to the correlation metric, and largely to Audiobox. Consequence encoded in
all eval tooling: numbers are instruments, audition is the verdict; spectral-flatness
logged as a smear guard.

## B. Confirmations / quantifications (established ideas, now measured here)

### B1. Cautious masking (C-Muon): coherent null-with-nuance across four instruments
- **Authority:** paired bootstrap (5000 resamples): NO significant difference at any
  gain (best soup_caut@g2 d=+0.102, P(d>0)=0.92; FusionCaut@g3 +0.044, P=0.69). An
  earlier "cautious wins at g3" point-estimate reading did not survive the bootstrap.
- **Geometry:** path efficiency 0.738 (baseline) vs 0.745 (cautious); net displacement
  28.6 vs 29.8; identical centroid. No trajectory effect.
- **Mechanism:** A1 explains both nulls (the mask is near-random on the spectral path).
- **Audition (the one real effect):** a quality TRADE — drier, cleaner separation, fewer
  hallucinated "proxy colour" artifacts; but muted highs and earlier spectral smear when
  pushed. Verdict: palette option with early-stop ~ep5; NOT a default. Plausible cause:
  the random sparsification acts as mild update noise/regularization.
- DoRA r128 cautious A/B: training done, eval pending (clean accum-4 re-run).

### B2. The 6–9 onsets/s saturation band is a SIGNAL problem, not an optimizer problem
75–81% of all eval cells (every head, every optimizer, gains ≤3) land in 6–9.5
onsets/s; requests ≤4 come out 6.2–7.1. Identical across AdamW/Fusion/cautious/soups.
The RF loss never rewarded reaching the extremes, so the capability never formed.
Attacks in flight: the CC loss term (differentiable meter in the gradient) and ES (A2).

### B3. Cross-optimizer same-task soups work; heterogeneous soups fail (basin geometry)
The 25%AdamW+75%Fusion density soup blends coherently because both checkpoints are the
same task/architecture/step → one basin (mode connectivity); the old "different
optimizers won't mix" finding came from heterogeneous-head soups (different tasks,
losses, components → different basins; LATCH_RESULTS §~1364). Optimizer difference
alone never prevented mixing. Quality metrics across blend ratios are flat; 25/75's
superiority is an audition finding (metrics can't see it — consistent with A5).

### B4. RF loss is blind to control (the root diagnosis)
Flat within 0.4% across configs that differ 3.1× in control authority; drift invisible;
saturation invisible; smear invisible. Every v1.2 direction (CC loss, ES, sonar,
landscape maps) is a way to route measurement around this blindness.

## C. New tooling (all TDD'd; uncommitted on the working tree as of this doc)

| Piece | Where | State |
|---|---|---|
| Cautious masking (`cautious` component + keep_frac telemetry) | `stable_audio_tools/training/fusion_opt.py` | 5/5 tests; A/B complete |
| CC probe + loss (`--cc-probe/--lambda-cc/--cc-t-max`) | `control/sa3_control/{cc_probe,train_cc_probe}.py`, `train.py` | 5/5 tests; probe R²=0.598 (MAE 0.69 on/s); GPU smoke pending |
| ES echo-location (+ server hook `raw_control_tokens_npy`) | `control/sa3_control/es_conditioner.py`, `onnx/control_eval_server.py` | 5/5 tests; pilot RUNNING |
| Sonar (radial probes → `FusionOpt.gamma_scale`) | `stable_audio_tools/training/sonar.py` | 6/6 tests; bake-off cell pending |
| Landscape mapper (Gram-trick PCA + closed-form null) | `control/sa3_control/landscape_map.py` | 3/3 tests; validated on real run |
| Eval/publish pipeline (CPU grid eval, A/B + audition pages, Dreamhost rsync) | `Misc/*.py`, published sets | live |

## D. Verdicts landed in the morning (10:00 2026-07-02)

### D1. DoRA r128 cautious A/B: DIVERGED — and the root cause is a genuinely new bug class
The cautious run NaN'd (all 687 LoRA tensors) between ep2 and ep3; the
identical-minus-cautious baseline trained 8 epochs clean. Healthy ep0–2 were
competitive (Fréchet 0.0785 vs baseline best 0.0750). **Root cause (adds to A1):
the C-AdamW-style `1/keep_frac` survivor rescale preserves mean magnitude but
inflates the update NORM by `1/sqrt(keep)` — +37% effective spectral LR at the
keep≈0.53 near-random masks orthogonalized updates produce** (vs ~+5% at C-AdamW's
keep≈0.9, where the convention is safe). FiLM tolerated the inflation (and it
explains its "pushes harder" audition character + slightly larger net displacement);
r128 full-fusion DoRA did not. Fixed: `apply_cautious` is now norm-preserving
(`||U||/||U·mask||` rescale; tests green). NOTE: all completed cautious A/Bs used the
OLD semantics. Eval page (collapse visible in the metrics):
`https://aavepyora.online/files/sa3-cautious-eval/dora/`.

### D2. ES pilot v1: null (seed-window artifact), diagnosed + σ-calibrated (see A2)
v2 running with σ=0.15 (probe-calibrated: 46–169× the noise floor at σ 0.1–0.5,
vs ~1× at v1's 0.02), lr 0.05. Verdict via fresh-seed validation of the FINAL iterate.

### D3. Still open
- FusionCC A/B (the CC-loss run) — RUNNING (wandb iy7z7cls, ETA ~15:00); the direct
  attack on B2. cc term verified engaging per the t-gate; ~19% step overhead.
- ES v2 final + fresh-seed validation (~13:00).
- Sonar bake-off cell; GPU loss-grid (RF+CC fields) on the A4 plane.
