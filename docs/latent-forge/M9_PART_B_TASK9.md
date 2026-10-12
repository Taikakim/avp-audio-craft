### Task 9: the master strip's PREVIEW/MIXDOWN A/B, and `▸ INPAINT OVERLAP`

**WHY.** Two controls were built as frames by earlier milestones with a note saying M9 would finish them,
and this is M9.

M5 built the A/B toggle and disabled half of it in the markup itself:

```svelte
    <div class="source-toggle" data-region="preview-mixdown-toggle">
      <button class:active={source === "preview"} data-testid="master-source-preview"
        onclick={() => (source = "preview")}>PREVIEW</button>
      <button class:active={source === "mixdown"} data-testid="master-source-mixdown"
        disabled
        title="MIXDOWN — wired to the committed mix in M9; nothing has been committed yet"
      >MIXDOWN</button>
    </div>
```

`source` is a component-local `let source = $state<"preview" | "mixdown">("preview")` that **nothing reads**:
M5's `draw()` always draws `masterBuffer`, its own audio-domain mix. So today the toggle is a pair of
radio buttons wired to a variable with no consequence, and the MIXDOWN half cannot be pressed at all.

M7 built `▸ INPAINT OVERLAP` the same way, and its own test says so out loud:

```ts
  it("the INPAINT OVERLAP button is present, enabled, and a no-op this milestone", async () => {
    …
    await fireEvent.click(btn);   // no throw, no network call -- M9 wires the job
  });
```

**Three things make this more than two `onclick`s.**

**1. `HELP.previewMixdownToggle` has existed since M1 and has never been attached to anything.** Its text is
not decoration — it is the only place the *point* of the A/B is written down:

> "A/B the audio-domain preview mix against the committed mixdown. PREVIEW is what the timeline sounds like
> now; MIXDOWN is what the server actually rendered. They should agree — where they do not, the commit
> changed something the preview cannot see."

That sentence is the acceptance criterion for this task. A toggle that switches only the picture is useless
for it: the operator has to *hear* both, which is why §9.6 puts the transport on `mix.wav` too and not just
the canvas.

**2. The visibility rule is a real fork, and it is decided here.** The spec says the toggle appears only when
the MIXDOWN slot holds a render; M5 built it always visible. **Shipped: always visible, with the MIXDOWN half
disabled and an honest title until `history.mixdown !== null`.** Three reasons, in order of weight:

- A control that appears and disappears moves the master strip's layout under the operator's cursor at the
  exact moment a commit lands — which is the moment they are most likely to be clicking in that row.
- The spec's intent is "do not offer an A/B that has no B". A disabled button with
  `"nothing has been committed yet"` satisfies that *and* answers the question the hidden version leaves
  open ("was there an A/B here? did I lose it?"). M5 already wrote almost exactly that sentence in its
  placeholder `title`; this task keeps it and drops the M9 promise from it.
- `master-source-mixdown` stays in the DOM unconditionally, so Task 10's Playwright spec and M7's can select
  it without a conditional wait, and a future regression that never enables it fails as a *disabled* check
  rather than as a flaky missing-element timeout.

**Open question 10** carries the departure to the assembly batch: this is a deliberate deviation from the
spec's wording and the reconcile should confirm it rather than discover it.

**3. The transport half has an import cycle in it, and Task 7 already established the way out.** §9.6 wants
the timeline transport playing `mix.wav` while MIXDOWN is selected. The natural implementation —
`masterSource.set()` telling `playback` to re-snapshot — makes `masterSource.svelte.ts` import
`transport.svelte.ts`, while `transport.svelte.ts` must import `masterSource.svelte.ts` to know which clip
list to play. That is exactly the cycle Task 7 hit between `previewPlayer` and `playback`, and it is solved
the same way: **the store holds only the choice, the component does the restart.** `masterSource` imports
`history` and nothing else; `transport.svelte.ts` imports `masterSource`; `MasterStrip.svelte`, which already
imports both, is what calls `playback.seek(playback.playheadSec)` after a switch. One direction of import,
no bus needed for a two-party case.

**Why `effective` is a getter and not an `$effect`.** The MIXDOWN choice can become invalid without anyone
touching the toggle: loading a session calls `history.restore(...)`, and a v2 file whose `mixdown` is `null`
leaves a strip sitting on a source that no longer exists. The obvious fix — an `$effect` that writes
`value = "preview"` when `available` goes false — is the `state_unsafe_mutation` trap in a different hat
(HANDOUT: writing state inside a `$derived` throws; an effect that writes what another derivation reads is
the same bug one frame later). So `value` records the operator's *choice* and is never rewritten, and a
getter `effective` gates it on availability. The choice survives a session load that had no mix and takes
effect again the moment a commit lands — which is the behaviour the operator expects and also the one that
needs no ordering guarantee at all.

**On the playhead.** Switching source does not move it. The mix is the same arrangement over the same
timebase, so second 40 of `mix.wav` is second 40 of the timeline; §9.6's same-playhead behaviour is what
makes the A/B worth anything (they have to be compared *at a moment*, not from the top). If the transport is
playing, the switch re-seeks to the current playhead so the other source is audible immediately, rather than
waiting for the operator to stop and start.

**On INPAINT OVERLAP.** It must not grow its own dispatch. Task 6 put §7.1's table in one pure function and
the fourth row of that table is *"overlap → `inpaint` preview of that overlap"* — the same row this button
is. So this task **extracts** Task 6's world construction out of `PreviewContainer.svelte` into
`dispatchWorld(target, heads)` and has both call sites use it. Two consequences worth stating: the overlap
dispatch is then covered by Task 6's existing `dispatch.test.ts` rows rather than by a second copy of them,
and a later change to §7.1 cannot be applied to one button and missed on the other.

`dispatchWorld` takes `heads` as a parameter and `OverlapInpaint.svelte` passes `{}`: `inpaintPayload`
(Writer A T1) builds `{a, b, region, curve, chroma_xfade, render, pad_sec}` and has **no `chain` field at
all**, so the LatCH head registry is not read on this path and fetching it here would be a network call whose
result is discarded. `PreviewContainer` keeps its own fetch, because its `generate`/`a2a_clip` rows do need it.

**Files:**
- Create: `latent-forge/src/lib/render/masterSource.svelte.ts`,
  `latent-forge/src/lib/render/__tests__/masterSource.test.ts`,
  `latent-forge/src/lib/render/dispatchWorld.ts`,
  `latent-forge/src/lib/math/__tests__/mixPlayback.test.ts`,
  `latent-forge/src/lib/stores/__tests__/transportMixSource.test.ts`,
  `latent-forge/src/ui/master/__tests__/masterSourceToggle.test.ts`,
  `latent-forge/src/ui/timeline/__tests__/overlapInpaintWired.test.ts`
- Modify: `latent-forge/src/lib/math/playback.ts` (M5 T3 — add `mixPlaybackClips`, `MIX_PLAYBACK_LANES`),
  `latent-forge/src/lib/stores/transport.svelte.ts` (M5 T3 — `snapshotClips`/`snapshotLanes` consult the
  source), `latent-forge/src/ui/master/MasterStrip.svelte` (M5 T10 — the toggle, the canvas, the HELP id),
  `latent-forge/src/ui/timeline/OverlapInpaint.svelte` (M7 T7 — `inpaint-overlap-button`),
  `latent-forge/src/ui/prompt/PreviewContainer.svelte` (Task 6 — its `world` literal moves to
  `dispatchWorld`)

No new HELP ids: `previewMixdownToggle` is M1's and has existed since M1 T14's `NEW_STRINGS`. **`strings.test.ts`
stays at 119**, the total Task 6 set.

**Interfaces** (everything consumed, with the task that produced it):

- From `latent-forge/src/lib/render/history.svelte.ts` (**Writer A T3**): `history.renders:
  RenderHistoryEntry[]`, `history.mixdown: number | null` (**an index into `renders`, always the newest
  commit** — the brief's pre-declaration), `history.refOf(e): AudioRef` →
  `{kind:"render", job_id: e.job_id, file: e.file}`, `history.restore(renders, mixdown, preview)`,
  `history.clear()`. `RenderHistoryEntry.dur_sec` is the mix's length in seconds.
- From `latent-forge/src/lib/forge/api.ts` (**M1 T5**): `forgeApi.audioUrl(ref: AudioRef): string` →
  `` `/forge/audio?ref=${encodeURIComponent(JSON.stringify(ref))}` `` — the same call M5's
  `toPlaybackClips` makes for every clip, so the mix is served by the same route as everything else and
  needs no new endpoint.
- From `latent-forge/src/lib/math/playback.ts` (**M5 T3**): `toPlaybackClips(clips: ForgeClip[]):
  PlaybackClip[]` (verified — `previewUrl: forgeApi.audioUrl(c.audio)`),
  `toPlaybackLanes(lanes: ForgeLane[]): PlaybackLane[]` (verified —
  `lanes.map((l) => ({ index: l.index, muted: l.muted, solo: l.solo, gain: l.gain }))`),
  `loopWrap(sec, loopOn, loopStartSec, loopEndSec)`. **This task adds `mixPlaybackClips` and
  `MIX_PLAYBACK_LANES`.**
- From `latent-forge/src/lib/audio/transport.ts` (**M1 T15, re-homed by M5 T3**):
  `interface PlaybackClip { id; laneIndex: number; startSec; durationSec; offsetSec; previewUrl: string | null }`,
  `interface PlaybackLane { index; muted; solo; gain }`, `interface PlaybackEngine { play(clips, lanes,
  fromSec); pause(); stop(); seek(sec, clips, lanes); … }`. Note `play` **filters on `previewUrl`** —
  `const withPreview = clips.filter((c): c is PlaybackClip & { previewUrl: string } => !!c.previewUrl)` —
  so a mix clip with a null URL is silently skipped rather than throwing, which is why
  `mixPlaybackClips` refuses to build a clip at all without a ref.
- From `latent-forge/src/lib/stores/transport.svelte.ts` (**M5 T3**): `class PlaybackStore` with the private
  `snapshotClips()` → `toPlaybackClips(arrangement.clips)` and `snapshotLanes()` →
  `toPlaybackLanes(arrangement.lanes)`, both called by `play()` and `seek()`; `playback.playing: boolean`,
  `playback.playheadSec: number`, `playback.play()`, `playback.pause()`, `playback.stop()`
  (`playheadSec = this.loopOn ? this.loopStartSec : 0` — Task 7's Open question 2), `playback.seek(sec)`,
  and the constructor's injectable `engine: PlaybackEngine = new Transport()`, which is what every test
  below drives.
- From `latent-forge/src/ui/master/MasterStrip.svelte` (**M5 T10**): the component. Its locals that this
  task touches: `masterBuffer: AudioBuffer | null`, `masterStale`, `busy`, `error`, the module-local
  `decoder = new Transport()` (**decode-only — "Not the playback engine, this only warms the same cache
  other consumers read"**), `refresh()`, `draw()`, `peakNow`/`dbfs`/`clipping` from `peakLevel(masterBuffer)`,
  and `let source = $state<"preview" | "mixdown">("preview")`, which this task **deletes** in favour of the
  store. Testids that must survive: `master-source-preview`, `master-source-mixdown`, the wrapper
  `data-region="preview-mixdown-toggle"`, `data-region="master-canvas"`.
- From `latent-forge/src/lib/audio/waveform.ts` (**M1 T15, re-homed by M5**): `computePeaks(buffer, columns)`,
  `drawPeaks(canvas, peaks, color)` — **three args, canvas first**, M5 T10's call (Task 7's Open question 5
  carries Writer A's four-arg variant to the reconcile; this task uses M5's, which is the one that exists),
  `peakLevel(buffer)`, `mixdownToBuffer(parts, sampleRate)`, `clipMarkColumns(peaks)` (M5 T10).
- From `latent-forge/src/lib/help/strings.ts` (**M1 T5 / M1 T14's `NEW_STRINGS`**): `HELP.previewMixdownToggle`,
  quoted in full in the WHY. **Pre-existing — this task attaches it, it does not add it.**
- From `latent-forge/src/lib/render/dispatch.ts` (**Task 6** of this plan): `renderRequest(target: Target,
  w: DispatchWorld): SubmitRequest`, `interface DispatchWorld`, `interface DispatchOverlap`,
  `PREVIEW_RENDER_IDLE_LABEL`, `renderLabel(busy, stepsLeft)`, `kindOf(op)`, `PAD_SEC`.
  **This task adds `dispatchWorld.ts` beside it**, holding the world *construction* Task 6 wrote inline in
  `PreviewContainer.svelte`.
- From `latent-forge/src/lib/render/renderBlock.ts` (**Writer A T5**): `renderBlock(target, state):
  string | null` and `interface RenderBlockState { busy; gpuBusyOther; settings; clip; clipOp; arcPrompt;
  bendOpCount; overlapSpanSec; padSec }`.
- From `latent-forge/src/lib/render/jobs.svelte.ts` (**Writer A T1**): `jobs.submit(req)`, `jobs.busy`,
  `jobs.active`, `jobs.stepsLeft`, `jobs.gpuBusyOther`, `jobs.lastError`.
- From `latent-forge/src/lib/render/payloads.ts` (**Writer A T1**): `class PayloadError extends Error`;
  `inpaintPayload(a: InpaintArgs)` builds `{a, b, region, curve, chroma_xfade, render, pad_sec}` — **no
  `chain` key**, which is why this task passes no heads on the overlap path.
- From `latent-forge/src/ui/timeline/OverlapInpaint.svelte` (**M7 T7**): the component; testids
  `inpaint-overlap-button` (text `▸ INPAINT OVERLAP`, `disabled={false}`, no handler),
  `overlap-chroma-xfade`, `overlap-override`, `overlap-steps`, `overlap-cfg`; it renders nothing at all for
  a selected overlap key that no longer exists (M7 critic pass 2 #5 — *"the body is gated on the overlap
  itself too"*), and that gate stays.
- From `latent-forge/src/lib/stores/arrangement.svelte.ts` (**M5 T1**): `arrangement.clips`,
  `arrangement.lanes`, `arrangement.overlaps` (derived `{key, lane, start_sec, end_sec, a_id, b_id}[]`),
  `arrangement.overlapParams(key): OverlapParams`, `arrangement.isAudible(lane)`.
- From `latent-forge/src/lib/stores/view.svelte.ts` (**M1 T7**): `view.selection`, `view.selectionKey`,
  `view.select(t)`, `view.appendLog(text, level?)`.
- From `latent-forge/src/lib/stores/settings.svelte.ts` (**M4 T2**): `settings.current(t)`,
  `settings.effectiveCfg(t)`, `settings.ckptPath`.
- From `latent-forge/src/lib/chains/latch.ts` (**M7 T1**): `interface LatchHeadInfo`,
  `fetchLatchHeads(): Promise<Record<string, LatchHeadInfo>>` (resolves `{}` on failure).

**Produces:** `src/lib/render/masterSource.svelte.ts` —
`type MasterSource = "preview" | "mixdown"`, `MIXDOWN_UNAVAILABLE_HINT = "nothing has been committed yet"`,
`class MasterSourceStore` with `value: MasterSource`, getters `available: boolean`,
`effective: MasterSource`, `entry: RenderHistoryEntry | null`, `url: string | null`, `durSec: number`, and
`set(v: MasterSource): void`; the singleton `masterSource`.
`src/lib/math/playback.ts` — `MIX_PLAYBACK_LANES: PlaybackLane[]`,
`mixPlaybackClips(url: string | null, durSec: number): PlaybackClip[]`.
`src/lib/render/dispatchWorld.ts` — `dispatchWorld(target: Target, heads: Record<string, LatchHeadInfo>):
DispatchWorld`.

---

- [ ] **Step 1: Write the failing store test**

`latent-forge/src/lib/render/__tests__/masterSource.test.ts`:

```ts
import { beforeEach, describe, expect, it } from "vitest";
import type { RenderHistoryEntry } from "../../forge/types";
import { history } from "../history.svelte";
import { masterSource, MIXDOWN_UNAVAILABLE_HINT } from "../masterSource.svelte";

function entry(p: Partial<RenderHistoryEntry> = {}): RenderHistoryEntry {
  return {
    job_id: "mix-1", forge_job_id: "forge-1", file: "mix.wav", label: "MIX 12:00:00",
    kind: "mix", dur_sec: 96, source_clip_id: null, created: 1, ...p,
  };
}

beforeEach(() => {
  history.clear();
  masterSource.set("preview");
});

describe("masterSource — the A/B choice, and the availability it is gated on", () => {
  it("starts on PREVIEW with no mix available", () => {
    expect(masterSource.value).toBe("preview");
    expect(masterSource.available).toBe(false);
    expect(masterSource.url).toBeNull();
  });

  it("is available exactly when history.mixdown is not null", () => {
    history.add(entry({ kind: "gen" }));
    expect(masterSource.available).toBe(false);   // a render is not a mixdown
    history.add(entry());
    history.mixdown = history.renders.length - 1;
    expect(masterSource.available).toBe(true);
  });

  it("resolves the mix through the same /forge/audio route as every clip", () => {
    history.add(entry());
    history.mixdown = 0;
    expect(masterSource.url).toContain("/forge/audio?ref=");
    expect(masterSource.url).toContain("mix.wav");
    expect(masterSource.durSec).toBe(96);
  });

  it("records the operator's choice even while no mix exists", () => {
    masterSource.set("mixdown");
    expect(masterSource.value).toBe("mixdown");
  });

  it("but plays PREVIEW until one does — `effective` gates, `value` remembers", () => {
    masterSource.set("mixdown");
    expect(masterSource.effective).toBe("preview");
    history.add(entry());
    history.mixdown = 0;
    expect(masterSource.effective).toBe("mixdown");
  });

  it("falls back the moment a session load leaves no mix, without any effect running", () => {
    history.add(entry());
    history.mixdown = 0;
    masterSource.set("mixdown");
    expect(masterSource.effective).toBe("mixdown");
    history.restore([], null, null);
    expect(masterSource.effective).toBe("preview");
    expect(masterSource.value).toBe("mixdown");   // the choice is never silently rewritten
  });

  it("names the reason the MIXDOWN half is unpressable, in the words the button shows", () => {
    expect(MIXDOWN_UNAVAILABLE_HINT).toBe("nothing has been committed yet");
  });
});
```

- [ ] **Step 2: Write the failing pure playback test**

`latent-forge/src/lib/math/__tests__/mixPlayback.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { MIX_PLAYBACK_LANES, mixPlaybackClips } from "../playback";

const URL = "/forge/audio?ref=%7B%22kind%22%3A%22render%22%7D";

describe("mixPlaybackClips — one file, from zero, over one audible lane", () => {
  it("is a single clip starting at 0 with no offset", () => {
    expect(mixPlaybackClips(URL, 96)).toEqual([
      { id: "mixdown", laneIndex: 0, startSec: 0, durationSec: 96, offsetSec: 0, previewUrl: URL },
    ]);
  });

  it("is empty without a url — the engine would silently skip it anyway", () => {
    expect(mixPlaybackClips(null, 96)).toEqual([]);
  });

  it("floors a missing or zero duration at 0 rather than emitting a negative clip", () => {
    expect(mixPlaybackClips(URL, 0)[0].durationSec).toBe(0);
    expect(mixPlaybackClips(URL, -5)[0].durationSec).toBe(0);
  });

  it("plays over a synthetic lane, so a muted or un-soloed lane 0 cannot silence the mix", () => {
    expect(MIX_PLAYBACK_LANES).toEqual([{ index: 0, muted: false, solo: false, gain: 1 }]);
  });
});
```

- [ ] **Step 3: Write the failing transport test**

`latent-forge/src/lib/stores/__tests__/transportMixSource.test.ts`:

```ts
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { PlaybackClip, PlaybackEngine, PlaybackLane } from "../../audio/transport";
import type { AudioRef, RenderHistoryEntry } from "../../forge/types";
import { history } from "../../render/history.svelte";
import { masterSource } from "../../render/masterSource.svelte";
import { arrangement } from "../arrangement.svelte";
import { PlaybackStore } from "../transport.svelte";

const REF: AudioRef = { kind: "upload", sha256: "a".repeat(64) };

function fakeEngine() {
  const calls: { clips: PlaybackClip[]; lanes: PlaybackLane[]; fromSec: number }[] = [];
  const engine: PlaybackEngine = {
    play: vi.fn(async (clips, lanes, fromSec) => { calls.push({ clips, lanes, fromSec }); }),
    pause: vi.fn(), stop: vi.fn(),
    seek: vi.fn(async (sec, clips, lanes) => { calls.push({ clips, lanes, fromSec: sec }); }),
    preload: vi.fn(async () => ({}) as AudioBuffer),
    invalidate: vi.fn(), scrub: vi.fn(), stopScrub: vi.fn(),
    currentTimeSec: 0, playing: false,
  } as unknown as PlaybackEngine;
  return { engine, calls };
}

function mixEntry(): RenderHistoryEntry {
  return {
    job_id: "mix-1", forge_job_id: "forge-1", file: "mix.wav", label: "MIX 12:00:00",
    kind: "mix", dur_sec: 96, source_clip_id: null, created: 1,
  };
}

beforeEach(() => {
  history.clear();
  masterSource.set("preview");
  for (const c of [...arrangement.clips]) arrangement.removeClip(c.id);
});

describe("the timeline transport follows the A/B toggle (spec §9.6)", () => {
  it("plays the arrangement while PREVIEW is selected", async () => {
    arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: REF });
    const { engine, calls } = fakeEngine();
    await new PlaybackStore(engine).play();
    expect(calls[0].clips).toHaveLength(1);
    expect(calls[0].clips[0].id).not.toBe("mixdown");
  });

  it("plays mix.wav, and only mix.wav, while MIXDOWN is selected", async () => {
    arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: REF });
    history.add(mixEntry());
    history.mixdown = 0;
    masterSource.set("mixdown");

    const { engine, calls } = fakeEngine();
    await new PlaybackStore(engine).play();
    expect(calls[0].clips).toHaveLength(1);
    expect(calls[0].clips[0].id).toBe("mixdown");
    expect(calls[0].clips[0].previewUrl).toContain("mix.wav");
  });

  it("is not silenced by a muted lane 0 — the commit already applied the mute", async () => {
    arrangement.setLaneMuted(0, true);
    history.add(mixEntry());
    history.mixdown = 0;
    masterSource.set("mixdown");

    const { engine, calls } = fakeEngine();
    await new PlaybackStore(engine).play();
    expect(calls[0].lanes).toEqual([{ index: 0, muted: false, solo: false, gain: 1 }]);
  });

  it("re-snapshots on a seek, so switching source mid-play swaps what is heard", async () => {
    history.add(mixEntry());
    history.mixdown = 0;
    const store = new PlaybackStore(fakeEngine().engine);
    const { engine, calls } = fakeEngine();
    void store;
    const playing = new PlaybackStore(engine);
    await playing.play();
    masterSource.set("mixdown");
    await playing.seek(40);
    expect(calls[calls.length - 1].clips[0].id).toBe("mixdown");
    expect(calls[calls.length - 1].fromSec).toBe(40);
  });
});
```

`PlaybackStore` is exported alongside the `playback` singleton by M5 T3 (its constructor takes the engine
for exactly this reason); if M5 exported only the singleton, export the class in this task and say so in the
commit — the singleton cannot be given a fake engine and every one of these assertions depends on that.

- [ ] **Step 4: Run the three, expect failure**

```bash
cd latent-forge && npx vitest run src/lib/render/__tests__/masterSource.test.ts \
  src/lib/math/__tests__/mixPlayback.test.ts src/lib/stores/__tests__/transportMixSource.test.ts
```

Expected: `Failed to resolve import "../masterSource.svelte"`, and
`"mixPlaybackClips" is not exported by "src/lib/math/playback.ts"`.

- [ ] **Step 5: Write `masterSource.svelte.ts`**

```ts
import { forgeApi } from "../forge/api";
import type { RenderHistoryEntry } from "../forge/types";
import { history } from "./history.svelte";

export type MasterSource = "preview" | "mixdown";

/** M5 wrote almost this sentence as the placeholder title on the disabled button; it is kept, minus
 *  the promise about M9, because the operator's question is "why can't I press this". */
export const MIXDOWN_UNAVAILABLE_HINT = "nothing has been committed yet";

class MasterSourceStore {
  /** What the operator chose. Never rewritten by anything but the operator: a session load that has
   *  no mix must not silently un-choose MIXDOWN, and an $effect that did would be writing state
   *  another derivation reads. `effective` does the gating instead. */
  value = $state<MasterSource>("preview");

  get entry(): RenderHistoryEntry | null {
    return history.mixdown === null ? null : history.renders[history.mixdown] ?? null;
  }

  get available(): boolean {
    return this.entry !== null;
  }

  /** What is actually played and drawn. */
  get effective(): MasterSource {
    return this.value === "mixdown" && this.available ? "mixdown" : "preview";
  }

  get url(): string | null {
    const e = this.entry;
    return e === null ? null : forgeApi.audioUrl(history.refOf(e));
  }

  get durSec(): number {
    return this.entry?.dur_sec ?? 0;
  }

  set(v: MasterSource): void {
    this.value = v;
  }
}

export const masterSource = new MasterSourceStore();
```

`history.mixdown` is read through the store's own getter rather than copied into a field, so nothing here
can go stale against `history.restore(...)`. Note `history.renders[history.mixdown] ?? null`: a v2 project
file can carry a `mixdown` index that no longer addresses a render (Writer A T3 validates the shape, not the
relationship), and an out-of-range index must read as "no mix", not as `undefined` flowing into `refOf`.

- [ ] **Step 6: Add the two pure helpers to `playback.ts`**

```ts
/** §9.6's MIXDOWN source. The commit already applied every lane's mute, solo and gain, so replaying
 *  the arrangement's lane state over the finished file would apply them a second time. */
export const MIX_PLAYBACK_LANES: PlaybackLane[] = [{ index: 0, muted: false, solo: false, gain: 1 }];

export function mixPlaybackClips(url: string | null, durSec: number): PlaybackClip[] {
  if (url === null) return [];
  return [{
    id: "mixdown",
    laneIndex: 0,
    startSec: 0,
    durationSec: Math.max(0, durSec),
    offsetSec: 0,
    previewUrl: url,
  }];
}
```

- [ ] **Step 7: Route the transport through the toggle**

In `latent-forge/src/lib/stores/transport.svelte.ts`, the two private snapshots — and only these two, so
`play`, `seek` and everything M5 built on them follow automatically:

```ts
  private snapshotClips() {
    if (masterSource.effective === "mixdown") {
      return mixPlaybackClips(masterSource.url, masterSource.durSec);
    }
    return toPlaybackClips(arrangement.clips);
  }

  private snapshotLanes() {
    if (masterSource.effective === "mixdown") return MIX_PLAYBACK_LANES;
    return toPlaybackLanes(arrangement.lanes);
  }
```

with `import { masterSource } from "../render/masterSource.svelte";` and the two new names from
`../math/playback`. This is the only edit to M5's store and it adds no field to it: the source of truth stays
in one place and the transport reads it, which is what keeps the import graph one-directional (WHY item 3).

- [ ] **Step 8: Run the three, expect pass**

```bash
cd latent-forge && npx vitest run src/lib/render/__tests__/masterSource.test.ts \
  src/lib/math/__tests__/mixPlayback.test.ts src/lib/stores/__tests__/transportMixSource.test.ts
```

Expected: `masterSource.test.ts` `Tests  7 passed (7)`, `mixPlayback.test.ts` `Tests  4 passed (4)`,
`transportMixSource.test.ts` `Tests  4 passed (4)`.

- [ ] **Step 9: Write the failing MasterStrip test**

`latent-forge/src/ui/master/__tests__/masterSourceToggle.test.ts`:

```ts
import { cleanup, fireEvent, render, waitFor } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { RenderHistoryEntry } from "../../../lib/forge/types";
import { history } from "../../../lib/render/history.svelte";
import { masterSource } from "../../../lib/render/masterSource.svelte";
import { playback } from "../../../lib/stores/transport.svelte";
import MasterStrip from "../MasterStrip.svelte";

function mixEntry(): RenderHistoryEntry {
  return {
    job_id: "mix-1", forge_job_id: "forge-1", file: "mix.wav", label: "MIX 12:00:00",
    kind: "mix", dur_sec: 96, source_clip_id: null, created: 1,
  };
}

beforeEach(() => {
  history.clear();
  masterSource.set("preview");
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("the master strip's PREVIEW/MIXDOWN A/B", () => {
  it("is always in the DOM, with MIXDOWN disabled until something is committed", () => {
    const { getByTestId } = render(MasterStrip);
    const mix = getByTestId("master-source-mixdown") as HTMLButtonElement;
    expect(mix).toBeTruthy();
    expect(mix.disabled).toBe(true);
    expect(mix.title).toBe("nothing has been committed yet");
  });

  it("enables MIXDOWN the moment history.mixdown points at a render", async () => {
    const { getByTestId } = render(MasterStrip);
    history.add(mixEntry());
    history.mixdown = 0;
    await waitFor(() =>
      expect((getByTestId("master-source-mixdown") as HTMLButtonElement).disabled).toBe(false));
    expect((getByTestId("master-source-mixdown") as HTMLButtonElement).title).toBe("");
  });

  it("switches the store, and marks the pressed half active", async () => {
    history.add(mixEntry());
    history.mixdown = 0;
    const { getByTestId } = render(MasterStrip);

    await fireEvent.click(getByTestId("master-source-mixdown"));
    expect(masterSource.effective).toBe("mixdown");
    await waitFor(() =>
      expect(getByTestId("master-source-mixdown").classList.contains("active")).toBe(true));
    expect(getByTestId("master-source-preview").classList.contains("active")).toBe(false);

    await fireEvent.click(getByTestId("master-source-preview"));
    expect(masterSource.effective).toBe("preview");
  });

  it("re-seeks a playing transport to the same playhead, so the A/B is heard at one moment", async () => {
    history.add(mixEntry());
    history.mixdown = 0;
    playback.playing = true;
    playback.playheadSec = 40;
    const seek = vi.spyOn(playback, "seek").mockResolvedValue(undefined);

    const { getByTestId } = render(MasterStrip);
    await fireEvent.click(getByTestId("master-source-mixdown"));
    expect(seek).toHaveBeenCalledWith(40);
    playback.playing = false;
  });

  it("does not touch the transport when it is not playing", async () => {
    history.add(mixEntry());
    history.mixdown = 0;
    playback.playing = false;
    const seek = vi.spyOn(playback, "seek").mockResolvedValue(undefined);

    const { getByTestId } = render(MasterStrip);
    await fireEvent.click(getByTestId("master-source-mixdown"));
    expect(seek).not.toHaveBeenCalled();
  });

  it("finally attaches HELP.previewMixdownToggle, which M1 wrote and nothing has ever used", () => {
    const { container } = render(MasterStrip);
    const toggle = container.querySelector('[data-region="preview-mixdown-toggle"]');
    expect(toggle?.getAttribute("data-help")).toContain("A/B the audio-domain preview mix");
  });
});
```

- [ ] **Step 10: Run it, expect failure**

```bash
cd latent-forge && npx vitest run src/ui/master/__tests__/masterSourceToggle.test.ts
```

Expected: the first test fails on the title (M5's placeholder still promises M9), the enable test fails
because the button is `disabled` unconditionally in the markup, and the HELP test fails on `null` — the
attribute does not exist.

- [ ] **Step 11: Wire `MasterStrip.svelte`**

Delete `let source = $state<"preview" | "mixdown">("preview");` and add:

```ts
  import { HELP } from "../../lib/help/strings";
  import { masterSource, MIXDOWN_UNAVAILABLE_HINT } from "../../lib/render/masterSource.svelte";
  import { playback } from "../../lib/stores/transport.svelte";

  /** The mix as a buffer, decoded through the same cache M5's preview mix uses. */
  let mixBuffer = $state<AudioBuffer | null>(null);

  const showing = $derived(masterSource.effective);
  const shownBuffer = $derived(showing === "mixdown" ? mixBuffer : masterBuffer);

  async function chooseSource(v: "preview" | "mixdown") {
    masterSource.set(v);
    // The two sources share a timebase, so the comparison happens at a moment, not from the top
    // (§9.6). A seek re-snapshots the clip list, which is what actually swaps what is heard.
    if (playback.playing) await playback.seek(playback.playheadSec);
  }

  $effect(() => {
    // Decode the committed mix when there is one. Reads masterSource.url; writes only mixBuffer,
    // which no derivation in this effect reads -- never write what you read (state_unsafe_mutation).
    const url = masterSource.url;
    if (url === null) {
      mixBuffer = null;
      return;
    }
    let cancelled = false;
    void decoder.preload(url)
      .then((b) => { if (!cancelled) mixBuffer = b; })
      .catch((e) => { if (!cancelled) error = e instanceof Error ? e.message : String(e); });
    return () => { cancelled = true; };
  });
```

`draw()` changes one line — `computePeaks(shownBuffer, cols)` and its `if (!shownBuffer)` guard in place of
`masterBuffer` — and the `$effect` that redraws voids `shownBuffer` instead. `peakNow` likewise reads
`shownBuffer`, so the dBFS readout and the CLIPPING flag describe whichever source is on screen; that is the
whole point of the A/B, since a commit that clips where the preview did not is exactly the disagreement
`HELP.previewMixdownToggle` is about.

The markup, with M5's testids, classes and `data-region` untouched:

```svelte
    <div class="source-toggle" data-region="preview-mixdown-toggle" data-help={HELP.previewMixdownToggle}>
      <button
        class:active={showing === "preview"}
        data-testid="master-source-preview"
        onclick={() => void chooseSource("preview")}
      >PREVIEW</button>
      <button
        class:active={showing === "mixdown"}
        data-testid="master-source-mixdown"
        disabled={!masterSource.available}
        title={masterSource.available ? "" : MIXDOWN_UNAVAILABLE_HINT}
        onclick={() => void chooseSource("mixdown")}
      >MIXDOWN</button>
    </div>
```

M5's `▸ MIX PREVIEW` button, the stale dot and the envelope overlay are all untouched. The stale dot keeps
describing the *preview* mix, which is correct — a committed mix has its own staleness, and Writer A T4's
SIGNAL PATH reconcile is where that lives.

- [ ] **Step 12: Run it, expect pass**

```bash
cd latent-forge && npx vitest run src/ui/master/__tests__/masterSourceToggle.test.ts
```

Expected: `Test Files  1 passed (1)` / `Tests  6 passed (6)`.

- [ ] **Step 13: Extract `dispatchWorld` and write the failing OVERLAP test**

`latent-forge/src/lib/render/dispatchWorld.ts` is Task 6's `$derived.by` body, lifted verbatim into a
function:

```ts
import { fetchLatchHeads, type LatchHeadInfo } from "../chains/latch";
import type { Target } from "../forge/types";
import { arrangement } from "../stores/arrangement.svelte";
import { settings } from "../stores/settings.svelte";
import { PAD_SEC, type DispatchWorld } from "./dispatch";

/** Task 6 built this inline in PreviewContainer; Task 9 needs the identical world for
 *  `▸ INPAINT OVERLAP`, and two copies of §7.1's inputs would drift on the first spec change.
 *  Called from inside a $derived.by, every store read below is still tracked -- the reads happen
 *  during derivation, and moving them behind a plain function call does not change that. */
export function dispatchWorld(
  target: Target,
  heads: Record<string, LatchHeadInfo>,
): DispatchWorld {
  const clip = target.kind === "clip" ? arrangement.clips.find((c) => c.id === target.id) ?? null : null;
  const overlap = target.kind === "overlap"
    ? arrangement.overlaps.find((o) => o.key === target.key) ?? null
    : null;
  return {
    settings: settings.current(target),
    cfgScale: settings.effectiveCfg(target),
    clip,
    lane: clip ? arrangement.lanes[clip.lane] : null,
    heads,
    ckptPath: settings.ckptPath,
    overlap,
    overlapParams: overlap ? arrangement.overlapParams(overlap.key) : null,
    clipById: (id: string) => arrangement.clips.find((c) => c.id === id) ?? null,
    arcPrompt: settings.current(target).prompt,
    bendOps: [] as unknown[],
    padSec: PAD_SEC,
  };
}

export { fetchLatchHeads };
```

and `PreviewContainer.svelte`'s `const world = $derived.by(() => ({ … }))` becomes
`const world = $derived.by(() => dispatchWorld(target, heads))`, deleting the literal. Nothing else in Task 6
changes and `dispatch.test.ts` is untouched — it tests `renderRequest`, which still receives the same object.

`latent-forge/src/ui/timeline/__tests__/overlapInpaintWired.test.ts`:

```ts
import { cleanup, fireEvent, render, waitFor } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AudioRef } from "../../../lib/forge/types";
import { jobs } from "../../../lib/render/jobs.svelte";
import { arrangement } from "../../../lib/stores/arrangement.svelte";
import { view } from "../../../lib/stores/view.svelte";
import OverlapInpaint from "../OverlapInpaint.svelte";

const REF: AudioRef = { kind: "upload", sha256: "a".repeat(64) };

function seedOverlap(): string {
  const a = arrangement.addClip({ lane: 0, startSec: 0, durSec: 8, audio: REF });
  const b = arrangement.addClip({ lane: 0, startSec: 6, durSec: 8, audio: REF });
  const key = arrangement.overlaps[0].key;
  view.select({ kind: "overlap", key });
  return `${a.id}-${b.id}-${key}`.slice(0, 0) + key;
}

beforeEach(() => {
  for (const c of [...arrangement.clips]) arrangement.removeClip(c.id);
  jobs.active = null;
  jobs.gpuBusyOther = null;
  jobs.lastError = null;
  view.clearSelection();
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("▸ INPAINT OVERLAP — §7.1's fourth row, through the same dispatch as ▸ RENDER", () => {
  it("submits an inpaint job for the selected overlap", async () => {
    seedOverlap();
    const submit = vi.spyOn(jobs, "submit").mockResolvedValue(null);
    const { getByTestId } = render(OverlapInpaint);

    await fireEvent.click(getByTestId("inpaint-overlap-button"));

    await waitFor(() => expect(submit).toHaveBeenCalledTimes(1));
    const req = submit.mock.calls[0][0];
    expect(req.op).toBe("inpaint");
    expect(req.kind).toBe("inpaint");
    expect(req.sourceClipId).toBeNull();
    expect(req.targetKey.startsWith("overlap:")).toBe(true);
    expect(req.payload).toMatchObject({ region: expect.any(Object), pad_sec: expect.any(Number) });
  });

  it("is disabled while any job runs, and says which — §7.1's blanket rule", async () => {
    seedOverlap();
    jobs.gpuBusyOther = "forge-99";
    const { getByTestId } = render(OverlapInpaint);
    const b = getByTestId("inpaint-overlap-button") as HTMLButtonElement;
    expect(b.disabled).toBe(true);
    expect(b.title).toBe("GPU busy — forge-99");
  });

  it("reads SAMPLING · N steps left while its own job runs, not while another control's does", async () => {
    const key = seedOverlap();
    const { getByTestId } = render(OverlapInpaint);
    jobs.active = {
      forgeJobId: "forge-1", op: "inpaint", kind: "inpaint", sourceClipId: null,
      targetKey: `overlap:${key}`, progress: { steps_left_total: 18 } as never,
    } as never;
    await waitFor(() =>
      expect(getByTestId("inpaint-overlap-button").textContent?.trim()).toBe("SAMPLING · 18 steps left"));
  });

  it("puts a PayloadError on §9.7's inline surface instead of throwing out of the handler", async () => {
    seedOverlap();
    vi.spyOn(jobs, "submit").mockRejectedValue(new Error("region start_sec < end_sec required"));
    const { getByTestId } = render(OverlapInpaint);
    await fireEvent.click(getByTestId("inpaint-overlap-button"));
    await waitFor(() => expect(jobs.lastError?.message).toContain("region start_sec"));
  });

  it("still renders nothing for an overlap key that no longer exists (M7 critic pass 2 #5)", () => {
    view.select({ kind: "overlap", key: "gone-a-gone-b" });
    const { queryByTestId } = render(OverlapInpaint);
    expect(queryByTestId("inpaint-overlap-button")).toBeNull();
  });
});
```

- [ ] **Step 14: Run it, expect failure**

```bash
cd latent-forge && npx vitest run src/ui/timeline/__tests__/overlapInpaintWired.test.ts
```

Expected: `expected "submit" to be called 1 times, but got 0 times` — M7's button is a no-op — plus failures
on the missing `title` and the missing SAMPLING label.

- [ ] **Step 15: Wire `inpaint-overlap-button`**

In `latent-forge/src/ui/timeline/OverlapInpaint.svelte`, inside the existing `{#if overlap}` gate that M7's
critic pass added:

```ts
  import { renderLabel, renderRequest } from "../../lib/render/dispatch";
  import { dispatchWorld } from "../../lib/render/dispatchWorld";
  import { renderBlock } from "../../lib/render/renderBlock";
  import { jobs } from "../../lib/render/jobs.svelte";
  import { PayloadError } from "../../lib/render/payloads";
  import { view } from "../../lib/stores/view.svelte";

  const target = $derived(view.selection);
  // inpaintPayload has no `chain` field, so the LatCH head registry is not read on this path and
  // fetching it here would be a network call whose result is discarded.
  const world = $derived.by(() => dispatchWorld(target, {}));

  const blocked = $derived(
    renderBlock(target, {
      busy: jobs.active !== null,
      gpuBusyOther: jobs.gpuBusyOther,
      settings: world.settings,
      clip: null,
      clipOp: null,
      arcPrompt: world.arcPrompt,
      bendOpCount: 0,
      overlapSpanSec: world.overlap ? world.overlap.end_sec - world.overlap.start_sec : 0,
      padSec: world.padSec,
    }),
  );

  /** Same rule as Task 6's `mine`: the SAMPLING count belongs to the control that started the job,
   *  identified by targetKey so selecting elsewhere mid-render does not move the label. */
  const mine = $derived(jobs.active !== null && jobs.active.targetKey === view.selectionKey);
  const label = $derived(renderLabel(mine, jobs.stepsLeft));

  async function onInpaint(): Promise<void> {
    if (blocked !== null) return;
    try {
      await jobs.submit(renderRequest(target, world));
    } catch (e) {
      jobs.lastError = {
        targetKey: view.selectionKey,
        message: e instanceof PayloadError ? e.message : String(e),
      };
    }
  }
```

and the button, keeping M7's testid and its idle text:

```svelte
    <button
      data-testid="inpaint-overlap-button"
      title={blocked ?? ""}
      disabled={blocked !== null}
      onclick={onInpaint}>{mine ? label : "▸ INPAINT OVERLAP"}</button>
```

`{mine ? label : "▸ INPAINT OVERLAP"}` rather than `renderLabel`'s own idle string: M7's test pins this
button's idle text to `▸ INPAINT OVERLAP` and Task 6's `PREVIEW_RENDER_IDLE_LABEL` is `▸ RENDER`. The two
controls share the *busy* sentence, which is the one Fact 9 wants identical everywhere, and keep their own
names.

- [ ] **Step 16: Run it, expect pass**

```bash
cd latent-forge && npx vitest run src/ui/timeline/__tests__/overlapInpaintWired.test.ts
```

Expected: `Test Files  1 passed (1)` / `Tests  5 passed (5)`.

- [ ] **Step 17: Run the whole suite and the type check**

```bash
cd latent-forge && npx vitest run && npm run check
```

Expected: this task's seven new/changed suites green (`masterSource.test.ts` 7, `mixPlayback.test.ts` 4,
`transportMixSource.test.ts` 4, `masterSourceToggle.test.ts` 6, `overlapInpaintWired.test.ts` 5);
M7's `overlapInpaint.test.ts` needs **one edit** — its
`it("the INPAINT OVERLAP button is present, enabled, and a no-op this milestone")` asserts the opposite of
this task and its comment says so (`// no throw, no network call -- M9 wires the job`). Replace that single
`it` with a one-line assertion that the button exists and carries a click handler; the other tests in the
file are untouched. M5's `transport.test.ts` and `masterStrip.test.ts` stay green — with no mix in history,
`masterSource.effective` is `"preview"` and every snapshot is M5's own. `strings.test.ts` still 119.
`npm run check` clean.

**`Tests 26 passed (26)`** for this task's five new files.

- [ ] **Step 18: Commit**

```bash
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M9 T9: the master strip's PREVIEW/MIXDOWN A/B drives both the canvas and the transport (§9.6), MIXDOWN gated on a committed mix rather than hidden, and ▸ INPAINT OVERLAP dispatches through §7.1's fourth row"
```

---

**Open questions raised by this task:**

10. **The toggle's visibility is a deliberate departure from the spec's wording.** Spec: appears only when
    the MIXDOWN slot holds a render. Shipped: always present, MIXDOWN disabled with
    `"nothing has been committed yet"`. Reasons in WHY item 2. The reconcile should confirm or overturn it.
11. **The dBFS/CLIPPING readout now describes whichever source is shown.** That is the A/B's whole purpose,
    but it means the number beside "Master — mix result" changes without the arrangement changing, and M5's
    label does not say which source it is reading. A two-word suffix on that label would settle it; it is a
    string change and belongs with the assembly's HELP/label pass, not here.
12. **The committed mix has no staleness indicator.** M5's `stale` dot tracks the *preview* mix only. A
    commit made before the last three clip moves is exactly as stale and there is nowhere that says so;
    Writer A T4's `mixdown.key` (`signalKeyOf` of the arrangement the stages described) already holds the
    information needed to compute it, so this is a display decision, not a missing mechanism.
