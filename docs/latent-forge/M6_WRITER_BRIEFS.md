# M6 — the two writer briefs, ready to dispatch

*Written 2026-09-21 by FLATLINE. M6 is the CHROMA tab: spec §5.4 in full, the `/forge/chroma`
contract of §6.3, and the v3 drawing's chroma pane (markup lines 285–350, logic 819–960). Dispatch
Writer A, then Writer B (sequential — B consumes A's math and client), then one critic over all of
it, then verify counts mechanically.*

**Plan file to produce:** `docs/superpowers/plans/2026-09-XX-latent-forge-m6-chroma.md`.

---

## Shared preamble — binding on both writers

Repo root `C:\Users\kim.ake\OneDrive - Bluefors\Documents\py\avp-audio-craft`, Windows, Bash
available. **No M365/Outlook/Teams/SharePoint tools.** Do not edit any existing file except the
scratch file you are writing.

**Read first:** `docs/latent-forge/HANDOUT.md` (every hazard applies — especially the
`getComputedStyle` token-stream trap and its **ramp exception**, which this milestone hits twice);
`docs/superpowers/specs/2026-09-15-latent-forge-design.md` **§5.4 in full**, §6.3's
`POST /forge/chroma`, §4.3 (the clip score label and the TARGET lane), §4.5 (the tab row), §4.1,
§9.1, §9.7, §11.2, §11.3; the drawing `docs/sa3-studio/design_handoff/SA3 Studio v3.dc.html`
**markup lines 285–350** (the chroma pane's exact layout, copy and `data-help` strings) and **logic
lines 819–960** (`_chroma`, `_chromaBand`, `_targetProfile`, `_rotate`, `_matchFrame`, `_anchors`,
`_detuneScan`) — high fidelity for layout/copy/colour, **low fidelity for data and behaviour**, so
where the drawing's fake data generator disagrees with §5.4, §5.4 wins; and one completed plan
(`2026-09-18-latent-forge-m4-prompt-sigma.md`) purely as a model of format and voice.

**Format, normative:** `### Task N: <title>`, a short WHY paragraph, `**Files:**` (Create/Modify,
full paths), `**Interfaces:**` (`- Consumes:` / `- Produces:`, exact names and types — an
implementing agent sees ONE task at a time and can look nothing up, so restate every consumed name
every time), then checkbox steps: failing test with FULL code → run command with expected failure →
implementation with FULL code → run command with expected pass **and a true `it()` count** → commit
as `Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M6 T<N>: ..."`. No placeholders, no "...",
no "similar to above". TS strict. Svelte 5 runes only (`$state`, `$derived`, `$props`, snippets —
never `export let`, never the stores API). vitest 2, `@testing-library/svelte` for components. Test
command `cd latent-forge && npx vitest run <paths>`; type gate `npm run check` expecting
`svelte-check found 0 errors and 0 warnings`. No border radius, no shadows.

**Count your own `it()` blocks.** A wrong "Expected:" count has been a defect in every milestone.

**Open-questions rule:** where the spec and the drawing disagree, ship the spec's reading and end
your file with `## Open questions (Tasks N-M)`, each as
`- **<subject>** — <what disagrees> — <what you shipped>`.

## The `data-help` ids that actually exist — use these, invent none

**Unlike M4 and M10, this milestone's controls mostly DO have ids.** M1 Task 14's `KEYS` table
(inside the M1 plan, which generates `docs/latent-forge/extract_help.mjs` and
`src/lib/help/strings.ts`) maps these, by their v3 line number:

| `HELP` id | v3 line | Control |
|---|---|---|
| `chromaMatchMarks` | 292 | the three-anchor legend |
| `chromaChord` | 323 | chord-symbol text field |
| `chromaMatchLegend` | 330 | `match <score> · <scale>` readout |
| `chromaDetuneScan` | 332 | the detune scan strip canvas |
| `chromaBestCriterion` | 335 | HIGHEST / STEADIEST toggle |
| `chromaBest` | 336 | BEST button |
| `chromaHeatmap` | 344 | the main heatmap canvas |
| `chromaMatchCurve` | 346 | the match-curve overlay canvas |
| `laneTarget` | 122 | the lane header's TARGET button (M5 already renders this) |
| `clipDetune` | 126 | the lane header's clip-detune field (M5 already renders this) |

**No id exists for:** the four mode buttons (GLOBAL / BASS oct1 / MID oct5 / HIGH oct9, v3 288),
the TARGET lane / SEMITONE SET mode buttons (v3 312–313), the twelve piano-key toggles (v3 320),
or the hover readout (v3 338). Ship those **without** `data-help` rather than inventing an id —
four invented ids were a blocking defect in M4, and M10 shipped nine controls bare for this reason.
Note it in your open questions.

## Names both writers inherit — all frozen or already shipped

- From `src/lib/forge/api.ts` (**M1 T5**):
  `forgeApi.chroma: (audio: AudioRef) => Promise<{ok: true; frames: number; fps: number; bands: {shape: [number, number, number]; scale: [number, number, number]; data_b64: string}; fold12: {shape: [number, number]; scale: number; data_b64: string}}>`
  and `forgeApi.stretch: (audio: AudioRef, speed: number, semitones: number) => Promise<...>`;
  `class ForgeApiError { status: number; message: string }`. **Check both against M1 before relying
  on them** — M4 found `forgeApi.schedule`'s declared shape did not match its route, and M10 found
  `forgeApi.stats` declared differently from how its brief described it. If one does not match §6.3,
  say so in an open question and call the route directly from your own module (as M4 Task 4 does)
  rather than editing M1.
- From `src/lib/stats/decode.ts` (**M10 T1**): `decodeBase64(b64: string): Uint8Array` and
  `dequantiseScaled(bytes: Uint8Array, scale: number): Float32Array` (`byte/255·scale`).
  **This function was built in M10 deliberately for M6 to reuse — use it, do not write a second
  one.** It means M6 depends on M10 Task 1; say so in the plan's **Depends on** line.
- From `src/lib/stores/arrangement.svelte.ts` (**M5 T1**): the singleton `arrangement`, with fields
  `bpm`, `beatsPerBar`, `snap`, `lanes`, `clips`, `pxPerSec`, `scrollSec`, derived `overlaps`,
  `arrangementEndSec`, `selectedClip`, `selectedOverlap`, and the methods this milestone needs:
  `setDetune`, `setTargetLane`, `setClipBpm`. A lane carries the chroma TARGET flag (M5's
  `ForgeLane`, spec §4.3 header row 3; `null` = none chosen).
- From `src/lib/forge/types.ts` (**M1 T3**): `ForgeClip`, `ForgeLane`, `AudioRef`, `LatentRef`.
  `ForgeClip.detune_cents` is the per-clip detune this milestone reads and writes;
  **`ForgeClip.previewAudio`** (added by M5 T10) is the **stretched** preview audio — §5.4 says
  chroma is computed on that, not on the raw source, "so it matches what the timeline plays".
  Settled 2026-09-21: `previewAudio` is **in-memory only and is NOT serialised** into the project
  JSON (§9.2 is unchanged); it is a cache of §7.3's analyze→stretch step, re-derived on load. Read
  it, never persist it, and read `clip.previewAudio ?? clip.audio` so an unstretched clip still
  resolves.
- From `src/lib/stores/view.svelte.ts` (**M1 T7**): `view.bottomTab`, `view.setBottomTab`,
  `view.activeLane`, `view.setActiveLane`. **The earlier caution is withdrawn — fixed by WINTERMUTE
  on 2026-09-21 (`7193ba9`).** M1 T7's class body now declares `screen` and `activeLane` as real
  fields, matching the Normative table; `setView(v)` keeps its name and writes `screen`, and
  `setActiveLane(n)` is new. Two neighbours changed in the same pass and **you must use the new
  spellings**: `TerminalMode`'s middle mode is `"pane"`, never `"normal"`, and the string-array
  constant of bottom-tab ids is `BOTTOM_TAB_IDS`, not `BOTTOM_TABS`. `ModuleId` is kebab, declared
  once, and now has **seven** members (the five spec modules plus `legacy-inspector` and
  `legacy-server`); `MODULE_IDS` carries all seven, while T12's `MODULE_ORDER` carries the five.
- From **M1 T11/T12**: the bottom-pane tab frame. The duplication is gone (WINTERMUTE,
  2026-09-21): the type is **`BottomTabId`**, declared **once in the view store (T7)** and
  re-exported by `src/ui/shell/bottomTabs.ts` (T11) for the tab table's convenience — T7 is built
  first, so declaring it there is what keeps T7's own vitest run green in task order. `type
  BottomTab` no longer exists; do not cite it. The body you fill is
  `[data-region="bottom-tab-body"]`, **162 px**, and
  the tab's right-aligned hint is already `hover the heatmap to read a frame` (M1 T12's
  `bottomHint("chroma")`) — do not re-render it.
- From **M5 T6**: `SCORE_PLACEHOLDER = "χ —"`, the clip box's score-label slot. **M6 fills the real
  number in** — M5's self-review lists this as deferred with M6 as its owner.

## The contract you are building against (spec §6.3, quoted — verify it yourself)

`POST /forge/chroma {audio: AudioRef}` →
`{ok, frames: T, fps: 10.7666015625, bands: {shape: [3,128,T], scale: [s0,s1,s2], data_b64: "<uint8 C-order>"}, fold12: {shape: [12,T], scale: 1.0, data_b64: "<uint8>"}}`,
**dequantised as `byte/255·scale`** — one scale per band for `bands`, a single scale for `fold12`.
Caching is keyed server-side on the audio file's sha256; §5.4 says the computation runs on the
clip's **stretched preview audio**. The mock server maps this route to fixture
`forge_chroma_render` (M1 T6); check whether a `handmade-forge_chroma_render.json` actually ships —
M10 found both of *its* routes mapped to fixture names that did not exist, and had to add them.

## The numbers §5.4 pins — copy them exactly, do not re-derive

- **Bin geometry:** pitch class C sits at **bin 2.0**; each semitone spans **128/12** bins (the
  `same_chroma` PITFALL). Y-axis note labels come from `semitone_bin_centers`.
- **Views:** `GLOBAL` = the 12-class fold (the three bands folded by `fold_to_12`, **per-frame
  normalised to max 1**); `BASS oct1` / `MID oct5` / `HIGH oct9` = the raw 128 bins of band 0/1/2.
- **Match:** `INTERVAL_W = [1.0, 0.10, 0.35, 0.62, 0.70, 0.82, 0.18, 0.90, 0.66, 0.72, 0.30, 0.22]`,
  pitch classes counted **only above 0.08** (`_matchFrame`, v3 925–937).
- **Detune rotation:** rotates a 12-class frame by `cents/100` classes with a **linear energy
  split** (`_rotate`, v3 895–903).
- **Legend anchors:** unison, fifth and tritone scores **of the target against itself**
  (`_anchors`).
- **Clip score label** = **mean frame match at the clip's detune**.
- **Detune scan:** cents **−100..100 step 4**, sampling **every 3rd frame**, computing `mean` and
  `sd`; **HIGHEST uses `mean`, STEADIEST uses `mean − sd`** (`_detuneScan`, v3 947–957). The strip
  plots the curve with a **red mark at the current detune**; click or drag sets detune; BEST jumps
  to the argmax under the current criterion.
- **Target, `lane` mode:** the TARGET lane's clips' 12-class fold, **summed over frames and
  max-normalised** (`_targetProfile`, v3 877–891).
- **Target, `SEMITONE SET` mode:** 12 piano-key toggles plus a chord-symbol field covering
  `C, Cm, C7, Cmaj7, Cm7, Cdim, Caug, Csus2, Csus4` **over all 12 roots**, with **`#` and `b`
  spellings**, that fills the key row.
- **Detune changes the clip's preview through `/forge/stretch`, debounced 400 ms**, and enters the
  commit as **semitones** (§8.1 S2) — cents/100.
- **Hover** reads note name + frame index into the readout (**14 px** note, **9 px** detail) and
  draws a **red vertical line at that frame on the selected clip in its lane**.

## Two constraints that shape the whole milestone

1. **The heatmap and the consonance colouring are RAMPS.** This is the one documented exception to
   "canvas colours come from `getComputedStyle`" (HANDOUT.md): an unregistered custom property's
   computed value is its literal token stream, with no channels to interpolate. Build `oklch()`
   strings per channel, exactly as M5's `downbeatColor` and M10's `xcorrColor` do, and put the
   reason in a comment so nobody "fixes" it back. Flat colours (borders, tick labels, the red
   detune mark if it maps to a token) still come from `getComputedStyle`.
2. **M6 must not reach into M7's or M9's territory.** The CHROMA CROSSFADE toggle on an overlap
   (§4.6, v3 459–460, `HELP.overlapChromaXfade`) belongs to M7's overlap module, and the commit-time
   chroma slot (§8.1) is server-side. M6 builds the *tab* and the *clip score label* only.

---

## Writer A — Tasks 1-5: the chroma data and math layer

Every one of these is a pure module plus one client, kept out of any component so vitest can pin
the exact numbers §5.4 specifies without a canvas or a network.

**Task 1 — `src/lib/chroma/bins.ts`, pure.** The bin geometry every other task depends on.
Produces: `BINS_PER_BAND = 128`; `BANDS = 3`; `BINS_PER_SEMITONE = 128 / 12`; `C_BIN = 2.0`;
`semitoneBinCenters(): number[]` (12 entries, C at 2.0, each semitone `128/12` apart, wrapping
within the 128-bin band); `binToPitchClass(bin: number): number` and its inverse;
`NOTE_NAMES: readonly string[]` (the twelve, sharp spellings, C first);
`foldTo12(band: Float32Array, binsPerBand?: number): Float32Array` (one frame of 128 bins → 12
classes) and `foldFrameTo12(bands: Float32Array, frame: number, T: number): Float32Array` (all
three bands of one frame → 12 classes, **then per-frame normalised to max 1**, which is what
GLOBAL displays). Cover: C lands at bin 2.0 and folds to class 0; the wrap at the top of the band
(a bin past 128 − `128/12`/2 belongs to C again); a frame of all zeros normalises to all zeros
rather than dividing by zero; and that the normalisation is **per frame**, not global.

**Task 2 — `src/lib/chroma/chromaClient.svelte.ts`.** `/forge/chroma` through `forgeApi.chroma`,
decoded on arrival with M10 T1's `decodeBase64` + `dequantiseScaled` so no component ever sees
base64. Produces `ChromaResult { frames: number; fps: number; bands: Float32Array; // 3*128*T,
C-order  fold12: Float32Array; // 12*T  T: number }`, `class ChromaClient` with `$state` fields
`result`/`pending`/`error`, methods `request(audio: AudioRef): Promise<void>`, `flush()`,
`dispose()`, **a per-`AudioRef` cache** (the server caches on sha256, but a re-request still costs a
round trip and the pane re-reads on every selection change), and the singleton
`export const chromaClient = new ChromaClient()`. **Three traps, all paid for elsewhere in this
project:** an `abort` listener added after the signal already fired never runs, so check
`signal.aborted` first; a singleton's cache outlives a component unmount, so every test must vary
its input or reset the client; and the two quantisations differ — `bands` has **three** scales
(one per band, applied to that band's slice) while `fold12` has **one**. Getting that wrong
silently mis-scales two-thirds of the data.

**Task 3 — `src/lib/chroma/match.ts`, pure.** The harmonic-overlap score. Produces
`INTERVAL_W` (the twelve weights above, exactly); `MATCH_THRESHOLD = 0.08`;
`matchFrame(frame: Float32Array, target: Float32Array): number` (pitch classes counted only above
the threshold); `rotate(frame: Float32Array, classes: number): Float32Array` (fractional rotation
with a **linear energy split** between the two neighbouring classes; `classes` may be negative and
wraps); `anchors(target: Float32Array): {unison: number; fifth: number; tritone: number}` (the
target scored against itself at 0, 7 and 6 semitones). Cover: a frame identical to the target
scores the unison anchor; rotating by a whole number of classes is a pure permutation (no energy
lost); rotating by 0.5 splits evenly; a frame entirely below 0.08 contributes nothing; and
`unison > fifth > tritone` for a non-degenerate target.

**Task 4 — `src/lib/chroma/target.ts`, pure.** Both target modes. Produces
`type ChromaTargetMode = "lane" | "set"`;
`targetProfile(frames: Float32Array[], ...): Float32Array` — lane mode, the 12-class folds
**summed over frames then max-normalised**; `setProfile(keys: readonly boolean[]): Float32Array` —
SEMITONE SET mode, the twelve toggles as a flat profile; and the chord parser
`parseChord(text: string): boolean[] | null` covering the nine qualities
(`"", "m", "7", "maj7", "m7", "dim", "aug", "sus2", "sus4"`) over all twelve roots with **`#` and
`b` spellings** (so `F#m`, `Gbm`, `Bb7` all parse), returning `null` for anything unrecognised
rather than throwing. Cover: every quality's interval set; `Db` and `C#` give the same keys;
case handling for the root; an empty and a nonsense string; and that a lane with no clips yields an
all-zero profile rather than NaN.

**Task 5 — `src/lib/chroma/detuneScan.ts`, pure.** Produces
`DETUNE_MIN = -100`, `DETUNE_MAX = 100`, `DETUNE_STEP = 4`, `FRAME_STRIDE = 3`;
`type ScanCriterion = "highest" | "steadiest"`;
`scanDetune(fold12: Float32Array, T: number, target: Float32Array): {cents: number[]; mean: number[]; sd: number[]}`
(sampling every 3rd frame, rotating by `cents/100` classes at each step);
`bestDetune(scan, criterion): number` (argmax of `mean`, or of `mean − sd`). Cover: the cents axis
is exactly `-100, -96, … 96, 100` (**51 points** — check that arithmetic yourself and state the
number in the test); HIGHEST and STEADIEST can disagree, with a constructed case proving it; a
single-frame input gives `sd === 0` everywhere so the two criteria agree; and an all-zero target
does not divide by zero.

Write Tasks 1-5 to `scratchpad/m6_part_a.md`, starting directly with `### Task 1:`.
Reply one line: `A: tasks=1-5 lines=<n> its=T1:<n>,T2:<n>,T3:<n>,T4:<n>,T5:<n> openq=<n>`.

## Writer B — Tasks 6-11: the pane

Consume Writer A's names exactly; do not redefine them. Read `scratchpad/m6_part_a.md` first.

**Task 6 — heatmap geometry + `src/ui/chroma/ChromaHeatmap.svelte`.** Split the geometry into a
pure `src/lib/chroma/heatmapGeometry.ts` (frame → x, bin/class → y, the target reference row at the
top, the visible frame window under middle-drag zoom/scroll — v3's `middle-drag: ↕ zoom · ↔ scroll`
hint at line 341) and keep the component to drawing. Four view modes (GLOBAL = 12 rows of the
fold, BASS/MID/HIGH = 128 rows of one band). **Consonance colour is a ramp** — see the constraints
above. The canvas carries `data-help={HELP.chromaHeatmap}`.

**Task 7 — the match curve overlay + the legend.** A second canvas stacked over the heatmap
(`data-help={HELP.chromaMatchCurve}`), toggled by `MATCH CURVE`, plotting `matchFrame` per frame.
The legend (`data-help={HELP.chromaMatchMarks}`) draws the gradient stops with **three tick marks at
the unison, fifth and tritone anchors** of the target against itself, and the readout line
`match <score> · <scale>` carries `HELP.chromaMatchLegend`. Note in the task that the drawing calls
the colouring CONSONANCE COLOUR and always leaves it on (v3 729).

**Task 8 — `src/ui/chroma/DetuneScanStrip.svelte`.** The 500×30 canvas
(`data-help={HELP.chromaDetuneScan}`) plotting Writer A's scan curve with the **red mark at the
clip's current detune**; click or drag anywhere on it sets detune; the criterion toggle
(`HELP.chromaBestCriterion`, HIGHEST / STEADIEST) and BEST (`HELP.chromaBest`) sit beneath it.
Writing detune goes through `arrangement.setDetune`, never by mutating the clip directly.

**Task 9 — the target row.** `TARGET` + the two mode buttons (lane / SEMITONE SET, no `data-help`),
and in SEMITONE SET mode the twelve piano-key toggles plus the chord field
(`data-help={HELP.chromaChord}`, placeholder `chord symbol`) that fills the key row through Writer
A's `parseChord`. In `lane` mode the label shows which lane is TARGET, from `arrangement`; with no
TARGET lane chosen, say so honestly rather than showing an empty profile as if it were data.

**Task 10 — hover readout, the lane cross-link, and the clip score label.** The readout is
**14 px note name, 9 px detail** (§5.4), rendering as DOM siblings of the canvas, never `fillText`
into it — a `fillText` label can never be found by `findByText`, which was a blocking M4 finding.
Hovering also **draws a red vertical line at that frame on the selected clip in its lane**: check
whether M5's lane canvas left a seam for this; if it did not, add the smallest one you can (a
`$state` field the lane canvas reads, not a restructure of M5's component) and flag it. Finally,
**fill M5 T6's `SCORE_PLACEHOLDER = "χ —"`** with the real mean-frame-match number at the clip's
detune — that is the one thing M5 explicitly deferred to this milestone.

**Task 11 — tab assembly, the stretch debounce, Playwright, self-review.** Compose Tasks 6-10 into
M1's `[data-region="bottom-tab-body"]` (162 px) for `bottomTab === "chroma"`; the hint is already
M1's, do not re-render it. **Detune changes re-request the clip's preview through `/forge/stretch`,
debounced 400 ms** (§5.4) — and the chroma itself must then be recomputed on the new stretched
audio, so say plainly which of the two requests leads. Honest empty states throughout: no clip
selected, no TARGET lane, chroma still computing, and a §9.7 server error (red line in TERMINAL plus
a one-line message in the pane). Playwright: the tab reachable, the heatmap canvas present and
sized, the scan strip present, the four mode buttons present. Finish with the self-review table
against §5.4, §6.3 and §9.7, plus a **Known incomplete** note.

Write Tasks 6-11 to `scratchpad/m6_part_b.md`, starting directly with `### Task 6:`.
Reply one line: `B: tasks=6-11 lines=<n> its=T6:<n>,T7:<n>,T8:<n>,T9:<n>,T10:<n>,T11:<n> openq=<n>`.

---

## After both

1. Assemble: header + Global Constraints + File Structure + "Status of this plan" (write these
   yourself) + both parts, with the open questions merged into one section at the tail.
2. Add a **Normative names and decisions** block including a **`data-*`/`data-testid` and `HELP`-id
   table**. M6 is the first milestone where most ids genuinely exist, so the table is mostly a
   restatement — which is the point.
3. **Run one critic over the whole plan**, then verify the counts mechanically (`grep -c '  it('`
   against every stated gate).
4. Budget: a writer has cost 245–310k subagent tokens and a critic ~280k, so this milestone is
   roughly three agents and ~27 points of a 5-hour window. Check the **weekly** window too.
