# Composed control: adapter × LatCH guidance sweep ("easier terrain")

**Status:** spec'd 2026-07-03 (Kim's ask); harness build in progress.
**Hypothesis (Kim):** weight-space control improvements (trained/evolved adapters)
and sample-space steering (LatCH guidance) should COMPOSE: the adapter reshapes the
terrain, guidance walks it — "the thing that helps move gets to move in easier
terrain." Measure whether guidance is more effective (more authority per unit
guidance gain, less quality damage) on top of better adapters.

## The canonical grid (now discretely spelled out — this section is the reference)

| Axis | Values |
|---|---|
| Prompts | the canonical three (goa / acid techno / psytrance — as in all prior evals) |
| Seeds | **2** (1234, 4242) |
| Adapter gains | **1, 2, 3** |
| Requested densities | **1, 3, 5, 6, 7, 7.5, 8, 9, 12** |
| Steps / CFG | 24 / 6.0 (CPU-canonical, matches all A/B evals since 2026-07-01) |
| Measurement | librosa onset density + spectral flatness (smear guard); audition page ships with every sweep |

= **162 cells per condition.**

## Condition matrix (6 conditions, staged)

Stage 1 — the core hypothesis (4 × 162 = 648 renders):
| | LatCH off | LatCH on (onset_envelope head) |
|---|---|---|
| baseline Fusion adapter | E (anchor) | F |
| **FusionCC adapter** | A | **B (the money cell)** |

Stage 2 — the ES/mapped variant (2 × 162 = 324 renders):
| FusionCaut + ES-v3-final conditioner | C | D |

Stretch (cheap, high-interest): the known-DEAD beat_activation head × {baseline,
FusionCC} on a mini-grid — does better terrain revive a dead walker?

## Guidance configuration

- Head: `latch_sa3_onset_envelope_best.pt` (constant target; target value mapped from
  requested density via the corpus envelope↔density regression, computed from
  TIMESERIES + json stats and frozen into the harness).
- Guidance strength: the head-family operating point (energy-family ~512 established;
  onset_envelope's point to be confirmed with a 1-cell probe before the sweep — do NOT
  assume 512 transfers).
- Guidance ON = two-stage Selective-TFG per `sa3_latch_onnx.py` conventions.

## Readouts (per condition)

1. corr(requested, measured) per gain — the authority table, as always.
2. **Composition gain**: authority(adapter+LatCH) − authority(adapter) vs
   authority(baseline+LatCH) − authority(baseline). Positive interaction = Kim's
   terrain hypothesis confirmed.
3. Band edges: does composition move the floor (<5) or the ceiling (>9.5) that
   neither method moved alone? (Densities 1 and 12 are in-grid for exactly this.)
4. Flatness (smear guard) + paired bootstrap on all deltas; audition page = verdict.

## Harness build required (CPU path, comparability with all prior evals)

`sa3_latch_onnx.generate_z0_latch_guided` currently drives a PLAIN DiT. Patch: accept
optional `cond_tok/zero_tok/gain` and run the CONTROL-DiT graph (token inputs already
exist in our exported fp16 graphs) inside the guided sampler. LatCH head stays
torch-autograd on the host as-is. Server/eval wiring reuses the existing queue +
cpu_onset_grid_eval pattern with a `--latch` mode.

## Budget

~50–70 s/render with guidance (head backprops per step) → Stage 1 ≈ 10–13 h CPU,
Stage 2 ≈ +5–6 h. Run staged, detached, kill-wave-proof, results ping per stage.
