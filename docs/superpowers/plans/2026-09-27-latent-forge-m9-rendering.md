# Latent Forge M9 — rendering

**Goal:** build spec line 1001's rendering client: the `▸ RENDER` controls and their per-target
dispatch (§7.1), job submission and polling against the forge queue, the `SAMPLING · N steps left`
labels, the raster border (§9.5), the render preview container (HISTORY, waveform scrub, drag to
lane, USE SETTINGS, REPLACE CLIP), the MIXDOWN slot (latest mix, scrub, drag to lane), the
PREVIEW/MIXDOWN A/B toggle, and the error surfaces (§9.7). This is the last frontend plan.

**Architecture:** split by LAYER at the job boundary. Writer A took the job layer and everything
that submits — the jobs store, the per-op payload builders, the history store, the raster border,
the MIXDOWN surfaces and the errors/TERMINAL fix. Writer B took the preview container and
everything that consumes a finished render — RENDER dispatch, HISTORY, USE SETTINGS, REPLACE CLIP,
the master-strip A/B, INPAINT OVERLAP and drag-to-lane. The two store interfaces that cross the
seam (`JobsStore`, `HistoryStore`) were pre-declared by exact name and signature in the brief
before either writer started, so neither waited on the other.

**Tech stack:** Vite + Svelte 5 (runes) + TypeScript 5.6, vitest 2, Playwright 1.

**Spec:** `docs/superpowers/specs/2026-09-15-latent-forge-design.md` — §7.1 is the render control
table and the per-target dispatch rule; §6.1/6.2 are the forge job contract; §6.7-6.9 are the
queue, status and cancel routes; §8.1 is the nine commit stages; §9.5 is the raster border; §9.6 is
the PREVIEW/MIXDOWN A/B rule; §9.7 is the error surfaces; §4.5 is the preview container and the
independent-transport rule; §4.2/§4.3 are the frames this milestone fills.

**Depends on:** **M1** (foundation) — `RenderHistoryEntry`, `AudioRef`, `forgeApi`'s job routes and
every frame this milestone fills (`MixdownSlot`, `PreviewContainer`, the root `canvas.raster-border`)
are already declared there. **M4** (PROMPT + SIGMA) — the `settings` store and `applyRenderPreset`,
which USE SETTINGS extends. **M5** (timeline) — `arrangement`, the lane drop handlers and the clip
lifecycle. **M7** (chains, mix, sessions) — `chainRequest(...)`, the MIX-tab MIXDOWN buttons, the
`inpaint-overlap-button` frame, and the session serialiser this milestone extends with history.
**M8** (server render routes, WINTERMUTE's) — the payload contract every builder here targets.
**M2** (server queue and fixtures, WINTERMUTE's) — the job lifecycle and the recorded fixtures the
contract tests skip against.

**Blocks:** nothing. M9 is the last frontend milestone in §12's build order
(M1 → M4, M5, M10 → M6, M7 → M9).

---

## Global constraints

**Read these before Task 1. Each one cost a debugging session, or is a defect a writer or critic
found and independently verified while researching this milestone.**

1. **The `$state` proxy rule.** A store method that appends to a `$state` array must return
   `arr[arr.length - 1]`, not the local object it just pushed — the pushed local is not the proxy
   the store now holds, and a caller that keeps it has a dead handle. `HistoryStore.add` returns
   the proxy for exactly this reason, and every caller uses the returned value.
2. **An abort listener added after the signal already fired never runs.** Check `signal.aborted`
   first. The job poller and the preview audio loader can both be superseded before they resolve.
3. **Serialise `$state` with `$state.snapshot`, never `structuredClone`.** `structuredClone` of a
   `$state` proxy throws `DataCloneError` (verified on Svelte 5.57.0). `$state.snapshot` is a rune,
   so any module calling it must be a `.svelte.ts` file.
4. **Nothing may write `$state` while a `$derived` or a template expression is being evaluated**
   (`state_unsafe_mutation`, verified on Svelte 5.57.0). Anything that seeds on first read must be
   called from an event handler, never from a `$derived`.
5. **`getComputedStyle().getPropertyValue("--token")` returns the token stream, not a colour.**
   The raster border builds its own `oklch()` string rather than parsing channels out of a token.
   In jsdom a `<style>` block on `:root` eats the space after `90%`, and an undefined token returns
   `""` — which makes `ctx.fillStyle = ""` a silent no-op that passes a naive test. Seed tokens
   inline in the test.
6. **Never `fillText` a label that a test asserts on.** `findByText` cannot see canvas text. Every
   label this milestone gates a test on is DOM text, not a canvas draw. (This blocked M4.)
7. **`steps_total` can be 0** — a commit with no a2a or inpaint passes, and the `decode` and `bend`
   ops, all report it. Every division by it guards first, and the progress label falls back rather
   than rendering `NaN`.
8. **Code must be correct against the SERVER, not the mock.** M1 T6's mock and M2 T5/T8's real
   routes disagree in four known places: the server trims list rows (no payload, result or
   progress), cancelling a finished job is 200 on the server and 409 in the mock, the 404 text
   differs, and `position` is live on the server but fixed in the mock. Tests that depend on any of
   these live in the recorded-contract file and skip until the fixture is recorded.
9. **Recorded-fixture contract tests follow M7 T10's `it.skipIf` rule**: skip when the fixture is
   missing or empty, never pass against a hand-written mock. In particular
   `handmade-forge_job_running.json` contradicts the Normative progress rule (`"SAMPLE"`,
   `stage_count: 1`) — no test pins to it.
10. **Where the spec and M8 differ, M8 wins**, and the task says so in prose where it happens.

---

## The M8 payload contract — copy it exactly, do not re-derive

These are verified against WINTERMUTE's M8 (`parse_render`, `parse_chain`, `validate_commit`, the
`a2a_clip` and `inpaint` validators) and are the single most common way a render request 400s.

1. **`parse_render` rejects unknown keys** (`_merge` → 400 `unknown render field(s)`), and
   `duration_sec` is **not** in `RENDER_DEFAULTS`. Strip `duration_sec` from every `render` and
   `defaults` object in `a2a_clip`, `inpaint` and `commit`. For `generate` the wire name is
   **`duration`**. `commit` carries a top-level **`duration_sec`** (≤ 184). Schedule keys are
   exactly M3 `parse_spec`'s.
2. **LatCH takes the whole chain object.** `chainRequest(...)` (M7) sends exactly 2 slots with
   nested `hparams`, and `rho`/`mu` as raw 0-30 multipliers mapped server-side. Sending one slot
   400s; pre-multiplying the gains client-side squares them. `parse_chain` validates
   `start_pct <= end_pct` before it checks `latch_on`.
3. **`validate_commit`**: `lanes` must be indexes 0-3 each exactly once; `clips` must be
   **non-empty** (so MIXDOWN is disabled with an honest hint on an empty arrangement); a clip's
   `a2a` is `null | {render, envelope}` (the client stores `{on, noise, envelope}` plus
   `clip.render` — map it); `overlaps` is a **list** of
   `{key, lane, start_sec, end_sec, a_id, b_id, curve, chroma_xfade, render}` with local steps and
   cfg already applied (the client stores a `Record<key, OverlapParams>` plus a derived `Overlap[]`);
   `native_bpm` ratio must be 0.5..2; `detune_cents` ±100; a lane's `chain` is `chainRequest(...)`;
   `master.head` must be a known head when `latch_on`.
4. **`a2a_clip` takes the whole source file** — no offset, dur or stretch. A null `envelope` means
   a flat `noise_level`.
5. **`inpaint`**: `a` and `b` are `{audio, start_sec, offset_sec, dur_sec}`, plus `region`,
   `pad_sec` (default 8), `curve`, `chroma_xfade` and `render`. The result audio spans
   `[region.start − pad, region.end + pad]` (`meta.span_start_sec`) — the preview and any
   REPLACE CLIP must account for the pad rather than assuming the region.
6. **FiLM checkpoints** are `family: "control_adapter"` with `control_mode: "scalar"`. There is no
   `film` family.
7. **Progress**: `stage_index` is 1-based and 0 means not started; only `commit` has the nine §8.1
   stage labels, every other op reports `stage: ""` and `stage_count: 0`; `progress` is present
   only while the job runs.

---

## Names inherited — do not redeclare them

- **Types** (M1): `RenderHistoryEntry` (`{job_id, forge_job_id, file, label, kind, dur_sec,
  source_clip_id, created}`, `created` in epoch seconds), `AudioRef`, `ProjectV2`, `ForgeClip`,
  `OverlapParams`. Import them; do not redeclare any.
- **Result → entry**: `job_id = result.job_id`, `file = result.urls[0].split("/").pop()`, and the
  render AudioRef is `{kind: "render", job_id, file}` — M2 T15 and M8 T11 both build it this way.
- **`forgeApi`** (M1 T5, frozen) already has the job routes this milestone needs. No task here adds
  a method to `forgeApi` itself.
- **`chainRequest(...)`** (M7) — the only supported way to build a LatCH request. Never rebuild the
  §5.5 mapping client-side.
- **`LaneChain.lora.ckpt_path` is the durable identity; `.slot` is a transient resolution** against
  the current `GET /slots` (M7, critic pass 2 #14). This milestone resolves from `ckpt_path` at
  submit time and treats `slot` as a hint at most.
- **`settings` store and `applyRenderPreset`** (M4) — note that `applyRenderPreset` ignores
  `duration`/`duration_sec`, so USE SETTINGS owns LENGTH itself.
- **`arrangement`, the two lane drop handlers, `lifecycle.addClip`, `scheduleStretch`** (M5).
- **`view.selection: Target`, `view.appendLog(…, "error")`, `logStore.lines`** (M1 T7).

### Frames already in place — keep their testids

| frame | owner | testids |
|---|---|---|
| `MixdownSlot` | M1 | `mixdown-button`, `mixdown-canvas` (220×26), `mixdown-play`; `mixdownLabel(busy, stepsLeft)` → `SAMPLING · N steps left`. Props `busy`/`stepsLeft` exist on TopBar but App does not pass them |
| `PreviewContainer` | M1 | `preview-render`, `preview-history`, `preview-wave` (900×30), `preview-play`, `preview-length`, `preview-drag-handle`, `preview-use-settings`, `preview-replace-clip`. Mounted propless in BottomPane |
| root raster border | M1 | `canvas.raster-border`, 300×170, `data-region="raster-border"` |
| master strip A/B toggle | M5 | `master-source-preview`, `master-source-mixdown` — MIXDOWN disabled, always visible |
| MIX-tab MIXDOWN buttons | M7 | no testid, `onMixdown` is a no-op |
| `inpaint-overlap-button` | M7 | a no-op |

**No new drawing.** The MIXDOWN slot, preview container, HISTORY, USE SETTINGS, REPLACE CLIP, the
PREVIEW/MIXDOWN toggle and the error line are all specified by the spec text and the M1/M5 frames.

---

## Two defects this milestone fixes at source

1. **TERMINAL renders `logStore.lines` only.** M6, M7 and M10 write their errors via
   `view.appendLog(…, "error")` into `view.logLines`, which nothing renders — every error those
   milestones report is invisible today. Writer A's Task 5 fixes this in one place, and M9's own
   errors use the fixed path.
2. **`serializeProject` hardcodes `renders: []`, `mixdown: null`, `preview: null`**, and
   `applyProject`/`validateProjectV2` ignore them, so render history never survives a save. This
   milestone serialises it. Note that `workKey` includes `renders`, which means history entries
   count as unsaved work — the task states whether that is wanted and why.

---

## HELP coverage

Almost no M9 control has a `KEYS` id. M1 wrote literal help strings onto the frames (the MIXDOWN
button and waveform; the preview RENDER, HISTORY, drag, USE SETTINGS and REPLACE CLIP) — each is
promoted to a `NEW_STRINGS` id and used as `HELP.x`. `previewMixdownToggle` already exists but M5's
toggle never attached it. M7's MIX-tab MIXDOWN buttons use `HELP.renderButton` ("Runs the current
target") and switch to the MIXDOWN id, so both MIXDOWN surfaces say the same thing.
`strings.test.ts` totals run per task in execution order and are recounted mechanically at assembly.

---

---

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

---

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
  add `setClipOp`), `latent-forge/src/lib/forge/projectSerializer.svelte.ts` (M7 T8 — `isClip`
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
- From `latent-forge/src/lib/forge/projectSerializer.svelte.ts` (**M7 T8**): `isClip(c: unknown):
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

In `latent-forge/src/lib/forge/projectSerializer.svelte.ts` (M7 T8), `isClip` must **tolerate a
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

---

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

---

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

---

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
