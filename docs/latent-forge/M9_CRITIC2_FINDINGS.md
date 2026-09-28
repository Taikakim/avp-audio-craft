# M9 critic pass 2 — test gates and Svelte 5 correctness (2026-09-27)

**11 findings, 4 blocking** (1, 1b, 2, 9 — all four are compile-or-throw defects, in Tasks 4, 6 and 9,
and three of them sit under a step whose own gate says `npm run check` clean).

Coverage: all ten tasks. Section 0 says which parts were read in which of the two sittings.

Target: `docs/superpowers/plans/2026-09-27-latent-forge-m9-rendering.md`, 8 476 lines, ten tasks.
Lens: per-file test-gate arithmetic, Svelte 5 runes traps, canvas/jsdom traps, `steps_total` division
guards, and the "fix round introduces a new defect" class from M7 critics 2 and 3.
Read-only pass — no file in the repo was edited except this one.

Line numbers refer to the plan as of this pass. Every finding quotes the text it rests on.

---

## 0. Coverage — what was actually read

This pass ran in two sittings; the second resumed after a budget stop. Stating the gap plainly so
nobody reads silence as a clean bill.

**Section A (gate arithmetic) is complete for all ten tasks.** It was produced mechanically: a script
walked every fenced block in the whole 8 476-line file, counted `it(` / `it.skipIf(` per fence, and
every count was matched against the `Tests  N passed (N)` line that follows it. Nothing was sampled
and nothing stopped partway. Base counts inherited from M7 (`projectSerializer.test.ts` 9,
`signalPath.test.ts` 10, `MixSignalPath.component.test.ts` 8, `strings.test.ts` 112) were each
verified against the M7 plan rather than taken on trust. Per-fence `it(` lines were eyeballed for
false positives; one was found and discarded (L3514, the phrase "the whole of it (open question 3)"
inside a comment in `renderBlock.ts`).

**The deeper lens — runes, canvas/jsdom, division guards, M7 data-loss shapes — did not reach
everything in the first sitting.** Read in full then: Tasks 2, 3, 4, 7, 8. Read in part: Tasks 1, 5,
6, 9, 10. Specifically not read in the first sitting:

| task | what was not read in sitting 1 |
|---|---|
| 1 | `payloads.ts`'s body — the six builders (L640-995) |
| 5 | `renderBlock.ts`'s body (L3471-3563) and `renderBlock.test.ts` (L3370-3463) |
| 6 | `dispatch.ts`'s body (L4230-4450) and `dispatch.test.ts` (L4053-4218) |
| 9 | the MasterStrip toggle wiring and the `▸ INPAINT OVERLAP` handler (L7330-7470, L7550-7640) |
| 10 | `laneHeader.ts`'s new drag helpers and `lifecycle.addClip`'s length resolution (L7840-8120) |

Findings 1, 1b, 2, 3, 4, 5, 6, 7, 8 and section C come from sitting 1. **Findings 9 and 10, and
section C2, come from sitting 2 and cover exactly the rows in that table.** Where sitting 2 found
nothing in a file it is recorded in section C2 rather than left silent, so every one of the ten
tasks is now either the subject of a finding or explicitly declared clean.

Note that finding 9 (blocking) and finding 10 both came out of regions sitting 1 had not reached —
`dispatchWorld`'s import block and `payloads.test.ts`'s commit titles — so the gap was not empty.

---

## A. Test-gate arithmetic — mechanical recount

Method: every fenced block in the plan was walked, `it(` / `it.skipIf(` rows counted per fence
(`py` script; one false positive discarded — line 3514 is the phrase "the whole of it (open question
3)" inside a comment in `renderBlock.ts`, not a test), then each count matched against the
`Tests  N passed (N)` gate that follows it.

| Task | file | counted | gate line | gate claims | verdict |
|---|---|---|---|---|---|
| 1 | `payloads.test.ts` (fence L328) | 29 | 999 | 29 | OK |
| 1 | `jobs.test.ts` (L1005) | 18 | 1416 | 18 | OK |
| 1 | `recordedContract.test.ts` append (L1431) | 4 `it.skipIf` | 1478 | "four … reported **skipped**" | OK |
| 1 | task total | 29+18 = 47 | 1480 | 47 | OK |
| 2 | `rasterBorder.test.ts` (L1629) | 16 | 1900, 1956 | 16 | OK |
| 3 | `history.test.ts` (L2067) | 11 | 2269 | 11 | OK |
| 3 | `projectSerializer.test.ts` append (L2277) | 6 | 2451 | 15 (= M7's 9 + 6) | OK — M7 plan line 7072 states "9 in `projectSerializer.test.ts`" |
| 4 | `mixdown.test.ts` (L2580) | 8 | 2969 | 8 | OK |
| 4 | `signalPath.test.ts` append (L2682) | 5 | 2969 | 15 (= M7's 10 + 5) | OK — M7 plan line 2483 states "10 in `signalPath.test.ts`" |
| 4 | `mixdownSlotWired.test.ts` (L2976) | 5 | 3255 | 5 | OK |
| 4 | `MixSignalPath.component.test.ts` append (L3195) | 3 | 3256 | 11 (= M7's 8 + 3) | OK — M7 T5's own fence counts 8 and its gate at M7:3111 says 8 |
| 5 | `renderBlock.test.ts` (L3370) | 11 | 3571, 3800 | 11 | OK |
| 5 | `terminalLog.test.ts` (L3577) | 4 | 3689, 3800 | 4 | OK |
| 5 | `inlineError.test.ts` (L3696) | 3 | 3800 | 3 | OK |
| 5 | task total | 11+4+3 = 18 | 3800 | 18 | OK |
| 6 | `dispatch.test.ts` (L4053) | 11 | 4446, 4908 | 11 | OK |
| 6 | `clipOp.test.ts` (L4452) | 3 | 4538, 4908 | 3 | OK |
| 6 | `promptSigmaTabOp.test.ts` (L4545) | 2 | 4632, 4908 | 2 | OK |
| 6 | `previewRender.test.ts` (L4638) | 7 | 4900, 4909 | 7 | OK |
| 7 | `soloBus.test.ts` (L5034) | 2 | 5185, 5667 | 2 | OK |
| 7 | `historyLabel.test.ts` (L5063) | 4 | 5185, 5667 | 4 | OK |
| 7 | `previewHistory.test.ts` (L5332) | 8 | 5469 (`7 failed \| 1 passed (8)`), 5657, 5667 | 8 | OK |
| 8 | `render/previewActions.test.ts` (L5871 + L5971) | 9 + 13 = 22 | 6200 | 22 | OK (the off-by-one you already fixed) |
| 8 | `replaceClipAudio.test.ts` (L6206) | 6 | 6443 | 6 | OK |
| 8 | `replaceAudio.test.ts` (L6276) | 5 | 6443 | 5 | OK |
| 8 | `prompt/previewActions.test.ts` (L6449) | 7 | 6688 | 7 | OK |
| 8 | task total | 22+6+5+7 = 40 | 6702 | 40 | OK (your fix) |
| 9 | `masterSource.test.ts` (L6932) | 7 | 7242 | 7 | OK |
| 9 | `mixPlayback.test.ts` (L7006) | 4 | 7242 | 4 | OK |
| 9 | `transportMixSource.test.ts` (L7038) | 4 | 7243 | 4 | OK |
| 9 | `masterSourceToggle.test.ts` (L7249) | 6 | 7422 | 6 | OK |
| 9 | `overlapInpaintWired.test.ts` (L7473) | 5 | 7637 | 5 | OK |
| 9 | task total | 7+4+4+6+5 = 26 | 7655 | 26 | OK — the extra `it(` at L6751 is the quoted M7 test in the WHY section, as flagged |
| 10 | `dragPayload.test.ts` (L7838) | 7 | 8124 | 7 | OK |
| 10 | `laneDropLength.test.ts` (L7906) | 4 | 8124 | 4 | OK |
| 10 | `recordedContract.test.ts` append (L8131) | 4 `it.skipIf` | 8174, 8343 | "4 skipped" | OK |
| 10 | task total | 7+4 = 11 | 8343 | 11 | OK |

`strings.test.ts` chain also recounted and consistent: M7 ends at 112 (M7:6638
`extract_help: wrote 112 strings (80 extracted, 14 rewritten, 32 new)`; 80 + 32 = 112), Task 4 adds
two ids → 114 (`wrote 114 strings (80 extracted, 14 rewritten, 34 new)`, L3243), Task 6 adds five
→ 119 (`wrote 119 strings (80 extracted, 14 rewritten, 39 new)`, L4888), and Tasks 7-10 each assert
"stays at 119" with no new ids. Arithmetic is sound in every link.

**No further gate off-by-one found.** The two you already fixed appear to have been the only ones.

### Task-level totals: which tasks state one

Stated: Task 1 (47, L1480), Task 5 (18, L3800), Task 8 (40, L6702), Task 9 (26, L7655), Task 10
(11, L8343).
Not stated: Task 2, 3, 4, 6, 7 — see finding 10 below for which of those is an omission and which is fine.

---

## B. Findings

### BLOCKING

**1. Task 4's `drawPeaks` call has the wrong arity AND the wrong first argument, and Task 4's own
gate claims `npm run check` clean.**

BLOCKING. Task 4, Step 8 — search `MixdownSlot.svelte` for `drawPeaks(ctx`.

Task 4 writes (plan L3097):

```ts
    if (peaks !== null) drawPeaks(ctx, peaks, canvasEl.width, canvasEl.height);
```

The function takes three arguments and a canvas, not a context. Task 7's own Interfaces block states
it (L5002):

> `drawPeaks(canvas: HTMLCanvasElement, peaks: Peaks, color: string): void`,

and the already-shipped M5 caller does it that way — M5 plan L4811: `drawPeaks(canvas, peaks, color);`.
Task 7's own new code at L5533 also uses the three-arg canvas-first form:
`drawPeaks(canvas, computePeaks(buffer, Math.max(1, canvas.width)), color);`.

The plan already notices the clash but defers it (L5004-5007: *"One of the two is wrong and it is
not this one; **Open question 5** carries it to the reconcile"*; repeated at L8448 as known-incomplete
item 5: *"one of the two is wrong and only the reconcile can say which"*). That deferral is not
needed and not safe, for two reasons, both mechanical:

- **It is knowable which is wrong, from source in this repo.** `waveform.ts` is re-homed verbatim
  from the v1 app by M1 T15 (M1 plan L8542, L8559, L8566 import it at its new path), and the v1
  file is still here — `C:\dev\avp-audio-craft\sa3-studio\src\lib\waveform.ts`, L80-84:

  ```ts
  export function drawPeaks(
    canvas: HTMLCanvasElement,
    peaks: Peaks,
    color: string,
    opts: { background?: string } = {},
  ) {
  ```

  Three required parameters, canvas first, and the body immediately reads `canvas.clientWidth` /
  `canvas.clientHeight` and assigns `canvas.width` / `canvas.height` itself — so the two extra
  numbers Task 4 passes are not just surplus, they are the values the function computes. Writer A's
  call is the wrong one; there is nothing for the reconcile to decide.
- Task 4 executes **before** Task 7, and Task 4's Step 12 gate (L3256-3257) reads
  *"`strings.test.ts` green at 114, the rest of the suite unchanged, `npm run check` clean."*
  `npm run check` cannot be clean with a four-argument call to a three-parameter function whose first
  parameter is `HTMLCanvasElement` and is handed a `CanvasRenderingContext2D`. The task as written
  cannot reach its own gate.

FIX (smallest): in Task 4 Step 8 replace the two lines of that `$effect` body with the canvas-first
call and a guarded colour, exactly as Task 7 does it:

```ts
  $effect(() => {
    if (canvasEl === undefined) return;
    const ctx = canvasEl.getContext("2d");
    if (ctx === null) return;
    ctx.clearRect(0, 0, canvasEl.width, canvasEl.height);
    if (peaks !== null) {
      drawPeaks(canvasEl, peaks, getComputedStyle(canvasEl).getPropertyValue("--accent").trim() || "#4ec9b0");
    }
  });
```

and delete known-incomplete item 5 / Open question 5, which then have no subject.

---

**1b. `peaksFor` is synchronous and takes a non-null `AudioBuffer`; Task 4 declares it as returning a
Promise, passes `null`, and calls `.then()` on the result.**

BLOCKING, same task and same `$effect` as finding 1. Task 4, Step 8 — search `MixdownSlot.svelte`
for `void peaksFor(`. Also Task 4's Interfaces, L2557-2560.

Task 4 declares (L2557-2560):

> Consumed from `src/lib/audio/waveform.ts` (M1 T15, re-homed unchanged, used by M5 T? exactly this
> way): `peaksFor(url: string, buffer: AudioBuffer | null, columns: number, fromSec: number,
> toSec: number): Promise<Peaks>`

and uses it (L3083-3090):

```ts
  $effect(() => {
    const u = url;
    const dur = entry?.dur_sec ?? 0;
    if (u === null || canvasEl === undefined) { peaks = null; return; }
    let live = true;
    void peaksFor(u, null, canvasEl.width, 0, dur).then((p) => { if (live) peaks = p; });
    return () => { live = false; };
  });
```

The real function, `C:\dev\avp-audio-craft\sa3-studio\src\lib\waveform.ts` L56-70:

```ts
export function peaksFor(
  url: string,
  buffer: AudioBuffer,
  columns: number,
  fromSec = 0,
  toSec = Infinity,
): Peaks {
  const clampedTo = Math.min(toSec, buffer.duration);
  …
}
```

It is **not** a `Promise`, `buffer` is **not** nullable, and the first statement dereferences
`buffer.duration`. M5's only caller uses it synchronously and guards the buffer — M5 plan L3085-3089:
`const buffer = bufferCache.get(url); if (!buffer) continue; … const peaks = peaksFor(url, buffer, columns, clip.offset_sec, clip.offset_sec + clip.dur_sec);`
— so the Interfaces claim *"used by M5 T? exactly this way"* is not true of either the nullable
buffer or the Promise.

Consequences, all in Task 4: `npm run check` reports `Argument of type 'null' is not assignable to
parameter of type 'AudioBuffer'` and `Property 'then' does not exist on type 'Peaks'`, so Step 12's
*"`npm run check` clean"* is unreachable; and at runtime the MIXDOWN slot's waveform throws
`TypeError: Cannot read properties of null (reading 'duration')` on the first render that has a mix.
Task 4 also never decodes anything, so there is no buffer for it to pass — the slot has no
equivalent of Task 7's lazy `decoder()` (L5509-5523).

FIX (smallest that is still correct): give the slot the same lazy decode Task 7 uses, then call both
functions with their real signatures —

```ts
  let buffer = $state<AudioBuffer | null>(null);

  $effect(() => {
    const u = url;
    if (u === null) { buffer = null; return; }
    let live = true;
    decoder()?.preload(u).then((b) => { if (live) buffer = b; }).catch(() => { if (live) buffer = null; });
    return () => { live = false; };
  });

  $effect(() => {
    if (canvasEl === undefined) return;
    const b = buffer;
    if (b === null) { canvasEl.getContext("2d")?.clearRect(0, 0, canvasEl.width, canvasEl.height); return; }
    drawPeaks(canvasEl, peaksFor(url ?? "", b, Math.max(1, canvasEl.width), 0, entry?.dur_sec ?? 0),
      getComputedStyle(canvasEl).getPropertyValue("--accent").trim() || "#4ec9b0");
  });
```

and correct the Interfaces block at L2557-2560 to the real signature
(`peaksFor(url: string, buffer: AudioBuffer, columns: number, fromSec?: number, toSec?: number): Peaks`).
Note Task 4's version also has no `.catch` on its promise chain while Task 7's equivalent (L5521)
does — with no fetch stub in `mixdownSlotWired.test.ts` (its `beforeEach` at L2991-2997 stubs
nothing) that is an unhandled rejection in the two cases that call `history.add(mixEntry())`
(L3026, L3040).

---

**2. The seeding `arrangement.overlapParams(key)` is called from inside a `$derived` in Task 6 and
again from inside a `$derived.by` in Task 9 — `state_unsafe_mutation`, the exact trap Global
Constraint 4 names.**

BLOCKING. Task 6, Step 15 (`PreviewContainer.svelte`'s `world`) — search for
`overlapParams: overlap ? arrangement.overlapParams(`. Task 9, Step 3 (`dispatchWorld` in
`src/lib/render/dispatch.ts`) — same string.

Task 6 (plan L4789, L4797):

```ts
  const world = $derived({
    …
    overlapParams: overlap ? arrangement.overlapParams(overlap.key) : null,
```

Task 9 lifts the identical line into a shared function and states in its own docstring that it runs
inside a `$derived.by` (L7436-7439, L7456):

> `/** Task 6 built this inline in PreviewContainer; Task 9 needs the identical world for`
> ` *  ▸ INPAINT OVERLAP … Called from inside a $derived.by, every store read below is still tracked …`
> `    overlapParams: overlap ? arrangement.overlapParams(overlap.key) : null,`

and L7467-7468 confirms the call site: *"`PreviewContainer.svelte`'s `const world = $derived.by(() => ({ … }))`
becomes `const world = $derived.by(() => dispatchWorld(target, heads))`"*.

`overlapParams` is the **seeding** reader. M7's own store comment (M7 plan L2452-2456):

> `M7 -- a NON-SEEDING read. `overlapParams` writes OVERLAP_DEFAULT into overlapStore on first`
> `read, which throws state_unsafe_mutation when it runs inside a $derived or a template. This is`
> `the reader for those places…`

and M7's Global Constraint 8 (M7 plan L92-94) forbids it in *"a `$derived`, a template, or a
`$derived.by` snapshot"* by name. M9 restates the same rule as its own Global Constraint 4 (L54-56):

> **Nothing may write `$state` while a `$derived` or a template expression is being evaluated**
> (`state_unsafe_mutation`, verified on Svelte 5.57.0). Anything that seeds on first read must be
> called from an event handler, never from a `$derived`.

The result: selecting an overlap whose params have never been edited throws out of the derivation the
first time `PreviewContainer` (Task 6) or the `▸ INPAINT OVERLAP` button (Task 9) derives `world`.
The plan gets this right in exactly one place — Task 4's `runMixdown` uses the non-seeding reader
(L2896): `overlapParamsOf: (key) => arrangement.peekOverlapParams(key) ?? OVERLAP_FALLBACK(),` — so
the two halves of the same milestone disagree with each other.

FIX (smallest): in both places call the non-seeding reader, which returns a default-shaped copy for
an unstored key and needs no fallback:

```ts
    overlapParams: overlap ? arrangement.peekOverlapParams(overlap.key) : null,
```

Also correct Task 6's Interfaces list, L4014, which currently names
`arrangement.overlapParams(key): OverlapParams` as the consumed method, and Task 9's, L6908, which
does the same.

---

**9. `PAD_SEC` is a component-local `const` in Task 6, and Task 9 imports it from `./dispatch`, which
never exports it.**

BLOCKING. Task 9, Step 13 — search `dispatchWorld.ts` for `import { PAD_SEC`. Task 6, Step 15 —
search `PreviewContainer.svelte` for `const PAD_SEC`.

Task 9's new module opens (plan L7430-7434):

```ts
import { fetchLatchHeads, type LatchHeadInfo } from "../chains/latch";
import type { Target } from "../forge/types";
import { arrangement } from "../stores/arrangement.svelte";
import { settings } from "../stores/settings.svelte";
import { PAD_SEC, type DispatchWorld } from "./dispatch";
```

and uses it at L7460 (`padSec: PAD_SEC,`). Task 9's Interfaces block asserts the same thing, L6890:

> `PREVIEW_RENDER_IDLE_LABEL`, `renderLabel(busy, stepsLeft)`, `kindOf(op)`, `PAD_SEC`.

But `PAD_SEC` is not in `dispatch.ts`. Task 6 declares it inside `PreviewContainer.svelte`'s
`<script>`, L4786-4787:

```ts
  // §6.8's default context each side. M9 has no UI for it; when one lands it reads from here.
  const PAD_SEC = 8;
```

and Task 6's **Produces** list for the module is explicit about what `dispatch.ts` exports
(L4043-4046):

> **Produces:** `src/lib/render/dispatch.ts` — `type ClipOp` (re-export), `PREVIEW_RENDER_IDLE_LABEL =
> "▸ RENDER"`, `renderLabel(busy: boolean, stepsLeft: number | null): string`,
> `interface DispatchWorld`, `renderRequest(target: Target, w: DispatchWorld): SubmitRequest`,
> `kindOf(op: JobOp): RenderKind`.

No `PAD_SEC`. Task 6's `dispatch.ts` body (L4290-4437) does not declare it either — the only two uses
of the name in that task are the component-local `const` and the two places the component reads it
(L4805, L4818).

So Task 9 Step 13 produces `TS2305: Module '"./dispatch"' has no exported member 'PAD_SEC'`, and
Step 17's gate (L7642-7645, *"`npx vitest run && npm run check`"*, expecting this task's suites green)
is unreachable — the same shape as finding 1. It also leaves the constant orphaned: Task 9 deletes
the literal world from `PreviewContainer` (L7467-7468, *"`const world = $derived.by(() => ({ … }))`
becomes `const world = $derived.by(() => dispatchWorld(target, heads))`, deleting the literal"*), so
after Task 9 `PAD_SEC` sits unused in a component while the module that needs it cannot see it.

FIX (smallest): move the declaration into `dispatch.ts` in **Task 6**, where the rest of the §7.1
vocabulary already lives, and have the component import it —

in `dispatch.ts`:

```ts
/** §6.8's default context each side. M9 has no UI for it; when one lands it reads from here. */
export const PAD_SEC = 8;
```

in `PreviewContainer.svelte`, add `PAD_SEC` to the existing
`import { … } from "../../lib/render/dispatch";` line and delete the local `const`. Task 6's
Produces list then needs `PAD_SEC` added to it, and Task 9 needs no change at all.

---

### NON-BLOCKING

**3. `peekOverlapParams` is documented in M9 as returning `OverlapParams | undefined`; it never
returns `undefined`, so Task 4's fallback is dead code.**

Not blocking. Task 1/Task 4 Interfaces — search for `peekOverlapParams(key): OverlapParams | undefined`
(L279) and for `OVERLAP_FALLBACK()` (L2896, L2924).

M9 L279 states:

> `.peekOverlapParams(key): OverlapParams | undefined` (non-seeding, M7 T3),

M7's implementation (M7 plan L2460-2465) is:

```ts
  peekOverlapParams(key: string): OverlapParams {
    return this.overlapStore[key] ?? {
      ...structuredClone(OVERLAP_DEFAULT),
      render: cloneRenderSettings(OVERLAP_DEFAULT.render),
    };
  }
```

— declared `OverlapParams`, and M7's own test proves the unstored case returns a usable object rather
than `undefined` (M7 plan L2259: `expect(arrangement.peekOverlapParams(key).steps).toBe(OVERLAP_DEFAULT.steps);`).

So `arrangement.peekOverlapParams(key) ?? OVERLAP_FALLBACK()` (L2896) can never take its right-hand
branch, and `OVERLAP_FALLBACK` (L2924) is unreachable. Harmless at runtime, but it is a wrong
statement about an inherited API in the section writers implement against, and it is the reason the
same paragraph's prose (L2918-2920, *"returns `undefined` and must fall back"*) is wrong too.

FIX: correct L279 to `.peekOverlapParams(key): OverlapParams` (non-seeding; returns a fresh
default-shaped copy for an unstored key, not `undefined`), drop the `?? OVERLAP_FALLBACK()` and the
`OVERLAP_FALLBACK` definition, and reword L2918-2920 to say the peek already supplies the default.

---

**4. USE SETTINGS decides which target to write only after its fetch returns, so a selection change
during the round trip writes the render's settings into a target the operator did not pick.**

Not blocking (it needs a mid-fetch selection change), but it is the same shape as M7 critic 3 #2 and
it ends in an autosave. Task 8, Step 13 — search `onUseSettings` for `applyPayloadSettings(view.selection, ps)`.

The handler (plan L6613-6627):

```ts
  async function onUseSettings(): Promise<void> {
    if (entry === null || useBlock !== null) return;
    acting = true;
    try {
      const record = await history.jobRecord(entry);
      const ps = payloadSettings(record.op, record.payload);
      …
      const out = applyPayloadSettings(view.selection, ps);
      …
      view.appendLog(`[render] USE SETTINGS: ${parts.join(", ")} from ${entry.label}`);
```

`target` in this component is `view.selection` itself — Task 6, L4774: `const target = $derived(view.selection);`
— so both the block check and the apply read the live selection, and `acting` (L6601, L6610-6611)
only stops a *second click*; it does nothing about the operator selecting another clip or an overlap
while `history.jobRecord(entry)` is in flight. `jobRecord` is a real network call
(`forgeApi.job(e.forge_job_id)` → `GET /forge/jobs/<id>`). When it resolves, `view.selection` may be a
different target, and `applyPayloadSettings` writes `settings.editable(target)` plus `settings.patch(target, {duration_sec})`
into it. Those are edits, so M7's autosave saves them 2 s later.

`entry` has the same exposure: `entry.label` at L6627 is re-read after the await (it is a `$derived`,
L5490), so the TERMINAL line can name a different render than the one whose payload was applied — and
if HISTORY was cleared during the fetch, `entry` is `null` there and the `TypeError` lands in the
`catch` as a bogus `jobs.lastError`.

M7 critic 3 raised the identical pattern for master-preset recall and the fix shipped there was a
load generation counter. Nothing carried it here.

FIX (smallest): capture both before the await and re-check after it —

```ts
      const forTarget = view.selection;
      const forEntry = entry;
      const record = await history.jobRecord(forEntry);
      if (view.selection !== forTarget || entry !== forEntry) return;   // superseded
```

then use `forTarget` / `forEntry` for the apply and the log line.

---

**5. Task 6 Step 9 runs `projectSerializer.test.ts` from the wrong directory, so the command matches
no test file.**

Not blocking, but the step cannot report what it claims. Task 6, Step 9 — search for
`src/lib/stores/__tests__/projectSerializer.test.ts`.

Plan L4534-4538:

```bash
cd latent-forge && npx vitest run src/lib/stores/__tests__/clipOp.test.ts src/lib/stores/__tests__/projectSerializer.test.ts
```
> Expected: `Tests  3 passed (3)` for `clipOp.test.ts`, and `projectSerializer.test.ts` unchanged and
> still green

The file is in `forge`, not `stores`: Task 3 uses the right path at L2448
(`npx vitest run src/lib/forge/__tests__/projectSerializer.test.ts …`), Task 3's Files block names
`latent-forge/src/lib/forge/__tests__/projectSerializer.test.ts` (L2020), and so does M7 (M7 plan
L4932). `vitest run` with a filter that matches nothing exits reporting no test files, so the
"unchanged and still green" half of the gate is never actually checked.

FIX: change that one path to `src/lib/forge/__tests__/projectSerializer.test.ts`.

---

**6. The plan has two independent "Open question N" numberings that collide, and Writer B's
questions 1-6 are never listed anywhere.**

Not blocking, but the assembly step is instructed to collect them and cannot. Search for
`## Open questions (Writer A, Tasks 1-5)` and for `Open questions raised by this task`.

Writer A's list is at L3812 and runs 1-9. Writer B's numbering is separate and runs 1-15, but only
7-15 are ever enumerated (L6712 *"Open questions raised by this task (numbering continues from Task 7…)"*,
L7665, L8464). Questions 1-6 of Writer B's namespace exist only as inline references — L3930
(*"**Open question 1** carries…"*), L4962 (*"**Open question 2**"*), L4803 (*"Open question 3"*),
L5771 (*"**Open question 7** carries…"*), L5006 (*"**Open question 5** carries it to the reconcile"*),
L4892 (*"The assembly step recounts (Open question 6)"*).

The same numbers mean different things in the two namespaces:

| N | Writer A (L3812 list) | Writer B (inline) |
|---|---|---|
| 1 | longform's `schedule` key means two things | `ForgeClip.op` type placement (L3930) |
| 2 | who owns `/status` | `pause()` vs `stop()` on the solo bus (L4962) |
| 3 | `a2a_track`/`a2a_mix` and where a latent lives | no bend-op editor (L4803) |
| 5 | renders excluded from `unsavedWorkKey` (L2013, L2432) | `drawPeaks`' signature (L5006) |
| 6 | final `strings.test.ts` total | final `strings.test.ts` total, again (L4892) |

Bare references such as L3247 *"the assembly step recounts (open question 6)"* and L8454
*"(Open question 13)"* cannot be resolved without knowing which writer wrote the line. The
self-review at L8441-8449 disambiguates some of them by task (*"(Task 6, Open question 3)"*,
*"(Task 7, Open question 5)"*) and not others.

FIX: give Writer B's questions their own heading and continue Writer A's numbering (Writer B's 1-15
become 10-24), or prefix every reference with the writer (`A-OQ 5` / `B-OQ 5`). Either way, add the
missing list for Writer B's 1-6.

---

**7. Five tasks state per-file gates but no task-level total; two of those omissions matter.**

Not blocking. See the table in section A.

- **Task 2** — one new file, gate `Tests  16 passed (16)` at L1900 and again at L1956. A separate
  total would be the same number. Fine as is.
- **Task 3** — no total anywhere. Step 9 (L2461) is only *"Expected: the whole suite green, `npm run check` clean."*
  The task creates `history.test.ts` (11) and appends 6 to `projectSerializer.test.ts`. **Omission**:
  every other task that creates a file states one, and without it nothing pins the 11.
- **Task 4** — Step 12 (L3255-3257) lists four per-file numbers and no sum. Only two of its four
  files are new (`mixdown.test.ts` 8, `mixdownSlotWired.test.ts` 5), so a "this task's new files"
  total of 13 would be the comparable figure. **Omission**, mild — the per-file list is complete.
- **Task 6** — Step 19 (L4908-4909) lists 11, 3, 2, 7 with no sum. All four files are new, so the
  Task-1/5/8/9/10 phrasing *"`Tests 23 passed (23)` for this task's four new files"* applies exactly.
  **Omission.**
- **Task 7** — Step 10 (L5667) lists 2, 4, 8 with no sum; all three are new, total 14. **Omission.**

FIX: add a `**`Tests N passed (N)`** for this task's M new files` line to Tasks 3 (11), 4 (13),
6 (23) and 7 (14), matching the wording already used at L1480, L3800, L6702, L7655 and L8343.

---

**10. Two `commitPayload` test titles miscount M8's key sets by one; the assertions beneath them are
correct, so the wrong number is the only thing a reconciler would read.**

Not blocking — both tests pass, because the arrays they assert are right. But each title is a claim
about `validate_commit`'s contract, stated in the one place someone checking the client against the
server would look. Task 1, Step 3 — search `payloads.test.ts` for `ten top-level keys` and for
`eleven clip keys`.

Plan L546-553:

```ts
  it("emits exactly validate_commit's ten top-level keys with duration_sec at the top", () => {
    const p = commitPayload(commitArgs());
    expect(Object.keys(p).sort()).toEqual([
      "clips", "decode_lanes", "defaults", "duration_sec", "lanes", "master", "mix", "overlaps", "project_bpm",
    ]);
```

That array has **nine** entries, and the builder emits nine (L962-989). M8 agrees — `validate_commit`'s
return, M8 plan L1485-1491, is
`{"project_bpm", "duration_sec", "defaults", "lanes", "clips", "overlaps", "mix", "master", "decode_lanes"}`,
nine keys. The title should say nine.

Plan L581-586:

```ts
  it("emits each clip with exactly validate_commit's eleven clip keys", () => {
    const p = commitPayload(commitArgs());
    expect(Object.keys((p.clips as object[])[0]).sort()).toEqual([
      "a2a", "audio", "detune_cents", "dur_sec", "id", "lane", "loop", "native_bpm", "offset_sec", "start_sec",
    ]);
```

**Ten** entries, and the builder emits ten (L930-944). M8's normalised clip dict, M8 plan L1443-1449,
is `{"id", "lane", "start_sec", "offset_sec", "dur_sec", "loop", "audio", "native_bpm", "detune_cents", "a2a"}`
— ten. The title should say ten.

For contrast the third one is right: L588's *"a LIST of nine-key rows"* matches both its array
(L595-597) and M8's overlap dict (M8 plan L1466-1469), nine keys each.

FIX: change "ten top-level keys" to "nine top-level keys" (L546) and "eleven clip keys" to "ten clip
keys" (L581). No code or assertion changes.

---

**8. Task 7 draws the preview playhead in device pixels under the CSS-pixel transform `drawPeaks`
leaves behind, so on any display with `devicePixelRatio > 1` the playhead is drawn off the canvas.**

Not blocking (no test sees it — jsdom's `clientWidth` is 0, so `drawPeaks` returns before doing
anything), but it is wrong in the product. Task 7, Step 8 — search `PreviewContainer.svelte` for
`function draw()`.

Plan L5525-5541:

```ts
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!buffer) return;
    const color = getComputedStyle(canvas).getPropertyValue("--accent").trim() || "#4ec9b0";
    drawPeaks(canvas, computePeaks(buffer, Math.max(1, canvas.width)), color);
    // Playhead. A LINE, not a label: nothing a test reads is ever painted here (M4's finding).
    const total = previewPlayer.durationSec;
    if (total > 0) {
      const x = Math.round((previewPlayer.playheadSec / total) * canvas.width);
      ctx.fillStyle = getComputedStyle(canvas).getPropertyValue("--fg").trim() || "#fff";
      ctx.fillRect(x, 0, 1, canvas.height);
    }
```

`drawPeaks` resizes the backing store and installs a DPR transform that it never restores —
`C:\dev\avp-audio-craft\sa3-studio\src\lib\waveform.ts` L85-97:

```ts
  const dpr = window.devicePixelRatio || 1;
  const cssW = canvas.clientWidth;
  const cssH = canvas.clientHeight;
  if (cssW <= 0 || cssH <= 0) return;
  if (canvas.width !== Math.round(cssW * dpr) || canvas.height !== Math.round(cssH * dpr)) {
    canvas.width = Math.round(cssW * dpr);
    canvas.height = Math.round(cssH * dpr);
  }
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
```

and it draws everything after that in CSS pixels (`for (let x = 0; x < cssW; x++)`). So after the
call, `canvas.width === cssW * dpr` while the active transform scales by `dpr`. Task 7's `x` is
computed from `canvas.width`, i.e. device pixels, and then drawn under the `dpr` scale — at `dpr: 2`
the playhead sits at four times its CSS-pixel position and leaves the canvas once playback passes
25 % of the render. `canvas.height` in the same `fillRect` is `dpr` times too tall.

M5's own post-`drawPeaks` overlay gets this right by staying in CSS pixels (M5 plan L4813-4817 uses
`clipMarkColumns(peaks)` and `canvas.clientHeight`), so this is Task 7's own slip rather than an
inherited one.

FIX: compute the playhead in CSS pixels, the space `drawPeaks` left the context in:

```ts
      const cssW = canvas.clientWidth;
      const cssH = canvas.clientHeight;
      const x = Math.round((previewPlayer.playheadSec / total) * cssW);
      ctx.fillStyle = getComputedStyle(canvas).getPropertyValue("--fg").trim() || "#fff";
      ctx.fillRect(x, 0, 1, cssH);
```

---

## C. Checked and clean

Recorded so a later pass does not re-derive them.

- **Global Constraint 1 (`$state` proxy rule).** Every method in this milestone that pushes into a
  `$state` array returns the live element or nothing: `HistoryStore.add` (L2219-2224) returns
  `this.renders[index]`; `view.appendLog` (Task 5 L3657-3669) returns `this.lastLogLine()`;
  `logStore.append` (M1 plan L5940-5945) returns `this.lines[this.lines.length - 1]`;
  `replaceClipAudio` (L6377-6388) pushes and returns `void`. No violation found.
- **Global Constraint 2 (abort listener after the signal fired).** The only `AbortController` in M9
  is `JobsStore`'s (L1298, L1314-1316), and it never registers a listener itself — it hands
  `ac.signal` to M1's `pollJob`, which checks `signal?.aborted` at L1314 and again at L1324 *before*
  the `addEventListener("abort", …)` at L1326 (M1 plan). Correct.
- **Global Constraint 3 (`structuredClone` on a `$state` proxy).** Every `structuredClone` in M9 is
  applied to a constant (`CHAIN_DEFAULTS` L361/477/499/2686, `OVERLAP_DEFAULT` L2924) or to a
  plain object parsed from JSON (`project.clips` L4525, `renders` in `HistoryStore.restore` L2254 —
  its only non-test caller is `applyProject` at L2416, which receives a validated `ProjectV2`).
  The one place a live clip is archived uses the rune: `c.history.push($state.snapshot(c.audio) as AudioRef)`
  (L6380), in `arrangement.svelte.ts`, and the plan says why at L6391.
- **Global Constraint 3, second half (`$state.snapshot` only in `.svelte.ts`).** Both call sites are
  in `.svelte.ts` modules — `projectSerializer.svelte.ts` (L2375) and `arrangement.svelte.ts`
  (L6380). `previewActions.ts`, `payloads.ts`, `renderBlock.ts`, `historyLabel.ts`, `soloBus.ts` and
  `dispatch.ts` are plain `.ts` and none of them calls a rune.
- **Global Constraint 6 (no `fillText` under a test assertion).** `fillText` does not appear anywhere
  in the plan. Every label a test reads is DOM: `mixdown-button` / `mix-mixdown` textContent
  (L3002-3004, L3217), `preview-render` textContent (L4671, L4704, L4716), `preview-length` as a
  `<span>` (L5414, L5636), HISTORY rows as `<option>` text (L5393), `render-error` textContent
  (L3711, L3723), `inpaint-overlap-button` textContent (L7538). Task 7 states the rule explicitly at
  L4943-4946 and the raster border is asserted through its driver, not its pixels (L8424-8426).
- **Global Constraint 5 (CSS custom property as a colour).** No test in M9 reads a token, so the
  jsdom `""` trap is not reachable from a gate. Both runtime reads carry a literal fallback
  (`|| "#4ec9b0"` L5532, `|| "#fff"` L5538), which is more than M5's own `--accent` read has
  (M5 plan L4809). See finding 8 for the separate problem with those two lines.
- **Global Constraint 7 (`steps_total` 0).** The milestone has exactly one division and it guards
  first — `sweepHzFor` (L1840-1846): `const total = p?.steps_total ?? 0; if (!p || !Number.isFinite(total) || total <= 0) return SWEEP_START;`,
  then clamps `left / total` into 0..1. Arithmetic checked against its own tests: with
  `SWEEP_START = 95`, `SWEEP_END = 0` (L1817-1818, asserted at L1684), `left/total = 0.5` gives
  `95 + (0 - 95) * 0.5 = 47.5` (L1695) and `6/24` gives `95 - 71.25 = 23.75` (L1696) — both match.
  The over- and under-range cases at L1710-1711 land on `SWEEP_START` / `SWEEP_END` as asserted.
  No progress label can print `NaN`: `mixdownLabel` and `renderLabel` both interpolate
  `${stepsLeft ?? 0}` (L2480-2481, L4293-4295), and L4209 tests the 0 case.
- **The M7 data-loss shapes, in Tasks 3 and 8.** Task 3's additions to `validateProjectV2`
  (L2403-2408) run *before* any store is touched, and `isRenderEntry` (L2386-2391) checks all eight
  `RenderHistoryEntry` fields listed at L118-119, with `isRenderIndex` (L2395-2397) rejecting a
  float or an out-of-range index. `history.restore` is placed before `view.restoreUi` (L2411-2416),
  and M7 already hardened `ui` against the throw-on-the-last-line case it used to have
  (M7 plan L6056-6057: `if (!isObj(p.ui) || !Array.isArray(p.ui.modules)) throw bad("ui");`).
  The non-`version: 2` hole M7 critic 3 found is closed in M7 itself (M7 plan L4530: *"any other
  version (missing, `"2"`, `3`)"*), and `convertProjectV1` already emits `renders: []`,
  `mixdown: null`, `preview: null` (M7 plan L4393-4395), so a v1 import does not trip Task 3's new
  check. Task 8's `ForgeClip.history` is likewise already covered by M7's `isClip`
  (M7 plan L5996: `&& Array.isArray(c.history) && c.history.every(isAudioRef)`) and by the
  converter's `history: []` (M7 plan L4358), so `c.history.push(...)` cannot meet an undefined
  array. `replaceAudio` (L6411-6430) keeps the swap when analysis fails and returns the error
  rather than reverting — the deliberate §7.3 reading, asserted at L6341-6348.
- **Task 6's `ForgeClip.op` load path.** `isClipOp` (L4514-4516) tolerates a missing `op` so M9 can
  still open v2 files written before it, and `applyProject` defaults it (L4525). Both halves are
  present; only the test-run path in that step is wrong (finding 5).
- **Playwright counts.** `render.spec.ts` contains exactly 6 `test(` rows (L8213-8316), matching
  L7830, L8329, L8341 and L8344. M7's `chains.spec.ts` 4 (M7 plan L3118: *"Expected: `4 passed`"*) and
  `sessionsFilesOverlap.spec.ts` 6 agree with L8340-8341.

---

## C2. Checked and clean — the five regions sitting 1 did not reach

Each row of the sitting-1 gap table was read in sitting 2. What follows is what was checked and
found sound, so these are declared clean rather than merely unread. Findings 9 and 10 came out of
this same sweep.

**Task 1 — `payloads.ts`'s six builders (L640-995).** Checked against M8's own source rather than
against the plan's summary of it. `renderWire` (L726-743) emits exactly `RENDER_WIRE_KEYS` (L673-676)
key by key and never spreads `RenderSettings`, which is the whole point of the file given
`_merge`'s unknown-key rejection; `duration_sec` never reaches a `render` object, and `generate`
alone carries a length under the wire name `duration` (L758). Every builder's refusal matches the
server's: `cap` quotes `check_cap`'s sentence verbatim (L670), `commitPayload` quotes
`validate_commit`'s empty-arrangement message (L916, identical to M8 plan L1452), the lane-index
rule (L918-921) matches M8 plan L1417-1419, the master-head rule (L958-960) matches M8 plan
L1481-1483, and the a2a mapping `{on, noise, envelope}` + `clip.render` → `null | {render, envelope}`
(L941-943) with a flat envelope rather than a null (L906-910) matches `validate_envelope`'s refusal.
There is **one division in this file** and it is safe: `const ratio = a.bpm / c.native_bpm;` (L925)
runs only under `if (c.native_bpm != null)`, and a zero `native_bpm` yields `Infinity`, which fails
the `ratio >= 0.5 && ratio <= 2` test and throws a named `PayloadError` — no `NaN` and no silent
pass. `num` (L691-696) rejects non-finite input before any range test, so no builder can put `NaN` on
the wire. No rune, no store read, no `structuredClone` — the file is pure, as its header claims.
- **`settings.current(target)` vs `clip.render` is not a divergence.** `clipRequest` sends
  `render: w.settings` (L4356) while `commitPayload` sends `renderWire(c.render, …)` (L942), which
  would be two different objects if M4 kept a per-target map. It does not: M4 plan L48 — *"There is
  no per-target map in this store"* — and L162, *"this store does not own clip or overlap settings …
  §7.2 says each clip owns `clip.render`"*. `current(t)` resolves to that same object, so a clip's
  ▸ RENDER and that clip inside MIXDOWN use one set of settings.

**Task 5 — `renderBlock.ts` (L3471-3563) and `renderBlock.test.ts` (L3370-3459).** The three-way
dispatch is exhaustive: `Target` has exactly three kinds (M1 plan L637-640,
`{kind:"none"} | {kind:"clip"; id} | {kind:"overlap"; key}`), so nothing falls through to the clip
branch by accident, and the `switch (state.clipOp)` after the `=== null` guard covers all four
`ClipOp` members. Length guards are NaN-safe by construction — `if (!(s.duration_sec > 0) || s.duration_sec > CAP_SEC)`
(L3521) refuses `NaN` rather than admitting it. `CAP_SEC` is a real export of `payloads.ts` (L669).
All eleven test cases match the implementation, including the ordering the code comments claim: the
GPU line outranks the busy line (L3528-3529, pinned by L3406-3408, which sets `busy: true` *and*
`gpuBusyOther` and expects the GPU sentence), and the padded-span arithmetic checks out
(`180 + 2*8 = 196 > 184` refuses at L3456; `4 + 2*8 = 20` passes at L3455). Pure, no store import,
as the header claims. The only untested branch is `clip === null` → `"the selected clip is gone"`
(L3541); not worth a finding, since Task 6's `renderRequest` throws the same sentence (L4426) and
that path *is* covered.

**Task 6 — `dispatch.ts` (L4290-4437) and its test.** `renderRequest`'s precedence matches §7.1:
overlap, then clip, then the session default (L4423-4437), and inside a clip A2A-on wins over the OP
select (L4348), which is what the plan says row 2 does to row 3. The two throw paths are states
`renderBlock` already refuses, and each throws the sentence `renderBlock` shows for it
(`"turn A2A on or choose an op"` L4370 vs L3545; `"the selected clip is gone"` L4426 vs L3541), so
the belt and the braces say the same thing. `kindOf`'s table (L4329-4332) maps every `JobOp` M9
submits, and `latentSourceOf` (L4338-4342) uses `renderBlock`'s own `hasLatent` rule, so the gate and
the builder cannot disagree about what a latent is. No division, no rune, no store read — `dispatch.ts`
is pure and the world is handed in, which is what makes finding 2 a problem in the *caller* rather
than here.

**Task 9 — the MasterStrip toggle (L7340-7414) and the `▸ INPAINT OVERLAP` handler (L7550-7624).**
The toggle's decode `$effect` (L7371-7384) reads `masterSource.url` and writes only `mixBuffer`,
which no derivation inside that effect reads, and it carries both a `cancelled` flag and a `.catch`,
so a superseded decode cannot land on a newer one. `chooseSource` (L7364-7369) is an event handler,
not a derivation, so `masterSource.set` is safe. `masterSource`'s gating is a getter rather than an
effect (L7152-7168) — the comment at L7152-7154 gives exactly the right reason, and `effective`
(L7166-7168) means a session whose `mixdown` index no longer addresses a row reads as "preview"
rather than pointing `refOf` at `undefined`. The inpaint handler's `mine` test compares
`jobs.active.targetKey === view.selectionKey` (L7600) and its catch writes `jobs.lastError` rather
than throwing out of a handler (L7607-7612), both matching Task 6's shape. `dispatchWorld` really is
its own module (L7426), so the two-path import at L7572-7573 is correct — the only thing wrong in
that import block is `PAD_SEC`, which is finding 9.

**Task 10 — `laneHeader.ts`'s drag helpers and `lifecycle.addClip`'s length resolution (L7840-8120).**
`writeForgeDrag` (L8017-8022) only sets the duration MIME for a finite positive number, and
`readForgeDrag` (L8024-8033) re-checks with `Number.isFinite(raw) && raw > 0` — the `raw > 0` half is
what makes an absent type (`Number("") === 0`, not `NaN`) read as "no length" rather than as a
zero-length clip, and the plan says so at L8036-8037. `resolveDuration` (L8050-8062) tries the given
length, then the URL-keyed decode, then a floor it *logs* rather than passes off as a measurement,
and that log goes through `view.appendLog(…, "error")`, which Task 5 has by then made visible in
TERMINAL. The length travels beside the ref rather than inside `AudioRef`, so nothing transient
reaches `ProjectV2` (L7707-7713). Task 7's existing drag-handle assertion survives the change:
it asserts `expect(setData).toHaveBeenCalledWith("application/x-forge-ref", JSON.stringify(...))`
(L5455-5458), and `writeForgeDrag` still makes exactly that call as its first statement. Both
rewritten `writeForgeDrag(e.dataTransfer, …)` call sites are inside an existing
`e.dataTransfer === null` guard (L3117, L5591), so the non-null parameter type is satisfied. `atSec`
is read before the first `await` and the plan says why (L8103-8105). No division, no rune trap.
