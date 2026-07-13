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

## 12. Layout + provenance requirements (Kim, 2026-07-07)

- **Use the full viewport width for table/compare views.** The reading-column `.wrap`
  (max-width 900 px) is for prose; the **dual-pane compare and sortable tables must NOT be
  confined to it** — on a wide monitor (e.g. 2560 px) two panes crammed into 900 px are
  unreadable. The compare container (`.tc-wrap`) breaks out full-bleed to `min(2200px,94vw)`,
  centered (implemented 2026-07-07 in `eval_grid.TABLE_CSS`). Any future table view inherits
  this — do not re-confine the tables to the prose column.
- **Selecting a checkpoint MUST display its training parameters.** The per-pane checkpoint
  dropdown, on selection, shows that checkpoint's **training hyperparameters** (lr, epochs/steps,
  optimizer, batch size, LoRA/DoRA rank, crop length, scalar_field if any) in the provenance
  box — sourced from the run's training `args` (`run_meta.json` / training-args sidecar),
  **redacted per §4**: hyperparameters and config are open (that IS the science being compared);
  checkpoint FILENAMES and absolute PATHS stay off. This is the whole point of a checkpoint
  comparison — the human is choosing *between training recipes*, so the recipe must be visible
  next to the audio, not just an opaque arm label.

## 13. Waveform popup player for long clips (Kim, 2026-07-07)

- **Requirement**: any clip **longer than 20 s** gets, next to its normal cell button, a small
  waveform-player affordance (`〰` icon button). Clicking it opens a **popup (modal overlay)
  player**: rendered waveform of the clip with a moving playhead, where **clicking/tapping a
  position on the waveform seeks directly to it**. Purpose: long-form and a2a/transition clips
  (2–8 min) where "jump to the relevant place" is the whole review action.
- **Popup, not inline**: grids stay dense; the modal is a single shared element per page,
  repopulated per clip. Dismiss = ✕ button / click-outside / Esc. Audio keeps playing through
  the SAME `<audio>` element the cell uses, so the **same-playhead convention (§ MASTER) is
  preserved** — opening the popup neither restarts nor forks playback; closing it doesn't stop it.
- **Waveform source**: client-side, lazy — on first open per clip, `fetch` the m4a →
  `AudioContext.decodeAudioData` → compute ~1000–2000 min/max peak pairs → draw to `<canvas>`
  → cache peaks per URL for the session. No build-time sidecars (the deploy excludes `*.json`,
  and precomputing would couple the transcode step to the UI). Show a "decoding…" shimmer while
  computing; on decode failure (old Safari/AAC quirk) fall back to a seekable progress bar —
  the popup must still seek even without the picture.
- **Layout**: desktop (the 2K main case) — modal ~`min(1400px, 90vw)` wide, waveform ~160 px
  tall, time ruler beneath, clip label + provenance line above. Phone — full-width modal,
  waveform ~96 px, touch `pointerdown` seeks; buttons ≥44 px tap targets. Keyboard: Space
  play/pause, ←/→ ±5 s, Esc close.
- **Threshold detection**: client-side from `audio.duration` on `loadedmetadata` (≥20 s shows
  the button) — no generator-side duration bookkeeping needed, works for every page including
  already-built ones once the shared JS ships.
- **Where**: shared JS/CSS in `build_evals.py` (all its pages inherit); the riffer-evals
  curated generators (`~/build_*.py`) adopt the same snippet as follow-up.

## 14. Every page = three audiences at once (Kim, 2026-07-10)

Design principle for ALL eval pages (curated + generated). Each page must simultaneously be:

1. **An eval TOOL for Kim** — the listening/decision surface: same-playhead players, sortable
   colour-graded tables, the audio one click from the numbers. (Largely exists.)
2. **A technical RESOURCE for engineers & other trainers** — full reproducibility: explicit
   prompts (not just p-keys), training hyperparameters, recipe line, `file://`+web links to the
   training/generation scripts, exact method + metrics defined. (G has been building this out —
   prompt legends, recipe lines, param-on-select, script links; keep extending.)
3. **A learning RESOURCE for medium-level SA3 users** — a plain-language explainer layer:
   WHAT this eval tests, WHY it matters, the CONCEPT behind it, and HOW to read the result
   (what a high/low value or a given verdict means). Current pages state findings *for insiders*;
   this asks for a short pedagogical "what this is / what it teaches" block so someone with
   moderate SA3 experience learns from the page, not just the fleet.

**Gap:** #3 (pedagogical layer) is the newest/weakest. Concretely: each page (or the landing's
category headers) gets a 2-4 sentence plain-language explainer of the concept + how to read it,
sitting above the tool. Applies to the landing categorisation too — each category header carries
a one-line "what this family of evals is for."

## §15 — Aggregation pages rank HIGH on the landing; dropdowns ordered by Kim's preference then date (Kim, 2026-07-12)

Kim, looking at `control_runs/_onset_control_audit/`: **"these should be higher up on the
landing page, maybe on top of their respective section instead of all the way down the site,
because they collect a lot of work."**

1. **Landing placement rule:** aggregation/audit pages (`_onset_control_audit`,
   `_misc_uncurated_runs` TOC, and any future "collects many runs" page) sit at the **TOP of
   their respective landing section**, not in bottom/alphabetical position. Rationale: a page
   that aggregates dozens of runs outranks any single run's page. (Generalizes the existing
   hero-block precedent: high-work-density surfaces float up.)
2. **Dropdown ordering rule:** checkpoint/model dropdowns on aggregation pages are ordered by
   **Kim's preference first, then date** — NOT alphabetically. Preference source of truth for
   the onset pile = the narrative verdict ranking (`docs/onset-density-control-narrative.md`
   §3): `onset_Fusion_lr1e-4_randomcrop` (07-07 ear-verdict) → `onset_FUSION_lr2e5_40epoch`
   ("favourite by ear" claim) → `onset_FusionCC_lr1e-4_randomcrop` (metric winner) → rest by
   date, newest first. Where no verdict exists for a pile, date-descending is the fallback;
   when future ear-verdicts land, they update the ordering (the narrative/HoF docs are the
   preference registry, don't hardcode lists in page JS).

## §16 — Red-exclamation unaudited marker + manifest v2 (Kim, 2026-07-12)

Every eval a page presents is either **audited** (Kim's feedback exists in its manifest's
`kim_feedback` field, verbatim + dated) or **unaudited** — and unaudited evals carry a visible
**red exclamation mark (❗)** next to their entry/section on every page (landing rows, audit
dropdowns, grid headers). Kim: "as long as an eval is uncommented by me, it's accompanied by a
red exclamation mark on the webpage. There's so much stuff that I'm probably missing some."
The mark is DERIVED from the manifest at build time — never hand-toggled. Recording Kim's
verdict into the sidecar (which MANIFEST v2 in MASTER §4 now requires anyway) is what clears
it. Manifest v2 additions builders should surface: hypothesis/motivation, `result` (auto
metrics), training recipe + dataset info (#files) for model renders.

### §16a — Comment granularity (Kim DIRECT, 2026-07-13, via CONTINUITY)

Site comments (the `/files/comment.php` + `comments.js` loop, W 2026-07-13; merge side
`Misc/merge_comments.py`, G) must attach at **three granularities** beyond the existing
per-page global: **per TRACK/clip**, **per CHECKPOINT**, and **per MODEL**. Each level
lands in the matching manifest scope on the nightly merge:

- **clip comment** → that cell's entry (per-clip scope in the run's manifest/sidecar);
- **checkpoint comment** → that ckpt's `run_meta.json` `kim_feedback`;
- **model comment** → the run-level manifest.

The **❗ clears at the matching level ONLY** — a model-level comment does not clear
per-clip marks (and vice versa). Endpoint side (W): the comment record carries an explicit
scope key (`page`, `model`, `ckpt`, `cell-id`, ip). Merge side (G): route by scope, never
by parsing free text. Attribution rule (G, 2026-07-13, standing): only unnamed or
Kim-named comments enter `kim_feedback`/clear the ❗; fleet-handle or third-party comments
merge into a separate `site_comments` field at the same scope.
