# Chroma-384 steering — eval design + 12-TET UX layer (WINTERMUTE, 2026-07-16)

*(Kim direct 2026-07-16: "did we have a2a clips steered with our 384dim LATCH/FILM? If not,
we should. Also we should run some evals on the 384-dim steering in general … not sure what's
a good shape for the control signal … fold bass/melody pitches to 12-tet, because 12 vs 384
parameters is manageable for an UX.")*

## 1. Inventory (verified against code + run_meta, 2026-07-16)

**Exists:**
- **Trained head:** `latch_weights_sa3_medium/latch_sa3_same_chroma_best.pt` — per-frame
  (384, T) prediction, cosine loss (chroma = direction; not standardized). 384 = SAME-format
  octave-band chroma, 3 register bands (bass ~55 Hz / mid ~880 Hz / treble ~14 kHz) × 128 bins,
  semitone = 128/12 ≈ 10.667 bins, **C at bin 2.0, not 0** (producer:
  `mir-same-chroma/src/harmonic/same_chroma.py`, faithful port of SAME's training targets).
- **a2a clips steered with it: YES** — `chroma_morph_transitions` + `chroma_morph_barsnap`
  (76 clips): bungee beatmatch + latent-slerp crossfade + graded a2a refine with the head
  morphing A-chroma→B-chroma. Kim verdict on record (run_meta findings): the w1024_nl42 clip
  — "one of the coolest things I've heard in my nearly 30 years of music."
- **12-TET math, both directions:** `fold_to_12()` (384→12/band) and
  `expand_semitone_weights()` (12→128/band, pitfall-correct). **Round-trip validated
  2026-07-16 on real audio: expand→fold cosine 0.9993; E/G/B peaks land on expected bins
  45/77/119.** Zero new math needed.
- **Prototype palette:** `build_chroma_prototypes.py` — spherical k-means over root-normalized
  corpus profiles → "bass flavors" × "melody colors", re-rotated to any root at selection
  (fractional roll). A ready-made human-facing layer above the 12 knobs.
- **Render path:** `eval/explorer_render_server.py` already registers the `chroma_other` head
  + gain, a2a chroma slot, `chroma_rung1/2` loss types; `eval/chroma_morph_transitions.py`
  carries the morph/target machinery.

**Missing (the actual work):**
1. Systematic **control-response eval** (the onset_eval analog for a 384-d signal).
2. **12-TET targets wired** into steering + the explorer UI (the brief's "80 expert knobs"
   worry, line 99 — answered by 12 knobs / palette-pick + root).
3. **FiLM/adapter leg untrained** (`chroma384` control feature is spec'd in
   `sa3_control/{dataset,conditioner,train}.py` incl. the pitch-circular chroma-aware
   encoder, but no adapter run exists).

## 2. The control-signal SHAPE question → test it as an axis

The open design question is what a user/system supplies as the target. Make it the eval's
primary axis — five target types, same seeds:

| T | target | built via | tests |
|---|---|---|---|
| T1 | **reference-clip chroma** (time-varying (384,T) from a real clip) | `_reference_chroma` / cmt machinery | positive control — the shipped morph mechanism |
| T2 | **static 12-TET profile** (key/chord, e.g. Em triad or full minor-scale profile), expanded → 384, broadcast over T | `expand_semitone_weights` per band (bass+mid; treble zero-weighted) | the minimal UX: 12 knobs |
| T3 | **palette prototype** (root × bass-flavor × melody-color) | `build_chroma_prototypes` output | the intended product UX |
| T4 | **12-TET progression** (2–4 chords stepped over the window, ~1 bar smoothing) | expand per segment | time-varying control from 12-d UX |
| T5 | **null/mismatch controls**: (a) gain 0 baseline, (b) WRONG-key profile | — | specificity: does the metric move only when it should |

Contexts: **a2a continuation** (Kim's ask; source anchor supplies competing harmony — the hard
case) and **t2a** (isolates raw authority). Gain ladder around the shipped default
(`cmt.CHROMA_GAIN` ×{0.25, 0.5, 1, 2, 4}).

## 3. Metrics (independent extractors; the chroma-trap correction)

The known trap (memory `sa3-riffer-findings`): absolute chroma similarity is meaningless on
tonal music — everything correlates. **All primary metrics are Δ-vs-baseline (same seed,
gain 0):**

- **Target movement (primary):** Δcos12 = cos(fold_to_12(SAME-chroma(out)), target12) −
  same for the gain-0 baseline. Per band (bass, mid). Positive = steering moved output
  toward the target relative to what the prompt/anchor alone produces.
- **Cross-extractor check:** the same Δ computed with essentia HPCP (mir venv) — guards
  against "the SAME-chroma extractor agrees with the SAME-chroma head" circularity.
- **Key/mode check (T2–T4):** essentia KeyExtractor on output — detected root/mode vs
  requested (fraction correct across seeds).
- **Specificity (T5):** wrong-key target must move the metric toward the WRONG key or
  nowhere; gain-0 Δ ≡ 0 by construction.
- **Disentanglement co-scores:** BPM (tempo shortcut), onset density, Audiobox CE/PQ —
  chroma steering must not ride tempo/density/quality.
- **Ears:** shortlist (best/worst per target type) → listening page (write-only notes).

Per-gain correlation of Δcos12 vs gain = the control-authority number (onset_eval
convention), per target type. **The deliverable table: authority × target-type** — answers
"what's a good shape" with data.

## 4. Grid + cost

- **Pilot (1 GPU-evening):** a2a only, T1/T2/T3 × gains {0.5, 1, 2} × 3 seeds ≈ 27 renders
  + 9 baselines (gain 0, per seed × target-context) ≈ 36 clips à ~24 s. Metrics CPU.
- **Full (1 night):** all five T × 5 gains × 3 seeds × {a2a, t2a} ≈ 150 + baselines.
- Output dir `Mantu/sa3_control_runs/chroma384_eval_<date>/` with MANIFEST-v2 `run_meta.json`
  (hypothesis: "384-d chroma steering has usable authority from 12-d folded targets, not
  only from reference clips; bass and mid bands steer independently").
- Harness: `eval/chroma384_eval.py` — target-builder (the five types) + render loop reusing
  `chroma_morph_transitions.py` machinery + scorer. Renders via the same LatCH-guidance
  path as the morph renders (server optional).

## 5. 12-TET UX layer (wiring plan)

- `harmonic/chroma12.py` thin wrapper (fold/expand/progression-builder + palette loader) so
  the explorer and eval share one target-builder.
- Explorer a2a/inference tabs: a "harmonic target" mode switch — **reference clip** (today's
  morph) | **12-TET knobs** (12 toggles/weights + root + band selector bass/melody) |
  **palette** (root + flavor + color dropdowns). Payload stays the existing steering JSON
  (the server already takes chroma targets). → G/W lane after the pilot validates T2/T3
  authority; don't build UI for a control shape that fails the eval.
- 12 knobs is the *interchange format*: palette and progressions both compile to it; it
  compiles to 384 via the validated expand.

## 6. FiLM/adapter-384 leg (pool, not now)

The chroma-aware conditioner + `chroma384` control feature are spec'd but untrained: needs
(a) `gen_same_chroma_ts.py` corpus pass packed for the control dataset, (b) an adapter
training run (local nights or LUMI). Value: CFG-riding harmonic control without per-step
guidance cost (the onset-adapter pattern), composable with the LatCH head. Schedule after
the E-series GPU pressure clears and only if the eval shows the head's authority is worth
productizing. FiLM answer to Kim's Q1: no FiLM-384 renders exist — only LatCH-guided ones.

## 7. Schedule (around the longform E-series; LUMI untouched)

- **Thu 16 (today):** this spec; corpus-bands running (also feeds T5 null design); harness
  target-builder + scorer (CPU) — evening. E1 pre-test still owns tonight's card slot.
- **Fri 17:** finish harness; **pilot grid Friday night** after/alongside E1 main grid
  (36 clips ≈ short). Metrics + authority table Sat morning.
- **Sat–Sun:** full grid if pilot shows authority; shortlist → listening page.
- Explorer UI wiring + adapter leg: gated on pilot results.
