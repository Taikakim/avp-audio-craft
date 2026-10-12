# Latent Forge M6 — the CHROMA tab

**Goal:** build spec §5.4's CHROMA bottom-pane tab: the chroma heatmap in four view modes, the
harmonic-overlap match curve and its consonance legend, the ±100 ¢ detune scan strip with BEST, the
target row in both `lane` and `SEMITONE SET` modes, the hover readout, the lane cross-link, and the
real clip score that M5 left as a placeholder.

**Architecture:** a pure data-and-math layer under `src/lib/chroma/` (Tasks 1–5) that knows nothing
about the DOM, and a pane under `src/ui/chroma/` (Tasks 6–11) that draws it. Every number the pane
shows comes from a pure function with its own unit test; the components own drawing, hit-testing and
empty states, and nothing else. The split is deliberate: the math is the part that has a right
answer, and it is checkable without a browser.

**Tech stack:** Vite + Svelte 5 (runes) + TypeScript 5.6, vitest 2, Playwright 1. Canvas 2D for the
heatmap, the curve overlay and the scan strip; DOM for anything a test asserts text on.

**Spec:** `docs/superpowers/specs/2026-09-15-latent-forge-design.md` — §5.4 is the normative section;
§6.3 is the `/forge/chroma` contract; §9.7 is error surfacing; §4.3 supplies the clip score label and
the TARGET lane; §4.5 supplies the bottom-pane frame.

**Depends on:**

- **M1** (foundation and shell) — types, the view store, the bottom-pane frame, the `HELP` table, the
  mock server. M1 must land first; nothing here compiles without it.
- **M5** (timeline fidelity) — `arrangement`, `setDetune`, `targetLane`, the lane canvas, and
  `ClipBox`'s `SCORE_PLACEHOLDER`, which Task 10 replaces with a real number.
- **M10 Task 1** (`src/lib/stats/decode.ts`) — Task 2 reuses its `dequantiseScaled` and its base64
  decoder rather than writing a second copy. **M10 T1 must land before M6 T2.** This is the one
  cross-milestone code dependency in the frontend track; it was built in M10 deliberately for here.

**Blocks:** nothing. M6 is a leaf on the frontend side. M7 and M9 do not read anything it produces,
beyond the clip score label already being filled in.

---

## Global constraints

**Read these before Task 1. Each one cost a debugging session, a critic round, or a green test that
could never have worked.**

1. **`getComputedStyle(el).getPropertyValue("--token")` returns the token stream, not a colour.** An
   unregistered custom property is not resolved, so you get the literal string `oklch(78% 0.08 250)`.
   That is fine to hand straight to `ctx.fillStyle`, which accepts it — and **fatal if you parse
   channels out of it**: a digit regex turns that string into `rgb(78, 0, 250)`, an indigo. So flat
   canvas colours come from `getComputedStyle`; a **ramp builds its own `oklch()` string and
   interpolates per channel**, because a ramp needs channels and a token stream has none. This
   milestone's ramp is `consonanceColor.ts` (Task 6), the fourth in the project after M5's
   `downbeatColor`, M4's CFG interval and M10's `xcorrColor`. Match their shape.
2. **In jsdom, seed tokens inline.** Measured, not assumed: a `<style>` block on `:root` returns
   `oklch(90%0.012 240)` — the space after `90%` is eaten; inline on the element or an ancestor
   round-trips exactly; never defined returns `""`. And `ctx.fillStyle = ""` is a **silent no-op that
   leaves the previous colour**, so every token read needs a per-token fallback. Task 6's
   `chromaCanvas.ts` carries that table.
3. **Never `fillText` a label a test asserts on.** A `fillText` label cannot be found by
   `findByText` — a blocking M4 finding. The hover readout (Task 10) renders as DOM siblings of the
   canvas: 14 px note name, 9 px detail, per §5.4.
4. **An abort listener added after the signal already fired never runs.** Check `signal.aborted`
   first, or the promise never settles. This was a real green-looking test that hung.
5. **The `$state` proxy rule.** Pushing an object into a `$state` array deep-proxies it; the local
   reference you built is a dead handle and mutating it does nothing. Any store method that appends
   must return `arr[arr.length - 1]`, never the object it constructed.
6. **SAME latents are not translation-invariant, and the timeline is audio.** Chroma is computed on
   the clip's **stretched preview audio** (§5.4), so it matches what the timeline plays — not on the
   raw source. Preview is not the output; only RENDER/MIXDOWN commits a real latent op.
7. **One task at a time.** Every task restates the interfaces it consumes, because an implementing
   agent sees a single `### Task N` section and can look nothing up. Where two tasks disagree, the
   **Normative names and decisions** block below wins over both.

---

## Names inherited from M1, M5 and M10 — do not redeclare them

These changed on **2026-09-21** (WINTERMUTE, `7193ba9`) and a plan drafted before that date may cite
the old spellings. These are the current ones:

| name | where it lives | note |
|---|---|---|
| `view.screen` | M1 T7 view store | **not `view.view`.** `setView(v)` is still its setter |
| `view.activeLane`, `view.setActiveLane(n)` | M1 T7 | both are real fields/methods now |
| `BottomTabId` | **M1 T7 declares it**, M1 T11 re-exports | `type BottomTab` no longer exists |
| `BOTTOM_TAB_IDS` | M1 T7 | not `BOTTOM_TABS` |
| `TerminalMode` | M1 T7 | `"collapsed" \| "pane" \| "full"` — the middle one is **`"pane"`**, not `"normal"` |
| `ModuleId` | M1 T7, declared once | kebab-case, **seven** members: the five spec modules plus `legacy-inspector`, `legacy-server` |
| `ForgeClip.previewAudio` | M5 T10 adds it | **in-memory only, never serialised** (§9.2 unchanged). Read `clip.previewAudio ?? clip.audio` |
| `ForgeClip.downbeats_sec` | M1 T3 | source seconds, unstretched, at `native_bpm` — unlike `start_sec`/`offset_sec`/`dur_sec` |
| `ForgeClip.detune_cents` | M1 T3 | the per-clip detune this milestone reads and writes, through `arrangement.setDetune` |
| `arrangement.targetLane` | **M5 T1 store**, `$state<0\|1\|2\|3\|null>(null)` | **not a `ForgeLane` field.** Written by `setTargetLane`, read by M5 T4's lane header. The writer brief said otherwise and was wrong |
| `SCORE_PLACEHOLDER = "χ —"` | M5 T6's `ClipBox` | the slot Task 10 fills with a real number |
| `dequantiseScaled`, the base64 decoder | **M10 T1** `src/lib/stats/decode.ts` | Task 2 imports them; do not write a second copy |
| `HELP` | M1 T14 | ten chroma-relevant ids exist; nine controls in this milestone have none. See the table below |

---

## Normative names and decisions

Where a task body and this block disagree, **this block wins.**

| decision | the reading this plan ships | why |
|---|---|---|
| `INTERVAL_W`'s index | the **directed, wrapped class distance** `INTERVAL_W[((a - b) % 12 + 12) % 12]`, `a` the frame's class and `b` the target's — *not* `Math.abs(a - b)`, and *not* folded to `min(ic, 12-ic)` | **RESOLVED 2026-09-22 by WINTERMUTE — and this DEPARTS FROM v3 on purpose.** v3 925–937 computes `ic = Math.abs(a - b) % 12` and then `min(ic, 12-ic) === 0 ? 0 : ic`, which only ever forces `ic` to 0 when it already is 0 — so the drawing's own indexing is exactly `Math.abs(a - b)`, the same thing this row overrules. §5.4 names `_matchFrame` as the score's definition, so an implementer who opens v3 to check will find `Math.abs` there and may "fix" the plan back to it unless told plainly that the drawing is the thing being overruled here, not the source of the fix. **The reason is stronger than any one mis-scored pair: `Math.abs(a-b)` is not transposition-invariant, and both the detune scan and the legend anchors depend on it being.** Verified in node: a G-major frame against a C-major target, both transposed together by 0/1/2/5 semitones, scores `0.6511 / 0.6244 / 0.6244 / 0.6400` under `Math.abs` — the same chord pair scoring differently depending only on what key it happens to be in — and a constant `0.6544` under the directed formula at every transposition. The detune scan rotates a frame and compares it to a fixed target across 51 steps; the legend anchors are `matchFrame(rotate(target, k), target)` — both are exactly the shape of computation `Math.abs` gets wrong. Target class 7 (G), frame class 0 (C) is the concrete instance: `Math.abs(7-0)=7` reads `INTERVAL_W[7]=0.90` ("a fifth"), when the ascending distance from G up to C is 5 semitones ("a fourth", `INTERVAL_W[5]=0.82`); the directed formula reproduces both readings correctly depending on which is target and which is frame. The table stays **unfolded** on purpose: it is asymmetric by design (fifth 0.90 vs fourth 0.82, minor second 0.10 vs major seventh 0.22), and folding would erase exactly the asymmetry the anchors are built against. Task 3's code comment carries this same reasoning so the asymmetry does not get "corrected" later. |
| which 12-class fold feeds what | **one array, not two: the server's transported `fold12`**, feeding GLOBAL's display cells, the hover value, `matchFrame`/the scan and the clip score alike | **RESOLVED 2026-09-22 by WINTERMUTE.** §5.4's GLOBAL definition — sum the three bands through `fold_to_12`, then per-frame normalise to max 1 — is exactly what M2 T12's `chroma_payload` computes and transports as `fold12` at `scale: 1.0`; that scale is 1.0 *because* the values are already normalised into [0,1] per frame, not because it is a whole-clip scale. So the client never needs a local re-fold of `bands` for display, and `foldFrameTo12` is deleted (Task 1). **One consequence worth stating once, here:** because `fold12` is normalised per frame, a quiet frame contributes to `meanMatchAtDetune` exactly as strongly as a loud one — intended, since the score measures harmonic agreement rather than energy, but the kind of thing an implementer "corrects" by weighting with band energy. Don't. |
| the B/C fold boundary | the server's **circular-nearest** rule: bin 124 is B, bin 125 is C (boundary at 2.0 + 11.5·(128/12) = 124.67) | client and server must fold identically. Bins **18, 50, 82 and 114** are exact ties and go to the **lower** class, matching numpy's `argmin`; the one-line `Math.round((bin−2)/(128/12))` sends all four the other way and is therefore not usable. There are exactly four: the midpoint between centres *s* and *s+1* is `2 + (2s+1)·16/3`, an integer only when `3 | (2s+1)`, i.e. `s ∈ {1, 4, 7, 10}` |
| C's bin, and the semitone width | C at bin **2.0**; each semitone spans **128/12** bins | §5.4, pinned verbatim |
| chord vocabulary | §5.4's **nine exactly** — `C, Cm, C7, Cmaj7, Cm7, Cdim, Caug, Csus2, Csus4`. `Cmin` returns `null` | the drawing accepts `min`/`min7`/`maj` and has no `sus2`/`sus4`; the spec's list is normative. Trivial to add aliases later |
| chord quality case | **lowercased**, as the drawing does, so `CDIM` works and `CM7` reads as C **minor** 7 | pinned in a test because it is a real ambiguity, not an oversight. **Open question 3** |
| enharmonic roots | letter-semitone + accidental **arithmetic**: `E#`→F, `Cb`→B, `B#m7`→`Cm7` | the drawing's `NOTES.indexOf(letter + "#")` returns −1 for `E#`/`B#` and produces a garbage root. This is a data-layer correction; the drawing is explicitly low-fidelity for data |
| detune scan | cents **−100..100 step 4**, every **3rd** frame; `HIGHEST` = `mean`, `STEADIEST` = `mean − sd` | §5.4, pinned verbatim |
| **how much detune to rotate by — the analysed ref decides** | **`analysisDetuneCents`**, derived once in `ChromaTab.svelte`: **`0`** when the analysed ref was `clip.previewAudio`, **`clip.detune_cents`** when it was `clip.audio`. It is what every consumer receives in place of `clip.detune_cents` — `ChromaHeatmap`'s per-cell hue, `windowScores`, `readHover`, `meanMatchAtDetune`, `scanDetune`. Consequently **the scan strip's ±100 ¢ axis is RELATIVE to the clip's current detune** — the red mark sits at the strip's centre, the label says what the axis is relative to, and **BEST is ADDITIVE**: `setDetune(clip.id, clip.detune_cents + bestDetune(...))`, clamped to ±100 | M5 T10's `runStretch` already pitch-shifts the preview by `clip.detune_cents / 100` (M5:5358), and this plan's own row below pins chroma to the stretched preview. So `chromaClient.result.fold12` is **already** the chroma of detuned audio and rotating it again by `detune_cents / 100` applies the detune twice. v3 did not have this bug because its scan and its chroma both started from the unstretched source. The rotation is still right in the one case where `runStretch` returns early (`clip.native_bpm == null`, so `previewAudio` stays null) — which is exactly what `analysisDetuneCents` encodes, in **one** place, so nothing re-derives the rule. Bare `bestDetune(...)` made pressing BEST twice walk the value instead of converging. **Open question 6** |
| the clip score | `meanMatchAtDetune` over **every** frame at the clip's current detune — deliberately un-strided where the scan strides | §5.4's score is the clip's, not the scan's; the scan may stride because it runs 51 times |
| `/forge/stretch` | debounced **400 ms**; the commit takes **semitones** (`cents / 100`) | §5.4 |
| which request leads on a detune change | **stretch first, chroma second.** Detune arms M5 T10's debounced stretch; chroma re-requests when the stretch lands a new `previewAudio`, not when detune changes | §5.4 computes chroma on the stretched preview, so a chroma request fired on the detune change would analyse the old audio |
| the target lane | `arrangement.targetLane`, not a `ForgeLane` field | verified against M5 T1's store. With no TARGET lane chosen, say so — never render an empty profile as if it were data |
| nine controls ship with **no `data-help`** | the four view buttons (v3 288), MATCH CURVE, the two TARGET-mode buttons (v3 312-313), the twelve piano keys (v3 320), the hover readout (v3 338) | M1 T14's `KEYS` has no id for any of them. Inventing ids would put strings in the table that M1 does not have. **Open question 4** |
| the heatmap's y-axis note labels | **not drawn** | §5.4 says they "use `semitone_bin_centers`"; the data is there and the hover readout names the note, but at 162 px of tab body the drawing itself draws none, and guessing a layout for twelve labels would be inventing UI. **Open question 5** |

### The `data-*` / `data-testid` / `HELP` contract

M6 is the first milestone where most ids genuinely exist, so this table is mostly a restatement —
which is the point. **Every selector a Playwright or component test asserts on appears here; no task
may emit one that is not in this table, and no task may assert one that no task emits.**

| selector | emitted by | `HELP` id |
|---|---|---|
| `[data-region="chroma-tab"]` | T11 | — |
| `[data-region="chroma-heatmap-box"]` | T11 | — |
| `[data-region="chroma-target-row"]` | T9 | — |
| `[data-chroma-view="global"\|"bass"\|"mid"\|"high"]` | T11 | none exists |
| `[data-testid="chroma-curve-toggle"]` | T11 | none exists |
| `[data-testid="chroma-heatmap"]` | T6 | `chromaHeatmap` (v3 344) |
| `[data-testid="chroma-heatmap-empty"]` | T6 | — |
| `[data-testid="chroma-match-curve"]` | T7 | `chromaMatchCurve` (v3 346) |
| `[data-testid="chroma-legend"]`, `[data-legend-stop]`, `[data-legend-tick]` | T7 | `chromaMatchMarks` (v3 292) |
| `[data-testid="chroma-match-readout"]` | T7 | `chromaMatchLegend` (v3 330) |
| `[data-testid="chroma-scan-strip"]` | T8 | `chromaDetuneScan` (v3 332) |
| `[data-testid="chroma-scan-label"]` | T8 | — |
| `[data-testid="chroma-best-criterion"]` | T8 | `chromaBestCriterion` (v3 335) |
| `[data-testid="chroma-best"]` | T8 | `chromaBest` (v3 336) |
| `[data-testid="chroma-target-mode-lane"\|"chroma-target-mode-set"]` | T9 | none exists |
| `[data-chroma-key="0".."11"]` | T9 | none exists |
| `[data-testid="chroma-chord"]`, `[data-testid="chroma-chord-hint"]` | T9 | `chromaChord` (v3 323) **on the input only** |
| `[data-testid="chroma-target-empty"]` | T9 | — |
| `[data-testid="chroma-hover-note"]`, `[data-testid="chroma-hover-detail"]` | T10 | none exists |
| `[data-testid="clip-score"]` | T10, as an edit to M5 T6's `ClipBox` | — |
| `[data-testid="chroma-empty"]`, `[data-testid="chroma-error"]` | T11 | — |

The two lane-level ids this milestone reads but does not own are M1 T14's `laneTarget` and
`clipDetune`, **both on M5's `LaneHeader.svelte`** (M5:2605 and M5:2631 — `clipDetune` sits on the
`bpmClip` detune input ten lines below `laneTarget`, not on the clip box). `ClipBox.svelte` carries
no `data-help` at all.

---

## File structure

| file | what it is |
|---|---|
| `latent-forge/src/lib/chroma/bins.ts` | bin geometry: C at 2.0, 128/12 per semitone, `foldTo12`, `binToPitchClass`, `fold12Column(s)` (T1) |
| `latent-forge/src/lib/chroma/chromaClient.svelte.ts` | `/forge/chroma`, decoded on arrival; `chromaRefKey`, `ChromaShapeError` (T2) |
| `latent-forge/src/lib/chroma/match.ts` | `INTERVAL_W`, `matchFrame`, `rotate`, `anchors` (T3) |
| `latent-forge/src/lib/chroma/target.ts` | `targetProfile`, `setProfile`, `parseChord` (T4) |
| `latent-forge/src/lib/chroma/detuneScan.ts` | `scanDetune`, `bestDetune`, `meanMatchAtDetune` (T5) |
| `latent-forge/src/lib/chroma/consonanceColor.ts` | the ramp — its own `oklch()` string, interpolated per channel (T6) |
| `latent-forge/src/lib/chroma/heatmapGeometry.ts` | frame↔x, row↔y, the target reference row, the zoom/scroll frame window (T6) |
| `latent-forge/src/lib/chroma/matchCurve.ts` | the curve's axis, `windowScores`, the legend's three anchor ticks (T7) |
| `latent-forge/src/lib/chroma/scanStrip.ts` | the 500×30 strip's geometry, the criterion toggle, `centsAtX`/`xForCents` (T8) |
| `latent-forge/src/lib/chroma/targetStore.svelte.ts` | the target row's own store: mode, keys, chord, labels (T9) |
| `latent-forge/src/lib/chroma/hoverReadout.ts` | `readHover`, and the two text lines it produces (T10) |
| `latent-forge/src/lib/chroma/chromaLink.svelte.ts` | the pane↔timeline link: hovered frame, the clip's score (T10) |
| `latent-forge/src/ui/chroma/chromaCanvas.ts` | `chromaColour` with its per-token fallback table, `fitChromaCanvas` (T6) |
| `latent-forge/src/ui/chroma/ChromaHeatmap.svelte` | the heatmap canvas, four view modes (T6) |
| `latent-forge/src/ui/chroma/MatchCurveOverlay.svelte`, `MatchLegend.svelte` | the curve over the heatmap, and the gradient legend (T7) |
| `latent-forge/src/ui/chroma/DetuneScanStrip.svelte` | the scan strip, BEST, the criterion toggle (T8) |
| `latent-forge/src/ui/chroma/TargetRow.svelte` | both target modes, the piano keys, the chord field (T9) |
| `latent-forge/src/ui/chroma/HoverReadout.svelte` | DOM, never `fillText` (T10) |
| `latent-forge/src/ui/chroma/ChromaTab.svelte` | the assembly, the empty states, the stretch debounce (T11) |
| `latent-forge/mock/makeChromaFixture.mjs` | generates `handmade-forge_chroma_render.json` (T11) |
| `latent-forge/tests/chroma.spec.ts` | Playwright (T11) |
| **modified:** `src/ui/shell/BottomPane.svelte`, `src/ui/timeline/ClipBox.svelte`, `src/ui/timeline/LaneCanvas.svelte` | the tab mount, the score label, the hover marker |

---

## Status of this plan

Written **2026-09-22** by FLATLINE, by two writers: Writer A drafted Tasks 1–5 (the math), Writer B
drafted Tasks 6–11 (the pane) **after reading A's output**, which is why no cross-writer count drift
appears in the gates below — unlike M4, whose three writers could not see each other.

**Test counts, all verified mechanically** by counting `it(` blocks at two-space
indent against each task's own stated `Tests N passed (N)` gate:

| task | `it()` | task | `it()` |
|---|---|---|---|
| 1 `bins.ts` | 13 | 7 match curve + legend | 21 |
| 2 `chromaClient.svelte.ts` | 11 | 8 `DetuneScanStrip.svelte` | 22 |
| 3 `match.ts` | 13 | 9 target row | 23 |
| 4 `target.ts` | 14 | 10 hover, cross-link, clip score | 23 |
| 5 `detuneScan.ts` | 13 | 11 tab, fixture, Playwright | 16 |
| 6 heatmap geometry + canvas | 39 | | |

**208 `it()` blocks across eleven tasks.** 215 after the 2026-09-22 critic pass (itself four more
than the 211 of first assembly: the reversible middle-drag in Task 6's
`ChromaHeatmap.component.test.ts`, `frameColumn` in its `heatmapGeometry.test.ts`, and, from the
blocking detune-applied-twice finding, the relative scan axis in Task 5's `detuneScan.test.ts` and a
stretched clip with a non-zero detune in Task 11's `ChromaTab.component.test.ts`). WINTERMUTE's three
2026-09-22 rulings then net **-7**: Task 1 loses `foldFrameTo12`'s five tests (18 → 13, Fix 2), and
Task 11 loses the two tests a raw grep of its plan text used to double-count from the
before/after of an M1 `plugin.test.ts` edit that no longer happens (18 → 16, Fix 3) — Task 11's own
test files are unchanged at 12 + 4. Tasks 3, 5 and 6 keep the same `it()` COUNT under Fix 1 (the
directed-distance correction) but change several of those tests' hardcoded expected values, each
recomputed by hand against the corrected formula in place, in the task body below. The same critic
pass **changed** rather than
added tests in Tasks 6, 7, 8, 10 and 11 — the canvas fallback table, the strip's relative axis and
additive BEST, and `await tick()` in place of `await Promise.resolve()`. See Open question 6.

**Reviewed twice, findings applied both times**, then reconciled against WINTERMUTE's three rulings
above. The first pass returned 2 findings (0 blocking); a second pass over the same file returned 17
(5 blocking) — see "Critic pass" below for the full account of both, including why a single clean
pass should not have been trusted on its own. Every milestone's critic pass so far has returned
findings — 17, 32, 49, 2, then 17 across five rounds — and none has come back empty on a first honest
look, which is itself the reason a second pass ran here.

---

### Task 1: `src/lib/chroma/bins.ts` — the bin geometry, pure

Spec §5.4. Every other task in this milestone stands on the same three facts: pitch class C sits at
**bin 2.0**, each semitone spans **128/12** bins, and the y-axis note labels come from
`semitone_bin_centers` (the `same_chroma` PITFALL — a fold that assumes C at bin 0 is wrong by two
bins everywhere and nothing downstream will tell you). This module is pure and imports nothing, so
vitest pins the exact geometry without a canvas, a store or a network. It also owns the two
**C-order layout rules** the transport imposes — `bands` is `[3,128,T]` and `fold12` is `[12,T]`,
both with **T as the fastest-varying axis** — because Tasks 2, 4 and 5 all index into those flat
arrays and a plan that states the rule once cannot let two tasks disagree about it.

**Files:**
- Create: `latent-forge/src/lib/chroma/bins.ts`, `latent-forge/src/lib/chroma/__tests__/bins.test.ts`

**Interfaces:**
- Consumes: nothing. This module imports no other module in the project.
- Produces, from `latent-forge/src/lib/chroma/bins.ts`:
  `BINS_PER_BAND = 128`; `BANDS = 3`; `BINS_PER_SEMITONE = 128 / 12`; `C_BIN = 2.0`;
  `NOTE_NAMES: readonly string[]` (the twelve, sharp spellings, C first);
  `semitoneBinCenters(): number[]` (12 entries, a fresh array each call, C at 2.0, spaced 128/12,
  wrapped into `[0, 128)`);
  `binToPitchClass(bin: number, binsPerBand?: number): number` (nearest semitone centre by
  **circular** distance, ties to the lower class);
  `pitchClassToBin(pitchClass: number, binsPerBand?: number): number` (its inverse — the class's
  exact centre);
  `foldTo12(band: Float32Array, binsPerBand?: number): Float32Array` (one frame of 128 bins → 12
  classes, **summed** into the nearest centre, matching the server's `fold_to_12`);
  `fold12Column(fold12: Float32Array, T: number, frame: number): Float32Array` and
  `fold12Columns(fold12: Float32Array, T: number): Float32Array[]` (one frame / every frame of the
  server's `[12,T]` C-order fold, `class p, frame t = fold12[p*T + t]`).

- [ ] **Step 1: Write the failing test**

`latent-forge/src/lib/chroma/__tests__/bins.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import {
  BANDS,
  BINS_PER_BAND,
  BINS_PER_SEMITONE,
  C_BIN,
  NOTE_NAMES,
  binToPitchClass,
  fold12Column,
  fold12Columns,
  foldTo12,
  pitchClassToBin,
  semitoneBinCenters,
} from "../bins";

describe("the bin geometry spec §5.4 pins", () => {
  it("is 128 bins per band, 3 bands, 128/12 bins per semitone, C at bin 2.0", () => {
    expect(BINS_PER_BAND).toBe(128);
    expect(BANDS).toBe(3);
    expect(BINS_PER_SEMITONE).toBe(128 / 12);
    expect(BINS_PER_SEMITONE).toBeCloseTo(10.666666666666666, 12);
    expect(C_BIN).toBe(2.0);
  });

  it("puts C at bin 2.0 and A at 98, with twelve centres all inside the band", () => {
    const c = semitoneBinCenters();
    expect(c).toHaveLength(12);
    expect(c[0]).toBe(2.0);      // C
    expect(c[3]).toBe(34.0);     // D#
    expect(c[6]).toBe(66.0);     // F#
    expect(c[9]).toBe(98.0);     // A
    for (const v of c) {
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThan(BINS_PER_BAND);
    }
    // A fresh array every call: a caller may not mutate the module's own table.
    expect(semitoneBinCenters()).not.toBe(c);
  });

  it("spaces the centres 128/12 apart, C# at 12.667 and B at 119.333", () => {
    const c = semitoneBinCenters();
    for (let s = 1; s < 12; s++) {
      expect(c[s] - c[s - 1]).toBeCloseTo(BINS_PER_SEMITONE, 10);
    }
    expect(c[1]).toBeCloseTo(12.666666666666666, 10);
    expect(c[11]).toBeCloseTo(119.33333333333333, 10);
  });

  it("names the twelve pitch classes with sharp spellings, C first", () => {
    expect(NOTE_NAMES).toEqual(["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]);
  });
});

describe("binToPitchClass and its inverse", () => {
  it("maps every centre back to its own pitch class", () => {
    const c = semitoneBinCenters();
    for (let s = 0; s < 12; s++) expect(binToPitchClass(c[s])).toBe(s);
  });

  it("round-trips pitchClassToBin -> binToPitchClass for all twelve classes", () => {
    const c = semitoneBinCenters();
    for (let s = 0; s < 12; s++) {
      expect(pitchClassToBin(s)).toBe(c[s]);
      expect(binToPitchClass(pitchClassToBin(s))).toBe(s);
    }
  });

  it("folds bin 2.0 to class 0, and bin 0 with it", () => {
    expect(binToPitchClass(2.0)).toBe(0);
    expect(binToPitchClass(0)).toBe(0);
    expect(binToPitchClass(7)).toBe(0);      // still inside C's half-semitone
    expect(binToPitchClass(8)).toBe(1);      // 7.333 is the C/C# boundary
  });

  it("wraps at the top of the band: the boundary is 124.667, so 124 is B and 125..127 are C again", () => {
    // B's centre is 119.333; C's next centre is 2.0 + 128 = 130. The midpoint
    // is 2.0 + 11.5*(128/12) = 124.6667, so every bin above it is nearer to C
    // going UP over the top of the band than to B going down.
    expect(2.0 + 11.5 * (128 / 12)).toBeCloseTo(124.66666666666667, 10);
    expect(binToPitchClass(124)).toBe(11);
    expect(binToPitchClass(125)).toBe(0);
    expect(binToPitchClass(126)).toBe(0);
    expect(binToPitchClass(127)).toBe(0);
  });

  it("breaks an exact tie to the LOWER pitch class, as the reference fold_to_12's argmin does", () => {
    // Bins 18, 50, 82 and 114 are the only four of the 128 that sit exactly halfway
    // between two centres (5.3333 from each). numpy's argmin keeps the first,
    // so they belong to C# and G -- Math.round() would send both the other way.
    expect(binToPitchClass(18)).toBe(1);
    expect(binToPitchClass(82)).toBe(7);
    expect(Math.round((18 - C_BIN) / BINS_PER_SEMITONE)).toBe(2);   // the trap
    expect(Math.round((82 - C_BIN) / BINS_PER_SEMITONE)).toBe(8);   // the trap
  });
});

describe("foldTo12 — one band of 128 bins to 12 classes", () => {
  it("sums each bin into its nearest class: an all-ones band folds to the per-class bin counts", () => {
    const band = new Float32Array(128).fill(1);
    const out = foldTo12(band);
    expect(Array.from(out)).toEqual([11, 11, 10, 11, 11, 10, 11, 11, 10, 11, 11, 10]);
    expect(Array.from(out).reduce((a, b) => a + b, 0)).toBe(128);
  });

  it("puts a single hot bin entirely in one class", () => {
    const band = new Float32Array(128);
    band[66] = 0.5;                                   // F#'s centre
    const out = foldTo12(band);
    expect(out[6]).toBeCloseTo(0.5, 6);
    expect(Array.from(out).filter((v) => v !== 0)).toHaveLength(1);
  });

  it("throws when the band is not binsPerBand long", () => {
    expect(() => foldTo12(new Float32Array(127))).toThrow(/expected 128 bins/);
  });
});

describe("fold12Column / fold12Columns — the server's [12,T] fold", () => {
  it("reads class p, frame t as fold12[p*T + t]", () => {
    const T = 3;
    const fold12 = new Float32Array(12 * T);
    for (let p = 0; p < 12; p++) for (let t = 0; t < T; t++) fold12[p * T + t] = p + t / 10;
    const col1 = fold12Column(fold12, T, 1);
    expect(col1).toHaveLength(12);
    expect(col1[0]).toBeCloseTo(0.1, 6);
    expect(col1[11]).toBeCloseTo(11.1, 6);
    const cols = fold12Columns(fold12, T);
    expect(cols).toHaveLength(3);
    expect(Array.from(cols[2])).toEqual(Array.from(fold12Column(fold12, T, 2)));
    expect(() => fold12Column(fold12, T, 3)).toThrow(/frame 3 out of range/);
  });
});
```

- [ ] **Step 2: Run it, expect failure**

```bash
cd latent-forge && npx vitest run src/lib/chroma/__tests__/bins.test.ts
```

Expected: `Failed to resolve import "../bins"`.

- [ ] **Step 3: Write the module**

`latent-forge/src/lib/chroma/bins.ts`:

```ts
// SAME chroma bin geometry (spec §5.4). Three octave-band chromagrams of 128
// bins each; pitch class C sits at bin 2.0, not bin 0, and each semitone spans
// 128/12 = 10.666... bins (the `same_chroma` PITFALL). Everything here mirrors
// the server's own harmonic/same_chroma.py so the client and the server agree
// bin for bin:
//
//   centre(s) = (128*(s+3)/12 - 3*floor(128/12)) mod 128   -> C = 2.0, A = 98.0
//   fold_to_12 SUMS each fine bin into its nearest centre by CIRCULAR distance
//
// Pure: no canvas, no store, no network, so vitest pins the numbers directly.

export const BINS_PER_BAND = 128;
export const BANDS = 3;
export const BINS_PER_SEMITONE = BINS_PER_BAND / 12;
export const C_BIN = 2.0;

/** Sharp spellings, C first -- the y-axis labels and the hover readout (§5.4). */
export const NOTE_NAMES: readonly string[] = [
  "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B",
];

function mod(x: number, n: number): number {
  return ((x % n) + n) % n;
}

const centreCache = new Map<number, readonly number[]>();

function centresFor(binsPerBand: number): readonly number[] {
  const hit = centreCache.get(binsPerBand);
  if (hit) return hit;
  const out: number[] = [];
  for (let s = 0; s < 12; s++) {
    // The server's exact expression, kept verbatim: base_c's integer roll is
    // what puts C at 2.0 rather than 0.0 for a 128-bin band.
    out.push(mod((binsPerBand * (s + 3)) / 12 - 3 * Math.floor(binsPerBand / 12), binsPerBand));
  }
  centreCache.set(binsPerBand, out);
  return out;
}

const assignCache = new Map<number, readonly number[]>();

/** bin -> nearest semitone centre, by circular distance, ties to the lower class. */
function assignmentFor(binsPerBand: number): readonly number[] {
  const hit = assignCache.get(binsPerBand);
  if (hit) return hit;
  const out: number[] = [];
  for (let b = 0; b < binsPerBand; b++) out.push(binToPitchClass(b, binsPerBand));
  assignCache.set(binsPerBand, out);
  return out;
}

/** The twelve semitone centres, C..B, in bins. A fresh array each call. */
export function semitoneBinCenters(): number[] {
  return [...centresFor(BINS_PER_BAND)];
}

/**
 * Nearest pitch class for a (possibly fractional) bin index, by CIRCULAR
 * distance -- the band wraps, so bin 125 is nearer to C's centre at 2.0 (going
 * up over the top: 128 - 123 = 5) than to B's at 119.333 (5.667). The boundary
 * is 2.0 + 11.5*(128/12) = 124.667.
 *
 * Ties break to the LOWER class because the comparison is strict `<`, which is
 * what numpy's argmin does in the server's fold_to_12. Bins 18, 50, 82 and 114
 * are the only exact ties -- the midpoint between centres s and s+1 is
 * 2 + (2s+1)*16/3, an integer only when 3 divides (2s+1), i.e. s in {1,4,7,10}
 * -- and Math.round() on (bin - 2)/(128/12) sends all four the other
 * way -- hence this loop rather than the one-line formula.
 */
export function binToPitchClass(bin: number, binsPerBand: number = BINS_PER_BAND): number {
  const centres = centresFor(binsPerBand);
  let best = Infinity;
  let bestClass = 0;
  for (let s = 0; s < 12; s++) {
    const raw = Math.abs(bin - centres[s]);
    const d = Math.min(raw, binsPerBand - raw);
    if (d < best) {
      best = d;
      bestClass = s;
    }
  }
  return bestClass;
}

/** The inverse: a pitch class's exact bin centre (fractional for most classes). */
export function pitchClassToBin(pitchClass: number, binsPerBand: number = BINS_PER_BAND): number {
  return centresFor(binsPerBand)[mod(Math.trunc(pitchClass), 12)];
}

/**
 * Fold one band's 128 bins onto 12 classes by SUMMING each bin into its
 * nearest centre -- the server's fold_to_12, not a mean and not a max.
 */
export function foldTo12(band: Float32Array, binsPerBand: number = BINS_PER_BAND): Float32Array {
  if (band.length !== binsPerBand) {
    throw new RangeError(`foldTo12: expected ${binsPerBand} bins, got ${band.length}`);
  }
  const assign = assignmentFor(binsPerBand);
  const out = new Float32Array(12);
  for (let b = 0; b < binsPerBand; b++) out[assign[b]] += band[b];
  return out;
}

/**
 * One frame of the server's own 12-class fold, which arrives as [12,T] in C
 * order, T fastest: class p, frame t = fold12[p*T + t]. Transposed from the
 * shape a caller intuitively wants, so it lives here once rather than in each
 * of the three places that need a column.
 *
 * This is ALSO the GLOBAL view's own array (§5.4's "sum the three bands
 * through fold_to_12, then per-frame normalise to max 1" is exactly what the
 * server computes and transports here — M2 T12's `chroma_payload` ships it at
 * `scale: 1.0` because the values are already in [0,1] per frame, not because
 * 1.0 is a whole-clip scale). There is no separate client-side fold: the
 * display, the match score, the detune scan and the clip score all read this
 * one array. See the plan's Normative table, "which 12-class fold feeds
 * what" — this used to be two arrays (`foldFrameTo12` locally re-folded
 * `bands` for the display) and WINTERMUTE's 2026-09-22 ruling collapsed that
 * to the one below.
 */
export function fold12Column(fold12: Float32Array, T: number, frame: number): Float32Array {
  if (fold12.length !== 12 * T) {
    throw new RangeError(`fold12Column: expected ${12 * T} values for [12,${T}], got ${fold12.length}`);
  }
  if (frame < 0 || frame >= T) {
    throw new RangeError(`fold12Column: frame ${frame} out of range for T=${T}`);
  }
  const out = new Float32Array(12);
  for (let p = 0; p < 12; p++) out[p] = fold12[p * T + frame];
  return out;
}

/** Every frame of a [12,T] fold, in order. */
export function fold12Columns(fold12: Float32Array, T: number): Float32Array[] {
  const out: Float32Array[] = [];
  for (let t = 0; t < T; t++) out.push(fold12Column(fold12, T, t));
  return out;
}
```

- [ ] **Step 4: Run it, expect pass**

```bash
cd latent-forge && npx vitest run src/lib/chroma/__tests__/bins.test.ts && npm run check
```

Expected: `Test Files  1 passed (1)` / `Tests  13 passed (13)`, and
`svelte-check found 0 errors and 0 warnings`.

- [ ] **Step 5: Commit**

```bash
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M6 T1: chroma/bins.ts -- C at bin 2.0, 128/12 per semitone, circular-nearest fold_to_12, [3,128,T] and [12,T] C-order accessors"
```

---

### Task 2: `src/lib/chroma/chromaClient.svelte.ts` — `/forge/chroma`, decoded on arrival

Spec §6.3 and §5.4. The heatmap, the match curve, the detune scan and the clip score label all read
the same analysis of the same clip, so this is a singleton with one current result — components
subscribe to it rather than each fetching a copy. Decoding happens here, on arrival, so no
component downstream ever sees base64 or a raw quantised byte, and it reuses M10 Task 1's
`decodeBase64` + `dequantiseScaled` rather than writing a second decoder.

**The quantisation trap this task exists to get right:** `bands` carries **three** scales, one per
band, each applied to that band's own `128*T` slice of the byte stream; `fold12` carries **one**
scale for the whole array. Applying `scale[0]` to all three bands silently mis-scales two thirds of
the data and nothing downstream can detect it — the heatmap just looks plausible and wrong.

**Files:**
- Create: `latent-forge/src/lib/chroma/chromaClient.svelte.ts`,
  `latent-forge/src/lib/chroma/__tests__/chromaClient.test.ts`

**Interfaces:**
- Consumes `AudioRef` from `latent-forge/src/lib/forge/types.ts` (M1 T3), exactly:
  `type AudioRef = {kind:"upload"; sha256:string} | {kind:"render"; job_id:string; file:string} | {kind:"crop"; crop_id:string} | {kind:"file"; root:string; rel:string} | {kind:"path"; path:string}`.
- Consumes `forgeApi` and `ForgeApiError` from `latent-forge/src/lib/forge/api.ts` (M1 T5).
  Verified against §6.3 — the declared shape and the route match the contract field for field, so
  this task calls it rather than bypassing it:
  `forgeApi.chroma: (audio: AudioRef) => Promise<{ok: true; frames: number; fps: number; bands: {shape: [number, number, number]; scale: [number, number, number]; data_b64: string}; fold12: {shape: [number, number]; scale: number; data_b64: string}}>`
  (it POSTs `{audio}` to `/forge/chroma`); `class ForgeApiError extends Error { status: number; message: string }`.
- Consumes `decodeBase64(b64: string): Uint8Array` and
  `dequantiseScaled(bytes: Uint8Array, scale: number): Float32Array` (`byte/255·scale`) from
  `latent-forge/src/lib/stats/decode.ts` (**M10 T1** — built there deliberately for M6 to reuse;
  do not write a second one).
- Consumes `BANDS = 3` and `BINS_PER_BAND = 128` from `./bins` (this milestone's Task 1).
- Produces, from `latent-forge/src/lib/chroma/chromaClient.svelte.ts`:
  `interface ChromaResult { frames: number; fps: number; bands: Float32Array /* 3*128*T, C-order */; fold12: Float32Array /* 12*T, C-order */; T: number }`;
  `class ChromaShapeError extends Error`;
  `chromaRefKey(ref: AudioRef): string` (the cache key, field-order independent);
  `class ChromaClient` with `$state` fields `result`, `pending`, `error` and methods
  `request(audio: AudioRef): Promise<void>`, `flush(): Promise<void>`, `dispose(): void`;
  the singleton `export const chromaClient = new ChromaClient()`.

- [ ] **Step 1: Write the failing test**

`latent-forge/src/lib/chroma/__tests__/chromaClient.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AudioRef } from "../../forge/types";
import { ChromaClient, chromaClient, chromaRefKey } from "../chromaClient.svelte";

const REF: AudioRef = { kind: "crop", crop_id: "000412" };

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function b64(bytes: Uint8Array): string {
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s);
}

/** A well-formed §6.3 body: band b is filled with the constant byte 50*(b+1),
 *  fold12 class p frame t with the byte p*10 + t. */
function chromaBody(T: number, scales: [number, number, number] = [1, 2, 4]) {
  const bandBytes = new Uint8Array(3 * 128 * T);
  for (let band = 0; band < 3; band++) {
    bandBytes.fill(50 * (band + 1), band * 128 * T, (band + 1) * 128 * T);
  }
  const foldBytes = new Uint8Array(12 * T);
  for (let p = 0; p < 12; p++) for (let t = 0; t < T; t++) foldBytes[p * T + t] = p * 10 + t;
  return {
    ok: true,
    frames: T,
    fps: 10.7666015625,
    bands: { shape: [3, 128, T], scale: scales, data_b64: b64(bandBytes) },
    fold12: { shape: [12, T], scale: 1.0, data_b64: b64(foldBytes) },
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  chromaClient.dispose();
});

describe("request decodes the §6.3 payload on arrival", () => {
  it("applies ONE SCALE PER BAND to that band's own slice of the byte stream", () => {
    // The whole reason this task exists: bands has three scales, fold12 has one.
    const client = new ChromaClient();
    const T = 2;
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse(chromaBody(T, [1, 2, 4]))));

    return client.request(REF).then(() => {
      const bands = client.result!.bands;
      expect(bands).toBeInstanceOf(Float32Array);
      expect(bands.length).toBe(3 * 128 * T);
      // band 0: byte 50, scale 1 ; band 1: byte 100, scale 2 ; band 2: byte 150, scale 4
      expect(bands[0]).toBe(Math.fround((50 / 255) * 1));
      expect(bands[128 * T]).toBe(Math.fround((100 / 255) * 2));
      expect(bands[2 * 128 * T]).toBe(Math.fround((150 / 255) * 4));
      // and the LAST value of each slice, not just the first
      expect(bands[128 * T - 1]).toBe(Math.fround((50 / 255) * 1));
      expect(bands[2 * 128 * T - 1]).toBe(Math.fround((100 / 255) * 2));
      expect(bands[3 * 128 * T - 1]).toBe(Math.fround((150 / 255) * 4));
    });
  });

  it("applies the single fold12 scale and keeps the [12,T] C-order layout", async () => {
    const client = new ChromaClient();
    const T = 2;
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse(chromaBody(T))));

    await client.request(REF);

    const fold12 = client.result!.fold12;
    expect(fold12.length).toBe(12 * T);
    expect(fold12[0 * T + 0]).toBe(Math.fround((0 / 255) * 1.0));
    expect(fold12[7 * T + 1]).toBe(Math.fround((71 / 255) * 1.0));
    expect(fold12[11 * T + 1]).toBe(Math.fround((111 / 255) * 1.0));
  });

  it("carries frames, fps and T, toggles pending, and POSTs {audio} to /forge/chroma", async () => {
    const client = new ChromaClient();
    const fetchMock = vi.fn(async () => jsonResponse(chromaBody(3)));
    vi.stubGlobal("fetch", fetchMock);

    const p = client.request(REF);
    expect(client.pending).toBe(true);
    await p;

    expect(client.pending).toBe(false);
    expect(client.error).toBeNull();
    expect(client.result?.frames).toBe(3);
    expect(client.result?.T).toBe(3);
    expect(client.result?.fps).toBe(10.7666015625);
    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe("/forge/chroma");
    expect((init as RequestInit).method).toBe("POST");
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({ audio: REF });
  });

  it("surfaces a server error (§9.7) and leaves result null and pending false", async () => {
    const client = new ChromaClient();
    vi.stubGlobal("fetch", async () => jsonResponse({ ok: false, error: "no such crop" }, 404));

    await client.request(REF);

    expect(client.pending).toBe(false);
    expect(client.result).toBeNull();
    expect(client.error).toBe("no such crop");
  });

  it("reports a byte count that does not match [3,128,T] rather than mis-slicing it", async () => {
    const client = new ChromaClient();
    const body = chromaBody(2);
    body.bands.data_b64 = b64(new Uint8Array(3 * 128 * 2 - 1));
    vi.stubGlobal("fetch", async () => jsonResponse(body));

    await client.request(REF);

    expect(client.result).toBeNull();
    expect(client.error).toMatch(/expected 768 bytes/);
  });
});

describe("the per-AudioRef cache", () => {
  it("serves a repeat request for the same ref without a round trip", async () => {
    const client = new ChromaClient();
    const fetchMock = vi.fn(async () => jsonResponse(chromaBody(2)));
    vi.stubGlobal("fetch", fetchMock);

    await client.request(REF);
    const first = client.result;
    await client.request({ kind: "crop", crop_id: "000412" });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(client.result).toBe(first);
    expect(client.pending).toBe(false);
  });

  it("keys on the ref's contents, not on the key order of the object literal", async () => {
    const client = new ChromaClient();
    const fetchMock = vi.fn(async () => jsonResponse(chromaBody(2)));
    vi.stubGlobal("fetch", fetchMock);

    const a: AudioRef = { kind: "file", root: "crops", rel: "a/b.wav" };
    const b = { rel: "a/b.wav", root: "crops", kind: "file" } as AudioRef;
    expect(chromaRefKey(a)).toBe(chromaRefKey(b));

    await client.request(a);
    await client.request(b);

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("fetches again for a different ref", async () => {
    const client = new ChromaClient();
    const fetchMock = vi.fn(async () => jsonResponse(chromaBody(2)));
    vi.stubGlobal("fetch", fetchMock);

    await client.request(REF);
    await client.request({ kind: "crop", crop_id: "000413" });

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});

describe("supersession, flush and dispose", () => {
  it("discards a superseded result even if it resolves after the latest one", async () => {
    const client = new ChromaClient();
    let resolveFirst!: (v: Response) => void;
    let resolveSecond!: (v: Response) => void;
    const first = new Promise<Response>((r) => (resolveFirst = r));
    const second = new Promise<Response>((r) => (resolveSecond = r));
    let call = 0;
    vi.stubGlobal("fetch", vi.fn(async () => (call++ === 0 ? first : second)));

    const p1 = client.request({ kind: "crop", crop_id: "a" });
    const p2 = client.request({ kind: "crop", crop_id: "b" });

    resolveSecond(jsonResponse(chromaBody(5)));
    await p2;
    resolveFirst(jsonResponse(chromaBody(9)));
    await p1;

    expect(client.result?.frames).toBe(5);
    expect(client.pending).toBe(false);
    expect(client.error).toBeNull();
  });

  it("flush() resolves once the in-flight request has settled", async () => {
    const client = new ChromaClient();
    let resolveFetch!: (v: Response) => void;
    const pendingFetch = new Promise<Response>((r) => (resolveFetch = r));
    vi.stubGlobal("fetch", vi.fn(async () => pendingFetch));

    void client.request(REF);
    expect(client.pending).toBe(true);

    const flushed = client.flush();
    resolveFetch(jsonResponse(chromaBody(1)));
    await flushed;

    expect(client.pending).toBe(false);
    expect(client.result?.frames).toBe(1);
  });

  it("dispose() never hangs the caller and clears the cache the singleton would otherwise keep", async () => {
    // A singleton's cache outlives a component unmount: without this reset, the
    // next test would read the previous one's result and pass for the wrong reason.
    const never = new Promise<Response>(() => {});
    vi.stubGlobal("fetch", vi.fn(async () => never));
    const p = chromaClient.request(REF);
    chromaClient.dispose();
    await expect(p).resolves.toBeUndefined();
    expect(chromaClient.result).toBeNull();
    expect(chromaClient.pending).toBe(false);
    expect(chromaClient.error).toBeNull();

    vi.unstubAllGlobals();
    const fetchMock = vi.fn(async () => jsonResponse(chromaBody(2)));
    vi.stubGlobal("fetch", fetchMock);
    await chromaClient.request(REF);
    expect(fetchMock).toHaveBeenCalledTimes(1);   // the cache really was cleared
  });
});
```

- [ ] **Step 2: Run it, expect failure**

```bash
cd latent-forge && npx vitest run src/lib/chroma/__tests__/chromaClient.test.ts
```

Expected: `Failed to resolve import "../chromaClient.svelte"`.

- [ ] **Step 3: Write the client**

`latent-forge/src/lib/chroma/chromaClient.svelte.ts`:

```ts
// The chroma data layer (spec §6.3, §5.4): POST /forge/chroma, decoded on
// arrival so no component ever sees base64 or a raw quantised byte.
//
// THE QUANTISATION IS NOT UNIFORM. §6.3 dequantises every byte as
// byte/255*scale, but `bands` carries THREE scales -- one per band, applied to
// that band's own 128*T slice of the C-order stream -- while `fold12` carries
// exactly one for the whole array. Using scale[0] everywhere mis-scales two
// thirds of the data and looks entirely plausible on screen.
//
// Singleton: the heatmap, the match curve, the scan strip and the clip score
// label are separate components reading the same analysis of the same clip.
// It also keeps a per-AudioRef cache. The server caches on the audio file's
// sha256, but the pane re-reads on every selection change and a cache miss
// still costs a round trip, so the decoded result is kept here too.
//
// Two traps, both paid for elsewhere in this project:
//  1. An "abort" listener added after its signal has already fired never runs,
//     so every abort path checks `signal.aborted` FIRST. Without it the
//     promise never settles and the test hangs green.
//  2. A singleton's cache outlives a component unmount -- and a test file.
//     Every test must vary its input or call dispose().

import { forgeApi, ForgeApiError } from "../forge/api";
import type { AudioRef } from "../forge/types";
import { decodeBase64, dequantiseScaled } from "../stats/decode";
import { BANDS, BINS_PER_BAND } from "./bins";

export interface ChromaResult {
  /** T, the number of latent frames the server analysed. */
  frames: number;
  /** 10.7666015625 = 44100/4096 (spec §6.3). */
  fps: number;
  /** 3*128*T, C order: value(band, bin, frame) = bands[(band*128 + bin)*T + frame]. */
  bands: Float32Array;
  /** 12*T, C order: value(class, frame) = fold12[class*T + frame]. */
  fold12: Float32Array;
  /** Same as `frames`; named T because every geometry expression uses it that way. */
  T: number;
}

export class ChromaShapeError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ChromaShapeError";
  }
}

type ChromaResponse = {
  ok: true;
  frames: number;
  fps: number;
  bands: { shape: [number, number, number]; scale: [number, number, number]; data_b64: string };
  fold12: { shape: [number, number]; scale: number; data_b64: string };
};

/**
 * A stable cache key for any AudioRef (spec §6.1's five kinds). Built from the
 * fields rather than JSON.stringify, whose output depends on the order the
 * caller happened to write the object literal in.
 */
export function chromaRefKey(ref: AudioRef): string {
  switch (ref.kind) {
    case "upload": return `upload:${ref.sha256}`;
    case "render": return `render:${ref.job_id}:${ref.file}`;
    case "crop":   return `crop:${ref.crop_id}`;
    case "file":   return `file:${ref.root}:${ref.rel}`;
    case "path":   return `path:${ref.path}`;
  }
}

function decodeChroma(res: ChromaResponse): ChromaResult {
  const T = res.frames;
  const [nBands, nBins, tBands] = res.bands.shape;
  const [nClasses, tFold] = res.fold12.shape;
  if (nBands !== BANDS || nBins !== BINS_PER_BAND || tBands !== T || nClasses !== 12 || tFold !== T) {
    throw new ChromaShapeError(
      `chroma: expected bands [3,128,${T}] and fold12 [12,${T}], got [${res.bands.shape}] and [${res.fold12.shape}]`,
    );
  }

  const bandBytes = decodeBase64(res.bands.data_b64);
  const per = BINS_PER_BAND * T;
  if (bandBytes.length !== BANDS * per) {
    throw new ChromaShapeError(
      `chroma: expected ${BANDS * per} bytes for bands [3,128,${T}], got ${bandBytes.length}`,
    );
  }
  // One scale per band, each applied to that band's own slice. dequantiseScaled
  // is M10 T1's -- built there for exactly this reuse.
  const bands = new Float32Array(BANDS * per);
  for (let b = 0; b < BANDS; b++) {
    bands.set(dequantiseScaled(bandBytes.subarray(b * per, (b + 1) * per), res.bands.scale[b]), b * per);
  }

  const foldBytes = decodeBase64(res.fold12.data_b64);
  if (foldBytes.length !== 12 * T) {
    throw new ChromaShapeError(
      `chroma: expected ${12 * T} bytes for fold12 [12,${T}], got ${foldBytes.length}`,
    );
  }
  const fold12 = dequantiseScaled(foldBytes, res.fold12.scale);

  return { frames: T, fps: res.fps, bands, fold12, T };
}

/**
 * signal-aware wrapper around a promise forgeApi cannot itself cancel (none of
 * its methods takes an AbortSignal). The underlying fetch keeps running; its
 * result is discarded by the `signal.aborted` guards below.
 */
function raceAbort<T>(promise: Promise<T>, signal: AbortSignal): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    // Check FIRST -- a listener added after the signal fired never runs.
    if (signal.aborted) {
      reject(new DOMException("chroma request superseded", "AbortError"));
      return;
    }
    const onAbort = () => reject(new DOMException("chroma request superseded", "AbortError"));
    signal.addEventListener("abort", onAbort, { once: true });
    promise.then(
      (v) => { signal.removeEventListener("abort", onAbort); resolve(v); },
      (e) => { signal.removeEventListener("abort", onAbort); reject(e); },
    );
  });
}

function errorMessage(err: unknown): string {
  if (err instanceof ForgeApiError) return err.message;
  if (err instanceof ChromaShapeError) return err.message;
  return String(err);
}

export class ChromaClient {
  result = $state<ChromaResult | null>(null);
  pending = $state(false);
  error = $state<string | null>(null);

  #controller: AbortController | null = null;
  #inFlight: Promise<void> | null = null;
  #cache = new Map<string, ChromaResult>();

  /**
   * Analyse one clip's audio. §5.4: the caller passes the clip's STRETCHED
   * preview audio (`ForgeClip.previewAudio ?? ForgeClip.audio`), not the raw
   * source, so the chroma matches what the timeline plays.
   */
  request(audio: AudioRef): Promise<void> {
    const key = chromaRefKey(audio);
    const cached = this.#cache.get(key);
    if (cached) {
      this.#controller?.abort();       // a cache hit supersedes anything in flight
      this.#controller = null;
      this.result = cached;
      this.pending = false;
      this.error = null;
      return Promise.resolve();
    }

    this.#controller?.abort();
    const controller = new AbortController();
    this.#controller = controller;
    this.pending = true;
    this.error = null;

    const run = (async () => {
      try {
        const res = await raceAbort(forgeApi.chroma(audio), controller.signal);
        if (controller.signal.aborted) return;   // superseded while in flight
        const decoded = decodeChroma(res as ChromaResponse);
        this.#cache.set(key, decoded);
        this.result = decoded;
      } catch (err) {
        if (controller.signal.aborted) return;
        this.error = errorMessage(err);
      } finally {
        if (this.#controller === controller) {
          this.pending = false;
          this.#controller = null;
        }
      }
    })();
    this.#inFlight = run;
    return run;
  }

  /** Await whatever is in flight. Used by tests and by a caller that needs
   *  `result` settled before it reads it. */
  async flush(): Promise<void> {
    if (this.#inFlight) await this.#inFlight;
  }

  /** Abort anything in flight, clear every field AND the cache. Required
   *  between tests that reuse the singleton, and on leaving the tab. */
  dispose(): void {
    this.#controller?.abort();
    this.#controller = null;
    this.#inFlight = null;
    this.#cache.clear();
    this.result = null;
    this.pending = false;
    this.error = null;
  }
}

/** One client for the whole CHROMA tab (spec §4.5, §5.4). */
export const chromaClient = new ChromaClient();
```

- [ ] **Step 4: Run it, expect pass**

```bash
cd latent-forge && npx vitest run src/lib/chroma/__tests__/chromaClient.test.ts && npm run check
```

Expected: `Test Files  1 passed (1)` / `Tests  11 passed (11)`, and
`svelte-check found 0 errors and 0 warnings`.

- [ ] **Step 5: Commit**

```bash
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M6 T2: chromaClient.svelte.ts -- /forge/chroma singleton, three band scales vs one fold12 scale, per-AudioRef cache, abort-safe"
```

---

### Task 3: `src/lib/chroma/match.ts` — the harmonic-overlap score, pure

Spec §5.4 (`_matchFrame`, v3 925–937; `_rotate`, v3 895–903; `_anchors`, v3 913–922). The score is
not a dot product: every pair of active pitch classes contributes its interval weight, so a fifth
scores high and a semitone low even though the semitone is closer in pitch. Three numbers are
pinned by the spec and must be copied, not re-derived — the twelve `INTERVAL_W` weights, the 0.08
threshold below which a pitch class is not counted at all, and the linear energy split that turns
cents into a fractional class rotation. Pure, so vitest reads the exact values with no canvas.

**Files:**
- Create: `latent-forge/src/lib/chroma/match.ts`, `latent-forge/src/lib/chroma/__tests__/match.test.ts`

**Interfaces:**
- Consumes: nothing. This module imports no other module in the project.
- Produces, from `latent-forge/src/lib/chroma/match.ts`:
  `INTERVAL_W: readonly number[]` = `[1.0, 0.10, 0.35, 0.62, 0.70, 0.82, 0.18, 0.90, 0.66, 0.72, 0.30, 0.22]`;
  `MATCH_THRESHOLD = 0.08`;
  `matchFrame(frame: Float32Array, target: Float32Array): number` (both 12 long; classes **below**
  the threshold are skipped on both sides; returns 0 rather than NaN when nothing is active);
  `rotate(frame: Float32Array, classes: number): Float32Array` (fractional rotation with a linear
  energy split between the two neighbouring classes; `classes` may be negative and wraps; always a
  fresh array);
  `interface MatchAnchors { unison: number; fifth: number; tritone: number }`;
  `anchors(target: Float32Array): MatchAnchors` (the target scored against itself at 0, 7 and 6
  semitones).

- [ ] **Step 1: Write the failing test**

`latent-forge/src/lib/chroma/__tests__/match.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { anchors, INTERVAL_W, matchFrame, MATCH_THRESHOLD, rotate } from "../match";

/** A 12-class profile from {class: value} pairs. */
function profile(entries: Record<number, number>): Float32Array {
  const out = new Float32Array(12);
  for (const [k, v] of Object.entries(entries)) out[Number(k)] = v;
  return out;
}

describe("the constants §5.4 pins", () => {
  it("is the twelve interval weights, in order, and a 0.08 threshold", () => {
    expect(Array.from(INTERVAL_W)).toEqual([
      1.0, 0.10, 0.35, 0.62, 0.70, 0.82, 0.18, 0.90, 0.66, 0.72, 0.30, 0.22,
    ]);
    expect(INTERVAL_W).toHaveLength(12);
    expect(MATCH_THRESHOLD).toBe(0.08);
  });
});

describe("matchFrame", () => {
  it("scores a frame identical to the target at the unison anchor", () => {
    const t = profile({ 0: 1.0, 4: 0.8, 7: 0.9 });
    expect(matchFrame(t, t)).toBe(anchors(t).unison);
    expect(matchFrame(t, t)).toBeCloseTo(0.8300137174211248, 10);
  });

  it("reads INTERVAL_W by the distance between the two classes: 1.0, 0.90, 0.18", () => {
    // A single-class target makes the weight visible on its own: the frame a
    // fifth above reads INTERVAL_W[7] = 0.90 and the tritone INTERVAL_W[6] = 0.18.
    const t = profile({ 0: 1.0 });
    expect(matchFrame(profile({ 0: 1.0 }), t)).toBeCloseTo(1.0, 10);
    expect(matchFrame(profile({ 7: 1.0 }), t)).toBeCloseTo(0.90, 10);
    expect(matchFrame(profile({ 6: 1.0 }), t)).toBeCloseTo(0.18, 10);
    expect(matchFrame(profile({ 1: 1.0 }), t)).toBeCloseTo(0.10, 10);
    expect(matchFrame(profile({ 11: 1.0 }), t)).toBeCloseTo(0.22, 10);
  });

  it("counts nothing when the whole frame sits below the threshold", () => {
    const t = profile({ 0: 1.0, 7: 0.9 });
    const quiet = profile({ 0: 0.07, 4: 0.05, 7: 0.079 });
    expect(matchFrame(quiet, t)).toBe(0);
  });

  it("includes a class at exactly 0.08 and excludes one just below it", () => {
    const t = profile({ 0: 1.0 });
    // `profile` writes into a Float32Array, so 0.08 arrives as 0.079999998.
    // The guard compares against Math.fround(MATCH_THRESHOLD) for exactly this
    // reason -- against the float64 literal, this assertion returns 0.
    expect(matchFrame(profile({ 6: MATCH_THRESHOLD }), t)).toBeCloseTo(0.18, 10);
    expect(matchFrame(profile({ 6: 0.0799 }), t)).toBe(0);
    // and the same rule applies on the target side
    expect(matchFrame(profile({ 0: 1.0 }), profile({ 0: 0.0799 }))).toBe(0);
  });

  it("returns 0, not NaN, for an all-zero target", () => {
    const out = matchFrame(profile({ 0: 1.0 }), new Float32Array(12));
    expect(out).toBe(0);
    expect(Number.isNaN(out)).toBe(false);
  });

  it("rejects a frame that is not twelve classes long", () => {
    expect(() => matchFrame(new Float32Array(11), new Float32Array(12))).toThrow(/expected 12/);
    expect(() => matchFrame(new Float32Array(12), new Float32Array(13))).toThrow(/expected 12/);
  });
});

describe("rotate — cents/100 classes with a linear energy split", () => {
  it("is a pure permutation for a whole number of classes: no energy lost", () => {
    const f = profile({ 0: 1.0, 4: 0.8, 7: 0.9 });
    const r = rotate(f, 7);
    expect(Array.from(r).reduce((a, b) => a + b, 0)).toBeCloseTo(2.7, 6);
    expect(r[7]).toBeCloseTo(1.0, 6);
    expect(r[11]).toBeCloseTo(0.8, 6);
    expect(r[2]).toBeCloseTo(0.9, 6);   // 7 + 7 = 14 -> class 2
  });

  it("splits evenly between the two neighbours at half a class", () => {
    const f = profile({ 0: 1.0 });
    const r = rotate(f, 0.5);
    expect(r[0]).toBeCloseTo(0.5, 6);
    expect(r[1]).toBeCloseTo(0.5, 6);
    expect(Array.from(r).reduce((a, b) => a + b, 0)).toBeCloseTo(1.0, 6);
    const q = rotate(f, 0.25);
    expect(q[0]).toBeCloseTo(0.75, 6);
    expect(q[1]).toBeCloseTo(0.25, 6);
  });

  it("wraps downward for a negative rotation", () => {
    const f = profile({ 0: 1.0 });
    expect(rotate(f, -1)[11]).toBeCloseTo(1.0, 6);
    const r = rotate(f, -0.5);
    expect(r[11]).toBeCloseTo(0.5, 6);
    expect(r[0]).toBeCloseTo(0.5, 6);
  });

  it("copies at 0 classes and is the identity at 12", () => {
    const f = profile({ 0: 1.0, 3: 0.4 });
    const zero = rotate(f, 0);
    expect(Array.from(zero)).toEqual(Array.from(f));
    expect(zero).not.toBe(f);                       // never hands back the caller's array
    expect(Array.from(rotate(f, 12))).toEqual(Array.from(f));
  });
});

describe("anchors — the legend's three marks, the target against itself", () => {
  it("orders unison > fifth > tritone for a non-degenerate target", () => {
    const t = profile({ 0: 1.0, 4: 0.8, 7: 0.9 });
    const a = anchors(t);
    expect(a.unison).toBeCloseTo(0.8300137174211248, 8);
    expect(a.fifth).toBeCloseTo(0.6600823045267491, 8);
    expect(a.tritone).toBeCloseTo(0.30367626886145405, 8);
    expect(a.unison).toBeGreaterThan(a.fifth);
    expect(a.fifth).toBeGreaterThan(a.tritone);
  });

  it("is 1.0 / 0.90 / 0.18 for a single-class target, and all zero for an empty one", () => {
    const single = anchors(profile({ 0: 1.0 }));
    expect(single.unison).toBeCloseTo(1.0, 10);
    expect(single.fifth).toBeCloseTo(0.90, 10);
    expect(single.tritone).toBeCloseTo(0.18, 10);
    expect(anchors(new Float32Array(12))).toEqual({ unison: 0, fifth: 0, tritone: 0 });
  });
});
```

- [ ] **Step 2: Run it, expect failure**

```bash
cd latent-forge && npx vitest run src/lib/chroma/__tests__/match.test.ts
```

Expected: `Failed to resolve import "../match"`.

- [ ] **Step 3: Write the module**

`latent-forge/src/lib/chroma/match.ts`:

```ts
// The harmonic-overlap match score (spec §5.4; the drawing's _matchFrame at
// v3 925-937, _rotate at 895-903, _anchors at 915-922). Pure -- no canvas, no
// store, no network -- so vitest pins the exact numbers the spec specifies.
//
// The score is a weighted average, not a dot product: every pair of ACTIVE
// pitch classes (both sides above MATCH_THRESHOLD) contributes
// frame[a]*target[b]*INTERVAL_W[((a-b)%12+12)%12] to the numerator and
// frame[a]*target[b] to the denominator -- a DIRECTED, wrapped distance from
// the target's class to the frame's, not Math.abs(a-b) (see matchFrame's own
// comment for why the two disagree and WINTERMUTE's fifth-vs-fourth example).
// So a fifth reads high and a semitone low even though the semitone is nearer
// in pitch, and the result is always in [0.10, 1.0] when anything is active
// at all.

export const INTERVAL_W: readonly number[] = [
  1.0, 0.10, 0.35, 0.62, 0.70, 0.82, 0.18, 0.90, 0.66, 0.72, 0.30, 0.22,
];

/** Pitch classes at or above this count; below it they are not there at all. */
export const MATCH_THRESHOLD = 0.08;

/**
 * MATCH_THRESHOLD rounded to float32, which is what the guards below actually
 * compare against. This is NOT pedantry: every chroma array in this milestone
 * is a `Float32Array`, so a value written as `0.08` is stored as
 * `Math.fround(0.08) = 0.079999998211860657`. Comparing that against the
 * float64 literal `0.08 = 0.080000000000000002` makes `value < MATCH_THRESHOLD`
 * TRUE for a class the caller set to exactly the threshold -- so "at exactly
 * 0.08" would be excluded, which is the opposite of the documented rule.
 * Rounding the threshold the same way makes the comparison happen in one
 * precision. `0.0799` still rounds to 0.079899996, which is strictly below, so
 * "just under the threshold is excluded" is unaffected.
 */
const THRESHOLD_F32 = Math.fround(MATCH_THRESHOLD);

function require12(name: string, v: Float32Array): void {
  if (v.length !== 12) throw new RangeError(`${name}: expected 12 pitch classes, got ${v.length}`);
}

/**
 * Harmonic-overlap score of one 12-class frame against a 12-class target.
 *
 * INTERVAL_W is indexed by the DIRECTED, wrapped class distance from the
 * TARGET class to the FRAME class -- `((a - b) % 12 + 12) % 12`, `a` the
 * frame's class and `b` the target's -- never `Math.abs(a - b)`. The two are
 * not the same table lookup: `Math.abs` is symmetric, so it depends only on
 * which of the two class numbers happens to be larger, not on a consistent
 * "distance from target to frame" direction, and for roughly half of all
 * pairs it silently reads the wrong entry. WINTERMUTE's own example (plan log,
 * 2026-09-22 17:12:49) is the one to keep in mind: target class 7 (G), frame
 * class 0 (C) -- `Math.abs(7-0) = 7` reads `INTERVAL_W[7] = 0.90` ("a fifth"),
 * but the ascending distance from G up to C is 5 semitones ("a fourth",
 * `INTERVAL_W[5] = 0.82`), and `((0 - 7) % 12 + 12) % 12 = 5` is what gets
 * that right.
 *
 * The table stays UNFOLDED on purpose -- do not "fix" this into
 * `INTERVAL_W[Math.min(ic, 12-ic)]`. A minor second up (index 1, weight 0.10)
 * and a major seventh (index 11, weight 0.22) are both interval class 1 and
 * are deliberately weighted differently; folding would average pairs like
 * that and would also move the legend's anchors, since `anchors()` computes
 * them through this same function. §5.4 names `_matchFrame` as the score's
 * definition and pins these twelve weights to it; the indexing above is what
 * WINTERMUTE settled as the correct, directed reading of that definition. See
 * the Normative table's `INTERVAL_W`'s index row, which carries this as
 * resolved rather than as an open question.
 */
export function matchFrame(frame: Float32Array, target: Float32Array): number {
  require12("matchFrame(frame)", frame);
  require12("matchFrame(target)", target);
  let num = 0;
  let den = 0;
  for (let a = 0; a < 12; a++) {
    const fa = frame[a];
    if (fa < THRESHOLD_F32) continue;
    for (let b = 0; b < 12; b++) {
      const tb = target[b];
      if (tb < THRESHOLD_F32) continue;
      const w = fa * tb;
      const distance = (((a - b) % 12) + 12) % 12;
      num += w * INTERVAL_W[distance];
      den += w;
    }
  }
  return den ? num / den : 0;
}

/**
 * Rotate a 12-class frame by a fractional number of classes -- detune in cents
 * divided by 100 (spec §5.4). The energy of each class is split LINEARLY
 * between the two classes it lands between, so the total is preserved and a
 * 50-cent detune reads as half in each neighbour. Negative rotations wrap.
 *
 * Always returns a fresh array: v3 returns its input unchanged at 0, which
 * makes the caller's array aliasable. Purity is cheaper than that bug.
 */
export function rotate(frame: Float32Array, classes: number): Float32Array {
  require12("rotate(frame)", frame);
  const out = new Float32Array(12);
  const i = Math.floor(classes);
  const fr = classes - i;
  for (let p = 0; p < 12; p++) {
    const a = (((p - i) % 12) + 12) % 12;
    const b = (((p - i - 1) % 12) + 12) % 12;
    out[p] = frame[a] * (1 - fr) + frame[b] * fr;
  }
  return out;
}

export interface MatchAnchors {
  unison: number;
  fifth: number;
  tritone: number;
}

/**
 * The legend's three reference marks (§5.4, `_anchors`): what the score reads
 * when the target's own chroma is heard at a unison, a fifth and a tritone
 * away. They are properties of the target alone, which is why the legend can
 * draw them before any clip is selected.
 */
export function anchors(target: Float32Array): MatchAnchors {
  require12("anchors(target)", target);
  return {
    unison: matchFrame(target, target),
    fifth: matchFrame(rotate(target, 7), target),
    tritone: matchFrame(rotate(target, 6), target),
  };
}
```

- [ ] **Step 4: Run it, expect pass**

```bash
cd latent-forge && npx vitest run src/lib/chroma/__tests__/match.test.ts && npm run check
```

Expected: `Test Files  1 passed (1)` / `Tests  13 passed (13)`, and
`svelte-check found 0 errors and 0 warnings`.

- [ ] **Step 5: Commit**

```bash
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M6 T3: chroma/match.ts -- INTERVAL_W harmonic overlap above 0.08, linear-split rotation, unison/fifth/tritone anchors"
```

---

### Task 4: `src/lib/chroma/target.ts` — both target modes and the chord parser, pure

Spec §5.4. The target is what everything else is scored against, and it has two sources: `lane`
mode folds the TARGET lane's clips down to one profile, and `SEMITONE SET` mode takes twelve piano
keys that a chord symbol can fill in. Both produce the same thing — a 12-class `Float32Array` — so
the match layer never needs to know which mode is on. Pure and store-free: the caller (Writer B's
Task 9) reads the TARGET lane from `arrangement` and hands the frames in, which keeps every chord
spelling testable without a timeline.

**Files:**
- Create: `latent-forge/src/lib/chroma/target.ts`, `latent-forge/src/lib/chroma/__tests__/target.test.ts`

**Interfaces:**
- Consumes: nothing. This module imports no other module in the project. (The caller builds
  `frames` from this milestone's Task 1 `fold12Columns(fold12: Float32Array, T: number): Float32Array[]`,
  which returns every frame of the server's `[12,T]` C-order fold.)
- Produces, from `latent-forge/src/lib/chroma/target.ts`:
  `type ChromaTargetMode = "lane" | "set"`;
  `targetProfile(frames: readonly Float32Array[]): Float32Array` (lane mode — the 12-class folds
  **summed over frames then max-normalised**; an empty list or all-zero frames give an all-zero
  profile, never NaN);
  `setProfile(keys: readonly boolean[]): Float32Array` (SEMITONE SET mode — exactly twelve toggles
  as a flat 1/0 profile);
  `parseChord(text: string): boolean[] | null` (twelve booleans for the nine qualities
  `"" m 7 maj7 m7 dim aug sus2 sus4` over all twelve roots, `#` and `b` spellings, `null` for
  anything unrecognised — never throws).

- [ ] **Step 1: Write the failing test**

`latent-forge/src/lib/chroma/__tests__/target.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { parseChord, setProfile, targetProfile } from "../target";

function profile(entries: Record<number, number>): Float32Array {
  const out = new Float32Array(12);
  for (const [k, v] of Object.entries(entries)) out[Number(k)] = v;
  return out;
}

/** The set of pitch classes a parse turned on, sorted. */
function classesOf(keys: boolean[] | null): number[] {
  expect(keys).not.toBeNull();
  return keys!.flatMap((on, p) => (on ? [p] : []));
}

describe("targetProfile — lane mode", () => {
  it("sums the 12-class folds over frames, then normalises to max 1", () => {
    const out = targetProfile([
      profile({ 0: 0.5, 7: 0.1 }),
      profile({ 0: 0.5, 4: 0.2 }),
      profile({ 7: 0.4 }),
    ]);
    // sums: C 1.0, E 0.2, G 0.5 -> max is C, so divide by 1.0
    expect(out[0]).toBeCloseTo(1.0, 6);
    expect(out[4]).toBeCloseTo(0.2, 6);
    expect(out[7]).toBeCloseTo(0.5, 6);
    expect(Math.max(...Array.from(out))).toBeCloseTo(1.0, 6);
  });

  it("normalises by the summed maximum, not by the per-frame one", () => {
    const out = targetProfile([profile({ 0: 0.25 }), profile({ 0: 0.25 }), profile({ 4: 0.4 })]);
    // sums: C 0.5, E 0.4 -> /0.5
    expect(out[0]).toBeCloseTo(1.0, 6);
    expect(out[4]).toBeCloseTo(0.8, 6);
  });

  it("gives an all-zero profile for a lane with no clips, not NaN", () => {
    const out = targetProfile([]);
    expect(Array.from(out)).toEqual(new Array(12).fill(0));
    expect(Array.from(out).every(Number.isFinite)).toBe(true);
  });

  it("gives an all-zero profile for all-zero frames rather than dividing by zero", () => {
    const out = targetProfile([new Float32Array(12), new Float32Array(12)]);
    expect(Array.from(out)).toEqual(new Array(12).fill(0));
    expect(Array.from(out).every(Number.isFinite)).toBe(true);
  });

  it("rejects a frame that is not twelve classes long", () => {
    expect(() => targetProfile([new Float32Array(11)])).toThrow(/expected 12/);
  });
});

describe("setProfile — SEMITONE SET mode", () => {
  it("turns the twelve toggles into a flat 1/0 profile", () => {
    const keys = new Array(12).fill(false);
    keys[0] = true;
    keys[3] = true;
    keys[7] = true;
    const out = setProfile(keys);
    expect(Array.from(out)).toEqual([1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0]);
    expect(out).toBeInstanceOf(Float32Array);
  });

  it("rejects a key row that is not twelve long", () => {
    expect(() => setProfile([true, false])).toThrow(/expected 12/);
  });
});

describe("parseChord — the nine qualities §5.4 lists", () => {
  it("parses each quality on C", () => {
    expect(classesOf(parseChord("C"))).toEqual([0, 4, 7]);
    expect(classesOf(parseChord("Cm"))).toEqual([0, 3, 7]);
    expect(classesOf(parseChord("C7"))).toEqual([0, 4, 7, 10]);
    expect(classesOf(parseChord("Cmaj7"))).toEqual([0, 4, 7, 11]);
    expect(classesOf(parseChord("Cm7"))).toEqual([0, 3, 7, 10]);
    expect(classesOf(parseChord("Cdim"))).toEqual([0, 3, 6]);
    expect(classesOf(parseChord("Caug"))).toEqual([0, 4, 8]);
    expect(classesOf(parseChord("Csus2"))).toEqual([0, 2, 7]);
    expect(classesOf(parseChord("Csus4"))).toEqual([0, 5, 7]);
  });

  it("transposes every quality to all twelve roots", () => {
    const naturals: Record<string, number> = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
    const qualities: [string, number[]][] = [
      ["", [0, 4, 7]], ["m", [0, 3, 7]], ["7", [0, 4, 7, 10]], ["maj7", [0, 4, 7, 11]],
      ["m7", [0, 3, 7, 10]], ["dim", [0, 3, 6]], ["aug", [0, 4, 8]],
      ["sus2", [0, 2, 7]], ["sus4", [0, 5, 7]],
    ];
    for (const [letter, base] of Object.entries(naturals)) {
      for (const accidental of ["", "#", "b"]) {
        const root = (base + (accidental === "#" ? 1 : accidental === "b" ? -1 : 0) + 12) % 12;
        for (const [q, ivs] of qualities) {
          const expected = ivs.map((i) => (root + i) % 12).sort((a, b) => a - b);
          expect(classesOf(parseChord(`${letter}${accidental}${q}`)), `${letter}${accidental}${q}`)
            .toEqual(expected);
        }
      }
    }
  });

  it("gives Db and C#, and Bb7 and A#7, the same keys", () => {
    expect(parseChord("Db")).toEqual(parseChord("C#"));
    expect(parseChord("Bb7")).toEqual(parseChord("A#7"));
    expect(classesOf(parseChord("F#m"))).toEqual([1, 6, 9]);
    expect(classesOf(parseChord("Gbm"))).toEqual([1, 6, 9]);
  });

  it("wraps E# to F and Cb to B rather than failing on the spelling", () => {
    expect(parseChord("E#")).toEqual(parseChord("F"));
    expect(parseChord("Cb")).toEqual(parseChord("B"));
    expect(parseChord("B#m7")).toEqual(parseChord("Cm7"));
  });

  it("takes the root letter in either case and lowercases the quality", () => {
    expect(parseChord("c")).toEqual(parseChord("C"));
    expect(parseChord("f#M7")).toEqual(parseChord("F#m7"));   // see Open questions
    expect(parseChord("bbSUS4")).toEqual(parseChord("Bbsus4"));
    expect(parseChord("  Cmaj7  ")).toEqual(parseChord("Cmaj7"));
    expect(parseChord("C maj7")).toEqual(parseChord("Cmaj7"));
  });

  it("returns null for an empty, nonsense, unknown or inherited-property input", () => {
    expect(parseChord("")).toBeNull();
    expect(parseChord("   ")).toBeNull();
    expect(parseChord("H")).toBeNull();
    expect(parseChord("Cxyz")).toBeNull();
    expect(parseChord("C11")).toBeNull();
    expect(parseChord("Cmin")).toBeNull();          // an alias §5.4 does not list
    expect(parseChord("Cconstructor")).toBeNull();  // not an inherited Object key
    expect(parseChord("CtoString")).toBeNull();
  });

  it("always returns exactly twelve booleans when it returns at all", () => {
    for (const text of ["C", "F#m7", "Bbsus2", "Adim", "Gaug"]) {
      const keys = parseChord(text);
      expect(keys).toHaveLength(12);
      expect(keys!.every((v) => typeof v === "boolean")).toBe(true);
    }
  });
});
```

- [ ] **Step 2: Run it, expect failure**

```bash
cd latent-forge && npx vitest run src/lib/chroma/__tests__/target.test.ts
```

Expected: `Failed to resolve import "../target"`.

- [ ] **Step 3: Write the module**

`latent-forge/src/lib/chroma/target.ts`:

```ts
// The chroma target (spec §5.4), in both of its modes, as one 12-class
// Float32Array so the match layer never has to know which mode is on:
//
//   lane mode -- the TARGET lane's clips' 12-class folds, SUMMED over frames
//                and then max-normalised (_targetProfile, v3 877-891)
//   set  mode -- twelve piano-key toggles, flat 1/0, optionally filled in by a
//                chord symbol
//
// Pure and store-free: the caller reads the TARGET lane from `arrangement` and
// hands the frames in, which keeps every chord spelling testable without a
// timeline.

export type ChromaTargetMode = "lane" | "set";

/**
 * Lane mode: sum the frames, then divide by the summed maximum. Summing first
 * means a long clip weighs more than a short one, which is what "the lane's
 * profile" should mean. An empty lane and an all-silent lane both give an
 * all-zero profile -- never NaN, and the caller is expected to say so honestly
 * rather than draw it as if it were data.
 */
export function targetProfile(frames: readonly Float32Array[]): Float32Array {
  const out = new Float32Array(12);
  for (const fr of frames) {
    if (fr.length !== 12) {
      throw new RangeError(`targetProfile: expected 12 pitch classes per frame, got ${fr.length}`);
    }
    for (let p = 0; p < 12; p++) out[p] += fr[p];
  }
  let max = 0;
  for (let p = 0; p < 12; p++) if (out[p] > max) max = out[p];
  if (max > 0) for (let p = 0; p < 12; p++) out[p] /= max;
  return out;
}

/** SEMITONE SET mode: the twelve toggles, flat. On is 1, off is 0. */
export function setProfile(keys: readonly boolean[]): Float32Array {
  if (keys.length !== 12) {
    throw new RangeError(`setProfile: expected 12 keys, got ${keys.length}`);
  }
  const out = new Float32Array(12);
  for (let p = 0; p < 12; p++) out[p] = keys[p] ? 1 : 0;
  return out;
}

/** Semitone offset of each natural letter from C. */
const LETTER_SEMITONE = new Map<string, number>([
  ["c", 0], ["d", 2], ["e", 4], ["f", 5], ["g", 7], ["a", 9], ["b", 11],
]);

/**
 * The nine qualities §5.4 lists, and only those. A Map, not an object literal:
 * an object lookup on arbitrary user text finds inherited keys, so "Cconstructor"
 * would return a truthy function and the parser would crash downstream.
 */
const QUALITY_INTERVALS = new Map<string, readonly number[]>([
  ["", [0, 4, 7]],
  ["m", [0, 3, 7]],
  ["7", [0, 4, 7, 10]],
  ["maj7", [0, 4, 7, 11]],
  ["m7", [0, 3, 7, 10]],
  ["dim", [0, 3, 6]],
  ["aug", [0, 4, 8]],
  ["sus2", [0, 2, 7]],
  ["sus4", [0, 5, 7]],
]);

const CHORD_RE = /^([A-Ga-g])([#b]?)\s*(.*)$/;

/**
 * Parse a chord symbol into twelve key toggles, or null if it is not one of
 * the nine qualities over one of the twelve roots. Never throws -- the field
 * is typed into character by character, so half-finished text is the normal
 * case and null simply means "the key row does not change yet".
 *
 * The root letter is case-insensitive and the quality is lowercased (as v3
 * does), so `CDIM` works. The accidental is case-SENSITIVE: a lowercase `b`
 * after the letter is a flat. Roots are computed from the letter's semitone
 * plus the accidental rather than looked up in a sharp-spelling table, so E#,
 * B# and Cb resolve instead of failing (v3's NOTES.indexOf("E#") is -1).
 */
export function parseChord(text: string): boolean[] | null {
  const m = CHORD_RE.exec(text.trim());
  if (!m) return null;
  const letter = LETTER_SEMITONE.get(m[1].toLowerCase());
  if (letter === undefined) return null;
  const accidental = m[2] === "#" ? 1 : m[2] === "b" ? -1 : 0;
  const root = (((letter + accidental) % 12) + 12) % 12;
  const intervals = QUALITY_INTERVALS.get(m[3].toLowerCase());
  if (!intervals) return null;
  const keys = new Array<boolean>(12).fill(false);
  for (const iv of intervals) keys[(root + iv) % 12] = true;
  return keys;
}
```

- [ ] **Step 4: Run it, expect pass**

```bash
cd latent-forge && npx vitest run src/lib/chroma/__tests__/target.test.ts && npm run check
```

Expected: `Test Files  1 passed (1)` / `Tests  14 passed (14)`, and
`svelte-check found 0 errors and 0 warnings`.

- [ ] **Step 5: Commit**

```bash
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M6 T4: chroma/target.ts -- lane profile summed then max-normalised, SEMITONE SET keys, nine-quality chord parser over twelve roots"
```

---

### Task 5: `src/lib/chroma/detuneScan.ts` — the detune scan and BEST, pure

Spec §5.4. The scan strip asks two different questions of the same clip: how HIGH the match sits on
average across the clip, and how STEADY it is. A flat curve is not the same as a good one — it can
be uniformly dissonant — so the scan reports `mean` and `sd` at every step and the criterion picks
which one BEST follows (`mean` for HIGHEST, `mean − sd` for STEADIEST). The grid is pinned: cents
**−100..100 step 4**, sampling **every 3rd frame**. The stride is a cost decision, not a modelling
one — 51 steps × every frame × a 144-term score is what it saves — so the **clip score label** is
computed separately over *every* frame, which is what §5.4 means by "mean frame match at the clip's
detune". Pure, so vitest pins the whole curve with no canvas and no store.

**Files:**
- Create: `latent-forge/src/lib/chroma/detuneScan.ts`,
  `latent-forge/src/lib/chroma/__tests__/detuneScan.test.ts`

**Interfaces:**
- Consumes `fold12Column(fold12: Float32Array, T: number, frame: number): Float32Array` from
  `./bins` (this milestone's Task 1 — one frame of the server's `[12,T]` C-order fold, i.e.
  `class p, frame t = fold12[p*T + t]`).
- Consumes `matchFrame(frame: Float32Array, target: Float32Array): number` and
  `rotate(frame: Float32Array, classes: number): Float32Array` from `./match` (this milestone's
  Task 3 — the harmonic-overlap score above a 0.08 threshold, and a fractional class rotation with
  a linear energy split).
- Produces, from `latent-forge/src/lib/chroma/detuneScan.ts`:
  `DETUNE_MIN = -100`, `DETUNE_MAX = 100`, `DETUNE_STEP = 4`, `FRAME_STRIDE = 3`;
  `type ScanCriterion = "highest" | "steadiest"`;
  `interface DetuneScan { cents: number[]; mean: number[]; sd: number[] }`;
  `scanDetune(fold12: Float32Array, T: number, target: Float32Array, analysisDetuneCents?: number):
  DetuneScan` (each step rotates by `(analysisDetuneCents + cents) / 100`, so the 51-point axis is
  **relative to the clip's current detune** in both analysis cases — see the Normative block's
  "how much detune to rotate by" row; the default `0` is the stretched-preview case);
  `bestDetune(scan: DetuneScan, criterion: ScanCriterion): number` (the step, i.e. an **offset** from
  the clip's current detune — callers add it, they do not assign it);
  `meanMatchAtDetune(fold12: Float32Array, T: number, target: Float32Array, cents: number): number`
  (the clip score label — **every** frame, no stride).

- [ ] **Step 1: Write the failing test**

`latent-forge/src/lib/chroma/__tests__/detuneScan.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import {
  bestDetune,
  DETUNE_MAX,
  DETUNE_MIN,
  DETUNE_STEP,
  FRAME_STRIDE,
  meanMatchAtDetune,
  scanDetune,
} from "../detuneScan";

function profile(entries: Record<number, number>): Float32Array {
  const out = new Float32Array(12);
  for (const [k, v] of Object.entries(entries)) out[Number(k)] = v;
  return out;
}

/** Pack per-frame 12-class columns into the server's [12,T] C-order layout. */
function packFold12(columns: Float32Array[]): Float32Array {
  const T = columns.length;
  const out = new Float32Array(12 * T);
  for (let t = 0; t < T; t++) for (let p = 0; p < 12; p++) out[p * T + t] = columns[t][p];
  return out;
}

describe("the scan grid §5.4 pins", () => {
  it("is cents -100..100 step 4 and every 3rd frame", () => {
    expect(DETUNE_MIN).toBe(-100);
    expect(DETUNE_MAX).toBe(100);
    expect(DETUNE_STEP).toBe(4);
    expect(FRAME_STRIDE).toBe(3);
  });

  it("gives a cents axis of exactly 51 points: (100 - -100)/4 + 1", () => {
    const scan = scanDetune(packFold12([profile({ 0: 1 })]), 1, profile({ 0: 1 }));
    expect((DETUNE_MAX - DETUNE_MIN) / DETUNE_STEP + 1).toBe(51);
    expect(scan.cents).toHaveLength(51);
    expect(scan.cents[0]).toBe(-100);
    expect(scan.cents[1]).toBe(-96);
    expect(scan.cents[25]).toBe(0);
    expect(scan.cents[50]).toBe(100);
    expect(scan.cents.every((c) => Number.isInteger(c))).toBe(true);
  });

  it("returns mean and sd arrays the same length as cents", () => {
    const scan = scanDetune(packFold12([profile({ 0: 1 }), profile({ 4: 1 })]), 2, profile({ 0: 1 }));
    expect(scan.mean).toHaveLength(51);
    expect(scan.sd).toHaveLength(51);
    expect(scan.mean.every(Number.isFinite)).toBe(true);
    expect(scan.sd.every(Number.isFinite)).toBe(true);
  });
});

describe("scanDetune", () => {
  it("samples every 3rd frame, so frames 1 and 2 change nothing", () => {
    const target = profile({ 0: 1 });
    const kept = [profile({ 0: 1 }), profile({ 6: 1 })];              // frames 0 and 3
    const a = scanDetune(packFold12([kept[0], new Float32Array(12), new Float32Array(12), kept[1]]), 4, target);
    const b = scanDetune(packFold12([kept[0], profile({ 3: 1 }), profile({ 9: 1 }), kept[1]]), 4, target);
    expect(b.mean).toEqual(a.mean);
    expect(b.sd).toEqual(a.sd);
  });

  it("reads the unison at 0 cents when the only sampled frame is the target", () => {
    const target = profile({ 0: 1 });
    const scan = scanDetune(packFold12([profile({ 0: 1 })]), 1, target);
    expect(scan.mean[25]).toBeCloseTo(1.0, 10);    // cents 0
    expect(scan.sd[25]).toBe(0);
    expect(scan.mean[50]).toBeCloseTo(0.10, 10);   // +100 cents: one class up, INTERVAL_W[1]
  });

  it("gives sd 0 at every cent for a single sampled frame, so the criteria agree", () => {
    const target = profile({ 0: 1.0, 4: 0.8, 7: 0.9 });
    const scan = scanDetune(packFold12([profile({ 0: 1.0, 4: 0.8, 7: 0.9 })]), 1, target);
    expect(scan.sd.every((v) => v === 0)).toBe(true);
    expect(bestDetune(scan, "highest")).toBe(bestDetune(scan, "steadiest"));
  });

  it("rotates by the ANALYSIS detune plus each step, so the axis is RELATIVE to it", () => {
    // The scan runs on audio the stretch has usually already detuned, so step
    // c means "the clip's current detune, plus c". The base argument is what
    // keeps that true in the OTHER case too -- a clip with no native_bpm,
    // whose previewAudio is null and whose fold is therefore undetuned.
    const target = profile({ 0: 1 });
    const fold12 = packFold12([profile({ 0: 1 })]);
    const flat = scanDetune(fold12, 1, target);
    const shifted = scanDetune(fold12, 1, target, 100);
    expect(shifted.cents).toEqual(flat.cents);                 // the axis itself never moves
    expect(shifted.mean[25]).toBeCloseTo(flat.mean[50], 9);    //    0 rel = +100 absolute
    expect(shifted.mean[0]).toBeCloseTo(flat.mean[25], 9);     // -100 rel =    0 absolute
  });

  it("returns zeros rather than NaN for an all-zero target", () => {
    const scan = scanDetune(packFold12([profile({ 0: 1 }), profile({ 4: 1 })]), 2, new Float32Array(12));
    expect(scan.mean.every((v) => v === 0)).toBe(true);
    expect(scan.sd.every((v) => v === 0)).toBe(true);
    expect(bestDetune(scan, "highest")).toBe(-100);   // first argmax of a flat curve
  });

  it("returns a 51-point scan of zeros for T = 0 rather than dividing by no frames", () => {
    const scan = scanDetune(new Float32Array(0), 0, profile({ 0: 1 }));
    expect(scan.cents).toHaveLength(51);
    expect(scan.mean.every((v) => v === 0)).toBe(true);
    expect(scan.sd.every((v) => v === 0)).toBe(true);
  });
});

describe("HIGHEST and STEADIEST", () => {
  it("disagree on a constructed clip: -12 cents is highest, -76 cents is steadiest", () => {
    // Target: a C major triad. Frame 0 is C-ish (scores well at no detune);
    // frame 3 is F/B-ish (scores badly there). HIGHEST nudges to where the
    // average is best; STEADIEST goes to where BOTH frames score alike.
    //
    // The steadiest step moved from -80 to -76 when Task 3's INTERVAL_W
    // indexing became the directed distance rather than Math.abs(a-b)
    // (WINTERMUTE, 2026-09-22): this fixture's cross terms (frame class vs a
    // non-equal target class) read different table entries under the
    // corrected formula, which reshapes the mean-sd curve enough to move its
    // argmax by one step. Recomputed by hand against the fixed matchFrame,
    // not eyeballed.
    const target = profile({ 0: 1.0, 4: 0.8, 7: 0.9 });
    const fold12 = packFold12([
      profile({ 0: 1.0, 4: 0.6 }),
      new Float32Array(12),
      new Float32Array(12),
      profile({ 5: 1.0, 11: 0.5 }),
    ]);
    const scan = scanDetune(fold12, 4, target);

    expect(bestDetune(scan, "highest")).toBe(-12);
    expect(bestDetune(scan, "steadiest")).toBe(-76);

    const hi = scan.cents.indexOf(-12);
    const st = scan.cents.indexOf(-76);
    expect(scan.mean[hi]).toBeCloseTo(0.6563495680089630, 6);
    expect(scan.mean[st]).toBeCloseTo(0.6166814814814815, 6);
    expect(scan.sd[st]).toBeLessThan(scan.sd[hi]);            // steadier, as claimed
    expect(scan.mean[st]).toBeLessThan(scan.mean[hi]);        // and lower, as claimed
    expect(scan.mean[st] - scan.sd[st]).toBeGreaterThan(scan.mean[hi] - scan.sd[hi]);
  });

  it("reads the arrays directly: argmax of mean, or of mean - sd, first wins a tie", () => {
    const scan = {
      cents: [-8, -4, 0, 4],
      mean: [0.5, 0.9, 0.9, 0.2],
      sd: [0.5, 0.5, 0.4, 0.0],
    };
    expect(bestDetune(scan, "highest")).toBe(-4);      // 0.9 first, at index 1
    // mean - sd = [0.0, 0.4, 0.5, 0.2]: a UNIQUE max at index 2. The earlier
    // sd of [0.0, 0.5, 0.4, 0.0] gave [0.5, 0.4, 0.5, 0.2] -- a tie between
    // index 0 and index 2 -- and first-wins would have returned -8, not 0.
    expect(bestDetune(scan, "steadiest")).toBe(0);
    expect(bestDetune({ cents: [-4, 0], mean: [0.3, 0.3], sd: [0, 0] }, "highest")).toBe(-4);
  });
});

describe("meanMatchAtDetune — the clip score label", () => {
  it("averages EVERY frame, not every 3rd, at the clip's own detune", () => {
    const target = profile({ 0: 1.0, 4: 0.8, 7: 0.9 });
    const fold12 = packFold12([
      profile({ 0: 1.0, 4: 0.6 }),
      new Float32Array(12),
      new Float32Array(12),
      profile({ 5: 1.0, 11: 0.5 }),
    ]);
    const scan = scanDetune(fold12, 4, target);
    const all = meanMatchAtDetune(fold12, 4, target, 0);
    // The two silent frames score 0 and the scan never sees them, so the label
    // is exactly half the scan's mean here -- the difference is the point.
    // (0.3320679012345679 before Task 3's directed-distance fix; recomputed.)
    expect(all).toBeCloseTo(0.3263966049382716, 6);
    expect(all).toBeCloseTo(scan.mean[scan.cents.indexOf(0)] / 2, 6);
  });

  it("is 0 for no frames and follows the detune it is given", () => {
    const target = profile({ 0: 1 });
    expect(meanMatchAtDetune(new Float32Array(0), 0, target, 0)).toBe(0);
    const fold12 = packFold12([profile({ 0: 1 })]);
    expect(meanMatchAtDetune(fold12, 1, target, 0)).toBeCloseTo(1.0, 10);
    expect(meanMatchAtDetune(fold12, 1, target, 100)).toBeCloseTo(0.10, 10);
    expect(meanMatchAtDetune(fold12, 1, target, -100)).toBeCloseTo(0.22, 10);
  });
});
```

- [ ] **Step 2: Run it, expect failure**

```bash
cd latent-forge && npx vitest run src/lib/chroma/__tests__/detuneScan.test.ts
```

Expected: `Failed to resolve import "../detuneScan"`.

- [ ] **Step 3: Write the module**

`latent-forge/src/lib/chroma/detuneScan.ts`:

```ts
// The detune scan (spec §5.4, the drawing's _detuneScan at v3 947-957). Match
// as a function of detune across +/-100 cents, in two readings:
//
//   HIGHEST   -> argmax of mean          : the match sits high on average
//   STEADIEST -> argmax of (mean - sd)   : the match holds level through the
//                                          clip, which is what matters before a
//                                          crossfade or an inpainted join
//
// A flat curve on its own is not a good match -- it can be uniformly
// dissonant -- which is why the scan reports both and the criterion chooses.
//
// The grid is pinned by the spec: cents -100..100 step 4 (51 points) sampling
// every 3rd frame. The stride is a cost decision, not a modelling one, so the
// clip score label (meanMatchAtDetune) deliberately does NOT stride: §5.4 says
// the label is the mean frame match at the clip's detune, over the clip.

import { fold12Column } from "./bins";
import { matchFrame, rotate } from "./match";

export const DETUNE_MIN = -100;
export const DETUNE_MAX = 100;
export const DETUNE_STEP = 4;
export const FRAME_STRIDE = 3;

export type ScanCriterion = "highest" | "steadiest";

export interface DetuneScan {
  /** 51 points: -100, -96, ... 96, 100. */
  cents: number[];
  /** Mean match over the sampled frames, one per cents step. */
  mean: number[];
  /** Population sd of the same samples (divided by n, as v3 does). */
  sd: number[];
}

/** The 51 cents steps, as integers. */
function centsAxis(): number[] {
  const out: number[] = [];
  for (let c = DETUNE_MIN; c <= DETUNE_MAX; c += DETUNE_STEP) out.push(c);
  return out;
}

/**
 * Scan the clip's 12-class fold against the target across the detune range.
 * `fold12` is the server's [12,T] C-order array; `T` its frame count.
 * Rotation is by `cents/100` classes -- 100 cents is exactly one pitch class.
 *
 * `analysisDetuneCents` is the detune NOT already present in the analysed
 * audio: 0 when the fold came from the stretched preview (M5 T10's runStretch
 * has already pitch-shifted it by clip.detune_cents / 100), and
 * clip.detune_cents when it came from the raw source. Each step therefore
 * rotates by (analysisDetuneCents + c) / 100, which makes the 51-point cents
 * axis RELATIVE to the clip's current detune in BOTH cases -- step c means
 * "clip.detune_cents + c". So `bestDetune`'s answer is an OFFSET the caller
 * adds to the clip's detune, never a value it assigns. See the plan's
 * Normative block and Open question 6.
 */
export function scanDetune(
  fold12: Float32Array,
  T: number,
  target: Float32Array,
  analysisDetuneCents = 0,
): DetuneScan {
  const cents = centsAxis();
  const mean: number[] = [];
  const sd: number[] = [];

  // Extract the sampled columns once: 51 steps would otherwise re-slice them.
  const columns: Float32Array[] = [];
  for (let t = 0; t < T; t += FRAME_STRIDE) columns.push(fold12Column(fold12, T, t));

  for (const c of cents) {
    if (columns.length === 0) {
      mean.push(0);
      sd.push(0);
      continue;
    }
    const semis = (analysisDetuneCents + c) / 100;
    const vals: number[] = [];
    let sum = 0;
    for (const col of columns) {
      const v = matchFrame(rotate(col, semis), target);
      vals.push(v);
      sum += v;
    }
    const m = sum / vals.length;
    let acc = 0;
    for (const v of vals) acc += (v - m) * (v - m);
    mean.push(m);
    sd.push(Math.sqrt(acc / vals.length));
  }

  return { cents, mean, sd };
}

/**
 * The scan step BEST moves by -- an OFFSET from the clip's current detune, not
 * an absolute detune, because scanDetune's axis is relative (see above). Ties
 * keep the FIRST (most negative) step --
 * the comparison is strict `>` -- so the button is deterministic on the flat
 * stretches the 0.08 threshold creates near a whole-class rotation.
 */
export function bestDetune(scan: DetuneScan, criterion: ScanCriterion): number {
  const score = (i: number): number =>
    criterion === "steadiest" ? scan.mean[i] - scan.sd[i] : scan.mean[i];
  let best = 0;
  for (let i = 1; i < scan.cents.length; i++) if (score(i) > score(best)) best = i;
  return scan.cents[best];
}

/**
 * The clip's score label (§5.4): the mean frame match at the clip's detune,
 * over EVERY frame -- no stride. M5 T6's `SCORE_PLACEHOLDER = "chi —"` is
 * replaced by this number.
 */
export function meanMatchAtDetune(
  fold12: Float32Array,
  T: number,
  target: Float32Array,
  cents: number,
): number {
  if (T <= 0) return 0;
  const semis = cents / 100;
  let sum = 0;
  for (let t = 0; t < T; t++) sum += matchFrame(rotate(fold12Column(fold12, T, t), semis), target);
  return sum / T;
}
```

- [ ] **Step 4: Run it, expect pass**

```bash
cd latent-forge && npx vitest run src/lib/chroma/__tests__/detuneScan.test.ts && npm run check
```

Expected: `Test Files  1 passed (1)` / `Tests  13 passed (13)`, and
`svelte-check found 0 errors and 0 warnings`.

The whole chroma math layer together, for the record:

```bash
cd latent-forge && npx vitest run src/lib/chroma
```

Expected: `Test Files  5 passed (5)` / `Tests  64 passed (64)` (13 + 11 + 13 + 14 + 13).

- [ ] **Step 5: Commit**

```bash
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M6 T5: chroma/detuneScan.ts -- 51-point +/-100c scan every 3rd frame, HIGHEST=mean vs STEADIEST=mean-sd, un-strided clip score label"
```

---

### Task 6: heatmap geometry, the consonance ramp, and `src/ui/chroma/ChromaHeatmap.svelte`

Spec §5.4. The heatmap is the pane's centre: four views (`GLOBAL` = the 12-class fold, `BASS oct1` /
`MID oct5` / `HIGH oct9` = the raw 128 bins of band 0/1/2), the target's own profile as a reference
row across the top, and middle-drag zoom/scroll over the frame axis (the drawing's
`middle-drag: ↕ zoom · ↔ scroll` hint, v3 **331** — the brief says 341, which is the `</div>` that
closes the hover readout; the source wins). All the *decidable* geometry lives in a pure module so
vitest can pin it without a canvas, exactly as M5 T5 does for the lane canvas ("canvas drawing
itself is not unit-tested — jsdom has no `CanvasRenderingContext2D`"), and the component only turns
those answers into `fillRect` calls.

**The cell colour is a RAMP, and that is the one documented exception to "canvas colours come from
`getComputedStyle`".** `docs/latent-forge/HANDOUT.md` is explicit: an unregistered custom property's
computed value is its *literal token stream* — the string `"oklch(78% 0.08 250)"`, not a colour with
channels — so `getComputedStyle` hands a ramp nothing to interpolate, and a digit regex over that
string turns it into `rgb(78, 0, 250)`, an indigo. So `consonanceColor.ts` builds its own `oklch()`
string per channel with named endpoint constants, precisely as M5's `downbeatColor`
(`lib/math/downbeats.ts`) and M10's `xcorrColor` (`lib/stats/xcorrColor.ts`) do, and carries the
reason in a comment so nobody "fixes" it back. Flat colours — the border, the separators, the tick
labels — still come from `getComputedStyle`, through this task's `chromaColour()`, which adds the
**per-token fallback** HANDOUT.md requires: `ctx.fillStyle = ""` is a *silent no-op that leaves the
previous colour*, and an undefined token returns `""`. (M1 T13's `panelColour` has no fallback; this
milestone does not reuse it — see the open questions.)

**Files:**
- Create: `latent-forge/src/lib/chroma/consonanceColor.ts`,
  `latent-forge/src/lib/chroma/__tests__/consonanceColor.test.ts`
- Create: `latent-forge/src/lib/chroma/heatmapGeometry.ts`,
  `latent-forge/src/lib/chroma/__tests__/heatmapGeometry.test.ts`
- Create: `latent-forge/src/ui/chroma/chromaCanvas.ts`,
  `latent-forge/src/ui/chroma/__tests__/chromaCanvas.test.ts`
- Create: `latent-forge/src/ui/chroma/ChromaHeatmap.svelte`,
  `latent-forge/src/ui/chroma/__tests__/ChromaHeatmap.component.test.ts`

**Interfaces:**
- Consumes `BINS_PER_BAND = 128`, `BINS_PER_SEMITONE = 128 / 12`,
  `binToPitchClass(bin: number, binsPerBand?: number): number` (nearest semitone centre by
  **circular** distance, ties to the lower class), `pitchClassToBin(pitchClass: number,
  binsPerBand?: number): number` (the class's exact centre), and
  `fold12Column(fold12: Float32Array, T: number, frame: number): Float32Array` (one frame of the
  server's `[12,T]` C-order fold, `class p, frame t = fold12[p*T + t]` — **what GLOBAL displays**,
  the same array the match/scan/clip-score path reads: WINTERMUTE's 2026-09-22 ruling settled that
  there is one 12-class fold, not a locally re-folded `bands` for display and a separately
  transported `fold12` for scoring) from `latent-forge/src/lib/chroma/bins.ts` (**this milestone's
  Task 1**).
- Consumes `matchFrame(frame: Float32Array, target: Float32Array): number` and
  `rotate(frame: Float32Array, classes: number): Float32Array` from
  `latent-forge/src/lib/chroma/match.ts` (**this milestone's Task 3**) — the harmonic-overlap score
  counting pitch classes only above `MATCH_THRESHOLD = 0.08`, and a fractional class rotation with a
  linear energy split.
- Consumes `interface ChromaResult { frames: number; fps: number; bands: Float32Array /* 3*128*T,
  C-order */; fold12: Float32Array /* 12*T, C-order */; T: number }` from
  `latent-forge/src/lib/chroma/chromaClient.svelte.ts` (**this milestone's Task 2**).
- Consumes `middleDragZoomFactor(deltaY: number): number` (`Math.pow(1.012, -deltaY)`; a negative
  `deltaY`, i.e. dragging up, returns > 1) from `latent-forge/src/lib/math/ruler.ts` (**M5 T3**).
- Consumes `HELP` from `latent-forge/src/lib/help/strings.ts` (**M1 T14**): `HELP.chromaHeatmap` is
  the id for this canvas (v3 line 344, verified against M1 T14's own `KEYS` table).
- Produces, from `consonanceColor.ts`: `CONSONANT_HUE = 60`, `DISSONANT_HUE = 260`,
  `CELL_L_TOP = 94`, `CELL_L_SPAN = 48`, `CELL_C_BASE = 0.02`, `CELL_C_SPAN = 0.19`,
  `TARGET_ROW_HUE = 300`, `TARGET_L_TOP = 90`, `TARGET_L_SPAN = 46`, `TARGET_C_BASE = 0.02`,
  `TARGET_C_SPAN = 0.12`, `LEGEND_L = 58`, `LEGEND_C = 0.17`, `LEGEND_STOPS = 9`;
  `consonanceHue(match: number): number`; `consonanceColor(value: number, match: number): string`;
  `targetRowColor(value: number): string`; `legendColor(t: number): string`.
- Produces, from `heatmapGeometry.ts`: `REF_ROW_H = 9`, `REF_GAP = 2`, `BODY_Y = 11`,
  `MIN_VISIBLE_FRAMES = 8`, `CELL_FLOOR = 0.04`; `type ChromaView = "global" | "bass" | "mid" | "high"`;
  `CHROMA_VIEWS: readonly ChromaView[]`; `VIEW_LABELS: Record<ChromaView, string>`;
  `bandIndexFor(view): 0 | 1 | 2 | null`; `rowCount(view): number`;
  `interface FrameWindow { from: number; to: number }`; `fullWindow(T): FrameWindow`;
  `clampWindow(win, T): FrameWindow`; `zoomWindow(win, factor, anchorFrac, T): FrameWindow`;
  `scrollWindow(win, deltaPx, widthPx, T): FrameWindow`; `frameToX(frame, win, widthPx): number`;
  `xToFrame(x, win, widthPx): number`; `rowHeight(view, heightPx): number`;
  `rowToY(row, view, heightPx): number`; `yToRow(y, view, heightPx): number | null`;
  `rowPitchClass(row, view): number`; `rowCents(row, view): number | null`;
  `cellValue(result: ChromaResult, view: ChromaView, frame: number, row: number): number`;
  `frameColumn(result: ChromaResult, view: ChromaView, frame: number): Float32Array` (the whole
  column for one frame, `rowCount(view)` long — the fold done **once** per frame instead of once
  per row).
- Produces, from `chromaCanvas.ts`: `CHROMA_TOKEN_FALLBACK: Readonly<Record<string, string>>`;
  `chromaColour(el: Element, token: string): string`;
  `fitChromaCanvas(canvas: HTMLCanvasElement): CanvasRenderingContext2D | null`.
- Produces the component `ChromaHeatmap` (props `{ view: ChromaView; win: FrameWindow; result:
  ChromaResult | null; target: Float32Array; detuneCents?: number; onwin?: (w: FrameWindow) => void }`
  — `detuneCents` is Task 11's **`analysisDetuneCents`**, not `clip.detune_cents`: `0` when the
  analysed ref was the already-stretched `clip.previewAudio`, `clip.detune_cents` when it was the
  raw `clip.audio`. See the Normative block's "how much detune to rotate by" row),
  rendering `<canvas data-testid="chroma-heatmap" data-help={HELP.chromaHeatmap}>` and an
  empty-state paragraph `data-testid="chroma-heatmap-empty"` as a **DOM sibling** — never `fillText`,
  which `findByText` can never see (the blocking M4 finding).

- [ ] **Step 1: Write the failing tests**

`latent-forge/src/lib/chroma/__tests__/consonanceColor.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import {
  CELL_C_BASE,
  CELL_C_SPAN,
  CELL_L_SPAN,
  CELL_L_TOP,
  CONSONANT_HUE,
  DISSONANT_HUE,
  LEGEND_C,
  LEGEND_L,
  LEGEND_STOPS,
  TARGET_ROW_HUE,
  consonanceColor,
  consonanceHue,
  legendColor,
  targetRowColor,
} from "../consonanceColor";

describe("consonanceHue (v3 _drawChroma 1186: hue = 60 + (1 - match) * 200)", () => {
  it("is the consonant hue at a perfect match and the dissonant hue at zero", () => {
    expect(consonanceHue(1)).toBe(CONSONANT_HUE);
    expect(consonanceHue(0)).toBe(DISSONANT_HUE);
    expect(DISSONANT_HUE - CONSONANT_HUE).toBe(200);
  });

  it("clamps outside 0..1 rather than running off the hue circle", () => {
    expect(consonanceHue(-3)).toBe(DISSONANT_HUE);
    expect(consonanceHue(9)).toBe(CONSONANT_HUE);
    expect(consonanceHue(Number.NaN)).toBe(DISSONANT_HUE);
  });
});

describe("consonanceColor builds its own oklch() string (HANDOUT.md ramp exception)", () => {
  it("never reads a token: the string is assembled from the named constants", () => {
    expect(consonanceColor(0, 1)).toBe(
      `oklch(${CELL_L_TOP.toFixed(2)}% ${CELL_C_BASE.toFixed(3)} ${CONSONANT_HUE.toFixed(1)})`,
    );
  });

  it("darkens and saturates with the cell's own value", () => {
    expect(consonanceColor(1, 1)).toBe(
      `oklch(${(CELL_L_TOP - CELL_L_SPAN).toFixed(2)}% ${(CELL_C_BASE + CELL_C_SPAN).toFixed(3)} ${CONSONANT_HUE.toFixed(1)})`,
    );
  });

  it("moves hue with the FRAME's match and lightness with the CELL's value", () => {
    expect(consonanceColor(0.5, 0)).not.toBe(consonanceColor(0.5, 1));
    expect(consonanceColor(0.5, 0.5)).toBe("oklch(70.00% 0.115 160.0)");
  });
});

describe("targetRowColor (the reference row across the top, v3 1178)", () => {
  it("uses its own purple hue, so the target never reads as a score", () => {
    expect(targetRowColor(1)).toContain(`${TARGET_ROW_HUE.toFixed(1)})`);
    expect(targetRowColor(0)).toContain(`${TARGET_ROW_HUE.toFixed(1)})`);
    expect(targetRowColor(1)).not.toBe(consonanceColor(1, 1));
  });
});

describe("legendColor (the gradient strip's nine stops, v3 2025-2028)", () => {
  it("walks the same hue axis as the cells, at one fixed lightness and chroma", () => {
    expect(legendColor(0)).toBe(
      `oklch(${LEGEND_L.toFixed(2)}% ${LEGEND_C.toFixed(3)} ${DISSONANT_HUE.toFixed(1)})`,
    );
    expect(legendColor(1)).toBe(
      `oklch(${LEGEND_L.toFixed(2)}% ${LEGEND_C.toFixed(3)} ${CONSONANT_HUE.toFixed(1)})`,
    );
  });

  it("is nine distinct stops wide, as the drawing draws it", () => {
    expect(LEGEND_STOPS).toBe(9);
    const stops = Array.from({ length: LEGEND_STOPS }, (_, i) => legendColor(i / (LEGEND_STOPS - 1)));
    expect(new Set(stops).size).toBe(LEGEND_STOPS);
  });
});
```

`latent-forge/src/lib/chroma/__tests__/heatmapGeometry.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { BINS_PER_SEMITONE } from "../bins";
import type { ChromaResult } from "../chromaClient.svelte";
import {
  BODY_Y,
  CHROMA_VIEWS,
  MIN_VISIBLE_FRAMES,
  REF_GAP,
  REF_ROW_H,
  VIEW_LABELS,
  bandIndexFor,
  cellValue,
  clampWindow,
  frameColumn,
  frameToX,
  fullWindow,
  rowCents,
  rowCount,
  rowHeight,
  rowPitchClass,
  rowToY,
  scrollWindow,
  xToFrame,
  yToRow,
  zoomWindow,
} from "../heatmapGeometry";

function result(T: number): ChromaResult {
  const bands = new Float32Array(3 * 128 * T);
  const fold12 = new Float32Array(12 * T);
  // A value that identifies all three coordinates it was read from.
  for (let b = 0; b < 3; b++) {
    for (let i = 0; i < 128; i++) {
      for (let t = 0; t < T; t++) bands[(b * 128 + i) * T + t] = (b + 1) / 10 + i / 1000 + t / 100000;
    }
  }
  for (let p = 0; p < 12; p++) for (let t = 0; t < T; t++) fold12[p * T + t] = p / 100 + t / 10000;
  return { frames: T, fps: 10.7666015625, bands, fold12, T };
}

describe("the four views spec §5.4 names", () => {
  it("is GLOBAL, BASS oct1, MID oct5, HIGH oct9 in the drawing's order (v3 2012-2015)", () => {
    expect(CHROMA_VIEWS).toEqual(["global", "bass", "mid", "high"]);
    expect(CHROMA_VIEWS.map((v) => VIEW_LABELS[v])).toEqual([
      "GLOBAL",
      "BASS oct1",
      "MID oct5",
      "HIGH oct9",
    ]);
  });

  it("maps the three band views onto bands 0, 1 and 2 and GLOBAL onto none", () => {
    expect(bandIndexFor("global")).toBe(null);
    expect(bandIndexFor("bass")).toBe(0);
    expect(bandIndexFor("mid")).toBe(1);
    expect(bandIndexFor("high")).toBe(2);
  });

  it("is 12 rows for GLOBAL and 128 for every band view", () => {
    expect(rowCount("global")).toBe(12);
    expect(rowCount("bass")).toBe(128);
    expect(rowCount("mid")).toBe(128);
    expect(rowCount("high")).toBe(128);
  });
});

describe("the reference row at the top (v3 1174: refH = 9, bodyY = refH + 2)", () => {
  it("is 9 px with a 2 px gap, so the body starts at 11", () => {
    expect(REF_ROW_H).toBe(9);
    expect(REF_GAP).toBe(2);
    expect(BODY_Y).toBe(11);
  });
});

describe("the visible frame window under middle-drag zoom/scroll (v3 331)", () => {
  it("starts as the whole clip", () => {
    expect(fullWindow(96)).toEqual({ from: 0, to: 96 });
  });

  it("never zooms in past MIN_VISIBLE_FRAMES and never out past the clip", () => {
    expect(zoomWindow({ from: 0, to: 96 }, 1000, 0.5, 96).to - zoomWindow({ from: 0, to: 96 }, 1000, 0.5, 96).from)
      .toBe(MIN_VISIBLE_FRAMES);
    expect(zoomWindow({ from: 20, to: 40 }, 0.001, 0.5, 96)).toEqual({ from: 0, to: 96 });
  });

  it("holds the anchored frame still while zooming in", () => {
    const w = zoomWindow({ from: 0, to: 96 }, 2, 0.5, 96);
    expect(w.to - w.from).toBeCloseTo(48, 9);
    expect(w.from + 0.5 * (w.to - w.from)).toBeCloseTo(48, 9);
  });

  it("scrolls so the content follows the hand, and stops at both ends", () => {
    expect(scrollWindow({ from: 40, to: 60 }, 50, 100, 96)).toEqual({ from: 30, to: 50 });
    expect(scrollWindow({ from: 0, to: 20 }, 500, 100, 96)).toEqual({ from: 0, to: 20 });
    expect(scrollWindow({ from: 76, to: 96 }, -500, 100, 96)).toEqual({ from: 76, to: 96 });
  });

  it("clamps a window wider than the clip, or one hanging off its end", () => {
    expect(clampWindow({ from: -10, to: 500 }, 40)).toEqual({ from: 0, to: 40 });
    expect(clampWindow({ from: 38, to: 44 }, 40)).toEqual({ from: 32, to: 40 });
  });
});

describe("frame <-> x over the visible window", () => {
  it("puts the window's first frame at x = 0 and its end at the right edge", () => {
    expect(frameToX(20, { from: 20, to: 40 }, 200)).toBe(0);
    expect(frameToX(40, { from: 20, to: 40 }, 200)).toBe(200);
    expect(frameToX(30, { from: 20, to: 40 }, 200)).toBe(100);
  });

  it("round-trips a pixel back to its frame, clamped inside the window", () => {
    expect(xToFrame(0, { from: 20, to: 40 }, 200)).toBe(20);
    expect(xToFrame(105, { from: 20, to: 40 }, 200)).toBe(30);
    expect(xToFrame(1e6, { from: 20, to: 40 }, 200)).toBe(39);
    expect(xToFrame(-50, { from: 20, to: 40 }, 200)).toBe(20);
  });
});

describe("row <-> y, with pitch class 0 (C) at the BOTTOM (v3 1184)", () => {
  it("spreads the rows over the body, below the reference row", () => {
    expect(rowHeight("global", 131)).toBeCloseTo(10, 9);
    expect(rowToY(0, "global", 131)).toBeCloseTo(BODY_Y + 110, 9);
    expect(rowToY(11, "global", 131)).toBeCloseTo(BODY_Y, 9);
  });

  it("reads a y back to its row and refuses the reference row entirely", () => {
    expect(yToRow(BODY_Y - 1, "global", 131)).toBe(null);
    expect(yToRow(BODY_Y + 0.5, "global", 131)).toBe(11);
    expect(yToRow(BODY_Y + 110.5, "global", 131)).toBe(0);
    expect(yToRow(1e6, "global", 131)).toBe(0);
  });
});

describe("row -> pitch class, honouring C at bin 2.0 (the same_chroma PITFALL)", () => {
  it("is the row itself in GLOBAL, which has no sub-semitone detail", () => {
    expect(rowPitchClass(0, "global")).toBe(0);
    expect(rowPitchClass(9, "global")).toBe(9);
    expect(rowCents(9, "global")).toBe(null);
  });

  it("puts C at bin 2 and A at bin 98 in a band view, not C at bin 0", () => {
    expect(rowPitchClass(2, "bass")).toBe(0);
    expect(rowPitchClass(98, "mid")).toBe(9);
    expect(rowCents(2, "bass")).toBe(0);
    expect(rowCents(98, "mid")).toBe(0);
  });

  it("reports cents off the class centre, wrapping over the top of the band", () => {
    expect(rowCents(3, "bass")).toBe(Math.round((1 / BINS_PER_SEMITONE) * 100));
    expect(rowCents(3, "bass")).toBe(9);
    expect(rowCents(124, "high")).toBe(44);   // B's centre is 119.333
    expect(rowCents(125, "high")).toBe(-47);  // C again, 5 bins below 2 + 128
  });
});

describe("cellValue reads the right axis out of a C-order payload", () => {
  it("takes GLOBAL directly from the transported fold12, not a local re-fold of bands", () => {
    // WINTERMUTE, 2026-09-22: §5.4's GLOBAL (the three bands summed through
    // fold_to_12, per-frame normalised to max 1) IS the server's transported
    // fold12 -- the client never re-derives it from `bands`. So this fixture's
    // fold12 (p/100 + t/10000, see result() above) is what cellValue must
    // return verbatim; there is no local normalisation left to assert on.
    const res = result(4);
    const col = Array.from({ length: 12 }, (_, p) => cellValue(res, "global", 2, p));
    for (let p = 0; p < 12; p++) expect(col[p]).toBeCloseTo(p / 100 + 2 / 10000, 9);
  });

  it("takes a band view from that band's own 128 raw bins", () => {
    const res = result(4);
    expect(cellValue(res, "bass", 3, 7)).toBeCloseTo(0.1 + 7 / 1000 + 3 / 100000, 6);
    expect(cellValue(res, "mid", 3, 7)).toBeCloseTo(0.2 + 7 / 1000 + 3 / 100000, 6);
    expect(cellValue(res, "high", 3, 7)).toBeCloseTo(0.3 + 7 / 1000 + 3 / 100000, 6);
  });

  it("frameColumn folds the frame ONCE and agrees with cellValue row for row", () => {
    // The heatmap draws a whole column per frame, so the folding cellValue
    // does per row is repeated twelve times for one frame's worth of pixels.
    // frameColumn is the same numbers computed once -- pinned here so the two
    // paths can never drift apart.
    const res = result(4);
    const global = frameColumn(res, "global", 2);
    expect(global).toHaveLength(12);
    for (let r = 0; r < 12; r++) expect(global[r]).toBeCloseTo(cellValue(res, "global", 2, r), 9);
    const bass = frameColumn(res, "bass", 3);
    expect(bass).toHaveLength(128);
    for (let r = 0; r < 128; r++) expect(bass[r]).toBeCloseTo(cellValue(res, "bass", 3, r), 9);
  });
});
```

`latent-forge/src/ui/chroma/__tests__/chromaCanvas.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { CHROMA_TOKEN_FALLBACK, chromaColour, fitChromaCanvas } from "../chromaCanvas";

afterEach(() => {
  document.body.innerHTML = "";
  vi.restoreAllMocks();
});

describe("chromaColour (HANDOUT.md: in jsdom, seed tokens INLINE, never from a <style> block)", () => {
  it("returns an inline-seeded token exactly", () => {
    const el = document.createElement("div");
    el.style.setProperty("--border", "oklch(80% 0.014 240)");
    document.body.append(el);
    expect(chromaColour(el, "--border")).toBe("oklch(80% 0.014 240)");
  });

  it("falls back per token when the property is undefined, never to the empty string", () => {
    const el = document.createElement("div");
    document.body.append(el);
    // ctx.fillStyle = "" is a SILENT no-op that leaves the previous colour.
    expect(chromaColour(el, "--border")).toBe(CHROMA_TOKEN_FALLBACK["--border"]);
    expect(chromaColour(el, "--border")).not.toBe("");
  });

  it("still returns a visible colour for a token it has never heard of", () => {
    const el = document.createElement("div");
    document.body.append(el);
    expect(chromaColour(el, "--not-a-token").length).toBeGreaterThan(0);
  });
});

describe("fitChromaCanvas", () => {
  it("returns null for a zero-sized canvas rather than painting into nothing", () => {
    const canvas = document.createElement("canvas");
    document.body.append(canvas);
    expect(fitChromaCanvas(canvas)).toBe(null);
  });
});
```

`latent-forge/src/ui/chroma/__tests__/ChromaHeatmap.component.test.ts`:

```ts
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ChromaResult } from "../../../lib/chroma/chromaClient.svelte";
import { consonanceColor } from "../../../lib/chroma/consonanceColor";
import { matchFrame } from "../../../lib/chroma/match";
import { HELP } from "../../../lib/help/strings";
import ChromaHeatmap from "../ChromaHeatmap.svelte";

type Call = { kind: "call"; name: string; args: unknown[] } | { kind: "set"; name: string; value: unknown };

function fakeContext() {
  const calls: Call[] = [];
  const ctx: Record<string, unknown> = {};
  for (const m of ["fillRect", "strokeRect", "beginPath", "moveTo", "lineTo", "stroke", "fillText", "clearRect", "setTransform"]) {
    ctx[m] = (...args: unknown[]) => { calls.push({ kind: "call", name: m, args }); };
  }
  for (const p of ["fillStyle", "strokeStyle", "lineWidth", "globalAlpha", "font", "textAlign", "textBaseline"]) {
    let v: unknown;
    Object.defineProperty(ctx, p, {
      get: () => v,
      set: (nv: unknown) => { v = nv; calls.push({ kind: "set", name: p, value: nv }); },
    });
  }
  return { ctx: ctx as unknown as CanvasRenderingContext2D, calls };
}

/** One clip whose only energy is C: bin 2 of band 0, and class 0 of the fold. */
function res(T: number): ChromaResult {
  const bands = new Float32Array(3 * 128 * T);
  const fold12 = new Float32Array(12 * T);
  for (let t = 0; t < T; t++) {
    bands[(0 * 128 + 2) * T + t] = 1;
    fold12[0 * T + t] = 1;
  }
  return { frames: T, fps: 10.7666015625, bands, fold12, T };
}

const TARGET = Float32Array.from([1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0]);

beforeEach(() => {
  // jsdom lays nothing out, so fitChromaCanvas would bail on w <= 0.
  Object.defineProperty(HTMLCanvasElement.prototype, "clientWidth", { configurable: true, get: () => 400 });
  Object.defineProperty(HTMLCanvasElement.prototype, "clientHeight", { configurable: true, get: () => 131 });
});

afterEach(() => {
  delete (HTMLCanvasElement.prototype as unknown as Record<string, unknown>).clientWidth;
  delete (HTMLCanvasElement.prototype as unknown as Record<string, unknown>).clientHeight;
  vi.restoreAllMocks();
  cleanup();
});

describe("ChromaHeatmap's DOM contract", () => {
  it("carries M1 T14's own id, HELP.chromaHeatmap (v3 line 344)", () => {
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(fakeContext().ctx);
    const { getByTestId } = render(ChromaHeatmap, {
      props: { view: "global", win: { from: 0, to: 4 }, result: res(4), target: TARGET },
    });
    expect(getByTestId("chroma-heatmap").getAttribute("data-help")).toBe(HELP.chromaHeatmap);
  });

  it("says so in the DOM when there is nothing to draw, never with fillText", () => {
    const fake = fakeContext();
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(fake.ctx);
    const { getByText } = render(ChromaHeatmap, {
      props: { view: "global", win: { from: 0, to: 1 }, result: null, target: TARGET },
    });
    // Findable by text == a real DOM node. A fillText label never can be (M4).
    expect(getByText("no chroma yet")).toBeTruthy();
    expect(fake.calls.some((c) => c.kind === "call" && c.name === "fillText")).toBe(false);
  });
});

describe("ChromaHeatmap draws the view it is given (spec §5.4)", () => {
  it("fills the background, the 12 reference cells, and one cell per lit row", () => {
    const fake = fakeContext();
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(fake.ctx);
    render(ChromaHeatmap, {
      props: { view: "global", win: { from: 0, to: 4 }, result: res(4), target: TARGET },
    });
    const fills = fake.calls.filter((c) => c.kind === "call" && c.name === "fillRect").length;
    // 1 background + 12 reference cells + 4 frames x 1 class above CELL_FLOOR
    expect(fills).toBe(1 + 12 + 4);
  });

  it("reads a band view out of that band's own 128 rows", () => {
    const fake = fakeContext();
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(fake.ctx);
    render(ChromaHeatmap, {
      props: { view: "bass", win: { from: 0, to: 4 }, result: res(4), target: TARGET },
    });
    const fills = fake.calls.filter((c) => c.kind === "call" && c.name === "fillRect").length;
    // only bin 2 of band 0 is above CELL_FLOOR in this fixture
    expect(fills).toBe(1 + 12 + 4);
  });

  it("colours a cell from the ramp, and never assigns the empty string", () => {
    const fake = fakeContext();
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(fake.ctx);
    render(ChromaHeatmap, {
      props: { view: "global", win: { from: 0, to: 4 }, result: res(4), target: TARGET },
    });
    const styles = fake.calls
      .filter((c) => c.kind === "set" && c.name === "fillStyle")
      .map((c) => (c as { value: unknown }).value);
    // NOT consonanceColor(1, 1). TARGET is [1,0,0,0,1,0,0,1,0,0,0,0] (classes
    // 0, 4, 7) and each frame's fold12 column is [1,0,...], so with matchFrame's
    // DIRECTED distance (frame class 0 against target classes 0, 4 and 7: the
    // distances are ((0-0)%12+12)%12=0, ((0-4)%12+12)%12=8 and
    // ((0-7)%12+12)%12=5) the frame's match is num/den =
    // (W[0] + W[8] + W[5]) / 3 = (1.0 + 0.66 + 0.82) / 3 = 0.8266..., not 1.
    // Compute the expectation rather than assuming a saturated frame.
    const frameMatch = matchFrame(Float32Array.from([1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]), TARGET);
    expect(styles).toContain(consonanceColor(1, frameMatch));
    expect(styles).not.toContain("");
  });
});

describe("ChromaHeatmap's middle-drag gesture (v3 331: up/down zooms, left/right scrolls)", () => {
  it("reports a narrower window when the middle button is dragged upward", async () => {
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(fakeContext().ctx);
    let seen: { from: number; to: number } | null = null;
    const { getByTestId } = render(ChromaHeatmap, {
      props: {
        view: "global", win: { from: 0, to: 96 }, result: res(96), target: TARGET,
        onwin: (w: { from: number; to: number }) => { seen = w; },
      },
    });
    const canvas = getByTestId("chroma-heatmap");
    vi.spyOn(canvas, "getBoundingClientRect").mockReturnValue({
      left: 0, top: 0, width: 400, height: 131, right: 400, bottom: 131, x: 0, y: 0, toJSON: () => ({}),
    });
    await fireEvent.pointerDown(canvas, { button: 1, clientX: 200, clientY: 60, pointerId: 1 });
    await fireEvent.pointerMove(canvas, { clientX: 200, clientY: 10, pointerId: 1 });
    expect(seen).not.toBe(null);
    expect(seen!.to - seen!.from).toBeLessThan(96);
  });

  it("recomputes from the drag's start each move, so reversing the pointer returns exactly to the start window", async () => {
    // A regression test for compounding: if each move zoomed the CURRENT
    // window instead of re-deriving from drag.startWin, ending back at the
    // pointer's start position would not generally restore the start window
    // once a step in between has been clamped -- and even short of a clamp,
    // compounding two inverse multiplicative factors is not exactly identity
    // in floating point the way "recompute from a fixed start" is.
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(fakeContext().ctx);
    let seen: { from: number; to: number } | null = null;
    const START = { from: 0, to: 96 };
    const { getByTestId } = render(ChromaHeatmap, {
      props: {
        view: "global", win: START, result: res(96), target: TARGET,
        onwin: (w: { from: number; to: number }) => { seen = w; },
      },
    });
    const canvas = getByTestId("chroma-heatmap");
    vi.spyOn(canvas, "getBoundingClientRect").mockReturnValue({
      left: 0, top: 0, width: 400, height: 131, right: 400, bottom: 131, x: 0, y: 0, toJSON: () => ({}),
    });
    await fireEvent.pointerDown(canvas, { button: 1, clientX: 200, clientY: 60, pointerId: 1 });
    await fireEvent.pointerMove(canvas, { clientX: 260, clientY: 10, pointerId: 1 }); // zoom in + scroll
    await fireEvent.pointerMove(canvas, { clientX: 200, clientY: 60, pointerId: 1 }); // back to the start point
    expect(seen).toEqual(START);
  });

  it("ignores a plain left-drag, which belongs to hover (Task 10)", async () => {
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(fakeContext().ctx);
    let seen: { from: number; to: number } | null = null;
    const { getByTestId } = render(ChromaHeatmap, {
      props: {
        view: "global", win: { from: 0, to: 96 }, result: res(96), target: TARGET,
        onwin: (w: { from: number; to: number }) => { seen = w; },
      },
    });
    const canvas = getByTestId("chroma-heatmap");
    await fireEvent.pointerDown(canvas, { button: 0, clientX: 200, clientY: 60, pointerId: 1 });
    await fireEvent.pointerMove(canvas, { clientX: 200, clientY: 10, pointerId: 1 });
    expect(seen).toBe(null);
  });
});
```

- [ ] **Step 2: Run the tests — they must fail**

```bash
cd latent-forge && npx vitest run src/lib/chroma/__tests__/consonanceColor.test.ts src/lib/chroma/__tests__/heatmapGeometry.test.ts src/ui/chroma/__tests__/chromaCanvas.test.ts src/ui/chroma/__tests__/ChromaHeatmap.component.test.ts
```

Expected: four failed suites, each on module resolution —
`Failed to resolve import "../consonanceColor"`, `Failed to resolve import "../heatmapGeometry"`,
`Failed to resolve import "../chromaCanvas"` and
`Failed to resolve import "../ChromaHeatmap.svelte"`.

- [ ] **Step 3: Write the ramp, the geometry, the canvas helpers and the component**

`latent-forge/src/lib/chroma/consonanceColor.ts`:

```ts
// The chroma heatmap's colour ramp (spec §5.4; v3 _drawChroma 1183-1190 and
// legendStops 2025-2028).
//
// THIS IS THE ONE DOCUMENTED EXCEPTION to "canvas colours come from
// getComputedStyle" (docs/latent-forge/HANDOUT.md). An unregistered custom
// property is NOT resolved by the engine, so
// getComputedStyle(el).getPropertyValue("--token") hands back the literal
// token STREAM -- the string "oklch(78% 0.08 250)" -- with no channels in it.
// That string is fine to assign straight to ctx.fillStyle, and FATAL to parse:
// a digit regex over it yields rgb(78, 0, 250), an indigo. A ramp needs three
// channels to interpolate, so it builds its own oklch() string, exactly as
// M5's downbeatColor (lib/math/downbeats.ts) and M10's xcorrColor
// (lib/stats/xcorrColor.ts) do. Do not "fix" this back into a token read.
//
// Two axes, deliberately independent:
//   HUE  carries the FRAME's harmonic match against the target -- consonant
//        frames run warm (60), dissonant ones cold (260).
//   L/C  carry the CELL's own energy, so a loud bin is dark and saturated and
//        a quiet one nearly disappears into the panel.

/** Hue at match = 1. */
export const CONSONANT_HUE = 60;
/** Hue at match = 0. v3: 60 + (1 - m) * 200. */
export const DISSONANT_HUE = 260;

export const CELL_L_TOP = 94;
export const CELL_L_SPAN = 48;
export const CELL_C_BASE = 0.02;
export const CELL_C_SPAN = 0.19;

/** The target reference row has its own hue so it never reads as a score. */
export const TARGET_ROW_HUE = 300;
export const TARGET_L_TOP = 90;
export const TARGET_L_SPAN = 46;
export const TARGET_C_BASE = 0.02;
export const TARGET_C_SPAN = 0.12;

/** The legend strip: one lightness and chroma, the hue axis alone (v3 2027). */
export const LEGEND_L = 58;
export const LEGEND_C = 0.17;
export const LEGEND_STOPS = 9;

function unit(v: number): number {
  return Number.isFinite(v) ? (v < 0 ? 0 : v > 1 ? 1 : v) : 0;
}

function oklch(l: number, c: number, h: number): string {
  return `oklch(${l.toFixed(2)}% ${c.toFixed(3)} ${h.toFixed(1)})`;
}

/** Hue for a harmonic-overlap score in 0..1. Clamped; NaN reads as dissonant. */
export function consonanceHue(match: number): number {
  return DISSONANT_HUE + (CONSONANT_HUE - DISSONANT_HUE) * unit(match);
}

/** One heatmap cell: `value` is the bin/class energy, `match` its frame's score. */
export function consonanceColor(value: number, match: number): string {
  const v = unit(value);
  return oklch(CELL_L_TOP - CELL_L_SPAN * v, CELL_C_BASE + CELL_C_SPAN * v, consonanceHue(match));
}

/** One cell of the target's reference row across the top of the heatmap. */
export function targetRowColor(value: number): string {
  const v = unit(value);
  return oklch(TARGET_L_TOP - TARGET_L_SPAN * v, TARGET_C_BASE + TARGET_C_SPAN * v, TARGET_ROW_HUE);
}

/** One stop of the legend gradient; `t` runs 0 (dissonant) .. 1 (consonant). */
export function legendColor(t: number): string {
  return oklch(LEGEND_L, LEGEND_C, consonanceHue(t));
}
```

`latent-forge/src/lib/chroma/heatmapGeometry.ts`:

```ts
// Pure geometry for the chroma heatmap (spec §5.4). Kept out of the component
// for the reason M5 T5 gives for the lane canvas: jsdom has no
// CanvasRenderingContext2D, so every piece of DECIDABLE geometry lives here
// where vitest can pin it, and the component only turns these answers into
// fillRect calls.
//
// Two coordinate facts everything else depends on:
//   * pitch class 0 (C) is drawn at the BOTTOM row, as the drawing does it
//     (v3 1184: bodyY + (rows - 1 - r) * rowH);
//   * in a band view the row index IS the raw bin index, and C sits at bin
//     2.0, not 0 -- the same_chroma PITFALL. Row -> class goes through Task
//     1's binToPitchClass, never through (row / 128) * 12, which is what the
//     drawing's own hover does and which is wrong by two bins everywhere.

import { BINS_PER_BAND, BINS_PER_SEMITONE, binToPitchClass, fold12Column, pitchClassToBin } from "./bins";
import type { ChromaResult } from "./chromaClient.svelte";

/** The target's reference row, v3 1174. */
export const REF_ROW_H = 9;
export const REF_GAP = 2;
export const BODY_Y = REF_ROW_H + REF_GAP;

/** Zooming past this stops being a heatmap and starts being a bar chart. */
export const MIN_VISIBLE_FRAMES = 8;

/** v3 1187 skips a cell below this; at 128 rows that is most of them. */
export const CELL_FLOOR = 0.04;

export type ChromaView = "global" | "bass" | "mid" | "high";

export const CHROMA_VIEWS: readonly ChromaView[] = ["global", "bass", "mid", "high"];

export const VIEW_LABELS: Record<ChromaView, string> = {
  global: "GLOBAL",
  bass: "BASS oct1",
  mid: "MID oct5",
  high: "HIGH oct9",
};

export function bandIndexFor(view: ChromaView): 0 | 1 | 2 | null {
  return view === "bass" ? 0 : view === "mid" ? 1 : view === "high" ? 2 : null;
}

export function rowCount(view: ChromaView): number {
  return view === "global" ? 12 : BINS_PER_BAND;
}

/** Half-open [from, to), in frames. */
export interface FrameWindow {
  from: number;
  to: number;
}

export function clampWindow(win: FrameWindow, T: number): FrameWindow {
  const total = Math.max(1, Math.floor(T));
  const floor = Math.min(MIN_VISIBLE_FRAMES, total);
  const span = Math.min(total, Math.max(floor, win.to - win.from));
  const from = Math.min(Math.max(0, win.from), total - span);
  return { from, to: from + span };
}

export function fullWindow(T: number): FrameWindow {
  return clampWindow({ from: 0, to: Math.max(1, Math.floor(T)) }, T);
}

/**
 * `factor > 1` zooms IN (fewer frames), matching M5 T3's
 * middleDragZoomFactor, which returns > 1 for a negative deltaY (an upward
 * drag). `anchorFrac` is the pointer's position across the canvas, 0..1; the
 * frame under it stays put.
 */
export function zoomWindow(win: FrameWindow, factor: number, anchorFrac: number, T: number): FrameWindow {
  const total = Math.max(1, Math.floor(T));
  const span = win.to - win.from;
  const anchor = win.from + anchorFrac * span;
  const floor = Math.min(MIN_VISIBLE_FRAMES, total);
  const f = Number.isFinite(factor) && factor > 0 ? factor : 1;
  const next = Math.min(total, Math.max(floor, span / f));
  const from = anchor - anchorFrac * next;
  return clampWindow({ from, to: from + next }, T);
}

/** Content follows the hand: a rightward drag reveals EARLIER frames. */
export function scrollWindow(win: FrameWindow, deltaPx: number, widthPx: number, T: number): FrameWindow {
  const span = win.to - win.from;
  const perPx = span / Math.max(1, widthPx);
  const from = win.from - deltaPx * perPx;
  return clampWindow({ from, to: from + span }, T);
}

export function frameToX(frame: number, win: FrameWindow, widthPx: number): number {
  const span = Math.max(1e-9, win.to - win.from);
  return ((frame - win.from) / span) * widthPx;
}

export function xToFrame(x: number, win: FrameWindow, widthPx: number): number {
  const span = Math.max(1e-9, win.to - win.from);
  const raw = Math.floor(win.from + (x / Math.max(1, widthPx)) * span);
  const lo = Math.floor(win.from);
  const hi = Math.ceil(win.to) - 1;
  return raw < lo ? lo : raw > hi ? hi : raw;
}

export function rowHeight(view: ChromaView, heightPx: number): number {
  return Math.max(0, heightPx - BODY_Y) / rowCount(view);
}

/** Row 0 (C, or bin 0) sits at the BOTTOM -- v3 1184. */
export function rowToY(row: number, view: ChromaView, heightPx: number): number {
  return BODY_Y + (rowCount(view) - 1 - row) * rowHeight(view, heightPx);
}

/** null inside the reference row, which is the target's, not the clip's. */
export function yToRow(y: number, view: ChromaView, heightPx: number): number | null {
  if (y < BODY_Y) return null;
  const rows = rowCount(view);
  const rh = rowHeight(view, heightPx);
  if (rh <= 0) return null;
  const row = rows - 1 - Math.floor((y - BODY_Y) / rh);
  return row < 0 ? 0 : row > rows - 1 ? rows - 1 : row;
}

export function rowPitchClass(row: number, view: ChromaView): number {
  return view === "global" ? ((row % 12) + 12) % 12 : binToPitchClass(row);
}

/** Cents off the class centre for a band row; null for GLOBAL, which has none. */
export function rowCents(row: number, view: ChromaView): number | null {
  if (view === "global") return null;
  const centre = pitchClassToBin(binToPitchClass(row));
  let d = row - centre;
  // The band wraps: bin 125 is five bins BELOW C's next centre at 2 + 128.
  while (d > BINS_PER_BAND / 2) d -= BINS_PER_BAND;
  while (d < -BINS_PER_BAND / 2) d += BINS_PER_BAND;
  return Math.round((d / BINS_PER_SEMITONE) * 100);
}

/**
 * The value drawn in one cell. GLOBAL reads the server's own transported
 * fold12 -- §5.4's definition ("sum the three bands through fold_to_12, then
 * per-frame normalise to max 1") is exactly what the server computes and
 * ships as fold12 (M2 T12's chroma_payload, at `scale: 1.0` because the
 * values are already in [0,1] per frame, not because 1.0 is a whole-clip
 * scale). WINTERMUTE's 2026-09-22 ruling: this is the SAME array the
 * match/scan/clip-score path reads, so there is no second, client-side fold
 * to compute here. A band view is that band's raw 128 bins, untouched.
 */
export function cellValue(result: ChromaResult, view: ChromaView, frame: number, row: number): number {
  const band = bandIndexFor(view);
  if (band === null) return fold12Column(result.fold12, result.T, frame)[((row % 12) + 12) % 12];
  return result.bands[(band * BINS_PER_BAND + row) * result.T + frame];
}

/**
 * The whole column for one frame -- rowCount(view) values, in the same order
 * cellValue returns them row by row.
 *
 * For a band view this is a genuine batching win, unchanged by the fold
 * decision below: cellValue's band branch is already a single array read, so
 * nothing here saves it any work beyond what materialising the 128 bins once
 * always saved.
 *
 * For GLOBAL the saving is smaller than it used to be, but it has not gone
 * away. Before WINTERMUTE's 2026-09-22 ruling, cellValue's GLOBAL branch
 * re-folded all 3 x 128 raw bins on every call; now that GLOBAL just reads the
 * transported fold12, cellValue's GLOBAL branch is fold12Column(...)[row] --
 * but fold12Column still allocates and fills a fresh Float32Array(12) on
 * EVERY call, regardless of which single row the caller wanted. A row loop
 * over GLOBAL's twelve rows would still call fold12Column twelve times for
 * one frame's pixels -- including on every pointermove of a middle-drag.
 * Fold once, index twelve times: frameColumn keeps exactly that shape, even
 * though what it now saves is "one Float32Array(12) build" per frame rather
 * than "one 384-bin sum" per frame. Dropping it because the saving got
 * smaller would still be dropping a real, reachable cost.
 *
 * cellValue stays the hover path's accessor (Task 10), which reads one cell
 * and has no row loop to batch.
 */
export function frameColumn(result: ChromaResult, view: ChromaView, frame: number): Float32Array {
  const band = bandIndexFor(view);
  if (band === null) return fold12Column(result.fold12, result.T, frame);
  const out = new Float32Array(BINS_PER_BAND);
  for (let i = 0; i < BINS_PER_BAND; i++) {
    out[i] = result.bands[(band * BINS_PER_BAND + i) * result.T + frame];
  }
  return out;
}
```

`latent-forge/src/ui/chroma/chromaCanvas.ts`:

```ts
// Canvas plumbing shared by every canvas in the CHROMA tab.
//
// chromaColour() is the FLAT-colour path: borders, separators, tick labels,
// the red detune mark. Those come from getComputedStyle, per the project's
// canvas rule -- it is only a RAMP that must build its own oklch() string
// (see consonanceColor.ts).
//
// The per-token fallback is not defensive padding. HANDOUT.md measured it: an
// undefined custom property returns "", and `ctx.fillStyle = ""` is a SILENT
// NO-OP that leaves the previous colour on the context. In the app tokens.css
// is loaded and the fallback never fires; in a bare component render, or a
// test that forgot to seed a token, it is the difference between a readable
// canvas and garbage. (M1 T13's panelColour has no fallback, which is why this
// milestone does not reuse it -- see the plan's open questions.)

// COPIED VERBATIM from M1 T12's tokens.css :root block (M1:2925-2937) -- NOT
// from v3's canvas literals, which is where an earlier draft of this table
// came from and where every one of these eight values was subtly wrong:
// --panel carried --bg's 96%, --red was 58%/0.170 rather than 55%/0.20,
// --purple-strong was hue 285 rather than 300. A fallback that does not match
// the real token is worse than no fallback at all -- it silently renders a
// DIFFERENT canvas in exactly the situation it exists for. If tokens.css
// changes, this table changes in the same commit.
const FALLBACK: Record<string, string> = {
  "--panel": "oklch(93% 0.008 240)",
  "--panel2": "oklch(90% 0.012 240)",
  "--border": "oklch(80% 0.014 240)",
  "--text": "oklch(27% 0.02 250)",
  "--text-dim": "oklch(52% 0.016 250)",
  "--red": "oklch(55% 0.20 25)",
  "--turq-strong": "oklch(55% 0.11 195)",
  "--purple-strong": "oklch(54% 0.10 300)",
};

const LAST_RESORT = "oklch(58% 0.014 240)";

export const CHROMA_TOKEN_FALLBACK: Readonly<Record<string, string>> = FALLBACK;

export function chromaColour(el: Element, token: string): string {
  const raw = getComputedStyle(el).getPropertyValue(token).trim();
  if (raw) return raw;
  return FALLBACK[token] ?? LAST_RESORT;
}

export function fitChromaCanvas(canvas: HTMLCanvasElement): CanvasRenderingContext2D | null {
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth;
  const h = canvas.clientHeight;
  if (w <= 0 || h <= 0) return null;
  if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
  }
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  return ctx;
}
```

`latent-forge/src/ui/chroma/ChromaHeatmap.svelte`:

```svelte
<script lang="ts">
  // The chroma heatmap (spec §5.4; v3 markup 343-344, logic _drawChroma
  // 1160-1215). Four views; the target's profile as a reference row across the
  // top; middle-drag zooms the frame axis (up/down) and scrolls it
  // (left/right) in one gesture, as the timeline ruler does -- INCLUDING M5
  // T3's convention that the gesture is anchored to the START of the drag,
  // not the previous pointermove: re-derive the absolute window from the
  // window the drag started with every move, rather than compounding onto
  // the already-clamped prop from the last move. Compounding onto `win`
  // (which clampWindow may already have floored or ceilinged) makes the
  // gesture non-reversible once a drag hits either bound and the pointer
  // reverses -- the same bug M5 T3's own comment exists to prevent.
  //
  // This component owns NO state but the gesture: the window arrives as a prop
  // and goes back out through onwin, so Task 11's tab is its single owner and
  // the match-curve overlay (Task 7) is guaranteed to be drawing the same
  // frames underneath the same pixels.
  //
  // Colours: the CELL ramp builds its own oklch() string (consonanceColor.ts,
  // whose comment says why); every flat colour goes through chromaColour(),
  // which has a per-token fallback because ctx.fillStyle = "" silently keeps
  // whatever colour was there before.
  //
  // DETUNE: `detuneCents` is the ANALYSIS detune (Task 11's
  // analysisDetuneCents), not the clip's. When the analysed audio was the
  // stretched preview it is 0, because M5 T10's runStretch already shifted
  // that audio by clip.detune_cents / 100 and rotating the fold again would
  // apply the detune twice.
  import { fold12Column } from "../../lib/chroma/bins";
  import type { ChromaResult } from "../../lib/chroma/chromaClient.svelte";
  import { consonanceColor, targetRowColor } from "../../lib/chroma/consonanceColor";
  import {
    BODY_Y,
    CELL_FLOOR,
    type ChromaView,
    type FrameWindow,
    REF_ROW_H,
    cellValue,
    frameColumn,
    frameToX,
    rowCount,
    rowHeight,
    rowToY,
    scrollWindow,
    zoomWindow,
  } from "../../lib/chroma/heatmapGeometry";
  import { matchFrame, rotate } from "../../lib/chroma/match";
  import { HELP } from "../../lib/help/strings";
  import { middleDragZoomFactor } from "../../lib/math/ruler";
  import { chromaColour, fitChromaCanvas } from "./chromaCanvas";

  interface Props {
    view: ChromaView;
    win: FrameWindow;
    result: ChromaResult | null;
    target: Float32Array;
    /**
     * The ANALYSIS detune, NOT `clip.detune_cents`. Task 11 derives it as
     * `analysisDetuneCents`: 0 when the analysed ref was `clip.previewAudio`
     * (M5 T10's runStretch already pitch-shifted that audio by the clip's
     * detune, so the fold12 in `result` is already detuned and rotating it
     * again would apply the detune twice), and `clip.detune_cents` when the
     * analysed ref was the raw `clip.audio`. Never re-derive the rule here.
     */
    detuneCents?: number;
    onwin?: (w: FrameWindow) => void;
  }
  let { view, win, result, target, detuneCents = 0, onwin }: Props = $props();

  let canvasEl = $state<HTMLCanvasElement>();
  // startWin is `win` AS IT STOOD when the drag began -- every move below
  // recomputes from it, never from the current `win` prop, so the gesture
  // stays reversible even after clampWindow has floored or ceilinged it.
  let drag: { startX: number; startY: number; anchorFrac: number; startWin: FrameWindow } | null = null;

  function draw(): void {
    const canvas = canvasEl;
    if (!canvas) return;
    const ctx = fitChromaCanvas(canvas);
    if (!ctx) return;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;

    ctx.fillStyle = chromaColour(canvas, "--panel2");
    ctx.fillRect(0, 0, w, h);
    if (!result) return;

    // The reference row: the target itself, twelve cells wide.
    const refW = w / 12;
    for (let p = 0; p < 12; p++) {
      ctx.fillStyle = targetRowColor(target[p] ?? 0);
      ctx.fillRect(p * refW, 0, refW, REF_ROW_H);
    }

    const rows = rowCount(view);
    const rh = rowHeight(view, h);
    const semis = detuneCents / 100;
    const from = Math.max(0, Math.floor(win.from));
    const to = Math.min(result.T, Math.ceil(win.to));
    const colW = Math.max(0.5, w / Math.max(1, to - from));

    for (let f = from; f < to; f++) {
      const m = matchFrame(rotate(fold12Column(result.fold12, result.T, f), semis), target);
      const x = frameToX(f, win, w);
      // GLOBAL: fold this frame ONCE. cellValue's GLOBAL branch folds all 384
      // bins and returns one class, so calling it inside the row loop folded
      // the same frame twelve times per repaint -- including on every
      // pointermove of a middle-drag. A band view's rows are single array
      // reads, so it keeps cellValue and materialises nothing.
      const col = view === "global" ? frameColumn(result, view, f) : null;
      for (let r = 0; r < rows; r++) {
        const v = col ? col[r] : cellValue(result, view, f, r);
        if (v < CELL_FLOOR) continue;
        ctx.fillStyle = consonanceColor(v, m);
        ctx.fillRect(x, rowToY(r, view, h), colW + 0.6, Math.max(0.7, rh + 0.4));
      }
    }

    // Pitch-class separators, so 128 raw bins stay readable as twelve classes.
    ctx.strokeStyle = chromaColour(canvas, "--border");
    ctx.lineWidth = 1;
    ctx.globalAlpha = 0.55;
    for (let p = 1; p < 12; p++) {
      const y = Math.round(BODY_Y + (h - BODY_Y) * (1 - p / 12)) + 0.5;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  }

  function onPointerDown(e: PointerEvent): void {
    if (e.button !== 1) return; // middle only: left is hover (Task 10)
    e.preventDefault();
    const canvas = canvasEl;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    drag = {
      startX: e.clientX, startY: e.clientY, startWin: win,
      anchorFrac: (e.clientX - rect.left) / Math.max(1, rect.width),
    };
    canvas.setPointerCapture?.(e.pointerId);
  }

  function onPointerMove(e: PointerEvent): void {
    const canvas = canvasEl;
    if (!drag || !canvas || !result) return;
    const rect = canvas.getBoundingClientRect();
    // Both deltas are measured from the START of the drag (drag.startX/Y),
    // never from the previous move, and both apply to drag.startWin, never
    // to the current `win` prop -- see the WHY comment above the component.
    const totalDy = e.clientY - drag.startY;
    const totalDx = e.clientX - drag.startX;
    let next = zoomWindow(drag.startWin, middleDragZoomFactor(totalDy), drag.anchorFrac, result.T);
    next = scrollWindow(next, totalDx, Math.max(1, rect.width), result.T);
    onwin?.(next);
  }

  function onPointerUp(e: PointerEvent): void {
    drag = null;
    canvasEl?.releasePointerCapture?.(e.pointerId);
  }

  $effect(() => {
    void view;
    void win;
    void result;
    void target;
    void detuneCents;
    draw();
  });
</script>

<div class="wrap">
  <canvas
    bind:this={canvasEl}
    data-testid="chroma-heatmap"
    data-help={HELP.chromaHeatmap}
    onpointerdown={onPointerDown}
    onpointermove={onPointerMove}
    onpointerup={onPointerUp}
    onpointercancel={onPointerUp}
  ></canvas>
  {#if !result}
    <p class="empty" data-testid="chroma-heatmap-empty">no chroma yet</p>
  {/if}
</div>

<style>
  .wrap {
    position: relative;
    flex: 1;
    min-width: 0;
    min-height: 0;
  }
  canvas {
    display: block;
    width: 100%;
    height: 100%;
    box-sizing: border-box;
    border: 1px solid var(--border);
  }
  .empty {
    position: absolute;
    inset: 0;
    margin: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 10px;
    color: var(--text-dim);
    pointer-events: none;
  }
</style>
```

- [ ] **Step 4: Run them, expect pass**

```bash
cd latent-forge && npx vitest run src/lib/chroma/__tests__/consonanceColor.test.ts src/lib/chroma/__tests__/heatmapGeometry.test.ts src/ui/chroma/__tests__/chromaCanvas.test.ts src/ui/chroma/__tests__/ChromaHeatmap.component.test.ts && npm run check
```

Expected: `Test Files  4 passed (4)` / `Tests  39 passed (39)` — 8 in `consonanceColor.test.ts`,
19 in `heatmapGeometry.test.ts` (one added by the 2026-09-22 critic's `frameColumn` fix),
4 in `chromaCanvas.test.ts` and 8 in `ChromaHeatmap.component.test.ts` (one added by the
2026-09-22 critic fix below) — and `svelte-check found 0 errors and 0 warnings`.

- [ ] **Step 5: Commit**

```bash
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M6 T6: chroma heatmap -- pure geometry (C on the bottom row, bin-2.0 class map, middle-drag frame window), consonance ramp built as its own oklch() string, per-token canvas fallback"
```

---
### Task 7: the MATCH CURVE overlay and the consonance legend

Spec §5.4 (`MATCH CURVE` toggles the overlay canvas; "Legend anchors: unison, fifth and tritone
scores of the target against itself"). Two pieces sit on top of Task 6's heatmap. The **overlay** is
a second canvas stacked over the first (v3 345-346, `position:absolute;inset:1px;pointer-events:none`),
plotting `matchFrame` per visible frame against a y-axis **anchored to the target's own anchors**, not
to the data — so the same height means the same thing from clip to clip (v3 1272-1276). The
**legend** is DOM, not canvas: nine gradient stops with three tick marks at the anchors, plus the
readout line `match <score> · <scale>`.

Two things the drawing settles that the spec leaves open, both shipped as the drawing has them.
**CONSONANCE COLOUR is not a toggle** — v3 729 declares `chromaModes: { curve: true, consonance: true }`
with the comment `// consonance colour is always on`, and no control ever writes it. So the readout's
scale label is the constant string `consonance colour` (v3 2039) and this milestone ships no button
for it. And **`MATCH CURVE` is a fifth button in the same row as the four view buttons** (v3
2011-2016 lists all five in `chromaModeButtons`, even though the markup's `sc-for` placeholder count
at line 288 says four) — so Task 11's Playwright assertion counts the four *view* buttons, and this
task adds the fifth beside them.

**Files:**
- Create: `latent-forge/src/lib/chroma/matchCurve.ts`,
  `latent-forge/src/lib/chroma/__tests__/matchCurve.test.ts`
- Create: `latent-forge/src/ui/chroma/MatchCurveOverlay.svelte`,
  `latent-forge/src/ui/chroma/__tests__/MatchCurveOverlay.component.test.ts`
- Create: `latent-forge/src/ui/chroma/MatchLegend.svelte`,
  `latent-forge/src/ui/chroma/__tests__/MatchLegend.component.test.ts`

**Interfaces:**
- Consumes `matchFrame(frame: Float32Array, target: Float32Array): number`,
  `rotate(frame: Float32Array, classes: number): Float32Array` and
  `anchors(target: Float32Array): MatchAnchors` where
  `interface MatchAnchors { unison: number; fifth: number; tritone: number }` — the target scored
  against itself at 0, 7 and 6 semitones — from `latent-forge/src/lib/chroma/match.ts` (**this
  milestone's Task 3**).
- Consumes `fold12Column(fold12: Float32Array, T: number, frame: number): Float32Array` from
  `latent-forge/src/lib/chroma/bins.ts` (**this milestone's Task 1**): one frame of the server's
  `[12,T]` C-order fold, `class p, frame t = fold12[p*T + t]`.
- Consumes `interface ChromaResult { frames: number; fps: number; bands: Float32Array; fold12:
  Float32Array; T: number }` from `latent-forge/src/lib/chroma/chromaClient.svelte.ts` (**Task 2**).
- Consumes `interface FrameWindow { from: number; to: number }` and `frameToX(frame, win, widthPx)`
  from `latent-forge/src/lib/chroma/heatmapGeometry.ts` (**this milestone's Task 6**).
- Consumes `LEGEND_STOPS = 9` and `legendColor(t: number): string` — a literal `oklch()` string
  built per channel, never a `getComputedStyle` token read — from
  `latent-forge/src/lib/chroma/consonanceColor.ts` (**Task 6**).
- Consumes `chromaColour(el: Element, token: string): string` (a `getComputedStyle` read **with a
  per-token fallback**) and `fitChromaCanvas(canvas): CanvasRenderingContext2D | null` from
  `latent-forge/src/ui/chroma/chromaCanvas.ts` (**Task 6**).
- Consumes `HELP` from `latent-forge/src/lib/help/strings.ts` (**M1 T14**): `HELP.chromaMatchCurve`
  (v3 346) for the overlay canvas, `HELP.chromaMatchMarks` (v3 292) for the legend,
  `HELP.chromaMatchLegend` (v3 330) for the `match … · …` readout. All three verified in M1 T14's
  `KEYS` table.
- Produces, from `matchCurve.ts`: `CURVE_TOP_PX = 13`, `CURVE_BOTTOM_PAD_PX = 4`,
  `CURVE_SPAN_MIN = 0.06`, `CURVE_PAD_LO = 0.22`, `CURVE_PAD_HI = 0.12`,
  `CONSONANCE_SCALE_LABEL = "consonance colour"`,
  `ANCHOR_COLORS: Readonly<Record<"unison" | "fifth" | "tritone", string>>`;
  `interface CurveAxis { lo: number; hi: number }`; `curveAxis(a: MatchAnchors): CurveAxis`;
  `curveY(match: number, axis: CurveAxis, heightPx: number): number`;
  `windowScores(result: ChromaResult, target: Float32Array, win: FrameWindow,
  analysisDetuneCents: number): number[]` (the **analysis** detune — `0` when `result` came from the
  already-stretched `clip.previewAudio`, `clip.detune_cents` when it came from the raw
  `clip.audio`; see the Normative block's "how much detune to rotate by" row);
  `interface LegendTick { label: "unison" | "fifth" | "tritone"; value: number; pct: number }`;
  `legendTicks(a: MatchAnchors): LegendTick[]` (ascending by value, `pct` clamped to 1..99);
  `matchVerdict(score: number, a: MatchAnchors): string`.
- Produces the component `MatchCurveOverlay` (props `{ result: ChromaResult | null; target:
  Float32Array; win: FrameWindow; detuneCents?: number }` — again the **analysis** detune, Task 11's
  `analysisDetuneCents`, never `clip.detune_cents`), rendering
  `<canvas data-testid="chroma-match-curve" data-help={HELP.chromaMatchCurve}>`.
- Produces the component `MatchLegend` (props `{ target: Float32Array; clipScore: number | null }`),
  rendering `<div data-testid="chroma-legend" data-help={HELP.chromaMatchMarks}>` with nine
  `[data-legend-stop]` spans and three `[data-legend-tick]` marks, plus
  `<span data-testid="chroma-match-readout" data-help={HELP.chromaMatchLegend}>`.

- [ ] **Step 1: Write the failing tests**

`latent-forge/src/lib/chroma/__tests__/matchCurve.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import type { ChromaResult } from "../chromaClient.svelte";
import {
  CONSONANCE_SCALE_LABEL,
  CURVE_SPAN_MIN,
  CURVE_TOP_PX,
  curveAxis,
  curveY,
  legendTicks,
  matchVerdict,
  windowScores,
} from "../matchCurve";

const ANCH = { unison: 1, fifth: 0.8, tritone: 0.4 };

function result(T: number, cls: number): ChromaResult {
  const fold12 = new Float32Array(12 * T);
  for (let t = 0; t < T; t++) fold12[cls * T + t] = 1;
  return { frames: T, fps: 10.7666015625, bands: new Float32Array(3 * 128 * T), fold12, T };
}

describe("the curve's y-axis is anchored to the target, not to the data (v3 1272-1276)", () => {
  it("spans from below the tritone anchor to above the unison anchor", () => {
    const axis = curveAxis(ANCH);
    expect(axis.lo).toBeLessThan(ANCH.tritone);
    expect(axis.hi).toBeGreaterThan(ANCH.unison);
  });

  it("keeps a minimum span so a degenerate target does not divide by zero", () => {
    const axis = curveAxis({ unison: 0.5, fifth: 0.5, tritone: 0.5 });
    expect(axis.hi - axis.lo).toBeGreaterThanOrEqual(CURVE_SPAN_MIN * 0.3);
    expect(Number.isFinite(curveY(0.5, axis, 120))).toBe(true);
  });

  it("maps a high score near the top of the canvas and a low one near the bottom", () => {
    const axis = curveAxis(ANCH);
    const hi = curveY(axis.hi, axis, 120);
    const lo = curveY(axis.lo, axis, 120);
    expect(hi).toBeLessThan(lo);
    expect(hi).toBeGreaterThanOrEqual(CURVE_TOP_PX);
    expect(lo).toBeLessThanOrEqual(120);
  });
});

describe("windowScores plots exactly the frames the heatmap is showing", () => {
  it("returns one score per visible frame, not per clip frame", () => {
    expect(windowScores(result(96, 0), Float32Array.from([1,0,0,0,0,0,0,0,0,0,0,0]), { from: 10, to: 20 }, 0))
      .toHaveLength(10);
  });

  it("scores a frame identical to the target at the unison anchor", () => {
    const target = Float32Array.from([1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]);
    const scores = windowScores(result(4, 0), target, { from: 0, to: 4 }, 0);
    expect(scores.every((s) => Math.abs(s - 1) < 1e-9)).toBe(true);
  });

  it("applies the ANALYSIS detune, so 100 cents rotates the frame a whole class", () => {
    // The argument is the analysis detune, not the clip's: it is 0 whenever
    // the chroma came from the already-stretched previewAudio, and only
    // carries the clip's detune when the chroma came from the raw source. 100
    // here is the raw-source case.
    const target = Float32Array.from([0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]);
    const at0 = windowScores(result(2, 0), target, { from: 0, to: 2 }, 0)[0];
    const at100 = windowScores(result(2, 0), target, { from: 0, to: 2 }, 100)[0];
    expect(at100).toBeGreaterThan(at0);
    expect(at100).toBeCloseTo(1, 9);
  });

  it("clamps a window that runs past the clip rather than reading out of bounds", () => {
    expect(windowScores(result(4, 0), Float32Array.from([1,0,0,0,0,0,0,0,0,0,0,0]), { from: -5, to: 99 }, 0))
      .toHaveLength(4);
  });
});

describe("legendTicks (v3 2029-2037: the three marks, sorted, clamped into the strip)", () => {
  it("is the three anchors in ascending order", () => {
    expect(legendTicks(ANCH).map((t) => t.label)).toEqual(["tritone", "fifth", "unison"]);
    expect(legendTicks(ANCH).map((t) => t.value)).toEqual([0.4, 0.8, 1]);
  });

  it("clamps each mark's position into 1..99 per cent so it stays on the strip", () => {
    const ticks = legendTicks({ unison: 5, fifth: 0.5, tritone: -3 });
    expect(ticks[0].pct).toBe(1);
    expect(ticks[2].pct).toBe(99);
  });
});

describe("matchVerdict (v3 2040-2044) says what a score means against this target", () => {
  it("names the band the score falls into", () => {
    expect(matchVerdict(1, ANCH)).toBe("at unison");
    expect(matchVerdict(0.85, ANCH)).toBe("above a fifth");
    expect(matchVerdict(0.6, ANCH)).toBe("between fifth and tritone");
    expect(matchVerdict(0.1, ANCH)).toBe("below a tritone");
  });
});

describe("the consonance scale label", () => {
  it("is a constant, because CONSONANCE COLOUR is always on (v3 729)", () => {
    expect(CONSONANCE_SCALE_LABEL).toBe("consonance colour");
  });
});
```

`latent-forge/src/ui/chroma/__tests__/MatchCurveOverlay.component.test.ts`:

```ts
import { cleanup, render } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ChromaResult } from "../../../lib/chroma/chromaClient.svelte";
import { HELP } from "../../../lib/help/strings";
import MatchCurveOverlay from "../MatchCurveOverlay.svelte";

type Call = { kind: "call"; name: string; args: unknown[] } | { kind: "set"; name: string; value: unknown };

function fakeContext() {
  const calls: Call[] = [];
  const ctx: Record<string, unknown> = {};
  for (const m of ["fillRect", "strokeRect", "beginPath", "moveTo", "lineTo", "stroke", "fill", "fillText", "clearRect", "setTransform", "closePath", "setLineDash"]) {
    ctx[m] = (...args: unknown[]) => { calls.push({ kind: "call", name: m, args }); };
  }
  for (const p of ["fillStyle", "strokeStyle", "lineWidth", "globalAlpha", "font", "textBaseline"]) {
    let v: unknown;
    Object.defineProperty(ctx, p, {
      get: () => v,
      set: (nv: unknown) => { v = nv; calls.push({ kind: "set", name: p, value: nv }); },
    });
  }
  return { ctx: ctx as unknown as CanvasRenderingContext2D, calls };
}

function result(T: number): ChromaResult {
  const fold12 = new Float32Array(12 * T);
  for (let t = 0; t < T; t++) fold12[0 * T + t] = 1;
  return { frames: T, fps: 10.7666015625, bands: new Float32Array(3 * 128 * T), fold12, T };
}

const TARGET = Float32Array.from([1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0]);

beforeEach(() => {
  Object.defineProperty(HTMLCanvasElement.prototype, "clientWidth", { configurable: true, get: () => 400 });
  Object.defineProperty(HTMLCanvasElement.prototype, "clientHeight", { configurable: true, get: () => 129 });
});

afterEach(() => {
  delete (HTMLCanvasElement.prototype as unknown as Record<string, unknown>).clientWidth;
  delete (HTMLCanvasElement.prototype as unknown as Record<string, unknown>).clientHeight;
  vi.restoreAllMocks();
  cleanup();
});

describe("MatchCurveOverlay", () => {
  it("carries HELP.chromaMatchCurve (v3 line 346)", () => {
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(fakeContext().ctx);
    const { getByTestId } = render(MatchCurveOverlay, {
      props: { result: result(8), target: TARGET, win: { from: 0, to: 8 } },
    });
    expect(getByTestId("chroma-match-curve").getAttribute("data-help")).toBe(HELP.chromaMatchCurve);
  });

  it("plots one point per visible frame", () => {
    const fake = fakeContext();
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(fake.ctx);
    render(MatchCurveOverlay, {
      props: { result: result(96), target: TARGET, win: { from: 10, to: 20 } },
    });
    const moves = fake.calls.filter((c) => c.kind === "call" && c.name === "moveTo").length;
    const lines = fake.calls.filter((c) => c.kind === "call" && c.name === "lineTo").length;
    // three dashed anchor lines (1 moveTo + 1 lineTo each) + the curve itself,
    // which is 1 moveTo + 9 lineTo for a 10-frame window.
    expect(moves).toBe(3 + 1);
    expect(lines).toBe(3 + 9);
  });

  it("draws the three anchor reference lines even before any frame is scored", () => {
    const fake = fakeContext();
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(fake.ctx);
    render(MatchCurveOverlay, {
      props: { result: null, target: TARGET, win: { from: 0, to: 8 } },
    });
    expect(fake.calls.filter((c) => c.kind === "call" && c.name === "setLineDash").length).toBeGreaterThan(0);
    expect(fake.calls.filter((c) => c.kind === "call" && c.name === "moveTo").length).toBe(3);
  });

  it("clears rather than fills its background, so the heatmap shows through", () => {
    const fake = fakeContext();
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(fake.ctx);
    render(MatchCurveOverlay, {
      props: { result: result(8), target: TARGET, win: { from: 0, to: 8 } },
    });
    expect(fake.calls.some((c) => c.kind === "call" && c.name === "fillRect")).toBe(false);
  });
});
```

`latent-forge/src/ui/chroma/__tests__/MatchLegend.component.test.ts`:

```ts
import { cleanup, render } from "@testing-library/svelte";
import { afterEach, describe, expect, it } from "vitest";
import { HELP } from "../../../lib/help/strings";
import { legendColor } from "../../../lib/chroma/consonanceColor";
import MatchLegend from "../MatchLegend.svelte";

const TARGET = Float32Array.from([1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0]);

afterEach(cleanup);

describe("MatchLegend's DOM contract", () => {
  it("carries HELP.chromaMatchMarks on the legend (v3 292)", () => {
    const { getByTestId } = render(MatchLegend, { props: { target: TARGET, clipScore: 0.62 } });
    expect(getByTestId("chroma-legend").getAttribute("data-help")).toBe(HELP.chromaMatchMarks);
  });

  it("carries HELP.chromaMatchLegend on the readout line (v3 330)", () => {
    const { getByTestId } = render(MatchLegend, { props: { target: TARGET, clipScore: 0.62 } });
    expect(getByTestId("chroma-match-readout").getAttribute("data-help")).toBe(HELP.chromaMatchLegend);
  });
});

describe("MatchLegend draws the gradient and its three anchor marks (spec §5.4)", () => {
  it("is nine stops, each coloured by the ramp rather than a token", () => {
    const { container } = render(MatchLegend, { props: { target: TARGET, clipScore: 0.62 } });
    const stops = container.querySelectorAll("[data-legend-stop]");
    expect(stops).toHaveLength(9);
    // Read the RAW attribute, not `.style.background`. jsdom parses the style
    // attribute through cssstyle, whose colour parser may not know `oklch()` --
    // an unrecognised value makes the whole `background` shorthand a no-op and
    // `.style.background` returns "". A version that does understand CSS Color 4
    // would SERIALISE it (`oklch(58% 0.17 60)`), so an exact-string compare
    // fails there too. The attribute is untouched by the CSSOM either way.
    expect(stops[0].getAttribute("style")).toContain("oklch");
    expect(stops[8].getAttribute("style")).toContain(legendColor(1));
  });

  it("marks unison, fifth and tritone, each with its own value", () => {
    const { container, getByText } = render(MatchLegend, { props: { target: TARGET, clipScore: 0.62 } });
    expect(container.querySelectorAll("[data-legend-tick]")).toHaveLength(3);
    expect(getByText(/unison/)).toBeTruthy();
    expect(getByText(/fifth/)).toBeTruthy();
    expect(getByText(/tritone/)).toBeTruthy();
  });
});

describe("MatchLegend's readout line (v3 330: `match <score> · <scale>`)", () => {
  it("reads the clip's score and where it sits against the anchors", () => {
    const { getByTestId } = render(MatchLegend, { props: { target: TARGET, clipScore: 1 } });
    expect(getByTestId("chroma-match-readout").textContent).toBe(
      "match 1.00 · at unison · consonance colour",
    );
  });

  it("says nothing it does not know when no clip has been scored yet", () => {
    const { getByTestId } = render(MatchLegend, { props: { target: TARGET, clipScore: null } });
    expect(getByTestId("chroma-match-readout").textContent).toBe("match — · consonance colour");
  });
});
```

- [ ] **Step 2: Run the tests — they must fail**

```bash
cd latent-forge && npx vitest run src/lib/chroma/__tests__/matchCurve.test.ts src/ui/chroma/__tests__/MatchCurveOverlay.component.test.ts src/ui/chroma/__tests__/MatchLegend.component.test.ts
```

Expected: three failed suites — `Failed to resolve import "../matchCurve"`,
`Failed to resolve import "../MatchCurveOverlay.svelte"` and
`Failed to resolve import "../MatchLegend.svelte"`.

- [ ] **Step 3: Write the curve maths and the two components**

`latent-forge/src/lib/chroma/matchCurve.ts`:

```ts
// The MATCH CURVE overlay's arithmetic and the consonance legend's marks
// (spec §5.4; v3 _drawCurve 1262-1302 and legendTicks 2029-2037).
//
// The y-axis is anchored to the TARGET's own anchors -- what the target scores
// against itself at a unison, a fifth and a tritone -- and never to the data.
// That is the whole point: the same height means the same thing from clip to
// clip, so a dip in the curve is a dissonant passage rather than "the quietest
// part of this particular clip".
//
// The three anchor colours are literals, not tokens: they are the drawing's
// own (v3 _anchors 910-917), they must survive on a canvas, and there is no
// token for "a fifth" to read.

import { fold12Column } from "./bins";
import type { ChromaResult } from "./chromaClient.svelte";
import type { FrameWindow } from "./heatmapGeometry";
import { type MatchAnchors, matchFrame, rotate } from "./match";

/** Top gutter, so the curve never collides with the reference row. */
export const CURVE_TOP_PX = 13;
export const CURVE_BOTTOM_PAD_PX = 4;
/** Floor on the anchor span, so a degenerate target cannot divide by zero. */
export const CURVE_SPAN_MIN = 0.06;
export const CURVE_PAD_LO = 0.22;
export const CURVE_PAD_HI = 0.12;

/** v3 2039. CONSONANCE COLOUR has no toggle: v3 729 says it is always on. */
export const CONSONANCE_SCALE_LABEL = "consonance colour";

export const ANCHOR_COLORS: Readonly<Record<"unison" | "fifth" | "tritone", string>> = {
  unison: "oklch(58% 0.13 155)",
  fifth: "oklch(60% 0.12 90)",
  tritone: "oklch(58% 0.17 25)",
};

export interface CurveAxis {
  lo: number;
  hi: number;
}

export function curveAxis(a: MatchAnchors): CurveAxis {
  const span = Math.max(CURVE_SPAN_MIN, a.unison - a.tritone);
  return { lo: a.tritone - span * CURVE_PAD_LO, hi: a.unison + span * CURVE_PAD_HI };
}

export function curveY(match: number, axis: CurveAxis, heightPx: number): number {
  const span = Math.max(1e-9, axis.hi - axis.lo);
  const usable = Math.max(1, heightPx - CURVE_TOP_PX - CURVE_BOTTOM_PAD_PX);
  const y = heightPx - CURVE_BOTTOM_PAD_PX - ((match - axis.lo) / span) * usable;
  return y < CURVE_TOP_PX ? CURVE_TOP_PX : y > heightPx ? heightPx : y;
}

/**
 * One score per VISIBLE frame, at the ANALYSIS detune. The window is clamped
 * to the clip, so a stale window after a shorter clip lands cannot read past
 * the end of the array.
 *
 * `analysisDetuneCents` is NOT `clip.detune_cents`. M5 T10's runStretch
 * already pitch-shifts the preview by `clip.detune_cents / 100`, and this
 * milestone analyses that preview, so `result.fold12` is ALREADY detuned:
 * rotating it again by the clip's detune would apply the detune twice. Task 11
 * derives the one right number (`analysisDetuneCents`: 0 for a previewAudio,
 * `clip.detune_cents` for the raw clip.audio) and passes it here. The
 * parameter stays because the raw-audio case is real -- runStretch returns
 * early when `clip.native_bpm == null`, leaving previewAudio null.
 */
export function windowScores(
  result: ChromaResult,
  target: Float32Array,
  win: FrameWindow,
  analysisDetuneCents: number,
): number[] {
  const from = Math.max(0, Math.floor(win.from));
  const to = Math.min(result.T, Math.ceil(win.to));
  const semis = analysisDetuneCents / 100;
  const out: number[] = [];
  for (let f = from; f < to; f++) {
    out.push(matchFrame(rotate(fold12Column(result.fold12, result.T, f), semis), target));
  }
  return out;
}

export interface LegendTick {
  label: "unison" | "fifth" | "tritone";
  value: number;
  pct: number;
}

/** Ascending by value, as the drawing sorts them, each clamped onto the strip. */
export function legendTicks(a: MatchAnchors): LegendTick[] {
  const raw: LegendTick[] = [
    { label: "unison", value: a.unison, pct: 0 },
    { label: "fifth", value: a.fifth, pct: 0 },
    { label: "tritone", value: a.tritone, pct: 0 },
  ];
  return raw
    .sort((x, y) => x.value - y.value)
    .map((t) => ({ ...t, pct: Math.min(99, Math.max(1, t.value * 100)) }));
}

/** Plain words for a score, against this target's own three reference points. */
export function matchVerdict(score: number, a: MatchAnchors): string {
  if (score >= a.unison - 0.02) return "at unison";
  if (score >= a.fifth) return "above a fifth";
  if (score >= a.tritone) return "between fifth and tritone";
  return "below a tritone";
}
```

`latent-forge/src/ui/chroma/MatchCurveOverlay.svelte`:

```svelte
<script lang="ts">
  // The MATCH CURVE overlay (spec §5.4, v3 345-346 and _drawCurve 1262-1302):
  // a second canvas stacked over the heatmap, transparent where it has nothing
  // to say, with pointer events off so the heatmap below still hovers.
  //
  // It clears rather than fills -- a filled background would hide exactly the
  // heatmap it is supposed to annotate.
  import type { ChromaResult } from "../../lib/chroma/chromaClient.svelte";
  import { type FrameWindow, frameToX } from "../../lib/chroma/heatmapGeometry";
  import { ANCHOR_COLORS, curveAxis, curveY, windowScores } from "../../lib/chroma/matchCurve";
  import { anchors } from "../../lib/chroma/match";
  import { HELP } from "../../lib/help/strings";
  import { chromaColour, fitChromaCanvas } from "./chromaCanvas";

  interface Props {
    result: ChromaResult | null;
    target: Float32Array;
    win: FrameWindow;
    /**
     * The ANALYSIS detune (Task 11's `analysisDetuneCents`), not the clip's:
     * 0 when `result` came from the already-stretched `clip.previewAudio`,
     * `clip.detune_cents` when it came from the raw `clip.audio`. Rotating an
     * already-stretched fold by the clip's detune applies it twice.
     */
    detuneCents?: number;
  }
  let { result, target, win, detuneCents = 0 }: Props = $props();

  let canvasEl = $state<HTMLCanvasElement>();

  function draw(): void {
    const canvas = canvasEl;
    if (!canvas) return;
    const ctx = fitChromaCanvas(canvas);
    if (!ctx) return;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;

    const anch = anchors(target);
    const axis = curveAxis(anch);

    // The three reference lines first, so the curve draws over them.
    ctx.lineWidth = 1;
    for (const key of ["unison", "fifth", "tritone"] as const) {
      const y = Math.round(curveY(anch[key], axis, h)) + 0.5;
      ctx.setLineDash([4, 4]);
      ctx.strokeStyle = ANCHOR_COLORS[key];
      ctx.globalAlpha = 0.75;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.globalAlpha = 1;
    }
    if (!result) return;

    const scores = windowScores(result, target, win, detuneCents);
    if (scores.length === 0) return;
    const from = Math.max(0, Math.floor(win.from));
    ctx.beginPath();
    scores.forEach((m, i) => {
      const x = frameToX(from + i, win, w);
      const y = curveY(m, axis, h);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.strokeStyle = chromaColour(canvas, "--purple-strong");
    ctx.lineWidth = 1.7;
    ctx.stroke();
  }

  $effect(() => {
    void result;
    void target;
    void win;
    void detuneCents;
    draw();
  });
</script>

<canvas
  bind:this={canvasEl}
  data-testid="chroma-match-curve"
  data-help={HELP.chromaMatchCurve}
></canvas>

<style>
  canvas {
    position: absolute;
    inset: 1px;
    display: block;
    width: calc(100% - 2px);
    height: calc(100% - 2px);
    pointer-events: none;
  }
</style>
```

`latent-forge/src/ui/chroma/MatchLegend.svelte`:

```svelte
<script lang="ts">
  // The consonance legend (spec §5.4, v3 292-308) and the `match <score> ·
  // <scale>` readout (v3 330).
  //
  // This is DOM, not canvas, for the same reason the hover readout is (Task
  // 10): a fillText label can never be found by findByText, which was a
  // blocking M4 finding. The nine stops are inline background colours from
  // legendColor(), which builds its own oklch() string -- a legend IS a ramp.
  //
  // The three marks are computed from the TARGET alone, which is why the
  // legend can draw them before any clip is selected.
  import { LEGEND_STOPS, legendColor } from "../../lib/chroma/consonanceColor";
  import { anchors } from "../../lib/chroma/match";
  import { CONSONANCE_SCALE_LABEL, legendTicks, matchVerdict } from "../../lib/chroma/matchCurve";
  import { ANCHOR_COLORS } from "../../lib/chroma/matchCurve";
  import { HELP } from "../../lib/help/strings";

  interface Props {
    target: Float32Array;
    clipScore: number | null;
  }
  let { target, clipScore }: Props = $props();

  const anch = $derived(anchors(target));
  const ticks = $derived(legendTicks(anch));
  const stops = $derived(Array.from({ length: LEGEND_STOPS }, (_, i) => legendColor(i / (LEGEND_STOPS - 1))));
  const readout = $derived(
    clipScore === null
      ? `match — · ${CONSONANCE_SCALE_LABEL}`
      : `match ${clipScore.toFixed(2)} · ${matchVerdict(clipScore, anch)} · ${CONSONANCE_SCALE_LABEL}`,
  );
</script>

<div class="legend" data-testid="chroma-legend" data-help={HELP.chromaMatchMarks}>
  <div class="strip">
    <div class="stops">
      {#each stops as colour, i (i)}
        <span data-legend-stop style="background:{colour}"></span>
      {/each}
    </div>
    {#each ticks as tick (tick.label)}
      <span data-legend-tick style="left:{tick.pct}%"></span>
    {/each}
  </div>
  <div class="keys">
    {#each ticks as tick (tick.label)}
      <span style="color:{ANCHOR_COLORS[tick.label]}">{tick.label} {tick.value.toFixed(2)}</span>
    {/each}
  </div>
</div>
<span class="readout" data-testid="chroma-match-readout" data-help={HELP.chromaMatchLegend}>{readout}</span>

<style>
  .legend {
    display: flex;
    align-items: flex-end;
    gap: 5px;
  }
  .strip {
    position: relative;
  }
  .stops {
    display: flex;
  }
  .stops span {
    display: inline-block;
    width: 15px;
    height: 10px;
  }
  [data-legend-tick] {
    position: absolute;
    top: -2px;
    width: 1px;
    height: 14px;
    background: var(--text);
  }
  .keys {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 9px;
    white-space: nowrap;
  }
  .readout {
    font-size: 10px;
    color: var(--turq-strong);
  }
</style>
```

- [ ] **Step 4: Run them, expect pass**

```bash
cd latent-forge && npx vitest run src/lib/chroma/__tests__/matchCurve.test.ts src/ui/chroma/__tests__/MatchCurveOverlay.component.test.ts src/ui/chroma/__tests__/MatchLegend.component.test.ts && npm run check
```

Expected: `Test Files  3 passed (3)` / `Tests  21 passed (21)` — 11 in `matchCurve.test.ts`,
4 in `MatchCurveOverlay.component.test.ts` and 6 in `MatchLegend.component.test.ts` — and
`svelte-check found 0 errors and 0 warnings`.

- [ ] **Step 5: Commit**

```bash
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M6 T7: MATCH CURVE overlay anchored to the target's own unison/fifth/tritone, nine-stop consonance legend with three anchor marks, match readout (CONSONANCE COLOUR is always on, v3 729)"
```

---
### Task 8: `src/ui/chroma/DetuneScanStrip.svelte` — the ±100 ¢ scan, BEST, and the criterion toggle

Spec §5.4: "The strip plots the curve with a red mark at the current detune; click or drag sets
detune; BEST jumps to the argmax." Writer A's Task 5 already computes the curve — 51 points from
−100 to +100 ¢ in steps of 4, sampling every 3rd frame, reporting `mean` and `sd` — and already
knows which number each criterion follows (`mean` for HIGHEST, `mean − sd` for STEADIEST). This task
is the 500×30 canvas that draws it (v3 332), the gesture that writes detune back, and the two
buttons beneath it (v3 335-336).

**Writing detune goes through `arrangement.setDetune(id, cents)` and nothing else.** Mutating
`clip.detune_cents` directly would work by accident — the clip in `arrangement.clips` is a `$state`
deep proxy — but it would skip the store's own ±100 clamp and rounding, and it is exactly the class
of shortcut the `$state` proxy rule exists to stop.

**The strip's ±100 ¢ axis is RELATIVE to the clip's current detune, and BEST is ADDITIVE.** The
chroma this strip scans is normally the chroma of the clip's *stretched preview*, which M5 T10's
`runStretch` has already pitch-shifted by `clip.detune_cents / 100` (M5:5358) — so step *c* of the
scan means "the clip's current detune, **plus** *c*", not "*c*". Three consequences, all pinned
below: the red mark sits at the strip's **centre**, not at `xForCents(clip.detune_cents)`; `onBest`
and `setFromPointer` write `clip.detune_cents + …`, clamped, because assigning `bestDetune(…)`'s
bare value made a second press of BEST *walk* the detune instead of converging on it; and the label
says what the axis is relative to, so a reader of "+40 ¢" knows what it is 40 cents from. The
`analysisDetuneCents` prop keeps this true for the one clip that has no stretched preview — see the
Normative block's "how much detune to rotate by" row and Open question 6.

**This component does NOT call `/forge/stretch`.** Spec §5.4 says a detune change re-stretches the
clip's preview, debounced 400 ms, and M5 T10 already ships that as
`scheduleStretch(clipId, onError?)` — but the lane header's own DETUNE ¢ field (M5 T4) writes detune
too, through the same store method, and a debounce wired into *this* component would not cover it.
So Task 11's tab owns one `$effect` on the selected clip's `detune_cents` that arms the stretch for
either writer. Stated here so an implementer building this task alone does not add a second one.

**Files:**
- Create: `latent-forge/src/lib/chroma/scanStrip.ts`,
  `latent-forge/src/lib/chroma/__tests__/scanStrip.test.ts`
- Create: `latent-forge/src/ui/chroma/DetuneScanStrip.svelte`,
  `latent-forge/src/ui/chroma/__tests__/DetuneScanStrip.component.test.ts`

**Interfaces:**
- Consumes `DETUNE_MIN = -100`, `DETUNE_MAX = 100`, `DETUNE_STEP = 4`, `FRAME_STRIDE = 3`,
  `type ScanCriterion = "highest" | "steadiest"`,
  `interface DetuneScan { cents: number[]; mean: number[]; sd: number[] }`,
  `scanDetune(fold12: Float32Array, T: number, target: Float32Array, analysisDetuneCents?: number):
  DetuneScan` (51 points; rotates by `(analysisDetuneCents + cents)/100` classes at each step,
  sampling every 3rd frame — so the axis is **relative to the clip's current detune**) and
  `bestDetune(scan: DetuneScan, criterion: ScanCriterion): number` (argmax of `mean`, or of
  `mean − sd`; ties keep the most negative step — and it is an **offset** from the clip's current
  detune, which is why `onBest` adds it) from
  `latent-forge/src/lib/chroma/detuneScan.ts` (**this milestone's Task 5**).
- Consumes `interface ChromaResult { frames: number; fps: number; bands: Float32Array; fold12:
  Float32Array; T: number }` from `latent-forge/src/lib/chroma/chromaClient.svelte.ts` (**Task 2**).
- Consumes `ForgeClip` from `latent-forge/src/lib/forge/types.ts` (**M1 T3**) — the field this task
  reads and writes is `detune_cents: number`.
- Consumes the singleton `arrangement` from `latent-forge/src/lib/stores/arrangement.svelte.ts`
  (**M5 T1**), one method only: `setDetune(id: string, cents: number): void`, which clamps to
  ±100 and rounds to a whole cent.
- Consumes `chromaColour(el: Element, token: string): string` (a `getComputedStyle` read with a
  per-token fallback, because `ctx.fillStyle = ""` is a silent no-op) and
  `fitChromaCanvas(canvas): CanvasRenderingContext2D | null` from
  `latent-forge/src/ui/chroma/chromaCanvas.ts` (**this milestone's Task 6**).
- Consumes `HELP` from `latent-forge/src/lib/help/strings.ts` (**M1 T14**):
  `HELP.chromaDetuneScan` (v3 332) for the canvas, `HELP.chromaBestCriterion` (v3 335) for the
  HIGHEST/STEADIEST toggle, `HELP.chromaBest` (v3 336) for BEST. All three verified in M1 T14's
  `KEYS` table.
- Produces, from `scanStrip.ts`: `SCAN_W = 500`, `SCAN_H = 30`, `SCAN_GRID_CENTS = [-50, 0, 50]`,
  `SCAN_RANGE_FLOOR = 0.01`; `criterionValues(scan: DetuneScan, criterion: ScanCriterion): number[]`;
  `criterionLabel(criterion: ScanCriterion): "HIGHEST" | "STEADIEST"`;
  `nextCriterion(criterion: ScanCriterion): ScanCriterion`;
  `centsAtX(x: number, widthPx: number): number`; `xForCents(cents: number, widthPx: number): number`;
  `interface ScanRange { lo: number; hi: number }`; `scanRange(values: readonly number[]): ScanRange`;
  `scanY(v: number, range: ScanRange, heightPx: number): number`;
  `nearestScanIndex(scan: DetuneScan, cents: number): number`;
  `scanLabel(scan: DetuneScan, relCents: number, criterion: ScanCriterion, currentCents: number):
  string` (`relCents` and the reported peak are **offsets** on the relative axis; `currentCents` is
  the clip's own detune, named in the label so "+40 ¢" says what it is 40 cents from).
- Produces the component `DetuneScanStrip` (props `{ clip: ForgeClip | null; result: ChromaResult |
  null; target: Float32Array; criterion: ScanCriterion; detuneCents?: number;
  oncriterion?: (c: ScanCriterion) => void }` — `detuneCents` is Task 11's `analysisDetuneCents`,
  the detune **not** already in the analysed audio, which is what keeps the axis relative for a clip
  with no stretched preview),
  rendering `<canvas data-testid="chroma-scan-strip" data-help={HELP.chromaDetuneScan} width="500"
  height="30">`, `<span data-testid="chroma-scan-label">`,
  `<button data-testid="chroma-best-criterion" data-help={HELP.chromaBestCriterion}>` and
  `<button data-testid="chroma-best" data-help={HELP.chromaBest}>`.

- [ ] **Step 1: Write the failing tests**

`latent-forge/src/lib/chroma/__tests__/scanStrip.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { DETUNE_MAX, DETUNE_MIN, DETUNE_STEP, type DetuneScan } from "../detuneScan";
import {
  SCAN_H,
  SCAN_W,
  centsAtX,
  criterionLabel,
  criterionValues,
  nearestScanIndex,
  nextCriterion,
  scanLabel,
  scanRange,
  scanY,
  xForCents,
} from "../scanStrip";

function scan(mean: number[], sd: number[]): DetuneScan {
  const cents: number[] = [];
  for (let c = DETUNE_MIN; c <= DETUNE_MAX; c += DETUNE_STEP) cents.push(c);
  return { cents, mean, sd };
}

/** 51 flat points with one peak at the given index. */
function peakAt(i: number, sdAt = 0): DetuneScan {
  const mean = new Array(51).fill(0.5);
  const sd = new Array(51).fill(0);
  mean[i] = 0.9;
  sd[i] = sdAt;
  return scan(mean, sd);
}

describe("the strip's fixed geometry (v3 332)", () => {
  it("is the drawing's 500 x 30 canvas", () => {
    expect(SCAN_W).toBe(500);
    expect(SCAN_H).toBe(30);
  });
});

describe("pixels <-> cents across the ±100 range", () => {
  it("puts -100 at the left edge, 0 at the middle and +100 at the right", () => {
    expect(centsAtX(0, 500)).toBe(-100);
    expect(centsAtX(250, 500)).toBe(0);
    expect(centsAtX(500, 500)).toBe(100);
  });

  it("clamps a pointer that leaves the strip rather than running past ±100", () => {
    expect(centsAtX(-900, 500)).toBe(-100);
    expect(centsAtX(9000, 500)).toBe(100);
  });

  it("round-trips every one of the 51 grid points", () => {
    for (let c = DETUNE_MIN; c <= DETUNE_MAX; c += DETUNE_STEP) {
      expect(centsAtX(xForCents(c, 500), 500)).toBe(c);
    }
  });
});

describe("the criterion chooses which number the strip plots (spec §5.4)", () => {
  it("HIGHEST follows mean and STEADIEST follows mean - sd", () => {
    const s = scan(new Array(51).fill(0.6), new Array(51).fill(0.25));
    expect(criterionValues(s, "highest")[0]).toBeCloseTo(0.6, 9);
    expect(criterionValues(s, "steadiest")[0]).toBeCloseTo(0.35, 9);
  });

  it("labels itself as the drawing does and toggles between exactly two states", () => {
    expect(criterionLabel("highest")).toBe("HIGHEST");
    expect(criterionLabel("steadiest")).toBe("STEADIEST");
    expect(nextCriterion("highest")).toBe("steadiest");
    expect(nextCriterion("steadiest")).toBe("highest");
  });
});

describe("the vertical range (v3 1233: expand a flat curve rather than divide by zero)", () => {
  it("uses the data's own range when it is wide enough", () => {
    expect(scanRange([0.2, 0.8, 0.5])).toEqual({ lo: 0.2, hi: 0.8 });
  });

  it("opens a dead-flat curve out by 0.01 either way", () => {
    const r = scanRange([0.5, 0.5, 0.5]);
    expect(r.hi - r.lo).toBeCloseTo(0.02, 9);
    expect(Number.isFinite(scanY(0.5, r, 30))).toBe(true);
  });

  it("maps the range's top near the top of the strip and its floor near the bottom", () => {
    const r = { lo: 0, hi: 1 };
    expect(scanY(1, r, 30)).toBeLessThan(scanY(0, r, 30));
    expect(scanY(1, r, 30)).toBeGreaterThanOrEqual(0);
    expect(scanY(0, r, 30)).toBeLessThanOrEqual(30);
  });
});

describe("reading the curve at the clip's own detune", () => {
  it("snaps to the nearest of the 51 sampled steps", () => {
    const s = peakAt(25);
    expect(s.cents[nearestScanIndex(s, 0)]).toBe(0);
    expect(s.cents[nearestScanIndex(s, 2)]).toBe(0);
    expect(s.cents[nearestScanIndex(s, 3)]).toBe(4);
    expect(s.cents[nearestScanIndex(s, -100)]).toBe(-100);
  });

  it("reads out now / mean ± sd / peak, signing the peak, and names what the axis is relative to", () => {
    const s = peakAt(28, 0.1); // index 28 -> cents = -100 + 28*4 = 12
    // The axis is RELATIVE: 0 is the clip's own detune, so the strip always
    // reads "now 0¢" and the final clause says what 0 actually is.
    expect(scanLabel(s, 0, "highest", 0)).toBe(
      "now 0¢ · mean 0.50 ± 0.00 · peak +12¢ · ±100¢ relative to 0¢",
    );
    expect(scanLabel(s, 0, "highest", -30)).toBe(
      "now 0¢ · mean 0.50 ± 0.00 · peak +12¢ · ±100¢ relative to -30¢",
    );
  });

  it("reports a negative peak without a plus sign, and follows the criterion", () => {
    const s = peakAt(10, 0.6); // cents = -60; mean - sd = 0.3, below the 0.5 floor
    expect(scanLabel(s, -60, "highest", 20)).toBe(
      "now -60¢ · mean 0.90 ± 0.60 · peak -60¢ · ±100¢ relative to 20¢",
    );
    expect(scanLabel(s, -60, "steadiest", 20)).toBe(
      "now -60¢ · mean 0.90 ± 0.60 · peak -100¢ · ±100¢ relative to 20¢",
    );
  });
});
```

`latent-forge/src/ui/chroma/__tests__/DetuneScanStrip.component.test.ts`:

```ts
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ChromaResult } from "../../../lib/chroma/chromaClient.svelte";
import type { ForgeClip } from "../../../lib/forge/types";
import { HELP } from "../../../lib/help/strings";
import { arrangement } from "../../../lib/stores/arrangement.svelte";
import DetuneScanStrip from "../DetuneScanStrip.svelte";

type Call = { kind: "call"; name: string; args: unknown[] } | { kind: "set"; name: string; value: unknown };

function fakeContext() {
  const calls: Call[] = [];
  const ctx: Record<string, unknown> = {};
  for (const m of ["fillRect", "beginPath", "moveTo", "lineTo", "stroke", "fill", "closePath", "clearRect", "setTransform", "setLineDash"]) {
    ctx[m] = (...args: unknown[]) => { calls.push({ kind: "call", name: m, args }); };
  }
  for (const p of ["fillStyle", "strokeStyle", "lineWidth", "globalAlpha"]) {
    let v: unknown;
    Object.defineProperty(ctx, p, {
      get: () => v,
      set: (nv: unknown) => { v = nv; calls.push({ kind: "set", name: p, value: nv }); },
    });
  }
  return { ctx: ctx as unknown as CanvasRenderingContext2D, calls };
}

/** A clip whose chroma is pure C; the target is pure C#, so the peak is at +100¢. */
function result(T: number): ChromaResult {
  const fold12 = new Float32Array(12 * T);
  for (let t = 0; t < T; t++) fold12[0 * T + t] = 1;
  return { frames: T, fps: 10.7666015625, bands: new Float32Array(3 * 128 * T), fold12, T };
}

const TARGET = Float32Array.from([0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]);

let clip: ForgeClip;

beforeEach(() => {
  for (const c of [...arrangement.clips]) arrangement.removeClip(c.id);
  clip = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: { kind: "crop", crop_id: "000412" } });
  Object.defineProperty(HTMLCanvasElement.prototype, "clientWidth", { configurable: true, get: () => 500 });
  Object.defineProperty(HTMLCanvasElement.prototype, "clientHeight", { configurable: true, get: () => 30 });
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(fakeContext().ctx);
});

afterEach(() => {
  delete (HTMLCanvasElement.prototype as unknown as Record<string, unknown>).clientWidth;
  delete (HTMLCanvasElement.prototype as unknown as Record<string, unknown>).clientHeight;
  vi.restoreAllMocks();
  for (const c of [...arrangement.clips]) arrangement.removeClip(c.id);
  cleanup();
});

function rect(canvas: HTMLElement) {
  vi.spyOn(canvas, "getBoundingClientRect").mockReturnValue({
    left: 0, top: 0, width: 500, height: 30, right: 500, bottom: 30, x: 0, y: 0, toJSON: () => ({}),
  });
}

describe("DetuneScanStrip's DOM contract", () => {
  it("carries all three of M1 T14's own ids (v3 332, 335, 336)", () => {
    const { getByTestId } = render(DetuneScanStrip, {
      props: { clip, result: result(12), target: TARGET, criterion: "highest" },
    });
    expect(getByTestId("chroma-scan-strip").getAttribute("data-help")).toBe(HELP.chromaDetuneScan);
    expect(getByTestId("chroma-best-criterion").getAttribute("data-help")).toBe(HELP.chromaBestCriterion);
    expect(getByTestId("chroma-best").getAttribute("data-help")).toBe(HELP.chromaBest);
  });

  it("is the drawing's 500 x 30 canvas", () => {
    const { getByTestId } = render(DetuneScanStrip, {
      props: { clip, result: result(12), target: TARGET, criterion: "highest" },
    });
    const canvas = getByTestId("chroma-scan-strip") as HTMLCanvasElement;
    expect(canvas.getAttribute("width")).toBe("500");
    expect(canvas.getAttribute("height")).toBe("30");
  });

  it("says so honestly when there is no clip to scan", () => {
    const { getByTestId } = render(DetuneScanStrip, {
      props: { clip: null, result: null, target: TARGET, criterion: "highest" },
    });
    expect(getByTestId("chroma-scan-label").textContent).toBe("detune scan · no clip");
  });
});

describe("clicking and dragging the strip sets detune (spec §5.4)", () => {
  it("writes through arrangement.setDetune, never by mutating the clip, and ADDS to what is there", async () => {
    // The axis is RELATIVE to the clip's current detune, because the fold
    // being scanned is the fold of already-stretched audio. x = 0 is therefore
    // "-100 ¢ FROM 20 ¢", i.e. -80 -- not -100.
    arrangement.setDetune(clip.id, 20);
    const spy = vi.spyOn(arrangement, "setDetune");
    const { getByTestId } = render(DetuneScanStrip, {
      props: { clip: arrangement.clips[0], result: result(12), target: TARGET, criterion: "highest" },
    });
    const canvas = getByTestId("chroma-scan-strip");
    rect(canvas);
    await fireEvent.pointerDown(canvas, { button: 0, clientX: 0, clientY: 15, pointerId: 1 });
    expect(spy).toHaveBeenCalledWith(clip.id, -80);
    expect(arrangement.clips[0].detune_cents).toBe(-80);
  });

  it("keeps following the pointer while the button is held, and stops after it is released", async () => {
    const { getByTestId } = render(DetuneScanStrip, {
      props: { clip, result: result(12), target: TARGET, criterion: "highest" },
    });
    const canvas = getByTestId("chroma-scan-strip");
    rect(canvas);
    // x = 250 is the strip's centre, i.e. 0 ¢ relative: the press alone leaves
    // the clip's 0 ¢ where it is. The move to the right edge is +100 from
    // there.
    await fireEvent.pointerDown(canvas, { button: 0, clientX: 250, clientY: 15, pointerId: 1 });
    expect(arrangement.clips[0].detune_cents).toBe(0);
    await fireEvent.pointerMove(canvas, { clientX: 500, clientY: 15, pointerId: 1 });
    expect(arrangement.clips[0].detune_cents).toBe(100);
    await fireEvent.pointerUp(canvas, { clientX: 500, clientY: 15, pointerId: 1 });
    await fireEvent.pointerMove(canvas, { clientX: 0, clientY: 15, pointerId: 1 });
    expect(arrangement.clips[0].detune_cents).toBe(100);
  });

  it("ignores a middle or right button, which are not the strip's gesture", async () => {
    const { getByTestId } = render(DetuneScanStrip, {
      props: { clip, result: result(12), target: TARGET, criterion: "highest" },
    });
    const canvas = getByTestId("chroma-scan-strip");
    rect(canvas);
    await fireEvent.pointerDown(canvas, { button: 1, clientX: 0, clientY: 15, pointerId: 1 });
    expect(arrangement.clips[0].detune_cents).toBe(0);
  });
});

describe("BEST and the criterion toggle (spec §5.4, v3 1919-1929)", () => {
  it("ADDS the argmax under the current criterion to the clip's own detune", async () => {
    arrangement.setDetune(clip.id, -20);
    const { getByTestId } = render(DetuneScanStrip, {
      props: { clip: arrangement.clips[0], result: result(12), target: TARGET, criterion: "highest" },
    });
    await fireEvent.click(getByTestId("chroma-best"));
    // A pure-C clip against a pure-C# target does NOT peak cleanly at +100.
    // `rotate` splits linearly, so at c cents the frame is {0: 1-c/100,
    // 1: c/100}; once 1-c/100 falls below the float32 threshold, class 0 drops
    // out entirely and the score is W[0] = 1.0 exactly. That happens at 96 and
    // at 100 -- a flat top -- and `bestDetune`'s strict `>` keeps the FIRST,
    // so BEST returns 96. (Against the float64 literal threshold it would be a
    // three-way tie from 92; the Math.fround fix in Task 3 is what moves the
    // first tied point to 96. The two are coupled -- do not change one alone.)
    //
    // And 96 is a step on a RELATIVE axis, so BEST adds it: -20 + 96 = 76.
    // The bare-assignment version returned 96 here and, pressed again, 96
    // again rather than converging -- which is the bug this pins.
    expect(arrangement.clips[0].detune_cents).toBe(76);
  });

  it("does nothing at all when there is no clip or no chroma yet", async () => {
    const { getByTestId } = render(DetuneScanStrip, {
      props: { clip, result: null, target: TARGET, criterion: "highest" },
    });
    await fireEvent.click(getByTestId("chroma-best"));
    expect(arrangement.clips[0].detune_cents).toBe(0);
  });

  it("reports the flipped criterion upward rather than owning it", async () => {
    let seen: string | null = null;
    const { getByTestId } = render(DetuneScanStrip, {
      props: {
        clip, result: result(12), target: TARGET, criterion: "highest",
        oncriterion: (c: string) => { seen = c; },
      },
    });
    expect(getByTestId("chroma-best-criterion").textContent).toBe("HIGHEST");
    await fireEvent.click(getByTestId("chroma-best-criterion"));
    expect(seen).toBe("steadiest");
  });
});

describe("the red mark at the clip's current detune (spec §5.4)", () => {
  it("strokes a line in the --red token at the CENTRE, because the axis is relative to it", () => {
    arrangement.setDetune(clip.id, 50);
    const fake = fakeContext();
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(fake.ctx);
    const { getByTestId } = render(DetuneScanStrip, {
      props: { clip: arrangement.clips[0], result: result(12), target: TARGET, criterion: "highest" },
    });
    expect(getByTestId("chroma-scan-strip")).toBeTruthy();
    // Find the mark by its colour and read the moveTo that follows it -- the
    // 0 ¢ GRID line is drawn at the same x, so a bare "some moveTo is at 250.5"
    // would pass even with no mark at all.
    const redAt = fake.calls.findIndex(
      (c) => c.kind === "set" && c.name === "strokeStyle" && c.value === "oklch(55% 0.20 25)",
    ); // chromaCanvas's --red fallback, copied from M1 T12's tokens.css
    expect(redAt).toBeGreaterThanOrEqual(0);
    const mark = fake.calls
      .slice(redAt)
      .find((c) => c.kind === "call" && c.name === "moveTo") as { args: number[] } | undefined;
    expect(mark).toBeTruthy();
    // 250.5, the strip's centre -- NOT xForCents(50) = 375.5. The clip's
    // detune is the axis ORIGIN, so the mark does not move when it changes.
    expect(mark!.args[0]).toBeCloseTo(250.5, 6);
  });
});
```

- [ ] **Step 2: Run the tests — they must fail**

```bash
cd latent-forge && npx vitest run src/lib/chroma/__tests__/scanStrip.test.ts src/ui/chroma/__tests__/DetuneScanStrip.component.test.ts
```

Expected: two failed suites — `Failed to resolve import "../scanStrip"` and
`Failed to resolve import "../DetuneScanStrip.svelte"`.

- [ ] **Step 3: Write the strip maths and the component**

`latent-forge/src/lib/chroma/scanStrip.ts`:

```ts
// The detune scan strip's own arithmetic (spec §5.4; v3 markup 332, logic
// _drawScan 1224-1260 and scanLabel 1912-1918). Task 5 computes the curve;
// this turns it into pixels, and pixels back into cents.
//
// Nothing here touches a store or a canvas, so the boundary cases that
// actually bite -- a dead-flat curve, a pointer dragged off the end of the
// strip, a detune that is not one of the 51 sampled steps -- are pinned under
// vitest rather than discovered on screen.

import { DETUNE_MAX, DETUNE_MIN, type DetuneScan, type ScanCriterion, bestDetune } from "./detuneScan";

/** The drawing's canvas, v3 332. */
export const SCAN_W = 500;
export const SCAN_H = 30;

/** Vertical guides, v3 1233. */
export const SCAN_GRID_CENTS: readonly number[] = [-50, 0, 50];

/** A curve flatter than this is opened out rather than divided by (v3 1231). */
export const SCAN_RANGE_FLOOR = 0.01;

export function criterionValues(scan: DetuneScan, criterion: ScanCriterion): number[] {
  return scan.mean.map((m, i) => (criterion === "steadiest" ? m - scan.sd[i] : m));
}

export function criterionLabel(criterion: ScanCriterion): "HIGHEST" | "STEADIEST" {
  return criterion === "steadiest" ? "STEADIEST" : "HIGHEST";
}

export function nextCriterion(criterion: ScanCriterion): ScanCriterion {
  return criterion === "steadiest" ? "highest" : "steadiest";
}

const SPAN = DETUNE_MAX - DETUNE_MIN;

/** Whole cents, clamped to ±100: a drag off the end of the strip pins there. */
export function centsAtX(x: number, widthPx: number): number {
  const frac = Math.min(1, Math.max(0, x / Math.max(1, widthPx)));
  return Math.round(frac * SPAN + DETUNE_MIN);
}

export function xForCents(cents: number, widthPx: number): number {
  const c = Math.min(DETUNE_MAX, Math.max(DETUNE_MIN, cents));
  return ((c - DETUNE_MIN) / SPAN) * widthPx;
}

export interface ScanRange {
  lo: number;
  hi: number;
}

export function scanRange(values: readonly number[]): ScanRange {
  if (values.length === 0) return { lo: 0, hi: 1 };
  let lo = Infinity;
  let hi = -Infinity;
  for (const v of values) {
    if (v < lo) lo = v;
    if (v > hi) hi = v;
  }
  if (hi - lo < SCAN_RANGE_FLOOR) return { lo: lo - SCAN_RANGE_FLOOR, hi: hi + SCAN_RANGE_FLOOR };
  return { lo, hi };
}

export function scanY(v: number, range: ScanRange, heightPx: number): number {
  const span = Math.max(1e-9, range.hi - range.lo);
  return heightPx - 2 - ((v - range.lo) / span) * (heightPx - 5);
}

/** The sampled step nearest a (possibly un-sampled) detune value. */
export function nearestScanIndex(scan: DetuneScan, cents: number): number {
  let best = 0;
  let d = Infinity;
  for (let i = 0; i < scan.cents.length; i++) {
    const dd = Math.abs(scan.cents[i] - cents);
    if (dd < d) {
      d = dd;
      best = i;
    }
  }
  return best;
}

/**
 * v3 1917: `now <n>¢ · mean <m> ± <sd> · peak <±n>¢`, plus the clause v3 did
 * not need.
 *
 * `relCents` and the peak are offsets on the strip's RELATIVE axis -- the scan
 * runs on audio the stretch has already detuned, so step c means "the clip's
 * current detune plus c". Without naming that origin, a reader of "peak +40¢"
 * cannot tell 40 from what. `currentCents` is the clip's own detune, and the
 * trailing clause states the axis and its origin together.
 */
export function scanLabel(
  scan: DetuneScan,
  relCents: number,
  criterion: ScanCriterion,
  currentCents: number,
): string {
  const i = nearestScanIndex(scan, relCents);
  const peak = bestDetune(scan, criterion);
  const sign = peak > 0 ? "+" : "";
  return `now ${relCents}¢ · mean ${scan.mean[i].toFixed(2)} ± ${scan.sd[i].toFixed(2)} · peak ${sign}${peak}¢ · ±${DETUNE_MAX}¢ relative to ${currentCents}¢`;
}
```

`latent-forge/src/ui/chroma/DetuneScanStrip.svelte`:

```svelte
<script lang="ts">
  // The detune scan strip (spec §5.4; v3 332-337). Task 5's scanDetune gives
  // 51 points across ±100 ¢; this draws them, marks the clip's current detune
  // in red, and writes a new detune back on click or drag.
  //
  // Detune is written ONLY through arrangement.setDetune, which clamps to ±100
  // and rounds. Writing clip.detune_cents directly would appear to work -- the
  // clip is a $state deep proxy -- while silently skipping both.
  //
  // This component does NOT debounce a /forge/stretch. M5 T10 already owns
  // that (scheduleStretch, 400 ms), and the lane header's DETUNE ¢ field
  // writes detune too, so Task 11's tab arms it once for BOTH writers.
  //
  // THE AXIS IS RELATIVE. The fold this strip scans is normally the fold of
  // the clip's STRETCHED preview, which runStretch has already pitch-shifted
  // by clip.detune_cents / 100 -- so scan step c means "the clip's current
  // detune, plus c". Hence: the red mark sits at the strip's CENTRE, both
  // writers ADD (clip.detune_cents + …), and the label names the origin. The
  // `detuneCents` prop is the ANALYSIS detune (Task 11's analysisDetuneCents),
  // which is 0 for a stretched preview and clip.detune_cents for a clip that
  // has none -- passing it to scanDetune is what keeps the axis relative in
  // both cases. See the plan's Normative block and Open question 6.
  import {
    DETUNE_MAX,
    DETUNE_MIN,
    type DetuneScan,
    type ScanCriterion,
    bestDetune,
    scanDetune,
  } from "../../lib/chroma/detuneScan";
  import type { ChromaResult } from "../../lib/chroma/chromaClient.svelte";
  import {
    SCAN_GRID_CENTS,
    SCAN_H,
    SCAN_W,
    centsAtX,
    criterionLabel,
    criterionValues,
    nextCriterion,
    scanLabel,
    scanRange,
    scanY,
    xForCents,
  } from "../../lib/chroma/scanStrip";
  import type { ForgeClip } from "../../lib/forge/types";
  import { HELP } from "../../lib/help/strings";
  import { arrangement } from "../../lib/stores/arrangement.svelte";
  import { chromaColour, fitChromaCanvas } from "./chromaCanvas";

  interface Props {
    clip: ForgeClip | null;
    result: ChromaResult | null;
    target: Float32Array;
    criterion: ScanCriterion;
    /** The ANALYSIS detune (Task 11's `analysisDetuneCents`), never the clip's. */
    detuneCents?: number;
    oncriterion?: (c: ScanCriterion) => void;
  }
  let { clip, result, target, criterion, detuneCents = 0, oncriterion }: Props = $props();

  let canvasEl = $state<HTMLCanvasElement>();
  let dragging = false;

  const scan = $derived<DetuneScan | null>(
    result ? scanDetune(result.fold12, result.T, target, detuneCents) : null,
  );
  // `0` because the axis is relative: the clip's current detune IS the centre.
  // Its absolute value goes in as the origin the label names.
  const label = $derived(
    !clip || !scan ? "detune scan · no clip" : scanLabel(scan, 0, criterion, clip.detune_cents),
  );

  /** Every write is an OFFSET from where the clip already is. */
  function applyOffset(offsetCents: number): void {
    if (!clip) return;
    const next = clip.detune_cents + offsetCents;
    // setDetune clamps and rounds too (M5 T1); clamping here says out loud
    // that an additive write can leave the range that an absolute one cannot.
    arrangement.setDetune(clip.id, Math.min(DETUNE_MAX, Math.max(DETUNE_MIN, next)));
  }

  function draw(): void {
    const canvas = canvasEl;
    if (!canvas) return;
    const ctx = fitChromaCanvas(canvas);
    if (!ctx) return;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;

    ctx.fillStyle = chromaColour(canvas, "--panel2");
    ctx.fillRect(0, 0, w, h);
    if (!clip || !scan) return;

    ctx.strokeStyle = chromaColour(canvas, "--border");
    ctx.lineWidth = 1;
    for (const c of SCAN_GRID_CENTS) {
      const x = Math.round(xForCents(c, w)) + 0.5;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
    }

    const values = criterionValues(scan, criterion);
    const range = scanRange(values);
    ctx.beginPath();
    values.forEach((v, i) => {
      const x = xForCents(scan.cents[i], w);
      const y = scanY(v, range, h);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.strokeStyle = chromaColour(canvas, "--turq-strong");
    ctx.lineWidth = 1.6;
    ctx.stroke();

    // The clip's current detune is the axis ORIGIN, so the mark is at 0
    // relative -- the centre of the strip -- whatever that detune is.
    const bx = Math.round(xForCents(0, w)) + 0.5;
    ctx.strokeStyle = chromaColour(canvas, "--red");
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(bx, 0);
    ctx.lineTo(bx, h);
    ctx.stroke();
  }

  function setFromPointer(e: PointerEvent): void {
    const canvas = canvasEl;
    if (!canvas || !clip) return;
    const rect = canvas.getBoundingClientRect();
    applyOffset(centsAtX(e.clientX - rect.left, rect.width));
  }

  function onPointerDown(e: PointerEvent): void {
    if (e.button !== 0 || !clip) return;
    e.preventDefault();
    dragging = true;
    canvasEl?.setPointerCapture?.(e.pointerId);
    setFromPointer(e);
  }

  function onPointerMove(e: PointerEvent): void {
    if (!dragging) return;
    setFromPointer(e);
  }

  function onPointerUp(e: PointerEvent): void {
    dragging = false;
    canvasEl?.releasePointerCapture?.(e.pointerId);
  }

  function onBest(): void {
    if (!clip || !scan) return;
    // ADDITIVE. bestDetune returns a step on the relative axis, so assigning
    // it bare made a second press walk the detune (d -> best -> best + best)
    // instead of converging on it.
    applyOffset(bestDetune(scan, criterion));
  }

  $effect(() => {
    void clip?.detune_cents;
    void scan;
    void criterion;
    void detuneCents;
    draw();
  });
</script>

<canvas
  bind:this={canvasEl}
  data-testid="chroma-scan-strip"
  data-help={HELP.chromaDetuneScan}
  width={SCAN_W}
  height={SCAN_H}
  onpointerdown={onPointerDown}
  onpointermove={onPointerMove}
  onpointerup={onPointerUp}
  onpointercancel={onPointerUp}
></canvas>
<div class="row">
  <span class="label" data-testid="chroma-scan-label">{label}</span>
  <button
    type="button"
    data-testid="chroma-best-criterion"
    data-help={HELP.chromaBestCriterion}
    onclick={() => oncriterion?.(nextCriterion(criterion))}>{criterionLabel(criterion)}</button
  >
  <button type="button" data-testid="chroma-best" data-help={HELP.chromaBest} onclick={onBest}>BEST</button>
</div>

<style>
  canvas {
    display: block;
    box-sizing: border-box;
    width: 100%;
    height: 30px;
    flex-shrink: 0;
    border: 1px solid var(--border);
    cursor: ew-resize;
    margin-top: 2px;
  }
  .row {
    display: flex;
    align-items: center;
    gap: 5px;
  }
  .label {
    flex: 1;
    font-size: 9px;
    color: var(--text-dim);
  }
  button {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text);
    font-size: 9px;
    padding: 2px 5px;
    cursor: pointer;
  }
</style>
```

- [ ] **Step 4: Run them, expect pass**

```bash
cd latent-forge && npx vitest run src/lib/chroma/__tests__/scanStrip.test.ts src/ui/chroma/__tests__/DetuneScanStrip.component.test.ts && npm run check
```

Expected: `Test Files  2 passed (2)` / `Tests  22 passed (22)` — 12 in `scanStrip.test.ts` and
10 in `DetuneScanStrip.component.test.ts` — and `svelte-check found 0 errors and 0 warnings`.

- [ ] **Step 5: Commit**

```bash
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M6 T8: DetuneScanStrip -- 500x30 scan curve with the red mark at the clip's detune, click/drag through arrangement.setDetune only, BEST under HIGHEST or STEADIEST"
```

---
### Task 9: the target row — `lane` mode, `SEMITONE SET` mode, and the chord field

Spec §5.4's **Target** paragraph. Everything the pane scores is scored against one 12-class profile,
and it has two sources: `lane` mode folds the TARGET lane's clips down to one profile; `SEMITONE SET`
mode takes twelve piano-key toggles that a chord symbol can fill in. Writer A's Task 4 already turns
either into a `Float32Array`; this task is the state that chooses between them, the fetching lane
mode needs, and the row of controls across the top of the pane (v3 310-326).

**Two things the sources disagree about, both settled here.**

*Where the TARGET lane lives.* The brief says "a lane carries the chroma TARGET flag (M5's
`ForgeLane`)". It does not: M1 T3's `ForgeLane` is `{index, name, muted, solo, gain, chain}` with no
target field, and M5 T1 puts it on the store instead — `arrangement.targetLane: 0 | 1 | 2 | 3 | null`
(M5 plan line 352), written by `arrangement.setTargetLane(lane)` (line 546) and read by M5 T4's lane
header as `arrangement.targetLane === lane.index` (line 2548). **The source wins**: this task reads
`arrangement.targetLane`. Recorded as an open question so the assembler can correct the brief's line.

*What lane mode costs.* §5.4 says the lane profile is "the TARGET lane's clips' 12-class fold, summed
over frames and max-normalised" — every clip in that lane, not just the selected one. Task 2's
`chromaClient` is a singleton with **one** current `result`, so requesting the target lane's clips
through it would clobber the heatmap's own analysis. This task therefore keeps a **second
`ChromaClient` instance** (Writer A exports the class as well as the singleton) purely for the target
lane, requests each of its clips in turn, and accumulates the folds. That is honest about the cost —
one round trip per target-lane clip, cached per `AudioRef` inside that client — and it never touches
the pane's own client.

**No `data-help` on the mode buttons or the piano keys.** M1 Task 14's table has ids for
`chromaChord` (v3 323) and nothing for the TARGET-mode buttons (v3 312-313) or the twelve key
toggles (v3 320) — verified against the `KEYS` list. Four invented ids were a blocking M4 defect and
M10 shipped nine controls bare for the same reason, so these ship bare too. Flagged at the end.

**Files:**
- Create: `latent-forge/src/lib/chroma/targetStore.svelte.ts`,
  `latent-forge/src/lib/chroma/__tests__/targetStore.test.ts`
- Create: `latent-forge/src/ui/chroma/TargetRow.svelte`,
  `latent-forge/src/ui/chroma/__tests__/TargetRow.component.test.ts`

**Interfaces:**
- Consumes `type ChromaTargetMode = "lane" | "set"`,
  `targetProfile(frames: readonly Float32Array[]): Float32Array` (the 12-class folds **summed over
  frames then max-normalised**; an empty list or all-zero frames give an all-zero profile, never
  NaN), `setProfile(keys: readonly boolean[]): Float32Array` (exactly twelve toggles as a flat 1/0
  profile) and `parseChord(text: string): boolean[] | null` (the nine qualities
  `"" m 7 maj7 m7 dim aug sus2 sus4` over all twelve roots, `#` and `b` spellings, `null` for
  anything unrecognised, never throws) from `latent-forge/src/lib/chroma/target.ts` (**this
  milestone's Task 4**).
- Consumes `NOTE_NAMES: readonly string[]` (the twelve, sharp spellings, C first) and
  `fold12Columns(fold12: Float32Array, T: number): Float32Array[]` (every frame of the server's
  `[12,T]` C-order fold) from `latent-forge/src/lib/chroma/bins.ts` (**this milestone's Task 1**).
- Consumes `class ChromaClient` (`$state` fields `result: ChromaResult | null`, `pending: boolean`,
  `error: string | null`; methods `request(audio: AudioRef): Promise<void>`, `flush(): Promise<void>`,
  `dispose(): void`; a per-`AudioRef` cache) and
  `interface ChromaResult { frames: number; fps: number; bands: Float32Array; fold12: Float32Array;
  T: number }` from `latent-forge/src/lib/chroma/chromaClient.svelte.ts` (**this milestone's Task 2**).
  The **class**, not the `chromaClient` singleton — the singleton belongs to the heatmap.
- Consumes `AudioRef` and `ForgeClip` from `latent-forge/src/lib/forge/types.ts` (**M1 T3**):
  `AudioRef = {kind:"upload"; sha256:string} | {kind:"render"; job_id:string; file:string} |
  {kind:"crop"; crop_id:string} | {kind:"file"; root:string; rel:string} | {kind:"path"; path:string}`;
  `ForgeClip.previewAudio: AudioRef | null` is the **stretched** preview (M5 T10), **in-memory only,
  never serialised**, so every read is `clip.previewAudio ?? clip.audio`.
- Consumes the singleton `arrangement` from `latent-forge/src/lib/stores/arrangement.svelte.ts`
  (**M5 T1**): `clips: ForgeClip[]` and `targetLane: 0 | 1 | 2 | 3 | null`.
- Consumes `HELP` from `latent-forge/src/lib/help/strings.ts` (**M1 T14**): `HELP.chromaChord`
  (v3 323) — the only id this row has.
- Produces, from `targetStore.svelte.ts`: `NO_TARGET_LANE_LABEL = "no TARGET lane"`;
  `EMPTY_KEYS_LABEL = "no classes selected"`; `laneTargetLabel(lane: 0|1|2|3|null): string`;
  `keysLabel(keys: readonly boolean[]): string`;
  `laneTargetRefs(clips: readonly ForgeClip[], lane: 0|1|2|3|null): AudioRef[]`;
  `class ChromaTargetStore` with `$state` fields `mode`, `keys`, `chordText`, `chordOk`,
  `laneProfile`, `laneClipCount`, `pending`, `error`, a `$derived` `profile: Float32Array`, and
  methods `setMode(m: ChromaTargetMode): void`, `toggleKey(p: number): void`,
  `setChordText(text: string): void`, `loadLane(refs: readonly AudioRef[]): Promise<void>`,
  `dispose(): void`; the singleton `export const chromaTarget = new ChromaTargetStore()`.
- Produces the component `TargetRow` (no props), rendering
  `[data-testid="chroma-target-mode-lane"]`, `[data-testid="chroma-target-mode-set"]` (**neither
  carries `data-help`**), `[data-chroma-key="0".."11"]` (twelve, no `data-help`) and
  `<input data-testid="chroma-chord" data-help={HELP.chromaChord} placeholder="chord symbol">`.

- [ ] **Step 1: Write the failing tests**

`latent-forge/src/lib/chroma/__tests__/targetStore.test.ts`:

```ts
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AudioRef, ForgeClip } from "../../forge/types";
import {
  ChromaTargetStore,
  EMPTY_KEYS_LABEL,
  NO_TARGET_LANE_LABEL,
  keysLabel,
  laneTargetLabel,
  laneTargetRefs,
} from "../targetStore.svelte";

function clip(over: Partial<ForgeClip>): ForgeClip {
  return {
    id: "c", lane: 0, start_sec: 0, offset_sec: 0, dur_sec: 4, loop: false,
    audio: { kind: "upload", sha256: "raw" }, previewAudio: null, native_bpm: null,
    detune_cents: 0, downbeats_sec: [], render: {} as never, a2a: null,
    latentState: "none", history: [],
    ...over,
  } as ForgeClip;
}

/** One frame of pure C, quantised the way /forge/chroma transports it. */
function chromaBody(cls: number, T: number) {
  const bands = new Uint8Array(3 * 128 * T);
  const fold = new Uint8Array(12 * T);
  for (let t = 0; t < T; t++) fold[cls * T + t] = 255;
  const b64 = (u: Uint8Array) => {
    let s = "";
    for (const b of u) s += String.fromCharCode(b);
    return btoa(s);
  };
  return {
    ok: true,
    frames: T,
    fps: 10.7666015625,
    bands: { shape: [3, 128, T], scale: [1, 1, 1], data_b64: b64(bands) },
    fold12: { shape: [12, T], scale: 1.0, data_b64: b64(fold) },
  };
}

let store: ChromaTargetStore;

beforeEach(() => {
  store = new ChromaTargetStore();
});

afterEach(() => {
  store.dispose();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("the labels the row shows when it has nothing to show", () => {
  it("names the TARGET lane, or says there is none", () => {
    expect(laneTargetLabel(2)).toBe("LANE 3");
    expect(laneTargetLabel(null)).toBe(NO_TARGET_LANE_LABEL);
  });

  it("lists the selected classes, or says none are", () => {
    const keys = new Array(12).fill(false);
    expect(keysLabel(keys)).toBe(EMPTY_KEYS_LABEL);
    keys[0] = true;
    keys[4] = true;
    keys[7] = true;
    expect(keysLabel(keys)).toBe("C E G");
  });
});

describe("laneTargetRefs reads the STRETCHED preview, falling back to the source", () => {
  it("takes previewAudio when a clip has one and audio when it does not", () => {
    const refs = laneTargetRefs(
      [
        clip({ id: "a", lane: 1, previewAudio: { kind: "path", path: "/stretched.wav" } }),
        clip({ id: "b", lane: 1 }),
        clip({ id: "c", lane: 0 }),
      ],
      1,
    );
    expect(refs).toEqual([
      { kind: "path", path: "/stretched.wav" },
      { kind: "upload", sha256: "raw" },
    ]);
  });

  it("is empty when no lane is the target at all", () => {
    expect(laneTargetRefs([clip({ lane: 0 })], null)).toEqual([]);
  });
});

describe("SEMITONE SET mode", () => {
  it("starts in lane mode with nothing selected", () => {
    expect(store.mode).toBe("lane");
    expect(store.keys.some((k) => k)).toBe(false);
  });

  it("toggles a key on and off again", () => {
    store.toggleKey(4);
    expect(store.keys[4]).toBe(true);
    store.toggleKey(4);
    expect(store.keys[4]).toBe(false);
  });

  it("fills the key row from a chord symbol and switches to SEMITONE SET", () => {
    store.setChordText("F#m");
    expect(store.mode).toBe("set");
    expect(store.chordOk).toBe(true);
    // F# A C#
    expect([...store.keys.keys()].filter((p) => store.keys[p])).toEqual([1, 6, 9]);
  });

  it("keeps half-typed text without touching the keys, and flags it", () => {
    store.toggleKey(0);
    store.setChordText("Cm");
    const before = [...store.keys];
    store.setChordText("Cmzz");
    expect(store.chordText).toBe("Cmzz");
    expect(store.chordOk).toBe(false);
    expect([...store.keys]).toEqual(before);
  });

  it("treats an empty field as neither right nor wrong", () => {
    store.setChordText("");
    expect(store.chordOk).toBe(true);
  });

  it("profiles the twelve toggles flat, 1 and 0", () => {
    store.setChordText("C");
    expect([...store.profile]).toEqual([1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0]);
  });
});

describe("lane mode", () => {
  it("is an all-zero profile, never NaN, before any lane has been loaded", () => {
    expect(store.mode).toBe("lane");
    expect([...store.profile]).toEqual(new Array(12).fill(0));
    expect(store.laneClipCount).toBe(0);
  });

  it("sums every target-lane clip's fold and max-normalises the result", async () => {
    vi.stubGlobal("fetch", vi.fn(async (_url: string, init?: RequestInit) => {
      const body = JSON.parse(String(init?.body ?? "{}")) as { audio: AudioRef };
      const cls = body.audio.kind === "crop" && body.audio.crop_id === "second" ? 7 : 0;
      return new Response(JSON.stringify(chromaBody(cls, 3)), {
        status: 200, headers: { "content-type": "application/json" },
      });
    }));
    await store.loadLane([{ kind: "crop", crop_id: "first" }, { kind: "crop", crop_id: "second" }]);
    expect(store.laneClipCount).toBe(2);
    expect(store.profile[0]).toBeCloseTo(1, 6);
    expect(store.profile[7]).toBeCloseTo(1, 6);
    expect(store.profile[3]).toBe(0);
    expect(store.error).toBe(null);
  });

  it("clears the profile and says so when the TARGET lane is empty", async () => {
    await store.loadLane([]);
    expect(store.laneClipCount).toBe(0);
    expect([...store.profile]).toEqual(new Array(12).fill(0));
  });

  it("surfaces a server error as one line rather than a half-built profile (spec §9.7)", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(
      JSON.stringify({ ok: false, error: "no such crop" }),
      { status: 404, headers: { "content-type": "application/json" } },
    )));
    await store.loadLane([{ kind: "crop", crop_id: "gone" }]);
    expect(store.error).not.toBe(null);
    expect([...store.profile]).toEqual(new Array(12).fill(0));
    expect(store.pending).toBe(false);
  });
});
```

`latent-forge/src/ui/chroma/__tests__/TargetRow.component.test.ts`:

```ts
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { chromaTarget } from "../../../lib/chroma/targetStore.svelte";
import { HELP } from "../../../lib/help/strings";
import { arrangement } from "../../../lib/stores/arrangement.svelte";
import TargetRow from "../TargetRow.svelte";

beforeEach(() => {
  chromaTarget.dispose();
  arrangement.setTargetLane(null);
});

afterEach(() => {
  chromaTarget.dispose();
  arrangement.setTargetLane(null);
  cleanup();
});

describe("TargetRow's DOM contract", () => {
  it("gives the chord field M1 T14's own id and the drawing's placeholder (v3 323)", () => {
    chromaTarget.setMode("set");
    const { getByTestId } = render(TargetRow);
    const field = getByTestId("chroma-chord") as HTMLInputElement;
    expect(field.getAttribute("data-help")).toBe(HELP.chromaChord);
    expect(field.placeholder).toBe("chord symbol");
  });

  it("ships the two mode buttons and the twelve keys WITHOUT data-help, because M1 has no id", () => {
    chromaTarget.setMode("set");
    const { container, getByTestId } = render(TargetRow);
    expect(getByTestId("chroma-target-mode-lane").hasAttribute("data-help")).toBe(false);
    expect(getByTestId("chroma-target-mode-set").hasAttribute("data-help")).toBe(false);
    const keys = container.querySelectorAll("[data-chroma-key]");
    expect(keys).toHaveLength(12);
    for (const k of keys) expect(k.hasAttribute("data-help")).toBe(false);
  });
});

describe("lane mode reads the TARGET lane from the arrangement store", () => {
  it("names the lane the timeline made the target", () => {
    arrangement.setTargetLane(2);
    const { getByTestId } = render(TargetRow);
    expect(getByTestId("chroma-target-mode-lane").textContent).toBe("LANE 3");
  });

  it("says so honestly when no lane is the target, instead of drawing an empty profile", () => {
    const { getByText } = render(TargetRow);
    expect(getByText("no TARGET lane — press TARGET in a lane header")).toBeTruthy();
  });
});

describe("SEMITONE SET mode (spec §5.4)", () => {
  it("shows the twelve pitch classes, C first, with sharp spellings", () => {
    chromaTarget.setMode("set");
    const { container } = render(TargetRow);
    const labels = [...container.querySelectorAll("[data-chroma-key]")].map((k) => k.textContent);
    expect(labels).toEqual(["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]);
  });

  it("toggles a key through the store, not through local state", async () => {
    chromaTarget.setMode("set");
    const { container } = render(TargetRow);
    const e = container.querySelector('[data-chroma-key="4"]')!;
    await fireEvent.click(e);
    expect(chromaTarget.keys[4]).toBe(true);
  });

  it("fills the key row from a chord symbol (v3 323)", async () => {
    chromaTarget.setMode("set");
    const { getByTestId } = render(TargetRow);
    await fireEvent.input(getByTestId("chroma-chord"), { target: { value: "F#m" } });
    expect(chromaTarget.keys[6]).toBe(true);
    expect(chromaTarget.keys[9]).toBe(true);
    expect(chromaTarget.keys[1]).toBe(true);
  });

  it("lists the selected classes beside the field, or says there are none", async () => {
    chromaTarget.setMode("set");
    const { getByTestId } = render(TargetRow);
    expect(getByTestId("chroma-chord-hint").textContent).toBe("no classes selected");
    await fireEvent.input(getByTestId("chroma-chord"), { target: { value: "C" } });
    expect(getByTestId("chroma-chord-hint").textContent).toBe("C E G");
  });

  it("marks an unrecognised chord rather than silently ignoring it", async () => {
    chromaTarget.setMode("set");
    const { getByTestId } = render(TargetRow);
    await fireEvent.input(getByTestId("chroma-chord"), { target: { value: "Hmaj9" } });
    expect(getByTestId("chroma-chord").getAttribute("aria-invalid")).toBe("true");
  });
});
```

- [ ] **Step 2: Run the tests — they must fail**

```bash
cd latent-forge && npx vitest run src/lib/chroma/__tests__/targetStore.test.ts src/ui/chroma/__tests__/TargetRow.component.test.ts
```

Expected: two failed suites — `Failed to resolve import "../targetStore.svelte"` and
`Failed to resolve import "../TargetRow.svelte"`.

- [ ] **Step 3: Write the store and the row**

`latent-forge/src/lib/chroma/targetStore.svelte.ts`:

```ts
// The chroma target (spec §5.4). Two sources, one 12-class Float32Array out,
// so nothing downstream ever has to know which mode is on.
//
// lane mode: the TARGET LANE's clips' folds, summed over frames and
//   max-normalised (Task 4's targetProfile). The lane lives on the ARRANGEMENT
//   store as `arrangement.targetLane: 0|1|2|3|null` (M5 T1), NOT as a flag on
//   ForgeLane -- M1 T3's ForgeLane has no such field.
// set mode: twelve piano-key toggles, which a chord symbol can fill in.
//
// Why a second ChromaClient. Task 2's `chromaClient` singleton holds ONE
// current result, which is the selected clip's -- the heatmap, the curve, the
// scan strip and the score label all read it. Lane mode needs a DIFFERENT
// clip's analysis (often several), so asking through the singleton would
// clobber the pane's own view. This store therefore owns its own instance of
// the same class, with its own per-AudioRef cache, and the two never collide.
// The cost is honest: one round trip per target-lane clip, once.

import { fold12Columns, NOTE_NAMES } from "./bins";
import { ChromaClient } from "./chromaClient.svelte";
import { type ChromaTargetMode, parseChord, setProfile, targetProfile } from "./target";
import type { AudioRef, ForgeClip } from "../forge/types";

export const NO_TARGET_LANE_LABEL = "no TARGET lane";
export const EMPTY_KEYS_LABEL = "no classes selected";

/** The lane button's own label: the drawing's `LANE n`, 1-based (v3 2047). */
export function laneTargetLabel(lane: 0 | 1 | 2 | 3 | null): string {
  return lane === null ? NO_TARGET_LANE_LABEL : `LANE ${lane + 1}`;
}

export function keysLabel(keys: readonly boolean[]): string {
  const on = NOTE_NAMES.filter((_, p) => keys[p]);
  return on.length ? on.join(" ") : EMPTY_KEYS_LABEL;
}

/**
 * The audio to analyse for each clip in the TARGET lane. §5.4 computes chroma
 * on the STRETCHED preview "so it matches what the timeline plays", and
 * previewAudio is in-memory only (M1's Normative table), so an unstretched
 * clip falls back to its source ref rather than being skipped.
 */
export function laneTargetRefs(clips: readonly ForgeClip[], lane: 0 | 1 | 2 | 3 | null): AudioRef[] {
  if (lane === null) return [];
  return clips.filter((c) => c.lane === lane).map((c) => c.previewAudio ?? c.audio);
}

const ZERO = new Float32Array(12);

export class ChromaTargetStore {
  mode = $state<ChromaTargetMode>("lane");
  keys = $state<boolean[]>(new Array(12).fill(false));
  chordText = $state("");
  /** false only for text that is neither empty nor a chord this app knows. */
  chordOk = $state(true);
  laneProfile = $state<Float32Array | null>(null);
  laneClipCount = $state(0);
  pending = $state(false);
  error = $state<string | null>(null);

  #client = new ChromaClient();
  #run = 0;

  /** The one thing everything downstream reads. */
  profile = $derived<Float32Array>(
    this.mode === "set" ? setProfile(this.keys) : (this.laneProfile ?? ZERO),
  );

  setMode(m: ChromaTargetMode): void {
    this.mode = m;
  }

  toggleKey(p: number): void {
    if (p < 0 || p > 11) return;
    this.keys[p] = !this.keys[p];
  }

  /**
   * Typing into the chord field. parseChord never throws and returns null for
   * half-finished text, which is the NORMAL case while someone types -- so
   * null leaves the key row exactly as it was and only marks the field.
   */
  setChordText(text: string): void {
    this.chordText = text;
    const trimmed = text.trim();
    if (trimmed === "") {
      this.chordOk = true;
      return;
    }
    const keys = parseChord(trimmed);
    if (!keys) {
      this.chordOk = false;
      return;
    }
    this.chordOk = true;
    this.keys = keys;
    this.mode = "set";
  }

  /**
   * Analyse every clip in the TARGET lane and fold them into one profile.
   * Sequential on purpose: the results are summed anyway, and a burst of
   * parallel /forge/chroma calls on one CPU server buys nothing.
   */
  async loadLane(refs: readonly AudioRef[]): Promise<void> {
    const run = ++this.#run;
    this.error = null;
    this.laneClipCount = refs.length;
    if (refs.length === 0) {
      this.laneProfile = null;
      this.pending = false;
      return;
    }
    this.pending = true;
    const frames: Float32Array[] = [];
    for (const ref of refs) {
      await this.#client.request(ref);
      await this.#client.flush();
      if (run !== this.#run) return; // a newer load superseded this one
      if (this.#client.error) {
        this.error = this.#client.error;
        this.laneProfile = null;
        this.pending = false;
        return;
      }
      const res = this.#client.result;
      if (res) frames.push(...fold12Columns(res.fold12, res.T));
    }
    this.laneProfile = targetProfile(frames);
    this.pending = false;
  }

  dispose(): void {
    this.#run += 1;
    this.#client.dispose();
    this.mode = "lane";
    this.keys = new Array(12).fill(false);
    this.chordText = "";
    this.chordOk = true;
    this.laneProfile = null;
    this.laneClipCount = 0;
    this.pending = false;
    this.error = null;
  }
}

/** One target for the whole CHROMA tab. */
export const chromaTarget = new ChromaTargetStore();
```

`latent-forge/src/ui/chroma/TargetRow.svelte`:

```svelte
<script lang="ts">
  // TARGET + the two mode buttons (v3 310-313), and in SEMITONE SET mode the
  // twelve piano-key toggles plus the chord field (v3 317-325).
  //
  // No data-help on the mode buttons or the keys: M1 T14's table has an id for
  // the chord field (chromaChord, v3 323) and none for these. Inventing one
  // was a blocking M4 defect, four times over, so they ship bare.
  //
  // In lane mode with no TARGET lane chosen, this says so rather than showing
  // an all-zero profile as if it were data.
  import { NOTE_NAMES } from "../../lib/chroma/bins";
  import { chromaTarget, keysLabel, laneTargetLabel } from "../../lib/chroma/targetStore.svelte";
  import { HELP } from "../../lib/help/strings";
  import { arrangement } from "../../lib/stores/arrangement.svelte";

  const laneLabel = $derived(laneTargetLabel(arrangement.targetLane));
  const noLane = $derived(chromaTarget.mode === "lane" && arrangement.targetLane === null);
</script>

<div class="row" data-region="chroma-target-row">
  <span class="label">TARGET</span>
  <button
    type="button"
    class:on={chromaTarget.mode === "lane"}
    data-testid="chroma-target-mode-lane"
    onclick={() => chromaTarget.setMode("lane")}>{laneLabel}</button
  >
  <button
    type="button"
    class:on={chromaTarget.mode === "set"}
    data-testid="chroma-target-mode-set"
    onclick={() => chromaTarget.setMode("set")}>SEMITONE SET</button
  >
</div>

{#if noLane}
  <p class="note" data-testid="chroma-target-empty">no TARGET lane — press TARGET in a lane header</p>
{/if}

{#if chromaTarget.mode === "set"}
  <div class="keys-row">
    <div class="keys">
      {#each NOTE_NAMES as name, p (name)}
        <button
          type="button"
          data-chroma-key={p}
          class:on={chromaTarget.keys[p]}
          class:black={name.includes("#")}
          onclick={() => chromaTarget.toggleKey(p)}>{name}</button
        >
      {/each}
    </div>
    <input
      type="text"
      data-testid="chroma-chord"
      data-help={HELP.chromaChord}
      placeholder="chord symbol"
      aria-invalid={chromaTarget.chordOk ? undefined : "true"}
      value={chromaTarget.chordText}
      oninput={(e) => chromaTarget.setChordText((e.currentTarget as HTMLInputElement).value)}
    />
    <span class="hint" data-testid="chroma-chord-hint">{keysLabel(chromaTarget.keys)}</span>
  </div>
{/if}

<style>
  .row {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .label {
    font-size: 10px;
    color: var(--text-dim);
  }
  button {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text);
    font-size: 9px;
    padding: 3px 4px;
    cursor: pointer;
  }
  button.on {
    border-color: var(--turq-strong);
    color: var(--turq-strong);
  }
  .keys-row {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .keys {
    display: flex;
    gap: 2px;
  }
  .keys button {
    min-width: 20px;
  }
  .keys button.black {
    background: var(--panel2);
  }
  .keys button.on {
    background: var(--warm);
    border-color: var(--warm);
  }
  input {
    width: 110px;
    box-sizing: border-box;
    background: var(--panel2);
    border: 1px solid var(--border);
    color: var(--text);
    font-size: 10px;
    padding: 3px 5px;
  }
  input[aria-invalid="true"] {
    border-color: var(--red);
  }
  .hint,
  .note {
    margin: 0;
    font-size: 10px;
    color: var(--text-dim);
  }
</style>
```

- [ ] **Step 4: Run them, expect pass**

```bash
cd latent-forge && npx vitest run src/lib/chroma/__tests__/targetStore.test.ts src/ui/chroma/__tests__/TargetRow.component.test.ts && npm run check
```

Expected: `Test Files  2 passed (2)` / `Tests  23 passed (23)` — 14 in `targetStore.test.ts` and
9 in `TargetRow.component.test.ts` — and `svelte-check found 0 errors and 0 warnings`.

- [ ] **Step 5: Commit**

```bash
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M6 T9: target row -- lane mode over arrangement.targetLane with its own ChromaClient, SEMITONE SET keys and chord field, honest empty state when no lane is the target"
```

---
### Task 10: the hover readout, the lane cross-link, and the real clip score label

Spec §5.4's **Hover** paragraph — "reads note name + frame index into the readout (14 px note, 9 px
detail) and draws a red vertical line at that frame on the selected clip in its lane" — plus the one
thing M5 explicitly deferred to this milestone: the clip box's score label. M5 T6 ships
`SCORE_PLACEHOLDER = "χ —"` with the comment *"M6 fills the real chroma-match number in"*
(`lib/math/clipBox.ts`, M5 plan line 3475), and its self-review lists it as deferred with M6 as its
owner. This task fills it.

**The readout is DOM, never `fillText`.** A `fillText` label can never be found by `findByText` —
that was a blocking M4 finding — and the 14 px / 9 px sizes §5.4 pins are CSS, not canvas font
strings. So `HoverReadout.svelte` renders two elements as siblings of the canvas, exactly as the
drawing does it (v3 338-341: a 14 px 600-weight purple note line over a 9 px dim detail line).

**M5's lane canvas left no seam for the red line, so this adds the smallest one.** `LaneCanvas.svelte`
(M5 T5) draws grid, waveform ink, overlap darkening, clip marks and downbeats, and its draw `$effect`
reads only `arrangement` fields — there is no hover or marker state anywhere in it, and
`ClipBox.svelte` has no score input. The seam is one `$state` singleton, `chromaLink`, that the
CHROMA tab writes and the two timeline components read: **eleven lines added to `LaneCanvas.svelte`**
(one import, one `void` in the effect, a nine-line marker block at the end of `redraw()`) and **three
to `ClipBox.svelte`**. No restructuring of either component. Flagged at the end of this file.

**Why only some clips get a number.** §5.4 defines the label as "mean frame match at the clip's
detune", which needs that clip's chroma — one `/forge/chroma` round trip each. The CHROMA tab
analyses the *selected* clip (Task 11) and Task 9's target store analyses the *TARGET lane's* clips;
nothing analyses the rest, and firing a request per clip on mount would be a real cost for a number
nobody asked for. So `chromaLink.scores` is filled for the clips that have been analysed, and every
other clip keeps M5's `SCORE_PLACEHOLDER` — which is what a placeholder is for. Recorded as an open
question.

**Files:**
- Create: `latent-forge/src/lib/chroma/hoverReadout.ts`,
  `latent-forge/src/lib/chroma/__tests__/hoverReadout.test.ts`
- Create: `latent-forge/src/lib/chroma/chromaLink.svelte.ts`,
  `latent-forge/src/lib/chroma/__tests__/chromaLink.test.ts`
- Create: `latent-forge/src/ui/chroma/HoverReadout.svelte`,
  `latent-forge/src/ui/chroma/__tests__/HoverReadout.component.test.ts`
- Modify: `latent-forge/src/ui/timeline/LaneCanvas.svelte` (M5 T5 — the red frame marker)
- Modify: `latent-forge/src/ui/timeline/ClipBox.svelte` (M5 T6 — the score label)
- Create: `latent-forge/src/ui/timeline/__tests__/ClipBox.score.component.test.ts`

**Interfaces:**
- Consumes `NOTE_NAMES: readonly string[]` (the twelve, sharp spellings, C first) and
  `fold12Column(fold12: Float32Array, T: number, frame: number): Float32Array` from
  `latent-forge/src/lib/chroma/bins.ts` (**this milestone's Task 1**).
- Consumes `matchFrame(frame: Float32Array, target: Float32Array): number` and
  `rotate(frame: Float32Array, classes: number): Float32Array` from
  `latent-forge/src/lib/chroma/match.ts` (**this milestone's Task 3**).
- Consumes `interface ChromaResult { frames: number; fps: number; bands: Float32Array /* 3*128*T */;
  fold12: Float32Array /* 12*T */; T: number }` from
  `latent-forge/src/lib/chroma/chromaClient.svelte.ts` (**Task 2**).
- Consumes `type ChromaView`, `interface FrameWindow { from: number; to: number }`, `xToFrame(x, win,
  widthPx)`, `yToRow(y, view, heightPx): number | null` (null inside the reference row),
  `rowPitchClass(row, view)`, `rowCents(row, view): number | null` (null in GLOBAL) and
  `cellValue(result, view, frame, row)` from
  `latent-forge/src/lib/chroma/heatmapGeometry.ts` (**this milestone's Task 6**).
- Consumes `ForgeClip` from `latent-forge/src/lib/forge/types.ts` (**M1 T3**) — fields used here:
  `id: string`, `lane: 0|1|2|3`, `start_sec: number`, `dur_sec: number`.
- Consumes `SCORE_PLACEHOLDER = "χ —"` from `latent-forge/src/lib/math/clipBox.ts` (**M5 T6**) — the
  clip box's score-label slot.
- Consumes, for the two edits: `LaneCanvas.svelte`'s local `redraw()`, which already has `canvas`,
  `ctx`, `w`, `h`, `scrollSec`, `pxPerSec` and `laneClips` in scope, and its
  `secToPx(sec, scrollSec, pxPerSec)` import from `latent-forge/src/lib/math/viewport.ts` (**M5 T3**);
  and `ClipBox.svelte`'s `<span class="score">{SCORE_PLACEHOLDER}</span>` (M5 T6).
- Produces, from `hoverReadout.ts`: `HOVER_NOTE_PX = 14`, `HOVER_DETAIL_PX = 9`;
  `interface ChromaHover { frame: number; frames: number; frac: number; pitchClass: number; cents:
  number | null; value: number; top: number; topValue: number; match: number; sec: number }`;
  `readHover(args: { result: ChromaResult; target: Float32Array; view: ChromaView; win: FrameWindow;
  x: number; y: number; widthPx: number; heightPx: number; detuneCents: number }): ChromaHover | null`
  (`detuneCents` is Task 11's **`analysisDetuneCents`** — `0` when `result` came from the
  already-stretched `clip.previewAudio`, `clip.detune_cents` when it came from the raw `clip.audio`;
  see the Normative block's "how much detune to rotate by" row);
  `hoverNoteText(h: ChromaHover): string`; `hoverDetailText(h: ChromaHover): string`.
- Produces, from `chromaLink.svelte.ts`: `class ChromaLink` with `$state` fields
  `hover: { clipId: string; frac: number } | null` and `scores: Record<string, number>`, methods
  `setHover(clipId: string, frac: number): void`, `clearHover(): void`,
  `setScore(clipId: string, score: number): void`, `clearScore(clipId: string): void`,
  `reset(): void`; the singleton `export const chromaLink = new ChromaLink()`;
  `clipScoreLabel(score: number | undefined): string`;
  `markerSecFor(clip: { start_sec: number; dur_sec: number }, frac: number): number`.
- Produces the component `HoverReadout` (props `{ hover: ChromaHover | null }`), rendering
  `[data-testid="chroma-hover-note"]` (14 px) and `[data-testid="chroma-hover-detail"]` (9 px), and
  **nothing at all** when `hover` is null. No `data-help`: M1 T14 has no id for it (v3 338).

- [ ] **Step 1: Write the failing tests**

`latent-forge/src/lib/chroma/__tests__/hoverReadout.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import type { ChromaResult } from "../chromaClient.svelte";
import {
  HOVER_DETAIL_PX,
  HOVER_NOTE_PX,
  hoverDetailText,
  hoverNoteText,
  readHover,
} from "../hoverReadout";

/** C loud everywhere; G a little quieter; bass band has its energy at bin 2. */
function result(T: number): ChromaResult {
  const bands = new Float32Array(3 * 128 * T);
  const fold12 = new Float32Array(12 * T);
  for (let t = 0; t < T; t++) {
    bands[(0 * 128 + 2) * T + t] = 0.8;
    fold12[0 * T + t] = 1;
    fold12[7 * T + t] = 0.5;
  }
  return { frames: T, fps: 10.7666015625, bands, fold12, T };
}

const TARGET = Float32Array.from([1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0]);

const base = {
  result: result(96),
  target: TARGET,
  win: { from: 0, to: 96 },
  widthPx: 480,
  heightPx: 131,
  detuneCents: 0,
};

describe("the two readout sizes spec §5.4 pins", () => {
  it("is a 14 px note over a 9 px detail (v3 339-340)", () => {
    expect(HOVER_NOTE_PX).toBe(14);
    expect(HOVER_DETAIL_PX).toBe(9);
  });
});

describe("readHover turns a pointer into a frame and a pitch class", () => {
  it("reads the frame from x across the visible window", () => {
    const h = readHover({ ...base, view: "global", x: 240, y: 60 })!;
    expect(h.frame).toBe(48);
    expect(h.frames).toBe(96);
  });

  it("refuses the reference row, which is the target's and not the clip's", () => {
    expect(readHover({ ...base, view: "global", x: 240, y: 3 })).toBe(null);
  });

  it("reads the class from y, with C at the bottom", () => {
    const h = readHover({ ...base, view: "global", x: 0, y: 130 })!;
    expect(h.pitchClass).toBe(0);
    expect(h.cents).toBe(null);
    expect(h.value).toBeCloseTo(1, 6);
  });

  it("reads a band view's own bin, with its cents off the class centre", () => {
    const h = readHover({ ...base, view: "bass", x: 0, y: 131 - ((131 - 11) / 128) * 2.5 })!;
    expect(h.pitchClass).toBe(0);
    expect(h.cents).toBe(0);
    expect(h.value).toBeCloseTo(0.8, 6);
  });

  it("names the frame's strongest class and its own match, at the ANALYSIS detune", () => {
    // `detuneCents` is the detune NOT already in the analysed audio: 0 for the
    // usual stretched-preview case, the clip's own only when the chroma came
    // from the raw source. 100 below is that second case.
    const h = readHover({ ...base, view: "global", x: 0, y: 130 })!;
    expect(h.top).toBe(0);
    expect(h.topValue).toBeCloseTo(1, 6);
    expect(h.match).toBeGreaterThan(0);
    const rotated = readHover({ ...base, view: "global", x: 0, y: 130, detuneCents: 100 })!;
    expect(rotated.match).not.toBeCloseTo(h.match, 6);
  });

  it("gives the frame's time from the latent frame rate, not from the clip's length", () => {
    const h = readHover({ ...base, view: "global", x: 240, y: 60 })!;
    expect(h.sec).toBeCloseTo(48 / 10.7666015625, 6);
  });
});

describe("the two readout strings (v3 1968-1973)", () => {
  it("is note, cents when a band view has them, then the value", () => {
    const flat = readHover({ ...base, view: "global", x: 0, y: 130 })!;
    expect(hoverNoteText(flat)).toBe("C  1.00");
    const banded = { ...flat, cents: 9, value: 0.8 };
    expect(hoverNoteText(banded)).toBe("C +9¢  0.80");
    expect(hoverNoteText({ ...flat, cents: -12 })).toBe("C -12¢  1.00");
  });

  it("is strongest / match / frame (1-based) / seconds", () => {
    const h = readHover({ ...base, view: "global", x: 240, y: 60 })!;
    expect(hoverDetailText(h)).toBe(
      `strongest C 1.00 · match ${h.match.toFixed(2)} · frame 49/96 · ${h.sec.toFixed(2)} s`,
    );
  });
});
```

`latent-forge/src/lib/chroma/__tests__/chromaLink.test.ts`:

```ts
import { afterEach, describe, expect, it } from "vitest";
import { SCORE_PLACEHOLDER } from "../../math/clipBox";
import { chromaLink, clipScoreLabel, markerSecFor } from "../chromaLink.svelte";

afterEach(() => chromaLink.reset());

describe("the hover cross-link the lane canvas reads", () => {
  it("remembers which clip and how far into it, and forgets on clear", () => {
    chromaLink.setHover("clip-1", 0.25);
    expect(chromaLink.hover).toEqual({ clipId: "clip-1", frac: 0.25 });
    chromaLink.clearHover();
    expect(chromaLink.hover).toBe(null);
  });

  it("clamps a fraction that came from a pointer off the end of the canvas", () => {
    chromaLink.setHover("clip-1", 9);
    expect(chromaLink.hover!.frac).toBe(1);
    chromaLink.setHover("clip-1", -2);
    expect(chromaLink.hover!.frac).toBe(0);
  });
});

describe("markerSecFor (the red vertical line's position in the lane)", () => {
  it("is the clip's own start plus that fraction of its duration", () => {
    expect(markerSecFor({ start_sec: 8, dur_sec: 4 }, 0.5)).toBeCloseTo(10, 9);
    expect(markerSecFor({ start_sec: 8, dur_sec: 4 }, 0)).toBeCloseTo(8, 9);
    expect(markerSecFor({ start_sec: 8, dur_sec: 4 }, 1)).toBeCloseTo(12, 9);
  });
});

describe("the clip score label (spec §4.3, filling M5 T6's slot)", () => {
  it("falls back to M5's own placeholder for a clip nothing has analysed", () => {
    expect(clipScoreLabel(undefined)).toBe(SCORE_PLACEHOLDER);
    expect(SCORE_PLACEHOLDER).toBe("χ —");
  });

  it("shows the real mean frame match to two places, keeping the χ", () => {
    chromaLink.setScore("clip-1", 0.6234);
    expect(clipScoreLabel(chromaLink.scores["clip-1"])).toBe("χ 0.62");
  });

  it("drops a clip's score when its analysis is no longer valid", () => {
    chromaLink.setScore("clip-1", 0.5);
    chromaLink.clearScore("clip-1");
    expect(clipScoreLabel(chromaLink.scores["clip-1"])).toBe(SCORE_PLACEHOLDER);
  });

  it("reset clears both the hover and every score, so a test cannot leak into the next", () => {
    chromaLink.setHover("clip-1", 0.5);
    chromaLink.setScore("clip-1", 0.5);
    chromaLink.reset();
    expect(chromaLink.hover).toBe(null);
    expect(Object.keys(chromaLink.scores)).toEqual([]);
  });
});
```

`latent-forge/src/ui/chroma/__tests__/HoverReadout.component.test.ts`:

```ts
import { cleanup, render } from "@testing-library/svelte";
import { afterEach, describe, expect, it } from "vitest";
import type { ChromaHover } from "../../../lib/chroma/hoverReadout";
import { HOVER_DETAIL_PX, HOVER_NOTE_PX } from "../../../lib/chroma/hoverReadout";
import HoverReadout from "../HoverReadout.svelte";

const HOVER: ChromaHover = {
  frame: 48, frames: 96, frac: 0.5, pitchClass: 0, cents: null,
  value: 1, top: 7, topValue: 0.5, match: 0.62, sec: 4.46,
};

afterEach(cleanup);

describe("HoverReadout renders as DOM, never as fillText (the blocking M4 finding)", () => {
  it("puts the note name where findByText can actually find it", () => {
    const { getByText } = render(HoverReadout, { props: { hover: HOVER } });
    expect(getByText("C  1.00")).toBeTruthy();
  });

  it("puts the detail line beside it, with the frame index 1-based", () => {
    const { getByTestId } = render(HoverReadout, { props: { hover: HOVER } });
    expect(getByTestId("chroma-hover-detail").textContent).toBe(
      "strongest G 0.50 · match 0.62 · frame 49/96 · 4.46 s",
    );
  });

  it("is 14 px for the note and 9 px for the detail (spec §5.4)", () => {
    const { getByTestId } = render(HoverReadout, { props: { hover: HOVER } });
    expect(getByTestId("chroma-hover-note").style.fontSize).toBe(`${HOVER_NOTE_PX}px`);
    expect(getByTestId("chroma-hover-detail").style.fontSize).toBe(`${HOVER_DETAIL_PX}px`);
  });

  it("renders nothing at all when the pointer has left the canvas", () => {
    const { queryByTestId } = render(HoverReadout, { props: { hover: null } });
    expect(queryByTestId("chroma-hover-note")).toBeNull();
    expect(queryByTestId("chroma-hover-detail")).toBeNull();
  });
});
```

`latent-forge/src/ui/timeline/__tests__/ClipBox.score.component.test.ts`:

```ts
import { cleanup, render } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { chromaLink } from "../../../lib/chroma/chromaLink.svelte";
import { SCORE_PLACEHOLDER } from "../../../lib/math/clipBox";
import { arrangement } from "../../../lib/stores/arrangement.svelte";
import ClipBox from "../ClipBox.svelte";

beforeEach(() => {
  for (const c of [...arrangement.clips]) arrangement.removeClip(c.id);
  chromaLink.reset();
});

afterEach(() => {
  for (const c of [...arrangement.clips]) arrangement.removeClip(c.id);
  chromaLink.reset();
  cleanup();
});

describe("the clip box's score label (spec §4.3; M5 T6 left the slot for M6)", () => {
  it("keeps M5's placeholder for a clip nothing has analysed", () => {
    const clip = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: { kind: "crop", crop_id: "a" } });
    const { getByTestId } = render(ClipBox, { props: { clip } });
    expect(getByTestId("clip-score").textContent).toBe(SCORE_PLACEHOLDER);
  });

  it("shows the real mean frame match once the CHROMA tab has scored that clip", () => {
    const clip = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: { kind: "crop", crop_id: "a" } });
    chromaLink.setScore(clip.id, 0.7148);
    const { getByTestId } = render(ClipBox, { props: { clip } });
    expect(getByTestId("clip-score").textContent).toBe("χ 0.71");
  });

  it("scores only the clip it was told about, not every clip on the timeline", () => {
    const a = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: { kind: "crop", crop_id: "a" } });
    arrangement.addClip({ lane: 0, startSec: 8, durSec: 4, audio: { kind: "crop", crop_id: "b" } });
    chromaLink.setScore(a.id, 0.5);
    const { getByTestId } = render(ClipBox, { props: { clip: arrangement.clips[1] } });
    expect(getByTestId("clip-score").textContent).toBe(SCORE_PLACEHOLDER);
  });
});
```

- [ ] **Step 2: Run the tests — they must fail**

```bash
cd latent-forge && npx vitest run src/lib/chroma/__tests__/hoverReadout.test.ts src/lib/chroma/__tests__/chromaLink.test.ts src/ui/chroma/__tests__/HoverReadout.component.test.ts src/ui/timeline/__tests__/ClipBox.score.component.test.ts
```

Expected: three suites fail on module resolution — `Failed to resolve import "../hoverReadout"`,
`Failed to resolve import "../chromaLink.svelte"` and
`Failed to resolve import "../HoverReadout.svelte"`. `ClipBox.score.component.test.ts` fails on its
own import of `../../../lib/chroma/chromaLink.svelte` for the same reason; once that module exists
it would still fail every assertion, because M5 T6's `ClipBox.svelte` renders a bare
`<span class="score">` with no `data-testid` and never reads a score.

- [ ] **Step 3: Write the readout, the link, and make the two timeline edits**

`latent-forge/src/lib/chroma/hoverReadout.ts`:

```ts
// The hover readout's content (spec §5.4: "reads note name + frame index into
// the readout (14 px note, 9 px detail)"; v3 onChromaHover 1944-1965 and the
// two strings at 1968-1973).
//
// Pure, and deliberately NOT a component: what a pixel means is the part that
// breaks, and it can be pinned here without a canvas. The component below does
// nothing but put the two strings in two elements.
//
// One correction to the drawing. v3's hover derives the pitch class from
// (row / 128) * 12, which assumes C sits at bin 0. It does not -- C is at bin
// 2.0 (the same_chroma PITFALL, spec §5.4) -- so the drawing's readout names
// the wrong note near every class boundary. This goes through Task 6's
// rowPitchClass/rowCents, which go through Task 1's binToPitchClass.

import { NOTE_NAMES, fold12Column } from "./bins";
import type { ChromaResult } from "./chromaClient.svelte";
import { type ChromaView, type FrameWindow, cellValue, rowCents, rowPitchClass, xToFrame, yToRow } from "./heatmapGeometry";
import { matchFrame, rotate } from "./match";

/** Spec §5.4, and v3 339-340. */
export const HOVER_NOTE_PX = 14;
export const HOVER_DETAIL_PX = 9;

export interface ChromaHover {
  /** 0-based frame index into the clip's analysis. */
  frame: number;
  frames: number;
  /** Where in the clip, 0..1 -- what the lane's red marker is drawn from. */
  frac: number;
  pitchClass: number;
  /** Cents off the class centre in a band view; null in GLOBAL. */
  cents: number | null;
  /** The value of the cell actually under the pointer. */
  value: number;
  /** The frame's strongest 12-class entry, and its value. */
  top: number;
  topValue: number;
  match: number;
  sec: number;
}

export interface HoverArgs {
  result: ChromaResult;
  target: Float32Array;
  view: ChromaView;
  win: FrameWindow;
  x: number;
  y: number;
  widthPx: number;
  heightPx: number;
  /**
   * The ANALYSIS detune, not the clip's: 0 when `result` came from the
   * already-stretched `clip.previewAudio` (M5 T10's runStretch pitch-shifted
   * that audio by clip.detune_cents / 100, so the fold is already detuned and
   * rotating it again applies the detune twice), and clip.detune_cents when
   * `result` came from the raw clip.audio. Task 11 derives it once as
   * `analysisDetuneCents`; never re-derive it here.
   */
  detuneCents: number;
}

export function readHover(args: HoverArgs): ChromaHover | null {
  const { result, target, view, win, x, y, widthPx, heightPx, detuneCents } = args;
  const row = yToRow(y, view, heightPx);
  if (row === null) return null;            // the target's reference row
  if (result.T <= 0) return null;

  const frame = xToFrame(x, win, widthPx);
  const col = fold12Column(result.fold12, result.T, frame);
  let top = 0;
  for (let p = 1; p < 12; p++) if (col[p] > col[top]) top = p;

  return {
    frame,
    frames: result.T,
    frac: result.T > 1 ? frame / (result.T - 1) : 0,
    pitchClass: rowPitchClass(row, view),
    cents: rowCents(row, view),
    value: cellValue(result, view, frame, row),
    top,
    topValue: col[top],
    match: matchFrame(rotate(col, detuneCents / 100), target),
    sec: frame / result.fps,
  };
}

export function hoverNoteText(h: ChromaHover): string {
  // `h.cents` is `number | null`, and 0 is falsy: a band-view hover landing
  // exactly on a class centre (bins 2, 34, 66, 98) has cents === 0 and must
  // still show "0¢", or it is indistinguishable from a GLOBAL hover, where
  // cents genuinely do not exist. Test the null, never the truthiness.
  const cents = h.cents === null ? "" : `${h.cents > 0 ? "+" : ""}${h.cents}¢ `;
  return `${NOTE_NAMES[h.pitchClass]} ${cents} ${h.value.toFixed(2)}`.replace(/\s{3,}/g, "  ");
}

export function hoverDetailText(h: ChromaHover): string {
  return `strongest ${NOTE_NAMES[h.top]} ${h.topValue.toFixed(2)} · match ${h.match.toFixed(2)} · frame ${h.frame + 1}/${h.frames} · ${h.sec.toFixed(2)} s`;
}
```

`latent-forge/src/lib/chroma/chromaLink.svelte.ts`:

```ts
// The seam between the CHROMA tab and the timeline. Two facts, both written by
// the tab and read by M5's components, and nothing else:
//
//   hover  -- which clip is being hovered and how far into it, so the lane
//             canvas can draw the red vertical line spec §5.4 asks for;
//   scores -- the mean frame match per clip, so the clip box can replace M5
//             T6's SCORE_PLACEHOLDER with a real number.
//
// It is a store rather than a prop chain because the two sides are three
// components apart (CHROMA tab -> BottomPane -> App -> Timeline -> LaneCanvas)
// and M5's components take no props from anything above the timeline. Adding
// this singleton costs LaneCanvas one import and nine lines; threading props
// would have meant editing four M5 files.
//
// Note the $state proxy rule does not bite here: nothing appends an object to
// a $state array. `scores` is a plain record whose values are numbers, and a
// deep-proxied assignment to a property is exactly what we want.

import { SCORE_PLACEHOLDER } from "../math/clipBox";

export class ChromaLink {
  hover = $state<{ clipId: string; frac: number } | null>(null);
  scores = $state<Record<string, number>>({});

  setHover(clipId: string, frac: number): void {
    const f = Number.isFinite(frac) ? (frac < 0 ? 0 : frac > 1 ? 1 : frac) : 0;
    this.hover = { clipId, frac: f };
  }

  clearHover(): void {
    this.hover = null;
  }

  setScore(clipId: string, score: number): void {
    this.scores[clipId] = score;
  }

  clearScore(clipId: string): void {
    delete this.scores[clipId];
  }

  reset(): void {
    this.hover = null;
    this.scores = {};
  }
}

export const chromaLink = new ChromaLink();

/**
 * The clip box's score label. `undefined` -- a clip nothing has analysed --
 * keeps M5 T6's own placeholder, which is what it is for: §5.4's number needs
 * a /forge/chroma round trip per clip, and only the selected clip and the
 * TARGET lane's clips are analysed.
 */
export function clipScoreLabel(score: number | undefined): string {
  return score === undefined || !Number.isFinite(score) ? SCORE_PLACEHOLDER : `χ ${score.toFixed(2)}`;
}

/** Timeline seconds for a hover fraction into a clip. */
export function markerSecFor(clip: { start_sec: number; dur_sec: number }, frac: number): number {
  return clip.start_sec + frac * clip.dur_sec;
}
```

`latent-forge/src/ui/chroma/HoverReadout.svelte`:

```svelte
<script lang="ts">
  // The hover readout (spec §5.4: 14 px note, 9 px detail; v3 338-341).
  //
  // DOM, as siblings of the canvas -- never fillText. A fillText label can
  // never be found by findByText, which was a blocking M4 finding, and the two
  // sizes the spec pins are CSS.
  //
  // No data-help: M1 T14's table has no id for the hover readout (v3 338), so
  // none is invented. See the plan's open questions.
  import {
    type ChromaHover,
    HOVER_DETAIL_PX,
    HOVER_NOTE_PX,
    hoverDetailText,
    hoverNoteText,
  } from "../../lib/chroma/hoverReadout";

  interface Props {
    hover: ChromaHover | null;
  }
  let { hover }: Props = $props();
</script>

{#if hover}
  <div class="readout">
    <div class="note" data-testid="chroma-hover-note" style="font-size:{HOVER_NOTE_PX}px">
      {hoverNoteText(hover)}
    </div>
    <div class="detail" data-testid="chroma-hover-detail" style="font-size:{HOVER_DETAIL_PX}px">
      {hoverDetailText(hover)}
    </div>
  </div>
{/if}

<style>
  .readout {
    flex-shrink: 0;
    margin-top: 3px;
    padding: 4px 6px;
    background: var(--panel2);
    border: 1px solid var(--border);
  }
  .note {
    font-weight: 600;
    line-height: 1.1;
    color: var(--purple-strong);
  }
  .detail {
    line-height: 1.35;
    color: var(--text-dim);
  }
</style>
```

Modify `latent-forge/src/ui/timeline/LaneCanvas.svelte` (M5 T5). Add one import to the script block,
beside the existing ones:

```ts
  import { chromaLink, markerSecFor } from "../../lib/chroma/chromaLink.svelte";
```

Append this block at the **end of `redraw()`**, after the downbeat loop's closing brace and before
the function's own closing brace:

```ts
    // Spec §5.4: hovering the chroma heatmap draws a red vertical line at that
    // frame on the selected clip, in its own lane. Last, so it sits over the
    // waveform and the downbeats.
    const mark = chromaLink.hover;
    if (mark) {
      const marked = laneClips.find((c) => c.id === mark.clipId);
      if (marked) {
        const x = Math.round(secToPx(markerSecFor(marked, mark.frac), scrollSec, pxPerSec)) + 0.5;
        if (x >= 0 && x <= w) {
          ctx.strokeStyle = red;
          ctx.lineWidth = 1.5;
          ctx.beginPath();
          ctx.moveTo(x, 0);
          ctx.lineTo(x, h);
          ctx.stroke();
        }
      }
    }
```

and add one line to the existing draw `$effect`, beside its other `void` reads, so a hover repaints:

```ts
    void chromaLink.hover;
```

`w`, `h`, `ctx`, `scrollSec`, `pxPerSec`, `laneClips` and `red` are all already in `redraw()`'s scope
(M5 T5), and `secToPx` is already imported from `../../lib/math/viewport`. Nothing else in the file
changes.

Modify `latent-forge/src/ui/timeline/ClipBox.svelte` (M5 T6). Add one import:

```ts
  import { chromaLink, clipScoreLabel } from "../../lib/chroma/chromaLink.svelte";
```

and replace

```svelte
    <span class="score">{SCORE_PLACEHOLDER}</span>
```

with

```svelte
    <span class="score" data-testid="clip-score">{clipScoreLabel(chromaLink.scores[clip.id])}</span>
```

`SCORE_PLACEHOLDER` stays imported in `clipBox.ts` and is still the value `clipScoreLabel` returns
for an unanalysed clip; `ClipBox.svelte` itself no longer needs the import, so drop it from its
import list if `svelte-check` reports it unused.

- [ ] **Step 4: Run them, expect pass**

```bash
cd latent-forge && npx vitest run src/lib/chroma/__tests__/hoverReadout.test.ts src/lib/chroma/__tests__/chromaLink.test.ts src/ui/chroma/__tests__/HoverReadout.component.test.ts src/ui/timeline/__tests__/ClipBox.score.component.test.ts && npm run check
```

Expected: `Test Files  4 passed (4)` / `Tests  23 passed (23)` — 9 in `hoverReadout.test.ts`,
7 in `chromaLink.test.ts`, 4 in `HoverReadout.component.test.ts` and 3 in
`ClipBox.score.component.test.ts` — and `svelte-check found 0 errors and 0 warnings`.

Then confirm M5's own timeline suites still pass with the two edits in place:

```bash
cd latent-forge && npx vitest run src/ui/timeline src/lib/math/__tests__/clipBox.test.ts src/lib/math/__tests__/laneCanvas.test.ts
```

Expected: every M5 timeline suite still green — the edits add a marker and a label and change no
existing assertion.

- [ ] **Step 5: Commit**

```bash
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M6 T10: hover readout as DOM at 14/9 px (never fillText), chromaLink seam for the lane's red frame marker, and M5 T6's SCORE_PLACEHOLDER filled with the real mean frame match"
```

---
### Task 11: tab assembly, the stretch debounce, the missing fixture, Playwright, self-review

Spec §4.5 (`CHROMA` — §5.4), §5.4 and §9.7. Tasks 6-10 are pieces; this composes them into M1's
`[data-region="bottom-tab-body"]` (162 px) for `bottomTab === "chroma"`, exactly as M4 T10 mounts
`PromptSigmaTab` into the same body for `tab === "prompt"`. The tab's right-aligned hint is already
M1 T12's (`bottomHint("chroma")` → `hover the heatmap to read a frame`); **do not re-render it.**

**Which of the two requests leads, plainly.** §5.4 says a detune change re-stretches the clip's
preview through `/forge/stretch`, debounced 400 ms, *and* that chroma is computed on the stretched
preview "so it matches what the timeline plays". Those are sequential, not parallel: **the stretch
leads, the chroma follows.** `arrangement.setDetune` (from the strip, or from M5 T4's lane-header
DETUNE ¢ field) → this tab's one `$effect` on the selected clip's `detune_cents` arms M5 T10's
`scheduleStretch(clipId, onError)` → 400 ms later that writes `clip.previewAudio` → a second
`$effect` reading `clip.previewAudio ?? clip.audio` sees a new ref and requests `/forge/chroma` for
it. Nothing requests chroma on the *old* audio in between, because the chroma effect is keyed on the
ref, not on the detune. One debounce, one owner, both writers of detune covered.

**The mock server has no chroma fixture.** M1 T6 routes `POST /forge/chroma` → fixture
`forge_chroma_render` (M1 plan line 1595 and 2027-2028); there is no
`handmade-forge_chroma_render.json`, so the route 501s today. This task adds it.

**M1 T6's own fixture-file test no longer needs an edit for that.** It used to assert the handmade
set was **exactly ten files, by name** (M1 plan lines 1668-1680), which meant every milestone that
added a fixture — this one included — had to widen that same list in the same commit or turn M1 T6
red. **RESOLVED 2026-09-22 by WINTERMUTE: fixed at the root, in M1, not per-milestone.** M1 T6's
test is now a superset check — every name M1 itself ships must be present, not an exact match — so
this task creates `handmade-forge_chroma_render.json` and stops there; M10 T7's own fixtures needed
the identical fix and its edit to `plugin.test.ts` is reverted for the same reason (see that plan's
Task 7).

**Files:**
- Create: `latent-forge/src/ui/chroma/ChromaTab.svelte`,
  `latent-forge/src/ui/chroma/__tests__/ChromaTab.component.test.ts`
- Modify: `latent-forge/src/ui/shell/BottomPane.svelte` (M1 T11 — mount the tab body)
- Create: `latent-forge/mock/makeChromaFixture.mjs`
- Create (generated by it, committed):
  `docs/latent-forge/contract/fixtures/handmade-forge_chroma_render.json`
- Create: `latent-forge/mock/__tests__/chromaFixture.test.ts`
- Create: `latent-forge/tests/chroma.spec.ts`

**Interfaces:**
- Consumes `ChromaHeatmap` (**Task 6**, props `{ view: ChromaView; win: FrameWindow; result:
  ChromaResult | null; target: Float32Array; detuneCents?: number; onwin?: (w: FrameWindow) => void }`,
  DOM `[data-testid="chroma-heatmap"]`), `MatchCurveOverlay` (**Task 7**, props `{ result:
  ChromaResult | null; target: Float32Array; win: FrameWindow; detuneCents?: number }`),
  `MatchLegend` (**Task 7**, props `{ target: Float32Array; clipScore: number | null }`),
  `DetuneScanStrip` (**Task 8**, props `{ clip: ForgeClip | null; result: ChromaResult | null;
  target: Float32Array; criterion: ScanCriterion; detuneCents?: number;
  oncriterion?: (c: ScanCriterion) => void }`),
  `TargetRow` (**Task 9**, no props) and `HoverReadout` (**Task 10**, props `{ hover: ChromaHover |
  null }`), all default exports from `latent-forge/src/ui/chroma/`. **Every `detuneCents` above takes
  this task's `analysisDetuneCents`, never `clip.detune_cents`** — see the Normative block's "how
  much detune to rotate by" row and Open question 6.
- Consumes `CHROMA_VIEWS: readonly ChromaView[]`, `VIEW_LABELS: Record<ChromaView, string>`,
  `type ChromaView = "global" | "bass" | "mid" | "high"`,
  `interface FrameWindow { from: number; to: number }` and `fullWindow(T): FrameWindow` from
  `latent-forge/src/lib/chroma/heatmapGeometry.ts` (**Task 6**).
- Consumes the singleton `chromaClient` (`$state` fields `result: ChromaResult | null`,
  `pending: boolean`, `error: string | null`; methods `request(audio: AudioRef): Promise<void>`,
  `flush(): Promise<void>`, `dispose(): void`) and
  `interface ChromaResult { frames: number; fps: number; bands: Float32Array; fold12: Float32Array;
  T: number }` from `latent-forge/src/lib/chroma/chromaClient.svelte.ts` (**Task 2**).
- Consumes `meanMatchAtDetune(fold12: Float32Array, T: number, target: Float32Array, cents: number):
  number` (§5.4's clip score — **every** frame, no stride; `cents` is this task's
  **`analysisDetuneCents`**, not `clip.detune_cents`) and `type ScanCriterion =
  "highest" | "steadiest"` from `latent-forge/src/lib/chroma/detuneScan.ts` (**Task 5**).
- Consumes the singleton `chromaTarget` (`mode`, `profile: Float32Array`, `loadLane(refs): Promise<void>`,
  `error`) and `laneTargetRefs(clips, lane): AudioRef[]` from
  `latent-forge/src/lib/chroma/targetStore.svelte.ts` (**Task 9**).
- Consumes the singleton `chromaLink` (`hover`, `scores`, `setHover(clipId, frac)`, `clearHover()`,
  `setScore(clipId, score)`, `reset()`) from `latent-forge/src/lib/chroma/chromaLink.svelte.ts`
  (**Task 10**), and `readHover(args): ChromaHover | null` from
  `latent-forge/src/lib/chroma/hoverReadout.ts` (**Task 10**).
- Consumes `scheduleStretch(clipId: string, onError?: (e: ForgeApiError) => void): void` — debounced
  400 ms, re-arms on every call for the same clip, writes `clip.previewAudio` — from
  `latent-forge/src/lib/clips/lifecycle.ts` (**M5 T10**), and `ForgeApiError { status: number;
  message: string }` from `latent-forge/src/lib/forge/api.ts` (**M1 T5**).
- Consumes the singleton `arrangement` from `latent-forge/src/lib/stores/arrangement.svelte.ts`
  (**M5 T1**): `clips: ForgeClip[]`, `targetLane: 0 | 1 | 2 | 3 | null`, and — used by this task's
  own component test, so restated here rather than looked up —
  `addClip(args: AddClipArgs): ForgeClip` where
  `interface AddClipArgs { lane: 0|1|2|3; startSec: number; durSec: number; audio: AudioRef;
  nativeBpm?: number | null; downbeatsSec?: number[] }` (M5:315, M5:396),
  `removeClip(id: string): void` (M5:422),
  `setDetune(id: string, cents: number): void` (M5:481 — clamps to ±100 and rounds) and
  `setPreviewAudio(id: string, ref: AudioRef | null): void` (M5:5200 — added to the store by M5 T10).
  **`arrangement.selectedClip` is promised in M5 T1's Interfaces line but never defined in its Step 3
  code** — M5's own self-review says so, and M5 T9 computes the selected clip locally instead. This
  task does the same: `view.selection.kind === "clip"` then `arrangement.clips.find(...)`.
- Consumes the singleton `view` from `latent-forge/src/lib/stores/view.svelte.ts` (**M1 T7**):
  `view.bottomTab: BottomTabId`, `view.selection: Target` where
  `Target = {kind:"none"} | {kind:"clip"; id:string} | {kind:"overlap"; key:string}`, and
  `view.appendLog(text: string, level?: "info" | "error"): TerminalLine`, which returns the array's
  **live** element (the `$state` proxy rule). Four more that this task's own component test calls,
  restated so an agent reading only `### Task 11` need look nothing up:
  `select(target: Target): void` (M1:3244), `clearSelection(): void` (M1:3248),
  `clearLog(): void` (M1:3274) and the field `logLines: TerminalLine[]` (M1:3145) where
  `interface TerminalLine { seq: number; text: string; level: "info" | "error" }` — `appendLog` is
  M1:3261.
- Consumes `ForgeClip` and `AudioRef` from `latent-forge/src/lib/forge/types.ts` (**M1 T3**);
  `ForgeClip.previewAudio: AudioRef | null` is the stretched preview (M5 T10), **in-memory only and
  never serialised**, so the tab always reads `clip.previewAudio ?? clip.audio`.
- Consumes, for the BottomPane edit: M1 T11's `<div class="tab-body" data-region="bottom-tab-body"
  data-tab={tab}>` and its `{#if tab === "chroma"}` branch, whose body is the placeholder comment
  `<!-- body: M6 (spec §5.4) -->` with `<div class="tab-empty"></div>`. The `.tab-body` element's own
  `flex: 0 0 162px` and `overflow: hidden` stay exactly as M1 wrote them.
- Produces the component `ChromaTab` (no props), rendering `[data-region="chroma-tab"]`,
  `[data-chroma-view="global"|"bass"|"mid"|"high"]` (no `data-help` — M1 T14 has no id for them),
  `[data-testid="chroma-curve-toggle"]`, `[data-testid="chroma-empty"]` and
  `[data-testid="chroma-error"]`.
- Produces `docs/latent-forge/contract/fixtures/handmade-forge_chroma_render.json`, matching §6.3's
  shape exactly: `{status: 200, body: {ok, frames: 24, fps: 10.7666015625, bands: {shape: [3,128,24],
  scale: [s0,s1,s2], data_b64}, fold12: {shape: [12,24], scale: 1.0, data_b64}}}`, uint8 C-order,
  **containing no absolute path under `/home/kim` or `/run/media`** (it contains no paths at all).

- [ ] **Step 1: Write the failing tests, the fixture generator and the Playwright spec**

`latent-forge/src/ui/chroma/__tests__/ChromaTab.component.test.ts`:

```ts
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import { tick } from "svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { chromaClient } from "../../../lib/chroma/chromaClient.svelte";
import { chromaLink } from "../../../lib/chroma/chromaLink.svelte";
import { meanMatchAtDetune } from "../../../lib/chroma/detuneScan";
import { chromaTarget } from "../../../lib/chroma/targetStore.svelte";
import { arrangement } from "../../../lib/stores/arrangement.svelte";
import { view } from "../../../lib/stores/view.svelte";
import ChromaTab from "../ChromaTab.svelte";

const scheduleStretch = vi.fn();
vi.mock("../../../lib/clips/lifecycle", () => ({
  scheduleStretch: (...args: unknown[]) => scheduleStretch(...args),
}));

// Waiting for Svelte is `await tick()`, never `await Promise.resolve()`.
// Svelte 5 flushes its scheduler in a microtask as well, so a bare resolved
// promise is not ORDERED after the re-render -- it happens to work today and
// is a flake tomorrow. `chromaClient.flush()` and timer advances stay where
// the test is genuinely waiting on a fetch or a debounce rather than the DOM.

/** /forge/chroma's own wire shape (spec §6.3), one frame of pure C. */
function chromaBody(T: number) {
  const bands = new Uint8Array(3 * 128 * T);
  const fold = new Uint8Array(12 * T);
  for (let t = 0; t < T; t++) {
    bands[(0 * 128 + 2) * T + t] = 255;
    fold[0 * T + t] = 255;
  }
  const b64 = (u: Uint8Array) => {
    let s = "";
    for (const b of u) s += String.fromCharCode(b);
    return btoa(s);
  };
  return {
    ok: true,
    frames: T,
    fps: 10.7666015625,
    bands: { shape: [3, 128, T], scale: [1, 1, 1], data_b64: b64(bands) },
    fold12: { shape: [12, T], scale: 1.0, data_b64: b64(fold) },
  };
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

beforeEach(() => {
  scheduleStretch.mockClear();
  chromaClient.dispose();
  chromaTarget.dispose();
  chromaLink.reset();
  view.clearLog();
  view.clearSelection();
  for (const c of [...arrangement.clips]) arrangement.removeClip(c.id);
  Object.defineProperty(HTMLCanvasElement.prototype, "clientWidth", { configurable: true, get: () => 480 });
  Object.defineProperty(HTMLCanvasElement.prototype, "clientHeight", { configurable: true, get: () => 131 });
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
});

afterEach(() => {
  delete (HTMLCanvasElement.prototype as unknown as Record<string, unknown>).clientWidth;
  delete (HTMLCanvasElement.prototype as unknown as Record<string, unknown>).clientHeight;
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.useRealTimers();
  chromaClient.dispose();
  chromaTarget.dispose();
  chromaLink.reset();
  for (const c of [...arrangement.clips]) arrangement.removeClip(c.id);
  cleanup();
});

function selectAClip(over: { detune?: number } = {}) {
  const clip = arrangement.addClip({
    lane: 0, startSec: 0, durSec: 4, audio: { kind: "crop", crop_id: "000412" },
  });
  if (over.detune !== undefined) arrangement.setDetune(clip.id, over.detune);
  view.select({ kind: "clip", id: clip.id });
  return arrangement.clips[0];
}

describe("the mode row (spec §5.4, v3 288 and 2011-2016)", () => {
  it("is the four views plus MATCH CURVE, none of them with a data-help M1 does not have", () => {
    const { container, getByTestId } = render(ChromaTab);
    const views = [...container.querySelectorAll("[data-chroma-view]")];
    expect(views.map((b) => b.getAttribute("data-chroma-view"))).toEqual(["global", "bass", "mid", "high"]);
    expect(views.map((b) => b.textContent)).toEqual(["GLOBAL", "BASS oct1", "MID oct5", "HIGH oct9"]);
    for (const b of views) expect(b.hasAttribute("data-help")).toBe(false);
    expect(getByTestId("chroma-curve-toggle").textContent).toBe("MATCH CURVE");
  });

  it("switches the active view, and MATCH CURVE mounts and unmounts the overlay", async () => {
    const { container, getByTestId, queryByTestId } = render(ChromaTab);
    expect(getByTestId("chroma-match-curve")).toBeTruthy();
    await fireEvent.click(getByTestId("chroma-curve-toggle"));
    expect(queryByTestId("chroma-match-curve")).toBeNull();
    await fireEvent.click(container.querySelector('[data-chroma-view="mid"]')!);
    expect(container.querySelector('[data-chroma-view="mid"]')!.classList.contains("on")).toBe(true);
  });
});

describe("honest empty states (spec §9.7 and §5.4)", () => {
  it("says no clip is selected rather than drawing an empty heatmap", () => {
    const { getByTestId } = render(ChromaTab);
    expect(getByTestId("chroma-empty").textContent).toBe("no clip selected");
  });

  it("says it is still computing while the request is in flight", async () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => {})));
    selectAClip();
    const { getByTestId } = render(ChromaTab);
    await tick();
    expect(getByTestId("chroma-empty").textContent).toBe("computing chroma…");
  });

  it("shows a server error in one line AND as a red TERMINAL line (spec §9.7)", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json({ ok: false, error: "no such crop" }, 404)));
    selectAClip();
    const { getByTestId } = render(ChromaTab);
    await chromaClient.flush();
    await tick();
    expect(getByTestId("chroma-error").textContent).toContain("no such crop");
    const last = view.logLines[view.logLines.length - 1];
    expect(last.level).toBe("error");
    expect(last.text).toContain("no such crop");
  });
});

describe("what the tab asks the server for (spec §5.4, §6.3)", () => {
  it("analyses the STRETCHED preview when the clip has one, not the source audio", async () => {
    const seen: unknown[] = [];
    vi.stubGlobal("fetch", vi.fn(async (_u: string, init?: RequestInit) => {
      seen.push(JSON.parse(String(init?.body ?? "{}")));
      return json(chromaBody(8));
    }));
    const clip = selectAClip();
    arrangement.setPreviewAudio(clip.id, { kind: "path", path: "/stretched.wav" });
    render(ChromaTab);
    await chromaClient.flush();
    expect(seen).toEqual([{ audio: { kind: "path", path: "/stretched.wav" } }]);
  });

  it("falls back to the source audio for an unstretched clip", async () => {
    const seen: unknown[] = [];
    vi.stubGlobal("fetch", vi.fn(async (_u: string, init?: RequestInit) => {
      seen.push(JSON.parse(String(init?.body ?? "{}")));
      return json(chromaBody(8));
    }));
    selectAClip();
    render(ChromaTab);
    await chromaClient.flush();
    expect(seen).toEqual([{ audio: { kind: "crop", crop_id: "000412" } }]);
  });
});

describe("detune: the stretch leads and the chroma follows (spec §5.4)", () => {
  it("arms M5 T10's debounced stretch once per detune change, and never its own", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(chromaBody(8))));
    const clip = selectAClip();
    render(ChromaTab);
    await chromaClient.flush();
    scheduleStretch.mockClear();
    arrangement.setDetune(clip.id, 24);
    await tick();
    expect(scheduleStretch).toHaveBeenCalledTimes(1);
    expect(scheduleStretch).toHaveBeenCalledWith(clip.id, expect.any(Function));
  });

  it("re-requests chroma when the stretch lands a new previewAudio, not when detune changes", async () => {
    const seen: unknown[] = [];
    vi.stubGlobal("fetch", vi.fn(async (_u: string, init?: RequestInit) => {
      seen.push(JSON.parse(String(init?.body ?? "{}")));
      return json(chromaBody(8));
    }));
    const clip = selectAClip();
    render(ChromaTab);
    await chromaClient.flush();
    expect(seen).toHaveLength(1);

    arrangement.setDetune(clip.id, 24);
    await tick();
    expect(seen).toHaveLength(1); // the detune alone asks the server nothing

    arrangement.setPreviewAudio(clip.id, { kind: "path", path: "/stretched-24.wav" });
    await chromaClient.flush();
    expect(seen).toHaveLength(2);
    expect(seen[1]).toEqual({ audio: { kind: "path", path: "/stretched-24.wav" } });
  });
});

describe("the clip score label and the lane cross-link", () => {
  it("writes the clip's mean frame match into chromaLink once the analysis lands", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(chromaBody(8))));
    chromaTarget.setChordText("C");
    const clip = selectAClip();
    render(ChromaTab);
    await chromaClient.flush();
    await tick();
    expect(chromaLink.scores[clip.id]).toBeGreaterThan(0);
  });

  it("does NOT rotate a STRETCHED clip's chroma by its detune -- the stretch already applied it", async () => {
    // The 2026-09-22 critic's blocking finding, pinned. M5 T10's runStretch
    // pitch-shifts previewAudio by clip.detune_cents / 100 (M5:5358) and this
    // tab analyses that preview, so result.fold12 is ALREADY detuned; rotating
    // it again by the clip's detune applied the detune twice. No test set BOTH
    // a previewAudio and a non-zero detune_cents, which is why nothing caught
    // it -- this one sets both, and asserts the UN-rotated score.
    vi.stubGlobal("fetch", vi.fn(async () => json(chromaBody(8))));
    chromaTarget.setChordText("C");
    const clip = selectAClip({ detune: 50 });
    arrangement.setPreviewAudio(clip.id, { kind: "path", path: "/stretched-50.wav" });
    render(ChromaTab);
    await chromaClient.flush();
    await tick();
    const res = chromaClient.result!;
    const target = chromaTarget.profile;
    expect(chromaLink.scores[clip.id]).toBeCloseTo(meanMatchAtDetune(res.fold12, res.T, target, 0), 9);
    // and it is genuinely a different number, so the assertion above has teeth:
    // rotating [1,0,...] by half a class splits it across classes 0 and 1.
    expect(chromaLink.scores[clip.id]).not.toBeCloseTo(
      meanMatchAtDetune(res.fold12, res.T, target, 50),
      6,
    );
  });

  it("marks the hovered frame on the clip in its lane, and clears it on leave", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(chromaBody(8))));
    const clip = selectAClip();
    const { container, getByTestId } = render(ChromaTab);
    await chromaClient.flush();
    await tick();
    const box = container.querySelector('[data-region="chroma-heatmap-box"]')! as HTMLElement;
    vi.spyOn(box, "getBoundingClientRect").mockReturnValue({
      left: 0, top: 0, width: 480, height: 131, right: 480, bottom: 131, x: 0, y: 0, toJSON: () => ({}),
    });
    await fireEvent.pointerMove(box, { clientX: 240, clientY: 120 });
    expect(chromaLink.hover?.clipId).toBe(clip.id);
    expect(getByTestId("chroma-hover-note")).toBeTruthy();
    await fireEvent.pointerLeave(box);
    expect(chromaLink.hover).toBe(null);
  });
});
```

`latent-forge/mock/__tests__/chromaFixture.test.ts`:

```ts
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { FIXTURE_DIR } from "../plugin";

const RAW = readFileSync(resolve(FIXTURE_DIR, "handmade-forge_chroma_render.json"), "utf8");
const FIX = JSON.parse(RAW) as {
  status: number;
  body: {
    ok: true; frames: number; fps: number;
    bands: { shape: [number, number, number]; scale: [number, number, number]; data_b64: string };
    fold12: { shape: [number, number]; scale: number; data_b64: string };
  };
};

function byteLength(b64: string): number {
  return Buffer.from(b64, "base64").length;
}

describe("handmade-forge_chroma_render.json is exactly spec §6.3's shape", () => {
  it("carries the 200 envelope and the latent frame rate", () => {
    expect(FIX.status).toBe(200);
    expect(FIX.body.ok).toBe(true);
    expect(FIX.body.fps).toBe(10.7666015625);
    expect(FIX.body.frames).toBe(24);
  });

  it("is [3,128,T] with THREE band scales and [12,T] with ONE fold scale", () => {
    expect(FIX.body.bands.shape).toEqual([3, 128, 24]);
    expect(FIX.body.bands.scale).toHaveLength(3);
    expect(FIX.body.fold12.shape).toEqual([12, 24]);
    expect(FIX.body.fold12.scale).toBe(1.0);
  });

  it("decodes to exactly one uint8 per element, C-order", () => {
    expect(byteLength(FIX.body.bands.data_b64)).toBe(3 * 128 * 24);
    expect(byteLength(FIX.body.fold12.data_b64)).toBe(12 * 24);
  });

  it("leaks no absolute server path", () => {
    expect(RAW.match(/\/(home|run\/media|mnt|Users)\//g) ?? []).toEqual([]);
  });
});
```

`latent-forge/mock/makeChromaFixture.mjs` — the generator, run once, its output committed. A 9 KiB
base64 blob is not something to hand-type into a plan or a review; this is deterministic, re-runnable
and reviewable:

```js
// Generates docs/latent-forge/contract/fixtures/handmade-forge_chroma_render.json,
// the mock server's answer for POST /forge/chroma (spec §6.3). M1 T6 maps that
// route to the fixture name `forge_chroma_render`; without this file the route
// 501s with "no fixture ... yet", which is what the whole CHROMA tab would have
// hit on every selection.
//
// Run:  node mock/makeChromaFixture.mjs
//
// The content is a plain C major triad (C, E, G) with a slow swell, so the
// heatmap, the match curve and the detune scan all have something honest to
// draw against a C-ish target. No paths of any kind, so the fixture cannot leak
// a server path (M1's own fixture rule).

import { writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const T = 24;
const BANDS = 3;
const BINS = 128;
const BINS_PER_SEMITONE = BINS / 12;
const C_BIN = 2.0;

/** The server's own centres: C at 2.0, each semitone 128/12 apart. */
function centre(pc) {
  return (C_BIN + pc * BINS_PER_SEMITONE) % BINS;
}

/** Triangular bump of half-width one semitone around a bin, wrapping. */
function bump(bin, at) {
  let d = Math.abs(bin - at);
  d = Math.min(d, BINS - d);
  return Math.max(0, 1 - d / BINS_PER_SEMITONE);
}

const CHORD = [0, 4, 7];
const BAND_GAIN = [0.9, 1.0, 0.6]; // oct 1 / oct 5 / oct 9

const bands = new Float64Array(BANDS * BINS * T);
for (let b = 0; b < BANDS; b++) {
  for (let i = 0; i < BINS; i++) {
    for (let t = 0; t < T; t++) {
      const swell = 0.55 + 0.45 * Math.sin((t / T) * Math.PI);
      let v = 0;
      for (let k = 0; k < CHORD.length; k++) {
        v += bump(i, centre(CHORD[k])) * (1 - k * 0.18);
      }
      bands[(b * BINS + i) * T + t] = v * BAND_GAIN[b] * swell;
    }
  }
}

// One scale per band, over that band's own slice -- spec §6.3.
const per = BINS * T;
const bandBytes = new Uint8Array(BANDS * per);
const bandScale = [];
for (let b = 0; b < BANDS; b++) {
  let max = 0;
  for (let i = 0; i < per; i++) max = Math.max(max, bands[b * per + i]);
  const scale = max > 0 ? Number(max.toFixed(6)) : 1;
  bandScale.push(scale);
  for (let i = 0; i < per; i++) {
    bandBytes[b * per + i] = Math.round(Math.min(255, (bands[b * per + i] / scale) * 255));
  }
}

// The 12-class fold: sum each bin into its nearest centre, then normalise the
// whole clip to 1 so the single fold12 scale of 1.0 is exact.
const fold = new Float64Array(12 * T);
for (let b = 0; b < BANDS; b++) {
  for (let i = 0; i < BINS; i++) {
    let best = 0;
    let bd = Infinity;
    for (let pc = 0; pc < 12; pc++) {
      const raw = Math.abs(i - centre(pc));
      const d = Math.min(raw, BINS - raw);
      if (d < bd) {
        bd = d;
        best = pc;
      }
    }
    for (let t = 0; t < T; t++) fold[best * T + t] += bands[(b * BINS + i) * T + t];
  }
}
let fmax = 0;
for (const v of fold) fmax = Math.max(fmax, v);
const foldBytes = new Uint8Array(12 * T);
for (let i = 0; i < fold.length; i++) {
  foldBytes[i] = Math.round(Math.min(255, (fold[i] / (fmax || 1)) * 255));
}

const fixture = {
  status: 200,
  body: {
    ok: true,
    frames: T,
    fps: 10.7666015625,
    bands: {
      shape: [BANDS, BINS, T],
      scale: bandScale,
      data_b64: Buffer.from(bandBytes).toString("base64"),
    },
    fold12: {
      shape: [12, T],
      scale: 1.0,
      data_b64: Buffer.from(foldBytes).toString("base64"),
    },
  },
};

const out = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../../docs/latent-forge/contract/fixtures/handmade-forge_chroma_render.json",
);
writeFileSync(out, `${JSON.stringify(fixture, null, 2)}\n`, "utf8");
console.log(`wrote ${out}: ${T} frames, band scales ${bandScale.join(", ")}`);
```

**No edit to `mock/__tests__/plugin.test.ts` is needed.** M1 T6's fixture-name assertion is, as of
2026-09-22 (WINTERMUTE's fixture-assertion ruling — see this plan's Normative table and Open
questions), a superset check: it asserts that the ten names M1's own shell calls are all present in
the fixture directory, not that the directory is exactly those ten. Adding
`handmade-forge_chroma_render.json` alongside them — regardless of what M10 T7 or anything else has
already added — leaves that assertion exactly as green as it was before. This task therefore just
creates the fixture file below and stops; it does not reach into M1's test the way an earlier draft
of this plan did.

`latent-forge/tests/chroma.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("bottom-tab-chroma").click();
});

test("the CHROMA tab is reachable from the bottom tab row (spec §4.5)", async ({ page }) => {
  await expect(page.locator('[data-region="bottom-tab-body"][data-tab="chroma"]')).toBeVisible();
  await expect(page.locator('[data-region="chroma-tab"]')).toBeVisible();
});

test("the tab body is M1's 162 px and the hint is M1's own (spec §4.5)", async ({ page }) => {
  const box = await page.locator('[data-region="bottom-tab-body"]').boundingBox();
  expect(box).not.toBeNull();
  expect(Math.round(box!.height)).toBe(162);
  await expect(page.getByTestId("bottom-hint")).toHaveText("hover the heatmap to read a frame");
});

test("the heatmap canvas is present and has real size (spec §5.4)", async ({ page }) => {
  const canvas = page.getByTestId("chroma-heatmap");
  await expect(canvas).toBeVisible();
  const box = await canvas.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.width).toBeGreaterThan(200);
  expect(box!.height).toBeGreaterThan(40);
});

test("the detune scan strip is present at its own 500 x 30 (spec §5.4, v3 332)", async ({ page }) => {
  const strip = page.getByTestId("chroma-scan-strip");
  await expect(strip).toBeVisible();
  await expect(strip).toHaveAttribute("width", "500");
  await expect(strip).toHaveAttribute("height", "30");
});

test("the four view buttons and MATCH CURVE are present (spec §5.4)", async ({ page }) => {
  for (const v of ["global", "bass", "mid", "high"]) {
    await expect(page.locator(`[data-chroma-view="${v}"]`)).toBeVisible();
  }
  await expect(page.getByTestId("chroma-curve-toggle")).toBeVisible();
});

test("the legend, its readout and the target row are present (spec §5.4)", async ({ page }) => {
  await expect(page.getByTestId("chroma-legend")).toBeVisible();
  await expect(page.getByTestId("chroma-match-readout")).toBeVisible();
  await expect(page.locator('[data-region="chroma-target-row"]')).toBeVisible();
});
```

- [ ] **Step 2: Run the tests — they must fail**

```bash
cd latent-forge && npx vitest run src/ui/chroma/__tests__/ChromaTab.component.test.ts mock/__tests__/chromaFixture.test.ts
```

Expected: `Failed to resolve import "../ChromaTab.svelte"`; `chromaFixture.test.ts` fails at module
scope with `ENOENT: no such file or directory, open '...handmade-forge_chroma_render.json'`.
`mock/__tests__/plugin.test.ts` is not run here and does not need to be: its fixture-name assertion
is a superset check (WINTERMUTE, 2026-09-22) that only requires M1's own ten names to be present, so
it stays green whether or not `handmade-forge_chroma_render.json` exists yet.

- [ ] **Step 3: Generate the fixture, write the tab, and mount it**

First the fixture, so the mock server has something to serve:

```bash
cd latent-forge && node mock/makeChromaFixture.mjs
```

Expected: `wrote .../handmade-forge_chroma_render.json: 24 frames, band scales <s0>, <s1>, <s2>`.

`latent-forge/src/ui/chroma/ChromaTab.svelte`:

```svelte
<script lang="ts">
  // The CHROMA tab (spec §4.5 -> §5.4), composed from Tasks 6-10 into M1 T11's
  // [data-region="bottom-tab-body"]. The tab's right-aligned hint is M1 T12's
  // (bottomHint("chroma")) and is NOT re-rendered here.
  //
  // WHICH REQUEST LEADS. §5.4 wants chroma computed on the clip's STRETCHED
  // preview, and a detune change re-stretched through /forge/stretch debounced
  // 400 ms. Those are sequential:
  //
  //   setDetune (this tab's strip, or M5 T4's lane-header field)
  //     -> $effect on clip.detune_cents  -> scheduleStretch (M5 T10, 400 ms)
  //     -> clip.previewAudio changes
  //     -> $effect on (previewAudio ?? audio) -> chromaClient.request
  //
  // The chroma effect is keyed on the REF, not on the detune, so nothing ever
  // analyses the pre-stretch audio in between. One debounce, one owner, and it
  // covers the lane header's detune field as well as the strip's.
  //
  // HOW MUCH DETUNE TO ROTATE BY -- decided ONCE, here. runStretch has already
  // pitch-shifted previewAudio by clip.detune_cents / 100 (M5:5358), so when
  // the analysed ref WAS previewAudio the chroma is already detuned and a
  // consumer that rotates it again by the clip's detune applies the detune
  // twice. When the analysed ref was the raw clip.audio -- which happens
  // whenever runStretch returns early, i.e. clip.native_bpm == null -- the
  // detune is NOT in the audio and the rotation is still needed. That is the
  // whole rule, and `analysisDetuneCents` below is the only place it lives:
  // every consumer (heatmap hue, match curve, hover, clip score, detune scan)
  // gets THAT number rather than clip.detune_cents, so nothing re-derives it.
  // Its knock-on effect is that the scan strip's axis is relative and BEST is
  // additive -- see Task 8 and the plan's Open question 6.
  //
  // arrangement.selectedClip is promised by M5 T1's Interfaces line and never
  // defined in its code (M5's own self-review says so), so the selected clip is
  // computed locally from view.selection, exactly as M5 T9 does.
  import { chromaClient } from "../../lib/chroma/chromaClient.svelte";
  import { chromaLink } from "../../lib/chroma/chromaLink.svelte";
  import { meanMatchAtDetune, type ScanCriterion } from "../../lib/chroma/detuneScan";
  import {
    CHROMA_VIEWS,
    type ChromaView,
    type FrameWindow,
    VIEW_LABELS,
    fullWindow,
  } from "../../lib/chroma/heatmapGeometry";
  import { type ChromaHover, readHover } from "../../lib/chroma/hoverReadout";
  import { chromaTarget, laneTargetRefs } from "../../lib/chroma/targetStore.svelte";
  import { scheduleStretch } from "../../lib/clips/lifecycle";
  import type { ForgeApiError } from "../../lib/forge/api";
  import { arrangement } from "../../lib/stores/arrangement.svelte";
  import { view } from "../../lib/stores/view.svelte";
  import ChromaHeatmap from "./ChromaHeatmap.svelte";
  import DetuneScanStrip from "./DetuneScanStrip.svelte";
  import HoverReadout from "./HoverReadout.svelte";
  import MatchCurveOverlay from "./MatchCurveOverlay.svelte";
  import MatchLegend from "./MatchLegend.svelte";
  import TargetRow from "./TargetRow.svelte";

  let chromaView = $state<ChromaView>("global");
  let showCurve = $state(true);
  let criterion = $state<ScanCriterion>("highest");
  let win = $state<FrameWindow>({ from: 0, to: 1 });
  let hover = $state<ChromaHover | null>(null);
  let boxEl = $state<HTMLDivElement>();
  let loggedError: string | null = null;

  const selectedClip = $derived.by(() => {
    const sel = view.selection;
    return sel.kind === "clip" ? arrangement.clips.find((c) => c.id === sel.id) : undefined;
  });
  /** §5.4: the STRETCHED preview, falling back to the source for an unstretched clip. */
  const audioRef = $derived(selectedClip ? (selectedClip.previewAudio ?? selectedClip.audio) : null);
  /**
   * The detune that is NOT already baked into the analysed audio -- 0 when the
   * analysed ref was the stretched preview, the clip's own when it was the raw
   * source. The single decision point; every consumer below takes this.
   */
  const analysisDetuneCents = $derived(
    selectedClip && !selectedClip.previewAudio ? selectedClip.detune_cents : 0,
  );
  const result = $derived(chromaClient.result);
  const target = $derived(chromaTarget.profile);
  const error = $derived(chromaClient.error ?? chromaTarget.error);
  const clipScore = $derived(selectedClip ? (chromaLink.scores[selectedClip.id] ?? null) : null);

  // 1. The analysis follows the REF, so a fresh stretch re-analyses and a bare
  //    detune change does not.
  $effect(() => {
    const ref = audioRef;
    if (!ref) return;
    void chromaClient.request(ref);
  });

  // 2. The window resets whenever a different-length analysis lands.
  $effect(() => {
    const res = result;
    win = res ? fullWindow(res.T) : { from: 0, to: 1 };
  });

  // 3. Detune -> M5 T10's debounced stretch. The ONLY place that arms it.
  $effect(() => {
    const clip = selectedClip;
    if (!clip) return;
    void clip.detune_cents;
    scheduleStretch(clip.id, (e: ForgeApiError) => view.appendLog(`[chroma] stretch: ${e.message}`, "error"));
  });

  // 4. lane-mode target: analyse the TARGET lane's own clips.
  $effect(() => {
    if (chromaTarget.mode !== "lane") return;
    void chromaTarget.loadLane(laneTargetRefs(arrangement.clips, arrangement.targetLane));
  });

  // 5. §5.4's clip score label: the mean frame match over EVERY frame.
  $effect(() => {
    const clip = selectedClip;
    const res = result;
    if (!clip || !res) return;
    chromaLink.setScore(clip.id, meanMatchAtDetune(res.fold12, res.T, target, analysisDetuneCents));
  });

  // 6. §9.7: a server error is a red TERMINAL line as well as an inline one.
  $effect(() => {
    const e = error;
    if (!e || e === loggedError) return;
    loggedError = e;
    view.appendLog(`[chroma] ${e}`, "error");
  });

  function onMove(e: PointerEvent): void {
    const box = boxEl;
    const res = result;
    const clip = selectedClip;
    if (!box || !res || !clip) return;
    const rect = box.getBoundingClientRect();
    const h = readHover({
      result: res,
      target,
      view: chromaView,
      win,
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
      widthPx: rect.width,
      heightPx: rect.height,
      detuneCents: analysisDetuneCents,
    });
    hover = h;
    if (h) chromaLink.setHover(clip.id, h.frac);
    else chromaLink.clearHover();
  }

  function onLeave(): void {
    hover = null;
    chromaLink.clearHover();
  }
</script>

<div class="tab" data-region="chroma-tab">
  <div class="mode-row">
    {#each CHROMA_VIEWS as v (v)}
      <button
        type="button"
        data-chroma-view={v}
        class:on={chromaView === v}
        onclick={() => (chromaView = v)}>{VIEW_LABELS[v]}</button
      >
    {/each}
    <button
      type="button"
      data-testid="chroma-curve-toggle"
      class:on={showCurve}
      onclick={() => (showCurve = !showCurve)}>MATCH CURVE</button
    >
    <MatchLegend target={target} clipScore={clipScore} />
    <div class="spacer"></div>
    <TargetRow />
  </div>

  <div class="body">
    <div class="side">
      <DetuneScanStrip
        clip={selectedClip ?? null}
        result={result}
        target={target}
        criterion={criterion}
        detuneCents={analysisDetuneCents}
        oncriterion={(c) => (criterion = c)}
      />
      <HoverReadout hover={hover} />
      {#if error}
        <p class="state error" data-testid="chroma-error">{error}</p>
      {:else if !selectedClip}
        <p class="state" data-testid="chroma-empty">no clip selected</p>
      {:else if chromaClient.pending}
        <p class="state" data-testid="chroma-empty">computing chroma…</p>
      {/if}
    </div>
    <div
      class="heatmap-box"
      data-region="chroma-heatmap-box"
      bind:this={boxEl}
      onpointermove={onMove}
      onpointerleave={onLeave}
    >
      <ChromaHeatmap
        view={chromaView}
        win={win}
        result={result}
        target={target}
        detuneCents={analysisDetuneCents}
        onwin={(w) => (win = w)}
      />
      {#if showCurve}
        <MatchCurveOverlay
          result={result}
          target={target}
          win={win}
          detuneCents={analysisDetuneCents}
        />
      {/if}
    </div>
  </div>
</div>

<style>
  .tab {
    box-sizing: border-box;
    height: 100%;
    display: flex;
    flex-direction: column;
    min-height: 0;
    border: 1px solid var(--border);
    background: var(--panel);
    overflow: hidden;
  }
  .mode-row {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
    padding: 5px 8px;
    background: var(--panel2);
    border-bottom: 1px solid var(--border);
  }
  .mode-row button {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text);
    font-size: 9px;
    padding: 3px 5px;
    cursor: pointer;
  }
  .mode-row button.on {
    border-color: var(--turq-strong);
    color: var(--turq-strong);
  }
  .spacer {
    flex: 1;
  }
  .body {
    display: flex;
    gap: 8px;
    flex: 1;
    min-height: 0;
    padding: 7px 8px;
  }
  .side {
    width: 250px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
    overflow-y: auto;
  }
  .heatmap-box {
    position: relative;
    display: flex;
    flex: 1;
    min-width: 0;
    min-height: 0;
  }
  .state {
    margin: 0;
    font-size: 10px;
    color: var(--text-dim);
  }
  .state.error {
    color: var(--red);
  }
</style>
```

Modify `latent-forge/src/ui/shell/BottomPane.svelte` (M1 T11): add
`import ChromaTab from "../chroma/ChromaTab.svelte";` to the script block, and inside
`data-region="bottom-tab-body"` replace

```svelte
    {#if tab === "chroma"}
      <!-- body: M6 (spec §5.4) -->
      <div class="tab-empty"></div>
```

with

```svelte
    {#if tab === "chroma"}
      <ChromaTab />
```

Nothing else in `BottomPane.svelte` changes: the `.tab-body` element's own `flex: 0 0 162px` and
`overflow: hidden` (M1 T11) already give `ChromaTab`'s `height: 100%` its 162 px, so the Playwright
height assertion holds without touching M1's sizing rules — the same edit shape M4 T10 made for
`PromptSigmaTab`.

- [ ] **Step 4: Run them, expect pass**

```bash
cd latent-forge && npx vitest run src/ui/chroma/__tests__/ChromaTab.component.test.ts && npx vitest run mock && npm run check
```

Expected: `Test Files  1 passed (1)` / `Tests  12 passed (12)` for the tab, then
`Test Files  3 passed (3)` / `Tests  28 passed (28)` for `mock` — M1 T6's own 24 over two files
(unchanged in count: its fixture-name assertion is a superset check as of WINTERMUTE's 2026-09-22
ruling, and this task does not touch it) plus this task's 4 in `chromaFixture.test.ts`. Then
`svelte-check found 0 errors and 0 warnings`.

The whole chroma milestone together, for the record:

```bash
cd latent-forge && npx vitest run src/lib/chroma src/ui/chroma
```

Expected: `Test Files  20 passed (20)` / `Tests  201 passed (201)`.
*Counting note for whoever verifies this plan mechanically:* a raw grep for indented `it(` blocks
over this task's section returns exactly **16** — 12 in `ChromaTab.component.test.ts` and 4 in
`chromaFixture.test.ts` — with no before/after double-count to explain away, because this task no
longer edits `mock/__tests__/plugin.test.ts` at all (WINTERMUTE's 2026-09-22 fixture-assertion
ruling; see the Normative table and Open questions).

`src/lib/chroma` is 12 files / 144 tests — Writer A's 64 (`bins` 13, `chromaClient` 11, `match` 13,
`target` 14, `detuneScan` 13) plus 80 here (`consonanceColor` 8, `heatmapGeometry` 19, `matchCurve`
11, `scanStrip` 12, `targetStore` 14, `hoverReadout` 9, `chromaLink` 7). `src/ui/chroma` is 8 files
/ 57 tests (`chromaCanvas` 4, `ChromaHeatmap` 8, `MatchCurveOverlay` 4, `MatchLegend` 6,
`DetuneScanStrip` 10, `TargetRow` 9, `HoverReadout` 4, `ChromaTab` 12). Task 10's remaining 3
(`ClipBox.score.component.test.ts`) live under `src/ui/timeline` and are not in this run.

Then the Playwright spec, against the mock server:

```bash
cd latent-forge && npx playwright test tests/chroma.spec.ts
```

Expected: `6 passed`.

- [ ] **Step 5: Commit**

```bash
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M6 T11: CHROMA tab assembled into M1's 162px tab body, stretch-leads-chroma detune chain on M5 T10's 400ms debounce, handmade-forge_chroma_render fixture (no M1 edit needed -- its assertion is a superset check), Playwright spec"
```

- [ ] **Step 6: Self-review**

| Requirement | Where | State |
|---|---|---|
| §5.4 bin geometry: C at 2.0, 128/12 per semitone, labels from `semitone_bin_centers` | T1 `bins.ts`, T6 `rowPitchClass`/`rowCents` | done |
| §5.4 views: GLOBAL = the fold per-frame normalised; BASS/MID/HIGH = raw 128 bins of band 0/1/2 | T6 `cellValue`, `VIEW_LABELS` | done |
| §5.4 `MATCH CURVE` toggles the overlay canvas | T7 overlay, T11 `showCurve` | done |
| §5.4 target, lane mode: TARGET lane's folds summed and max-normalised | T4 `targetProfile`, T9 `loadLane` | done |
| §5.4 target, SEMITONE SET: 12 toggles + chord field over nine qualities and twelve roots | T4 `parseChord`, T9 `TargetRow` | done |
| §5.4 match: `INTERVAL_W`, classes counted only above 0.08 | T3 `matchFrame` | done |
| §5.4 detune rotation: `cents/100` classes, linear energy split | T3 `rotate` | done |
| §5.4 legend anchors: unison / fifth / tritone of the target against itself | T3 `anchors`, T7 `legendTicks` | done |
| §5.4 clip score label = mean frame match at the clip's detune | T5 `meanMatchAtDetune`, T10 `clipScoreLabel`, T11 effect 5 — at `analysisDetuneCents`, because the analysed preview already carries the detune | done |
| §5.4 scan: −100..100 step 4, every 3rd frame, HIGHEST = mean, STEADIEST = mean − sd | T5 `scanDetune`/`bestDetune`, T8 strip | done |
| §5.4 strip: red mark at the current detune; click or drag sets it; BEST jumps to the argmax | T8 — on a **relative** axis: the mark is the strip's centre, and both writers add rather than assign | done |
| §5.4 detune re-stretches through `/forge/stretch`, debounced 400 ms | T11 effect 3, via M5 T10's `scheduleStretch` | done |
| §5.4 hover: note name + frame index, 14 px / 9 px, red line on the clip in its lane | T10 `HoverReadout`, `chromaLink`, `LaneCanvas` edit | done |
| §6.3 `[3,128,T]` with **three** band scales, `[12,T]` with **one**, `byte/255·scale` | T2 `decodeChroma` (M10 T1's `dequantiseScaled`) | done |
| §6.3 `fps` 10.7666015625 | T2 `ChromaResult.fps`, fixture | done |
| §6.3 computed on the clip's stretched preview | T11 `previewAudio ?? audio` | done |
| §9.7 server error → red TERMINAL line + a one-line inline message | T11 effect 6, `[data-testid="chroma-error"]` | done |
| §4.5 tab body 162 px, hint already M1's | T11 BottomPane edit, Playwright | done |
| §4.3 clip box score label | T10 `ClipBox` edit | partial — see below |
| Detune enters the commit as **semitones** (§8.1 S2) | — | not this milestone: M8 reads `detune_cents / 100`, as M5 T10's stretch already does |

**Known incomplete.**

1. **Only analysed clips get a real score label.** §4.3 puts a chroma-match score on every clip box;
   §5.4 defines it as needing that clip's own chroma, i.e. one `/forge/chroma` round trip each. This
   milestone fills the label for the clips it already analyses — the selected one and the TARGET
   lane's — and leaves M5's `SCORE_PLACEHOLDER` on the rest. Filling every box needs a background
   analysis pass that nothing in M1–M6 owns.
2. **The lane's red hover marker is not unit-tested at the canvas.** The seam (`chromaLink`,
   `markerSecFor`) is pinned, and M5 T5's own rule — "canvas drawing itself is not unit-tested, jsdom
   has no `CanvasRenderingContext2D`" — applies to the nine lines added to `LaneCanvas.redraw()`.
   Worth one Playwright check once a clip can be dropped from a fixture.
3. **`CHROMA CROSSFADE` on an overlap is M7's, and the commit-time chroma slot is server-side.**
   §4.6's toggle (`HELP.overlapChromaXfade`, v3 460) and §8.1's stage are deliberately untouched
   here.
4. **Lane-mode target cost.** One `/forge/chroma` per TARGET-lane clip, sequentially, on every change
   to that lane's clip list. The per-`AudioRef` cache inside the target store's own `ChromaClient`
   means it is paid once per ref, but a four-clip target lane is four round trips before the legend
   can draw its anchors.
5. **The heatmap's y-axis has no note labels yet.** §5.4 says "the y-axis note labels come from
   `semitone_bin_centers`"; `rowPitchClass` + `NOTE_NAMES` give them, and the hover readout uses
   them, but no label column is drawn beside the 128-row views. Cheap to add; left out rather than
   guessed at, because at 162 px there is no room for twelve labels and the drawing draws none.
6. **`consonanceColor`'s two hues are a design choice, not a spec number.** §5.4 requires a
   consonance colouring and names no hues; T6 ships the drawing's 60/260, so changing them is two
   constants and no test shape (every colour test derives its expectation from the constants).


---

## Critic pass (2026-09-22)

One agent, read-only, against the sources listed in this plan's header. **2 findings, 0 blocking,
1 unconfirmed** — the lightest of any milestone's pass so far (prior rounds: 17, 32, 49, 6). Every
INTERVAL_W/rotate/anchor/detune-scan number was hand-recomputed rather than trusted, every v3 line
citation was checked against the actual handoff file, every data-*/HELP id was checked in both
directions against the Normative table, and the API restatements were checked against M1/M5/M10's
declaring tasks. All held except the two below, both now fixed in this plan.

1. **NON-BLOCKING, fixed.** The header's "Spec:" line cited §4.6 for the bottom-pane frame; §4.5 is
   the section that actually defines the 248 px bottom pane and lists CHROMA under it (§4.6 is the
   unrelated right-pane accordion). Every task-body citation elsewhere in this plan already said
   §4.5 correctly — this was an isolated slip in the header. Fixed above.
2. **NON-BLOCKING, fixed.** Task 6's middle-drag zoom/scroll compounded each pointermove's delta onto
   the *already-clamped* `win` prop from the previous move, rather than recomputing an absolute
   target from the window the drag started with — the convention M5 T3's own comment establishes
   ("middleDragZoomFactor is relative to the START of the drag, not the previous event") and which
   this task's own docstring claimed to replicate but did not. Once a drag pushes the window to
   `MIN_VISIBLE_FRAMES` or the full-clip bound and the pointer reverses, compounding does not unwind
   symmetrically the way start-anchored recomputation does — the gesture silently stops being
   reversible. Not visible in the single-pointermove test that existed. **Fixed**: `drag` now stores
   `startWin` (the window at drag start) alongside the start pointer position, and every move
   recomputes `zoomWindow`/`scrollWindow` from `startWin` using the *total* delta since drag start,
   never from the current `win` prop. A new test drags out then reverses to the exact start point and
   asserts the reported window is exactly the start window — something the compounding version would
   not generally guarantee once a clamp had fired in between. Task 6's gate moved 37 → **38**; the
   header table, the 211 → 212 total, and the tail's combined-run count (202 → 203) are all updated
   to match.

**One item flagged but not treated as a finding:** `hoverReadout.ts`'s `hoverNoteText` uses
`h.cents ? … : ""`, which is falsy for `cents === 0` — a real, reachable case (bin 2 in a band view
is exactly a class centre). No test exercises a genuine `cents === 0` from `readHover`, so whether
omitting "+0¢" is intended or accidental could not be confirmed either way; it reads as a defensible
UX choice and is left as written. Worth a look if it ever comes up during implementation.

**A single clean pass should not have been trusted, and was not — a second one ran.** The first
pass's "2 findings, 0 blocking" was correct as far as it went, but no critic pass on this project had
ever come back that clean before (prior rounds: 17, 32, 49, 6), and the person who applied it moved
the plan to "done" and committed on that single result. A second, independent pass over the same file
returned **17 findings, 5 of them blocking**, every number verified in node before being applied.
**The lesson, stated once so it isn't relearned:** a suspiciously clean result is itself a reason to
run another pass, not a reason to stop.

The five blocking findings, all fixed in the task bodies above:

- **B1.** `matchFrame`'s threshold guard compared a `Float32Array` value against the float64 literal
  `0.08` directly. `Math.fround(0.08) = 0.0799999982… < 0.08`, so a class sitting at exactly the
  threshold was silently **excluded** — the opposite of the documented rule, and the test asserting
  `0.18` for a rotated single-class target could never have passed as written. Fixed with a
  `THRESHOLD_F32 = Math.fround(MATCH_THRESHOLD)` constant, compared against instead.
- **B2.** The "steadiest" scan fixture originally scored `[0.5, 0.4, 0.5, 0.2]` — a tie between
  indices 0 and 2 under first-wins-a-tie, returning `-8` — while the test's own title claimed "first
  wins a tie" and its comment picked the *last*. Fixture reshaped so the tie resolves unambiguously.
- **B3.** An assertion expected `consonanceColor(1, 1)` where the fixture's actual match value was
  `(W[0]+W[4]+W[7])/3 = 0.8667` under the formula then in force — corrected to match what the code
  actually computes rather than a guessed round number.
- **B4.** BEST did not land on +100 cents as claimed: the 0.08 threshold flattens the top of the scan
  curve, so several points score exactly 1.0 and first-wins-a-tie picks the lowest of them, not the
  requested one. **B1 and B4 are coupled**, and the critic that found them individually did not
  notice: against the float64 threshold the flat top starts at cents = 92; once B1's `Math.fround`
  fix lands, class 0 survives to 92 as well and the first *tied* point moves to 96. Applying either
  fix alone leaves the other test red — both branches were computed by hand and the coupling is
  written into both places, so a future edit to one cannot silently break the other without a test
  saying why.
- **B5. Detune was being applied twice.** M5 T10's `runStretch` already pitch-shifts a clip's preview
  audio by `clip.detune_cents / 100` before this milestone ever sees it, and this plan pins chroma
  analysis to that stretched preview — but every consumer (heatmap hue, match curve, hover, scan, the
  §5.4 clip score) then rotated the *already-shifted* chroma by the same detune again, corrupting all
  five. No test caught it because none set a `previewAudio` **and** a non-zero `detune_cents`
  together — each half was individually correct, which is exactly the shape of bug that ships. Fixed
  by deriving `analysisDetuneCents` once, centrally, in `ChromaTab.svelte`: `0` when the analysed ref
  was the stretched preview, the clip's own detune when it was the raw source (`runStretch` returns
  early without a `native_bpm`, and in that one case the rotation really is correct as originally
  written) — then threading that single value to every consumer instead of letting each one read
  `clip.detune_cents` for itself. As a consequence the scan strip's axis became **relative** to the
  clip's current detune rather than absolute, and BEST became **additive and clamped** rather than
  assigning, so pressing it twice converges instead of walking the value indefinitely. Sixteen call
  sites changed, seventeen tests added or rewritten.

Non-blocking, all applied: four exact fold ties rather than two (bins 18, 50, 82 **and** 114 — the
midpoint is an integer whenever 3 divides `2s+1`, not just at the two the plan first claimed); the
fold open question's stated consequence was backwards (a quiet frame renders **bright** and scores
exactly 0 under the two-array reading then in force, not "looks quiet, scores high" as first
written); a stale `plugin.test.ts` anchor rewritten as a rule rather than a literal name so M6 and
M10 can land in either order (superseded again by WINTERMUTE's superset-check answer, below);
`HELP.clipDetune` lives on M5's lane header, not the clip box; `cents === 0` was treated as falsy
(the item logged above as unconfirmed); five v3 line citations off by one or two; the canvas token
fallback table did not match M1's real token names; `cellValue` re-folded 384 bins twelve times per
frame where once would do (superseded again by WINTERMUTE's single-fold answer, below); and Task
11's Interfaces block omitted eight members its own tests called. Two unconfirmed items from the
first pass were hardened rather than left as guesses: asserting the raw `style` attribute instead of
`.style.background` (jsdom's `cssstyle` may not parse `oklch()`), and `await tick()` in place of
`await Promise.resolve()` for Svelte 5 effects.

## Open questions

**Every one has a shipped reading, so nothing here blocks an implementer.** The six below are the
load-bearing ones — they want Kim's or WINTERMUTE's answer rather than a default, because changing
any of them later changes numbers the app has already shown someone. Items 1 and 2 have since been
answered by WINTERMUTE (2026-09-22) and are kept in their numbered slots as a record, not deleted, so
a reader following a cross-reference to "Open question 1" or "2" from elsewhere in this plan still
finds something at that number. The rest are recorded in full underneath, as each writer found them.

1. **RESOLVED 2026-09-22 by WINTERMUTE.** `INTERVAL_W` stays indexed by the **directed, wrapped**
   class distance, `((a - b) % 12 + 12) % 12` with `a` the frame's class and `b` the target's — not
   `Math.abs(a - b)`, which silently read the wrong entry for about half of all pairs, and not folded
   to interval class either. See the Normative table's `INTERVAL_W`'s index row for the full
   reasoning and WINTERMUTE's fifth-vs-fourth example; Task 3's `match.ts` carries the same reasoning
   in its own comment so the asymmetry does not get "corrected" later.
2. **RESOLVED 2026-09-22 by WINTERMUTE.** There is one 12-class fold, not two: §5.4's GLOBAL display
   and §6.3's transported `fold12` are the same array, because the server already computes and ships
   fold12 per-frame-normalised to max 1 (M2 T12's `chroma_payload`, `scale: 1.0`). `foldFrameTo12` is
   deleted (Task 1); GLOBAL's cells, the hover value, the match score, the scan and the clip score all
   read `fold12Column`. See the Normative table's "which 12-class fold feeds what" row for
   WINTERMUTE's stated consequence (a quiet frame counts exactly as much as a loud one, which is
   intended).
3. **Chord quality is lowercased, so `CM7` reads as C minor 7.** That is the drawing's behaviour and
   it is what makes `CDIM` work, but many charts mean C major 7 by `CM7`. The alternative is to match
   §5.4's nine spellings case-sensitively and reject `CM7` outright.
4. **Nine controls ship with no `data-help`**, because M1 T14's `KEYS` has no id for them: the four
   view buttons, MATCH CURVE, the two TARGET-mode buttons, the twelve piano keys, and the hover
   readout. M10 shipped nine bare for the same reason. **A single follow-up to M1 T14 should add ids
   for both milestones' eighteen in one pass**, rather than each milestone inventing its own.
5. **The heatmap's y-axis note labels are not drawn**, although §5.4 says they "use
   `semitone_bin_centers`". The data exists and the hover readout names the note; at 162 px of tab
   body the drawing itself draws none, and guessing a layout for twelve labels would be inventing UI.
6. **Detune was applied twice, and the fix makes the scan strip's axis relative.** Found by the
   **2026-09-22 critic pass**, blocking. M5 T10's `runStretch` already stretches the clip's preview
   by `clip.detune_cents / 100` (M5:5358), and this plan pins chroma to that stretched preview — so
   `chromaClient.result.fold12` is the chroma of audio that has *already* been pitch-shifted, and
   every consumer rotating it again by `detune_cents / 100` applied the detune a second time. (v3
   did not have the bug: its scan and its chroma both started from the unstretched source. The
   rotation was, however, still correct in the one case where `runStretch` returns early —
   `clip.native_bpm == null`, leaving `previewAudio` null.) **Shipped reading: the analysed ref
   decides.** `ChromaTab.svelte` derives `analysisDetuneCents` — `0` when the analysed ref was
   `clip.previewAudio`, `clip.detune_cents` when it was `clip.audio` — and passes that to every
   consumer in place of `clip.detune_cents`, so one place decides and nothing re-derives the rule.
   The consequence is that **the scan strip's ±100 ¢ axis becomes relative to the clip's current
   detune**: the red mark sits at the strip's centre, the label says what the axis is relative to,
   and **BEST is additive** (`clip.detune_cents + bestDetune(...)`, clamped), which is also what
   makes pressing BEST twice converge rather than walk the value. **The relative-axis reading was
   chosen over the alternative** — re-requesting chroma on the *unstretched* source so the axis
   could stay absolute — because it is one fewer server round-trip, and because the scan re-centres
   after each BEST as the new stretch lands, so repeated presses converge. **Kim or WINTERMUTE may
   prefer the other reading**: an absolute axis reads more naturally beside the lane header's
   DETUNE ¢ field, at the price of a second `/forge/chroma` per clip and a scan that no longer
   describes the audio the timeline actually plays.

**Two defects in other plans, found while writing this one, both already fixed:**

- **M10 Task 7 created two handmade fixtures without extending M1 T6's exact-name assertion** — that
  suite compared a sorted `readdirSync` listing to a literal array, so a new fixture was a failure
  rather than an addition, and M10 would have turned M1 T6 red on landing. Patched once, per
  milestone, earlier on 2026-09-22: M10 T7 modified `mock/__tests__/plugin.test.ts` itself, in the
  same commit, writing out a twelve-name list — the same shape of edit this plan's own Task 11 made
  for the chroma fixture, each widening the list the other had left.
  **Superseded, same day, by WINTERMUTE's fixture-assertion ruling** (see Task 11's fixture-list
  edit below, and M1 T6's own test). The root problem was the assertion itself, not any one
  milestone's fixture: M1 T6's list is now a
  superset check (`expect(names).toEqual(expect.arrayContaining([...]))`) done once in M1, so a
  fixture landing in M10, M6 or anywhere after needs no edit to M1's test at all. M10 T7's edit to
  `plugin.test.ts` is reverted and Task 11 below no longer touches that file either — both plans just
  ship their own fixture file and say so.
- **The writer brief's v3 line number for the middle-drag hint was wrong** — it cited 341; the string
  is at **v3 331**, and 341 closes the hover readout. Every other v3 number in the brief was checked
  and holds.

Also worth knowing before an implementer starts: **`arrangement.selectedClip` is promised by M5 T1's
Interfaces line and never defined in its Step 3 code** (M5's own self-review flags it). Task 11 uses
M5 T9's workaround — computing the selected clip from `view.selection` — rather than depending on a
name that may not exist. If M5's committed code turns out to have it, Task 11 simplifies to one line
and nothing else in M6 changes.

And: **M1 T13's `panelColour` has no per-token fallback**, so `ctx.fillStyle = ""` can silently leave
the previous colour there. M10's canvases use it. This milestone ships its own `chromaColour()` in
`src/ui/chroma/chromaCanvas.ts` with a fallback table rather than editing frozen M1. Two
near-identical helpers now exist; merging them is a one-task follow-up, not M6's call.

*Line numbers cited as `M1:nnnn` in the two lists below were taken before WINTERMUTE's `7193ba9`
shifted M1's body. The fixture-name assertion the writers cite as M1:1623-1634 and M1:1668-1680 is at
**M1:1666-1677** in the current file; verify any M1 line reference against the file rather than
against this plan.*

### Writer A — Tasks 1-5, in full

- **`INTERVAL_W`'s index is the raw class distance, not the interval class** — v3 925–937 computes
  `ic = |a-b| % 12` and then indexes `INTERVAL_W[min(ic, 12-ic) === 0 ? 0 : ic]`, which collapses to
  `INTERVAL_W[|a-b|]`: a minor second up (index 1, 0.10) and a major seventh (index 11, 0.22) are
  weighted differently although both are interval class 1, and the table's own second half (0.66,
  0.72, 0.30, 0.22) only ever reads as "inverted" intervals. §5.4 pins the twelve weights and names
  `_matchFrame` as the definition but does not restate the indexing. — Shipped the drawing's raw
  distance, with the equivalence spelled out in a comment so nobody "fixes" it into
  `min(ic, 12-ic)`, which would silently change every score in the app.
  **RESOLVED 2026-09-22 by WINTERMUTE: "raw distance" is not enough on its own — `|a-b|` is
  symmetric, so it depended on which of the two class numbers was larger rather than on a
  consistent target→frame direction, and read the wrong table entry for about half of all pairs
  (target G, frame C: `|7-0|=7` reads the fifth's 0.90, when the ascending distance from G to C is
  5 semitones, the fourth's 0.82).** Task 3 now indexes by the DIRECTED distance
  `((a - b) % 12 + 12) % 12` instead, keeping the table itself unfolded exactly as shipped here —
  every hardcoded expectation in Tasks 3, 5 and 6 that this changed was hand-recomputed against the
  corrected formula (see the Normative table's `INTERVAL_W`'s index row).
- **The wrap boundary at the top of the band** — the brief says "a bin past 128 − (128/12)/2"
  (= 122.67) belongs to C again; the server's own `fold_to_12` assigns each bin to the nearest
  centre by *circular* distance, which puts the B/C boundary at 2.0 + 11.5·(128/12) = **124.67**
  (bin 124 is B, bin 125 is C). — Shipped the server's rule, since client and server must fold
  identically, and pinned 124/125 in a test. Bins 18, 50, 82 and 114 (four, not two — corrected by
  the 2026-09-22 critic) are exact ties and go to the *lower*
  class, matching numpy's `argmin`; `Math.round((bin−2)/(128/12))` sends both the other way, so the
  one-line formula is not usable.
- **Which 12-class fold feeds the match** — §5.4 defines GLOBAL as the three bands folded locally
  and per-frame normalised, while §6.3 also transports a precomputed `fold12` with a single scale
  for the whole clip. They are not the same array: the transported fold is quantised once over the
  clip, so quiet frames keep less resolution, and it is not per-frame normalised. §5.4 does not say
  which one the match, the scan and the clip score read. — Shipped GLOBAL's *display* from
  `foldFrameTo12(bands, …)` (§5.4's words) and the *match* path from the transported `fold12`
  (§6.3 ships it for exactly this, and 51 × T rotations on a locally folded array would be the
  pane's slowest path). If Kim wants the two identical, the match path should fold the bands too.
  **RESOLVED 2026-09-22 by WINTERMUTE: they were never two arrays to begin with.** §6.3's `fold12`
  scale of `1.0` is not "one scale for the whole clip" — it is `1.0` because the server already
  per-frame-normalises to max 1 before quantising, i.e. it computes exactly what §5.4's GLOBAL
  definition asks for and transports it. `foldFrameTo12` is deleted (Task 1); `cellValue` and
  `frameColumn`'s GLOBAL branches now read `fold12Column(result.fold12, …)`, the same array the
  match, scan and clip score already used. See the Normative table's "which 12-class fold feeds
  what" row for WINTERMUTE's one stated consequence of this being the reading.
- **Chord aliases the drawing accepts and the spec does not** — v3 2061 matches
  `maj7|min7|m7|maj|min|m|dim|aug|7`: it has `min`, `min7` and `maj` but **no `sus2`/`sus4`**. §5.4
  lists nine: `C, Cm, C7, Cmaj7, Cm7, Cdim, Caug, Csus2, Csus4`. — Shipped the spec's nine exactly;
  `Cmin` now returns `null`. Trivial to add the three aliases if Kim types them.
- **Chord quality case** — v3 lowercases the quality, so `CM7` parses as C **minor** 7 even though
  many charts mean C major 7 by it. — Shipped the drawing's lowercasing (it is what makes `CDIM`
  work) and pinned the `CM7` reading in a test, but this is a real ambiguity: the alternative is to
  match the nine spellings case-sensitively and reject `CM7`.
- **Enharmonic roots the drawing cannot parse** — v3 resolves a sharp root by
  `NOTES.indexOf(letter + "#")`, which is −1 for `E#` and `B#` (they are not in a sharp-spelling
  table), producing a garbage root. — Shipped letter-semitone + accidental arithmetic instead, so
  `E#` is `F`, `Cb` is `B` and `B#m7` is `Cm7`. Pure data-layer correction; the drawing is
  explicitly low-fidelity for data.
- **Five names the brief did not list** — `fold12Column` / `fold12Columns` (Task 1, the `[12,T]`
  C-order accessor Tasks 4's caller and Task 5 both need — written once so two tasks cannot disagree
  about which axis is fastest), `meanMatchAtDetune` (Task 5, §5.4's clip score label over *every*
  frame, deliberately un-strided where the scan strides), `chromaRefKey` and `ChromaShapeError`
  (Task 2, the cache key and the contract-violation error, parallel to M10 T1's `XcorrShapeError`).
  The brief's `targetProfile(frames, …)` resolved to a single `readonly Float32Array[]` argument.
- **The mock server has no chroma fixture** — M1 T6 routes `POST /forge/chroma` to fixture
  `forge_chroma_render` (M1:1550, 1982–1983), but M1 T6's own fixture test asserts the handmade set
  is **exactly ten files** (M1:1623–1634) and none of them is chroma. M10 hit the same thing on both
  of its routes and had to add them. Tasks 1–5 do not need it — every test here stubs `fetch` or is
  pure — but **Writer B's Task 11 must add `handmade-forge_chroma_render.json`**, or the mock-server
  suite goes red the moment the fixture lands.
  **RESOLVED 2026-09-22 by WINTERMUTE: M1 T6's assertion is now a superset check** (`ships at least
  the ten fixtures M1's own shell calls`), done once in M1, so Task 11 below adds its fixture file
  and needs no edit to `plugin.test.ts` at all — the "and extend M1 T6's ten-file assertion" half of
  this finding no longer applies.

### Writer B — Tasks 6-11, in full

- **The TARGET lane is not a `ForgeLane` flag** — the brief's inherited-names block says "a lane
  carries the chroma TARGET flag (M5's `ForgeLane`, spec §4.3 header row 3; `null` = none chosen)",
  but M1 T3's `ForgeLane` is `{index, name, muted, solo, gain, chain}` with no such field
  (M1:535-542), and M5 T1 puts it on the store as `targetLane = $state<0|1|2|3|null>(null)`
  (M5:352), written by `setTargetLane` (M5:546) and read by M5 T4's lane header as
  `arrangement.targetLane === lane.index` (M5:2548). — **Shipped the source's reading**:
  `arrangement.targetLane`. The brief's line should be corrected in the assembled plan's
  Normative-names block.
- **The brief's v3 line number for the middle-drag hint is wrong** — it cites line 341 for
  `middle-drag: ↕ zoom · ↔ scroll`; that string is at **v3 331**, and 341 is the `</div>` closing the
  hover readout. Every other v3 number the brief gives was checked and holds: mode buttons 288,
  legend 292, target-mode buttons 312-313, piano keys 320, chord field 323, match readout 330, scan
  canvas 332, criterion 335, BEST 336, hover readout 338, heatmap 344, curve 346, CONSONANCE COLOUR
  always-on 729, and M1 T14's `KEYS` entries for all eight chroma ids plus `laneTarget`/`clipDetune`
  (M1:7679-7694).
- **`arrangement.selectedClip` is promised by M5 T1 and never built** — M5 T1's Interfaces line lists
  it as a derived field (M5:71), its Step 3 `ArrangementStore` never defines it, and M5's own
  self-review flags this (M5:5996-6002); M5 T9 works around it by computing the selected clip from
  `view.selection` (M5:4738-4741). — **Shipped M5 T9's workaround** in Task 11 rather than depending
  on a name that may not exist. If M5's committed code turns out to have it, Task 11 can be
  simplified to one line; nothing else in M6 changes.
- **M10 Task 7 adds two fixtures without extending M1 T6's ten-name assertion** — M10 T7 creates
  `handmade-forge_stats_crops.json` and `handmade-forge_dataset_scalars.json` (M10:2655-2656) but
  does not modify `mock/__tests__/plugin.test.ts`, whose `ships the ten fixtures` test asserts the
  directory listing by exact name (M1:1668-1680). M6 depends on M10 T1, so M10 will usually have
  landed first, and that assertion will already be red before M6 touches it. — **Shipped both lists
  in Task 11** (the eleven-name one, and the thirteen-name one to use if M10's two are on disk) with
  a one-command check. Worth a one-line fix in M10 T7 rather than carrying it here.
  **RESOLVED 2026-09-22 by WINTERMUTE: fixed at the root instead of per-milestone.** M1 T6's
  assertion is now a superset check, so no milestone that adds a fixture needs to touch it, and
  the eleven/thirteen-name branching above is gone — Task 11 just ships its own fixture file.
  M10 T7's own edit to `plugin.test.ts` is reverted for the same reason.
- **M1 T13's `panelColour` has no per-token fallback** — `getComputedStyle(canvas).getPropertyValue(token).trim()`
  returns `""` for an undefined token (M1:6918-6920), and `ctx.fillStyle = ""` is the silent no-op
  HANDOUT.md documents. M10's canvases use it. — **Shipped a separate `chromaColour()` in
  `src/ui/chroma/chromaCanvas.ts`** with a fallback table rather than editing M1, since M1 is frozen.
  Two near-identical helpers now exist; merging them is a one-task follow-up, not M6's call.
- **Which fold feeds the display versus the match — inherited from Writer A, and Tasks 6-11 follow
  it** — Writer A ships GLOBAL's *display* from `foldFrameTo12(bands, …)` (§5.4's own words,
  per-frame normalised) and the *match* path from §6.3's transported `fold12` (quantised once over
  the clip, not per-frame normalised). Task 6's `cellValue` and Task 10's `readHover().value` use the
  first; Task 6's per-frame `matchFrame`, Task 7's curve, Task 8's scan and Task 11's clip score all
  use the second. The consequence a reviewer should know: **a GLOBAL cell's colour and its hue come
  from two different arrays**, so a frame can look quiet and still score high. Consistent with A, and
  restated here because it is invisible at a glance.
  **RESOLVED 2026-09-22 by WINTERMUTE: there was only ever one array.** `foldFrameTo12` is deleted;
  Task 6's `cellValue` and `frameColumn`, and Task 10's `readHover().value`, now read
  `fold12Column(result.fold12, …)` — the same transported array Task 6's `matchFrame`, Task 7's
  curve, Task 8's scan and Task 11's clip score already used. A GLOBAL cell's colour and its hue
  come from the same array now; see the Normative table's "which 12-class fold feeds what" row for
  the one consequence worth keeping in mind (a quiet frame counts as much as a loud one in the
  scores, which is intended).
- **No `data-help` on nine controls, because M1 T14 has no id for them** — the four view buttons
  (v3 288), MATCH CURVE (the fifth button in the same row, v3 2016), the two TARGET-mode buttons
  (v3 312-313), the twelve piano keys (v3 320) and the hover readout (v3 338) all ship bare, as the
  brief instructs and as M10 did for nine of its own. A follow-up to M1 T14 should add ids for the
  full set in one pass — this milestone's nine plus M10's nine.
- **The clip score label is filled only for analysed clips** — §4.3 puts a score on every clip box;
  §5.4's definition needs one `/forge/chroma` per clip. M6 fills the selected clip's and leaves M5's
  `SCORE_PLACEHOLDER` on the rest (Task 10). A background pass that scores every clip belongs to
  whichever milestone owns project-wide analysis; nothing in M1–M6 does.
- **`v3`'s hover derives the pitch class as `(row / 128) * 12`** (v3 1955-1957), which assumes C at
  bin 0 and so names the wrong note near every class boundary. — **Shipped Task 1's
  `binToPitchClass`** instead (Task 6's `rowPitchClass`/`rowCents`), matching the server's own
  `fold_to_12`. The drawing is explicitly low-fidelity for data.
- **Heatmap y-axis note labels are not drawn** — §5.4 says "the y-axis note labels use
  `semitone_bin_centers`". The data is there (`rowPitchClass` + `NOTE_NAMES`) and the hover readout
  names the note, but no label column is rendered: at 162 px of tab body the drawing itself draws
  none, and guessing a layout for twelve labels would be inventing UI. Flagged rather than shipped.
- **Names chosen here that the brief did not pre-name** (for the assembler's Normative-names block):
  from `src/lib/chroma/` — `consonanceColor.ts` (`CONSONANT_HUE`, `DISSONANT_HUE`, `CELL_L_TOP`,
  `CELL_L_SPAN`, `CELL_C_BASE`, `CELL_C_SPAN`, `TARGET_ROW_HUE`, `TARGET_L_TOP`, `TARGET_L_SPAN`,
  `TARGET_C_BASE`, `TARGET_C_SPAN`, `LEGEND_L`, `LEGEND_C`, `LEGEND_STOPS`, `consonanceHue`,
  `consonanceColor`, `targetRowColor`, `legendColor`); `heatmapGeometry.ts` (`REF_ROW_H`, `REF_GAP`,
  `BODY_Y`, `MIN_VISIBLE_FRAMES`, `CELL_FLOOR`, `ChromaView`, `CHROMA_VIEWS`, `VIEW_LABELS`,
  `bandIndexFor`, `rowCount`, `FrameWindow`, `fullWindow`, `clampWindow`, `zoomWindow`,
  `scrollWindow`, `frameToX`, `xToFrame`, `rowHeight`, `rowToY`, `yToRow`, `rowPitchClass`,
  `rowCents`, `cellValue`); `matchCurve.ts` (`CURVE_TOP_PX`, `CURVE_BOTTOM_PAD_PX`, `CURVE_SPAN_MIN`,
  `CURVE_PAD_LO`, `CURVE_PAD_HI`, `CONSONANCE_SCALE_LABEL`, `ANCHOR_COLORS`, `CurveAxis`,
  `curveAxis`, `curveY`, `windowScores`, `LegendTick`, `legendTicks`, `matchVerdict`);
  `scanStrip.ts` (`SCAN_W`, `SCAN_H`, `SCAN_GRID_CENTS`, `SCAN_RANGE_FLOOR`, `criterionValues`,
  `criterionLabel`, `nextCriterion`, `centsAtX`, `xForCents`, `ScanRange`, `scanRange`, `scanY`,
  `nearestScanIndex`, `scanLabel`); `targetStore.svelte.ts` (`NO_TARGET_LANE_LABEL`,
  `EMPTY_KEYS_LABEL`, `laneTargetLabel`, `keysLabel`, `laneTargetRefs`, `ChromaTargetStore`,
  `chromaTarget`); `hoverReadout.ts` (`HOVER_NOTE_PX`, `HOVER_DETAIL_PX`, `ChromaHover`, `HoverArgs`,
  `readHover`, `hoverNoteText`, `hoverDetailText`); `chromaLink.svelte.ts` (`ChromaLink`,
  `chromaLink`, `clipScoreLabel`, `markerSecFor`). From `src/ui/chroma/` — `chromaCanvas.ts`
  (`CHROMA_TOKEN_FALLBACK`, `chromaColour`, `fitChromaCanvas`) and the components `ChromaHeatmap`,
  `MatchCurveOverlay`, `MatchLegend`, `DetuneScanStrip`, `TargetRow`, `HoverReadout`, `ChromaTab`.
  From `mock/` — `makeChromaFixture.mjs`.
- **The `data-*` / `data-testid` / `HELP` contract Tasks 6-11 emit**, for the assembler's table:

  | selector | owner | `HELP` id |
  |---|---|---|
  | `[data-region="chroma-tab"]` | T11 | — |
  | `[data-region="chroma-heatmap-box"]` | T11 | — |
  | `[data-region="chroma-target-row"]` | T9 | — |
  | `[data-chroma-view="global"\|"bass"\|"mid"\|"high"]` | T11 | none exists |
  | `[data-testid="chroma-curve-toggle"]` | T11 | none exists |
  | `[data-testid="chroma-heatmap"]` | T6 | `chromaHeatmap` (v3 344) |
  | `[data-testid="chroma-heatmap-empty"]` | T6 | — |
  | `[data-testid="chroma-match-curve"]` | T7 | `chromaMatchCurve` (v3 346) |
  | `[data-testid="chroma-legend"]`, `[data-legend-stop]`, `[data-legend-tick]` | T7 | `chromaMatchMarks` (v3 292) |
  | `[data-testid="chroma-match-readout"]` | T7 | `chromaMatchLegend` (v3 330) |
  | `[data-testid="chroma-scan-strip"]` | T8 | `chromaDetuneScan` (v3 332) |
  | `[data-testid="chroma-scan-label"]` | T8 | — |
  | `[data-testid="chroma-best-criterion"]` | T8 | `chromaBestCriterion` (v3 335) |
  | `[data-testid="chroma-best"]` | T8 | `chromaBest` (v3 336) |
  | `[data-testid="chroma-target-mode-lane"\|"chroma-target-mode-set"]` | T9 | none exists |
  | `[data-chroma-key="0".."11"]` | T9 | none exists |
  | `[data-testid="chroma-chord"]`, `[data-testid="chroma-chord-hint"]` | T9 | `chromaChord` (v3 323) on the input only |
  | `[data-testid="chroma-target-empty"]` | T9 | — |
  | `[data-testid="chroma-hover-note"]`, `[data-testid="chroma-hover-detail"]` | T10 | none exists |
  | `[data-testid="clip-score"]` | T10 (edit to M5 T6's `ClipBox`) | — |
  | `[data-testid="chroma-empty"]`, `[data-testid="chroma-error"]` | T11 | — |
