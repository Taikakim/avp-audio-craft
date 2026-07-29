# LR × Epoch × Weight equivalence grid — design spec

**DRAFT (2026-07-30, WINTERMUTE, for Kim's review).** Turns Kim's "are the three
assertion knobs interchangeable, and is there a fewest-steps × largest-weight sweet
spot?" question into a concrete LUMI experiment. Spawned from the goa AdamW LR-sweep
listening + the cheap weight-space check below.

## Motivation

Three knobs all raise "how much the adapter asserts": **inference weight** (LoRA
strength, post-hoc), **learning rate**, and **training steps**. Kim's hypothesis: they
trade off along a "cumulative learning" axis (LR × steps), and weight — being free —
might let us hit the quality sweet spot with the fewest training steps.

## Cheap weight-space check (DONE 2026-07-30) — reframes the experiment

Three goa AdamW DoRA arms, **identical 13500 steps**, differ only in LR
(`ckpt_dir_check.py`; dW = lora_B @ lora_A per layer, 229 adapted layers):

| LR | ‖dW‖ | ratio vs 5e-5 |
|---|---|---|
| 5e-5 | 55.5 | 1.00 |
| 1e-4 | 105.1 | 1.89 |
| 2e-4 | 234.0 | 4.22 |

- **Magnitude channel: the invariant HOLDS.** ‖dW‖ scales ~linearly with LR (1 : 1.89 :
  4.22 ≈ the 1 : 2 : 4 LR ratio; the slight super-linearity at 2e-4 is its over-assertion).
  Because AdamW normalizes the gradient, per-step displacement ≈ LR, so **LR × steps =
  cumulative displacement** — 2× LR ≈ 2× steps in magnitude. Confirmed in parameter space.
- **Direction channel: the arms RE-POINT.** cross-LR direction cosine =
  0.47 (5e-5↔1e-4), 0.22 (1e-4↔2e-4), 0.17 (5e-5↔2e-4) — far from 1.0. Different LRs learn
  **different directions**, not a shared direction at different scale.

**Consequence (the reframing):** inference weight ↔ LR×steps are interchangeable **only on
the MAGNITUDE (assertion) axis, NOT the DIRECTION (flavor) axis.** Weight scales a *frozen*
direction; each LR trains a *different* direction. This is exactly Kim's "twice the weight
is kind of, but not quite, twice the LR" — same assertion level, different flavor — and it
predicts that matched-cumulative-LR points sound **equally asserted but timbrally
different**. (Low param-cosine ≠ low output-similarity — the shared frozen base keeps
content the same; the direction difference shows up as the subtle bass/kick/damping timbre
Kim heard.)

**The one quantity that sets the efficiency frontier is still unmeasured:** how fast the
**direction stabilizes with steps** — cos(dW@ep_k, dW@ep_final). Once the direction matures,
weight can carry the remaining magnitude → the fewest-steps sweet spot. The current sweep
saved **only ep9**, so this needs a run that saves intermediate checkpoints. That is the
core new requirement of this grid.

## Experiment

**Fixed:** goa corpus (the clean large one), DoRA r128, AdamW, bf16, T512, cfg7, the 18
board prompts+seeds.

**LR × epoch arms — matched cumulative-LR endpoints + trajectory:**

| arm | train to | cumulative (LR×ep) | note |
|---|---|---|---|
| 2e-4 | ep10 | 2e-3 | (also run to ep14 to see over-train/collapse) |
| 1e-4 | ep20 | 2e-3 | |
| 5e-5 | ep40 | 2e-3 | dominant cost |

**Save a checkpoint every ~4 epochs** (the trajectory — this is the change from the current
sweep). Each arm reaches the same cumulative endpoint, so a matched-cumulative comparison is
possible AND the per-epoch direction-maturity curve is recoverable.

**Inference render:** each saved checkpoint × weight {1.0, 1.5, 2.0, 3.0} × 18 prompts,
cfg7, 20 s. (Native-length only for a handful of picked cells, on LUMI.)

**Analysis:**
- *Parameter-space (cheap, per checkpoint — extend `ckpt_dir_check.py`):* ‖dW‖;
  **direction-maturity** cos(dW@ep, dW@final) per LR; cross-LR direction cosine at matched
  cumulative points.
- *Perceptual:* MERT content-rank (nearest-neighbor only, never thresholded — its scale is
  compressed, 0.885 = noise-vs-music) + **crest** (the DSP meter that survived Kim's ear —
  tracks punch/clipping) + Audiobox ce/pq + Kim's ear on:
  - (a) matched-cumulative triples: 5e-5@ep40@w1 vs 1e-4@ep20@w1 vs 2e-4@ep10@w1 — do they
    sound equally asserted? equally *good*? same or different flavor?
  - (b) weight-for-steps substitution: 2e-4@ep5@w2 vs 2e-4@ep10@w1 — can weight buy back
    the missing steps?

**Hypotheses:**
- H1 — magnitude invariant (confirmed in param space; confirm perceptually via equal assertion).
- H2 — direction = LR-specific flavor (matched-cumulative → same assertion, different timbre).
- H3 — direction matures at some ep_k; past it, weight substitutes for further steps (read ep_k
  off the maturity curve).
- H4 — efficiency frontier: the (steps, weight) giving best ear-quality at minimum steps.

**Acceptance:** the per-LR direction-maturity curve; a labeled iso-assertion vs iso-flavor
map over (LR, epoch, weight); Kim's verdict on the (a)/(b) shortlists.

**Cost / logistics:** modest training (3 arms, ~70 epoch-equiv, 5e-5@ep40 dominant); render
≈ (≤5 ckpt × 3 LR) × 4 weights × 18 prompts × 20 s ≈ 4k clips — a LUMI render matrix. Ships
from the working tree. **MUST save intermediate checkpoints** (unlike the current sweep). Every
output dir carries a `run_meta.json` per the manifest-v2 rule. Overlaps the aug8/fp32 campaign
scaffolding (same train_lora + render_matrix_cells path) — coordinate with CONTINUITY (their
theory + LUMI-campaign lane).
