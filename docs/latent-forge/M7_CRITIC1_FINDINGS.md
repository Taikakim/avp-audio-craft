# M7 critic pass 1 — findings (2026-09-24), 31 findings, 12 blocking, 2 unconfirmed

Target: `docs/superpowers/plans/2026-09-23-latent-forge-m7-chains-mix-sessions.md`. "plan:N" = line in that file at the time of the pass. "Verified on Svelte 5.57.0" = the critic compiled a small module in memory against `sa3-studio/node_modules/svelte` and ran it.

## BLOCKING

1. **`strings.test.ts` `toHaveLength(87)` is never updated; final count never stated** — plan:148, 2462-2465, 3922-3923, 4222-4228 (T2, T4, T5, T6, T9). Every task defers to "FLATLINE at assembly"; no step edits `strings.test.ts` (M1:7501) — M1's full suite is red from T2's first `NEW_STRINGS` entry. Writer B's OQ1 claim "independently green" is false for the whole suite. Stated "wrote N strings" outputs are cumulative for one writer only; in execution order should be T2 97, T4 101, T5 104, T6 106, T9 107 (T6 says 89). FIX: step in T9 (last string-adding task) setting `toHaveLength(107)` + retitle; correct every task's "wrote N" line for execution order.

2. **jest-dom matchers never registered** — plan:773, 837, 1628, 1826, 1872 (T2, T4, T5). M1 installs `@testing-library/jest-dom` (M1:261) but `vitest.config.ts` has no `setupFiles` (M1:264-282). `toHaveValue`/`toHaveClass`/`toHaveAttribute` fail "Invalid Chai property". FIX: add `setupFiles: ["@testing-library/jest-dom/vitest"]` (T2's Files list), or assert on DOM properties.

3. **`structuredClone` on `$state` proxies throws `DataCloneError` (verified Svelte 5.57.0)** — plan:3817-3821, 3872-3880 (T9 `serializeProject`/`buildMasterPresetPayload`). `arrangement.lanes/.clips/.mix/.master`, `overlapParams()`, `settings.defaults.schedule` are proxies. All 5 projectSerializer tests fail; every real save throws. M5 uses `structuredClone($state.snapshot(c))` (M5:430). FIX: `$state.snapshot(...)` (rename to `projectSerializer.svelte.ts`) or JSON round-trip.

4. **Lazy seeding inside `$derived` throws `state_unsafe_mutation` (verified Svelte 5.57.0)** — plan:2794 (T7 `params = $derived(arrangement.overlapParams(key))`), same expression plan:126 and 2571. `overlapParams` writes `overlapStore[key]` on first read (M5:552-560); a fresh overlap is unseeded → all 7 OverlapInpaint tests throw, and RightPaneModules' snapshot throws in-app on first overlap selection. FIX: non-seeding reader (`overlapStore[key] ?? OVERLAP_DEFAULT`), or seed in the selection handler.

5. **`arrangement.setPxPerSec` does not exist** — plan:3836 (T9 `applyProject`). M5 store has only `zoomBy`/`setScrollSec` (M5:593-599); M5 T1 removes `setPxPerSec` from the view store (M5:606). Round-trip test throws TypeError. FIX: assign `arrangement.pxPerSec` directly, clamped to `MIN_PX_PER_SEC..MAX_PX_PER_SEC`.

6. **`AdapterEntry` imported from a file that doesn't export it** — plan:972, 620-622, 93 (T2). Declared in `src/ui/topbar/modelOptions.ts` (M1:5050); `models.ts` only `import type`s it (M1:5099), never re-exports. T2's `npm run check` "0 errors" gate (plan:1167) fails. FIX: import from `../../ui/topbar/modelOptions`, or add `export type { AdapterEntry }` to `models.ts`.

7. **Quad-weight HELP test reads the wrong element** — plan:2038-2041, 1891 (T5). `aria-label` on the `<label>`, so `findAllByLabelText(/quad weight/i)` returns the `<label>`s; `data-help` is on the inner `<input>` → `getAttribute("data-help")` is null. FIX: move `aria-label` onto the `<input>`.

8. **`chains.spec.ts` test 4 closes the module it is about to use** — plan:1934 (T5). `lane-chain` is open by default (`openModules = ["files","lane-chain"]`, M1:3148); ModuleShell renders body under `{#if open}` (M1:4069); the unconditional toggle click closes it, so `latch-toggle` never appears. FIX: same `isVisible()` guard as test 1.

9. **T10 test 2 can never see `unsaved`** — plan:4123 (T10) vs T9. M1's `loadTopBar` does `if (!session && sessions.length > 0) session = sessions[0].name` (M1:5502); mock lists three sessions (M1:2489-2493) → `session` never empty. T9 doesn't change this despite §9.2 "shows `unsaved` until named". FIX: T9 drops the auto-select (also required by #12).

10. **T10's expected Playwright results wrong both ways** — plan:4165-4176, 4112-4120. "16 passed — M1 T15's 11 plus this task's 5" impossible: Global Constraint #5 itself says M1's "each bottom tab opens" is broken, and #9 fails test 2. Step 2's "4 failed, 1 passed" also wrong: test 1 already passes pre-T9 (mock `session_get` 404s because its sessions Map starts empty, M1:2171, 2224; four `lane-canvas` always exist). FIX: correct both gates; seed a session via PUT in `beforeEach` so test 1 actually loads something.

11. **Unmocked `forgeApi.info()` → unhandled rejections** — plan:716-727, 991 (T2). Component calls `forgeApi.info()` directly; `beforeEach` never mocks it (only the FILM test does). In jsdom Node's `fetch("/info")` rejects on a relative URL; `.then` has no `.catch`. Vitest fails the run on unhandled errors even if all 19 pass. FIX: spy `forgeApi.info` in `beforeEach`; `.catch` every fetch in the effect.

12. **Autosave misses real edits AND overwrites an unloaded session at launch** — plan:4034-4046 (T9, App.svelte). The effect reads `arrangement.lanes/.mix/.master` and `settings.defaults` only as references plus `clips.length`; every M7 control mutates in place (GC #1), so chain/mix/master/clip-move/prompt edits never trigger a save. Worse: effect fires at mount; with `session` auto-set to the first listed name (#9), the blank arrangement is PUT over that saved session 2 s after launch — DATA LOSS. FIX: track `JSON.stringify($state.snapshot(...))` of the serialised shape; skip saving until a session has actually been loaded or named.

## NON-BLOCKING

13. **`previewAudio` gets serialised; converter omits a required field** — plan:3818, 3314-3331, 3188. `structuredClone(arrangement.clips)` carries M5 T10's in-memory-only `previewAudio` (M5:5178), violating §9.2 (spec:862-865) and W's ruling (M5:6003-6008). `convertProjectV1` omits required `previewAudio: AudioRef | null` (type error); T8's test asserting absence contradicts the type, as does T7's `clip()` helper. FIX: strip on serialise; emit `previewAudio: null` in converter and `applyProject`; test checks persisted JSON.
14. **Normative table MASTER CHAIN row names wrong ids** — plan:143 vs 1577: lists `masterLatchHead` (T4 never adds); omits `masterLatchHeadLabel` and `masterHead` (T4 adds).
15. **`masterPresetSave` added but never used** — plan:3916 vs 3950. MASTER PRESET SAVE markup has no `data-help`; new `session-save` button has none either.
16. **RightPaneModules snapshot edit belongs to no task** — plan:121-134. "FLATLINE makes this" is not a step; `sampling: /* unchanged from M4 */` isn't code; lane-chain/master/overlap lit dots stay dark. FIX: numbered step (e.g. in T9) with full code, using #4's non-seeding reader.
17. **v1→v2 converter unreachable for real v1 files** — plan:3929-3933, 3979. T9 deletes the only file LOAD path (which read the v1 JSON M1 T15's SAVE downloads). Server sessions are always v2, so `convertProjectV1` only runs on a server session with `version != 2`, which nothing creates. §9.2: "Version 1 files … load through a converter".
18. **Backbone saved but never restored** — plan:3823, 3832-3848. `backboneId` is a getter over `settings.stage` (M4:427); `applyProject` never sets `stage`. Merged OQ7 (plan:4342-4347, from Writer B item 8) wrongly says a session load/save "moves `settings` correctly" — wrong for backbone.
19. **Module presets recall-only; no save/delete** — plan:614-619, 1012-1020. T2 claims to consume `savePreset`/`deletePreset`, nothing calls them — §9.3 module level can never be populated. Recall targets inconsistent: latch payload includes `latch_on` and is assigned into `chain`; film payload assigned into `chain.film`, which has no `film_on`.
20. **M4→M7 handoff dropped** — M4:4076, 4741, 6155. M4 says M7 passes the active lane's LatCH slots to `SigmaColumn`'s `slots` prop and `AdvancedSampling`'s `latch` prop. No M7 task wires either.
21. **LatCH TARGET slider isn't §5.5** — plan:1051-1055: no `step` (default 1 → `chroma_other`'s [0,1] allows only 0 or 1); `value_default` never applied as start value on head change; `beat_grid`'s 60–200 BPM range not implemented.
22. **Unknown head sent instead of dropped** — plan:395-403, 527. Sent with `gain = 0` → `rho = mu = 0`; real `resolve_latch` raises `unknown latch head` for unknown names (`eval/explorer_render_server.py:602-604`); the test locks this in. FIX: unknown head = inactive = omitted.
23. **Spec spells the idle note two ways** — plan:160, 1493. §5.5 `chain idle — no A2A clip in lane` (spec:476); §8.1 S4 `chain idle — no A2A clip` (spec:797-798). Plan calls its string "the one the spec pins verbatim" without noting the conflict.
24. **LORA/DORA model select misreports state, ignores resident slots** — plan:996, 1127-1130. No "none" option → null `ckpt_path` displays as the first adapter; picking a resident slot never sets `lora.slot` (declared in M1).
25. **Tests that prove nothing** — plan:769-774 (FILM fallback test passes without the fallback; `ckpt` null by default), 4112-4120 (T10 test 1 passes whether or not a session loads, #10), 4150-4156 (T10 test 2 titled "autosave fires" but asserts no autosave).
26. **T10 Known Incomplete #1 wrong premise** — plan:4202-4208. M5's `tests/timeline.spec.ts` already has a `dropClip` helper creating overlaps against dev:mock (M5:5780-5790, 5850-5858) — positive OVERLAP-INPAINT case IS testable in Playwright.
27. **`moveClip` called with three args** — plan:3671; M5 signature `(id, startSec)` (M5:439). Type error.
28. **GC #5's diagnosis slightly off** — plan:72-75. Tab body carries `data-tab={tab}` (M1:6143), so the locator matches the current tab's body; fails only for non-current tabs, starting with `chroma`.
29. **Small text errors** — plan:2285-2286 credits MIX quad/LERP/SLERP to T4 not T5 and cites a "Normative names and decisions" section this plan doesn't have; plan:917 says M1's `NEW_STRINGS` has eight entries (it has seven); plan:1102 puts `HELP.filmToggle` on the FILM CKPT select.

## UNCONFIRMED

30. **Async option-loading races in tests** — plan:747-752, 778-788, 820-828. `findByLabelText` resolves when the select exists; the test then changes its value or reads `options[0]`, but options arrive 1-2 promise hops later → value falls back to `""`.
31. **`App.svelte` may not import `view`** — plan:3982. T9's App code calls `view.appendLog` but its import list never adds `view`; M1 T10's reconciled text still imports `viewStore` (M1:5476).

## Clean
Test counts 14/19/16/6/8/8/15/12/17 = 115 `it()` + 4 + 5 Playwright in separate files. LatCH mapping, tree/cascade node trees, nine stage labels, `/slots` and `/models` field names match spec and server. Spot-checked v3 line citations accurate.
