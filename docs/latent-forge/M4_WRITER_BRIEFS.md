# M4 — the two writer briefs, ready to dispatch

*Written 2026-09-18 at the 5-hour budget line, before the writers could run. Tasks 1–3 of
`docs/superpowers/plans/2026-09-18-latent-forge-m4-prompt-sigma.md` are written, critic-reviewed and
committed. Tasks 4–11 are not. These are the two briefs, already built against the spec, the drawing
and M1 — dispatch them verbatim as two parallel **Sonnet** agents and then assemble.*

**Both briefs share this preamble.** Repo root `C:\Users\kim.ake\OneDrive - Bluefors\Documents\py\avp-audio-craft`,
Windows, Bash available. No M365 tools. Do not edit any existing file. Read first:
the M4 plan (header, Global Constraints, Normative names, File Structure, Tasks 1–3 **in full** — match
their voice and format); the spec `docs/superpowers/specs/2026-09-15-latent-forge-design.md`; the drawing
`docs/sa3-studio/design_handoff/SA3 Studio v3.dc.html`.

**Format, normative for both:** `### Task N: <title>`, a short WHY paragraph, then `**Files:**`
(Create/Modify, full paths), `**Interfaces:**` (`- Consumes:` / `- Produces:`, exact names and types —
an implementing agent sees ONE task at a time and can look nothing up, so restate every consumed name
every time), then checkbox steps: failing test with FULL code → run command + expected failure →
implementation with FULL code → run command + expected pass **with a true `it()` count** (a wrong count
is a blocking defect) → commit as `Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M4 T<N>: ..."`.
No placeholders, no "...", no "similar to above". TS strict. Node 26.8.1 / npm 12.0.2, Svelte 5 runes
(`$state`/`$derived`/`$props`/snippets — never `export let`), vitest 2, `@testing-library/svelte` for
components. Test command `cd latent-forge && npx vitest run <paths>`; type gate `npm run check`
expecting `svelte-check found 0 errors and 0 warnings`. No border radius, no shadows. Every interactive
element carries `data-help={HELP.<id>}`.

**Open-questions rule, both:** where spec and drawing disagree, ship the spec's reading and end the file
with `## Open questions (Tasks N-M)`, each as `- **<subject>** — <what disagrees> — <what you shipped>`.

## Names both writers inherit

**From M1 (frozen):** `RenderSettings { prompt; negative_prompt; steps; cfg_scale; seed; apg_scale;
cfg_interval_progress: [number, number]; schedule: ScheduleSpec; scale_phi; sampler_type: string | null }`;
`ScheduleSpec { shape: "model"|"logsnr"|"geometric"|"linear"|"log"|"exponential"|"cosine"; rho; sigma_min;
lam_min; lam_max; stepped: boolean; plateaus: number; tilt }`; `LatchSlot { head: string; kind: string;
value: number; weight: number; start_pct: number; end_pct: number }`; `Target = {kind:"none"} |
{kind:"clip"; id: string} | {kind:"overlap"; key: string}` with `targetKey(t)` → `"session"` /
`"clip:<id>"` / `"overlap:<key>"`; `LENGTH_CAP_SEC = 184`; `SCHEDULE_DEFAULT`, `BASE_DEFAULTS`,
`POST_DEFAULTS`, `cloneRenderSettings` from `src/lib/forge/defaults`; `forgeApi` (`schedule`, `setBackbone`,
`backbone`, `presets`, `preset`, `savePreset`, `deletePreset`) and `ForgeApiError { status, message }`
from `src/lib/forge/api`; `view.selection`, `view.activeLane`, `view.bottomTab`, `view.helpOn` from
`src/lib/stores/view.svelte`; `use:dragScale={{min, max, int, value, onValue}}` from
`src/lib/actions/dragScale`; `ModuleShell` props `{id, title, lit, children}`; `HELP: Record<HelpId, string>`.

**From M4 Tasks 1–3 (written):** `settings` singleton from `src/lib/stores/settings.svelte` —
`defaults`, `stage: "POST"|"BASE"`, `objective`, `backboneId`, `cfgDisabled`, `current(t)`, `editable(t)`,
`patch(t, p)`, `patchSchedule(t, p)`, `resetSampling(t)`, `setStage(s)`, `effectiveCfg(t)`, `scope(t)`,
`attach(src)`; `resolveSampler(objective, requested, latch): {value, label, options, disabled, forced}`,
`activeSlots(l)`, `isLatchActive(l)`, `LatchState { latch_on: boolean; slots: readonly LatchSlot[] }` from
`src/lib/sampling/samplers`; `validateSchedule(spec, sigmaMax, samplerType: string|null): ScheduleIssue[]`,
`flatPlateauNote(spec, samplerType)`, `RANGES` (keys `rho, sigma_min, sigma_max, lam_min, lam_max, plateaus,
tilt, steps, cfg_scale, scale_phi, length_sec, seed, cfg_interval, noise, detune_cents`, each
`{min, max, int?}`), `SCHEDULE_SHAPES`, `FLAT_PLATEAU_NOTE`, `POST_CFG_NOTE` from
`src/lib/sampling/scheduleRules`; `sigmaMaxFor(a2a): number` (**unclamped**), `chartableSigmaMax(sigmaMax):
number | null`, `SIGMA_MAX_FIXED = 1.0` from `src/lib/sampling/sigmaMax`.

---

## Writer A — Tasks 4–7: the `/schedule` client and the sigma graph

Also read: spec §5.3 in full, §4.5, §5.1, §10 X5/X6; `eval/explorer_render_server.py:1009-1062` (the real
route); the drawing lines 1309–1430 (`_sigmaAt`, `_progressAt`, `_stepAtProgress`, `_drawSigma`) and
560–600 (UNIT button, RESCALE field). **You are porting the DRAWING of `_drawSigma`, not its maths** —
§5.3 says the canvas never computes σ, so `_sigmaAt` becomes an array lookup into what `/schedule` returned.

**Task 4 — `src/lib/sampling/scheduleClient.ts`.** Debounced 150 ms, abortable, cached `POST /schedule`.
Produces `SCHEDULE_DEBOUNCE_MS = 150`; `ScheduleRequest { steps: number; duration: number; sigma_max: number;
sampler_type: string | null; schedule: ScheduleSpec }`; `ScheduleResult { sigmas: number[]; steps: number;
duration: number; sigma_max: number; dist_shift: string | number; latent_len: number; shape?: string;
warnings?: string[] }`; `scheduleKey(req): string`; `isNonIncreasing(sigmas): boolean`; `class ScheduleClient`
with `$state` fields `result | null`, `pending`, `error | null` and methods `request(req)`, `flush(): Promise<void>`
(test seam), `dispose()`. Restate in the task: `duration` is REQUIRED (the model shape's dist shift is
length-dependent, `latent_len = ceil(duration·SR/DS)`); `shape` and `warnings` are OPTIONAL because today's
server returns neither (M3 adds them); today's server IGNORES `schedule` and `sampler_type` entirely, so expose
a derived `staleShape: boolean` — true when the request's `schedule.shape !== "model"` and the response echoed
no `shape`. Abort a superseded request with `AbortController`, and **check `signal.aborted` before registering
an abort listener** — one added after the signal fired never runs and the promise never settles (found and
fixed in M1). Cache by `scheduleKey`. A response whose sigmas are not non-increasing sets `error`; §5.3 requires
it and this is the only place the client has the array. Pick `.ts` or `.svelte.ts` by whether you use runes and
be consistent across all four tasks.

**Task 5 — `src/lib/sampling/cfgInterval.ts`, pure.** §5.3: progress `= 1 − σ/σ₀`, stored always as progress;
the step unit is display-only. Produces `type CfgUnit = "progress" | "steps"`; `progressAt(sigmas, i)`;
`stepAtProgress(sigmas, p)` (first index whose progress ≥ p — the drawing's `_stepAtProgress`, lines 1347–1351);
`progressAtStep(sigmas, step)`; `formatCfgBound(sigmas, p, unit): string`; `cfgBandFraction(sigmas, lo, hi):
{lo, hi}` (the 0..1 x-fractions the graph fills). Cover: empty and 1-element arrays (the pane renders before the
first response — no NaN, no divide by zero); `σ₀ = 0` (an A2A clip at NOISE 0: define progress as 0 and say why);
p outside [0,1]; and that a stored progress is never converted into a stored step.

**Task 6 — `src/lib/sampling/sigmaGraph.ts`, pure geometry** so the canvas only strokes and vitest can assert
layout without a canvas. Produces `LANE_H = 7`, `LANE_GAP = 2`, `PAD = 4`, `MAX_TICKS = 200`,
`reservedHeight(nSlots)` (the drawing's `RESERVED = 2·LANE_H + LANE_GAP + 2` — it reserves for TWO lanes
unconditionally); `SigmaGraphInput { sigmas: number[]; steps: number; cfgLo: number; cfgHi: number;
stepped: boolean; scalePhi: number; slots: readonly LatchSlot[]; width: number; height: number }`;
`SlotBand { index: 0|1; x0: number; w: number; laneY: number; hatch: {x0, w} | null }`;
`SigmaGraphGeometry { plotHeight; cfgBand: {x0, x1}; sigmaPath: {x,y}[]; progressPath: {x,y}[];
ticks: {x,y}[]; rescaleY: number | null; slotBands: SlotBand[]; stepLabel: string }`;
`sigmaGraphGeometry(input): SigmaGraphGeometry`. σ curve `y = plotHeight − PAD − (σ_i/σ_0)·(plotHeight − 2·PAD)`,
sampled per pixel column by INDEXING the array (nearest index for `u = x/width`), never by a formula.
Stair-step when `stepped`. One tick per step capped at `MAX_TICKS`. `rescaleY` null when `scale_phi <= 0`.
A slot's hatch is its window ∩ the CFG band. Empty `sigmas` → empty paths, no crash.

**Task 7 — `src/ui/prompt/SigmaGraph.svelte`.** Props `{ input: SigmaGraphInput | null; note: string | null;
pending: boolean; error: string | null }`. Colours resolve through `getComputedStyle(canvas).getPropertyValue("--token")`
once per frame; opacity via `ctx.globalAlpha`, **never** string surgery on the token (restate the Global
Constraints' reason). Tokens: `--panel2` ground, `--turq-strong` CFG band and edges, `--slot1`/`--slot2` lanes,
`--warm` the dotted rescale line, `--text-dim` labels, `--text` the σ curve. Labels `sigma + progress` left and
the step count right, as the drawing does. Handle devicePixelRatio. Render `note` and the error state. Test in
jsdom by stubbing `HTMLCanvasElement.prototype.getContext` with a recording fake and asserting the call
sequence — that is how the geometry is proved to reach the canvas without a real one.

Output to `scratchpad/m4_part_a.md`, starting directly with `### Task 4:` — no preamble, no front matter.
Reply one line: `A: tasks=4-7 lines=<n> its=T4:<n>,T5:<n>,T6:<n>,T7:<n> openq=<n>`.

---

## Writer B — Tasks 8–11: the PROMPT + SIGMA tab and ADVANCED SAMPLING

Also read: spec §4.5 in full, §4.6 item 4, §5.1, §5.3, §7.1, §7.2, §9.3, §9.4, §10 (X4, X7, X11, X14, X15);
the drawing's template markup lines 353–409 (the three columns you are building) and 560–600 (UNIT, RESCALE);
M1 plan Tasks 11 and 12 ONLY (the bottom-tab frame and the module accordion you fill in — M1 is frozen, extend it).

**Consume from Writer A, never redefine:** `SigmaGraph.svelte` and its props; `SigmaGraphInput`;
`ScheduleClient` (`result`, `pending`, `error`, `staleShape`, `request(req)`); `ScheduleRequest`;
`ScheduleResult`; `type CfgUnit`, `formatCfgBound(sigmas, p, unit)`, `stepAtProgress(sigmas, p)`.

**Task 8 — `src/ui/prompt/TargetBar.svelte`** (§4.5 item 1, first row) plus `src/ui/prompt/targetBar.ts` with
the pure parts: `type TargetTag = "GENERATE" | "CLIP" | "A2A" | "INPAINT"`; `targetTag(t, a2aOn)`;
`targetTagColorVar(tag, lane)` (GENERATE `--turq-strong`, CLIP the lane colour `--lane<n>`, A2A and INPAINT
`--purple-strong`); `CLIP_OPS: readonly ["generate", "decode", "longform", "bend"]`;
`opDisabledReason(op, clipHasLatent): string | null`. The component renders the tag, the target name, a
SETTINGS PRESET select **slot** (disabled, label `SETTINGS PRESET`, a single `—` option; say that Task 12 fills
it), and for a clip target: the A2A toggle, NOISE via `use:dragScale` over `RANGES.noise`, and the OP select
(§10 X11). **M4 must not depend on M5's arrangement store**, so clip-shaped data arrives as props:
`{ target: Target; clipName: string | null; lane: 0|1|2|3; a2a: {on: boolean; noise: number} | null;
clipHasLatent: boolean; onA2AToggle: (on: boolean) => void; onNoise: (v: number) => void; op: string | null;
onOp: (op: string) => void }`. State that plainly: M5 wires the props, M4 owns the bar.

**Task 9 — `src/ui/prompt/PromptColumn.svelte` and `src/ui/prompt/ModelStageColumn.svelte`** (§4.5 items 1–2),
plus `src/ui/prompt/modelStage.ts` with `randomSeed(rand?: () => number): number` and
`stageConfirmMessage(next: "POST" | "BASE"): string`. PromptColumn: the flex prompt textarea and the 34 px
negative prompt, writing through `settings.patch(target, {...})`. ModelStageColumn: MODEL STAGE POST/BASE,
STEPS, CFG, the cfg note, the flat-plateau warning, LENGTH s, SEED + RND. Not optional, must be in the task text:
the stage is session-level (§10 X4) and toggling shows the inline confirm `rebuilds the model — continue?`, then
calls `forgeApi.setBackbone({ id: settings.backboneId })` **for the new stage** and calls `settings.setStage`
**only on success** — a failed rebuild must leave the store on the stage actually loaded; in POST the CFG field is
`disabled` and shows `POST_CFG_NOTE` while the stored value is untouched; LENGTH is capped at `LENGTH_CAP_SEC`
(§10 X12) and is what the `/schedule` request's `duration` carries; SEED uses `RANGES.seed` and RND writes a fresh
in-range integer; every numeric field uses `use:dragScale` with its matching `RANGES` entry.

**Task 10 — `src/ui/prompt/SigmaColumn.svelte` and `src/ui/prompt/PromptSigmaTab.svelte`** (§4.5 item 3 and the
tab assembly). SigmaColumn: the SIGMA label, the graph label, the LatCH slot legend (two swatches in
`--slot1`/`--slot2` with the slot's head name or `—`), and `<SigmaGraph>`. It owns the `ScheduleClient` and builds
the `ScheduleRequest` from `settings.current(view.selection)` plus the LENGTH the ModelStageColumn holds —
**`duration` is required**; omitting it silently charts the server's 47 s default. `note` is the first of: the
client's `error`; `staleShape ? "schedule shape is charted from M3 onward" : null`; `flatPlateauNote(...)`.
PromptSigmaTab lays the three columns out at 162 px above M1's 44 px preview-container slot inside M1's 248 px
bottom pane and registers as the `prompt` tab body. It passes clip-shaped data through to TargetBar; it does not
reach into a store M4 does not own.

**Task 11 — `src/ui/modules/AdvancedSampling.svelte`** (§4.6 item 4, §5.3), plus
`src/ui/modules/advancedSampling.ts` with `shapeUsesLambda(shape): boolean` and
`fieldIssue(issues, field): {severity, message} | null`. Fill M1's module frame: SAMPLER select (from
`resolveSampler`, disabled and relabelled when LatCH forces Euler), SHAPE select (`SCHEDULE_SHAPES`), ρ, σ MIN,
**σ MAX read-only** (normative: it is the pass's init noise level — `1.00` for a generate, the clip's NOISE on an
A2A target, edited in the target bar, not here), λ MIN / λ MAX (meaningful only for `logsnr` — grey them otherwise
and say so), STEPPED + PLATEAUS + TILT, CFG INTERVAL LO/HI with the UNIT toggle (`formatCfgBound`), CFG RESCALE
(`scale_phi`). Every field via `use:dragScale` over its `RANGES` entry, writing through `settings.patchSchedule`
(schedule fields) or `settings.patch` (the rest). `validateSchedule` errors and warnings render inline under the
offending field.

Output to `scratchpad/m4_part_b.md`, starting directly with `### Task 8:` — no preamble, no front matter.
Reply one line: `B: tasks=8-11 lines=<n> its=T8:<n>,T9:<n>,T10:<n>,T11:<n> openq=<n>`.

---

## After both return

1. Concatenate: plan (as committed) + `m4_part_a.md` tasks + `m4_part_b.md` tasks, splitting each part's
   `## Open questions` off the end and merging them into one section at the bottom.
2. Write **Task 12** myself: the `prompt` and `render` preset levels (`src/lib/presets/renderPresets.ts`,
   §9.3 — `prompt` presets appear in the same SETTINGS PRESET select under a `prompt only` group, §4.5),
   the Playwright spec `tests/sampling.spec.ts`, and the self-review table against §4.5, §4.6.4, §5.3, §7.2, §9.3.
3. Extend the Normative-names block with anything the two parts spelled differently — that block exists
   precisely because parallel writers cannot see each other, and it is what stopped M5's drift.
4. Run a critic over Tasks 4–11 before calling it done. On M5 the critic returned 32 findings, 11 blocking,
   on work I had already called finished; on M4's Tasks 1–3 it returned 17, 8 blocking. **It has never once
   come back empty.** Budget for it as part of the milestone, not as an optional extra.
