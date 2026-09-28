# M9 critic pass 3 — narrow review of the fix round only

*2026-09-28. Scope: only what commits `0716184`, `83f3da1`, `06e950b` changed in
`docs/superpowers/plans/2026-09-27-latent-forge-m9-rendering.md` (diff base `d9149cb`), guided by
`docs/latent-forge/M9_FIXROUND_LOG.md`. Read-only pass; the plan is not edited.*

---

## C3-1 — BLOCKING. The new cross-task Ordering note names the wrong Task 7 steps; `previewPlayer.svelte.ts` is written in Step 5, not Steps 3-4.

**Where:** plan lines 2597-2608, Task 4 **Interfaces** (NEW TEXT, fix-round row `F4`).

**Evidence.** The note says:

> **Ordering:** this makes Task 4 Step 8 depend on Task 7
> Steps 3-4, which produce `soloBus.ts` and `previewPlayer.svelte.ts`. Build those two files before
> Task 4 Step 8 — they are pure additions with no dependency of their own on the rest of Task 7 […]

Task 7's own step list (plan 5230, 5266, 5330) is:

```
- [ ] **Step 3: Write the two pure modules**
- [ ] **Step 4: Run them, expect pass**
- [ ] **Step 5: Write the preview player store and register both sides of the solo bus**
```

Step 3's body writes `latent-forge/src/lib/audio/soloBus.ts` and
`latent-forge/src/lib/render/historyLabel.ts` — the "two pure modules". Step 4 only runs
`npx vitest run src/lib/audio/__tests__/soloBus.test.ts src/lib/render/__tests__/historyLabel.test.ts`.
`previewPlayer.svelte.ts` is created in **Step 5** (plan 5331-5332:
"`latent-forge/src/lib/render/previewPlayer.svelte.ts`:").

**Consequence.** An implementer who follows the note literally lands Task 7 Steps 3-4, returns to
Task 4 Step 8, and Step 12's gate (`cd latent-forge && npx vitest run && npm run check`) fails on
`Failed to resolve import "../../lib/render/previewPlayer.svelte"` — exactly the failure the note
was added to prevent. Secondarily, "pure additions with no dependency of their own on the rest of
Task 7" is not true of Step 5: its second half also modifies M5's
`latent-forge/src/lib/stores/transport.svelte.ts` to `registerAudioSource(AUDIO_SOURCE_TIMELINE, …)`
and to call `takeAudio` in `play()`, and without that half §4.5's "starting one stops the other"
does not hold for the MIXDOWN `▶` that Task 4 Step 8 just wired.

**Smallest fix.** Change "Task 7 Steps 3-4" to "Task 7 Steps 3 and 5", and change the parenthetical
to name what each produces: Step 3 → `soloBus.ts`, Step 5 → `previewPlayer.svelte.ts` plus the
solo-bus registration in M5's `transport.svelte.ts`.

---

## C3-2 — BLOCKING. The rewritten draw effect feeds a stale `AudioBuffer` into the URL-keyed `peaksFor` cache, so a mixdown can show the previous mix's waveform permanently.

**Where:** plan lines 3155-3183, Task 4 Step 8, `MixdownSlot.svelte` (NEW CODE, fix-round rows
`F3 + C2-1` and `C2-1b`).

**Evidence.** The new decode effect never clears `buffer` when `url` changes to a *different*
non-null url:

```ts
  $effect(() => {
    const u = url;
    if (u === null) { buffer = null; return; }
    let live = true;
    decoder()?.preload(u).then((b) => { if (live) buffer = b; }).catch(() => { if (live) buffer = null; });
    return () => { live = false; };
  });
```

and the draw effect, which depends on both `buffer` and `url`, re-runs the moment `url` changes —
before the new decode resolves — and calls:

```ts
    drawPeaks(
      canvasEl,
      peaksFor(url, b, Math.max(1, canvasEl.width), 0, entry?.dur_sec ?? 0),
      getComputedStyle(canvasEl).getPropertyValue("--accent").trim() || "#4ec9b0",
    );
```

`peaksFor` is a **memoizing** function keyed on the URL, not on the buffer
(`sa3-studio/src/lib/waveform.ts`, the file M1 T15 re-homes verbatim):

```ts
const cache = new Map<string, Peaks>();

function key(url: string, columns: number, fromSec: number, toSec: number): string {
  return `${url}@${columns}:${fromSec.toFixed(3)}-${toSec.toFixed(3)}`;
}

export function peaksFor(url: string, buffer: AudioBuffer, columns: number, fromSec = 0, toSec = Infinity): Peaks {
  const clampedTo = Math.min(toSec, buffer.duration);
  const k = key(url, columns, fromSec, clampedTo);
  const hit = cache.get(k);
  if (hit) return hit;
  const peaks = computePeaks(buffer, columns, fromSec, clampedTo);
  cache.set(k, peaks);
  return peaks;
}
```

So on the second and every later commit, the first draw after `url` flips computes the *old* mix's
peaks and stores them under the *new* mix's cache key. When the two mixes have the same effective
duration — the normal case: re-commit after a mix tweak, same `LENGTH`, so
`Math.min(entry.dur_sec, buffer.duration)` is identical — the key matches exactly and the poisoned
entry is returned forever. Nothing calls `invalidatePeaks`, and the cache is module-scoped, so the
MIXDOWN slot keeps drawing the previous mix's waveform for the rest of the session.

This is new: the pre-fix code called `peaksFor(u, null, …)` inside the *same* effect that read `u`,
so url and source could not disagree. Task 7's PreviewContainer, which the fix round says it copied
the pattern from, uses the **uncached** `computePeaks(buffer, columns)` (plan 5671) and is not
affected.

**Smallest fix.** Clear the buffer whenever the url changes, so the draw effect cannot run with a
mismatched pair:

```ts
  $effect(() => {
    const u = url;
    buffer = null;                 // a new url invalidates the old buffer, not just supersedes it
    if (u === null) return;
    …
  });
```

(Task 7's equivalent effect has the same missing line but does not reach a URL-keyed cache, so it
only shows a stale frame; fixing both keeps the two copies identical.)

---

## C3-3 — BLOCKING. Task 8's new superseded guard compares `view.selection` by reference, and every selection click constructs a fresh object — so re-clicking the *same* clip silently drops a legitimate USE SETTINGS.

**Where:** plan line 6834, Task 8 Step 13, `onUseSettings` (NEW CODE, fix-round row `C2-4`).

**Evidence.** The guard:

```ts
    const forTarget = view.selection;
    const forEntry = entry;
    acting = true;
    try {
      const record = await history.jobRecord(forEntry);
      if (view.selection !== forTarget || entry !== forEntry) return;   // superseded
```

`view.selection` is a plain `$state` slot that `select()` **overwrites with whatever object it is
handed** (M1 plan 3179-3281):

```ts
  selection = $state<Target>({ kind: "none" });
  …
    this.selection = target;
```

and every caller in every milestone hands it a **fresh object literal**, unconditionally, including
M5's clip `onPointerDown` (m5 plan 3632-3635):

```ts
  function onPointerDown(e: PointerEvent) {
    if (e.button !== 0) return;
    e.stopPropagation(); // never also fire the lane body's own seek/select
    view.select({ kind: "clip", id: clip.id });
```

So a single pointerdown anywhere on the **already-selected** clip while `history.jobRecord`'s
`GET /forge/jobs/<id>` is in flight makes `view.selection !== forTarget` true even though the target
has not changed. The function then returns through `finally { acting = false; }` with no
`useSettingsNote`, no `view.appendLog` line and no error — the operator clicked USE SETTINGS and
nothing happened, with nothing anywhere saying why. The guard was added to stop a write to the
*wrong* target; as written it also stops writes to the *right* one.

**Smallest fix.** Compare by the string key that already exists for exactly this purpose — M1 T3's
`targetKey` (m1 plan:713), which Task 5's fix round already established as the one spelling:

```ts
    const forKey = view.selectionKey;      // M1 T7's derived, targetKey(view.selection)
    const forEntry = entry;
    …
      if (view.selectionKey !== forKey || entry !== forEntry) return;   // superseded
```

and keep `const forTarget = view.selection;` for the `applyPayloadSettings(forTarget, ps)` call.

---

## C3-4 — Not blocking. The same new guard leaves the `catch` path keyed to the *current* selection, so a failed fetch can raise §9.7's inline error under a target that never asked for it.

**Where:** plan lines 6847-6850, Task 8 Step 13, `onUseSettings` (the `catch` was not changed by
the fix round, but the fix round's capture is what makes the inconsistency visible and wrong).

**Evidence.** The body now consistently uses the captured values —

```ts
      const record = await history.jobRecord(forEntry);
      …
      const out = applyPayloadSettings(forTarget, ps);
      …
      view.appendLog(`[render] USE SETTINGS: ${parts.join(", ")} from ${forEntry.label}`);
```

— but the failure path does not:

```ts
    } catch (e) {
      // §9.7: the job fetch is the failure the operator must see, and jobs.lastError is that surface.
      jobs.lastError = { targetKey: view.selectionKey, message: e instanceof Error ? e.message : String(e) };
```

A `throw` from `history.jobRecord` skips the superseded check (it is inside the same `try`, after
the await), so if the operator has moved on, `jobs.lastError` is stamped with the **new** target's
key and `InlineError` paints the failure under a clip that ran nothing. The rest of the function was
just taught not to do this; the `catch` is the one path left behind.

**Smallest fix.** Use the captured key in the `catch` too — with C3-3's `forKey`:
`jobs.lastError = { targetKey: forKey, message: … };`.

---

## Verified clean (checked, nothing found)

- **`PAD_SEC` move (`F6`).** `export const PAD_SEC = 8;` is declared once (plan 4419) in
  `dispatch.ts`, listed in Task 6's **Produces** (4154) and Task 9's Interfaces (7109), imported by
  `PreviewContainer.svelte` (4891) and by Task 9's `dispatchWorld.ts` (7655), and consumed at 4940,
  4953, 7682. No second declaration and no orphaned consumer; the old component-local `const PAD_SEC = 8`
  is gone. The `padSec` field on `renderBlock`/`DispatchWorld` is a separate, pre-existing name and is
  untouched.
- **`CLIP_OPS` move (`F12`).** `export { CLIP_OPS } from "../../lib/forge/types";` re-exports the
  same binding, so the added `expect(TARGET_BAR_CLIP_OPS).toBe(CLIP_OPS)` holds by identity. Both
  import paths in `src/lib/stores/__tests__/clipOp.test.ts` resolve
  (`../../forge/types` → `src/lib/forge/types`, `../../../ui/prompt/targetBar` → `src/ui/prompt/targetBar`).
  M4's only consumers (`m4 plan:3244` `value={op ?? CLIP_OPS[0]}`, `m4:3247` `{#each CLIP_OPS as o (o)}`)
  and M4's own test (`m4:2964`) still compile and pass against `readonly ClipOp[]`; `latent-forge/`
  has no tsconfig yet and `sa3-studio`'s does not set `noUncheckedIndexedAccess`. No new `it(`,
  so `clipOp.test.ts` stays at 3 as claimed. The edit to the M4-owned file is declared in Task 6's
  Files `Modify:` with its reason.
- **`workKey` move (`F8`).** Verified against M7: `function workKey(p: ProjectV2)` is declared in
  `sessionController.svelte.ts` (m7 plan:6262, directly above `export class SessionController`) with
  exactly four call sites at m7:6301, 6408, 6424, 6434 — the four the plan names — and that file
  already imports from `./projectSerializer.svelte` (m7:6216-6220), so the move creates no cycle.
  `grep -rn workKey` over the M7 plan finds no fifth caller. Task 3's Files `Modify:` gains
  `sessionController.svelte.ts`, Step 7 (f) says **Move** and **delete the original**, and Task 3's
  own test calls `unsavedWorkKey`, not `workKey`.
- **`peekOverlapParams` / removed `OVERLAP_FALLBACK` (`F5`, `F13`).** Verified against M7 T3
  (m7 plan:2460-2464): `peekOverlapParams(key: string): OverlapParams` returns
  `this.overlapStore[key] ?? { ...structuredClone(OVERLAP_DEFAULT), render: cloneRenderSettings(…) }`
  — never `undefined`. Deleting `?? OVERLAP_FALLBACK()` and the `OVERLAP_DEFAULT` import is safe,
  and the Task 1 Interfaces line now states the non-`undefined` return correctly.
- **`F9` (TopBar props).** Verified against M1 T10: `mixdownBusy?`/`mixdownStepsLeft?` are declared
  (m1:5317-5318), destructured (m1:5338-5339) and already forwarded as
  `<MixdownSlot busy={mixdownBusy} stepsLeft={mixdownStepsLeft} />` (m1:5396). Dropping
  `TopBar.svelte` from Task 4's Files `Modify:` and passing M1's names from `App.svelte` is correct,
  and the header frames table row now matches.
- **`F2` (the `vi.waitFor` in `jobs.test.ts`).** `submitJob` is `mockResolvedValue` and `pollJob`
  carries the never-resolving first mock; `JobsStore.submit` sets `this.active = { forgeJobId: job_id, … }`
  *before* `await forgeApi.pollJob(…)` (plan 1332-1337), so the wait resolves and the second submit
  consumes the second `pollJob` mock. No deadlock. (The added comment's phrasing — "`submit` suspends
  at `await forgeApi.submitJob(...)`" — describes the wrong await; harmless, prose only.)
- **`F7` (`seedPrompt`).** `BASE_DEFAULTS.prompt` really is `""` (m1 plan:898-899) and
  `data-testid="prompt-text"` really is M4 T9's (m4 plan:3765), so the five `▸ RENDER` tests needed
  it. The sixth test — *"the PREVIEW/MIXDOWN A/B is present but unpressable until a commit exists"* —
  never opens the PROMPT tab and never touches `preview-render`; it only asserts
  `master-source-mixdown` is visible, disabled and titled. Correctly left alone. `test(` count is 6.
- **Task-level totals (`A7`, `C2-7`).** All ten now state one, and a mechanical count of `it(` +
  `it.skipIf(` over each task's own line range reproduces every stated figure:
  T1 51 (47 + 4 skipIf), T2 16, T3 17, T4 21, T5 18, T6 23, T7 14, T8 40, T9 26 + the one quoted M7
  `it(` in that task's prose = 27 mechanical, T10 15 (11 + 4 skipIf). Each task's breakdown also
  sums to its total (e.g. T6: 11 + 3 + 2 + 7 = 23; T7: 2 + 4 + 8 = 14; T9: 7 + 4 + 4 + 6 + 5 = 26).
- **`A`/`B` namespacing (`A6`).** Every M9 citation now carries its letter. The only bare
  "open question N" strings left are the five the log declares out of scope, and each checks out:
  three name M7 explicitly (plan 2513 *"M7's own open question 7"*, 2744 a `describe(` title
  *"M7 open question 7"*, 2841 a source comment *"M7 open question 7"*), one names M1 (3933,
  inside `A2`'s own heading), and one — 4017, *"Both are recorded in Open questions 20."* — sits
  inside a verbatim quotation of M7 T9's text and correctly was not edited. The sixth bare hit,
  at 8721, is the consolidated index deliberately quoting *"Open question 7"* as the ambiguous
  example. The index lists all 24 ids with no gaps other than `B4`, which is recorded as
  deliberately never used. No dangling id: every cited id (`A2`-`A6`, `B1`-`B3`, `B6`, `B7`, `B9`,
  `B10`, `B12`, `B13`) has an entry.
- **Runes rules in the rewritten Task 4 Step 8.** No write to state inside any `$derived`; both
  writes to `buffer` are inside `$effect`s; no `$state.snapshot` is used anywhere in the new code;
  the decode effect's `let live = true` / `return () => { live = false; }` abort-and-supersede
  ordering is correct (the cleanup runs before the re-run, so a resolved stale promise cannot
  overwrite a newer one — the separate defect in C3-2 is the *unset* buffer, not the ordering); and
  `const playing = $derived(previewPlayer.playing && previewPlayer.url === url)` is only ever read
  (template line 3229), never assigned, so replacing M5's local `$state` is sound. `load()` is
  idempotent for the same url (`if (this.url === url) return;`, plan 5386) so calling it before
  `toggle()` does not rewind a playing mix.
- **Task 4's other Task 7 references.** `previewPlayer` is the only Task 7 symbol Task 4 Step 8
  reaches; `Transport`, `peaksFor`/`drawPeaks`, `history`, `forgeApi` and `mixdownLabel` all come
  from M1/M5 or Task 3/Task 4 itself. Task 4's own tests (`mixdownSlotWired.test.ts`, 5 rows) assert
  only label, disabled state, click and drag — none references `playback` or `previewPlayer` — so
  the rewire breaks no existing assertion.
