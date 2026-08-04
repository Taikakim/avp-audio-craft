# Metrical-Tree Positional Encoding — design pass (E3/E5 of the reality-structured plan)

*THE-FINN, 2026-07-31. Companion design doc for E3 (metrical-position FiLM retrofit) + E5
(from-scratch tree-PE) of `2026-07-31-reality-structured-model-experiments.md`. Greenlit by
CONTINUITY to run in parallel with G2 (the phase probe) — position is orthogonal to phase.
Constraints baked (C): the tree signal is DATA WE ALREADY HAVE; retrofit-before-rebuild;
partial-coverage handling is a design decision (melody-sidecar precedent, 2649/5400).
Standing law (F's Q2, from the plan §0): every arm ships a matched-baseline + a used-structure
ablation.*

## 0. The hypothesis, sharpened
`#60`'s loop-collapse null left **long-range structure recall / prompt-arc** (motif return,
key relationships) as the surviving open problem, fixable so far only by *behavioral* patches
(breathing `#35`, interval-CFG). Mechanism (C-endorsed): **flat RoPE makes bar 17→18
positionally identical to bar 1→2** — phrase position is architecturally invisible, so the
model has no coordinate for "where in the form am I." A hierarchy-native positional signal
attacks the *architecture*; the patches only manage symptoms.

## 1. The representation — a 4-level metrical tree, per frame (data we already have)
Music's position is a tree: **subdivision → beat → bar → phrase**. We can derive a per-frame
path in that tree TODAY from existing sidecars (no new labeling):
- `{track}.DOWNBEATS` (whitespace-sep downbeat times, sec) → **bar boundaries** on our grid.
- `downbeat_activation_ts` / `beat_activation_ts` (the `dataset.py` "rhythm" feature group) →
  **beat + subdivision** positions per frame (10.77 Hz), beat-aware-cropped already.
- `musicology.json → structure.section_lens_bars` → **phrase/section grouping** (cumulative
  bars → phrase index; see `eval/section_boundary_validate.py` for the exact cum-sum reader).

**Per-frame features (4 indices):** `subdiv_in_beat` (0..S-1, S=4 default), `beat_in_bar`
(0..B-1, B from meter, default 4), `bar_in_phrase` (0..7, phrase=8 bars default), `phrase_idx`
(0..P-1, clamp/wrap at P=8). Emit each as a **HARD CLASS** — following the load-bearing lesson
from `prep_melody_conditioning.py`: *the conditioning INPUT is not a loss target, so hard
argmax classes are correct and soft boundary weights are wrong* (a generative conditioner
wants "you are here," not a probability). Optionally add a **cyclic (sin/cos) encoding per
level** for within-level continuity — test hard-class vs cyclic as a sub-arm.

## 2. Partial coverage / ragged edges (C's constraint — a design decision, not an afterthought)
Coverage is imperfect: tracks with missing/low-confidence `DOWNBEATS`, and **tempo drift where
bar length varies** (the grid stretches). The melody-sidecar precedent (2649/5400 covered)
says handle this explicitly. Decision:
- **Uncovered / low-confidence frames → zero-condition DROPOUT, not subset-training.** Feed a
  learned "no-metrical-info" null token (all-zero one-hots + a coverage-flag channel = 0) for
  uncovered frames, and additionally apply **classifier-free-style condition dropout** (p≈0.1–0.2)
  on covered frames during training. Rationale: (a) the model must generate when metrical
  position is unknown (inference on un-sidecarred prompts), so it must see the null; (b) dropout
  prevents the adapter from memorizing coverage as a shortcut; (c) it gives a free CFG knob at
  inference (push toward the metrical condition). Train-on-covered-subset is rejected — it
  biases the data distribution toward well-structured tracks (a confound with the very thing we
  measure) and can't generate un-sidecarred.
- **Tempo drift:** derive indices from the *actual* DOWNBEATS spacing per bar (variable), not a
  fixed frames-per-bar constant — the tree is defined by the grid, which already breathes.
- Emit a **per-frame coverage-confidence scalar** as an extra conditioning channel so the model
  can discount uncertain metrical info rather than trust it blindly.

## 3. E3 — the retrofit build (no new PE, no base retrain)
Directly mirror **Head B (melody FiLM)** — this is the same machinery with metrical features
swapped for melody features:
- **Injection:** the 4 hard-class streams (+ cyclic + coverage) → embedding → the EXISTING
  `sa3_control` FiLM conditioner (the `es_conditioner` / Head-B path). No RoPE touch, no base
  weights trained — adapter + FiLM only.
- **Recipe:** byte-match the shared baseline (`lreq_goa_lr1e4` / the Head-B bracket recipe);
  single-GCD small-g; ~adapter cost (the whole point — cheapest possible confirmation).
- **Baseline (collapse-test, mandatory):** an identical adapter with the metrical channels
  **shuffled/zeroed** (matched params, no real metrical info). Signal only counts as structure
  gain over THIS baseline, not over base.

## 4. Readouts (operationalized) + the used-structure ablation
- **Structure metrics:** lag-similarity matrices at **bar and phrase lags** (does self-similarity
  sharpen at 8-bar/phrase periods?); **contour-repetition** (the muscriptor hook axis); **a2a
  loop-attractor at nl.55+** — does the attractor SOFTEN when the model knows where in the phrase
  it is? (direct tie to the `#60` gap + `docs/a2a-loop-attractor.md`).
- **Quality guard:** board PQ/CLAP cells; disintegration gate on outputs (standing directive).
- **USED-STRUCTURE ablation (F's Q2, the anti-rename test):** at inference, ABLATE the metrical
  channel (feed the null) on a model trained WITH it, and measure the structure-metric delta.
  If structure collapses toward the no-condition baseline → the model genuinely uses metrical
  position (real). If ablation barely moves it → the adapter learned to ignore it and the gain
  (if any) came from elsewhere → honest null.

## 5. Kill criteria
- Board PQ drops > 0.3 vs baseline at ep20, OR disintegration-gate failures rise → kill.
- Structure metrics (bar/phrase self-similarity, contour-repetition) show **no** gain over the
  shuffled-metrical baseline at matched params → metrical position isn't the missing coordinate;
  honest null, do NOT escalate to E5.
- Ablation (§4) shows the channel is unused → the arm is a rename; kill.

## 6. E5 — from-scratch tree-PE design space (gated on E3 positive)
If E3 shows metrical position *as conditioning* helps, the clean test is a *positional-encoding*
that bakes the tree into the geometry. Small DiT (SAT / SAO-Small on goa latents), tree-PE vs
RoPE, matched params/steps/data. Encoding options (swept from the survey's Theme-G):
1. **RoPE with hierarchical frequency bands *(recommended first — it is the literal fix for the
   mechanism)*.** Partition RoPE's frequency bands across metrical levels: high-freq bands rotate
   with subdivision/beat, low-freq bands rotate once per bar/phrase. Bar 17→18 and bar 1→2 stop
   being identical because the phrase-frequency band has advanced. Minimal, drop-in, RoPE-shaped,
   and directly undoes "flat RoPE." (Cf. UltraViCo/LoL RoPE-frequency analysis — same knob, used
   constructively.)
2. **Sinusoidal-per-level PE** — concatenate a standard sinusoidal PE computed per tree level
   (position = 4-tuple); simplest baseline for the tree signal as absolute PE.
3. **Learned tree-PE / path embedding** — an embedding of the node-path (subdiv,beat,bar,phrase);
   most expressive, least inductive-bias.
4. **Hyperbolic path embedding** (Nickel–Kiela 1705.08039) — position = a point in hyperbolic
   space along the metrical path; geometry-native to trees (exponential room for hierarchy),
   the survey's Theme-G card. Higher-risk, highest fractal-fidelity.
5. **Scale-tied / RG-covariant** (Theme-G) — one relational positional rule reused across
   metrical scales (self-similar). The "organized like reality itself" purest form; test only if
   1–4 show the tree matters.
**Recommendation:** E5 tests **(1) hierarchical-band RoPE** as the deployable frontrunner and
**(4) hyperbolic** as the high-fidelity contrast, both vs plain RoPE — with the same
structure-recall readouts as E3. (1) is also the one that could later retrofit onto SA3 proper.

## 7. Sequencing + cost
- **E3 now-designed (this doc) → launch on Kim's go, adapter-cost, ~1 small-g arm + its
  shuffled baseline.** Pairs naturally with the running subloss grid / Head-B (all melody-wall).
- **E5 gated on E3 positive** — a small-model build (SAT harness), the clean falsifiable test of
  the whole fractal thesis.
- The decisive cheap confirmation is E3's retrofit: if metrical-position-as-conditioning moves
  structure metrics at mere adapter cost, the tree hypothesis is validated before anyone builds
  a new PE. That is the intended order.

## 8. What NOT to do
- Do **not** feed soft boundary probabilities as the conditioning input (hard classes — the
  `prep_melody_conditioning` lesson).
- Do **not** touch base RoPE or retrain the base in E3 (that's E5's job, and only if E3 earns it).
- Do **not** train-on-covered-subset (§2 — distribution confound).
- Do **not** escalate to E5 on a weak/ablation-unused E3 signal (the collapse test gates it).
