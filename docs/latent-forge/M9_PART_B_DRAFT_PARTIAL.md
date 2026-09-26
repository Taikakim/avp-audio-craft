### Task 6: `▸ RENDER` — §7.1's dispatch table, and the OP's new home on `ForgeClip`

**WHY.** M1 built the preview container as a frame: `preview-render` is a `disabled` button with a
literal `data-help` string and no click handler at all (m1 plan, `PreviewContainer.svelte`:
`data-testid="preview-render"` … `disabled>▸ RENDER</button>`). Spec §7.1 gives that one button four
different jobs depending on what is selected, and the table is the whole of this task:

| Selection | Job | §7.1's own words |
|---|---|---|
| nothing | `generate` | "`generate`, `duration = LENGTH`, session-default settings" |
| clip, A2A on | `a2a_clip` | "on the clip's current audio with its envelope and settings, using its lane's chain" |
| clip, A2A off | the clip's OP | "(`generate`/`decode`/`longform`/`bend`); disabled with the hint `turn A2A on or choose an op` when the clip has neither" |
| overlap | `inpaint` | "`inpaint` preview of that overlap" |

Two things make this more than a `switch`. First, **the OP has no home.** M1's `ForgeClip`
(m1 plan:545-568) has `id, lane, start_sec, offset_sec, dur_sec, loop, audio, native_bpm,
detune_cents, downbeats_sec, render, a2a, latentState, history` — no `op`. M4 built the OP select
and left it unwired (`op = null, onOp = () => {}`), and M7 T9 wired every other TargetBar prop to
the selected clip but explicitly not this one: "`clipName` and `op`/`onOp` stay M4's defaults on
purpose: M1's `ForgeClip` has no name field … and no `op` field (Task 8 WHY item 2 — the OP select
is M9's to back). Both are recorded in Open questions 20." So §7.1 row 3 cannot be implemented
without adding the field.

**WINTERMUTE's steer (log 2026-09-26 03:06)** settles the shape: put `op` on `ForgeClip` **in the
same shape M8's render path already accepts, so there is no client-side translation**. The wire
already has exactly this vocabulary — spec §6.2: "`POST /forge/jobs` `{op, payload}` … `op ∈
generate | a2a_track | a2a_mix | longform | decode | bend | a2a_clip | inpaint | commit`", and M1
types it as `JobOp` (m1 plan:488-490). So the field is a **narrowing of `JobOp`**, not a new
enum: `op: ClipOp | null` where `ClipOp = Extract<JobOp, "generate" | "decode" | "longform" |
"bend">`. `jobs.submit({ op: clip.op, … })` passes the string straight through with no map, and the
§9.2 project change is one field with a default (`null`), not a new object — exactly what the steer
asked for. `null` is not a nicety: §7.1 row 3 *needs* a representable "has neither", or its own
`turn A2A on or choose an op` hint can never fire. Writer A already declared the same four-member
type as `ClipOp` inside `renderBlock.ts` for its `RenderBlockState.clipOp`; this task moves the
declaration down into `types.ts` (where the `JobOp` it narrows lives) and leaves a re-export behind,
so the two halves of M9 do not ship two structurally identical types. **Open question 1** carries
the §9.2 spec-text amendment to the assembly batch, on the `previewAudio` precedent (§9.2 names one
field as deliberately *not* serialised, so §9.2 is where a new serialised clip field is ruled on).

Second, **the dispatch must be pure.** Writer A's `renderBlock(target, state)` is pure for the same
reason and this is its twin: the component reads five stores and a fetched head registry, and if the
branch logic lived in `.svelte` markup every row of §7.1's table would need a mounted component and a
mocked `fetch` to test. `renderRequest(target, world)` therefore returns the `SubmitRequest` Writer
A's `jobs.submit` takes, and `PreviewContainer.svelte` becomes: read the world → `renderBlock` → if
null, `jobs.submit(renderRequest(...))`.

**Ordering note.** This task deliberately wires only `▸ RENDER`. HISTORY, the waveform and the two
action buttons stay `disabled` until Tasks 7 and 8; they keep M1's markup untouched so nothing
half-works between commits.

**Files:**
- Create: `latent-forge/src/lib/render/dispatch.ts`,
  `latent-forge/src/lib/render/__tests__/dispatch.test.ts`,
  `latent-forge/src/lib/stores/__tests__/clipOp.test.ts`,
  `latent-forge/src/ui/prompt/__tests__/previewRender.test.ts`,
  `latent-forge/src/ui/prompt/__tests__/promptSigmaTabOp.test.ts`
- Modify: `latent-forge/src/lib/forge/types.ts` (`ClipOp`; `ForgeClip.op`),
  `latent-forge/src/lib/render/renderBlock.ts` (Writer A T5 — re-export `ClipOp` instead of
  declaring it), `latent-forge/src/lib/stores/arrangement.svelte.ts` (seed `op: null` in `addClip`,
  add `setClipOp`), `latent-forge/src/lib/stores/projectSerializer.svelte.ts` (M7 T8 — `isClip`
  tolerates a missing `op`; `applyProject` defaults it), `latent-forge/src/ui/prompt/PromptSigmaTab.svelte`
  (M4 T10 / M7 T9 — source `op`/`onOp` from the selected clip),
  `latent-forge/src/ui/prompt/PreviewContainer.svelte` (M1 T11 — `▸ RENDER` wired),
  `docs/latent-forge/extract_help.mjs` (five `NEW_STRINGS` ids),
  `latent-forge/src/lib/help/__tests__/strings.test.ts`

**Interfaces** (everything consumed, with the task that produced it — nothing here is lookup-able
from inside this task):

- From `latent-forge/src/lib/forge/types.ts` (**M1 T3**):
  `type JobOp = "generate" | "a2a_track" | "a2a_mix" | "longform" | "decode" | "bend" | "a2a_clip" |
  "inpaint" | "commit"`;
  `type Target = {kind:"none"} | {kind:"clip"; id: string} | {kind:"overlap"; key: string}`;
  `targetKey(t: Target): string` → `"session"` / `"clip:<id>"` / `"overlap:<key>"`;
  `interface ForgeClip { id; lane: 0|1|2|3; start_sec; offset_sec; dur_sec; loop; audio: AudioRef;
  native_bpm: number|null; detune_cents; downbeats_sec: number[]; render: RenderSettings;
  a2a: null | {on: boolean; noise: number; envelope: Envelope}; latentState: "none"|"valid"|"stale";
  history: AudioRef[] }`;
  `interface ForgeLane { index: 0|1|2|3; name; muted; solo; gain; chain: LaneChain }`;
  `interface OverlapParams { curve: Envelope; chroma_xfade: boolean; override: boolean; steps: number;
  cfg: number; render: RenderSettings }`; `RenderSettings`, `AudioRef`, `Envelope`.
  **This task adds to this file:** `type ClipOp`, and `ForgeClip.op: ClipOp | null`.
- From `latent-forge/src/lib/render/payloads.ts` (**Writer A T1**), all pure, all throwing
  `PayloadError`:
  `generatePayload(s: RenderSettings, cfgScale?: number)` → `{...renderWire, duration}` (wire name is
  `duration`, never `duration_sec`);
  `opPayload(op: "decode"|"longform"|"bend", a: OpArgs)` where
  `interface OpArgs { cropId?; latentPath?; ops?: unknown[]; seed?; arc?; steps?; cfgScale?; durationSec? }`;
  `a2aClipPayload(a: A2AClipArgs)` where
  `interface A2AClipArgs { audio: AudioRef; render: RenderSettings; a2a: {on; noise; envelope: Envelope|null};
  chain: ForgeLane["chain"] | null; heads: Record<string, LatchHeadInfo>; ckptPath: string|null; cfgScale? }`;
  `inpaintPayload(a: InpaintArgs)` where
  `interface InpaintSide { audio: AudioRef; start_sec; offset_sec; dur_sec }` and
  `interface InpaintArgs { a: InpaintSide; b: InpaintSide; region: {start_sec; end_sec};
  params: OverlapParams; padSec?; cfgScale? }`;
  `class PayloadError extends Error`; `CAP_SEC = 184`.
- From `latent-forge/src/lib/render/jobs.svelte.ts` (**Writer A T1**):
  `interface SubmitRequest { op: JobOp; payload: unknown; kind: RenderKind; sourceClipId: string | null;
  targetKey: string }`; `type RenderKind = "gen" | "a2a" | "inpaint" | "mix"`;
  `jobs.submit(req: SubmitRequest): Promise<RenderHistoryEntry | null>`; `jobs.busy: boolean`;
  `jobs.active: ActiveJob | null` with `ActiveJob.targetKey`; `jobs.stepsLeft: number | null`
  (**may be 0, and `0` is a real answer — never `??` it into a truthiness test**);
  `jobs.gpuBusyOther: string | null`.
- From `latent-forge/src/lib/render/renderBlock.ts` (**Writer A T5**):
  `renderBlock(target: Target, state: RenderBlockState): string | null` — the one-line reason a
  render is blocked, or null. `interface RenderBlockState { busy; gpuBusyOther; settings; clip;
  clipOp; arcPrompt; bendOpCount; overlapSpanSec; padSec }`. It already returns
  `"turn A2A on or choose an op"` verbatim for §7.1 row 3, and `"GPU busy — <id>"` for §9.7.
- From `latent-forge/src/ui/topbar/mixdown.ts` (**M1 T10**):
  `MIXDOWN_IDLE_LABEL = "▸ MIXDOWN"`; `mixdownLabel(busy: boolean, stepsLeft: number | null): string`
  → `"SAMPLING · ${stepsLeft ?? 0} steps left"` while busy. This task's `renderLabel` reuses that
  sentence so the two render controls say the same thing.
- From `latent-forge/src/lib/render/mixdown.svelte.ts` (**Writer A T4**):
  `MIXDOWN_TARGET_KEY = "mixdown"` — the `targetKey` a commit is submitted under.
- From `latent-forge/src/lib/stores/view.svelte.ts` (**M1 T7**): `view.selection: Target`,
  `view.select(t)`, `view.clearSelection()`, `view.selectionKey` (`$derived(targetKey(selection))`),
  `view.activeLane`.
- From `latent-forge/src/lib/stores/arrangement.svelte.ts` (**M5 T1**): `arrangement.clips: ForgeClip[]`,
  `arrangement.lanes: ForgeLane[]`, derived `arrangement.overlaps: {key; lane; start_sec; end_sec;
  a_id; b_id}[]`, `arrangement.overlapParams(key): OverlapParams`, `arrangement.addClip({lane, startSec,
  durSec, audio, nativeBpm?}): ForgeClip`, `arrangement.ensureA2A(id)`, `arrangement.setNoise(id, v)`.
  **This task adds `setClipOp(id, op)`.**
- From `latent-forge/src/lib/stores/settings.svelte.ts` (**M4 T2**): `settings.current(t: Target):
  RenderSettings` (the owner's object, not a copy), `settings.effectiveCfg(t): number` (1.0 under
  POST), `settings.ckptPath: string | null`, `settings.defaults`.
- From `latent-forge/src/lib/chains/latch.ts` (**M7 T1**): `interface LatchHeadInfo`,
  `chainRequest(chain: LaneChain, heads: Record<string, LatchHeadInfo>): ChainRequest`,
  `fetchLatchHeads(): Promise<Record<string, LatchHeadInfo>>` (resolves `{}` on failure —
  m7 plan:832 asserts exactly that).
- From `latent-forge/src/ui/prompt/PromptSigmaTab.svelte` (**M4 T10**, modified **M7 T9**): props
  `{ clipName?; lane?; a2a?; clipHasLatent?; onA2AToggle?; onNoise?; op?: string | null;
  onOp?: (op: string) => void }`, all optional; mounted **propless** by `BottomPane.svelte`; it reads
  `target` from `view.selection` itself and already derives `clip`, `barA2A`, `barHasLatent`,
  `barOnA2AToggle`, `barOnNoise` from `arrangement`. `TargetBar` (M4 T8) takes `op: string | null`
  and `onOp: (op: string) => void`.
- From `latent-forge/src/ui/prompt/PreviewContainer.svelte` (**M1 T11**): the frame, mounted
  **propless** from `BottomPane.svelte` (`<PreviewContainer />`). Testids that must survive:
  `preview-render`, `preview-history`, `preview-wave` (900×30), `preview-play`, `preview-length`,
  `preview-drag-handle`, `preview-use-settings`, `preview-replace-clip`, and the root
  `[data-region="preview-container"]` (44 px). M1's props `lengthSec?`, `history?` exist and are
  unused by the only call site; this task leaves them alone (Task 7 retires them).
- From `latent-forge/src/lib/stores/projectSerializer.svelte.ts` (**M7 T8**): `isClip(c: unknown):
  boolean` (used by `validateProjectV2`), `applyProject(project, opts)` — its clip restore is
  `...structuredClone(project.clips).map((c) => ({ ...c, previewAudio: null }))`.
- From `docs/latent-forge/extract_help.mjs` (**M1 T5**): the `NEW_STRINGS` map, regenerated by
  `npm run help:extract` into `src/lib/help/strings.ts` as `HELP`. Running total after Writer A's
  Task 4 is **114**.

**Produces:** `src/lib/render/dispatch.ts` — `type ClipOp` (re-export), `PREVIEW_RENDER_IDLE_LABEL =
"▸ RENDER"`, `renderLabel(busy: boolean, stepsLeft: number | null): string`,
`interface DispatchWorld`, `renderRequest(target: Target, w: DispatchWorld): SubmitRequest`,
`kindOf(op: JobOp): RenderKind`. For the Playwright spec: `[data-testid="preview-render"]` gains
`data-blocked="<reason>"` when disabled for a reason, and `title` carrying the same string.

- [ ] **Step 1: Write the failing dispatch test**

`latent-forge/src/lib/render/__tests__/dispatch.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import type { AudioRef, Envelope, ForgeClip, ForgeLane, OverlapParams, RenderSettings } from "../../forge/types";
import { PayloadError } from "../payloads";
import { PREVIEW_RENDER_IDLE_LABEL, renderLabel, renderRequest, type DispatchWorld } from "../dispatch";
import { mixdownLabel } from "../../../ui/topbar/mixdown";

const CROP: AudioRef = { kind: "crop", crop_id: "000412" };
const UP: AudioRef = { kind: "upload", sha256: "a".repeat(64) };
const FLAT: Envelope = { points: [0.4, 0.4, 0.4, 0.4], curves: [0, 0, 0] };

function settings(p: Partial<RenderSettings> = {}): RenderSettings {
  return {
    prompt: "a room", negative_prompt: "", steps: 24, cfg_scale: 6, seed: -1, apg_scale: 0,
    cfg_interval_progress: [0, 1], scale_phi: 0, sampler_type: null, duration_sec: 45,
    schedule: { shape: "model", rho: 1, sigma_min: 0.01, lam_min: -6, lam_max: 3, stepped: false, plateaus: 4, tilt: 0.5 },
    ...p,
  } as RenderSettings;
}

function clip(p: Partial<ForgeClip> = {}): ForgeClip {
  return {
    id: "c1", lane: 0, start_sec: 0, offset_sec: 0, dur_sec: 8, loop: false, audio: UP,
    native_bpm: null, detune_cents: 0, downbeats_sec: [], render: settings(), a2a: null,
    latentState: "none", history: [], op: null, ...p,
  } as ForgeClip;
}

function lane(index: 0 | 1 | 2 | 3 = 0): ForgeLane {
  return {
    index, name: `LANE ${index + 1}`, muted: false, solo: false, gain: 1,
    chain: { latch_on: false, slots: [], film_on: false, film: null, lora_on: false, lora: null, bungee_on: false, semitones: 0 },
  } as ForgeLane;
}

function overlapParams(p: Partial<OverlapParams> = {}): OverlapParams {
  return { curve: { points: [0, 0.35, 0.7, 1], curves: [0, 0, 0] }, chroma_xfade: true, override: false, steps: 28, cfg: 3.0, render: settings(), ...p };
}

function world(p: Partial<DispatchWorld> = {}): DispatchWorld {
  return {
    settings: settings(), cfgScale: 6, clip: null, lane: null, heads: {}, ckptPath: null,
    overlap: null, overlapParams: null, clipById: () => null, arcPrompt: "", bendOps: [], padSec: 8,
    ...p,
  };
}

describe("renderRequest — spec §7.1's dispatch table, one row per test", () => {
  it("nothing selected renders `generate` under the session target key", () => {
    const req = renderRequest({ kind: "none" }, world({ settings: settings({ duration_sec: 30 }) }));
    expect(req.op).toBe("generate");
    expect(req.kind).toBe("gen");
    expect(req.sourceClipId).toBeNull();
    expect(req.targetKey).toBe("session");
  });

  it("sends LENGTH as the wire name `duration`, never `duration_sec` (Fact 1)", () => {
    const req = renderRequest({ kind: "none" }, world({ settings: settings({ duration_sec: 30 }) }));
    const payload = req.payload as Record<string, unknown>;
    expect(payload.duration).toBe(30);
    expect("duration_sec" in payload).toBe(false);
  });

  it("a clip with A2A on renders `a2a_clip` on the clip's whole audio", () => {
    const c = clip({ audio: CROP, a2a: { on: true, noise: 0.4, envelope: FLAT } });
    const req = renderRequest({ kind: "clip", id: c.id }, world({ clip: c, lane: lane(0) }));
    expect(req.op).toBe("a2a_clip");
    expect(req.kind).toBe("a2a");
    expect(req.sourceClipId).toBe("c1");
    expect(req.targetKey).toBe("clip:c1");
    expect((req.payload as Record<string, unknown>).audio).toEqual(CROP);
    expect((req.payload as Record<string, unknown>).noise_level).toBe(0.4);
  });

  it("a2a_clip uses the CLIP's own lane chain, not the active lane's (§7.1 row 2)", () => {
    const c = clip({ lane: 2, a2a: { on: true, noise: 0.2, envelope: FLAT } });
    const l2 = lane(2);
    l2.chain.bungee_on = true;
    l2.chain.semitones = 5;
    const req = renderRequest({ kind: "clip", id: c.id }, world({ clip: c, lane: l2 }));
    const chain = (req.payload as Record<string, unknown>).chain as Record<string, unknown>;
    expect(chain.bungee_on).toBe(true);
    expect(chain.semitones).toBe(5);
  });

  it("a clip with A2A off renders the clip's OP, passed to the wire untranslated", () => {
    const c = clip({ audio: CROP, op: "decode", latentState: "valid" });
    const req = renderRequest({ kind: "clip", id: c.id }, world({ clip: c, lane: lane(0) }));
    expect(req.op).toBe("decode");
    expect(req.kind).toBe("gen");
    expect(req.sourceClipId).toBe("c1");
    expect(req.payload).toEqual({ crop_id: "000412" });
  });

  it("op `longform` sends the prompt ARC under `schedule`, not a ScheduleSpec", () => {
    const c = clip({ op: "longform" });
    const req = renderRequest(
      { kind: "clip", id: c.id },
      world({ clip: c, lane: lane(0), arcPrompt: "0:opening pad|45:driving bass" }),
    );
    expect(req.op).toBe("longform");
    expect((req.payload as Record<string, unknown>).schedule).toBe("0:opening pad|45:driving bass");
  });

  it("a clip with neither A2A nor an OP is a caller error, not a silent generate", () => {
    const c = clip({ a2a: null, op: null });
    expect(() => renderRequest({ kind: "clip", id: c.id }, world({ clip: c, lane: lane(0) })))
      .toThrow(PayloadError);
  });

  it("an overlap renders `inpaint` with both clips' sides and the overlap's span", () => {
    const a = clip({ id: "a", dur_sec: 8, start_sec: 0 });
    const b = clip({ id: "b", dur_sec: 8, start_sec: 6, audio: CROP });
    const req = renderRequest(
      { kind: "overlap", key: "a-b" },
      world({
        overlap: { key: "a-b", lane: 0, start_sec: 6, end_sec: 8, a_id: "a", b_id: "b" },
        overlapParams: overlapParams(),
        clipById: (id) => (id === "a" ? a : id === "b" ? b : null),
      }),
    );
    expect(req.op).toBe("inpaint");
    expect(req.kind).toBe("inpaint");
    expect(req.sourceClipId).toBeNull();
    expect(req.targetKey).toBe("overlap:a-b");
    const payload = req.payload as Record<string, unknown>;
    expect(payload.region).toEqual({ start_sec: 6, end_sec: 8 });
    expect((payload.a as Record<string, unknown>).audio).toEqual(UP);
    expect((payload.b as Record<string, unknown>).audio).toEqual(CROP);
    expect(payload.pad_sec).toBe(8);
  });

  it("the overlap's LOCAL steps/cfg override reaches the wire already applied (Fact 2)", () => {
    const a = clip({ id: "a" });
    const b = clip({ id: "b" });
    const req = renderRequest(
      { kind: "overlap", key: "a-b" },
      world({
        overlap: { key: "a-b", lane: 0, start_sec: 6, end_sec: 8, a_id: "a", b_id: "b" },
        overlapParams: overlapParams({ override: true, steps: 40, cfg: 2.5 }),
        clipById: (id) => (id === "a" ? a : id === "b" ? b : null),
      }),
    );
    const render = (req.payload as Record<string, unknown>).render as Record<string, unknown>;
    expect(render.steps).toBe(40);
    expect(render.cfg_scale).toBe(2.5);
  });
});

describe("renderLabel is M1's MIXDOWN sentence on the other render control (§7.1)", () => {
  it("is ▸ RENDER while idle and the SAMPLING sentence while a job runs", () => {
    expect(renderLabel(false, 44)).toBe(PREVIEW_RENDER_IDLE_LABEL);
    expect(renderLabel(true, 44)).toBe("SAMPLING · 44 steps left");
    expect(renderLabel(true, 44)).toBe(mixdownLabel(true, 44));
  });

  it("shows 0 steps left rather than nothing when steps_total is 0 (Fact 5)", () => {
    expect(renderLabel(true, 0)).toBe("SAMPLING · 0 steps left");
    expect(renderLabel(true, null)).toBe("SAMPLING · 0 steps left");
  });
});
```

- [ ] **Step 2: Run it, expect the import to fail**

```bash
cd latent-forge && npx vitest run src/lib/render/__tests__/dispatch.test.ts
```

Expected: `Error: Failed to resolve import "../dispatch" from "src/lib/render/__tests__/dispatch.test.ts"`.
(TypeScript also reports `Object literal may only specify known properties, and 'op' does not exist
in type 'ForgeClip'` on the `clip()` helper — Step 3 adds the field.)

- [ ] **Step 3: Add `ClipOp` and `ForgeClip.op` to `src/lib/forge/types.ts`**

Below the `JobOp` declaration (m1 plan:488-490), add:

```ts
/**
 * The OP a clip renders with when A2A is off (spec §7.1 row 3, §10 X11's "compact OP select in
 * the target bar"). It is a NARROWING of `JobOp`, not a parallel enum: WINTERMUTE's steer
 * (log 2026-09-26 03:06) is that the field carry the shape M8's render path already accepts, so
 * `jobs.submit({ op: clip.op, … })` passes the string through with no translation step.
 *
 * `a2a_track` / `a2a_mix` are deliberately outside it: both need a server-side `audio_path` and
 * there is no upload-to-path route, which is also why Writer A's payload builders do not build
 * them. `commit`, `a2a_clip` and `inpaint` are not per-clip ops at all.
 */
export type ClipOp = Extract<JobOp, "generate" | "decode" | "longform" | "bend">;

export const CLIP_OPS: readonly ClipOp[] = ["generate", "decode", "longform", "bend"] as const;
```

and in `ForgeClip`, beside `render`:

```ts
  /**
   * §7.1 row 3's OP, or null when the clip has none. `null` is load-bearing: it is what makes
   * "disabled with the hint `turn A2A on or choose an op` when the clip has neither" reachable.
   * Serialised into ProjectV2's `clips[]` (§9.2 amendment — Open question 1); a v2 file written
   * before M9 has no `op` key and loads as null.
   */
  op: ClipOp | null;
```

In `latent-forge/src/lib/render/renderBlock.ts` (Writer A T5), replace the local declaration
`export type ClipOp = "generate" | "decode" | "longform" | "bend";` with a re-export so there is one
type, not two structurally identical ones:

```ts
export type { ClipOp } from "../forge/types";
```

- [ ] **Step 4: Write `latent-forge/src/lib/render/dispatch.ts`**

```ts
// Spec §7.1's table, as a pure function. The twin of Writer A's renderBlock: the component reads
// the stores and hands the world in, so every row of the table is a one-line test and none of them
// needs a mounted component or a mocked fetch.
//
// The division of labour with renderBlock: renderBlock answers "may this run, and if not, what do I
// tell the operator" and owns every user-facing refusal. renderRequest answers "what exactly goes
// on the wire" and THROWS on a state renderBlock would already have refused -- a PayloadError here
// means the caller skipped the gate, which is a bug, not an operator mistake.

import type {
  AudioRef, ClipOp, ForgeClip, ForgeLane, JobOp, OverlapParams, RenderSettings, Target,
} from "../forge/types";
import { targetKey } from "../forge/types";
import type { LatchHeadInfo } from "../chains/latch";
import type { RenderKind, SubmitRequest } from "./jobs.svelte";
import { a2aClipPayload, generatePayload, inpaintPayload, opPayload, PayloadError } from "./payloads";

export type { ClipOp } from "../forge/types";

/** M1's MIXDOWN copy on the other render control, so both say the same sentence. */
export const PREVIEW_RENDER_IDLE_LABEL = "▸ RENDER";

/** `stepsLeft` may legitimately be 0 (Fact 5: a commit with no sampling passes, decode, bend), so
 *  `?? 0` is for the null case only and the 0 is printed, never swallowed. */
export function renderLabel(busy: boolean, stepsLeft: number | null): string {
  if (!busy) return PREVIEW_RENDER_IDLE_LABEL;
  return `SAMPLING · ${stepsLeft ?? 0} steps left`;
}

/** Derived overlap, M5 T1's shape. */
export interface DispatchOverlap {
  key: string;
  lane: 0 | 1 | 2 | 3;
  start_sec: number;
  end_sec: number;
  a_id: string;
  b_id: string;
}

export interface DispatchWorld {
  /** `settings.current(target)` -- the TARGET's own copy (§7.2), the session defaults for `none`. */
  settings: RenderSettings;
  /** `settings.effectiveCfg(target)` -- 1.0 under POST (§5.3), which must not overwrite the field
   *  the operator is editing. */
  cfgScale: number;
  clip: ForgeClip | null;
  /** The CLIP's lane (§7.1 row 2: "using its lane's chain"), not `view.activeLane`. */
  lane: ForgeLane | null;
  heads: Record<string, LatchHeadInfo>;
  ckptPath: string | null;
  overlap: DispatchOverlap | null;
  overlapParams: OverlapParams | null;
  clipById: (id: string) => ForgeClip | null;
  /** The prompt-ARC string for `longform`. */
  arcPrompt: string;
  bendOps: unknown[];
  /** §6.8's context each side; default 8. */
  padSec: number;
}

const KIND_OF: Record<string, RenderKind> = {
  generate: "gen", decode: "gen", longform: "gen", bend: "gen",
  a2a_clip: "a2a", inpaint: "inpaint", commit: "mix",
};

export function kindOf(op: JobOp): RenderKind {
  return KIND_OF[op] ?? "gen";
}

function latentSourceOf(audio: AudioRef): { cropId?: string; latentPath?: string } {
  // renderBlock's own rule (`hasLatent`): the clip's latent IS its crop ref. A clip whose audio is
  // anything else has no latent to decode or bend, which renderBlock already refuses.
  return audio.kind === "crop" ? { cropId: audio.crop_id } : {};
}

function clipRequest(clip: ForgeClip, w: DispatchWorld): SubmitRequest {
  const key = targetKey({ kind: "clip", id: clip.id });

  // §7.1 row 2 wins over row 3: A2A on is a2a_clip whatever the OP select says.
  if (clip.a2a?.on) {
    return {
      op: "a2a_clip",
      kind: "a2a",
      sourceClipId: clip.id,
      targetKey: key,
      payload: a2aClipPayload({
        audio: clip.audio,
        render: w.settings,
        a2a: { on: true, noise: clip.a2a.noise, envelope: clip.a2a.envelope ?? null },
        chain: w.lane?.chain ?? null,
        heads: w.heads,
        ckptPath: w.ckptPath,
        cfgScale: w.cfgScale,
      }),
    };
  }

  const op: ClipOp | null = clip.op;
  if (op === null) {
    // renderBlock returns "turn A2A on or choose an op" for exactly this state; reaching here means
    // the gate was skipped.
    throw new PayloadError("turn A2A on or choose an op");
  }

  const payload =
    op === "generate"
      ? generatePayload(w.settings, w.cfgScale)
      : opPayload(op, {
          ...latentSourceOf(clip.audio),
          ops: w.bendOps,
          seed: w.settings.seed,
          arc: w.arcPrompt,
          steps: w.settings.steps,
          cfgScale: w.cfgScale,
          durationSec: w.settings.duration_sec,
        });

  return { op, kind: "gen", sourceClipId: clip.id, targetKey: key, payload };
}

function overlapRequest(w: DispatchWorld): SubmitRequest {
  const o = w.overlap;
  const params = w.overlapParams;
  if (!o || !params) throw new PayloadError("the overlap is gone");
  const a = w.clipById(o.a_id);
  const b = w.clipById(o.b_id);
  if (!a || !b) throw new PayloadError("the overlap is gone");

  const side = (c: ForgeClip) => ({
    audio: c.audio, start_sec: c.start_sec, offset_sec: c.offset_sec, dur_sec: c.dur_sec,
  });

  return {
    op: "inpaint",
    kind: "inpaint",
    // §7.1 row 4 lands in "preview container + history" with no REPLACE CLIP: an inpaint is made
    // from two clips, so there is no single clip to replace.
    sourceClipId: null,
    targetKey: targetKey({ kind: "overlap", key: o.key }),
    payload: inpaintPayload({
      a: side(a),
      b: side(b),
      region: { start_sec: o.start_sec, end_sec: o.end_sec },
      params,
      padSec: w.padSec,
      cfgScale: w.cfgScale,
    }),
  };
}

/**
 * The §7.1 table. Throws `PayloadError` on a state `renderBlock` would already have refused, or a
 * payload field outside the server's range (Writer A's builders name the field).
 */
export function renderRequest(target: Target, w: DispatchWorld): SubmitRequest {
  if (target.kind === "overlap") return overlapRequest(w);
  if (target.kind === "clip") {
    if (!w.clip) throw new PayloadError("the selected clip is gone");
    return clipRequest(w.clip, w);
  }
  // §7.1 row 1: session-default settings, LENGTH as `duration`.
  return {
    op: "generate",
    kind: "gen",
    sourceClipId: null,
    targetKey: targetKey({ kind: "none" }),
    payload: generatePayload(w.settings, w.cfgScale),
  };
}
```

- [ ] **Step 5: Run it, expect pass**

```bash
cd latent-forge && npx vitest run src/lib/render/__tests__/dispatch.test.ts
```

Expected: `Test Files  1 passed (1)` / `Tests  11 passed (11)`.

- [ ] **Step 6: Write the failing clip-OP store test**

`latent-forge/src/lib/stores/__tests__/clipOp.test.ts`:

```ts
import { beforeEach, describe, expect, it } from "vitest";
import type { AudioRef } from "../../forge/types";
import { CLIP_OPS } from "../../forge/types";
import { arrangement } from "../arrangement.svelte";

const REF: AudioRef = { kind: "upload", sha256: "b".repeat(64) };

beforeEach(() => {
  for (const c of [...arrangement.clips]) arrangement.removeClip(c.id);
});

describe("ForgeClip.op — §7.1 row 3's OP, in M8's own wire vocabulary", () => {
  it("a new clip has no op, so §7.1's `turn A2A on or choose an op` is reachable", () => {
    const c = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: REF });
    expect(c.op).toBeNull();
  });

  it("setClipOp writes through the live proxy, not a dead handle ($state rule)", () => {
    const c = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: REF });
    arrangement.setClipOp(c.id, "bend");
    expect(arrangement.clips[0].op).toBe("bend");
    expect(c.op).toBe("bend");
  });

  it("every op is a JobOp the server's POST /forge/jobs already accepts (no translation)", () => {
    expect([...CLIP_OPS]).toEqual(["generate", "decode", "longform", "bend"]);
  });
});
```

- [ ] **Step 7: Run it, expect the missing method**

```bash
cd latent-forge && npx vitest run src/lib/stores/__tests__/clipOp.test.ts
```

Expected: `TypeError: arrangement.setClipOp is not a function` on two tests, and
`expected undefined to be null` on the first.

- [ ] **Step 8: Back the field in the arrangement store and the serialiser**

In `latent-forge/src/lib/stores/arrangement.svelte.ts` (M5 T1), in the clip literal `addClip` pushes
(m5 plan:3570, `native_bpm: null, detune_cents: 0, downbeats_sec: [], latentState: "none", history: []`),
add `op: null,` and add the setter beside `setNoise`:

```ts
  /** §7.1 row 3's OP. `$state` rule: the array element is the live proxy, so the write goes
   *  through `this.clips.find(...)`, never through a caller's captured reference. */
  setClipOp(id: string, op: ClipOp | null): void {
    const clip = this.clips.find((c) => c.id === id);
    if (clip) clip.op = op;
  }
```

with `ClipOp` added to the `import type { … } from "../forge/types"` line already at the top.

In `latent-forge/src/lib/stores/projectSerializer.svelte.ts` (M7 T8), `isClip` must **tolerate a
missing `op`** — every v2 file written before M9 lacks it, and `validateProjectV2` throwing on those
would make M9 unable to open its own earlier sessions:

```ts
function isClipOp(v: unknown): boolean {
  return v === undefined || v === null || (typeof v === "string" && (CLIP_OPS as readonly string[]).includes(v));
}
```

and add `&& isClipOp(c.op)` to `isClip`'s chain. In `applyProject`, change the clip restore line to
default it:

```ts
  arrangement.clips.splice(
    0, arrangement.clips.length,
    ...structuredClone(project.clips).map((c) => ({ ...c, op: c.op ?? null, previewAudio: null })),
  );
```

`serializeProject` already spreads each clip, so `op` serialises with no change there — confirm with
the existing `projectSerializer` round-trip test rather than adding one.

- [ ] **Step 9: Run it, expect pass**

```bash
cd latent-forge && npx vitest run src/lib/stores/__tests__/clipOp.test.ts src/lib/stores/__tests__/projectSerializer.test.ts
```

Expected: `Tests  3 passed (3)` for `clipOp.test.ts`, and `projectSerializer.test.ts` unchanged and
still green (its round trip now carries one more field, which its `toEqual` on the whole clip covers).

- [ ] **Step 10: Write the failing PromptSigmaTab OP-wiring test**

`latent-forge/src/ui/prompt/__tests__/promptSigmaTabOp.test.ts`:

```ts
// @vitest-environment jsdom
// M7 T9 wired every TargetBar clip prop except op/onOp ("the OP select is M9's to back").
// This is that wiring, in the same shape as M7's own promptSigmaTabClip.test.ts.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import type { AudioRef } from "../../../lib/forge/types";
import { arrangement } from "../../../lib/stores/arrangement.svelte";
import { view } from "../../../lib/stores/view.svelte";
import PromptSigmaTab from "../PromptSigmaTab.svelte";

const REF: AudioRef = { kind: "upload", sha256: "c".repeat(64) };

beforeEach(() => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}", { status: 200 }));
  for (const c of [...arrangement.clips]) arrangement.removeClip(c.id);
  view.clearSelection();
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("the OP select is backed by the selected clip (spec §10 X11)", () => {
  it("shows the selected clip's op", async () => {
    const c = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: REF });
    arrangement.setClipOp(c.id, "longform");
    view.select({ kind: "clip", id: c.id });
    const { getByTestId } = render(PromptSigmaTab);     // propless, as BottomPane mounts it
    expect((getByTestId("target-op") as HTMLSelectElement).value).toBe("longform");
  });

  it("choosing an op writes it back to the clip", async () => {
    const c = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: REF });
    view.select({ kind: "clip", id: c.id });
    const { getByTestId } = render(PromptSigmaTab);
    await fireEvent.change(getByTestId("target-op"), { target: { value: "decode" } });
    expect(arrangement.clips[0].op).toBe("decode");
  });
});
```

*(`target-op` is M4 T8's testid on TargetBar's OP select; if M4's implementation named it otherwise,
use that name — the assertion is the wiring, not the id.)*

- [ ] **Step 11: Run it, expect the unwired default**

```bash
cd latent-forge && npx vitest run src/ui/prompt/__tests__/promptSigmaTabOp.test.ts
```

Expected: both fail — `expected '' to be 'longform'` (M4's `op = null` default renders no
selection) and `expected null to be 'decode'` (M4's `onOp = () => {}` default swallows the change).

- [ ] **Step 12: Wire `op`/`onOp` in `PromptSigmaTab.svelte`**

Beside M7 T9's `barA2A` / `barOnNoise` derivations, add the same two lines for the OP — a passed
prop still wins, exactly as it does for the other five:

```ts
  function setClipOpFromBar(op: string): void {
    if (clip) arrangement.setClipOp(clip.id, op as ClipOp);
  }

  const barOp = $derived(op ?? clip?.op ?? null);
  const barOnOp = $derived(onOp ?? setClipOpFromBar);
```

change the `$props()` destructuring so "not passed" is `undefined` for these two as well —
`op` and `onOp` lose their defaults, like the five M7 T9 already un-defaulted:

```ts
  let {
    clipName = null, lane, a2a, clipHasLatent,
    onA2AToggle, onNoise, op, onOp,
  }: Props = $props();
```

and change the `<TargetBar …>` element's last two attributes to `op={barOp} onOp={barOnOp}`.
Add `ClipOp` to the file's `import type` from `../../lib/forge/types`.

- [ ] **Step 13: Run it, expect pass**

```bash
cd latent-forge && npx vitest run src/ui/prompt/__tests__/promptSigmaTabOp.test.ts src/ui/prompt/__tests__/promptSigmaTabClip.test.ts
```

Expected: `Tests  2 passed (2)` and M7's `promptSigmaTabClip.test.ts` unchanged and still green.

- [ ] **Step 14: Write the failing `▸ RENDER` component test**

`latent-forge/src/ui/prompt/__tests__/previewRender.test.ts`:

```ts
// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import type { AudioRef } from "../../../lib/forge/types";
import { arrangement } from "../../../lib/stores/arrangement.svelte";
import { jobs } from "../../../lib/render/jobs.svelte";
import { settings } from "../../../lib/stores/settings.svelte";
import { view } from "../../../lib/stores/view.svelte";
import PreviewContainer from "../PreviewContainer.svelte";

const REF: AudioRef = { kind: "upload", sha256: "d".repeat(64) };

beforeEach(() => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}", { status: 200 }));
  for (const c of [...arrangement.clips]) arrangement.removeClip(c.id);
  view.clearSelection();
  jobs.active = null;
  jobs.gpuBusyOther = null;
  jobs.lastError = null;
  settings.defaults.prompt = "a room";
  settings.defaults.duration_sec = 30;
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("preview ▸ RENDER — spec §7.1", () => {
  it("is enabled and reads ▸ RENDER with nothing selected and a prompt", () => {
    const { getByTestId } = render(PreviewContainer);
    const button = getByTestId("preview-render") as HTMLButtonElement;
    expect(button.disabled).toBe(false);
    expect(button.textContent?.trim()).toBe("▸ RENDER");
  });

  it("submits `generate` with LENGTH under the session target key", async () => {
    const submit = vi.spyOn(jobs, "submit").mockResolvedValue(null);
    const { getByTestId } = render(PreviewContainer);
    await fireEvent.click(getByTestId("preview-render"));
    expect(submit).toHaveBeenCalledTimes(1);
    const req = submit.mock.calls[0][0];
    expect(req.op).toBe("generate");
    expect(req.targetKey).toBe("session");
    expect((req.payload as Record<string, unknown>).duration).toBe(30);
  });

  it("submits `inpaint` when an overlap is selected", async () => {
    const a = arrangement.addClip({ lane: 0, startSec: 0, durSec: 8, audio: REF });
    const b = arrangement.addClip({ lane: 0, startSec: 6, durSec: 8, audio: REF });
    const key = `${a.id}-${b.id}`;
    view.select({ kind: "overlap", key });
    const submit = vi.spyOn(jobs, "submit").mockResolvedValue(null);
    const { getByTestId } = render(PreviewContainer);
    await fireEvent.click(getByTestId("preview-render"));
    expect(submit.mock.calls[0][0].op).toBe("inpaint");
    expect(submit.mock.calls[0][0].targetKey).toBe(`overlap:${key}`);
  });

  it("counts the remaining steps on the control that started the job (§7.1)", () => {
    jobs.active = {
      forgeJobId: "forge-1", op: "generate", kind: "gen", sourceClipId: null, targetKey: "session",
      progress: { job_id: "forge-1", op: "generate", stage: "", stage_index: 0, stage_count: 0, step: 3, steps: 24, steps_left_total: 21, steps_total: 24 },
    };
    const { getByTestId } = render(PreviewContainer);
    const button = getByTestId("preview-render") as HTMLButtonElement;
    expect(button.textContent?.trim()).toBe("SAMPLING · 21 steps left");
    expect(button.disabled).toBe(true);
  });

  it("is disabled but NOT relabelled while the MIXDOWN slot owns the job", () => {
    jobs.active = {
      forgeJobId: "forge-2", op: "commit", kind: "mix", sourceClipId: null, targetKey: "mixdown",
      progress: null,
    };
    const { getByTestId } = render(PreviewContainer);
    const button = getByTestId("preview-render") as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    expect(button.textContent?.trim()).toBe("▸ RENDER");
  });

  it("a clip with neither A2A nor an OP is disabled with §7.1's own hint", () => {
    const c = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: REF });
    view.select({ kind: "clip", id: c.id });
    const { getByTestId } = render(PreviewContainer);
    const button = getByTestId("preview-render") as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    expect(button.getAttribute("data-blocked")).toBe("turn A2A on or choose an op");
    expect(button.title).toBe("turn A2A on or choose an op");
  });

  it("shows §9.7's GPU line when another client holds the card", () => {
    jobs.gpuBusyOther = "dash-77";
    const { getByTestId } = render(PreviewContainer);
    const button = getByTestId("preview-render") as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    expect(button.getAttribute("data-blocked")).toBe("GPU busy — dash-77");
  });
});
```

- [ ] **Step 15: Run it, expect every assertion past the first to fail**

```bash
cd latent-forge && npx vitest run src/ui/prompt/__tests__/previewRender.test.ts
```

Expected: `Tests  7 failed (7)`. The first fails `expected true to be false` (M1's button is
hard-`disabled`); the submit tests fail `expected "spy" to be called 1 times, but got 0 times`; the
label tests fail `expected '▸ RENDER' to be 'SAMPLING · 21 steps left'`; the two blocked tests fail
`expected null to be 'turn A2A on or choose an op'` (no `data-blocked` attribute exists).

- [ ] **Step 16: Wire `▸ RENDER` in `PreviewContainer.svelte`**

Keep M1's markup, its `data-testid`s and its `data-help` copy. Add the script body above M1's
`let canvasEl`:

```ts
  import { fetchLatchHeads, type LatchHeadInfo } from "../../lib/chains/latch";
  import { renderLabel, renderRequest } from "../../lib/render/dispatch";
  import { jobs } from "../../lib/render/jobs.svelte";
  import { MIXDOWN_TARGET_KEY } from "../../lib/render/mixdown.svelte";
  import { renderBlock } from "../../lib/render/renderBlock";
  import { PayloadError } from "../../lib/render/payloads";
  import { arrangement } from "../../lib/stores/arrangement.svelte";
  import { settings } from "../../lib/stores/settings.svelte";
  import { view } from "../../lib/stores/view.svelte";

  // One fetch per mounted container, resolving {} on failure (M7 T1). The heads only decide which
  // LatCH slots survive into the chain, so an empty registry sends a chain with no slots rather
  // than blocking a render.
  let heads = $state<Record<string, LatchHeadInfo>>({});
  $effect(() => {
    fetchLatchHeads().then((h) => (heads = h)).catch(() => {});
  });

  const target = $derived(view.selection);

  const clip = $derived.by(() => {
    const sel = view.selection;
    return sel.kind === "clip" ? (arrangement.clips.find((c) => c.id === sel.id) ?? null) : null;
  });

  const overlap = $derived.by(() => {
    const sel = view.selection;
    return sel.kind === "overlap" ? (arrangement.overlaps.find((o) => o.key === sel.key) ?? null) : null;
  });

  // §6.8's default context each side. M9 has no UI for it; when one lands it reads from here.
  const PAD_SEC = 8;

  const world = $derived({
    settings: settings.current(target),
    cfgScale: settings.effectiveCfg(target),
    clip,
    lane: clip ? (arrangement.lanes[clip.lane] ?? null) : null,
    heads,
    ckptPath: settings.ckptPath,
    overlap,
    overlapParams: overlap ? arrangement.overlapParams(overlap.key) : null,
    clipById: (id: string) => arrangement.clips.find((c) => c.id === id) ?? null,
    // No prompt-ARC field exists in M9's UI: `longform` reads the target's prompt as its arc, which
    // is what _longform_impl falls back to on the server (`req["schedule"] or req["prompt"]`).
    arcPrompt: settings.current(target).prompt,
    // No bend-op editor exists either -- renderBlock refuses `bend` with an empty list, so this is
    // the honest empty rather than an invented default (Open question 3).
    bendOps: [] as unknown[],
    padSec: PAD_SEC,
  });

  const blocked = $derived(
    renderBlock(target, {
      busy: jobs.active !== null,
      gpuBusyOther: jobs.gpuBusyOther,
      settings: world.settings,
      clip,
      clipOp: clip?.op ?? null,
      arcPrompt: world.arcPrompt,
      bendOpCount: world.bendOps.length,
      overlapSpanSec: overlap ? overlap.end_sec - overlap.start_sec : 0,
      padSec: PAD_SEC,
    }),
  );

  /** The SAMPLING count belongs to the control that STARTED the job (§7.1). A commit runs under
   *  MIXDOWN_TARGET_KEY, so the top-bar slot counts it and this button only greys out; anything
   *  else was started from here. Comparing against the key rather than the live selection means
   *  selecting a different clip mid-render does not move the label. */
  const mine = $derived(jobs.active !== null && jobs.active.targetKey !== MIXDOWN_TARGET_KEY);
  const label = $derived(renderLabel(mine, jobs.stepsLeft));

  async function onRender(): Promise<void> {
    if (blocked !== null) return;
    try {
      await jobs.submit(renderRequest(target, world));
    } catch (e) {
      // A PayloadError here is a field the server would 400 on; §9.7 wants it on the target bar,
      // and jobs.lastError is that surface (Writer A T5 renders it).
      jobs.lastError = { targetKey: view.selectionKey, message: e instanceof PayloadError ? e.message : String(e) };
    }
  }
```

and replace M1's `preview-render` button with the same element, unfrozen:

```svelte
  <button
    class="render"
    data-testid="preview-render"
    data-help={HELP.previewRender}
    data-blocked={blocked}
    title={blocked ?? ""}
    disabled={blocked !== null}
    onclick={onRender}>{label}</button>
```

with `import { HELP } from "../../lib/help/strings";` added.

- [ ] **Step 17: Promote M1's five preview `data-help` literals to HELP ids**

Fact 9: "M1 already wrote literal help strings on the frames … promote each to a `NEW_STRINGS` id
and use `HELP.x`". All five are added in one step so `strings.test.ts` moves once and stays green
through Tasks 7-9, rather than going red in each. In `docs/latent-forge/extract_help.mjs`, add to
`NEW_STRINGS` — **M1's own copy, moved verbatim, nothing reworded**:

```js
  previewRender:
    "Renders the current target with the settings in this pane. The result lands here to be " +
    "auditioned; drag it onto a lane if you want it.",
  previewHistory:
    "Every render of this session, newest first. Loading one plays it here — it does not change " +
    "the settings in this pane.",
  previewDragHandle:
    "Drag the previewed render onto a lane to add it as a clip at the drop position.",
  previewUseSettings:
    "Copies the settings the previewed render was made with into the current target. Loading a " +
    "render from HISTORY never does this on its own.",
  previewReplaceClip:
    "Swaps the selected clip's audio for the previewed render, keeping the previous audio in the " +
    "clip's history. Enabled only when the render was made from that clip.",
```

Replace the literal `data-help="…"` on all five controls in `PreviewContainer.svelte` with
`data-help={HELP.previewRender}` … `data-help={HELP.previewReplaceClip}`; the other four controls'
markup is otherwise untouched until Tasks 7 and 8. Then:

```bash
cd latent-forge && npm run help:extract
```

Expected: `extract_help: wrote 119 strings (80 extracted, 14 rewritten, 39 new)`. In
`latent-forge/src/lib/help/__tests__/strings.test.ts`, change
`expect(Object.keys(HELP)).toHaveLength(114);` to `119` and the title's count to match.
**114 is Writer A's Task 4 total; 119 is M9's, and no later task of either writer adds another id**
— Task 9 attaches the *existing* `previewMixdownToggle`. The assembly step recounts (Open question 6).

- [ ] **Step 18: Run it, expect pass**

```bash
cd latent-forge && npx vitest run src/ui/prompt/__tests__/previewRender.test.ts
```

Expected: `Test Files  1 passed (1)` / `Tests  7 passed (7)`.

- [ ] **Step 19: Run the whole suite and the type check**

```bash
cd latent-forge && npx vitest run && npm run check
```

Expected: `dispatch.test.ts` 11, `clipOp.test.ts` 3, `promptSigmaTabOp.test.ts` 2,
`previewRender.test.ts` 7, `strings.test.ts` green at 119, and every other file unchanged.
`npm run check` clean — the `ForgeClip.op` addition compiles everywhere because `addClip` seeds it
and `applyProject` defaults it; nothing else constructs a `ForgeClip` literal.

- [ ] **Step 20: Commit**

```bash
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M9 T6: preview ▸ RENDER dispatches spec §7.1's four rows; the clip OP gets a home on ForgeClip in the server's own wire vocabulary"
```

---

### Task 7: HISTORY, the preview waveform, scrub, play, length and the drag handle

**WHY.** Everything left of `USE SETTINGS` in M1's frame is still inert: the HISTORY `<select>` is
`disabled` and renders a single `no renders yet` option, the 900×30 canvas is never drawn on, `▶` is
`disabled`, `preview-length` prints `—` from an unused prop, and the drag handle is a `<span>` with
no `draggable` attribute. Spec §4.5 describes all five in one paragraph: "HISTORY select (every
render of the session, newest first, tagged `GEN` / `A2A` / `INPAINT` / `MIX` with length) · waveform
canvas (flex) with click/drag scrub and playhead · `▶/■` · length label · drag handle
`⠿ drag to lane`".

Three of its sentences are behavioural rules, not decoration, and each gets its own test:

1. **"Loading from HISTORY loads audio only. The previewed render changes; the pane's settings do
   not."** — §10 X15 is the departure this enforces ("HISTORY loads audio only; settings come from a
   SETTINGS PRESET or an explicit USE SETTINGS"). Writer A's `history.select(index)` already sets
   exactly one field for this reason. The test asserts the *absence* of a settings write, which is
   the only way a regression here is ever caught.
2. **"Preview playback is independent of the timeline transport; starting one stops the other."** —
   two directions, two tests. This cannot live inside either store: `previewPlayer` importing
   `playback` and `playback` importing `previewPlayer` is a cycle. So a three-line
   `soloBus` module owns the rule and both stores register with it — which also means M10 can add a
   third audio source without touching either.
3. **The length label and the HISTORY tags are DOM.** M4's blocking finding was a label painted with
   `fillText` that no `findByText` could ever reach. `preview-length` is already a `<span>` and the
   tags are `<option>` text; this task keeps them there and the tests use `textContent`, so the rule
   is enforced by construction rather than by a comment.

**On the player engine.** There is no "play one buffer" method to add: M5's `Transport` already
plays a list of `PlaybackClip`s, and a one-element list *is* the preview. So the preview player is a
second `Transport` driving `[{id:"preview", laneIndex:0, startSec:0, durationSec, offsetSec:0,
previewUrl}]` against one unmuted lane — no new audio code, and `currentTimeSec`, `onEnded`,
`pause`, `seek`, `scrub` and `stopScrub` all come free. The engine is built **lazily inside a
try/catch**, the pattern M5 itself established for its peak-cache decoder ("there is no Web Audio in
the vitest environment (node, no jsdom AudioContext), and a browser that somehow lacks it should not
lose the clip over a peak-cache warm-up"), rather than at module load where a singleton would take
the whole import graph down under jsdom.

**One reading shipped.** §4.5 says starting one "stops" the other. `playback.stop()` (M5 T3) sets
`playheadSec = this.loopOn ? this.loopStartSec : 0` — so the literal reading rewinds the operator's
timeline every time they audition a render, which no DAW does and which §9.6's "same-playhead
behaviour" argues against. This task calls `playback.pause()`, which satisfies the requirement that
actually matters (the two never sound together) and keeps the playhead. **Open question 2.**

**Files:**
- Create: `latent-forge/src/lib/audio/soloBus.ts`,
  `latent-forge/src/lib/audio/__tests__/soloBus.test.ts`,
  `latent-forge/src/lib/render/historyLabel.ts`,
  `latent-forge/src/lib/render/__tests__/historyLabel.test.ts`,
  `latent-forge/src/lib/render/previewPlayer.svelte.ts`,
  `latent-forge/src/ui/prompt/__tests__/previewHistory.test.ts`
- Modify: `latent-forge/src/lib/stores/transport.svelte.ts` (M5 T3 — register with the solo bus),
  `latent-forge/src/ui/prompt/PreviewContainer.svelte` (M1 T11 — HISTORY, canvas, `▶`, length, handle)

**Interfaces** (everything consumed, with its source task):

- From `latent-forge/src/lib/render/history.svelte.ts` (**Writer A T3**):
  `interface RenderHistoryEntry { job_id: string; forge_job_id: string; file: string; label: string;
  kind: "gen"|"a2a"|"inpaint"|"mix"; dur_sec: number; source_clip_id: string | null; created: number }`
  (M1 T3's type; `created` in epoch **seconds**);
  `history.renders: RenderHistoryEntry[]` — **newest LAST in storage, newest first in the UI**;
  `history.preview: number | null` (index into `renders`); `history.mixdown: number | null`;
  `history.add(e): RenderHistoryEntry` (returns the live proxy element, sets `preview` to it);
  `history.select(index: number): void` — **sets `preview` and nothing else**, ignoring an index
  outside the array; `history.refOf(e): AudioRef` → `{kind:"render", job_id: e.job_id, file: e.file}`
  where `job_id` is the RESULT's output-dir id, not the `forge-…` queue id;
  `history.jobRecord(e): Promise<JobRecord>`; `history.clear()`.
  Writer A's label is built as `` `${KIND_LABEL[kind]} ${new Date().toISOString().slice(11,19)}` `` —
  i.e. `"GEN 12:00:00"`, tag and time but **no length**, so §4.5's "with length" is this task's job.
- From `latent-forge/src/lib/forge/api.ts` (**M1 T5**): `forgeApi.audioUrl(ref: AudioRef): string`
  → `` `/forge/audio?ref=${encodeURIComponent(JSON.stringify(ref))}` ``.
- From `latent-forge/src/lib/audio/transport.ts` (**M1 T15, re-homed by M5 T3**):
  `class Transport implements PlaybackEngine`, `readonly ctx: AudioContext`;
  `interface PlaybackEngine { play(clips: PlaybackClip[], lanes: PlaybackLane[], fromSec: number):
  Promise<void>; pause(): void; stop(): void; seek(sec, clips, lanes): Promise<void>;
  preload(url: string): Promise<AudioBuffer>; invalidate(url: string): void;
  scrub(buffer: AudioBuffer, atSec: number, windowSec?: number): void; stopScrub(): void;
  readonly currentTimeSec: number; readonly playing: boolean; onEnded?: () => void }`;
  `interface PlaybackClip { id; laneIndex; startSec; durationSec; offsetSec; previewUrl: string | null }`;
  `interface PlaybackLane { index; muted; solo; gain }`.
- From `latent-forge/src/lib/audio/waveform.ts` (**M1 T15, re-homed by M5**):
  `computePeaks(buffer: AudioBuffer, columns: number): Peaks`,
  `drawPeaks(canvas: HTMLCanvasElement, peaks: Peaks, color: string): void`,
  `interface Peaks { columns: number; data: Float32Array }`.
  **Note the signature**: M5 T10 calls `drawPeaks(canvas, peaks, color)` (three args, canvas first).
  Writer A's Task 4 draft writes `drawPeaks(ctx, peaks, canvasEl.width, canvasEl.height)` — a
  four-arg call against a 2D context. One of the two is wrong and it is not this one; **Open
  question 5** carries it to the reconcile.
- From `latent-forge/src/lib/stores/transport.svelte.ts` (**M5 T3**): `playback.play()`,
  `playback.pause()`, `playback.stop()`, `playback.togglePlay()`, `playback.seek(sec)`,
  `playback.playing: boolean`, `playback.playheadSec: number`, `playback.preload(url)`.
- From `latent-forge/src/lib/math/laneHeader.ts` (**M5 T4**): the drop MIME is
  `application/x-forge-ref` and its payload is a bare `JSON.stringify(AudioRef)` —
  `parseForgeRefPayload(raw)` is `JSON.parse` then `isAudioRef(parsed) ? parsed : null`.
- From `latent-forge/src/lib/help/strings.ts` (**M1 T5**, extended by **Task 6**):
  `HELP.previewHistory`, `HELP.previewDragHandle`. Task 6 already added both; this task only
  attaches the two that belong to its own controls. No new ids, so `strings.test.ts` stays at 119.
- From Task 6 of this plan: `PreviewContainer.svelte`'s wired `▸ RENDER`, `world`, `blocked`,
  `target`, `clip` — all already in the file.

**Produces:** `src/lib/audio/soloBus.ts` — `registerAudioSource(id: string, stop: () => void): void`,
`takeAudio(id: string): void`, `AUDIO_SOURCE_TIMELINE = "timeline"`, `AUDIO_SOURCE_PREVIEW = "preview"`.
`src/lib/render/historyLabel.ts` — `HISTORY_EMPTY_LABEL = "no renders yet"`,
`interface HistoryOption { index: number; label: string }`,
`historyOptions(renders: RenderHistoryEntry[]): HistoryOption[]` (newest first),
`lengthLabel(durSec: number | null): string`.
`src/lib/render/previewPlayer.svelte.ts` — `class PreviewPlayerStore` with `playing`, `playheadSec`,
`durationSec`, `url`, `load(url, durSec)`, `play()`, `stop()`, `toggle()`, `seek(sec)`,
`scrubAt(sec)`, `useEngine(e)`; the singleton `previewPlayer`.

- [ ] **Step 1: Write the failing pure tests**

`latent-forge/src/lib/audio/__tests__/soloBus.test.ts`:

```ts
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AUDIO_SOURCE_PREVIEW, AUDIO_SOURCE_TIMELINE, registerAudioSource, takeAudio } from "../soloBus";

describe("soloBus — §4.5's 'starting one stops the other', without an import cycle", () => {
  let timeline = vi.fn();
  let preview = vi.fn();

  beforeEach(() => {
    timeline = vi.fn();
    preview = vi.fn();
    registerAudioSource(AUDIO_SOURCE_TIMELINE, timeline);
    registerAudioSource(AUDIO_SOURCE_PREVIEW, preview);
  });

  it("stops every other registered source", () => {
    takeAudio(AUDIO_SOURCE_PREVIEW);
    expect(timeline).toHaveBeenCalledTimes(1);
  });

  it("never stops the source that is taking the bus", () => {
    takeAudio(AUDIO_SOURCE_PREVIEW);
    expect(preview).not.toHaveBeenCalled();
  });
});
```

`latent-forge/src/lib/render/__tests__/historyLabel.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import type { RenderHistoryEntry } from "../../forge/types";
import { HISTORY_EMPTY_LABEL, historyOptions, lengthLabel } from "../historyLabel";

function entry(p: Partial<RenderHistoryEntry> = {}): RenderHistoryEntry {
  return {
    job_id: "gen-1", forge_job_id: "forge-1", file: "out_00.wav", label: "GEN 12:00:00",
    kind: "gen", dur_sec: 30, source_clip_id: null, created: 1, ...p,
  };
}

describe("historyOptions — spec §4.5's HISTORY select", () => {
  it("is newest first, though the store holds newest last", () => {
    const options = historyOptions([
      entry({ label: "GEN 12:00:00" }),
      entry({ label: "A2A 12:01:00", kind: "a2a" }),
      entry({ label: "MIX 12:02:00", kind: "mix" }),
    ]);
    expect(options.map((o) => o.index)).toEqual([2, 1, 0]);
    expect(options[0].label.startsWith("MIX")).toBe(true);
  });

  it("carries the tag and the length, which the stored label does not have", () => {
    expect(historyOptions([entry({ dur_sec: 30 })])[0].label).toBe("GEN 12:00:00 · 30.0 s");
  });

  it("says — rather than 0.0 s when the result carried no duration", () => {
    expect(historyOptions([entry({ dur_sec: 0 })])[0].label).toBe("GEN 12:00:00 · —");
    expect(lengthLabel(null)).toBe("—");
    expect(lengthLabel(0)).toBe("—");
  });

  it("has an empty-state label matching M1's own frame copy", () => {
    expect(historyOptions([])).toEqual([]);
    expect(HISTORY_EMPTY_LABEL).toBe("no renders yet");
  });
});
```

- [ ] **Step 2: Run them, expect two unresolved imports**

```bash
cd latent-forge && npx vitest run src/lib/audio/__tests__/soloBus.test.ts src/lib/render/__tests__/historyLabel.test.ts
```

Expected: `Failed to resolve import "../soloBus"` and `Failed to resolve import "../historyLabel"`.

- [ ] **Step 3: Write the two pure modules**

`latent-forge/src/lib/audio/soloBus.ts`:

```ts
// Spec §4.5: "Preview playback is independent of the timeline transport; starting one stops the
// other." Neither store can own that rule -- previewPlayer imports playback or playback imports
// previewPlayer, and either way it is a cycle. A registry owns it instead, which also means a third
// audio source (M10's statistics auditioning, say) joins without touching either store.
//
// Deliberately not reactive: nothing renders from this, and a $state Map would make every stop
// callback a proxied function for no gain.

export const AUDIO_SOURCE_TIMELINE = "timeline";
export const AUDIO_SOURCE_PREVIEW = "preview";

const sources = new Map<string, () => void>();

/** Idempotent: re-registering the same id replaces the callback, so HMR does not leave a stale one. */
export function registerAudioSource(id: string, stop: () => void): void {
  sources.set(id, stop);
}

/** Stops every registered source except `id`. Safe to call when `id` is not registered. */
export function takeAudio(id: string): void {
  for (const [key, stop] of sources) {
    if (key !== id) stop();
  }
}
```

`latent-forge/src/lib/render/historyLabel.ts`:

```ts
// Spec §4.5's HISTORY option text. Pure so the ordering rule -- the store holds newest LAST and the
// select shows newest FIRST -- is tested once, here, rather than being re-derived in markup.

import type { RenderHistoryEntry } from "../forge/types";

/** M1's own placeholder copy, kept verbatim so the frame reads the same before and after M9. */
export const HISTORY_EMPTY_LABEL = "no renders yet";

export interface HistoryOption {
  /** Index into `history.renders` (storage order), which is what `history.select` takes. */
  index: number;
  label: string;
}

/**
 * `0` means "the result carried no duration_sec in meta" (Writer A's `durationOf` returns 0 there),
 * not "a zero-length render". Printing `0.0 s` would be a claim the server never made.
 */
export function lengthLabel(durSec: number | null): string {
  if (durSec === null || !Number.isFinite(durSec) || durSec <= 0) return "—";
  return `${durSec.toFixed(1)} s`;
}

/**
 * The tag (`GEN`/`A2A`/`INPAINT`/`MIX`) is already the first word of `entry.label`, which Writer A's
 * `jobs.submit` builds from the job's own kind; the length §4.5 asks for is appended here.
 */
export function historyOptions(renders: RenderHistoryEntry[]): HistoryOption[] {
  return renders
    .map((e, index) => ({ index, label: `${e.label} · ${lengthLabel(e.dur_sec)}` }))
    .reverse();
}
```

- [ ] **Step 4: Run them, expect pass**

```bash
cd latent-forge && npx vitest run src/lib/audio/__tests__/soloBus.test.ts src/lib/render/__tests__/historyLabel.test.ts
```

Expected: `Tests  2 passed (2)` and `Tests  4 passed (4)`.

- [ ] **Step 5: Write the preview player store and register both sides of the solo bus**

`latent-forge/src/lib/render/previewPlayer.svelte.ts`:

```ts
// The preview container's own transport (spec §4.5). NOT M5's `playback`: that one plays the
// arrangement, and §4.5 requires these two to be independent and mutually exclusive.
//
// There is no "play one buffer" engine method to write. M5's Transport already plays a list of
// PlaybackClips, and the preview IS a one-element list -- so currentTimeSec, onEnded, pause, seek,
// scrub and stopScrub all arrive for free and the two transports behave identically.

import { Transport, type PlaybackEngine } from "../audio/transport";
import { AUDIO_SOURCE_PREVIEW, registerAudioSource, takeAudio } from "../audio/soloBus";

const PREVIEW_LANE = { index: 0, muted: false, solo: false, gain: 1 };

export class PreviewPlayerStore {
  playing = $state(false);
  playheadSec = $state(0);
  durationSec = $state(0);
  url = $state<string | null>(null);

  /** `undefined` = not tried yet, `null` = this environment has no Web Audio. M5's own lazy-decoder
   *  pattern: a module-level `new Transport()` would throw at IMPORT time under jsdom and take the
   *  whole graph with it. */
  #engine: PlaybackEngine | null | undefined;

  constructor() {
    registerAudioSource(AUDIO_SOURCE_PREVIEW, () => this.stop());
  }

  /** Test seam, and the one M10 would use to share an engine. */
  useEngine(engine: PlaybackEngine | null): void {
    this.#engine = engine;
    if (engine) engine.onEnded = () => { this.playing = false; };
  }

  engine(): PlaybackEngine | null {
    if (this.#engine === undefined) {
      try {
        const t = new Transport();
        t.onEnded = () => { this.playing = false; };
        this.#engine = t;
      } catch {
        this.#engine = null;
      }
    }
    return this.#engine;
  }

  /** A new previewed render: audio only (§10 X15). Rewinds, because it is different audio. */
  load(url: string, durSec: number): void {
    if (this.url === url) return;
    this.stop();
    this.url = url;
    this.durationSec = durSec;
    this.playheadSec = 0;
  }

  #clips() {
    return [{
      id: "preview", laneIndex: 0, startSec: 0,
      durationSec: this.durationSec, offsetSec: 0, previewUrl: this.url,
    }];
  }

  async play(): Promise<void> {
    const engine = this.engine();
    if (!engine || this.url === null || this.playing) return;
    // §4.5: starting one stops the other. Before the engine starts, so the two never overlap even
    // for the length of an await.
    takeAudio(AUDIO_SOURCE_PREVIEW);
    await engine.play(this.#clips(), [PREVIEW_LANE], this.playheadSec);
    this.playing = true;
  }

  stop(): void {
    const engine = this.#engine;
    if (!engine) return;
    engine.stop();
    engine.stopScrub();
    this.playing = false;
  }

  async toggle(): Promise<void> {
    if (this.playing) this.stop();
    else await this.play();
  }

  async seek(sec: number): Promise<void> {
    const clamped = Math.max(0, Math.min(sec, this.durationSec));
    this.playheadSec = clamped;
    const engine = this.engine();
    if (engine && this.playing) await engine.seek(clamped, this.#clips(), [PREVIEW_LANE]);
  }

  /** Click/drag on the waveform (§4.5). Audible scrub, same gesture as M5's Alt+drag on a clip. */
  async scrubAt(sec: number): Promise<void> {
    await this.seek(sec);
    const engine = this.engine();
    if (!engine || this.url === null || this.playing) return;
    takeAudio(AUDIO_SOURCE_PREVIEW);
    engine.scrub(await engine.preload(this.url), this.playheadSec);
  }

  /** Pulled by the container's rAF loop while playing, exactly as M5's Ruler drives `syncPlayhead`. */
  syncPlayhead(): void {
    const engine = this.#engine;
    if (!engine || !this.playing) return;
    this.playheadSec = engine.currentTimeSec;
  }
}

export const previewPlayer = new PreviewPlayerStore();
```

In `latent-forge/src/lib/stores/transport.svelte.ts` (M5 T3), add the other half of the rule. Import
`AUDIO_SOURCE_TIMELINE, registerAudioSource, takeAudio` from `../audio/soloBus`, register in the
constructor beside the existing `this.engine.onEnded = …`:

```ts
    registerAudioSource(AUDIO_SOURCE_TIMELINE, () => this.pause());
```

and make `play()` take the bus first — one line at the top of the existing body, before the
`if (this.playing) return;` guard is unchanged:

```ts
  async play() {
    if (this.playing) return;
    takeAudio(AUDIO_SOURCE_TIMELINE);           // §4.5: starting one stops the other
    await this.engine.play(this.snapshotClips(), this.snapshotLanes(), this.playheadSec);
    this.playing = true;
  }
```

`pause()` rather than `stop()` on the timeline side is the reading this plan ships (see WHY, Open
question 2): the requirement is that they never sound together, and `stop()` would additionally
rewind the operator's playhead to 0 on every audition.

- [ ] **Step 6: Write the failing container test**

`latent-forge/src/ui/prompt/__tests__/previewHistory.test.ts`:

```ts
// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import type { PlaybackEngine, PlaybackClip, PlaybackLane } from "../../../lib/audio/transport";
import { history } from "../../../lib/render/history.svelte";
import { previewPlayer } from "../../../lib/render/previewPlayer.svelte";
import { playback } from "../../../lib/stores/transport.svelte";
import { settings } from "../../../lib/stores/settings.svelte";
import { view } from "../../../lib/stores/view.svelte";
import PreviewContainer from "../PreviewContainer.svelte";

function fakeEngine(): PlaybackEngine {
  return {
    play: vi.fn(async (_c: PlaybackClip[], _l: PlaybackLane[], _s: number) => {}),
    pause: vi.fn(), stop: vi.fn(),
    seek: vi.fn(async () => {}),
    preload: vi.fn(async () => ({ duration: 30 }) as unknown as AudioBuffer),
    invalidate: vi.fn(), scrub: vi.fn(), stopScrub: vi.fn(),
    currentTimeSec: 0, playing: false,
  };
}

function entry(p: Partial<Parameters<typeof history.add>[0]> = {}) {
  return history.add({
    job_id: "gen-1", forge_job_id: "forge-1", file: "out_00.wav", label: "GEN 12:00:00",
    kind: "gen", dur_sec: 30, source_clip_id: null, created: 1, ...p,
  });
}

let engine: PlaybackEngine;

beforeEach(() => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}", { status: 200 }));
  history.clear();
  view.clearSelection();
  engine = fakeEngine();
  previewPlayer.useEngine(engine);
  previewPlayer.url = null;
  previewPlayer.playing = false;
  playback.playing = false;
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("HISTORY, the waveform and the handle — spec §4.5", () => {
  it("is disabled and empty until the session has a render", () => {
    const { getByTestId } = render(PreviewContainer);
    const select = getByTestId("preview-history") as HTMLSelectElement;
    expect(select.disabled).toBe(true);
    expect(select.textContent?.trim()).toBe("no renders yet");
  });

  it("lists renders newest first, tagged and with their length", () => {
    entry({ label: "GEN 12:00:00" });
    entry({ label: "A2A 12:01:00", kind: "a2a", dur_sec: 8 });
    const { getByTestId } = render(PreviewContainer);
    const select = getByTestId("preview-history") as HTMLSelectElement;
    expect(select.disabled).toBe(false);
    expect([...select.options].map((o) => o.textContent)).toEqual([
      "A2A 12:01:00 · 8.0 s",
      "GEN 12:00:00 · 30.0 s",
    ]);
  });

  it("loading from HISTORY loads audio only — the target's settings are untouched (X15)", async () => {
    entry({ label: "GEN 12:00:00" });
    entry({ label: "A2A 12:01:00", kind: "a2a", dur_sec: 8 });
    settings.defaults.prompt = "untouched";
    settings.defaults.steps = 24;
    const { getByTestId } = render(PreviewContainer);
    await fireEvent.change(getByTestId("preview-history"), { target: { value: "0" } });
    expect(history.preview).toBe(0);
    expect(settings.defaults.prompt).toBe("untouched");
    expect(settings.defaults.steps).toBe(24);
  });

  it("shows the previewed render's length in the DOM, not on the canvas", () => {
    entry({ dur_sec: 12.5 });
    const { getByTestId } = render(PreviewContainer);
    expect(getByTestId("preview-length").textContent?.trim()).toBe("12.5 s");
  });

  it("starting the preview stops the timeline transport (§4.5)", async () => {
    entry();
    playback.playing = true;
    const { getByTestId } = render(PreviewContainer);
    await fireEvent.click(getByTestId("preview-play"));
    expect(playback.playing).toBe(false);
    expect(previewPlayer.playing).toBe(true);
  });

  it("starting the timeline transport stops the preview (§4.5, the other direction)", async () => {
    entry();
    const { getByTestId } = render(PreviewContainer);
    await fireEvent.click(getByTestId("preview-play"));
    expect(previewPlayer.playing).toBe(true);
    await playback.play();
    expect(previewPlayer.playing).toBe(false);
    expect(engine.stop).toHaveBeenCalled();
  });

  it("clicking the waveform scrubs to that second", async () => {
    entry({ dur_sec: 30 });
    const { getByTestId } = render(PreviewContainer);
    const canvas = getByTestId("preview-wave") as HTMLCanvasElement;
    vi.spyOn(canvas, "getBoundingClientRect").mockReturnValue(
      { left: 0, top: 0, width: 900, height: 30, right: 900, bottom: 30, x: 0, y: 0, toJSON: () => "" },
    );
    await fireEvent.pointerDown(canvas, { clientX: 300 });
    expect(previewPlayer.playheadSec).toBeCloseTo(10, 5);
    expect(engine.scrub).toHaveBeenCalled();
  });

  it("the handle carries the render AudioRef as application/x-forge-ref", async () => {
    const e = entry();
    const { getByTestId } = render(PreviewContainer);
    const handle = getByTestId("preview-drag-handle");
    expect(handle.getAttribute("draggable")).toBe("true");
    const setData = vi.fn();
    await fireEvent.dragStart(handle, { dataTransfer: { setData, effectAllowed: "" } });
    expect(setData).toHaveBeenCalledWith(
      "application/x-forge-ref",
      JSON.stringify({ kind: "render", job_id: e.job_id, file: e.file }),
    );
  });
});
```

- [ ] **Step 7: Run it, expect every test but the first to fail**

```bash
cd latent-forge && npx vitest run src/ui/prompt/__tests__/previewHistory.test.ts
```

Expected: `Tests  7 failed | 1 passed (8)`. The first passes by accident — M1's frame really is
disabled and really does read `no renders yet`. The rest fail on M1's frame: `expected true to be
false` (the select never enables), `expected [] to equal [ 'A2A…', 'GEN…' ]`, `expected null to be
0` (no change handler), `expected '—' to be '12.5 s'`, `expected false to be true` (`▶` is disabled),
`expected undefined to be called` (no pointer handler), and `expected null to be 'true'` (no
`draggable` attribute).

- [ ] **Step 8: Wire the five controls in `PreviewContainer.svelte`**

Add to the script, below Task 6's block:

```ts
  import { computePeaks, drawPeaks } from "../../lib/audio/waveform";
  import { Transport } from "../../lib/audio/transport";
  import { forgeApi } from "../../lib/forge/api";
  import { history } from "../../lib/render/history.svelte";
  import { HISTORY_EMPTY_LABEL, historyOptions, lengthLabel } from "../../lib/render/historyLabel";
  import { previewPlayer } from "../../lib/render/previewPlayer.svelte";

  const options = $derived(historyOptions(history.renders));

  const entry = $derived(
    history.preview !== null ? (history.renders[history.preview] ?? null) : null,
  );

  const previewUrl = $derived(entry ? forgeApi.audioUrl(history.refOf(entry)) : null);

  // §4.5: "A finished render lands here" -- history.add already moved `preview`, so this effect is
  // what makes a finished render audible without the operator touching HISTORY.
  $effect(() => {
    if (previewUrl !== null && entry !== null) previewPlayer.load(previewUrl, entry.dur_sec);
  });

  let canvasEl = $state<HTMLCanvasElement>();        // M1 already declares this; keep the one line
  let buffer = $state<AudioBuffer | null>(null);
  let scrubbing = $state(false);

  /** Decode-only Transport, M5's own pattern -- this warms the same URL-keyed cache the player
   *  reads, and never plays. Lazily built so jsdom's missing AudioContext costs a waveform, not
   *  the component. */
  let _decoder: Transport | null | undefined;
  function decoder(): Transport | null {
    if (_decoder === undefined) {
      try { _decoder = new Transport(); } catch { _decoder = null; }
    }
    return _decoder;
  }

  $effect(() => {
    const url = previewUrl;
    if (url === null) { buffer = null; return; }
    let live = true;
    decoder()?.preload(url).then((b) => { if (live) buffer = b; }).catch(() => { if (live) buffer = null; });
    return () => { live = false; };
  });

  function draw(): void {
    const canvas = canvasEl;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
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
  }

  $effect(() => {
    void buffer;
    void canvasEl;
    void previewPlayer.playheadSec;
    draw();
  });

  // The playhead clock, the same shape as M5's Ruler loop and stopped with the component.
  $effect(() => {
    if (!previewPlayer.playing) return;
    let frame = 0;
    const tick = () => { previewPlayer.syncPlayhead(); frame = requestAnimationFrame(tick); };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  });

  function secAt(e: { clientX: number }): number {
    const canvas = canvasEl;
    if (!canvas || previewPlayer.durationSec <= 0) return 0;
    const rect = canvas.getBoundingClientRect();
    const ratio = rect.width > 0 ? (e.clientX - rect.left) / rect.width : 0;
    return Math.max(0, Math.min(1, ratio)) * previewPlayer.durationSec;
  }

  function onWavePointerDown(e: PointerEvent): void {
    if (previewUrl === null) return;
    scrubbing = true;
    (e.currentTarget as HTMLCanvasElement).setPointerCapture?.(e.pointerId);
    void previewPlayer.scrubAt(secAt(e));
  }

  function onWavePointerMove(e: PointerEvent): void {
    if (scrubbing) void previewPlayer.scrubAt(secAt(e));
  }

  function onWavePointerUp(): void {
    if (!scrubbing) return;
    scrubbing = false;
    previewPlayer.stop();
  }

  function onHistoryChange(e: Event): void {
    // Audio only (§4.5, §10 X15). `history.select` sets exactly one field, and this handler
    // deliberately calls nothing else -- a settings write here is the regression X15 exists to stop.
    history.select(Number((e.currentTarget as HTMLSelectElement).value));
  }

  function onHandleDragStart(e: DragEvent): void {
    if (!entry || !e.dataTransfer) return;
    e.dataTransfer.setData("application/x-forge-ref", JSON.stringify(history.refOf(entry)));
    e.dataTransfer.effectAllowed = "copy";
  }
```

and replace M1's four inert elements (its `data-testid`s, classes, `data-help` ids and the handle's
`⠿ drag to lane` text all stay exactly as they are):

```svelte
  <select
    class="history"
    data-testid="preview-history"
    data-help={HELP.previewHistory}
    disabled={options.length === 0}
    value={history.preview === null ? "" : String(history.preview)}
    onchange={onHistoryChange}
  >
    {#if options.length === 0}
      <option value="">{HISTORY_EMPTY_LABEL}</option>
    {:else}
      {#each options as o (o.index)}
        <option value={String(o.index)}>{o.label}</option>
      {/each}
    {/if}
  </select>

  <canvas
    class="wave"
    data-testid="preview-wave"
    bind:this={canvasEl}
    width="900"
    height="30"
    onpointerdown={onWavePointerDown}
    onpointermove={onWavePointerMove}
    onpointerup={onWavePointerUp}
    onpointercancel={onWavePointerUp}
  ></canvas>

  <button
    class="transport"
    data-testid="preview-play"
    aria-label="play the previewed render"
    disabled={previewUrl === null}
    onclick={() => void previewPlayer.toggle()}>{previewPlayer.playing ? "■" : "▶"}</button>
  <span class="length" data-testid="preview-length">{lengthLabel(entry?.dur_sec ?? null)}</span>

  <span
    class="handle"
    data-testid="preview-drag-handle"
    data-help={HELP.previewDragHandle}
    draggable={entry !== null}
    ondragstart={onHandleDragStart}
    >⠿ drag to lane</span>
```

M1's `lengthSec` and `history` props are now dead — the only call site (`BottomPane.svelte`) passes
neither. Delete the `interface Props` block and the `$props()` line rather than leave two ways to
set the same text.

- [ ] **Step 9: Run it, expect pass**

```bash
cd latent-forge && npx vitest run src/ui/prompt/__tests__/previewHistory.test.ts src/lib/stores/__tests__/transport.test.ts
```

Expected: `Tests  8 passed (8)` for `previewHistory.test.ts`, and M5's `transport.test.ts` unchanged
and still green — `play()` gained one line that stops nothing when the preview player has never
played.

- [ ] **Step 10: Run the whole suite and the type check**

```bash
cd latent-forge && npx vitest run && npm run check
```

Expected: `soloBus.test.ts` 2, `historyLabel.test.ts` 4, `previewHistory.test.ts` 8, Task 6's four
files unchanged, `strings.test.ts` still 119, everything else unchanged, `npm run check` clean.

- [ ] **Step 11: Commit**

```bash
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M9 T7: preview HISTORY newest-first with lengths, waveform with scrub and playhead, play/stop mutually exclusive with the timeline transport, drag handle carrying the render ref"
```

---
