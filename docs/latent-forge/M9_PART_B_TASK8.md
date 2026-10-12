### Task 8: USE SETTINGS and REPLACE CLIP — the two actions under the preview

**WHY.** M1 built both buttons as dead frames. In `PreviewContainer.svelte` they are literally:

```svelte
  <button
    class="action"
    data-testid="preview-use-settings"
    data-help="Copies the settings the previewed render was made with into the current target. …"
    disabled>USE SETTINGS</button>
  <button
    class="action"
    data-testid="preview-replace-clip"
    data-help="Swaps the selected clip's audio for the previewed render, keeping the previous audio in the …"
    disabled>REPLACE CLIP</button>
```

— `disabled`, no handler, no props. Task 6 replaced the two `data-help` literals with `HELP.previewUseSettings`
and `HELP.previewReplaceClip`; everything else about them is still M1's. This task is the other half of
§10 X15. Task 7 shipped the half that says *HISTORY loads audio only*; X15's own sentence is
*"HISTORY loads audio only; settings come from a SETTINGS PRESET or an explicit USE SETTINGS"* — so the
explicit path has to exist, or X15 is a rule against a door that was never built.

Three things make this more than two `onclick`s.

**1. The settings are on the wire, not in the client.** Nothing in `RenderHistoryEntry` carries what a render
was made with: it is `{job_id, forge_job_id, file, label, kind, dur_sec, source_clip_id, created}` and that is
all (M1 T3's type, restated in the shared interfaces). The settings live on the server's job record, which is
why Writer A's brief entry for `history` says `jobRecord(e): Promise<JobRecord>` — *"`USE SETTINGS` (Writer B,
Task 8) reads `.payload`"* (Writer A's Task 3 interface list). So USE SETTINGS is a **fetch**, and every path
through it must survive the fetch failing.

**2. The payload shape differs per op, and one of them is a trap.** Writer A's builders (Task 1) put the
settings in a different place for every op this milestone can submit:

| op | where the render settings are | length |
|---|---|---|
| `generate` | the payload **is** the render wire | top-level `duration` |
| `a2a_clip` | nested `payload.render` | none — the clip supplies it |
| `inpaint` | nested `payload.render` | none — the region and `pad_sec` supply it |
| `commit` | nowhere: lanes/clips/overlaps each carry their own | top-level `duration_sec` |
| `decode` | nowhere — `{crop_id}` or `{latent_path}` | none |
| `bend` | `seed` only | none |
| `longform` | `steps`, `cfg_scale`, `seed` | top-level `duration` |

The trap is `longform`. `opPayload("longform", …)` returns
`{ schedule: arc, steps, cfg_scale, seed, duration }` (Writer A T1) — and that `schedule` is the **arc string**
`"0:promptA|45:promptB"`, not M3's `ScheduleSpec` object. `RenderSettings.schedule` is the object.
Handing a `longform` payload to `applyRenderPreset` whole would put a string in front of the branch that
expects `{shape, rho, sigma_min, lam_min, lam_max, stepped, plateaus, tilt}`. M4's validator is strict enough
to reject it rather than corrupt the target (`applyRenderPreset(s, { schedule: { shape: "karras" } })` is
already a rejection test there), so the damage is a silent no-op rather than a bad write — but a silent no-op
on the one field the operator was looking at is still a bug. **The payload is therefore never passed through
whole.** A pure `payloadSettings(op, payload)` reduces each shape above to one `{body, durationSec}` pair, and
only `body` ever reaches `applyRenderPreset`. That reduction is this task's main unit under test.

**3. LENGTH is not a preset field.** M4's `applyRenderPreset` walks `NUMERIC_TOP`, which is
`steps`, `cfg_scale`, `seed`, `scale_phi` (m4 plan, the `NUMERIC_TOP` table), plus `apg_scale`,
`sampler_type`, `cfg_interval_progress` and the schedule block — **`duration_sec` is in none of them**, by
design: M4's own Normative row says LENGTH "lives in the **per-target settings**… **Wire name is `duration`**
on both `/generate` and `/schedule`". So `applyRenderPreset` cannot restore the length a render was made at,
and USE SETTINGS has to write it itself, through `settings.patch(target, { duration_sec })`, clamped the way
M4 T10 clamps it — *"reading `settings.current(target).duration_sec` and writing it back with
`settings.patch(target, { duration_sec })` clamped to `LENGTH_CAP_SEC`"*. This task is the second owner of
that write and uses the identical clamp, floored at `RANGES.length_sec.min` (`{ min: 1, max: 184 }`, m4 plan)
so a corrupt `duration: 0` on an old job record cannot push a target to zero length.

**REPLACE CLIP needs a store method that does not exist.** M5's `arrangement` can add, duplicate, move, trim,
loop, set BPM, set detune, set downbeats and set preview audio — there is no way to change `clip.audio`
after the clip exists. `ForgeClip.history: AudioRef[]` has been in the type since M1 T3 and **nothing has
ever written to it**: every construction site in M5 seeds `history: []` and leaves it there. This task is what
that field was for. The new `arrangement.replaceClipAudio(id, ref)` is a `Modify:` on M5's store, not a new
module, because it is three fields of one clip and M5 owns clip state.

Swapping the audio invalidates three derived things, and each is a test:
- **the stretch**, because `previewAudio` is a stretched copy of the *old* file (M5 T? `setPreviewAudio`);
- **the analysis**, because `native_bpm` and `downbeats_sec` describe the old file;
- **the latent**, because it was encoded from the old audio. M5's own precedent for this is
  `duplicateClip`: *"A latent is valid only where it was encoded, so a copy elsewhere is stale by
  definition"* — `latentState: c.latentState === "none" ? "none" : "stale"`. Same reasoning, same expression.

So the store method does the state change and `lifecycle.replaceAudio` does the async follow-up
(`ensureAnalysis` then `scheduleStretch`), exactly mirroring `lifecycle.addClip`, which already does
`arrangement.addClip` → `ensureAnalysis` → `scheduleStretch` and returns `{clip, analyzeError}` so a failed
analysis degrades honestly instead of losing the clip.

**One decision shipped, with its reason.** A render is rarely the same length as the clip it replaces. Leaving
`dur_sec` alone would let a clip claim audio that does not exist (a 30 s clip over a 12 s render plays 18 s of
silence and the timeline lies). Growing it would silently move every clip's neighbours' overlap geometry, which
is §7.2's business and not a side effect an audio swap may have. So: **`dur_sec` shrinks to the render's
length when the render is shorter, and is left alone when it is longer.** The clip never claims audio it does
not have, and no overlap is ever created by a replace. **Open question 7** carries the alternative (offer the
operator a "fit clip to render" affordance instead) to the assembly batch.

**Why the blocking rules are pure.** Both buttons are disabled for four different reasons between them and
each reason is a sentence the operator reads in a `title`. Writer A's `renderBlock` is pure for this reason and
Task 6's `renderRequest` is pure for this reason; `useSettingsBlock` and `replaceClipBlock` are the same shape,
so the table of reasons is tested without mounting anything.

**Files:**
- Create: `latent-forge/src/lib/render/previewActions.ts`,
  `latent-forge/src/lib/render/__tests__/previewActions.test.ts`,
  `latent-forge/src/lib/stores/__tests__/replaceClipAudio.test.ts`,
  `latent-forge/src/lib/clips/__tests__/replaceAudio.test.ts`,
  `latent-forge/src/ui/prompt/__tests__/previewActions.test.ts`
- Modify: `latent-forge/src/lib/stores/arrangement.svelte.ts` (M5 T1 — add `replaceClipAudio`),
  `latent-forge/src/lib/clips/lifecycle.ts` (M5 — add `replaceAudio`),
  `latent-forge/src/ui/prompt/PreviewContainer.svelte` (M1 T11, wired by Tasks 6-7 — the two buttons)

No new HELP ids: Task 6 already added `previewUseSettings` and `previewReplaceClip` and moved
`strings.test.ts` to 119. **`strings.test.ts` stays at 119.**

**Interfaces** (everything consumed, with the task that produced it):

- From `latent-forge/src/lib/render/history.svelte.ts` (**Writer A T3**):
  `interface RenderHistoryEntry { job_id: string; forge_job_id: string; file: string; label: string;
  kind: "gen"|"a2a"|"inpaint"|"mix"; dur_sec: number; source_clip_id: string | null; created: number }`;
  `history.renders: RenderHistoryEntry[]` (newest LAST in storage); `history.preview: number | null`;
  `history.refOf(e): AudioRef` → `{kind:"render", job_id: e.job_id, file: e.file}`;
  `history.jobRecord(e): Promise<JobRecord>` — `forgeApi.job(e.forge_job_id)`, which is
  `getJSON<JobRecord>("/forge/jobs/<id>")` and therefore **rejects with `ForgeApiError` on a 404 or a dead
  server**. Everything in this task that calls it is inside a `try`.
- From `latent-forge/src/lib/forge/types.ts` (**M1 T3**, extended by **Task 6** of this plan):
  `interface JobRecord { ok: true; job_id: string; op: JobOp; payload: unknown; state: JobState;
  position: number|null; progress: Progress|null; result: JobResponse|null; error: string|null;
  created: number; started: number|null; finished: number|null }` — **`payload` is `unknown`**, so every read
  of it in this task is guarded, not cast;
  `type JobOp = "generate" | "a2a_track" | "a2a_mix" | "longform" | "decode" | "bend" | "a2a_clip" |
  "inpaint" | "commit"`;
  `type Target = {kind:"none"} | {kind:"clip"; id: string} | {kind:"overlap"; key: string}`;
  `interface RenderSettings { prompt; negative_prompt; steps; cfg_scale; seed; apg_scale;
  cfg_interval_progress: [number, number]; schedule: ScheduleSpec; scale_phi; sampler_type: string | null;
  duration_sec: number }`; `AudioRef`; `interface ForgeClip { …; audio: AudioRef; native_bpm: number|null;
  downbeats_sec: number[]; previewAudio?: AudioRef | null; latentState: "none"|"valid"|"stale";
  history: AudioRef[]; op: ClipOp | null }`.
- From `latent-forge/src/lib/presets/renderPresets.ts` (**M4 T13**):
  `applyRenderPreset(into: RenderSettings, body: unknown): PresetApplyResult` where
  `interface PresetApplyResult { applied: string[]; rejected: string[] }`. It returns
  `{ applied: [], rejected: ["<body>"] }` for a non-object body (m4 plan asserts exactly
  `expect(applyRenderPreset(s, null)).toEqual({ applied: [], rejected: ["<body>"] })`), validates every field
  before it lands, ignores unknown keys and is `__proto__`-safe (m4 plan:
  `applyRenderPreset(s, { steps: 40, nonsense: 1, __proto__: { polluted: true } })`).
  **It never touches `duration_sec`** — see WHY item 3.
- From `latent-forge/src/lib/stores/settings.svelte.ts` (**M4 T2**): `settings.current(t: Target):
  RenderSettings` (**reads** — the owner's object, not a copy), `settings.editable(t: Target):
  RenderSettings` (**returns the object a write must mutate** — m4 plan's Normative row:
  *"`settings.current(t)` **reads**, `settings.editable(t)` **returns the object a write must mutate**"*),
  `settings.patch(t: Target, p: Partial<RenderSettings>): void`, `settings.scope(t)`.
- From `latent-forge/src/lib/forge/defaults.ts` (**M1 T4**): `LENGTH_CAP_SEC = 184`.
- From `latent-forge/src/lib/sampling/scheduleRules.ts` (**M4 T3**): `RANGES.length_sec` = `{ min: 1, max: 184 }`.
- From `latent-forge/src/lib/stores/arrangement.svelte.ts` (**M5 T1**): `arrangement.clips: ForgeClip[]`,
  the private `find(id)`, `arrangement.setClipBpm(id, bpm)`, `arrangement.setDownbeats(id, downbeatsSec)`,
  `arrangement.setPreviewAudio(id, ref)`, and the `$state.snapshot` discipline M5 already uses in
  `duplicateClip` (`structuredClone($state.snapshot(c))` — **`structuredClone` on a live proxy throws
  `DataCloneError`**, HANDOUT). **This task adds `replaceClipAudio(id, ref)`.**
- From `latent-forge/src/lib/clips/lifecycle.ts` (**M5**): `addClip(input: AddClipInput):
  Promise<AddClipOutcome>`, `ensureAnalysis(clipId: string): Promise<void>` (returns immediately when
  `clip.native_bpm != null` — which is why `replaceClipAudio` must null it), `scheduleStretch(clipId, onError?)`
  (debounced 400 ms, `STRETCH_DEBOUNCE_MS`), `interface AddClipOutcome { clip: ForgeClip; analyzeError:
  ForgeApiError | null }`. **This task adds `replaceAudio`.**
- From `latent-forge/src/lib/forge/api.ts` (**M1 T5**): `class ForgeApiError extends Error { readonly status: number }`.
- From `latent-forge/src/lib/stores/view.svelte.ts` (**M1 T7**): `view.selection: Target`,
  `view.selectionKey`, `view.appendLog(text: string, level?: "info" | "error"): TerminalLine` (M1 T7's
  signature, quoted in m6 plan; **Writer A T5 is what makes those lines reach TERMINAL** — Fact 8).
- From `latent-forge/src/lib/render/jobs.svelte.ts` (**Writer A T1**): `jobs.busy: boolean`,
  `jobs.lastError: {targetKey, message} | null` (§9.7's inline surface, rendered by Writer A T5).
- From Task 7 of this plan, already in `PreviewContainer.svelte`: the `entry` derived
  (`history.preview === null ? null : history.renders[history.preview] ?? null`), `target`, `clip`,
  `options`, `previewUrl`. From Task 6: `world`, `blocked`, `onRender`.
- From `latent-forge/src/lib/help/strings.ts` (**M1 T5**, extended by **Task 6**):
  `HELP.previewUseSettings`, `HELP.previewReplaceClip` — already attached by Task 6, unchanged here.

**Produces:** `src/lib/render/previewActions.ts` —
`interface PayloadSettings { body: Record<string, unknown> | null; durationSec: number | null }`,
`payloadSettings(op: JobOp, payload: unknown): PayloadSettings`,
`interface ApplyOutcome { applied: string[]; rejected: string[]; lengthSec: number | null }`,
`applyPayloadSettings(target: Target, ps: PayloadSettings): ApplyOutcome`,
`useSettingsBlock(entry: RenderHistoryEntry | null, busy: boolean): string | null`,
`replaceClipBlock(entry: RenderHistoryEntry | null, target: Target, busy: boolean): string | null`,
and the four hint constants `NO_PREVIEW_HINT`, `RENDER_RUNNING_HINT`, `NO_SETTINGS_HINT`, `NOT_THIS_CLIP_HINT`.
`arrangement.replaceClipAudio(id: string, ref: AudioRef): void`.
`lifecycle.replaceAudio(input: ReplaceAudioInput): Promise<ReplaceAudioOutcome>` with
`interface ReplaceAudioInput { clipId: string; ref: AudioRef; durationSec: number | null }` and
`interface ReplaceAudioOutcome { analyzeError: ForgeApiError | null }`.

---

- [ ] **Step 1: Write the failing pure tests for the payload reduction**

`latent-forge/src/lib/render/__tests__/previewActions.test.ts`:

```ts
import { beforeEach, describe, expect, it } from "vitest";
import { BASE_DEFAULTS, cloneRenderSettings, LENGTH_CAP_SEC } from "../../forge/defaults";
import type { RenderHistoryEntry, Target } from "../../forge/types";
import { settings } from "../../stores/settings.svelte";
import {
  applyPayloadSettings, NOT_THIS_CLIP_HINT, NO_PREVIEW_HINT, NO_SETTINGS_HINT,
  payloadSettings, RENDER_RUNNING_HINT, replaceClipBlock, useSettingsBlock,
} from "../previewActions";

const NONE: Target = { kind: "none" };
const CLIP: Target = { kind: "clip", id: "c1" };
const OVERLAP: Target = { kind: "overlap", key: "c1-c2" };

function entry(p: Partial<RenderHistoryEntry> = {}): RenderHistoryEntry {
  return {
    job_id: "gen-1", forge_job_id: "forge-1", file: "out_00.wav", label: "GEN 12:00:00",
    kind: "gen", dur_sec: 30, source_clip_id: null, created: 1, ...p,
  };
}

// Writer A T1's generatePayload: `{ ...renderWire(s, cfg), duration: cap(s.duration_sec) }`.
const GENERATE_PAYLOAD = {
  prompt: "a room", negative_prompt: "", steps: 40, cfg_scale: 7, seed: -1, apg_scale: 0,
  cfg_interval_progress: [0.1, 0.9], scale_phi: 0, sampler_type: "dpmpp-3m-sde",
  schedule: { shape: "model", rho: 7, sigma_min: 0.03, lam_min: -8, lam_max: 8, stepped: false, plateaus: [], tilt: 0 },
  duration: 62.5,
};

describe("payloadSettings — one shape per op, and the payload is never passed through whole", () => {
  it("takes generate's own body as the settings and its `duration` as the length", () => {
    const ps = payloadSettings("generate", GENERATE_PAYLOAD);
    expect(ps.durationSec).toBe(62.5);
    expect(ps.body).not.toBeNull();
    expect("duration" in (ps.body as object)).toBe(false);
    expect(ps.body).toMatchObject({ prompt: "a room", steps: 40, sampler_type: "dpmpp-3m-sde" });
  });

  it("takes a2a_clip's NESTED render object, and no length — the clip supplies that", () => {
    const ps = payloadSettings("a2a_clip", {
      audio: { kind: "upload", sha256: "a" }, render: { steps: 24, prompt: "x" },
      envelope: null, noise_level: 0.4, chain: null, ckpt_path: null,
    });
    expect(ps.body).toEqual({ steps: 24, prompt: "x" });
    expect(ps.durationSec).toBeNull();
  });

  it("takes inpaint's nested render object, and no length — the region supplies that", () => {
    const ps = payloadSettings("inpaint", {
      a: {}, b: {}, region: { start_sec: 1, end_sec: 3 }, curve: null, chroma_xfade: true,
      render: { steps: 32 }, pad_sec: 8,
    });
    expect(ps.body).toEqual({ steps: 32 });
    expect(ps.durationSec).toBeNull();
  });

  it("takes commit's top-level duration_sec and offers no settings — every lane has its own", () => {
    const ps = payloadSettings("commit", { lanes: [], clips: [], overlaps: [], duration_sec: 120 });
    expect(ps.body).toBeNull();
    expect(ps.durationSec).toBe(120);
  });

  it("never hands longform's arc string to the schedule field", () => {
    const ps = payloadSettings("longform", {
      schedule: "0:a|45:b", steps: 24, cfg_scale: 6, seed: 7, duration: 120,
    });
    expect(ps.body).toEqual({ steps: 24, cfg_scale: 6, seed: 7 });
    expect("schedule" in (ps.body as object)).toBe(false);
    expect(ps.durationSec).toBe(120);
  });

  it("offers bend's seed and nothing else", () => {
    expect(payloadSettings("bend", { crop_id: "000412", ops: [{}], seed: 11 }))
      .toEqual({ body: { seed: 11 }, durationSec: null });
  });

  it("says honestly that a decode carries no settings at all", () => {
    expect(payloadSettings("decode", { crop_id: "000412" }))
      .toEqual({ body: null, durationSec: null });
  });

  it("survives a payload that is not an object — JobRecord.payload is `unknown`", () => {
    expect(payloadSettings("generate", null)).toEqual({ body: null, durationSec: null });
    expect(payloadSettings("generate", "nope")).toEqual({ body: null, durationSec: null });
    expect(payloadSettings("a2a_clip", { render: "nope" })).toEqual({ body: null, durationSec: null });
  });

  it("ignores a non-finite or out-of-range duration rather than writing it", () => {
    expect(payloadSettings("generate", { ...GENERATE_PAYLOAD, duration: "long" }).durationSec).toBeNull();
    expect(payloadSettings("generate", { ...GENERATE_PAYLOAD, duration: 0 }).durationSec).toBeNull();
    expect(payloadSettings("generate", { ...GENERATE_PAYLOAD, duration: NaN }).durationSec).toBeNull();
  });
});
```

- [ ] **Step 2: Write the failing tests for the write half and the two block rules**

Appended to the same file. `applyPayloadSettings` is the only impure function in the module; it is still
plain `.ts` because it *uses* the settings store rather than declaring runes.

```ts
describe("applyPayloadSettings — LENGTH is M4's blind spot and this is where it is handled", () => {
  beforeEach(() => {
    settings.defaults = cloneRenderSettings(BASE_DEFAULTS);
  });

  it("writes the body through M4's validator into the object settings says is editable", () => {
    const out = applyPayloadSettings(NONE, { body: { steps: 40, prompt: "a room" }, durationSec: null });
    expect(out.applied).toEqual(expect.arrayContaining(["steps", "prompt"]));
    expect(settings.current(NONE).steps).toBe(40);
    expect(settings.current(NONE).prompt).toBe("a room");
  });

  it("writes LENGTH itself, because applyRenderPreset does not know duration_sec", () => {
    const out = applyPayloadSettings(NONE, { body: null, durationSec: 62.5 });
    expect(out.lengthSec).toBe(62.5);
    expect(settings.current(NONE).duration_sec).toBe(62.5);
  });

  it("clamps a length to LENGTH_CAP_SEC and to RANGES.length_sec.min, like M4 T10 does", () => {
    expect(applyPayloadSettings(NONE, { body: null, durationSec: 9000 }).lengthSec).toBe(LENGTH_CAP_SEC);
    expect(settings.current(NONE).duration_sec).toBe(LENGTH_CAP_SEC);
    expect(applyPayloadSettings(NONE, { body: null, durationSec: 0.2 }).lengthSec).toBe(1);
  });

  it("leaves duration_sec alone when the render had no length of its own (a2a_clip, inpaint)", () => {
    settings.patch(NONE, { duration_sec: 33 });
    applyPayloadSettings(NONE, { body: { steps: 12 }, durationSec: null });
    expect(settings.current(NONE).duration_sec).toBe(33);
  });

  it("reports what M4 rejected instead of failing the whole apply", () => {
    const out = applyPayloadSettings(NONE, { body: { steps: 40, cfg_scale: 999 }, durationSec: null });
    expect(out.applied).toContain("steps");
    expect(out.rejected).toContain("cfg_scale");
    expect(settings.current(NONE).steps).toBe(40);
  });
});

describe("useSettingsBlock — §7.1's disabled rule and X15's door", () => {
  it("blocks with an honest hint when nothing is previewed", () => {
    expect(useSettingsBlock(null, false)).toBe(NO_PREVIEW_HINT);
  });

  it("blocks while a job runs, like every other render control", () => {
    expect(useSettingsBlock(entry(), true)).toBe(RENDER_RUNNING_HINT);
  });

  it("allows a previewed render, whatever op made it — the op is only known after the fetch", () => {
    expect(useSettingsBlock(entry(), false)).toBeNull();
    expect(useSettingsBlock(entry({ kind: "mix" }), false)).toBeNull();
  });
});

describe("replaceClipBlock — enabled only when source_clip_id is the selected clip", () => {
  it("allows exactly the clip the render was made from", () => {
    expect(replaceClipBlock(entry({ source_clip_id: "c1" }), CLIP, false)).toBeNull();
  });

  it("refuses a different clip", () => {
    expect(replaceClipBlock(entry({ source_clip_id: "c9" }), CLIP, false)).toBe(NOT_THIS_CLIP_HINT);
  });

  it("refuses a render that came from no clip at all", () => {
    expect(replaceClipBlock(entry({ source_clip_id: null }), CLIP, false)).toBe(NOT_THIS_CLIP_HINT);
  });

  it("refuses a session or overlap target, where there is no clip to replace", () => {
    expect(replaceClipBlock(entry({ source_clip_id: "c1" }), NONE, false)).toBe(NOT_THIS_CLIP_HINT);
    expect(replaceClipBlock(entry({ source_clip_id: "c1" }), OVERLAP, false)).toBe(NOT_THIS_CLIP_HINT);
  });

  it("blocks on no preview and on a running job before it looks at the clip", () => {
    expect(replaceClipBlock(null, CLIP, false)).toBe(NO_PREVIEW_HINT);
    expect(replaceClipBlock(entry({ source_clip_id: "c1" }), CLIP, true)).toBe(RENDER_RUNNING_HINT);
  });
});
```

`NO_SETTINGS_HINT` is exported and asserted in Step 7's component test rather than here: it is the message
the *button* shows after the fetch comes back with a `decode` payload, which is a post-click state, not a
block rule.

- [ ] **Step 3: Run them, expect failure**

```bash
cd latent-forge && npx vitest run src/lib/render/__tests__/previewActions.test.ts
```

Expected: `Failed to resolve import "../previewActions"` — the module does not exist.

- [ ] **Step 4: Write `previewActions.ts`**

`latent-forge/src/lib/render/previewActions.ts`:

```ts
import { LENGTH_CAP_SEC } from "../forge/defaults";
import type { JobOp, RenderHistoryEntry, Target } from "../forge/types";
import { applyRenderPreset } from "../presets/renderPresets";
import { RANGES } from "../sampling/scheduleRules";
import { settings } from "../stores/settings.svelte";

export const NO_PREVIEW_HINT = "load a render from HISTORY first";
export const RENDER_RUNNING_HINT = "a render is running";
export const NO_SETTINGS_HINT = "that render carries no settings";
export const NOT_THIS_CLIP_HINT = "select the clip this render was made from";

export interface PayloadSettings {
  /** Exactly the keys applyRenderPreset may look at, or null when the op has none. */
  body: Record<string, unknown> | null;
  /** Seconds, already validated as finite and in range — or null when the op has no length. */
  durationSec: number | null;
}

function isObj(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

/** A length is only a length if it is a finite number inside RANGES.length_sec. An old job record
 *  from a server that has since changed its mind is data, not a promise. */
function durationOf(v: unknown): number | null {
  if (typeof v !== "number" || !Number.isFinite(v)) return null;
  if (v < RANGES.length_sec.min || v > LENGTH_CAP_SEC) return null;
  return v;
}

function pick(src: Record<string, unknown>, keys: string[]): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const k of keys) if (k in src) out[k] = src[k];
  return out;
}

/** Reduce a JobRecord.payload to the settings USE SETTINGS may copy. Writer A T1 builds each of
 *  these shapes; this is their one inverse, and it is total — `payload` is `unknown`. */
export function payloadSettings(op: JobOp, payload: unknown): PayloadSettings {
  if (!isObj(payload)) return { body: null, durationSec: null };

  switch (op) {
    case "generate": {
      // generatePayload: { ...renderWire(s, cfg), duration }. `duration` is not a RenderSettings key
      // and applyRenderPreset would ignore it silently, so it is removed rather than left to be.
      const { duration, ...rest } = payload;
      return { body: rest, durationSec: durationOf(duration) };
    }
    case "a2a_clip":
    case "inpaint": {
      // Both carry a nested `render` (M8 parse_render's key set) and take their length from the
      // clip or the region, never from settings.
      const render = payload.render;
      return { body: isObj(render) ? render : null, durationSec: null };
    }
    case "commit":
      // Lanes, clips and overlaps each carry their own render block; there is no session-wide one.
      return { body: null, durationSec: durationOf(payload.duration_sec) };
    case "longform": {
      // `schedule` here is the ARC STRING, not a ScheduleSpec. It must not reach applyRenderPreset.
      const body = pick(payload, ["steps", "cfg_scale", "seed"]);
      return {
        body: Object.keys(body).length > 0 ? body : null,
        durationSec: durationOf(payload.duration),
      };
    }
    case "bend": {
      const body = pick(payload, ["seed"]);
      return { body: Object.keys(body).length > 0 ? body : null, durationSec: null };
    }
    default:
      // decode, and the a2a_track / a2a_mix ops M9's UI never submits.
      return { body: null, durationSec: null };
  }
}

export interface ApplyOutcome {
  applied: string[];
  rejected: string[];
  /** The length actually written, after the clamp — or null when nothing was written. */
  lengthSec: number | null;
}

export function applyPayloadSettings(target: Target, ps: PayloadSettings): ApplyOutcome {
  const out: ApplyOutcome = { applied: [], rejected: [], lengthSec: null };

  if (ps.body !== null) {
    // editable(), not current(): M4's Normative row says current() reads and editable() returns the
    // object a write must mutate. applyRenderPreset mutates in place.
    const result = applyRenderPreset(settings.editable(target), ps.body);
    out.applied = result.applied;
    out.rejected = result.rejected;
  }

  if (ps.durationSec !== null) {
    // M4 T10's clamp, verbatim in effect: the single owner of duration_sec writes it through patch().
    const sec = Math.min(LENGTH_CAP_SEC, Math.max(RANGES.length_sec.min, ps.durationSec));
    settings.patch(target, { duration_sec: sec });
    out.lengthSec = sec;
  }

  return out;
}

export function useSettingsBlock(entry: RenderHistoryEntry | null, busy: boolean): string | null {
  if (entry === null) return NO_PREVIEW_HINT;
  if (busy) return RENDER_RUNNING_HINT;
  // Whether the op carries settings is only knowable after jobRecord() resolves, so it is not a
  // block reason — it is what the button reports afterwards.
  return null;
}

export function replaceClipBlock(
  entry: RenderHistoryEntry | null, target: Target, busy: boolean,
): string | null {
  if (entry === null) return NO_PREVIEW_HINT;
  if (busy) return RENDER_RUNNING_HINT;
  if (target.kind !== "clip") return NOT_THIS_CLIP_HINT;
  if (entry.source_clip_id === null || entry.source_clip_id !== target.id) return NOT_THIS_CLIP_HINT;
  return null;
}
```

Note `durationOf` rejects `0`: Fact-1's wire name for `generate` is `duration`, and a `0` there is either a
server that has changed its defaults or a hand-edited record. Writing it would put a target at zero length,
which no later control recovers from without the operator noticing.

- [ ] **Step 5: Run them, expect pass**

```bash
cd latent-forge && npx vitest run src/lib/render/__tests__/previewActions.test.ts
```

Expected: `Test Files  1 passed (1)` / `Tests  22 passed (22)`.

- [ ] **Step 6: Write the failing store and lifecycle tests**

`latent-forge/src/lib/stores/__tests__/replaceClipAudio.test.ts`:

```ts
import { beforeEach, describe, expect, it } from "vitest";
import type { AudioRef } from "../../forge/types";
import { arrangement } from "../arrangement.svelte";

const OLD: AudioRef = { kind: "upload", sha256: "a".repeat(64) };
const NEW: AudioRef = { kind: "render", job_id: "gen-7", file: "out_00.wav" };

function reset() {
  for (const c of [...arrangement.clips]) arrangement.removeClip(c.id);
}

beforeEach(reset);

describe("arrangement.replaceClipAudio — the first writer ForgeClip.history has ever had", () => {
  it("swaps the audio and pushes the old ref onto the clip's history", () => {
    const c = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: OLD });
    arrangement.replaceClipAudio(c.id, NEW);
    expect(c.audio).toEqual(NEW);
    expect(c.history).toEqual([OLD]);
  });

  it("keeps the order across two replacements, oldest first", () => {
    const mid: AudioRef = { kind: "render", job_id: "gen-1", file: "m.wav" };
    const c = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: OLD });
    arrangement.replaceClipAudio(c.id, mid);
    arrangement.replaceClipAudio(c.id, NEW);
    expect(c.history).toEqual([OLD, mid]);
    expect(c.audio).toEqual(NEW);
  });

  it("stores a snapshot, not the live proxy, so a later swap cannot rewrite history", () => {
    const c = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: OLD });
    arrangement.replaceClipAudio(c.id, NEW);
    // Mutating the clip's CURRENT audio must not reach the archived entry.
    (c.audio as { file: string }).file = "tampered.wav";
    expect(c.history[0]).toEqual(OLD);
  });

  it("drops the stretched preview and the analysis, which describe the old file", () => {
    const c = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: OLD, nativeBpm: 128 });
    arrangement.setDownbeats(c.id, [0.5, 1.0]);
    arrangement.setPreviewAudio(c.id, { kind: "upload", sha256: "b".repeat(64) });
    arrangement.replaceClipAudio(c.id, NEW);
    expect(c.native_bpm).toBeNull();
    expect(c.downbeats_sec).toEqual([]);
    expect(c.previewAudio ?? null).toBeNull();
    expect(c.offset_sec).toBe(0);
  });

  it("marks a valid latent stale, and leaves 'none' alone — M5's duplicateClip rule", () => {
    const a = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: OLD });
    a.latentState = "valid";
    arrangement.replaceClipAudio(a.id, NEW);
    expect(a.latentState).toBe("stale");

    const b = arrangement.addClip({ lane: 1, startSec: 0, durSec: 4, audio: OLD });
    arrangement.replaceClipAudio(b.id, NEW);
    expect(b.latentState).toBe("none");
  });

  it("is a no-op for an id that is not there", () => {
    expect(() => arrangement.replaceClipAudio("gone", NEW)).not.toThrow();
    expect(arrangement.clips).toHaveLength(0);
  });
});
```

`latent-forge/src/lib/clips/__tests__/replaceAudio.test.ts`:

```ts
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ForgeApiError } from "../../forge/api";
import type { AudioRef } from "../../forge/types";
import { arrangement } from "../../stores/arrangement.svelte";
import { replaceAudio } from "../lifecycle";

const OLD: AudioRef = { kind: "upload", sha256: "a".repeat(64) };
const NEW: AudioRef = { kind: "render", job_id: "gen-7", file: "out_00.wav" };

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

function reset() {
  for (const c of [...arrangement.clips]) arrangement.removeClip(c.id);
  arrangement.setBpm(120);
}

beforeEach(reset);
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("lifecycle.replaceAudio — the analyze/stretch follow-up, mirroring addClip", () => {
  it("re-analyzes the NEW audio, because native_bpm was cleared", async () => {
    const seen: unknown[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (url === "/forge/analyze") {
        seen.push(JSON.parse(String(init?.body)));
        return jsonResponse({
          ok: true, bpm: 96, bpm_candidates: [], beats_sec: [], downbeats_sec: [0.25],
          duration_sec: 12, source: "librosa",
        });
      }
      throw new Error(`unexpected fetch ${url}`);
    }));

    const c = arrangement.addClip({ lane: 0, startSec: 0, durSec: 30, audio: OLD, nativeBpm: 128 });
    await replaceAudio({ clipId: c.id, ref: NEW, durationSec: 12 });

    expect(c.native_bpm).toBe(96);
    expect(c.downbeats_sec).toEqual([0.25]);
    expect(JSON.stringify(seen)).toContain("gen-7");
  });

  it("shrinks dur_sec to the render when the render is shorter, so the clip never claims silence", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({
      ok: true, bpm: null, bpm_candidates: [], beats_sec: [], downbeats_sec: [], duration_sec: 12, source: "librosa",
    })));
    const c = arrangement.addClip({ lane: 0, startSec: 0, durSec: 30, audio: OLD });
    await replaceAudio({ clipId: c.id, ref: NEW, durationSec: 12 });
    expect(c.dur_sec).toBe(12);
  });

  it("leaves dur_sec alone when the render is longer — a replace never creates an overlap", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({
      ok: true, bpm: null, bpm_candidates: [], beats_sec: [], downbeats_sec: [], duration_sec: 90, source: "librosa",
    })));
    const c = arrangement.addClip({ lane: 0, startSec: 0, durSec: 30, audio: OLD });
    await replaceAudio({ clipId: c.id, ref: NEW, durationSec: 90 });
    expect(c.dur_sec).toBe(30);
  });

  it("keeps the swap when analysis fails, and hands the error back — §7.3's honest degradation", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({ ok: false, error: "no drive" }, 503)));
    const c = arrangement.addClip({ lane: 0, startSec: 0, durSec: 30, audio: OLD });
    const out = await replaceAudio({ clipId: c.id, ref: NEW, durationSec: null });
    expect(c.audio).toEqual(NEW);
    expect(c.history).toEqual([OLD]);
    expect(out.analyzeError).toBeInstanceOf(ForgeApiError);
  });

  it("does nothing at all for a clip that was removed first", async () => {
    const out = await replaceAudio({ clipId: "gone", ref: NEW, durationSec: 12 });
    expect(out.analyzeError).toBeNull();
    expect(arrangement.clips).toHaveLength(0);
  });
});
```

- [ ] **Step 7: Run them, expect failure**

```bash
cd latent-forge && npx vitest run src/lib/stores/__tests__/replaceClipAudio.test.ts src/lib/clips/__tests__/replaceAudio.test.ts
```

Expected: `TypeError: arrangement.replaceClipAudio is not a function` and
`"replaceAudio" is not exported by "src/lib/clips/lifecycle.ts"`.

- [ ] **Step 8: Add `replaceClipAudio` to M5's arrangement store**

In `latent-forge/src/lib/stores/arrangement.svelte.ts`, beside `duplicateClip` (whose latent comment this
one deliberately echoes):

```ts
  /** Spec §4.5 REPLACE CLIP. The previous audio is archived on the clip rather than dropped:
   *  ForgeClip.history has existed since M1 T3 for exactly this and nothing has written it until now.
   *  $state.snapshot, not the live proxy and not structuredClone — a proxy in the array would alias
   *  the clip's current audio, and structuredClone on a proxy throws DataCloneError. */
  replaceClipAudio(id: string, ref: AudioRef) {
    const c = this.find(id);
    if (!c) return;
    c.history.push($state.snapshot(c.audio) as AudioRef);
    c.audio = ref;
    c.offset_sec = 0;          // the new file starts where it starts
    c.previewAudio = null;     // a stretched copy of the file we just replaced
    c.native_bpm = null;       // and its analysis
    c.downbeats_sec = [];
    // A latent is valid only for the audio it was encoded from (M5 duplicateClip's rule).
    if (c.latentState !== "none") c.latentState = "stale";
  }
```

`$state.snapshot` is available here because `arrangement.svelte.ts` is a `.svelte.ts` module — it does not
exist in a plain `.ts`, which is why the archiving lives in the store and not in `lifecycle.ts`.

- [ ] **Step 9: Add `replaceAudio` to `lifecycle.ts`**

```ts
export interface ReplaceAudioInput {
  clipId: string;
  ref: AudioRef;
  /** The render's own length, from RenderHistoryEntry.dur_sec. null when it is not known. */
  durationSec: number | null;
}

export interface ReplaceAudioOutcome {
  /** Set when re-analysis failed; the swap stands regardless (spec §7.3). */
  analyzeError: ForgeApiError | null;
}

/** The async half of REPLACE CLIP, mirroring addClip: the store swaps the refs, then the analysis
 *  and the stretch are re-derived for the new file. */
export async function replaceAudio(input: ReplaceAudioInput): Promise<ReplaceAudioOutcome> {
  const clip = arrangement.clips.find((c) => c.id === input.clipId);
  if (!clip) return { analyzeError: null };

  arrangement.replaceClipAudio(clip.id, input.ref);

  // A clip must never claim audio that is not there; growing it is §7.2's business, not a swap's.
  if (input.durationSec !== null && input.durationSec > 0 && input.durationSec < clip.dur_sec) {
    arrangement.trimClip(clip.id, "end", clip.start_sec + input.durationSec);
  }

  let analyzeError: ForgeApiError | null = null;
  try {
    await ensureAnalysis(clip.id);
  } catch (e) {
    analyzeError = asApiError(e);
  }
  scheduleStretch(clip.id);
  return { analyzeError };
}
```

`trimClip(id, "end", sec)` rather than a raw `dur_sec` write: it is M5's own guarded path (it refuses a
duration under 0.05 s) and it calls `refreshStale`, so a latent that was valid at this position is handled
the same way M5 handles it everywhere else.

- [ ] **Step 10: Run them, expect pass**

```bash
cd latent-forge && npx vitest run src/lib/stores/__tests__/replaceClipAudio.test.ts src/lib/clips/__tests__/replaceAudio.test.ts
```

Expected: `replaceClipAudio.test.ts` `Tests  6 passed (6)`, `replaceAudio.test.ts` `Tests  5 passed (5)`.

- [ ] **Step 11: Write the failing component test**

`latent-forge/src/ui/prompt/__tests__/previewActions.test.ts`:

```ts
import { cleanup, fireEvent, render, waitFor } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BASE_DEFAULTS, cloneRenderSettings } from "../../../lib/forge/defaults";
import type { AudioRef, RenderHistoryEntry } from "../../../lib/forge/types";
import { history } from "../../../lib/render/history.svelte";
import { jobs } from "../../../lib/render/jobs.svelte";
import { arrangement } from "../../../lib/stores/arrangement.svelte";
import { settings } from "../../../lib/stores/settings.svelte";
import { view } from "../../../lib/stores/view.svelte";
import PreviewContainer from "../PreviewContainer.svelte";

const OLD: AudioRef = { kind: "upload", sha256: "a".repeat(64) };

function entry(p: Partial<RenderHistoryEntry> = {}): RenderHistoryEntry {
  return {
    job_id: "gen-7", forge_job_id: "forge-7", file: "out_00.wav", label: "GEN 12:00:00",
    kind: "gen", dur_sec: 12, source_clip_id: null, created: 1, ...p,
  };
}

beforeEach(() => {
  history.clear();
  jobs.active = null;
  settings.defaults = cloneRenderSettings(BASE_DEFAULTS);
  for (const c of [...arrangement.clips]) arrangement.removeClip(c.id);
  view.clearSelection();
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("USE SETTINGS — X15's explicit path", () => {
  it("is disabled with an honest title when nothing has been rendered yet", () => {
    const { getByTestId } = render(PreviewContainer);
    const b = getByTestId("preview-use-settings") as HTMLButtonElement;
    expect(b.disabled).toBe(true);
    expect(b.title).toBe("load a render from HISTORY first");
  });

  it("copies the job payload's settings AND its length into the current target", async () => {
    history.add(entry());
    vi.spyOn(history, "jobRecord").mockResolvedValue({
      ok: true, job_id: "gen-7", op: "generate",
      payload: { prompt: "a room", steps: 40, cfg_scale: 7, duration: 62.5 },
      state: "done", position: null, progress: null, result: null, error: null,
      created: 1, started: 1, finished: 2,
    } as never);

    const { getByTestId } = render(PreviewContainer);
    await fireEvent.click(getByTestId("preview-use-settings"));

    await waitFor(() => expect(settings.current(view.selection).steps).toBe(40));
    expect(settings.current(view.selection).prompt).toBe("a room");
    expect(settings.current(view.selection).duration_sec).toBe(62.5);
  });

  it("changes no audio — the converse of X15, and the only way that regression is caught", async () => {
    history.add(entry());
    history.add(entry({ job_id: "gen-8", file: "out_01.wav" }));
    const before = history.preview;
    vi.spyOn(history, "jobRecord").mockResolvedValue({
      ok: true, job_id: "gen-8", op: "generate", payload: { steps: 11 }, state: "done",
      position: null, progress: null, result: null, error: null, created: 1, started: 1, finished: 2,
    } as never);

    const { getByTestId } = render(PreviewContainer);
    await fireEvent.click(getByTestId("preview-use-settings"));
    await waitFor(() => expect(settings.current(view.selection).steps).toBe(11));
    expect(history.preview).toBe(before);
  });

  it("says so, and writes nothing, when the render carries no settings", async () => {
    history.add(entry({ kind: "gen" }));
    settings.patch(view.selection, { steps: 33 });
    vi.spyOn(history, "jobRecord").mockResolvedValue({
      ok: true, job_id: "gen-7", op: "decode", payload: { crop_id: "000412" }, state: "done",
      position: null, progress: null, result: null, error: null, created: 1, started: 1, finished: 2,
    } as never);

    const { getByTestId } = render(PreviewContainer);
    await fireEvent.click(getByTestId("preview-use-settings"));
    await waitFor(() =>
      expect((getByTestId("preview-use-settings") as HTMLButtonElement).title)
        .toBe("that render carries no settings"));
    expect(settings.current(view.selection).steps).toBe(33);
  });

  it("surfaces a failed job fetch on §9.7's inline error line instead of throwing", async () => {
    history.add(entry());
    vi.spyOn(history, "jobRecord").mockRejectedValue(new Error("job forge-7 not found"));
    const { getByTestId } = render(PreviewContainer);
    await fireEvent.click(getByTestId("preview-use-settings"));
    await waitFor(() => expect(jobs.lastError?.message).toContain("forge-7"));
  });
});

describe("REPLACE CLIP", () => {
  it("is disabled when the selected clip is not the one the render came from", async () => {
    const c = arrangement.addClip({ lane: 0, startSec: 0, durSec: 30, audio: OLD });
    history.add(entry({ source_clip_id: "someone-else" }));
    view.select({ kind: "clip", id: c.id });

    const { getByTestId } = render(PreviewContainer);
    const b = getByTestId("preview-replace-clip") as HTMLButtonElement;
    expect(b.disabled).toBe(true);
    expect(b.title).toBe("select the clip this render was made from");
  });

  it("swaps the clip's audio for the previewed render and archives the old ref", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(
      JSON.stringify({ ok: true, bpm: null, bpm_candidates: [], beats_sec: [], downbeats_sec: [], duration_sec: 12, source: "librosa" }),
      { status: 200, headers: { "content-type": "application/json" } },
    )));
    const c = arrangement.addClip({ lane: 0, startSec: 0, durSec: 30, audio: OLD });
    history.add(entry({ source_clip_id: c.id }));
    view.select({ kind: "clip", id: c.id });

    const { getByTestId } = render(PreviewContainer);
    await fireEvent.click(getByTestId("preview-replace-clip"));

    await waitFor(() => expect(c.audio).toEqual({ kind: "render", job_id: "gen-7", file: "out_00.wav" }));
    expect(c.history).toEqual([OLD]);
    expect(c.dur_sec).toBe(12);
    vi.unstubAllGlobals();
  });
});
```

- [ ] **Step 12: Run it, expect failure**

```bash
cd latent-forge && npx vitest run src/ui/prompt/__tests__/previewActions.test.ts
```

Expected: the first test fails on `expected '' to be 'load a render from HISTORY first'` — M1's button has
no `title` — and every later test fails because the buttons carry no handler.

- [ ] **Step 13: Wire the two buttons in `PreviewContainer.svelte`**

Added to the component's `<script>` (Tasks 6 and 7 already put `entry`, `target`, `clip` and `jobs` there):

```ts
  import {
    applyPayloadSettings, NO_SETTINGS_HINT, payloadSettings, replaceClipBlock, useSettingsBlock,
  } from "../../lib/render/previewActions";
  import { replaceAudio } from "../../lib/clips/lifecycle";

  /** Post-click state, not a block reason: what the last USE SETTINGS actually did. Cleared the
   *  moment the previewed render changes, so the hint can never describe a different render. */
  let useSettingsNote = $state<string | null>(null);
  let acting = $state(false);

  $effect(() => {
    // Read `entry` so this re-runs on a HISTORY change; never write state that this same effect
    // reads, or Svelte throws state_unsafe_mutation.
    void entry;
    useSettingsNote = null;
  });

  const useBlock = $derived(useSettingsBlock(entry, jobs.busy || acting));
  const replaceBlock = $derived(replaceClipBlock(entry, target, jobs.busy || acting));

  async function onUseSettings(): Promise<void> {
    if (entry === null || useBlock !== null) return;
    acting = true;
    try {
      const record = await history.jobRecord(entry);
      const ps = payloadSettings(record.op, record.payload);
      if (ps.body === null && ps.durationSec === null) {
        useSettingsNote = NO_SETTINGS_HINT;
        return;
      }
      const out = applyPayloadSettings(view.selection, ps);
      useSettingsNote = null;
      const parts = [`${out.applied.length} field(s)`];
      if (out.lengthSec !== null) parts.push(`LENGTH ${out.lengthSec.toFixed(3)} s`);
      view.appendLog(`[render] USE SETTINGS: ${parts.join(", ")} from ${entry.label}`);
      if (out.rejected.length > 0) {
        view.appendLog(`[render] USE SETTINGS ignored: ${out.rejected.join(", ")}`, "error");
      }
    } catch (e) {
      // §9.7: the job fetch is the failure the operator must see, and jobs.lastError is that surface.
      jobs.lastError = { targetKey: view.selectionKey, message: e instanceof Error ? e.message : String(e) };
    } finally {
      acting = false;
    }
  }

  async function onReplaceClip(): Promise<void> {
    if (entry === null || replaceBlock !== null || target.kind !== "clip") return;
    acting = true;
    try {
      const out = await replaceAudio({
        clipId: target.id, ref: history.refOf(entry), durationSec: entry.dur_sec || null,
      });
      if (out.analyzeError) {
        view.appendLog(`[render] REPLACE CLIP: analysis failed — ${out.analyzeError.message}`, "error");
      }
    } finally {
      acting = false;
    }
  }
```

and the two buttons become, keeping M1's testids, classes and Task 6's HELP ids exactly:

```svelte
  <button
    class="action"
    data-testid="preview-use-settings"
    data-help={HELP.previewUseSettings}
    title={useSettingsNote ?? useBlock ?? ""}
    disabled={useBlock !== null}
    onclick={onUseSettings}>USE SETTINGS</button>
  <button
    class="action"
    data-testid="preview-replace-clip"
    data-help={HELP.previewReplaceClip}
    title={replaceBlock ?? ""}
    disabled={replaceBlock !== null}
    onclick={onReplaceClip}>REPLACE CLIP</button>
```

`entry.dur_sec || null` rather than `entry.dur_sec ?? null`: Task 7's `lengthLabel` already established that
`0` here means *the result carried no duration*, and `??` would pass that `0` on as a real length.

Three runes traps are avoided on purpose and each has a line above it in the source: `acting` is folded into
the two `$derived` block calls rather than tested separately in markup, so the buttons cannot be clicked twice
while a fetch is in flight; the `$effect` that clears `useSettingsNote` reads `entry` and writes only
`useSettingsNote`, never a value it reads; and nothing here calls `structuredClone` on a clip.

- [ ] **Step 14: Run it, expect pass**

```bash
cd latent-forge && npx vitest run src/ui/prompt/__tests__/previewActions.test.ts
```

Expected: `Test Files  1 passed (1)` / `Tests  7 passed (7)`.

- [ ] **Step 15: Run the whole suite and the type check**

```bash
cd latent-forge && npx vitest run && npm run check
```

Expected: `src/lib/render/__tests__/previewActions.test.ts` 22,
`replaceClipAudio.test.ts` 6, `replaceAudio.test.ts` 5,
`src/ui/prompt/__tests__/previewActions.test.ts` 7; Tasks 6 and 7's files unchanged;
`strings.test.ts` still green at 119; M5's `lifecycle.test.ts` and `arrangement.test.ts` unchanged — the
store gains a method and no existing one changes behaviour. `npm run check` clean.

**`Tests 40 passed (40)`** for this task's four new files.

- [ ] **Step 16: Commit**

```bash
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M9 T8: USE SETTINGS reads the job payload per op (and owns LENGTH, which applyRenderPreset does not), REPLACE CLIP swaps clip audio and archives the old ref on ForgeClip.history"
```

---

**Open questions raised by this task** (numbering continues from Task 7; the assembly batch collects them):

7. **`dur_sec` on a REPLACE CLIP.** Shipped: shrink when the render is shorter, leave alone when longer,
   never grow. The alternative is an explicit "fit clip to render" affordance so the operator chooses. §4.5
   describes the button in one clause and does not say.
8. **`RENDER_RUNNING_HINT` is this task's own string**, not Writer A's `renderBlock` busy text. Two controls
   should not have two sentences for one condition; the reconcile should pick one. (`GPU busy — <id>` is
   already A's and is not duplicated here — while a GPU job runs, `jobs.busy` is true and these two buttons
   are blocked by the running-job rule before the GPU rule is reached.)
9. **`ForgeClip.history` is now written but still never read.** Nothing offers the operator a way back to an
   archived ref, and §9.2's serialisation of `history` was settled before anything wrote to it. A one-line
   UNDO on the clip inspector is the obvious follow-up and is M10's, not M9's.
