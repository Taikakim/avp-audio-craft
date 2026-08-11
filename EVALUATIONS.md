# EVALUATIONS — how the SA3 eval site is organized

*2026-07-06, GHOST-NOTE, per Kim's ask — a taxonomy of the eval TYPES we run and
which UI pattern each one gets, so future evals land in the right shape by
default instead of every new sweep reinventing (or degrading to) a flat clip
dump. Companion to the two implementation specs this builds on:
`docs/superpowers/specs/2026-07-05-eval-grid-rich-renderer.md` (the gain×density
grid) and `docs/superpowers/specs/2026-07-06-eval-tables-human-first.md` (the
sortable table + dual-checkpoint compare). Those describe HOW the renderers
work; this doc describes WHICH renderer a given eval should use and WHY.*

## 1. The core distinction: what varies, and along how many axes

Every eval we run is fundamentally "generate N clips varying some parameters,
score them, let Kim listen." The right UI follows from **what's varying**:

- **A genuine 2D parameter *surface*** (e.g. gain × density) where the *shape*
  of the response matters, not just the individual values → **grid**.
- **A checkpoint/variant axis** (different training runs, epochs, DoRA
  strengths, lengths — anything where the interesting comparison is
  "A vs B") → **sortable table**, and if there's more than one checkpoint worth
  comparing side-by-side → **dual-pane compare**.
- **Neither** (a one-off render, a demo, a handful of unstructured clips) →
  **flat clip grid** (the fallback; still same-playhead playable, just no
  sort/colour machinery because there's nothing structured to sort).

A single eval can combine axes (e.g. the DoRA weight×length sweep has BOTH a
checkpoint-like axis — strength × length — AND prompt/seed rows) — those still
route to **table**, since the checkpoint/variant axis is what you're
comparing, and rows carry the rest.

## 2. Eval families we actually run (as of 2026-07-06)

| Family | Varies | Checkpoint axis? | UI pattern | Data files |
|---|---|---|---|---|
| **Control-adapter response grid** (`composed_sweep/*`, `onset_eval.py` output) | gain × density × prompt × seed, ONE trained adapter per page | No (single run per page) | **Grid** (gain-grouped rows, density columns) + table toggle for the same data sorted/inspected differently | `onset_eval.json` + `pq_scores.json` |
| **Bracket / multihead bracket sweeps** | a scalar knob swept to find where quality degrades | No | Grid (same renderer, degenerate to 1 prompt) | `onset_eval.json` |
| **Onset-per-beat / disentanglement runs** | training epoch × prompt, tracking a control-vs-tempo-cheat metric over time | Epoch is a checkpoint-like axis | Table (epoch dropdown) — *not yet built as a generic table, currently a hand-curated page (`riffer/disentangle.html`)* | ad hoc |
| **DoRA/LoRA quality audition** (`renders_dora`) | checkpoint (run+epoch) × prompt × seed | Yes — many checkpoints | **Table + dual-pane compare** (built 2026-07-06) | `pq_scores.json` (DoRA-flavored rows) |
| **DoRA weight×length quality sweep** (e.g. `dora128_everything_8ep_lr1x_ep7_sweep`) | DoRA strength × generation length × prompt × seed, ONE checkpoint | Strength/length act as the "variant" axis | **Table + dual-pane compare** (strength or length as the thing each pane picks) — *not yet wired; currently a flat clip grid, see §4* | `_meta.json` sidecar only (no per-clip scores yet) |
| **Step-count / hyperparameter diagnostics** (e.g. `..._steps_diag`) | one knob (steps) × seed, small N, one-off | No | Flat clip grid (small enough to just listen through) | `_meta.json` sidecar |
| **Model-soup renders** (`renders_soups*`) | which checkpoints got averaged | Yes — each soup recipe is a variant | Table (candidate: soup recipe as the "checkpoint") — *not yet built, currently flat* | none structured yet |
| **Cross-prompt renders** (`renders_cross`) | text prompt, fixed control settings | No | Flat clip grid (small N, prompt text is the label) | none |
| **Flow-separation / zero-shot-separation renders** | η / guidance strength, source material | No (usually one setting explored per page) | Flat clip grid | none |
| **Weight-garden mutation renders** | mutation op × amount × seed | Each mutation recipe is a variant | Table (candidate) — *not yet built, currently flat* | `run_meta.json` sidecar |
| **LatCH head sweep** | head × gain, per checkpoint | Head is a checkpoint-like axis | Table (candidate) — *currently a hand-curated page (`riffer/latch_sweep.html`)* | ad hoc |

**Bold = already built.** Everything else in the table is the known backlog —
listed here so the next instance building one of these doesn't have to
re-derive which pattern fits; just generalize the existing table/grid data
layer (`Misc/eval_grid.py`) rather than writing a new one-off renderer.

## 3. The decision rule (for anything not in the table above)

Ask two questions:

1. **Is there a 2D parameter surface where the *shape* is the point** (e.g. "does
   control authority fall off at high density")? → grid, possibly with a table
   toggle for per-clip inspection.
2. **Is there a checkpoint/variant axis with 2+ values worth comparing
   side-by-side**? → table, with dual-pane compare if picking between variants
   is the actual task (not just browsing one).
3. **Neither** → flat clip grid. Don't invent a table with one row per clip and
   no sortable columns just to look fancy — that's worse than the flat grid.

**Never write a new bespoke HTML template for a new eval type.** Every family
above should reduce to: (a) a JSON schema `eval_grid.py` can parse into
records with the shared field set (`checkpoint`, `prompt_idx`, `prompt`,
`seed`, plus family-specific fields), and (b) one of the three existing
renderers (`render_grid_page`, `render_table_compare_page`, or the plain
`write_folder` flat fallback in `build_evals.py`). If a new family genuinely
doesn't fit any of the three, that's a signal to extend the shared renderer,
not to hand-write a fourth pattern.

## 4. Open backlog (not yet built, in rough priority order)

1. ~~**Control grids need the table toggle**~~ — **done, 2026-07-06.** The
   grid page's existing grid⇆ranked toggle now switches to a full Excel-style
   sortable table (click any column header to sort, per-column colour grading
   self-normalized over the page) instead of the old single-metric ranked
   list. Same page, same toggle button, no new template — just upgraded
   `eval_grid.py`'s `renderRanked()` to the shared `.tc-table` pattern.
2. **DoRA weight×length sweep** (`dora128_everything_8ep_lr1x_ep7_sweep`)
   should get the table+compare treatment (strength or length as the pane
   axis) once it has per-clip Audiobox scores (currently unscored — only the
   `_meta.json` sidecar exists, no `pq_scores.json`).
3. **Model-soup / weight-garden renders** as table views, once each has a
   `checkpoint`-equivalent key (soup recipe / mutation recipe) in a scored
   JSON.
4. **Disentanglement + LatCH-sweep** hand-curated pages could migrate onto the
   shared table renderer instead of being bespoke one-offs, once there's
   appetite to touch pages Kim already reads regularly (lower priority — they
   already work, just aren't generalized).

## 5. Accessibility (standing requirement, not per-eval)

Every eval page — regardless of family — must: be reachable from the landing
(`~/.cache/evals_aac/index.html`, also served at `aavepyora.online/files/evals/`
and mirrored non-hidden at `~/evals/`), be same-playhead playable, carry a
provenance box or `_meta.json`-derived description, and be leak-scanned before
any public transfer (no absolute paths / checkpoint filenames — see the
redaction seam in `Misc/build_evals.py`'s `redact()`).
