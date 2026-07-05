# Spec: human-first eval tables with dual-checkpoint comparison

*2026-07-06, WINTERMUTE from Kim's design (Kim: "the whole eval thing, which I should be
doing, has been needlessly unintuitive for me — we need a system a human can access and
read"). For GHOST-NOTE to implement. Reviewer gate: Kim eyeballs this before the build.*

## 1. Intent — reclaim the eval for the human

The eval review is **Kim's** job — the **listening test is the final word** on a training
outcome. The current presentation makes that job hard:
- the main page lives in a **hidden cache** (`~/.cache/evals_aac`), not a place a human finds;
- pages are **opaque** (e.g. `renders_dora` shows cryptic filenames — no checkpoints, no
  prompt texts, no params);
- **comparing checkpoints means endless scrolling** up and down, especially on big sweeps.

Goal: a **human-first, readable, sortable** eval system Kim can actually use, where the numbers
help him decide *what to listen to* and the ear makes the call.

## 2. What was good before + what to add (Kim's design)

- **Keep:** square **tables**, each **column sortable like Excel** by feature.
- **The pain:** comparing different checkpoints = too much scrolling.
- **The fix (Kim's):** **two tables** — side by side on desktop, **stacked in a column on phone** —
  each with a **checkpoint dropdown**, **synchronized sort** (reordering one reorders the other so
  rows stay aligned), and **per-feature min→max colour grading**.

## 3. Accessibility — kill the hidden-cache problem

- **Canonical human entry point = the served site** `https://aavepyora.online/files/evals/`
  (already public + accessible — this is the URL to bookmark; state it on the landing).
- **Local browsing must not require a hidden path.** Build/mirror the site into a **non-hidden
  location** (e.g. a `~/evals` symlink → the mirror, or output to a project dir) so `file://`
  works without spelunking `.cache`. `build_evals.py`'s `OUT` currently == the AAC staging cache;
  add a stable non-hidden mirror alongside.
- Landing lists **every** eval, described: date · what was tested · checkpoints · why.

## 4. Data layer — reuse `eval_grid.py`

`eval_grid.py` already merges `onset_eval.json` ⋈ `pq_scores.json` into per-clip records:
`prompt_idx, prompt(text), seed, gain, density, measured, error_delta, flatness,
spectral_balance, CE, CU, PC, PQ, broke, clip_path`. Reuse it; **generalize** it to carry an
explicit **`checkpoint`** key and to parse the two structured eval families:
- **control grids** (`composed_sweep/*`): checkpoint = the trained control head; varying params =
  gain × density × prompt × seed.
- **DoRA auditions** (`renders_dora`): checkpoint = **run + epoch/step**; varying params =
  prompt × seed. Parse `<runid>_epoch<N>-step<M>__p<pi>_seed<seed>.m4a`; map `runid`→run name
  (e.g. `2ankrkoh`→`sa3-goa-dora-47s`, `vjnnndnu`→`-b4`, `x20b3ygb`→`-b4-cont`); prompt text from
  the render script's `PROMPTS` list (`Misc/build_dora_audition_page.py` already has it). Audiobox
  metrics from `pq_scores.json` (score the dir if missing, per the eval-grid spec).

## 5. The table view (core)

- **Rows** = the varying param-combos for the shown checkpoint (control: gain×density×prompt×seed;
  DoRA: prompt×seed).
- **Columns** = params (prompt / gain / density / seed / epoch) **+** measured features (measured
  onset, error-delta, flatness, spectral-balance) **+** Audiobox (CE, CU, PC, PQ).
- **Every column sortable** — click header toggles asc/desc, Excel-style. Sort is stable.
- **Per-feature colour grading**, gradient **min→max over the realized range of the currently-shown
  checkpoint** (each table self-normalizes). **Deliberately NOT comparable across checkpoints** —
  Kim's explicit call: the point is to *gauge the distribution inside the realized range at a
  glance*; the ear is the final arbiter, so absolute cross-checkpoint colour equivalence isn't worth
  the loss of within-range contrast. (Param columns like gain/density are un-graded or lightly so.)
- **Cells/rows playable**, **same-playhead** (switch keeps position, re-click stops) — listening is
  the final word, so play must be one click from the table.
- Checkpoint **provenance** in an info box (run · config · prompt legend), redacted per SPEC §4.

## 6. Dual-checkpoint comparison (the hard part — Kim's solution)

- **Two tables**: side by side on desktop; **stacked (one above the other) on phone** (responsive
  breakpoint — Kim evaluates mostly on desktop, but phone must degrade to a vertical stack).
- **Each table has its own checkpoint dropdown** — selects which checkpoint's values it shows; the
  dropdown lists every checkpoint in the eval (epochs / variants / heads). Default: table A = first,
  table B = a sensible second (e.g. last epoch, or best).
- **Shared row set + synchronized sort:** the rows are the **same param-combos** in both tables, in
  the **same order**. Sorting **either** table (by any column, its own values) **reorders both
  identically**, so **row N in both tables is the same combo** → read straight across to compare
  checkpoint-A vs checkpoint-B for that combo. (The header you click drives the order; the other
  table mirrors it.)
- **Playback shared** across both panes (one global playhead).

This is the whole point: swap checkpoints via dropdowns, keep the layout fixed and aligned, and the
scrolling-to-compare problem disappears.

## 7. Relationship to the existing grid view

- The **gain×density grid** GHOST just built stays for the control-response *surface* (it shows the
  gain→density shape a table flattens). The **table+compare** view is the new **human-review default**
  for sortable multi-feature inspection and checkpoint comparison.
- Provide a **view toggle** (grid ⇆ table) where both apply (control grids); **table-only** where the
  grid doesn't fit (DoRA auditions, plain renders). Share the data layer + same-playhead JS; add a
  table renderer + the dual-pane compare harness. No third divergent copy.

## 8. Immediate test case — `renders_dora`

3 DoRA checkpoints (`2ankrkoh`=sa3-goa-dora-47s, `vjnnndnu`=-b4, `x20b3ygb`=-b4-cont) × 3 prompts
(`aggressive upbeat goa trance` / `energetic acid techno, 130 BPM, analog bassline` /
`psytrance, 140 bpm`) × epochs × seed 1234. Currently opaque. Validate the design here first: a
table with a **checkpoint dropdown (run+epoch)**, prompt texts shown, columns = prompt/epoch +
CE/CU/PC/PQ (+ any measured features), sortable, colour-graded, dual-pane to compare two epochs/variants.

## 9. Acceptance criteria

1. A human opens the eval landing from a **memorable URL** (not a hidden cache path) and can read what
   each eval is (date · checkpoints · prompts · purpose).
2. Each eval page shows a **sortable feature table**; every column sorts asc/desc; each feature column
   is **colour-graded min→max within the shown checkpoint's realized range**.
3. **Two tables**, side by side (desktop) / stacked (phone), **each with a checkpoint dropdown**;
   sorting one **syncs the other's row order**; cells **playable same-playhead**.
4. `renders_dora` renders legibly — 3 checkpoints + prompt texts, comparable via the dropdowns.
5. Provenance visible; public pages redact plumbing per SPEC §4.

## 10. Build order (suggested)

1. Generalize `eval_grid.py`'s record with a `checkpoint` key + add DoRA-audition parsing (runid→run,
   epoch/step, prompt text). Score `renders_dora` with `pq_score.py` (audiobox) if unscored.
2. **Table renderer** — sortable columns, per-column min→max colour, same-playhead rows.
3. **Dual-pane compare harness** — two tables, per-pane checkpoint dropdown, synced sort, shared
   playhead; desktop side-by-side / phone stacked.
4. Wire `build_evals` routing: multi-checkpoint dirs (sweeps, DoRA auditions) → table+compare; single
   grids keep grid (+ the toggle where both apply).
5. **Accessibility**: non-hidden local mirror + the canonical URL on the landing.
6. Validate `renders_dora`, then the `composed_sweep` grids; WINTERMUTE leak-scans + transfers.

## 11. Open items for Kim's review

- **Grid vs table default per eval type** — I've made table the human-review default and kept grid for
  the control surface (toggle where both apply). Confirm that split, or make table the only view.
- **Row identity when a combo exists in one checkpoint but not the other** (ragged sweeps) — proposal:
  show the row in both, blank the missing side; keep alignment. Confirm.
- **Which pane drives sort** when both are visible — proposal: whichever header was last clicked.
