# M10 — the two writer briefs, ready to dispatch

*Written 2026-09-20 by FLATLINE. M10 is the statistics view, first version: three panels over
`/forge/stats` and `/forge/dataset_scalars`. It is a leaf — it needs only M1 and fixtures, and
nothing depends on it. Dispatch Writer A, then Writer B (they are sequential because B consumes A's
client and decoders), then one critic over all of it.*

**Plan file to produce:** `docs/superpowers/plans/2026-09-XX-latent-forge-m10-statistics.md`.

---

## Shared preamble — binding on both writers

Repo root `C:\Users\kim.ake\OneDrive - Bluefors\Documents\py\avp-audio-craft`, Windows, Bash
available. **No M365/Outlook/Teams/SharePoint tools.** Do not edit any existing file except the plan
you are writing.

**Read first:** `docs/latent-forge/HANDOUT.md` (the hazards list — all of it applies here);
`docs/superpowers/specs/2026-09-15-latent-forge-design.md` §4.4, §6.5, §4.1, §9.1, §9.7, §11.2,
§11.3; `docs/superpowers/plans/2026-09-16-latent-forge-m1-foundation-shell.md` **Task 13 in full**
(the statistics shell you are filling in) plus Tasks 3, 5 and 7 for the names you consume — M1 is
**approved and frozen**, so extend it and never change it; and one completed plan
(`2026-09-18-latent-forge-m4-prompt-sigma.md`) purely as a model of the format and voice.

**Format, normative:** `### Task N: <title>`, a short WHY paragraph, `**Files:**` (Create/Modify,
full paths), `**Interfaces:**` (`- Consumes:` / `- Produces:`, exact names and types — an
implementing agent sees ONE task at a time and can look nothing up, so restate every consumed name
every time), then checkbox steps: failing test with FULL code → run command with expected failure →
implementation with FULL code → run command with expected pass **and a true `it()` count** → commit
as `Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M10 T<N>: ..."`. No placeholders, no "...",
no "similar to above". TS strict. Svelte 5 runes only (`$state`, `$derived`, `$props`, snippets —
never `export let`, never the stores API). vitest 2, `@testing-library/svelte` for components. Test
command `cd latent-forge && npx vitest run <paths>`; type gate `npm run check` expecting
`svelte-check found 0 errors and 0 warnings`. No border radius, no shadows. Every interactive element
carries `data-help={HELP.<id>}` — **verify each id exists in M1 Task 14's table before using it**;
four invented ids were a blocking defect in M4.

**Count your own `it()` blocks.** A wrong "Expected:" count has been a defect in every milestone so
far.

**Open-questions rule:** where the spec and the drawing disagree, ship the spec's reading and end
your file with `## Open questions (Tasks N-M)`, each as
`- **<subject>** — <what disagrees> — <what you shipped>`.

## Names both writers inherit from M1 (frozen)

- From `src/lib/stores/view.svelte.ts` (T7): `view.screen: "workspace" | "statistics"`,
  `view.activeLane: 0 | 1 | 2 | 3`.
- From `src/lib/math/axis.ts` (T13): `niceTicks(min: number, max: number, target?: number): number[]`,
  `linScale(domain: [number, number], range: [number, number]): (v: number) => number`,
  `xcorrCellSize(px: number, n: number): number`.
- From `src/ui/stats/panelCanvas.ts` (T13): `fitPanelCanvas(canvas: HTMLCanvasElement):
  CanvasRenderingContext2D | null`, `panelColour(canvas: HTMLCanvasElement, token: string): string`.
- Components from T13 to fill in, not recreate: `StatisticsView`, `XcorrPanel`, `XYPanel`,
  `TimeSeriesPanel`.
- **The DOM contract M1 T13 already publishes, and which the Playwright spec asserts — use these
  exact attributes:** `[data-region="stats-view"]`, `[data-stats-panel="xcorr" | "xy" |
  "timeseries"]`, `[data-stats-lane="1" | "2" | "3" | "4" | "all"]`.
- From `src/lib/forge/api.ts` (T5): `forgeApi.stats(body)`, `forgeApi.datasetScalars(x, y)`,
  `ForgeApiError { status: number; message: string }`. **Check both signatures against M1 before
  relying on them** — M4 found `forgeApi.schedule`'s declared shape did not match its route, and the
  same class of error may be present here. If one does not match §6.5, say so in an open question and
  call the route directly from your own module, as M4 Task 4 does, rather than editing M1.
- From `src/lib/forge/types.ts` (T3): `LatentRef`, `AudioRef`.

## The contract you are building against (spec §6.5, quoted — verify it yourself)

`POST /forge/stats {latents: LatentRef[], features: string[], max_frames: 20000, max_points: 2000}` →
`{ok, n_frames, xcorr: {shape: [256,256], data_b64: "<uint8>"}, timeseries: [{index, feature, fps,
values: [number | null]}], features_available: [string]}`. **The xcorr bytes dequantise as
`byte/255·2 − 1`** (so the range is −1..1, not 0..1), `index` is the position in the `latents` array,
and `values` are resampled to at most `max_points`. A feature a latent lacks yields **all-`null`
values** — that is a normal response, not an error.

`GET /forge/dataset_scalars?x=<field>&y=<field>` → `{ok, fields: [numeric sidecar fields], points:
[{crop_id, x, y, label}] ≤ 6000}`.

## The constraint that shapes the whole milestone

**M10 must not depend on M5's arrangement store.** They are siblings; neither may import the other's
store. So *which* latents a lane contains arrives as **props or a callback**, never by reaching into
an arrangement. Say that plainly in every task that needs it. M5 or M7 wires the real source later;
until then the panels are driven by their props and the fixtures.

---

## Writer A — Tasks 1-3: the data layer

**Task 1 — `src/lib/stats/decode.ts`, pure.** Base64 and quantisation, separated from any fetch so
vitest can pin the numbers exactly. Produces: `decodeBase64(b64: string): Uint8Array`;
`dequantiseXcorr(bytes: Uint8Array, n: number): Float32Array` (`byte/255·2 − 1`, row-major C order,
throws a named error when `bytes.length !== n·n`); `dequantiseScaled(bytes: Uint8Array, scale:
number): Float32Array` (`byte/255·scale`, for §6.3's chroma bands, which M6 will reuse — build it
here and say so). Cover: an empty string, a length mismatch, the exact endpoints (`0 → −1`,
`255 → +1`, `128 → 0.00392…` and pin the real value rather than rounding it), and that C order is
row-major so `cell(r, c) = out[r·n + c]`.

**Task 2 — `src/lib/stats/statsClient.svelte.ts`.** The two calls, with `$state` for
`result`/`pending`/`error`, an `AbortController` for supersession, and decoding applied on arrival so
components never see base64. Produces `StatsRequest`, `StatsResult` (with `xcorr: Float32Array` and
`n: number`, not raw bytes), `DatasetScalars`, `class StatsClient` with `requestStats`,
`requestScalars`, `flush(): Promise<void>` and `dispose()`, and **a singleton
`export const statsClient = new StatsClient()`** — the panels are in separate components and all read
one result. **Two traps, both paid for elsewhere in this project:** an `abort` listener added after
the signal already fired never runs, so check `signal.aborted` before registering one; and a
singleton's cache outlives a component unmount, so every test must vary its input or reset the
client, or it silently reads the previous test's result.

**Task 3 — `src/ui/stats/StatsHeader.svelte` + `src/ui/stats/statsHeader.ts`.** §4.4's header row:
`ANALYSE`, the buttons `LANE 1..4` and `ALL`, and the note `features read from the sidecars
(.TIMESERIES.npz, .json)` verbatim. Pure part: `type LaneSel = 1 | 2 | 3 | 4 | "all"`;
`LANE_SELECTIONS: readonly LaneSel[]`; `laneSelLabel(s: LaneSel): string`;
`laneSelAttr(s: LaneSel): string` (feeding `[data-stats-lane]`, which M1 already fixed as
`"1" | "2" | "3" | "4" | "all"`). ANALYSE triggers the request; the selection is this milestone's own
state, not the workspace's `view.activeLane`, and the task should say why: §4.4 offers `ALL`, which
`activeLane` cannot express.

Write Tasks 1-3 to `scratchpad/m10_part_a.md`, starting directly with `### Task 1:`.
Reply one line: `A: tasks=1-3 lines=<n> its=T1:<n>,T2:<n>,T3:<n> openq=<n>`.

## Writer B — Tasks 4-7: the three panels and the wiring

Consume Writer A's names exactly; do not redefine them. Read `scratchpad/m10_part_a.md` first.

**Task 4 — `XcorrPanel.svelte`**, the 256×256 dim cross-correlation at 300 px (§4.4). Cell size from
M1's `xcorrCellSize`. **The colour scale is a diverging RAMP over −1..+1, and a ramp is the one case
where the project's "canvas colours come from `getComputedStyle`" rule does NOT apply** — an
unregistered custom property's computed value is its literal token stream, which has no channels to
interpolate. Build the `oklch()` string per channel, exactly as M5's `downbeatColor` does, and put
the reason in a comment so nobody "fixes" it back. Zero must be visibly neutral, and the two poles
must differ in hue, not only lightness. Hovering a cell reads out its `(row, col)` and value.

**Task 5 — `XYPanel.svelte`**, the dataset scatter. X/Y selects populated from
`DatasetScalars.fields` (§4.4 names `bpm`, `lufs`, `rel_pos` plus every numeric crop-sidecar scalar —
they come from the server, do not hard-code them). Axes from M1's `niceTicks` and `linScale`. The
selected lane's clips are **highlighted**, which means the panel needs to know which `crop_id`s are
in that lane — that arrives as a prop (see the constraint above), and with no prop nothing is
highlighted rather than everything. Handle: fewer than two points, all-identical values (a zero-width
domain — do not divide by zero), and a field present in `fields` but null on some points.

**Task 6 — `TimeSeriesPanel.svelte`**, one line per clip of the selected lane(s) over latent frames.
Feature select from `features_available`. **`values` may contain `null`, and a feature a latent lacks
is all-`null`** — a null is a GAP: break the line, never plot it as zero. Series are identified by
`index` into the request's `latents`, so the panel must be told what those indices mean. The x axis is
frames at the returned `fps`; the server resamples to `max_points`, so the axis is derived from
`n_frames`, not from `values.length`.

**Task 7 — wiring, empty and error states, and the Playwright spec.** `StatisticsView` composes the
header and three panels inside M1's `[data-region="stats-view"]`; the bottom pane stays hidden in
this view (§4.4). Every panel needs an honest empty state (**nothing analysed yet** is the state on
first paint, and it is not an error) and an error state per §9.7 — a server error puts a red line in
TERMINAL and a one-line message in the panel. Playwright: the view reachable, the three
`[data-stats-panel]` elements present, the five `[data-stats-lane]` buttons present, and the xcorr
canvas sized per §4.1. Finish with the self-review table against §4.4, §6.5 and §9.7, plus a
**Known incomplete** note: the "later — full statistics" panels of §4.4 (radar, PCA, dim ↔ feature
correlation, multi-selection bands) are explicitly out of scope, and §6.5 is additive so they join
without breaking this.

Write Tasks 4-7 to `scratchpad/m10_part_b.md`, starting directly with `### Task 4:`.
Reply one line: `B: tasks=4-7 lines=<n> its=T4:<n>,T5:<n>,T6:<n>,T7:<n> openq=<n>`.

---

## After both

1. Assemble: header + Global Constraints + File Structure (write these yourself) + both parts, with
   the open questions merged into one section at the tail.
2. Add a **Normative names and decisions** block — and this time include a **`data-*` and `HELP`-id
   table**, not just type names. In M4 every type-level name the parallel writers shared agreed and
   **every single break was in the DOM contract**. M1 T13 already fixes the stats attributes, so this
   block mostly restates them, which is exactly the point.
3. **Run one critic over the whole plan**, then verify the counts mechanically — count every `it(`
   block per task and compare against every stated gate. That has caught a stale cross-agent count no
   individual agent could see.
4. Budget: a writer has cost 260-270k subagent tokens and a critic 240k, so this milestone is roughly
   four agents. Check the **weekly** window before starting, not just the 5-hour one — the weekly is
   what has bound every time.
