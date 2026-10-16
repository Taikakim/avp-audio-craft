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
4. `test_vadd_damping_is_applied_twice`: documents that today `var_damp` multiplies eta twice whenever VADD fires
   (with or without escape velocity); test pins whichever behaviour Kim decides.
5. `test_rms_scale_mode`: `update_scale="rms0.2"` gives update RMS = 0.2*lr on every 2D shape.

## Code changes (draft branch, all default-off so existing runs reproduce)

- C1 (as built: `--mod-state-dtype fp32`, see Build status) fp32 optimizer state and update arithmetic for bf16
  adapters; the adapters and the frozen DiT stay bf16. Dion3 lesson: one fp32 update per step, cast once.
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
- C6 Half-batch noise logging (section N), opt-in flag `--log-grad-noise N` (every N optimizer steps), all trainers.

## Build status (KUANG, 2026-10-17): C1-C7 + T0 written and CPU-tested on the laptop

**Branches** (all `feature/modular-opt-c-series`, none merged):
| Repo (desktop path) | Base | What |
|---|---|---|
| audio-tools-avp (`SAO/stable-audio-tools`) | origin/fix/inharmonicity-aux 4af13b0 | `modular_opt/`: optimizer options, `grad_noise.py`, routing `scalar_opt`; `tests/test_modular_c_series.py`; `scripts/ns_orthogonality_check.py` |
| stable-audio-3 (`SAO/stable-audio-3`) | origin/latch-sa3-phase1 42cc95e | `scripts/latch/train_latch.py` + `scripts/train_lora_modular.py` flags; `tests/test_latch_modular_c_series.py` |
| avp-audio-craft (`SAO`) | origin/main acdedf5 | `control/sa3_control/train.py` flags; `control/sa3_control/tests/test_grad_noise_accum_halves.py`; this file; TRAINING.md |

The trainer branches need the audio-tools-avp branch checked out in `SAO/stable-audio-tools` (the new keyword
arguments raise `TypeError` on the old optimizer, so a mismatch fails loudly at launch, not silently).
⚠ stable-audio-3: GHOST-NOTE's `train_latch.py --optimizer muon_ref` (used by `latch/run_bass_baselines.sh`) is not
on origin/latch-sa3-phase1, so it is uncommitted on the desktop; merging this branch there may conflict in
`make_optimizer` / argparse. Commit it first, then merge.

**Verified on the laptop (CPU):**
- All new options at their defaults reproduce the historical optimizer bit-for-bit: 24 configurations (whitening
  none/shampoo/soap x SF off, NorMuon off, warmup+wd, brake, escape velocity, SNR gate, multiplicative magnitude),
  25 steps each, max |difference| 0.0 vs origin/main's code.
- `tests/test_modular_c_series.py` 22 tests + existing modular tests: 34 passed. Covers T0.1-T0.5, dion-mode equality
  with a re-implementation of dion's NorMuon (1e-4), rms0.2 = 0.2*lr per element, bf16 NS direction (cos > 0.99),
  NorMuon-after-unwhiten row equalisation, Adam group (= manual Adam; no momentum under SF), per-group telemetry,
  fp32 state (recovers the bf16 loss: 1.00 +/- 0.05 of fp32 motion at lr 3e-4, survives a save/load), and the
  noise meter recovering a known noise scale (within 25%).
- stable-audio-3 `tests/test_latch_modular_c_series.py` (flags reach the optimizer; the half-batch reading leaves
  `p.grad` and the RNG untouched) + existing latch tests: 7 passed. FiLM accumulation-halves arithmetic: 2 passed.
- `scripts/ns_orthogonality_check.py` on CPU (Gaussian + low-rank 256-3072 wide): our bf16 NS = FusionOpt's bf16
  `newton_schulz_5` exactly (same polynomial); cos to fp32 0.9997 on well-conditioned inputs, 0.91-0.96 on low-rank
  ones (the noise directions differ). The GPU run on real momentum (`--ckpt`) is still the T readout.

**Not verified:** anything on a GPU, any real training run, the FiLM and DoRA trainers end to end (they need the DiT).

**Deviation from the plan: C1 is `--mod-state-dtype fp32`, not `--adapter-dtype fp32`.** Keeping bf16 adapters and
giving the OPTIMIZER fp32 master state (momentum, Schedule-Free z/x, or an fp32 weight copy without SF; the bf16
weight is written from it once per step) fixes the rounding (F21) without touching the forward pass, autocast or
the adapters' dtype, and works in every trainer (FiLM, LatCH, DoRA, full-FT). It is what FusionOpt already does.
torch's `load_state_dict` would cast that state back to bf16 on resume; `ModularOptimizer.load_state_dict` keeps it fp32
(tested). In T3/T4 read "fp32 (C1)" as `--mod-state-dtype fp32`.

**Found while building:**
- `train_latch.py` set `opt._telem_on` only with `--wandb`, and ModularOptimizer's `_telem_on` defaults to True (FusionOpt's
  to False), so every LatCH modular run WITHOUT wandb (Phases A-E) computed the per-parameter `.item()` telemetry on
  every step. Fixed: telemetry now runs only on logged steps. Unmeasured speed effect; numerics unchanged.
- VADD: `var_damp` is applied twice whenever VADD fires, with or without escape velocity (ev_mult *= var_damp, then
  eta *= ev_mult * var_damp): the damping is var_damp squared. Pinned by `test_vadd_damping_is_applied_twice`; behaviour
  unchanged pending Kim's decision.
- Our NorMuon vs dion on a 32x512 matrix: 4.76x (sqrt(16) = 4 from the shape, the rest because ours rescales rows to
  exactly unit length while dion keeps the Newton-Schulz output size). Matches GHOST-NOTE's 4-8% on square/tall.

**Not built:** the momentum-buffer version of N (needs two shadow momentum buffers every step, not only on log steps);
the MONA version of N (FusionOpt); Dion3 row selection; section E's representation script.

### Flags per arm (desktop launch cheat sheet)

FiLM (`control/sa3_control/train.py`, E12 recipe + these):
| Arm | Flags |
|---|---|
| T1 / A1-A3 | (none: today) |
| T2 | `--mod-ns-dtype bf16` |
| T3 / A4-A6 | `--mod-state-dtype fp32` |
| T4 | `--mod-state-dtype fp32 --mod-ns-dtype bf16` |
| A, Wintermute's extra arm | add `--grad-accum 1 --ema 0` to the A winner (the shipped run used neither) |
| N on FiLM | `--log-grad-noise 50` (needs even `--grad-accum`; accum 2 = halves of 1 crop, accum 4 = 2+2) |
| C4 on any arm | `--log-opt-groups` (opt_groups.jsonl every `--log-every` steps) |

LatCH (`stable-audio-3/scripts/latch/train_latch.py --optimizer modular`, E05 recipe + these):
| Arm | Flags |
|---|---|
| B1 | `--mod-sign-lr 2e-3` |
| B2 | `--lr 3e-2 --mod-sign-lr 2e-3` |
| B3 | `--lr 3e-2` |
| B4 | `--mod-update-scale rms0.2 --mod-scalar-opt adam --mod-scalar-sf-beta 0.95 --mod-momentum 0.8 --mod-wd 0.05 --mod-warmup 1500` |
| B5 | B4 with `--lr 2e-2` |
| C (head) | `--mod-normuon-mode dion` |
| S1 / S2 | `--mod-whitening none` / `--mod-normuon-after-unwhiten` |
| N, C4 | `--log-grad-noise 50 --log-opt-groups` (2 extra passes on logged steps) |
| P0 / speed | `--save-opt-state`, `--log-mom-spectra 200`, `--mod-ns-batch` (section P) |
Note: in B4 `--mod-wd 0.05` decays at z for the matrices; the adam group's wd is `--mod-sign-wd` (default 0).

DoRA (`stable-audio-3/scripts/train_lora_modular.py --optimizer modular`): C arms `--modular-normuon-mode dion`,
`... dion --modular-lora-a-lr-mult 3.5`; also `--modular-update-scale`, `--modular-ns-dtype`, `--modular-state-dtype`,
`--modular-scalar-opt`, `--modular-sign-lr`, `--modular-normuon-after-unwhiten`.

## N. Gradient-noise logging: a measured batch-size estimate (logging only, rides on A and B)

Idea (Kim, 2026-10-17): instead of borrowing an LLM batch size, measure per matrix whether the batch carries more
signal than noise. Split each step's batch into two independent halves, compute the gradient of each, compare.

What is logged, per 2-D matrix, every N steps (C6):
- `c_t = cos(G1, G2)`: cosine between the two half-batch gradients. Noise differs between the halves, the signal does not,
  so c_t is the share of signal seen at HALF the batch.
- `r_t = |G1 - G2|^2 / |G1 + G2|^2` and the derived **noise scale** `B_noise ~ B * tr(Sigma) / |G|^2` (McCandlish et al.
  2018, "An Empirical Model of Large-Batch Training", estimated from the two halves: the difference measures the noise,
  the sum the signal). Below B_noise a bigger batch gives nearly proportional progress per step; well above it, compute
  is wasted. This is the number that answers "is batch 16 (or 64) enough for this model and data".
- The same two quantities on the momentum buffer (the thing Muon actually orthogonalises).
- **Null baseline:** the cosine between half-batch gradients from two UNRELATED steps (e.g. step t and t+N), so "near
  zero" is read against what no shared signal looks like here, not against a guessed threshold.

How the halves come for free:
- FiLM: the standing recipe uses grad accumulation 2, so the two micro-batches are the two halves; keep their gradients
  apart for one step every N (one extra gradient copy of the trainable params on log steps only).
- LatCH: batch 16 = 8 + 8 (two backward passes on log steps only, or per-half accumulation).
- Batch 1 with no accumulation: not measurable this way; log on an accumulation-2 run instead.

Optional MONA version (FusionOpt only): the same test on MONA's term A_t (running sum of gradient differences).
- Keep TWO separate A buffers, one fed by each half, or their shared history makes the cosine look good by itself.
- Also log `|A_t| / |G_t|`: a large ratio with poor half-to-half alignment means noise is steering the update.
- Prediction: near-zero alignment at batch 1-16 (the signal in a gradient difference is curvature x step, the noise about
  twice a gradient's), i.e. MONA is not usable at our batch sizes. This settles F26 without a listening arm.

Reading:
- Convert the half-batch cosine to full-batch terms before comparing runs (a half has twice the noise variance).
- B_noise grows as the loss falls: report it over the run (start / middle / end), not once.
- It answers the efficiency question only. Whether a smaller batch SOUNDS or generalises better is a separate question
  (F6, D26); listening decides that.
- Cost: on log steps only; nothing changes the training trajectory (verify: same loss curve with the flag on/off at fixed seed).

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

### E2. Sensitive directions of the DiT: find, render, name (built 2026-10-17, KUANG; paper 2610.15724)

`eval/sensitive_directions.py` (tests: `eval/tests/test_sensitive_directions.py`, CPU incl. an end-to-end run against a fake
SA3; never run on the real model). Per prompt and seed: Euler-sample to the first step with sigma <= 0.6, take the top-k right
singular vectors of d(block output)/d(latent) (or d/d text conditioning, `--wrt cond`) at one DiT block via SA3's
`exit_layer_ix` early exit, render a +/- ladder along each (perturbation RMS = alpha x RMS of x_k), measure descriptors
(onsets, hi-hat onsets, kick-band bpm, centroid, loudness, bass/mid/air level, crest; optional CLAP labels), propose a name
from the descriptor slope z-scored against the spread of the unperturbed renders, report cosines with LatCH head gradients
(`--heads`), count which names recur across seeds/prompts, and write a listening page. Names are proposals; listening
decides. Suggested first run: 2 prompts x 3 seeds, block 12 and one early and one late block, k 8, both `--wrt` modes.
Cost per seed and block: ~2 x iters x k/chunk partial forward passes + k/chunk backward passes for the directions, plus
k x (len(alphas) - 1) renders of the remaining steps.

## T. Throughput: bf16 Newton-Schulz (WINTERMUTE, 2026-10-17)

Measured 2026-10-16 (`control/time_film_optimizers.sh`, `train.py --step-times`, FiLM adapter 119.5M params, 400 steps per arm,
results in `Mantu/sa3_control_runs/film_optimizer_timing_20261016/SUMMARY.tsv`):
- Forward + backward without an optimizer update: 216-218 ms in every arm.
- Extra per update: AdamW +14 ms, Lion +63, FusionOpt (ns5 + normuon + sf, `hot_dtype="bf16"`) +100, ModularOptimizer +320.
- Switching off Shampoo, NorMuon, Schedule-Free or EMA each changes the modular cost by under 15 ms. The cost is the core
  spectral update on 73 matrices, which `lmo.py` runs in fp32 (`G.float()`); FusionOpt runs the same iteration in bf16.
- The shipped FiLM's 3.2 steps/s = FusionOpt at accum 1. The E12 54k modular run trained at 2.29 steps/s (2.61 in the timing run).
- SOAP OOMs on the 16 GB card (a 2.25 GiB identity matrix for the 3072-wide layers).

Proposed code change C7 (default off): `ModularOptimizer(ns_dtype="fp32"|"bf16")`, running only the Newton-Schulz iteration in
bf16 and casting the result back. This is compatible with F28 (rounding matters where small updates are added to large
weights, not inside the orthogonalisation) and with C1 (fp32 adapters and state): the target recipe is bf16 orthogonalisation,
fp32 weights, fp32 optimizer state.

| Arm | ns_dtype | adapters | note |
|---|---|---|---|
| T1 | fp32 | bf16 | today (= M1 above, 549 ms per update step) |
| T2 | bf16 | bf16 | the speed change alone |
| T3 | fp32 | fp32 (C1) | the precision fix alone: does fp32 storage cost time? |
| T4 | bf16 | fp32 (C1) | the target recipe |

- Readouts: the same `--step-times` summary (startup, first step, steady ms, update vs no-update step), peak VRAM; plus an
  orthogonality check on 20 sampled update matrices, ||U^T U - I|| for bf16 vs fp32 NS on the same input (CPU or GPU, no training).
- Prediction: T2/T4 cut the per-update cost from ~320 ms toward FusionOpt's ~100; T3 adds little.
- Kill for C7: bf16 NS saves under ~30% of the per-update cost, or its orthogonality error is clearly worse than FusionOpt's.
- Cost: ~20 min GPU (4 x 400 steps + model loads). Run before A, so A's arms can use the faster path if T4 holds.

### WINTERMUTE comments on the plan (2026-10-17)

- **A has a result to compare against already.** The E12 bracket's FiLM density grid (`files/evals/film_bracket_check.html`,
  `film_bracket_density_check_20261016/run_meta.json`) found that the density response comes with training length: the shipped
  FiLM at its own step 5400 barely steers (spread 3 -> 12 onsets/s = 0.2 at gain 1, 2.9 at 54k), the bf16 modular 6000-step arms
  0-0.2, and the bf16 modular 54k run 1.4 at gain 1, 3.9 at gain 2.5. So a 6000-step A arm cannot be judged on density spread
  alone; read A on loss and per-group relative update (C4), then take the winner to a longer run (or compare at matched steps
  against the shipped run's own checkpoints, which exist every 5400 steps).
- **A should also use `--grad-accum 1` in one arm.** The trainer's defaults became `--ema 0.999 --grad-accum 2` after the shipped
  run, which used neither, so E12 vs shipped is also confounded by accumulation and EMA (on top of optimizer, precision, Shampoo).
- **bf16 EMA elsewhere:** the LUMI full-FT trainer's `--base_precision bf16` trains the weights themselves in bf16 and its
  EMA (0.9999) barely moves (1.4% from base vs 4.8% for fp32; AVP drone sweep, WORKLOG 2026-10-16). Same family as F21; the
  precision question (item 3 of the planning rule) applies to `train_lora.py` full fine-tunes too, not only the FiLM trainer.
- **Half-batch noise logging (N) on FiLM:** with `--grad-accum 2` the two micro-batches are the halves, but each is batch 1,
  i.e. one crop; the cosine then mixes crop-to-crop variation with gradient noise. Worth stating in the reading, or logging on an
  accum-4 run (2 + 2).

## P. Spectral probes, direction agreement, adapter audit (KUANG, 2026-10-17; papers: SAMuon 2608.25990, Evil Spectra 2606.31591)

Gate for any new optimizer (SAMuon-lite, PolarAdamW, finite-r): does a bigger step along the NON-leading momentum
directions lower HELD-OUT loss under our optimizer, precision, batch and parametrisation? "The bulk is noise at batch 16" is
a hypothesis, not a conclusion. No new optimizer is justified before P1-P3 have read out.

**Audit: loss reduction and effective batch** (code read, 2026-10-17):
| Trainer | Loss reduction | Batch per optimizer step | Halves for N |
|---|---|---|---|
| LatCH `train_latch.py` | masked mean over all valid frames x channels of the whole batch (frame-weighted; `--voiced-field` adds a per-frame weight), divided by `--grad-accum` | `--batch-size` (16) x `--grad-accum` (1) | the micro-batch split 8 + 8, each half its own masked mean |
| FiLM `control/sa3_control/train.py` | plain MSE mean over all elements (+ optional CC / fingerprint terms), divided by `--grad-accum` | `--batch` (1) x `--grad-accum` (2) = 2 crops | the two micro-batches (1 crop each; accum 4 gives 2 + 2) |
| DoRA `train_lora_modular.py` | Lightning: masked, normalised MSE (diffusion.py `compute_normalized_mse`, per-sample mask) + subspace/aux terms | `--batch_size` (8 default; recipes 32) x `--accumulate_grad_batches` (1) | not wired (N is LatCH/FiLM only) |

**Routing found in the LatCH head while building the probe (`build_modular_param_groups` on LatCH, d64 test model):**
- `blocks.N.adaLN_mod.1.weight` does NOT match the AdaLN regex (`modulation | global_cond_embedder.2 | scale_shift_table`), so the
  heads' AdaLN emitters go to the SPECTRAL group whole: not split into shift/scale/gate blocks and not sign, which is what the
  routing docstring says AdaLN emitters should get. Effect on results unknown.
- `t_embedder.mlp.0/2.weight` match the embedding regex (`embed`) and go to COLNORM, i.e. the time-embedding MLP is treated
  like an embedding table.
- `blocks.N.attn.qkv.weight` is NOT split into Q/K/V blocks: the split regex looks for `.to_qkv.` / `.to_kv.` / `.to_q.`
  (DiT naming), the head says `attn.qkv`. So Q, K and V are orthogonalised as one matrix. (Verified at d256 depth 2:
  spectral = latent_proj, qkv, proj, mlp.0, mlp.2, adaLN_mod, all with blocks = 1; colnorm = t_embedder.mlp.*; sign =
  norm_final, out_proj and the 1-D tensors.)
- `blocks.N.mlp.2.weight` (d x 4d) is WIDE, so our row_unit NorMuon steps it 2x dion's (F23); "heads are mostly square/tall"
  (section C) is corrected: the MLP down-projections are wide.
Decide whether to fix the regex (a routing change = new arms, not a silent default change).

**Tools (built, CPU-tested; nothing run on real data):**
- P1 `stable-audio-3/scripts/latch/spectral_probe.py` (tests: `tests/test_latch_spectral_probe.py`). Per checkpoint: probes =
  single ranks 1..32, bands r1 / r2-4 / r5-16 / r17-32, the full polar direction, and `beyond_32` (residual bulk, labelled);
  each matrix contributes -s_j u_i v_i^T with s_j = max(1, sqrt(d_out/d_in)) so alpha = 1 is the step the optimizer takes at
  this lr. Held-out loss on alpha in {0, .25, .5, 1, 2, 4, 8, 16, 32} x lr, the diffusion time and noise FIXED per batch,
  `--repeats` independent evaluation sets (other batches, other draws); plus SAMuon's local-quadratic estimate.
  `--point y` (PRIMARY): the gradient point (1 - sf_beta) z + sf_beta x and the run's own momentum, from a checkpoint written
  with `train_latch --save-opt-state` (new). `--point x`: the Schedule-Free average, read separately. `--point saved`: weights
  as saved (EMA or x) and the momentum REBUILT from a third group C of training batches (disjoint from A, B and held-out).
  Held-out = the checkpoint's own `val_split` (refuses to run without one unless given explicitly). Nothing is mutated
  (functional calls); alpha = 0 must reproduce the reference loss and the module is checked unchanged at the end.
- P2 direction-resolved agreement (`modular_opt.direction_agreement`, called by P1): gradients from two independent training
  groups A, B projected on the FIXED momentum basis; per band the cosine of the band blocks (invariant to rotations inside a
  band, so near-degenerate singular vectors need no identification; unstable band edges are flagged), each band's energy share,
  the fraction of ranks whose coefficient agrees with the momentum's descent direction in both groups (SAMuon appendix I), and
  the residual outside the top k.
- P3 pre-polar momentum spectra: `train_latch --log-mom-spectra N` -> mom_spectra.jsonl (top-32 normalised singular values,
  stable rank, top-1 energy per matrix; reading only). The update's own spectrum is flat by construction (up to NorMuon's row
  scaling) and only verifies the implementation.
- P4 `eval/adapter_spectrum_audit.py` (tests: `eval/tests/test_adapter_spectrum_audit.py`): stable rank, Frobenius/nuclear,
  spectral entropy, condition of each adapter CHANGE (LoRA/DoRA: B @ A; FiLM: W - W_init with `--init`). Run on the shipped
  FiLM, the E12 modular FiLMs, DoRA runs; set against the CLAP drift already measured in E7-E11. Shape, not size.
- Speed (section T, add as T5/T6): `--mod-ns-batch` (FiLM, LatCH; `--modular-ns-batch` DoRA) runs the Newton-Schulz of all
  same-shape matrices (and same-shape QKV/AdaLN blocks) as one batched call. Equal to the per-matrix result up to
  floating-point reassociation (tests: 7 configurations + bf16/fp32-state, rtol 1e-5); off by default; speed unmeasured
  (needs the GPU). T5 = T4 + `--mod-ns-batch`.

**Runs (training interventions, need Kim's go; after P1-P3 read out):**
| Arm | What | Flags (E05 recipe +) | Why |
|---|---|---|---|
| B7 | NorMuon off, nothing else changed | `--no-mod-normuon` | the missing isolated ablation; note the routing radius becomes live with NorMuon off (F22) |
| B8 | SAMuon-lite (head held, bulk x gamma) | not built; build only if P1 shows the bulk tolerating > 1x at batch 16 | discriminates "head at the edge of stability" from "the fast sign group" (F24) for the lr ceiling |
| P0 | one anchor re-run with `--save-opt-state --log-mom-spectra 200 --log-grad-noise 50` | E05 recipe | produces the checkpoints P1 `--point y` needs |

Reading rule for P1: per probe, best alpha from the grid on each repeat; a band "tolerates more" only if best alpha > 1 on
every repeat AND the held-out loss at that alpha is below alpha = 1 by more than the repeat-to-repeat spread. Where no metric
tracks the factor of interest (detune: log-mel is blind to it, V5 ladder gate), the verdict comes from controlled examples
and listening, never from spectral rank.

## Order and gates

T0 + C1-C7 (KUANG, CPU) -> T (throughput, ~20 min GPU; + T5 ns-batch) -> A -> P0 (anchor with optimizer state) -> P1-P4
(read-only) -> B (N logs on during A and B; B7 NorMuon-off; B8 only if P1 says so) (in parallel with E if VRAM allows: E is
inference only) -> C -> D.
Kim approves each launch. B overlaps the unlaunched Phase F (EXPERIMENTS E5: "not authorised to launch"), so B needs
Kim's explicit go as well.
