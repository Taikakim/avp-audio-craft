# M9 CRITIC 1 — contracts and cross-writer seams

Plan under review: `docs/superpowers/plans/2026-09-27-latent-forge-m9-rendering.md` (8,476 lines).
Lens: contracts across the Writer A (Tasks 1-5) / Writer B (Tasks 6-10) seam, the M8 payload
contract, and claims made about files this plan does not own (M1, M4, M5, M7, the spec).

Note on sources: the latent-forge frontend and the M8 forge server do not exist as code in this
repo yet — M1-M8 are themselves plan documents under `docs/superpowers/plans/`. "The real server
code" for the M8 contract is therefore
`docs/superpowers/plans/2026-09-15-latent-forge-m8-commit-pipeline.md`, and claims about M1/M4/M5/M7
are checked against those plans. Every quotation below is from a real file in this repo.

Findings are appended in the order they were confirmed; the ranked summary is at the end.

---

## F1 — BLOCKING — Task 1's `generate` cap test lands red: it throws "prompt is required", not the 184 message

**Location.** Task 1, Step 1, `payloads.test.ts`, `describe("generatePayload")`. Search for
`refuses a length over the 184 s cap before the round trip`.

**The test:**

```ts
it("refuses a length over the 184 s cap before the round trip", () => {
  expect(() => generatePayload(settings({ duration_sec: CAP_SEC + 1 }))).toThrow(/184/);
});
```

`settings()` in the same file is `{ ...cloneRenderSettings(BASE_DEFAULTS), ...patch }`, and the
patch here sets only `duration_sec`. `BASE_DEFAULTS.prompt` is the empty string —
`docs/superpowers/plans/2026-09-16-latent-forge-m1-foundation-shell.md:898-901`:

```ts
export const BASE_DEFAULTS: RenderSettings = {
  prompt: "",
  negative_prompt: "",
```

And Task 1's own `generatePayload` checks the prompt **before** the cap:

```ts
export function generatePayload(s: RenderSettings, cfgScale: number = s.cfg_scale): Record<string, unknown> {
  const wire = renderWire(s, cfgScale);
  if (!wire.prompt.trim()) throw new PayloadError("prompt is required");
  return { ...wire, duration: cap(s.duration_sec, "generate") };
}
```

So the call throws `PayloadError("prompt is required")`, which does not match `/184/`. The assertion
fails, Step 4's `Tests 29 passed (29)` cannot be reached, and the task lands red.

**Smallest fix.** Give the case a prompt, the way the neighbouring `sends the wire name duration`
case already does:

```ts
expect(() => generatePayload(settings({ prompt: "dub", duration_sec: CAP_SEC + 1 }))).toThrow(/184/);
```

(Reordering `generatePayload` to cap first would also work but changes which error an operator sees
for a payload that is wrong in both ways; the test-side fix is smaller and keeps the server's own
precedence — `_generate_impl` raises `prompt is required`.)

---

## F2 — BLOCKING — Task 1's "superseded job" test never reaches `pollJob` for the first submit, so `await second` hangs

**Location.** Task 1, Step 5, `jobs.test.ts`. Search for
`a superseded job never writes active again`.

**The test:**

```ts
let release: (r: JobRecord) => void = () => {};
vi.spyOn(forgeApi, "pollJob")
  .mockImplementationOnce(() => new Promise<JobRecord>((res) => { release = res; }))
  .mockImplementationOnce(async () => done({ job_id: "forge-2" }));
const first = jobs.submit(SUBMIT);
const second = jobs.submit({ ...SUBMIT, targetKey: "clip:c9" });
release(done({ job_id: "forge-1" }));
await expect(first).resolves.toBeNull();
await second;
```

**Evidence.** `submit` in Step 7 suspends at its *first* statement that awaits, before `pollJob` is
ever reached:

```ts
  async submit(req: SubmitRequest): Promise<RenderHistoryEntry | null> {
    const token = ++this.#token;
    this.#abort?.abort();
    …
      const { job_id } = await forgeApi.submitJob(req.op, req.payload);
      if (token !== this.#token) return null;
```

`jobs.submit(...)` runs synchronously only as far as `await forgeApi.submitJob(...)`. Both calls
therefore happen before any microtask drains, so at the moment `release(...)` executes, `release` is
still the initial `() => {}` — the first `mockImplementationOnce` has not run and has not
reassigned it. The call is a no-op.

When the microtasks then drain, the **first** submit sees `token (1) !== this.#token (2)` and
returns `null` *without calling `pollJob` at all*. The second submit therefore consumes the **first**
`mockImplementationOnce` — the never-resolving promise — and `await second` never settles. The test
times out; Step 8's `Tests 18 passed (18)` cannot be reached.

(The assertion `expect(history.renders[0].forge_job_id).toBe("forge-2")` also depends on the second
submit consuming the *second* mock, which it does not.)

**Smallest fix.** Let the first submit reach `pollJob` before starting the second — one tick is
enough:

```ts
const first = jobs.submit(SUBMIT);
await vi.waitFor(() => expect(jobs.active?.forgeJobId).toBe("forge-1"));
const second = jobs.submit({ ...SUBMIT, targetKey: "clip:c9" });
release(done({ job_id: "forge-1" }));
```

---

## F3 — BLOCKING — Writer A's Task 4 calls `drawPeaks` with the wrong signature; the MIXDOWN waveform never draws and `npm run check` fails

**Location.** Task 4, Step 8, `latent-forge/src/ui/topbar/MixdownSlot.svelte`. Search for
`drawPeaks(ctx, peaks, canvasEl.width, canvasEl.height)`.

**Evidence.** Writer A writes a four-argument call whose first argument is a 2D context:

```ts
  $effect(() => {
    if (canvasEl === undefined) return;
    const ctx = canvasEl.getContext("2d");
    if (ctx === null) return;
    ctx.clearRect(0, 0, canvasEl.width, canvasEl.height);
    if (peaks !== null) drawPeaks(ctx, peaks, canvasEl.width, canvasEl.height);
  });
```

The real signature is canvas-first, three arguments, and takes a colour.
`docs/superpowers/plans/2026-09-17-latent-forge-m5-timeline-fidelity.md:4809-4811` — the only
in-repo call site of the function, in M5 T10's `MasterStrip.svelte`:

```ts
    const color = getComputedStyle(canvas).getPropertyValue("--accent").trim();
    const peaks = computePeaks(masterBuffer, cols);
    drawPeaks(canvas, peaks, color);
```

Writer B independently reached the same conclusion and documented it rather than fixing it —
Task 7's Interfaces:

> **Note the signature**: M5 T10 calls `drawPeaks(canvas, peaks, color)` (three args, canvas first).
> Writer A's Task 4 draft writes `drawPeaks(ctx, peaks, canvasEl.width, canvasEl.height)` — a
> four-arg call against a 2D context. One of the two is wrong and it is not this one; **Open
> question 5** carries it to the reconcile.

and Writer B's own Task 7 code (Step 5, `PreviewContainer.svelte`) uses the three-arg form:
`drawPeaks(canvas, computePeaks(buffer, Math.max(1, canvas.width)), color);`. Deferring this to the
reconcile leaves a task that cannot typecheck — Task 4 Step 10 runs `npm run check`.

Note also Global constraint 5: a colour read out of a CSS token can come back `""`, so the fix must
pass a real colour, not an empty string, or `fillStyle = ""` is a silent no-op that a naive test
passes.

**Smallest fix.** In Task 4 Step 8, replace the draw effect's body with M5 T10's form:

```ts
  $effect(() => {
    if (canvasEl === undefined || peaks === null) return;
    const color = getComputedStyle(canvasEl).getPropertyValue("--accent").trim() || "#7fd";
    drawPeaks(canvasEl, peaks, color);
  });
```

and delete Open question 5's "carry it to the reconcile" wording.

---

## F4 — BLOCKING — the MIXDOWN slot's `▶` never plays anything, and its scrub moves the *timeline* playhead

**Location.** Task 4, Step 8, `MixdownSlot.svelte`. Search for `function togglePlay()` and
`function scrub(e: MouseEvent)`.

**The code, with its own comment contradicting it:**

```ts
  function togglePlay() {
    if (url === null) return;
    // §4.5: preview playback is independent of the timeline transport; starting one stops the other.
    playing = !playing;
    if (playing) void playback.preload(url);
    else playback.seek(0);
  }
```

```ts
    playback.seek(frac * entry.dur_sec);
```

**Evidence.** `playback` is M5 T3's `PlaybackStore`, which drives the **arrangement** transport.
`docs/superpowers/plans/2026-09-17-latent-forge-m5-timeline-fidelity.md:2031-2033`:

```ts
  preload(url: string) {
    return this.engine.preload(url);
  }
```

`preload` only decodes a buffer into the cache — it starts no sound. And `seek` writes the timeline
playhead (same file, 2007-2013):

```ts
  async seek(sec: number) {
    const clamped = Math.max(0, sec);
    this.playheadSec = clamped;
    if (this.playing) {
      await this.engine.seek(clamped, this.snapshotClips(), this.snapshotLanes());
    }
  }
```

So: pressing `mixdown-play` decodes a file and flips a local boolean to `■`; pressing it again
rewinds the operator's **arrangement** to 0; and clicking `mixdown-canvas` jumps the arrangement
playhead to a position inside the mixdown. That is the opposite of the §4.5 rule the comment cites,
and it is the exact rule Writer B built machinery for in the same milestone — Task 7 produces
`src/lib/render/previewPlayer.svelte.ts` (`class PreviewPlayerStore` with `play()`, `stop()`,
`seek(sec)`, `scrubAt(sec)`) and `src/lib/audio/soloBus.ts`
(`registerAudioSource`, `takeAudio`, `AUDIO_SOURCE_TIMELINE`, `AUDIO_SOURCE_PREVIEW`) precisely so
"starting one stops the other" has one home.

Task 4's own Interfaces section asserts the opposite of what it ships:

> Preview playback is independent of the timeline transport and **starting one stops the other**
> (§4.5) — Writer B owns that rule for the preview container; this task applies the same rule to the
> MIXDOWN slot's `▶`.

It does not apply it. Task 4's unit test only asserts the button's `disabled` state
(`play and the canvas stay disabled until a mix exists`), so this ships green and silently broken.

**Smallest fix.** Have `MixdownSlot.svelte` drive Writer B's `previewPlayer` rather than `playback`,
exactly as `PreviewContainer.svelte` does — `previewPlayer.load(url, entry.dur_sec)` /
`previewPlayer.toggle()` / `previewPlayer.seek(frac * entry.dur_sec)` — and drop the local `playing`
flag in favour of `previewPlayer.playing`. That makes Task 4 depend on Task 7, so either reorder the
two or move `previewPlayer`/`soloBus` into Task 1's job-layer commit series.

---

## F5 — BLOCKING — Writer B calls the *seeding* `arrangement.overlapParams(key)` from inside a `$derived`; selecting an unedited overlap throws `state_unsafe_mutation`

**Location.** Task 6, Step 9, `PreviewContainer.svelte` — search for
`overlapParams: overlap ? arrangement.overlapParams(overlap.key) : null`. Task 9, Step 5 lifts the
same line into `src/lib/render/dispatchWorld.ts` (search for the same string), so it appears twice.

**The code.** Task 6:

```ts
  const world = $derived({
    settings: settings.current(target),
    …
    overlapParams: overlap ? arrangement.overlapParams(overlap.key) : null,
```

Task 9 (`dispatchWorld.ts`), with a docstring that explicitly says it runs inside a derived:

```ts
/** … Called from inside a $derived.by, every store read below is still tracked … */
export function dispatchWorld(…): DispatchWorld {
  …
    overlapParams: overlap ? arrangement.overlapParams(overlap.key) : null,
```

**Evidence that `overlapParams` writes.** `docs/superpowers/plans/2026-09-17-latent-forge-m5-timeline-fidelity.md:564-570`:

```ts
  overlapParams(key: string): OverlapParams {
    if (!this.overlapStore[key]) {
      this.overlapStore[key] = {
        ...structuredClone(OVERLAP_DEFAULT),
        render: cloneRenderSettings(OVERLAP_DEFAULT.render),
      };
    }
    return this.overlapStore[key];
  }
```

M7 added a non-seeding reader for exactly this reason and states the rule as a Global Constraint —
`docs/superpowers/plans/2026-09-23-latent-forge-m7-chains-mix-sessions.md:91-95`:

> 8. **Nothing may write `$state` while a `$derived` or a template expression is being evaluated**
>    (`state_unsafe_mutation`, verified on Svelte 5.57.0). M5's `arrangement.overlapParams(key)` seeds
>    `OVERLAP_DEFAULT` into its private store on first read, so it must never be called from a
>    `$derived`, a template, or a `$derived.by` snapshot. Read with **`arrangement.peekOverlapParams(key)`**
>    (added in T3, non-seeding) there; write only through `setOverlapParams`.

M9's own Global constraint 4 repeats it, and Writer A obeys it — Task 4 Step 4 uses
`peekOverlapParams` and carries an `OVERLAP_FALLBACK()` for the `undefined` it can return:

> `OVERLAP_FALLBACK()` is M1 T4's `OVERLAP_DEFAULT` cloned — `peekOverlapParams` is the
> **non-seeding** read (M7 T3), so a derived overlap whose params were never edited returns
> `undefined` and must fall back rather than seed the store from inside a submit path

So the two writers disagree, and Writer B's side is the one the constraint forbids. The first time an
operator selects an overlap they have never opened in the INPAINT module, `world` derives, the store
seeds, and Svelte throws.

**Note on the fallback.** M7's spec text for `peekOverlapParams` says it returns "a fresh
`OVERLAP_DEFAULT`-shaped copy that is **not stored**" (m7 plan:2044-2046), while Writer A's Task 4
says it "returns `undefined`". Whichever M7 T3 actually ships, the replacement must handle it — see
F-note in the summary.

**Smallest fix.** In both places, swap the reader and keep a non-seeding fallback, matching Writer A:

```ts
    overlapParams: overlap ? (arrangement.peekOverlapParams(overlap.key) ?? OVERLAP_FALLBACK()) : null,
```

---

## F6 — BLOCKING — Task 9 imports `PAD_SEC` from `dispatch.ts`, which never exports it; Task 6 declares it as a component-local `const`

**Location.** Task 9, Step 5, `latent-forge/src/lib/render/dispatchWorld.ts`. Search for
`import { PAD_SEC, type DispatchWorld } from "./dispatch";`.

**Evidence.** Task 9's Interfaces section claims Task 6's module produces it:

> `PREVIEW_RENDER_IDLE_LABEL`, `renderLabel(busy, stepsLeft)`, `kindOf(op)`, `PAD_SEC`.

Task 6's "Produces" line says otherwise — it lists everything `dispatch.ts` exports and `PAD_SEC` is
not among them:

> **Produces:** `src/lib/render/dispatch.ts` — `type ClipOp` (re-export), `PREVIEW_RENDER_IDLE_LABEL =
> "▸ RENDER"`, `renderLabel(busy: boolean, stepsLeft: number | null): string`,
> `interface DispatchWorld`, `renderRequest(target: Target, w: DispatchWorld): SubmitRequest`,
> `kindOf(op: JobOp): RenderKind`.

and the full body of `dispatch.ts` written out in Task 6 Step 4 contains no `PAD_SEC` at all. The
only declaration in the plan is inside the Svelte component, Task 6 Step 9:

```ts
  // §6.8's default context each side. M9 has no UI for it; when one lands it reads from here.
  const PAD_SEC = 8;
```

A component-scoped `const` in `PreviewContainer.svelte` is not importable. Task 9's
`dispatchWorld.ts` therefore fails to build: `"PAD_SEC" is not exported by "../dispatch"`.

**Smallest fix.** Move the constant into `dispatch.ts` in Task 6 Step 4, beside `CAP_SEC`'s
neighbours:

```ts
/** §6.8's default context each side. M9 has no UI for it; when one lands it reads from here. */
export const PAD_SEC = 8;
```

add it to Task 6's "Produces" list, and have Task 6 Step 9's component import it instead of
declaring its own.

---

## F7 — BLOCKING — five of Task 10's six Playwright tests click a `▸ RENDER` that is disabled, because nothing types a prompt

**Location.** Task 10, Step 9, `latent-forge/tests/render.spec.ts`. Search for
`await expect(render).toBeEnabled();`, and for each `preview-render` click.

**Evidence.** The button's `disabled` is bound to the block reason — Task 6, Step 16:

```svelte
  <button
    class="render"
    data-testid="preview-render"
    …
    disabled={blocked !== null}
    onclick={onRender}>{label}</button>
```

With no clip selected, `view.selection` is `{kind: "none"}`, and Writer A's `renderBlock`
(Task 5, Step 3) sends that straight to `generateBlock`:

```ts
function generateBlock(s: RenderSettings): string | null {
  if (!s.prompt.trim()) return "needs a prompt — /generate requires a non-empty prompt.";
```

```ts
  if (target.kind === "none") return generateBlock(state.settings);
```

and the session settings start from M1's `BASE_DEFAULTS`, whose prompt is empty —
`docs/superpowers/plans/2026-09-16-latent-forge-m1-foundation-shell.md:898-899`:

```ts
export const BASE_DEFAULTS: RenderSettings = {
  prompt: "",
```

Nothing in the spec file types a prompt before clicking. So on a fresh `page.goto("/")` the button
is disabled with `title="needs a prompt — …"`, and these fail:

- `▸ RENDER submits, labels itself SAMPLING…` — fails at `await expect(render).toBeEnabled()`.
- `the previewed render drags onto a lane…` — its first `preview-render` click times out.
- `MIXDOWN commits and lights the SIGNAL PATH` — same, in its arrangement seeding.
- `a rejected render shows §9.7's inline error…` — same.
- `USE SETTINGS copies the render's own settings…` — fills STEPS but never PROMPT.

Only `the PREVIEW/MIXDOWN A/B is present but unpressable` survives. Step 9's `6 passed` and
Step 10's full-suite gate cannot be reached.

**Smallest fix.** Give the spec a helper beside `openPrompt` and call it in each affected test —
M4 T9 already gives the field a testid (`docs/superpowers/plans/2026-09-18-latent-forge-m4-prompt-sigma.md:3765`:
`data-testid="prompt-text"`):

```ts
async function seedPrompt(page: Page) {
  await page.locator('[data-testid="prompt-text"]').fill("dub techno, tape hiss");
}
```

(Alternatively assert the disabled-with-reason state first — it is worth one assertion —
then type the prompt and continue.)

---

## F8 — BLOCKING — Task 3 edits `workKey` "in `projectSerializer.svelte.ts`", but `workKey` lives in `sessionController.svelte.ts`

**Location.** Task 3, Interfaces (search for `the module-private `workKey(p: ProjectV2): string``),
Task 3 "Files" (`Modify:` list), and Task 3 Step 7 (f) (search for
`Change \`workKey\` and export it under a name the test can reach`).

**The claim.** Task 3's Interfaces section:

> Consumed from `src/lib/forge/projectSerializer.svelte.ts` (M7 T9, verified — quoted in the steps
> below): `serializeProject(…)`, `validateProjectV2(…)`, `applyProject(…)`, and the module-private
> `workKey(p: ProjectV2): string` used by `SessionController`.

and Step 7 is headed **"Change `latent-forge/src/lib/forge/projectSerializer.svelte.ts`"**, with (f)
saying "It is module-private today and `SessionController` is its only caller, so renaming the
export costs nothing."

**What the file actually says.** `workKey` is declared in the *other* file. M7 Task 9 writes
`sessionController.svelte.ts` starting at
`docs/superpowers/plans/2026-09-23-latent-forge-m7-chains-mix-sessions.md:6207`, and at 6258-6264 of
that same block:

```ts
/** What counts as work for step 3's "replace unsaved work?" (critic pass 3 #3): everything saved
 *  except the name, the viewport, the ui slice and the model -- scrolling, opening a module or a
 *  STAGE revert is not work anyone would lose. */
function workKey(p: ProjectV2): string {
  return JSON.stringify({ ...p, name: "", view: null, ui: null, backbone: "", ckpt_path: null });
}

export class SessionController {
```

`projectSerializer.svelte.ts` begins at m7:5883 and ends before m7:6207; it contains no `workKey`.
(Task 3's own line citation, "m7 plan:6262-6264", points into the session-controller file — the
number is right, the filename is not.)

Consequences as written: Task 3's `Modify:` list names only `projectSerializer.svelte.ts` and its
test, so `sessionController.svelte.ts` is edited by a step but never declared; and an implementer
who follows Step 7's heading literally will add a *new* `unsavedWorkKey` to `projectSerializer` and
leave `SessionController`'s own `workKey` untouched — which means the "replace unsaved work?" prompt
still counts `renders`, and Task 3's whole Fact-11 decision silently does not take effect. The
test at Step 5 (`expect(unsavedWorkKey(serializeProject({ name: "" }))).toBe(before)`) would pass
against the dead copy.

**Smallest fix.** Say "move": in Task 3, change the Interfaces line to name
`src/lib/forge/sessionController.svelte.ts` as `workKey`'s home, add that file to the `Modify:`
list, and reword Step 7 (f) as "**Move** `workKey` out of `sessionController.svelte.ts` into
`projectSerializer.svelte.ts`, exported as `unsavedWorkKey`, delete the original, and import it back
in `SessionController` alongside the names it already imports from `./projectSerializer.svelte`."
The direction is safe — `sessionController.svelte.ts` already imports from
`./projectSerializer.svelte` (m7:6216-6220), so no cycle is created.

---

## F9 — BLOCKING — `<TopBar busy={…} stepsLeft={…} />` passes props TopBar does not have; they are `mixdownBusy` / `mixdownStepsLeft`, and TopBar already forwards them

**Location.** Task 4, Step 8 (search for `<TopBar … busy={jobs.busy} stepsLeft={jobs.stepsLeft} />`),
and the header table "Frames already in place — keep their testids", `MixdownSlot` row (search for
`Props \`busy\`/\`stepsLeft\` exist on TopBar but App does not pass them`).

**What M1 actually declares.** `docs/superpowers/plans/2026-09-16-latent-forge-m1-foundation-shell.md:5317-5318`
and `:5338-5339`, in `TopBar.svelte`'s `$props()` block:

```ts
    mixdownBusy?: boolean;
    mixdownStepsLeft?: number | null;
```
```ts
    mixdownBusy = false,
    mixdownStepsLeft = null,
```

and, at `:5396`, TopBar **already** does the forwarding Task 4 Step 8 asks for:

```svelte
  <MixdownSlot busy={mixdownBusy} stepsLeft={mixdownStepsLeft} />
```

So `busy` / `stepsLeft` are `MixdownSlot`'s prop names, not TopBar's — the header table has them on
the wrong component, and the "forward `busy`/`stepsLeft` to `<MixdownSlot>`" half of Step 8 is
already done in M1.

**Why it lands red.** Step 8's App edit passes two props TopBar never declares. Svelte 5's
`$props()` destructuring drops them silently at runtime, so `mixdownBusy` stays `false` forever and
the MIXDOWN button never leaves `▸ MIXDOWN` — which fails Task 10's Playwright gate:

```ts
  await mixdown.click();
  await expect(mixdown).toContainText(/SAMPLING · \d+ steps left/);
```

and `npm run check` (svelte-check) reports the two excess props on the component as a type error,
failing Task 4 Step 10's gate as well. (M1's App element at `:5580-5601` passes neither name, so
nothing currently masks this.)

**Smallest fix.** In Task 4 Step 8, drop the TopBar-forwarding sentence — it is already true — and
make the App edit use M1's own prop names:

```svelte
  <TopBar … mixdownBusy={jobs.busy} mixdownStepsLeft={jobs.stepsLeft} />
```

and correct the header table row to read "Props `mixdownBusy`/`mixdownStepsLeft` exist on TopBar,
which already forwards them to `MixdownSlot` as `busy`/`stepsLeft`; App passes neither."

---

