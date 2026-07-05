# Spec: rich gain×density eval-grid renderer (restore + extend)

*2026-07-05 · authored WINTERMUTE, for GHOST-NOTE to implement · Kim-directed.*
*Reviewer gate: Kim eyeballs this before implementation begins (he has strong specifics here).*

## 1. Problem — a real regression

The per-folder eval pages that `Misc/build_evals.py` generates for `control_runs/` and
`renders/` are **flat, undifferentiated cell grids** (`write_folder()` → one `.cell` per
clip, label = filename). For **gain×density sweep** evals (`composed_sweep/A_cc_v2`,
`E_fusion_v2`, the `onset_eval_*` dirs) this is a big step down from what we had: the
original `Misc/build_onset_eval_page.py` rendered a **gain-row × density-column grid**,
**heatmap-colored by measured density**, with **per-gain correlation**, a **same-playhead
player**, a **provenance info box**, and a **sort toggle**. And the **Audiobox quality
descriptors (CE/PC/PQ/CU + a disintegration flag)** — computed by `pq_score.py` — were
color-coded onto the cells. All of that is currently absent from the per-folder pages
(example Kim flagged: `/files/evals/control_runs/A_cc_v2/index.html`).

Root cause: `build_evals.py` became the generic "turn any served dump into a player"
generator and never learned to (a) read `onset_eval.json` / `pq_scores.json`, (b) group by
gain/density, or (c) color by quality. `A_cc_v2` was also **never scored** — it has no
`pq_scores.json`.

**Goal:** for grid-style eval dirs, restore the rich renderer and extend it with prompt
grouping, a multi-metric sort control, an always-visible CE/PC quality badge, and a new
**spectral-balance** cheat-detector.

## 2. What already exists (reuse, don't reinvent)

- **Reference renderer** `Misc/build_onset_eval_page.py` (137 lines) — the gold layout:
  gain rows × density cols; `col(m)=hsl(clamp(m/14,0,1)·130,45%,22%)` red→green heatmap by
  measured onset density; per-gain `corr`; same-playhead player (`cell()` keeps `au.currentTime`
  on switch, re-click stops); provenance `#info` box from `run_meta.json`; a "sort all clips by
  output density" flat-table toggle. **Restore this behavior; generalize it.**
- **Metric producers (MIR venv — `mir/bin/python`):**
  - `onset_eval.json` (list, per clip): `prompt_idx, prompt, seed, gain, requested, measured,
    flatness, in_support`. `measured − requested` = the **error delta**.
  - `pq_scores.json` (list, per clip; from `control/sa3_control/pq_score.py`, Audiobox
    Aesthetics + WavLM): `gain, density, PQ, CE, CU, PC, broke`. `broke = PQ<FLOOR or CE<FLOOR`
    (disintegration on either axis). **CE/CU/PC/PQ = the "color-coded quality descriptors"
    Kim means** (`mir/src/timbral/audiobox_aesthetics.py`: CE=Content Enjoyment,
    CU=Content Usefulness, PC=Production Complexity, PQ=Production Quality).
- **Existing conventions** (SAO/MASTER.md §4): every eval dir carries `run_meta.json`
  provenance; eval pages MUST present clips as clickable **same-playhead** cells; public pages
  **redact plumbing** (checkpoint filenames / absolute paths / infra out; config settings —
  lr/optimizer/epochs/scalar_field — and metrics are OK to show, per Kim "that's how the light
  gets out").

## 3. Data contract — the merged per-clip record the renderer consumes

Merge `onset_eval.json` ⋈ `pq_scores.json` on `(prompt_idx, seed, gain, density)`
(`density == requested`). Each clip →

```
{ prompt_idx, prompt, seed, gain,
  density,                 # = requested
  measured,                # measured onset density (onsets/s)
  error_delta,             # measured − requested (signed)
  flatness,                # spectral flatness (from onset_eval.json)
  spectral_balance,        # NEW — see §4
  CE, CU, PC, PQ, broke,   # from pq_scores.json
  clip_path }              # served-relative .m4a
```

Clips missing a partner in either source: keep the row, mark the absent metrics `null`
(renderer shows "·"), never drop the cell.

**Clip-name parsing must handle both conventions:** legacy `onset_g{g}_d{q}.wav` and the
composed-sweep `{run}_p{pi}_s{seed}_g{g}_d{d}.m4a` (note densities like `d7.5`). Parse
`p/s/g/d` from the name; don't assume integer densities.

## 4. New metric — `spectral_balance` (the lowpass-cheat detector)

Some models fake higher onset density by **lowpass-filtering** (mushier top end reads as
"busier" to the onset meter without real events). `flatness` is a weak proxy. Add an explicit
brightness metric per clip, computed in MIR over each rendered clip:

- **`spectral_balance`** = normalized spectral centroid (Hz / Nyquist), OR a high/low
  band-energy ratio (e.g. energy>2kHz ÷ energy<2kHz). Implementer picks one; document it.
- Compute it in `pq_score.py` (it already loads each clip's audio) and add it to each
  `pq_scores.json` row, so no extra audio pass. Keep `flatness` too (onset_eval already has it).

Interpretation for color: a clip whose measured density is high **but** spectral_balance is
low = a likely cheat → flag it (diverging color, dark = suspicious).

## 5. Metric pipeline — make the data exist

For **every grid-style eval dir** (detected by presence of `onset_eval.json`):

1. If `pq_scores.json` is absent (e.g. `A_cc_v2` and the `composed_sweep` dirs), run
   `mir/bin/python control/sa3_control/pq_score.py <dir>` to produce it (Audiobox, MIR venv).
2. Ensure `pq_score.py` emits `spectral_balance` (§4).
3. `onset_eval.json` already provides gain/requested/measured/flatness (produced by
   `onset_eval.py`, mir venv) — no change needed there.

This scoring step is a **prerequisite** the builder should trigger or check; the renderer
must degrade gracefully (show onset/error/flatness even when CE/PC are missing) but the
intent is every online grid dir is fully scored.

## 6. Layout — the grid (Kim's explicit structure)

Group **by GAIN (outer)**; within each gain, **one ROW per PROMPT**; each row = **density
cells in ascending density order**. Single-prompt dirs (the `A_cc_v2` case) collapse to
**one row per gain**. Ordering within a block: iterate all prompts at a gain before moving to
the next gain (gain-major, prompt-minor, density along the row).

Each **cell**:
- shows the **primary value** (default: `measured` onset density),
- **background** colored by the **active color metric** (§7),
- a small **CE/PC quality badge** — *always visible regardless of the active metric* (this is
  the descriptor Kim missed): e.g. a corner chip colored green (healthy) / amber (marginal) /
  red (`broke`), tooltip = `CE x.x · PC x.x · PQ x.x`,
- **click to play** (same-playhead: switching keeps `currentTime`, re-click stops),
- on click, the **info box** shows the clip's full metric readout + run provenance
  (`run_meta.json`, redacted).

Per **gain row/block**: show `corr` (measured-vs-requested correlation) and mean |error|, as
the original did.

## 7. Sort / order control (Kim's ask)

A segmented control / button row selecting the **active metric**:
`gain · density · content enjoyment (CE) · onset density (measured) · error delta (|measured−requested|) · spectral balance`.

Two view modes (generalize the original toggle):
- **Grid mode** — the gain→prompt→density grid; cells **recolored** by the active metric.
- **Ranked mode** — a flat table of *all* clips **sorted** by the active metric (best- or
  worst-first, direction sensible per metric: CE/PQ high-first, |error|/cheat low-first),
  each row playable (same-playhead). This is where "which clips actually cheated / disintegrated"
  jumps out.

Color maps per metric: measured→existing red→green heatmap; CE/PQ→green(high)→red(low, `broke`
outlined red); PC→diverging (thin↔distorted); error_delta→diverging around 0; spectral_balance→
diverging (dark/lowpassed = red).

## 8. Integration

- `build_evals.py`: in `write_folder`, **route** dirs that have `onset_eval.json` to the new
  rich grid renderer; dirs without keep the current flat player. Detection = file presence.
- **Factor the grid renderer into a shared module** (`Misc/eval_grid.py`?) so the per-folder
  pages *and* the curated `riffer/onset_eval.html` can share one implementation — do **not**
  add a third divergent copy. (`build_onset_eval_page.py` should eventually call it too.)
- Keep the site's **edg3 light theme** for the per-folder pages (the current build_evals CSS),
  not the old dark `#0e0e10` — port the *logic*, restyle to match the rest of `/files/evals/`.
- Redact provenance per SPEC §4 at render time (config settings shown; filenames/paths/infra out).

## 9. Scope / non-goals

- Covers the **gain×density grid eval type** (`composed_sweep/*`, `onset_eval_*`). The curated
  riffer pages (`disentangle`, `dora_results`, `latch_sweep`, `mp`, `traj`) already have rich
  renderers and are linked from the landing — not regressed here, out of scope (but the shared
  module should let them converge later).
- No new training/measurement beyond `spectral_balance` and running `pq_score.py` where missing.

## 10. Acceptance criteria

1. `A_cc_v2` (and every `composed_sweep` grid dir) renders as **gain-grouped rows of density
   cells**, one row per prompt, densities in order.
2. Every cell carries an **always-visible color-coded CE/PC badge**; `broke` cells are visibly
   flagged.
3. The **sort control** reorders + recolors by gain / density / CE / onset density / error-delta
   / spectral-balance, in both **grid** and **ranked** modes.
4. **Same-playhead** playback (switch keeps position, re-click stops) works throughout.
5. `pq_scores.json` (incl. `spectral_balance`) exists for every scored online grid dir;
   renderer degrades gracefully where a metric is absent.
6. Per-folder pages match the site's light theme; provenance redacted per SPEC §4.
7. One **shared** grid-render module; no third divergent copy.

## 11. Suggested implementation order

1. Extend `pq_score.py`: add `spectral_balance`; run it over `A_cc_v2` as the test dir.
2. `Misc/eval_grid.py`: the merge (onset_eval ⋈ pq_scores) + the grid/ranked renderer + JS
   (sort/recolor/same-playhead), light-themed. Unit-test the pure parts (name parse, merge,
   metric→color, sort keys) against `A_cc_v2` data.
3. Wire `build_evals.py write_folder` to route grid dirs to it.
4. Backfill: `pq_score.py` over the other `composed_sweep` + `onset_eval_*` dirs, rebuild,
   hand to WINTERMUTE for leak-scan + transfer to `/files/evals/`.
5. Verify `A_cc_v2` live: gain rows, density cells, CE/PC badges, all six sorts, same-playhead.
