# ModularOptimizer test plan: precision, group balance, NorMuon variant (desktop)

Owner: KUANG (draft October 17, 2026). Code changes are written and CPU-tested by KUANG; runs are launched on the
desktop (Antigravity or a desktop agent) through `Misc/gpu_guard.sh`. Nothing below has run on a GPU yet.

Source review: memory note `project_modular_opt_review_2026_10`; Microsoft dion (`dion/normuon.py`, `dion/nordion2.py`,
origin/main 7692479); arXiv 2605.23061 (SF-NorMuon, Appendix D); arXiv 2608.11612 (Dion3, section 6 "Finite Precision").
Code baseline: `stable_audio_tools/training/modular_opt/` on audio-tools-avp `origin/fix/inharmonicity-aux` (4af13b0).

## Reading rules (from TRAINING.md / EXPERIMENTS E5)

- A difference under 0.004 in held-out loss is noise for a head bracket. Hold `--num-workers` fixed (16) inside a
  comparison and record it. Every "winner" needs a repeat seed before it becomes a default.
- Batch arms match optimizer STEPS, not epochs.
- Every run writes `run_meta.json` with hypothesis, kill criterion, recipe and `kim_feedback: null`.
- Loss is not the verdict for steering heads or FiLM: the ear and the density/drift meters are. Listening gates are marked.

## Hypotheses under test

| # | Hypothesis | Evidence so far | Test |
|---|---|---|---|
| H1 | bf16 adapter + optimizer state in the FiLM trainer rounds away most of each step at lr <= 1e-3, and biases the E12 bracket toward high lr | CPU probe: bf16 keeps 29% (lr 3e-4), 64% (1e-3), 92% (3e-3) of fp32 motion | A |
| H2 | The sign group (1D gains/biases, lr per element, no wd) is ~sqrt(d_in) = 16x hotter than the spectral group at d256 and is what diverges at lr >= 5e-2 | arithmetic + E6 divergences; SF-NorMuon runs 1D params on SF-AdamW at matched RMS | B |
| H3 | The SF-NorMuon recipe (update RMS 0.2*lr, Adam for 1D, mu 0.8, wd 0.05 at z, longer warmup) trains heads at least as well as the anchor and tolerates higher lr | paper Table 5, Fig. 2 | B, D |
| H4 | Our NorMuon vs dion's differs only on wide matrices (d_out < d_in) by sqrt(d_in/d_out); for heads it is noise, for DoRA it is a built-in ~3.5x lora_A boost | CPU probe (below) | C |
| H5 | The routing radius is a no-op whenever NorMuon is on | CPU probe: steps identical to 0.0 for radius 1 vs 2 | T0 |

## T0. CPU unit tests (KUANG, laptop, before any GPU time)

Added to `tests/` next to the existing modular tests; tiny tensors only.
1. `test_radius_noop_with_normuon`: radius 1 vs 4 give bit-identical steps with NorMuon on, and different steps with it off.
2. `test_bf16_step_retention`: fp32 vs bf16 parameter, 600 steps; documents the retention numbers above (regression guard for the C1 fix).
3. `test_normuon_dion_mode_matches_reference`: new `normuon_mode="dion"` equals a re-implementation of dion's
   `_normuon_normalization_core` + `adjust_lr_spectral_norm` to 1e-5.
4. `test_vadd_damping_applied_once`: documents that today `var_damp` multiplies eta twice when VADD is active
   (`optimizer.py` line 510 and line 516); test pins whichever behaviour Kim decides.
5. `test_rms_scale_mode`: `update_scale="rms0.2"` gives update RMS = 0.2*lr on every 2D shape.

## Code changes (draft branch, all default-off so existing runs reproduce)

- C1 `control/sa3_control/train.py --adapter-dtype {bf16,fp32}` (default bf16 = today). fp32 keeps the adapters,
  `cond_enc` and therefore the optimizer state in fp32; the frozen DiT stays bf16; forward under bf16 autocast.
  Dion3 lesson: one fp32 update per step, cast once.
- C2 `ModularOptimizer(normuon_mode="row_unit"|"dion")`: "dion" = per-row mean-square EMA, divide, then rescale to the
  pre-normalization Frobenius norm, step lr*sqrt(d_out/d_in) (dion's `spectral_norm` adjust).
- C3 `ModularOptimizer(update_scale="native"|"rms0.2")` (SF-NorMuon line 13: step = 0.2*lr*sqrt(m*n)/||P||_F) and routing
  `scalar_opt="sign"|"adam"` (1D parameters on Adam inside the same Schedule-Free z/x/y, betas (0.95, 0.99)).
  `train_latch.py`: expose `--mod-sign-lr`, `--mod-sign-wd`, `--mod-update-scale`, `--mod-scalar-opt`, `--mod-momentum`
  (beta1 today; the paper's mu), `--mod-normuon-mode`.
- C5 `ModularOptimizer(normuon_after_unwhiten=False)`: when True, NorMuon runs after the Shampoo pullback, so the
  per-neuron equalisation is what reaches the weights.
- C4 Telemetry per group (only on log steps): update RMS, weight RMS, relative update ||dW||/||W|| per group, Shampoo
  `eigh_failures`. This is what tells a damped group from a hot one; today's telemetry sums all groups.

## A. FiLM precision (first; tests H1)

Base = E12 bracket recipe (`control/run_film_modular_bracket.sh`: medium-base, batch 1, crop 512, random crop,
cfg dropout 0.1, warmup 300, logit_normal t, scalar onset_density, Shampoo, EMA 0.999, 6000 steps, saves every 2000).

| Arm | dtype | lr |
|---|---|---|
| A1-A3 | bf16 (today) | 3e-4 / 1e-3 / 3e-3 (reuse E12 stage-1 results if they are complete and same commit) |
| A4-A6 | fp32 adapters | 3e-4 / 1e-3 / 3e-3 |
| A7 | fp32 | best of A4-A6, seed 43 (repeat) |

- Readouts: val RF loss; `eval/film_bracket_density_check.py` density spread at FiLM gain 1.0; CLAP drift vs the
  unguided render; peak VRAM; s/step.
- Prediction: A4/A5 clearly better than A1/A2; A6 close to A3; the lr optimum moves down.
- Kill: fp32 arms within noise of bf16 at every lr (then H1 is real in the probe but irrelevant in practice).
- Decision: if fp32 wins, the E12 54k run is re-read as a bf16 result and re-run at fp32 with the A-bracket lr (Kim's call).
- Cost (estimate from E12's 3 x 6000 steps ~ 2 h): ~4 h for A4-A7.

## B. LatCH head group balance (tests H2, H3)

Base = Phase E E05 recipe (density head, depth 8, d256, b16, 20 epochs, SF on, Shampoo, 16 workers, EMA as in E05).

| Arm | spectral lr | 1D / sign | notes |
|---|---|---|---|
| B0 | 1e-2 | sign, 1e-2 | anchor (= E05) |
| B1 | 1e-2 | sign, 2e-3 | only the 1D group cooled |
| B2 | 3e-2 | sign, 2e-3 | was divergent territory with sign at 3e-2 |
| B3 | 3e-2 | sign, 3e-2 | control for B2 (expected to diverge, as Phase A) |
| B4 | rms0.2, lr 1e-2 | Adam 1e-2 (0.95, 0.99) | SF-NorMuon recipe: mu 0.8, wd 0.05 at z, warmup 1500 |
| B5 | rms0.2, lr 2e-2 | Adam 2e-2 | same, higher lr |
| B6 | best of B1-B5, seed 1 | | repeat |

- Readouts: held-out loss per epoch; per-group relative update (C4); divergence epoch if any.
- Predictions: B1 within noise of B0 or slightly better late; B2 trains where B3 diverges (that is the H2 test);
  B4 within noise of B0; B5 does not diverge.
- Kill for H2: B2 diverges like B3.
- Then the stability check on the air head (E6 setup, seed 764 clip, the 0:13 reverse-cymbal event): best B-arm at the
  lr that diverged before (5e-2) for 25 epochs. Listening gate: Kim, per-epoch sweep page as in E6.
- Cost (estimate, Phase D/E timings): ~1.5 h per 20-epoch arm, ~10 h for B0-B6.

## C. NorMuon variant (tests H4)

1. Head: B0 recipe with `normuon_mode="dion"` (1 arm + repeat). Prediction: within noise (heads are mostly square or
   tall; only the 256->1 output, if routed spectral, is wide and would step ~16x smaller).
2. DoRA: goa3 recipe (`train_lora_modular.py`), 2000 steps, `row_unit` vs `dion` vs `dion` + `lora_a_lr_mult 3.5`.
   Readouts: loss, lora_A row-space change (the 99.2%-unchanged metric of 2026-09-22), DoRA magnitude spread.
   Prediction: `dion` alone slows lora_A (~3.5x smaller steps at 128x1536) and loses; with mult 3.5 it matches `row_unit`.
- Decision: keep `row_unit` unless `dion` + mult wins beyond noise; either way document that `row_unit` contains a
  sqrt(d_in/d_out) boost on wide matrices.

## C2. Shampoo and MONA

Facts (code read, October 17, 2026):
- The shipped FiLM `onset_Fusion_lr1e-4_randomcrop` used `--optimizer fusion` = ns5 + normuon + sf: no MONA, no Shampoo.
  FusionOpt keeps z/x/momentum in fp32, so that run did not have the bf16 problem of section A.
- The E12 modular FiLM runs use `--mod-whitening shampoo`, so E12 vs shipped FiLM is confounded by Shampoo as well as by
  optimizer and precision.
- ModularOptimizer Shampoo (Mousse, one-sided, alpha 0.125): whiten -> NS -> NorMuon -> unwhiten -> restore norm. For
  left-side matrices (d_out <= d_in, incl. square head layers) the unwhitening mixes rows after NorMuon equalised them.
- FusionOpt Shampoo (two-sided, -1/4, no unwhitening) feeds NS, which sets every singular value to 1: it only rotates the
  polar factor (exactly redundant with NS when the statistics are instantaneous).
- MONA adds alpha * EMA(g_t - g_{t-1}) to the momentum input: a high-pass term that, at batch 1-16, is mostly gradient noise.

Arms (on the B winner, heads; and on the A winner, FiLM):
| Arm | whitening | note |
|---|---|---|
| S0 | shampoo (today) | reference |
| S1 | none | prediction: within noise, faster per step (Phase B found no Shampoo gain) |
| S2 | shampoo, NorMuon after unwhitening | code change C5 (`normuon_after_unwhiten=True`); tests the ordering, not Shampoo itself |
MONA: no new arms; not ported to ModularOptimizer. Re-test only if S2 shows preconditioning matters.

## D. Weight decay and warmup (only after B, on its best arm)

wd at z {0.01, 0.05, 0.1} x warmup {500, 1500}; 6 arms, 20 epochs. SF-NorMuon Lemma 3.2: wd sets the steady-state weight
RMS and therefore the relative step size; expect the effect to show late (epoch 10+), so read the last 5 epochs.

## E. Representation measurements (no training; feeds the VICReg decision)

Script (KUANG to write; reimplemented from Skean et al. 2025, since `information_flow` has no LICENSE file): hook the 24 DiT
block outputs at sigma {0.9, 0.5, 0.1}, 64 clips x 2 prompts, for base, shipped FiLM, the A-arm FiLM, one DoRA.
Per block: top-3 channel magnitude (spikes), step-up/step-down blocks, prompt entropy and dataset entropy (with and
without spike channels), curvature over frames, TwoNN intrinsic dimension, a linear probe for onset density, and the
attention-sink ratio on a few heads (needs explicit attention, not SDPA).
- FiLM spike test: FiLM scale/shift magnitude on spike channels vs others; then zero FiLM on spike channels only and
  measure density range vs CLAP drift. Prediction (hypothesis): style drift drops more than density range.
- VICReg gate: add a correlation-based (not covariance) variance/decorrelation penalty only if a block shows entropy
  collapse vs base beyond the seed spread.

## Not in this plan

- Dion3 row selection: only for DiT/DoRA/full-FT runs; heads gain nothing (Newton-Schulz is cheap there).
- Running anything on the laptop.

## Order and gates

T0 + C1-C4 (KUANG, CPU) -> A -> B (in parallel with E if VRAM allows: E is inference only) -> C -> D.
Kim approves each launch. B overlaps the unlaunched Phase F (EXPERIMENTS E5: "not authorised to launch"), so B needs
Kim's explicit go as well.
