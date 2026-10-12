### Task 10: drops that carry their own length, the M9 Playwright spec, the gated legacy removal, and the self-review

**WHY.** Three loose ends, one gate and one review.

**1. Every drop onto a lane still invents four seconds.** M5 wrote the two drop handlers before
`lib/clips/lifecycle.ts` existed, and both hardcode a length. In `LaneHeader.svelte`:

```ts
    const c = arrangement.addClip({ lane: lane.index, startSec: playback.playheadSec, durSec: 4, audio: ref });
```

and in `Timeline.svelte`'s `onLaneBodyDrop`:

```ts
      const c = arrangement.addClip({ lane: laneIndex, startSec: atSec, durSec: 4, audio: ref });
```

Both call **M5's store directly**, which means three things are skipped that the OS-file branch three
lines below in the same function does not skip: the clip never gets `ensureAnalysis`, so `native_bpm`
stays `null` and CLIP BPM is blank; it never gets `scheduleStretch`, so it plays at its own tempo under a
project at another; and it is four seconds long whatever it actually is. After Tasks 7, 8 and 9 that is
the common case, not the corner: the preview drag handle, the MIXDOWN slot and the FILES rows all drop
`application/x-forge-ref` payloads, and a committed three-minute mix dropped on a lane becomes a 4 s clip.
Note the OS-file branch of `onLaneBodyDrop` is already correct (`durSec: uploaded.duration_sec`) — so the
same function is right about a dragged file and wrong about a dragged render.

**The length is not in the payload, and that is the actual design problem.** M5's drag MIME carries a bare
`JSON.stringify(AudioRef)` and nothing else (`parseForgeRefPayload` is `JSON.parse` then
`isAudioRef(parsed) ? parsed : null`). An `AudioRef` is an identity, not a description — there is nowhere
in `{kind:"render", job_id, file}` for a duration to live, and inventing a field on `AudioRef` would put a
transient measurement inside the thing that gets serialised into `ProjectV2`. So the length travels
**beside** the ref, on a second `DataTransfer` type, and every drag source that knows its own length sets
it. This is additive: a drop with no length still parses, and falls back.

Three sources know their length and one does not:
- the preview drag handle — Task 7 sets the ref; `entry.dur_sec` is right there;
- the MIXDOWN slot — Writer A T4's `draggable` handler; its entry has `dur_sec` too;
- FILES rows (M7 T6) — the `/forge/files` row carries `size` and `mtime`, **not a duration**.

So the fallback has to be real rather than decorative: when no length arrives, `lifecycle.addClip`
resolves it by decoding the audio through the same `Transport.preload` cache every other consumer reads
(`AudioBuffer.duration`), and only if *that* fails does the clip land at M5's four seconds with a log line
saying so. FILES drops therefore get their real length as well, which is what the brief asks for, without
FILES learning anything new.

**2. M9 has no end-to-end spec.** Every milestone since M1 has extended the Playwright suite over the mock
server, and M9 is the milestone where the client first submits jobs. The four behaviours that are only
observable end-to-end — a job's progress label appearing on the control that started it, a finished render
reaching HISTORY, a drag landing a real clip, and a 400 surfacing as a line rather than a console error —
are all cross-store sequences that a mounted-component test can fake its way through.

**3. The legacy removal W asked for is a gate, not a step.** `ModuleId` has seven members, five spec
modules plus `legacy-inspector` and `legacy-server`, and they are **real ids T9 mounts** and that
`MODULE_IDS` (`restoreUi`'s whitelist) persists. Deleting a persisted vocabulary member is not a tidy-up:
any stored UI state naming it stops round-tripping. W's instruction (log 2026-09-25 21:05) is to remove
`legacy-server`, and `legacy-inspector` too if its replacement is proven — **after the M7 and M9 Playwright
gates pass**. That ordering is the whole content of the instruction, so this task writes it as a gate with
an explicit stop, not as a step someone can run early.

**Recorded-fixture contract tests.** M7 T10's rule: skip when the fixture is missing or empty, never pass
against the hand-made mock. Task 8's `payloadSettings` is the one new function in Writer B's half whose
correctness is a claim about **real server payloads** — it is the inverse of Writer A's builders, and a
builder and its inverse can agree with each other while both being wrong about the wire. The recorded
`forge_job_*_done` fixtures carry real submitted payloads, so four `it.skipIf` rows pin the inverse against
them.

**Files:**
- Create: `latent-forge/tests/render.spec.ts` (Playwright),
  `latent-forge/src/lib/math/__tests__/dragPayload.test.ts`,
  `latent-forge/src/ui/timeline/__tests__/laneDropLength.test.ts`
- Modify: `latent-forge/src/lib/math/laneHeader.ts` (M5 T4 — the drag payload helpers),
  `latent-forge/src/lib/clips/lifecycle.ts` (M5 — resolve a missing length),
  `latent-forge/src/ui/timeline/LaneHeader.svelte` (M5 T4 — drop through `lifecycle`),
  `latent-forge/src/ui/timeline/Timeline.svelte` (M5 T6 — `onLaneBodyDrop` likewise),
  `latent-forge/src/ui/prompt/PreviewContainer.svelte` (Task 7 — set the length beside the ref),
  `latent-forge/src/ui/topbar/MixdownSlot.svelte` (Writer A T4 — the same),
  `latent-forge/src/lib/forge/__tests__/recordedContract.test.ts` (M7 T10, appended by Writer A T1 —
  four more `it.skipIf` rows)
- Delete, **only once the gate in Step 9 passes**: `latent-forge/src/ui/modules/LegacyServer.svelte` and
  its `legacy-server` entries; `LegacyInspector.svelte` and its `legacy-inspector` entries **only if** its
  replacement is proven.

No new HELP ids. **`strings.test.ts` stays at 119.**

**Interfaces** (everything consumed, with the task that produced it):

- From `latent-forge/src/lib/math/laneHeader.ts` (**M5 T4**): the drop MIME is
  `application/x-forge-ref` and its payload is a bare `JSON.stringify(AudioRef)`;
  `parseForgeRefPayload(raw: string): AudioRef | null` is `JSON.parse` then
  `isAudioRef(parsed) ? parsed : null`. **This task adds `FORGE_REF_MIME`, `FORGE_DUR_MIME`,
  `writeForgeDrag(dt, ref, durSec)` and `readForgeDrag(dt)`.**
- From `latent-forge/src/lib/clips/lifecycle.ts` (**M5**): `addClip(input: AddClipInput):
  Promise<AddClipOutcome>` where `interface AddClipInput { lane: 0|1|2|3; startSec: number; file?: File;
  ref?: AudioRef; durationSec?: number; nativeBpm?: number; downbeatsSec?: number[] }` and
  `interface AddClipOutcome { clip: ForgeClip; analyzeError: ForgeApiError | null }`. Verified body:
  `durSec = input.durationSec ?? 0`, then `arrangement.addClip({...})`, then `ensureAnalysis` **only when
  `input.nativeBpm == null && input.downbeatsSec == null`**, then `scheduleStretch`. Also the module-local
  lazy `decoder(): Transport | null` — *"Lazily built and never allowed to take the caller down with it:
  there is no Web Audio in the vitest environment"* — which this task reuses rather than building a second
  one. **This task changes `durSec = input.durationSec ?? 0` into a resolution.**
- From `latent-forge/src/lib/audio/transport.ts` (**M1 T15, re-homed by M5 T3**): `class Transport`,
  `preload(url: string): Promise<AudioBuffer>` (fetches + decodes, **cached by URL**), `readonly ctx`.
- From `latent-forge/src/lib/forge/api.ts` (**M1 T5**): `forgeApi.audioUrl(ref): string`,
  `forgeApi.upload(file)` → `{ok, ref, path, bytes, duration_sec, sample_rate, channels}`,
  `class ForgeApiError extends Error { readonly status: number }`.
- From `latent-forge/src/ui/timeline/LaneHeader.svelte` (**M5 T4**): props `{ lane: ForgeLane }`; its
  `onDrop(e: DragEvent)`, quoted in the WHY; `data-help={HELP.laneHeader}`.
- From `latent-forge/src/ui/timeline/Timeline.svelte` (**M5 T6**): `onLaneBodyDrop(e, laneIndex)`, quoted
  in the WHY, including its already-correct OS-file branch; `pxToSec(px, scrollSec, pxPerSec)`;
  `<canvas class="lane-canvas" data-region="lane-canvas">`, which is what every Playwright drag targets.
- From `latent-forge/src/lib/stores/arrangement.svelte.ts` (**M5 T1**): `addClip(args): ForgeClip`
  (the **store's**, which this task stops calling from the drop handlers), `clips`, `bpm`,
  `setScrollSec`, `pxPerSec`, `scrollSec`.
- From `latent-forge/src/lib/stores/transport.svelte.ts` (**M5 T3**): `playback.playheadSec`.
- From `latent-forge/src/lib/stores/view.svelte.ts` (**M1 T7**): `view.select(t)`, `view.activeLane`,
  `view.appendLog(text, level?)`.
- From Task 7 of this plan: `PreviewContainer.svelte`'s `onHandleDragStart` and its `entry` derived
  (`entry.dur_sec`). From Task 8: `previewActions.ts`'s `payloadSettings(op, payload)`. From Task 9:
  `masterSource`, and `mixPlaybackClips`.
- From `latent-forge/src/ui/topbar/MixdownSlot.svelte` (**M1 T10, wired by Writer A T4**): testids
  `mixdown-button`, `mixdown-canvas` (220×26), `mixdown-play`; the `draggable` handler that sets
  `application/x-forge-ref`; `mixdownLabel(busy, stepsLeft)` → `SAMPLING · N steps left`.
- From `latent-forge/src/ui/mix/MixSignalPath.svelte` (**M7 T5**): `data-signal-stage` and `data-lit` on
  each stage, `data-tab-body="mix"`, `HELP.signalPath`; Writer A T4 feeds a finished commit's
  `meta.stages` into it.
- From Writer A T5: `InlineError` — `data-testid="render-error"`, props `{ targetKey: string }`, rendering
  `jobs.lastError` when the key matches and nothing otherwise (its own tests assert
  `expect(queryByTestId("render-error")).toBeNull()` and
  `expect(getByTestId("render-error").textContent?.trim()).toBe("GPU busy — dash-77")`).
- From `latent-forge/src/lib/forge/__tests__/recordedContract.test.ts` (**M7 T10**, appended by
  **Writer A T1**): the module-local harness this task reuses verbatim — `recorded(name): Fixture | null`,
  `title(desc, ...names): string` (which appends `[SKIPPED: … a hand-made mock is not a contract]` /
  `… an empty recording proves nothing`), `serve(f)` (*"Answer every fetch with the recorded response,
  status and all"*), and `afterEach(() => vi.unstubAllGlobals())`.
- Fixtures (**M2 T15 / M8 T11**): `forge_job_generate_done`, `forge_job_a2a_clip_done`,
  `forge_job_inpaint_done`, `forge_job_commit_done`. The hand-made `handmade-forge_job_running.json`
  contradicts the Normative progress rule and **nothing here pins to it** (Fact 7).
- Playwright harness (**M1 T14/T15**, extended by M4 T12, M5, M6, M7 T5/T10): `tests/layout.spec.ts`,
  `tests/sampling.spec.ts`, `tests/timeline.spec.ts`, `tests/chains.spec.ts`,
  `tests/sessionsFilesOverlap.spec.ts`; the dev mock server; `page.goto("/")` then
  `await expect(page.locator('[data-region="topbar"]')).toBeVisible()`; the bottom-tab idiom
  `[data-testid=bottom-tab-<id>]`; the module idiom `[data-module-toggle="<id>"]` /
  `[data-module-body="<id>"]`; M5's `box(loc)` and `dropClip(page, lane, x)` helpers, copied verbatim as
  M7 T10 copied them.

**Produces:** `src/lib/math/laneHeader.ts` — `FORGE_REF_MIME = "application/x-forge-ref"`,
`FORGE_DUR_MIME = "application/x-forge-dur"`,
`writeForgeDrag(dt: DataTransfer, ref: AudioRef, durSec: number | null): void`,
`readForgeDrag(dt: DataTransfer | null): { ref: AudioRef; durationSec: number | null } | null`.
`tests/render.spec.ts` — 6 Playwright tests.

---

- [ ] **Step 1: Write the failing drag-payload test**

`latent-forge/src/lib/math/__tests__/dragPayload.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import type { AudioRef } from "../../forge/types";
import { FORGE_DUR_MIME, FORGE_REF_MIME, readForgeDrag, writeForgeDrag } from "../laneHeader";

const REF: AudioRef = { kind: "render", job_id: "gen-7", file: "out_00.wav" };

/** jsdom has no DataTransfer; this is the two methods the helpers touch. */
function dt(seed: Record<string, string> = {}): DataTransfer {
  const store = { ...seed };
  return {
    setData: (type: string, value: string) => { store[type] = value; },
    getData: (type: string) => store[type] ?? "",
  } as unknown as DataTransfer;
}

describe("the lane drag payload — the ref stays a bare AudioRef, the length rides beside it", () => {
  it("writes the ref exactly as M5 wrote it, so an old drop handler still parses it", () => {
    const d = dt();
    writeForgeDrag(d, REF, 96);
    expect(d.getData(FORGE_REF_MIME)).toBe(JSON.stringify(REF));
  });

  it("writes the length on its own MIME, never inside the ref", () => {
    const d = dt();
    writeForgeDrag(d, REF, 96);
    expect(d.getData(FORGE_DUR_MIME)).toBe("96");
    expect(JSON.parse(d.getData(FORGE_REF_MIME))).toEqual(REF);
  });

  it("omits the length rather than writing a fake one when the source does not know it", () => {
    const d = dt();
    writeForgeDrag(d, REF, null);
    expect(d.getData(FORGE_DUR_MIME)).toBe("");
    expect(readForgeDrag(d)).toEqual({ ref: REF, durationSec: null });
  });

  it("reads back both halves", () => {
    const d = dt();
    writeForgeDrag(d, REF, 12.5);
    expect(readForgeDrag(d)).toEqual({ ref: REF, durationSec: 12.5 });
  });

  it("is null for a drop that carries no ref at all — an OS file drag, say", () => {
    expect(readForgeDrag(dt())).toBeNull();
    expect(readForgeDrag(null)).toBeNull();
  });

  it("ignores a junk or non-positive length instead of passing it to addClip", () => {
    expect(readForgeDrag(dt({ [FORGE_REF_MIME]: JSON.stringify(REF), [FORGE_DUR_MIME]: "soon" })))
      .toEqual({ ref: REF, durationSec: null });
    expect(readForgeDrag(dt({ [FORGE_REF_MIME]: JSON.stringify(REF), [FORGE_DUR_MIME]: "0" })))
      .toEqual({ ref: REF, durationSec: null });
    expect(readForgeDrag(dt({ [FORGE_REF_MIME]: JSON.stringify(REF), [FORGE_DUR_MIME]: "-4" })))
      .toEqual({ ref: REF, durationSec: null });
  });

  it("is null for a ref-shaped payload that is not an AudioRef — M5's isAudioRef guard is kept", () => {
    expect(readForgeDrag(dt({ [FORGE_REF_MIME]: JSON.stringify({ kind: "nope" }) }))).toBeNull();
    expect(readForgeDrag(dt({ [FORGE_REF_MIME]: "{not json" }))).toBeNull();
  });
});
```

- [ ] **Step 2: Write the failing drop test**

`latent-forge/src/ui/timeline/__tests__/laneDropLength.test.ts`:

```ts
import { cleanup, fireEvent, render, waitFor } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AudioRef } from "../../../lib/forge/types";
import { FORGE_DUR_MIME, FORGE_REF_MIME } from "../../../lib/math/laneHeader";
import { arrangement } from "../../../lib/stores/arrangement.svelte";
import LaneHeader from "../LaneHeader.svelte";

const REF: AudioRef = { kind: "render", job_id: "gen-7", file: "out_00.wav" };

function dropEvent(data: Record<string, string>) {
  return {
    preventDefault: () => {},
    dataTransfer: { getData: (t: string) => data[t] ?? "", files: [] },
  } as unknown as DragEvent;
}

function analyzeOk(bpm: number | null) {
  return vi.fn(async () => new Response(
    JSON.stringify({
      ok: true, bpm, bpm_candidates: [], beats_sec: [], downbeats_sec: bpm === null ? [] : [0.5],
      duration_sec: 96, source: "librosa",
    }),
    { status: 200, headers: { "content-type": "application/json" } },
  ));
}

beforeEach(() => {
  for (const c of [...arrangement.clips]) arrangement.removeClip(c.id);
  arrangement.setBpm(120);
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("a drop onto a lane gets the render's real length, not M5's four seconds", () => {
  it("lands a clip as long as the dragged render says it is", async () => {
    vi.stubGlobal("fetch", analyzeOk(null));
    const { container } = render(LaneHeader, { props: { lane: arrangement.lanes[0] } });
    const slot = container.querySelector(".header") as HTMLElement;

    await fireEvent(slot, Object.assign(new Event("drop", { bubbles: true }), dropEvent({
      [FORGE_REF_MIME]: JSON.stringify(REF), [FORGE_DUR_MIME]: "96",
    })));

    await waitFor(() => expect(arrangement.clips).toHaveLength(1));
    expect(arrangement.clips[0].dur_sec).toBe(96);
    expect(arrangement.clips[0].audio).toEqual(REF);
  });

  it("runs the analysis the old path skipped, so CLIP BPM is no longer blank", async () => {
    vi.stubGlobal("fetch", analyzeOk(96));
    const { container } = render(LaneHeader, { props: { lane: arrangement.lanes[0] } });
    const slot = container.querySelector(".header") as HTMLElement;

    await fireEvent(slot, Object.assign(new Event("drop", { bubbles: true }), dropEvent({
      [FORGE_REF_MIME]: JSON.stringify(REF), [FORGE_DUR_MIME]: "96",
    })));

    await waitFor(() => expect(arrangement.clips[0]?.native_bpm).toBe(96));
    expect(arrangement.clips[0].downbeats_sec).toEqual([0.5]);
  });

  it("decodes the audio for its length when the drag source did not know one (a FILES row)", async () => {
    vi.stubGlobal("fetch", analyzeOk(null));
    const { container } = render(LaneHeader, { props: { lane: arrangement.lanes[0] } });
    const slot = container.querySelector(".header") as HTMLElement;

    await fireEvent(slot, Object.assign(new Event("drop", { bubbles: true }), dropEvent({
      [FORGE_REF_MIME]: JSON.stringify({ kind: "crop", crop_id: "000412" }),
    })));

    // No AudioContext in vitest, so the decode path returns null and the documented floor applies.
    await waitFor(() => expect(arrangement.clips).toHaveLength(1));
    expect(arrangement.clips[0].dur_sec).toBe(4);
  });

  it("ignores a drop with no forge ref, exactly as M5 did", async () => {
    const { container } = render(LaneHeader, { props: { lane: arrangement.lanes[0] } });
    const slot = container.querySelector(".header") as HTMLElement;
    await fireEvent(slot, Object.assign(new Event("drop", { bubbles: true }), dropEvent({})));
    expect(arrangement.clips).toHaveLength(0);
  });
});
```

- [ ] **Step 3: Run the two, expect failure**

```bash
cd latent-forge && npx vitest run src/lib/math/__tests__/dragPayload.test.ts \
  src/ui/timeline/__tests__/laneDropLength.test.ts
```

Expected: `"writeForgeDrag" is not exported by "src/lib/math/laneHeader.ts"`, and — once the helpers
exist — `expected 4 to be 96`, which is the bug this task is here for.

- [ ] **Step 4: Add the drag helpers**

In `latent-forge/src/lib/math/laneHeader.ts`, beside `parseForgeRefPayload`, which stays exactly as it is
(M5's drop handlers, M7's FILES rows and Task 7's handle all still call it):

```ts
export const FORGE_REF_MIME = "application/x-forge-ref";

/** The length rides BESIDE the ref, never inside it: an AudioRef is an identity that gets
 *  serialised into ProjectV2, and a measurement has no business in it. A drop with no length is
 *  still a valid drop (a FILES row does not know one) -- lifecycle.addClip resolves it. */
export const FORGE_DUR_MIME = "application/x-forge-dur";

export function writeForgeDrag(dt: DataTransfer, ref: AudioRef, durSec: number | null): void {
  dt.setData(FORGE_REF_MIME, JSON.stringify(ref));
  if (durSec !== null && Number.isFinite(durSec) && durSec > 0) {
    dt.setData(FORGE_DUR_MIME, String(durSec));
  }
}

export function readForgeDrag(
  dt: DataTransfer | null,
): { ref: AudioRef; durationSec: number | null } | null {
  if (!dt) return null;
  const ref = parseForgeRefPayload(dt.getData(FORGE_REF_MIME));
  if (!ref) return null;
  const raw = Number(dt.getData(FORGE_DUR_MIME));
  const durationSec = Number.isFinite(raw) && raw > 0 ? raw : null;
  return { ref, durationSec };
}
```

`Number("")` is `0`, not `NaN`, so the `raw > 0` half of that guard is what makes an absent length read as
`null` rather than as zero. Both halves are load-bearing and Step 1's junk-length test pins them.

- [ ] **Step 5: Resolve a missing length in `lifecycle.addClip`**

In `latent-forge/src/lib/clips/lifecycle.ts`, `durSec = input.durationSec ?? 0` becomes:

```ts
/** Spec §4.1: a clip is as long as its audio. A drag source that knows its length sends it; a FILES
 *  row does not, so the audio is decoded through the same URL-keyed cache every other consumer
 *  reads. The 4 s floor is M5's old hardcoded default, kept ONLY for the case where there is no
 *  Web Audio at all -- and it says so in the log rather than pretending to be a measurement. */
const DROP_FALLBACK_SEC = 4;

async function resolveDuration(ref: AudioRef, given: number | undefined): Promise<number> {
  if (given !== undefined && Number.isFinite(given) && given > 0) return given;
  const d = decoder();
  if (d) {
    try {
      return (await d.preload(forgeApi.audioUrl(ref))).duration;
    } catch {
      // fall through to the floor
    }
  }
  view.appendLog(`[clip] could not measure the dropped audio; using ${DROP_FALLBACK_SEC} s`, "error");
  return DROP_FALLBACK_SEC;
}
```

and in `addClip`, the `else if (input.ref)` branch becomes `ref = input.ref; durSec = await
resolveDuration(ref, input.durationSec);`. The `input.file` branch is untouched — an upload already
answers with `duration_sec` and must not be decoded twice.

`decoder()` is M5's own lazy accessor and returns `null` under vitest, which is why Step 2's third test
asserts the documented 4 s floor rather than a decoded length: that is the honest assertion for that
environment, and the Playwright test in Step 7 is what proves the decode path in a real browser.

- [ ] **Step 6: Route both drop handlers through `lifecycle`**

`LaneHeader.svelte`:

```ts
  async function onDrop(e: DragEvent) {
    e.preventDefault();
    const drag = readForgeDrag(e.dataTransfer ?? null);
    if (!drag) return;
    const { clip } = await addClip({
      lane: lane.index, startSec: playback.playheadSec, ref: drag.ref, durationSec: drag.durationSec ?? undefined,
    });
    view.activeLane = lane.index;
    view.select({ kind: "clip", id: clip.id });
  }
```

and the ref branch of `Timeline.svelte`'s `onLaneBodyDrop`:

```ts
    const drag = readForgeDrag(e.dataTransfer ?? null);
    if (drag) {
      const { clip } = await addClip({
        lane: laneIndex, startSec: atSec, ref: drag.ref, durationSec: drag.durationSec ?? undefined,
      });
      view.select({ kind: "clip", id: clip.id });
      return;
    }
```

with `import { addClip } from "../../lib/clips/lifecycle";` in both. `atSec` is read from the event
**before** the first `await` — it already is, in M5's code — because `e.currentTarget` is null after an
await and the bounding box would be measured against the wrong element.

The OS-file branch below it is left alone. Its `arrangement.addClip` could also become
`lifecycle.addClip({file})`, which would give it analyze and stretch too; that is a second behaviour
change in a function this task is already editing and it is **Open question 13**, not a silent extra.

Task 7's `onHandleDragStart` and Writer A T4's MIXDOWN drag handler each change one line, from
`e.dataTransfer?.setData("application/x-forge-ref", JSON.stringify(ref))` to
`writeForgeDrag(e.dataTransfer, ref, entry.dur_sec || null)` — the `|| null` for the same reason Task 8
used it: Task 7's `lengthLabel` already established that `dur_sec === 0` means *the result carried no
duration*, and `??` would pass that zero on as a length.

- [ ] **Step 7: Run the two, expect pass**

```bash
cd latent-forge && npx vitest run src/lib/math/__tests__/dragPayload.test.ts \
  src/ui/timeline/__tests__/laneDropLength.test.ts
```

Expected: `dragPayload.test.ts` `Tests  7 passed (7)`, `laneDropLength.test.ts` `Tests  4 passed (4)`.

- [ ] **Step 8: Append the recorded-fixture contract rows**

In `latent-forge/src/lib/forge/__tests__/recordedContract.test.ts`, reusing M7 T10's `recorded`, `title`
and `serve` exactly as Writer A T1's rows do, and adding nothing to the harness:

```ts
const GEN_DONE = recorded("forge_job_generate_done");
const A2A_DONE = recorded("forge_job_a2a_clip_done");
const INPAINT_DONE = recorded("forge_job_inpaint_done");
const COMMIT_DONE = recorded("forge_job_commit_done");

describe("USE SETTINGS against real submitted payloads (M2 T15 / M8 T11 fixtures)", () => {
  it.skipIf(!GEN_DONE)(title("a recorded generate payload reduces to settings plus a real LENGTH, and `duration` never leaks into the preset body", "forge_job_generate_done"), () => {
    const rec = GEN_DONE!.body as { op: JobOp; payload: unknown };
    const ps = payloadSettings(rec.op, rec.payload);
    expect(ps.body).not.toBeNull();
    expect("duration" in ps.body!).toBe(false);
    expect("duration_sec" in ps.body!).toBe(false);
    expect(ps.durationSec).toBeGreaterThan(0);
    // The reduction must be applicable, not merely non-null.
    const into = cloneRenderSettings(BASE_DEFAULTS);
    expect(applyRenderPreset(into, ps.body).applied.length).toBeGreaterThan(0);
  });

  it.skipIf(!A2A_DONE)(title("a recorded a2a_clip payload yields its nested render block and no length", "forge_job_a2a_clip_done"), () => {
    const rec = A2A_DONE!.body as { op: JobOp; payload: unknown };
    const ps = payloadSettings(rec.op, rec.payload);
    expect(ps.body).not.toBeNull();
    expect(ps.durationSec).toBeNull();
    expect(Object.keys(ps.body!)).toContain("steps");
  });

  it.skipIf(!INPAINT_DONE)(title("a recorded inpaint payload yields its nested render block, with the region supplying the span", "forge_job_inpaint_done"), () => {
    const rec = INPAINT_DONE!.body as { op: JobOp; payload: unknown };
    const ps = payloadSettings(rec.op, rec.payload);
    expect(ps.body).not.toBeNull();
    expect(ps.durationSec).toBeNull();
  });

  it.skipIf(!COMMIT_DONE)(title("a recorded commit payload offers a top-level duration_sec and no session-wide settings", "forge_job_commit_done"), () => {
    const rec = COMMIT_DONE!.body as { op: JobOp; payload: unknown };
    const ps = payloadSettings(rec.op, rec.payload);
    expect(ps.body).toBeNull();
    expect(ps.durationSec).toBeGreaterThan(0);
  });
});
```

These are **4 `it.skipIf`** rows. Until M2 T15 and M8 T11 have been run against a live server they report
as skipped with `title()`'s own reason text appended; they never pass against the hand-made mock, which is
the entire point of M7 T10's rule. `serve()` is not called — these read the fixture body directly rather
than through `fetch`, because `payloadSettings` is pure and the fixture *is* its input.

```bash
cd latent-forge && npx vitest run src/lib/forge/__tests__/recordedContract.test.ts
```

Expected with no recordings present: the four rows listed as **skipped**, each with
`[SKIPPED: … a hand-made mock is not a contract]`, and the rest of the file unchanged.

- [ ] **Step 9: Write the M9 Playwright spec**

`latent-forge/tests/render.spec.ts`:

```ts
import { expect, test, type Locator, type Page } from "@playwright/test";

// ---- M5's helpers (tests/timeline.spec.ts), copied verbatim as M7 T10 copied them ----
async function box(loc: Locator) {
  const b = await loc.boundingBox();
  if (!b) throw new Error("element has no bounding box");
  return b;
}
// ---------------------------------------------------------------------------------------

async function openPrompt(page: Page) {
  await page.locator('[data-testid="bottom-tab-prompt"]').click();
  return page.locator('[data-tab-body="prompt"]');
}

const CLIP = '.clip[role="button"]';

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await expect(page.locator('[data-region="topbar"]')).toBeVisible();
});

test("▸ RENDER submits, labels itself SAMPLING, and lands one HISTORY entry", async ({ page }) => {
  await openPrompt(page);
  const render = page.locator('[data-testid="preview-render"]');
  await expect(render).toBeEnabled();
  await expect(page.locator('[data-testid="preview-history"]')).toBeDisabled();

  await render.click();
  // §7.1: the control that started the job reads the count; the mock queues before it runs.
  await expect(render).toContainText(/SAMPLING · \d+ steps left/);
  await expect(render).toBeDisabled();

  const history = page.locator('[data-testid="preview-history"]');
  await expect(history).toBeEnabled({ timeout: 30_000 });
  await expect(history.locator("option")).toHaveCount(1);
  await expect(history.locator("option").first()).toContainText("GEN");
  await expect(render).toContainText("▸ RENDER");
});

test("the previewed render drags onto a lane as a clip of its own length, not four seconds", async ({ page }) => {
  await openPrompt(page);
  await page.locator('[data-testid="preview-render"]').click();
  await expect(page.locator('[data-testid="preview-history"]')).toBeEnabled({ timeout: 30_000 });

  const label = await page.locator('[data-testid="preview-length"]').textContent();
  const shown = Number((label ?? "").replace(/[^\d.]/g, ""));
  expect(shown).toBeGreaterThan(0);

  const canvas = page.locator('[data-region="lane-canvas"]').first();
  const target = await box(canvas);
  await page.locator('[data-testid="preview-drag-handle"]')
    .dragTo(canvas, { targetPosition: { x: 20, y: target.height / 2 } });

  await expect(page.locator(CLIP)).toHaveCount(1);
  // A 4 s clip at the mock's default zoom is visibly narrower than the render; the width is the
  // end-to-end evidence that the drop used the render's length.
  const clipBox = await box(page.locator(CLIP).first());
  expect(clipBox.width).toBeGreaterThan(4 * (target.width / 60));
});

test("MIXDOWN commits and lights the SIGNAL PATH", async ({ page }) => {
  // A commit needs a non-empty arrangement (validate_commit), so seed one from a render.
  await openPrompt(page);
  await page.locator('[data-testid="preview-render"]').click();
  await expect(page.locator('[data-testid="preview-history"]')).toBeEnabled({ timeout: 30_000 });
  const canvas = page.locator('[data-region="lane-canvas"]').first();
  await page.locator('[data-testid="preview-drag-handle"]')
    .dragTo(canvas, { targetPosition: { x: 20, y: (await box(canvas)).height / 2 } });
  await expect(page.locator(CLIP)).toHaveCount(1);

  const mixdown = page.locator('[data-testid="mixdown-button"]');
  await expect(mixdown).toBeEnabled();
  await mixdown.click();
  await expect(mixdown).toContainText(/SAMPLING · \d+ steps left/);
  await expect(mixdown).toContainText("▸ MIXDOWN", { timeout: 60_000 });

  await page.locator('[data-testid="bottom-tab-mix"]').click();
  const lit = page.locator('[data-tab-body="mix"] [data-signal-stage][data-lit="true"]');
  await expect(lit.first()).toBeVisible();
});

test("the PREVIEW/MIXDOWN A/B is present but unpressable until a commit exists", async ({ page }) => {
  const mix = page.locator('[data-testid="master-source-mixdown"]');
  // Task 9's decision: always in the DOM, disabled with a reason -- not hidden.
  await expect(mix).toBeVisible();
  await expect(mix).toBeDisabled();
  await expect(mix).toHaveAttribute("title", "nothing has been committed yet");
  await expect(page.locator('[data-region="preview-mixdown-toggle"]')).toHaveAttribute("data-help", /.+/);
});

test("a rejected render shows §9.7's inline error, and the next render clears it", async ({ page }) => {
  await page.route("**/forge/jobs", async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    await route.fulfill({
      status: 400, contentType: "application/json",
      body: JSON.stringify({ ok: false, error: "unknown render field(s): duration_sec" }),
    });
  });
  await openPrompt(page);
  await page.locator('[data-testid="preview-render"]').click();

  const err = page.locator('[data-testid="render-error"]');
  await expect(err).toBeVisible();
  await expect(err).toContainText("duration_sec");

  await page.unroute("**/forge/jobs");
  await page.locator('[data-testid="preview-render"]').click();
  await expect(err).toHaveCount(0);
});

test("USE SETTINGS copies the render's own settings into the pane; HISTORY alone does not", async ({ page }) => {
  const body = await openPrompt(page);
  const steps = body.getByLabel("STEPS");
  await steps.fill("31");
  await page.locator('[data-testid="preview-render"]').click();
  await expect(page.locator('[data-testid="preview-history"]')).toBeEnabled({ timeout: 30_000 });

  await steps.fill("12");
  // X15: selecting in HISTORY loads audio only.
  await page.locator('[data-testid="preview-history"]').selectOption({ index: 0 });
  await expect(steps).toHaveValue("12");

  await page.locator('[data-testid="preview-use-settings"]').click();
  await expect(steps).toHaveValue("31");
});
```

**6 Playwright tests.** `getByLabel("STEPS")` is M4 T9's own affordance — *"Each of the four numeric
inputs carries an `aria-label` matching the `<span class="label">` beside it… Task 12's Playwright spec
reaches CFG by `getByLabel`"* — so this spec reaches STEPS the way the existing suite already reaches CFG.
The 30 s and 60 s timeouts are for the mock's queue, not the GPU; they are generous on purpose because a
flaky gate is worse than a slow one, and Step 10 makes this spec a gate.

```bash
cd latent-forge && npx playwright test tests/render.spec.ts
```

Expected: `6 passed`.

- [ ] **Step 10: Run every gate**

```bash
cd latent-forge && npx vitest run && npm run check && npx playwright test
```

Expected: the whole vitest suite green with this task's `dragPayload.test.ts` 7 and
`laneDropLength.test.ts` 4, the four new `recordedContract.test.ts` rows **skipped**,
`strings.test.ts` still at 119; `npm run check` clean; and the full Playwright suite green —
M1's `layout.spec.ts`, M4's `sampling.spec.ts`, M5's `timeline.spec.ts`, M6's, M7's `chains.spec.ts` (4)
and `sessionsFilesOverlap.spec.ts` (6), plus this task's `render.spec.ts` (6).

**`Tests 11 passed (11)`** for this task's two new vitest files, plus **4 skipped** contract rows and
**6 Playwright tests**.

- [ ] **Step 11: Commit the wiring and the spec**

```bash
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M9 T10: drops onto a lane carry their own length and run analyze/stretch, plus the M9 Playwright spec over the mock (render, progress, history, drag-to-lane, MIXDOWN, A/B, inline error)"
```

---

- [ ] **Step 12: THE GATE — do not run Step 13 until every line here is true**

W's instruction (log 2026-09-25 21:05) is ordered, and the order is the instruction. Before removing
anything, confirm and record, in the commit message of Step 13:

1. `npx playwright test` is **green in full**, not just `render.spec.ts` — M7's `chains.spec.ts` and
   `sessionsFilesOverlap.spec.ts` included. M7's gate and M9's gate are both required; M7's is what
   proves the module system those ids live in still round-trips.
2. `npx vitest run` is green and `npm run check` is clean.
3. `legacy-server` is mounted by **no** module body that is still reachable, and nothing in
   `MODULE_IDS`-shaped persisted state depends on it being resolvable — check what `restoreUi` does with
   an id it does not recognise **before** deleting the id, not after. If `restoreUi` throws or blanks the
   layout on an unknown id, that is a bug to fix first and the removal waits for it.
4. For `legacy-inspector` **only**: its replacement is *proven*, meaning a named, passing test or
   Playwright assertion exercises the surface that replaced it. "M10 will cover it" is not proof, and
   neither is "nothing calls it" — a module the operator can still toggle is a surface.

**If item 4 is not true, remove `legacy-server` only and leave `legacy-inspector` in place**, saying so in
the commit. That is the explicitly allowed outcome, not a failure of this task.

- [ ] **Step 13: Remove the legacy modules (gated on Step 12)**

- Delete `LegacyServer.svelte` and every `legacy-server` entry: the `ModuleId` union member, its
  `MODULE_IDS` row, its `RightColumn`/module-registry mount, and any `HELP` id used only by it (if one is
  removed, `strings.test.ts`'s total moves off 119 and **that is the one place in this plan where it may**
  — state the new number in the commit message).
- The same for `legacy-inspector` **only if Step 12 item 4 held**.
- Keep a one-line migration in `restoreUi`: an unknown persisted module id is dropped silently rather than
  throwing, so a UI state saved before this commit still loads. Add one test for exactly that, in M7 T9's
  existing `restoreUi` suite, and say in the commit which file it went into.

```bash
cd latent-forge && npx vitest run && npm run check && npx playwright test
```

Expected: all three green, with the layout suite unchanged — the five spec modules are what the Playwright
specs assert on, and none of them names a legacy id.

```bash
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M9 T13: remove the legacy-server module now that the M7 and M9 Playwright gates pass; unknown persisted module ids are dropped rather than thrown on"
```

- [ ] **Step 14: Self-review against the spec**

Read each section and answer it in one line. This is a written artefact in the assembly, not a mental
check — an unanswered row is a finding.

**§4.2 (top bar / MIXDOWN slot).** Slot wired by Writer A T4: `busy`/`stepsLeft` passed,
`mixdownLabel(busy, stepsLeft)` shown, latest-mix waveform from `history.mixdown`, play/stop,
click-to-scrub, `draggable` with the ref — and, after this task, with its length beside it. **Check:**
does App actually pass `busy`/`stepsLeft` to `TopBar`? Fact 10 says the props exist on `TopBar` and
**App does not pass them**; if Writer A T4 did not close that, the label never counts and no test in
either half catches it, because both test the slot directly.

**§4.3 (timeline).** Drops now carry length, analysis and stretch. Loop, trim, move, detune, lane
mute/solo/gain all M5's and untouched. **Known gap:** the OS-file branch of `onLaneBodyDrop` still calls
the store directly and so still skips analyze/stretch (Open question 13).

**§4.5 (preview container).** RENDER (T6), HISTORY newest-first with tags and lengths (T7), waveform with
scrub and playhead (T7), play/stop mutually exclusive with the transport (T7), length label (T7), drag
handle (T7 + this task), USE SETTINGS (T8), REPLACE CLIP (T8). All eight controls M1 framed are live.
**Departure:** §4.5 says starting one player "stops" the other; Task 7 pauses the timeline instead, to
keep the playhead (Open question 2).

**§7 (render controls).** §7.1's four rows are one pure `renderRequest` (T6) with one blocked-reason
function (`renderBlock`, Writer A T5), used by `▸ RENDER` and by `▸ INPAINT OVERLAP` (T9) through the
shared `dispatchWorld`. Every render control disables while `jobs.busy`; the control that started the job
carries the count. §7.2/§7.3 are M5's and M7's. **Check at assembly:** the MIX-tab MIXDOWN buttons (Writer
A T4) and the top-bar slot must both disable on `jobs.busy`, not only on their own target key.

**§9.5 (raster border).** Writer A T2. Not exercised by Writer B's tests or by `render.spec.ts` — the
border is a canvas and `findByText` cannot see canvas content (M4's blocking finding), so it is asserted
through its driver's start/stop, not its pixels. **Noted as untested end-to-end on purpose.**

**§9.6 (transport and preview).** Task 9: MIXDOWN switches both the master strip and the transport to
`mix.wav`, at the same playhead, over a synthetic unmuted lane so the commit's own mute/solo/gain are not
applied twice. **Departure:** the toggle is always visible with MIXDOWN disabled, rather than appearing
only when a mix exists (Open question 10).

**§9.7 (error surfaces).** One inline line under the target bar from `jobs.lastError`, cleared by the next
render (Writer A T5); `GPU busy — <job_id>`; TERMINAL fixed in one place (Fact 8). Writer B's three
throwing paths — `renderRequest`'s `PayloadError` (T6), USE SETTINGS' job fetch (T8) and INPAINT OVERLAP's
submit (T9) — all land there and none throws out of a handler. `render.spec.ts` test 5 is the end-to-end
proof.

**Known incomplete** (carried into M10 / the assembly, not hidden in a step):

1. **No bend-op editor**, so `bendOps` is `[]` and `renderBlock` refuses `bend` (Task 6, Open question 3).
   The OP select offers it; choosing it produces an honest refusal rather than a render.
2. **No ARC editor for `longform`**: the target's prompt is used as the arc, which is what
   `_longform_impl` falls back to server-side. A real `0:a|45:b` grammar has no UI.
3. **`ForgeClip.history` is written and never read** (Task 8, Open question 9) — no UNDO for a REPLACE
   CLIP.
4. **The committed mix has no staleness indicator** (Task 9, Open question 12).
5. **`drawPeaks`' signature disagreement** between M5 T10's three-arg call and Writer A T4's four-arg one
   (Task 7, Open question 5) — one of the two is wrong and only the reconcile can say which.
6. **The recorded-contract rows are skipped** until M2 T15 and M8 T11 have been run against a live server.
   Four of them are Writer B's; they prove nothing today and are designed to say so out loud.
7. **`workKey` includes `renders`** (Fact 11), so history entries count as unsaved work. Writer A T3 was
   asked to state the decision; the assembly must check it was stated, not just implemented.
8. **The OS-file drop path** still bypasses `lifecycle` (Open question 13).

- [ ] **Step 15: Commit the review**

```bash
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M9 T10 review: self-review against §4.2/4.3/4.5/7/9.5-9.7 with the eight known-incomplete items and the four skipped contract rows recorded"
```

---

**Open questions raised by this task:**

13. **The OS-file branch of `onLaneBodyDrop` still calls `arrangement.addClip` directly.** Routing it
    through `lifecycle.addClip({file})` would give a dropped file analysis and stretch too, and would make
    one function have one path instead of two. It is a behaviour change to a path this task did not
    otherwise touch, so it is named rather than slipped in.
14. **`render.spec.ts` asserts the dropped clip's WIDTH, not its `dur_sec`.** Playwright can only see the
    DOM, and M5's `ClipBox` renders no length. A `data-dur-sec` attribute on `.clip` would make the
    assertion exact instead of geometric; that is a markup addition to M5's component and belongs to
    whoever owns `ClipBox`, not to M9's last task.
15. **Removing a `ModuleId` member changes a persisted vocabulary.** Step 13 adds the
    drop-unknown-ids migration, but nothing versions the UI state, so an id removed later has to repeat
    the same reasoning. A `ui.version` field would settle it once — M10's, if anyone's.
