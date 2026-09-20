# M4 critic findings — Tasks 4-12

*2026-09-20. 32 findings, 24 blocking, on tasks that three writers had each called done. Kept in full
because the fixes are being applied in stages and a half-applied list is worse than none.*

**Status key:** `[x]` applied · `[ ]` outstanding · `[W]` escalated to WINTERMUTE.

## The one that is not M4's to fix

**F2, F3, F4 together say M1's `forgeApi.schedule` cannot do what M4 needs.** M1 T5 (approved,
frozen) declares:

```ts
schedule: (body: { steps: number; sigma_max?: number; sampler_type?: string | null; schedule: ScheduleSpec }) =>
  sendJSON<{ ok: true; sigmas: number[]; shape: string; warnings: string[] }>("/schedule", "POST", body),
```

Three separate problems: no `duration` in the body (so the model shape's length-dependent dist shift
silently charts the server's 47 s default); no `AbortSignal` parameter (so T4's whole
abort-and-supersede mechanism has nothing to abort, and `forgeApi.schedule(req, signal)` is TS2554);
and a return type that both *claims* fields today's route does not send (`shape`, `warnings`) and
*omits* five it does (`steps`, `duration`, `sigma_max`, `dist_shift`, `latent_len`).

**Decision (FLATLINE, mine to make): M4 does NOT go through `forgeApi.schedule`.** T4's
`scheduleClient.svelte.ts` calls `/schedule` itself. The justification is in the spec, not in
convenience: §6 freezes only `/forge/*`, lists `/schedule` among the pre-existing routes the client
"calls directly", and says to keep them "in their own client module so the frozen and unfrozen
surfaces stay distinguishable". M1's `forgeApi.schedule` was written from §5.3's sketch rather than
from `explorer_render_server.py`, and correcting it would be an edit to an approved plan for no gain.

**[W] For WINTERMUTE:** `forgeApi.schedule` is then dead and wrong in an approved plan. It should
either be deleted from M1 T5 or corrected to the real route's shape. Not urgent — nothing calls it —
but it will mislead whoever reads M1 next.

## Blocking

- [ ] **F1** T4 `ScheduleClient.dispose()` — nulls `#controller` before `#run`'s `finally`, so the
  `this.#controller === controller` guard fails and `pending` never clears; the task's own test
  asserts `false`. → set `this.pending = false` in `dispose()`.
- [x] **F2** T4 `forgeApi.schedule(req, signal)` — M1's client takes one parameter. → own the call.
- [x] **F3** T4 `ScheduleResult` not assignable from M1's declared return. → own the call.
- [x] **F4** T4/T10 `duration` absent from M1's request body type. → own the call.
- [ ] **F5** T4 `get staleShape` — true only when `shape !== "model"`, but ρ/STEPPED/PLATEAUS/TILT
  changed at shape `model` are equally uncharted and get no note. → compare the whole `ScheduleSpec`
  against `SCHEDULE_DEFAULT`.
- [ ] **F6** T7 `SigmaGraph.svelte` emits `data-testid="sigma-graph"` but T10 and T12 both assert
  `canvas[data-canvas="sigma"]`. → add the attribute.
- [ ] **F7** T7 ships two mutually exclusive colour implementations — literal `"var(--x)"` (what its
  13 tests assert) and a `token()`/`getComputedStyle` rewrite (what Global Constraints require). In
  jsdom `getComputedStyle(canvas).getPropertyValue("--panel2")` is `""`. → keep `token()`, set the
  custom properties inline on the fixture canvas, assert resolved values.
- [ ] **F8** T7 — not one of its 13 tests asserts a coordinate, so a component that strokes an empty
  path or swaps σ for progress passes. → assert first/last `lineTo` and the CFG band's `fillRect`
  against `sigmaGraphGeometry`'s own output.
- [ ] **F9** T9 numeric fields use a sibling `<span class="label">`, so T12's three
  `page.getByLabel("CFG")` assertions match nothing. → add `aria-label`, as T11 already does.
- [ ] **F10** T10 emits `data-col="sigma"` on both `SigmaColumn`'s root and `PromptSigmaTab`'s
  wrapper; T12 asserts one and Playwright strict mode fails on two. → drop it from `SigmaColumn`.
- [ ] **F11** T10 "shows the client's error as the graph's note" — `SigmaGraph` paints `error` with
  `fillText`, never into the DOM, so `findByText` cannot match; the test also polls real timers under
  `vi.useFakeTimers()`. → render the note as a DOM sibling of the canvas.
- [ ] **F12** T10 same test expects `"render server unreachable"`, but `#run`'s catch does
  `String(e)` → `"Error: render server unreachable"`. → `e instanceof Error ? e.message : String(e)`.
- [ ] **F13** T11 `HELP.shape`, `HELP.sigmaRho`, `HELP.cfgRescale` are not in M1 T14's frozen table;
  the real ids are `scheduleShape`, `scheduleRho`, `rescale`. → rename.
- [ ] **F14** T11 passes `EMPTY_SIGMAS` to `formatCfgBound`, so the STEPS unit renders `"0"` forever
  and the UNIT toggle is a dead control — §5.3 requires it computed from the returned array. → share
  the `ScheduleClient` result, or move the CFG interval fields into the SIGMA column that owns it.
- [ ] **F15** T11 in the STEPS unit shows a step index but writes `Number(value)` straight into
  `cfg_interval_progress`, so typing `3` stores progress 3.0; the drag range also stays
  `RANGES.cfg_interval` when §5.1 gives the steps unit `0–steps, int`. → convert on input, swap the
  range with the unit.
- [ ] **F16** T12 "applies a complete, valid preset" — the fixture's `seed` is M1's `-1`
  server-resolve sentinel, which fails `RANGES.seed {min: 0}`, so a round-trip of the app's own
  defaults is rejected. → exempt `-1` in `numberOk` for `seed`, and say why.
- [ ] **F17** T12 `forgeApi.preset(level, name)` returns the payload itself (§6.3), not
  `{ok, preset}`; `res.preset` is `undefined` and every recall silently applies nothing. → pass `res`.
- [ ] **F18** T12 `HELP.settingsPreset` does not exist; T8 uses `promptPreset` for this control.
- [ ] **F19** T12 `settingsPresetSelect.test.ts` lacks the `// @vitest-environment jsdom` pragma every
  sibling suite declares.
- [ ] **F20** T12 replaces T8's placeholder select, breaking T8's green test
  `renders the SETTINGS PRESET slot disabled with one dash option`, and never amends it.
- [ ] **F21** T12 Playwright `getByRole("tab", …)`. CONFIRMED against M1:5554, which produces
  `[data-testid="bottom-tab-chroma" | "-prompt" | "-mix" | "-terminal"]` and no `role="tab"`. M1 T11 renders `<button class="tab"
  data-testid="bottom-tab-prompt">` with no `role="tab"`.
- [ ] **F22** T12 Playwright `[data-module-toggle=advanced-sampling]`. **The critic has this
  backwards, and in doing so found an M1 bug instead.** Verified: M1 T7's view store declares
  `type ModuleId = "overlap" | "files" | "lane-chain" | "advanced-sampling" | "master-chain"`
  (kebab, M1:3027, with `MODULE_IDS` matching at 3056), while **M1 T12 independently declares its own
  `ModuleId` as `["overlapInpaint", "files", "laneChain", "advancedSampling", "masterChain"]`
  (camel, M1:6259)** and `ModuleShell` renders `data-module-toggle={id}` from *that* list. So M1
  contradicts itself about its own module ids, in an approved plan, and no M4 task can be correct
  against both. → M4 ships the **kebab** spelling (the view store's, which is what persists into the
  project JSON's `ui.modules` at M1:3231) and the Normative-names block records it. **[W]** M1 needs
  one of its two `ModuleId` declarations deleted.
- [ ] **F23** T8 states `Tests 22 passed (22)`; actual 21.
- [ ] **F24** T12 states `Tests 26 passed (26)`; actual 27.

## Minor

- [ ] **F25** T8 `opDisabledReason` invents a latent gate; §7.1 disables RENDER with
  `turn A2A on or choose an op`, and §7.3 says staleness "is informational (badge) and no longer
  blocks anything". → drop it or make it a question for W.
- [ ] **F26** T10 comment claims the server would 400 on `sigma_max` out of range; the route does no
  range check at all. → restate as a client-side chartability rule.
- [ ] **F27** T4 `abortRejection`'s listener is never removed on success — one leak per request.
- [ ] **F28** T9/T11 `await Promise.resolve()` before asserting the DOM; Svelte 5 flushes on its own
  schedule. → `await tick()`.
- [ ] **F29** T9 "highlights BASE as active by default" — `beforeEach` sets the stage explicitly, so
  the test proves nothing about the default; and `not.toHaveProperty("length")` is vacuous.
- [ ] **F30** T10 `sigmaNote(null, true, spec(), "euler")` is unreachable: `spec()` is shape `model`,
  where `staleShape` cannot be true.
- [ ] **F31** T12's four component tests share the `settings` singleton with no reset, so test 3's
  "before" value is test 2's leftover.
- [ ] **F32** Open question "HELP.sigmaGraph may not exist" is answerable — it does exist in M1's
  table. → close it; the real HELP defect is F13.

## What the seam check found

The thing most likely to be broken turned out mostly sound: `ScheduleClient`, `ScheduleRequest`,
`ScheduleResult` and `scheduleKey` are identical in T4 and T10 (both `.svelte.ts` — only the File
Structure table disagrees); `SigmaGraphInput`, `SigmaGraphGeometry`, `sigmaGraphGeometry`, `CfgUnit`,
`formatCfgBound`, `stepAtProgress`, `progressAt` and `cfgBandFraction` agree across T5/T6/T7/T10/T11;
and `SigmaGraph.svelte`'s props `{input, note, pending, error}` match T7 ↔ T10 exactly.

The breaks are all at the **DOM contract**, not the type contract: `data-canvas=sigma` asserted but
never emitted (F6), `data-col=sigma` emitted twice (F10), `advanced-sampling` vs `advancedSampling`
(F22), missing `aria-label`s (F9), four wrong `HELP` ids (F13, F18) and a missing `role="tab"` (F21).
Writing components and the spec that asserts against them in separate agents is what produced that,
and a shared `data-*` contract in the Normative-names block would have prevented every one.
