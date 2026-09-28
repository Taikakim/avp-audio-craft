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


## Coverage of this pass (stated before the remaining findings)

All ten tasks were examined. The pass ran in two sittings; it was interrupted mid-Task-4 at a budget
line, not because anything was wrong, and then resumed and completed.

**Read in full, line by line:** the header sections (Global constraints, The M8 payload contract,
Names inherited, the frames/testids table, HELP coverage, Two defects), Task 1, Task 3, Task 5,
Task 6, Task 7, Task 10.

**Read in full after the resume:** Task 2 (Steps 3-9, including the driver and the App wiring),
Task 4 (Steps 1-3, the mixdown store and the signalPath merge), Task 8 (Steps 5-14), Task 9
(Steps 1-8, masterSource and the transport routing).

**Verified against the real files they cite** (not merely read): M1
(`2026-09-16-latent-forge-m1-foundation-shell.md` — `BASE_DEFAULTS`, `ForgeClip`, `Progress`,
`targetKey`, `LogStore`, `PreviewContainer`, `TopBar`/`MixdownSlot`, `mixdownLabel`), M4
(`RANGES.length_sec`, `NUMERIC_TOP`, `CLIP_OPS`, `target-op`, `cfgDisabled`/`effectiveCfg`,
`prompt-text`), M5 (`PlaybackStore`, `overlapParams`, `trimClip`, `find`, `lifecycle.addClip`,
the two drop handlers, `drawPeaks` call site, `isAudible`, `math/playback`), M7 (`chainRequest`,
`peekOverlapParams`, `projectSerializer` guards, `workKey`, `recordedContract` harness,
strings totals), M8 (`parse_render`, `_merge`, `RENDER_DEFAULTS`, `parse_chain`, `validate_commit`,
`validate_a2a_clip`, `validate_inpaint`, `smoke_commit.py` fixtures), M2 (fixture names, `redact`),
M3 (`parse_spec` DEFAULTS), and the one real source file this plan copies,
`docs/sa3-studio/design_handoff/phosphor-border.js` (PALETTES, DEFAULTS, the handle API).

**Not examined:** the `<style>` blocks of any component; the prose of the two Open-questions
sections beyond skimming for contradictions with the steps; and the M10 plan (it precedes M9 in
the build order but touches none of the names that cross this seam — checked only that it adds no
HELP ids).

**One thing I could not check at all:** the server side of the M8 contract has no implementation in
this repo. `parse_render`, `parse_chain`, `validate_commit`, `validate_a2a_clip` and
`validate_inpaint` exist only inside
`docs/superpowers/plans/2026-09-15-latent-forge-m8-commit-pipeline.md`; `eval/` contains
`explorer_render_server.py` (the pre-forge server) and no `eval/forge/` package. Every M8 claim
below is therefore checked against the M8 *plan*, which is the strongest source that exists today.
The same is true of M1/M4/M5/M7: they are plans, not code.

**Test-count gates: all checked mechanically.** I counted `it(`/`test(` per block against every
`Expected: Tests N passed` line in the plan — 29/18/16/11/15/8/15/5/11/11/4/3/11/3/2/7/2/4/8/22/6/5/7/7/4/4/6/5/7/4/6
— and the HELP running totals (M7 112 -> T4 114 -> T6 119, then flat). **They are all correct**,
including the two the coordinator has already fixed. The numbers are not where this plan is weak;
the seams are.

---

## F10 — BLOCKING — Task 4's `meta.stages` test asserts `mixdown.key` is not null, but the path it exercises always leaves it null

**Location.** Task 4, Step 1, `latent-forge/src/lib/render/__tests__/mixdown.test.ts`. Search for
`stores a finished commit's meta.stages with the signal key of the arrangement it described`.

**The test:**

```ts
  it("stores a finished commit's meta.stages with the signal key of the arrangement it described", async () => {
    addClip();
    vi.spyOn(mixdown, "heads").mockResolvedValue({});
    const entry = { job_id: "mix-1", … };
    vi.spyOn(jobs, "submit").mockImplementation(async () => {
      mixdown.acceptStages([{ label: "MIX", on: true, note: "(1+2) + (3+4)", seconds: 2.5 }]);
      return entry;
    });
    await runMixdown();
    expect(mixdown.stages).toHaveLength(1);
    expect(mixdown.key).not.toBeNull();
  });
```

**Evidence.** `acceptStages`' second parameter defaults to the store's *current* key — Task 4,
Step 4, `mixdown.svelte.ts`:

```ts
  acceptStages(stages: CommitStage[], key: string | null = this.key): void {
    this.stages = stages;
    this.key = key;
  }
```

`beforeEach` calls `mixdown.reset()`, whose body is `this.stages = null; this.key = null;`. The test
then calls `acceptStages` with **one** argument, so `key` defaults to `this.key`, i.e. `null`, and
`this.key = null` again. `expect(mixdown.key).not.toBeNull()` fails.

The only place a real key is supplied is the `jobs.onDone` hook (Task 4, Step 5):

```ts
jobs.onDone = (rec) => {
  …
  mixdown.acceptStages(raw as CommitStage[], pendingKey);
};
```

and that hook is reached from inside `jobs.submit` — which this test has replaced with
`vi.spyOn(jobs, "submit").mockImplementation(...)`. So the very mechanism the test title names
(`with the signal key of the arrangement it described`) is mocked out, and nothing sets the key.
Step 6's `Tests 8 passed (8)` cannot be reached.

**Smallest fix.** Drive the real path instead of mocking `jobs.submit` — mock the transport one
level down, so `submit` runs, `onDone` fires, and `pendingKey` is what lands:

```ts
    vi.spyOn(forgeApi, "submitJob").mockResolvedValue({ ok: true, job_id: "forge-1", position: 0 });
    vi.spyOn(forgeApi, "pollJob").mockResolvedValue(doneCommitRecord([
      { label: "MIX", on: true, note: "(1+2) + (3+4)", seconds: 2.5 },
    ]));
    await runMixdown();
    expect(mixdown.stages).toHaveLength(1);
    expect(mixdown.key).toBe(signalKeyOf(signalInputNow()));
```

(If the `jobs.submit` mock is kept for speed, the test must at minimum pass a key explicitly —
`mixdown.acceptStages([...], "k")` — but then it no longer tests what its title claims, and the
`onDone` → `pendingKey` wiring introduced in Step 5 has no test at all.)

---

## F11 — not blocking — Writer A declares a second `targetKeyOf` with the identical body to M1's exported `targetKey`, which Writer B imports

**Location.** Task 5, Step 10 (search for `export function targetKeyOf(t: Target): string`).

**The new declaration**, placed in `renderBlock.ts`:

```ts
/** The string `jobs.lastError.targetKey` is keyed by. One spelling, used by every render control. */
export function targetKeyOf(t: Target): string {
  return t.kind === "none" ? "session" : t.kind === "clip" ? `clip:${t.id}` : `overlap:${t.key}`;
}
```

**What already exists.** `docs/superpowers/plans/2026-09-16-latent-forge-m1-foundation-shell.md:712-719`,
in `src/lib/forge/types.ts`:

```ts
/** Stable key for a target; also the key of the per-target settings map. */
export function targetKey(t: Target): string {
  switch (t.kind) {
    case "none": return "session";
    case "clip": return `clip:${t.id}`;
    case "overlap": return `overlap:${t.key}`;
  }
}
```

Same three cases, same three strings. M1 T7's view store already derives `selectionKey` from it
(`selectionKey = $derived(targetKey(this.selection));`, m1:3183), and Writer B imports it by that
name — Task 6, Step 4: `import { targetKey } from "../forge/types";`, then
`targetKey({ kind: "clip", id: clip.id })`. Task 6's own Interfaces list even names it as an
inherited M1 T3 export.

So the docstring's "One spelling, used by every render control" is false as written: there are two
spellings, `targetKeyOf` used by `InlineError` and `targetKey` used by `▸ RENDER`. The M9 header's
own rule — *"Names inherited — do not redeclare them"* — forbids exactly this. It is not red today
because the two agree; it is a finding because nothing keeps them agreeing, and the whole §9.7
surface is a string match between the key `jobs.submit` stored and the key `InlineError` compares.

**Smallest fix.** Delete `targetKeyOf` from `renderBlock.ts` and have `PromptSigmaTab.svelte` use
`view.selectionKey` (M1 T7's existing derived, which is `targetKey(view.selection)`):

```svelte
  <InlineError targetKey={view.selectionKey} />
```

`renderBlock.ts` already imports `Target` from `../forge/types`, so nothing else changes.

---

## F12 — not blocking — `CLIP_OPS` is declared a second time, in a different module, and the two copies gate different things

**Location.** Task 6, Step 3 (search for `export const CLIP_OPS: readonly ClipOp[]`).

**The new declaration**, added to `src/lib/forge/types.ts`:

```ts
export type ClipOp = Extract<JobOp, "generate" | "decode" | "longform" | "bend">;
export const CLIP_OPS: readonly ClipOp[] = ["generate", "decode", "longform", "bend"] as const;
```

**What already exists.** M4 Task 8 exports the same constant from a different file —
`docs/superpowers/plans/2026-09-18-latent-forge-m4-prompt-sigma.md:3151`, in
`latent-forge/src/ui/prompt/targetBar.ts`:

```ts
export const CLIP_OPS = ["generate", "decode", "longform", "bend"] as const;
```

declared in that task's Produces line as `CLIP_OPS: readonly ["generate", "decode", "longform", "bend"]`,
and it is the one `TargetBar.svelte` renders the OP select from (m4:3244-3248,
`value={op ?? CLIP_OPS[0]}` … `{#each CLIP_OPS as o (o)}`).

After Task 6 there are two exported `CLIP_OPS`: M4's drives **what the operator can pick**, and
M9's drives **what a loaded project is allowed to contain** — Task 6, Step 8 adds
`isClipOp` to `validateProjectV2` from the `forge/types` copy:

```ts
function isClipOp(v: unknown): boolean {
  return v === undefined || v === null || (typeof v === "string" && (CLIP_OPS as readonly string[]).includes(v));
}
```

If the two ever diverge, an op the select offers becomes an op that makes a saved session refuse to
load with `not a v2 project: clips[0] is missing or the wrong type` — a failure mode with no
obvious cause. Task 6's own test (`every op is a JobOp the server's POST /forge/jobs already
accepts`) pins only the new copy.

**Smallest fix.** Declare `ClipOp` in `forge/types.ts` (it belongs there — `ForgeClip.op` uses it)
but not a second `CLIP_OPS`; instead re-export M4's, or move M4's list into `forge/types.ts` and
change `targetBar.ts` to `export { CLIP_OPS } from "../../lib/forge/types";` so both the select and
the validator read one array.

---

## F13 — not blocking — `peekOverlapParams` is documented as returning `OverlapParams | undefined`; M7 makes it non-nullable, so Writer A's fallback is dead code

**Location.** Task 1, Interfaces (search for `peekOverlapParams(key): OverlapParams | undefined`),
and Task 4, Step 4 (search for `OVERLAP_FALLBACK`).

**The claims.** Task 1:

> `.peekOverlapParams(key): OverlapParams | undefined` (**non-seeding**, M7 T3)

Task 4, in prose:

> `peekOverlapParams` is the **non-seeding** read (M7 T3), so a derived overlap whose params were
> never edited returns `undefined` and must fall back rather than seed the store from inside a
> submit path

and in code: `overlapParamsOf: (key) => arrangement.peekOverlapParams(key) ?? OVERLAP_FALLBACK()`.

**What M7 actually ships.** `docs/superpowers/plans/2026-09-23-latent-forge-m7-chains-mix-sessions.md:2460-2465`:

```ts
  peekOverlapParams(key: string): OverlapParams {
    return this.overlapStore[key] ?? {
      ...structuredClone(OVERLAP_DEFAULT),
      render: cloneRenderSettings(OVERLAP_DEFAULT.render),
    };
  }
```

and its Produces line (m7:2043-2046) says the same in prose: "the live entry if
`overlapParams`/`setOverlapParams` has already seeded one, **otherwise a fresh
`OVERLAP_DEFAULT`-shaped copy that is not stored**". It never returns `undefined`.

So Task 4's `?? OVERLAP_FALLBACK()` can never fire, and the `OVERLAP_FALLBACK` constant plus its
`structuredClone(OVERLAP_DEFAULT)` import exist for a case that does not occur. Under
`strictNullChecks` TypeScript will not error on a redundant `??`, so this ships quietly; it matters
because the *stated reason* for the fallback is wrong, and the next hand to read it may conclude
the non-seeding reader is unsafe and switch back to `overlapParams` — which is F5.

**Smallest fix.** Correct the two interface lines to `peekOverlapParams(key: string): OverlapParams`,
drop `OVERLAP_FALLBACK` and the `OVERLAP_DEFAULT` import from `mixdown.svelte.ts`, and write
`overlapParamsOf: (key) => arrangement.peekOverlapParams(key)`. (Keep the fallback only if F5's fix
introduces a nullable reader; it does not.)

---

## F14 — not blocking — three "exactly N keys" sentences in Task 1 are each one higher than both the assertion beneath them and the server

**Location.** Task 1, Step 1, `payloads.test.ts`. Three test titles.

| title says | the assertion lists | `validate_*` reads |
|---|---|---|
| `emits exactly the eight keys validate_inpaint reads` | `a, b, chroma_xfade, curve, pad_sec, region, render` = **7** | 7 |
| `emits exactly validate_commit's ten top-level keys` | `clips, decode_lanes, defaults, duration_sec, lanes, master, mix, overlaps, project_bpm` = **9** | 9 |
| `emits each clip with exactly validate_commit's eleven clip keys` | `a2a, audio, detune_cents, dur_sec, id, lane, loop, native_bpm, offset_sec, start_sec` = **10** | 10 |

**Evidence for the server side.**
`docs/superpowers/plans/2026-09-15-latent-forge-m8-commit-pipeline.md:2026-2034` — `validate_inpaint`
returns `{"a": …, "b": …, "region": …, "curve": …, "chroma_xfade": …, "render": …}` and reads
`payload.get("pad_sec", 8.0)`; that is seven inputs, and it accepts no `chain` or `ckpt_path`.
m8:1488-1491 — `validate_commit` returns
`{"project_bpm", "duration_sec", "defaults", "lanes", "clips", "overlaps", "mix", "master", "decode_lanes"}`,
nine. m8:1442-1448 — a clip is built from
`{"id", "lane", "start_sec", "offset_sec", "dur_sec", "loop", "audio", "native_bpm", "detune_cents", "a2a"}`,
ten.

Writer A's builders emit exactly the right sets, and the assertions are right, so nothing lands red.
It is worth fixing because these three sentences are the plan's stated contract with M8, and a later
reader reconciling "eleven" against a ten-key literal will assume a key was dropped — most plausibly
`render`, which on the wire belongs *inside* `a2a`, not beside it.

**Smallest fix.** Change "eight" → "seven", "ten top-level" → "nine top-level", "eleven clip keys" →
"ten clip keys".

---

## F15 — not blocking — every `ForgeClip` quoted in this plan is missing `previewAudio`, which M5 T10 made a required field

**Location.** The header ("Names inherited"), Task 1 Interfaces, Task 5 Interfaces, Task 6
Interfaces, Task 8 Interfaces. Search for `latentState; history: AudioRef[]`.

**The claims.** Four of the five spell the type as

> `interface ForgeClip { id; lane; start_sec; offset_sec; dur_sec; loop; audio: AudioRef;
> native_bpm; detune_cents; downbeats_sec; render; a2a; latentState; history: AudioRef[] }`

and the fifth (Task 8) makes it optional: `previewAudio?: AudioRef | null`.

**What the type really is.** `docs/superpowers/plans/2026-09-17-latent-forge-m5-timeline-fidelity.md:5213`
adds it as required, and M7 restates it (m7:147-149):

> - **`ForgeClip.previewAudio: AudioRef | null`** (M5 T10) — required on the type, **in-memory only**
>   (spec §9.2 "Not serialised", M1 Normative row…). Every `ForgeClip` this milestone constructs sets
>   it to `null`

M5's own construction sites do (`a2a: null, previewAudio: null,` — m7:3571). M9's own code depends on
it existing: Task 8's `replaceClipAudio` writes `c.previewAudio = null;`, and Task 6 Step 8 restores
`{ ...c, op: c.op ?? null, previewAudio: null }`.

Nothing lands red *today* because every clip literal in M9's tests ends with `} as ForgeClip;` — the
cast suppresses the missing-property error. That is the risk, not the reassurance: the next clip
helper written without the cast fails `npm run check` for a reason the plan's own interface quote
says is impossible. (`encodedAtSec?: number`, used by M5's `refreshStale` at m5:498-500, is missing
from the same quotes.)

**Smallest fix.** Add `previewAudio: AudioRef | null` (and `encodedAtSec?: number`) to the four
interface quotes, and change Task 8's `previewAudio?:` to `previewAudio:`.

---

## F16 — not blocking — three source attributions point at the wrong task, one at a task that does not exist

**Location and evidence** (each is a "this came from X" line that a writer would follow to look
something up):

1. **Task 6 Interfaces and Files:** "`latent-forge/src/lib/forge/projectSerializer.svelte.ts` (**M7 T8**)".
   M7 Task 8 is *The v1 → v2 project converter* (m7:3967), which owns `convertProjectV1.ts`.
   `projectSerializer.svelte.ts`, `isClip` (m7:5992) and `applyProject` (m7:6083-6087) are all in
   **M7 Task 9** (m7:4417-7099), which creates the file at m7:4617. Task 3 of this plan gets it right
   ("M7 T9"), so the two tasks disagree with each other as well as with M7.
2. **Task 6, Task 8 and Task 9 Interfaces:** "`latent-forge/src/lib/stores/settings.svelte.ts`
   (**M4 T2**)". M4 Task 2 is *Which samplers are offered…* (m4:551). The settings store,
   `settings.current`, `editable`, `patch`, `effectiveCfg` and `cfgDisabled` are all **M4 Task 1**
   (m4:158; its Produces line is m4:171). Task 5 of this plan is silent, Task 1 says "M4 T?".
3. **Task 8 Interfaces:** "`latent-forge/src/lib/presets/renderPresets.ts` (**M4 T13**)". **M4 has
   twelve tasks** — the last is `### Task 12: The SETTINGS PRESET select, and the milestone's layout
   spec` (m4:5478) — and that is the task that creates `renderPresets.ts` and `applyRenderPreset`
   (m4:5485, m4:5496). There is no M4 T13 to look in.
4. **Task 9 and Task 10 Interfaces:** "`latent-forge/src/lib/math/playback.ts` (**M5 T3**)". The file
   is created in the M5 task whose Files block is at m5:1154 and whose Produces line is m5:1179-1180;
   M5 T3 is the transport *store*. The module is right and the task number is not.

These cost nothing at runtime; they cost an implementer a search each, and #3 sends them to a task
that is not there. `isClip` in particular is module-private in M7 (`function isClip(c: unknown)`,
no `export`, m7:5992), so a writer who goes to the wrong task and then cannot find it may reasonably
conclude it must be written from scratch.

**Smallest fix.** M7 T8 → M7 T9 (two places in Task 6); M4 T2 → M4 T1 (three places); M4 T13 → M4 T12
(one place); M5 T3 → the task that creates `math/playback.ts` (two places).

---

## Addendum to F5 — where it lands red

F5 (the seeding `arrangement.overlapParams(key)` inside `$derived`) is not only a latent runtime
hazard; Task 6 ships a test that walks straight into it. Task 6, Step 14,
`previewRender.test.ts`:

```ts
  it("submits `inpaint` when an overlap is selected", async () => {
    const a = arrangement.addClip({ lane: 0, startSec: 0, durSec: 8, audio: REF });
    const b = arrangement.addClip({ lane: 0, startSec: 6, durSec: 8, audio: REF });
    const key = `${a.id}-${b.id}`;
    view.select({ kind: "overlap", key });
    …
    const { getByTestId } = render(PreviewContainer);
```

Those two clips have never had their overlap params opened, so `world`'s first derivation is the
first read of that key, which seeds `overlapStore` during a derivation —
`state_unsafe_mutation`, which M7 records as verified on Svelte 5.57.0. That moves F5 from
"BLOCKING on the running app" to "BLOCKING on Task 6 Step 15's own gate".

---

## Ranked summary

**BLOCKING (10).** Each would fail a gate the plan itself declares, or ships a control that cannot
work.

| # | one line | task |
|---|---|---|
| F1 | `generate` cap test throws "prompt is required", not `/184/` | T1 |
| F2 | superseded-job test never reaches `pollJob`; `await second` hangs | T1 |
| F3 | `drawPeaks(ctx, peaks, w, h)` — wrong signature, wrong first argument | T4 |
| F4 | MIXDOWN `▶` never plays; its scrub moves the arrangement playhead | T4 |
| F5 | seeding `overlapParams` inside `$derived` → `state_unsafe_mutation` | T6, T9 |
| F6 | `PAD_SEC` imported from `dispatch.ts`, which never exports it | T9 |
| F7 | five Playwright tests click a `▸ RENDER` disabled for want of a prompt | T10 |
| F8 | `workKey` edited "in `projectSerializer`"; it lives in `sessionController` | T3 |
| F9 | `<TopBar busy=… stepsLeft=…>` — props are `mixdownBusy`/`mixdownStepsLeft` | T4 |
| F10 | `meta.stages` test asserts a key the mocked path never sets | T4 |

**Not blocking (6).** Each is a false statement about a file this plan does not own, or a
redeclaration the plan's own rules forbid.

| # | one line | task |
|---|---|---|
| F11 | `targetKeyOf` duplicates M1's exported `targetKey` | T5 |
| F12 | second `CLIP_OPS`; M4's gates the select, M9's gates project validation | T6 |
| F13 | `peekOverlapParams` is non-nullable; the `?? OVERLAP_FALLBACK()` is dead | T1, T4 |
| F14 | three "exactly N keys" titles one higher than the assertion and the server | T1 |
| F15 | every `ForgeClip` quote omits the required `previewAudio` | header, T1, T5, T6, T8 |
| F16 | four wrong task attributions, one to an M4 task that does not exist | T6, T8, T9, T10 |

**Where the two writers actually disagree** (the lens this pass was given), in order of cost:
F5 (`overlapParams` vs `peekOverlapParams`), F3 (`drawPeaks` arity — Writer B diagnosed it and
filed it as an open question instead of fixing it), F4 (`playback` vs `previewPlayer` for the same
§4.5 rule), F6 (`PAD_SEC` assumed exported), F13 and F11 (one name, two spellings). The M8 payload
contract itself is in good shape: no `duration_sec` survives into any `render` or `defaults` object,
`generate` sends `duration`, `commit` carries top-level `duration_sec`, every LatCH request goes
through `chainRequest(...)` with the whole chain and two slots, `inpaint` correctly sends no chain
at all, and the `overlaps` list ⇄ `Record<key, OverlapParams>` mapping is built and tested. The
seven header rules hold; the seams do not.

