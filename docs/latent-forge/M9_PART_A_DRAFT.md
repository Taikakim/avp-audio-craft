### Task 1: `src/lib/render/payloads.ts` and `src/lib/render/jobs.svelte.ts` — the job layer

**WHY.** Every render in this app is one shape: build a payload, `POST /forge/jobs`, poll it,
turn the result into a history entry. M1 built the transport (`forgeApi.submitJob`/`pollJob`) and
M7 built the one piece of payload mapping that needed server knowledge (`chainRequest`). Nothing
has ever assembled a payload or owned "a job is running". Both live here, and both are built
before any control calls them, because the expensive failures in this milestone are payload
failures: M8's `_merge` **rejects unknown keys** rather than ignoring them
(`docs/superpowers/plans/2026-09-15-latent-forge-m8-commit-pipeline.md:284-292`:
`unknown = sorted(set(obj) - set(defaults))` … `raise ForgeError(400, f"unknown {what} field(s): …")`),
so a single stray key 400s a commit that took a minute to reach the GPU.

`RenderSettings` carries `duration_sec` (M1 T3, the field comment: *"§4.5 LENGTH, in seconds,
<= 184 … WIRE NAME: the existing server reads `duration` on /generate and /schedule"*). M8's
`RENDER_DEFAULTS` does **not** declare it
(m8:262-264: `{"prompt", "negative_prompt", "steps", "cfg_scale", "seed", "apg_scale",
"cfg_interval_progress", "schedule", "scale_phi", "sampler_type"}`). So **every** object that
reaches `parse_render` must be built key by key from that list and never spread from
`RenderSettings` — one `{...settings}` anywhere and `a2a_clip`, `inpaint` and `commit` all 400.
That is the whole reason `renderWire()` exists and why its key set is asserted, not reviewed.

The payload builders are pure and live in a non-`.svelte.ts` file so they are testable without a
runes runtime. `JobsStore` is the only thing in the client that knows a job is in flight: §7.1
*"While any job runs, every render control is disabled; the control that started it reads
`SAMPLING · N steps left`"*, which is why `busy`, `stepsLeft` and `active.targetKey` are on the
store and not on any component.

Two rules from the handout are load-bearing here and are each covered by a test.
`HANDOUT.md` "Things that will bite you": *"An abort listener added after the signal already
fired never runs. Check `signal.aborted` before registering one, or the promise never settles."* —
`submit()` re-checks `#token` after every await so a superseded job cannot write `active` again.
And *"The `$state` proxy rule … Any store method that appends must return `arr[arr.length - 1]`"* —
`submit()` returns whatever `history.add` returns, never the object it built.

**`steps_total` can be 0.** Brief Fact 5, and it is visible in M8: `plan_passes` returns
`"steps_total": sum(g["render"]["steps"] for g in a2a + inpaint)`
(m8:1518), which is `0` for a commit whose lanes hold no A2A clip and no overlap; `decode` and
`bend` never sample at all. Nothing here divides by it, and Task 2 guards the one place that does.

**Files:**
- Create: `latent-forge/src/lib/render/payloads.ts`,
  `latent-forge/src/lib/render/__tests__/payloads.test.ts`
- Create: `latent-forge/src/lib/render/jobs.svelte.ts`,
  `latent-forge/src/lib/render/__tests__/jobs.test.ts`
- Modify: `latent-forge/src/lib/forge/__tests__/recordedContract.test.ts` (M7 T10) — append the
  four job fixtures' `it.skipIf` block

**Interfaces.**

Consumed from `src/lib/forge/types.ts` (M1 T3, verified against the file — quoted below):
- `type AudioRef = {kind:"upload";sha256} | {kind:"render";job_id;file} | {kind:"crop";crop_id} | {kind:"file";root;rel} | {kind:"path";path}`
- `interface Envelope { points: [number,number,number,number]; curves: [number,number,number] }`
- `interface ScheduleSpec { shape: ScheduleShape; rho: number; sigma_min: number; lam_min: number;
  lam_max: number; stepped: boolean; plateaus: number; tilt: number }` — exactly M3 `parse_spec`'s
  eight keys (`docs/superpowers/plans/2026-09-15-latent-forge-m3-sampling-server.md:205-206`:
  `DEFAULTS = {"shape": "model", "rho": 1.0, "sigma_min": 0.01, "lam_min": -6.2, "lam_max": 2.0,
  "stepped": False, "plateaus": 6, "tilt": 0.15}`).
- `interface RenderSettings { prompt; negative_prompt; steps; cfg_scale; seed; apg_scale;
  cfg_interval_progress: [number, number]; schedule: ScheduleSpec; scale_phi;
  sampler_type: string | null; duration_sec: number }`
- `interface LaneChain { latch_on; slots:[LatchSlot,LatchSlot]; hparams:{rho,mu,gamma,n_iter,log_norms};
  film_on; film:{ckpt,gain,value}; lora_on; lora:{ckpt_path,slot,strength}; bungee_on; semitones }`
- `interface ForgeLane { index: 0|1|2|3; name: string; muted: boolean; solo: boolean; gain: number; chain: LaneChain }`
- `interface ForgeClip { id; lane: 0|1|2|3; start_sec; offset_sec; dur_sec; loop; audio: AudioRef;
  native_bpm: number|null; detune_cents; downbeats_sec: number[]; render: RenderSettings;
  a2a: null | { on: boolean; noise: number; envelope: Envelope }; latentState; history: AudioRef[] }`
  — note the **client** `a2a` shape is `{on, noise, envelope}`; the **wire** shape is
  `null | {render, envelope}`. Mapping them is this task's job (Fact 2).
- `interface OverlapParams { curve: Envelope; chroma_xfade: boolean; override: boolean;
  steps: number; cfg: number; render: RenderSettings }`
- `interface MixSpec { order: "tree"|"cascade"|"quad"; nodes: { M1:{interp,t}; M2:{…}; MX:{…} };
  quad_weights: [number,number,number,number] }`
- `interface MasterChain { latch_on: boolean; head: string; gain: number; norm_on: boolean }`
- `type JobOp = "generate" | "a2a_track" | "a2a_mix" | "longform" | "decode" | "bend" | "a2a_clip" | "inpaint" | "commit"`
- `interface Progress { job_id; op; stage; stage_index; stage_count; step; steps; steps_left_total; steps_total }`
- `interface JobRecord { ok: true; job_id; op: JobOp; payload: unknown; state: JobState;
  position: number|null; progress: Progress|null; result: JobResponse|null; error: string|null;
  created: number; started: number|null; finished: number|null }`
- `interface JobResponse { status; job_id; files: string[]; latents: string[]; urls: string[];
  seed: number|null; timings; warnings: string[]; meta: Record<string, unknown> }`
- `interface RenderHistoryEntry { job_id; forge_job_id; file; label; kind: "gen"|"a2a"|"inpaint"|"mix";
  dur_sec; source_clip_id: string|null; created: number }`

Consumed from `src/lib/forge/api.ts` (M1 T5, verified —
`submitJob: (op: JobOp, payload: unknown) => sendJSON<{ok: true; job_id: string; position: number}>("/forge/jobs", "POST", {op, payload})`;
`job: (jobId) => getJSON<JobRecord>(…)`; `cancelJob: (jobId) => sendJSON<{ok: true; state: string}>(…, "DELETE")`;
`status: () => getJSON<{ok: true; busy: boolean; job_id: string|null; log_tail: string[]; progress: Progress|null}>("/status")`;
`async pollJob(jobId, onProgress: (p: Progress) => void, signal?: AbortSignal): Promise<JobRecord>`;
`class ForgeApiError extends Error { readonly status: number }`). **`POLL_MS = 500` is module-private
in M1's `api.ts`** — it is not exported, so nothing here imports it; the cadence belongs to
`pollJob`.

Consumed from `src/lib/chains/latch.ts` (M7 T1, verified at that plan's Step 3):
`chainRequest(chain: LaneChain, heads: Record<string, LatchHeadInfo>): ChainRequest`, where
`ChainRequest` is `{latch_on; slots:[LatchSlot,LatchSlot]; hparams:{rho,mu,gamma,n_iter,log_norms};
film_on; film:{ckpt,gain,value}; lora_on; lora:{ckpt_path; slot: null; strength}; bungee_on;
semitones}` — key for key M8's `CHAIN_DEFAULTS`, and `fetchLatchHeads(): Promise<Record<string, LatchHeadInfo>>`.
`LatchHeadInfo` has at least `{name: string; default_gain: number}`.

Consumed from `src/lib/stores/arrangement.svelte.ts` (M5 T1, extended by M7 T3):
`arrangement.bpm: number`, `.lanes: ForgeLane[]`, `.clips: ForgeClip[]`,
`.overlaps: Overlap[]` (**derived**, `interface Overlap {key; lane: 0|1|2|3; start_sec; end_sec; a_id; b_id}` —
no params on it), `.peekOverlapParams(key): OverlapParams | undefined` (non-seeding, M7 T3),
`.mix: MixSpec`, `.master: MasterChain`, `.arrangementEndSec: number`.

Consumed from `src/lib/stores/settings.svelte.ts` (M4 T?, verified —
`export const settings = new SettingsStore()`): `settings.defaults: RenderSettings`,
`settings.ckptPath: string | null` (*"Set from `/info`; displayed by the top bar, carried in the
project JSON (9.2)"*), `settings.effectiveCfg(t: Target): number` (*"Spec 5.3: guidance is
distilled into POST"* — returns `1.0` when `stage === "POST"`).

Consumed from `src/lib/stores/log.svelte.ts` (M1 T11): `logStore.append(text: string, seq: number,
tone?: "text"|"dim"|"accent"|"error"): LogLine` and `logStore.seq: number`.

Produced by this task, for Tasks 2-5 and for Writer B:
- `payloads.ts`: `RENDER_WIRE_KEYS`, `type RenderWire`, `renderWire(s, cfgScale?)`,
  `CAP_SEC = 184`, `generatePayload`, `opPayload`, `a2aClipPayload`, `inpaintPayload`,
  `commitPayload`, `PayloadError`.
- `jobs.svelte.ts`: `type RenderKind`, `interface ActiveJob`, `class JobsStore`, `const jobs`.

**The two stores are declared exactly as the brief pre-declares them** (both writers cite the same
text; do not widen or rename anything):

```ts
export type RenderKind = "gen" | "a2a" | "inpaint" | "mix";
export interface ActiveJob { forgeJobId: string; op: JobOp; kind: RenderKind; sourceClipId: string | null;
  targetKey: string; progress: Progress | null; }
export class JobsStore {
  active = $state<ActiveJob | null>(null);
  lastError = $state<{ targetKey: string; message: string } | null>(null);
  get busy(): boolean;
  gpuBusyOther = $state<string | null>(null);
  get stepsLeft(): number | null;
  submit(req: { op: JobOp; payload: unknown; kind: RenderKind; sourceClipId: string | null; targetKey: string }): Promise<RenderHistoryEntry | null>;
  cancel(): Promise<void>;
}
export const jobs: JobsStore;
```

`history` (Task 3) is imported by `jobs.svelte.ts`. It is written in Task 3; until then the import
resolves against the stub Task 3 replaces — **so Task 3 must land in the same commit series before
`npm run check` is run over the app**, and this task's own vitest run stubs `history.add` with
`vi.mock`. Its one method used here is `add(e: RenderHistoryEntry): RenderHistoryEntry`, which
*returns `renders[renders.length - 1]`*.

---

- [ ] **Step 1: Write the failing payload test**

`latent-forge/src/lib/render/__tests__/payloads.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import type { Envelope, ForgeClip, ForgeLane, OverlapParams, RenderSettings } from "../../forge/types";
import { BASE_DEFAULTS, CHAIN_DEFAULTS, cloneRenderSettings } from "../../forge/defaults";
import type { LatchHeadInfo } from "../../chains/latch";
import {
  CAP_SEC, PayloadError, RENDER_WIRE_KEYS, a2aClipPayload, commitPayload,
  generatePayload, inpaintPayload, opPayload, renderWire,
} from "../payloads";

// M8 RENDER_DEFAULTS, m8 plan:262-264 -- the ONLY keys parse_render tolerates. duration_sec is
// deliberately absent: _merge 400s on it.
const M8_RENDER_KEYS = [
  "apg_scale", "cfg_interval_progress", "cfg_scale", "negative_prompt", "prompt",
  "sampler_type", "scale_phi", "schedule", "seed", "steps",
];
// M3 parse_spec DEFAULTS, m3 plan:205-206.
const M8_SCHEDULE_KEYS = ["lam_max", "lam_min", "plateaus", "rho", "shape", "sigma_min", "stepped", "tilt"];

const HEADS: Record<string, LatchHeadInfo> = {
  recurrence: { name: "recurrence", default_gain: 10 } as LatchHeadInfo,
  density: { name: "density", default_gain: 4 } as LatchHeadInfo,
};
const ENV: Envelope = { points: [0.2, 0.6, 0.6, 0.2], curves: [0, 0, 0] };
const REF = { kind: "upload", sha256: "a".repeat(64) } as const;

function settings(patch: Partial<RenderSettings> = {}): RenderSettings {
  return { ...cloneRenderSettings(BASE_DEFAULTS), ...patch };
}

function lane(index: 0 | 1 | 2 | 3): ForgeLane {
  return {
    index, name: `LANE ${index + 1}`, muted: false, solo: false, gain: 1,
    chain: structuredClone(CHAIN_DEFAULTS),
  };
}

function clip(patch: Partial<ForgeClip> = {}): ForgeClip {
  return {
    id: "c1", lane: 0, start_sec: 0, offset_sec: 0, dur_sec: 8, loop: false, audio: REF,
    native_bpm: 120, detune_cents: 0, downbeats_sec: [], render: settings(),
    a2a: null, latentState: "none", history: [], ...patch,
  } as ForgeClip;
}

function overlapParams(patch: Partial<OverlapParams> = {}): OverlapParams {
  return {
    curve: { points: [0, 0.35, 0.7, 1], curves: [0, 0, 0] }, chroma_xfade: true,
    override: false, steps: 28, cfg: 3.0, render: settings({ steps: 24, cfg_scale: 6 }), ...patch,
  };
}

function commitArgs(patch: Record<string, unknown> = {}) {
  return {
    bpm: 120,
    durationSec: 40,
    defaults: settings(),
    lanes: [lane(0), lane(1), lane(2), lane(3)],
    clips: [clip()],
    overlaps: [],
    overlapParamsOf: () => overlapParams(),
    mix: {
      order: "tree" as const,
      nodes: { M1: { interp: "lerp" as const, t: 0.5 }, M2: { interp: "lerp" as const, t: 0.5 }, MX: { interp: "lerp" as const, t: 0.5 } },
      quad_weights: [1, 1, 1, 1] as [number, number, number, number],
    },
    master: { latch_on: false, head: "none", gain: 64, norm_on: true },
    decodeLanes: false,
    heads: HEADS,
    cfgOf: (s: RenderSettings) => s.cfg_scale,
    ...patch,
  };
}

describe("renderWire -- the only object that may reach M8 parse_render", () => {
  it("emits exactly M8 RENDER_DEFAULTS' key set and drops duration_sec", () => {
    const wire = renderWire(settings({ duration_sec: 47.556 }));
    expect(Object.keys(wire).sort()).toEqual(M8_RENDER_KEYS);
    expect("duration_sec" in wire).toBe(false);
    expect(RENDER_WIRE_KEYS.slice().sort()).toEqual(M8_RENDER_KEYS);
  });

  it("emits exactly M3 parse_spec's schedule key set, as a copy", () => {
    const s = settings();
    const wire = renderWire(s);
    expect(Object.keys(wire.schedule).sort()).toEqual(M8_SCHEDULE_KEYS);
    expect(wire.schedule).not.toBe(s.schedule);
    expect(wire.cfg_interval_progress).not.toBe(s.cfg_interval_progress);
  });

  it("takes the caller's cfg so POST can send 1.0 without mutating the target (spec 5.3)", () => {
    expect(renderWire(settings({ cfg_scale: 6 }), 1.0).cfg_scale).toBe(1.0);
    expect(renderWire(settings({ cfg_scale: 6 })).cfg_scale).toBe(6);
  });

  it("refuses a non-finite number rather than sending NaN that 400s server-side", () => {
    expect(() => renderWire(settings({ steps: Number.NaN }))).toThrow(PayloadError);
  });
});

describe("generatePayload", () => {
  it("sends the wire name `duration`, never `duration_sec` (M1 Normative; HANDOUT)", () => {
    const p = generatePayload(settings({ duration_sec: 45, prompt: "dub" }));
    expect(p.duration).toBe(45);
    expect("duration_sec" in p).toBe(false);
    expect(p.prompt).toBe("dub");
  });

  it("refuses a length over the 184 s cap before the round trip", () => {
    expect(() => generatePayload(settings({ duration_sec: CAP_SEC + 1 }))).toThrow(/184/);
  });

  it("refuses an empty prompt -- _generate_impl raises `prompt is required`", () => {
    expect(() => generatePayload(settings({ prompt: "   " }))).toThrow(/prompt/);
  });
});

describe("opPayload -- the clip's OP when A2A is off (spec 7.1)", () => {
  it("decode needs a latent source and sends it unchanged", () => {
    expect(opPayload("decode", { cropId: "000412" })).toEqual({ crop_id: "000412" });
    expect(opPayload("decode", { latentPath: "/SERVER/z/a.npy" })).toEqual({ latent_path: "/SERVER/z/a.npy" });
    expect(() => opPayload("decode", {})).toThrow(/latent_path or crop_id/);
  });

  it("bend sends a non-empty ops list beside the same latent source", () => {
    const p = opPayload("bend", { cropId: "000412", ops: [{ op: "roll", amount: 0.2 }], seed: 7 });
    expect(p).toEqual({ crop_id: "000412", ops: [{ op: "roll", amount: 0.2 }], seed: 7 });
    expect(() => opPayload("bend", { cropId: "000412", ops: [] })).toThrow(/ops/);
  });

  it("longform sends the prompt-ARC STRING under `schedule` and no ScheduleSpec object", () => {
    // _longform_impl reads req["schedule"] as the arc grammar
    // (eval/explorer_render_server.py:1366 `schedule_arg = (req.get("schedule") or req.get("prompt") or "")`).
    const p = opPayload("longform", { arc: "0:pad|45:break", steps: 24, cfgScale: 6, seed: -1, durationSec: 120 });
    expect(p.schedule).toBe("0:pad|45:break");
    expect(typeof p.schedule).toBe("string");
    expect(p.duration).toBe(120);
  });

  it("longform refuses an empty arc and a length over the cap", () => {
    expect(() => opPayload("longform", { arc: "  ", steps: 24, cfgScale: 6, seed: -1, durationSec: 60 })).toThrow(/arc/);
    expect(() => opPayload("longform", { arc: "0:pad", steps: 24, cfgScale: 6, seed: -1, durationSec: CAP_SEC + 1 })).toThrow(/184/);
  });
});

describe("a2aClipPayload -- spec 6.7, validated by M8 validate_a2a_clip", () => {
  it("emits exactly the six keys validate_a2a_clip reads, with a duration_sec-free render", () => {
    const p = a2aClipPayload({
      audio: REF, render: settings({ duration_sec: 47 }), a2a: { on: true, noise: 0.35, envelope: ENV },
      chain: structuredClone(CHAIN_DEFAULTS), heads: HEADS, ckptPath: "/SERVER/x.ckpt", cfgScale: 6,
    });
    expect(Object.keys(p).sort()).toEqual(["audio", "chain", "ckpt_path", "envelope", "noise_level", "render"]);
    expect(Object.keys(p.render as object).sort()).toEqual(M8_RENDER_KEYS);
  });

  it("sends the envelope when the clip has one, and null with a flat noise_level when it does not", () => {
    const withEnv = a2aClipPayload({
      audio: REF, render: settings(), a2a: { on: true, noise: 0.35, envelope: ENV },
      chain: null, heads: HEADS, ckptPath: null, cfgScale: 6,
    });
    expect(withEnv.envelope).toEqual(ENV);
    expect(withEnv.noise_level).toBe(0.35);
    const flat = a2aClipPayload({
      audio: REF, render: settings(), a2a: { on: true, noise: 0.35, envelope: null as unknown as Envelope },
      chain: null, heads: HEADS, ckptPath: null, cfgScale: 6,
    });
    expect(flat.envelope).toBeNull();
    expect(flat.noise_level).toBe(0.35);
  });

  it("sends chainRequest's object, with lora.slot null, and null when the lane has no chain", () => {
    const chain = structuredClone(CHAIN_DEFAULTS);
    chain.lora = { ckpt_path: "/SERVER/lora.ckpt", slot: 3, strength: 0.8 };
    const p = a2aClipPayload({ audio: REF, render: settings(), a2a: { on: true, noise: 0.4, envelope: null as unknown as Envelope }, chain, heads: HEADS, ckptPath: null, cfgScale: 6 });
    expect((p.chain as { lora: unknown }).lora).toEqual({ ckpt_path: "/SERVER/lora.ckpt", slot: null, strength: 0.8 });
    const none = a2aClipPayload({ audio: REF, render: settings(), a2a: { on: true, noise: 0.4, envelope: null as unknown as Envelope }, chain: null, heads: HEADS, ckptPath: null, cfgScale: 6 });
    expect(none.chain).toBeNull();
  });

  it("refuses a noise level outside 0..1 -- validate_a2a_clip's _num(…, 0, 1)", () => {
    expect(() => a2aClipPayload({
      audio: REF, render: settings(), a2a: { on: true, noise: 1.5, envelope: null as unknown as Envelope },
      chain: null, heads: HEADS, ckptPath: null, cfgScale: 6,
    })).toThrow(/noise_level/);
  });
});

describe("inpaintPayload -- spec 6.8, validated by M8 validate_inpaint", () => {
  const args = {
    a: { audio: REF, start_sec: 0, offset_sec: 0, dur_sec: 20 },
    b: { audio: { kind: "upload", sha256: "b".repeat(64) } as const, start_sec: 16, offset_sec: 0, dur_sec: 20 },
    region: { start_sec: 16, end_sec: 20 },
    params: overlapParams(),
    cfgScale: 6,
  };

  it("emits exactly the eight keys validate_inpaint reads, with pad_sec defaulting to 8", () => {
    const p = inpaintPayload(args);
    expect(Object.keys(p).sort()).toEqual(["a", "b", "chroma_xfade", "curve", "pad_sec", "region", "render"]);
    expect(p.pad_sec).toBe(8);
    expect(Object.keys(p.render as object).sort()).toEqual(M8_RENDER_KEYS);
  });

  it("applies the overlap's LOCAL steps/cfg into the render when override is on", () => {
    const p = inpaintPayload({ ...args, params: overlapParams({ override: true, steps: 28, cfg: 3 }) });
    expect((p.render as { steps: number; cfg_scale: number }).steps).toBe(28);
    expect((p.render as { steps: number; cfg_scale: number }).cfg_scale).toBe(3);
    const off = inpaintPayload({ ...args, params: overlapParams({ override: false }) });
    expect((off.render as { steps: number }).steps).toBe(24);
  });

  it("refuses start >= end, and a padded span over the cap, before the round trip", () => {
    expect(() => inpaintPayload({ ...args, region: { start_sec: 20, end_sec: 16 } })).toThrow(/start_sec/);
    expect(() => inpaintPayload({ ...args, region: { start_sec: 0, end_sec: 180 } })).toThrow(/184/);
  });
});

describe("commitPayload -- spec 6.9, validated by M8 validate_commit", () => {
  it("emits exactly validate_commit's ten top-level keys with duration_sec at the top", () => {
    const p = commitPayload(commitArgs());
    expect(Object.keys(p).sort()).toEqual([
      "clips", "decode_lanes", "defaults", "duration_sec", "lanes", "master", "mix", "overlaps", "project_bpm",
    ]);
    expect(p.duration_sec).toBe(40);
    expect(Object.keys(p.defaults as object).sort()).toEqual(M8_RENDER_KEYS);
  });

  it("sends lanes 0,1,2,3 exactly once, each with a chainRequest chain", () => {
    const p = commitPayload(commitArgs());
    const lanes = p.lanes as { index: number; chain: Record<string, unknown> }[];
    expect(lanes.map((l) => l.index).sort()).toEqual([0, 1, 2, 3]);
    for (const l of lanes) expect(Object.keys(l.chain).sort()).toEqual(Object.keys(CHAIN_DEFAULTS).sort());
    expect(Object.keys(lanes[0]).sort()).toEqual(["chain", "gain", "index", "muted", "solo"]);
  });

  it("maps the client's {on, noise, envelope} + clip.render onto the wire's null | {render, envelope}", () => {
    const on = commitPayload(commitArgs({ clips: [clip({ a2a: { on: true, noise: 0.4, envelope: ENV } })] }));
    const wired = (on.clips as { a2a: { render: object; envelope: Envelope } | null }[])[0].a2a!;
    expect(Object.keys(wired).sort()).toEqual(["envelope", "render"]);
    expect(Object.keys(wired.render).sort()).toEqual(M8_RENDER_KEYS);
    expect(wired.envelope).toEqual(ENV);
    const off = commitPayload(commitArgs({ clips: [clip({ a2a: { on: false, noise: 0.4, envelope: ENV } })] }));
    expect((off.clips as { a2a: unknown }[])[0].a2a).toBeNull();
    const absent = commitPayload(commitArgs({ clips: [clip({ a2a: null })] }));
    expect((absent.clips as { a2a: unknown }[])[0].a2a).toBeNull();
  });

  it("emits a flat noise envelope when A2A is on with no curve, so the wire is never {render, null}", () => {
    const p = commitPayload(commitArgs({ clips: [clip({ a2a: { on: true, noise: 0.25, envelope: null as unknown as Envelope } })] }));
    const wired = (p.clips as { a2a: { envelope: Envelope } }[])[0].a2a;
    expect(wired.envelope).toEqual({ points: [0.25, 0.25, 0.25, 0.25], curves: [0, 0, 0] });
  });

  it("emits each clip with exactly validate_commit's eleven clip keys", () => {
    const p = commitPayload(commitArgs());
    expect(Object.keys((p.clips as object[])[0]).sort()).toEqual([
      "a2a", "audio", "detune_cents", "dur_sec", "id", "lane", "loop", "native_bpm", "offset_sec", "start_sec",
    ]);
  });

  it("turns the derived Overlap[] plus the OverlapParams record into a LIST of nine-key rows", () => {
    const p = commitPayload(commitArgs({
      clips: [clip({ id: "a", start_sec: 0, dur_sec: 10 }), clip({ id: "b", start_sec: 6, dur_sec: 10 })],
      overlaps: [{ key: "a-b", lane: 0 as const, start_sec: 6, end_sec: 10, a_id: "a", b_id: "b" }],
    }));
    const rows = p.overlaps as Record<string, unknown>[];
    expect(Array.isArray(rows)).toBe(true);
    expect(Object.keys(rows[0]).sort()).toEqual([
      "a_id", "b_id", "chroma_xfade", "curve", "end_sec", "key", "lane", "render", "start_sec",
    ]);
  });

  it("applies each overlap's LOCAL steps/cfg into its render before sending", () => {
    const p = commitPayload(commitArgs({
      clips: [clip({ id: "a", start_sec: 0, dur_sec: 10 }), clip({ id: "b", start_sec: 6, dur_sec: 10 })],
      overlaps: [{ key: "a-b", lane: 0 as const, start_sec: 6, end_sec: 10, a_id: "a", b_id: "b" }],
      overlapParamsOf: () => overlapParams({ override: true, steps: 28, cfg: 3 }),
    }));
    expect(((p.overlaps as { render: { steps: number; cfg_scale: number } }[])[0]).render).toMatchObject({ steps: 28, cfg_scale: 3 });
  });

  it("refuses an empty arrangement with the hint the MIXDOWN button shows", () => {
    expect(() => commitPayload(commitArgs({ clips: [] }))).toThrow(/no clips/);
  });

  it("refuses a stretch ratio outside 0.5..2 and a detune outside +/-100", () => {
    expect(() => commitPayload(commitArgs({ bpm: 120, clips: [clip({ native_bpm: 40 })] }))).toThrow(/0\.5\.\.2/);
    expect(() => commitPayload(commitArgs({ clips: [clip({ detune_cents: 150 })] }))).toThrow(/detune/);
  });

  it("refuses a master head the registry does not list while latch_on", () => {
    expect(() => commitPayload(commitArgs({ master: { latch_on: true, head: "ghost", gain: 64, norm_on: true } }))).toThrow(/master head/);
    expect(() => commitPayload(commitArgs({ master: { latch_on: false, head: "ghost", gain: 64, norm_on: true } }))).not.toThrow();
  });

  it("refuses a duration over the cap", () => {
    expect(() => commitPayload(commitArgs({ durationSec: CAP_SEC + 0.1 }))).toThrow(/184/);
  });
});
```

- [ ] **Step 2: Run it, expect failure**

```bash
cd latent-forge && npx vitest run src/lib/render/__tests__/payloads.test.ts
```

Expected: `Error: Failed to resolve import "../payloads" from "src/lib/render/__tests__/payloads.test.ts"`.

- [ ] **Step 3: Write `latent-forge/src/lib/render/payloads.ts`**

```ts
// Pure builders for every /forge/jobs payload (spec §6.7-6.9, §7.1). Nothing here touches a store
// or a rune: the caller reads state and hands it in, so each builder is a table-testable function.
//
// THE RULE THIS FILE EXISTS FOR: M8's `_merge` REJECTS unknown keys --
//   unknown = sorted(set(obj) - set(defaults))
//   if unknown: raise ForgeError(400, f"unknown {what} field(s): {', '.join(unknown)}")
// (m8 plan:284-292). `RENDER_DEFAULTS` has no `duration_sec` (m8 plan:262-264), but M1's
// RenderSettings does (§4.5 LENGTH). So a render object is built key by key from
// RENDER_WIRE_KEYS and NEVER spread from RenderSettings. `generate` is the one op that carries a
// length, under the wire name `duration` (_generate_impl reads `duration`; a `duration_sec` there
// is silently ignored and renders 47 s -- HANDOUT, "A payload key the server does not read is
// silently ignored").

import { chainRequest, type ChainRequest, type LatchHeadInfo } from "../chains/latch";
import type {
  AudioRef, Envelope, ForgeClip, ForgeLane, JobOp, MasterChain, MixSpec, OverlapParams,
  RenderSettings, ScheduleSpec,
} from "../forge/types";

/** Client-side refusal, raised before the round trip. Carries the server's own wording where the
 *  server has one, so an operator sees the same sentence whichever side caught it. */
export class PayloadError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "PayloadError";
  }
}

/** eval/forge/contract.py:301 `CAP_SEC = 184.0`. check_cap's message is quoted verbatim below. */
export const CAP_SEC = 184;
const CAP_MESSAGE = "forge passes are capped at 184 s locally (T<2048)";

/** M8 RENDER_DEFAULTS' key set, in the spec's field order (m8 plan:262-264). */
export const RENDER_WIRE_KEYS = [
  "prompt", "negative_prompt", "steps", "cfg_scale", "seed", "apg_scale",
  "cfg_interval_progress", "schedule", "scale_phi", "sampler_type",
] as const;

export interface RenderWire {
  prompt: string;
  negative_prompt: string;
  steps: number;
  cfg_scale: number;
  seed: number;
  apg_scale: number;
  cfg_interval_progress: [number, number];
  schedule: ScheduleSpec;
  scale_phi: number;
  sampler_type: string | null;
}

function num(v: number, lo: number, hi: number, what: string): number {
  if (typeof v !== "number" || !Number.isFinite(v) || v < lo || v > hi) {
    throw new PayloadError(`${what}=${String(v)} outside ${lo}..${hi}`);
  }
  return v;
}

function cap(durationSec: number, what: string): number {
  if (typeof durationSec !== "number" || !Number.isFinite(durationSec) || durationSec <= 0) {
    throw new PayloadError(`${what}: duration must be a positive number`);
  }
  if (durationSec > CAP_SEC) throw new PayloadError(CAP_MESSAGE);
  return durationSec;
}

/** M3 parse_spec's eight keys, copied one by one (m3 plan:205-206). */
function scheduleWire(s: ScheduleSpec): ScheduleSpec {
  return {
    shape: s.shape,
    rho: num(s.rho, 0.1, 15, "schedule.rho"),
    sigma_min: num(s.sigma_min, 0.001, 0.5, "schedule.sigma_min"),
    lam_min: num(s.lam_min, -12, 0, "schedule.lam_min"),
    lam_max: num(s.lam_max, 0, 6, "schedule.lam_max"),
    stepped: s.stepped === true,
    plateaus: num(s.plateaus, 2, 24, "schedule.plateaus"),
    tilt: num(s.tilt, 0, 1, "schedule.tilt"),
  };
}

/**
 * The ONLY object that may be handed to M8's parse_render. `cfgScale` is a parameter rather than a
 * read of `s.cfg_scale` so the POST stage can send 1.0 (spec §5.3, `settings.effectiveCfg`) without
 * mutating the target the user is editing. Ranges mirror parse_render's `_num` calls so a bad field
 * is named here instead of coming back as an opaque 400 a minute later.
 */
export function renderWire(s: RenderSettings, cfgScale: number = s.cfg_scale): RenderWire {
  const cip = s.cfg_interval_progress;
  const lo = num(cip?.[0] ?? 0, 0, 1, "cfg_interval_progress[0]");
  const hi = num(cip?.[1] ?? 1, 0, 1, "cfg_interval_progress[1]");
  if (lo > hi) throw new PayloadError("render.cfg_interval_progress lo must be <= hi");
  return {
    prompt: s.prompt ?? "",
    negative_prompt: s.negative_prompt ?? "",
    steps: num(s.steps, 1, 150, "render.steps"),
    cfg_scale: num(cfgScale, 0, 64, "render.cfg_scale"),
    seed: num(s.seed, -1, 2 ** 31 - 1, "render.seed"),
    apg_scale: num(s.apg_scale, 0, 1, "render.apg_scale"),
    cfg_interval_progress: [lo, hi],
    schedule: scheduleWire(s.schedule),
    scale_phi: num(s.scale_phi, 0, 1, "render.scale_phi"),
    sampler_type: s.sampler_type === "" ? null : s.sampler_type,
  };
}

// ------------------------------------------------------------------ generate (spec §7.1 row 1)

/**
 * `generate` does NOT go through parse_render: M2 registers the first six ops with
 * `_validate_existing`, which only checks the cap (m2 plan:1747-1751), and `_generate_impl` reads
 * the request key by key. The wire length is `duration` (server:1122 `duration = _f(req, "duration", 47.0)`).
 * No `chain` is sent: _generate_impl reads top-level `latch`/`film`/`dora` in chain_to_request's
 * ALREADY-MAPPED shape, which needs the head gains the client deliberately does not compute
 * (M7 T1's WHY). §7.1 row 1 is session defaults only, so nothing is lost.
 */
export function generatePayload(s: RenderSettings, cfgScale: number = s.cfg_scale): Record<string, unknown> {
  const wire = renderWire(s, cfgScale);
  if (!wire.prompt.trim()) throw new PayloadError("prompt is required");
  return { ...wire, duration: cap(s.duration_sec, "generate") };
}

// ------------------------------------------------------------------ the clip's OP (spec §7.1 row 3)

export interface OpArgs {
  cropId?: string;
  latentPath?: string;
  ops?: unknown[];
  seed?: number;
  arc?: string;
  steps?: number;
  cfgScale?: number;
  durationSec?: number;
}

function latentSource(a: OpArgs): Record<string, unknown> {
  if (a.latentPath) return { latent_path: a.latentPath };
  if (a.cropId) return { crop_id: a.cropId };
  // _decode_impl / _bend_impl both raise exactly this (server:1977, 2032).
  throw new PayloadError("need latent_path or crop_id");
}

/**
 * `decode`, `longform`, `bend` -- the three of §7.1's OP column M9 can reach. `a2a_track`/`a2a_mix`
 * need a server-side audio PATH rather than an AudioRef and have no UI in this milestone; they stay
 * unbuilt rather than half-built (open question 3).
 *
 * The `longform` collision is real and is why `arc` is a separate field: `_longform_impl` reads
 * `req["schedule"]` as the PROMPT-ARC STRING (server:1366,
 * `schedule_arg = (req.get("schedule") or req.get("prompt") or "").strip()`), while M3 T2 makes
 * `resolve_shift(req, ...)` read `req["schedule"]` as a ScheduleSpec OBJECT on the same path. One
 * key, two meanings. This builder therefore sends the arc string and NO ScheduleSpec on longform.
 */
export function opPayload(op: Extract<JobOp, "decode" | "longform" | "bend">, a: OpArgs): Record<string, unknown> {
  if (op === "decode") return latentSource(a);
  if (op === "bend") {
    if (!Array.isArray(a.ops) || a.ops.length === 0) {
      throw new PayloadError("ops must be a non-empty list of bend-op dicts");
    }
    return { ...latentSource(a), ops: a.ops, seed: a.seed ?? -1 };
  }
  const arc = (a.arc ?? "").trim();
  if (!arc) throw new PayloadError("schedule is required ('0:promptA|45:promptB|...' arc grammar)");
  return {
    schedule: arc,
    steps: num(a.steps ?? 24, 1, 150, "steps"),
    cfg_scale: num(a.cfgScale ?? 6, 0, 64, "cfg_scale"),
    seed: a.seed ?? -1,
    duration: cap(a.durationSec ?? 120, "longform"),
  };
}

// ------------------------------------------------------------------ a2a_clip (spec §6.7)

export interface A2AClipArgs {
  audio: AudioRef;
  render: RenderSettings;
  a2a: { on: boolean; noise: number; envelope: Envelope | null };
  chain: ForgeLane["chain"] | null;
  heads: Record<string, LatchHeadInfo>;
  ckptPath: string | null;
  cfgScale?: number;
}

/**
 * Six keys, exactly validate_a2a_clip's (m8 plan:1944-1954). The source is the WHOLE FILE: M8 takes
 * no offset, dur or stretch here (`duration = check_cap(audio.shape[1] / SR, "a2a_clip")`), so a
 * trimmed clip is A2A'd whole. That is the server's behaviour, not a client simplification --
 * Writer B's REPLACE CLIP has to keep the clip's own trim afterwards (open question 4).
 */
export function a2aClipPayload(a: A2AClipArgs): Record<string, unknown> {
  return {
    audio: a.audio,
    render: renderWire(a.render, a.cfgScale ?? a.render.cfg_scale),
    envelope: a.a2a.envelope ?? null,
    noise_level: num(a.a2a.noise, 0, 1, "noise_level"),
    chain: a.chain === null ? null : chainRequest(a.chain, a.heads),
    ckpt_path: a.ckptPath || null,
  };
}

// ------------------------------------------------------------------ inpaint (spec §6.8)

export interface InpaintSide { audio: AudioRef; start_sec: number; offset_sec: number; dur_sec: number }

export interface InpaintArgs {
  a: InpaintSide;
  b: InpaintSide;
  region: { start_sec: number; end_sec: number };
  params: OverlapParams;
  padSec?: number;
  cfgScale?: number;
}

/** LOCAL is the overlap's own steps/cfg override (spec §7.2: `{curve, chroma_xfade, override,
 *  steps, cfg, render}`). §6.8 says the render arrives with "steps/cfg already resolved by the
 *  client", so the override is folded in here and nowhere else. */
function withLocal(params: OverlapParams, cfgScale?: number): RenderWire {
  const base = renderWire(params.render, cfgScale ?? params.render.cfg_scale);
  if (!params.override) return base;
  return { ...base, steps: num(params.steps, 1, 150, "overlap.steps"), cfg_scale: num(params.cfg, 0, 64, "overlap.cfg") };
}

export function inpaintPayload(a: InpaintArgs): Record<string, unknown> {
  const { start_sec: rs, end_sec: re } = a.region;
  num(rs, 0, 1e5, "region.start_sec");
  num(re, 0, 1e5, "region.end_sec");
  if (!(rs < re)) throw new PayloadError("region start_sec < end_sec required");
  const pad = num(a.padSec ?? 8, 0, 60, "pad_sec");
  cap(re + pad - Math.max(0, rs - pad), "inpaint");
  return {
    a: { audio: a.a.audio, start_sec: a.a.start_sec, offset_sec: a.a.offset_sec, dur_sec: a.a.dur_sec },
    b: { audio: a.b.audio, start_sec: a.b.start_sec, offset_sec: a.b.offset_sec, dur_sec: a.b.dur_sec },
    region: { start_sec: rs, end_sec: re },
    curve: a.params.curve,
    chroma_xfade: a.params.chroma_xfade,
    render: withLocal(a.params, a.cfgScale),
    pad_sec: pad,
  };
}

// ------------------------------------------------------------------ commit (spec §6.9)

export interface DerivedOverlap {
  key: string; lane: 0 | 1 | 2 | 3; start_sec: number; end_sec: number; a_id: string; b_id: string;
}

export interface CommitArgs {
  bpm: number;
  durationSec: number;
  defaults: RenderSettings;
  lanes: ForgeLane[];
  clips: ForgeClip[];
  overlaps: DerivedOverlap[];
  overlapParamsOf: (key: string) => OverlapParams;
  mix: MixSpec;
  master: MasterChain;
  decodeLanes: boolean;
  heads: Record<string, LatchHeadInfo>;
  cfgOf?: (s: RenderSettings) => number;
}

const FLAT_CURVES: [number, number, number] = [0, 0, 0];

/** A2A on with no drawn envelope is a FLAT curve at the noise level, not a null: the wire shape is
 *  `null | {render, envelope}` and validate_envelope 400s on a null envelope inside an a2a object
 *  (m8 plan:1437-1441). The per-clip noise level has no other home on this op. */
function clipEnvelope(a2a: { noise: number; envelope: Envelope | null }): Envelope {
  if (a2a.envelope) return a2a.envelope;
  const n = num(a2a.noise, 0, 1, "clip a2a noise");
  return { points: [n, n, n, n], curves: [...FLAT_CURVES] as [number, number, number] };
}

export function commitPayload(a: CommitArgs): Record<string, unknown> {
  const cfgOf = a.cfgOf ?? ((s: RenderSettings) => s.cfg_scale);
  num(a.bpm, 20, 300, "project_bpm");
  cap(a.durationSec, "commit");
  if (a.clips.length === 0) throw new PayloadError("nothing to commit — the arrangement has no clips");

  const indexes = a.lanes.map((l) => l.index).sort();
  if (indexes.length !== 4 || indexes.join(",") !== "0,1,2,3") {
    throw new PayloadError("lanes must list indexes 0, 1, 2, 3 exactly once");
  }

  const clips = a.clips.map((c) => {
    if (c.native_bpm != null) {
      const ratio = a.bpm / c.native_bpm;
      if (!(ratio >= 0.5 && ratio <= 2)) {
        throw new PayloadError(`clip ${c.id}: stretch ratio ${ratio.toFixed(3)} outside 0.5..2`);
      }
    }
    return {
      id: c.id,
      lane: c.lane,
      start_sec: num(c.start_sec, 0, CAP_SEC, `clip ${c.id} start_sec`),
      offset_sec: num(c.offset_sec, 0, 1e5, `clip ${c.id} offset_sec`),
      dur_sec: num(c.dur_sec, 1e-3, CAP_SEC, `clip ${c.id} dur_sec`),
      loop: c.loop === true,
      audio: c.audio,
      native_bpm: c.native_bpm,
      detune_cents: num(c.detune_cents, -100, 100, `clip ${c.id} detune`),
      // The client keeps {on, noise, envelope} + clip.render; the wire is null | {render, envelope}.
      a2a: c.a2a && c.a2a.on
        ? { render: renderWire(c.render, cfgOf(c.render)), envelope: clipEnvelope(c.a2a) }
        : null,
    };
  });

  // `arrangement.overlaps` is a DERIVED list with no params on it; the params live in a record
  // keyed by "<a>-<b>". M8 wants ONE list with both halves merged (Fact 2).
  const overlaps = a.overlaps.map((o) => {
    const p = a.overlapParamsOf(o.key);
    return {
      key: o.key, lane: o.lane, start_sec: o.start_sec, end_sec: o.end_sec,
      a_id: o.a_id, b_id: o.b_id, curve: p.curve, chroma_xfade: p.chroma_xfade,
      render: withLocal(p, cfgOf(p.render)),
    };
  });

  if (a.master.latch_on && !Object.prototype.hasOwnProperty.call(a.heads, a.master.head)) {
    throw new PayloadError(`unknown master head ${JSON.stringify(a.master.head)}`);
  }

  return {
    project_bpm: a.bpm,
    duration_sec: a.durationSec,              // top level, NOT inside `defaults` (Fact 1)
    defaults: renderWire(a.defaults, cfgOf(a.defaults)),
    lanes: a.lanes
      .slice()
      .sort((x, y) => x.index - y.index)
      .map((l) => ({
        index: l.index, muted: l.muted === true, solo: l.solo === true,
        gain: num(l.gain, 0, 2, "lane.gain"), chain: chainRequest(l.chain, a.heads),
      })),
    clips,
    overlaps,
    mix: {
      order: a.mix.order,
      nodes: {
        M1: { interp: a.mix.nodes.M1.interp, t: num(a.mix.nodes.M1.t, 0, 1, "mix node M1 t") },
        M2: { interp: a.mix.nodes.M2.interp, t: num(a.mix.nodes.M2.t, 0, 1, "mix node M2 t") },
        MX: { interp: a.mix.nodes.MX.interp, t: num(a.mix.nodes.MX.t, 0, 1, "mix node MX t") },
      },
      quad_weights: a.mix.quad_weights,
    },
    master: {
      latch_on: a.master.latch_on === true, head: a.master.head,
      gain: num(a.master.gain, 0, 120, "master.gain"), norm_on: a.master.norm_on === true,
    },
    decode_lanes: a.decodeLanes === true,
  };
}
```

- [ ] **Step 4: Run it, expect pass**

```bash
cd latent-forge && npx vitest run src/lib/render/__tests__/payloads.test.ts
```

Expected: `Test Files  1 passed (1)` / `Tests  29 passed (29)`.

- [ ] **Step 5: Write the failing jobs-store test**

`latent-forge/src/lib/render/__tests__/jobs.test.ts`:

```ts
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ForgeApiError, forgeApi } from "../../forge/api";
import type { JobRecord, Progress, RenderHistoryEntry } from "../../forge/types";
import { logStore } from "../../stores/log.svelte";
import { history } from "../history.svelte";
import { jobs } from "../jobs.svelte";

function progress(patch: Partial<Progress> = {}): Progress {
  return {
    job_id: "forge-1", op: "commit", stage: "", stage_index: 0, stage_count: 0,
    step: 0, steps: 0, steps_left_total: 12, steps_total: 24, ...patch,
  };
}

function done(patch: Partial<JobRecord> = {}): JobRecord {
  return {
    ok: true, job_id: "forge-1", op: "generate", payload: {}, state: "done", position: null,
    progress: null, error: null, created: 1_700_000_000, started: 1_700_000_001,
    finished: 1_700_000_040,
    result: {
      status: "ok", job_id: "gen-20260926-1", files: ["/SERVER/out/gen-1/out_00.wav"],
      latents: [], urls: ["/audio/gen-20260926-1/out_00.wav"], seed: 7,
      timings: { total_sec: 39, per_stage: {} }, warnings: [], meta: { duration_sec: 45 },
    },
    ...patch,
  };
}

const SUBMIT = { op: "generate" as const, payload: { prompt: "dub" }, kind: "gen" as const, sourceClipId: null, targetKey: "session" };

beforeEach(() => {
  jobs.active = null;
  jobs.lastError = null;
  jobs.gpuBusyOther = null;
  history.clear();
  logStore.clear();
});
afterEach(() => vi.restoreAllMocks());

describe("submit", () => {
  it("holds one ActiveJob while it runs and clears it when the job finishes", async () => {
    vi.spyOn(forgeApi, "submitJob").mockResolvedValue({ ok: true, job_id: "forge-1", position: 0 });
    let seen: unknown = "not started";
    vi.spyOn(forgeApi, "pollJob").mockImplementation(async () => {
      seen = jobs.active && { ...jobs.active };
      return done();
    });
    await jobs.submit(SUBMIT);
    expect(seen).toMatchObject({ forgeJobId: "forge-1", op: "generate", kind: "gen", targetKey: "session" });
    expect(jobs.active).toBeNull();
  });

  it("busy is true for the whole round trip and false again afterwards", async () => {
    vi.spyOn(forgeApi, "submitJob").mockResolvedValue({ ok: true, job_id: "forge-1", position: 0 });
    const busyDuring: boolean[] = [];
    vi.spyOn(forgeApi, "pollJob").mockImplementation(async () => { busyDuring.push(jobs.busy); return done(); });
    expect(jobs.busy).toBe(false);
    await jobs.submit(SUBMIT);
    expect(busyDuring).toEqual([true]);
    expect(jobs.busy).toBe(false);
  });

  it("busy is also true when the GPU is held by a job this client did not start", () => {
    expect(jobs.busy).toBe(false);
    jobs.gpuBusyOther = "dash-77";
    expect(jobs.busy).toBe(true);
  });

  it("stepsLeft tracks progress.steps_left_total and is null with no progress", async () => {
    vi.spyOn(forgeApi, "submitJob").mockResolvedValue({ ok: true, job_id: "forge-1", position: 0 });
    const seen: (number | null)[] = [];
    vi.spyOn(forgeApi, "pollJob").mockImplementation(async (_id, onProgress) => {
      seen.push(jobs.stepsLeft);
      onProgress(progress({ steps_left_total: 12 }));
      seen.push(jobs.stepsLeft);
      onProgress(progress({ steps_left_total: 3 }));
      seen.push(jobs.stepsLeft);
      return done();
    });
    await jobs.submit(SUBMIT);
    expect(seen).toEqual([null, 12, 3]);
    expect(jobs.stepsLeft).toBeNull();
  });

  it("survives steps_total 0 -- a commit with no sampling passes, decode, bend (Fact 5)", async () => {
    vi.spyOn(forgeApi, "submitJob").mockResolvedValue({ ok: true, job_id: "forge-1", position: 0 });
    vi.spyOn(forgeApi, "pollJob").mockImplementation(async (_id, onProgress) => {
      onProgress(progress({ steps_total: 0, steps_left_total: 0 }));
      expect(jobs.stepsLeft).toBe(0);
      expect(Number.isFinite(jobs.active?.progress?.steps_total ?? NaN)).toBe(true);
      return done();
    });
    await expect(jobs.submit(SUBMIT)).resolves.not.toBeNull();
  });

  it("builds the history entry from the result: job_id, the basename of urls[0], the kind", async () => {
    vi.spyOn(forgeApi, "submitJob").mockResolvedValue({ ok: true, job_id: "forge-1", position: 0 });
    vi.spyOn(forgeApi, "pollJob").mockResolvedValue(done());
    const entry = (await jobs.submit(SUBMIT)) as RenderHistoryEntry;
    expect(entry).toMatchObject({
      job_id: "gen-20260926-1", forge_job_id: "forge-1", file: "out_00.wav",
      kind: "gen", source_clip_id: null,
    });
    expect(entry.created).toBeGreaterThan(1_600_000_000);
    expect(history.renders).toHaveLength(1);
  });

  it("returns the store's live entry, not the object it built ($state proxy rule)", async () => {
    vi.spyOn(forgeApi, "submitJob").mockResolvedValue({ ok: true, job_id: "forge-1", position: 0 });
    vi.spyOn(forgeApi, "pollJob").mockResolvedValue(done());
    const entry = await jobs.submit(SUBMIT);
    expect(entry).toBe(history.renders[history.renders.length - 1]);
  });

  it("clears the previous inline error when a new render starts (§9.7)", async () => {
    jobs.lastError = { targetKey: "session", message: "old" };
    vi.spyOn(forgeApi, "submitJob").mockResolvedValue({ ok: true, job_id: "forge-1", position: 0 });
    vi.spyOn(forgeApi, "pollJob").mockResolvedValue(done());
    await jobs.submit(SUBMIT);
    expect(jobs.lastError).toBeNull();
  });

  it("surfaces a 400 as lastError on the target that asked, logs it red, and resolves null", async () => {
    vi.spyOn(forgeApi, "submitJob").mockRejectedValue(new ForgeApiError(400, "unknown render field(s): duration_sec"));
    await expect(jobs.submit({ ...SUBMIT, targetKey: "clip:c1" })).resolves.toBeNull();
    expect(jobs.lastError).toEqual({ targetKey: "clip:c1", message: "unknown render field(s): duration_sec" });
    expect(jobs.active).toBeNull();
    expect(logStore.lines.at(-1)).toMatchObject({ tone: "error" });
    expect(logStore.lines.at(-1)?.text).toContain("duration_sec");
  });

  it("surfaces a 409 queue-full as a message rather than throwing", async () => {
    vi.spyOn(forgeApi, "submitJob").mockRejectedValue(new ForgeApiError(409, "job queue full"));
    await expect(jobs.submit(SUBMIT)).resolves.toBeNull();
    expect(jobs.lastError?.message).toContain("job queue full");
  });

  it("surfaces a mid-poll server error and leaves no active job behind", async () => {
    vi.spyOn(forgeApi, "submitJob").mockResolvedValue({ ok: true, job_id: "forge-1", position: 0 });
    vi.spyOn(forgeApi, "pollJob").mockRejectedValue(new ForgeApiError(500, "non-finite latents in lane 2"));
    await expect(jobs.submit(SUBMIT)).resolves.toBeNull();
    expect(jobs.lastError?.message).toContain("non-finite latents");
    expect(jobs.active).toBeNull();
    expect(history.renders).toHaveLength(0);
  });

  it("a superseded job never writes active again, and never adds a second history entry", async () => {
    // Abort ordering, HANDOUT: "An abort listener added after the signal already fired never runs."
    vi.spyOn(forgeApi, "submitJob").mockResolvedValue({ ok: true, job_id: "forge-1", position: 0 });
    let release: (r: JobRecord) => void = () => {};
    vi.spyOn(forgeApi, "pollJob")
      .mockImplementationOnce(() => new Promise<JobRecord>((res) => { release = res; }))
      .mockImplementationOnce(async () => done({ job_id: "forge-2" }));
    const first = jobs.submit(SUBMIT);
    const second = jobs.submit({ ...SUBMIT, targetKey: "clip:c9" });
    release(done({ job_id: "forge-1" }));
    await expect(first).resolves.toBeNull();
    await second;
    expect(jobs.active).toBeNull();
    expect(history.renders).toHaveLength(1);
    expect(history.renders[0].forge_job_id).toBe("forge-2");
  });
});

describe("cancel", () => {
  it("cancels a queued job and clears active", async () => {
    vi.spyOn(forgeApi, "cancelJob").mockResolvedValue({ ok: true, state: "cancelled" });
    jobs.active = { forgeJobId: "forge-1", op: "commit", kind: "mix", sourceClipId: null, targetKey: "mix", progress: null };
    await jobs.cancel();
    expect(forgeApi.cancelJob).toHaveBeenCalledWith("forge-1");
    expect(jobs.active).toBeNull();
  });

  it("surfaces the 409 on a running pass instead of throwing, and keeps the job active", async () => {
    vi.spyOn(forgeApi, "cancelJob").mockRejectedValue(new ForgeApiError(409, "cannot cancel a running pass"));
    jobs.active = { forgeJobId: "forge-1", op: "commit", kind: "mix", sourceClipId: null, targetKey: "mix", progress: null };
    await expect(jobs.cancel()).resolves.toBeUndefined();
    expect(jobs.lastError?.message).toContain("cannot cancel a running pass");
    expect(jobs.active?.forgeJobId).toBe("forge-1");
  });

  it("is a no-op with nothing running", async () => {
    const spy = vi.spyOn(forgeApi, "cancelJob");
    await jobs.cancel();
    expect(spy).not.toHaveBeenCalled();
  });
});

describe("gpuBusyOther (§9.7 `GPU busy — <job_id>`)", () => {
  it("is set from /status when the GPU holds a job this client did not start", async () => {
    vi.spyOn(forgeApi, "status").mockResolvedValue({ ok: true, busy: true, job_id: "dash-77", log_tail: [], progress: null });
    await jobs.pollStatusOnce();
    expect(jobs.gpuBusyOther).toBe("dash-77");
  });

  it("stays null for this client's own job and clears when the GPU goes idle", async () => {
    jobs.active = { forgeJobId: "forge-1", op: "generate", kind: "gen", sourceClipId: null, targetKey: "session", progress: null };
    vi.spyOn(forgeApi, "status").mockResolvedValue({ ok: true, busy: true, job_id: "forge-1", log_tail: [], progress: null });
    await jobs.pollStatusOnce();
    expect(jobs.gpuBusyOther).toBeNull();
    vi.spyOn(forgeApi, "status").mockResolvedValue({ ok: true, busy: false, job_id: null, log_tail: [], progress: null });
    await jobs.pollStatusOnce();
    expect(jobs.gpuBusyOther).toBeNull();
  });

  it("swallows a dead server -- a stopped render server is a normal state on this box", async () => {
    jobs.gpuBusyOther = "dash-77";
    vi.spyOn(forgeApi, "status").mockRejectedValue(new ForgeApiError(502, "render server unreachable"));
    await expect(jobs.pollStatusOnce()).resolves.toBeUndefined();
    expect(jobs.gpuBusyOther).toBeNull();
  });
});
```

- [ ] **Step 6: Run it, expect failure**

```bash
cd latent-forge && npx vitest run src/lib/render/__tests__/jobs.test.ts
```

Expected: `Error: Failed to resolve import "../jobs.svelte" from "src/lib/render/__tests__/jobs.test.ts"`.

- [ ] **Step 7: Write `latent-forge/src/lib/render/jobs.svelte.ts`**

```ts
// The one place that knows a render is in flight (spec §7.1: "While any job runs, every render
// control is disabled; the control that started it reads SAMPLING · N steps left").
//
// At most ONE active job. A second click while one runs does not queue: §7.1, "A second click
// queues nothing; the queue exists for the Dash explorer and scripted use." `submit` therefore
// supersedes -- it aborts the in-flight poll and takes over -- and the superseded call resolves
// null without writing `active` or `history` again.
//
// #token is the superseding guard. `signal.aborted` is checked FIRST everywhere a listener could
// be added (HANDOUT: "An abort listener added after the signal already fired never runs"), and
// after every await the token is re-compared, because an abort only stops the POLLER -- it cannot
// stop a promise that is already resolving.

import { forgeApi, ForgeApiError } from "../forge/api";
import type { JobOp, JobRecord, Progress, RenderHistoryEntry } from "../forge/types";
import { logStore } from "../stores/log.svelte";
import { history } from "./history.svelte";

export type RenderKind = "gen" | "a2a" | "inpaint" | "mix";

export interface ActiveJob {
  forgeJobId: string;
  op: JobOp;
  kind: RenderKind;
  sourceClipId: string | null;
  targetKey: string;
  progress: Progress | null;
}

export interface SubmitRequest {
  op: JobOp;
  payload: unknown;
  kind: RenderKind;
  sourceClipId: string | null;
  targetKey: string;
}

const KIND_LABEL: Record<RenderKind, string> = { gen: "GEN", a2a: "A2A", inpaint: "INPAINT", mix: "MIX" };

function message(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

/** `result.urls[0].split("/").pop()` -- the brief's Result→entry rule, and the shape M2 T15 /
 *  M8 T11 record. A result with no urls is a server bug, not a crash here. */
function fileOf(rec: JobRecord): string {
  const url = rec.result?.urls?.[0];
  return url ? (url.split("/").pop() ?? "") : "";
}

function durationOf(rec: JobRecord): number {
  const meta = (rec.result?.meta ?? {}) as Record<string, unknown>;
  const d = meta.duration_sec;
  return typeof d === "number" && Number.isFinite(d) ? d : 0;
}

export class JobsStore {
  /** At most one -- §7.1: every render control is disabled while a job runs. */
  active = $state<ActiveJob | null>(null);

  /** §9.7's inline error, keyed by the target that asked for the render. Cleared by the next one. */
  lastError = $state<{ targetKey: string; message: string } | null>(null);

  /** `/status.busy` with a job id that is not ours → "GPU busy — <job_id>". */
  gpuBusyOther = $state<string | null>(null);

  #token = 0;
  #abort: AbortController | null = null;
  #statusTimer: ReturnType<typeof setInterval> | null = null;

  get busy(): boolean {
    return this.active !== null || this.gpuBusyOther !== null;
  }

  /** May be 0: `steps_total` is 0 for a commit with no sampling passes, and for decode/bend
   *  (M8 plan_passes, `sum(...)` over an empty list). 0 is a real answer; null means "no progress
   *  yet". Never divide by either without a guard. */
  get stepsLeft(): number | null {
    return this.active?.progress?.steps_left_total ?? null;
  }

  async submit(req: SubmitRequest): Promise<RenderHistoryEntry | null> {
    const token = ++this.#token;
    this.#abort?.abort();
    const ac = new AbortController();
    this.#abort = ac;
    this.lastError = null;

    try {
      const { job_id } = await forgeApi.submitJob(req.op, req.payload);
      if (token !== this.#token) return null;
      this.active = {
        forgeJobId: job_id, op: req.op, kind: req.kind,
        sourceClipId: req.sourceClipId, targetKey: req.targetKey, progress: null,
      };
      const rec = await forgeApi.pollJob(job_id, (p) => {
        // A superseded poller must not keep writing `active` -- that is how the OLD job's step
        // count ends up under the NEW job's control.
        if (token !== this.#token || this.active === null) return;
        this.active.progress = p;
      }, ac.signal);
      if (token !== this.#token) return null;
      this.active = null;
      return history.add({
        job_id: rec.result?.job_id ?? rec.job_id,
        forge_job_id: rec.job_id,
        file: fileOf(rec),
        label: `${KIND_LABEL[req.kind]} ${new Date().toISOString().slice(11, 19)}`,
        kind: req.kind,
        dur_sec: durationOf(rec),
        source_clip_id: req.sourceClipId,
        created: Math.floor(Date.now() / 1000),       // epoch SECONDS, like the server's own fields
      });
    } catch (e) {
      if (token !== this.#token) return null;         // superseded: the new job owns the surfaces
      this.active = null;
      const text = message(e);
      this.lastError = { targetKey: req.targetKey, message: text };
      logStore.append(`[forge] ${req.op} failed: ${text}`, logStore.seq, "error");
      return null;
    } finally {
      if (token === this.#token) this.#abort = null;
    }
  }

  /**
   * Queued only. A RUNNING pass answers 409 `cannot cancel a running pass` (M2 plan:1829) -- that
   * is surfaced as a message, not thrown, and the job stays active because it really is still
   * running. NOTE (Fact 6): M1's mock also 409s a FINISHED job where the real server answers 200.
   * The code is written for the server; the mock's variant is covered in the recorded-contract file.
   */
  async cancel(): Promise<void> {
    const job = this.active;
    if (job === null) return;
    try {
      await forgeApi.cancelJob(job.forgeJobId);
      this.#token += 1;            // the poller's result is no longer wanted
      this.#abort?.abort();
      this.#abort = null;
      this.active = null;
    } catch (e) {
      this.lastError = { targetKey: job.targetKey, message: message(e) };
      if (!(e instanceof ForgeApiError) || e.status !== 409) throw e;
    }
  }

  /**
   * One `/status` read. M1 OQ 16 asked who owns `/status`: BOTH may call it and the answers are
   * independent (`logStore.busy` drives the TERMINAL dot, this drives render-control disabling), so
   * nothing is removed from the log store -- see open question 2. A dead render server is a normal
   * state on this box, so a failure clears the flag rather than surfacing anything.
   */
  async pollStatusOnce(): Promise<void> {
    try {
      const s = await forgeApi.status();
      const mine = this.active?.forgeJobId ?? null;
      this.gpuBusyOther = s.busy && s.job_id !== null && s.job_id !== mine ? s.job_id : null;
    } catch {
      this.gpuBusyOther = null;
    }
  }

  /** Started by App once; 1000 ms, the log store's own cadence, not pollJob's 500. */
  startStatusPolling(intervalMs = 1000): void {
    if (this.#statusTimer !== null) return;
    void this.pollStatusOnce();
    this.#statusTimer = setInterval(() => void this.pollStatusOnce(), intervalMs);
  }

  stopStatusPolling(): void {
    if (this.#statusTimer === null) return;
    clearInterval(this.#statusTimer);
    this.#statusTimer = null;
  }
}

export const jobs = new JobsStore();
```

- [ ] **Step 8: Run it, expect pass**

```bash
cd latent-forge && npx vitest run src/lib/render/__tests__/jobs.test.ts
```

Expected: `Test Files  1 passed (1)` / `Tests  18 passed (18)`.

- [ ] **Step 9: Append the job fixtures to M7 T10's recorded-contract file**

These are **contract** tests: they run against responses recorded from the real server and skip,
with the reason in the title, until `eval/forge/record_fixtures.py` has run (M7 T10's rule — a
hand-made mock never passes them). `handmade-forge_job_running.json` is **deliberately not used**:
it contradicts M1's Normative progress rule (it carries `"SAMPLE"` and `stage_count: 1`, where
only `commit` has stage labels), so `recorded()` returning null for it is the correct outcome, not
a gap.

Append to `latent-forge/src/lib/forge/__tests__/recordedContract.test.ts`, inside the existing
`describe("the client against recorded real-server responses (M2 T15 fixtures)", …)` — reusing its
own `recorded`, `ready`, `title` and `serve` helpers verbatim:

```ts
  const JOB_SUBMIT = recorded("forge_job_submit");
  const JOB_DONE = recorded("forge_job_generate_done");
  const JOB_CAP = recorded("forge_error_cap");
  const STATUS_BUSY = recorded("status_busy");

  it.skipIf(!JOB_SUBMIT)(title("POST /forge/jobs: 202 with {ok, job_id, position}, and forgeApi.submitJob returns the id", "forge_job_submit"), async () => {
    serve(JOB_SUBMIT!);
    expect(JOB_SUBMIT!.status).toBe(202);
    const out = await forgeApi.submitJob("generate", { prompt: "probe", duration: 8 });
    expect(typeof out.job_id).toBe("string");
    expect(out.job_id.length).toBeGreaterThan(0);
    expect(Number.isInteger(out.position)).toBe(true);
  });

  it.skipIf(!JOB_DONE)(title("GET /forge/jobs/{id} done: urls[0]'s basename is the history entry's file, and result.job_id is the output-dir id", "forge_job_generate_done"), async () => {
    serve(JOB_DONE!);
    const rec = await forgeApi.job("probe");
    expect(rec.state).toBe("done");
    expect(rec.result).not.toBeNull();
    expect(rec.result!.urls.length).toBeGreaterThan(0);
    const file = rec.result!.urls[0].split("/").pop()!;
    expect(file).toMatch(/\.wav$/);
    expect(rec.result!.job_id).not.toBe(rec.job_id);   // output-dir id vs forge queue id
    expect(typeof rec.created).toBe("number");
  });

  it.skipIf(!JOB_CAP)(title("a refused over-cap render is a 400 whose message ForgeApiError carries verbatim", "forge_error_cap"), async () => {
    serve(JOB_CAP!);
    expect(JOB_CAP!.status).toBe(400);
    await expect(forgeApi.submitJob("generate", { prompt: "x", duration: 300 }))
      .rejects.toMatchObject({ status: 400, message: expect.stringContaining("184") });
  });

  it.skipIf(!STATUS_BUSY)(title("GET /status busy: job_id is a string, which is what `GPU busy — <job_id>` prints", "status_busy"), async () => {
    serve(STATUS_BUSY!);
    const s = await forgeApi.status();
    expect(s.busy).toBe(true);
    expect(typeof s.job_id).toBe("string");
  });
```

- [ ] **Step 10: Run the whole client suite, expect pass**

```bash
cd latent-forge && npx vitest run && npm run check
```

Expected: the four new contract tests reported **skipped** with their reasons until M2 T15 has
recorded the fixtures; `Tests  47 passed (47)` across this task's two new files
(29 payloads + 18 jobs), and `npm run check` clean.

- [ ] **Step 11: Commit**

```bash
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M9 T1: payload builders (duration_sec stripped from every parse_render object) and JobsStore (one active job, abortable poll, 409s surfaced)"
```

---

### Task 2: The C64 raster border — `phosphor-border.js`, its `.d.ts`, and the progress driver

**WHY.** Spec §9.5 is the one piece of this app whose implementation already exists and is *not*
to be rewritten: *"`phosphor-border.js` is copied verbatim to `src/lib/fx/phosphor-border.js`
(plus a `.d.ts`)"*. M1 already put the canvas on the page — `latent-forge/src/App.svelte`:
`<!-- Spec §9.5: the raster border is a root-level overlay. M9 copies phosphor-border.js in and
drives this canvas from steps_left_total. -->` then `<canvas class="raster-border"
data-region="raster-border" width="300" height="170" aria-hidden="true"></canvas>`, styled
`position: fixed; inset: 0; width: 100vw; height: 100vh; image-rendering: pixelated;
pointer-events: none; z-index: 90;`. Nothing drives it. This task adds the file, the types, and
the one function that turns a step count into a sweep rate.

**Three mismatches between the spec's settled config and the module's actual API.** All three
were checked against `docs/sa3-studio/design_handoff/phosphor-border.js` itself, and each one is
silent rather than loud if got wrong:

1. **`palette` must be an ARRAY, not the name `"teal"`.** The spec's settled config reads
   `palette:"teal"`, but `DEFAULTS` has `palette: PALETTES.teal` and `nextColour()` does
   `const list = cfg.palette; idx = (idx + 1) % list.length; const [r, g, b] = hexToRgb(list[idx]);`
   — a string would index single characters and `hexToRgb("t")` returns three `NaN`s, which
   propagate through the whole ring and paint nothing. Pass `PALETTES.teal`.
2. **`sweepStart` / `sweepEnd` are app-side, not module config.** `DEFAULTS` has `sweepHz: 95`
   and no `sweepStart`/`sweepEnd`; `set()` does a bare `Object.assign(cfg, patch)`, so unknown
   keys are accepted and then ignored forever. The ramp is the app's arithmetic; the module only
   ever hears `sweepHz`.
3. **`alphaOut` defaults to `false`.** The spec wants `true` (*"the canvas is left transparent
   where the phosphor is dark, so an unlit border settles to whatever is behind it instead of to
   black"*) — and with a `position: fixed; inset: 0` overlay at `z-index: 90`, `false` paints the
   whole app black. It must be passed explicitly.

**`steps_total` can be 0** (Fact 5) and this is the one division in the milestone, so the guard is
the point of `sweepHzFor` rather than an inline expression at the call site: a `commit` with no
A2A clip and no overlap reports `steps_total: 0` (M8 `plan_passes`:
`"steps_total": sum(g["render"]["steps"] for g in a2a + inpaint)` over an empty list), and `NaN`
reaches `stepPx = (cfg.sweepHz * N * dt) / S`, then `Math.round(Math.min(remain, …))` — the beam
loop spins its full `guard = 40000` iterations every frame and the border freezes solid.

Two smaller traps, each covered by a test. `destroy()` is written `destroy() { this.stop(); … }`
— it is **`this`-dependent**, so the handle must be kept whole and never destructured. And
`buildRing()` returns `false` when `RW * RH === 0` without allocating `ring`/`img`, after which
`step()` throws on `ring.length`; a detached or zero-sized canvas must therefore never be handed
to `createPhosphorBorder`.

**Files:**
- Create: `latent-forge/src/lib/fx/phosphor-border.js` (**verbatim copy**, not retyped),
  `latent-forge/src/lib/fx/phosphor-border.d.ts`,
  `latent-forge/src/lib/fx/rasterBorder.ts`,
  `latent-forge/src/lib/fx/__tests__/rasterBorder.test.ts`
- Modify: `latent-forge/src/App.svelte` (M1 T9 — bind the existing canvas and drive it)

**Interfaces.**

Consumed from `src/lib/render/jobs.svelte.ts` (Task 1): `jobs.active: ActiveJob | null` where
`ActiveJob` is `{forgeJobId: string; op: JobOp; kind: RenderKind; sourceClipId: string | null;
targetKey: string; progress: Progress | null}`, and `Progress` (M1 T3) is
`{job_id; op; stage; stage_index; stage_count; step; steps; steps_left_total; steps_total}`.

Consumed from the copied module (its own source, quoted above): `PALETTES` — an object whose
values are arrays of `#rrggbb` strings, keys `teal`, `amber`, `accent`, `sparse`, `c64` — and
`createPhosphorBorder(canvas, options) => {start(), stop(), set(patch), resize(w, h), destroy()}`.

Consumed from `src/App.svelte` (M1 T9): the canvas element carrying
`class="raster-border" data-region="raster-border" width="300" height="170" aria-hidden="true"`.
**Keep every one of those attributes** — M1 T15's Playwright layout spec asserts
`[data-region="raster-border"]`.

Produced by this task: `RASTER_CONFIG`, `SWEEP_START`, `SWEEP_END`, `sweepHzFor`,
`createRasterDriver(canvas): {update(progressOrNull), stop()}`.

- [ ] **Step 1: Copy the module verbatim**

Do **not** retype it. One copy, no edits — the verbatim test in Step 3 fails on a single changed
byte, which is the point (the file is a tuned simulation; a "tidied" constant is a different
effect).

```bash
cp docs/sa3-studio/design_handoff/phosphor-border.js latent-forge/src/lib/fx/phosphor-border.js
```

- [ ] **Step 2: Hand-write `latent-forge/src/lib/fx/phosphor-border.d.ts`**

```ts
// Hand-written types for the verbatim-copied phosphor-border.js (spec §9.5: "copied verbatim …
// plus a .d.ts"). The .js is never edited, so the types live beside it. Every field below is
// read from that file's own DEFAULTS object; `sweepStart`/`sweepEnd` are deliberately ABSENT --
// they are the app's ramp endpoints, not module config, and set() would silently swallow them.

/** Each value is a list of `#rrggbb` strings the beam cycles through. */
export declare const PALETTES: {
  teal: string[];
  amber: string[];
  accent: string[];
  sparse: string[];
  c64: string[];
};

export interface PhosphorOptions {
  /** Border ring thickness in backing pixels; clamped to `ceil(height / 2)`. Changing it rebuilds the ring. */
  thickness?: number;
  linesPerColour?: number;
  /** 0..1 randomisation of the write interval. */
  jitter?: number;
  /** Seconds; the red-phosphor time constant, scaled 1.0 / 1.6 / 0.6 for R / G / B. */
  persistence?: number;
  chromaBleed?: number;
  /** Integer sub-steps per animation frame. */
  supersample?: number;
  /** Full raster sweeps per second. THE field the progress driver writes. */
  sweepHz?: number;
  gain?: number;
  spotSpread?: number;
  /** true = transparent where the phosphor is dark. Required for an overlay canvas. */
  alphaOut?: boolean;
  /** An ARRAY of hex strings -- e.g. PALETTES.teal, never the string "teal". */
  palette?: string[];
}

export interface PhosphorBorder {
  start(): void;
  stop(): void;
  /** Merges into the live config. Only `thickness` triggers a ring rebuild. */
  set(patch: PhosphorOptions): void;
  /** Sets canvas.width/height and rebuilds. */
  resize(width: number, height: number): void;
  /** Calls `this.stop()` -- keep the handle whole; a destructured `destroy` throws. */
  destroy(): void;
}

export declare function createPhosphorBorder(
  canvas: HTMLCanvasElement,
  options?: PhosphorOptions,
): PhosphorBorder;
```

- [ ] **Step 3: Write the failing test**

`latent-forge/src/lib/fx/__tests__/rasterBorder.test.ts`:

```ts
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Progress } from "../../forge/types";
import { PALETTES } from "../phosphor-border.js";
import { RASTER_CONFIG, SWEEP_END, SWEEP_START, createRasterDriver, sweepHzFor } from "../rasterBorder";

const HERE = dirname(fileURLToPath(import.meta.url));
const HANDOFF = resolve(HERE, "../../../../../docs/sa3-studio/design_handoff/phosphor-border.js");
const COPY = resolve(HERE, "../phosphor-border.js");

function progress(patch: Partial<Progress> = {}): Progress {
  return {
    job_id: "forge-1", op: "commit", stage: "", stage_index: 0, stage_count: 0,
    step: 0, steps: 0, steps_left_total: 24, steps_total: 24, ...patch,
  };
}

/** A canvas whose getContext is a no-op: jsdom has no 2d context, and this task's unit is the
 *  DRIVER, not the simulation. createPhosphorBorder itself is stubbed per test. */
function canvas(width = 300, height = 170): HTMLCanvasElement {
  const el = document.createElement("canvas");
  el.width = width;
  el.height = height;
  return el;
}

afterEach(() => vi.restoreAllMocks());

describe("the copied module", () => {
  it("is byte-identical to the design handoff (spec §9.5: copied verbatim)", () => {
    expect(readFileSync(COPY, "utf8")).toBe(readFileSync(HANDOFF, "utf8"));
  });

  it("exports PALETTES whose values are ARRAYS of hex strings -- `palette: \"teal\"` would paint NaN", () => {
    expect(Array.isArray(PALETTES.teal)).toBe(true);
    expect(PALETTES.teal.length).toBeGreaterThan(1);
    for (const c of PALETTES.teal) expect(c).toMatch(/^#[0-9a-f]{6}$/);
  });
});

describe("RASTER_CONFIG -- spec §9.5's settled config, corrected for the module's real API", () => {
  it("passes the palette ARRAY, alphaOut true, and every other settled value", () => {
    expect(RASTER_CONFIG).toEqual({
      thickness: 4, linesPerColour: 3, jitter: 0.59, persistence: 0.002, chromaBleed: 1.5,
      supersample: 8, gain: 0.8, spotSpread: 0.16, palette: PALETTES.teal, alphaOut: true,
      sweepHz: SWEEP_START,
    });
  });

  it("carries no sweepStart/sweepEnd -- set() would accept and then ignore them", () => {
    expect("sweepStart" in RASTER_CONFIG).toBe(false);
    expect("sweepEnd" in RASTER_CONFIG).toBe(false);
    expect([SWEEP_START, SWEEP_END]).toEqual([95, 0]);
  });
});

describe("sweepHzFor", () => {
  it("is sweepStart at no progress and sweepEnd at the last step", () => {
    expect(sweepHzFor(progress({ steps_left_total: 24, steps_total: 24 }))).toBe(SWEEP_START);
    expect(sweepHzFor(progress({ steps_left_total: 0, steps_total: 24 }))).toBe(SWEEP_END);
  });

  it("ramps linearly in between -- spec §9.5's sweepStart + (sweepEnd − sweepStart)·(1 − left/total)", () => {
    expect(sweepHzFor(progress({ steps_left_total: 12, steps_total: 24 }))).toBeCloseTo(47.5, 6);
    expect(sweepHzFor(progress({ steps_left_total: 6, steps_total: 24 }))).toBeCloseTo(23.75, 6);
  });

  it("returns sweepStart, never NaN, when steps_total is 0 (Fact 5: commit with no passes, decode, bend)", () => {
    const hz = sweepHzFor(progress({ steps_left_total: 0, steps_total: 0 }));
    expect(Number.isFinite(hz)).toBe(true);
    expect(hz).toBe(SWEEP_START);
  });

  it("returns sweepStart for a job with no progress yet", () => {
    expect(sweepHzFor(null)).toBe(SWEEP_START);
  });

  it("clamps a left count outside 0..total instead of sweeping backwards", () => {
    expect(sweepHzFor(progress({ steps_left_total: 99, steps_total: 24 }))).toBe(SWEEP_START);
    expect(sweepHzFor(progress({ steps_left_total: -3, steps_total: 24 }))).toBe(SWEEP_END);
  });
});

describe("createRasterDriver", () => {
  function stubFx() {
    const fx = { start: vi.fn(), stop: vi.fn(), set: vi.fn(), resize: vi.fn(), destroy: vi.fn() };
    const create = vi.fn(() => fx);
    return { fx, create };
  }

  it("creates and starts the effect on the first active job, and only once", () => {
    const { fx, create } = stubFx();
    const d = createRasterDriver(canvas(), create);
    d.update(progress());
    d.update(progress({ steps_left_total: 20 }));
    expect(create).toHaveBeenCalledTimes(1);
    expect(fx.start).toHaveBeenCalledTimes(1);
    expect(create.mock.calls[0][1]).toMatchObject({ alphaOut: true, palette: PALETTES.teal });
  });

  it("writes sweepHz on every tick and nothing else", () => {
    const { fx, create } = stubFx();
    const d = createRasterDriver(canvas(), create);
    d.update(progress({ steps_left_total: 24, steps_total: 24 }));
    d.update(progress({ steps_left_total: 12, steps_total: 24 }));
    expect(fx.set).toHaveBeenLastCalledWith({ sweepHz: 47.5 });
    for (const call of fx.set.mock.calls) expect(Object.keys(call[0])).toEqual(["sweepHz"]);
  });

  it("stops AND destroys when the job ends, so no rAF loop survives an idle app", () => {
    const { fx, create } = stubFx();
    const d = createRasterDriver(canvas(), create);
    d.update(progress());
    d.update(null);
    expect(fx.destroy).toHaveBeenCalledTimes(1);
    d.update(null);
    expect(fx.destroy).toHaveBeenCalledTimes(1);
  });

  it("calls destroy as a METHOD on the handle -- the module's destroy() uses `this.stop()`", () => {
    let receiver: unknown = null;
    const fx = {
      start: vi.fn(), stop: vi.fn(), set: vi.fn(), resize: vi.fn(),
      destroy(this: unknown) { receiver = this; },
    };
    const d = createRasterDriver(canvas(), vi.fn(() => fx));
    d.update(progress());
    d.update(null);
    expect(receiver).toBe(fx);
  });

  it("starts a fresh effect for the next job after a destroy", () => {
    const { create } = stubFx();
    const d = createRasterDriver(canvas(), create);
    d.update(progress());
    d.update(null);
    d.update(progress());
    expect(create).toHaveBeenCalledTimes(2);
  });

  it("never builds an effect on a zero-sized canvas -- buildRing() bails and step() then throws", () => {
    const { create } = stubFx();
    const d = createRasterDriver(canvas(0, 0), create);
    d.update(progress());
    expect(create).not.toHaveBeenCalled();
  });

  it("stop() tears down whatever is live and is safe to call twice", () => {
    const { fx, create } = stubFx();
    const d = createRasterDriver(canvas(), create);
    d.update(progress());
    d.stop();
    d.stop();
    expect(fx.destroy).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 4: Run it, expect failure**

```bash
cd latent-forge && npx vitest run src/lib/fx/__tests__/rasterBorder.test.ts
```

Expected: `Error: Failed to resolve import "../rasterBorder" from "src/lib/fx/__tests__/rasterBorder.test.ts"`.
(If Step 1's copy was skipped, the first failure is instead
`Failed to resolve import "../phosphor-border.js"` — do Step 1.)

- [ ] **Step 5: Write `latent-forge/src/lib/fx/rasterBorder.ts`**

```ts
// Spec §9.5, the C64 loader border, driven by REAL progress rather than a timer:
//   "sweepHz = sweepStart + (sweepEnd − sweepStart) · (1 − steps_left_total / steps_total),
//    polling /forge/jobs/{id} every 500 ms while running."
// The polling is M1 T5's pollJob (POLL_MS = 500); this file only owns the arithmetic and the
// effect's lifetime.
//
// The spec's settled config is corrected in two places against the module's own DEFAULTS:
// `palette` is an ARRAY (PALETTES.teal), not the name "teal", and `sweepStart`/`sweepEnd` are not
// module config at all -- the module knows only `sweepHz`. See the task's WHY.

import type { Progress } from "../forge/types";
import { PALETTES, createPhosphorBorder, type PhosphorBorder, type PhosphorOptions } from "./phosphor-border.js";

/** Full raster sweeps per second at the first step and at the last (spec §9.5). */
export const SWEEP_START = 95;
export const SWEEP_END = 0;

/** Spec §9.5's settled config. `sweepHz` starts at SWEEP_START; the driver rewrites it per tick. */
export const RASTER_CONFIG: PhosphorOptions = {
  thickness: 4,
  linesPerColour: 3,
  jitter: 0.59,
  persistence: 0.002,
  chromaBleed: 1.5,
  supersample: 8,
  gain: 0.8,
  spotSpread: 0.16,
  palette: PALETTES.teal,
  alphaOut: true,
  sweepHz: SWEEP_START,
};

/**
 * THE guarded division of this milestone. `steps_total` is 0 for a commit with no sampling passes
 * and for `decode`/`bend` (Fact 5), and `null` progress means the job has not reported yet -- both
 * mean "no measurable progress", which is the START of the ramp, not NaN and not the end.
 */
export function sweepHzFor(p: Progress | null | undefined): number {
  const total = p?.steps_total ?? 0;
  if (!p || !Number.isFinite(total) || total <= 0) return SWEEP_START;
  const left = Number.isFinite(p.steps_left_total) ? p.steps_left_total : total;
  const fraction = Math.min(1, Math.max(0, left / total));
  return SWEEP_START + (SWEEP_END - SWEEP_START) * (1 - fraction);
}

type CreateFn = (canvas: HTMLCanvasElement, options?: PhosphorOptions) => PhosphorBorder;

export interface RasterDriver {
  /** Called with the active job's progress, or null when nothing is rendering. */
  update(progress: Progress | null | undefined): void;
  stop(): void;
}

/**
 * Owns the effect's lifetime: built and started on the first tick of a job, `set({sweepHz})` on
 * every tick after, stopped and DESTROYED the moment nothing is running. Destroying rather than
 * only stopping matters because the effect holds an Int32Array/Float32Array pair sized to the
 * canvas plus an ImageData, and a long session would otherwise keep one per render.
 *
 * `create` is a parameter so the driver is testable without a 2d context (jsdom has none).
 */
export function createRasterDriver(canvas: HTMLCanvasElement, create: CreateFn = createPhosphorBorder): RasterDriver {
  let fx: PhosphorBorder | null = null;

  function teardown(): void {
    if (fx === null) return;
    // A METHOD call: the module's destroy() body is `this.stop()`, so a destructured handle throws.
    fx.destroy();
    fx = null;
  }

  return {
    update(progress) {
      if (progress === null || progress === undefined) {
        teardown();
        return;
      }
      if (fx === null) {
        // buildRing() bails out when width*height is 0 and leaves `ring`/`img` unallocated, after
        // which the first step() throws on ring.length. Never hand it an unsized canvas.
        if (canvas.width <= 0 || canvas.height <= 0) return;
        fx = create(canvas, { ...RASTER_CONFIG });
        fx.start();
      }
      fx.set({ sweepHz: sweepHzFor(progress) });
    },
    stop: teardown,
  };
}
```

- [ ] **Step 6: Run it, expect pass**

```bash
cd latent-forge && npx vitest run src/lib/fx/__tests__/rasterBorder.test.ts
```

Expected: `Test Files  1 passed (1)` / `Tests  16 passed (16)`.

- [ ] **Step 7: Drive the canvas from `App.svelte`**

In `latent-forge/src/App.svelte` (M1 T9), add to the existing `<script lang="ts">`:

```ts
  import { createRasterDriver, type RasterDriver } from "./lib/fx/rasterBorder";
  import { jobs } from "./lib/render/jobs.svelte";

  let rasterCanvas = $state<HTMLCanvasElement | null>(null);
  let raster: RasterDriver | null = null;

  // Reads jobs.active and writes nothing reactive -- M7's Global Constraint "no writes inside a
  // $derived" is about $derived; this is an $effect, and the only state it touches is the local
  // non-rune `raster` handle and the canvas.
  $effect(() => {
    const active = jobs.active;
    if (rasterCanvas === null) return;
    raster ??= createRasterDriver(rasterCanvas);
    raster.update(active === null ? null : active.progress ?? { ...EMPTY_PROGRESS });
  });

  $effect(() => () => { raster?.stop(); raster = null; });
```

where `EMPTY_PROGRESS` is declared beside it — a job that has been accepted but has not reported
yet must still light the border, and `sweepHzFor` maps a zero `steps_total` to `SWEEP_START`:

```ts
  const EMPTY_PROGRESS = {
    job_id: "", op: "", stage: "", stage_index: 0, stage_count: 0,
    step: 0, steps: 0, steps_left_total: 0, steps_total: 0,
  } as const;
```

Then bind the existing canvas — **add only `bind:this`; every other attribute stays** (M1 T15's
Playwright spec asserts `[data-region="raster-border"]`):

```svelte
  <canvas
    bind:this={rasterCanvas}
    class="raster-border"
    data-region="raster-border"
    width="300"
    height="170"
    aria-hidden="true"
  ></canvas>
```

- [ ] **Step 8: Run the suite and the type checker**

```bash
cd latent-forge && npx vitest run && npm run check
```

Expected: `Tests  16 passed (16)` for this file, the rest of the suite unchanged, `npm run check`
clean (the `.d.ts` is what makes the `.js` import type-check — if `check` reports
`Could not find a declaration file`, `allowJs`/`checkJs` are off and the `.d.ts` is not being
picked up; put it beside the `.js`, do not add the module to `tsconfig`'s `include`).

- [ ] **Step 9: Commit**

```bash
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M9 T2: phosphor-border.js copied verbatim + hand-written .d.ts, and the progress-driven raster border (sweepHz guarded against steps_total 0)"
```

---

### Task 3: `src/lib/render/history.svelte.ts`, and teaching M7's serialiser about it

**WHY.** `ProjectV2` has carried `renders`, `mixdown` and `preview` since M1 T3 declared it, and
nothing has ever written them. M7's `serializeProject` hardcodes all three —
`docs/superpowers/plans/2026-09-23-latent-forge-m7-chains-mix-sessions.md:5933-5935`:
`renders: [],       // M9 owns render history; nothing exists to serialise yet` / `mixdown: null,` /
`preview: null,` — `validateProjectV2` checks neither, and `applyProject` restores neither. This
task fills all three holes at once, because a store that is saved but not restored is worse than
one that is neither.

The store is the single home for "what has this session rendered". Three consumers read it and one
writes it: Task 1's `jobs.submit` calls `add`; Task 4's MIXDOWN slot reads `mixdown`; Writer B's
preview container reads `preview`, `renders` and `jobRecord`. Because they run in parallel, the
shape is the brief's pre-declared one, verbatim, and nothing here widens it.

**`add` must return `renders[renders.length - 1]`.** `HANDOUT.md`: *"Pushing an object into a
`$state` array deep-proxies it; the local reference you built is a dead handle and mutating it does
nothing. Any store method that appends must return `arr[arr.length - 1]`, never the object it
constructed. This silently ate a clip trim once — the duration simply stayed 47."* Task 1's
`submit` returns whatever `add` returns and hands it to a caller that may scrub or drag it, so a
dead handle here is a drag that produces the wrong clip.

**`select` loads audio only.** Spec §4.5: *"**Loading from HISTORY loads audio only.** The previewed
render changes; the pane's settings do not"*, and §10 X15: *"HISTORY loads audio only; settings come
from a SETTINGS PRESET or an explicit USE SETTINGS"*. So `select` touches exactly one field —
`preview` — and there is a test asserting `settings.defaults` is untouched, because this is the
kind of convenience a later hand adds without noticing it contradicts a decision.

**`mixdown` is always the newest commit, not the newest render.** The brief pre-declares it as
*"index into renders — always the newest commit"*, which matches §7.1's *"top-bar `▸ MIXDOWN` …
Result goes to: MIXDOWN slot (always the latest) + history"*. A `gen` landing after a `mix` must
not steal the slot.

**The `workKey` decision, stated (Fact 11).** M7's `workKey` is
`JSON.stringify({ ...p, name: "", view: null, ui: null, backbone: "", ckpt_path: null })`
(m7 plan:6262-6264) — it includes `renders`, and its docstring says it is *"everything saved except
the name, the viewport, the ui slice and the model — scrolling, opening a module or a STAGE revert
is not work anyone would lose."* While M7 hardcoded `renders: []` that was moot. Once this task
writes them, **every finished render would mark the session as unsaved work**, so the "replace
unsaved work?" prompt would fire on a LOAD immediately after any render — including the render the
user is about to drag onto a lane. **Decision: `renders`/`mixdown`/`preview` are excluded from
`workKey`.** They are output, not edits: a render is a file the server already wrote, reachable
through `/forge/jobs/{id}` and the FILES `renders` root whether or not the entry survives. They are
still *serialised* and *restored*, so a saved-and-reloaded session keeps its history; only the
"is this worth protecting?" question ignores them. Recorded as open question 5.

**Files:**
- Create: `latent-forge/src/lib/render/history.svelte.ts`,
  `latent-forge/src/lib/render/__tests__/history.test.ts`
- Modify: `latent-forge/src/lib/forge/projectSerializer.svelte.ts` (M7 T9 — `serializeProject`,
  `validateProjectV2`, `applyProject`, `workKey`),
  `latent-forge/src/lib/forge/__tests__/projectSerializer.test.ts` (M7 T9)

**Interfaces.**

Consumed from `src/lib/forge/types.ts` (M1 T3, verified):
- `interface RenderHistoryEntry { job_id: string; forge_job_id: string; file: string; label: string;
  kind: "gen" | "a2a" | "inpaint" | "mix"; dur_sec: number; source_clip_id: string | null;
  created: number }` — `created` in epoch **seconds**.
- `type AudioRef = … | { kind: "render"; job_id: string; file: string } | …`
- `interface JobRecord { ok: true; job_id; op; payload: unknown; state; position; progress;
  result: JobResponse | null; error; created; started; finished }` — `USE SETTINGS` (Writer B,
  Task 8) reads `.payload`.
- `interface ProjectV2 { … renders: RenderHistoryEntry[]; mixdown: number | null;
  preview: number | null; ui: {…} }`

Consumed from `src/lib/forge/api.ts` (M1 T5, verified):
`job: (jobId: string) => Promise<JobRecord>` — `getJSON<JobRecord>(\`/forge/jobs/${encodeURIComponent(jobId)}\`)`.

Consumed from `src/lib/forge/projectSerializer.svelte.ts` (M7 T9, verified — quoted in the steps
below): `serializeProject(opts: {name: string; backbone?: string}): ProjectV2`,
`validateProjectV2(raw: unknown): ProjectV2` (its local `bad(field)` helper throws
`` new Error(`not a v2 project: ${field} is missing or the wrong type`) ``, and its local guards are
`isObj`, `isNum`, `isBool`, `isStrOrNull`, `isLaneIndex`), `applyProject(project: ProjectV2,
opts?: {restoreModel?: boolean}): void`, and the module-private `workKey(p: ProjectV2): string`
used by `SessionController`.

Produced by this task, for Task 1, Task 4 and Writer B: `class HistoryStore`, `const history`,
exactly as the brief pre-declares:

```ts
export class HistoryStore {
  renders = $state<RenderHistoryEntry[]>([]);        // newest LAST in storage; UI shows newest first
  mixdown = $state<number | null>(null);             // index into renders — always the newest commit
  preview = $state<number | null>(null);             // index into renders — what the preview container shows
  add(e: RenderHistoryEntry): RenderHistoryEntry;    // returns renders[renders.length - 1] ($state proxy rule)
  select(index: number): void;                       // loads audio only (§4.5, X15) — never touches settings
  refOf(e: RenderHistoryEntry): AudioRef;            // {kind:"render", job_id: e.job_id, file: e.file}
  jobRecord(e: RenderHistoryEntry): Promise<JobRecord>;   // forgeApi.job(e.forge_job_id)
  clear(): void; restore(renders: RenderHistoryEntry[], mixdown: number | null, preview: number | null): void;
}
export const history: HistoryStore;
```

- [ ] **Step 1: Write the failing store test**

`latent-forge/src/lib/render/__tests__/history.test.ts`:

```ts
import { beforeEach, describe, expect, it, vi } from "vitest";
import { forgeApi } from "../../forge/api";
import type { RenderHistoryEntry } from "../../forge/types";
import { settings } from "../../stores/settings.svelte";
import { history } from "../history.svelte";

function entry(patch: Partial<RenderHistoryEntry> = {}): RenderHistoryEntry {
  return {
    job_id: "gen-20260926-1", forge_job_id: "forge-1", file: "out_00.wav", label: "GEN 12:00:00",
    kind: "gen", dur_sec: 45, source_clip_id: null, created: 1_759_000_000, ...patch,
  };
}

beforeEach(() => history.clear());

describe("add", () => {
  it("returns the array's LIVE element, not the object it was handed ($state proxy rule)", () => {
    const built = entry();
    const live = history.add(built);
    expect(live).toBe(history.renders[history.renders.length - 1]);
    live.label = "renamed";
    expect(history.renders[0].label).toBe("renamed");
  });

  it("stores newest LAST", () => {
    history.add(entry({ forge_job_id: "forge-1" }));
    history.add(entry({ forge_job_id: "forge-2" }));
    expect(history.renders.map((r) => r.forge_job_id)).toEqual(["forge-1", "forge-2"]);
  });

  it("makes the new render the previewed one -- §4.5 'a finished render lands here'", () => {
    history.add(entry());
    expect(history.preview).toBe(0);
    history.add(entry({ forge_job_id: "forge-2" }));
    expect(history.preview).toBe(1);
  });

  it("moves mixdown only for a commit, and always to the newest one (§7.1 'always the latest')", () => {
    history.add(entry({ kind: "gen" }));
    expect(history.mixdown).toBeNull();
    history.add(entry({ kind: "mix", forge_job_id: "forge-m1" }));
    expect(history.mixdown).toBe(1);
    history.add(entry({ kind: "a2a", forge_job_id: "forge-3" }));
    expect(history.mixdown).toBe(1);
    history.add(entry({ kind: "mix", forge_job_id: "forge-m2" }));
    expect(history.mixdown).toBe(3);
  });
});

describe("select -- audio only (§4.5, §10 X15)", () => {
  it("moves preview and touches nothing else", () => {
    history.add(entry({ forge_job_id: "forge-1" }));
    history.add(entry({ forge_job_id: "forge-2" }));
    const before = JSON.stringify(settings.defaults);
    history.select(0);
    expect(history.preview).toBe(0);
    expect(JSON.stringify(settings.defaults)).toBe(before);
    expect(history.mixdown).toBeNull();
  });

  it("ignores an index that is not a real row", () => {
    history.add(entry());
    history.select(7);
    history.select(-1);
    history.select(0.5);
    expect(history.preview).toBe(0);
  });
});

describe("refOf and jobRecord", () => {
  it("builds the render AudioRef from the RESULT job id and the file, not the forge queue id", () => {
    const e = entry({ job_id: "gen-20260926-1", forge_job_id: "forge-1", file: "out_00.wav" });
    expect(history.refOf(e)).toEqual({ kind: "render", job_id: "gen-20260926-1", file: "out_00.wav" });
  });

  it("reads the job record by the FORGE id, because that is what /forge/jobs/{id} keys on", async () => {
    const spy = vi.spyOn(forgeApi, "job").mockResolvedValue({ payload: { prompt: "dub" } } as never);
    const rec = await history.jobRecord(entry({ forge_job_id: "forge-9" }));
    expect(spy).toHaveBeenCalledWith("forge-9");
    expect((rec as { payload: { prompt: string } }).payload.prompt).toBe("dub");
    spy.mockRestore();
  });
});

describe("clear and restore", () => {
  it("clear empties all three fields", () => {
    history.add(entry({ kind: "mix" }));
    history.clear();
    expect(history.renders).toEqual([]);
    expect(history.mixdown).toBeNull();
    expect(history.preview).toBeNull();
  });

  it("restore replaces the list wholesale and keeps valid indexes", () => {
    history.add(entry({ forge_job_id: "stale" }));
    history.restore([entry({ forge_job_id: "a" }), entry({ forge_job_id: "b", kind: "mix" })], 1, 0);
    expect(history.renders.map((r) => r.forge_job_id)).toEqual(["a", "b"]);
    expect(history.mixdown).toBe(1);
    expect(history.preview).toBe(0);
  });

  it("restore drops an index that does not address a row, rather than pointing the slot at nothing", () => {
    history.restore([entry()], 4, -1);
    expect(history.mixdown).toBeNull();
    expect(history.preview).toBeNull();
  });
});
```

- [ ] **Step 2: Run it, expect failure**

```bash
cd latent-forge && npx vitest run src/lib/render/__tests__/history.test.ts
```

Expected: `Error: Failed to resolve import "../history.svelte" from "src/lib/render/__tests__/history.test.ts"`.

- [ ] **Step 3: Write `latent-forge/src/lib/render/history.svelte.ts`**

```ts
// Every render of the session, in the order they finished (spec §4.5: the HISTORY select shows
// them newest FIRST, but storage keeps newest LAST so an index stays valid as more arrive -- a
// newest-first array would renumber every entry on every render, and `mixdown`/`preview` are
// indexes that ProjectV2 persists).
//
// This store holds NO audio and no settings. It holds refs. §4.5: "Loading from HISTORY loads
// audio only. The previewed render changes; the pane's settings do not" (and §10 X15). Settings
// come back only through USE SETTINGS, which reads the job record's `payload` -- hence jobRecord().

import { forgeApi } from "../forge/api";
import type { AudioRef, JobRecord, RenderHistoryEntry } from "../forge/types";

function isIndexInto<T>(list: T[], i: number | null): boolean {
  return i !== null && Number.isInteger(i) && i >= 0 && i < list.length;
}

export class HistoryStore {
  /** Newest LAST. The UI reverses for display; the indexes below address THIS order. */
  renders = $state<RenderHistoryEntry[]>([]);

  /** Index into `renders` -- always the newest `kind: "mix"` (§7.1: "always the latest"). */
  mixdown = $state<number | null>(null);

  /** Index into `renders` -- what the preview container is showing. */
  preview = $state<number | null>(null);

  /**
   * Svelte 5 proxy rule (HANDOUT): pushing into a `$state` array deep-proxies the object, so the
   * literal the caller built is a dead handle. Return the array's live element -- Task 1's
   * `jobs.submit` hands this straight on to a caller that scrubs and drags it.
   */
  add(e: RenderHistoryEntry): RenderHistoryEntry {
    this.renders.push(e);
    const index = this.renders.length - 1;
    this.preview = index;                       // §4.5: "A finished render lands here"
    if (e.kind === "mix") this.mixdown = index;  // a later gen/a2a must not steal the slot
    return this.renders[index];
  }

  /** Audio only. This method sets exactly one field on purpose (§4.5, §10 X15). */
  select(index: number): void {
    if (!isIndexInto(this.renders, index)) return;
    this.preview = index;
  }

  /** `job_id` here is the RESULT's output-dir id (`result.job_id`), which is what /forge/audio and
   *  /audio/{job_id}/{file} resolve -- not the `forge-…` queue id. */
  refOf(e: RenderHistoryEntry): AudioRef {
    return { kind: "render", job_id: e.job_id, file: e.file };
  }

  /** The queue id is what GET /forge/jobs/{id} keys on; `payload` is what USE SETTINGS reads
   *  (spec §7.2: "Every job record keeps the exact payload it ran with"). */
  jobRecord(e: RenderHistoryEntry): Promise<JobRecord> {
    return forgeApi.job(e.forge_job_id);
  }

  clear(): void {
    this.renders = [];
    this.mixdown = null;
    this.preview = null;
  }

  /** Called by applyProject. An index a saved project cannot address becomes null rather than
   *  pointing the MIXDOWN slot or the preview container at nothing. */
  restore(renders: RenderHistoryEntry[], mixdown: number | null, preview: number | null): void {
    this.renders = structuredClone(renders);
    this.mixdown = isIndexInto(this.renders, mixdown) ? mixdown : null;
    this.preview = isIndexInto(this.renders, preview) ? preview : null;
  }
}

export const history = new HistoryStore();
```

- [ ] **Step 4: Run it, expect pass**

```bash
cd latent-forge && npx vitest run src/lib/render/__tests__/history.test.ts
```

Expected: `Test Files  1 passed (1)` / `Tests  11 passed (11)`.

- [ ] **Step 5: Write the failing serialiser tests**

Append to `latent-forge/src/lib/forge/__tests__/projectSerializer.test.ts` (M7 T9), adding
`import { history } from "../../render/history.svelte";` to its imports and this describe block.
`makeEntry` is local to the block so nothing in M7's existing cases changes.

```ts
describe("render history round-trips through ProjectV2 (M9 T3)", () => {
  function makeEntry(patch: Partial<RenderHistoryEntry> = {}): RenderHistoryEntry {
    return {
      job_id: "gen-1", forge_job_id: "forge-1", file: "out_00.wav", label: "GEN 12:00:00",
      kind: "gen", dur_sec: 45, source_clip_id: null, created: 1_759_000_000, ...patch,
    };
  }

  it("serializeProject writes the live history instead of the hardcoded empty triple", () => {
    history.clear();
    history.add(makeEntry());
    history.add(makeEntry({ forge_job_id: "forge-2", kind: "mix", job_id: "mix-1" }));
    const p = serializeProject({ name: "s" });
    expect(p.renders).toHaveLength(2);
    expect(p.renders[1].kind).toBe("mix");
    expect(p.mixdown).toBe(1);
    expect(p.preview).toBe(1);
  });

  it("serializeProject writes a SNAPSHOT -- a later render does not mutate an already-saved project", () => {
    history.clear();
    history.add(makeEntry());
    const p = serializeProject({ name: "s" });
    history.add(makeEntry({ forge_job_id: "forge-2" }));
    expect(p.renders).toHaveLength(1);
  });

  it("validateProjectV2 refuses a bad renders array and a mixdown that is not an index or null", () => {
    const base = serializeProject({ name: "s" });
    expect(() => validateProjectV2({ ...base, renders: "nope" })).toThrow(/renders/);
    expect(() => validateProjectV2({ ...base, renders: [{ job_id: "x" }] })).toThrow(/renders\[0\]/);
    expect(() => validateProjectV2({ ...base, mixdown: "1" })).toThrow(/mixdown/);
    expect(() => validateProjectV2({ ...base, preview: 1.5 })).toThrow(/preview/);
    expect(() => validateProjectV2({ ...base, mixdown: null, preview: null })).not.toThrow();
  });

  it("applyProject restores all three fields", () => {
    history.clear();
    const project = {
      ...serializeProject({ name: "s" }),
      renders: [makeEntry(), makeEntry({ forge_job_id: "forge-2", kind: "mix" })],
      mixdown: 1,
      preview: 0,
    };
    applyProject(validateProjectV2(project));
    expect(history.renders.map((r) => r.forge_job_id)).toEqual(["forge-1", "forge-2"]);
    expect(history.mixdown).toBe(1);
    expect(history.preview).toBe(0);
  });

  it("applyProject clears a previous session's history when the loaded project has none", () => {
    history.clear();
    history.add(makeEntry({ forge_job_id: "stale", kind: "mix" }));
    applyProject(validateProjectV2({ ...serializeProject({ name: "s" }), renders: [], mixdown: null, preview: null }));
    expect(history.renders).toEqual([]);
    expect(history.mixdown).toBeNull();
    expect(history.preview).toBeNull();
  });

  it("a finished render is NOT unsaved work -- workKey ignores renders/mixdown/preview", () => {
    history.clear();
    const before = unsavedWorkKey(serializeProject({ name: "" }));
    history.add(makeEntry({ kind: "mix" }));
    expect(unsavedWorkKey(serializeProject({ name: "" }))).toBe(before);
    arrangement.setBpm(arrangement.bpm + 1);
    expect(unsavedWorkKey(serializeProject({ name: "" }))).not.toBe(before);
  });
});
```

- [ ] **Step 6: Run it, expect failure**

```bash
cd latent-forge && npx vitest run src/lib/forge/__tests__/projectSerializer.test.ts
```

Expected: `Failed to resolve import "../../render/history.svelte"` if Step 3 was skipped;
otherwise `unsavedWorkKey is not exported by "../projectSerializer.svelte"`, then — once that is
exported — the six cases fail on `p.renders` being `[]`, `validateProjectV2` accepting
`renders: "nope"`, and `applyProject` leaving the store untouched.

- [ ] **Step 7: Change `latent-forge/src/lib/forge/projectSerializer.svelte.ts`**

(a) Add to the imports:

```ts
import { history } from "../render/history.svelte";
import type { RenderHistoryEntry } from "./types";
```

(b) Replace the three hardcoded lines in `serializeProject` (currently
`renders: [],       // M9 owns render history; nothing exists to serialise yet` / `mixdown: null,` /
`preview: null,`) with:

```ts
    // M9 T3 owns these. $state.snapshot, like every other store read here (Global Constraint #7:
    // `$state.snapshot` only in a .svelte.ts file -- which is why this module is one).
    renders: $state.snapshot(history.renders) as RenderHistoryEntry[],
    mixdown: history.mixdown,
    preview: history.preview,
```

(c) Add a shape guard beside the existing `isLaneChain` / `isClip` / `isOverlapParams` ones:

```ts
const RENDER_KINDS = ["gen", "a2a", "inpaint", "mix"];

/** Every field the preview container, the MIXDOWN slot and refOf dereference. */
function isRenderEntry(v: unknown): boolean {
  return isObj(v) && typeof v.job_id === "string" && typeof v.forge_job_id === "string"
    && typeof v.file === "string" && typeof v.label === "string"
    && RENDER_KINDS.includes(v.kind as string) && isNum(v.dur_sec)
    && isStrOrNull(v.source_clip_id) && isNum(v.created);
}

/** null, or an integer that addresses a row of `renders`. A float or an out-of-range index would
 *  leave the MIXDOWN slot pointing at nothing. */
function isRenderIndex(v: unknown, renders: unknown[]): boolean {
  return v === null || (typeof v === "number" && Number.isInteger(v) && v >= 0 && v < renders.length);
}
```

(d) In `validateProjectV2`, add before `if (!isObj(p.ui) …)`:

```ts
  if (!Array.isArray(p.renders)) throw bad("renders");
  p.renders.forEach((r: unknown, i: number) => {
    if (!isRenderEntry(r)) throw bad(`renders[${i}]`);
  });
  if (!isRenderIndex(p.mixdown, p.renders)) throw bad("mixdown");
  if (!isRenderIndex(p.preview, p.renders)) throw bad("preview");
```

(e) In `applyProject`, add beside the other store writes — before `view.restoreUi(project.ui);`:

```ts
  // Wholesale, like overlaps: a previous session's renders must not survive into this one, and
  // `restore` drops an index the loaded list cannot address.
  history.restore(project.renders, project.mixdown, project.preview);
```

(f) Change `workKey` and export it under a name the test can reach. It is module-private today and
`SessionController` is its only caller, so renaming the export costs nothing:

```ts
/**
 * What counts as work for step 3's "replace unsaved work?" (critic pass 3 #3): everything saved
 * except the name, the viewport, the ui slice and the model -- scrolling, opening a module or a
 * STAGE revert is not work anyone would lose.
 *
 * M9 T3 adds `renders`/`mixdown`/`preview` to that list. They are OUTPUT, not edits: the audio a
 * history entry points at is a file the server already wrote, reachable through /forge/jobs/{id}
 * and the FILES `renders` root whether or not the entry survives. Counting them would make the
 * prompt fire after every single render -- including the render the user is about to drag onto a
 * lane. They are still serialised and restored; only this question ignores them. (M9 open question 5.)
 */
export function unsavedWorkKey(p: ProjectV2): string {
  return JSON.stringify({
    ...p, name: "", view: null, ui: null, backbone: "", ckpt_path: null,
    renders: null, mixdown: null, preview: null,
  });
}
```

and replace the four `workKey(` call sites in `SessionController` (m7 plan:6301, 6408, 6424, 6434)
with `unsavedWorkKey(`.

- [ ] **Step 8: Run the serialiser and session suites, expect pass**

```bash
cd latent-forge && npx vitest run src/lib/forge/__tests__/projectSerializer.test.ts src/lib/forge/__tests__/sessionController.test.ts
```

Expected: `Tests  15 passed (15)` for `projectSerializer.test.ts` (M7 left it at 9; this task adds
6) and `sessionController.test.ts` unchanged and green.

- [ ] **Step 9: Run everything and the type checker**

```bash
cd latent-forge && npx vitest run && npm run check
```

Expected: the whole suite green, `npm run check` clean.

- [ ] **Step 10: Commit**

```bash
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M9 T3: HistoryStore (add returns the live element, select loads audio only) and renders/mixdown/preview through serialize/validate/applyProject; history excluded from the unsaved-work key"
```

---

### Task 4: MIXDOWN — both buttons, the latest-mix slot, and `meta.stages` into the SIGNAL PATH

**WHY.** Two controls run the same job. Spec §7.1's table: `top-bar ▸ MIXDOWN | any | commit of the
whole arrangement | MIXDOWN slot (always the latest) + history` and `MIX tab ▸ MIXDOWN | any | same
as the row above | same`. Both frames exist and neither does anything — M1's `MixdownSlot.svelte` is
`FRAME ONLY. Everything here is disabled in M1`, and M7's `MixSignalPath.svelte` has
`function onMixdown() { // M9 wires the real `commit` job submission (spec §6.9, §7.1). No-op here
on purpose. }`. One action module serves both, so the two buttons cannot drift.

`mixdownLabel` is already written and tested (M1 T10): `export function mixdownLabel(busy: boolean,
stepsLeft: number | null): string { if (!busy) return MIXDOWN_IDLE_LABEL; return \`SAMPLING ·
${stepsLeft ?? 0} steps left\`; }`, with `MIXDOWN_IDLE_LABEL = "▸ MIXDOWN"`. M1's own comment says
why: *"M1 only ever calls this with busy = false; the copy is fixed and tested here so M9 wires
progress to it without re-deciding it."* Do not re-decide it. The `?? 0` matters — `stepsLeft` is
`null` between submit and the first progress tick, and reads `SAMPLING · 0 steps left`, which is
correct for a commit whose `steps_total` is 0 anyway (Fact 5).

**The M7 OQ 12 decision, stated: reconcile, not replace.** M7's own open question 7 (that plan,
line 3181): *"Whether M9 should replace this estimate wholesale with the real `meta.stages` once a
commit has run, or reconcile the two (estimate before a commit, ground truth after), is not decided
here — flagging for whoever plans M9."* **Decided: the estimate is always computed, and a finished
commit's `meta.stages` overrides it only while it still describes the arrangement on screen.**
Replacing wholesale would leave nine rows asserting that `INPAINT OVERLAPS` ran, lit, for an
overlap the user deleted thirty seconds after the commit — a confidently wrong readout is worse
than an honest estimate, and `signalPath.ts`'s own header already calls itself *"a CLIENT-SIDE
PREVIEW, not the ground truth."* The reconciliation key is the `SignalPathInput` itself, because
the estimate is a pure function of exactly that: if the input changes, the commit's stages no
longer describe it and are dropped.

**MIXDOWN must be disabled with an honest hint on an empty arrangement** (Fact 2). M8's
`validate_commit` raises `ForgeError(400, "nothing to commit — the arrangement has no clips")`
(m8 plan:1452-1453) — that is a round trip and a red log line for something the client can see, so
`mixdownBlock()` catches it first and the button carries the same sentence as its `title`.

**Fact 9, HELP.** M1 wrote the MIXDOWN copy as literal `data-help` strings on the frame. This task
promotes both to `NEW_STRINGS` ids and switches M7's two MIX-tab buttons off `HELP.renderButton`
(*"Runs the current target"* — wrong for a commit) onto the same id, so **both MIXDOWN surfaces say
the same thing**.

**Files:**
- Create: `latent-forge/src/lib/render/mixdown.svelte.ts`,
  `latent-forge/src/lib/render/__tests__/mixdown.test.ts`,
  `latent-forge/src/ui/topbar/__tests__/mixdownSlotWired.test.ts`
- Modify: `latent-forge/src/lib/mix/signalPath.ts` (M7 T3 — append two pure functions),
  `latent-forge/src/lib/mix/__tests__/signalPath.test.ts` (M7 T3)
- Modify: `latent-forge/src/ui/topbar/MixdownSlot.svelte` (M1 T10),
  `latent-forge/src/ui/shell/TopBar.svelte` + `latent-forge/src/App.svelte` (M1 T9/T10 — pass
  `busy`/`stepsLeft`, which exist as props but are never passed),
  `latent-forge/src/ui/mix/MixSignalPath.svelte` (M7 T5),
  `latent-forge/src/ui/mix/__tests__/MixSignalPath.component.test.ts` (M7 T5)
- Modify: `docs/latent-forge/extract_help.mjs` (two `NEW_STRINGS` entries), the regenerated
  `latent-forge/src/lib/help/strings.ts`, and
  `latent-forge/src/lib/help/__tests__/strings.test.ts` (M7 left the total at **112**; this task
  takes it to **114**)

**Interfaces.**

Consumed from `src/lib/render/jobs.svelte.ts` (Task 1): `jobs.submit(req: {op: JobOp;
payload: unknown; kind: RenderKind; sourceClipId: string | null; targetKey: string}):
Promise<RenderHistoryEntry | null>`, `jobs.busy: boolean`, `jobs.stepsLeft: number | null`,
`jobs.active: ActiveJob | null`, `jobs.lastError: {targetKey: string; message: string} | null`.

Consumed from `src/lib/render/payloads.ts` (Task 1): `commitPayload(a: CommitArgs):
Record<string, unknown>` and `PayloadError`, where `CommitArgs` is `{bpm; durationSec;
defaults: RenderSettings; lanes: ForgeLane[]; clips: ForgeClip[]; overlaps: DerivedOverlap[];
overlapParamsOf: (key: string) => OverlapParams; mix: MixSpec; master: MasterChain;
decodeLanes: boolean; heads: Record<string, LatchHeadInfo>; cfgOf?: (s: RenderSettings) => number}`.

Consumed from `src/lib/render/history.svelte.ts` (Task 3): `history.renders:
RenderHistoryEntry[]`, `history.mixdown: number | null`, `history.refOf(e): AudioRef`.

Consumed from `src/lib/mix/signalPath.ts` (M7 T3, verified): `buildSignalPath(input:
SignalPathInput): SignalPathStage[]`, `interface SignalPathStage { n: number; label: string;
lit: boolean; note: string }`, `interface SignalPathInput { lanes: Array<{index: 0|1|2|3;
chain: LaneChain}>; clips: SignalPathClip[]; overlapCount: number; mix: MixSpec;
master: MasterChain }`, `interface SignalPathClip { lane; isCropAudio; needsStretch; a2aOn }`.

Consumed from `src/lib/chains/latch.ts` (M7 T1): `fetchLatchHeads(): Promise<Record<string,
LatchHeadInfo>>`.

Consumed from `src/lib/stores/arrangement.svelte.ts` (M5 T1 + M7 T3): `arrangement.bpm`,
`.lanes`, `.clips`, `.overlaps` (derived `Overlap[]`), `.peekOverlapParams(key)`,
`.arrangementEndSec`, `.mix`, `.master`.

Consumed from `src/lib/stores/settings.svelte.ts` (M4): `settings.defaults: RenderSettings`,
`settings.effectiveCfg(t: Target): number`.

Consumed from `src/lib/audio/waveform.ts` (M1 T15, re-homed unchanged, used by M5 T? exactly this
way): `peaksFor(url: string, buffer: AudioBuffer | null, columns: number, fromSec: number,
toSec: number): Promise<Peaks>` and `drawPeaks(...)`; `interface Peaks { columns: number;
data: Float32Array }` (pairs of lo/hi per column).

Consumed from `src/lib/stores/transport.svelte.ts` (M5 T3): `playback.preload(url)`,
`playback.seek(sec)`. Preview playback is independent of the timeline transport and **starting one
stops the other** (§4.5) — Writer B owns that rule for the preview container; this task applies the
same rule to the MIXDOWN slot's `▶`.

Consumed from `src/lib/forge/api.ts` (M1 T5): `forgeApi.audioUrl(ref: AudioRef): string`.

Consumed from `src/lib/math/laneHeader.ts` (M5 T4): the drag MIME is `application/x-forge-ref` and
its payload is a bare `JSON.stringify(AudioRef)` — `parseForgeRefPayload(raw)` does
`JSON.parse(raw)` then `isAudioRef(parsed) ? parsed : null`.

Produced: `MIXDOWN_TARGET_KEY`, `mixdownBlock()`, `runMixdown()`, `mixdown` (the store holding the
last commit's stages), `signalKeyOf`, `mergeSignalPath`, `HELP.mixdownButton`, `HELP.mixdownWave`.

- [ ] **Step 1: Write the failing tests for the action module and the merge**

`latent-forge/src/lib/render/__tests__/mixdown.test.ts`:

```ts
import { beforeEach, describe, expect, it, vi } from "vitest";
import { arrangement } from "../../stores/arrangement.svelte";
import { jobs } from "../jobs.svelte";
import { history } from "../history.svelte";
import { MIXDOWN_TARGET_KEY, mixdown, mixdownBlock, runMixdown } from "../mixdown.svelte";

const REF = { kind: "upload", sha256: "a".repeat(64) } as const;

function addClip() {
  return arrangement.addClip({ lane: 0, startSec: 0, durSec: 8, audio: REF, nativeBpm: 120 });
}

beforeEach(() => {
  arrangement.clips.splice(0, arrangement.clips.length);
  jobs.active = null;
  jobs.lastError = null;
  jobs.gpuBusyOther = null;
  history.clear();
  mixdown.reset();
  vi.restoreAllMocks();
});

describe("mixdownBlock -- why MIXDOWN is disabled, in the button's own words", () => {
  it("names the empty arrangement, using validate_commit's own sentence", () => {
    expect(mixdownBlock()).toBe("nothing to commit — the arrangement has no clips");
  });

  it("is null once there is something to commit", () => {
    addClip();
    expect(mixdownBlock()).toBeNull();
  });

  it("names the running job -- §7.1 disables every render control while one runs", () => {
    addClip();
    jobs.active = { forgeJobId: "forge-1", op: "generate", kind: "gen", sourceClipId: null, targetKey: "session", progress: null };
    expect(mixdownBlock()).toMatch(/running/i);
    jobs.active = null;
    jobs.gpuBusyOther = "dash-77";
    expect(mixdownBlock()).toBe("GPU busy — dash-77");
  });
});

describe("runMixdown", () => {
  it("submits op `commit`, kind `mix`, on the MIXDOWN target key", async () => {
    addClip();
    const submit = vi.spyOn(jobs, "submit").mockResolvedValue(null);
    vi.spyOn(mixdown, "heads").mockResolvedValue({});
    await runMixdown();
    expect(submit).toHaveBeenCalledTimes(1);
    const req = submit.mock.calls[0][0];
    expect(req.op).toBe("commit");
    expect(req.kind).toBe("mix");
    expect(req.sourceClipId).toBeNull();
    expect(req.targetKey).toBe(MIXDOWN_TARGET_KEY);
    expect(Object.keys(req.payload as object)).toContain("duration_sec");
  });

  it("does not submit when blocked, and shows the reason as the inline error instead", async () => {
    const submit = vi.spyOn(jobs, "submit").mockResolvedValue(null);
    await runMixdown();
    expect(submit).not.toHaveBeenCalled();
    expect(jobs.lastError).toEqual({ targetKey: MIXDOWN_TARGET_KEY, message: "nothing to commit — the arrangement has no clips" });
  });

  it("turns a client-side payload refusal into the same inline error, never a throw", async () => {
    addClip();
    arrangement.clips[0].detune_cents = 900;         // outside ±100: validate_commit would 400
    vi.spyOn(mixdown, "heads").mockResolvedValue({});
    const submit = vi.spyOn(jobs, "submit").mockResolvedValue(null);
    await expect(runMixdown()).resolves.toBeUndefined();
    expect(submit).not.toHaveBeenCalled();
    expect(jobs.lastError?.message).toMatch(/detune/);
  });

  it("stores a finished commit's meta.stages with the signal key of the arrangement it described", async () => {
    addClip();
    vi.spyOn(mixdown, "heads").mockResolvedValue({});
    const entry = { job_id: "mix-1", forge_job_id: "forge-1", file: "mix.wav", label: "MIX", kind: "mix" as const, dur_sec: 40, source_clip_id: null, created: 1 };
    vi.spyOn(jobs, "submit").mockImplementation(async () => {
      mixdown.acceptStages([{ label: "MIX", on: true, note: "(1+2) + (3+4)", seconds: 2.5 }]);
      return entry;
    });
    await runMixdown();
    expect(mixdown.stages).toHaveLength(1);
    expect(mixdown.key).not.toBeNull();
  });

  it("leaves the stages untouched when the commit fails", async () => {
    addClip();
    vi.spyOn(mixdown, "heads").mockResolvedValue({});
    vi.spyOn(jobs, "submit").mockResolvedValue(null);
    await runMixdown();
    expect(mixdown.stages).toBeNull();
    expect(mixdown.key).toBeNull();
  });
});
```

Append to `latent-forge/src/lib/mix/__tests__/signalPath.test.ts` (M7 T3), importing
`mergeSignalPath` and `signalKeyOf` beside its existing `buildSignalPath` import:

```ts
describe("meta.stages reconciled with the estimate (M9 T4; M7 open question 7)", () => {
  function input(patch: Partial<SignalPathInput> = {}): SignalPathInput {
    return {
      lanes: [0, 1, 2, 3].map((i) => ({ index: i as 0 | 1 | 2 | 3, chain: structuredClone(CHAIN_DEFAULTS) })),
      clips: [{ lane: 0, isCropAudio: false, needsStretch: false, a2aOn: false }],
      overlapCount: 0,
      mix: { order: "tree", nodes: { M1: { interp: "lerp", t: 0.5 }, M2: { interp: "lerp", t: 0.5 }, MX: { interp: "lerp", t: 0.5 } }, quad_weights: [1, 1, 1, 1] },
      master: { latch_on: false, head: "none", gain: 64, norm_on: true },
      ...patch,
    };
  }

  it("signalKeyOf is stable for equal input and changes when the arrangement does", () => {
    expect(signalKeyOf(input())).toBe(signalKeyOf(input()));
    expect(signalKeyOf(input({ overlapCount: 1 }))).not.toBe(signalKeyOf(input()));
  });

  it("returns the estimate untouched when no commit has run", () => {
    const est = buildSignalPath(input());
    expect(mergeSignalPath(est, null, signalKeyOf(input()))).toEqual(est);
  });

  it("takes on/note/seconds from the commit when the key still matches", () => {
    const key = signalKeyOf(input());
    const merged = mergeSignalPath(buildSignalPath(input()), {
      key,
      stages: [{ label: "DECODE latent → audio", on: true, note: "3 crops", seconds: 1.5 }],
    }, key);
    expect(merged[0]).toMatchObject({ n: 1, lit: true, note: "3 crops", seconds: 1.5 });
    expect(merged).toHaveLength(9);
  });

  it("falls back to the estimate once the arrangement has moved on", () => {
    const est = buildSignalPath(input({ overlapCount: 2 }));
    const merged = mergeSignalPath(est, {
      key: signalKeyOf(input()),
      stages: [{ label: "INPAINT OVERLAPS", on: false, note: "", seconds: 0 }],
    }, signalKeyOf(input({ overlapCount: 2 })));
    expect(merged).toEqual(est);
  });

  it("keeps the nine rows when the server sends fewer, or a label the client does not have", () => {
    const key = signalKeyOf(input());
    const merged = mergeSignalPath(buildSignalPath(input()), {
      key, stages: [{ label: "SOMETHING NEW", on: true, note: "", seconds: 9 }],
    }, key);
    expect(merged).toHaveLength(9);
    expect(merged.map((s) => s.n)).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9]);
  });
});
```

- [ ] **Step 2: Run them, expect failure**

```bash
cd latent-forge && npx vitest run src/lib/render/__tests__/mixdown.test.ts src/lib/mix/__tests__/signalPath.test.ts
```

Expected: `Failed to resolve import "../mixdown.svelte"`, and in `signalPath.test.ts`
`"mergeSignalPath" is not exported by "../signalPath"`.

- [ ] **Step 3: Append the two pure functions to `latent-forge/src/lib/mix/signalPath.ts`**

Also widen `SignalPathStage` with an optional `seconds`, and export the label list so the merge
can key on it:

```ts
/** From a commit job's `meta.stages` (spec §6.9: "meta.stages (label, on, note, seconds)"). */
export interface CommitStage {
  label: string;
  on: boolean;
  note: string;
  seconds: number;
}

/** The last commit's ground truth, plus the arrangement it described. */
export interface CommitStages {
  key: string;
  stages: CommitStage[];
}

/**
 * The estimate is a pure function of SignalPathInput, so the input IS the identity of what a
 * commit's stages describe. Field order is fixed by construction here rather than by
 * JSON.stringify's insertion order, which differs between a live $state proxy and a structuredClone.
 */
export function signalKeyOf(input: SignalPathInput): string {
  return JSON.stringify([
    input.lanes.map((l) => [l.index, chainActive(l.chain), l.chain.bungee_on]),
    input.clips.map((c) => [c.lane, c.isCropAudio, c.needsStretch, c.a2aOn]),
    input.overlapCount,
    input.mix.order,
    [input.master.latch_on, input.master.norm_on],
  ]);
}

/**
 * M7 open question 7, decided in M9 T4: RECONCILE, not replace. The estimate is always computed;
 * a finished commit's stages override it only while `commit.key` still equals the current input's
 * key. The moment the arrangement changes, the commit describes something else and is dropped --
 * a confidently wrong lit row is worse than an honest estimate (signalPath.ts's own header).
 * Rows are matched by LABEL, so a server that adds or reorders stages degrades to the estimate for
 * the rows the client does not recognise instead of producing a short or renumbered list.
 */
export function mergeSignalPath(
  estimate: SignalPathStage[],
  commit: CommitStages | null,
  currentKey: string,
): SignalPathStage[] {
  if (commit === null || commit.key !== currentKey) return estimate;
  const byLabel = new Map(commit.stages.map((s) => [s.label, s]));
  return estimate.map((row) => {
    const real = byLabel.get(row.label);
    return real === undefined
      ? row
      : { ...row, lit: real.on, note: real.note || row.note, seconds: real.seconds };
  });
}
```

and on the existing interface:

```ts
export interface SignalPathStage {
  n: number;
  label: string;
  lit: boolean;
  note: string;
  /** Present only on a row a finished commit reported (spec §6.9 meta.stages). */
  seconds?: number;
}
```

`chainActive` is already module-private in that file
(`function chainActive(chain: LaneChain): boolean { return chain.latch_on || chain.film_on ||
chain.lora_on || chain.bungee_on; }`) — `signalKeyOf` reuses it, nothing is redeclared.

- [ ] **Step 4: Write `latent-forge/src/lib/render/mixdown.svelte.ts`**

```ts
// The `commit` action, shared by BOTH ▸ MIXDOWN buttons (spec §7.1: the MIX tab's row reads "same
// as the row above"). One module so the two cannot drift: same payload, same block reasons, same
// label, same HELP id.

import { fetchLatchHeads, type LatchHeadInfo } from "../chains/latch";
import type { RenderSettings } from "../forge/types";
import type { CommitStage } from "../mix/signalPath";
import { arrangement } from "../stores/arrangement.svelte";
import { settings } from "../stores/settings.svelte";
import { commitPayload, PayloadError } from "./payloads";
import { jobs } from "./jobs.svelte";

/** §9.7's inline error is keyed by target; a commit has no clip or overlap, so it gets its own. */
export const MIXDOWN_TARGET_KEY = "mixdown";

class MixdownStore {
  /** The last commit's meta.stages, or null. */
  stages = $state<CommitStage[] | null>(null);
  /** The signalKeyOf() of the arrangement those stages describe. */
  key = $state<string | null>(null);

  /** Overridable in tests; /info is fetched once per commit, not cached across a backbone switch. */
  heads(): Promise<Record<string, LatchHeadInfo>> {
    return fetchLatchHeads();
  }

  acceptStages(stages: CommitStage[], key: string | null = this.key): void {
    this.stages = stages;
    this.key = key;
  }

  reset(): void {
    this.stages = null;
    this.key = null;
  }
}

export const mixdown = new MixdownStore();

/**
 * Why MIXDOWN is disabled, in the words the button shows. The empty-arrangement sentence is
 * validate_commit's own (M8 plan:1452-1453, `raise ForgeError(400, "nothing to commit — the
 * arrangement has no clips")`) so the operator reads the same text whichever side caught it.
 */
export function mixdownBlock(): string | null {
  if (jobs.gpuBusyOther !== null) return `GPU busy — ${jobs.gpuBusyOther}`;
  if (jobs.active !== null) return "a render is already running";
  if (arrangement.clips.length === 0) return "nothing to commit — the arrangement has no clips";
  return null;
}

/** §4.5 LENGTH does not apply to a commit: the arrangement's own end is the length (§6.9's
 *  top-level duration_sec), floored at one second so an empty-ish arrangement is not 0. */
function commitDuration(): number {
  return Math.max(1, arrangement.arrangementEndSec);
}

export async function runMixdown(): Promise<void> {
  const blocked = mixdownBlock();
  if (blocked !== null) {
    jobs.lastError = { targetKey: MIXDOWN_TARGET_KEY, message: blocked };
    return;
  }
  let payload: Record<string, unknown>;
  try {
    const heads = await mixdown.heads();
    payload = commitPayload({
      bpm: arrangement.bpm,
      durationSec: commitDuration(),
      defaults: settings.defaults,
      lanes: arrangement.lanes,
      clips: arrangement.clips,
      overlaps: arrangement.overlaps,
      overlapParamsOf: (key) => arrangement.peekOverlapParams(key) ?? OVERLAP_FALLBACK(),
      mix: arrangement.mix,
      master: arrangement.master,
      decodeLanes: false,
      heads,
      // Spec §5.3: guidance is distilled into POST, so cfg goes on the wire as 1.0 there --
      // without mutating any target's own cfg_scale.
      cfgOf: (s: RenderSettings) => (settings.cfgDisabled ? 1.0 : s.cfg_scale),
    });
  } catch (e) {
    // A PayloadError is a refusal we can explain; anything else is a bug and is surfaced the same
    // way rather than thrown into a click handler where nothing would catch it.
    jobs.lastError = {
      targetKey: MIXDOWN_TARGET_KEY,
      message: e instanceof PayloadError || e instanceof Error ? e.message : String(e),
    };
    return;
  }
  await jobs.submit({ op: "commit", payload, kind: "mix", sourceClipId: null, targetKey: MIXDOWN_TARGET_KEY });
}
```

`OVERLAP_FALLBACK()` is M1 T4's `OVERLAP_DEFAULT` cloned — `peekOverlapParams` is the
**non-seeding** read (M7 T3), so a derived overlap whose params were never edited returns
`undefined` and must fall back rather than seed the store from inside a submit path:

```ts
import { OVERLAP_DEFAULT } from "../forge/defaults";
const OVERLAP_FALLBACK = () => structuredClone(OVERLAP_DEFAULT);
```

- [ ] **Step 5: Store the finished commit's stages**

In `latent-forge/src/lib/render/jobs.svelte.ts` (Task 1), the `submit` success path already has the
`JobRecord`. Rather than importing the mix layer into the job layer, expose a hook the mixdown
module registers — `jobs.svelte.ts` stays free of mix imports and the cycle
`mixdown → jobs → mixdown` never forms:

```ts
  /** Called with a finished job's record. M9 T4 registers one to capture a commit's meta.stages. */
  onDone: ((rec: JobRecord) => void) | null = null;
```

called immediately before the `history.add(...)` return in `submit`:

```ts
      this.onDone?.(rec);
```

and in `mixdown.svelte.ts`, at module scope:

```ts
// Spec §6.9: a commit's result carries `meta.stages` ([{label, on, note, seconds}]). Captured with
// the signal key of the arrangement it described, so mergeSignalPath can tell when it has gone stale.
jobs.onDone = (rec) => {
  if (rec.op !== "commit") return;
  const raw = (rec.result?.meta as { stages?: unknown } | undefined)?.stages;
  if (!Array.isArray(raw)) return;
  mixdown.acceptStages(raw as CommitStage[], pendingKey);
};
```

with `pendingKey` captured in `runMixdown` just before submit (`pendingKey =
signalKeyOf(signalInputNow())`), where `signalInputNow()` is the same builder
`MixSignalPath.svelte` uses — extract it into this module and have the component import it, so the
key the commit is stamped with and the key the component compares against come from one function.

- [ ] **Step 6: Run the two suites, expect pass**

```bash
cd latent-forge && npx vitest run src/lib/render/__tests__/mixdown.test.ts src/lib/mix/__tests__/signalPath.test.ts
```

Expected: `Tests  8 passed (8)` in `mixdown.test.ts`, and `Tests  15 passed (15)` in
`signalPath.test.ts` (M7 left it at 10).

- [ ] **Step 7: Write the failing MixdownSlot test**

`latent-forge/src/ui/topbar/__tests__/mixdownSlotWired.test.ts`:

```ts
import { render } from "@testing-library/svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { arrangement } from "../../../lib/stores/arrangement.svelte";
import { history } from "../../../lib/render/history.svelte";
import { jobs } from "../../../lib/render/jobs.svelte";
import * as mixdownModule from "../../../lib/render/mixdown.svelte";
import MixdownSlot from "../MixdownSlot.svelte";

const REF = { kind: "upload", sha256: "a".repeat(64) } as const;

function mixEntry() {
  return { job_id: "mix-1", forge_job_id: "forge-1", file: "mix.wav", label: "MIX 12:00:00", kind: "mix" as const, dur_sec: 40, source_clip_id: null, created: 1 };
}

beforeEach(() => {
  arrangement.clips.splice(0, arrangement.clips.length);
  history.clear();
  jobs.active = null;
  jobs.gpuBusyOther = null;
  vi.restoreAllMocks();
});

describe("MixdownSlot, wired (spec §4.2, §7.1)", () => {
  it("reads ▸ MIXDOWN idle and SAMPLING · N steps left while a commit runs", async () => {
    const { getByTestId, rerender } = render(MixdownSlot, { props: { busy: false, stepsLeft: null } });
    expect(getByTestId("mixdown-button").textContent?.trim()).toBe("▸ MIXDOWN");
    await rerender({ busy: true, stepsLeft: 44 });
    expect(getByTestId("mixdown-button").textContent?.trim()).toBe("SAMPLING · 44 steps left");
  });

  it("is disabled with the block reason as its title on an empty arrangement", () => {
    const { getByTestId } = render(MixdownSlot, { props: {} });
    const button = getByTestId("mixdown-button") as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    expect(button.title).toBe("nothing to commit — the arrangement has no clips");
  });

  it("runs the shared commit action on click once there is something to commit", async () => {
    arrangement.addClip({ lane: 0, startSec: 0, durSec: 8, audio: REF, nativeBpm: 120 });
    const run = vi.spyOn(mixdownModule, "runMixdown").mockResolvedValue(undefined);
    const { getByTestId } = render(MixdownSlot, { props: {} });
    (getByTestId("mixdown-button") as HTMLButtonElement).click();
    expect(run).toHaveBeenCalledTimes(1);
  });

  it("is draggable only with a mix in the slot, and drags the render AudioRef", () => {
    const { getByTestId, rerender } = render(MixdownSlot, { props: {} });
    const canvas = getByTestId("mixdown-canvas") as HTMLCanvasElement;
    expect(canvas.draggable).toBe(false);
    history.add(mixEntry());
    return rerender({}).then(() => {
      expect(canvas.draggable).toBe(true);
      const data: Record<string, string> = {};
      canvas.dispatchEvent(Object.assign(new Event("dragstart", { bubbles: true }), {
        dataTransfer: { setData: (k: string, v: string) => { data[k] = v; }, effectAllowed: "" },
      }));
      expect(JSON.parse(data["application/x-forge-ref"])).toEqual({ kind: "render", job_id: "mix-1", file: "mix.wav" });
    });
  });

  it("play and the canvas stay disabled until a mix exists", async () => {
    const { getByTestId, rerender } = render(MixdownSlot, { props: {} });
    expect((getByTestId("mixdown-play") as HTMLButtonElement).disabled).toBe(true);
    history.add(mixEntry());
    await rerender({});
    expect((getByTestId("mixdown-play") as HTMLButtonElement).disabled).toBe(false);
  });
});
```

- [ ] **Step 8: Wire `latent-forge/src/ui/topbar/MixdownSlot.svelte`**

Keep **every** existing testid and both canvas dimensions (220×26) — M1 T10's own tests and M1
T15's Playwright spec assert them. The changes: `data-help` becomes `HELP.mixdownButton` /
`HELP.mixdownWave` (Fact 9); the button gets `onclick`, a real `disabled` and a `title`; the canvas
gets peaks, scrub, and `draggable`.

```svelte
<script lang="ts">
  // Spec §4.2 + §7.1. The commit action itself lives in lib/render/mixdown.svelte.ts, shared with
  // the MIX tab's button (§7.1: "same as the row above").
  import { HELP } from "../../lib/help/strings";
  import { forgeApi } from "../../lib/forge/api";
  import { drawPeaks, peaksFor, type Peaks } from "../../lib/audio/waveform";
  import { history } from "../../lib/render/history.svelte";
  import { mixdownBlock, runMixdown } from "../../lib/render/mixdown.svelte";
  import { playback } from "../../lib/stores/transport.svelte";
  import { mixdownLabel } from "./mixdown";

  interface Props {
    busy?: boolean;
    stepsLeft?: number | null;
  }
  let { busy = false, stepsLeft = null }: Props = $props();

  let canvasEl = $state<HTMLCanvasElement>();
  let peaks = $state<Peaks | null>(null);
  let playing = $state(false);

  const label = $derived(mixdownLabel(busy, stepsLeft));
  const block = $derived(mixdownBlock());
  const entry = $derived(history.mixdown === null ? null : history.renders[history.mixdown] ?? null);
  const url = $derived(entry === null ? null : forgeApi.audioUrl(history.refOf(entry)));

  // Reads url, writes `peaks` -- an $effect, NOT a $derived (M7 Global Constraint: no writes
  // inside a $derived), and guarded so a superseded load cannot overwrite a newer one.
  $effect(() => {
    const u = url;
    const dur = entry?.dur_sec ?? 0;
    if (u === null || canvasEl === undefined) { peaks = null; return; }
    let live = true;
    void peaksFor(u, null, canvasEl.width, 0, dur).then((p) => { if (live) peaks = p; });
    return () => { live = false; };
  });

  $effect(() => {
    if (canvasEl === undefined) return;
    const ctx = canvasEl.getContext("2d");
    if (ctx === null) return;
    ctx.clearRect(0, 0, canvasEl.width, canvasEl.height);
    if (peaks !== null) drawPeaks(ctx, peaks, canvasEl.width, canvasEl.height);
  });

  function scrub(e: MouseEvent) {
    if (entry === null || canvasEl === undefined) return;
    const rect = canvasEl.getBoundingClientRect();
    // rect.width, not canvas.width: the backing store is 220 px but CSS may size it otherwise.
    const frac = rect.width > 0 ? Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width)) : 0;
    playback.seek(frac * entry.dur_sec);
  }

  function togglePlay() {
    if (url === null) return;
    // §4.5: preview playback is independent of the timeline transport; starting one stops the other.
    playing = !playing;
    if (playing) void playback.preload(url);
    else playback.seek(0);
  }

  function onDragStart(e: DragEvent) {
    if (entry === null || e.dataTransfer === null) return;
    e.dataTransfer.setData("application/x-forge-ref", JSON.stringify(history.refOf(entry)));
    e.dataTransfer.effectAllowed = "copy";
  }
</script>

<div class="mixdown-slot" data-region="mixdown-slot">
  <button
    class="commit"
    class:busy
    data-testid="mixdown-button"
    data-help={HELP.mixdownButton}
    title={block ?? ""}
    disabled={busy || block !== null}
    onclick={() => void runMixdown()}>{label}</button>
  <canvas
    class="wave"
    data-testid="mixdown-canvas"
    data-help={HELP.mixdownWave}
    bind:this={canvasEl}
    width="220"
    height="26"
    draggable={entry !== null}
    ondragstart={onDragStart}
    onclick={scrub}
  ></canvas>
  <button class="play" data-testid="mixdown-play" aria-label="play the latest mixdown"
    disabled={entry === null} onclick={togglePlay}>{playing ? "■" : "▶"}</button>
</div>
```

The `<style>` block is unchanged — Fact 12: *"No drawing for the MIXDOWN slot … the spec text and
M1/M5 frames are the design."*

Then pass the two props that already exist but are never passed. In
`latent-forge/src/ui/shell/TopBar.svelte` (M1 T10) forward `busy`/`stepsLeft` to `<MixdownSlot>`,
and in `latent-forge/src/App.svelte` (M1 T9) pass them from the store:

```svelte
  <TopBar … busy={jobs.busy} stepsLeft={jobs.stepsLeft} />
```

- [ ] **Step 9: Wire M7's two MIX-tab buttons**

In `latent-forge/src/ui/mix/MixSignalPath.svelte` (M7 T5), replace the no-op

```ts
  function onMixdown() {
    // M9 wires the real `commit` job submission (spec §6.9, §7.1). No-op here on purpose.
  }
```

with imports of the shared action and the same label/disable logic, and give both buttons a testid
(M7 gave them none — Fact 10) and the MIXDOWN help id:

```svelte
  <button class="mixdown" data-testid="mix-mixdown" data-help={HELP.mixdownButton}
    title={block ?? ""} disabled={jobs.busy || block !== null}
    onclick={() => void runMixdown()}>{mixdownLabel(jobs.busy, jobs.stepsLeft)}</button>
```

for the expanded panel, and the identical button with `data-testid="mix-mixdown-folded"` in the
`{:else}` summary row. Then reconcile the stage list with the commit's ground truth:

```ts
  const input = $derived(signalInputNow());
  const stages = $derived(mergeSignalPath(buildSignalPath(input), commitStages(), signalKeyOf(input)));
```

where `commitStages()` reads `mixdown.stages === null || mixdown.key === null ? null :
{ key: mixdown.key, stages: mixdown.stages }`. `signalInputNow()` is Task 4's shared builder (Step
5) — the component no longer builds its own `SignalPathInput`, so the key a commit is stamped with
and the key compared here can never disagree.

- [ ] **Step 10: Extend M7's MixSignalPath component test**

Append to `latent-forge/src/ui/mix/__tests__/MixSignalPath.component.test.ts` (M7 T5, 8 cases):

```ts
describe("the MIX-tab MIXDOWN buttons (M9 T4)", () => {
  it("carry a testid and the MIXDOWN help id, not HELP.renderButton", () => {
    const { getByTestId } = render(MixSignalPath, { props: {} });
    const button = getByTestId("mix-mixdown");
    expect(button.getAttribute("data-help")).toBe(HELP.mixdownButton);
    expect(button.getAttribute("data-help")).not.toBe(HELP.renderButton);
  });

  it("run the same commit action as the top bar's button", () => {
    arrangement.addClip({ lane: 0, startSec: 0, durSec: 8, audio: REF, nativeBpm: 120 });
    const run = vi.spyOn(mixdownModule, "runMixdown").mockResolvedValue(undefined);
    const { getByTestId } = render(MixSignalPath, { props: {} });
    (getByTestId("mix-mixdown") as HTMLButtonElement).click();
    expect(run).toHaveBeenCalledTimes(1);
  });

  it("read SAMPLING · N steps left while a commit runs, like the top bar's", async () => {
    arrangement.addClip({ lane: 0, startSec: 0, durSec: 8, audio: REF, nativeBpm: 120 });
    jobs.active = { forgeJobId: "forge-1", op: "commit", kind: "mix", sourceClipId: null, targetKey: "mixdown", progress: null };
    jobs.active.progress = { job_id: "forge-1", op: "commit", stage: "MIX", stage_index: 7, stage_count: 9, step: 0, steps: 0, steps_left_total: 12, steps_total: 24 };
    const { getByTestId } = render(MixSignalPath, { props: {} });
    expect(getByTestId("mix-mixdown").textContent?.trim()).toBe("SAMPLING · 12 steps left");
  });
});
```

- [ ] **Step 11: Add the two HELP strings**

In `docs/latent-forge/extract_help.mjs`, add to `NEW_STRINGS` — the text is M1's own literal
`data-help` copy from `MixdownSlot.svelte`, moved verbatim so nothing is reworded:

```js
  mixdownButton:
    "Mixes the four lanes in the latent domain and decodes the result — the commit that turns " +
    "the arrangement into audio. While it samples, the window border runs a C64 loader raster " +
    "bar whose sweep rate falls with the remaining step count.",
  mixdownWave:
    "The latest mixdown. Click to scrub it, and drag it onto a lane to use it as a clip. " +
    "Earlier mixdowns stay in the render history at the bottom of the screen.",
```

Then regenerate and move the count:

```bash
cd latent-forge && npm run help:extract
```

Expected: `extract_help: wrote 114 strings (80 extracted, 14 rewritten, 34 new)`. In
`latent-forge/src/lib/help/__tests__/strings.test.ts`, change
`expect(Object.keys(HELP)).toHaveLength(112);` to `114` and the title's count to match. **Writer B's
Tasks 6-10 add more; 114 is this task's running total, not M9's final one** — the assembly step
recounts (open question 6).

- [ ] **Step 12: Run everything**

```bash
cd latent-forge && npx vitest run && npm run check
```

Expected: `mixdown.test.ts` 8, `signalPath.test.ts` 15, `mixdownSlotWired.test.ts` 5,
`MixSignalPath.component.test.ts` 11, `strings.test.ts` green at 114, the rest of the suite
unchanged, `npm run check` clean.

- [ ] **Step 13: Commit**

```bash
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M9 T4: both MIXDOWN buttons run one shared commit action; latest-mix waveform, scrub, play and drag-to-lane in the top-bar slot; commit meta.stages reconciled with the SIGNAL PATH estimate"
```

---

### Task 5: Error surfaces — the TERMINAL split, the inline error, and `renderBlock`

**WHY.** Spec §9.7 is four lines and three of them are currently unreachable:

> - Server error → TERMINAL gains a red line, and the target shows an inline one-line error under
>   the target bar until the next render.
> - `/status.busy` with a non-forge job → RENDER shows `GPU busy — <job_id>`.
> - Unmounted drive errors keep the server's hint text.
> - Blocked targets use the existing `renderBlock` reasons, extended to the new ops.

**Fact 8 — the bug this task fixes once.** There are **two** log arrays and the TERMINAL renders
only one. M1 T11's `BottomPane.svelte` mounts `<Terminal mode={terminalMode} busy={logStore.busy}
lines={logStore.lines} onmode={onterminalmode} />` — `logStore.lines`, which is filled only by
`logStore.poll()` from `GET /forge/log`. Meanwhile M1 T7's view store has its own
`logLines = $state<TerminalLine[]>([])` and `appendLog(text: string, level: "info" | "error" =
"info"): TerminalLine`, and **that** is what every milestone's error path calls:
`view.appendLog(\`[stats] ${e}\`, "error")` (M10), `view.appendLog(\`[chroma] stretch:
${e.message}\`, "error")` and `view.appendLog(\`[chroma] ${e}\`, "error")` (M6),
`log: (text, level) => view.appendLog(text, level)` (M7's SessionController). Every one of those
red lines is written into an array nothing renders. Three milestones' error reporting is invisible.

**The single fix, decided: `view.appendLog` mirrors into `logStore`, and TERMINAL keeps rendering
`logStore.lines`.** The two rejected alternatives and why:

- *Render both arrays in `Terminal.svelte`.* They have independent sequence spaces —
  `view.logSeq` is a client counter starting at 1, `logStore.seq` is the **server's** `/forge/log`
  cursor — so any merge by `seq` interleaves them wrongly, and a merge by arrival order needs a
  third array anyway. Two renders in one pane is also two scroll positions.
- *Repoint `view.appendLog` at `logStore` and delete `view.logLines`.* It changes the method's
  return type (`TerminalLine {seq, text, level}` → `LogLine {seq, text, tone}`) and M1 T7's own
  suite asserts the old one: `expect(line).toBe(v.logLines[v.logLines.length - 1]);`. That is a
  cross-milestone break for no behavioural gain.

Mirroring is additive: `view.appendLog` keeps its array, its return value and its ring, and
*also* appends to `logStore`. M6/M7/M10 need no change at all, which is the point — the fix is in
one file and nothing that already works is touched.

**The cursor must not move.** `logStore.append(text, seq)` ends with `if (seq > this.seq)
this.seq = seq;`, and `poll()` fetches `forgeApi.log(this.seq)` — lines *since* that cursor. A
client-side line appended at a made-up sequence number would advance the cursor past real server
lines and they would never be fetched. So the mirror appends at `logStore.seq`, exactly as
`logStore`'s own transport-failure path already does (`this.append(message, this.seq, "error")`).
This task adds `logStore.appendLocal(text, tone)` to say that in one place, and switches Task 1's
`logStore.append(\`[forge] …\`, logStore.seq, "error")` call over to it.

**`renderBlock` is pure and shared.** Writer B's `▸ RENDER` (Task 6) and this task's inline error
both need the reasons, and the two writers run in parallel — so it takes its whole world as an
argument and imports no store. The v1 reasons it extends are in
`sa3-studio/src/lib/store.svelte.ts:351-388` (`renderBlock(clip: Clip): RenderBlock | null`) —
`"needs a prompt"`, `"no latent to decode"`, `"needs a schedule"`, `"no bend ops"`, each with a
hint. §9.7's surface is **one line**, so the reason and the hint are joined the way v1's own
`renderClip` already joined them: `` throw new Error(`${blocked.reason} — ${blocked.hint}`) ``.
`a2a_track`/`a2a_mix` are not carried over: they need a server-side `audio_path` and there is no
UI for them in M9 (open question 3).

**Files:**
- Create: `latent-forge/src/lib/render/renderBlock.ts`,
  `latent-forge/src/lib/render/__tests__/renderBlock.test.ts`,
  `latent-forge/src/ui/prompt/InlineError.svelte`,
  `latent-forge/src/ui/prompt/__tests__/inlineError.test.ts`,
  `latent-forge/src/lib/stores/__tests__/terminalLog.test.ts`
- Modify: `latent-forge/src/lib/stores/log.svelte.ts` (M1 T11 — add `appendLocal`),
  `latent-forge/src/lib/stores/view.svelte.ts` (M1 T7 — `appendLog` mirrors),
  `latent-forge/src/lib/render/jobs.svelte.ts` (Task 1 — use `appendLocal`),
  `latent-forge/src/ui/prompt/PromptSigmaTab.svelte` (M4 — mount `InlineError` under the target bar)

**Interfaces.**

Consumed from `src/lib/stores/view.svelte.ts` (M1 T7, verified):
`interface TerminalLine { seq: number; text: string; level: "info" | "error" }`,
`view.logLines: TerminalLine[]`, `view.appendLog(text: string, level?: "info" | "error"):
TerminalLine` (its body: `this.logSeq += 1; this.logLines.push({seq: this.logSeq, text, level});`
then the `LOG_RING` trim, then `return this.lastLogLine();`), `view.clearLog()`,
`LOG_RING = 400`, `view.selection: Target`.

Consumed from `src/lib/stores/log.svelte.ts` (M1 T11, verified):
`type LogTone = "text" | "dim" | "accent" | "error"`, `interface LogLine { seq: number;
text: string; tone: LogTone }`, `logTone(text: string): LogTone`, `logStore.lines: LogLine[]`,
`logStore.seq: number`, `logStore.append(text: string, seq: number, tone?: LogTone): LogLine`
(*"Svelte 5 proxy rule … Return the array's live element."*), `logStore.clear()`.

Consumed from `src/lib/render/jobs.svelte.ts` (Task 1): `jobs.lastError: {targetKey: string;
message: string} | null`, `jobs.busy: boolean`, `jobs.gpuBusyOther: string | null`.

Consumed from `src/lib/forge/types.ts` (M1 T3): `type Target = {kind: "none"} | {kind: "clip";
id: string} | {kind: "overlap"; key: string}`, `interface RenderSettings {… duration_sec: number}`,
`interface ForgeClip {… audio: AudioRef; a2a: null | {on; noise; envelope}; …}`,
`type AudioRef` (its `crop` member is `{kind: "crop"; crop_id: string}`).

Consumed from `src/lib/render/payloads.ts` (Task 1): `CAP_SEC = 184`.

Produced, **and cited by Writer B's Task 6**:
`type ClipOp = "generate" | "decode" | "longform" | "bend"`,
`interface RenderBlockState { busy: boolean; gpuBusyOther: string | null;
settings: RenderSettings; clip: ForgeClip | null; clipOp: ClipOp | null; arcPrompt: string;
bendOpCount: number; overlapSpanSec: number; padSec: number }`,
`renderBlock(target: Target, state: RenderBlockState): string | null`, and the component
`InlineError` (`data-testid="render-error"`, props `{ targetKey: string }`).

- [ ] **Step 1: Write the failing `renderBlock` test**

`latent-forge/src/lib/render/__tests__/renderBlock.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { BASE_DEFAULTS, cloneRenderSettings } from "../../forge/defaults";
import type { ForgeClip, RenderSettings, Target } from "../../forge/types";
import { CAP_SEC } from "../payloads";
import { renderBlock, type RenderBlockState } from "../renderBlock";

const CROP = { kind: "crop", crop_id: "000412" } as const;
const UPLOAD = { kind: "upload", sha256: "a".repeat(64) } as const;

function clip(patch: Partial<ForgeClip> = {}): ForgeClip {
  return {
    id: "c1", lane: 0, start_sec: 0, offset_sec: 0, dur_sec: 8, loop: false, audio: UPLOAD,
    native_bpm: 120, detune_cents: 0, downbeats_sec: [], render: cloneRenderSettings(BASE_DEFAULTS),
    a2a: null, latentState: "none", history: [], ...patch,
  } as ForgeClip;
}

function state(patch: Partial<RenderBlockState> = {}): RenderBlockState {
  return {
    busy: false, gpuBusyOther: null,
    settings: { ...cloneRenderSettings(BASE_DEFAULTS), prompt: "dub", duration_sec: 45 } as RenderSettings,
    clip: null, clipOp: null, arcPrompt: "", bendOpCount: 0,
    overlapSpanSec: 4, padSec: 8, ...patch,
  };
}

const NONE: Target = { kind: "none" };
const CLIP: Target = { kind: "clip", id: "c1" };
const OVERLAP: Target = { kind: "overlap", key: "a-b" };

describe("renderBlock -- §9.7's blocked-target reasons, extended to M9's ops", () => {
  it("blocks everything while a job runs (§7.1)", () => {
    expect(renderBlock(NONE, state({ busy: true }))).toBe("a render is already running");
  });

  it("reports a GPU held by another job first, in §9.7's exact words", () => {
    expect(renderBlock(NONE, state({ busy: true, gpuBusyOther: "dash-77" }))).toBe("GPU busy — dash-77");
  });

  it("nothing selected: needs a prompt, then nothing", () => {
    expect(renderBlock(NONE, state({ settings: { ...state().settings, prompt: "  " } })))
      .toBe("needs a prompt — /generate requires a non-empty prompt.");
    expect(renderBlock(NONE, state())).toBeNull();
  });

  it("nothing selected: refuses a LENGTH over the 184 s cap", () => {
    const over = { ...state().settings, duration_sec: CAP_SEC + 1 };
    expect(renderBlock(NONE, state({ settings: over }))).toMatch(/184/);
  });

  it("clip with A2A on is never blocked for a prompt -- a2a_clip needs no prompt", () => {
    const c = clip({ a2a: { on: true, noise: 0.4, envelope: null } });
    expect(renderBlock(CLIP, state({ clip: c, settings: { ...state().settings, prompt: "" } }))).toBeNull();
  });

  it("clip with A2A off and no op shows §7.1's own hint", () => {
    expect(renderBlock(CLIP, state({ clip: clip(), clipOp: null })))
      .toBe("turn A2A on or choose an op");
  });

  it("clip + decode needs a latent: a crop ref passes, an upload does not", () => {
    expect(renderBlock(CLIP, state({ clip: clip({ audio: CROP }), clipOp: "decode" }))).toBeNull();
    expect(renderBlock(CLIP, state({ clip: clip({ audio: UPLOAD }), clipOp: "decode" })))
      .toBe("no latent to decode — /decode takes crop_id or latent_path.");
  });

  it("clip + bend needs a latent AND at least one op", () => {
    expect(renderBlock(CLIP, state({ clip: clip({ audio: CROP }), clipOp: "bend", bendOpCount: 0 })))
      .toMatch(/no bend ops/);
    expect(renderBlock(CLIP, state({ clip: clip({ audio: CROP }), clipOp: "bend", bendOpCount: 2 }))).toBeNull();
  });

  it("clip + longform needs the arc, not the plain prompt", () => {
    expect(renderBlock(CLIP, state({ clip: clip(), clipOp: "longform", arcPrompt: "" })))
      .toMatch(/arc/);
    expect(renderBlock(CLIP, state({ clip: clip(), clipOp: "longform", arcPrompt: "0:pad|45:bass" }))).toBeNull();
  });

  it("clip + generate still needs a prompt", () => {
    expect(renderBlock(CLIP, state({ clip: clip(), clipOp: "generate", settings: { ...state().settings, prompt: "" } })))
      .toMatch(/needs a prompt/);
  });

  it("overlap: passes normally, refuses a padded span over the cap", () => {
    expect(renderBlock(OVERLAP, state())).toBeNull();
    expect(renderBlock(OVERLAP, state({ overlapSpanSec: 180, padSec: 8 }))).toMatch(/184/);
  });
});
```

- [ ] **Step 2: Run it, expect failure**

```bash
cd latent-forge && npx vitest run src/lib/render/__tests__/renderBlock.test.ts
```

Expected: `Error: Failed to resolve import "../renderBlock"`.

- [ ] **Step 3: Write `latent-forge/src/lib/render/renderBlock.ts`**

```ts
// Spec §9.7: "Blocked targets use the existing `renderBlock` reasons, extended to the new ops."
// The existing ones are v1's (sa3-studio/src/lib/store.svelte.ts:351-388) -- {reason, hint} pairs.
// §9.7's surface is ONE line, so reason and hint are joined with the em dash v1's own renderClip
// used: `${blocked.reason} — ${blocked.hint}`.
//
// PURE, and it imports no store: Writer B's ▸ RENDER (M9 T6) and this task's inline error both
// call it, and the two were written in parallel. The caller reads the stores and hands the world
// in, which is also what makes every branch here a one-line test.
//
// a2a_track and a2a_mix are deliberately absent: both need a server-side `audio_path` and there is
// no upload-to-path route (v1's own hint says so), and §7.1's OP column lists only
// generate/decode/longform/bend. See open question 3.

import type { ForgeClip, RenderSettings, Target } from "../forge/types";
import { CAP_SEC } from "./payloads";

export type ClipOp = "generate" | "decode" | "longform" | "bend";

export interface RenderBlockState {
  /** jobs.busy -- §7.1: "While any job runs, every render control is disabled". */
  busy: boolean;
  /** jobs.gpuBusyOther -- §9.7's `GPU busy — <job_id>`. */
  gpuBusyOther: string | null;
  /** The TARGET's own settings (§7.2), not the session defaults, unless the target is `none`. */
  settings: RenderSettings;
  /** The selected clip, when the target is a clip. */
  clip: ForgeClip | null;
  /** The clip's OP when A2A is off. null = it has neither (§7.1's disabled row). */
  clipOp: ClipOp | null;
  /** The prompt-ARC string for `longform` (server:1366 reads it as req["schedule"]). */
  arcPrompt: string;
  /** How many bend ops are configured. */
  bendOpCount: number;
  /** The overlap's own length in seconds, when the target is an overlap. */
  overlapSpanSec: number;
  /** The inpaint context each side (spec §6.8, default 8.0). */
  padSec: number;
}

const CAP_LINE = `over the 184 s cap — forge passes are capped at 184 s locally (T<2048).`;

/** v1's rule, unchanged: a latent exists if the clip's own audio is a crop ref. M9 has no
 *  `latentPath` on ForgeClip, so the crop ref is the whole of it (open question 3). */
function hasLatent(clip: ForgeClip): boolean {
  return clip.audio.kind === "crop";
}

function generateBlock(s: RenderSettings): string | null {
  if (!s.prompt.trim()) return "needs a prompt — /generate requires a non-empty prompt.";
  if (!(s.duration_sec > 0) || s.duration_sec > CAP_SEC) return `LENGTH is ${CAP_LINE}`;
  return null;
}

export function renderBlock(target: Target, state: RenderBlockState): string | null {
  // §9.7 puts the GPU line on RENDER itself, so it outranks the generic busy line -- an operator
  // needs to know it is someone else's job, not theirs.
  if (state.gpuBusyOther !== null) return `GPU busy — ${state.gpuBusyOther}`;
  if (state.busy) return "a render is already running";

  if (target.kind === "overlap") {
    const span = state.overlapSpanSec + 2 * state.padSec;
    if (!(state.overlapSpanSec > 0)) return "the overlap has no length";
    if (span > CAP_SEC) return `the padded inpaint span is ${CAP_LINE}`;
    return null;
  }

  if (target.kind === "none") return generateBlock(state.settings);

  const clip = state.clip;
  if (clip === null) return "the selected clip is gone";
  // §7.1 row 2: A2A on wins, and a2a_clip needs no prompt -- the source audio is the prompt.
  if (clip.a2a?.on) return null;
  // §7.1 row 3's own words, quoted: "disabled with the hint `turn A2A on or choose an op`".
  if (state.clipOp === null) return "turn A2A on or choose an op";

  switch (state.clipOp) {
    case "generate":
      return generateBlock(state.settings);
    case "decode":
      return hasLatent(clip) ? null : "no latent to decode — /decode takes crop_id or latent_path.";
    case "bend":
      if (!hasLatent(clip)) return "no latent to bend — /bend takes crop_id or latent_path.";
      return state.bendOpCount > 0
        ? null
        : "no bend ops — add at least one op: channel_roll, quantize, segment_shuffle…";
    case "longform":
      return state.arcPrompt.trim()
        ? null
        : "needs a prompt arc — arc grammar, e.g. 0:opening pad|45:driving bass.";
  }
}
```

- [ ] **Step 4: Run it, expect pass**

```bash
cd latent-forge && npx vitest run src/lib/render/__tests__/renderBlock.test.ts
```

Expected: `Test Files  1 passed (1)` / `Tests  11 passed (11)`.

- [ ] **Step 5: Write the failing TERMINAL test**

`latent-forge/src/lib/stores/__tests__/terminalLog.test.ts`:

```ts
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ForgeApiError, forgeApi } from "../../forge/api";
import { jobs } from "../../render/jobs.svelte";
import { logStore } from "../log.svelte";
import { view } from "../view.svelte";

beforeEach(() => {
  logStore.clear();
  view.clearLog();
  jobs.active = null;
  jobs.lastError = null;
  vi.restoreAllMocks();
});

describe("Fact 8: view.appendLog's red lines must reach what TERMINAL renders", () => {
  it("mirrors into logStore.lines -- the array BottomPane hands to <Terminal>", () => {
    view.appendLog("[chroma] stretch: drive not mounted", "error");
    expect(logStore.lines.at(-1)?.text).toBe("[chroma] stretch: drive not mounted");
    expect(logStore.lines.at(-1)?.tone).toBe("error");
  });

  it("keeps its own M1 T7 contract: still returns view.logLines' LIVE element", () => {
    const line = view.appendLog("[session] saved");
    expect(line).toBe(view.logLines[view.logLines.length - 1]);
    expect(line.level).toBe("info");
  });

  it("does NOT advance the server log cursor -- /forge/log would skip real lines", () => {
    logStore.append("server line", 41);
    const cursor = logStore.seq;
    view.appendLog("[stats] client-side failure", "error");
    view.appendLog("[stats] another", "error");
    expect(logStore.seq).toBe(cursor);
  });

  it("a server error reaches TERMINAL with its hint text intact (§9.7 unmounted drives)", async () => {
    const hint = "crops root /run/media/… is not mounted — plug the drive or pick another root";
    vi.spyOn(forgeApi, "submitJob").mockRejectedValue(new ForgeApiError(400, hint));
    await jobs.submit({ op: "generate", payload: {}, kind: "gen", sourceClipId: null, targetKey: "session" });
    expect(logStore.lines.at(-1)?.tone).toBe("error");
    expect(logStore.lines.at(-1)?.text).toContain(hint);
    expect(jobs.lastError?.message).toBe(hint);
  });
});
```

- [ ] **Step 6: Run it, expect failure**

```bash
cd latent-forge && npx vitest run src/lib/stores/__tests__/terminalLog.test.ts
```

Expected: case 1 fails — `expected undefined to be '[chroma] stretch: drive not mounted'` (the
line went into `view.logLines`, which nothing renders); case 4 fails on
`logStore.appendLocal is not a function` once Step 7's `jobs.svelte.ts` change is in, or passes
against Task 1's `logStore.append(..., logStore.seq, "error")` call — either way case 1 is the
gate.

- [ ] **Step 7: Make the fix, in two small edits**

(a) In `latent-forge/src/lib/stores/log.svelte.ts` (M1 T11), add beside `append`:

```ts
  /**
   * A line the CLIENT produced, not the server. It goes in the same ring TERMINAL renders, at the
   * current cursor -- never past it. `poll()` fetches `forgeApi.log(this.seq)`, i.e. lines SINCE
   * the cursor, so a client line appended at an invented sequence number would skip real server
   * lines forever. This is the same trick poll()'s own failure path already uses.
   */
  appendLocal(text: string, tone: LogTone = logTone(text)): LogLine {
    return this.append(text, this.seq, tone);
  }
```

(b) In `latent-forge/src/lib/stores/view.svelte.ts` (M1 T7), have `appendLog` mirror. Everything
else about it is unchanged — same array, same ring, same return value, so M1 T7's own tests and
M6/M7/M10's call sites all stay exactly as they are:

```ts
  appendLog(text: string, level: "info" | "error" = "info"): TerminalLine {
    this.logSeq += 1;
    this.logLines.push({ seq: this.logSeq, text, level });
    if (this.logLines.length > LOG_RING) {
      this.logLines.splice(0, this.logLines.length - LOG_RING);
    }
    // Fact 8 / M9 T5: TERMINAL renders logStore.lines (M1 T11's BottomPane passes
    // `lines={logStore.lines}`), so a line written only here was invisible -- M6's chroma errors,
    // M7's session errors and M10's stats errors all were. Mirrored rather than moved: this
    // method's return type is part of M1 T7's tested contract.
    logStore.appendLocal(text, level === "error" ? "error" : logTone(text));
    return this.lastLogLine();
  }
```

with `import { logStore, logTone } from "./log.svelte";` at the top of the view store. **Check the
direction of the import**: `log.svelte.ts` imports only `forgeApi` from `../forge/api`, so
`view → log` adds no cycle.

(c) In `latent-forge/src/lib/render/jobs.svelte.ts` (Task 1), swap the one call for the named
helper so there is a single spelling of "a client-side line":

```ts
      logStore.appendLocal(`[forge] ${req.op} failed: ${text}`, "error");
```

- [ ] **Step 8: Run it, expect pass**

```bash
cd latent-forge && npx vitest run src/lib/stores/__tests__/terminalLog.test.ts src/lib/stores/__tests__/view.test.ts
```

Expected: `Tests  4 passed (4)` in `terminalLog.test.ts`, and M1 T7's `view.test.ts` **unchanged
and green** — that is the check that the fix is additive.

- [ ] **Step 9: Write the failing inline-error test**

`latent-forge/src/ui/prompt/__tests__/inlineError.test.ts`:

```ts
import { render } from "@testing-library/svelte";
import { beforeEach, describe, expect, it } from "vitest";
import { jobs } from "../../../lib/render/jobs.svelte";
import InlineError from "../InlineError.svelte";

beforeEach(() => {
  jobs.lastError = null;
  jobs.gpuBusyOther = null;
});

describe("InlineError -- §9.7's one line under the target bar", () => {
  it("shows the message for its own target", () => {
    jobs.lastError = { targetKey: "clip:c1", message: "unknown render field(s): duration_sec" };
    const { getByTestId } = render(InlineError, { props: { targetKey: "clip:c1" } });
    expect(getByTestId("render-error").textContent).toContain("duration_sec");
  });

  it("stays out of the way for another target's error", () => {
    jobs.lastError = { targetKey: "clip:c9", message: "boom" };
    const { queryByTestId } = render(InlineError, { props: { targetKey: "clip:c1" } });
    expect(queryByTestId("render-error")).toBeNull();
  });

  it("shows `GPU busy — <job_id>` on every target, with no error of its own", () => {
    jobs.gpuBusyOther = "dash-77";
    const { getByTestId } = render(InlineError, { props: { targetKey: "session" } });
    expect(getByTestId("render-error").textContent?.trim()).toBe("GPU busy — dash-77");
  });
});
```

- [ ] **Step 10: Write `latent-forge/src/ui/prompt/InlineError.svelte`**

Fact 12: *"No drawing for … an error line — the spec text and M1/M5 frames are the design."* So it
is one line of existing tokens, no new visual language.

```svelte
<script lang="ts">
  // Spec §9.7: "the target shows an inline one-line error under the target bar until the next
  // render". `jobs.lastError` is cleared by the next submit (M9 T1), which IS "until the next
  // render" -- nothing here needs a timer or a dismiss button.
  import { jobs } from "../../lib/render/jobs.svelte";

  interface Props {
    /** The same key the render control passes to jobs.submit. */
    targetKey: string;
  }
  let { targetKey }: Props = $props();

  // The GPU line is not a failure of THIS target, so it shows on every target, and an actual
  // error for this target outranks it.
  const text = $derived(
    jobs.lastError?.targetKey === targetKey
      ? jobs.lastError.message
      : jobs.gpuBusyOther !== null
        ? `GPU busy — ${jobs.gpuBusyOther}`
        : null,
  );
</script>

{#if text !== null}
  <div class="render-error" data-testid="render-error" role="status">{text}</div>
{/if}

<style>
  .render-error {
    font-size: 10px;
    color: var(--danger, var(--text-dim));
    padding: 2px 0 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
</style>
```

Mount it in `latent-forge/src/ui/prompt/PromptSigmaTab.svelte` (M4), immediately after the target
bar, with the key the pane's own target uses:

```svelte
  <InlineError targetKey={targetKeyOf(view.selection)} />
```

where `targetKeyOf` is the shared spelling of a target as a string — declared once in
`renderBlock.ts` beside `renderBlock`, because `jobs.submit`, `InlineError` and Writer B's RENDER
all need the same one:

```ts
/** The string `jobs.lastError.targetKey` is keyed by. One spelling, used by every render control. */
export function targetKeyOf(t: Target): string {
  return t.kind === "none" ? "session" : t.kind === "clip" ? `clip:${t.id}` : `overlap:${t.key}`;
}
```

(Task 4's `MIXDOWN_TARGET_KEY = "mixdown"` sits outside this scheme on purpose — a commit has no
target.)

- [ ] **Step 11: Run everything**

```bash
cd latent-forge && npx vitest run && npm run check
```

Expected: `renderBlock.test.ts` 11, `terminalLog.test.ts` 4, `inlineError.test.ts` 3 — 18 for this
task — with M1 T7's `view.test.ts`, M1 T11's log suite, M6's, M7's and M10's suites all unchanged
and green, and `npm run check` clean.

- [ ] **Step 12: Commit**

```bash
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M9 T5: view.appendLog mirrors into what TERMINAL actually renders (M6/M7/M10 red lines were invisible), §9.7 inline target error and GPU-busy line, pure renderBlock shared with the RENDER dispatch"
```

---

## Open questions (Writer A, Tasks 1-5)

Each of these is **shipped with a reading** — the tasks above build one answer and say why. They
are listed so the assembly pass and WINTERMUTE can overrule any of them cheaply, not because
anything is left unbuilt.

1. **`longform`'s `schedule` key means two different things on the same request.**
   `_longform_impl` reads it as the prompt-ARC string — `eval/explorer_render_server.py:1366`:
   `schedule_arg = (req.get("schedule") or req.get("prompt") or "").strip()`, then
   `arc = _parse_prompt_arc(schedule_arg)`. But M3 Task 2 edit (h) puts `resolve_shift(req, steps,
   nl, warnings)` on longform's a2a branch, and `resolve_shift` reads `req["schedule"]` as a
   **ScheduleSpec object** through `parse_spec`, which 400s on a string
   (`m3 plan:217`: `raise ForgeError(400, "schedule must be an object")`). One key, two readers,
   and on the t2a branch M3 already hard-refuses (`"schedule shapes are not supported on the t2a
   longform path"`). **Shipped:** `opPayload("longform", …)` sends the arc string under `schedule`
   and no ScheduleSpec at all, so the client can never trip `parse_spec`. That costs longform every
   ADVANCED SAMPLING shape. **For W:** the fix is server-side — a separate `prompt_arc` key, or
   `resolve_shift` ignoring a string `schedule`. Until then longform charts and samples the model
   shape only. This is the batched-DM item with the most consequence.

2. **Who owns `/status` (M1 open question 16).** The brief says *"if M9's poller owns `/status`,
   the log store drops its own `/status` call."* **Shipped: both keep calling it**, 1000 ms each,
   because they read different fields for different consumers — `logStore.busy` drives the
   TERMINAL status dot and is polled *only while the TERMINAL tab is visible*
   (M1 T11: `logStore.start(1000)` in the tab's effect), while `jobs.gpuBusyOther` must be live
   whichever tab is open, since it disables every render control. Folding them would mean either
   polling the log when nothing shows it, or losing the GPU line on three tabs out of four. The
   cost is one extra GET per second while TERMINAL is open, against a local server. If that is
   judged wasteful, the merge is `logStore` reading `jobs.gpuBusyOther` and dropping its own call —
   one edit, no behaviour change.

3. **`a2a_track`, `a2a_mix`, and where a clip's latent lives.** §6.2 lists both ops and M2
   registers them, but both need a server-side `audio_path` and there is no upload-to-path route
   (v1's own `renderBlock` hint says exactly this). §7.1's OP column lists only
   `generate`/`decode`/`longform`/`bend`, so `opPayload` builds those four and `renderBlock` blocks
   nothing for the other two — they are unreachable, not half-built. Related: `renderBlock`'s
   "has a latent" test is `clip.audio.kind === "crop"`, because v1's `clip.latentPath` has no
   equivalent on `ForgeClip`. A render's own `.z0.npy` is written by every job
   (`meta.latents`) and is **not** reachable from a `RenderHistoryEntry` — so DECODE and BEND work
   on library crops only. Worth a field on `ForgeClip` or `RenderHistoryEntry` if that matters.

4. **`a2a_clip` takes the whole file, and REPLACE CLIP has to cope** (Fact 3). M8:
   `duration = check_cap(audio.shape[1] / SR, "a2a_clip")` — no offset, no dur, no stretch. So a
   clip trimmed to 4 s of a 40 s source is A2A'd across all 40 s, and the returned render is 40 s.
   **Shipped:** the builder sends the clip's `audio` ref unchanged and says so. **For Writer B:**
   REPLACE CLIP (Task 8) must decide whether the clip keeps its `offset_sec`/`dur_sec` against the
   new audio (they still address the same timebase, so yes) or is re-fitted to the render. Flagged
   here because the payload builder is where the constraint is visible.

5. **Render history and the "replace unsaved work?" prompt** (Task 3). `renders`/`mixdown`/
   `preview` are serialised and restored but **excluded from `unsavedWorkKey`**, so a finished
   render does not make a session count as edited. Rationale in Task 3's WHY. The opposite reading
   — that losing a session's history list is a real loss worth a prompt — is defensible; it just
   makes the prompt fire after every render.

6. **The final `strings.test.ts` total is not knowable from this half of the plan.** Task 4 takes
   M7's 112 to **114**. Writer B's Tasks 6-10 add the preview-container ids (Fact 9 lists
   `preview-render`, HISTORY, drag, USE SETTINGS, REPLACE CLIP and `previewMixdownToggle`'s
   attachment). The two writers cannot see each other's running totals, so **the assembly pass must
   re-run `npm run help:extract` and set the number from its output**, exactly as M7's own critic
   round had to (M7's finding 1: *"`strings.test.ts` never updated. M1's suite went red at Task 2's
   first new string."*).

7. **M2 T15's `EXPECTED` has 25 names; its docstring and Step 6 still say 20**
   (m2 plan:3198-3201, 3244-3252, 3362 — the tuple lists 25 entries while the text says *"All 25
   fixtures are REQUIRED"* in one place and *"it is TWENTY fixtures, not nineteen"* in `HANDOUT.md`).
   Nothing here depends on the count — the four job fixtures this plan uses are named individually
   and each test skips on its own missing file — but the recorder's success line and its docstring
   disagree, so a run that records 20 of 25 could be read as complete. One for the batched DM.

8. **`jobs.onDone` is a plain field, not a rune** (Task 4 Step 5). It exists so the job layer never
   imports the mix layer. If a second consumer ever wants a finished job (Writer B's assembly is
   the likely one), it needs to become a small subscriber list rather than a single slot — cheap
   to change, worth noticing before two things fight over it.

9. **Cancel is offered but nothing in M9 mounts a CANCEL control.** `JobsStore.cancel()` is in the
   brief's pre-declared interface and is built and tested, but §4.2/§4.5 draw no cancel button, and
   §6.2 only cancels a *queued* job — the queue exists "for the Dash explorer and scripted use"
   (§7.1), and M9 never queues a second job. So `cancel()` is reachable only from code. Left as is
   rather than inventing a control the drawing does not have (Fact 12).
