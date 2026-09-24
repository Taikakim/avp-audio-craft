# Latent Forge M7 — chains, mix, library, sessions

**Goal:** build spec line 999's five things: the LANE CHAIN and MASTER CHAIN right-pane modules
(§5.5, §4.6.5), the MIX + SIGNAL PATH bottom-pane tab (§4.5), the FILES module's remaining HELP
coverage (§4.6.2), the OVERLAP — INPAINT module (§4.6.1), and SESSION / MASTER PRESET, module
presets, autosave and the project v1→v2 converter (§9.2, §9.3).

**Architecture:** split by FEATURE AREA, not by layer, unlike M6 — `RightPaneModules.svelte` already
mounts all five right-pane modules with no props, so each module's body is filled in independently
with nothing shared between them except the types M1/M4/M5 already declared. Writer A took LANE
CHAIN + MASTER CHAIN + MIX/SIGNAL PATH (math and UI together, since §5.5's LatCH mapping and §8.1's
signal-path derivation are small enough not to need a separate layer split); Writer B took FILES'
remaining gap, OVERLAP-INPAINT, and the sessions/presets/autosave/converter plumbing. **The two ran
in parallel**, not sequentially — the one real shared dependency (`arrangement.mix`/`.master`, two
new fields on M5's store) was pre-declared by exact name and type in the brief before either started,
so neither needed the other's output.

**Tech stack:** Vite + Svelte 5 (runes) + TypeScript 5.6, vitest 2, Playwright 1. No canvas in this
milestone except the CROSSFADE CURVE editor, which reuses M5's existing envelope component rather
than building a second one.

**Spec:** `docs/superpowers/specs/2026-09-15-latent-forge-design.md` — §5.5 is LANE CHAIN, normative,
including the LatCH-request mapping math; §4.6 is the right-pane module frame (OVERLAP-INPAINT,
FILES, MASTER CHAIN); §4.5's "MIX + SIGNAL PATH" paragraph and §8.1's nine commit stages; §9.2 is
sessions/projects/the v1→v2 converter; §9.3 is the four preset levels; §6.3 is the `/forge/files`,
`/forge/sessions`, `/forge/presets` HTTP contract.

**Depends on:** **M1** (foundation) — every type this milestone uses (`LaneChain`, `MasterChain`,
`MixSpec`, `OverlapParams`, `ProjectV2`, their defaults, `forgeApi`'s full sessions/presets/files
CRUD) is already declared there; this milestone fills in bodies M1 left as stubs or partial. **M4**
(PROMPT + SIGMA) — the `settings` store, prompt/render-level presets already wired there. **M5**
(timeline) — `arrangement.lanes[n].chain`, `arrangement.overlapParams`, the envelope/curve component,
both already built.

**Blocks:** M9 (rendering) — needs the `▸ MIXDOWN` and `▸ INPAINT OVERLAP` buttons this milestone
renders (both UI-only here; M9 wires the actual job submission behind them).

---

## Global constraints

**Read these before Task 1. Each one cost a debugging session, or is a defect this milestone's own
writers found and independently verified while researching it.**

1. **The `$state` proxy rule.** Every control in this milestone mutates a field on an existing
   `$state` object in place (`arrangement.lanes[n].chain.slots[0].weight = v`,
   `arrangement.overlapParams(key)`'s returned object) — never reassigns the object itself or a
   captured local copy, which would be a dead handle.
2. **An abort listener added after the signal already fired never runs.** Check `signal.aborted`
   first if a fetch (session load, in particular) can be superseded by a second click before it
   resolves.
3. **Two M1 internal contradictions, already resolved for you — use the second reading in each
   pair, do not re-derive:**
   - **`ModuleShell` is declared twice and disagrees with itself.** Task 9's own code block takes
     props `{label, open, ontoggle, lit, accent, help, children}` and emits `data-module={label}`;
     M1's own Normative-names table and every real consumer (`RightPaneModules.svelte`, the frozen
     Playwright e2e spec) assume props `{id, title, lit, children}`, self-driven off
     `view.isModuleOpen(id)`/`view.toggleModule(id)`, emitting `data-module={id}`,
     `data-module-toggle={id}`, `data-module-body={id}`. **Use the second version.** Both writers did.
   - **The view store singleton is `view`, not `viewStore`.** Some of M1 Task 9-11's own `App.svelte`
     code blocks import a `viewStore` binding that does not exist anywhere in the real module (Task
     7's actual export is `export const view = new ViewStore();`). Import `view`.
4. **`fetchAdapters()` (M1, `src/lib/forge/models.ts`) reads the wrong field and always resolves to
   `[]` against the real server.** Verified directly against `eval/explorer_render_server.py:975-993`:
   the real `/models` route returns `{"ok", "count", "models": [...], "stale_root_ids"}` — the array
   is under `models`, never `ckpts`. M1's own mock test seeds `{ok:true, ckpts:[...]}`, so it stays
   green and never catches this. **Do not copy the bug forward** — this milestone's own
   `fetchFilmCkpts()`/`fetchSlots()` read the real fields. `fetchAdapters()` itself is not edited
   here (it is M1's, frozen) but is flagged to WINTERMUTE; if it is fixed before this milestone is
   implemented, LORA/DORA's model select gets adapters for the first time as a side effect, which is
   the point.
5. **M1's own Playwright layout spec clicks the wrong element.** Its "each bottom tab opens" test
   clicks `[data-tab="${id}"]` (M1 plan line 8335); the tab BUTTONS carry
   `data-testid="bottom-tab-{id}"` (M1 plan line 6134) and no `data-tab` at all. The only element
   with a `data-tab` attribute is the tab BODY, `data-tab={tab}` (M1 plan line 6143), so the locator
   matches the current tab's body and nothing else — it fails for every non-current tab, starting
   with the very first iteration (`chroma`, while the default tab is `prompt`). **That test is red
   before and after this milestone**; T10's whole-suite gate states it as the one expected failure.
   M4's own later e2e fragment already clicks the real attribute. This milestone's own Playwright
   specs use the real attribute.
6. **`settings.attach()` (M4) is never called anywhere outside a test file, across M1, M4 and M5.**
   Verified by a full grep of both plans. This means PROMPT + SIGMA / ADVANCED SAMPLING may currently
   always resolve to `session.defaults`, never a clip's own `render` settings — a real M4/M5
   integration gap this milestone does not need to close (clip/overlap `render` fields serialise
   independently of whether `settings` reads them) but that is flagged below for WINTERMUTE.
7. **Serialise `$state` with `$state.snapshot`, never `structuredClone`.** `structuredClone` of a
   `$state` proxy (`arrangement.lanes`, `.clips`, `.mix`, `.master`, an overlap's params,
   `settings.defaults`) throws `DataCloneError` (verified by the critic on Svelte 5.57.0). M5's own
   `duplicateClip` already uses `structuredClone($state.snapshot(c))`. `$state.snapshot` is a rune, so
   any module calling it must be a `.svelte.ts` file — hence `projectSerializer.svelte.ts` (T9).
8. **Nothing may write `$state` while a `$derived` or a template expression is being evaluated**
   (`state_unsafe_mutation`, verified on Svelte 5.57.0). M5's `arrangement.overlapParams(key)` seeds
   `OVERLAP_DEFAULT` into its private store on first read, so it must never be called from a
   `$derived`, a template, or a `$derived.by` snapshot. Read with **`arrangement.peekOverlapParams(key)`**
   (added in T3, non-seeding) there; write only through `setOverlapParams`.
9. **`@testing-library/jest-dom` is installed by M1 but never registered.** M1's `vitest.config.ts`
   has no `setupFiles`, so `toHaveValue`/`toHaveClass`/`toHaveAttribute` fail with "Invalid Chai
   property". T2 adds `setupFiles: ["@testing-library/jest-dom/vitest"]`; every later task relies on it.

---
## Names inherited from M1, M4 and M5 — do not redeclare them

- **Types, already declared with defaults** (M1 T3/T4): `LatchSlot`, `LaneChain` (+ `CHAIN_DEFAULTS`),
  `ForgeLane`, `OverlapParams` (+ `OVERLAP_DEFAULT`), `MixSpec` (+ `MIX_DEFAULT`), `MasterChain`
  (+ `MASTER_DEFAULT`), `RenderHistoryEntry`, `ProjectV2`. Import these; do not redeclare any of them.
- **`forgeApi`** (M1 T5, frozen) already has the full CRUD this milestone needs:
  `files({root?, q?, limit?})`, `audioUrl(ref)`, `upload(file)`, `sessions()`, `session(name)`,
  `saveSession(name, project)`, `presets(level)`, `preset(level, name)`,
  `savePreset(level, name, payload)`, `deletePreset(level, name)`. None of this milestone's tasks add
  a method to `forgeApi` itself.
- **`fetchAdapters(): Promise<AdapterEntry[]>`** (M1 T10, `src/lib/forge/models.ts`) — `/models?
  family=adapter&loadable=1`. `AdapterEntry = {path: string; name: string; label?: string;
  family?: string}` is **declared and exported by `src/ui/topbar/modelOptions.ts`** (M1 plan
  line 5050); `models.ts` only `import type`s it (M1 plan line 5099) and does not re-export it, so a
  component imports the type from `modelOptions`, never from `models`. This milestone adds two
  siblings in `models.ts`: `fetchFilmCkpts()`
  (`/models?family=film`, falls back to `/info.film_default`) and `fetchSlots()` (`GET /slots`,
  verified shape `{ok, active: number|null, backbone: string|null, slots: [{index, path, label,
  family, cost_gb, strength}], max_slots, vram_floor_gb, free_gb}` against
  `eval/adapter_slots.py:51-60,156-160` and `eval/explorer_render_server.py:839-846,901-905`).
- **`arrangement.lanes[n].chain: LaneChain`** already exists, seeded `CHAIN_DEFAULTS`, since M5 day
  one (`defaultLanes()`). **`arrangement.mix: MixSpec`** and **`arrangement.master: MasterChain`**
  are two NEW fields this milestone adds (Task 3), seeded `structuredClone(MIX_DEFAULT)` /
  `structuredClone(MASTER_DEFAULT)`, plus one non-seeding reader, `peekOverlapParams(key)`
  (Global Constraint #8) — nothing else in `ArrangementStore` changes. The viewport is
  `arrangement.pxPerSec`/`scrollSec` with `zoomBy`/`setScrollSec` and the exported
  `MIN_PX_PER_SEC`/`MAX_PX_PER_SEC` (M5 plan lines 300-301, 593-599); there is **no
  `setPxPerSec`** (M5 T1 removed it from the view store and did not add one to `arrangement`).
- **`arrangement.overlapParams(key): OverlapParams`** / **`setOverlapParams(key, patch)`** already
  exist (M5) — OVERLAP-INPAINT writes through `setOverlapParams` and reads through T3's
  `peekOverlapParams`, because `overlapParams` seeds on first read (Global Constraint #8).
- **`arrangement.moveClip(id, startSec)`** — two arguments (M5 plan line 439).
- **`ForgeClip.previewAudio: AudioRef | null`** (M5 T10) — required on the type, **in-memory only**
  (spec §9.2 "Not serialised", M1 Normative row, M5 plan lines 6004-6008). Every `ForgeClip` this
  milestone constructs sets it to `null`, and the serialiser writes `null` rather than the live ref.
- **`view.activeLane: 0|1|2|3`**, **`view.selection: Target`**, **`view.isModuleOpen(id)`** /
  **`view.toggleModule(id)`** (M1 T7, current — the export is `view`, never `viewStore`).
- **`ModuleId`** — kebab, declared once in the view store, seven members (five spec modules +
  `legacy-inspector`/`legacy-server`). `MODULE_IDS` (all seven) and `MODULE_ORDER`/`SpecModuleId`
  (the five, render order, M1 T12) are different lists.
- **`litModules(snapshot: ModuleStateSnapshot): Record<SpecModuleId, boolean>`** (M1 T12) already
  does the non-default comparison. Tasks 2, 4 and 7 each state the expression their domain
  contributes to `RightPaneModules.svelte`'s snapshot; **Task 9 Step 5** makes the edit (below).
- **M4's `settings` store, `TargetSettingsSource` seam, prompt/render-level presets** — already
  built and out of scope here; this milestone touches only the MODULE (latch/film/lora/bungee) and
  MASTER preset levels.
- **M5's envelope/curve component** — reused for the CROSSFADE CURVE editor rather than rebuilt;
  Task 7 below names the exact file and export it imports.

### The `RightPaneModules.svelte` wiring — a real step, Task 9 Step 5

M1 T12's `RightPaneModules.svelte` (M1 plan lines 6641-6693) still holds a one-shot constant
snapshot of four `null`s. **M4 never edited this file** — M4 plan line 4712 says its module "does not
need `RightPaneModules.svelte` touched at all" and no M4 task changes `sampling` — so `sampling` is
still literally `null` and stays `null` here (see Open questions). Task 9 Step 5 replaces the
constant with a `$derived` over `chain` (T2's expression), `master` (T4's) and `overlap` (T7's, read
through the non-seeding `peekOverlapParams`), makes `lit` a `$derived` too, and passes the active
lane's chain to `<AdvancedSampling latch=…>` (M4's own handoff, M4 plan line 4741). The full code is
in that step.

## The `data-*` / `data-testid` / `HELP` contract

| selector / id | owner | note |
|---|---|---|
| `[data-module-toggle="lane-chain"\|"master-chain"\|"files"\|"overlap"]`, `[data-module-body=...]` | pre-existing (M1 T9/T12) | not re-emitted by this milestone — the modules mount inside them |
| `HELP.modulePreset`, `.latchHead`, `.latchTargetKind`, `.latchTargetValue`, `.latchWeight`, `.latchStartPct`, `.latchEndPct`, `.latchRho`, `.latchMu`, `.latchGamma`, `.latchMeanIter`, `.latchLogNorms`, `.bungeeSemitones` | pre-existing (M1 T14) | LANE CHAIN, T2 |
| `HELP.latchToggle`, `.filmToggle`, `.filmPreset`, `.filmCkpt`, `.filmScale`, `.loraToggle`, `.loraPreset`, `.loraModel`, `.loraScale`, `.bungeeToggle`, `.bungeePreset`, `.modulePresetSave`, `.modulePresetDelete` (13); `.filmTarget` pre-existing (M1 `NEW_STRINGS`) | **new, T2** | LANE CHAIN; none of the 13 existed anywhere before |
| `data-testid="latch-toggle"`/`"film-toggle"`/`"lora-toggle"`/`"bungee-toggle"`, `"<level>-preset-save"`, `"<level>-preset-delete"` for `level` ∈ `latch`/`film`/`lora`/`bungee` | **new, T2** | LANE CHAIN |
| `HELP.masterLatchToggle`, `.masterLatchHeadLabel`, `.masterHead`, `.masterGain` (4); `.latentNormalise` pre-existing | **new, T4** | MASTER CHAIN; `data-testid="master-latch-toggle"`/`"master-norm-toggle"` |
| `HELP.mixQuadWeight`, `.mixLerp`, `.mixSlerp` (3); `.mixOrder`/`.mixFold`/`.mixNodeT`/`.signalPath`/`.mixExpand` pre-existing, `HELP.renderButton` reused for both MIXDOWN buttons | **new, T5** | MIX + SIGNAL PATH; `data-testid="mix-fold"`/`"mix-expand"`/`"m1-lerp"`…, `data-signal-stage`/`data-lit`, `data-tab-body="mix"` |
| `HELP.filesRoot`, `.filesFilter` (2) | **new, T6** | FILES — `filesRow` (pre-existing) is untouched |
| `HELP.overlapChromaXfade`, `.overlapOverride`, `.overlapSteps`, `.overlapCfg` (all pre-existing) | T7 | OVERLAP-INPAINT — no new ids; `data-testid="overlap-chroma-xfade"`/`"overlap-override"`/`"overlap-steps"`/`"overlap-cfg"`/`"inpaint-overlap-button"` |
| `HELP.masterPresetSave`, `.sessionSave`, `.sessionImportV1` (3) | **new, T9** | top bar: on `data-testid="master-preset-save"`, `"session-save"`, `"session-import"` (+ hidden `"session-import-file"` input) |
| `docs/latent-forge/extract_help.mjs`'s `NEW_STRINGS` and `strings.test.ts`'s total | **T2, T4, T5, T6, T9 each add entries and each updates `strings.test.ts`** | cumulative totals in execution order: M1 T14 87 → T2 **100** → T4 **104** → T5 **107** → T6 **109** → T9 **112** (80 extracted + 7 M1 new + 25 M7 new) |

---

## The numbers §5.5 and §9.x pin — copy them exactly, do not re-derive

- **LatCH mapping** (verbatim): `gain_k = head.default_gain · weight_k`; `rho = ρ·gain_0`,
  `mu = μ·gain_0`, `gamma`/`n_iter`/`log_norms` passed through unmodified. A slot whose head is
  `"none"` or whose weight is 0 is **omitted from the request entirely**, not sent at zero. A slot
  whose head is not in `/info.latch_heads` is treated the same way (inactive, omitted): the real
  `resolve_latch` raises `unknown latch head` for any name it does not know
  (`eval/explorer_render_server.py:602-604`), so sending it would fail the whole job.
- Slot ranges: TARGET over `[head.slider_min, head.slider_max]` starting at `head.value_default`
  (a **60–200 BPM** slider when the kind is `beat_grid`); WEIGHT 0–50 (1), START%/END% 0–1
  (0/0.6); ρ 0–30 (1), μ 0–30 (1), γ 0–20 (0.3), MEAN ITER 1–80 (4). FILM: SCALE 0–2, TARGET 0–16
  onsets/s (4.0). LORA/DORA: SCALE 0–1. BUNGEE: SEMITONES ±24. MASTER CHAIN: GAIN 0–120 (64).
- **`chain idle — no A2A clip in lane`** — exact, lowercase. **The spec spells this note two
  ways**: §5.5 (spec line 474) says `chain idle — no A2A clip in lane`, §8.1 S4 (spec line 788) says
  `chain idle — no A2A clip`. This plan ships §5.5's spelling because §5.5 is the normative section
  for LANE CHAIN and the longer form names *which* thing is missing its clip; recorded in Open
  questions so the spec can be made to agree with itself.
- **Autosave: 2 s** after the last change. Session name regex `^[A-Za-z0-9._-]{1,80}$`, validated
  client-side. **Master preset scope**: shipped as the spec's own enumeration (lane chains, clip
  layout, mix order/nodes, master chain, sampling schedule, default prompt) rather than the
  "everything except two fields" blacklist reading — §9.3's two sentences do not fully reconcile;
  recorded as a real spec-internal tension in Open questions, not silently resolved either way.
- **§9.3 says "three levels" but lists four** (prompt/render/module/master) — a spec slip, reproduced
  as found, shipped against the four bullets (matching the HTTP contract's `level` enum).

---

## Two constraints that shape the whole milestone

1. **You are filling in seams, not designing from scratch.** Every type this milestone touches is
   already declared and defaulted by M1; every store field either already exists or is the one
   pre-declared addition (`arrangement.mix`/`.master`); the entire API client already exists.
2. **Several real defects in already-approved milestones (M1, M4, M5) were found while researching
   and writing this plan, verified independently, none of them M7's to fix.** They are listed in
   Global Constraints (`fetchAdapters`'s wrong field, the stale Playwright locator, `ModuleShell`'s
   duplicate declaration, `viewStore`/`view`) and in Open Questions (`settings.attach` never called
   in production, M5's Normative table wrongly naming Task 7 as the v1-store swap point, the real
   v1 `SnapMode` spelling, the TopBar MODEL select never wired to `settings`). All are flagged for
   WINTERMUTE as one batch at assembly, per his own instruction after M6.

---
## File structure

| file | what it is |
|---|---|
| `latent-forge/src/lib/chains/latch.ts` | `resolveLatch`, `chainIsIdle`, `fetchLatchHeads` (T1) |
| `latent-forge/src/test-setup.ts`, `latent-forge/vitest.config.ts` | **new / modified**: registers `@testing-library/jest-dom/vitest` through a `setupFiles` entry (T2) |
| `latent-forge/src/lib/forge/models.ts` | **modified**: adds `fetchFilmCkpts`, `fetchSlots` beside the existing `fetchAdapters` (T2) |
| `latent-forge/src/lib/chains/modulePresets.ts` | the four module-preset slices (`latch`/`film`/`lora`/`bungee`): payload builder + in-place recall (T2) |
| `latent-forge/src/ui/modules/LaneChain.svelte` | **modified**: full LatCH/FiLM/LoRA/Bungee UI with module preset recall/SAVE/DEL, replacing M1's stub (T2) |
| `latent-forge/src/lib/help/__tests__/strings.test.ts` | **modified** (M1 T14's file): the total-count assertion, updated by every string-adding task (T2, T4, T5, T6, T9) |
| `latent-forge/src/lib/mix/mixMath.ts` | MIX ORDER node-tree resolution (T3) |
| `latent-forge/src/lib/mix/signalPath.ts` | the nine §8.1 stage rows, lit/dimmed derivation (T3) |
| `latent-forge/src/lib/stores/arrangement.svelte.ts` | **modified**: adds `mix`/`master` fields and the non-seeding `peekOverlapParams` (T3) |
| `latent-forge/src/ui/modules/MasterChain.svelte` | **modified**: LATCH HEAD + GAIN + NORMALISE, replacing M1's stub (T4) |
| `latent-forge/src/ui/mix/MixSignalPath.svelte` | the MIX + SIGNAL PATH tab (T5) |
| `latent-forge/src/ui/shell/BottomPane.svelte` | **modified**: mounts `MixSignalPath` into the `mix` tab body (T5) |
| `latent-forge/tests/chains.spec.ts` | Playwright, Writer A's half (T5) |
| `latent-forge/src/ui/modules/Files.svelte` | **modified**: adds the two missing HELP ids only — already a full implementation, not a stub (T6) |
| `latent-forge/src/ui/modules/OverlapInpaint.svelte` | **modified**: crossfade curve, CHROMA CROSSFADE, LOCAL STEPS/CFG, the button, replacing M1's stub (T7) |
| `latent-forge/src/lib/forge/overlapLabel.ts` | the OVERLAP-INPAINT info line's label logic (T7) |
| `latent-forge/src/lib/forge/convertProjectV1.ts` | the v1→v2 converter (T8) |
| `latent-forge/src/lib/forge/projectSerializer.svelte.ts` | `ProjectV2` ⇄ live-store (de)serialisation via `$state.snapshot` (a rune, hence `.svelte.ts`) (T9) |
| `latent-forge/src/lib/forge/sessionName.ts` | session-name validation/prompt logic (T9) |
| `latent-forge/src/lib/forge/autosave.ts` | the 2 s debounce, and the snapshot-gated session autosave that never writes before a load or an explicit SAVE (T9) |
| `latent-forge/src/ui/shell/TopBar.svelte` | **modified**: real SESSION load/save with an `unsaved` option, IMPORT (v1/v2 project file), MASTER PRESET load/save, M1 T15's temporary SAVE/LOAD buttons removed (T9) |
| `latent-forge/src/ui/shell/__tests__/topBar.test.ts` | **modified** (M1 T10's file): its "SAVE disabled until M7" assertion flips (T9) |
| `latent-forge/src/App.svelte` | **modified**: session load/save/import, master preset load/save, autosave hookup, M1's `sessions[0]` auto-select removed (T9) |
| `latent-forge/src/ui/shell/RightPaneModules.svelte` | **modified**: live `litModules` snapshot, `<AdvancedSampling latch=…>` (T9) |
| `latent-forge/src/ui/prompt/PromptSigmaTab.svelte` | **modified** (M4 T10's file): passes the active lane's LatCH slots to `<SigmaColumn slots=…>` (T9) |
| `latent-forge/tests/sessionsFilesOverlap.spec.ts` | Playwright, Writer B's half (T10) |
| `docs/latent-forge/extract_help.mjs` | **modified**: `NEW_STRINGS` entries appended by T2, T4, T5, T6, T9, `help:extract` re-run by each |

## Status of this plan

Written **2026-09-23** by FLATLINE, by two writers working **in parallel** (not sequentially, unlike
M6) — the split is by feature area, and the one real shared name (`arrangement.mix`/`.master`) was
pre-declared in the brief before either started, so there was nothing to wait on.

**Test counts, all verified mechanically** by counting `it(` blocks at two-space indent against each
task's own stated `Tests N passed (N)` gate, plus each writer's own Playwright `test(` count read
separately (Playwright specs don't use `it(`):

| task | `it()` | task | `it()` |
|---|---|---|---|
| 1 `latch.ts` | 14 | 6 FILES HELP ids | 8 |
| 2 `LaneChain.svelte` + `modulePresets` + `models` | 26 (5 + 3 + 18) | 7 `OverlapInpaint.svelte` | 15 |
| 3 `mixMath`/`signalPath`/arrangement | 18 (6 + 10 + 2) | 8 v1→v2 converter | 12 |
| 4 `MasterChain.svelte` | 6 | 9 sessions/preset/autosave/wiring | 25 (3 + 7 + 6 + 2 + 5 + 2) |
| 5 `MixSignalPath.svelte` + Playwright | 8 (+ 4 Playwright) | 10 Playwright + self-review | 0 (+ 6 Playwright) |

**132 `it()` blocks across nine vitest-bearing tasks, plus 10 Playwright `test()`s (4 in
`tests/chains.spec.ts`, 6 in `tests/sessionsFilesOverlap.spec.ts`) — 142 total.** (Before critic
pass 1: 115 + 9 = 124.) Counted mechanically after the pass: `it(` at exactly two-space indent per
`### Task N` section, and top-level `test(` per task; every task's `Tests N passed (N)` gate matches.
M1's `strings.test.ts` total goes 87 → **112** across Tasks 2, 4, 5, 6 and 9.

**Critic pass 1 applied (2026-09-24) — see "Critic pass 1" below.** 31 findings, 12 blocking, all 31
applied after each was checked against its cited source. Every earlier milestone's pass has found
something, and no pass on this project has ever come back clean on a second, independent look —
**run a second pass before this plan is treated as done**, per the lesson M6 cost this project.

### Critic pass 1 (2026-09-24)

One read-only critic, against M1/M4/M5, the spec, `eval/explorer_render_server.py` and (for the two
runtime claims) Svelte 5.57.0 in `sa3-studio/node_modules`. **31 findings, 12 blocking, 2
unconfirmed.** The fix agent re-checked every finding against its cited lines before applying it;
all 31 held (the two unconfirmed ones were confirmed on inspection). What changed:

**Blocking.**
1. **`strings.test.ts` never updated.** M1's suite went red at Task 2's first new string. Every
   string-adding task now moves the assertion, cumulatively in execution order: T2 100, T4 104,
   T5 107, T6 109, T9 **112** (80 `KEYS` + M1's 7 `NEW_STRINGS` + M7's 25). The "wrote N strings"
   lines follow the same order.
2. **jest-dom never registered.** T2 adds `src/test-setup.ts` (`import "@testing-library/jest-dom/vitest"`)
   and `setupFiles` in `vitest.config.ts`; T4/T5 rely on it (Global Constraint #9).
3. **`structuredClone` on `$state` proxies throws.** The serialiser is now
   `projectSerializer.svelte.ts` and uses `$state.snapshot` throughout (Global Constraint #7); a test
   proves its output survives `structuredClone`.
4. **`overlapParams` seeds inside `$derived`.** T3 adds the non-seeding `peekOverlapParams`; T7's
   `params`, T9's RightPaneModules snapshot and the serialiser read through it (Global Constraint #8).
5. **`arrangement.setPxPerSec` does not exist.** `applyProject` assigns `pxPerSec`, clamped to
   M5's `MIN_PX_PER_SEC..MAX_PX_PER_SEC`.
6. **`AdapterEntry` imported from `models.ts`.** Now imported from `ui/topbar/modelOptions`.
7. **Quad-weight HELP test read the `<label>`.** `aria-label` moved onto the `<input>`.
8. **`chains.spec.ts` test 4 closed LANE CHAIN.** It now opens it only if closed.
9. **`unsaved` was unreachable.** T9 deletes M1's `sessions[0]` auto-select; `unsaved` is an option
   in the SESSION select.
10. **T10's Playwright gates were wrong both ways.** `beforeEach` PUTs a real session into the
    mock's (empty) store; Step 2 is an honest verification run (`6 passed`); Step 3 expects
    `1 failed, 16 passed`, the failure being M1's own `each bottom tab opens`.
11. **Unmocked `forgeApi.info()`.** Stubbed in T2's `beforeEach`; every fetch in T2's/T4's effects
    `.catch()`es.
12. **Autosave missed in-place edits and overwrote an unloaded session at launch.** Replaced by
    `createSnapshotAutosave`: the App effect observes `JSON.stringify(serializeProject(...))`, and
    nothing is written until a session has been loaded or explicitly saved. Unit tests prove a
    mount never saves; T10 test 1 proves it against dev:mock, test 2 proves an in-place edit lands.

**Non-blocking.**
13. `previewAudio` is written as `null` by the serialiser, the converter and `applyProject`; T8's
    test and T7's `clip()` helper match the required field.
14. MASTER CHAIN's contract-table row now names the ids T4 actually adds.
15. `HELP.masterPresetSave` is on the master SAVE button; the new session SAVE carries the new
    `HELP.sessionSave`.
16. The RightPaneModules edit is a real step (T9 Step 5) with full code; `sampling` stays M4's
    literal `null` (Open questions 19).
17. v1 files get IMPORT (T9), the smallest replacement for the removed LOAD button.
18. `applyProject` restores `settings.stage` from `backbone`; `loadSession`/IMPORT rebuild the
    server model when it changes; merged Open question 7 corrected. The converter now emits
    `medium-base` so a v1 import never forces a rebuild.
19. Module presets get SAVE and DEL (T2, `modulePresets.ts`); every level's payload includes its
    `*_on`; recall writes only that level's fields, into the active lane.
20. M4's handoff wired (T9 Step 5): `SigmaColumn slots` and `AdvancedSampling latch`.
21. LatCH TARGET has a fractional `step`, starts at `value_default` on a head change, and is a
    60–200 BPM slider for `beat_grid`.
22. An unknown head is inactive and omitted (the server raises on it); T1's test changed to match.
23. The spec's two spellings of the idle note are recorded; §5.5's is shipped, with the reason.
24. LORA/DORA has a `none` option and a resident slot sets `lora.slot`.
25. The FILM fallback test can now only pass through the fallback; T10 tests 1-2 assert a real load
    and a real autosave.
26. T10's wrong Known Incomplete item is gone: the positive OVERLAP-INPAINT case is a Playwright
    test using M5's `dropClip`.
27. `moveClip(id, startSec)` — two arguments.
28. Global Constraint #5 now says the locator matches the current tab's body, failing from `chroma`.
29. T6 credits MIX quad/LERP/SLERP to T5 and no longer cites a section this plan lacks; M1's
    `NEW_STRINGS` has seven entries; FILM CKPT has its own `HELP.filmCkpt`.
30. (unconfirmed → confirmed) option lists load after their `<select>`: every test that picks or
    reads an option now waits for it (`findByRole("option", …)`), including T4's, which the critic
    did not list.
31. (unconfirmed → confirmed) T9's `App.svelte` code now states the `view` import explicitly.

**Found while applying, not in the critic's list:** M1 T10's own `topBar.test.ts` asserts
`master-preset-save` is disabled "until M7 owns presets" — T9 flips it. M5's own Playwright
selectors (`[data-testid="clip"]`, `[data-module="overlapInpaint"]`) match nothing M5 renders;
T10 uses the real markup and this is flagged (Open questions 21). `AdvancedSampling`'s `a2a` prop
is still unwired by M5 (Open questions 20). Test counts moved 115 → 132 `it()`, 9 → 10 Playwright.

---

### Task 1: `src/lib/chains/latch.ts` — LatCH request mapping (pure)

**WHY.** Spec §5.5's mapping from a lane's `LaneChain` to the server's LatCH request is the one
piece of real math LANE CHAIN needs, and §8.1 S4's idle note (`chain idle — no A2A clip in lane`)
depends on knowing whether a chain has anything on at all. Both are pure functions of data already
declared (M1 T3's `LaneChain`/`LatchSlot`), so they are written and hand-verified before any Svelte
component touches them — Task 2's component only wires fields to `arrangement.lanes[n].chain` and
never re-derives this arithmetic. `fetchLatchHeads()` lives in the same file because it produces
the exact `Record<string, LatchHeadInfo>` shape `resolveLatch` consumes, even though — unlike
`resolveLatch`/`chainIsIdle` — it is not pure (it calls `forgeApi.info()`); it is co-located for
that reason, not because this file stops being "the pure module." Both Task 2 (LaneChain.svelte)
and Task 4 (MasterChain.svelte) import `fetchLatchHeads` and `LatchHeadInfo` from here so the head
list is fetched once per shape, not redeclared per component.

**Files:**
- Create: `latent-forge/src/lib/chains/latch.ts`, `latent-forge/src/lib/chains/__tests__/latch.test.ts`

**Interfaces:**
- Consumes from `src/lib/forge/types.ts` (M1 T3, verified at
  `docs/superpowers/plans/2026-09-16-latent-forge-m1-foundation-shell.md:470-485`):
  `interface LatchSlot { head: string; kind: string; value: number; weight: number; start_pct:
  number; end_pct: number }` and `interface LaneChain { latch_on: boolean; slots: [LatchSlot,
  LatchSlot]; hparams: { rho: number; mu: number; gamma: number; n_iter: number; log_norms:
  boolean }; film_on: boolean; film: {...}; lora_on: boolean; lora: {...}; bungee_on: boolean;
  semitones: number }`.
- Consumes `forgeApi.info(): Promise<Record<string, unknown>>` from `src/lib/forge/api.ts` (M1 T5,
  verified at m1 plan:1211 — `info: () => getJSON<Record<string, unknown>>("/info")`). `/info` is
  untyped in M1; there is no existing `LatchHeadInfo` type anywhere in M1, so it is declared fresh
  here, restated from spec §5.5/§6.4 and cross-checked against the real fixture
  `docs/latent-forge/contract/fixtures/handmade-info.json`'s `latch_heads` array (m1 plan:2374-2393,
  reproduced in Step 1 below) — **not** from the spec text alone, which never enumerates every
  field. The fixture is the ground truth used here.
- Produces: `interface LatchHeadInfo`, `interface LatchRequestSlot`, `interface LatchRequest`,
  `resolveLatch(chain: LaneChain, heads: Record<string, LatchHeadInfo>): LatchRequest | null`,
  `chainIsIdle(chain: LaneChain, hasA2AClip: boolean): boolean`,
  `fetchLatchHeads(): Promise<Record<string, LatchHeadInfo>>`. `LatchRequest`'s shape (an array of
  only the ACTIVE slots, in original order, plus five hyperparameter fields) is not pre-named
  anywhere — see Open Questions.

- [ ] **Step 1: Write the failing test**

`latent-forge/src/lib/chains/__tests__/latch.test.ts`:

```ts
import { describe, expect, it, vi } from "vitest";
import { chainIsIdle, fetchLatchHeads, resolveLatch, type LatchHeadInfo } from "../latch";
import { CHAIN_DEFAULTS } from "../../forge/defaults";
import type { LaneChain } from "../../forge/types";

function clone(c: LaneChain): LaneChain {
  return JSON.parse(JSON.stringify(c)) as LaneChain;
}

// The two real heads from docs/latent-forge/contract/fixtures/handmade-info.json (M1 plan:2374-2393),
// restated field-for-field so the test fixture and the shipped fixture cannot silently diverge.
const RMS_BASS: LatchHeadInfo = {
  name: "rms_energy_bass", family: "medium", default_gain: 512.0,
  health: "ok", supports_kinds: ["constant", "ramp_up", "ramp_down", "beat_grid"],
  slider_min: -35.2, slider_max: -0.13, value_default: -12.0,
};
const CHROMA_OTHER: LatchHeadInfo = {
  name: "chroma_other", family: "chroma", default_gain: 2048.0,
  health: "ok", supports_kinds: ["constant"],
  slider_min: 0.0, slider_max: 1.0, value_default: 0.5,
};
const HEADS: Record<string, LatchHeadInfo> = { rms_energy_bass: RMS_BASS, chroma_other: CHROMA_OTHER };

describe("resolveLatch — null cases", () => {
  it("returns null when latch_on is false, even with two fully-configured slots", () => {
    const chain = clone(CHAIN_DEFAULTS);
    chain.slots[0] = { head: "rms_energy_bass", kind: "constant", value: -10, weight: 2, start_pct: 0, end_pct: 0.6 };
    expect(resolveLatch(chain, HEADS)).toBeNull();
  });

  it("returns null when latch_on is true but every slot is inactive (head none or weight 0)", () => {
    const chain = clone(CHAIN_DEFAULTS);
    chain.latch_on = true;
    chain.slots[0] = { head: "none", kind: "constant", value: 0, weight: 1, start_pct: 0, end_pct: 0.6 };
    chain.slots[1] = { head: "rms_energy_bass", kind: "constant", value: -10, weight: 0, start_pct: 0, end_pct: 0.6 };
    expect(resolveLatch(chain, HEADS)).toBeNull();
  });
});

describe("resolveLatch — the mapping, hand-verified (spec §5.5, verbatim 468-471)", () => {
  it("computes gain_k = head.default_gain * weight_k for a single active slot", () => {
    const chain = clone(CHAIN_DEFAULTS);
    chain.latch_on = true;
    chain.slots[0] = { head: "rms_energy_bass", kind: "constant", value: -10, weight: 2, start_pct: 0, end_pct: 0.6 };
    chain.slots[1] = { head: "none", kind: "constant", value: 0, weight: 1, start_pct: 0, end_pct: 0.6 };
    chain.hparams = { rho: 2, mu: 3, gamma: 0.5, n_iter: 5, log_norms: true };
    const req = resolveLatch(chain, HEADS)!;
    // gain_0 = 512.0 * 2 = 1024
    expect(req.slots).toEqual([
      { head: "rms_energy_bass", kind: "constant", value: -10, gain: 1024, start_pct: 0, end_pct: 0.6 },
    ]);
    // rho_req = rho * gain_0 = 2 * 1024 = 2048 ; mu_req = mu * gain_0 = 3 * 1024 = 3072
    expect(req.rho).toBe(2048);
    expect(req.mu).toBe(3072);
    // gamma, n_iter, log_norms pass through UNMODIFIED, not gain-scaled.
    expect(req.gamma).toBe(0.5);
    expect(req.n_iter).toBe(5);
    expect(req.log_norms).toBe(true);
  });

  it("with rho = mu = weight = 1 reproduces the server's own default_gain exactly (spec's own identity)", () => {
    const chain = clone(CHAIN_DEFAULTS);
    chain.latch_on = true;
    chain.slots[0] = { head: "chroma_other", kind: "constant", value: 0.5, weight: 1, start_pct: 0, end_pct: 0.6 };
    chain.slots[1] = { head: "none", kind: "constant", value: 0, weight: 1, start_pct: 0, end_pct: 0.6 };
    // hparams at CHAIN_DEFAULTS is already rho: 1, mu: 1.
    const req = resolveLatch(chain, HEADS)!;
    expect(req.slots[0].gain).toBe(2048); // = chroma_other.default_gain * 1
    expect(req.rho).toBe(2048);
    expect(req.mu).toBe(2048);
  });

  it("omits an inactive slot ENTIRELY — not present at all, not a zero-weight entry", () => {
    const chain = clone(CHAIN_DEFAULTS);
    chain.latch_on = true;
    chain.slots[0] = { head: "none", kind: "constant", value: 0, weight: 1, start_pct: 0, end_pct: 0.6 };
    chain.slots[1] = { head: "chroma_other", kind: "constant", value: 0.5, weight: 4, start_pct: 0, end_pct: 0.6 };
    const req = resolveLatch(chain, HEADS)!;
    // Strong form of "entirely omitted": the head string "none" never appears anywhere in the
    // serialised request, and the array literally has one element, not two with a hole.
    expect(JSON.stringify(req)).not.toContain('"none"');
    expect(req.slots).toHaveLength(1);
    expect(req.slots[0]).not.toHaveProperty("weight"); // weight itself is never sent, only the derived gain
  });

  it("renumbers so gain_0 is the FIRST ACTIVE slot, not literal slot index 0", () => {
    // slot 0 inactive, slot 1 active and alone: k=0 in "for the active slots in order" is slot 1.
    const chain = clone(CHAIN_DEFAULTS);
    chain.latch_on = true;
    chain.slots[0] = { head: "none", kind: "constant", value: 0, weight: 1, start_pct: 0, end_pct: 0.6 };
    chain.slots[1] = { head: "chroma_other", kind: "constant", value: 0.5, weight: 4, start_pct: 0, end_pct: 0.6 };
    chain.hparams = { ...CHAIN_DEFAULTS.hparams, rho: 1, mu: 1 };
    const req = resolveLatch(chain, HEADS)!;
    // gain_0 = 2048 * 4 = 8192, from slot 1, because slot 0 dropped out of the enumeration.
    expect(req.rho).toBe(8192);
    expect(req.mu).toBe(8192);
  });

  it("keeps both slots, in order, when both are active", () => {
    const chain = clone(CHAIN_DEFAULTS);
    chain.latch_on = true;
    chain.slots[0] = { head: "rms_energy_bass", kind: "constant", value: -10, weight: 1, start_pct: 0, end_pct: 0.6 };
    chain.slots[1] = { head: "chroma_other", kind: "constant", value: 0.5, weight: 1, start_pct: 0, end_pct: 0.6 };
    const req = resolveLatch(chain, HEADS)!;
    expect(req.slots.map((s) => s.head)).toEqual(["rms_energy_bass", "chroma_other"]);
    // rho/mu still key off slot 0's gain only (512), not slot 1's.
    expect(req.rho).toBe(512);
  });

  it("treats a head the registry does not know as inactive and omits it (the server raises on unknown names)", () => {
    // eval/explorer_render_server.py:602-604: resolve_latch raises `unknown latch head` for any
    // name not in HEADS, so sending it -- even at gain 0 -- would fail the whole job.
    const chain = clone(CHAIN_DEFAULTS);
    chain.latch_on = true;
    chain.slots[0] = { head: "deleted_head", kind: "constant", value: 0, weight: 3, start_pct: 0, end_pct: 0.6 };
    chain.slots[1] = { head: "chroma_other", kind: "constant", value: 0.5, weight: 1, start_pct: 0, end_pct: 0.6 };
    const req = resolveLatch(chain, HEADS)!;
    expect(req.slots.map((s) => s.head)).toEqual(["chroma_other"]);
    expect(JSON.stringify(req)).not.toContain("deleted_head");
    // gain_0 is the first SURVIVING slot's: 2048 * 1
    expect(req.rho).toBe(2048);
    // and with nothing else active, the whole request is null rather than an empty slot list
    chain.slots[1].head = "none";
    expect(resolveLatch(chain, HEADS)).toBeNull();
  });
});

describe("chainIsIdle (spec §5.5, §8.1 S4 — the exact SIGNAL PATH string)", () => {
  it("is false when no feature is on, regardless of an A2A clip", () => {
    expect(chainIsIdle(clone(CHAIN_DEFAULTS), false)).toBe(false);
    expect(chainIsIdle(clone(CHAIN_DEFAULTS), true)).toBe(false);
  });

  it("is true when latch_on is on and the lane has no A2A clip", () => {
    const chain = clone(CHAIN_DEFAULTS);
    chain.latch_on = true;
    expect(chainIsIdle(chain, false)).toBe(true);
  });

  it("is false when latch_on is on and the lane DOES have an A2A clip", () => {
    const chain = clone(CHAIN_DEFAULTS);
    chain.latch_on = true;
    expect(chainIsIdle(chain, true)).toBe(false);
  });

  it("treats FiLM, LoRA and Bungee as equally 'active' — any one of the four, not just LatCH", () => {
    const film = clone(CHAIN_DEFAULTS); film.film_on = true;
    const lora = clone(CHAIN_DEFAULTS); lora.lora_on = true;
    const bungee = clone(CHAIN_DEFAULTS); bungee.bungee_on = true;
    expect(chainIsIdle(film, false)).toBe(true);
    expect(chainIsIdle(lora, false)).toBe(true);
    expect(chainIsIdle(bungee, false)).toBe(true);
  });
});

describe("fetchLatchHeads", () => {
  it("keys the /info.latch_heads array by head name", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({
      ok: true,
      latch_heads: [
        { name: "rms_energy_bass", family: "medium", default_gain: 512.0, health: "ok",
          supports_kinds: ["constant"], slider_min: -35.2, slider_max: -0.13, value_default: -12.0 },
      ],
    }))));
    const heads = await fetchLatchHeads();
    expect(Object.keys(heads)).toEqual(["rms_energy_bass"]);
    expect(heads.rms_energy_bass.default_gain).toBe(512.0);
  });

  it("returns an empty record rather than throwing when latch_heads is missing", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ ok: true }))));
    await expect(fetchLatchHeads()).resolves.toEqual({});
  });
});
```

- [ ] **Step 2: Run it, expect failure**

```bash
cd latent-forge && npx vitest run src/lib/chains/__tests__/latch.test.ts
```

Expected: `Failed to resolve import "../latch"`.

- [ ] **Step 3: Implement**

`latent-forge/src/lib/chains/latch.ts`:

```ts
// Spec §5.5 — LANE CHAIN's mapping to the server's LatCH request, and the SIGNAL PATH idle note
// (§8.1 S4). Pure except fetchLatchHeads (network); everything here is hand-verified against the
// spec's own worked example ("with rho = mu = weight = 1 this reproduces today's server defaults
// exactly") in the test file, not just shape-checked.

import { forgeApi } from "../forge/api";
import type { LaneChain, LatchSlot } from "../forge/types";

/**
 * The subset of /info.latch_heads' element shape LANE CHAIN actually reads (M1's own /info typing
 * is `Record<string, unknown>` -- there is no existing LatchHeadInfo anywhere in M1). Restated from
 * spec §5.5/§6.4 and cross-checked field-for-field against
 * docs/latent-forge/contract/fixtures/handmade-info.json's two real entries. The real payload
 * carries more fields (path, out_channels, loss_type, target_kind_default, standardized, schema) --
 * they exist on the wire but nothing in this milestone reads them, so they are not declared here.
 */
export interface LatchHeadInfo {
  name: string;
  family: string;
  default_gain: number;
  health: string;
  supports_kinds: string[];
  slider_min: number;
  slider_max: number;
  value_default: number;
}

export interface LatchRequestSlot {
  head: string;
  kind: string;
  value: number;
  gain: number;
  start_pct: number;
  end_pct: number;
}

/**
 * The server's LatCH request (resolve_latch semantics unchanged, spec §5.5/§6.6.4). `slots`
 * holds ONLY the active slots, in their original relative order -- an inactive slot (head "none",
 * weight 0, or a head the registry does not list) does not appear at all. rho/mu are computed from
 * `slots[0]`'s gain, i.e. from gain_0 = the first slot that SURVIVED the filter, not literal
 * LaneChain.slots[0].
 */
export interface LatchRequest {
  slots: LatchRequestSlot[];
  rho: number;
  mu: number;
  gamma: number;
  n_iter: number;
  log_norms: boolean;
}

/**
 * Spec §5.5: head "none" or weight 0 is omitted. A head the registry does not list is omitted too:
 * the real resolve_latch raises `unknown latch head` for it (eval/explorer_render_server.py:602-604),
 * so it can never be sent. Callers must therefore pass the fetched heads, not `{}`.
 */
function isActive(slot: LatchSlot, heads: Record<string, LatchHeadInfo>): boolean {
  return slot.head !== "none" && slot.weight !== 0 && Object.prototype.hasOwnProperty.call(heads, slot.head);
}

/** null when the module is off, or on but every slot is inactive (spec §5.5, verbatim 468-471). */
export function resolveLatch(chain: LaneChain, heads: Record<string, LatchHeadInfo>): LatchRequest | null {
  if (!chain.latch_on) return null;
  const active = chain.slots.filter((s) => isActive(s, heads)).map((slot): LatchRequestSlot => {
    const gain = heads[slot.head].default_gain * slot.weight;
    return { head: slot.head, kind: slot.kind, value: slot.value, gain, start_pct: slot.start_pct, end_pct: slot.end_pct };
  });
  if (active.length === 0) return null;
  const gain0 = active[0].gain;
  return {
    slots: active,
    rho: chain.hparams.rho * gain0,
    mu: chain.hparams.mu * gain0,
    gamma: chain.hparams.gamma,
    n_iter: chain.hparams.n_iter,
    log_norms: chain.hparams.log_norms,
  };
}

/**
 * Spec §8.1 S4: "a lane with an active chain but no A2A clip shows chain idle -- no A2A clip in
 * lane". Active means ANY of the four features is on, not just LatCH -- FiLM, LoRA and Bungee all
 * run during the same A2A pass and are equally idle without one.
 */
export function chainIsIdle(chain: LaneChain, hasA2AClip: boolean): boolean {
  const active = chain.latch_on || chain.film_on || chain.lora_on || chain.bungee_on;
  return active && !hasA2AClip;
}

/** Keys /info.latch_heads by name, for the head selects in Task 2 and Task 4. */
export async function fetchLatchHeads(): Promise<Record<string, LatchHeadInfo>> {
  const info = await forgeApi.info();
  const raw = (info as { latch_heads?: unknown }).latch_heads;
  const list = Array.isArray(raw) ? (raw as LatchHeadInfo[]) : [];
  const out: Record<string, LatchHeadInfo> = {};
  for (const h of list) out[h.name] = h;
  return out;
}
```

- [ ] **Step 4: Run it, expect pass**

```bash
cd latent-forge && npx vitest run src/lib/chains/__tests__/latch.test.ts
```

Expected: `Test Files  1 passed (1)` / `Tests  14 passed (14)`.

- [ ] **Step 5: Commit**

```bash
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M7 T1: resolveLatch/chainIsIdle (spec 5.5, 8.1 S4), hand-verified against the spec's own rho=mu=weight=1 identity and the fixture's two real heads"
```

---

### Task 2: `src/ui/modules/LaneChain.svelte` — replacing M1's stub in full

**WHY.** This is the module the whole milestone hangs off: LATCH GUIDANCE, FiLM, LoRA/DORA and
Bungee, all four writing into the SAME `LaneChain` object that Task 1 reads and that M5's lane
header dot (`docs/superpowers/plans/2026-09-17-latent-forge-m5-timeline-fidelity.md:2546`,
`const chainActive = $derived(!deepEqual(lane.chain, CHAIN_DEFAULTS))`) already watches for
free — mutate `arrangement.lanes[view.activeLane].chain` in place and the lane header's dot lights
itself; no wiring back to M5 is needed or wanted. M1's stub
(`docs/superpowers/plans/2026-09-16-latent-forge-m1-foundation-shell.md:6549-6568`) is replaced in
full, not extended.

**Files:**
- Create: `latent-forge/src/test-setup.ts`; Modify: `latent-forge/vitest.config.ts` (M1 T1 —
  register jest-dom's matchers via `setupFiles`; Global Constraint #9. Every later task's
  `toHaveValue`/`toHaveClass`/`toHaveAttribute` relies on this.)
- Modify: `latent-forge/src/ui/modules/LaneChain.svelte` (M1 T12 stub, replaced whole)
- Modify: `latent-forge/src/lib/forge/models.ts` (add `fetchFilmCkpts`, `fetchSlots` beside M1's
  `fetchAdapters`)
- Create: `latent-forge/src/lib/chains/modulePresets.ts`,
  `latent-forge/src/lib/chains/__tests__/modulePresets.test.ts`
- Modify: `docs/latent-forge/extract_help.mjs` (13 new `NEW_STRINGS` entries — see below) and
  regenerate the committed `latent-forge/src/lib/help/strings.ts`
- Modify: `latent-forge/src/lib/help/__tests__/strings.test.ts` (M1 T14: total 87 → 100)
- Create: `latent-forge/src/lib/forge/__tests__/models.test.ts`,
  `latent-forge/src/ui/modules/__tests__/LaneChain.component.test.ts`

**Interfaces:**
- Consumes from `src/lib/forge/types.ts` (M1 T3): `LaneChain`, `LatchSlot`.
- Consumes from `src/lib/forge/defaults.ts` (M1 T4): `CHAIN_DEFAULTS` (test fixtures only — the
  component itself never constructs a default, it only ever reads the live store's object).
- Consumes from `src/lib/chains/latch.ts` (Task 1): `LatchHeadInfo`, `fetchLatchHeads()`. (Task 1
  does not export `resolveLatch`/`chainIsIdle` for this component to call directly — those are
  Task 3's `signalPath.ts` concern, at commit-preview time, not at edit time.)
- Consumes from `src/lib/stores/arrangement.svelte.ts` (M5, current file verified at
  `docs/superpowers/plans/2026-09-17-latent-forge-m5-timeline-fidelity.md:330-348`):
  `arrangement.lanes: ForgeLane[]`, where `ForgeLane.chain: LaneChain` is already seeded
  `structuredClone(CHAIN_DEFAULTS)` per lane (`defaultLanes()`). **This is a `$state`-proxied
  object**: every control here mutates a field of `arrangement.lanes[view.activeLane].chain` in
  place (`chain.slots[0].weight = v`) and never reassigns `chain` or a captured local copy of it.
- Consumes from `src/lib/stores/view.svelte.ts` (M1 T7): `view.activeLane: 0 | 1 | 2 | 3` (which
  lane's chain this module edits and follows when the active lane changes).
- Consumes `forgeApi` from `src/lib/forge/api.ts` (M1 T5, verified at m1 plan:1249-1252):
  `forgeApi.presets(level: string): Promise<{ok:true; names:string[]}>`,
  `forgeApi.preset(level, name): Promise<Record<string, unknown>>`,
  `forgeApi.savePreset(level, name, payload): Promise<{ok:true}>`,
  `forgeApi.deletePreset(level, name): Promise<{ok:true}>` — called directly by the component for
  each of the four levels (`latch`, `film`, `lora`, `bungee`): `presets` lists, `preset` recalls,
  `savePreset` saves (the SAVE button), `deletePreset` deletes (the DEL button). No intermediate
  client, per the brief. Spec §9.3: "module (`latch`, `film`, `lora`, `bungee`): that module's
  settings object … module recall applies to the active lane."
- Consumes `fetchAdapters(): Promise<AdapterEntry[]>` from `src/lib/forge/models.ts` (M1 T10,
  verified at m1 plan:5099-5113 — reads `/models?family=adapter&loadable=1`), and the **type**
  `AdapterEntry` from `src/ui/topbar/modelOptions.ts` (M1 plan line 5050 — `models.ts` does not
  re-export it).
- Produces, from `src/lib/chains/modulePresets.ts`: `type ModuleLevel = "latch" | "film" | "lora" |
  "bungee"`, `MODULE_PRESET_FIELDS: Record<ModuleLevel, readonly (keyof LaneChain)[]>` (`latch` →
  `latch_on, slots, hparams`; `film` → `film_on, film`; `lora` → `lora_on, lora`; `bungee` →
  `bungee_on, semitones` — every level carries its own `*_on` flag, so a recalled preset restores
  on/off as well as values), `modulePresetPayload(chain: LaneChain, level: ModuleLevel):
  Partial<LaneChain>` (a plain deep copy of exactly those fields, safe on a `$state` proxy because
  it copies through JSON rather than `structuredClone`), `applyModulePreset(chain: LaneChain, level:
  ModuleLevel, payload: Record<string, unknown>): void` (writes ONLY that level's fields, in place,
  into the chain it is given — the component passes the active lane's).
- Produces, added to `src/lib/forge/models.ts`: `fetchFilmCkpts(): Promise<AdapterEntry[]>` (reads
  `/models?family=film`) and `fetchSlots(): Promise<SlotsResponse>` (reads `/slots`, shape verified
  directly against `eval/adapter_slots.py:51-60,156-160` and
  `eval/explorer_render_server.py:839-846,901-905` — `{ok: true, active: number|null, backbone:
  string|null, slots: [{index, path, label, family, cost_gb, strength}], max_slots: number,
  vram_floor_gb: number, free_gb: number}`).
- Produces the component `LaneChain`, and the expression Task 9 Step 5 wires into
  `RightPaneModules.svelte`'s snapshot (M1 T12, `docs/superpowers/plans/2026-09-16-latent-forge-m1-foundation-shell.md:6661-6666`):
  **`chain: arrangement.lanes[view.activeLane].chain`**, read inside that step's `$derived`.
- Produces new `HELP` ids (Normative names, added via `docs/latent-forge/extract_help.mjs`'s
  `NEW_STRINGS`, `latent-forge/src/lib/help/strings.ts` regenerated — see Step 4), 13 of them:
  `latchToggle`, `filmToggle`, `filmPreset`, `filmCkpt`, `filmScale`, `loraToggle`, `loraPreset`,
  `loraModel`, `loraScale`, `bungeeToggle`, `bungeePreset`, `modulePresetSave`,
  `modulePresetDelete`. (`filmTarget`, `latchHead`, `latchTargetKind`,
  `latchTargetValue`, `latchWeight`, `latchStartPct`, `latchEndPct`, `latchRho`, `latchMu`,
  `latchGamma`, `latchMeanIter`, `latchLogNorms`, `bungeeSemitones`, `modulePreset` already exist,
  M1 T14 — reused, not redeclared.)

- [ ] **Step 1: Register jest-dom's matchers, then write the failing tests**

M1 T1 installs `@testing-library/jest-dom` (M1 plan line 261) but its `vitest.config.ts` (M1 plan
lines 264-282) has no `setupFiles`, so `expect(el).toHaveValue(...)` fails with "Invalid Chai
property: toHaveValue" in every jsdom test that uses it (this task's, T4's, T5's). Create
`latent-forge/src/test-setup.ts` — inside `src/` so `tsconfig`'s include picks up the `vitest`
module augmentation the import carries, and `svelte-check` knows the matchers' types:

```ts
// Registers @testing-library/jest-dom's matchers (toHaveValue, toHaveClass, toHaveAttribute, ...)
// on vitest's expect, for every test file. Importing it in a node-environment test is harmless.
import "@testing-library/jest-dom/vitest";
```

and in `latent-forge/vitest.config.ts`, inside `test: { ... }`, add one line after
`restoreMocks: true,`:

```ts
    setupFiles: ["./src/test-setup.ts"],
```

Nothing else in the config changes. Tasks 4 and 5 rely on this and do not repeat it.

`latent-forge/src/lib/forge/__tests__/models.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchFilmCkpts, fetchSlots } from "../models";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

afterEach(() => vi.unstubAllGlobals());

describe("fetchFilmCkpts", () => {
  it("asks /models for the film family", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ ok: true, models: [{ path: "/SERVER/f.ckpt", name: "f.ckpt" }] }));
    vi.stubGlobal("fetch", fetchMock);
    const out = await fetchFilmCkpts();
    expect(fetchMock.mock.calls[0][0]).toBe("/models?family=film");
    expect(out).toEqual([{ path: "/SERVER/f.ckpt", name: "f.ckpt" }]);
  });

  it("returns an empty list, not a throw, when the server refuses", async () => {
    vi.stubGlobal("fetch", async () => jsonResponse({ ok: false, error: "no film root" }, 200));
    await expect(fetchFilmCkpts()).resolves.toEqual([]);
  });

  // Verified directly against eval/explorer_render_server.py:977-997 (the real /models route):
  // the response key is "models", not "ckpts". M1's own fetchAdapters (models.ts) reads
  // body.ckpts and would silently return [] against the real server -- see Open Questions. This
  // new function does NOT copy that key.
  it("reads the 'models' key, not 'ckpts' (the real server's field name)", async () => {
    vi.stubGlobal("fetch", async () => jsonResponse({ ok: true, models: [{ path: "/SERVER/g.ckpt", name: "g.ckpt" }] }));
    const out = await fetchFilmCkpts();
    expect(out).toHaveLength(1);
  });
});

describe("fetchSlots", () => {
  it("parses the real /slots shape (eval/adapter_slots.py Slot.as_dict + _slot_state)", async () => {
    vi.stubGlobal("fetch", async () => jsonResponse({
      ok: true, active: 0, backbone: "medium-base",
      slots: [{ index: 0, path: "/SERVER/a.safetensors", label: "a", family: "adapter", cost_gb: 1.2, strength: 1.0 }],
      max_slots: 4, vram_floor_gb: 6.0, free_gb: 9.4,
    }));
    const out = await fetchSlots();
    expect(out.slots).toHaveLength(1);
    expect(out.slots[0].label).toBe("a");
    expect(out.max_slots).toBe(4);
  });

  it("returns an empty slot table rather than throwing on a malformed body", async () => {
    vi.stubGlobal("fetch", async () => jsonResponse({ ok: false }));
    const out = await fetchSlots();
    expect(out.slots).toEqual([]);
  });
});
```

`latent-forge/src/ui/modules/__tests__/LaneChain.component.test.ts`:

```ts
// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CHAIN_DEFAULTS } from "../../../lib/forge/defaults";
import { arrangement } from "../../../lib/stores/arrangement.svelte";
import { view } from "../../../lib/stores/view.svelte";
import { forgeApi } from "../../../lib/forge/api";
import * as models from "../../../lib/forge/models";
import * as latch from "../../../lib/chains/latch";
import LaneChain from "../LaneChain.svelte";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

beforeEach(() => {
  view.setActiveLane(0);
  // every lane, not just lane 0: two tests below assert on lane 1 staying default
  for (const lane of arrangement.lanes) lane.chain = structuredClone(CHAIN_DEFAULTS);
  vi.spyOn(latch, "fetchLatchHeads").mockResolvedValue({
    rms_energy_bass: { name: "rms_energy_bass", family: "medium", default_gain: 512, health: "ok",
      supports_kinds: ["constant", "beat_grid"], slider_min: -35.2, slider_max: -0.13, value_default: -12 },
  });
  vi.spyOn(models, "fetchFilmCkpts").mockResolvedValue([]);
  vi.spyOn(models, "fetchSlots").mockResolvedValue({ ok: true, active: null, backbone: null, slots: [], max_slots: 4, vram_floor_gb: 6, free_gb: 9 });
  vi.spyOn(models, "fetchAdapters").mockResolvedValue([{ path: "/SERVER/lora1.safetensors", name: "lora1" }]);
  vi.spyOn(forgeApi, "presets").mockResolvedValue({ ok: true, names: [] });
  // The component calls forgeApi.info() itself (FILM's /info.film_default fallback). Unmocked, a
  // relative fetch("/info") rejects in jsdom and vitest fails the run on the unhandled rejection
  // even when every assertion passed -- so it is stubbed for every test, and the component
  // .catch()es it besides.
  vi.spyOn(forgeApi, "info").mockResolvedValue({ ok: true });
});

describe("LATCH GUIDANCE toggle", () => {
  it("mutates arrangement.lanes[activeLane].chain.latch_on in place, not by reassigning chain", async () => {
    render(LaneChain);
    const before = arrangement.lanes[0].chain;
    await fireEvent.click(await screen.findByTestId("latch-toggle"));
    expect(arrangement.lanes[0].chain.latch_on).toBe(true);
    expect(arrangement.lanes[0].chain).toBe(before); // same object, mutated -- not replaced
  });
});

describe("LatCH slot fields write through the live chain", () => {
  it("writing WEIGHT sets chain.slots[0].weight", async () => {
    render(LaneChain);
    const weight = await screen.findByLabelText("WEIGHT — slot 1");
    await fireEvent.input(weight, { target: { value: "5" } });
    expect(arrangement.lanes[0].chain.slots[0].weight).toBe(5);
  });

  it("writing the head select sets chain.slots[0].head from the fetched /info.latch_heads list", async () => {
    render(LaneChain);
    const head = await screen.findByLabelText("HEAD — slot 1");
    // The select exists before the heads arrive; wait for the option itself, or the change below
    // sets a value no <option> has and the select falls back to "".
    await screen.findAllByRole("option", { name: "rms_energy_bass · medium" });
    await fireEvent.change(head, { target: { value: "rms_energy_bass" } });
    expect(arrangement.lanes[0].chain.slots[0].head).toBe("rms_energy_bass");
  });

  it("choosing a head starts TARGET at head.value_default and ranges it over slider_min..slider_max (spec 5.5)", async () => {
    render(LaneChain);
    const head = await screen.findByLabelText("HEAD — slot 1");
    await screen.findAllByRole("option", { name: "rms_energy_bass · medium" });
    await fireEvent.change(head, { target: { value: "rms_energy_bass" } });
    expect(arrangement.lanes[0].chain.slots[0].value).toBe(-12);
    const target = (await screen.findByLabelText("TARGET — slot 1")) as HTMLInputElement;
    expect(target.min).toBe("-35.2");
    expect(target.max).toBe("-0.13");
    // a fractional step, not the browser's default of 1 -- chroma_other's [0, 1] range would
    // otherwise allow only 0 or 1
    expect(Number(target.step)).toBeLessThan(1);
  });

  it("the beat_grid kind turns TARGET into a 60-200 BPM slider (spec 5.5)", async () => {
    render(LaneChain);
    const head = await screen.findByLabelText("HEAD — slot 1");
    await screen.findAllByRole("option", { name: "rms_energy_bass · medium" });
    await fireEvent.change(head, { target: { value: "rms_energy_bass" } });
    const kind = await screen.findByLabelText("KIND — slot 1");
    await screen.findAllByRole("option", { name: "beat_grid" });
    await fireEvent.change(kind, { target: { value: "beat_grid" } });
    expect(arrangement.lanes[0].chain.slots[0].kind).toBe("beat_grid");
    const target = (await screen.findByLabelText("TARGET — slot 1")) as HTMLInputElement;
    expect(target.min).toBe("60");
    expect(target.max).toBe("200");
    expect(arrangement.lanes[0].chain.slots[0].value).toBeGreaterThanOrEqual(60);
    expect(arrangement.lanes[0].chain.slots[0].value).toBeLessThanOrEqual(200);
  });
});

describe("FILM", () => {
  it("toggling FILM sets chain.film_on", async () => {
    render(LaneChain);
    await fireEvent.click(await screen.findByTestId("film-toggle"));
    expect(arrangement.lanes[0].chain.film_on).toBe(true);
  });

  it("SCALE writes chain.film.gain over its 0-2 range", async () => {
    render(LaneChain);
    const scale = await screen.findByLabelText("FILM SCALE");
    await fireEvent.input(scale, { target: { value: "1.5" } });
    expect(arrangement.lanes[0].chain.film.gain).toBe(1.5);
  });

  it("falls back to /info.film_default when /models?family=film is empty", async () => {
    // A non-null default ckpt, so the assertion can only pass if the component actually read
    // /info.film_default -- chain.film.ckpt is null by default, so checking the select's value
    // alone would pass with or without the fallback.
    vi.spyOn(forgeApi, "info").mockResolvedValue({ ok: true, film_default: { ckpt: "/SERVER/film_default.ckpt", gain: 1.0 } });
    render(LaneChain);
    const ckpt = await screen.findByLabelText("FILM CKPT");
    expect(await screen.findByRole("option", { name: "server default (/SERVER/film_default.ckpt)" })).toBeTruthy();
    expect(ckpt).toHaveValue(""); // null ckpt -> the "server default" option, not a blank/broken select
  });
});

describe("LORA / DORA", () => {
  it("tries fetchSlots() before fetchAdapters() for the model list", async () => {
    vi.spyOn(models, "fetchSlots").mockResolvedValue({
      ok: true, active: 0, backbone: "medium-base",
      slots: [{ index: 0, path: "/SERVER/resident.safetensors", label: "resident", family: "adapter", cost_gb: 1, strength: 1 }],
      max_slots: 4, vram_floor_gb: 6, free_gb: 9,
    });
    render(LaneChain);
    const model = (await screen.findByLabelText("LORA / DORA MODEL")) as HTMLSelectElement;
    // options arrive one or two promise hops after the select renders -- wait for the last one
    await screen.findByRole("option", { name: "lora1" });
    const options = Array.from(model.options).map((o) => o.textContent);
    // an explicit "none" first (ckpt_path null must not display as the first adapter), then the
    // resident slot, then the /models adapter fallback
    expect(options).toEqual(["none", "resident", "lora1"]);
    expect(model).toHaveValue("");
    // picking a resident slot records its slot index as well as its path (LaneChain.lora.slot, M1 T3)
    await fireEvent.change(model, { target: { value: "/SERVER/resident.safetensors" } });
    expect(arrangement.lanes[0].chain.lora.ckpt_path).toBe("/SERVER/resident.safetensors");
    expect(arrangement.lanes[0].chain.lora.slot).toBe(0);
    // an adapter that is not resident clears it again
    await fireEvent.change(model, { target: { value: "/SERVER/lora1.safetensors" } });
    expect(arrangement.lanes[0].chain.lora.slot).toBeNull();
  });

  it("SCALE writes chain.lora.strength over its 0-1 range", async () => {
    render(LaneChain);
    const scale = await screen.findByLabelText("LORA / DORA SCALE");
    await fireEvent.input(scale, { target: { value: "0.4" } });
    expect(arrangement.lanes[0].chain.lora.strength).toBe(0.4);
  });
});

describe("BUNGEE", () => {
  it("SEMITONES drag-scales chain.semitones over its +/-24 range", async () => {
    render(LaneChain);
    const semis = await screen.findByLabelText("SEMITONES");
    await fireEvent.change(semis, { target: { value: "-7" } });
    expect(arrangement.lanes[0].chain.semitones).toBe(-7);
  });

  it("ships an undrawn module preset select for the bungee level (spec 9.3's fourth, undrawn, level)", async () => {
    render(LaneChain);
    expect(await screen.findByLabelText("BUNGEE preset")).toBeTruthy();
  });
});

describe("module presets — direct forgeApi calls, no intermediate client", () => {
  it("LATCH GUIDANCE's preset select lists forgeApi.presets('latch')", async () => {
    vi.spyOn(forgeApi, "presets").mockImplementation(async (level) =>
      level === "latch" ? { ok: true, names: ["dub"] } : { ok: true, names: [] });
    render(LaneChain);
    expect(await screen.findByText("dub")).toBeTruthy();
  });

  it("choosing a saved latch preset applies it to the active lane via forgeApi.preset('latch', name)", async () => {
    vi.spyOn(forgeApi, "presets").mockResolvedValue({ ok: true, names: ["dub"] });
    vi.spyOn(forgeApi, "preset").mockResolvedValue({ latch_on: true, slots: CHAIN_DEFAULTS.slots, hparams: CHAIN_DEFAULTS.hparams });
    render(LaneChain);
    const select = await screen.findByLabelText("LATCH GUIDANCE preset");
    await screen.findByRole("option", { name: "dub" }); // wait for the option, not just the select
    await fireEvent.change(select, { target: { value: "dub" } });
    expect(forgeApi.preset).toHaveBeenCalledWith("latch", "dub");
    await waitFor(() => expect(arrangement.lanes[0].chain.latch_on).toBe(true));
    expect(arrangement.lanes[1].chain.latch_on).toBe(false); // spec 9.3: recall applies to the active lane only
  });

  it("SAVE writes the active lane's latch slice -- including latch_on -- through forgeApi.savePreset", async () => {
    const save = vi.spyOn(forgeApi, "savePreset").mockResolvedValue({ ok: true });
    vi.spyOn(window, "prompt").mockReturnValue("my-latch");
    arrangement.lanes[0].chain.latch_on = true;
    arrangement.lanes[0].chain.hparams.rho = 7;
    render(LaneChain);
    await fireEvent.click(await screen.findByTestId("latch-preset-save"));
    await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
    const [level, name, payload] = save.mock.calls[0];
    expect(level).toBe("latch");
    expect(name).toBe("my-latch");
    expect(payload).toEqual({
      latch_on: true,
      slots: JSON.parse(JSON.stringify(arrangement.lanes[0].chain.slots)),
      hparams: { ...CHAIN_DEFAULTS.hparams, rho: 7 },
    });
  });

  it("DEL deletes the selected module preset through forgeApi.deletePreset and drops it from the list", async () => {
    vi.spyOn(forgeApi, "presets").mockImplementation(async (level) =>
      level === "film" ? { ok: true, names: ["tight"] } : { ok: true, names: [] });
    vi.spyOn(forgeApi, "preset").mockResolvedValue({ film_on: true, film: CHAIN_DEFAULTS.film });
    const del = vi.spyOn(forgeApi, "deletePreset").mockResolvedValue({ ok: true });
    render(LaneChain);
    const select = await screen.findByLabelText("FILM preset");
    await screen.findByRole("option", { name: "tight" });
    await fireEvent.change(select, { target: { value: "tight" } });
    await fireEvent.click(await screen.findByTestId("film-preset-delete"));
    await waitFor(() => expect(del).toHaveBeenCalledWith("film", "tight"));
    await waitFor(() => expect(screen.queryByRole("option", { name: "tight" })).toBeNull());
  });
});

describe("following the active lane", () => {
  it("switching view.activeLane switches which lane's chain the module edits", async () => {
    arrangement.lanes[1].chain.latch_on = true;
    render(LaneChain);
    view.setActiveLane(1);
    const toggle = await screen.findByTestId("latch-toggle");
    expect(toggle).toHaveClass("on");
  });
});

describe("HELP ids on the controls this task adds (docs/latent-forge/extract_help.mjs NEW_STRINGS)", () => {
  it("attaches HELP.filmScale, .filmCkpt, .loraScale, .bungeePreset, .modulePresetSave and .modulePresetDelete", async () => {
    render(LaneChain);
    const { HELP } = await import("../../../lib/help/strings");
    expect((await screen.findByLabelText("FILM SCALE")).getAttribute("data-help")).toBe(HELP.filmScale);
    expect((await screen.findByLabelText("FILM CKPT")).getAttribute("data-help")).toBe(HELP.filmCkpt);
    expect((await screen.findByLabelText("LORA / DORA SCALE")).getAttribute("data-help")).toBe(HELP.loraScale);
    expect((await screen.findByLabelText("BUNGEE preset")).getAttribute("data-help")).toBe(HELP.bungeePreset);
    expect((await screen.findByTestId("bungee-preset-save")).getAttribute("data-help")).toBe(HELP.modulePresetSave);
    expect((await screen.findByTestId("bungee-preset-delete")).getAttribute("data-help")).toBe(HELP.modulePresetDelete);
  });
});
```

`latent-forge/src/lib/chains/__tests__/modulePresets.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { CHAIN_DEFAULTS } from "../../forge/defaults";
import type { LaneChain } from "../../forge/types";
import { applyModulePreset, MODULE_PRESET_FIELDS, modulePresetPayload } from "../modulePresets";

function clone(c: LaneChain): LaneChain {
  return JSON.parse(JSON.stringify(c)) as LaneChain;
}

describe("module presets (spec 9.3: module level = that module's settings object)", () => {
  it("each level's payload is exactly its own fields, *_on flag included", () => {
    const chain = clone(CHAIN_DEFAULTS);
    chain.film_on = true;
    chain.semitones = -5;
    expect(Object.keys(modulePresetPayload(chain, "latch")).sort()).toEqual(["hparams", "latch_on", "slots"]);
    expect(modulePresetPayload(chain, "film")).toEqual({ film_on: true, film: CHAIN_DEFAULTS.film });
    expect(modulePresetPayload(chain, "lora")).toEqual({ lora_on: false, lora: CHAIN_DEFAULTS.lora });
    expect(modulePresetPayload(chain, "bungee")).toEqual({ bungee_on: false, semitones: -5 });
    expect(MODULE_PRESET_FIELDS.bungee).toEqual(["bungee_on", "semitones"]);
  });

  it("the payload is a deep copy -- editing the chain afterwards does not change a saved payload", () => {
    const chain = clone(CHAIN_DEFAULTS);
    const payload = modulePresetPayload(chain, "latch") as Pick<LaneChain, "hparams">;
    chain.hparams.rho = 9;
    expect(payload.hparams.rho).toBe(CHAIN_DEFAULTS.hparams.rho);
  });

  it("recall writes only that level's fields, in place, and ignores anything else in the payload", () => {
    const chain = clone(CHAIN_DEFAULTS);
    const before = chain;
    applyModulePreset(chain, "bungee", { bungee_on: true, semitones: 7, latch_on: true, film_on: true });
    expect(chain).toBe(before);                 // same object -- the $state proxy rule
    expect(chain.bungee_on).toBe(true);
    expect(chain.semitones).toBe(7);
    expect(chain.latch_on).toBe(false);         // not bungee's field: untouched
    expect(chain.film_on).toBe(false);
  });
});
```

- [ ] **Step 2: Run it, expect failure**

```bash
cd latent-forge && npx vitest run src/lib/forge/__tests__/models.test.ts src/lib/chains/__tests__/modulePresets.test.ts src/ui/modules/__tests__/LaneChain.component.test.ts
```

Expected: `models.test.ts` fails with `"fetchFilmCkpts" is not exported by "src/lib/forge/models.ts"`
(and the same for `fetchSlots`); `modulePresets.test.ts` fails with `Failed to resolve import
"../modulePresets"`; `LaneChain.component.test.ts` fails on the first `findByTestId` timing out,
since M1's stub renders only a `<p class="pending">`.

- [ ] **Step 3: Extend `models.ts`, write `modulePresets.ts`**

Add to `latent-forge/src/lib/forge/models.ts` (M1's `fetchAdapters` and its header comment stay
untouched above this):

```ts
/** Sibling of fetchAdapters, same shape, for FiLM's CKPT select (spec §5.5, §10 X9). */
export async function fetchFilmCkpts(): Promise<AdapterEntry[]> {
  const res = await fetch("/models?family=film");
  const text = await res.text();
  if (!text) return [];
  let body: { ok?: boolean; models?: AdapterEntry[] };
  try {
    body = JSON.parse(text) as { ok?: boolean; models?: AdapterEntry[] };
  } catch {
    return [];
  }
  if (!res.ok || body.ok === false || !Array.isArray(body.models)) return [];
  return body.models;
}

export interface SlotEntry {
  index: number; path: string; label: string; family: string; cost_gb: number; strength: number;
}
export interface SlotsResponse {
  ok: boolean; active: number | null; backbone: string | null;
  slots: SlotEntry[]; max_slots: number; vram_floor_gb: number; free_gb: number;
}

/**
 * Resident adapter slots (eval/adapter_slots.py, eval/explorer_render_server.py:901-905). LORA/DORA
 * lists these first -- switching between them costs milliseconds, a fresh /models load does not.
 */
export async function fetchSlots(): Promise<SlotsResponse> {
  const res = await fetch("/slots");
  const text = await res.text();
  const empty: SlotsResponse = { ok: false, active: null, backbone: null, slots: [], max_slots: 0, vram_floor_gb: 0, free_gb: 0 };
  if (!text) return empty;
  let body: Partial<SlotsResponse>;
  try {
    body = JSON.parse(text) as Partial<SlotsResponse>;
  } catch {
    return empty;
  }
  if (!res.ok || body.ok === false || !Array.isArray(body.slots)) return empty;
  return {
    ok: true, active: body.active ?? null, backbone: body.backbone ?? null,
    slots: body.slots, max_slots: body.max_slots ?? 0,
    vram_floor_gb: body.vram_floor_gb ?? 0, free_gb: body.free_gb ?? 0,
  };
}
```

`latent-forge/src/lib/chains/modulePresets.ts`:

```ts
// Spec §9.3's module level: "`latch`, `film`, `lora`, `bungee`: that module's settings object …
// module recall applies to the active lane." Each level's slice is the set of LaneChain fields its
// module owns, INCLUDING its own on/off flag, so every level has the same shape rule: a recalled
// preset restores whether the module is on, not just its values.
import type { LaneChain } from "../forge/types";

export type ModuleLevel = "latch" | "film" | "lora" | "bungee";

export const MODULE_PRESET_FIELDS: Record<ModuleLevel, readonly (keyof LaneChain)[]> = {
  latch: ["latch_on", "slots", "hparams"],
  film: ["film_on", "film"],
  lora: ["lora_on", "lora"],
  bungee: ["bungee_on", "semitones"],
};

/** A plain deep copy of the level's fields. JSON, not structuredClone: `chain` is normally a
 *  $state proxy, and structuredClone throws DataCloneError on one (Global Constraint #7). */
export function modulePresetPayload(chain: LaneChain, level: ModuleLevel): Partial<LaneChain> {
  const out: Record<string, unknown> = {};
  for (const k of MODULE_PRESET_FIELDS[level]) out[k] = JSON.parse(JSON.stringify(chain[k]));
  return out as Partial<LaneChain>;
}

/** Writes ONLY the level's own fields into `chain`, in place (the $state proxy rule). Anything else
 *  in the payload -- another level's field, or junk from a hand-edited preset file -- is ignored. */
export function applyModulePreset(chain: LaneChain, level: ModuleLevel, payload: Record<string, unknown>): void {
  const target = chain as unknown as Record<string, unknown>;
  for (const k of MODULE_PRESET_FIELDS[level]) {
    if (k in payload && payload[k] !== undefined) target[k] = JSON.parse(JSON.stringify(payload[k]));
  }
}
```

- [ ] **Step 4: Add the new HELP strings**

Add to `docs/latent-forge/extract_help.mjs`'s `NEW_STRINGS` object (m1 plan:7829-7852; append,
do not touch the seven entries already there — `transportPlay`, `transportStop`, `transportLoop`,
`darkToggle`, `filmTarget`, `opSelect`, `previewMixdownToggle`):

```js
  latchToggle:
    "Turns LatCH guidance on for this lane. Both slots keep their settings while off; nothing is " +
    "unloaded. Safe value: off.",
  filmToggle:
    "Turns the FiLM density adapter on for this lane. Safe value: off.",
  filmPreset:
    "Module preset — recalls just this FiLM slot's settings.",
  filmScale:
    "How hard the FiLM conditioning is applied, scaling the head's own default gain. Safe value: 1.0.",
  loraToggle:
    "Turns the resident LoRA/DORA adapter on for this lane. Safe value: off.",
  loraPreset:
    "Module preset — recalls just this LoRA/DORA slot's settings.",
  loraModel:
    "Which adapter to apply. Resident slots (already loaded, from /slots) are listed first because " +
    "switching to one is instant; anything else is loaded from disk on first use.",
  loraScale:
    "Adapter strength. Safe value: 1.0.",
  bungeeToggle:
    "Turns Bungee pitch-shifting on for this lane, applied during the Bungee stage before " +
    "re-encoding. Safe value: off.",
  bungeePreset:
    "Module preset — recalls just this Bungee slot's settings. Undrawn in the handoff; the level " +
    "exists in the frozen preset contract (spec §9.3, §6.3's level enum), so it needs a place to live.",
  filmCkpt:
    "Which FiLM checkpoint this lane uses. Server default is whatever /info reports as the film " +
    "default; anything else is loaded from the film model root on first use.",
  modulePresetSave:
    "Saves this module's current settings, on/off state included, as a module preset -- under the " +
    "selected name, or a new one you are asked for. Recall applies to the active lane only.",
  modulePresetDelete:
    "Deletes the selected module preset from the server. The lane's current settings are not changed.",
```

Then regenerate the committed file:

```bash
cd latent-forge && npm run help:extract
```

Expected: `extract_help: wrote 100 strings (80 extracted, 14 rewritten, 20 new) to
.../latent-forge/src/lib/help/strings.ts` (M1 T14 left 87 = 80 extracted + 7 new; this task adds
13 more `NEW_STRINGS` entries — see Open Questions for why `latchToggle`/`bungeeToggle` are among
them, and why the module-preset SAVE/DEL buttons and the FILM CKPT select each got a string).

Then, in `latent-forge/src/lib/help/__tests__/strings.test.ts` (M1 T14, M1 plan line 7501), update
the total so M1's own suite stays green after this task: the test title
`"has the 80 handoff strings plus the 7 new controls"` becomes
`"has the 80 handoff strings plus the 20 new controls"`, and `expect(Object.keys(HELP)).toHaveLength(87);`
becomes `expect(Object.keys(HELP)).toHaveLength(100);`. Nothing else in that file changes. (Tasks 4,
5, 6 and 9 each move this same line again, to 104, 107, 109 and finally 112.)

- [ ] **Step 5: Write the component**

`latent-forge/src/ui/modules/LaneChain.svelte` (replacing M1's stub in full):

```svelte
<script lang="ts">
  // Spec §5.5. Every field below mutates arrangement.lanes[view.activeLane].chain IN PLACE -- it
  // is a $state-proxied object (M5's defaultLanes() seeds it from structuredClone(CHAIN_DEFAULTS)).
  // Never do `lane.chain = {...}` or capture `const chain = lane.chain` and mutate the capture only
  // -- both silently stop being reactive. M5's lane-header chain dot
  // (docs/superpowers/plans/.../m5-timeline-fidelity.md:2546) already derives off this same object,
  // so nothing here needs to "light" anything itself.
  import { arrangement } from "../../lib/stores/arrangement.svelte";
  import { view } from "../../lib/stores/view.svelte";
  import { forgeApi } from "../../lib/forge/api";
  import { fetchAdapters, fetchFilmCkpts, fetchSlots, type SlotEntry } from "../../lib/forge/models";
  // AdapterEntry is declared in modelOptions.ts; models.ts only `import type`s it (M1 plan 5050, 5099).
  import type { AdapterEntry } from "../topbar/modelOptions";
  import { fetchLatchHeads, type LatchHeadInfo } from "../../lib/chains/latch";
  import { applyModulePreset, modulePresetPayload, type ModuleLevel } from "../../lib/chains/modulePresets";
  import { HELP } from "../../lib/help/strings";
  import { dragScale } from "../../lib/actions/dragScale";

  const chain = $derived(arrangement.lanes[view.activeLane].chain);

  let heads = $state<Record<string, LatchHeadInfo>>({});
  let filmCkpts = $state<AdapterEntry[]>([]);
  let filmDefaultCkpt = $state<string | null>(null);
  let residentSlots = $state<SlotEntry[]>([]);
  let loraOptions = $state<AdapterEntry[]>([]);
  let presetNames = $state<Record<ModuleLevel, string[]>>({ latch: [], film: [], lora: [], bungee: [] });
  let presetPicked = $state<Record<ModuleLevel, string>>({ latch: "", film: "", lora: "", bungee: "" });

  const LEVELS: readonly ModuleLevel[] = ["latch", "film", "lora", "bungee"];

  // Every fetch .catch()es: an unmounted root, a dead server or (in jsdom) a relative URL must
  // leave the control empty, not raise an unhandled rejection.
  $effect(() => {
    fetchLatchHeads().then((h) => (heads = h)).catch(() => {});
    fetchFilmCkpts().then((c) => (filmCkpts = c)).catch(() => {});
    forgeApi.info().then((info) => {
      const fd = (info as { film_default?: { ckpt: string | null } }).film_default;
      filmDefaultCkpt = fd?.ckpt ?? null;
    }).catch(() => {});
    fetchSlots()
      .then(async (s) => {
        residentSlots = s.slots;
        const resident: AdapterEntry[] = s.slots.map((sl) => ({ path: sl.path, name: sl.label, label: sl.label, family: sl.family }));
        const a = await fetchAdapters().catch(() => [] as AdapterEntry[]);
        const seen = new Set(resident.map((r) => r.path));
        loraOptions = [...resident, ...a.filter((x) => !seen.has(x.path))];
      })
      .catch(() => {});
    for (const level of LEVELS) {
      forgeApi.presets(level).then((r) => (presetNames[level] = r.names)).catch(() => {});
    }
  });

  // --- LatCH slot helpers (spec §5.5) ---------------------------------------------------------
  function targetRange(i: number): { min: number; max: number; step: number } {
    const slot = chain.slots[i];
    if (slot.kind === "beat_grid") return { min: 60, max: 200, step: 1 };   // "a BPM slider 60–200"
    const h = heads[slot.head];
    const min = h?.slider_min ?? 0;
    const max = h?.slider_max ?? 1;
    return { min, max, step: (max - min) / 200 || 0.01 };
  }

  /** New head: kind falls back to the head's first supported kind, value starts at value_default. */
  function setHead(i: number, name: string) {
    const slot = chain.slots[i];
    slot.head = name;
    const h = heads[name];
    if (!h) return;   // "none"
    if (!h.supports_kinds.includes(slot.kind)) slot.kind = h.supports_kinds[0] ?? "constant";
    slot.value = slot.kind === "beat_grid"
      ? Math.max(60, Math.min(200, Math.round(arrangement.bpm)))
      : h.value_default;
  }

  function setKind(i: number, kind: string) {
    const slot = chain.slots[i];
    const was = slot.kind;
    slot.kind = kind;
    if (kind === "beat_grid" && was !== "beat_grid") slot.value = Math.max(60, Math.min(200, Math.round(arrangement.bpm)));
    else if (kind !== "beat_grid" && was === "beat_grid") slot.value = heads[slot.head]?.value_default ?? slot.value;
  }

  // --- LORA / DORA ----------------------------------------------------------------------------
  function setLoraModel(path: string) {
    chain.lora.ckpt_path = path || null;
    // a resident /slots entry also records its slot index, so switching to it is the cheap path
    chain.lora.slot = residentSlots.find((s) => s.path === path)?.index ?? null;
  }

  // --- module presets (spec §9.3: recall applies to the ACTIVE lane) -----------------------------
  async function recallModulePreset(level: ModuleLevel, name: string) {
    presetPicked[level] = name;
    if (!name) return;
    try {
      const payload = await forgeApi.preset(level, name);
      applyModulePreset(chain, level, payload);
    } catch {
      // a preset deleted elsewhere, or a dead server: the lane keeps what it has
    }
  }

  async function saveModulePreset(level: ModuleLevel) {
    let name = presetPicked[level];
    if (!name) {
      const typed = window.prompt(`${level} preset name:`, "");
      if (!typed) return;
      name = typed;
    }
    try {
      await forgeApi.savePreset(level, name, modulePresetPayload(chain, level));
      if (!presetNames[level].includes(name)) presetNames[level] = [...presetNames[level], name];
      presetPicked[level] = name;
    } catch {
      // the server's refusal (bad name, disk) is surfaced by forgeApi's own error; nothing to undo
    }
  }

  async function deleteModulePreset(level: ModuleLevel) {
    const name = presetPicked[level];
    if (!name) return;
    try {
      await forgeApi.deletePreset(level, name);
      presetNames[level] = presetNames[level].filter((n) => n !== name);
      presetPicked[level] = "";
    } catch {
      // leave the list as it is if the server refused
    }
  }
</script>

{#snippet presetControls(level: ModuleLevel, label: string, help: string)}
  <select aria-label="{label} preset" data-help={help} value={presetPicked[level]}
    onchange={(e) => recallModulePreset(level, (e.currentTarget as HTMLSelectElement).value)}>
    <option value=""></option>
    {#each presetNames[level] as name (name)}<option value={name}>{name}</option>{/each}
  </select>
  <button data-testid="{level}-preset-save" data-help={HELP.modulePresetSave} onclick={() => saveModulePreset(level)}>SAVE</button>
  <button data-testid="{level}-preset-delete" data-help={HELP.modulePresetDelete}
    disabled={!presetPicked[level]} onclick={() => deleteModulePreset(level)}>DEL</button>
{/snippet}

<div class="lane-chain">
  <p class="hint">latent chain for the selected lane — click another lane header to switch</p>

  <!-- LATCH GUIDANCE -->
  <div class="row">
    <button data-testid="latch-toggle" class:on={chain.latch_on} data-help={HELP.latchToggle}
      onclick={() => (chain.latch_on = !chain.latch_on)}>{chain.latch_on ? "ON" : "OFF"}</button>
    <span>LATCH GUIDANCE</span>
    {@render presetControls("latch", "LATCH GUIDANCE", HELP.modulePreset)}
  </div>

  {#each [0, 1] as i (i)}
    {@const range = targetRange(i)}
    <fieldset class="slot">
      <select aria-label="HEAD — slot {i + 1}" data-help={HELP.latchHead}
        value={chain.slots[i].head} onchange={(e) => setHead(i, (e.currentTarget as HTMLSelectElement).value)}>
        <option value="none">none</option>
        {#each Object.values(heads) as h (h.name)}
          <option value={h.name}>{h.name} · {h.family}{h.health !== "ok" ? " ⚠" : ""}</option>
        {/each}
      </select>
      <select aria-label="KIND — slot {i + 1}" data-help={HELP.latchTargetKind}
        value={chain.slots[i].kind} onchange={(e) => setKind(i, (e.currentTarget as HTMLSelectElement).value)}>
        {#each (heads[chain.slots[i].head]?.supports_kinds ?? ["constant"]) as k (k)}<option value={k}>{k}</option>{/each}
      </select>
      <!-- min/max/step BEFORE value: an <input type=range> clamps value to the range it has when
           value is applied, so the range attributes must already be the head's. -->
      <label>TARGET{chain.slots[i].kind === "beat_grid" ? " (BPM)" : ""}
        <input type="range" aria-label="TARGET — slot {i + 1}" data-help={HELP.latchTargetValue}
          min={range.min} max={range.max} step={range.step}
          value={chain.slots[i].value} oninput={(e) => (chain.slots[i].value = Number((e.currentTarget as HTMLInputElement).value))} />
      </label>
      <label>WEIGHT — slot {i + 1}
        <input type="range" aria-label="WEIGHT — slot {i + 1}" data-help={HELP.latchWeight} min="0" max="50" step="0.1"
          value={chain.slots[i].weight} oninput={(e) => (chain.slots[i].weight = Number((e.currentTarget as HTMLInputElement).value))} />
      </label>
      <label>START %
        <input type="range" aria-label="START % — slot {i + 1}" data-help={HELP.latchStartPct} min="0" max="1" step="0.01"
          value={chain.slots[i].start_pct} oninput={(e) => (chain.slots[i].start_pct = Number((e.currentTarget as HTMLInputElement).value))} />
      </label>
      <label>END %
        <input type="range" aria-label="END % — slot {i + 1}" data-help={HELP.latchEndPct} min="0" max="1" step="0.01"
          value={chain.slots[i].end_pct} oninput={(e) => (chain.slots[i].end_pct = Number((e.currentTarget as HTMLInputElement).value))} />
      </label>
    </fieldset>
  {/each}

  <p class="section">GUIDANCE HYPERPARAMETERS</p>
  <label>ρ VARIANCE
    <input type="range" aria-label="ρ VARIANCE" data-help={HELP.latchRho} min="0" max="30" step="0.1"
      value={chain.hparams.rho} oninput={(e) => (chain.hparams.rho = Number((e.currentTarget as HTMLInputElement).value))} />
  </label>
  <label>μ MEAN
    <input type="range" aria-label="μ MEAN" data-help={HELP.latchMu} min="0" max="30" step="0.1"
      value={chain.hparams.mu} oninput={(e) => (chain.hparams.mu = Number((e.currentTarget as HTMLInputElement).value))} />
  </label>
  <label>γ NOISE
    <input type="range" aria-label="γ NOISE" data-help={HELP.latchGamma} min="0" max="20" step="0.05"
      value={chain.hparams.gamma} oninput={(e) => (chain.hparams.gamma = Number((e.currentTarget as HTMLInputElement).value))} />
  </label>
  <label>MEAN ITER
    <input type="range" aria-label="MEAN ITER" data-help={HELP.latchMeanIter} min="1" max="80" step="1"
      value={chain.hparams.n_iter} oninput={(e) => (chain.hparams.n_iter = Number((e.currentTarget as HTMLInputElement).value))} />
  </label>
  <button data-help={HELP.latchLogNorms} class:on={chain.hparams.log_norms}
    onclick={() => (chain.hparams.log_norms = !chain.hparams.log_norms)}>LOG GRADIENT NORMS</button>

  <!-- FILM -->
  <div class="row">
    <button data-testid="film-toggle" class:on={chain.film_on} data-help={HELP.filmToggle}
      onclick={() => (chain.film_on = !chain.film_on)}>{chain.film_on ? "ON" : "OFF"}</button>
    <span>FILM</span>
    {@render presetControls("film", "FILM", HELP.filmPreset)}
  </div>
  <select aria-label="FILM CKPT" data-help={HELP.filmCkpt} value={chain.film.ckpt ?? ""}
    onchange={(e) => (chain.film.ckpt = (e.currentTarget as HTMLSelectElement).value || null)}>
    <option value="">server default{filmDefaultCkpt ? ` (${filmDefaultCkpt})` : ""}</option>
    {#each filmCkpts as c (c.path)}<option value={c.path}>{c.label || c.name}</option>{/each}
  </select>
  <label>FILM SCALE
    <input type="range" aria-label="FILM SCALE" data-help={HELP.filmScale} min="0" max="2" step="0.05"
      value={chain.film.gain} oninput={(e) => (chain.film.gain = Number((e.currentTarget as HTMLInputElement).value))} />
  </label>
  <label>TARGET
    <input type="range" aria-label="FILM TARGET" data-help={HELP.filmTarget} min="0" max="16" step="0.1"
      value={chain.film.value} oninput={(e) => (chain.film.value = Number((e.currentTarget as HTMLInputElement).value))} />
  </label>

  <!-- LORA / DORA -->
  <div class="row">
    <button data-testid="lora-toggle" class:on={chain.lora_on} data-help={HELP.loraToggle}
      onclick={() => (chain.lora_on = !chain.lora_on)}>{chain.lora_on ? "ON" : "OFF"}</button>
    <span>LORA / DORA</span>
    {@render presetControls("lora", "LORA / DORA", HELP.loraPreset)}
  </div>
  <!-- An explicit "none": without it a null ckpt_path would display as the first adapter. -->
  <select aria-label="LORA / DORA MODEL" data-help={HELP.loraModel} value={chain.lora.ckpt_path ?? ""}
    onchange={(e) => setLoraModel((e.currentTarget as HTMLSelectElement).value)}>
    <option value="">none</option>
    {#each loraOptions as o (o.path)}<option value={o.path}>{o.label || o.name}</option>{/each}
  </select>
  <label>LORA / DORA SCALE
    <input type="range" aria-label="LORA / DORA SCALE" data-help={HELP.loraScale} min="0" max="1" step="0.01"
      value={chain.lora.strength} oninput={(e) => (chain.lora.strength = Number((e.currentTarget as HTMLInputElement).value))} />
  </label>

  <!-- BUNGEE -->
  <div class="row">
    <button data-testid="bungee-toggle" class:on={chain.bungee_on} data-help={HELP.bungeeToggle}
      onclick={() => (chain.bungee_on = !chain.bungee_on)}>{chain.bungee_on ? "ON" : "OFF"}</button>
    <span>BUNGEE STRETCH / PITCH</span>
  </div>
  <div class="row">
    {@render presetControls("bungee", "BUNGEE", HELP.bungeePreset)}
  </div>
  <label>SEMITONES
    <input type="number" step="0.5" aria-label="SEMITONES" data-help={HELP.bungeeSemitones}
      value={chain.semitones}
      use:dragScale={{ min: -24, max: 24, value: chain.semitones, onValue: (v) => (chain.semitones = v) }}
      onchange={(e) => (chain.semitones = Number((e.currentTarget as HTMLInputElement).value))} />
  </label>
</div>

<style>
  .lane-chain { display: flex; flex-direction: column; gap: 6px; padding: 6px 10px 8px; }
  .row { display: flex; align-items: center; gap: 5px; }
  .hint, .section { margin: 0; font-size: 10px; color: var(--text-dim); }
  button.on { background: var(--turq-strong); color: white; border-color: var(--turq-strong); }
  select, input, button { background: var(--panel2); border: 1px solid var(--border); color: var(--text); font-size: 10px; }
</style>
```

- [ ] **Step 6: Run it, expect pass**

```bash
cd latent-forge && npx vitest run src/lib/forge/__tests__/models.test.ts src/lib/chains/__tests__/modulePresets.test.ts src/ui/modules/__tests__/LaneChain.component.test.ts && npx vitest run src/lib/help && npm run check
```

Expected: `Test Files  3 passed (3)` / `Tests  26 passed (26)` (5 in `models.test.ts`, 3 in
`modulePresets.test.ts`, 18 in `LaneChain.component.test.ts`); then M1's own `src/lib/help` suite
passes with the updated total of 100; then `svelte-check found 0 errors and 0 warnings`.

- [ ] **Step 7: Commit**

```bash
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M7 T2: LANE CHAIN (spec 5.5) -- LatCH/FiLM/LoRA/Bungee wired through arrangement.lanes[activeLane].chain in place, module presets recall/SAVE/DEL on the active lane, fetchFilmCkpts/fetchSlots added, jest-dom registered, 13 new HELP strings (total 100)"
```

---

### Task 3: `src/lib/mix/mixMath.ts` + `src/lib/mix/signalPath.ts`, plus `arrangement.mix`/`.master`

**WHY.** MIX ORDER and the SIGNAL PATH are the two pieces of math the MIX + SIGNAL PATH tab (Task
5) needs and neither belongs in a component: which pairs feed which node is a pure function of
`MixSpec.order`, and which of the nine §8.1 stages light up is a pure function of the lanes' chains,
the overlap count, and the mix/master state. This task also lands the two store fields ("Names both
writers inherit" in the M7 brief) that both LaneChain-adjacent modules and Writer B's session
serialiser read: `arrangement.mix`/`.master`, seeded from M1's own frozen defaults.

**Files:**
- Create: `latent-forge/src/lib/mix/mixMath.ts`, `latent-forge/src/lib/mix/__tests__/mixMath.test.ts`
- Create: `latent-forge/src/lib/mix/signalPath.ts`, `latent-forge/src/lib/mix/__tests__/signalPath.test.ts`
- Modify: `latent-forge/src/lib/stores/arrangement.svelte.ts` (M5, current file — add two fields
  and one read-only method, nothing else changes)
- Create: `latent-forge/src/lib/stores/__tests__/arrangementMixMaster.test.ts`

**Interfaces:**
- Consumes from `src/lib/forge/types.ts` (M1 T3): `MixSpec` (`order: "tree"|"cascade"|"quad";
  nodes: {M1,M2,MX: {interp, t}}; quad_weights: [number,number,number,number]`), `MasterChain`
  (`latch_on, head, gain, norm_on`), `LaneChain`.
- Consumes from `src/lib/forge/defaults.ts` (M1 T4): `MIX_DEFAULT`, `MASTER_DEFAULT`.
- Consumes from `src/lib/chains/latch.ts` (Task 1): `chainIsIdle(chain, hasA2AClip): boolean` — the
  exact function `signalPath.ts` calls for S4's idle note, so the string is derived once, not
  reinvented here.
- Consumes the current `src/lib/stores/arrangement.svelte.ts` (M5, verified at
  `docs/superpowers/plans/2026-09-17-latent-forge-m5-timeline-fidelity.md:293-299,341-354`):
  the class is `ArrangementStore`, its current import block is
  `import { A2A_ENVELOPE_DEFAULT, BASE_DEFAULTS, CHAIN_DEFAULTS, cloneRenderSettings,
  OVERLAP_DEFAULT } from "../forge/defaults"; import type { AudioRef, Envelope, ForgeClip,
  ForgeLane, OverlapParams } from "../forge/types";`, its `lanes = $state<ForgeLane[]>
  (defaultLanes())` field already carries `chain: LaneChain` per lane, and `overlaps` is a
  `$derived.by` over `clips` — **untouched by this task**.
- Produces, from `mixMath.ts`: `interface MixTreeNode { id: "M1"|"M2"|"MX"; a: string; b: string }`,
  `mixTree(order: MixSpec["order"]): MixTreeNode[] | null` (`null` for `"quad"`, which has no
  intermediate nodes), `isQuad(order: MixSpec["order"]): boolean` (Task 5 imports this by name, per
  the brief's own "per isQuad" wording), `normalizedQuadWeights(weights: readonly
  [number,number,number,number]): [number,number,number,number]` (all-zero → equal 0.25 each, per
  §8.1 S7's own fallback rule, restated here for the UI preview only — the server does the real
  mix).
- Produces, from `signalPath.ts`: `interface SignalPathClip { lane: 0|1|2|3; isCropAudio: boolean;
  needsStretch: boolean; a2aOn: boolean }`, `interface SignalPathInput { lanes: Array<{index:
  0|1|2|3; chain: LaneChain}>; clips: SignalPathClip[]; overlapCount: number; mix: MixSpec; master:
  MasterChain }`, `interface SignalPathStage { n: number; label: string; lit: boolean; note: string
  }`, `buildSignalPath(input: SignalPathInput): SignalPathStage[]` (exactly 9 stages, §8.1's own
  labels, in order).
- Produces, on `arrangement` (Modify): two new fields, `mix = $state<MixSpec>
  (structuredClone(MIX_DEFAULT))` and `master = $state<MasterChain>
  (structuredClone(MASTER_DEFAULT))`, and one method, **`peekOverlapParams(key: string):
  OverlapParams`** — the live entry if `overlapParams`/`setOverlapParams` has already seeded one,
  otherwise a fresh `OVERLAP_DEFAULT`-shaped copy that is **not stored**. It never writes, so it is
  the only overlap reader allowed inside a `$derived`, a template or a `$derived.by` snapshot
  (Global Constraint #8: M5's `overlapParams` seeds on first read, and a write during a derived
  throws `state_unsafe_mutation`, verified on Svelte 5.57.0). Nothing else in the file changes.

- [ ] **Step 1: Write the failing tests**

`latent-forge/src/lib/mix/__tests__/mixMath.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { isQuad, mixTree, normalizedQuadWeights } from "../mixMath";

describe("mixTree (spec §4.5/§8.1 S7)", () => {
  it("tree: M1=(L1,L2), M2=(L3,L4), MX=(M1,M2)", () => {
    expect(mixTree("tree")).toEqual([
      { id: "M1", a: "L1", b: "L2" },
      { id: "M2", a: "L3", b: "L4" },
      { id: "MX", a: "M1", b: "M2" },
    ]);
  });

  it("cascade: M1=(L1,L2), M2=(M1,L3), MX=(M2,L4)", () => {
    expect(mixTree("cascade")).toEqual([
      { id: "M1", a: "L1", b: "L2" },
      { id: "M2", a: "M1", b: "L3" },
      { id: "MX", a: "M2", b: "L4" },
    ]);
  });

  it("quad has no intermediate node tree", () => {
    expect(mixTree("quad")).toBeNull();
  });
});

describe("isQuad", () => {
  it("is true only for the weighted 4-way order", () => {
    expect(isQuad("quad")).toBe(true);
    expect(isQuad("tree")).toBe(false);
    expect(isQuad("cascade")).toBe(false);
  });
});

describe("normalizedQuadWeights (spec §8.1 S7's own fallback)", () => {
  it("normalises to fractions summing to 1", () => {
    expect(normalizedQuadWeights([1, 1, 1, 1])).toEqual([0.25, 0.25, 0.25, 0.25]);
    expect(normalizedQuadWeights([2, 2, 0, 0])).toEqual([0.5, 0.5, 0, 0]);
  });

  it("falls back to equal weights when every weight is zero", () => {
    expect(normalizedQuadWeights([0, 0, 0, 0])).toEqual([0.25, 0.25, 0.25, 0.25]);
  });
});
```

`latent-forge/src/lib/mix/__tests__/signalPath.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { CHAIN_DEFAULTS, MASTER_DEFAULT, MIX_DEFAULT } from "../../forge/defaults";
import { buildSignalPath, type SignalPathInput } from "../signalPath";

function baseInput(): SignalPathInput {
  return {
    lanes: [0, 1, 2, 3].map((i) => ({ index: i as 0 | 1 | 2 | 3, chain: structuredClone(CHAIN_DEFAULTS) })),
    clips: [],
    overlapCount: 0,
    mix: structuredClone(MIX_DEFAULT),
    master: structuredClone(MASTER_DEFAULT),
  };
}

describe("buildSignalPath — the nine §8.1 stages, in order", () => {
  it("returns exactly the nine spec labels, numbered 1-9", () => {
    const stages = buildSignalPath(baseInput());
    expect(stages.map((s) => s.label)).toEqual([
      "DECODE latent → audio", "BUNGEE stretch / pitch", "ENCODE audio → latent",
      "LANE CHAINS", "A2A RE-NOISE", "INPAINT OVERLAPS", "MIX", "MASTER CHAIN",
      "DECODE latent → audio",
    ]);
    expect(stages.map((s) => s.n)).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9]);
  });

  it("dims everything except MIX and the final DECODE when nothing is on and there are no clips", () => {
    const stages = buildSignalPath(baseInput());
    expect(stages[0].lit).toBe(false); // S1 DECODE: no crop-ref clips
    expect(stages[1].lit).toBe(false); // S2 BUNGEE
    expect(stages[3].lit).toBe(false); // S4 LANE CHAINS
    expect(stages[4].lit).toBe(false); // S5 A2A
    expect(stages[5].lit).toBe(false); // S6 INPAINT OVERLAPS
  });

  it("lights S1 DECODE when a clip's audio is a crop ref", () => {
    const input = baseInput();
    input.clips = [{ lane: 0, isCropAudio: true, needsStretch: false, a2aOn: false }];
    expect(buildSignalPath(input)[0].lit).toBe(true);
  });

  it("lights S2 BUNGEE from either a lane's bungee_on or a clip needing stretch", () => {
    const byChain = baseInput();
    byChain.lanes[0].chain.bungee_on = true;
    expect(buildSignalPath(byChain)[1].lit).toBe(true);

    const byStretch = baseInput();
    byStretch.clips = [{ lane: 0, isCropAudio: false, needsStretch: true, a2aOn: false }];
    expect(buildSignalPath(byStretch)[1].lit).toBe(true);
  });

  it("lights S4 LANE CHAINS when any lane has an active feature, and notes idle lanes exactly (spec's own string)", () => {
    const input = baseInput();
    input.lanes[0].chain.latch_on = true;
    // no A2A clip in lane 0 -> idle
    const stages = buildSignalPath(input);
    expect(stages[3].lit).toBe(true);
    expect(stages[3].note).toBe("chain idle — no A2A clip in lane");
  });

  it("clears S4's idle note once the active lane has an A2A clip", () => {
    const input = baseInput();
    input.lanes[0].chain.latch_on = true;
    input.clips = [{ lane: 0, isCropAudio: false, needsStretch: false, a2aOn: true }];
    expect(buildSignalPath(input)[3].note).toBe("");
  });

  it("lights S5 A2A RE-NOISE exactly when some clip has A2A on", () => {
    const input = baseInput();
    input.clips = [{ lane: 2, isCropAudio: false, needsStretch: false, a2aOn: true }];
    expect(buildSignalPath(input)[4].lit).toBe(true);
  });

  it("lights S6 INPAINT OVERLAPS exactly when overlapCount > 0", () => {
    const input = baseInput();
    input.overlapCount = 1;
    expect(buildSignalPath(input)[5].lit).toBe(true);
  });

  it("S7 MIX's note names the current order using the drawing's own option text", () => {
    const tree = baseInput();
    expect(buildSignalPath(tree)[6].note).toBe("(1+2) + (3+4)");
    const cascade = baseInput(); cascade.mix.order = "cascade";
    expect(buildSignalPath(cascade)[6].note).toBe("((1+2)+3)+4");
    const quad = baseInput(); quad.mix.order = "quad";
    expect(buildSignalPath(quad)[6].note).toBe("weighted 4-way (lerp only)");
  });

  it("lights S8 MASTER CHAIN when either latch_on or norm_on is set (norm_on defaults true)", () => {
    const input = baseInput(); // MASTER_DEFAULT.norm_on === true
    expect(buildSignalPath(input)[7].lit).toBe(true);
    const bothOff = baseInput();
    bothOff.master = { ...bothOff.master, latch_on: false, norm_on: false };
    expect(buildSignalPath(bothOff)[7].lit).toBe(false);
  });
});
```

`latent-forge/src/lib/stores/__tests__/arrangementMixMaster.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { MASTER_DEFAULT, MIX_DEFAULT, OVERLAP_DEFAULT } from "../../forge/defaults";
import { arrangement } from "../arrangement.svelte";

describe("arrangement.mix / .master (M7 T3)", () => {
  it("are seeded from M1's frozen defaults, as copies rather than the constants themselves", () => {
    expect(arrangement.mix).toEqual(MIX_DEFAULT);
    expect(arrangement.master).toEqual(MASTER_DEFAULT);
    arrangement.master.gain = 99;
    expect(MASTER_DEFAULT.gain).toBe(64);
    arrangement.master.gain = 64;
  });
});

describe("arrangement.peekOverlapParams (non-seeding; Global Constraint #8)", () => {
  it("returns an unstored default-shaped copy until the key is seeded, then the live entry", () => {
    const key = "peek-a-peek-b";
    const first = arrangement.peekOverlapParams(key);
    expect(first.steps).toBe(OVERLAP_DEFAULT.steps);
    expect(first.chroma_xfade).toBe(OVERLAP_DEFAULT.chroma_xfade);
    // not stored: two peeks are two different objects, and mutating one reaches nothing
    expect(arrangement.peekOverlapParams(key)).not.toBe(first);
    first.steps = 99;
    expect(arrangement.peekOverlapParams(key).steps).toBe(OVERLAP_DEFAULT.steps);
    // once a write seeds it, peek hands back the SAME live entry overlapParams does
    arrangement.setOverlapParams(key, { steps: 40 });
    expect(arrangement.peekOverlapParams(key)).toBe(arrangement.overlapParams(key));
    expect(arrangement.peekOverlapParams(key).steps).toBe(40);
  });
});
```

- [ ] **Step 2: Run it, expect failure**

```bash
cd latent-forge && npx vitest run src/lib/mix/__tests__/mixMath.test.ts src/lib/mix/__tests__/signalPath.test.ts src/lib/stores/__tests__/arrangementMixMaster.test.ts
```

Expected: `Failed to resolve import "../mixMath"` and `"../signalPath"`; `arrangementMixMaster.test.ts`
fails on `arrangement.mix` being `undefined` and `peekOverlapParams` not being a function.

- [ ] **Step 3: Implement**

`latent-forge/src/lib/mix/mixMath.ts`:

```ts
// Spec §4.5 MIX ORDER, §8.1 S7 MIX. Which pairs feed which node is fixed by `order`; each node's
// own {interp, t} lives on MixSpec.nodes and is read directly by the component -- this file only
// describes the WIRING between lanes and nodes, and the quad-weight normalisation used for the
// client-side preview (the server does the real mix, spec §8.1 S7).

import type { MixSpec } from "../forge/types";

export interface MixTreeNode {
  id: "M1" | "M2" | "MX";
  a: string; // "L1".."L4" or another node's id
  b: string;
}

export function mixTree(order: MixSpec["order"]): MixTreeNode[] | null {
  if (order === "quad") return null;
  if (order === "tree") {
    return [
      { id: "M1", a: "L1", b: "L2" },
      { id: "M2", a: "L3", b: "L4" },
      { id: "MX", a: "M1", b: "M2" },
    ];
  }
  return [ // cascade
    { id: "M1", a: "L1", b: "L2" },
    { id: "M2", a: "M1", b: "L3" },
    { id: "MX", a: "M2", b: "L4" },
  ];
}

export function isQuad(order: MixSpec["order"]): boolean {
  return order === "quad";
}

export function normalizedQuadWeights(weights: readonly [number, number, number, number]): [number, number, number, number] {
  const sum = weights.reduce((s, w) => s + w, 0);
  if (sum <= 0) return [0.25, 0.25, 0.25, 0.25];
  return weights.map((w) => w / sum) as [number, number, number, number];
}
```

`latent-forge/src/lib/mix/signalPath.ts`:

```ts
// Spec §8.1's nine stages, rendered live in the MIX + SIGNAL PATH tab. This is a CLIENT-SIDE
// PREVIEW, not the ground truth -- the real per-stage on/off comes back from a commit job's
// meta.stages (spec §6.9), which does not exist until M9 wires the button. Until then this
// estimates from what is currently on the timeline, same spirit as M1's litModules() estimating
// module dots before their stores existed.

import { chainIsIdle } from "../chains/latch";
import type { LaneChain, MasterChain, MixSpec } from "../forge/types";

export interface SignalPathClip {
  lane: 0 | 1 | 2 | 3;
  isCropAudio: boolean;   // this clip's AudioRef.kind === "crop" -> S1 decodes it
  needsStretch: boolean;  // native_bpm differs from the project tempo, or detune_cents !== 0
  a2aOn: boolean;         // clip.a2a?.on
}

export interface SignalPathInput {
  lanes: Array<{ index: 0 | 1 | 2 | 3; chain: LaneChain }>;
  clips: SignalPathClip[];
  overlapCount: number;
  mix: MixSpec;
  master: MasterChain;
}

export interface SignalPathStage {
  n: number;
  label: string;
  lit: boolean;
  note: string;
}

const MIX_ORDER_NOTE: Record<MixSpec["order"], string> = {
  tree: "(1+2) + (3+4)",
  cascade: "((1+2)+3)+4",
  quad: "weighted 4-way (lerp only)",
};

function chainActive(chain: LaneChain): boolean {
  return chain.latch_on || chain.film_on || chain.lora_on || chain.bungee_on;
}

export function buildSignalPath(input: SignalPathInput): SignalPathStage[] {
  const anyCrop = input.clips.some((c) => c.isCropAudio);
  const anyStretch = input.clips.some((c) => c.needsStretch) || input.lanes.some((l) => l.chain.bungee_on);
  const anyChainOn = input.lanes.some((l) => chainActive(l.chain));
  const anyA2A = input.clips.some((c) => c.a2aOn);

  // S4's idle note: any lane whose chain is active but whose OWN clips have no A2A on.
  const idleLane = input.lanes.find((l) => {
    if (!chainActive(l.chain)) return false;
    const hasA2AInLane = input.clips.some((c) => c.lane === l.index && c.a2aOn);
    return chainIsIdle(l.chain, hasA2AInLane);
  });

  return [
    { n: 1, label: "DECODE latent → audio", lit: anyCrop, note: "" },
    { n: 2, label: "BUNGEE stretch / pitch", lit: anyStretch, note: "" },
    { n: 3, label: "ENCODE audio → latent", lit: input.clips.length > 0, note: "" },
    { n: 4, label: "LANE CHAINS", lit: anyChainOn, note: idleLane ? "chain idle — no A2A clip in lane" : "" },
    { n: 5, label: "A2A RE-NOISE", lit: anyA2A, note: "" },
    { n: 6, label: "INPAINT OVERLAPS", lit: input.overlapCount > 0, note: "" },
    { n: 7, label: "MIX", lit: input.clips.length > 0, note: MIX_ORDER_NOTE[input.mix.order] },
    { n: 8, label: "MASTER CHAIN", lit: input.master.latch_on || input.master.norm_on, note: "" },
    { n: 9, label: "DECODE latent → audio", lit: input.clips.length > 0, note: "" },
  ];
}
```

Modify `latent-forge/src/lib/stores/arrangement.svelte.ts` — change only the import block, add
two fields and one method to `ArrangementStore`; nothing else in the file changes:

```ts
import {
  A2A_ENVELOPE_DEFAULT, BASE_DEFAULTS, CHAIN_DEFAULTS, cloneRenderSettings, MASTER_DEFAULT,
  MIX_DEFAULT, OVERLAP_DEFAULT,
} from "../forge/defaults";
import type {
  AudioRef, Envelope, ForgeClip, ForgeLane, MasterChain, MixSpec, OverlapParams,
} from "../forge/types";
```

and, inside `class ArrangementStore`, immediately after `lanes = $state<ForgeLane[]>(defaultLanes());`:

```ts
  /** M7 — spec §4.5/§4.6.5. Seeded from M1's own frozen defaults; nothing else about the store changes. */
  mix = $state<MixSpec>(structuredClone(MIX_DEFAULT));
  master = $state<MasterChain>(structuredClone(MASTER_DEFAULT));
```

and, immediately after the existing `setOverlapParams` method:

```ts
  /**
   * M7 -- a NON-SEEDING read. `overlapParams` writes OVERLAP_DEFAULT into overlapStore on first
   * read, which throws state_unsafe_mutation when it runs inside a $derived or a template. This is
   * the reader for those places: the live entry once one exists, otherwise a fresh default-shaped
   * copy that is NOT stored (mutating it reaches nothing; write through setOverlapParams).
   * Reading `this.overlapStore[key]` still registers the dependency, so a derived that peeked an
   * unseeded key re-runs when setOverlapParams later seeds it.
   */
  peekOverlapParams(key: string): OverlapParams {
    return this.overlapStore[key] ?? {
      ...structuredClone(OVERLAP_DEFAULT),
      render: cloneRenderSettings(OVERLAP_DEFAULT.render),
    };
  }
```

- [ ] **Step 4: Run it, expect pass**

```bash
cd latent-forge && npx vitest run src/lib/mix/__tests__/mixMath.test.ts src/lib/mix/__tests__/signalPath.test.ts src/lib/stores/__tests__/arrangementMixMaster.test.ts
```

Expected: `Test Files  3 passed (3)` / `Tests  18 passed (18)` (6 in `mixMath.test.ts`, 10 in
`signalPath.test.ts`, 2 in `arrangementMixMaster.test.ts`).

Then confirm the modified store file still passes its own, pre-existing suite untouched (this
task's own diff is additive-only — two new fields and one new read-only method, no changed method — so no specific count is
asserted here beyond "still green"; M5's own plan is the source of truth for that file's count):

```bash
cd latent-forge && npx vitest run src/lib/stores/__tests__/arrangement.test.ts && npm run check
```

Expected: every existing test in `arrangement.test.ts` passes unchanged, then `svelte-check found
0 errors and 0 warnings`.

- [ ] **Step 5: Commit**

```bash
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M7 T3: mixMath (node tree wiring, quad normalisation) and signalPath (the nine spec 8.1 stages, live), arrangement.mix/.master fields seeded from M1's frozen defaults, non-seeding peekOverlapParams for derived/template reads"
```

---

### Task 4: `src/ui/modules/MasterChain.svelte` — replacing M1's stub

**WHY.** Spec §4.6.5: LATCH HEAD toggle + head select + GAIN (0-120, default 64), LATENT NORMALISE
(default on), applied to the mixed latent after the lane chains. Simpler than LANE CHAIN — one
toggle, one select, one slider, one toggle — but it writes into `arrangement.master`, the field
Task 3 just added, and it shares the head list with Task 2 via `fetchLatchHeads()` so the two
components don't each re-fetch and re-shape `/info` independently.

**Files:**
- Modify: `latent-forge/src/ui/modules/MasterChain.svelte` (M1 T12 stub,
  `docs/superpowers/plans/2026-09-16-latent-forge-m1-foundation-shell.md:6592-6616`, replaced whole)
- Modify: `docs/latent-forge/extract_help.mjs` (four new `NEW_STRINGS` entries), regenerated
  `latent-forge/src/lib/help/strings.ts`, and `latent-forge/src/lib/help/__tests__/strings.test.ts`
  (total 100 → 104)
- Create: `latent-forge/src/ui/modules/__tests__/MasterChain.component.test.ts`

**Interfaces:**
- Consumes from `src/lib/forge/types.ts` (M1 T3): `MasterChain { latch_on: boolean; head: string;
  gain: number; norm_on: boolean }`.
- Consumes `arrangement.master: MasterChain` from `src/lib/stores/arrangement.svelte.ts` (Task 3,
  this same plan — `$state<MasterChain>(structuredClone(MASTER_DEFAULT))`). Mutated in place,
  same rule as Task 2: `arrangement.master.gain = v`, never `arrangement.master = {...}`.
- Consumes `fetchLatchHeads(): Promise<Record<string, LatchHeadInfo>>` from `src/lib/chains/latch.ts`
  (Task 1) — the SAME function Task 2 uses, so the two head selects can never disagree about what
  `/info.latch_heads` contains.
- Produces the component `MasterChain`, and the expression Task 9 Step 5 wires into
  `RightPaneModules.svelte`'s snapshot: **`master: arrangement.master`** (given verbatim by the
  brief), read inside that step's `$derived`.
- Produces new `HELP` ids: `masterLatchToggle`, `masterLatchHeadLabel`, `masterHead`, `masterGain`.
  (`latentNormalise` already exists, M1 T14, v3:616 — reused on the LATENT NORMALISE label exactly
  as the drawing has it.)

- [ ] **Step 1: Write the failing test**

`latent-forge/src/ui/modules/__tests__/MasterChain.component.test.ts`:

```ts
// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MASTER_DEFAULT } from "../../../lib/forge/defaults";
import { arrangement } from "../../../lib/stores/arrangement.svelte";
import * as latch from "../../../lib/chains/latch";
import MasterChain from "../MasterChain.svelte";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

beforeEach(() => {
  arrangement.master = structuredClone(MASTER_DEFAULT);
  vi.spyOn(latch, "fetchLatchHeads").mockResolvedValue({
    chroma_other: { name: "chroma_other", family: "chroma", default_gain: 2048, health: "ok",
      supports_kinds: ["constant"], slider_min: 0, slider_max: 1, value_default: 0.5 },
  });
});

describe("MASTER CHAIN (spec §4.6.5)", () => {
  it("shows the applied-after-the-lane-chains note verbatim", async () => {
    render(MasterChain);
    expect(await screen.findByText("applied to the mixed latent, after the lane chains")).toBeTruthy();
  });

  it("toggling LATCH HEAD mutates arrangement.master.latch_on in place", async () => {
    render(MasterChain);
    const before = arrangement.master;
    await fireEvent.click(await screen.findByTestId("master-latch-toggle"));
    expect(arrangement.master.latch_on).toBe(true);
    expect(arrangement.master).toBe(before);
  });

  it("the head select lists /info.latch_heads and writes arrangement.master.head", async () => {
    render(MasterChain);
    const select = await screen.findByLabelText("MASTER LATCH HEAD");
    // wait for the fetched option -- the select renders before the heads resolve
    await screen.findByRole("option", { name: "chroma_other · chroma" });
    await fireEvent.change(select, { target: { value: "chroma_other" } });
    expect(arrangement.master.head).toBe("chroma_other");
  });

  it("GAIN drags over 0-120 with default 64", async () => {
    render(MasterChain);
    const gain = await screen.findByLabelText("GAIN");
    expect(gain).toHaveValue("64");
    await fireEvent.input(gain, { target: { value: "80" } });
    expect(arrangement.master.gain).toBe(80);
  });

  it("LATENT NORMALISE defaults on and toggles off", async () => {
    render(MasterChain);
    expect(arrangement.master.norm_on).toBe(true);
    await fireEvent.click(await screen.findByTestId("master-norm-toggle"));
    expect(arrangement.master.norm_on).toBe(false);
  });

  it("attaches HELP.latentNormalise to the existing label, and the three new ids to the new controls", async () => {
    render(MasterChain);
    const { HELP } = await import("../../../lib/help/strings");
    expect((await screen.findByText("LATENT NORMALISE")).getAttribute("data-help")).toBe(HELP.latentNormalise);
    expect((await screen.findByTestId("master-latch-toggle")).getAttribute("data-help")).toBe(HELP.masterLatchToggle);
    expect((await screen.findByLabelText("MASTER LATCH HEAD")).getAttribute("data-help")).toBe(HELP.masterHead);
    expect((await screen.findByLabelText("GAIN")).getAttribute("data-help")).toBe(HELP.masterGain);
  });
});
```

- [ ] **Step 2: Run it, expect failure**

```bash
cd latent-forge && npx vitest run src/ui/modules/__tests__/MasterChain.component.test.ts
```

Expected: every `findBy*` call times out — M1's stub renders only two `<p>` tags and no
interactive controls.

- [ ] **Step 3: Add the new HELP strings**

Add to `docs/latent-forge/extract_help.mjs`'s `NEW_STRINGS` (append after Task 2's thirteen):

```js
  masterLatchToggle:
    "Turns LatCH steering on for the mixed latent, after the lane chains. Safe value: off.",
  masterLatchHeadLabel:
    "Which head steers the mixed latent (spec §8.1 S8 -- the existing /steer math).",
  masterHead:
    "The LatCH head applied to the mix. Uses the same registry as the lane chains' slots.",
  masterGain:
    "How hard the head's gradient is applied to the mixed latent. Safe value: 64.",
```

Regenerate:

```bash
cd latent-forge && npm run help:extract
```

Expected: `extract_help: wrote 104 strings (80 extracted, 14 rewritten, 24 new) to
.../latent-forge/src/lib/help/strings.ts`.

In `latent-forge/src/lib/help/__tests__/strings.test.ts`, move the total Task 2 set:
`it("has the 80 handoff strings plus the 24 new controls", ...)` / `toHaveLength(104)`.

- [ ] **Step 4: Write the component**

`latent-forge/src/ui/modules/MasterChain.svelte` (replacing M1's stub in full):

```svelte
<script lang="ts">
  // Spec §4.6.5, §8.1 S8. arrangement.master is $state -- every control mutates a field on it in
  // place (Task 3 adds the field; this task never reassigns it).
  import { arrangement } from "../../lib/stores/arrangement.svelte";
  import { fetchLatchHeads, type LatchHeadInfo } from "../../lib/chains/latch";
  import { HELP } from "../../lib/help/strings";

  const master = $derived(arrangement.master);
  let heads = $state<Record<string, LatchHeadInfo>>({});

  $effect(() => {
    // .catch: a dead /info leaves the select at "none" rather than an unhandled rejection
    fetchLatchHeads().then((h) => (heads = h)).catch(() => {});
  });
</script>

<div class="master-chain">
  <p class="note">applied to the mixed latent, after the lane chains</p>

  <div class="row">
    <button data-testid="master-latch-toggle" class:on={master.latch_on} data-help={HELP.masterLatchToggle}
      onclick={() => (master.latch_on = !master.latch_on)}>{master.latch_on ? "ON" : "OFF"}</button>
    <span data-help={HELP.masterLatchHeadLabel}>LATCH HEAD</span>
  </div>

  <select aria-label="MASTER LATCH HEAD" data-help={HELP.masterHead} value={master.head}
    onchange={(e) => (master.head = (e.currentTarget as HTMLSelectElement).value)}>
    <option value="none">none</option>
    {#each Object.values(heads) as h (h.name)}
      <option value={h.name}>{h.name} · {h.family}{h.health !== "ok" ? " ⚠" : ""}</option>
    {/each}
  </select>

  <label>GAIN
    <input type="range" aria-label="GAIN" data-help={HELP.masterGain} min="0" max="120"
      value={master.gain} oninput={(e) => (master.gain = Number((e.currentTarget as HTMLInputElement).value))} />
  </label>

  <div class="row">
    <button data-testid="master-norm-toggle" class:on={master.norm_on}
      onclick={() => (master.norm_on = !master.norm_on)}>{master.norm_on ? "ON" : "OFF"}</button>
    <span data-help={HELP.latentNormalise}>LATENT NORMALISE</span>
  </div>
</div>

<style>
  .master-chain { display: flex; flex-direction: column; gap: 6px; padding: 6px 10px 8px; }
  .row { display: flex; align-items: center; gap: 5px; }
  .note { margin: 0; font-size: 10px; color: var(--text-dim); }
  button.on { background: var(--turq-strong); color: white; border-color: var(--turq-strong); }
  select, input, button { background: var(--panel2); border: 1px solid var(--border); color: var(--text); font-size: 10px; }
</style>
```

- [ ] **Step 5: Run it, expect pass**

```bash
cd latent-forge && npx vitest run src/ui/modules/__tests__/MasterChain.component.test.ts && npx vitest run src/lib/help && npm run check
```

Expected: `Test Files  1 passed (1)` / `Tests  6 passed (6)`, then M1's `src/lib/help` suite green
at the new total of 104, then `svelte-check found 0 errors and 0 warnings`.

- [ ] **Step 6: Commit**

```bash
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M7 T4: MASTER CHAIN (spec 4.6.5, 8.1 S8) -- LATCH HEAD toggle/select/GAIN and LATENT NORMALISE wired through arrangement.master in place"
```

---

### Task 5: `src/ui/mix/MixSignalPath.svelte` + the `BottomPane.svelte` mount + Playwright fragment

**WHY.** The last piece: MIX ORDER, the node/quad controls, and the live SIGNAL PATH list, composed
from Task 3's pure `mixMath`/`signalPath` over `arrangement.mix`/`.master`/`.lanes`/`.clips`/
`.overlaps`. The `▸ MIXDOWN` button is UI-only this milestone, same boundary as Writer B's
OVERLAP-INPAINT render button (M1's own stub for OVERLAP-INPAINT says exactly this: "its `▸ INPAINT
OVERLAP` button wired in M9",
`docs/superpowers/plans/2026-09-16-latent-forge-m1-foundation-shell.md:6282`).

**Files:**
- Create: `latent-forge/src/ui/mix/MixSignalPath.svelte`,
  `latent-forge/src/ui/mix/__tests__/MixSignalPath.component.test.ts`
- Modify: `latent-forge/src/ui/shell/BottomPane.svelte` (the `mix` tab body only — same
  `data-region="bottom-tab-body"` edit pattern M4 used for `prompt`, verified at
  `docs/superpowers/plans/2026-09-18-latent-forge-m4-prompt-sigma.md:4666-4686`)
- Modify: `docs/latent-forge/extract_help.mjs` (three new `NEW_STRINGS` entries), regenerated
  `latent-forge/src/lib/help/strings.ts`, and `latent-forge/src/lib/help/__tests__/strings.test.ts`
  (total 104 → 107)
- Create: `latent-forge/tests/chains.spec.ts` (Playwright)

**Interfaces:**
- Consumes from `src/lib/mix/mixMath.ts` (Task 3): `mixTree`, `isQuad`, `normalizedQuadWeights`.
- Consumes from `src/lib/mix/signalPath.ts` (Task 3): `buildSignalPath`, `SignalPathInput`,
  `SignalPathClip`.
- Consumes from `src/lib/stores/arrangement.svelte.ts` (M5 + Task 3): `arrangement.mix: MixSpec`,
  `arrangement.master: MasterChain`, `arrangement.lanes: ForgeLane[]`, `arrangement.clips:
  ForgeClip[]`, `arrangement.overlaps: Overlap[]` (all `$state`/`$derived` on the live singleton —
  mutate `arrangement.mix`/`.master` fields in place, same rule as Tasks 2 and 4).
- Consumes from `src/lib/forge/types.ts` (M1 T3): `ForgeClip.a2a: null | {on: boolean; ...}`,
  `ForgeClip.native_bpm: number | null`, `ForgeClip.detune_cents: number`, `ForgeClip.audio:
  AudioRef` (`audio.kind === "crop"` feeds `SignalPathClip.isCropAudio`).
- Consumes `arrangement.bpm: number` (M5, current file) to derive `needsStretch` per clip
  (`native_bpm !== null && native_bpm !== arrangement.bpm) || detune_cents !== 0`).
- Consumes `HELP` from `src/lib/help/strings.ts` (M1 T14 + this task's own additions): `mixFold`
  (216), `mixOrder`(218), `mixNodeT`(248), `signalPath`(262), `mixExpand`(274), `renderButton`(45,
  reused for both `▸ MIXDOWN` buttons in this tab — see Open Questions) — all six already exist,
  M1 T14. New: `mixQuadWeight`, `mixLerp`, `mixSlerp`.
- Consumes `MIXDOWN_IDLE_LABEL` from `src/ui/topbar/mixdown.ts` (M1 T10,
  `docs/superpowers/plans/2026-09-16-latent-forge-m1-foundation-shell.md:5123` — `"▸ MIXDOWN"`),
  reused verbatim so the two buttons never drift apart in copy.
- Produces the component `MixSignalPath`, mounted at `data-tab-body="mix"` (the same convention
  `PromptSigmaTab.svelte` uses for `data-tab-body="prompt"`, M4 plan:4620) inside
  `BottomPane.svelte`'s existing `data-region="bottom-tab-body"` wrapper.

- [ ] **Step 1: Write the failing tests**

`latent-forge/src/ui/mix/__tests__/MixSignalPath.component.test.ts`:

```ts
// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MASTER_DEFAULT, MIX_DEFAULT } from "../../../lib/forge/defaults";
import { arrangement } from "../../../lib/stores/arrangement.svelte";
import { forgeApi } from "../../../lib/forge/api";
import MixSignalPath from "../MixSignalPath.svelte";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

beforeEach(() => {
  arrangement.mix = structuredClone(MIX_DEFAULT);
  arrangement.master = structuredClone(MASTER_DEFAULT);
  arrangement.clips.splice(0, arrangement.clips.length);
});

describe("MIX ORDER", () => {
  it("defaults to the tree label and shows three node boxes", async () => {
    render(MixSignalPath);
    const select = await screen.findByLabelText("MIX ORDER");
    expect(select).toHaveValue("tree");
    expect(screen.getAllByText("LERP")).toHaveLength(3);
    expect(screen.getAllByText("SLERP")).toHaveLength(3);
  });

  it("switching to quad shows four weight sliders instead of node boxes", async () => {
    render(MixSignalPath);
    const select = await screen.findByLabelText("MIX ORDER");
    await fireEvent.change(select, { target: { value: "quad" } });
    expect(arrangement.mix.order).toBe("quad");
    expect(screen.queryAllByText("LERP")).toHaveLength(0);
    expect(screen.getAllByLabelText(/quad weight/i)).toHaveLength(4);
  });

  it("a node's T slider writes MixSpec.nodes[id].t in place", async () => {
    render(MixSignalPath);
    const t = await screen.findByLabelText("M1 position");
    await fireEvent.input(t, { target: { value: "0.25" } });
    expect(arrangement.mix.nodes.M1.t).toBe(0.25);
  });

  it("LERP/SLERP set a node's interp in place", async () => {
    render(MixSignalPath);
    await fireEvent.click(await screen.findByTestId("m1-lerp"));
    expect(arrangement.mix.nodes.M1.interp).toBe("lerp");
    await fireEvent.click(await screen.findByTestId("m1-slerp"));
    expect(arrangement.mix.nodes.M1.interp).toBe("slerp");
  });
});

describe("fold / expand (spec 4.5's own summary row)", () => {
  it("toggling the fold button switches to the one-line summary, and expand switches back", async () => {
    render(MixSignalPath);
    await fireEvent.click(await screen.findByTestId("mix-fold"));
    expect(screen.queryByLabelText("MIX ORDER")).toBeNull();
    expect(await screen.findByText("MIX + SIGNAL PATH")).toBeTruthy();
    await fireEvent.click(await screen.findByTestId("mix-expand"));
    expect(await screen.findByLabelText("MIX ORDER")).toBeTruthy();
  });
});

describe("SIGNAL PATH", () => {
  it("lists the nine stages live, and lights LANE CHAINS with the idle note when a chain is on with no A2A clip", async () => {
    arrangement.lanes[0].chain.latch_on = true;
    render(MixSignalPath);
    const row = await screen.findByText("LANE CHAINS");
    expect(row.closest("[data-signal-stage]")).toHaveAttribute("data-lit", "true");
    expect(await screen.findByText("chain idle — no A2A clip in lane")).toBeTruthy();
  });
});

describe("▸ MIXDOWN — UI only this milestone", () => {
  it("is clickable and calls no job submission (M9's boundary, same as OVERLAP-INPAINT's render button)", async () => {
    const spy = vi.spyOn(forgeApi, "submitJob");
    render(MixSignalPath);
    await fireEvent.click((await screen.findAllByText("▸ MIXDOWN"))[0]);
    expect(spy).not.toHaveBeenCalled();
  });
});

describe("HELP ids", () => {
  it("attaches the three new mix-control ids", async () => {
    render(MixSignalPath);
    const { HELP } = await import("../../../lib/help/strings");
    await fireEvent.change(await screen.findByLabelText("MIX ORDER"), { target: { value: "quad" } });
    expect((await screen.findAllByLabelText(/quad weight/i))[0].getAttribute("data-help")).toBe(HELP.mixQuadWeight);
    await fireEvent.change(await screen.findByLabelText("MIX ORDER"), { target: { value: "tree" } });
    expect((await screen.findByTestId("m1-lerp")).getAttribute("data-help")).toBe(HELP.mixLerp);
    expect((await screen.findByTestId("m1-slerp")).getAttribute("data-help")).toBe(HELP.mixSlerp);
  });
});
```

`latent-forge/tests/chains.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

// Same testid convention M4's own e2e fragment verified against the real BottomPane.svelte
// (data-testid="bottom-tab-<id>" to click, tests/sampling.spec.ts:beforeEach) -- M1 T14's layout
// spec instead clicks `[data-tab="${id}"]`, which matches nothing real; see Open Questions.

test("LANE CHAIN and MASTER CHAIN modules open from the right pane", async ({ page }) => {
  await page.goto("/");
  for (const id of ["lane-chain", "master-chain"]) {
    const body = page.locator(`[data-module-body="${id}"]`);
    if (!(await body.isVisible())) await page.locator(`[data-module-toggle="${id}"]`).click();
    await expect(body).toBeVisible();
  }
});

test("the MIX + SIGNAL PATH tab renders", async ({ page }) => {
  await page.goto("/");
  await page.locator("[data-testid=bottom-tab-mix]").click();
  await expect(page.locator("[data-tab-body=mix]")).toBeVisible();
});

test("the fold / summary toggle works", async ({ page }) => {
  await page.goto("/");
  await page.locator("[data-testid=bottom-tab-mix]").click();
  await page.locator('[data-testid="mix-fold"]').click();
  await expect(page.locator('[aria-label="MIX ORDER"]')).toHaveCount(0);
  await page.locator('[data-testid="mix-expand"]').click();
  await expect(page.locator('[aria-label="MIX ORDER"]')).toBeVisible();
});

test("a lane's chain dot lights when its LANE CHAIN goes non-default", async ({ page }) => {
  await page.goto("/");
  // lane-chain is OPEN by default (view.openModules = ["files", "lane-chain"], M1 plan line 3148),
  // and ModuleShell renders the body only while open -- an unconditional click would close it.
  const body = page.locator('[data-module-body="lane-chain"]');
  if (!(await body.isVisible())) await page.locator('[data-module-toggle="lane-chain"]').click();
  // M5's LaneHeader.svelte carries no data-testid on the dot itself (verified against
  // docs/superpowers/plans/.../m5-timeline-fidelity.md:2594) -- .dot is the only hook there is.
  const dot = page.locator(".header").first().locator(".dot");
  await expect(dot).not.toHaveClass(/lit/);
  await page.locator('[data-testid="latch-toggle"]').click();
  await expect(dot).toHaveClass(/lit/);
});
```

- [ ] **Step 2: Run it, expect failure**

```bash
cd latent-forge && npx vitest run src/ui/mix/__tests__/MixSignalPath.component.test.ts
```

Expected: `Failed to resolve import "../MixSignalPath.svelte"`.

- [ ] **Step 3: Add the new HELP strings, then implement**

Add to `docs/latent-forge/extract_help.mjs`'s `NEW_STRINGS` (append after Task 4's four):

```js
  mixQuadWeight:
    "This lane's share of the weighted 4-way mix. All four are renormalised together; leaving " +
    "every one at zero mixes the lanes equally.",
  mixLerp:
    "Linear interpolation between this node's two inputs.",
  mixSlerp:
    "Spherical interpolation between this node's two inputs -- the default, since SAME's latent " +
    "space is strongly anisotropic and a straight lerp can cut through low-energy regions a slerp " +
    "arcs around.",
```

Regenerate:

```bash
cd latent-forge && npm run help:extract
```

Expected: `extract_help: wrote 107 strings (80 extracted, 14 rewritten, 27 new) to
.../latent-forge/src/lib/help/strings.ts`.

In `latent-forge/src/lib/help/__tests__/strings.test.ts`, move the total Task 4 set:
`it("has the 80 handoff strings plus the 27 new controls", ...)` / `toHaveLength(107)`.

`latent-forge/src/ui/mix/MixSignalPath.svelte`:

```svelte
<script lang="ts">
  // Spec §4.5 MIX + SIGNAL PATH, v3:211-282. The MIXDOWN button here is UI ONLY this milestone --
  // M9 wires the actual commit job submission (spec §7.1), same boundary as OVERLAP-INPAINT's
  // render button (M1 plan:6282).
  import { arrangement } from "../../lib/stores/arrangement.svelte";
  import { isQuad, mixTree, normalizedQuadWeights } from "../../lib/mix/mixMath";
  import { buildSignalPath, type SignalPathClip } from "../../lib/mix/signalPath";
  import { HELP } from "../../lib/help/strings";
  import { MIXDOWN_IDLE_LABEL } from "../topbar/mixdown";

  const mix = $derived(arrangement.mix);
  const master = $derived(arrangement.master);
  const tree = $derived(mixTree(mix.order));
  const quad = $derived(isQuad(mix.order));
  const normalisedWeights = $derived(normalizedQuadWeights(mix.quad_weights));

  const signalClips = $derived<SignalPathClip[]>(
    arrangement.clips.map((c) => ({
      lane: c.lane,
      isCropAudio: c.audio.kind === "crop",
      needsStretch: (c.native_bpm !== null && c.native_bpm !== arrangement.bpm) || c.detune_cents !== 0,
      a2aOn: c.a2a?.on ?? false,
    })),
  );
  const stages = $derived(
    buildSignalPath({
      lanes: arrangement.lanes.map((l) => ({ index: l.index, chain: l.chain })),
      clips: signalClips,
      overlapCount: arrangement.overlaps.length,
      mix, master,
    }),
  );

  let expanded = $state(true);

  function onMixdown() {
    // M9 wires the real `commit` job submission (spec §6.9, §7.1). No-op here on purpose.
  }
</script>

<div class="mix-signal-path" data-tab-body="mix">
  {#if expanded}
    <div class="panels">
      <div class="order-panel">
        <div class="head">
          <button data-testid="mix-fold" data-help={HELP.mixFold} onclick={() => (expanded = false)}>▾</button>
          <span>MIX ORDER</span>
          <select aria-label="MIX ORDER" data-help={HELP.mixOrder} value={mix.order}
            onchange={(e) => (mix.order = (e.currentTarget as HTMLSelectElement).value as typeof mix.order)}>
            <option value="tree">(1+2) + (3+4)</option>
            <option value="cascade">((1+2)+3)+4</option>
            <option value="quad">weighted 4-way (lerp only)</option>
          </select>
        </div>

        {#if quad}
          <div class="quad-weights">
            {#each [0, 1, 2, 3] as i (i)}
              <!-- aria-label on the INPUT, not the <label>: findAllByLabelText returns the element
                   carrying it, and data-help lives on the input -->
              <label>
                LANE {i + 1} <span class="value">{normalisedWeights[i].toFixed(2)}</span>
                <input type="range" aria-label="quad weight — lane {i + 1}" min="0" max="1" step="0.01" data-help={HELP.mixQuadWeight}
                  value={mix.quad_weights[i]}
                  oninput={(e) => (mix.quad_weights[i] = Number((e.currentTarget as HTMLInputElement).value))} />
              </label>
            {/each}
          </div>
        {:else if tree}
          <div class="nodes">
            {#each tree as node (node.id)}
              <div class="node">
                <span class="label">{node.id}</span>
                <div class="interp">
                  <button data-testid="{node.id.toLowerCase()}-lerp" data-help={HELP.mixLerp}
                    class:on={mix.nodes[node.id].interp === "lerp"}
                    onclick={() => (mix.nodes[node.id].interp = "lerp")}>LERP</button>
                  <button data-testid="{node.id.toLowerCase()}-slerp" data-help={HELP.mixSlerp}
                    class:on={mix.nodes[node.id].interp === "slerp"}
                    onclick={() => (mix.nodes[node.id].interp = "slerp")}>SLERP</button>
                </div>
                <input type="range" aria-label="{node.id} position" data-help={HELP.mixNodeT}
                  min="0" max="1" step="0.01" value={mix.nodes[node.id].t}
                  oninput={(e) => (mix.nodes[node.id].t = Number((e.currentTarget as HTMLInputElement).value))} />
              </div>
            {/each}
          </div>
        {/if}
      </div>

      <div class="signal-panel">
        <span class="head">SIGNAL PATH <span class="live">live</span></span>
        <div class="stages">
          {#each stages as st (st.n)}
            <div class="stage" data-signal-stage data-lit={st.lit} data-help={HELP.signalPath} class:lit={st.lit}>
              <span class="n">{st.n}</span><span class="label">{st.label}</span><span class="note">{st.note}</span>
            </div>
          {/each}
        </div>
        <button class="mixdown" onclick={onMixdown} data-help={HELP.renderButton}>{MIXDOWN_IDLE_LABEL}</button>
      </div>
    </div>
  {:else}
    <div class="summary">
      <button data-testid="mix-expand" data-help={HELP.mixExpand} onclick={() => (expanded = true)}>▸</button>
      <span>MIX + SIGNAL PATH</span>
      <span>{mix.order}</span>
      <span class="dim">{stages.filter((s) => s.lit).length}/{stages.length} lit</span>
      <div class="spacer"></div>
      <button class="mixdown" onclick={onMixdown} data-help={HELP.renderButton}>{MIXDOWN_IDLE_LABEL}</button>
    </div>
  {/if}
</div>

<style>
  .mix-signal-path { height: 100%; box-sizing: border-box; }
  .panels { display: flex; gap: 8px; height: 100%; }
  .order-panel, .signal-panel { flex: 1; min-width: 0; box-sizing: border-box; border: 1px solid var(--border); background: var(--panel); padding: 8px 10px; }
  .head { display: flex; align-items: center; gap: 8px; margin-bottom: 7px; font-size: 10px; color: var(--text-dim); }
  .nodes { display: flex; gap: 8px; }
  .node { flex: 1; box-sizing: border-box; border: 1px solid var(--border); padding: 6px; }
  .interp { display: flex; gap: 3px; margin-bottom: 5px; }
  button.on { background: var(--turq-strong); color: white; }
  .quad-weights { display: flex; gap: 12px; }
  .stages { display: flex; flex-direction: column; gap: 3px; }
  .stage { display: flex; gap: 6px; font-size: 10px; opacity: 0.4; }
  .stage.lit { opacity: 1; }
  .summary { display: flex; align-items: center; gap: 8px; height: 100%; }
  .spacer { flex: 1; }
</style>
```

Modify `latent-forge/src/ui/shell/BottomPane.svelte`: add
`import MixSignalPath from "../mix/MixSignalPath.svelte";` and, inside
`data-region="bottom-tab-body"`, replace

```svelte
    {:else if tab === "mix"}
      <!-- body: M7 (spec §4.5 MIX ORDER + SIGNAL PATH, §8.1 stage labels) -->
      <div class="tab-empty"></div>
```

with

```svelte
    {:else if tab === "mix"}
      <MixSignalPath />
```

Nothing else in `BottomPane.svelte` changes — its `.tab-body`'s own `flex: 0 0 162px` and
`overflow: hidden` (M1 T11) already size `MixSignalPath`'s `height: 100%`.

- [ ] **Step 4: Run it, expect pass**

```bash
cd latent-forge && npx vitest run src/ui/mix/__tests__/MixSignalPath.component.test.ts && npx vitest run src/lib/help && npm run check
```

Expected: `Test Files  1 passed (1)` / `Tests  8 passed (8)`, then M1's `src/lib/help` suite green
at the new total of 107, then `svelte-check found 0 errors and 0 warnings`.

Then the e2e fragment, against the mock server (per spec §11.3/M1 T14's own harness):

```bash
cd latent-forge && npx playwright test tests/chains.spec.ts
```

Expected: `4 passed`. (Test 4 opens `lane-chain` only if it is closed — it is open by default —
so the `latch-toggle` it clicks is actually rendered.)

- [ ] **Step 5: Commit**

```bash
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M7 T5: MIX + SIGNAL PATH tab (spec 4.5, 8.1) -- MIX ORDER/node/quad controls over mixMath, live SIGNAL PATH from signalPath, MIXDOWN UI-only (M9 wires the commit), mounted in BottomPane's mix tab"
```

---

## Open questions

1. **`LatchRequest`'s shape is not pre-named anywhere** (spec §5.5 only gives the formula, not a
   wire shape). I shipped `{slots: LatchRequestSlot[]; rho; mu; gamma; n_iter; log_norms}` with
   `slots` holding only the active entries in original relative order (so "omitted" = absent from
   the array, verified in the test both by length and by a `JSON.stringify` substring check, not
   just a falsy value). If M8's real server-side LatCH payload shape turns out to be keyed
   differently (e.g. per-slot dict), this type and `resolveLatch`'s return need a matching change
   at that point — flagged for WINTERMUTE.

2. **Two toggle buttons the brief's own "Controls with NO id anywhere" table omitted, verified
   directly against the real v3 file**: LATCH GUIDANCE's own toggle (v3:507) and BUNGEE's own
   toggle (v3:557) both carry no `data-help`, exactly like FILM's (538) and LORA/DORA's (546)
   toggles which the brief DID flag. I added `latchToggle` and `bungeeToggle` to `NEW_STRINGS` for
   consistency (every on/off toggle in this module now has a string); if that's unwanted, drop
   those two entries and the two `data-help={HELP.latchToggle|bungeeToggle}` attachments.
   **Critic pass 1 added three more to Task 2, for the same reason:** `filmCkpt` (the FILM CKPT
   select had been given `HELP.filmToggle`, the toggle's text, by mistake), and `modulePresetSave`/
   `modulePresetDelete` for the SAVE/DEL buttons §9.3's module level needs and the drawing does not
   show. Task 2 therefore adds 13 strings, not 10.

3. **A second omission, also verified directly**: the MIX + SIGNAL PATH tab's own two `▸ MIXDOWN` /
   render buttons (v3:269 expanded, v3:279 summary) carry no `data-help` in the drawing, and the
   brief's ids table doesn't assign them a new string either. I reused the existing `HELP
   .renderButton` (M1 T14, id 45, the top-bar RENDER/MIXDOWN control) on both, since it's
   conceptually the same commit action rather than a genuinely new control — flag if a distinct
   `mixMixdown` string is wanted instead.

4. **`fetchAdapters()`'s real server mismatch, verified, not mine to fix.** M1's `fetchAdapters()`
   (`src/lib/forge/models.ts`) reads `body.ckpts`, but the real `/models` route
   (`eval/explorer_render_server.py:977-997`) returns `{"ok", "count", "models", "stale_root_ids"}`
   — the array is under `models`, not `ckpts`. Against the real server this makes `fetchAdapters()`
   always resolve to `[]`. M1's own test mocks `{ok:true, ckpts:[...]}`, so the test is
   self-consistently green and never catches this. My new `fetchFilmCkpts()` deliberately reads
   `body.models` (verified correct) rather than copying the bug forward. This is an M1-internal
   defect like the two the brief already named (`ModuleShell`, `viewStore`/`view`) — worth a line
   in WINTERMUTE's DM alongside them, and a real, if small, fix for whoever next touches M1.

5. **M1 T14's own Playwright layout spec has a third, previously-unflagged internal defect.**
   `docs/superpowers/plans/2026-09-16-latent-forge-m1-foundation-shell.md:8335` clicks
   `[data-tab="${id}"]` to open a bottom tab, but the real `BottomPane.svelte`
   (m1 plan:6128-6159) gives its tab BUTTONS `data-testid="bottom-tab-{t.id}"` and no `data-tab`;
   the only `data-tab` is the tab BODY's `data-tab={tab}` (m1 plan:6143), so the locator matches the
   current tab's body only and the test fails from its first non-current tab (`chroma`) on. M4's own, later, working e2e fragment
   (`docs/superpowers/plans/2026-09-18-latent-forge-m4-prompt-sigma.md:5703-5708`) already clicks
   `[data-testid=bottom-tab-prompt]` instead, which is what I used for `tests/chains.spec.ts` too.
   Worth a line to WINTERMUTE alongside the other M1-internal defects; not mine to fix in M1 itself.

6. **All v3 line citations and `data-help` ids for LANE CHAIN (501-563), MASTER CHAIN (601-620) and
   MIX + SIGNAL PATH (211-282) were independently re-verified line-for-line against the real
   `docs/sa3-studio/design_handoff/SA3 Studio v3.dc.html`** — the brief's own table is accurate for
   all three regions (no off-by-one found), except for the two toggle-button omissions in item 2
   above. The `/slots` shape (item consumed in Task 2) was likewise re-verified directly against
   `eval/adapter_slots.py:51-60,156-160` and `eval/explorer_render_server.py:839-846,901-905` and
   matches the brief exactly.

7. **The SIGNAL PATH list this milestone builds is a client-side estimate, not ground truth.** The
   real per-stage `on`/`note` data only exists in a commit job's `meta.stages` (spec §6.9), which
   nothing produces until M9 wires the `▸ MIXDOWN` button. `signalPath.ts`'s lit/dimmed rules
   (S1 from any crop-ref clip, S2 from `bungee_on` or a stretch-needing clip, S3/S7/S9 from
   `clips.length > 0`) are my own reasonable approximation for "what would probably run," stated
   plainly in the file's header comment. Whether M9 should replace this estimate wholesale with the
   real `meta.stages` once a commit has run, or reconcile the two (estimate before a commit, ground
   truth after), is not decided here — flagging for whoever plans M9.

8. **S4's idle note is attached once, for the first lane found idle**, when the SIGNAL PATH is a
   single aggregate row rather than per-lane. Spec §8.1 states the note per-lane
   ("Lanes whose chain is active but which have no A2A clip get the stage note `chain idle...`"),
   but the SIGNAL PATH UI (v3:260-268) is one row per STAGE, not per lane — there is nowhere in the
   drawn UI to show more than one idle lane's note simultaneously. I take the first idle lane found;
   a project with two independently-idle lane chains only ever shows one note at a time in this
   milestone. Worth a look if that turns out to matter in practice.

9. **`needsStretch`'s exact definition (§8.1 S2) is my own choice**, since Task 3's brief line names
   only "the lanes' chains, overlaps, mix and master state" as signalPath.ts's inputs, not clip
   stretch data — I extended `SignalPathInput` with a `clips: SignalPathClip[]` array (assembled in
   Task 5 from `arrangement.clips`/`arrangement.bpm`) to make S1/S2/S3/S5's lit conditions
   meaningful at all. If a narrower reading (chains/overlaps/mix/master ONLY, no clip awareness) was
   intended, S1/S2/S3/S5 would need to drop to only ever showing dimmed, which seemed clearly wrong
   given the spec's own worked example of an idle lane chain.

10. **`fetchLatchHeads()` lives in `src/lib/chains/latch.ts` (Task 1) rather than
    `src/lib/forge/models.ts`** (where `fetchAdapters`/`fetchFilmCkpts` live), because it shapes
    `/info.latch_heads` into the exact `Record<string, LatchHeadInfo>` `resolveLatch` consumes, and
    both Task 2 and Task 4 need the identical shape. This is a name the brief did not pre-declare;
    flag if a different placement (e.g. beside the other `/info`-adjacent fetchers) is preferred.

11. **Test file placement for `fetchFilmCkpts`/`fetchSlots`** — M1 placed `fetchAdapters`'s own test
    inside `src/ui/topbar/__tests__/modelOptions.test.ts` even though the function lives in
    `src/lib/forge/models.ts` (verified at m1 plan:4851,4898-4911). I did not follow that placement
    for the two new functions and instead created `src/lib/forge/__tests__/models.test.ts` beside
    the file they extend, which seems like the less surprising convention going forward.

12. **`spec §9.3`'s own "three levels... lists four" slip** (prompt, render, module, master) is
    reproduced as found, per the brief's own instruction — not mine to silently correct. Noted here
    again for WINTERMUTE's DM batch alongside the other cross-cutting flags in items 4 and 5.

13. **`ModuleShell`'s duplicate declaration and the `viewStore`/`view` mismatch**, both already
    named in the M7 brief's shared preamble, were relied on exactly as the brief resolved them (the
    second version — `{id, title, lit, children}`, self-driven off `view.isModuleOpen`/
    `view.toggleModule`) throughout Tasks 2 and 4's Interfaces; I did not re-verify M1's Task 9 code
    block itself since the brief's resolution is corroborated directly by `RightPaneModules.svelte`'s
    real, working usage (m1 plan:6297-6304, 6678) and by the Playwright spec's own frozen assertions
    (m1 plan:8341-8348) — both agree with each other and disagree with Task 9's shown snippet.

### Task 6: FILES — add the two missing HELP ids, prove the module works end to end

**WHY.** The brief could not confirm from the plan text alone whether M1 Task 15's `Files.svelte`
already renders a root `<select>` and filter `<input>`, or only the internal `root`/`q` state with
no markup for them. I read the real file
(`docs/superpowers/plans/2026-09-16-latent-forge-m1-foundation-shell.md:8623-8785`, which is what
lands at `latent-forge/src/ui/modules/Files.svelte`) and it is **not a stub**: it already has an
`$effect` that calls `forgeApi.files({root, q, limit: 200})`, a root `<select bind:value={root}>`
with `aria-label="file root"`, a filter `<input bind:value={q}>` with `aria-label="filter files"`,
a root header (`{rootLabel}`), an unavailable-root affordance (`disabled={!r.available}` plus
`" (unmounted)"` suffix — shown, not hidden, exactly per spec §6.3), an empty/error message, and a
draggable row list that sets both `application/x-forge-ref` and (for a crop) `text/sa3-crop-id`.
Every behavioural requirement of spec §4.6.2 ("root header, root select, filter field, list of
files draggable onto lanes") is already there. What is missing is exactly two `data-help`
attributes: the root select and the filter field have `aria-label`s but no `data-help`, and the
M7 brief's own v3-line-range table confirms why nobody could have extracted one for them —
**the drawing has no root select or filter field at all** (v3 474–484 has only the draggable row,
480, with a `data-help`; I re-verified this directly against
`docs/sa3-studio/design_handoff/SA3 Studio v3.dc.html:474-484`, which hard-codes the root header
as the literal string `~/PROJECTS/LATENTS_SA3/AUDIO` and has no `<select>` or filter `<input>`
anywhere in the module). So these two are spec-only controls invented for this build, `NEW_STRINGS`-style, with no handoff wording to keep beside them.

This task therefore does three things: adds the two `data-help` ids to the existing markup, adds
them to the HELP source (`docs/latent-forge/extract_help.mjs`'s `NEW_STRINGS` block, regenerated
into `latent-forge/src/lib/help/strings.ts`), and — since Task 15 never wrote a dedicated unit test
for `Files.svelte` itself (only the Playwright layout spec's one row-is-draggable assertion) —
adds one, so the module's actual behaviour (fetch, filter, unavailable root, drag payload) is
under vitest rather than resting on a single E2E assertion.

**Files shared with Tasks 2, 4, 5 and 9.** `docs/latent-forge/extract_help.mjs`,
`latent-forge/src/lib/help/strings.ts` and M1's `strings.test.ts` are the same three files Task 2
(LANE CHAIN), Task 4 (MASTER CHAIN) and Task 5 (MIX quad/LERP/SLERP) have already extended by the
time this task runs, and Task 9 extends after it. Each task appends to the same `NEW_STRINGS`
object literal, re-runs `npm run help:extract`, and moves `strings.test.ts`'s total to the new
cumulative count (see the `data-*`/`HELP` contract table above) so M1's own suite is green after
every task, not only at the end. This task's own new tests assert only the two ids it adds, never
the total.

**Files:**
- Modify: `latent-forge/src/ui/modules/Files.svelte` (two `data-help` attributes only — no other
  markup, state or behaviour changes; everything else in the file is correct as Task 15 left it)
- Modify: `docs/latent-forge/extract_help.mjs` (append `filesRoot`, `filesFilter` to `NEW_STRINGS`,
  in the same style as the existing entries — plain wording, no `// handoff:` comment, since there
  is no original to quote)
- Modify (regenerated by `npm run help:extract`, committed): `latent-forge/src/lib/help/strings.ts`
- Modify: `latent-forge/src/lib/help/__tests__/strings.test.ts` (total 107 → 109)
- Create: `latent-forge/src/lib/help/__tests__/filesHelp.test.ts`
- Create: `latent-forge/src/ui/modules/__tests__/Files.test.ts`

**Interfaces:**
- Consumes `forgeApi.files({root?, q?, limit?})` → `{ok: true, roots: {id, label, available:
  boolean}[], files: {root, rel, kind: "audio"|"latent", size, mtime, ref: AudioRef|LatentRef}[]}`
  from `src/lib/forge/api.ts` (M1 T5, frozen — restated verbatim, not re-derived).
- Consumes `AudioRef`, `LatentRef` from `src/lib/forge/types.ts` (M1 T3).
- Consumes `HELP: Record<HelpId, string>` from `src/lib/help/strings.ts` (M1 T14) — this task adds
  `HELP.filesRoot`, `HELP.filesFilter`; `HELP.filesRow` already exists and is unchanged.
- Consumes the real, already-written `Files.svelte` internals: `root = $state("crops")`,
  `q = $state("")`, `rows = $state<Row[]>([])`, `roots = $state<{id,label,available}[]>([])`,
  `rootLabel = $derived(...)`, the `$effect` that fetches on `[root, q]`, `onDragStart(e, row)`.
  None of these are touched; they are restated here only so the implementing agent does not
  duplicate them thinking the file is empty.
- Produces: no new exports. The component gains two attributes; `strings.ts` gains two `HELP` keys.

- [ ] **Step 1: Write the failing tests**

`latent-forge/src/lib/help/__tests__/filesHelp.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { HELP } from "../strings";

describe("FILES' two brand-new HELP strings (spec §4.6.2, v3 474-484 has no select or filter at all)", () => {
  it("has filesRoot, non-empty, describing the root select", () => {
    expect(HELP.filesRoot.length).toBeGreaterThan(10);
    expect(HELP.filesRoot.toLowerCase()).toContain("root");
  });

  it("has filesFilter, non-empty, describing the filter field", () => {
    expect(HELP.filesFilter.length).toBeGreaterThan(10);
    expect(HELP.filesFilter.toLowerCase()).toContain("filter");
  });

  it("keeps filesRow exactly as the drawing had it (v3 line 480)", () => {
    expect(HELP.filesRow).toBe(
      "Drag onto a lane to add a clip at the playhead. Audio and latents are both accepted.",
    );
  });
});
```

`latent-forge/src/ui/modules/__tests__/Files.test.ts`:

```ts
// @vitest-environment jsdom
import { cleanup, fireEvent, render, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { forgeApi } from "../../../lib/forge/api";
import Files from "../Files.svelte";

vi.mock("../../../lib/forge/api", () => ({
  forgeApi: { files: vi.fn() },
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const FILES_RESPONSE = {
  ok: true as const,
  roots: [
    { id: "crops", label: "crops", available: true },
    { id: "renders", label: "renders", available: true },
    { id: "uploads", label: "uploads", available: false },
  ],
  files: [
    { root: "crops", rel: "000412.npy", kind: "latent" as const, size: 1024, mtime: 1,
      ref: { kind: "crop" as const, crop_id: "000412" } },
    { root: "crops", rel: "kick_loop.wav", kind: "audio" as const, size: 2048, mtime: 2,
      ref: { kind: "file" as const, root: "crops", rel: "kick_loop.wav" } },
  ],
};

describe("Files.svelte (spec §4.6.2) -- Task 15's real implementation, plus this task's two HELP ids", () => {
  it("fetches on mount and lists what the server returned", async () => {
    vi.mocked(forgeApi.files).mockResolvedValue(FILES_RESPONSE);
    const { getAllByRole } = render(Files);
    await waitFor(() => expect(forgeApi.files).toHaveBeenCalledWith({ root: "crops", q: undefined, limit: 200 }));
    const rows = getAllByRole("listitem");
    expect(rows).toHaveLength(2);
    expect(rows[0].textContent).toContain("000412.npy");
  });

  it("re-fetches with the query when the filter field changes", async () => {
    vi.mocked(forgeApi.files).mockResolvedValue(FILES_RESPONSE);
    const { getByLabelText } = render(Files);
    await waitFor(() => expect(forgeApi.files).toHaveBeenCalledTimes(1));
    await fireEvent.input(getByLabelText("filter files"), { target: { value: "kick" } });
    await waitFor(() => expect(forgeApi.files).toHaveBeenCalledWith({ root: "crops", q: "kick", limit: 200 }));
  });

  it("shows an unavailable root disabled, with the (unmounted) suffix, not hidden", async () => {
    vi.mocked(forgeApi.files).mockResolvedValue(FILES_RESPONSE);
    const { findByText } = render(Files);
    const opt = (await findByText("uploads (unmounted)")) as HTMLOptionElement;
    expect(opt.tagName).toBe("OPTION");
    expect(opt.disabled).toBe(true);
  });

  it("sets application/x-forge-ref and text/sa3-crop-id on drag for a crop row, only x-forge-ref for a file row", async () => {
    vi.mocked(forgeApi.files).mockResolvedValue(FILES_RESPONSE);
    const { getAllByRole } = render(Files);
    await waitFor(() => expect(getAllByRole("listitem")).toHaveLength(2));
    const rows = getAllByRole("listitem");

    const dtCrop = { setData: vi.fn(), effectAllowed: "" };
    await fireEvent.dragStart(rows[0], { dataTransfer: dtCrop });
    expect(dtCrop.setData).toHaveBeenCalledWith("application/x-forge-ref", JSON.stringify(FILES_RESPONSE.files[0].ref));
    expect(dtCrop.setData).toHaveBeenCalledWith("text/sa3-crop-id", "000412");

    const dtFile = { setData: vi.fn(), effectAllowed: "" };
    await fireEvent.dragStart(rows[1], { dataTransfer: dtFile });
    expect(dtFile.setData).toHaveBeenCalledWith("application/x-forge-ref", JSON.stringify(FILES_RESPONSE.files[1].ref));
    expect(dtFile.setData).not.toHaveBeenCalledWith("text/sa3-crop-id", expect.anything());
  });

  it("carries data-help on the root select and the filter field", () => {
    vi.mocked(forgeApi.files).mockResolvedValue({ ok: true, roots: [], files: [] });
    const { getByLabelText } = render(Files);
    expect(getByLabelText("file root").getAttribute("data-help")).toBeTruthy();
    expect(getByLabelText("filter files").getAttribute("data-help")).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run them, expect failure**

```bash
cd /home/kim/Projects/sa3-studio-review/latent-forge && npx vitest run src/lib/help/__tests__/filesHelp.test.ts src/ui/modules/__tests__/Files.test.ts
```

Expected: `filesHelp.test.ts` fails two of its three assertions (`HELP.filesRoot`/`HELP.filesFilter`
are `undefined`, `.length` throws); `Files.test.ts` fails only its last case (`data-help` is `null`
on both elements) — the other four already pass, because Task 15's implementation is real. Summary:
`Test Files  2 failed (2)`.

- [ ] **Step 3: Add the two HELP strings**

In `docs/latent-forge/extract_help.mjs`, append to `NEW_STRINGS` (after Task 5's `mixSlerp`,
the last entry at this point, before the closing `};`):

```ts
  filesRoot:
    "Which server root to browse: crops (extracted latents), renders (past commits) or uploads " +
    "(files dropped or picked from disk). An unmounted root is listed, greyed, rather than hidden.",
  filesFilter:
    "Filters the file list by substring match on its path. Clears to show every file under the " +
    "selected root again.",
```

Regenerate:

```bash
cd /home/kim/Projects/sa3-studio-review/latent-forge && npm run help:extract
```

Expected: `extract_help: wrote 109 strings (80 extracted, 14 rewritten, 29 new) to .../strings.ts`
(Tasks 2, 4 and 5 already brought it to 107; this task adds two).

In `latent-forge/src/lib/help/__tests__/strings.test.ts`, move the total Task 5 set:
`it("has the 80 handoff strings plus the 29 new controls", ...)` / `toHaveLength(109)`.

In `latent-forge/src/ui/modules/Files.svelte`, add exactly two attributes (no other change):

```svelte
    <select bind:value={root} aria-label="file root" data-help={HELP.filesRoot}>
```

```svelte
    <input type="text" placeholder="filter" bind:value={q} aria-label="filter files" data-help={HELP.filesFilter} />
```

- [ ] **Step 4: Run them, expect pass**

```bash
cd /home/kim/Projects/sa3-studio-review/latent-forge && npx vitest run src/lib/help/__tests__/filesHelp.test.ts src/ui/modules/__tests__/Files.test.ts
```

Expected: `Test Files  2 passed (2)` / `Tests  8 passed (8)` (3 in `filesHelp.test.ts`, 5 in
`Files.test.ts`). Then `npx vitest run src/lib/help` — M1's `strings.test.ts` green at 109.

- [ ] **Step 5: Commit**

```bash
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M7 T6: FILES gets its two brand-new HELP ids (root select, filter field -- the drawing never had either); Files.svelte itself was already Task 15's real implementation, now under a dedicated vitest suite"
```

---

### Task 7: OVERLAP — INPAINT module, replacing M1's stub

**WHY.** M1 Task 12's `OverlapInpaint.svelte` is a one-line placeholder
(`<p class="pending">crossfade curve, chroma crossfade and the local STEPS / CFG override arrive
in M7</p>`), present only while `view.selection.kind === "overlap"` (`RightPaneModules.svelte`'s
`overlapSelected = $derived(view.selection.kind === "overlap")` filter, M1 T12). This task fills
its body per spec §4.6.1: an info line naming the overlap and its two clips, the 64 px CROSSFADE
CURVE editor, the CHROMA CROSSFADE toggle (default on), the LOCAL STEPS / CFG override (default
off) with its STEPS/CFG drag fields, and the `▸ INPAINT OVERLAP` button — the button is a no-op in
this milestone, exactly as M1's own table already says ("its `▸ INPAINT OVERLAP` button wired in
M9").

Everything this module edits already exists and is live: `arrangement.overlapParams(key):
OverlapParams` / `arrangement.setOverlapParams(key, patch)` (M5 T1,
`docs/superpowers/plans/2026-09-17-latent-forge-m5-timeline-fidelity.md:552-563` — `overlapParams`
lazily seeds `OVERLAP_DEFAULT` into a `$state` record and returns the live entry;
`setOverlapParams` is `Object.assign(this.overlapParams(key), patch)` on that same live object),
plus Task 3's non-seeding `peekOverlapParams(key)`, which is what this module actually reads.
Which overlap is selected comes from `view.selection: Target` (M1 T7) and `arrangement.overlaps:
Overlap[]` (M5 T7 — `{key, lane, start_sec, end_sec, a_id, b_id}`, re-exported from
`arrangement.svelte.ts`). I do **not** use `arrangement.selectedOverlap` even though M5's own Task
1 Interfaces line names it: M5 Task 9's own text
(`docs/superpowers/plans/2026-09-17-latent-forge-m5-timeline-fidelity.md:4436-4439`) flags that
this field is never actually defined by Task 1's Step 3 code, and works around it the same way —
by deriving the selection locally from `view.selection` plus `arrangement.clips`/`arrangement.overlaps`.
I follow that same, already-precedented workaround rather than depending on a field that does not
exist.

The 64 px CROSSFADE CURVE editor is **not a new component**: M5 Task 9 already built
`src/ui/master/EnvelopeEditor.svelte` (props `{envelope: Envelope; active: boolean; onChange: (env:
Envelope) => void}`, default export, absolutely positioned `inset:0` SVG overlay) for the a2a noise
envelope on the master strip, and the brief for this task explicitly says to reuse it rather than
build a second one. I wrap it in a `position: relative; height: 64px` box (spec's own "64 px"
figure) and always pass `active={true}` — unlike the master strip's usage, which is only active
while the selected clip has A2A on, OVERLAP's curve is always the render target's own editable
parameter whenever the module is showing at all (the module only exists while an overlap actually
is the selection), so there is no separate "armed" state to gate it on.

`▸ INPAINT OVERLAP`'s no-op status matches OVERLAP-INPAINT to Writer A's `▸ MIXDOWN` (Task 5) and
M1's MIXDOWN slot (Task 10): every render-triggering control in this milestone is UI only, M9 wires
the job.

**Files:**
- Create: `latent-forge/src/lib/forge/overlapLabel.ts`,
  `latent-forge/src/lib/forge/__tests__/overlapLabel.test.ts`
- Modify: `latent-forge/src/ui/modules/OverlapInpaint.svelte` (replaces the M1 T12 stub in full)
- Create: `latent-forge/src/ui/modules/__tests__/OverlapInpaint.test.ts`

**Interfaces:**
- Consumes `OverlapParams { curve: Envelope; chroma_xfade: boolean; override: boolean; steps:
  number; cfg: number; render: RenderSettings }`, `Envelope`, `ForgeClip`, `AudioRef` from
  `src/lib/forge/types.ts` (M1 T3).
- Consumes `OVERLAP_DEFAULT` (`chroma_xfade: true, override: false, steps: 28, cfg: 3.0, curve:
  {points:[0,0.35,0.7,1], curves:[0,0,0]}`) from `src/lib/forge/defaults.ts` (M1 T4).
- Consumes `arrangement.overlaps: Overlap[]` (`{key, lane, start_sec, end_sec, a_id, b_id}`),
  `arrangement.clips: ForgeClip[]`, `arrangement.setOverlapParams(key, patch:
  Partial<OverlapParams>): void` from `src/lib/stores/arrangement.svelte.ts` (M5 T1/T7), and
  **`arrangement.peekOverlapParams(key): OverlapParams`** (this plan's Task 3). **Not
  `overlapParams(key)`**: it seeds `OVERLAP_DEFAULT` into the store on first read (M5 plan lines
  552-560), and this component's `params` is a `$derived` — a fresh overlap is always unseeded, so
  the write would throw `state_unsafe_mutation` on the very first render (Global Constraint #8,
  verified on Svelte 5.57.0). `peekOverlapParams` never writes; `setOverlapParams` seeds on the
  first edit, and the `$derived` re-runs because it read `overlapStore[key]`. This module never
  holds its own copy of an `OverlapParams` and never mutates what `peek` returns — every write goes
  through `setOverlapParams`, per the `$state` proxy rule.
- Consumes `view.selection: Target` (`{kind:"none"} | {kind:"clip"; id} | {kind:"overlap"; key}`)
  from `src/lib/stores/view.svelte.ts` (M1 T7).
- Consumes `EnvelopeEditor` (default export) from `src/ui/master/EnvelopeEditor.svelte` (M5 T9),
  props `{envelope: Envelope; active: boolean; onChange: (env: Envelope) => void}`.
- Consumes `dragScale` action from `src/lib/actions/dragScale.ts` (M1 T8), used as
  `use:dragScale={{min, max, int, value, onValue}}`.
- Consumes `HELP.overlapChromaXfade` (v3:460), `HELP.overlapOverride` (v3:464),
  `HELP.overlapSteps` (v3:466), `HELP.overlapCfg` (v3:467) from `src/lib/help/strings.ts` (M1 T14)
  — all four verified directly against `docs/sa3-studio/design_handoff/SA3 Studio
  v3.dc.html:460,464,466,467`; the brief's table is correct on all four lines. No new HELP id is
  needed for this module: the info line, the curve editor and the `▸ INPAINT OVERLAP` button have
  no `data-help` in the drawing (v3:445-448,468) and the brief's own "Controls with NO id anywhere"
  enumeration does not ask for one, so none is invented here.
- Produces, from `src/lib/forge/overlapLabel.ts`: `clipLabel(clip: ForgeClip | undefined): string`,
  `overlapInfoLine(overlap: {lane: 0|1|2|3; start_sec: number; end_sec: number}, a: ForgeClip |
  undefined, b: ForgeClip | undefined): string`.
- Produces, for `RightPaneModules.svelte`'s snapshot (Task 9 Step 5, spec §4.6's lit dot):
  **`overlap: view.selection.kind === "overlap" ? arrangement.peekOverlapParams(view.selection.key) : null`**
  (read inside that step's `$derived`; `peek`, not `overlapParams`, for the same reason as above) — `null` exactly when nothing is selected as an overlap, matching
  `litModules`'s `ModuleStateSnapshot.overlap: OverlapParams | null` (M1 T12,
  `docs/superpowers/plans/2026-09-16-latent-forge-m1-foundation-shell.md:6271-6742`, `nonDefault.ts`).

- [ ] **Step 1: Write the failing tests**

`latent-forge/src/lib/forge/__tests__/overlapLabel.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { clipLabel, overlapInfoLine } from "../overlapLabel";
import type { ForgeClip } from "../types";

function clip(over: Partial<ForgeClip> & { audio: ForgeClip["audio"] }): ForgeClip {
  return {
    id: "clip_x", lane: 0, start_sec: 0, offset_sec: 0, dur_sec: 4, loop: false,
    native_bpm: null, detune_cents: 0, downbeats_sec: [], latentState: "none", history: [],
    a2a: null, previewAudio: null,   // required on ForgeClip since M5 T10 (in-memory only)
    render: {} as ForgeClip["render"],
    ...over,
  };
}

describe("clipLabel picks a readable name per AudioRef kind (spec §6.1)", () => {
  it("crop -> the crop id", () => {
    expect(clipLabel(clip({ audio: { kind: "crop", crop_id: "000412" } }))).toBe("000412");
  });
  it("render -> the file", () => {
    expect(clipLabel(clip({ audio: { kind: "render", job_id: "forge-1", file: "out_00.wav" } }))).toBe("out_00.wav");
  });
  it("file -> the last path segment of rel", () => {
    expect(clipLabel(clip({ audio: { kind: "file", root: "crops", rel: "a/b/kick.wav" } }))).toBe("kick.wav");
  });
  it("path -> the last path segment", () => {
    expect(clipLabel(clip({ audio: { kind: "path", path: "/SERVER/out/x.wav" } }))).toBe("x.wav");
  });
  it("upload -> the first 8 chars of the sha256", () => {
    expect(clipLabel(clip({ audio: { kind: "upload", sha256: "a".repeat(64) } }))).toBe("aaaaaaaa");
  });
  it("undefined clip -> a fixed placeholder, never throws", () => {
    expect(clipLabel(undefined)).toBe("?");
  });
});

describe("overlapInfoLine (spec §4.6.1: which overlap, its two clip names)", () => {
  it("names the lane, both clips and the mask window in seconds", () => {
    const a = clip({ id: "clip_a", audio: { kind: "crop", crop_id: "000100" } });
    const b = clip({ id: "clip_b", audio: { kind: "crop", crop_id: "000200" } });
    const line = overlapInfoLine({ lane: 1, start_sec: 10, end_sec: 12.5 }, a, b);
    expect(line).toBe("lane 2 · 000100 → 000200 · mask 10.00–12.50 s");
  });

  it("falls back to the placeholder name when a clip cannot be found", () => {
    const line = overlapInfoLine({ lane: 0, start_sec: 0, end_sec: 1 }, undefined, undefined);
    expect(line).toBe("lane 1 · ? → ? · mask 0.00–1.00 s");
  });
});
```

`latent-forge/src/ui/modules/__tests__/OverlapInpaint.test.ts`:

```ts
// @vitest-environment jsdom
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { arrangement } from "../../../lib/stores/arrangement.svelte";
import { view } from "../../../lib/stores/view.svelte";
import OverlapInpaint from "../OverlapInpaint.svelte";

function seedOverlap(): string {
  arrangement.clips.splice(0, arrangement.clips.length);
  const a = arrangement.addClip({ lane: 0, startSec: 0, durSec: 10, audio: { kind: "crop", crop_id: "A" } });
  const b = arrangement.addClip({ lane: 0, startSec: 6, durSec: 10, audio: { kind: "crop", crop_id: "B" } });
  const [overlap] = arrangement.overlaps;
  view.select({ kind: "overlap", key: overlap.key });
  return overlap.key;
}

beforeEach(() => {
  arrangement.clips.splice(0, arrangement.clips.length);
  view.clearSelection();
});

afterEach(() => {
  cleanup();
  arrangement.clips.splice(0, arrangement.clips.length);
  view.clearSelection();
});

describe("OverlapInpaint.svelte (spec §4.6.1)", () => {
  it("shows the info line naming the lane and both clips", () => {
    seedOverlap();
    const { getByText } = render(OverlapInpaint);
    expect(getByText(/lane 1 · A → B · mask/)).toBeTruthy();
  });

  it("CHROMA CROSSFADE is on by default and toggling it writes through setOverlapParams", async () => {
    const key = seedOverlap();
    const { getByTestId } = render(OverlapInpaint);
    const toggle = getByTestId("overlap-chroma-xfade");
    expect(toggle.textContent).toContain("ON");
    await fireEvent.click(toggle);
    expect(arrangement.overlapParams(key).chroma_xfade).toBe(false);
    expect(toggle.textContent).toContain("OFF");
  });

  it("LOCAL STEPS / CFG is off by default, and the STEPS/CFG fields are disabled until it is on", async () => {
    const key = seedOverlap();
    const { getByTestId } = render(OverlapInpaint);
    expect(arrangement.overlapParams(key).override).toBe(false);
    expect((getByTestId("overlap-steps") as HTMLInputElement).disabled).toBe(true);
    expect((getByTestId("overlap-cfg") as HTMLInputElement).disabled).toBe(true);
    await fireEvent.click(getByTestId("overlap-override"));
    expect(arrangement.overlapParams(key).override).toBe(true);
    expect((getByTestId("overlap-steps") as HTMLInputElement).disabled).toBe(false);
  });

  it("STEPS and CFG show OVERLAP_DEFAULT's values (28, 3.0)", () => {
    seedOverlap();
    const { getByTestId } = render(OverlapInpaint);
    expect((getByTestId("overlap-steps") as HTMLInputElement).value).toBe("28");
    expect((getByTestId("overlap-cfg") as HTMLInputElement).value).toBe("3");
  });

  it("mounts the 64px CROSSFADE CURVE editor, always active, over the overlap's own curve", () => {
    const key = seedOverlap();
    const { getByTestId, container } = render(OverlapInpaint);
    const wrapper = container.querySelector(".curve-editor") as HTMLElement;
    expect(wrapper).toBeTruthy();
    expect(getByTestId("envelope-node-0")).toBeTruthy();
    const region = getByTestId("envelope-node-0").closest('[data-region="envelope-overlay"]') as HTMLElement;
    expect(region.dataset.active).toBe("true");
    void key;
  });

  it("the INPAINT OVERLAP button is present, enabled, and a no-op this milestone", async () => {
    seedOverlap();
    const { getByTestId } = render(OverlapInpaint);
    const btn = getByTestId("inpaint-overlap-button");
    expect(btn.textContent?.trim()).toBe("▸ INPAINT OVERLAP");
    expect((btn as HTMLButtonElement).disabled).toBe(false);
    await fireEvent.click(btn);   // no throw, no network call -- M9 wires the job
  });

  it("data-help matches the four verified v3 ids (460, 464, 466, 467)", () => {
    seedOverlap();
    const { getByTestId } = render(OverlapInpaint);
    expect(getByTestId("overlap-chroma-xfade").getAttribute("data-help")).toBeTruthy();
    expect(getByTestId("overlap-override").getAttribute("data-help")).toBeTruthy();
    expect(getByTestId("overlap-steps").getAttribute("data-help")).toBeTruthy();
    expect(getByTestId("overlap-cfg").getAttribute("data-help")).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run them, expect failure**

```bash
cd /home/kim/Projects/sa3-studio-review/latent-forge && npx vitest run src/lib/forge/__tests__/overlapLabel.test.ts src/ui/modules/__tests__/OverlapInpaint.test.ts
```

Expected: `Failed to resolve import "../overlapLabel"`, and every `OverlapInpaint.test.ts` case
fails against the M1 stub's `<p class="pending">` markup (no `data-testid`s exist yet). Summary:
`Test Files  2 failed (2)`.

- [ ] **Step 3: Write `overlapLabel.ts`**

`latent-forge/src/lib/forge/overlapLabel.ts`:

```ts
// Turns an overlap's two clips into the info line spec §4.6.1 asks for ("which
// overlap, its two clip names"). ForgeClip has no `name` field -- only an
// AudioRef -- so "name" means whatever's most readable per ref kind, the same
// idea as v3's own `{{overlapInfo}}` (design_handoff/SA3 Studio v3.dc.html:2078),
// which showed `a.file -> b.file`.

import type { ForgeClip } from "./types";

const PLACEHOLDER = "?";

export function clipLabel(clip: ForgeClip | undefined): string {
  if (!clip) return PLACEHOLDER;
  const ref = clip.audio;
  switch (ref.kind) {
    case "crop": return ref.crop_id;
    case "render": return ref.file;
    case "file": return ref.rel.split(/[\\/]/).pop() ?? ref.rel;
    case "path": return ref.path.split(/[\\/]/).pop() ?? ref.path;
    case "upload": return ref.sha256.slice(0, 8);
  }
}

export function overlapInfoLine(
  overlap: { lane: 0 | 1 | 2 | 3; start_sec: number; end_sec: number },
  a: ForgeClip | undefined,
  b: ForgeClip | undefined,
): string {
  return (
    `lane ${overlap.lane + 1} · ${clipLabel(a)} → ${clipLabel(b)} · ` +
    `mask ${overlap.start_sec.toFixed(2)}–${overlap.end_sec.toFixed(2)} s`
  );
}
```

- [ ] **Step 4: Write `OverlapInpaint.svelte`**

`latent-forge/src/ui/modules/OverlapInpaint.svelte`:

```svelte
<script lang="ts">
  // Spec §4.6.1. Present only while view.selection.kind === "overlap"
  // (RightPaneModules.svelte's own filter, M1 T12) -- this component does not
  // re-check that; it derives the CURRENT overlap from the selection so it
  // never throws if it is ever mounted transiently during a selection change.
  import { overlapInfoLine } from "../../lib/forge/overlapLabel";
  import { arrangement } from "../../lib/stores/arrangement.svelte";
  import { view } from "../../lib/stores/view.svelte";
  import { dragScale } from "../../lib/actions/dragScale";
  import { HELP } from "../../lib/help/strings";
  import EnvelopeEditor from "../master/EnvelopeEditor.svelte";

  const key = $derived(view.selection.kind === "overlap" ? view.selection.key : null);
  const overlap = $derived(key ? arrangement.overlaps.find((o) => o.key === key) ?? null : null);
  // peekOverlapParams, NEVER overlapParams, inside a $derived: overlapParams seeds the store on
  // first read, and a write during a derived throws state_unsafe_mutation (Global Constraint #8).
  // Edits go through patch() -> setOverlapParams, which seeds; this derived then re-runs.
  const params = $derived(key ? arrangement.peekOverlapParams(key) : null);
  const clipA = $derived(overlap ? arrangement.clips.find((c) => c.id === overlap.a_id) : undefined);
  const clipB = $derived(overlap ? arrangement.clips.find((c) => c.id === overlap.b_id) : undefined);
  const info = $derived(overlap ? overlapInfoLine(overlap, clipA, clipB) : "");

  function patch(p: Parameters<typeof arrangement.setOverlapParams>[1]) {
    if (key) arrangement.setOverlapParams(key, p);
  }
</script>

{#if params}
  <div class="overlap">
    <p class="info">{info}</p>

    <span class="caption">CROSSFADE CURVE — drag a node or bend a segment</span>
    <div class="curve-editor">
      <EnvelopeEditor envelope={params.curve} active={true} onChange={(env) => patch({ curve: env })} />
    </div>

    <div class="row">
      <button
        class="toggle"
        class:on={params.chroma_xfade}
        data-testid="overlap-chroma-xfade"
        data-help={HELP.overlapChromaXfade}
        onclick={() => patch({ chroma_xfade: !params.chroma_xfade })}
      >{params.chroma_xfade ? "[ON]" : "[OFF]"}</button>
      <span class="label">CHROMA CROSSFADE</span>
    </div>

    <div class="row">
      <button
        class="toggle"
        class:on={params.override}
        data-testid="overlap-override"
        data-help={HELP.overlapOverride}
        onclick={() => patch({ override: !params.override })}
      >{params.override ? "[ON]" : "[OFF]"}</button>
      <span class="label">LOCAL STEPS / CFG</span>
    </div>

    <div class="field">
      <span class="fieldlabel">STEPS</span>
      <input
        type="number"
        data-testid="overlap-steps"
        data-help={HELP.overlapSteps}
        disabled={!params.override}
        value={params.steps}
        use:dragScale={{ min: 1, max: 100, int: true, value: params.steps, onValue: (v) => patch({ steps: v }) }}
        onchange={(e) => patch({ steps: parseInt((e.currentTarget as HTMLInputElement).value, 10) || 0 })}
      />
    </div>

    <div class="field">
      <span class="fieldlabel">CFG</span>
      <input
        type="number"
        step="0.1"
        data-testid="overlap-cfg"
        data-help={HELP.overlapCfg}
        disabled={!params.override}
        value={params.cfg}
        use:dragScale={{ min: 0, max: 64, value: params.cfg, onValue: (v) => patch({ cfg: v }) }}
        onchange={(e) => patch({ cfg: parseFloat((e.currentTarget as HTMLInputElement).value) || 0 })}
      />
    </div>

    <!-- M9 wires the real preview-job submission (spec §7.1); this milestone's
         button is a frame only, the same boundary as MIXDOWN (M1 T10) and the
         MIX tab's own ▸ MIXDOWN (M7 Writer A T5). -->
    <button
      class="inpaint"
      data-testid="inpaint-overlap-button"
      onclick={() => { /* no-op: M9 submits the inpaint job */ }}
    >▸ INPAINT OVERLAP</button>
  </div>
{/if}

<style>
  .overlap {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 8px 10px 12px;
    border-left: 3px solid var(--purple-strong);
    background: oklch(54% 0.10 300 / 0.08);
  }
  .info,
  .caption {
    margin: 0;
    font-size: 10px;
    color: var(--text-dim);
  }
  .curve-editor {
    position: relative;
    width: 100%;
    height: 64px;
    background: var(--panel2);
    border: 1px solid var(--border);
  }
  .row {
    display: flex;
    align-items: center;
    gap: 5px;
  }
  .label {
    font-size: 10px;
  }
  .toggle {
    background: var(--panel2);
    border: 1px solid var(--border);
    color: var(--text-dim);
    font-family: inherit;
    font-size: 10px;
    padding: 2px 6px;
    cursor: pointer;
  }
  .toggle.on {
    border-color: var(--purple-strong);
    color: var(--purple-strong);
  }
  .field {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .fieldlabel {
    width: 52px;
    font-size: 10px;
    color: var(--text-dim);
  }
  .field input {
    flex: 1;
    background: var(--panel2);
    border: 1px solid var(--border);
    color: var(--text);
    font-size: 10px;
    padding: 3px;
    cursor: ew-resize;
  }
  .field input:disabled {
    cursor: default;
    opacity: 0.5;
  }
  .inpaint {
    background: var(--purple-strong);
    border: 1px solid var(--purple-strong);
    color: white;
    font-size: 11px;
    font-weight: 600;
    padding: 6px;
    cursor: pointer;
  }
</style>
```

- [ ] **Step 5: Run them, expect pass**

```bash
cd /home/kim/Projects/sa3-studio-review/latent-forge && npx vitest run src/lib/forge/__tests__/overlapLabel.test.ts src/ui/modules/__tests__/OverlapInpaint.test.ts
```

Expected: `Test Files  2 passed (2)` / `Tests  15 passed (15)` (8 in `overlapLabel.test.ts`, 7 in
`OverlapInpaint.test.ts`).

- [ ] **Step 6: Commit**

```bash
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M7 T7: OVERLAP -- INPAINT module (spec 4.6.1) -- info line, 64px crossfade curve reusing M5's EnvelopeEditor, chroma crossfade + local STEPS/CFG override through arrangement.overlapParams/setOverlapParams, INPAINT OVERLAP button a no-op until M9"
```

---

### Task 8: The v1 → v2 project converter

**WHY.** I located and read the actual legacy v1 project store directly — it was NOT findable
under `latent-forge/` (that directory does not exist yet; nothing in this milestone chain has been
built), so I read it from the pre-rename tree M1 T15 re-homes from:
`sa3-studio/src/lib/store.svelte.ts` (`ProjectStore.toJSON`/`.loadJSON`, lines 606-649) plus
`sa3-studio/src/lib/types.ts` (`Clip`, `Lane`, `RenderParams`, `defaultLanes`, `LANE_IDS`) and
`sa3-studio/src/lib/musictime.ts` (`SnapMode`, `Meter`, `DEFAULT_METER`). This is the real v1 shape,
not the spec's one-paragraph summary (867–869) — every field below is cited to that file.

**The real v1 JSON** (`ProjectStore.toJSON()`, `store.svelte.ts:612-629`):
```
{ version: 1, meter: {bpm, beatsPerBar}, snap: SnapMode, pxPerSec: number,
  lanes: Lane[], clips: Clip[] }
```
— nothing else. No `name`, no `mix`/`master`/`chain`, no `overlaps`, no `renders`, no `ui`, no
`backbone`/`ckpt_path`. `Lane = {id: "drums"|"bass"|"other"|"vocals", label, color, muted, solo,
gain}` (`types.ts:183-190`, `LANE_IDS`, `types.ts:175`). `Clip = {id, laneId, startSec, durationSec,
offsetSec, source: ClipSource, latentState, encodedAt?, previewUrl?, serverPath?, latentPath?,
bpm?, downbeatSec?, render: RenderParams, pendingJobId?, lastRenderNote?}` (`types.ts:135-170`).
`ClipSource = {kind:"empty"} | {kind:"audio-file"; name; url} | {kind:"crop"; cropId} |
{kind:"render"; jobId; filename}` (`types.ts:115-119`). `RenderParams = {op: RenderOp; prompt;
negativePrompt?; steps; cfgScale; seed; samplerType?; distShift?; noiseLevel; apgScale?; mixBPath?;
promptRegion?; schedule?; windowSec?; overlapSec?; xfadeSec?; bendOps?}` (`types.ts:82-104`),
`RenderOp = "generate"|"decode"|"a2a_track"|"a2a_mix"|"longform"|"bend"` (`types.ts:47`).
`SnapMode = "bar"|"beat"|"1/8"|"1/16"|"1/32"|"edge"|"off"` (`musictime.ts:52`).

**Two findings that correct the brief and M5's own Normative table, both verified against source:**

1. **The brief's snap mapping is stale.** M7's brief and M5's own frozen Normative-names table
   (`docs/superpowers/plans/2026-09-17-latent-forge-m5-timeline-fidelity.md:5921`) both say v1
   spells snap steps as bare `"8"`/`"16"`/`"32"`, converted to `"1/8"`/`"1/16"`/`"1/32"`. The real
   v1 `SnapMode` (`musictime.ts:52`, quoted above) already spells them `"1/8"`/`"1/16"`/`"1/32"` —
   there is no bare-digit spelling anywhere in the source. Only `"off"` → `"free"` is a real
   mapping; the rest of v1's `SnapMode` union is already valid `v2` `SnapMode`
   (`docs/superpowers/plans/2026-09-17-latent-forge-m5-timeline-fidelity.md:887`, which adds only
   `"lane"` as a new v2-only mode with no v1 counterpart). I ship a mapping table that handles BOTH
   readings defensively (`"8"→"1/8"` etc. are harmless no-ops if no such file exists, real safety
   if an even older save does), and flag the conflict below rather than silently trusting either
   source.
2. **v2's `ForgeClip` (M1 T3, frozen) has no field for a clip's `op`.** v1's `RenderOp` and every
   op-specific field (`mixBPath`, `promptRegion`, the longform arc-grammar `schedule` *string*,
   `windowSec`/`overlapSec`/`xfadeSec`, `bendOps`) have no home in `ProjectV2`'s `ForgeClip` — I
   checked M4's own plan (`docs/superpowers/plans/2026-09-18-latent-forge-m4-prompt-sigma.md:2840`,
   the OP select task) and it takes `op` as a **prop supplied by whichever store ends up owning
   clips**, not a `ForgeClip` field; I then checked all of M5's plan for anywhere `ForgeClip` gains
   an `op` field and found none. So these v1 fields are not merely hard to convert, they are
   **structurally unrepresentable** in the current, frozen `ProjectV2` — they are dropped, and this
   is not this converter's gap to paper over.
3. **v1's `ClipSource.kind === "empty"` and `"audio-file"` have no v2 `AudioRef`.** `AudioRef` (M1
   T3) is a closed union of five kinds, none of which is "nothing yet" or "an in-browser blob URL".
   v1's own `toJSON()` already drops `previewUrl` for an `"audio-file"` clip
   (`store.svelte.ts:622`), and its own `loadJSON()` already reports these as needing a manual
   relink (`relinkNeeded`, `store.svelte.ts:648`) — so v1 itself treats these as not durably saved.
   **Decision:** clips whose v1 source is `"empty"` or `"audio-file"` are dropped from the
   converted project rather than given a synthetic/invalid `AudioRef`; `crop` and `render` sources
   convert cleanly since their identifiers (`cropId`, `jobId`/`filename`) are exactly `AudioRef`'s
   own `crop`/`render` shapes.

**Files:**
- Create: `latent-forge/src/lib/forge/convertProjectV1.ts`,
  `latent-forge/src/lib/forge/__tests__/convertProjectV1.test.ts`

**Interfaces:**
- Consumes the real v1 shape above (no import — v1 lives in `sa3-studio/`, outside `latent-forge/`,
  and is read only as JSON `unknown` input; this function never imports v1 types).
- Consumes `ProjectV2`, `ForgeLane`, `ForgeClip`, `AudioRef`, `RenderSettings` from
  `src/lib/forge/types.ts` (M1 T3).
- Consumes `CHAIN_DEFAULTS`, `MIX_DEFAULT`, `MASTER_DEFAULT`, `BASE_DEFAULTS`,
  `cloneRenderSettings` from `src/lib/forge/defaults.ts` (M1 T4).
- Consumes `SnapMode` from `src/lib/math/snap.ts` (M5 T2) — `"bar"|"beat"|"1/8"|"1/16"|"1/32"|
  "lane"|"edge"|"free"`.
- Produces: `convertProjectV1(raw: unknown): ProjectV2`.

- [ ] **Step 1: Write the failing test**

`latent-forge/src/lib/forge/__tests__/convertProjectV1.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { BASE_DEFAULTS, CHAIN_DEFAULTS, MASTER_DEFAULT, MIX_DEFAULT } from "../defaults";
import { convertProjectV1 } from "../convertProjectV1";

function v1Base() {
  return {
    version: 1,
    meter: { bpm: 128, beatsPerBar: 4 },
    snap: "beat",
    pxPerSec: 90,
    lanes: [
      { id: "drums", label: "Drums", color: "var(--purple)", muted: false, solo: false, gain: 1 },
      { id: "bass", label: "Bass", color: "var(--green)", muted: true, solo: false, gain: 0.8 },
      { id: "other", label: "Other", color: "var(--accent)", muted: false, solo: false, gain: 1 },
      { id: "vocals", label: "Vocals", color: "var(--neutral-lane)", muted: false, solo: true, gain: 1 },
    ],
    clips: [] as unknown[],
  };
}

describe("lanes: drums/bass/other/vocals -> LANE 1..4 (spec 867-869)", () => {
  it("maps ids to indices 0-3 and names LANE n, keeping mute/solo/gain, seeding CHAIN_DEFAULTS", () => {
    const out = convertProjectV1(v1Base());
    expect(out.lanes.map((l) => l.index)).toEqual([0, 1, 2, 3]);
    expect(out.lanes.map((l) => l.name)).toEqual(["LANE 1", "LANE 2", "LANE 3", "LANE 4"]);
    expect(out.lanes[1].muted).toBe(true);
    expect(out.lanes[1].gain).toBe(0.8);
    expect(out.lanes[3].solo).toBe(true);
    for (const lane of out.lanes) expect(lane.chain).toEqual(CHAIN_DEFAULTS);
  });
});

describe("snap: off -> free, digits or 1/n pass through as 1/n (M5's own table cites bare digits; the real v1 SnapMode, musictime.ts:52, already spells 1/8 -- both are handled)", () => {
  it("off -> free", () => {
    expect(convertProjectV1({ ...v1Base(), snap: "off" }).snap).toBe("free");
  });
  it("1/8 (the real v1 spelling) passes through unchanged", () => {
    expect(convertProjectV1({ ...v1Base(), snap: "1/8" }).snap).toBe("1/8");
  });
  it("a bare-digit spelling, if ever encountered, still maps to 1/n", () => {
    expect(convertProjectV1({ ...v1Base(), snap: "16" }).snap).toBe("1/16");
  });
  it("bar/beat/edge pass through unchanged", () => {
    expect(convertProjectV1({ ...v1Base(), snap: "edge" }).snap).toBe("edge");
  });
  it("an unrecognised value falls back to the arrangement store's own default, lane", () => {
    expect(convertProjectV1({ ...v1Base(), snap: "nonsense" }).snap).toBe("lane");
  });
});

describe("clips: crop and render sources convert; empty and audio-file are dropped (no v2 AudioRef exists for them)", () => {
  it("a crop clip converts with defaults filled into render", () => {
    const out = convertProjectV1({
      ...v1Base(),
      clips: [{
        id: "clip_1", laneId: "bass", startSec: 4, durationSec: 8, offsetSec: 0,
        source: { kind: "crop", cropId: "000412" }, latentState: "valid",
        bpm: 140, downbeatSec: 0.3,
        render: { op: "decode", prompt: "warm pad", negativePrompt: "vocals", steps: 30, cfgScale: 5, seed: 7, noiseLevel: 0.4 },
      }],
    });
    expect(out.clips).toHaveLength(1);
    const c = out.clips[0];
    expect(c.lane).toBe(1);
    expect(c.audio).toEqual({ kind: "crop", crop_id: "000412" });
    expect(c.start_sec).toBe(4);
    expect(c.dur_sec).toBe(8);
    expect(c.native_bpm).toBe(140);
    expect(c.downbeats_sec).toEqual([0.3]);
    expect(c.detune_cents).toBe(0);
    expect(c.loop).toBe(false);
    expect(c.a2a).toBeNull();
    expect(c.history).toEqual([]);
    expect(c.render.prompt).toBe("warm pad");
    expect(c.render.negative_prompt).toBe("vocals");
    expect(c.render.steps).toBe(30);
    expect(c.render.cfg_scale).toBe(5);
    expect(c.render.seed).toBe(7);
    // fields v1 never had stay at BASE_DEFAULTS
    expect(c.render.schedule).toEqual(BASE_DEFAULTS.schedule);
    expect(c.render.duration_sec).toBe(8);   // filled from the clip's own duration
  });

  it("a render-sourced clip converts jobId/filename to job_id/file", () => {
    const out = convertProjectV1({
      ...v1Base(),
      clips: [{
        id: "clip_2", laneId: "drums", startSec: 0, durationSec: 5, offsetSec: 0,
        source: { kind: "render", jobId: "forge-1", filename: "out_00.wav" }, latentState: "none",
        render: { op: "generate", prompt: "kick", steps: 24, cfgScale: 6, seed: -1, noiseLevel: 0.4 },
      }],
    });
    expect(out.clips[0].audio).toEqual({ kind: "render", job_id: "forge-1", file: "out_00.wav" });
  });

  it("drops empty and audio-file clips, since v1 itself never durably saved their audio", () => {
    const out = convertProjectV1({
      ...v1Base(),
      clips: [
        { id: "e", laneId: "drums", startSec: 0, durationSec: 4, offsetSec: 0, source: { kind: "empty" }, latentState: "none", render: { op: "generate", prompt: "", steps: 24, cfgScale: 6, seed: -1, noiseLevel: 0.4 } },
        { id: "f", laneId: "drums", startSec: 4, durationSec: 4, offsetSec: 0, source: { kind: "audio-file", name: "x.wav", url: "blob:x" }, latentState: "none", render: { op: "generate", prompt: "", steps: 24, cfgScale: 6, seed: -1, noiseLevel: 0.4 } },
      ],
    });
    expect(out.clips).toHaveLength(0);
  });
});

describe("a v1 file with no mix/master/chain data converts to the defaults per lane, never throws (brief's own rule, generalised)", () => {
  it("fills mix, master and every lane's chain from the M1 defaults", () => {
    const out = convertProjectV1(v1Base());
    expect(out.mix).toEqual(MIX_DEFAULT);
    expect(out.master).toEqual(MASTER_DEFAULT);
  });

  it("never throws on missing lanes/clips or a garbage top level, and fills every ProjectV2 field", () => {
    expect(() => convertProjectV1({})).not.toThrow();
    expect(() => convertProjectV1(null)).not.toThrow();
    expect(() => convertProjectV1("not an object")).not.toThrow();
    const out = convertProjectV1({});
    expect(out.version).toBe(2);
    expect(out.lanes).toHaveLength(4);
    expect(out.clips).toEqual([]);
    expect(out.overlaps).toEqual({});
    expect(out.renders).toEqual([]);
    expect(out.mixdown).toBeNull();
    expect(out.preview).toBeNull();
    expect(out.ui).toEqual({ bottomTab: "prompt", modules: ["files", "lane-chain"], sideOpen: true, terminal: "pane" });
  });
});

describe("previewAudio is never read from v1 (spec 9.2, M5's Normative table)", () => {
  it("ignores a v1 clip's previewUrl entirely: the required ForgeClip.previewAudio is always null", () => {
    const out = convertProjectV1({
      ...v1Base(),
      clips: [{
        id: "clip_3", laneId: "drums", startSec: 0, durationSec: 4, offsetSec: 0,
        source: { kind: "crop", cropId: "000900" }, latentState: "valid",
        previewUrl: "http://example/preview.wav",
        render: { op: "decode", prompt: "", steps: 24, cfgScale: 6, seed: -1, noiseLevel: 0.4 },
      }],
    });
    // ForgeClip.previewAudio is a REQUIRED field (M5 T10: `AudioRef | null`), so "never written"
    // means null, not absent -- the v1 previewUrl must not leak into it or anywhere else.
    expect(out.clips[0].previewAudio).toBeNull();
    expect(JSON.stringify(out)).not.toContain("preview.wav");
  });
});
```

- [ ] **Step 2: Run it, expect failure**

```bash
cd /home/kim/Projects/sa3-studio-review/latent-forge && npx vitest run src/lib/forge/__tests__/convertProjectV1.test.ts
```

Expected: `Failed to resolve import "../convertProjectV1"`.

- [ ] **Step 3: Write the converter**

`latent-forge/src/lib/forge/convertProjectV1.ts`:

```ts
// Converts a v1 project (the pre-rename app, sa3-studio/src/lib/store.svelte.ts
// `toJSON()`) into ProjectV2 (spec §9.2). The real v1 shape was read directly
// from that file and from sa3-studio/src/lib/types.ts / musictime.ts -- NOT
// guessed from the spec's one paragraph (867-869), which names only the lane
// rename and the RenderSettings default-fill.
//
// Two things v1 has that ProjectV2's frozen ForgeClip cannot represent, and are
// therefore dropped rather than forced: the per-clip RenderOp and its
// op-specific fields (mixBPath, promptRegion, the longform arc-grammar
// `schedule` STRING, windowSec/overlapSec/xfadeSec, bendOps) -- ForgeClip has no
// `op` field at all (verified against M1 T3 and M4/M5's own plans); and a v1
// clip whose source is "empty" or "audio-file", which has no representable
// AudioRef (v1 itself never durably saved either -- its own toJSON() drops
// previewUrl for audio-file clips and loadJSON() already flags them for manual
// relink).
//
// Never throws: this is the ONLY project-load path for an old save, so a
// garbage or partial input degrades to defaults rather than blocking the load.

import {
  BASE_DEFAULTS, CHAIN_DEFAULTS, cloneRenderSettings, MASTER_DEFAULT, MIX_DEFAULT,
} from "./defaults";
import type { AudioRef, ForgeClip, ForgeLane, ProjectV2, RenderSettings } from "./types";

const V1_LANE_IDS = ["drums", "bass", "other", "vocals"] as const;

/** v1's own SnapMode (musictime.ts:52) is bar|beat|1/8|1/16|1/32|edge|off -- already
 *  spelled 1/n, not bare digits, contrary to what M5's own Normative table and this
 *  milestone's brief both claim (see this task's WHY). Handled defensively both ways. */
const SNAP_V1_TO_V2: Record<string, string> = {
  off: "free",
  "8": "1/8", "16": "1/16", "32": "1/32",
  "1/8": "1/8", "1/16": "1/16", "1/32": "1/32",
  bar: "bar", beat: "beat", edge: "edge",
};

function isObj(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

function asArray(v: unknown): unknown[] {
  return Array.isArray(v) ? v : [];
}

function convertSnap(raw: unknown): ProjectV2["snap"] {
  if (typeof raw === "string" && raw in SNAP_V1_TO_V2) return SNAP_V1_TO_V2[raw];
  return "lane";   // ArrangementStore's own default (M5 T1)
}

function convertAudio(source: unknown): AudioRef | null {
  if (!isObj(source)) return null;
  switch (source.kind) {
    case "crop":
      return typeof source.cropId === "string" ? { kind: "crop", crop_id: source.cropId } : null;
    case "render":
      return typeof source.jobId === "string" && typeof source.filename === "string"
        ? { kind: "render", job_id: source.jobId, file: source.filename }
        : null;
    // "empty" and "audio-file" have no v2 AudioRef -- see this task's WHY.
    default:
      return null;
  }
}

function convertRender(v1render: unknown, fallbackDurationSec: number): RenderSettings {
  const out = cloneRenderSettings(BASE_DEFAULTS);
  if (!isObj(v1render)) {
    out.duration_sec = fallbackDurationSec;
    return out;
  }
  if (typeof v1render.prompt === "string") out.prompt = v1render.prompt;
  if (typeof v1render.negativePrompt === "string") out.negative_prompt = v1render.negativePrompt;
  if (typeof v1render.steps === "number") out.steps = v1render.steps;
  if (typeof v1render.cfgScale === "number") out.cfg_scale = v1render.cfgScale;
  if (typeof v1render.seed === "number") out.seed = v1render.seed;
  if (typeof v1render.apgScale === "number") out.apg_scale = v1render.apgScale;
  if (typeof v1render.samplerType === "string") out.sampler_type = v1render.samplerType;
  // schedule (ScheduleSpec) and cfg_interval_progress have no v1 analogue --
  // v1's `schedule` field, when present, is a longform arc-grammar STRING, an
  // entirely different thing, and is not read here.
  out.duration_sec = fallbackDurationSec;
  return out;
}

function convertLanes(raw: unknown): ForgeLane[] {
  const lanes = asArray(raw);
  return [0, 1, 2, 3].map((index) => {
    const id = V1_LANE_IDS[index];
    const src = lanes.find((l) => isObj(l) && l.id === id);
    return {
      index: index as 0 | 1 | 2 | 3,
      name: `LANE ${index + 1}`,
      muted: isObj(src) && typeof src.muted === "boolean" ? src.muted : false,
      solo: isObj(src) && typeof src.solo === "boolean" ? src.solo : false,
      gain: isObj(src) && typeof src.gain === "number" ? src.gain : 1,
      chain: structuredClone(CHAIN_DEFAULTS),
    };
  });
}

function convertClips(raw: unknown): ForgeClip[] {
  const out: ForgeClip[] = [];
  for (const c of asArray(raw)) {
    if (!isObj(c)) continue;
    const audio = convertAudio(c.source);
    if (!audio) continue;   // "empty" / "audio-file" / malformed -- dropped, see WHY
    const laneIndex = V1_LANE_IDS.indexOf((c.laneId as (typeof V1_LANE_IDS)[number]) ?? "drums");
    const durSec = typeof c.durationSec === "number" ? c.durationSec : 0;
    out.push({
      id: typeof c.id === "string" ? c.id : `clip_${out.length}`,
      lane: (laneIndex >= 0 ? laneIndex : 0) as 0 | 1 | 2 | 3,
      start_sec: typeof c.startSec === "number" ? c.startSec : 0,
      offset_sec: typeof c.offsetSec === "number" ? c.offsetSec : 0,
      dur_sec: durSec,
      loop: false,   // v1 has no loop concept
      audio,
      native_bpm: typeof c.bpm === "number" ? c.bpm : null,
      detune_cents: 0,   // v1 has no per-clip detune
      downbeats_sec: typeof c.downbeatSec === "number" ? [c.downbeatSec] : [],
      render: convertRender(c.render, durSec),
      a2a: null,   // v1 has no per-clip A2A state
      latentState: c.latentState === "valid" || c.latentState === "stale" ? c.latentState : "none",
      history: [],
      // previewUrl is intentionally never read (spec §9.2: previewAudio is
      // in-memory only, and the converter neither reads nor writes it). The
      // field itself is required on ForgeClip (M5 T10), so it is always null.
      previewAudio: null,
    });
  }
  return out;
}

export function convertProjectV1(raw: unknown): ProjectV2 {
  const data = isObj(raw) ? raw : {};
  const meter = isObj(data.meter) ? data.meter : {};
  return {
    version: 2,
    name: "",
    meter: {
      bpm: typeof meter.bpm === "number" ? meter.bpm : 120,
      beatsPerBar: typeof meter.beatsPerBar === "number" ? meter.beatsPerBar : 4,
    },
    snap: convertSnap(data.snap),
    view: { pxPerSec: typeof data.pxPerSec === "number" ? data.pxPerSec : 80, scrollSec: 0 },
    lanes: convertLanes(data.lanes),
    clips: convertClips(data.clips),
    overlaps: {},
    mix: structuredClone(MIX_DEFAULT),
    master: structuredClone(MASTER_DEFAULT),
    defaults: cloneRenderSettings(BASE_DEFAULTS),
    // v1 records no backbone. "medium-base" is STAGE_BACKBONE.BASE (M4 T1), the stage
    // settings.svelte.ts starts in, so importing a v1 file never triggers the model rebuild
    // that Task 9's loader performs when a project's backbone differs from the current stage.
    backbone: "medium-base",
    ckpt_path: null,
    renders: [],
    mixdown: null,
    preview: null,
    ui: { bottomTab: "prompt", modules: ["files", "lane-chain"], sideOpen: true, terminal: "pane" },
  };
}
```

- [ ] **Step 4: Run it, expect pass**

```bash
cd /home/kim/Projects/sa3-studio-review/latent-forge && npx vitest run src/lib/forge/__tests__/convertProjectV1.test.ts
```

Expected: `Tests  12 passed (12)`.

- [ ] **Step 5: Commit**

```bash
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M7 T8: v1 -> v2 project converter, built against the real legacy shape (sa3-studio/src/lib/store.svelte.ts), not the spec's one paragraph -- drops what ProjectV2 structurally cannot represent (per-clip op, empty/audio-file sources) rather than forcing it"
```

---

### Task 9: Sessions, master preset and autosave

**WHY.** M1 T10's `TopBar.svelte` already renders a SESSION select (`data-testid="session-select"`)
that lists `forgeApi.sessions()` results and calls a prop `onsession(name)` whose only real
implementation, in `App.svelte`, is `onsession={(name) => (session = name)}` — it changes which
name is highlighted and nothing else, exactly as M1's own comment says ("Loading a session is M7's
too"). The MASTER PRESET select is the same shape, and its SAVE button is hard-`disabled` with a
comment pointing at this milestone. M1 T15 additionally carried the app's ONLY working persistence
(`saveProject`/`loadProject`, a client-side download/upload pair reading `project.toJSON()` /
`project.loadJSON()`) as a stated *temporary* measure, to be replaced by this exact task.

**A real cross-milestone gap, found while tracing what `saveProject`/`loadProject` actually call.**
`project` is the v1 store (`sa3-studio/src/lib/store.svelte.ts`, Task 8's WHY). M5's own
Normative-names table claims "Task 7 is the swap point: once `overlaps.ts` is extracted and
`arrangement` is complete, `App.svelte`, `keyboard.ts` and every re-homed timeline component rewire
to `arrangement` and the v1 `project` store is deleted"
(`docs/superpowers/plans/2026-09-17-latent-forge-m5-timeline-fidelity.md:5925`). I read M5's actual
Task 7 body in full (`Overlap regions`) and it touches only
`src/lib/math/overlaps.ts`/`src/ui/timeline/OverlapBox.svelte`/`Timeline.svelte` — it never touches
`App.svelte`, `TopBar.svelte` or `keyboard.ts`. I then grepped the entire M5 plan for any edit to
those three files and found none. **So, as written, the v1 `project` store is never actually
deleted or rewired, and `TopBar.svelte`'s `saveProject`/`loadProject` — and possibly the keyboard
handlers and transport buttons — may still be reading/writing the orphaned v1 store rather than
`arrangement`.** This is a real defect spanning M1/M5, not something Tasks 6-10 can fix (rewiring
`App.svelte`'s keyboard actions and the transport is well outside "sessions, master preset,
autosave"), so I flag it in Open Questions for FLATLINE to route to WINTERMUTE, same as the
`ModuleShell`/`viewStore` defects the brief already flags. What I *can* guarantee is that **my own
session/autosave code never touches `project`** — it reads and writes only `arrangement`, `view`
and `settings` (below), and removing `saveProject`/`loadProject` from `TopBar.svelte` removes the
only place in that file that referenced the orphaned store.

**Where `defaults`/`backbone`/`ckpt_path` come from.** `ProjectV2.defaults: RenderSettings` is
`session.defaults` per spec §7.2 — owned by `settings.svelte.ts`'s singleton `settings` (M4,
`docs/superpowers/plans/2026-09-18-latent-forge-m4-prompt-sigma.md:137`, field `defaults =
$state<RenderSettings>(...)`, a plain public field, directly assignable). Its own doc comment says
`ckptPath` is "carried in the project JSON (9.2)"
(`docs/superpowers/plans/2026-09-18-latent-forge-m4-prompt-sigma.md:410`), confirming `settings` is
the intended source for `ckpt_path` too; I use `settings.backboneId` (`STAGE_BACKBONE[stage]`) for
`backbone` on the same reasoning. **`backboneId` is a getter over `settings.stage`** (M4 plan line
427), so writing `backbone` out is not enough — `applyProject` also restores it, by mapping the saved
backbone back through `STAGE_BACKBONE` (`{POST: "medium", BASE: "medium-base"}`, M4 plan lines
337-340) and assigning `settings.stage` directly. Not through `setStage()`, which would overwrite
`defaults`' `steps`/`sampler_type`/`schedule` with the stage defaults — the saved `defaults` are
restored right after and must win. A backbone outside that map (`small-music`, `small-music-base`
— reachable only through the MODEL select, which nothing wires to `settings`, see below) leaves the
stage unchanged. Because the stage is **session-level and rebuilds the model** (M4 T9's
`confirmStage` calls `forgeApi.setBackbone` before `setStage`), `loadSession` does the same when the
restored stage differs from the current one: it calls `forgeApi.setBackbone(STAGE_BACKBONE[stage])`,
and on failure puts `settings.stage` back so the client never claims a model the server did not
load. **Note, not fixed here:** `TopBar.svelte`'s own `model`/
`modelFolder` `$state` (M1 T10, local to `App.svelte`) is a *different* piece of state that is
never wired to `settings` by any milestone I can find — another gap, flagged below, not this
task's to fix.

**Another verified gap, in the opposite direction from what M4's own table claims**: `settings.attach(source)` (the seam that makes PROMPT + SIGMA / ADVANCED SAMPLING actually read/write a
selected clip's or overlap's own `render`, rather than always `session.defaults`) is never called
outside test files anywhere in M1, M4 or M5 — I grepped both plans for every occurrence of
`.attach(` and every hit outside a `__tests__` file is zero. This does not block Task 9: a clip's
own `render`/`a2a` and an overlap's own `render`/`steps`/`cfg` are plain fields on
`arrangement.clips[]` / `arrangement.overlapParams()` regardless of whether `settings` is wired to
read them, so serialising them is unaffected. It does mean the PROMPT + SIGMA pane may currently
always edit `session.defaults` no matter what is selected — flagged below, again not mine to fix
under "sessions, master preset, autosave."

**Naming a session or a master preset that does not exist yet.** Neither the v3 drawing nor the
spec gives either SAVE affordance a name-entry field — the SESSION select only ever lists existing
names (§6.3's `GET /forge/sessions`), and the MASTER PRESET select the same. I use `window.prompt()`
to name a brand-new session/preset (asked only when nothing is already selected), which needs no
new markup beyond the two SAVE buttons the drawing/M1 already reserve space for, and is trivially
mockable in a test. Flagged as an authored decision, open for a real name-entry field later.

**Abort-listener-ordering, applied where it actually fits.** `forgeApi.session(name)` (M1 T5) has
**no `AbortSignal` parameter** — its whole signature is `(name: string) => Promise<ProjectV2>` — so
there is nothing to abort. The HANDOUT's rule ("an abort listener added after the signal already
fired never runs") is about a promise that never settles; the analogous risk here is a **stale
response applied after a second, newer selection**, which I guard with a monotonic sequence number
captured before the fetch and checked after it resolves — the same "check first, don't rely on
a callback firing later" discipline, adapted to an API with no signal to check.

**Launch must never overwrite a saved session — M1's auto-select is removed.** M1 T10's
`loadTopBar` does `if (!session && sessions.length > 0) session = sessions[0].name` (M1 plan line
5502), so `session` is never empty once the list arrives (the mock lists three, M1 plan lines
2489-2493). Two things break on that: spec §9.2's "SESSION select shows `unsaved` until named" can
never be seen, and an autosave keyed on "the current session name" would PUT the blank launch
arrangement over whichever session happens to be listed first, two seconds after the tab opens —
data loss. This task deletes that line, so a fresh tab starts `unsaved`, and — independently, so a
future auto-select cannot reintroduce the bug — autosave only writes to a session that was **armed**
by a successful load or an explicit SAVE (`createSnapshotAutosave` below).

**Autosave tracks the serialised project, not a few references.** Every control in this milestone
mutates in place (Global Constraint #1), so an effect that reads `arrangement.lanes`/`.mix`/`.master`
as bare references plus `clips.length` never re-runs for a chain slot, a mix node, a clip move or a
prompt edit. The effect instead computes `JSON.stringify(serializeProject({name}))`; `$state.snapshot`
reads every field through the proxies, so the effect depends on all of them, and the autosave
compares that string with the last one saved (or loaded), so an effect re-run that changed nothing
saves nothing.

**v1 files still need a way in.** M1 T15's LOAD button — which this task removes along with the v1
`project` store it read — was the only path a v1 JSON file had into the app, and server sessions
are always v2. Spec §9.2 still says "Version 1 files (the existing app) load through a converter",
so this task keeps a minimal replacement: an **IMPORT** button beside the SESSION select opening a
hidden `<input type="file" accept="application/json">`. The chosen file goes through
`convertProjectV1` (or straight to `applyProject` if it already says `version: 2`), and the result
is `unsaved` until SAVE names it — an imported file belongs to no server session yet, so autosave
stays off for it. `forgeApi.session()` results take the same `version === 2 ? … : convertProjectV1`
branch, so a hand-copied v1 file on the server loads too.

**Files:**
- Create: `latent-forge/src/lib/forge/projectSerializer.svelte.ts` (`.svelte.ts` because it calls
  the `$state.snapshot` rune — Global Constraint #7),
  `latent-forge/src/lib/forge/__tests__/projectSerializer.test.ts`
- Create: `latent-forge/src/lib/forge/autosave.ts`,
  `latent-forge/src/lib/forge/__tests__/autosave.test.ts`
- Create: `latent-forge/src/lib/forge/sessionName.ts`,
  `latent-forge/src/lib/forge/__tests__/sessionName.test.ts`
- Modify: `latent-forge/src/ui/shell/TopBar.svelte` — **removes** the M1 T15 `saveProject`/
  `loadProject` functions, their hidden `<input type="file">`, the `notice` state and the
  `data-testid="save-project"`/`"load-project"` buttons (the file loses
  `import { project } from "../../lib/store.svelte"` and every reference to `project`); **adds** an
  `unsaved` option to the SESSION select while no session is named, `data-testid="session-save"`
  and `data-testid="session-import"` (+ its hidden `"session-import-file"` input) beside the SESSION
  select, and enables the existing `data-testid="master-preset-save"` button (hard-`disabled` in
  M1 T10) with a `data-help`.
- Modify: `latent-forge/src/ui/shell/__tests__/topBar.test.ts` (M1 T10) — its one assertion that
  `master-preset-save` is disabled "until M7 owns presets" flips; M7 is that milestone.
- Modify: `latent-forge/src/App.svelte` — removes M1's `sessions[0]` auto-select, wires
  `onsession`/`onmasterpreset` to real loads, adds the session save/import and master-preset save
  handlers, starts the autosave watcher.
- Modify: `latent-forge/src/ui/shell/RightPaneModules.svelte` (M1 T12) — the live `litModules`
  snapshot and `<AdvancedSampling latch=…>` (Step 5).
- Modify: `latent-forge/src/ui/prompt/PromptSigmaTab.svelte` (M4 T10) — `<SigmaColumn slots=…>`
  (Step 5).
- Modify: `docs/latent-forge/extract_help.mjs` (append `masterPresetSave`, `sessionSave`,
  `sessionImportV1` to `NEW_STRINGS`); regenerated `latent-forge/src/lib/help/strings.ts`;
  `latent-forge/src/lib/help/__tests__/strings.test.ts` (total 109 → **112**, the final count).
- Create: `latent-forge/src/lib/help/__tests__/sessionHelp.test.ts`
- Create: `latent-forge/src/ui/shell/__tests__/topBarSessions.test.ts`
- Create: `latent-forge/src/ui/shell/__tests__/rightPaneModules.test.ts`

**Interfaces:**
- Consumes `forgeApi.sessions()`, `forgeApi.session(name): Promise<ProjectV2>`,
  `forgeApi.saveSession(name, project: ProjectV2)`, `forgeApi.presets(level)`,
  `forgeApi.preset(level, name)`, `forgeApi.savePreset(level, name, payload)`,
  `forgeApi.setBackbone(id)` from `src/lib/forge/api.ts` (M1 T5, frozen — restated verbatim per
  "an implementing agent sees ONE task").
- Consumes `convertProjectV1(raw: unknown): ProjectV2` from `src/lib/forge/convertProjectV1.ts`
  (this milestone's Task 8).
- Consumes `arrangement` (`bpm, beatsPerBar, snap, lanes, clips, pxPerSec, scrollSec, mix, master,
  overlaps: Overlap[], peekOverlapParams(key), setOverlapParams(key, patch), setBpm, setSnap,
  setScrollSec, setDetune, setPreviewAudio, moveClip(id, startSec)`) and the constants
  `MIN_PX_PER_SEC`/`MAX_PX_PER_SEC` from `src/lib/stores/arrangement.svelte.ts` (M5 T1/T10, extended
  by Task 3). **There is no `arrangement.setPxPerSec`** — `applyProject` assigns `pxPerSec`
  directly, clamped the way M5's own `zoomBy` clamps.
- Consumes `view` (`snapshotUi(): UiState`, `restoreUi(ui)`, `appendLog(text, level)`, `selection`,
  `activeLane`, `select`, `clearSelection`, `openModule`, `closeModule`) from
  `src/lib/stores/view.svelte.ts` (M1 T7 — the export is `view`, Global Constraint #3).
- Consumes `settings` (`defaults: RenderSettings`, `stage: ModelStage`, `ckptPath: string | null`,
  getter `backboneId: string`), `STAGE_BACKBONE: Record<ModelStage, string>` and
  `type ModelStage` from `src/lib/stores/settings.svelte.ts` (M4 T1, M4 plan lines 332-487).
- Consumes `ProjectV2`, `ForgeLane`, `ForgeClip`, `OverlapParams`, `MixSpec`, `MasterChain`,
  `LaneChain`, `RenderSettings` from `src/lib/forge/types.ts` (M1 T3, M5 T10's `previewAudio`).
- Consumes `CHAIN_DEFAULTS`, `cloneRenderSettings` from `src/lib/forge/defaults.ts` (M1 T4).
- Consumes `litModules`, `MODULE_ORDER`, `moduleTitle`, `type ModuleStateSnapshot` from
  `src/lib/forge/nonDefault.ts` (M1 T12); `AdvancedSampling`'s `latch?: LatchState` prop (M4 plan
  line 4741 — a `LaneChain` satisfies `LatchState` structurally, M4 plan line 515) and
  `SigmaColumn`'s `slots?: readonly LatchSlot[]` prop (M4 plan line 4076).
- Produces, from `src/lib/forge/sessionName.ts`: `SESSION_NAME_RE = /^[A-Za-z0-9._-]{1,80}$/`
  (spec §6.3, verbatim), `isValidSessionName(name: string): boolean`.
- Produces, from `src/lib/forge/projectSerializer.svelte.ts`: `serializeProject(opts: {name:
  string}): ProjectV2` (plain data — every `$state` read goes through `$state.snapshot`, every clip's
  `previewAudio` is written as `null`, overlaps are read with the non-seeding `peekOverlapParams`),
  `applyProject(project: ProjectV2): void` (also restores `settings.stage` from `backbone`, and sets
  every clip's `previewAudio` to `null`), `type MasterPresetPayload = {lanes: {chain:
  LaneChain}[]; clips: {id: string; lane: 0|1|2|3; start_sec: number; offset_sec: number; dur_sec:
  number; loop: boolean; native_bpm: number|null; detune_cents: number; a2a: ForgeClip["a2a"]}[];
  mix: MixSpec; master: MasterChain; defaults: {schedule: RenderSettings["schedule"]; prompt:
  string}}`, `buildMasterPresetPayload(): MasterPresetPayload`, `applyMasterPreset(payload:
  MasterPresetPayload): void`.
- Produces, from `src/lib/forge/autosave.ts`: `createAutosave(save: () => void, delayMs?: number):
  {trigger(): void; cancel(): void}` (the bare 2 s debounce) and `createSnapshotAutosave(save: (name:
  string, snapshot: string) => void, delayMs?: number): {arm(name: string, snapshot: string): void;
  observe(name: string, snapshot: string): void; cancel(): void}` — `observe` never saves until
  `arm` has named that session (an empty name disarms), saves only a snapshot that differs from the
  last armed/saved one, and `arm`ing a different name first flushes a still-pending save under its
  own, old name.
- **Master preset's exact scope** (spec §9.3, quoted): "the whole project minus `clips[*].audio`
  refs and `renders` — every lane chain, clip layout (positions, trims, BPM, detune, A2A settings),
  mix order and node values, master chain, sampling schedule and default prompt." The opening
  clause ("whole project minus two things") and the enumeration that follows it do not fully
  reconcile — the enumeration is narrower (it never mentions `name`, `view`, `ui`, `backbone`,
  `ckpt_path`, or `defaults` fields other than `schedule`/`prompt`). I ship the literal enumeration
  as `MasterPresetPayload`'s own shape (not a trimmed `ProjectV2`), because it is the one spec text
  actually names field by field, and because a full `render`-level preset already exists separately
  (M4, §9.3's `render` level covers every ADVANCED SAMPLING field) — folding all of `defaults` into
  `master` too would make the two levels redundant. Recall matches clip entries by `id` against
  `arrangement.clips` (a master preset restores a *snapshot of the same session's arrangement*, not
  a transplant into a different one — clip ids from a different project would simply not match and
  are skipped) and patches lane `chain` by `index`. This is a documented judgment call; flagged in
  Open Questions.

- [ ] **Step 1: Write the failing tests**

`latent-forge/src/lib/forge/__tests__/sessionName.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { isValidSessionName, SESSION_NAME_RE } from "../sessionName";

describe("session name validation (spec §6.3, client-side before the PUT)", () => {
  it("accepts letters, digits, dot, underscore, dash, up to 80 chars", () => {
    expect(isValidSessionName("session_2026-09-23.v2")).toBe(true);
    expect(isValidSessionName("a".repeat(80))).toBe(true);
  });
  it("rejects empty, spaces, slashes, and over-length names", () => {
    expect(isValidSessionName("")).toBe(false);
    expect(isValidSessionName("my set")).toBe(false);
    expect(isValidSessionName("a/b")).toBe(false);
    expect(isValidSessionName("a".repeat(81))).toBe(false);
  });
  it("SESSION_NAME_RE is exactly the spec's pattern", () => {
    expect(SESSION_NAME_RE.source).toBe("^[A-Za-z0-9._-]{1,80}$");
  });
});
```

`latent-forge/src/lib/forge/__tests__/autosave.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAutosave, createSnapshotAutosave } from "../autosave";

afterEach(() => vi.useRealTimers());

describe("createAutosave: 2s after the last change (spec §9.2)", () => {
  it("fires once, 2000ms after trigger()", () => {
    vi.useFakeTimers();
    const save = vi.fn();
    const a = createAutosave(save);
    a.trigger();
    vi.advanceTimersByTime(1999);
    expect(save).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(save).toHaveBeenCalledTimes(1);
  });

  it("resets the timer on every new trigger, so rapid edits save once", () => {
    vi.useFakeTimers();
    const save = vi.fn();
    const a = createAutosave(save);
    a.trigger();
    vi.advanceTimersByTime(1000);
    a.trigger();
    vi.advanceTimersByTime(1999);
    expect(save).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(save).toHaveBeenCalledTimes(1);
  });

  it("cancel() stops a pending save", () => {
    vi.useFakeTimers();
    const save = vi.fn();
    const a = createAutosave(save);
    a.trigger();
    a.cancel();
    vi.advanceTimersByTime(5000);
    expect(save).not.toHaveBeenCalled();
  });

  it("honours a custom delay", () => {
    vi.useFakeTimers();
    const save = vi.fn();
    const a = createAutosave(save, 500);
    a.trigger();
    vi.advanceTimersByTime(500);
    expect(save).toHaveBeenCalledTimes(1);
  });
});

describe("createSnapshotAutosave: never writes a session it did not load or save", () => {
  it("does nothing before arm() -- a fresh mount observing the blank arrangement never PUTs", () => {
    vi.useFakeTimers();
    const save = vi.fn();
    const a = createSnapshotAutosave(save);
    // App's effect runs at mount with whatever `session` is; even a non-empty name must not save
    a.observe("dub-sketch", '{"clips":[]}');
    a.observe("dub-sketch", '{"clips":[1]}');
    vi.advanceTimersByTime(10_000);
    expect(save).not.toHaveBeenCalled();
  });

  it("after arm(), saves a CHANGED snapshot once, 2s later, under the armed name -- and never an unchanged one", () => {
    vi.useFakeTimers();
    const save = vi.fn();
    const a = createSnapshotAutosave(save);
    a.arm("take1", "A");
    a.observe("take1", "A");            // the effect re-running on the state that was just loaded
    vi.advanceTimersByTime(5000);
    expect(save).not.toHaveBeenCalled();
    a.observe("take1", "B");
    vi.advanceTimersByTime(1999);
    expect(save).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(save).toHaveBeenCalledWith("take1", "B");
    a.observe("take1", "B");            // B is now the baseline
    a.observe("other", "C");            // not the armed name
    vi.advanceTimersByTime(5000);
    expect(save).toHaveBeenCalledTimes(1);
  });

  it("arming a different session first flushes the previous session's pending save under ITS name", () => {
    vi.useFakeTimers();
    const save = vi.fn();
    const a = createSnapshotAutosave(save);
    a.arm("take1", "A");
    a.observe("take1", "A-edited");     // pending, not yet due
    a.arm("take2", "Z");                // user loaded another session within the 2s
    expect(save).toHaveBeenCalledWith("take1", "A-edited");
    vi.advanceTimersByTime(5000);
    expect(save).toHaveBeenCalledTimes(1); // nothing written to take2, which did not change
  });
});
```

`latent-forge/src/lib/forge/__tests__/projectSerializer.test.ts`:

```ts
import { beforeEach, describe, expect, it } from "vitest";
import { arrangement } from "../../stores/arrangement.svelte";
import { settings } from "../../stores/settings.svelte";
import { view } from "../../stores/view.svelte";
import { CHAIN_DEFAULTS, MASTER_DEFAULT, MIX_DEFAULT } from "../defaults";
import {
  applyMasterPreset, applyProject, buildMasterPresetPayload, serializeProject,
} from "../projectSerializer.svelte";

beforeEach(() => {
  arrangement.clips.splice(0, arrangement.clips.length);
  settings.stage = "BASE";
  view.clearSelection();
  view.restoreUi({ bottomTab: "prompt", modules: ["files", "lane-chain"], sideOpen: true, terminal: "pane" });
});

describe("serializeProject reads the live stores into ProjectV2 (spec §9.2)", () => {
  it("carries meter, snap, viewport, lanes, clips, mix, master, defaults and ui", () => {
    arrangement.addClip({ lane: 0, startSec: 1, durSec: 3, audio: { kind: "crop", crop_id: "X" } });
    const p = serializeProject({ name: "my-session" });
    expect(p.version).toBe(2);
    expect(p.name).toBe("my-session");
    expect(p.meter).toEqual({ bpm: arrangement.bpm, beatsPerBar: arrangement.beatsPerBar });
    expect(p.snap).toBe(arrangement.snap);
    expect(p.view).toEqual({ pxPerSec: arrangement.pxPerSec, scrollSec: arrangement.scrollSec });
    expect(p.lanes).toHaveLength(4);
    expect(p.clips).toHaveLength(1);
    expect(p.mix).toEqual(arrangement.mix);
    expect(p.master).toEqual(arrangement.master);
    expect(p.defaults).toEqual(settings.defaults);
    expect(p.backbone).toBe(settings.backboneId);
    expect(p.ckpt_path).toBe(settings.ckptPath);
    expect(p.ui).toEqual(view.snapshotUi());
  });

  it("carries every overlap keyed exactly as arrangement.overlaps names it", () => {
    arrangement.addClip({ lane: 0, startSec: 0, durSec: 10, audio: { kind: "crop", crop_id: "A" } });
    arrangement.addClip({ lane: 0, startSec: 6, durSec: 10, audio: { kind: "crop", crop_id: "B" } });
    const [ov] = arrangement.overlaps;
    arrangement.setOverlapParams(ov.key, { steps: 40 });
    const p = serializeProject({ name: "s" });
    expect(p.overlaps[ov.key].steps).toBe(40);
  });

  it("never persists a clip's previewAudio (spec §9.2 'Not serialised'), and returns plain data, not $state proxies", () => {
    const c = arrangement.addClip({ lane: 1, startSec: 0, durSec: 4, audio: { kind: "crop", crop_id: "P" } });
    arrangement.setPreviewAudio(c.id, { kind: "path", path: "/SERVER/out/stretched.wav" });
    const p = serializeProject({ name: "s" });
    expect(p.clips[0].previewAudio).toBeNull();
    expect(JSON.stringify(p)).not.toContain("stretched.wav");
    // structuredClone throws DataCloneError on a $state proxy (Global Constraint #7): passing
    // proves nothing proxied leaked into the result.
    expect(() => structuredClone(p)).not.toThrow();
    // and the live clip still has its in-memory preview
    expect(arrangement.clips[0].previewAudio).toEqual({ kind: "path", path: "/SERVER/out/stretched.wav" });
  });
});

describe("applyProject writes a loaded ProjectV2 back into the live stores", () => {
  it("round-trips a serialized project, including the backbone -> settings.stage", () => {
    arrangement.addClip({ lane: 2, startSec: 5, durSec: 4, audio: { kind: "crop", crop_id: "Z" } });
    settings.stage = "POST";
    const saved = serializeProject({ name: "round-trip" });
    expect(saved.backbone).toBe("medium");
    arrangement.clips.splice(0, arrangement.clips.length);
    settings.stage = "BASE";
    applyProject(saved);
    expect(arrangement.clips).toHaveLength(1);
    expect(arrangement.clips[0].lane).toBe(2);
    expect(arrangement.clips[0].previewAudio).toBeNull();
    expect(arrangement.bpm).toBe(saved.meter.bpm);
    expect(settings.stage).toBe("POST");   // backboneId is a getter over stage (M4 plan line 427)
    expect(view.snapshotUi()).toEqual(saved.ui);
  });
});

describe("buildMasterPresetPayload / applyMasterPreset (spec §9.3 master scope)", () => {
  it("captures every lane's chain, clip layout+a2a (no audio), mix, master, schedule+prompt only", () => {
    const clip = arrangement.addClip({ lane: 0, startSec: 2, durSec: 4, audio: { kind: "crop", crop_id: "Q" } });
    arrangement.setDetune(clip.id, 5);
    settings.defaults.prompt = "warm pad";
    const payload = buildMasterPresetPayload();
    expect(payload.lanes).toHaveLength(4);
    expect(payload.lanes[0].chain).toEqual(CHAIN_DEFAULTS);
    expect(payload.clips[0]).not.toHaveProperty("audio");
    expect(payload.clips[0].detune_cents).toBe(5);
    expect(payload.mix).toEqual(MIX_DEFAULT);
    expect(payload.master).toEqual(MASTER_DEFAULT);
    expect(payload.defaults.prompt).toBe("warm pad");
  });

  it("recall patches the same-id clip's layout and every lane's chain, and ignores a clip id no longer present", () => {
    const clip = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: { kind: "crop", crop_id: "Q" } });
    const payload = buildMasterPresetPayload();
    arrangement.moveClip(clip.id, 9);   // M5's signature is (id, startSec) -- two arguments
    payload.clips.push({ id: "ghost", lane: 0, start_sec: 0, offset_sec: 0, dur_sec: 1, loop: false, native_bpm: null, detune_cents: 0, a2a: null });
    expect(() => applyMasterPreset(payload)).not.toThrow();
    expect(arrangement.clips.find((c) => c.id === clip.id)?.start_sec).toBe(0);
  });
});
```

`latent-forge/src/lib/help/__tests__/sessionHelp.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { HELP } from "../strings";

describe("the top bar's three new HELP strings (v3 line 43's SAVE has none; IMPORT is not drawn at all)", () => {
  it("masterPresetSave exists and mentions saving", () => {
    expect(HELP.masterPresetSave.length).toBeGreaterThan(10);
    expect(HELP.masterPresetSave.toLowerCase()).toContain("save");
  });

  it("sessionSave mentions saving, and sessionImportV1 names the v1 files it converts", () => {
    expect(HELP.sessionSave.toLowerCase()).toContain("save");
    expect(HELP.sessionImportV1.toLowerCase()).toContain("v1");
  });
});
```

`latent-forge/src/ui/shell/__tests__/topBarSessions.test.ts`:

```ts
// @vitest-environment jsdom
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HELP } from "../../../lib/help/strings";
import TopBar from "../TopBar.svelte";

afterEach(() => cleanup());

const base = {
  view: "workspace" as const, onview: () => {}, helpMode: false, onhelp: () => {},
  theme: "light" as const, ontheme: () => {},
};
const SESSIONS = [{ name: "take1", updated: 1, n_clips: 2 }];

describe("TopBar.svelte after M7 T9 (spec §9.2/§9.3)", () => {
  it("has no SAVE/LOAD project buttons left (M1 T15's temporary pair is removed)", () => {
    const { queryByTestId } = render(TopBar, { props: base });
    expect(queryByTestId("save-project")).toBeNull();
    expect(queryByTestId("load-project")).toBeNull();
  });

  it("the SESSION select shows `unsaved` until a session is named, then drops it", async () => {
    const { getByTestId, queryByRole, rerender } = render(TopBar, { props: { ...base, sessions: SESSIONS, session: "" } });
    const select = getByTestId("session-select") as HTMLSelectElement;
    expect(queryByRole("option", { name: "unsaved" })).not.toBeNull();
    expect(select.value).toBe("");
    await rerender({ ...base, sessions: SESSIONS, session: "take1" });
    expect(queryByRole("option", { name: "unsaved" })).toBeNull();
    expect(select.value).toBe("take1");
  });

  it("calls onsessionsave from the session SAVE button, which carries HELP.sessionSave", async () => {
    const onsessionsave = vi.fn();
    const { getByTestId } = render(TopBar, { props: { ...base, sessions: SESSIONS, session: "take1", onsessionsave } });
    const btn = getByTestId("session-save");
    expect(btn.getAttribute("data-help")).toBe(HELP.sessionSave);
    await fireEvent.click(btn);
    expect(onsessionsave).toHaveBeenCalledTimes(1);
  });

  it("enables the master preset SAVE button, with HELP.masterPresetSave, and calls onmasterpresetsave", async () => {
    const onmasterpresetsave = vi.fn();
    const { getByTestId } = render(TopBar, { props: { ...base, masterPresets: ["live A"], masterPreset: "live A", onmasterpresetsave } });
    const btn = getByTestId("master-preset-save") as HTMLButtonElement;
    expect(btn.disabled).toBe(false);
    expect(btn.getAttribute("data-help")).toBe(HELP.masterPresetSave);
    await fireEvent.click(btn);
    expect(onmasterpresetsave).toHaveBeenCalledTimes(1);
  });

  it("IMPORT hands the picked project file to onimportv1 (spec §9.2's v1 converter needs a way in)", async () => {
    const onimportv1 = vi.fn();
    const { getByTestId } = render(TopBar, { props: { ...base, onimportv1 } });
    expect(getByTestId("session-import").getAttribute("data-help")).toBe(HELP.sessionImportV1);
    const file = new File(['{"version":1}'], "old-set.json", { type: "application/json" });
    await fireEvent.change(getByTestId("session-import-file"), { target: { files: [file] } });
    expect(onimportv1).toHaveBeenCalledWith(file);
  });
});
```

`latent-forge/src/ui/shell/__tests__/rightPaneModules.test.ts`:

```ts
// @vitest-environment jsdom
import { cleanup, render } from "@testing-library/svelte";
import { tick } from "svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CHAIN_DEFAULTS } from "../../../lib/forge/defaults";
import { arrangement } from "../../../lib/stores/arrangement.svelte";
import { view } from "../../../lib/stores/view.svelte";
import RightPaneModules from "../RightPaneModules.svelte";

// The dot is found by M1 T9's own hooks, `data-testid="module-dot"` + `data-lit` (M1 plan lines
// 4062-4066), inside the `data-module={id}` wrapper the reconciled ModuleShell emits (Global
// Constraint #3). If the reconciled shell renamed the dot's testid, fix the selector, not the intent.

beforeEach(() => {
  // Every module body fetches on mount (FILES, LANE CHAIN, MASTER CHAIN); answer all of them with
  // one empty-but-valid body so nothing rejects on jsdom's relative URLs.
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({
    ok: true, roots: [], files: [], names: [], latch_heads: [], models: [], slots: [],
  }))));
  arrangement.clips.splice(0, arrangement.clips.length);
});

afterEach(() => {
  cleanup();
  view.clearSelection();
  view.closeModule("overlap");
  arrangement.clips.splice(0, arrangement.clips.length);
  for (const lane of arrangement.lanes) lane.chain = structuredClone(CHAIN_DEFAULTS);
  vi.unstubAllGlobals();
});

describe("RightPaneModules after M7 T9", () => {
  it("lights LANE CHAIN's dot from the active lane's live chain, and relights on an in-place edit", async () => {
    view.setActiveLane(0);
    const { container } = render(RightPaneModules);
    const dot = () => container.querySelector('[data-module="lane-chain"] [data-testid="module-dot"]')!;
    expect(dot().getAttribute("data-lit")).toBe("false");
    arrangement.lanes[0].chain.latch_on = true;   // in place -- Global Constraint #1
    await tick();
    expect(dot().getAttribute("data-lit")).toBe("true");
    expect(container.querySelector('[data-module="master-chain"] [data-testid="module-dot"]')!.getAttribute("data-lit")).toBe("false");
  });

  it("renders a never-edited overlap's module without seeding it (no state_unsafe_mutation from the lit snapshot or the body)", () => {
    arrangement.addClip({ lane: 0, startSec: 0, durSec: 10, audio: { kind: "crop", crop_id: "A" } });
    arrangement.addClip({ lane: 0, startSec: 6, durSec: 10, audio: { kind: "crop", crop_id: "B" } });
    const [ov] = arrangement.overlaps;
    view.select({ kind: "overlap", key: ov.key });
    view.openModule("overlap");   // mount OverlapInpaint's body too, not just the shell
    const { container, getByTestId } = render(RightPaneModules);
    expect(container.querySelector('[data-module="overlap"]')).not.toBeNull();
    expect(getByTestId("inpaint-overlap-button")).toBeTruthy();
    // still unseeded: two peeks are two different objects (Task 3's own contract)
    expect(arrangement.peekOverlapParams(ov.key)).not.toBe(arrangement.peekOverlapParams(ov.key));
  });
});
```

- [ ] **Step 2: Run them, expect failure**

```bash
cd /home/kim/Projects/sa3-studio-review/latent-forge && npx vitest run src/lib/forge/__tests__/sessionName.test.ts src/lib/forge/__tests__/autosave.test.ts src/lib/forge/__tests__/projectSerializer.test.ts src/lib/help/__tests__/sessionHelp.test.ts src/ui/shell/__tests__/topBarSessions.test.ts src/ui/shell/__tests__/rightPaneModules.test.ts
```

Expected: `Failed to resolve import "../sessionName"`, `"../autosave"`, `"../projectSerializer.svelte"`;
`HELP.masterPresetSave`/`.sessionSave`/`.sessionImportV1` undefined; the five `topBarSessions.test.ts`
cases fail against the pre-T9 `TopBar.svelte` (SAVE/LOAD project buttons still present, no
`unsaved` option, no `session-save`/`session-import` test ids, `master-preset-save` still
hard-disabled); `rightPaneModules.test.ts` fails its lit-dot case (M1's constant snapshot keeps
every dot at `data-lit="false"`). Its overlap case already passes at this point, because Task 7's
body already reads through `peekOverlapParams` — it is the regression guard for Step 5's snapshot,
which is the other place that must never call the seeding `overlapParams`. Summary:
`Test Files  6 failed (6)`.

- [ ] **Step 3: Write `sessionName.ts`, `autosave.ts`, `projectSerializer.svelte.ts`**

`latent-forge/src/lib/forge/sessionName.ts`:

```ts
// Spec §6.3, verbatim: the server 400s a name outside this pattern, so the
// client validates before the PUT rather than round-tripping a guaranteed error.
export const SESSION_NAME_RE = /^[A-Za-z0-9._-]{1,80}$/;

export function isValidSessionName(name: string): boolean {
  return SESSION_NAME_RE.test(name);
}
```

`latent-forge/src/lib/forge/autosave.ts`:

```ts
// Spec §9.2: "Autosave to the current session name 2 s after the last change."
// Timer-owning, deliberately not a $effect itself, so it is testable with
// vi.useFakeTimers() without mounting anything.
export function createAutosave(save: () => void, delayMs = 2000): { trigger(): void; cancel(): void } {
  let handle: ReturnType<typeof setTimeout> | null = null;
  return {
    trigger() {
      if (handle !== null) clearTimeout(handle);
      handle = setTimeout(() => {
        handle = null;
        save();
      }, delayMs);
    },
    cancel() {
      if (handle !== null) {
        clearTimeout(handle);
        handle = null;
      }
    },
  };
}

export interface SnapshotAutosave {
  /** A session was just loaded or explicitly saved as `snapshot`: start autosaving `name`.
   *  An empty name disarms. A pending save for a DIFFERENT name is flushed first, under that name. */
  arm(name: string, snapshot: string): void;
  /** Called by App's $effect on every change. Saves nothing until `name` is the armed session,
   *  and nothing when `snapshot` equals the last armed/saved one. */
  observe(name: string, snapshot: string): void;
  cancel(): void;
}

/**
 * The session autosave. Two guarantees the bare debounce cannot give on its own:
 *  1. a tab that has not loaded or saved a session never writes one -- the launch arrangement is
 *     blank, and PUTting it over a listed session would destroy that session;
 *  2. a re-run of the watching effect that changed nothing saves nothing.
 */
export function createSnapshotAutosave(
  save: (name: string, snapshot: string) => void,
  delayMs = 2000,
): SnapshotAutosave {
  let armedName = "";
  let baseline = "";
  let pending: { name: string; snapshot: string } | null = null;

  const debounce = createAutosave(() => {
    if (!pending) return;
    const { name, snapshot } = pending;
    pending = null;
    if (name === armedName) baseline = snapshot;
    save(name, snapshot);
  }, delayMs);

  return {
    arm(name, snapshot) {
      if (pending && pending.name !== name) {
        const p = pending;
        pending = null;
        debounce.cancel();
        save(p.name, p.snapshot);
      }
      armedName = name;
      baseline = snapshot;
    },
    observe(name, snapshot) {
      if (!armedName || name !== armedName) return;
      if (snapshot === baseline) {
        if (pending?.name === name) {
          pending = null;
          debounce.cancel();
        }
        return;
      }
      pending = { name, snapshot };
      debounce.trigger();
    },
    cancel() {
      pending = null;
      debounce.cancel();
    },
  };
}
```

`latent-forge/src/lib/forge/projectSerializer.svelte.ts`:

```ts
// Turns the live stores into ProjectV2 (spec §9.2) and back, and the narrower
// master-preset slice (spec §9.3). Reads/writes the real singletons directly,
// the same pattern every other store-adjacent module in this codebase uses.
//
// `.svelte.ts` because of $state.snapshot: structuredClone throws DataCloneError
// on a $state proxy (Global Constraint #7), and every arrangement/settings field
// read here IS one. $state.snapshot reads through the proxies, which is also why
// App's autosave $effect, which calls serializeProject, depends on every field.
import {
  arrangement, MAX_PX_PER_SEC, MIN_PX_PER_SEC,
} from "../stores/arrangement.svelte";
import { settings, STAGE_BACKBONE, type ModelStage } from "../stores/settings.svelte";
import { view } from "../stores/view.svelte";
import { CHAIN_DEFAULTS, cloneRenderSettings } from "./defaults";
import type {
  ForgeClip, ForgeLane, LaneChain, MasterChain, MixSpec, OverlapParams, ProjectV2, RenderSettings,
} from "./types";

export function serializeProject(opts: { name: string }): ProjectV2 {
  const overlaps: Record<string, OverlapParams> = {};
  // peek, not overlapParams: this runs inside App's autosave $effect, and must not write.
  for (const o of arrangement.overlaps) {
    overlaps[o.key] = $state.snapshot(arrangement.peekOverlapParams(o.key)) as OverlapParams;
  }

  return {
    version: 2,
    name: opts.name,
    meter: { bpm: arrangement.bpm, beatsPerBar: arrangement.beatsPerBar },
    snap: arrangement.snap,
    view: { pxPerSec: arrangement.pxPerSec, scrollSec: arrangement.scrollSec },
    lanes: $state.snapshot(arrangement.lanes) as ForgeLane[],
    // previewAudio is in-memory only (spec §9.2 "Not serialised", M1 Normative row): the field is
    // required on ForgeClip, so it is written as null -- the live ref never reaches the JSON.
    clips: ($state.snapshot(arrangement.clips) as ForgeClip[]).map((c) => ({ ...c, previewAudio: null })),
    overlaps,
    mix: $state.snapshot(arrangement.mix) as MixSpec,
    master: $state.snapshot(arrangement.master) as MasterChain,
    defaults: $state.snapshot(settings.defaults) as RenderSettings,
    backbone: settings.backboneId,
    ckpt_path: settings.ckptPath,
    renders: [],       // M9 owns render history; nothing exists to serialise yet
    mixdown: null,
    preview: null,
    ui: $state.snapshot(view.snapshotUi()) as ProjectV2["ui"],
  };
}

/** STAGE_BACKBONE inverted: "medium" -> POST, "medium-base" -> BASE, anything else -> null. */
function stageForBackbone(backbone: string): ModelStage | null {
  const hit = (Object.keys(STAGE_BACKBONE) as ModelStage[]).find((s) => STAGE_BACKBONE[s] === backbone);
  return hit ?? null;
}

/** `project` is plain data (a server response, a parsed file, or serializeProject's output). */
export function applyProject(project: ProjectV2): void {
  arrangement.setBpm(project.meter.bpm);
  arrangement.beatsPerBar = project.meter.beatsPerBar;
  arrangement.setSnap(project.snap as Parameters<typeof arrangement.setSnap>[0]);
  // arrangement has no setPxPerSec (M5 T1): assign directly, clamped exactly as zoomBy clamps.
  arrangement.pxPerSec = Math.max(MIN_PX_PER_SEC, Math.min(MAX_PX_PER_SEC, project.view.pxPerSec));
  arrangement.setScrollSec(project.view.scrollSec);
  arrangement.lanes.splice(0, arrangement.lanes.length, ...structuredClone(project.lanes));
  arrangement.clips.splice(
    0, arrangement.clips.length,
    ...structuredClone(project.clips).map((c) => ({ ...c, previewAudio: null })),
  );
  arrangement.mix = structuredClone(project.mix);
  arrangement.master = structuredClone(project.master);
  for (const [key, params] of Object.entries(project.overlaps)) {
    arrangement.setOverlapParams(key, structuredClone(params));
  }
  // backboneId is a getter over settings.stage (M4 plan line 427), so restoring `backbone` means
  // restoring the stage. Assigned directly, NOT via setStage(): setStage overwrites defaults'
  // steps/sampler/schedule with the stage defaults, and the saved defaults (next line) must win.
  // The caller (App's loadSession/importProjectFile) rebuilds the server model if this changed it.
  const stage = stageForBackbone(project.backbone);
  if (stage) settings.stage = stage;
  settings.defaults = cloneRenderSettings(project.defaults);
  settings.ckptPath = project.ckpt_path;
  view.restoreUi(project.ui);
}

// ---------------------------------------------------------- master preset (§9.3)

export interface MasterPresetPayload {
  lanes: { chain: LaneChain }[];
  clips: {
    id: string; lane: 0 | 1 | 2 | 3; start_sec: number; offset_sec: number; dur_sec: number;
    loop: boolean; native_bpm: number | null; detune_cents: number; a2a: ForgeClip["a2a"];
  }[];
  mix: MixSpec;
  master: MasterChain;
  defaults: { schedule: RenderSettings["schedule"]; prompt: string };
}

/**
 * Spec §9.3's own enumeration, taken literally rather than as "ProjectV2 minus
 * two fields" (the two readings do not fully reconcile -- see this task's WHY).
 * No `audio`, no `render.steps`/`cfg_scale`/etc: those belong to the separate
 * `render`-level preset (M4), and re-including them here would make the two
 * levels redundant.
 */
export function buildMasterPresetPayload(): MasterPresetPayload {
  return {
    lanes: arrangement.lanes.map((l) => ({ chain: $state.snapshot(l.chain) as LaneChain })),
    clips: arrangement.clips.map((c) => ({
      id: c.id, lane: c.lane, start_sec: c.start_sec, offset_sec: c.offset_sec,
      dur_sec: c.dur_sec, loop: c.loop, native_bpm: c.native_bpm, detune_cents: c.detune_cents,
      a2a: $state.snapshot(c.a2a) as ForgeClip["a2a"],
    })),
    mix: $state.snapshot(arrangement.mix) as MixSpec,
    master: $state.snapshot(arrangement.master) as MasterChain,
    defaults: {
      schedule: $state.snapshot(settings.defaults.schedule) as RenderSettings["schedule"],
      prompt: settings.defaults.prompt,
    },
  };
}

/** Recall replaces the whole slice (spec §9.3): matched by clip id within the
 *  CURRENT session's arrangement, since a master preset is a snapshot of one
 *  session's layout, not a transplant of clips into a different one. A clip id
 *  the preset names that no longer exists is skipped, not an error.
 *  `payload` is plain data (a server response or buildMasterPresetPayload's output). */
export function applyMasterPreset(payload: MasterPresetPayload): void {
  payload.lanes.forEach((l, i) => {
    if (arrangement.lanes[i]) arrangement.lanes[i].chain = structuredClone(l.chain ?? CHAIN_DEFAULTS);
  });
  for (const saved of payload.clips) {
    const clip = arrangement.clips.find((c) => c.id === saved.id);
    if (!clip) continue;
    clip.lane = saved.lane;
    clip.start_sec = saved.start_sec;
    clip.offset_sec = saved.offset_sec;
    clip.dur_sec = saved.dur_sec;
    clip.loop = saved.loop;
    clip.native_bpm = saved.native_bpm;
    clip.detune_cents = saved.detune_cents;
    clip.a2a = structuredClone(saved.a2a);
  }
  arrangement.mix = structuredClone(payload.mix);
  arrangement.master = structuredClone(payload.master);
  settings.defaults.schedule = structuredClone(payload.defaults.schedule);
  settings.defaults.prompt = payload.defaults.prompt;
}
```

- [ ] **Step 4: Wire `TopBar.svelte` and `App.svelte`; add the HELP strings**

In `docs/latent-forge/extract_help.mjs`, append to `NEW_STRINGS` (after Task 6's `filesFilter`):

```js
  masterPresetSave:
    "Saves the current master slice under the highlighted name, or asks for a new one if nothing " +
    "is named yet. Recall replaces the whole slice (spec §9.3): every lane chain, clip layout, " +
    "mix order and node values, master chain, sampling schedule and default prompt.",
  sessionSave:
    "Saves the whole project to the server under the selected session name, or asks for a name " +
    "while it is still unsaved. After that, every change autosaves to it 2 s later.",
  sessionImportV1:
    "Opens a project file from disk. A v1 file from the old app is converted (lanes renamed " +
    "LANE 1-4, missing settings filled with defaults); it stays unsaved until you SAVE it.",
```

Regenerate:

```bash
cd /home/kim/Projects/sa3-studio-review/latent-forge && npm run help:extract
```

Expected: `extract_help: wrote 112 strings (80 extracted, 14 rewritten, 32 new) to .../strings.ts`.

Then the **final** `strings.test.ts` update — in `latent-forge/src/lib/help/__tests__/strings.test.ts`
(M1 T14, M1 plan line 7501), move the lines Task 6 left: the title
`"has the 80 handoff strings plus the 29 new controls"` becomes
`"has the 80 handoff strings plus the 32 new controls (M1's 7, M7's 25)"`, and
`toHaveLength(109)` becomes `toHaveLength(112)`.

112 = 80 extracted (`KEYS`, M1 plan lines 7672-7728) + M1's 7 `NEW_STRINGS` + this milestone's 25
(Task 2: 13, Task 4: 4, Task 5: 3, Task 6: 2, Task 9: 3).

In `latent-forge/src/ui/shell/TopBar.svelte`, **remove** (M1 T15's temporary pair):
- the `fileInput`/`notice` state and the `saveProject`/`loadProject` functions
- `import { project } from "../../lib/store.svelte";`
- the `<button data-testid="save-project">`, `<button data-testid="load-project">`, the hidden
  file `<input>`, and the `{#if notice}` span

**Add** to the `<script>`: `import { HELP } from "../../lib/help/strings";`; to `interface Props`:

```ts
    onsessionsave?: () => void;
    onimportv1?: (file: File) => void;
    onmasterpresetsave?: () => void;
```

to the destructuring, `onsessionsave = () => {}, onimportv1 = () => {}, onmasterpresetsave = () => {},`;
and below it:

```ts
  let importInput = $state<HTMLInputElement>();

  function onImportPicked(e: Event) {
    const input = e.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    if (file) onimportv1(file);
    input.value = "";   // picking the same file twice still fires change
  }
```

In the markup, add the `unsaved` option as the SESSION select's first child (spec §9.2: "SESSION
select shows `unsaved` until named"):

```svelte
    {#if !session}<option value="">unsaved</option>{/if}
```

and, immediately after the SESSION select (the exact spot the removed buttons occupied):

```svelte
  <button class="save" data-testid="session-save" data-help={HELP.sessionSave} onclick={onsessionsave}>SAVE</button>
  <button class="save" data-testid="session-import" data-help={HELP.sessionImportV1}
    onclick={() => importInput?.click()}>IMPORT</button>
  <input bind:this={importInput} data-testid="session-import-file" type="file"
    accept="application/json,.json" onchange={onImportPicked} hidden />
```

and change the MASTER PRESET `SAVE` button from hard-`disabled` to:

```svelte
    <button class="save" data-testid="master-preset-save" data-help={HELP.masterPresetSave} onclick={onmasterpresetsave}>SAVE</button>
```

(also delete the `<!-- Saving a master preset is M7 (spec §9.3); the copy is final here. -->`
comment above it).

In `latent-forge/src/ui/shell/__tests__/topBar.test.ts` (M1 T10, M1 plan lines 5010-5017), the
test titled `"disables SAVE on the master preset until M7 owns presets, and keeps the MIXDOWN frame"`
is retitled `"enables SAVE on the master preset now that M7 owns presets, and keeps the MIXDOWN
frame"`, and in its body `.disabled).toBe(true);` becomes `.disabled).toBe(false);`. Nothing else in
that file changes (it keeps its 3 tests).

In `latent-forge/src/App.svelte`, inside `loadTopBar()`, **delete** the auto-select line (M1 plan
line 5502) — this is what makes `unsaved` reachable and keeps launch from ever naming a session:

```ts
      if (!session && sessions.length > 0) session = sessions[0].name;
```

Make sure `App.svelte` imports the view store as `view` exactly once (Global Constraint #3: if the
file still says `import { viewStore } …`, that is the same singleton under a name that does not
exist — change the import to `import { view } from "./lib/stores/view.svelte";` and its uses to
`view`). `forgeApi` is already imported by M1 T10. Then add:

```ts
  import {
    applyMasterPreset, applyProject, buildMasterPresetPayload, serializeProject,
    type MasterPresetPayload,
  } from "./lib/forge/projectSerializer.svelte";
  import { convertProjectV1 } from "./lib/forge/convertProjectV1";
  import { isValidSessionName } from "./lib/forge/sessionName";
  import { createSnapshotAutosave } from "./lib/forge/autosave";
  import type { ProjectV2 } from "./lib/forge/types";
  import { arrangement } from "./lib/stores/arrangement.svelte";
  import { settings, STAGE_BACKBONE, type ModelStage } from "./lib/stores/settings.svelte";

  const errText = (e: unknown) => (e instanceof Error ? e.message : String(e));

  /** A server session or an imported file: v2 as-is, anything else through the converter. */
  function toV2(raw: unknown): ProjectV2 {
    return (raw as { version?: number } | null)?.version === 2 ? (raw as ProjectV2) : convertProjectV1(raw);
  }

  /** Stage is session-level and rebuilds the model (M4 T9 confirmStage). applyProject moved the
   *  client-side stage; move the server to match, or put the client back if the rebuild fails. */
  async function syncBackbone(prevStage: ModelStage): Promise<void> {
    if (settings.stage === prevStage) return;
    const wanted = settings.stage;
    try {
      await forgeApi.setBackbone(STAGE_BACKBONE[wanted]);
    } catch (e) {
      settings.stage = prevStage;
      view.appendLog(`[forge] project wants backbone ${STAGE_BACKBONE[wanted]}; rebuild failed, staying on ${STAGE_BACKBONE[prevStage]}: ${errText(e)}`, "error");
    }
  }

  // Autosave (spec §9.2): 2 s after the last change, to the current session -- but only once that
  // session has been loaded or explicitly saved (createSnapshotAutosave's arm()).
  const autosave = createSnapshotAutosave((name, json) => {
    forgeApi.saveSession(name, JSON.parse(json) as ProjectV2)
      .catch((e) => view.appendLog(`[forge] autosave of ${name} failed: ${errText(e)}`, "error"));
  });
  $effect(() => {
    // serializeProject reads every saved field through $state.snapshot, which reads through the
    // proxies: this re-runs on ANY in-place edit (Global Constraint #1) -- a chain slot, a mix node,
    // a clip move, the prompt -- and observe() compares the string, so a re-run that changed
    // nothing saves nothing.
    autosave.observe(session, JSON.stringify(serializeProject({ name: session })));
  });

  // Guards a stale response from a superseded session load. forgeApi.session()
  // has no AbortSignal parameter (M1 T5) -- there is nothing to abort -- so a
  // monotonic sequence number stands in for the HANDOUT's abort-listener check.
  let sessionLoadSeq = 0;

  async function loadSession(name: string) {
    session = name;
    if (!name) return;
    const mySeq = ++sessionLoadSeq;
    try {
      const raw = await forgeApi.session(name);
      if (mySeq !== sessionLoadSeq) return;   // superseded by a later pick
      const prevStage = settings.stage;
      applyProject(toV2(raw));
      await syncBackbone(prevStage);
      if (mySeq !== sessionLoadSeq) return;
      // Baseline = what is loaded now; only a later change autosaves.
      autosave.arm(name, JSON.stringify(serializeProject({ name })));
    } catch (e) {
      // Not armed: a session that failed to load is never autosaved over.
      view.appendLog(`[forge] failed to load session ${name}: ${errText(e)}`, "error");
    }
  }

  async function saveSession() {
    let name = session;
    if (!name) {
      const typed = window.prompt("Session name (letters, numbers, . _ - only):", "");
      if (!typed) return;
      name = typed;
    }
    if (!isValidSessionName(name)) {
      view.appendLog(`[forge] "${name}" is not a valid session name (spec §6.3)`, "error");
      return;
    }
    const project = serializeProject({ name });
    try {
      await forgeApi.saveSession(name, project);
      session = name;
      autosave.arm(name, JSON.stringify(project));
      if (!sessions.some((s) => s.name === name)) sessions = [...sessions, { name, updated: Date.now() / 1000, n_clips: project.clips.length }];
    } catch (e) {
      view.appendLog(`[forge] session save failed: ${errText(e)}`, "error");
    }
  }

  /** IMPORT: a v1 (or v2) project file from disk. It belongs to no server session yet, so it
   *  is `unsaved` and autosave is disarmed until SAVE names it. */
  async function importProjectFile(file: File) {
    try {
      const raw: unknown = JSON.parse(await file.text());
      sessionLoadSeq++;              // any in-flight session load is now stale
      const prevStage = settings.stage;
      applyProject(toV2(raw));
      session = "";
      autosave.arm("", "");          // empty name = disarmed (flushes a pending save of the old session)
      await syncBackbone(prevStage);
      view.appendLog(`[forge] imported ${file.name} -- unsaved until you SAVE it under a session name`);
    } catch (e) {
      view.appendLog(`[forge] could not import ${file.name}: ${errText(e)}`, "error");
    }
  }

  async function loadMasterPreset(name: string) {
    masterPreset = name;
    if (!name) return;
    try {
      applyMasterPreset((await forgeApi.preset("master", name)) as unknown as MasterPresetPayload);
    } catch (e) {
      view.appendLog(`[forge] failed to load master preset ${name}: ${errText(e)}`, "error");
    }
  }

  async function saveMasterPreset() {
    let name = masterPreset;
    if (!name) {
      const typed = window.prompt("Master preset name:", "");
      if (!typed) return;
      name = typed;
    }
    try {
      await forgeApi.savePreset("master", name, buildMasterPresetPayload());
      masterPreset = name;
      if (!masterPresets.includes(name)) masterPresets = [...masterPresets, name];
    } catch (e) {
      view.appendLog(`[forge] master preset save failed: ${errText(e)}`, "error");
    }
  }
```

(`autosave.arm("", "")` in `importProjectFile` runs before `applyProject`'s changes reach the
effect, which re-runs on the next microtask — by then the autosave is disarmed and `session` is
`""`, so the imported project is never written anywhere until SAVE.) Then replace the
`onsession`/`onmasterpreset` bindings on `<TopBar>` with:

```svelte
    onsession={loadSession}
    onsessionsave={saveSession}
    onimportv1={importProjectFile}
    onmasterpreset={loadMasterPreset}
    onmasterpresetsave={saveMasterPreset}
```

- [ ] **Step 5: Wire `RightPaneModules.svelte`'s lit snapshot and M4's two LatCH handoffs**

This is the edit Tasks 2, 4 and 7 each stated an expression for. In
`latent-forge/src/ui/shell/RightPaneModules.svelte` (M1 T12, M1 plan lines 6641-6693 — M4 never
changed it, M4 plan line 4712), add the import:

```ts
  import { arrangement } from "../../lib/stores/arrangement.svelte";
```

and replace M1's constant block

```ts
  // M1 has no settings stores, so every dot is dark and the snapshot is a
  // constant. M4 replaces `sampling` with render.settingsFor(view.selection) and
  // M7 replaces `overlap`, `chain` and `master` with the chains store; both turn
  // these two consts into `$derived(...)`. litModules() itself does not change.
  const snapshot: ModuleStateSnapshot = {
    overlap: null,
    chain: null,
    sampling: null,
    master: null,
  };
  const lit = litModules(snapshot);
```

with

```ts
  // M7 T9: live. Every field is read inside the $derived (and litModules' deepEqual reads through
  // the proxies), so a module's dot relights on any in-place edit.
  //  - overlap: peekOverlapParams, NEVER overlapParams -- that one seeds the store, and a write
  //    during a $derived throws state_unsafe_mutation (Global Constraint #8).
  //  - sampling: still null. M4 never wired it (M4 plan line 4712); see Open questions.
  const snapshot = $derived<ModuleStateSnapshot>({
    overlap: view.selection.kind === "overlap" ? arrangement.peekOverlapParams(view.selection.key) : null,
    chain: arrangement.lanes[view.activeLane].chain,
    sampling: null,
    master: arrangement.master,
  });
  const lit = $derived(litModules(snapshot));

  // M4's handoff (M4 plan line 4741): ADVANCED SAMPLING's `latch` prop is the active lane's LatCH
  // state. A LaneChain satisfies LatchState structurally (M4 plan line 515) -- no adapter.
  const activeChain = $derived(arrangement.lanes[view.activeLane].chain);
```

and in the markup replace `<AdvancedSampling />` with:

```svelte
        <AdvancedSampling latch={activeChain} />
```

Nothing else in the file changes (`lit[id]` is already what `<ModuleShell>` reads).

In `latent-forge/src/ui/prompt/PromptSigmaTab.svelte` (M4 T10, M4 plan lines 4575-4633), M4's
other handoff (M4 plan line 4076: "M7 passes the active lane's real two slots"): add the import

```ts
  import { arrangement } from "../../lib/stores/arrangement.svelte";
```

and, below `const target = $derived(view.selection);`:

```ts
  // M7 T9: the active lane's LatCH slots for the sigma graph's slot lanes -- only while that lane's
  // LATCH GUIDANCE is on (M4 plan line 1982: the caller passes slots when there is something to draw).
  const latchSlots = $derived.by(() => {
    const chain = arrangement.lanes[view.activeLane].chain;
    return chain.latch_on ? chain.slots : [];
  });
```

and change `<SigmaColumn {target} {length} {a2a} />` to:

```svelte
    <SigmaColumn {target} {length} {a2a} slots={latchSlots} />
```

- [ ] **Step 6: Run them, expect pass**

```bash
cd /home/kim/Projects/sa3-studio-review/latent-forge && npx vitest run src/lib/forge/__tests__/sessionName.test.ts src/lib/forge/__tests__/autosave.test.ts src/lib/forge/__tests__/projectSerializer.test.ts src/lib/help/__tests__/sessionHelp.test.ts src/ui/shell/__tests__/topBarSessions.test.ts src/ui/shell/__tests__/rightPaneModules.test.ts
```

Expected: `Test Files  6 passed (6)` / `Tests  25 passed (25)` — 3 in `sessionName.test.ts`, 7 in
`autosave.test.ts`, 6 in `projectSerializer.test.ts` (3 `serializeProject` + 1 `applyProject` + 2
`buildMasterPresetPayload`/`applyMasterPreset`), 2 in `sessionHelp.test.ts`, 5 in
`topBarSessions.test.ts`, 2 in `rightPaneModules.test.ts`: 3+7+6+2+5+2 = 25, counted mechanically
with `grep -c '^  it('` over this task's own test blocks.

Then the files this task modified that already had suites — M1's `strings.test.ts` (now 112) and
`topBar.test.ts` (the flipped assertion), M4's `PromptSigmaTab` tests — and the whole project's
types:

```bash
cd /home/kim/Projects/sa3-studio-review/latent-forge && npx vitest run src/lib/help src/ui/shell src/ui/prompt && npm run check
```

Expected: every test in those three directories passes, then `svelte-check found 0 errors and 0
warnings`.

- [ ] **Step 7: Commit**

```bash
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M7 T9: sessions load/save/import through convertProjectV1 (backbone restored to settings.stage), snapshot-gated 2s autosave that never writes before a load or SAVE, M1's sessions[0] auto-select removed, master preset recall/save against spec 9.3's literal slice, RightPaneModules lit snapshot + M4's two LatCH handoffs wired, removes M1 T15's temporary SAVE/LOAD project buttons, HELP total 112"
```
---

### Task 10: Playwright fragment and self-review

**WHY.** Every prior milestone's own Playwright fragment extends M1 T15's `tests/layout.spec.ts`
rather than replacing it, and none of them may weaken M1's frozen assertion that
`[data-module="overlap"]` has count 0 when nothing is selected as an overlap
(`docs/superpowers/plans/2026-09-16-latent-forge-m1-foundation-shell.md:8341-8348`). This task adds
one new spec file covering what Tasks 6-9 built, plus the mandated self-review table and Known
Incomplete note every milestone plan ends with (M6's own Task 11 is the template followed here).

**Files:**
- Create: `latent-forge/tests/sessionsFilesOverlap.spec.ts`

**Interfaces:**
- Consumes the mock server's `/forge/sessions`, `/forge/presets/*`, `/forge/files` routes (M1 T6,
  `dev:mock`) — session save/load and preset save/load/delete are held in-memory by the mock
  plugin (`docs/superpowers/plans/2026-09-16-latent-forge-m1-foundation-shell.md:2172-2248`,
  `routeFor` kinds `session_get`/`session_put`/`preset_list`/`preset_put`/`preset_delete`), so a
  Playwright round trip against `dev:mock` is real, not stubbed. **Two mock facts every test here
  depends on:** the session *list* is the fixed fixture `handmade-forge_sessions.json`
  (`dub-sketch`, `goa-transitions`, `scratch`, M1 plan lines 2484-2493), while the session *store*
  behind `GET`/`PUT /forge/sessions/{name}` is a `Map` that starts **empty** (M1 plan lines 2171,
  2223-2231). So picking `dub-sketch` 404s unless something PUT it first — `beforeEach` does, and
  the tests read the store back with `page.request.get` to see what the app actually wrote.
- Consumes `convertProjectV1` from `src/lib/forge/convertProjectV1.ts` (Task 8 — plain TypeScript,
  no runes, so Playwright's own TS loader can import it) to build a complete seeded `ProjectV2`
  without restating every field.
- Consumes the `[data-*]` contract Tasks 6-9 produced: `data-testid="session-select"` (and its
  `option[value=""]` `unsaved` entry), `"master-preset-select"`, `"master-preset-save"`,
  `"latch-toggle"`, `"inpaint-overlap-button"`, `"overlap-chroma-xfade"`,
  `data-module-toggle="files"`/`"lane-chain"`/`"overlap"`, `[data-file-row]`, `data-module="overlap"`.
- Consumes M5's `dropClip` helper (M5 plan lines 5779-5794), copied verbatim with its `box`/
  `openFiles` helpers, and M5's own premise that dropping at x = 10 and x = 60 on one lane overlaps
  (M5 plan lines 5853-5854). **M5's `ClipBox`/`OverlapBox` emit no `data-testid`** (M5 plan lines
  3659-3667, 4069-4076) even though M5's own `timeline.spec.ts` assumes `[data-testid="clip"]`/
  `[data-testid="overlap"]`, so this spec selects `.clip[role="button"]`/`.overlap[role="button"]`
  — the markup those components actually have (the `role` keeps `.overlap` from also matching
  OverlapInpaint's own root `<div class="overlap">`).

- [ ] **Step 1: Write the spec**

`latent-forge/tests/sessionsFilesOverlap.spec.ts`:

```ts
import { expect, test, type Locator, type Page } from "@playwright/test";
import { convertProjectV1 } from "../src/lib/forge/convertProjectV1";

// dev:mock LISTS dub-sketch (a fixed fixture) but STORES nothing until a PUT (an empty Map), so
// beforeEach PUTs a real project under that name. One clip at tempo 137; backbone medium-base (the
// default stage, so loading it triggers no model rebuild).
const SEEDED = "dub-sketch";
function seededProject() {
  const p = convertProjectV1({
    version: 1,
    meter: { bpm: 137, beatsPerBar: 4 },
    clips: [{
      id: "clip_seed", laneId: "drums", startSec: 1, durationSec: 4, offsetSec: 0,
      source: { kind: "crop", cropId: "001077" }, latentState: "none",
      render: { op: "decode", prompt: "seeded", steps: 24, cfgScale: 6, seed: 1, noiseLevel: 0.4 },
    }],
  });
  p.name = SEEDED;
  return p;
}

async function storedSession(page: Page) {
  const res = await page.request.get(`/forge/sessions/${SEEDED}`);
  expect(res.ok()).toBe(true);
  return res.json();
}

// M5's ClipBox/OverlapBox have no data-testid; this is the markup they really emit.
const CLIP = '.clip[role="button"]';
const OVERLAP_BOX = '.overlap[role="button"]';

// ---- M5's helpers (tests/timeline.spec.ts, M5 plan lines 5773-5794), copied verbatim ----
async function box(loc: Locator) {
  const b = await loc.boundingBox();
  if (!b) throw new Error("element has no bounding box");
  return b;
}

async function openFiles(page: Page) {
  const body = page.locator('[data-module-body="files"]');
  if (!(await body.isVisible())) await page.locator('[data-module-toggle="files"]').click();
  return body;
}

async function dropClip(page: Page, lane: number, x: number) {
  const files = await openFiles(page);
  const row = files.locator("[data-file-row]").first();
  const canvas = page.locator('[data-region="lane-canvas"]').nth(lane);
  const target = await box(canvas);
  await row.dragTo(canvas, { targetPosition: { x, y: target.height / 2 } });
}
// ------------------------------------------------------------------------------------------

test.beforeEach(async ({ page }) => {
  const put = await page.request.put(`/forge/sessions/${SEEDED}`, { data: seededProject() });
  expect(put.ok()).toBe(true);
  await page.goto("/");
  await expect(page.locator('[data-region="topbar"]')).toBeVisible();
});

test("launch never overwrites a saved session, and picking one actually loads it", async ({ page }) => {
  const select = page.locator('[data-testid="session-select"]');
  // M1's sessions[0] auto-select is gone (T9): a fresh tab is `unsaved` ...
  await expect(select).toHaveValue("");
  // ... and even past the 2 s autosave window, the seeded session is untouched on the server.
  await page.waitForTimeout(2600);
  const before = await storedSession(page);
  expect(before.clips).toHaveLength(1);
  expect(before.meter.bpm).toBe(137);

  await expect(page.locator(CLIP)).toHaveCount(0);
  await select.selectOption(SEEDED);
  await expect(page.locator(CLIP)).toHaveCount(1);   // the seeded clip, loaded from the server
});

test("unsaved until named; once loaded, an in-place edit autosaves to the server about 2 s later", async ({ page }) => {
  const select = page.locator('[data-testid="session-select"]');
  await expect(select.locator('option[value=""]')).toHaveText("unsaved");
  await select.selectOption(SEEDED);
  await expect(page.locator(CLIP)).toHaveCount(1);
  await expect(select.locator('option[value=""]')).toHaveCount(0);   // named now
  expect((await storedSession(page)).lanes[0].chain.latch_on).toBe(false);

  // An in-place chain edit -- exactly what a reference-only autosave effect never sees.
  const body = page.locator('[data-module-body="lane-chain"]');
  if (!(await body.isVisible())) await page.locator('[data-module-toggle="lane-chain"]').click();
  await page.locator('[data-testid="latch-toggle"]').click();

  await expect
    .poll(async () => (await storedSession(page)).lanes[0].chain.latch_on, { timeout: 6000 })
    .toBe(true);
  expect((await storedSession(page)).clips).toHaveLength(1);   // the rest of the session survived
});

test("the MASTER PRESET SAVE button is enabled and a saved preset round-trips", async ({ page }) => {
  const saveBtn = page.locator('[data-testid="master-preset-save"]');
  await expect(saveBtn).toBeEnabled();
  page.once("dialog", (d) => d.accept("smoke-test-preset"));
  await saveBtn.click();
  await expect(page.locator('[data-testid="master-preset-select"] option', { hasText: "smoke-test-preset" })).toHaveCount(1);
});

test("the FILES module lists mock files and rows stay draggable after M7's HELP additions", async ({ page }) => {
  const body = page.locator('[data-module-body="files"]');
  if (!(await body.isVisible())) await page.locator('[data-module-toggle="files"]').click();
  const rows = body.locator("[data-file-row]");
  await expect(rows.first()).toBeVisible();
  await expect(rows.first()).toHaveAttribute("draggable", "true");
  await expect(page.locator('[aria-label="file root"]')).toHaveAttribute("data-help", /.+/);
  await expect(page.locator('[aria-label="filter files"]')).toHaveAttribute("data-help", /.+/);
});

test("OVERLAP-INPAINT is absent without an overlap selected -- M1's frozen count-0 assertion, untouched", async ({ page }) => {
  await expect(page.locator('[data-module="overlap"]')).toHaveCount(0);
});

test("OVERLAP-INPAINT appears with its real content once two clips overlap and the overlap is clicked", async ({ page }) => {
  await expect(page.locator('[data-module="overlap"]')).toHaveCount(0);
  await dropClip(page, 2, 10);
  await dropClip(page, 2, 60);   // M5's own premise: close enough to overlap the first
  const overlap = page.locator(OVERLAP_BOX).first();
  await expect(overlap).toBeVisible();
  await overlap.click();
  await expect(page.locator('[data-module="overlap"]')).toHaveCount(1);
  const body = page.locator('[data-module-body="overlap"]');
  if (!(await body.isVisible())) await page.locator('[data-module-toggle="overlap"]').click();
  await expect(page.locator('[data-testid="inpaint-overlap-button"]')).toHaveText("▸ INPAINT OVERLAP");
  // a never-edited overlap renders OVERLAP_DEFAULT (chroma crossfade on) without seeding it first
  await expect(page.locator('[data-testid="overlap-chroma-xfade"]')).toHaveText("[ON]");
});
```

- [ ] **Step 2: Run it**

```bash
cd /home/kim/Projects/sa3-studio-review/latent-forge && npx playwright test tests/sessionsFilesOverlap.spec.ts
```

This is a verification run, not a red step: Tasks 6-9, which this spec exercises, are already
implemented by the time it is written. Expected: `6 passed`. What each test would catch if a
T6-T9 behaviour regressed: test 1 fails at `toHaveValue("")` if the `sessions[0]` auto-select comes
back, at `clips toHaveLength(1)` if launch autosaves over the session, and at the clip count if
`loadSession` stops applying; test 2 fails at the poll if autosave stops seeing in-place edits;
test 3 if `master-preset-save` is disabled again; test 4 if a FILES `data-help` goes missing; test 6
if OVERLAP-INPAINT's body throws or seeds on first render.

- [ ] **Step 3: Run the layout suite beside it**

```bash
cd /home/kim/Projects/sa3-studio-review/latent-forge && npx playwright test tests/layout.spec.ts tests/sessionsFilesOverlap.spec.ts
```

Expected: **`1 failed, 16 passed`** — M1 T15's 11 layout tests plus this task's 6 = 17. The one
failure is M1's own `each bottom tab opens`, which is red before and after this milestone (Global
Constraint #5: it clicks `[data-tab="chroma"]`, which matches no button and not the current tab's
body either). None of the other 10 layout tests changed. Do not "fix" it from here — it is M1's
frozen file and is flagged for WINTERMUTE.

- [ ] **Step 4: Commit**

```bash
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M7 T10: sessions/presets/FILES/OVERLAP Playwright fragment against dev:mock (seeded session, real autosave round trip, positive OVERLAP-INPAINT case via M5's dropClip); self-review below"
```

- [ ] **Step 5: Self-review**

| Requirement | Where | State |
|---|---|---|
| §4.6.1 OVERLAP-INPAINT: info line, 64px curve, chroma xfade, local STEPS/CFG, INPAINT OVERLAP button (no-op) | T7 `OverlapInpaint.svelte`; T10 test 6 in the real app | done |
| §4.6.2 FILES: root header, root select, filter field, draggable list | T15 (M1) real body; T6 adds the two missing `data-help`s | done |
| §6.3 FILES roots `crops`/`renders`/`uploads`, unavailable shown not hidden | T15 (M1), verified by T6's own test | done |
| §9.2 sessions: SESSION select loads through `convertProjectV1` when not already v2 | T9 `loadSession`/`toV2`; T10 test 1 | done |
| §9.2 v1 files load through a converter | T9 IMPORT button → `importProjectFile` → `convertProjectV1` | done (file import; the server only ever stores v2) |
| §9.2 autosave 2s after the last change, `unsaved` until named | T9 `createSnapshotAutosave` + the `unsaved` option; T10 tests 1-2 | done |
| §9.2 `previewAudio` not serialised | T9 `serializeProject` writes `null`; T8 converter writes `null` | done |
| §9.2 `backbone` restored on load | T9 `applyProject` → `settings.stage`, `syncBackbone` rebuilds | done (`small-music*` backbones leave the stage alone — see Open questions) |
| §9.2 v1→v2: lane rename, `RenderSettings` default-fill | T8 `convertProjectV1` | done |
| §9.3 module presets (`latch`/`film`/`lora`/`bungee`): recall, SAVE, DEL, active lane only | T2 `modulePresets.ts` + `LaneChain.svelte` | done |
| §9.3 master scope: lane chains, clip layout+A2A (no audio), mix, master chain, schedule+prompt | T9 `buildMasterPresetPayload`/`applyMasterPreset` | done, against the literal enumeration (see Open Questions on the two-reading conflict) |
| §6.3 session name regex validated client-side before the PUT | T9 `sessionName.ts` | done |
| M1's frozen `[data-module="overlap"]` count-0 assertion | T10 test 5, untouched | done |
| RightPaneModules' lit dots (`chain`, `master`, `overlap`) | T9 Step 5 | done; `sampling` stays `null` (M4 never wired it) |
| M4 → M7 handoff: `SigmaColumn slots`, `AdvancedSampling latch` | T9 Step 5 | done |

**Known incomplete.**

1. **Autosave's end-to-end test costs real time.** T10 test 1 waits 2.6 s on purpose (to prove
   launch does not write), and test 2 polls for up to 6 s for the real 2 s debounce. Together they
   add roughly 5 s to the Playwright run; the debounce's own edge cases stay in `autosave.test.ts`
   (Task 9, fake timers).
2. **The v1 store's orphaned state (`App.svelte`/`keyboard.ts`/transport possibly still reading
   `sa3-studio`'s `project` singleton instead of `arrangement`)** is a verified cross-milestone gap
   (see Task 9's WHY) that this task cannot close — rewiring the keyboard/transport is outside
   "FILES, OVERLAP-INPAINT, sessions, presets, autosave, v1→v2." Flagged for FLATLINE to route to
   WINTERMUTE alongside the `ModuleShell`/`viewStore` defects the brief already names.
3. **M1's `each bottom tab opens` stays red** (Global Constraint #5) — M1's file, not this
   milestone's to edit.

## Open questions

1. ~~**`NEW_STRINGS` is edited by both writers in parallel; `strings.test.ts`'s `toHaveLength(87)`
   is updated once at assembly.**~~ — **closed by critic pass 1.** The "each task is independently
   green" claim was false for the whole suite: M1's `strings.test.ts` went red at Task 2's first
   entry and no step ever edited it. Every string-adding task (2, 4, 5, 6, 9) now updates that
   assertion to its cumulative total in execution order — 100, 104, 107, 109, **112** — and the
   `RightPaneModules.svelte` edit is a real step (Task 9 Step 5), not an assembly note.

2. **M5's own Normative-names table is wrong about where the v1 `project` store gets rewired/
   deleted.** It says "Task 7 is the swap point" (`2026-09-17-latent-forge-m5-timeline-fidelity.md
   :5925`); I read M5 Task 7's actual body in full and it never touches `App.svelte`, `TopBar.svelte`
   or `keyboard.ts`, and a full-file grep of the M5 plan for edits to those three files returns
   nothing. As of "M5 done, reviewed, reconciled," the v1 `project` store (`sa3-studio/src/lib/
   store.svelte.ts`) may still be what `App.svelte`'s keyboard actions and `RulerTransport.svelte`'s
   transport buttons read/write, disconnected from `arrangement`. Task 9 does not depend on
   `project` (it removes the one place in `TopBar.svelte` that referenced it), but this is a real,
   verified defect worth a line to WINTERMUTE, the same class as the `ModuleShell`/`viewStore`
   defects the brief already flags.

3. **`settings.attach(source: TargetSettingsSource)` (M4) is never called in production code
   anywhere across M1/M4/M5** — every occurrence outside a `__tests__` file is zero, checked by a
   full grep of both plans. This means PROMPT + SIGMA / ADVANCED SAMPLING may currently always
   resolve to `session.defaults` regardless of the selected clip/overlap, never actually reading or
   writing a clip's own `render`. It does not block Task 9 (clip/overlap `render` fields exist and
   serialise independently of whether `settings` is wired to edit them), but it is a real
   integration gap between M4 and M5 worth flagging to WINTERMUTE.

4. **The v1 `SnapMode` spelling the brief and M5's own Normative table cite ("8"/"16"/"32" bare
   digits) does not match the real source.** `sa3-studio/src/lib/musictime.ts:52` already spells
   `SnapMode` as `"1/8"|"1/16"|"1/32"` — the only real v1→v2 mapping needed is `"off"` → `"free"`.
   `convertProjectV1`'s `SNAP_V1_TO_V2` table (Task 8) handles both the claimed and the real
   spelling defensively, but the claim itself should be corrected in whichever document repeats it
   next.

5. **No text-entry affordance exists in the v3 drawing for naming a brand-new session or master
   preset** — the SESSION and MASTER PRESET selects only ever list existing names (§6.3's `GET`
   routes), and neither the spec nor the drawing shows a name field next to either SAVE button.
   Task 9 uses `window.prompt()` for both (asked only when nothing is currently named), which needs
   no new screen real estate and is straightforward to mock in tests, but is a placeholder for a
   real inline name field. Confirm with Kim, or design one, before this ships user-facing.

6. **§9.3's master-preset scope has two readings that do not fully reconcile**: "the whole project
   minus `clips[*].audio` refs and `renders`" (a blacklist) versus the sentence's own enumeration
   ("every lane chain, clip layout..., mix order and node values, master chain, sampling schedule
   and default prompt" — narrower than "everything except two fields," since it never mentions
   `name`, `view`, `ui`, `backbone`, `ckpt_path`, or any `defaults` field beyond `schedule`/
   `prompt`). Task 9 ships the literal enumeration as its own `MasterPresetPayload` shape (distinct
   from `ProjectV2`), reasoning that the separate `render`-level preset (M4) already owns the rest
   of `RenderSettings`, so folding all of `defaults` into `master` too would make the two levels
   redundant. Recorded as a real spec-internal tension, not silently resolved either way.

7. **§9.3's own heading says "three levels" but lists four** (prompt, render, module, master) — a
   spec-internal slip the brief itself already flagged as not M7's to silently "correct." Repeating
   it here since Task 9 is the master-level implementation and the four-bullet enumeration (not the
   heading's "three") is what it ships against, matching the HTTP contract's `level` enum.

8. **`ProjectV2.backbone`/`ckpt_path` and `App.svelte`'s own `model`/`modelFolder` `$state` (M1 T10)
   are two different pieces of state, and nothing wires them together.** Task 9 serialises/restores
   `backbone`/`ckpt_path` through `settings.backboneId`/`settings.ckptPath` (M4), reasoning from
   `settings.svelte.ts`'s own doc comment that `ckptPath` is "carried in the project JSON" — but the
   TopBar's actual MODEL select (`App.svelte`'s `model`/`modelFolder`) is never read from or written
   to `settings` by any milestone I can find. A session load/save under this task's design will not
   visibly move the MODEL select. **Corrected by critic pass 1:** this item originally said a load
   "correctly moves `settings`" — it did not for the backbone, because `backboneId` is a getter over
   `settings.stage` and `applyProject` never set `stage`. It now does (mapping `backbone` back
   through `STAGE_BACKBONE`, and rebuilding the server model when the stage changes); `ckpt_path`
   was already restored. Wiring `App.svelte`'s model state through `settings` (or vice versa) is
   still a follow-up, outside "sessions, master preset, autosave."

9. **`Files.svelte`'s current state, resolved definitively (per the brief's own open question).**
   Read directly against `docs/superpowers/plans/2026-09-16-latent-forge-m1-foundation-shell.md
   :8623-8785`: it is a full, working implementation — `$effect`-driven fetch on `[root, q]`, a real
   root `<select>` and filter `<input>` (both with `aria-label`, neither with `data-help` until this
   task), unavailable-root handling exactly per spec §6.3, and drag payloads on both
   `application/x-forge-ref` and (for a crop) `text/sa3-crop-id`. It is **not** a stub, and the only
   gap against spec §4.6.2 is the two missing `data-help` ids, closed by Task 6.

10. **All v3 line numbers and HELP ids this writer's tasks cite were re-verified against the real
    file**, not trusted from the brief: top-bar SESSION (27)/MASTER PRESET select (40)/label
    (39, none)/SAVE button (43, none) — confirmed against
    `docs/sa3-studio/design_handoff/SA3 Studio v3.dc.html:25-52`; FILES (474-484, no select/filter
    anywhere, row's `data-help` at 480) — confirmed against the same file's 470-486; the four
    OVERLAP ids (`overlapChromaXfade` 460, `overlapOverride` 464, `overlapSteps` 466, `overlapCfg`
    467) — confirmed against the same file's 448-468. No discrepancy found in any of these; the
    brief's table is correct on all of them. The one discrepancy found (item 4 above) is in v1's
    `SnapMode` spelling, not in any v3 line number or HELP id.

---

## Open questions

**Every one has a shipped reading, so nothing here blocks an implementer.** The load-bearing ones
want Kim's or WINTERMUTE's answer rather than a default; the rest are recorded as each writer found
them, in full, in the two per-writer "Open questions" sections above (after Task 5 and after
Task 10). Items 18-24 were added by critic pass 1.

1. **`LatchRequest`'s wire shape is FLATLINE's writer's own invention** — spec §5.5 gives only the
   mapping formula, not a request shape. Shipped `{slots: LatchRequestSlot[]; rho; mu; gamma; n_iter;
   log_norms}`, `slots` holding only active entries. If M8's real server-side payload is keyed
   differently, this and `resolveLatch`'s return need a matching change.
2. **`settings.attach()` (M4) is never called anywhere outside a test file, across M1, M4 and M5** —
   verified by a full grep of both plans; every real occurrence is inside a `beforeEach` test fixture.
   PROMPT + SIGMA / ADVANCED SAMPLING may currently always resolve to `session.defaults`, never a
   clip's own settings. Does not block this milestone (clip/overlap `render` serialises
   independently) but is a real M4/M5 integration gap.
3. **M5's own Normative-names table wrongly names Task 7 as where the legacy v1 `project` store is
   rewired or removed** — M5 Task 7's actual body never touches `App.svelte`, `TopBar.svelte` or
   `keyboard.ts` (verified by a full grep of the M5 plan). The legacy store may still be what
   keyboard actions and the transport buttons read/write, disconnected from `arrangement`. This
   milestone's Task 9 does not depend on it (it removes the one `TopBar.svelte` reference), but it's
   worth a line to WINTERMUTE.
4. **The real v1 `SnapMode` spelling is not what the brief (and M5's own table) claimed.** The actual
   source (`sa3-studio/src/lib/musictime.ts:52`) already spells it `"1/8"|"1/16"|"1/32"` — only
   `"off"` → `"free"` needs mapping. The converter (Task 8) handles both the claimed and the real
   spelling defensively; the claim itself should be corrected wherever it's repeated next.
5. **No text-entry affordance exists in the drawing for naming a new session or master preset** —
   both selects only ever list existing names. Task 9 uses `window.prompt()` as a placeholder
   (asked only when nothing is currently named). Confirm with Kim, or design an inline field, before
   this ships user-facing.
6. **§9.3's master-preset scope has two readings that don't fully reconcile**: "everything except
   `clips[*].audio` and `renders`" (a blacklist) versus the same sentence's own narrower enumeration.
   Task 9 ships the literal enumeration as its own `MasterPresetPayload` shape, reasoning that the
   separate render-level preset (M4) already owns the rest of `RenderSettings` — recorded as a real
   spec-internal tension, not silently resolved.
7. **`ProjectV2.backbone`/`ckpt_path` and `App.svelte`'s own MODEL select `$state` are never wired
   together anywhere.** Task 9 serialises backbone/ckpt through `settings.backboneId`/`.ckptPath`
   (M4), but the TopBar's actual MODEL select is never read from or written to `settings` by any
   milestone found, so a session load does not visibly move the MODEL select. (The earlier text
   here said a load "moves `settings` correctly"; for the backbone it did not — `backboneId` is a
   getter over `settings.stage`, which `applyProject` never set. Critic pass 1 fixed that:
   `applyProject` now restores `stage` through `STAGE_BACKBONE`, and `loadSession`/IMPORT rebuild the
   server model when it changes, reverting on failure. A saved `small-music`/`small-music-base`
   backbone has no stage and leaves `stage` alone.) Wiring `App.svelte`'s model state through
   `settings` is a follow-up — not attempted here, outside "sessions, master preset, autosave."
8. **`fetchAdapters()`'s real server mismatch** (Global Constraints #4) — flagged again here as it's
   the kind of cross-milestone defect WINTERMUTE asked to hear about as one batch.
9. **M1's own Playwright layout spec clicks the tab body, not the tab button** (Global Constraints
   #5) — `each bottom tab opens` is red before and after M7, and Task 10's whole-suite gate says so.
   Same batch.
10. **Two toggle buttons the brief's own HELP-gap table omitted**: LATCH GUIDANCE's own toggle
    (v3:507) and BUNGEE's own toggle (v3:557), verified directly against the real v3 file, carry no
    `data-help` exactly like FILM's and LORA/DORA's toggles which the brief did flag. Added
    `latchToggle`/`bungeeToggle` to `NEW_STRINGS` for consistency (every on/off toggle in the module
    now has a string) — drop both if unwanted.
11. **The MIX + SIGNAL PATH tab's two render buttons reuse `HELP.renderButton`** (the existing
    top-bar id) rather than a new `mixMixdown` string, on the reasoning that it's conceptually the
    same commit action. Flag if a distinct string is wanted.
12. **The SIGNAL PATH list is a client-side estimate, not ground truth.** The real per-stage data
    only exists in a commit job's `meta.stages` (§6.9), produced by nothing until M9 wires the
    MIXDOWN button. `signalPath.ts`'s lit/dimmed rules are a reasonable approximation, stated as such
    in the file's own header comment. Whether M9 should replace this wholesale with `meta.stages`
    once a commit has run, or reconcile the two, is not decided here.
13. **S4's idle note is attached once, for the first idle lane found**, since the SIGNAL PATH is one
    aggregate row per stage, not per lane, while §8.1 states the note per-lane. A project with two
    independently-idle lane chains only ever shows one note at a time.
14. **`needsStretch` (§8.1 S2)'s exact definition is the writer's own choice** — the brief named only
    "chains, overlaps, mix and master state" as `signalPath.ts`'s inputs, not clip stretch data;
    `SignalPathInput` was extended with a `clips` array to make S1/S2/S3/S5 meaningful at all. A
    narrower reading would make those stages permanently dimmed, which seemed clearly wrong given the
    spec's own worked idle-lane example.
15. **`Files.svelte` is confirmed, definitively, NOT a stub** — read directly: a full working
    implementation with a real root select and filter input (both with `aria-label`, neither with
    `data-help` until Task 6), `$effect`-driven fetch, unavailable-root handling per spec, and both
    drag-payload formats. The only gap against §4.6.2 was the two missing HELP ids, closed by Task 6.
16. **`fetchLatchHeads()` lives in `src/lib/chains/latch.ts`** rather than `src/lib/forge/models.ts`
    (where the other `/models`/`/slots` fetchers live), since it shapes `/info.latch_heads` into the
    exact type `resolveLatch` consumes and both LaneChain and MasterChain need the identical shape.
    Flag if a different placement is preferred.
17. **§9.3's "three levels, four bullets" slip** — reproduced as found, shipped against the four
    bullets (matching the HTTP contract's `level` enum), not silently corrected.
18. **The spec spells S4's idle note two ways**: §5.5 (spec line 474) `chain idle — no A2A clip in
    lane`, §8.1 S4 (spec line 788) `chain idle — no A2A clip`. Shipped §5.5's, since §5.5 is the
    normative LANE CHAIN section and the longer form says which thing lacks the clip. The spec should
    be made to agree with itself; `signalPath.ts` and its test change one string if §8.1 wins.
19. **ADVANCED SAMPLING's lit dot stays dark.** M1 T12's comment promised "M4 replaces `sampling`
    with render.settingsFor(view.selection)", but M4 never edited `RightPaneModules.svelte` (M4 plan
    line 4712). Task 9 Step 5 keeps `sampling: null` rather than silently doing M4's wiring; the
    one-line fix would be `sampling: settings.current(view.selection)`. Flag for WINTERMUTE.
20. **`AdvancedSampling`'s other handoff prop, `a2a`, is still unwired** (M4 plan line 4741 says "M5
    and M7 exist to wire them"). Task 9 wires `latch` (M7's half); `a2a` is the selected clip's A2A
    state, M5's half, and no M5 task passes it. Same batch.
21. **M5's own Playwright selectors do not match M5's own markup.** `tests/timeline.spec.ts` assumes
    `[data-testid="clip"]`/`[data-testid="overlap"]` (M5 plan lines 5727, 5746), but `ClipBox`/
    `OverlapBox` emit no `data-testid` (M5 plan lines 3659-3667, 4069-4076); and it asserts
    `[data-module="overlapInpaint"]`, while the module id is `overlap` (M1 plan line 8342, the frozen
    count-0 assertion). Task 10 selects `.clip[role="button"]`/`.overlap[role="button"]` and
    `[data-module="overlap"]`. Not M7's file to fix — same batch.
22. **v1 files come in through an IMPORT button, not a server session.** Task 9 removes M1 T15's
    LOAD button with the v1 store it read, and server sessions are always v2, so §9.2's "version 1
    files … load through a converter" needed a new way in. IMPORT (a hidden file input) is the
    smallest one: the drawing has no such control, so it is spec-only, like FILES' root select. An
    imported file stays `unsaved` until SAVE names it.
23. **The client does not validate module- or master-preset names**, only session names (spec §6.3's
    regex is stated for sessions). A bad preset name comes back as the server's refusal. If §6.3
    means the same pattern for presets, `isValidSessionName` is the check to reuse.
24. **The `unsaved` label is an option inside the SESSION select**, not a span beside it — §9.2 says
    the select itself "shows `unsaved` until named". Picking a real session removes the option.

*Two writers, dispatched in parallel this time (the split is by feature area, not by layer — see
"Architecture" above), each independently re-verified every v3 line number and HELP id their tasks
cite against the real handoff file and M1's real table; no discrepancy was found in either half
beyond items 10-11 above, both already resolved with a shipped reading.*
