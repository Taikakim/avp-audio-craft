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
3. **Two M1 internal contradictions — fixed at source by the reconcile pass (2026-09-25); M1 now
   reads the way this milestone uses it:**
   - **`ModuleShell` has one declaration**: M1 T9's code is the Normative `{id, title, lit,
     children}` version, self-driven off `view.isModuleOpen(id)`/`view.toggleModule(id)`, emitting
     `data-module={id}`, `data-module-toggle={id}`, `data-module-body={id}` and the now-pinned lit
     dot `data-module-dot={id}` with `data-lit="true" | "false"` (M1 T9's Interfaces). T9's
     `rightPaneModules.test.ts` reads that dot directly; the `ModuleShellProbe` it used to mock
     `ModuleShell` with is gone (Open questions 27).
   - **The view store singleton is `view`** (`export const view = new ViewStore();`, M1 T7). M1
     T9-T11's `App.svelte` blocks import `{ view }` now; there is no `viewStore` binding anywhere.
4. **`fetchAdapters()` (M1, `src/lib/forge/models.ts`) reads `models`** — fixed at source by the
   reconcile pass. The real `/models` route returns `{"ok", "count", "models": [...],
   "stale_root_ids"}` (`eval/explorer_render_server.py`, the `/models` route); M1 read `ckpts` and
   its own mock seeded `ckpts`, so it agreed with itself and resolved `[]` against the real server.
   This milestone's `fetchFilmCkpts()`/`fetchSlots()` read the real fields, and **Task 10's
   recorded-response contract test** checks `fetchAdapters()` against the recorded
   `models_adapters.json` — the kind of mock/server disagreement WINTERMUTE asked every route this
   milestone touches to be tested for. LORA/DORA's model select now gets adapters.
   **`fetchFilmCkpts()` asks `/models?family=control_adapter` and keeps only `control_mode ===
   "scalar"`** (WINTERMUTE 2026-09-25, critic follow-up #1; Open questions 36). There is no `film`
   family (`eval/ckpt_probe.py` `FAMILIES`), so the reconcile pass's `family=film` always answered
   `[]`. The filter is required: `_install_film` builds a `ScalarAttributeEncoder`, and the other
   control modes would load the wrong encoder. Task 10 checks it against the recorded
   `models_control_adapters.json`, never against the adapter recording.
5. **M1's Playwright tab test is fixed at source** (reconcile pass): it clicks
   `[data-testid="bottom-tab-<id>"]` and checks the tab body's `data-tab`, instead of clicking
   `[data-tab="<id>"]` (the body) and waiting for a `[data-tab-body]` M1 never emits. Task 10's
   whole-suite gate therefore expects **no** failure. This milestone's own specs click the same
   buttons.
6. **`settings.attach()` (M4) is wired in production by this milestone** (reconcile pass). It was
   called only in test fixtures across M1, M4 and M5, so PROMPT + SIGMA / ADVANCED SAMPLING always
   resolved to `session.defaults`. M5 T1 now provides the source (`arrangement.settingsSource`,
   never seeding) and Task 9 Step 4's `App.svelte` attaches it; M7 does it because it is the first
   plan that depends on both M4 and M5, which §12 keeps from importing each other.
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
10. **Never arm, or SAVE to, a session the stores do not hold** (critic pass 2; reworded by critic
    pass 3 #11). A session load or IMPORT validates before it touches a store, disarms autosave
    before it applies, and names/arms the target only after apply (and the model rebuild) finished
    and no newer load superseded it; SAVE is refused, and its button disabled, while one is in
    flight. During steps 5-8 the SESSION select still shows the previous, already-disarmed name, so
    the TopBar says `loading <name>…` beside it: the name on screen is never taken for what the
    timeline holds. The whole order is stated once, in Task 9's WHY, and lives in one unit-tested
    class (`SessionController`), not in `App.svelte`.

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
  family=adapter&loadable=1`. `AdapterEntry = {path: string; name?: string; label?: string;
  family?: string}` is **declared and exported by `src/ui/topbar/modelOptions.ts`** (M1 T10,
  `export interface AdapterEntry`; `name` optional since critic follow-up #6 — real `model_db` rows
  carry `label`, not `name`); `models.ts` only `import type`s it (M1 T10, `import type {
  AdapterEntry } from "../../ui/topbar/modelOptions";`) and does not re-export it, so a
  component imports the type from `modelOptions`, never from `models`. This milestone adds two
  siblings in `models.ts`: `fetchFilmCkpts()`
  (`/models?family=control_adapter`, keeping only `control_mode === "scalar"` rows — Open questions
  36 — with `/info.film_default.ckpt` as the preselected default) and `fetchSlots()` (`GET /slots`,
  verified shape `{ok, active: number|null, backbone: string|null, slots: [{index, path, label,
  family, cost_gb, strength}], max_slots, vram_floor_gb, free_gb}` against
  `eval/adapter_slots.py:51-60,156-160` and `eval/explorer_render_server.py:839-846,901-905`).
- **`arrangement.lanes[n].chain: LaneChain`** already exists, seeded `CHAIN_DEFAULTS`, since M5 day
  one (`defaultLanes()`). **`arrangement.mix: MixSpec`** and **`arrangement.master: MasterChain`**
  are two NEW fields this milestone adds (Task 3), seeded `structuredClone(MIX_DEFAULT)` /
  `structuredClone(MASTER_DEFAULT)`, plus one non-seeding reader, `peekOverlapParams(key)`
  (Global Constraint #8), and one reset, `clearOverlapParams()` (T9's load empties the private
  overlap store through it), and the `renderSeed` hook `addClip` seeds a clip's `render` from
  (critic follow-up #4; App points it at `settings.defaults`) — nothing else in `ArrangementStore`
  changes. The viewport is
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
  It is "re-derived on load" (M5 plan lines 6004-6005): T9's load calls M5's
  `scheduleStretch(clipId)` (`src/lib/clips/lifecycle.ts`, M5 T10) for every loaded clip.
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

M1 T12's `RightPaneModules.svelte` (M1 T12, the block starting `const snapshot:
ModuleStateSnapshot = {`) still holds a one-shot constant
snapshot of four `null`s. **M4 never edited this file** — M4 plan line 4712 says its module "does not
need `RightPaneModules.svelte` touched at all" and no M4 task changes `sampling` — so `sampling` is
still literally `null` and stays `null` here (see Open questions). Task 9 Step 5 replaces the
constant with a `$derived` over `chain` (T2's expression), `master` (T4's) and `overlap` (T7's, read
through the non-seeding `peekOverlapParams`), makes `lit` a `$derived` too, and passes the active
lane's LatCH state to `<AdvancedSampling latch=…>` (M4's own handoff, M4 plan line 4741) — only the
slots whose head `/info.latch_heads` lists, so it agrees with `chainRequest` (critic pass 2 #8). The
same step also carries M4's other two handoffs, moved here by the reconcile pass (2026-09-25):
`sampling: settings.current(view.selection)` (Open questions 19) and `<AdvancedSampling a2a=…>`
(Open questions 20). The full code is in that step.

## The `data-*` / `data-testid` / `HELP` contract

| selector / id | owner | note |
|---|---|---|
| `[data-module-toggle="lane-chain"\|"master-chain"\|"files"\|"overlap"]`, `[data-module-body=...]`, the lit dot `[data-module-dot=...]` + `data-lit` | pre-existing (M1 T9/T12; the dot pinned by the reconcile pass 2026-09-25) | not re-emitted by this milestone — the modules mount inside them |
| `HELP.modulePreset`, `.latchHead`, `.latchTargetKind`, `.latchTargetValue`, `.latchWeight`, `.latchStartPct`, `.latchEndPct`, `.latchRho`, `.latchMu`, `.latchGamma`, `.latchMeanIter`, `.latchLogNorms`, `.bungeeSemitones` | pre-existing (M1 T14) | LANE CHAIN, T2 |
| `HELP.latchToggle`, `.filmToggle`, `.filmPreset`, `.filmCkpt`, `.filmScale`, `.loraToggle`, `.loraPreset`, `.loraModel`, `.loraScale`, `.bungeeToggle`, `.bungeePreset`, `.modulePresetSave`, `.modulePresetDelete` (13); `.filmTarget` pre-existing (M1 `NEW_STRINGS`) | **new, T2** | LANE CHAIN; none of the 13 existed anywhere before |
| `data-testid="latch-toggle"`/`"film-toggle"`/`"lora-toggle"`/`"bungee-toggle"`, `"<level>-preset-save"`, `"<level>-preset-delete"` for `level` ∈ `latch`/`film`/`lora`/`bungee` | **new, T2** | LANE CHAIN |
| `HELP.masterLatchToggle`, `.masterLatchHeadLabel`, `.masterHead`, `.masterGain` (4); `.latentNormalise` pre-existing | **new, T4** | MASTER CHAIN; `data-testid="master-latch-toggle"`/`"master-norm-toggle"` |
| `HELP.mixQuadWeight`, `.mixLerp`, `.mixSlerp` (3); `.mixOrder`/`.mixFold`/`.mixNodeT`/`.signalPath`/`.mixExpand` pre-existing, `HELP.renderButton` reused for both MIXDOWN buttons | **new, T5** | MIX + SIGNAL PATH; `data-testid="mix-fold"`/`"mix-expand"`/`"m1-lerp"`…, `data-signal-stage`/`data-lit`, `data-tab-body="mix"` |
| `HELP.filesRoot`, `.filesFilter` (2) | **new, T6** | FILES — `filesRow` (pre-existing) is untouched |
| `HELP.overlapChromaXfade`, `.overlapOverride`, `.overlapSteps`, `.overlapCfg` (all pre-existing) | T7 | OVERLAP-INPAINT — no new ids; `data-testid="overlap-chroma-xfade"`/`"overlap-override"`/`"overlap-steps"`/`"overlap-cfg"`/`"inpaint-overlap-button"` |
| `HELP.masterPresetSave`, `.sessionSave`, `.sessionImportV1` (3) | **new, T9** | top bar: on `data-testid="master-preset-save"`, `"session-save"`, `"session-import"` (+ hidden `"session-import-file"` input) |
| `LaneChain.lora.ckpt_path` is the adapter's **durable identity**; `LaneChain.lora.slot` is a **transient resolution** of that path against the current `GET /slots` | **rule, T2/T9** (critic pass 2 #14) | a `/slots` index names whatever is resident *now*, so it is never persisted: every saved payload (module preset, session, master preset) writes `slot: null` through `durableChain`/`modulePresetPayload` (T2), and the live value is re-resolved by path when LORA/DORA picks or recalls a model. M9 must resolve from `ckpt_path` at submit and treat `slot` as a hint at most (Open questions 25) |
| `docs/latent-forge/extract_help.mjs`'s `NEW_STRINGS` and `strings.test.ts`'s total | **T2, T4, T5, T6, T9 each add entries and each updates `strings.test.ts`** | cumulative totals in execution order: M1 T14 87 → T2 **100** → T4 **104** → T5 **107** → T6 **109** → T9 **112** (80 extracted + 7 M1 new + 25 M7 new) |

---

## The numbers §5.5 and §9.x pin — copy them exactly, do not re-derive

- **LatCH mapping — the SERVER's, not the client's** (WINTERMUTE 2026-09-25; M8 `parse_chain` →
  `chain_to_request`, M8 plan lines 331-395). §5.5's `gain_k = head.default_gain · weight_k`,
  `rho = ρ·gain_0`, `mu = μ·gain_0` is computed server-side. The client sends the chain object
  itself, exactly `{latch_on, slots:[s0, s1], hparams:{rho, mu, gamma, n_iter, log_norms}, film_on,
  film, lora_on, lora, bungee_on, semitones}` (Task 1's `chainRequest`): **always two slots** (one is
  a 400), `rho`/`mu` the raw **0–30 multipliers** (pre-multiplied values 400 or get squared), an
  inactive slot sent in place as `head: "none"` or `weight: 0` (the server drops it), a head
  `/info.latch_heads` does not list rewritten to `"none"` in place (the server 400s on an unknown
  head with weight > 0, and W keeps that), and `lora.slot: null` beside `ckpt_path`.
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
   and writing this plan, verified independently.** They were flagged to WINTERMUTE as one batch at
   assembly; W handed them back (2026-09-25), and **the reconcile pass fixed them at their source
   plans** — `fetchAdapters`'s wrong field, the stale Playwright locator, `ModuleShell`'s duplicate
   declaration, `viewStore`/`view`, M1 T15's App replacement, `.notice`, M4's unblocked
   `confirmStage`, M5's Normative table and `SnapMode` claim, M5's Playwright selectors. The M4/M5
   handoffs that need both stores (`settings.attach`, ADVANCED SAMPLING's `a2a` prop and lit dot)
   landed here, in Task 9, because M7 is the first plan that depends on both. Still open: the TopBar
   MODEL select never wired to `settings` (Open questions 7), and the v1 store's keyboard rewire,
   which no plan owns (Open questions 3). See "Reconcile pass 2026-09-25" below.

---
## File structure

| file | what it is |
|---|---|
| `latent-forge/src/lib/chains/latch.ts` | `chainRequest` (the wire chain M8 takes), `chainIsIdle`, `fetchLatchHeads` (T1) |
| `latent-forge/src/test-setup.ts`, `latent-forge/vitest.config.ts` | **new / modified**: registers `@testing-library/jest-dom/vitest` through a `setupFiles` entry (T2) |
| `latent-forge/src/lib/forge/models.ts` | **modified**: adds `fetchFilmCkpts` (`family=control_adapter`, `control_mode` scalar only — Open questions 36), `fetchSlots` beside the existing `fetchAdapters` (T2) |
| `latent-forge/src/lib/chains/modulePresets.ts` | the four module-preset slices (`latch`/`film`/`lora`/`bungee`): payload builder + in-place recall, and `durableChain` (a plain copy with the transient `lora.slot` cleared) (T2) |
| `latent-forge/src/ui/modules/LaneChain.svelte` | **modified**: full LatCH/FiLM/LoRA/Bungee UI with module preset recall/SAVE/DEL, replacing M1's stub (T2) |
| `latent-forge/src/lib/help/__tests__/strings.test.ts` | **modified** (M1 T14's file): the total-count assertion, updated by every string-adding task (T2, T4, T5, T6, T9) |
| `latent-forge/src/lib/mix/mixMath.ts` | MIX ORDER node-tree resolution (T3) |
| `latent-forge/src/lib/mix/signalPath.ts` | the nine §8.1 stage rows, lit/dimmed derivation (T3) |
| `latent-forge/src/lib/stores/arrangement.svelte.ts` | **modified**: adds `mix`/`master` fields, the non-seeding `peekOverlapParams`, the in-place `clearOverlapParams`, and the `renderSeed` hook `addClip` seeds a new clip's `render` from (T3; critic follow-up #4) |
| `latent-forge/src/ui/modules/MasterChain.svelte` | **modified**: LATCH HEAD + GAIN + NORMALISE, replacing M1's stub (T4) |
| `latent-forge/src/ui/mix/MixSignalPath.svelte` | the MIX + SIGNAL PATH tab (T5) |
| `latent-forge/src/ui/shell/BottomPane.svelte` | **modified**: mounts `MixSignalPath` into the `mix` tab body (T5) |
| `latent-forge/tests/chains.spec.ts` | Playwright, Writer A's half (T5) |
| `latent-forge/src/ui/modules/Files.svelte` | **modified**: adds the two missing HELP ids only — already a full implementation, not a stub (T6) |
| `latent-forge/src/ui/modules/OverlapInpaint.svelte` | **modified**: crossfade curve, CHROMA CROSSFADE, LOCAL STEPS/CFG, the button, replacing M1's stub (T7) |
| `latent-forge/src/lib/forge/overlapLabel.ts` | the OVERLAP-INPAINT info line's label logic (T7) |
| `latent-forge/src/lib/forge/convertProjectV1.ts` | the v1→v2 converter (T8) |
| `latent-forge/src/lib/forge/projectSerializer.svelte.ts` | `ProjectV2` ⇄ live-store (de)serialisation via `$state.snapshot` (a rune, hence `.svelte.ts`), and `validateProjectV2`, the whole-shape check run before any store is touched (T9) |
| `latent-forge/src/lib/forge/sessionController.svelte.ts` | `SessionController`: the ONE load/import/save sequence (Task 9's numbered order), the session name as `$state`, the autosave it arms, chained PUTs per session name, and MASTER PRESET recall/save (T9) |
| `latent-forge/src/lib/forge/sessionName.ts` | session-name validation/prompt logic (T9) |
| `latent-forge/src/lib/forge/autosave.ts` | the 2 s debounce, and the snapshot-gated session autosave that never writes before a load or an explicit SAVE (T9) |
| `latent-forge/src/ui/shell/TopBar.svelte` | **modified**: real SESSION load/save with an `unsaved` option (the select keeps the committed name until a load succeeds), a `loading <name>…` note with SAVE disabled mid-load, IMPORT (v1/v2 project file), MASTER PRESET load/save (that select also snaps back until a recall applies), M1 T15's temporary SAVE/LOAD buttons removed (T9) |
| `latent-forge/src/ui/shell/__tests__/topBar.test.ts` | **modified** (M1 T10's file): its "SAVE disabled until M7" assertion flips (T9) |
| `latent-forge/src/App.svelte` | **modified**: hands session load/save/import and master preset recall/save to `SessionController`, the autosave `$effect`, M1's `sessions[0]` auto-select removed, `settings.attach(arrangement.settingsSource)` — M4's seam, wired in production for the first time — and `arrangement.renderSeed = () => cloneRenderSettings(settings.defaults)` (T9; critic follow-up #4) |
| `latent-forge/src/ui/shell/RightPaneModules.svelte` | **modified**: live `litModules` snapshot (including `sampling`), `<AdvancedSampling latch=… a2a=…>` with registry-known slots only (T9) |
| `latent-forge/src/lib/forge/__tests__/recordedContract.test.ts` | **new, T10**: one contract test per route this milestone touches that M2 T15 records — `/info`, `/models` (adapters, FiLM control adapters), `/slots`, `/forge/files`, and the session and preset GETs — against the RECORDED fixture (skipped, with the reason, until recorded or while the recording is empty) |
| `latent-forge/src/ui/prompt/PromptSigmaTab.svelte` | **modified** (M4 T10's file): passes the active lane's LatCH slots to `<SigmaColumn slots=…>`, and the selected clip's `lane`/`a2a`/`clipHasLatent`/`onA2AToggle` (M5 `ensureA2A`)/`onNoise` to TargetBar — a passed prop still wins (T9; critic follow-up #2, tested in `src/ui/prompt/__tests__/promptSigmaTabClip.test.ts`) |
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
| 1 `latch.ts` (`chainRequest`) | 15 | 6 FILES HELP ids | 8 |
| 2 `LaneChain.svelte` + `modulePresets` + `models` | 29 (6 + 3 + 20) | 7 `OverlapInpaint.svelte` | 16 (8 + 8) |
| 3 `mixMath`/`signalPath`/arrangement | 20 (6 + 10 + 4) | 8 v1→v2 converter | 13 |
| 4 `MasterChain.svelte` | 6 | 9 sessions/preset/autosave/wiring | 51 (4 + 8 + 9 + 16 + 2 + 7 + 4 + 1) |
| 5 `MixSignalPath.svelte` + Playwright | 8 (+ 4 Playwright) | 10 Playwright + contract tests + self-review | 9 `it.skipIf` (+ 6 Playwright) |

**175 `it()` blocks across all ten tasks (166 `it(` + 9 `it.skipIf(`), plus 10 Playwright
`test()`s (4 in `tests/chains.spec.ts`, 6 in `tests/sessionsFilesOverlap.spec.ts`) — 185 total.**
(Before critic pass 1: 115 + 9 = 124; before critic pass 2: 132 + 10 = 142; before critic pass 3:
147 + 10 = 157; before the reconcile pass: 158 + 10 = 168; before its critic follow-up: 164 + 10 =
174.) Counted mechanically after the critic follow-up: `it(` and `it.skipIf(` at exactly two-space
indent per `### Task N` section, and top-level `test(` per task; every task's `Tests N passed (N)`
gate matches. Task 10's 9 are `it.skipIf` contract tests, reported as skipped until M2 T15 has
recorded their fixtures, and while a recording is empty. M1's `strings.test.ts`
total goes 87 → **112** across Tasks 2, 4, 5, 6 and 9 (passes 2 and 3 added no HELP string).

**Critic pass 1 applied (2026-09-24) — see "Critic pass 1" below.** 31 findings, 12 blocking, all 31
applied after each was checked against its cited source. **Critic pass 2 applied (2026-09-25) — see
"Critic pass 2" below.** 14 findings, 2 blocking (both data-loss paths in session load/import), all
14 applied. **Critic pass 3 applied (2026-09-25) — see "Critic pass 3" below.** 12 findings, all in
Task 9, 1 blocking; all 12 applied. Every pass has found its blocking bug in code the previous fix
round had just added, so the pass-3 additions (the rebuild chain, the PUT chain, the prompts) are
where a fourth look would start. **Reconcile pass applied (2026-09-25) — see "Reconcile pass
2026-09-25" below:** WINTERMUTE's contract answers, and the M1/M4/M5 defects fixed at source. **Its
critic follow-up applied (2026-09-25)** — 12 findings (`docs/latent-forge/RECONCILE_CRITIC_FINDINGS.md`),
all 12 applied with WINTERMUTE's answers of 2026-09-25 21:05 (authoritative for #1, #5, #7 and the
new M2 T15 fixtures), see "Critic follow-up" under the reconcile note. Open questions 35 and 36 are
resolved; one item stays open — the explicit later task that removes the legacy modules (Open
questions 37). The follow-up's own additions (the stage-lock release, the clip-prop wiring,
`renderSeed`, FiLM's `control_adapter` filter, the five new contract tests and the empty-recording
skips) have had no critic.

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
    `1 failed, 16 passed`, the failure being M1's own `each bottom tab opens` (`17 passed` since the
    reconcile pass fixed that test at source).
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

### Critic pass 2 (2026-09-24 findings, applied 2026-09-25)

A second, independent read-only critic against the plan at commit 11560e7
(`docs/latent-forge/M7_CRITIC2_FINDINGS.md`), which compiled the four new components on Svelte
5.57.0 and runtime-checked the `peekOverlapParams` pattern. **14 findings, 2 blocking, 2
unconfirmed.** The fix agent re-checked each against its cited source (M1/M4/M5 plan lines, the spec,
`sa3-studio/src/lib/types.ts` and `store.svelte.ts`, `eval/explorer_render_server.py`); all 14 held.
The blocking pair and #3, #5, #6, #7 all touch one path, so they were fixed together as **one
load/import sequence**, stated once as a numbered order in Task 9's WHY and implemented in one new,
unit-tested class (`SessionController`) instead of `App.svelte` closures (Global Constraint #10).

**Blocking.**
1. **IMPORT could autosave a half-imported project over the loaded session.** `applyProject` ran
   before `session` was cleared, with no validation of a v2 file. Now: a v2 object passes
   `validateProjectV2` (every field `applyProject` and its readers dereference) before any store is
   touched; autosave is disarmed and an IMPORT's `session` cleared before `applyProject`.
   `sessionController.test.ts` proves a v2 file missing its last-read field PUTs nothing, leaves
   `session` and the stores alone, and keeps the old session armed.
2. **`loadSession` renamed the session before the content arrived.** Now the previous name stays
   (and stays armed) until apply, rebuild and arm succeed; a fetch/validation failure changes
   nothing; SAVE is refused while a load is in flight; the TopBar select snaps back to the committed
   name after a pick. Tests: a failed load keeps the previous name and its autosave; a SAVE mid-load
   writes nothing to either name; the select stays on the committed name.

**Non-blocking.**
3. **A failed rebuild rewrote the saved session's backbone, and edits during the rebuild were folded
   into the baseline.** The baseline is now the project as loaded, taken before the rebuild wait; a
   failed rebuild reverts the client stage but pins the session's backbone into what is saved;
   `observe()` runs once after arming. Tested; the defaults choice is Open question 29.
4. **Module-preset selection was shared by all lanes, and recall wrote to whichever lane was active
   when the response arrived.** `presetPicked` is per lane; recall/save capture the lane before the
   await. Two new T2 tests.
5. **A load kept the old selection and old overlap params.** `applyProject` clears the selection
   and calls T3's new `clearOverlapParams()`; OverlapInpaint renders only `{#if overlap && params}`.
   One T3, one T7 and one T9 test.
6. **Stretched previews were not rebuilt on load.** Step 6 schedules M5's `scheduleStretch` per
   loaded clip; tested.
7. **v1 IMPORT forced the BASE stage.** Converted v1 input is applied with `restoreModel: false` and
   never rebuilds; the converter's `backbone` is a documented placeholder. Tested.
8. **M4 and M7 disagreed on an active LatCH slot.** ADVANCED SAMPLING now gets only registry-known
   slots (a new T9 test); `SigmaColumn` keeps raw slots (drawing only) — Open question 28.
9. **The signal-path test title overclaimed.** Retitled; stages 3, 7, 8 and 9 now asserted.
10. **FILM SCALE ignores `/info.film_default.gain`.** Recorded as a known gap, with the reason
    (M1's frozen default, lit dots) — Open question 26, Known incomplete 4.
11. **The converter dropped v1 `audio-file` clips with a `serverPath`.** They now become `path`
    refs; one new T8 test.
12. **T3's import-block edit would have dropped `import type { SnapMode }`.** The step now says
    "extend the first two imports" and shows the third, unchanged.
13. (unconfirmed → confirmed) **The RightPaneModules test relied on `module-dot`,** which only the
    ruled-out label-prop `ModuleShell` emits; no plan pins the `{id, title, lit}` version's dot. The
    test now mocks `ModuleShell` with a probe carrying exactly the Normative props and asserts the
    `lit` value passed — Open question 27.
14. (unconfirmed → decided) **`lora.slot` was saved as if stable.** `ckpt_path` is now the durable
    identity and `slot` a transient resolution: contract-table row, `durableChain`/`modulePresetPayload`
    write `slot: null`, LORA/DORA re-resolves by path — Open question 25.

**Found while applying, not in the critic's list:** a SAVE whose PUT was still in flight when a load
started would have armed its name over the newly loaded stores (now guarded by the load sequence);
a master-preset recall during a load would patch half-replaced stores (now refused while loading);
a load superseded after it applied left stores no session owns (now shown as `unsaved`). Test counts
moved 132 → 147 `it()` (T2 +2, T3 +1, T7 +1, T8 +1, T9 +10); Playwright unchanged at 10.

### Critic pass 3 (2026-09-25)

A third, independent read-only critic, scoped to Task 9 only — `SessionController`, the
load/import/save/autosave paths, TopBar/App wiring and the tests claiming to prove them — against the
plan at commit b2915a8 (`docs/latent-forge/M7_CRITIC3_FINDINGS.md`). **12 findings, 1 blocking, 2
unconfirmed.** The fix agent re-checked each against its source (M1 T10/T15's App blocks, M1's
`restoreUi` and guards, M4's `STAGE_FIELDS`/`setStage`/`confirmStage`, M5's `SNAP_MODES`, the v1
store's own `loadJSON`); all 12 held, both unconfirmed ones confirmed. Every new guard has a test
built on the deferred-promise / fake-timer patterns Task 9 already used; the nine-step order in the
WHY was re-walked and updated (steps 1, 2, 3, 5, 7 and 8 changed in content, not in number).

**Blocking.**
1. **Any body that was not `version: 2` went through the never-failing converter.** A missing,
   string or future version was converted as v1, lost every clip, and was then named, armed and
   autosaved over the real session. Now only `version === 1` is converted; anything else is refused
   at step 3 with nothing touched (the v1 app's own `loadJSON` refuses the same way). One new test.

**Non-blocking.**
2. **Master-preset recall checked `loading` only before its fetch.** It moved into
   `SessionController.recallMasterPreset`: refused mid-load, dropped if the load sequence moved
   during the fetch, and App highlights the name (and the TopBar select snaps back) only once it
   applied. Tested with #12.
3. **Unsaved work was replaced without asking.** A `confirm` dependency: step 3 asks before a load or
   import replaces edited work no session owns (`session` is `""`, or orphaned stores). One test.
4. **SAVE silently overwrote a listed session under a typed name**, and so did master-preset SAVE.
   An `exists` dependency plus `confirm`; `saveMasterPreset` moved into the controller. One test.
5. **A failed autosave was never retried, and PUTs were unordered.** `createSnapshotAutosave` keeps a
   rejected save pending against the last confirmed snapshot (the next change re-queues it, a re-arm
   flushes it); the controller chains PUTs per name and a load of that name waits for them. One
   `autosave.test.ts` test, one controller test.
6. **A superseded load with a failed rebuild left the client claiming its model.** The controller
   tracks the server's stage, serialises rebuilds, compares against the server's stage, and lets
   STAGE follow the server when the latest load ends without committing (also for converted v1
   input and an apply that throws). One test (also #9's orphan case). M4's own `confirmStage`
   racing a load is recorded, not fixed (Known incomplete 7, Open questions 32).
7. **A v1 IMPORT under POST reset `defaults` to BASE values.** `applyProject` with
   `restoreModel: false` overlays the kept stage's `STAGE_FIELDS`; the v1 test asserts `steps`,
   `sampler_type` and `schedule`.
8. **`validateProjectV2` checked less than its docstring.** It now checks every lane, clip, overlap
   entry, mix node and master field, the snap mode against M5's `SNAP_MODES`, and `ui.modules`. One
   new test, including the `ui.modules: "files"` case.
9. **The pass-2 branches were untested.** Three tests: a load superseded then failed (shared with
   #6), a SAVE whose PUT outlives a load's commit, an `applyProject` that throws.
10. (unconfirmed → confirmed) **App's anchors may not exist.** M1 T15's App `<script>` "becomes" a
    block without M1 T10's top-bar state, imports and `loadTopBar`. Step 4 now states App's required
    starting state and says to restore T10's block verbatim if T15 removed it.
11. **Mid-load, the SESSION select named a session the stores did not hold.** The TopBar now shows
    `loading <name>…` and disables SAVE while `loadingName` is set; Global Constraint #10 is reworded
    to what is guaranteed. One TopBar test.
12. (unconfirmed → confirmed) **A master preset could be half-applied, then autosaved.**
    `validateMasterPreset` checks the payload whole before the first write; tested with #2.

**Found while applying, not in the critic's list:** a converted v1 file imported while a superseded
load's rebuild was still running could keep that load's stage whatever the server ended on, and an
`applyProject` that threw after restoring the stage left it unreconciled — both now go through the
same stage reconcile as #6. The mid-load indicator's `class="notice"` has no M1 style rule (M1 T15's
removed span had none either). Test counts moved 147 → 158 `it()` (T9 +11: autosave +1,
projectSerializer +1, sessionController +8, topBarSessions +1); Playwright unchanged at 10.

### Reconcile pass 2026-09-25

FLATLINE's one reconcile pass after WINTERMUTE's contract check (`flatline.wintermute.log`,
2026-09-25 16:20 — authoritative for the server contract) handed the M1/M4/M5 defects back. Each
claim was re-checked against its source first (M8's `parse_chain`/`chain_to_request`, M2 T15's
`record_fixtures.py`, `eval/explorer_render_server.py`, `sa3-studio/src/lib/musictime.ts`, the
M1/M4/M5 plan text). Where W's reply and a source disagreed, the source won: the fixture recorder
is M2 **Task 15**, not Task 12. What changed:

**A — blocking: the lane chain goes to the server as the chain object.** `resolveLatch` (client-side
§5.5 gains, active slots only) is replaced by Task 1's `chainRequest`, which sends exactly
`{latch_on, slots:[s0, s1], hparams:{rho, mu, gamma, n_iter, log_norms}, film_on, film, lora_on,
lora, bungee_on, semitones}`: two slots always, `rho`/`mu` as the raw 0–30 multipliers, an unknown
head rewritten to `"none"` in place, `lora.slot: null`, built key by key because `parse_chain`
400s on unknown keys. No display used the gain math, so it is gone from the client. Task 1 keeps
14 tests (the 8 mapping tests rewritten for the new shape); Open questions 1 resolved; the §5.5
numbers block, Task 2's Interfaces and Task 9's comments follow.

**B — FILM default 1.75** (W's decision): M1 T4's `CHAIN_DEFAULTS.film.gain`, its test, M1 T6's
`handmade-info.json`, Task 2's `/info` mock, the SCALE comment and `HELP.filmScale`. Open questions
26 and Known incomplete 4 resolved.

**C — envelope asymmetry:** M1 T5's `request()` never unwrapped or required `ok`, which is right —
`GET /forge/sessions/{name}` and `GET /forge/presets/{level}/{name}` are raw. M1 now documents and
tests it; this plan's consumers already read both raw (restated in Task 2's and Task 9's
Interfaces). `updated` is epoch seconds: nothing here displays it; App's one write uses seconds.

**D — M1/M4/M5 defects, at source:** M1 — `fetchAdapters` reads `models`; one `ModuleShell` with
its lit dot pinned; `view` everywhere; T12 and T15 say what happens to App (T15 extends it); the
tab test clicks the tab buttons; `.notice` has a rule; the master-preset SAVE assertion stays in M1
with this plan's T9 owning the flip. M4 — `stageLocked`/`stageRebuilding` stop a STAGE rebuild and a
session load overlapping (Task 9's controller holds the lock and refuses a load mid-rebuild). M5 —
Normative table corrected (no Task 7 swap point; `SnapMode` spelling), Playwright selectors match
the markup, and `arrangement.settingsSource` is the M4 seam's source. `settings.attach` and
ADVANCED SAMPLING's `a2a` prop and lit dot land in Task 9 here, because this is the first plan that
depends on both M4 and M5. This plan's workarounds for them (the `ModuleShellProbe`, the "App's
required starting state" restore, the red-test gate, Global Constraints 3-6's "not ours to fix")
are removed; Open questions 2-4, 8, 9, 19-21, 27, 32 resolved.

**E — contract tests against recorded responses:** Task 10 Step 4, `recordedContract.test.ts` —
one test each for `/info`, `/models`, `/slots` and `/forge/files`, loading the **recorded** fixture
through M1 T6's `preferRecorded` and skipping, with the reason in the title, until M2 T15 has
recorded it. M2 records no session or preset route, so those have no test (Open questions 35).

Test counts moved 158 → 164 `it()` (T9 +2: sessionController +1, rightPaneModules +1; T10 +4);
Playwright unchanged at 10. The code this pass added has not been through a critic.

**Critic follow-up (2026-09-25):** 12 findings on this pass
(`docs/latent-forge/RECONCILE_CRITIC_FINDINGS.md`), each re-checked at its source, all applied, with
WINTERMUTE's answers of 21:05 and M2 `ebaf823` authoritative for #1, #5, #7 and the new fixtures.
#1 `fetchFilmCkpts` asks `family=control_adapter` and keeps `control_mode === "scalar"` (there is
no `film` family; the filter is required); tested against M2 T15's `models_control_adapters`, and a
T2 test excludes every non-scalar row (Open questions 36 resolved). #2 TargetBar's clip props wired
in T9 Step 5 (`onA2AToggle` through M5's `ensureA2A`), so M5 T12's A2A test can pass; M5's gate
says `2 failed, 18 passed` before M7 and `1 failed, 19 passed` after. #3 the stage lock is released
only when no load runs and no rebuild the controller started is pending. #4 new clips seed `render`
from `settings.defaults` (T3 `renderSeed`, set by App); OQ 19 states what remains. #5 `wireSlot`
sends `end_pct = max(start_pct, end_pct)` (W; the UI stays two independent sliders). #6 contract
tests skip empty recordings, check `label`; `AdapterEntry.name` optional (M1). #7 M1 T15 keeps the
legacy shells; their removal is a later explicit task (Open questions 37). #8 `.`/`..` refused. #9
stale M1 line cites replaced by quoted text where the finding named them (other M1 line numbers in
this plan predate M1's reconcile lengthening — read them as approximate). #10 M1 T9's store-free
claim lists the real exceptions, and T13's CentreColumn imports `view`. #11 T10 test 6's seeding
claim corrected. #12 the contract file restates `preferRecorded` instead of importing `mock/`. Open
questions 35: M2 T15 now records the session and preset GETs, and T10 tests all four. Counts 164 →
175 `it()` (T1 +1, T2 +1, T3 +1, T9 +3, T10 +5 `it.skipIf`); Playwright unchanged at 10.

---

### Task 1: `src/lib/chains/latch.ts` — the lane-chain request (pure)

**WHY.** A lane's `LaneChain` goes to the server as **the chain object itself**: the server does
spec §5.5's gain mapping (`gain_k = head.default_gain · weight_k`, `rho = ρ·gain_0`, `mu = μ·gain_0`)
server-side, in M8's `parse_chain` → `chain_to_request` (M8 plan lines 331-395; WINTERMUTE,
2026-09-25, `flatline.wintermute.log`). The client therefore sends exactly
`{latch_on, slots:[s0, s1], hparams:{rho, mu, gamma, n_iter, log_norms}, film_on, film, lora_on,
lora, bungee_on, semitones}` and does **no** gain arithmetic: `rho`/`mu` are the 0–30 multipliers the
sliders hold (`parse_chain` range-checks them at 0..30, so a pre-multiplied value either 400s or is
squared), `slots` always has **exactly two** entries (`parse_chain` 400s on any other length), and an
inactive slot stays in place as `head: "none"` or `weight: 0`, which `chain_to_request` drops. The
one thing the client still does is omit a head `/info.latch_heads` does not list, by rewriting that
slot's head to `"none"` in place: `chain_to_request` 400s on an unknown head with weight > 0
(M8 plan lines 377-379), and W keeps it that way on purpose. `lora.slot` is always sent `null` and
`ckpt_path` carries the adapter (Open questions 25; M8 prefers `slot` when set, falls back to
`ckpt_path`). `parse_chain`'s `_merge` 400s on a key `CHAIN_DEFAULTS` does not declare (M8 plan
lines 284-292), so the request is built key by key from the chain, never spread from it.

This used to be `resolveLatch`, which did the §5.5 mapping client-side and sent active slots only;
that wire shape was FLATLINE's own invention (old Open questions 1) and W's check against M8 found
it would 400 on every request with one active slot. **No display in this milestone needs the gain
math**, so it is gone from the client entirely, not kept beside the wire path.

§8.1 S4's idle note (`chain idle — no A2A clip in lane`) depends on knowing whether a chain has
anything on at all. Both are pure functions of data already declared (M1 T3's
`LaneChain`/`LatchSlot`), so they are written and hand-verified before any Svelte component touches
them — Task 2's component only wires fields to `arrangement.lanes[n].chain`. `fetchLatchHeads()`
lives in the same file because it produces the exact `Record<string, LatchHeadInfo>` shape
`chainRequest` consumes, even though — unlike `chainRequest`/`chainIsIdle` — it is not pure (it
calls `forgeApi.info()`); it is co-located for that reason, not because this file stops being "the
pure module." Both Task 2 (LaneChain.svelte) and Task 4 (MasterChain.svelte) import
`fetchLatchHeads` and `LatchHeadInfo` from here so the head list is fetched once per shape, not
redeclared per component. **Nothing in M7 submits a job**: `chainRequest` is what M9 puts under a
lane's `chain` key in the `commit` / `a2a_clip` payload (M8 plan lines 1422, 1980).

**Files:**
- Create: `latent-forge/src/lib/chains/latch.ts`, `latent-forge/src/lib/chains/__tests__/latch.test.ts`

**Interfaces:**
- Consumes from `src/lib/forge/types.ts` (M1 T3, verified at
  `docs/superpowers/plans/2026-09-16-latent-forge-m1-foundation-shell.md:470-485`):
  `interface LatchSlot { head: string; kind: string; value: number; weight: number; start_pct:
  number; end_pct: number }` and `interface LaneChain { latch_on: boolean; slots: [LatchSlot,
  LatchSlot]; hparams: { rho: number; mu: number; gamma: number; n_iter: number; log_norms:
  boolean }; film_on: boolean; film: { ckpt: string | null; gain: number; value: number };
  lora_on: boolean; lora: { ckpt_path: string | null; slot: number | null; strength: number };
  bungee_on: boolean; semitones: number }` — key for key the same as M8's `CHAIN_DEFAULTS`
  (M8 plan lines 265-270).
- Consumes from `src/lib/forge/defaults.ts` (M1 T4, test only): `CHAIN_DEFAULTS` — `film.gain` is
  **1.75**, the server's `/info.film_default.gain` (reconcile pass 2026-09-25, Open questions 26).
- Consumes `forgeApi.info(): Promise<Record<string, unknown>>` from `src/lib/forge/api.ts` (M1 T5,
  verified at m1 plan:1211 — `info: () => getJSON<Record<string, unknown>>("/info")`). `/info` is
  untyped in M1; there is no existing `LatchHeadInfo` type anywhere in M1, so it is declared fresh
  here, restated from spec §5.5/§6.4 and cross-checked against the real fixture
  `docs/latent-forge/contract/fixtures/handmade-info.json`'s `latch_heads` array (m1 plan:2374-2393,
  reproduced in Step 1 below) — **not** from the spec text alone, which never enumerates every
  field. Task 10's recorded-response contract test checks the same fields against the recorded
  `info.json` once M2 T15 has recorded it.
- Produces: `interface LatchHeadInfo`, `interface ChainRequest`,
  `chainRequest(chain: LaneChain, heads: Record<string, LatchHeadInfo>): ChainRequest`,
  `chainIsIdle(chain: LaneChain, hasA2AClip: boolean): boolean`,
  `fetchLatchHeads(): Promise<Record<string, LatchHeadInfo>>`. `ChainRequest` is the server's own
  shape (W 2026-09-25), not a client choice — Open questions 1 is resolved.

- [ ] **Step 1: Write the failing test**

`latent-forge/src/lib/chains/__tests__/latch.test.ts`:

```ts
import { describe, expect, it, vi } from "vitest";
import { chainIsIdle, chainRequest, fetchLatchHeads, type LatchHeadInfo } from "../latch";
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

// M8's CHAIN_DEFAULTS keys (M8 plan lines 265-270). parse_chain's _merge 400s on any other key.
const CHAIN_KEYS = ["bungee_on", "film", "film_on", "hparams", "latch_on", "lora", "lora_on", "semitones", "slots"];

describe("chainRequest — the chain object M8's parse_chain takes (W 2026-09-25)", () => {
  it("sends exactly the chain's nine keys and two slots for an untouched chain, FILM gain 1.75", () => {
    const req = chainRequest(clone(CHAIN_DEFAULTS), HEADS);
    expect(Object.keys(req).sort()).toEqual(CHAIN_KEYS);
    expect(req.slots).toHaveLength(2);
    expect(Object.keys(req.hparams).sort()).toEqual(["gamma", "log_norms", "mu", "n_iter", "rho"]);
    expect(req.film).toEqual({ ckpt: null, gain: 1.75, value: 4.0 });   // the server's own default
    expect(req).toEqual(CHAIN_DEFAULTS);                                 // nothing else changed
  });

  it("sends the chain even while latch_on is false -- the server ignores the slots then", () => {
    const chain = clone(CHAIN_DEFAULTS);
    chain.slots[0] = { head: "rms_energy_bass", kind: "constant", value: -10, weight: 2, start_pct: 0, end_pct: 0.6 };
    const req = chainRequest(chain, HEADS);
    expect(req.latch_on).toBe(false);
    expect(req.slots[0]).toEqual(chain.slots[0]);
  });

  it("keeps an inactive slot in place -- head none or weight 0 is sent, never dropped (one slot is a 400)", () => {
    const chain = clone(CHAIN_DEFAULTS);
    chain.latch_on = true;
    chain.slots[0] = { head: "none", kind: "constant", value: 0, weight: 1, start_pct: 0, end_pct: 0.6 };
    chain.slots[1] = { head: "rms_energy_bass", kind: "constant", value: -10, weight: 0, start_pct: 0, end_pct: 0.6 };
    const req = chainRequest(chain, HEADS);
    expect(req.slots).toHaveLength(2);
    expect(req.slots.map((s) => s.head)).toEqual(["none", "rms_energy_bass"]);
    expect(req.slots[1].weight).toBe(0);   // the server drops it; the client does not
  });

  it("sends rho/mu as the 0..30 multipliers the sliders hold -- no gain is computed client-side", () => {
    // Hand-check: with weight 2 on rms_energy_bass (default_gain 512) the OLD client sent
    // rho = 2 * (512 * 2) = 2048, which parse_chain's 0..30 range check refuses. The server now
    // computes gain_0 = 512 * 2 = 1024 and rho = 2 * 1024 = 2048 itself (M8 chain_to_request; its
    // own test_chain_latch_gains pins the same arithmetic at rho 1.0 -> 1024, mu 0.5 -> 512).
    const chain = clone(CHAIN_DEFAULTS);
    chain.latch_on = true;
    chain.slots[0] = { head: "rms_energy_bass", kind: "constant", value: -10, weight: 2, start_pct: 0, end_pct: 0.6 };
    chain.hparams = { rho: 2, mu: 3, gamma: 0.5, n_iter: 5, log_norms: true };
    const req = chainRequest(chain, HEADS);
    expect(req.hparams).toEqual({ rho: 2, mu: 3, gamma: 0.5, n_iter: 5, log_norms: true });
    expect(req.slots[0]).toEqual({ head: "rms_energy_bass", kind: "constant", value: -10, weight: 2, start_pct: 0, end_pct: 0.6 });
    expect(JSON.stringify(req)).not.toContain('"gain":1024');
    expect(req.slots[0]).not.toHaveProperty("gain");
    expect(req).not.toHaveProperty("rho");   // nested under hparams only
  });

  it("rewrites a head the registry does not list to none, in place -- both slots stay (the server 400s on it)", () => {
    // M8 plan lines 377-379: chain_to_request raises `unknown LatCH head` for a name it does not
    // know with weight > 0, so sending it would fail the whole job.
    const chain = clone(CHAIN_DEFAULTS);
    chain.latch_on = true;
    chain.slots[0] = { head: "deleted_head", kind: "constant", value: 0, weight: 3, start_pct: 0, end_pct: 0.6 };
    chain.slots[1] = { head: "chroma_other", kind: "constant", value: 0.5, weight: 1, start_pct: 0, end_pct: 0.6 };
    const req = chainRequest(chain, HEADS);
    expect(req.slots.map((s) => s.head)).toEqual(["none", "chroma_other"]);
    expect(JSON.stringify(req)).not.toContain("deleted_head");
    expect(req.slots[0].weight).toBe(3);                // only the head changes
    expect(chain.slots[0].head).toBe("deleted_head");   // and the live chain is not touched
  });

  it("never sends start_pct > end_pct: crossed sliders go out as end_pct = start_pct, even with LatCH off (W 2026-09-25; critic follow-up #5)", () => {
    const chain = clone(CHAIN_DEFAULTS);   // latch_on false, head none: parse_chain still checks the order
    expect(chain.latch_on).toBe(false);
    chain.slots[1] = { head: "none", kind: "constant", value: 0, weight: 1, start_pct: 0.8, end_pct: 0.3 };
    const req = chainRequest(chain, HEADS);
    expect(req.slots[1].start_pct).toBe(0.8);                // the handle the user dragged is kept
    expect(req.slots[1].end_pct).toBe(0.8);                  // end = max(start, end)
    expect(req.slots[0]).toEqual(CHAIN_DEFAULTS.slots[0]);   // an ordered slot is sent as it is
    expect(chain.slots[1].end_pct).toBe(0.3);                // and the live chain is not touched
  });

  it("writes lora.slot null and keeps ckpt_path -- the path is the durable identity (Open questions 25)", () => {
    const chain = clone(CHAIN_DEFAULTS);
    chain.lora_on = true;
    chain.lora = { ckpt_path: "/SERVER/lora/x.ckpt", slot: 3, strength: 0.8 };
    expect(chainRequest(chain, HEADS).lora).toEqual({ ckpt_path: "/SERVER/lora/x.ckpt", slot: null, strength: 0.8 });
    expect(chain.lora.slot).toBe(3);
  });

  it("returns plain data: editing the request never reaches the chain, and it survives structuredClone", () => {
    const chain = clone(CHAIN_DEFAULTS);
    const req = chainRequest(chain, HEADS);
    req.slots[0].weight = 9;
    req.hparams.rho = 9;
    req.film.gain = 0;
    expect(chain.slots[0].weight).toBe(1);
    expect(chain.hparams.rho).toBe(1);
    expect(chain.film.gain).toBe(1.75);
    expect(() => structuredClone(req)).not.toThrow();
  });

  it("drops any key the chain type does not declare (parse_chain's _merge 400s on unknown fields)", () => {
    const chain = clone(CHAIN_DEFAULTS) as LaneChain & { stray?: number };
    chain.stray = 1;
    (chain.slots[0] as unknown as Record<string, unknown>).gain = 512;
    (chain.film as unknown as Record<string, unknown>).target = 4;
    const req = chainRequest(chain, HEADS);
    expect(Object.keys(req).sort()).toEqual(CHAIN_KEYS);
    expect(Object.keys(req.slots[0]).sort()).toEqual(["end_pct", "head", "kind", "start_pct", "value", "weight"]);
    expect(Object.keys(req.film).sort()).toEqual(["ckpt", "gain", "value"]);
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
// The lane chain as the server takes it (WINTERMUTE 2026-09-25; M8 parse_chain -> chain_to_request)
// and the SIGNAL PATH idle note (spec §8.1 S4). The §5.5 gain mapping is the SERVER's: nothing
// here multiplies a head gain. Pure except fetchLatchHeads (network).

import { forgeApi } from "../forge/api";
import type { LaneChain, LatchSlot } from "../forge/types";

/**
 * The subset of /info.latch_heads' element shape LANE CHAIN actually reads (M1's own /info typing
 * is `Record<string, unknown>` -- there is no existing LatchHeadInfo anywhere in M1). Restated from
 * spec §5.5/§6.4 and cross-checked field-for-field against
 * docs/latent-forge/contract/fixtures/handmade-info.json's two real entries (Task 10's contract
 * test re-checks them against the RECORDED info.json). The real payload carries more fields (path,
 * out_channels, loss_type, target_kind_default, standardized, schema) -- they exist on the wire but
 * nothing in this milestone reads them, so they are not declared here.
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

/**
 * Exactly M8's CHAIN_DEFAULTS keys (parse_chain's _merge 400s on any other), exactly two slots
 * (parse_chain 400s on any other length), rho/mu as the 0..30 multipliers, lora.slot always null.
 */
export interface ChainRequest {
  latch_on: boolean;
  slots: [LatchSlot, LatchSlot];
  hparams: { rho: number; mu: number; gamma: number; n_iter: number; log_norms: boolean };
  film_on: boolean;
  film: { ckpt: string | null; gain: number; value: number };
  lora_on: boolean;
  lora: { ckpt_path: string | null; slot: null; strength: number };
  bungee_on: boolean;
  semitones: number;
}

/**
 * One slot, key by key. "none" and weight 0 pass through untouched -- chain_to_request drops them
 * (M8 plan line 375). A head the registry does not list becomes "none": chain_to_request 400s on it
 * with weight > 0 (M8 plan lines 377-379). Callers must therefore pass the fetched heads, not `{}`,
 * or every slot is sent as "none". end_pct is clamped up to start_pct: parse_chain 400s on
 * start_pct > end_pct for EVERY slot, before it looks at latch_on or the head (M8 parse_chain), so
 * an idle slot with crossed START%/END% sliders would 400 every render. The start handle is the one
 * the user dragged, so it is kept (WINTERMUTE 2026-09-25; critic follow-up #5).
 */
function wireSlot(slot: LatchSlot, heads: Record<string, LatchHeadInfo>): LatchSlot {
  const known = slot.head === "none" || Object.prototype.hasOwnProperty.call(heads, slot.head);
  return {
    head: known ? slot.head : "none",
    kind: slot.kind,
    value: slot.value,
    weight: slot.weight,
    start_pct: slot.start_pct,
    end_pct: Math.max(slot.start_pct, slot.end_pct),
  };
}

/** The chain object for a job payload's `chain` key (M8 plan lines 1422, 1980). Always a plain copy. */
export function chainRequest(chain: LaneChain, heads: Record<string, LatchHeadInfo>): ChainRequest {
  const hp = chain.hparams;
  return {
    latch_on: chain.latch_on,
    slots: [wireSlot(chain.slots[0], heads), wireSlot(chain.slots[1], heads)],
    hparams: { rho: hp.rho, mu: hp.mu, gamma: hp.gamma, n_iter: hp.n_iter, log_norms: hp.log_norms },
    film_on: chain.film_on,
    film: { ckpt: chain.film.ckpt, gain: chain.film.gain, value: chain.film.value },
    lora_on: chain.lora_on,
    // ckpt_path is the durable identity; a /slots index is transient (Open questions 25).
    lora: { ckpt_path: chain.lora.ckpt_path, slot: null, strength: chain.lora.strength },
    bungee_on: chain.bungee_on,
    semitones: chain.semitones,
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

Expected: `Test Files  1 passed (1)` / `Tests  15 passed (15)` (14, plus critic follow-up #5's
start/end case).

- [ ] **Step 5: Commit**

```bash
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M7 T1: chainRequest (the chain object M8 parse_chain takes: two slots, hparams multipliers, lora.slot null) and chainIsIdle (spec 8.1 S4)"
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
- Consumes from `src/lib/chains/latch.ts` (Task 1): `LatchHeadInfo`, `fetchLatchHeads()`. (This
  component calls neither `chainRequest` nor `chainIsIdle` — `chainRequest` is M9's, at submit
  time, and `chainIsIdle` is Task 3's `signalPath.ts` concern. It writes the chain's raw fields:
  `hparams.rho`/`.mu` are the 0–30 multipliers the server scales itself, never a gain.)
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
  `forgeApi.preset(level, name): Promise<Record<string, unknown>>` — the stored payload **raw**, no
  `{ok}` wrapper (WINTERMUTE 2026-09-25; M1 T5 pins it),
  `forgeApi.savePreset(level, name, payload): Promise<{ok:true}>`,
  `forgeApi.deletePreset(level, name): Promise<{ok:true}>` — called directly by the component for
  each of the four levels (`latch`, `film`, `lora`, `bungee`): `presets` lists, `preset` recalls,
  `savePreset` saves (the SAVE button), `deletePreset` deletes (the DEL button). No intermediate
  client, per the brief. Spec §9.3: "module (`latch`, `film`, `lora`, `bungee`): that module's
  settings object … module recall applies to the active lane."
- Consumes `fetchAdapters(): Promise<AdapterEntry[]>` from `src/lib/forge/models.ts` (M1 T10,
  its `export async function fetchAdapters()` — reads `/models?family=adapter&loadable=1`), and the
  **type** `AdapterEntry` from `src/ui/topbar/modelOptions.ts` (M1 T10's `export interface
  AdapterEntry` — `models.ts` does not re-export it; `name` is optional, so a label reads
  `label || name || path`).
- Produces, from `src/lib/chains/modulePresets.ts`: `type ModuleLevel = "latch" | "film" | "lora" |
  "bungee"`, `MODULE_PRESET_FIELDS: Record<ModuleLevel, readonly (keyof LaneChain)[]>` (`latch` →
  `latch_on, slots, hparams`; `film` → `film_on, film`; `lora` → `lora_on, lora`; `bungee` →
  `bungee_on, semitones` — every level carries its own `*_on` flag, so a recalled preset restores
  on/off as well as values), `modulePresetPayload(chain: LaneChain, level: ModuleLevel):
  Partial<LaneChain>` (a plain deep copy of exactly those fields, safe on a `$state` proxy because
  it copies through JSON rather than `structuredClone`; the `lora` level writes `lora.slot: null`),
  `applyModulePreset(chain: LaneChain, level: ModuleLevel, payload: Record<string, unknown>): void`
  (writes ONLY that level's fields, in place, into the chain it is given — the component passes the
  lane the preset was picked on, captured before the fetch), and `durableChain(chain: LaneChain):
  LaneChain` (a plain JSON copy with `lora.slot` set to `null` — T9's serialiser and master preset
  write every lane's chain through it). **`lora.ckpt_path` is the durable identity, `lora.slot` a
  transient `/slots` resolution** (contract table; critic pass 2 #14): no saved payload carries a
  slot index, and the component re-resolves it by path.
- Produces, added to `src/lib/forge/models.ts`: `fetchFilmCkpts(): Promise<AdapterEntry[]>` (reads
  `/models?family=control_adapter` and keeps only rows with `control_mode === "scalar"` —
  WINTERMUTE 2026-09-25, critic follow-up #1: there is no `film` family; FiLM checkpoints are
  `control_adapter`s, and the filter is **required**, because the server's `_install_film` builds a
  `ScalarAttributeEncoder` and any other control mode would load the wrong encoder; Open questions
  36) and
  `fetchSlots(): Promise<SlotsResponse>` (reads `/slots`, shape verified
  directly against `eval/adapter_slots.py:51-60,156-160` and
  `eval/explorer_render_server.py:839-846,901-905` — `{ok: true, active: number|null, backbone:
  string|null, slots: [{index, path, label, family, cost_gb, strength}], max_slots: number,
  vram_floor_gb: number, free_gb: number}`).
- Produces the component `LaneChain`, and the expression Task 9 Step 5 wires into
  `RightPaneModules.svelte`'s snapshot (M1 T12, the `const snapshot: ModuleStateSnapshot = {` block):
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
  // WINTERMUTE 2026-09-25 (critic follow-up #1): there is no "film" family. FiLM checkpoints are
  // family "control_adapter" with control_mode "scalar" -- the only mode _install_film's
  // ScalarAttributeEncoder can load.
  it("asks /models for the control_adapter family", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ ok: true, models: [{ path: "/SERVER/f.pt", label: "f", control_mode: "scalar" }] }));
    vi.stubGlobal("fetch", fetchMock);
    const out = await fetchFilmCkpts();
    expect(fetchMock.mock.calls[0][0]).toBe("/models?family=control_adapter");
    expect(out.map((m) => m.path)).toEqual(["/SERVER/f.pt"]);
  });

  it("keeps only control_mode 'scalar' rows -- any other mode would load the wrong encoder", async () => {
    vi.stubGlobal("fetch", async () => jsonResponse({ ok: true, models: [
      { path: "/SERVER/film.pt", label: "film", control_mode: "scalar" },
      { path: "/SERVER/melody.pt", label: "melody", control_mode: "melody_contour" },
      { path: "/SERVER/dual.pt", label: "dual", control_mode: "dual_scalar" },   // not "scalar"
      { path: "/SERVER/attr.pt", label: "attr", control_mode: "attribute" },
      { path: "/SERVER/unprobed.pt", label: "unprobed", control_mode: null },
      { path: "/SERVER/missing.pt", label: "missing" },
    ] }));
    const out = await fetchFilmCkpts();
    expect(out.map((m) => m.path)).toEqual(["/SERVER/film.pt"]);
  });

  it("returns an empty list, not a throw, when the server refuses", async () => {
    vi.stubGlobal("fetch", async () => jsonResponse({ ok: false, error: "no film root" }, 200));
    await expect(fetchFilmCkpts()).resolves.toEqual([]);
  });

  // Verified directly against eval/explorer_render_server.py:977-997 (the real /models route):
  // the response key is "models", not "ckpts". M1's fetchAdapters read body.ckpts until the
  // reconcile pass of 2026-09-25 fixed it at source; this function reads `models` too. Task 10's
  // recorded-response contract tests check both against the real server's recordings
  // (models_adapters and models_control_adapters, M2 T15).
  it("reads the 'models' key, not 'ckpts' (the real server's field name)", async () => {
    vi.stubGlobal("fetch", async () => jsonResponse({ ok: true, models: [{ path: "/SERVER/g.pt", label: "g", control_mode: "scalar" }] }));
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

  it("falls back to /info.film_default when the control_adapter/scalar list is empty", async () => {
    // A non-null default ckpt, so the assertion can only pass if the component actually read
    // /info.film_default -- chain.film.ckpt is null by default, so checking the select's value
    // alone would pass with or without the fallback.
    vi.spyOn(forgeApi, "info").mockResolvedValue({ ok: true, film_default: { ckpt: "/SERVER/film_default.ckpt", gain: 1.75 } });
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

  it("the picked preset belongs to the lane it was picked on: another lane shows none, and SAVE there asks for a new name", async () => {
    vi.spyOn(forgeApi, "presets").mockImplementation(async (level) =>
      level === "latch" ? { ok: true, names: ["dub"] } : { ok: true, names: [] });
    vi.spyOn(forgeApi, "preset").mockResolvedValue({ latch_on: true, slots: CHAIN_DEFAULTS.slots, hparams: CHAIN_DEFAULTS.hparams });
    const save = vi.spyOn(forgeApi, "savePreset").mockResolvedValue({ ok: true });
    const prompt = vi.spyOn(window, "prompt").mockReturnValue(null);   // the user cancels the name prompt
    render(LaneChain);
    const select = await screen.findByLabelText("LATCH GUIDANCE preset");
    await screen.findByRole("option", { name: "dub" });
    await fireEvent.change(select, { target: { value: "dub" } });
    await waitFor(() => expect(arrangement.lanes[0].chain.latch_on).toBe(true));
    view.setActiveLane(1);
    await waitFor(() => expect(select).toHaveValue(""));
    expect(screen.getByTestId("latch-preset-delete")).toBeDisabled();   // DEL cannot delete lane 1's non-pick
    await fireEvent.click(screen.getByTestId("latch-preset-save"));
    expect(prompt).toHaveBeenCalledTimes(1);   // a NEW name for lane 2 -- "dub" is never overwritten
    expect(save).not.toHaveBeenCalled();
    view.setActiveLane(0);
    await waitFor(() => expect(select).toHaveValue("dub"));
  });

  it("a recall still in flight when the active lane changes lands in the lane it was picked on", async () => {
    vi.spyOn(forgeApi, "presets").mockImplementation(async (level) =>
      level === "latch" ? { ok: true, names: ["dub"] } : { ok: true, names: [] });
    let answer!: (payload: Record<string, unknown>) => void;
    vi.spyOn(forgeApi, "preset").mockImplementation(() => new Promise((resolve) => (answer = resolve)));
    render(LaneChain);
    const select = await screen.findByLabelText("LATCH GUIDANCE preset");
    await screen.findByRole("option", { name: "dub" });
    await fireEvent.change(select, { target: { value: "dub" } });
    view.setActiveLane(1);   // switch lanes BEFORE the preset arrives
    answer({ latch_on: true, slots: CHAIN_DEFAULTS.slots, hparams: CHAIN_DEFAULTS.hparams });
    await waitFor(() => expect(arrangement.lanes[0].chain.latch_on).toBe(true));
    expect(arrangement.lanes[1].chain.latch_on).toBe(false);
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
import { applyModulePreset, durableChain, MODULE_PRESET_FIELDS, modulePresetPayload } from "../modulePresets";

function clone(c: LaneChain): LaneChain {
  return JSON.parse(JSON.stringify(c)) as LaneChain;
}

describe("module presets (spec 9.3: module level = that module's settings object)", () => {
  it("each level's payload is exactly its own fields, *_on flag included -- and never a resident slot index", () => {
    const chain = clone(CHAIN_DEFAULTS);
    chain.film_on = true;
    chain.semitones = -5;
    chain.lora = { ckpt_path: "/SERVER/a.safetensors", slot: 2, strength: 1 };   // slot 2 is only true NOW
    expect(Object.keys(modulePresetPayload(chain, "latch")).sort()).toEqual(["hparams", "latch_on", "slots"]);
    expect(modulePresetPayload(chain, "film")).toEqual({ film_on: true, film: CHAIN_DEFAULTS.film });
    // ckpt_path is the durable identity; slot is a transient /slots resolution (critic pass 2 #14)
    expect(modulePresetPayload(chain, "lora")).toEqual({ lora_on: false, lora: { ckpt_path: "/SERVER/a.safetensors", slot: null, strength: 1 } });
    expect(durableChain(chain).lora.slot).toBeNull();
    expect(chain.lora.slot).toBe(2);   // the live chain keeps its resolution
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
/** A /models row as the control_adapter query returns it: every model_db row carries
 *  `control_mode` (eval/model_db.py), null when the probe found none. */
type ControlAdapterRow = AdapterEntry & { control_mode?: string | null };

/**
 * Sibling of fetchAdapters, same shape, for FiLM's CKPT select (spec §5.5, §10 X9).
 * There is no "film" family (WINTERMUTE 2026-09-25; critic follow-up #1, M7 Open questions 36):
 * FiLM checkpoints are family "control_adapter" with control_mode "scalar". The filter is
 * REQUIRED, not cosmetic -- the server's _install_film builds a ScalarAttributeEncoder, so a
 * melody_contour / metrical_position / fingerprint / dual_scalar / attribute adapter would load
 * the wrong encoder. /info.film_default.ckpt stays the preselected default (the "" option).
 */
export async function fetchFilmCkpts(): Promise<AdapterEntry[]> {
  const res = await fetch("/models?family=control_adapter");
  const text = await res.text();
  if (!text) return [];
  let body: { ok?: boolean; models?: ControlAdapterRow[] };
  try {
    body = JSON.parse(text) as { ok?: boolean; models?: ControlAdapterRow[] };
  } catch {
    return [];
  }
  if (!res.ok || body.ok === false || !Array.isArray(body.models)) return [];
  return body.models.filter((m) => m.control_mode === "scalar");
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
 *  $state proxy, and structuredClone throws DataCloneError on one (Global Constraint #7).
 *  `lora.slot` is written null: a /slots index names whatever is resident NOW, so only
 *  `lora.ckpt_path` is durable (contract table, critic pass 2 #14). */
export function modulePresetPayload(chain: LaneChain, level: ModuleLevel): Partial<LaneChain> {
  const out: Record<string, unknown> = {};
  for (const k of MODULE_PRESET_FIELDS[level]) out[k] = JSON.parse(JSON.stringify(chain[k]));
  if (level === "lora") (out.lora as LaneChain["lora"]).slot = null;
  return out as Partial<LaneChain>;
}

/** The whole chain as it may be SAVED (session, master preset): a plain copy with the transient
 *  `lora.slot` cleared. The live chain is never modified. */
export function durableChain(chain: LaneChain): LaneChain {
  const copy = JSON.parse(JSON.stringify(chain)) as LaneChain;
  copy.lora.slot = null;
  return copy;
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
    "How hard the FiLM conditioning is applied, scaling the head's own default gain. Safe value: 1.75, the server's default.",
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
  // AdapterEntry is declared in modelOptions.ts; models.ts only `import type`s it (M1 T10).
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
  // The picked preset per LANE, not per component (critic pass 2 #4): recall "dub" on lane 1,
  // switch to lane 2, and SAVE must not overwrite "dub" with lane 2's settings, nor DEL delete a
  // preset lane 2 never used. Indexed by view.activeLane.
  const blankPicked = (): Record<ModuleLevel, string> => ({ latch: "", film: "", lora: "", bungee: "" });
  let presetPicked = $state<Record<ModuleLevel, string>[]>([blankPicked(), blankPicked(), blankPicked(), blankPicked()]);
  const picked = $derived(presetPicked[view.activeLane]);

  const LEVELS: readonly ModuleLevel[] = ["latch", "film", "lora", "bungee"];

  // Every fetch .catch()es: an unmounted root, a dead server or (in jsdom) a relative URL must
  // leave the control empty, not raise an unhandled rejection.
  $effect(() => {
    fetchLatchHeads().then((h) => (heads = h)).catch(() => {});
    fetchFilmCkpts().then((c) => (filmCkpts = c)).catch(() => {});
    // Only the ckpt is read here. SCALE already starts at the server's gain: M1's
    // CHAIN_DEFAULTS.film.gain is 1.75, the same FILM_DEFAULT_GAIN /info.film_default reports
    // (reconcile pass 2026-09-25, Open questions 26), so an untouched lane stays default.
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
  /** ckpt_path is the durable identity; the slot index is resolved from it against what /slots
   *  says is resident NOW (contract table, critic pass 2 #14), never trusted from a saved payload. */
  function slotFor(path: string | null): number | null {
    return path ? (residentSlots.find((s) => s.path === path)?.index ?? null) : null;
  }

  function setLoraModel(path: string) {
    chain.lora.ckpt_path = path || null;
    // a resident /slots entry also records its slot index, so switching to it is the cheap path
    chain.lora.slot = slotFor(chain.lora.ckpt_path);
  }

  // --- module presets (spec §9.3: recall applies to the ACTIVE lane) -----------------------------
  // Every handler captures the lane (and its chain) BEFORE its first await: a response must land
  // in the lane the user acted on, even if view.activeLane changed while it was in flight.
  async function recallModulePreset(level: ModuleLevel, name: string) {
    const lane = view.activeLane;
    const target = arrangement.lanes[lane].chain;
    presetPicked[lane][level] = name;
    if (!name) return;
    try {
      const payload = await forgeApi.preset(level, name);
      applyModulePreset(target, level, payload);
      if (level === "lora") target.lora.slot = slotFor(target.lora.ckpt_path);
    } catch {
      // a preset deleted elsewhere, or a dead server: the lane keeps what it has
    }
  }

  async function saveModulePreset(level: ModuleLevel) {
    const lane = view.activeLane;
    const source = arrangement.lanes[lane].chain;
    let name = presetPicked[lane][level];
    if (!name) {
      const typed = window.prompt(`${level} preset name:`, "");
      if (!typed) return;
      name = typed;
    }
    const payload = modulePresetPayload(source, level);   // taken before the await, from that lane
    try {
      await forgeApi.savePreset(level, name, payload);
      if (!presetNames[level].includes(name)) presetNames[level] = [...presetNames[level], name];
      presetPicked[lane][level] = name;
    } catch {
      // the server's refusal (bad name, disk) is surfaced by forgeApi's own error; nothing to undo
    }
  }

  async function deleteModulePreset(level: ModuleLevel) {
    const name = presetPicked[view.activeLane][level];
    if (!name) return;
    try {
      await forgeApi.deletePreset(level, name);
      presetNames[level] = presetNames[level].filter((n) => n !== name);
      // gone from the server, so gone from every lane that had it picked
      for (const p of presetPicked) if (p[level] === name) p[level] = "";
    } catch {
      // leave the list as it is if the server refused
    }
  }
</script>

{#snippet presetControls(level: ModuleLevel, label: string, help: string)}
  <select aria-label="{label} preset" data-help={help} value={picked[level]}
    onchange={(e) => recallModulePreset(level, (e.currentTarget as HTMLSelectElement).value)}>
    <option value=""></option>
    {#each presetNames[level] as name (name)}<option value={name}>{name}</option>{/each}
  </select>
  <button data-testid="{level}-preset-save" data-help={HELP.modulePresetSave} onclick={() => saveModulePreset(level)}>SAVE</button>
  <button data-testid="{level}-preset-delete" data-help={HELP.modulePresetDelete}
    disabled={!picked[level]} onclick={() => deleteModulePreset(level)}>DEL</button>
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
      <!-- The two sliders are independent; Task 1's wireSlot sends end_pct = max(start_pct, end_pct),
           so crossed sliders never reach parse_chain's start <= end check (critic follow-up #5). -->
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
    {#each filmCkpts as c (c.path)}<option value={c.path}>{c.label || c.name || c.path}</option>{/each}
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
    {#each loraOptions as o (o.path)}<option value={o.path}>{o.label || o.name || o.path}</option>{/each}
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

Expected: `Test Files  3 passed (3)` / `Tests  29 passed (29)` (6 in `models.test.ts` — 5, plus
critic follow-up #1's "only `control_mode` scalar" case — 3 in `modulePresets.test.ts`, 20 in
`LaneChain.component.test.ts`); then M1's own `src/lib/help` suite
passes with the updated total of 100; then `svelte-check found 0 errors and 0 warnings`.

- [ ] **Step 7: Commit**

```bash
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M7 T2: LANE CHAIN (spec 5.5) -- LatCH/FiLM/LoRA/Bungee wired through arrangement.lanes[activeLane].chain in place, module presets recall/SAVE/DEL on the active lane (pick kept per lane, lane captured before each await), lora.slot never saved (ckpt_path is the identity), fetchFilmCkpts/fetchSlots added, jest-dom registered, 13 new HELP strings (total 100)"
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
- Modify: `latent-forge/src/lib/stores/arrangement.svelte.ts` (M5, current file — add two fields,
  one read-only method and one in-place reset, the `renderSeed` hook `addClip` seeds a new clip's
  `render` from (critic follow-up #4), and extend the first two imports; nothing else changes)
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
  ForgeLane, OverlapParams } from "../forge/types"; import type { SnapMode } from "../math/snap";`
  (three statements — M5 plan lines 291-297; this task extends the first two and **keeps the
  third**), its `lanes = $state<ForgeLane[]>
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
  throws `state_unsafe_mutation`, verified on Svelte 5.57.0). And **`clearOverlapParams(): void`**
  — empties the private `overlapStore` in place, for T9's `applyProject` (critic pass 2 #5: a load
  must not let the previous project's overlap edits survive under a key the next project reuses; a
  v1 import keeps its clip ids, so its derived keys can repeat). And **`renderSeed: () =>
  RenderSettings`** (critic follow-up #4) — the one line of M5's `addClip` that wrote
  `render: cloneRenderSettings(BASE_DEFAULTS)` now calls `this.renderSeed()`, which defaults to
  exactly that. App (Task 9 Step 4) sets it to `() => cloneRenderSettings(settings.defaults)`, so a
  clip added under POST starts from POST's `steps`/`sampler_type`/`schedule` (M4's `defaults` "seeds
  new targets", spec §7.2) instead of BASE's — the arrangement cannot import M4 (§12), hence a hook.
  Nothing else in the file changes.

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

  it("with no clips and nothing on, dims every stage except MASTER CHAIN (norm_on defaults true)", () => {
    const stages = buildSignalPath(baseInput());
    expect(stages[0].lit).toBe(false); // S1 DECODE: no crop-ref clips
    expect(stages[1].lit).toBe(false); // S2 BUNGEE
    expect(stages[2].lit).toBe(false); // S3 ENCODE: no clips
    expect(stages[3].lit).toBe(false); // S4 LANE CHAINS
    expect(stages[4].lit).toBe(false); // S5 A2A
    expect(stages[5].lit).toBe(false); // S6 INPAINT OVERLAPS
    expect(stages[6].lit).toBe(false); // S7 MIX: nothing to mix
    expect(stages[7].lit).toBe(true);  // S8 MASTER CHAIN: MASTER_DEFAULT.norm_on is true
    expect(stages[8].lit).toBe(false); // S9 DECODE: nothing to decode
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
import { BASE_DEFAULTS, cloneRenderSettings, MASTER_DEFAULT, MIX_DEFAULT, OVERLAP_DEFAULT, POST_DEFAULTS } from "../../forge/defaults";
import { arrangement } from "../arrangement.svelte";

describe("arrangement.renderSeed (critic follow-up #4)", () => {
  it("seeds a new clip's render from the hook -- BASE until App sets it, a fresh copy per clip", () => {
    const REF = { kind: "crop" as const, crop_id: "seed" };
    const before = arrangement.renderSeed;
    try {
      const base = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: REF });
      expect(base.render).toEqual(BASE_DEFAULTS);                        // M5's behaviour, unchanged by default
      arrangement.renderSeed = () => cloneRenderSettings(POST_DEFAULTS);   // what App's settings.defaults is under POST
      const a = arrangement.addClip({ lane: 0, startSec: 8, durSec: 4, audio: REF });
      const b = arrangement.addClip({ lane: 1, startSec: 0, durSec: 4, audio: REF });
      expect(a.render).toEqual(POST_DEFAULTS);
      expect(a.render.schedule).not.toBe(b.render.schedule);            // never a shared object
      expect(base.render).toEqual(BASE_DEFAULTS);                        // an existing clip is not re-seeded
    } finally {
      arrangement.renderSeed = before;
      arrangement.clips.splice(0, arrangement.clips.length);
    }
  });
});

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

  it("clearOverlapParams drops every seeded entry, in place, so peek is back to an unstored default", () => {
    const key = "clear-a-clear-b";
    arrangement.setOverlapParams(key, { steps: 40 });
    expect(arrangement.peekOverlapParams(key)).toBe(arrangement.peekOverlapParams(key)); // seeded: one live object
    arrangement.clearOverlapParams();
    expect(arrangement.peekOverlapParams(key).steps).toBe(OVERLAP_DEFAULT.steps);
    expect(arrangement.peekOverlapParams(key)).not.toBe(arrangement.peekOverlapParams(key)); // unstored again
  });
});
```

- [ ] **Step 2: Run it, expect failure**

```bash
cd latent-forge && npx vitest run src/lib/mix/__tests__/mixMath.test.ts src/lib/mix/__tests__/signalPath.test.ts src/lib/stores/__tests__/arrangementMixMaster.test.ts
```

Expected: `Failed to resolve import "../mixMath"` and `"../signalPath"`; `arrangementMixMaster.test.ts`
fails on `arrangement.mix` being `undefined`, `peekOverlapParams`/`clearOverlapParams` not
being functions, and a POST-seeded clip still getting BASE's `render` (no `renderSeed` yet).

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

Modify `latent-forge/src/lib/stores/arrangement.svelte.ts` — **extend the first two import
statements** (the `../forge/defaults` value import and the `../forge/types` type import) to the
form below, **keep the third, `import type { SnapMode } from "../math/snap";`, exactly as it is**
(M5 plan line 297 — `snap = $state<SnapMode>(…)` needs it; replacing the whole block with only these
two statements fails `svelte-check`), and add three fields and two methods to `ArrangementStore`
plus the one-line `renderSeed` call in `addClip`; nothing else in the file changes:

```ts
import {
  A2A_ENVELOPE_DEFAULT, BASE_DEFAULTS, CHAIN_DEFAULTS, cloneRenderSettings, MASTER_DEFAULT,
  MIX_DEFAULT, OVERLAP_DEFAULT,
} from "../forge/defaults";
import type {
  AudioRef, Envelope, ForgeClip, ForgeLane, MasterChain, MixSpec, OverlapParams, RenderSettings,
} from "../forge/types";
import type { SnapMode } from "../math/snap";   // unchanged -- M5's own third import
```

and, inside `class ArrangementStore`, immediately after `lanes = $state<ForgeLane[]>(defaultLanes());`:

```ts
  /** M7 — spec §4.5/§4.6.5. Seeded from M1's own frozen defaults; nothing else about the store changes. */
  mix = $state<MixSpec>(structuredClone(MIX_DEFAULT));
  master = $state<MasterChain>(structuredClone(MASTER_DEFAULT));

  /**
   * M7 (critic follow-up #4) -- what a NEW clip's `render` starts from. BASE until App sets it to
   * `() => cloneRenderSettings(settings.defaults)` (Task 9 Step 4): M4's defaults "seed new targets"
   * (spec §7.2) and follow STAGE, but this store may not import M4 (§12). A plain field, not $state:
   * it is read only inside addClip. Must return a fresh object every call.
   */
  renderSeed: () => RenderSettings = () => cloneRenderSettings(BASE_DEFAULTS);
```

and, in M5's `addClip`, change the one line

```ts
      render: cloneRenderSettings(BASE_DEFAULTS),
```

to

```ts
      render: this.renderSeed(),
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

  /**
   * M7 -- empties overlapStore IN PLACE (the field is private, and M5 has no way to drop an entry).
   * T9's applyProject calls it before writing a loaded project's overlaps: without it a previous
   * project's edits survive under any key the next one reuses (a v1 import keeps its clip ids).
   */
  clearOverlapParams(): void {
    for (const k of Object.keys(this.overlapStore)) delete this.overlapStore[k];
  }
```

- [ ] **Step 4: Run it, expect pass**

```bash
cd latent-forge && npx vitest run src/lib/mix/__tests__/mixMath.test.ts src/lib/mix/__tests__/signalPath.test.ts src/lib/stores/__tests__/arrangementMixMaster.test.ts
```

Expected: `Test Files  3 passed (3)` / `Tests  20 passed (20)` (6 in `mixMath.test.ts`, 10 in
`signalPath.test.ts`, 4 in `arrangementMixMaster.test.ts` — the `renderSeed` case is critic
follow-up #4).

Then confirm the modified store file still passes its own, pre-existing suite untouched (this
task's own diff is additive except `addClip`'s one `render` line, whose default seed is exactly the
line it replaces — so no specific count is
asserted here beyond "still green"; M5's own plan is the source of truth for that file's count):

```bash
cd latent-forge && npx vitest run src/lib/stores/__tests__/arrangement.test.ts && npm run check
```

Expected: every existing test in `arrangement.test.ts` passes unchanged, then `svelte-check found
0 errors and 0 warnings`.

- [ ] **Step 5: Commit**

```bash
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M7 T3: mixMath (node tree wiring, quad normalisation) and signalPath (the nine spec 8.1 stages, live), arrangement.mix/.master fields seeded from M1's frozen defaults, non-seeding peekOverlapParams for derived/template reads, in-place clearOverlapParams for T9's load"
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
// (data-testid="bottom-tab-<id>" to click, tests/sampling.spec.ts:beforeEach) -- and, since the
// reconcile pass of 2026-09-25, the one M1's own layout spec uses too (Global Constraint #5).

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

1. ~~**`LatchRequest`'s shape is not pre-named anywhere.**~~ **Resolved by WINTERMUTE
   (2026-09-25):** M8 keys it differently — the server takes the chain object and does §5.5's
   mapping itself. Task 1 now ships `chainRequest` (two slots, nested `hparams` multipliers,
   `lora.slot: null`); see the merged Open questions 1 at the end of the plan.

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

4. **[Reconcile pass 2026-09-25: fixed at source — M1 T10 now reads `models`, its mock test seeds the real envelope, and T10's contract test checks it against the recording.]** **`fetchAdapters()`'s real server mismatch, verified, not mine to fix.** M1's `fetchAdapters()`
   (`src/lib/forge/models.ts`) reads `body.ckpts`, but the real `/models` route
   (`eval/explorer_render_server.py:977-997`) returns `{"ok", "count", "models", "stale_root_ids"}`
   — the array is under `models`, not `ckpts`. Against the real server this makes `fetchAdapters()`
   always resolve to `[]`. M1's own test mocks `{ok:true, ckpts:[...]}`, so the test is
   self-consistently green and never catches this. My new `fetchFilmCkpts()` deliberately reads
   `body.models` (verified correct) rather than copying the bug forward. This is an M1-internal
   defect like the two the brief already named (`ModuleShell`, `viewStore`/`view`) — worth a line
   in WINTERMUTE's DM alongside them, and a real, if small, fix for whoever next touches M1.

5. **[Reconcile pass 2026-09-25: fixed at source — M1's tab test clicks `[data-testid="bottom-tab-<id>"]` and checks the body's `data-tab`.]** **M1 T14's own Playwright layout spec has a third, previously-unflagged internal defect.**
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
    `/info.latch_heads` into the exact `Record<string, LatchHeadInfo>` `chainRequest` consumes, and
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

13. **[Reconcile pass 2026-09-25: both fixed at source in M1 T9-T11; the dot is pinned too.]** **`ModuleShell`'s duplicate declaration and the `viewStore`/`view` mismatch**, both already
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

  it("renders nothing for a selected overlap key that no longer exists (a load or a clip move removed it)", () => {
    // peekOverlapParams never returns null, so `{#if params}` alone would render a body for a
    // stale key; the body is gated on the overlap itself too (critic pass 2 #5).
    view.select({ kind: "overlap", key: "gone-a-gone-b" });
    const { container, queryByTestId } = render(OverlapInpaint);
    expect(queryByTestId("inpaint-overlap-button")).toBeNull();
    expect(container.querySelector(".overlap")).toBeNull();
  });
});
```

- [ ] **Step 2: Run them, expect failure**

```bash
cd /home/kim/Projects/sa3-studio-review/latent-forge && npx vitest run src/lib/forge/__tests__/overlapLabel.test.ts src/ui/modules/__tests__/OverlapInpaint.test.ts
```

Expected: `Failed to resolve import "../overlapLabel"`, and every `OverlapInpaint.test.ts` case
but the last fails against the M1 stub's `<p class="pending">` markup (no `data-testid`s exist yet).
The last one — a stale overlap key renders nothing — already passes against the stub, which renders
no `.overlap`; it is the regression guard for Step 4's `{#if overlap && params}` gate. Summary:
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

<!-- Both, not `params` alone: peekOverlapParams never returns null, so a selected key that no
     longer names an overlap (after a load or a clip move) would otherwise still render a body. -->
{#if overlap && params}
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

Expected: `Test Files  2 passed (2)` / `Tests  16 passed (16)` (8 in `overlapLabel.test.ts`, 8 in
`OverlapInpaint.test.ts`).

- [ ] **Step 6: Commit**

```bash
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M7 T7: OVERLAP -- INPAINT module (spec 4.6.1) -- info line, 64px crossfade curve reusing M5's EnvelopeEditor, chroma crossfade + local STEPS/CFG override through arrangement.peekOverlapParams/setOverlapParams, body gated on the overlap existing, INPAINT OVERLAP button a no-op until M9"
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
   **Except when v1 recorded where the server has the audio** (critic pass 2 #11): a v1 `Clip` can
   carry `serverPath` (`sa3-studio/src/lib/types.ts:150-158` — set from a job's returned files or
   typed in by hand), and `{kind: "path", path}` is a valid v2 `AudioRef`. **Decision:** `crop` and
   `render` sources convert cleanly (their identifiers — `cropId`, `jobId`/`filename` — are exactly
   `AudioRef`'s own `crop`/`render` shapes); any other source with a non-empty `serverPath` becomes
   a `path` ref; only a clip with neither is dropped, rather than given a synthetic/invalid
   `AudioRef`.

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

describe("clips: crop and render sources convert; empty and audio-file are dropped unless v1 recorded a serverPath", () => {
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

  it("drops empty and audio-file clips with no serverPath, since v1 itself never durably saved their audio", () => {
    const out = convertProjectV1({
      ...v1Base(),
      clips: [
        { id: "e", laneId: "drums", startSec: 0, durationSec: 4, offsetSec: 0, source: { kind: "empty" }, latentState: "none", render: { op: "generate", prompt: "", steps: 24, cfgScale: 6, seed: -1, noiseLevel: 0.4 } },
        { id: "f", laneId: "drums", startSec: 4, durationSec: 4, offsetSec: 0, source: { kind: "audio-file", name: "x.wav", url: "blob:x" }, latentState: "none", render: { op: "generate", prompt: "", steps: 24, cfgScale: 6, seed: -1, noiseLevel: 0.4 } },
      ],
    });
    expect(out.clips).toHaveLength(0);
  });

  it("keeps an audio-file clip whose v1 serverPath says where the server has its audio, as a path ref", () => {
    const out = convertProjectV1({
      ...v1Base(),
      clips: [{
        id: "g", laneId: "other", startSec: 2, durationSec: 4, offsetSec: 0,
        source: { kind: "audio-file", name: "take.wav", url: "blob:y" },
        serverPath: "/SERVER/renders/take.wav",   // types.ts:150-158 -- a job's file, or typed in
        latentState: "none", render: { op: "generate", prompt: "", steps: 24, cfgScale: 6, seed: -1, noiseLevel: 0.4 },
      }],
    });
    expect(out.clips).toHaveLength(1);
    expect(out.clips[0].audio).toEqual({ kind: "path", path: "/SERVER/renders/take.wav" });
    expect(out.clips[0].lane).toBe(2);
    expect(JSON.stringify(out)).not.toContain("blob:");
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
// clip whose source is "empty" or "audio-file" AND which has no `serverPath`,
// which has no representable AudioRef (v1 itself never durably saved it -- its
// own toJSON() drops previewUrl for audio-file clips and loadJSON() already
// flags them for manual relink). With a serverPath it becomes a `path` ref.
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
    // "empty" and "audio-file" have no v2 AudioRef of their own -- see this task's WHY and
    // serverPathRef below.
    default:
      return null;
  }
}

/** v1's `serverPath` (types.ts:150-158): an absolute path ON THE SERVER, from a job's returned
 *  files or typed in by hand -- exactly v2's `{kind: "path"}` ref. */
function serverPathRef(clip: Record<string, unknown>): AudioRef | null {
  return typeof clip.serverPath === "string" && clip.serverPath !== ""
    ? { kind: "path", path: clip.serverPath }
    : null;
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
    const audio = convertAudio(c.source) ?? serverPathRef(c);
    if (!audio) continue;   // "empty" / "audio-file" with no serverPath, or malformed -- dropped, see WHY
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
    // v1 records no backbone (and no ckpt). This value only fills the required field -- it is NOT
    // a stage request: Task 9's loader applies converted v1 input with `restoreModel: false`, so
    // the current stage and ckpt stay, no model rebuild runs, and a later SAVE records whatever
    // backbone is actually loaded (critic pass 2 #7 -- emitting a fixed value here used to flip a
    // POST session to BASE and rebuild the server model on every v1 import).
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

Expected: `Tests  13 passed (13)`.

- [ ] **Step 5: Commit**

```bash
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M7 T8: v1 -> v2 project converter, built against the real legacy shape (sa3-studio/src/lib/store.svelte.ts), not the spec's one paragraph -- drops what ProjectV2 structurally cannot represent (per-clip op, empty/audio-file sources without a serverPath) rather than forcing it; serverPath becomes a path ref"
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
`ModuleShell`/`viewStore` defects the brief already flags. (Reconcile pass 2026-09-25: M5's
Normative table now says no M5 task is the swap point; the rewire is still unowned — Open
questions 3.) What I *can* guarantee is that **my own
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
`confirmStage` calls `forgeApi.setBackbone` before `setStage`), a v2 load does the same when the
restored stage differs from the current one: it calls `forgeApi.setBackbone(STAGE_BACKBONE[stage])`,
and on failure puts `settings.stage` back so the client never claims a model the server did not
load — **without letting that revert reach the saved session** (step 8 of the order below). A
converted v1 file restores neither stage nor ckpt: v1 records no model (critic pass 2 #7).
**Note, not fixed here:** `TopBar.svelte`'s own `model`/
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
mockable in a test. Flagged as an authored decision, open for a real name-entry field later. A
typed name that the TopBar already lists asks `confirm` before its PUT replaces that session or
preset (critic pass 3 #4); SAVE under the name already selected is the normal save and asks nothing.
Both prompts are injected into `SessionController` (`prompt`, `confirm`, `exists`), so tests answer
them.

**Abort-listener-ordering, applied where it actually fits.** `forgeApi.session(name)` (M1 T5) has
**no `AbortSignal` parameter** — its whole signature is `(name: string) => Promise<ProjectV2>` — so
there is nothing to abort. The HANDOUT's rule ("an abort listener added after the signal already
fired never runs") is about a promise that never settles; the analogous risk here is a **stale
response applied after a second, newer selection**, which I guard with a monotonic sequence number
captured before the fetch and checked after every await — the same "check first, don't rely on
a callback firing later" discipline, adapted to an API with no signal to check.

**One load/import sequence, stated once (critic pass 2 #1-#3, #5-#7).** The first draft had two
data-loss paths: IMPORT applied the file store by store and only then cleared `session`, so a v2
file missing a later field threw half-way with the old session still armed, and the next autosave
PUT the mixed state over it; and `loadSession` renamed the session before its content arrived, so a
failed fetch left the select on B, the stores on A, A's later edits unsaved, and an explicit SAVE
writing A's content to B. Both now run through **one** class, `SessionController`
(`sessionController.svelte.ts`), in this order — App only calls it:

1. **Bump the load sequence.** Any earlier load or import still in flight is stale from here: it
   stops at its next check and never names or arms anything. `loading` stays true until the latest
   one ends, the TopBar says `loading <name>…` beside the SESSION select (`loadingName`), and **SAVE
   is refused, its button disabled, while it is** — so no SAVE can write the arriving project under
   the previous name, or anything under the target name before it is armed. **M4's stage lock**
   (reconcile pass 2026-09-25, Open questions 32): a load or import is refused outright, before this
   step, while M4's own POST/BASE rebuild is in flight (`settings.stageRebuilding`), and
   `settings.stageLocked` is held for as long as `loading` **and** any rebuild this controller
   started is still running (critic follow-up #3: a superseded load's `setBackbone` can outlive the
   latest load), so M4's MODEL STAGE offers no switch mid-load — a stage rebuild and a load never
   overlap in either order.
2. **Fetch** (session load only), after any PUT to that same name still in flight has landed: PUTs
   are chained per name, so a quick re-load never reads the server before the flush that step 4 of
   the previous load sent (critic pass 3 #5). The stores are untouched and the previous session
   stays named and armed; a failed or superseded fetch changes nothing.
3. **Validate, then ask.** A `version: 2` object goes through `validateProjectV2`, which checks every
   field `applyProject`, `view.restoreUi` and the components it hands data to dereference — down to
   each lane, clip, overlap entry, mix node and master field — and throws naming the first bad one;
   a `version: 1` object goes through `convertProjectV1`; **any other version (missing, `"2"`, `3`)
   is refused**, never converted as if it were v1 (critic pass 3 #1 — v1's own `loadJSON` refuses the
   same way). A malformed or unsupported file or session stops here — nothing is PUT, `session` is
   unchanged, the previous session is still armed. Then, if the stores hold work no session owns
   (`session` is `""` — a fresh tab, or after an IMPORT — or a superseded load orphaned them) and it
   differs from what was last loaded (or the blank launch project), **`confirm` asks before it is
   replaced**: autosave never wrote that work anywhere (critic pass 3 #3). A refusal also stops here,
   with nothing touched.
4. **Disarm autosave** (`arm("", "")`, which flushes the outgoing session's pending save under its
   own name, with its own content — no store has been touched yet). An IMPORT clears `session`
   here; a session load keeps the previous name on screen, beside the `loading` note, until step 9.
5. **Apply** (`applyProject`), which first **clears the selection and every overlap's params**
   (`clearOverlapParams`, T3), then writes the stores; converted v1 input keeps the current stage and
   ckpt (`restoreModel: false`) **and that stage's `STAGE_FIELDS`** (M4: `steps`, `sampler_type`,
   `schedule`) instead of the converter's BASE values (critic pass 3 #7). If apply throws anyway
   (step 3 makes that unreachable for any input it passes), `session` becomes `""`: the stores then
   match no session, so no name may be armed or saved to, and STAGE follows the server (step 8's
   reconcile).
6. **Schedule a stretch per loaded clip** (M5's `scheduleStretch`): `previewAudio` is re-derived on
   load, never read from the file (M5 plan lines 6004-6005).
7. **Snapshot the baseline** — the project as loaded, under its own saved backbone (v2; a converted
   v1 file takes the current one) — *before* the rebuild
   wait, so an edit made during that wait is a change to save, not part of the baseline. It is also
   step 3's "was this edited?" reference from now on.
8. **Bring the model in line.** First wait for any earlier load's rebuild to settle, so the stage
   the server holds is known — the controller tracks it (`serverStage`), and rebuilds never overlap
   (critic pass 3 #6). **v2:** rebuild if the restored stage differs from the **server's** stage (not
   the client's, which a superseded load may have moved). On failure the client stage reverts to the
   server's (M4: never claim a model the server did not load) and the session's own backbone is
   **pinned**: `serializeProject` writes it instead of `settings.backboneId` while the stage stays
   reverted, so the revert never reaches the saved session, and the loaded `defaults` stay exactly as
   saved (logged — Open questions 29). A saved backbone with no stage (`small-music*`) is pinned the
   same way. Changing STAGE drops the pin. **Converted v1:** no rebuild; if a superseded load left
   the client on a stage the server never reached, STAGE follows the server.
9. **Check the sequence, then commit:** name the session (a load) or leave it `unsaved` (an import),
   `arm` with step 7's baseline, and `observe()` once, so an edit made during steps 5-8 autosaves.

A load superseded after step 5 leaves stores that no session owns; if the latest load or import
then ends without committing, `session` becomes `""`, and once every rebuild has settled STAGE
follows the server — so a superseded load whose rebuild failed never leaves the client claiming its
model (critic pass 3 #6). A SAVE whose PUT is still in flight when a load or import starts saves, but
neither names nor arms anything. A failed autosave PUT is not lost: it stays pending, so the next
change re-queues it and step 4's flush retries it (critic pass 3 #5). A MASTER PRESET recall goes
through the controller too: refused while `loading`, dropped if a load started during its fetch, and
validated whole before its first write; the TopBar highlights its name only once it applied (critic
pass 3 #2, #12). The TopBar's SESSION select keeps showing the committed name until step 9 moves it,
so a failed pick never displays the name it failed to load. `sessionController.test.ts` proves the
coupled cases: a malformed v2 IMPORT PUTs nothing and keeps the session; an unsupported version is
refused the same way; a failed load keeps the previous name armed; a SAVE mid-load writes nothing; a
SAVE whose PUT outlives a load names nothing; a failed rebuild saves the loaded backbone plus the
edits made during it; a superseded load whose rebuild fails leaves the timeline `unsaved` and STAGE
on the server's; an apply that throws names nothing; a load schedules one stretch per clip; a v1
IMPORT never touches the stage and takes the stage's sampling fields; unsaved work and existing names
are not replaced without asking; PUTs to one name are ordered; a master-preset recall is whole or
nothing.

**Launch must never overwrite a saved session — M1's auto-select is removed.** M1 T10's
`loadTopBar` does `if (!session && sessions.length > 0) session = sessions[0].name` (M1 T10, that
line verbatim), so `session` is never empty once the list arrives (the mock lists three, M1 plan lines
2489-2493). Two things break on that: spec §9.2's "SESSION select shows `unsaved` until named" can
never be seen, and an autosave keyed on "the current session name" would PUT the blank launch
arrangement over whichever session happens to be listed first, two seconds after the tab opens —
data loss. This task deletes that line, so a fresh tab starts `unsaved`, and — independently, so a
future auto-select cannot reintroduce the bug — autosave only writes to a session that was **armed**
by a successful load or an explicit SAVE (`createSnapshotAutosave` below).

**Autosave tracks the serialised project, not a few references.** Every control in this milestone
mutates in place (Global Constraint #1), so an effect that reads `arrangement.lanes`/`.mix`/`.master`
as bare references plus `clips.length` never re-runs for a chain slot, a mix node, a clip move or a
prompt edit. The effect instead calls `SessionController.observe()`, which computes
`JSON.stringify(serializeProject({name}))`; `$state.snapshot`
reads every field through the proxies, so the effect depends on all of them, and the autosave
compares that string with the last one saved (or loaded), so an effect re-run that changed nothing
saves nothing.

**v1 files still need a way in.** M1 T15's LOAD button — which this task removes along with the v1
`project` store it read — was the only path a v1 JSON file had into the app, and server sessions
are always v2. Spec §9.2 still says "Version 1 files (the existing app) load through a converter",
so this task keeps a minimal replacement: an **IMPORT** button beside the SESSION select opening a
hidden `<input type="file" accept="application/json">`. The chosen file goes through
`convertProjectV1` if it says `version: 1`, through `validateProjectV2` if it says `version: 2`, and
is refused otherwise; the result
is `unsaved` until SAVE names it — an imported file belongs to no server session yet, so autosave
stays off for it. `forgeApi.session()` results take the same three-way branch (`2` validate, `1`
convert, anything else refused — step 3), so a hand-copied v1 file on the server loads too.

**Files:**
- Create: `latent-forge/src/lib/forge/projectSerializer.svelte.ts` (`.svelte.ts` because it calls
  the `$state.snapshot` rune — Global Constraint #7),
  `latent-forge/src/lib/forge/__tests__/projectSerializer.test.ts`
- Create: `latent-forge/src/lib/forge/autosave.ts`,
  `latent-forge/src/lib/forge/__tests__/autosave.test.ts`
- Create: `latent-forge/src/lib/forge/sessionName.ts`,
  `latent-forge/src/lib/forge/__tests__/sessionName.test.ts`
- Create: `latent-forge/src/lib/forge/sessionController.svelte.ts` (`.svelte.ts`: `session`/`loading`
  are `$state` the TopBar reads), `latent-forge/src/lib/forge/__tests__/sessionController.test.ts`
- Modify: `latent-forge/src/ui/shell/TopBar.svelte` — **removes** the M1 T15 `saveProject`/
  `loadProject` functions, their hidden `<input type="file">`, the `notice` state and the
  `data-testid="save-project"`/`"load-project"` buttons (the file loses
  `import { project } from "../../lib/store.svelte"` and every reference to `project`); **adds** an
  `unsaved` option to the SESSION select while no session is named, `data-testid="session-save"`
  and `data-testid="session-import"` (+ its hidden `"session-import-file"` input) beside the SESSION
  select, enables the existing `data-testid="master-preset-save"` button (hard-`disabled` in
  M1 T10) with a `data-help`, and makes the SESSION select snap back to the committed `session`
  prop after a pick (a load that fails or is still in flight never shows the picked name); adds a
  `loadingName` prop (`data-testid="session-loading"` note, session SAVE disabled while it is set)
  and the same snap-back on the MASTER PRESET select (critic pass 3 #2, #11).
- Modify: `latent-forge/src/ui/shell/__tests__/topBar.test.ts` (M1 T10) — its one assertion that
  `master-preset-save` is disabled "until M7 owns presets" flips; M7 is that milestone.
- Modify: `latent-forge/src/App.svelte` — at M1 T15's end state (T15 now extends App, so M1
  T10's top-bar block is there; reconcile pass 2026-09-25), removes M1's `sessions[0]`
  auto-select and its own `session` `$state` (the controller owns it), wires
  `onsession`/`onsessionsave`/`onimportv1` and `onmasterpreset`/`onmasterpresetsave` to
  `SessionController`, starts the autosave `$effect`, and attaches M4's settings seam to M5's
  source (`settings.attach(arrangement.settingsSource)`), and points Task 3's
  `arrangement.renderSeed` at `settings.defaults` (critic follow-up #4).
- Modify: `latent-forge/src/ui/shell/RightPaneModules.svelte` (M1 T12) — the live `litModules`
  snapshot (`sampling: settings.current(view.selection)` included) and `<AdvancedSampling latch=…
  a2a=…>` with registry-known slots only (Step 5).
- Modify: `latent-forge/src/ui/prompt/PromptSigmaTab.svelte` (M4 T10) — `<SigmaColumn slots=…>`,
  and TargetBar's clip props (`lane`, `a2a`, `clipHasLatent`, `onA2AToggle` through M5's
  `ensureA2A`, `onNoise` through `setNoise`) from the selected clip (Step 5; critic follow-up #2).
- Create: `latent-forge/src/ui/prompt/__tests__/promptSigmaTabClip.test.ts` (Step 5)
- Modify: `docs/latent-forge/extract_help.mjs` (append `masterPresetSave`, `sessionSave`,
  `sessionImportV1` to `NEW_STRINGS`); regenerated `latent-forge/src/lib/help/strings.ts`;
  `latent-forge/src/lib/help/__tests__/strings.test.ts` (total 109 → **112**, the final count).
- Create: `latent-forge/src/lib/help/__tests__/sessionHelp.test.ts`
- Create: `latent-forge/src/ui/shell/__tests__/topBarSessions.test.ts`
- Create: `latent-forge/src/ui/shell/__tests__/rightPaneModules.test.ts`

**Interfaces:**
- Consumes `forgeApi.sessions()` (`{ok, sessions:[{name, updated, n_clips}]}` — `updated` is the
  file mtime in epoch **seconds**, a float; nothing in this milestone displays it, and anything
  that ever does formats it client-side as `new Date(updated * 1000)`),
  `forgeApi.session(name): Promise<ProjectV2>` (the stored object **raw** — no `{ok}` wrapper;
  WINTERMUTE 2026-09-25, pinned by M1 T5's test),
  `forgeApi.saveSession(name, project: ProjectV2)` (wrapped `{ok}`; 400 on anything but
  `version: 2`), `forgeApi.presets(level)`,
  `forgeApi.preset(level, name)` (raw, like `session`), `forgeApi.savePreset(level, name, payload)`,
  `forgeApi.setBackbone(id)` from `src/lib/forge/api.ts` (M1 T5, frozen — restated verbatim per
  "an implementing agent sees ONE task").
- Consumes `convertProjectV1(raw: unknown): ProjectV2` from `src/lib/forge/convertProjectV1.ts`
  (this milestone's Task 8).
- Consumes `arrangement` (`bpm, beatsPerBar, snap, lanes, clips, pxPerSec, scrollSec, mix, master,
  overlaps: Overlap[], peekOverlapParams(key), clearOverlapParams(), setOverlapParams(key, patch),
  setBpm, setSnap, setScrollSec, setDetune, setPreviewAudio, moveClip(id, startSec), ensureA2A(id),
  setNoise(id, noise)`, and the never-seeding `settingsSource: {clipSettings(id); overlapSettings(key)}`
  — M4's `TargetSettingsSource`, structurally, added to M5 T1 by the reconcile pass) and the constants
  `MIN_PX_PER_SEC`/`MAX_PX_PER_SEC` from `src/lib/stores/arrangement.svelte.ts` (M5 T1/T10, extended
  by Task 3). **There is no `arrangement.setPxPerSec`** — `applyProject` assigns `pxPerSec`
  directly, clamped the way M5's own `zoomBy` clamps.
- Consumes `view` (`snapshotUi(): UiState`, `restoreUi(ui)`, `appendLog(text, level)`, `selection`,
  `activeLane`, `select`, `clearSelection`, `openModule`, `closeModule`) from
  `src/lib/stores/view.svelte.ts` (M1 T7 — the export is `view`, Global Constraint #3).
- Consumes `settings` (`defaults: RenderSettings`, `stage: ModelStage`, `ckptPath: string | null`,
  getter `backboneId: string`, `current(t: Target): RenderSettings`, `attach(source)`/`detach()`,
  and the stage-lock pair `stageLocked: boolean` — the controller sets it for a whole load/import —
  and `stageRebuilding: boolean` — M4 T9's own rebuild is in flight, so no load may start; both
  added to M4 T1 by the reconcile pass of 2026-09-25), `STAGE_BACKBONE: Record<ModelStage, string>`,
  `STAGE_FIELDS` (`["steps", "sampler_type", "schedule"]`, M4 plan line 365) and
  `type ModelStage` from `src/lib/stores/settings.svelte.ts` (M4 T1, M4 plan lines 332-487).
- Consumes `ProjectV2`, `ForgeLane`, `ForgeClip`, `OverlapParams`, `MixSpec`, `MasterChain`,
  `LaneChain`, `RenderSettings` from `src/lib/forge/types.ts` (M1 T3, M5 T10's `previewAudio`), the
  guards `isAudioRef`, `isEnvelope` from `src/lib/forge/guards.ts` (M1 T3, M1 plan lines 668-699),
  and `SNAP_MODES` from `src/lib/math/snap.ts` (M5 T2, M5 plan line 890).
- Consumes `CHAIN_DEFAULTS`, `BASE_DEFAULTS`, `POST_DEFAULTS`, `cloneRenderSettings` from
  `src/lib/forge/defaults.ts` (M1 T4), and
  `durableChain(chain): LaneChain` from `src/lib/chains/modulePresets.ts` (Task 2 — every saved lane
  chain goes through it, so no `lora.slot` index is ever persisted).
- Consumes `scheduleStretch(clipId: string, onError?): void` from `src/lib/clips/lifecycle.ts` (M5
  T10, M5 plan lines 4977, 5341-5351 — debounced 400 ms, re-derives `previewAudio`).
- Consumes `fetchLatchHeads(): Promise<Record<string, LatchHeadInfo>>` and `type LatchHeadInfo` from
  `src/lib/chains/latch.ts` (Task 1).
- Consumes `litModules`, `MODULE_ORDER`, `moduleTitle`, `type ModuleStateSnapshot` from
  `src/lib/forge/nonDefault.ts` (M1 T12); `AdvancedSampling`'s `latch?: LatchState` and
  `a2a?: {on: boolean; noise: number} | null` props (M4 T11's Produces line —
  `LatchState = {latch_on: boolean; slots: readonly LatchSlot[]}`, M4 T2) and
  `SigmaColumn`'s `slots?: readonly LatchSlot[]` prop (M4 plan line 4076).
- Produces, from `src/lib/forge/sessionName.ts`: `SESSION_NAME_RE = /^[A-Za-z0-9._-]{1,80}$/`
  (spec §6.3, verbatim), `isValidSessionName(name: string): boolean` (the pattern, minus `.` and
  `..`, which the server also refuses — critic follow-up #8).
- Produces, from `src/lib/forge/projectSerializer.svelte.ts`: `serializeProject(opts: {name:
  string; backbone?: string}): ProjectV2` (plain data — every `$state` read goes through
  `$state.snapshot`, every clip's `previewAudio` is written as `null`, every lane chain through
  `durableChain`, overlaps are read with the non-seeding `peekOverlapParams`; `backbone` overrides
  `settings.backboneId` — the controller's pin, step 8), `validateProjectV2(raw: unknown): ProjectV2`
  (throws `Error("not a v2 project: <field> …")` naming the first missing or mistyped field; checks
  every field `applyProject` and its readers dereference, down to each lane, clip, overlap entry, mix
  node, master field, the snap mode and `ui.modules`), `applyProject(project: ProjectV2, opts?:
  {restoreModel?: boolean}): void` (first clears `view` selection and `clearOverlapParams()`; restores
  `settings.stage` from `backbone` and `settings.ckptPath` unless `restoreModel === false`, in which
  case the current stage's `STAGE_FIELDS` overlay the loaded `defaults`; sets every
  clip's `previewAudio` to `null`), `validateMasterPreset(raw: unknown): MasterPresetPayload`
  (throws `Error("not a master preset: <field> …")`; checks every field `applyMasterPreset` writes),
  `type MasterPresetPayload = {lanes: {chain:
  LaneChain}[]; clips: {id: string; lane: 0|1|2|3; start_sec: number; offset_sec: number; dur_sec:
  number; loop: boolean; native_bpm: number|null; detune_cents: number; a2a: ForgeClip["a2a"]}[];
  mix: MixSpec; master: MasterChain; defaults: {schedule: RenderSettings["schedule"]; prompt:
  string}}`, `buildMasterPresetPayload(): MasterPresetPayload`, `applyMasterPreset(payload:
  MasterPresetPayload): void`.
- Produces, from `src/lib/forge/autosave.ts`: `createAutosave(save: () => void, delayMs?: number):
  {trigger(): void; cancel(): void}` (the bare 2 s debounce) and `createSnapshotAutosave(save: (name:
  string, snapshot: string) => Promise<unknown> | void, delayMs?: number): {arm(name: string,
  snapshot: string): void; observe(name: string, snapshot: string): void; cancel(): void}` —
  `observe` never saves until `arm` has named that session (an empty name disarms), saves only a
  snapshot that differs from the last armed/saved one, and `arm`ing a different name first flushes a
  still-pending save under its own, old name; a `save` whose promise rejects keeps that snapshot
  pending against the last confirmed one, so the next `observe` re-queues it and a re-`arm` flushes
  it (critic pass 3 #5).
- Produces, from `src/lib/forge/sessionController.svelte.ts`: `interface SessionDeps {api:
  {session(name: string): Promise<unknown>; saveSession(name: string, project: ProjectV2):
  Promise<unknown>; setBackbone(id: string): Promise<unknown>; preset(level: string, name: string):
  Promise<unknown>; savePreset(level: string, name: string, payload: unknown): Promise<unknown>};
  log(text: string, level?: "info" | "error"): void; prompt(message: string): string | null;
  confirm(message: string): boolean; exists(kind: "session" | "master", name: string): boolean;
  scheduleStretch?: (clipId: string) => void; delayMs?: number}` (`forgeApi` satisfies `api`
  structurally; tests pass fakes) and `class SessionController` — `constructor(deps: SessionDeps)`,
  `session: string`, `loading: boolean` and `loadingName: string` (all `$state`; `settings.stageLocked`
  is held while `loading`, and until a rebuild the controller started has settled), `observe(): void`
  (App's `$effect` body), `loadSession(name: string): Promise<void>` (refused, with a log line, while
  `settings.stageRebuilding`), `importProjectFile(file:
  {name: string; text(): Promise<string>}): Promise<void>` (a `File` satisfies it), `saveSession():
  Promise<string | null>` (the name saved under, or `null`), `recallMasterPreset(name: string):
  Promise<boolean>` (true when applied), `saveMasterPreset(current: string): Promise<string | null>`.
  The order of operations inside is the WHY's numbered list, verbatim.
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
  it("rejects `.` and `..`, which the pattern allows but the server refuses (WINTERMUTE 2026-09-25; critic follow-up #8)", () => {
    expect(isValidSessionName(".")).toBe(false);
    expect(isValidSessionName("..")).toBe(false);
    expect(isValidSessionName("...")).toBe(true);        // only the two path names are special
    expect(isValidSessionName(".hidden")).toBe(true);
  });

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

  it("a failed save is not lost: the next observe re-queues it, and arming another session flushes it (critic pass 3 #5)", async () => {
    vi.useFakeTimers();
    const first = deferred<unknown>();
    const second = deferred<unknown>();
    const save = vi.fn<(name: string, snapshot: string) => Promise<unknown>>()
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise)
      .mockResolvedValue({ ok: true });
    const a = createSnapshotAutosave(save);
    a.arm("take1", "A");
    a.observe("take1", "B");
    vi.advanceTimersByTime(2000);
    first.reject(new Error("503"));
    await first.promise.catch(() => {});   // runs after autosave's own rejection handler
    a.observe("take1", "B");               // the effect re-running on unchanged stores: B never landed
    vi.advanceTimersByTime(2000);
    expect(save).toHaveBeenCalledTimes(2);
    expect(save.mock.calls[1]).toEqual(["take1", "B"]);
    second.reject(new Error("503"));
    await second.promise.catch(() => {});
    a.arm("take2", "Z");                   // the user loads another session: step 4's flush retries B
    expect(save).toHaveBeenCalledTimes(3);
    expect(save.mock.calls[2]).toEqual(["take1", "B"]);
  });
});

function deferred<T>() {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}
```

`latent-forge/src/lib/forge/__tests__/projectSerializer.test.ts`:

```ts
import { beforeEach, describe, expect, it } from "vitest";
import { arrangement } from "../../stores/arrangement.svelte";
import { settings } from "../../stores/settings.svelte";
import { view } from "../../stores/view.svelte";
import { CHAIN_DEFAULTS, MASTER_DEFAULT, MIX_DEFAULT, OVERLAP_DEFAULT } from "../defaults";
import {
  applyMasterPreset, applyProject, buildMasterPresetPayload, serializeProject, validateProjectV2,
} from "../projectSerializer.svelte";
import type { ProjectV2 } from "../types";

beforeEach(() => {
  arrangement.clips.splice(0, arrangement.clips.length);
  for (const lane of arrangement.lanes) lane.chain = structuredClone(CHAIN_DEFAULTS);
  arrangement.clearOverlapParams();
  settings.stage = "BASE";
  view.clearSelection();
  view.restoreUi({ bottomTab: "prompt", modules: ["files", "lane-chain"], sideOpen: true, terminal: "pane" });
});

describe("serializeProject reads the live stores into ProjectV2 (spec §9.2)", () => {
  it("carries meter, snap, viewport, lanes, clips, mix, master, defaults and ui", () => {
    arrangement.addClip({ lane: 0, startSec: 1, durSec: 3, audio: { kind: "crop", crop_id: "X" } });
    arrangement.lanes[0].chain.lora = { ckpt_path: "/SERVER/a.safetensors", slot: 2, strength: 1 };
    const p = serializeProject({ name: "my-session" });
    expect(p.version).toBe(2);
    expect(p.name).toBe("my-session");
    expect(p.meter).toEqual({ bpm: arrangement.bpm, beatsPerBar: arrangement.beatsPerBar });
    expect(p.snap).toBe(arrangement.snap);
    expect(p.view).toEqual({ pxPerSec: arrangement.pxPerSec, scrollSec: arrangement.scrollSec });
    expect(p.lanes).toHaveLength(4);
    // ckpt_path is the durable identity; the resident slot index is never saved (critic pass 2 #14)
    expect(p.lanes[0].chain.lora).toEqual({ ckpt_path: "/SERVER/a.safetensors", slot: null, strength: 1 });
    expect(arrangement.lanes[0].chain.lora.slot).toBe(2);   // the live chain keeps its resolution
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

  it("clears the selection and every previous overlap's params -- nothing from the last project survives", () => {
    arrangement.addClip({ lane: 0, startSec: 0, durSec: 10, audio: { kind: "crop", crop_id: "A" } });
    arrangement.addClip({ lane: 0, startSec: 6, durSec: 10, audio: { kind: "crop", crop_id: "B" } });
    const [ov] = arrangement.overlaps;
    const saved = serializeProject({ name: "same-clips" });
    saved.overlaps = {};   // as a converted v1 file has it: same clip ids, so the same overlap key
    arrangement.setOverlapParams(ov.key, { steps: 40 });   // an edit the loaded project does not have
    view.select({ kind: "overlap", key: ov.key });
    applyProject(saved);
    expect(view.selection).toEqual({ kind: "none" });
    expect(arrangement.overlaps.map((o) => o.key)).toEqual([ov.key]);   // the key is back ...
    expect(arrangement.peekOverlapParams(ov.key).steps).toBe(OVERLAP_DEFAULT.steps);   // ... its old edit is not
  });
});

describe("validateProjectV2 checks a v2 object as a whole, before anything is applied (critic pass 2 #1)", () => {
  it("passes serializeProject's own output, and names the first missing field of anything else", () => {
    const good = JSON.parse(JSON.stringify(serializeProject({ name: "ok" }))) as Record<string, unknown>;
    expect(validateProjectV2(good)).toBe(good);
    for (const field of ["meter", "view", "lanes", "clips", "overlaps", "mix", "master", "defaults", "ui"]) {
      const broken = JSON.parse(JSON.stringify(good)) as Record<string, unknown>;
      delete broken[field];
      expect(() => validateProjectV2(broken)).toThrow(`not a v2 project: ${field}`);
    }
    expect(() => validateProjectV2({ version: 2 })).toThrow("not a v2 project: meter");
    expect(() => validateProjectV2(null)).toThrow("not a v2 project: version");
  });

  it("looks inside every entry, so nothing that passes can throw part-way through applyProject (critic pass 3 #8)", () => {
    arrangement.addClip({ lane: 0, startSec: 0, durSec: 10, audio: { kind: "crop", crop_id: "A" } });
    arrangement.addClip({ lane: 0, startSec: 6, durSec: 10, audio: { kind: "crop", crop_id: "B" } });
    const [ov] = arrangement.overlaps;
    arrangement.setOverlapParams(ov.key, { steps: 40 });
    const good = JSON.parse(JSON.stringify(serializeProject({ name: "ok" }))) as ProjectV2;
    expect(validateProjectV2(good)).toBe(good);
    const broken = (edit: (p: Record<string, any>) => void) => {
      const p = JSON.parse(JSON.stringify(good)) as Record<string, any>;
      edit(p);
      return p;
    };
    // M1's restoreUi calls .filter on it -- the LAST line of applyProject, after every store is written
    expect(() => validateProjectV2(broken((p) => { p.ui.modules = "files"; }))).toThrow("not a v2 project: ui");
    expect(() => validateProjectV2(broken((p) => { p.snap = "wobbly"; }))).toThrow("not a v2 project: snap");
    expect(() => validateProjectV2(broken((p) => { delete p.lanes[2].gain; }))).toThrow("not a v2 project: lanes[2]");
    expect(() => validateProjectV2(broken((p) => { p.lanes[1].chain.slots[0] = null; }))).toThrow("not a v2 project: lanes[1].chain");
    expect(() => validateProjectV2(broken((p) => { delete p.clips[1].history; }))).toThrow("not a v2 project: clips[1]");
    expect(() => validateProjectV2(broken((p) => { p.clips[0].offset_sec = "0"; }))).toThrow("not a v2 project: clips[0]");
    expect(() => validateProjectV2(broken((p) => { p.overlaps[ov.key].curve = null; }))).toThrow(`not a v2 project: overlaps.${ov.key}`);
    expect(() => validateProjectV2(broken((p) => { delete p.mix.nodes.MX; }))).toThrow("not a v2 project: mix");
    expect(() => validateProjectV2(broken((p) => { p.master.gain = null; }))).toThrow("not a v2 project: master");
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

`latent-forge/src/lib/forge/__tests__/sessionController.test.ts`:

```ts
// The load/import/save order (Task 9's WHY, steps 1-9), proven on the coupled cases. The App
// $effect is simulated by calling ctl.observe() wherever a store edit would re-run it.
import { afterEach, describe, expect, it, vi } from "vitest";
import { CHAIN_DEFAULTS, MASTER_DEFAULT, POST_DEFAULTS } from "../defaults";
import { arrangement } from "../../stores/arrangement.svelte";
import { settings, type ModelStage } from "../../stores/settings.svelte";
import { view } from "../../stores/view.svelte";
import { buildMasterPresetPayload, serializeProject, type MasterPresetPayload } from "../projectSerializer.svelte";
import { SessionController, type SessionDeps } from "../sessionController.svelte";
import type { ProjectV2 } from "../types";

function resetStores() {
  arrangement.clips.splice(0, arrangement.clips.length);
  for (const lane of arrangement.lanes) lane.chain = structuredClone(CHAIN_DEFAULTS);
  arrangement.master = structuredClone(MASTER_DEFAULT);
  settings.stage = "BASE";
  settings.stageLocked = false;
  settings.stageRebuilding = false;
  view.clearSelection();
}

/** Plain data holding one crop clip, built through the real serialiser; the stores are reset
 *  afterwards, so a test starts from a different arrangement than the one it will load. */
function project(name: string, cropId: string, stage: ModelStage = "BASE"): ProjectV2 {
  resetStores();
  settings.stage = stage;
  arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: { kind: "crop", crop_id: cropId } });
  const p = JSON.parse(JSON.stringify(serializeProject({ name }))) as ProjectV2;
  resetStores();
  return p;
}

function deferred<T>() {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

/** `confirmAnswer` answers every yes/no (critic pass 3 #3, #4); `exists` lists nothing unless a test says so. */
function harness(promptAnswer: string | null = null, confirmAnswer = true) {
  const api = {
    session: vi.fn<(name: string) => Promise<unknown>>(),
    saveSession: vi.fn(async (_name: string, _project: ProjectV2): Promise<unknown> => ({ ok: true })),
    setBackbone: vi.fn(async (_id: string): Promise<unknown> => ({ ok: true })),
    preset: vi.fn<(level: string, name: string) => Promise<unknown>>(),
    savePreset: vi.fn(async (_level: string, _name: string, _payload: unknown): Promise<unknown> => ({ ok: true })),
  };
  const deps: SessionDeps = {
    api, log: vi.fn(), prompt: vi.fn(() => promptAnswer), confirm: vi.fn(() => confirmAnswer),
    exists: vi.fn((_kind: "session" | "master", _name: string) => false), scheduleStretch: vi.fn(),
  };
  return { api, deps, ctl: new SessionController(deps) };
}

const loadedCrops = () => arrangement.clips.map((c) => (c.audio as { crop_id: string }).crop_id);
const savedCrops = (p: ProjectV2) => p.clips.map((c) => (c.audio as { crop_id: string }).crop_id);

afterEach(() => {
  vi.useRealTimers();
  resetStores();
});

describe("SessionController: one load/import sequence (critic pass 2 #1-#3, #6, #7)", () => {
  it("IMPORT of a malformed v2 file PUTs nothing and leaves the session, its autosave and the stores alone", async () => {
    vi.useFakeTimers();
    const { api, ctl } = harness();
    const take1 = project("take1", "T1");
    const broken = JSON.parse(JSON.stringify(project("broken", "X"))) as Record<string, unknown>;
    delete broken.ui;   // the LAST field applyProject reads: the old code had written every store by then
    api.session.mockResolvedValue(take1);
    await ctl.loadSession("take1");
    await ctl.importProjectFile({ name: "broken.json", text: async () => JSON.stringify(broken) });
    ctl.observe();                                    // the App effect re-running after the attempt
    vi.advanceTimersByTime(10_000);
    expect(api.saveSession).not.toHaveBeenCalled();   // nothing PUT anywhere
    expect(ctl.session).toBe("take1");                // not cleared: nothing was touched
    expect(loadedCrops()).toEqual(["T1"]);            // not half-applied
    arrangement.lanes[0].chain.latch_on = true;       // and take1 is still armed on take1's content
    ctl.observe();
    vi.advanceTimersByTime(2000);
    expect(api.saveSession).toHaveBeenCalledTimes(1);
    expect(api.saveSession.mock.calls[0][0]).toBe("take1");
    expect(savedCrops(api.saveSession.mock.calls[0][1])).toEqual(["T1"]);
  });

  it("a session that fails to load keeps the previous name, still armed -- nothing renamed, nothing lost", async () => {
    vi.useFakeTimers();
    const { api, ctl } = harness();
    api.session.mockResolvedValueOnce(project("take1", "T1")).mockRejectedValueOnce(new Error("404 take2"));
    await ctl.loadSession("take1");
    await ctl.loadSession("take2");
    expect(ctl.session).toBe("take1");
    expect(ctl.loading).toBe(false);
    expect(loadedCrops()).toEqual(["T1"]);
    arrangement.lanes[0].chain.latch_on = true;       // take1's own edit, after the failed pick
    ctl.observe();
    vi.advanceTimersByTime(2000);
    expect(api.saveSession).toHaveBeenCalledTimes(1);
    expect(api.saveSession.mock.calls[0][0]).toBe("take1");   // autosaved to take1, not dropped
    expect(await ctl.saveSession()).toBe("take1");            // an explicit SAVE goes to take1 too
    expect(api.saveSession.mock.calls[1][0]).toBe("take1");
  });

  it("SAVE while a load is in flight writes nothing -- neither to the session being loaded nor to the previous one", async () => {
    const { api, ctl } = harness();
    const take1 = project("take1", "T1");
    const take2 = project("take2", "T2");
    const pending = deferred<unknown>();
    api.session.mockResolvedValueOnce(take1).mockReturnValueOnce(pending.promise);
    await ctl.loadSession("take1");
    const loading = ctl.loadSession("take2");
    expect(ctl.loading).toBe(true);
    expect(ctl.session).toBe("take1");                // the previous name until take2 is applied AND armed
    expect(ctl.loadingName).toBe("take2");            // ... beside `loading take2…` (critic pass 3 #11)
    expect(await ctl.saveSession()).toBeNull();
    pending.resolve(take2);
    await loading;
    expect(api.saveSession).not.toHaveBeenCalled();
    expect(ctl.session).toBe("take2");
    expect(ctl.loadingName).toBe("");
    expect(loadedCrops()).toEqual(["T2"]);
    expect(await ctl.saveSession()).toBe("take2");    // once armed, SAVE writes take2's content to take2
    expect(savedCrops(api.saveSession.mock.calls[0][1])).toEqual(["T2"]);
  });

  it("a failed model rebuild reverts the client stage but not the session's backbone, and edits made during the rebuild are saved", async () => {
    vi.useFakeTimers();
    const { api, ctl } = harness();
    const post = project("post-set", "P", "POST");
    expect(post.backbone).toBe("medium");
    const rebuild = deferred<unknown>();
    api.session.mockResolvedValue(post);
    api.setBackbone.mockReturnValue(rebuild.promise);
    const loading = ctl.loadSession("post-set");
    await vi.waitFor(() => expect(api.setBackbone).toHaveBeenCalledWith("medium"));
    arrangement.lanes[0].chain.latch_on = true;       // edited while the rebuild is still running
    ctl.observe();                                    // disarmed: nothing is queued yet
    rebuild.reject(new Error("rebuild failed"));
    await loading;
    expect(settings.stage).toBe("BASE");              // M4: never claim a model the server did not load
    expect(ctl.session).toBe("post-set");
    vi.advanceTimersByTime(2000);                     // the mid-rebuild edit was not folded into the baseline
    expect(api.saveSession).toHaveBeenCalledTimes(1);
    const saved = api.saveSession.mock.calls[0][1];
    expect(saved.backbone).toBe("medium");            // the revert did not reach the session
    expect(saved.defaults).toEqual(post.defaults);    // nor did it touch the loaded sampling defaults
    expect(saved.lanes[0].chain.latch_on).toBe(true);
  });

  it("a successful load schedules one stretch per loaded clip, then arms: only a later edit autosaves, under the loaded name", async () => {
    vi.useFakeTimers();
    const { api, deps, ctl } = harness();
    api.session.mockResolvedValue(project("take1", "T1"));
    await ctl.loadSession("take1");
    expect(deps.scheduleStretch).toHaveBeenCalledTimes(1);
    expect(deps.scheduleStretch).toHaveBeenCalledWith(arrangement.clips[0].id);
    ctl.observe();                                    // the effect re-running on what was just loaded
    vi.advanceTimersByTime(5000);
    expect(api.saveSession).not.toHaveBeenCalled();
    arrangement.master.gain = 90;
    ctl.observe();
    vi.advanceTimersByTime(2000);
    expect(api.saveSession).toHaveBeenCalledTimes(1);
    expect(api.saveSession.mock.calls[0][0]).toBe("take1");
    expect(api.saveSession.mock.calls[0][1].master.gain).toBe(90);
  });

  it("a v1 IMPORT keeps the loaded stage (v1 records no backbone) and that stage's sampling fields: no rebuild, and SAVE records the current backbone", async () => {
    const { api, ctl } = harness("from-v1");
    settings.stage = "POST";
    await ctl.importProjectFile({
      name: "old-set.json",
      text: async () => JSON.stringify({ version: 1, meter: { bpm: 100, beatsPerBar: 4 }, lanes: [], clips: [] }),
    });
    expect(arrangement.bpm).toBe(100);                // it did load
    expect(settings.stage).toBe("POST");
    // the converter fills defaults from BASE_DEFAULTS; under POST, M4's STAGE_FIELDS must stay POST's (critic pass 3 #7)
    expect(settings.defaults.steps).toBe(POST_DEFAULTS.steps);
    expect(settings.defaults.sampler_type).toBe(POST_DEFAULTS.sampler_type);
    expect(settings.defaults.schedule).toEqual(POST_DEFAULTS.schedule);
    expect(api.setBackbone).not.toHaveBeenCalled();
    expect(ctl.session).toBe("");                     // unsaved until SAVE names it
    expect(await ctl.saveSession()).toBe("from-v1");
    expect(api.saveSession.mock.calls[0][1].backbone).toBe("medium");
  });
});

describe("SessionController after critic pass 3: versions, prompts, PUT order, rebuild races, master presets", () => {
  it("a session or file whose version is neither 1 nor 2 is refused before anything is touched -- never converted as if it were v1 (#1)", async () => {
    vi.useFakeTimers();
    const { api, ctl } = harness();
    const future = { ...project("take2", "T2"), version: 3 };
    const stringVersion = JSON.stringify({ ...project("x", "X"), version: "2" });
    api.session.mockResolvedValueOnce(project("take1", "T1")).mockResolvedValueOnce(future);
    await ctl.loadSession("take1");
    await ctl.loadSession("take2");
    await ctl.importProjectFile({ name: "string-version.json", text: async () => stringVersion });
    ctl.observe();
    vi.advanceTimersByTime(10_000);
    expect(api.saveSession).not.toHaveBeenCalled();   // nothing PUT: the converter would have emptied take2
    expect(ctl.session).toBe("take1");
    expect(loadedCrops()).toEqual(["T1"]);
    arrangement.master.gain = 90;                     // take1 is still armed on take1's content
    ctl.observe();
    vi.advanceTimersByTime(2000);
    expect(api.saveSession).toHaveBeenCalledTimes(1);
    expect(api.saveSession.mock.calls[0][0]).toBe("take1");
  });

  it("loading or importing over edited work no session owns asks first -- a refusal changes nothing (#3)", async () => {
    const { api, deps, ctl } = harness(null, false);
    const file = JSON.stringify(project("t", "T"));
    api.session.mockResolvedValue(project("take1", "T1"));
    arrangement.addClip({ lane: 1, startSec: 0, durSec: 4, audio: { kind: "crop", crop_id: "MINE" } });   // a fresh tab's work
    await ctl.loadSession("take1");
    expect(deps.confirm).toHaveBeenCalledTimes(1);
    expect(loadedCrops()).toEqual(["MINE"]);          // declined: nothing replaced
    expect(ctl.session).toBe("");
    await ctl.importProjectFile({ name: "t.json", text: async () => file });
    expect(deps.confirm).toHaveBeenCalledTimes(2);
    expect(loadedCrops()).toEqual(["MINE"]);
    vi.mocked(deps.confirm).mockReturnValue(true);
    await ctl.importProjectFile({ name: "t.json", text: async () => file });
    expect(deps.confirm).toHaveBeenCalledTimes(3);
    expect(loadedCrops()).toEqual(["T"]);
    await ctl.loadSession("take1");                   // an untouched import is on disk already: no question
    expect(deps.confirm).toHaveBeenCalledTimes(3);
    expect(ctl.session).toBe("take1");
    expect(api.saveSession).not.toHaveBeenCalled();
  });

  it("SAVE and MASTER PRESET SAVE under a typed name that is already listed ask before overwriting it (#4)", async () => {
    const { api, deps, ctl } = harness(null, false);
    vi.mocked(deps.exists).mockImplementation((kind, name) => name === (kind === "session" ? "take1" : "live A"));
    vi.mocked(deps.prompt).mockReturnValue("take1");
    expect(await ctl.saveSession()).toBeNull();       // declined: take1 on the server is not replaced
    expect(api.saveSession).not.toHaveBeenCalled();
    expect(ctl.session).toBe("");
    vi.mocked(deps.prompt).mockReturnValue("live A");
    expect(await ctl.saveMasterPreset("")).toBeNull();
    expect(api.savePreset).not.toHaveBeenCalled();
    expect(deps.confirm).toHaveBeenCalledTimes(2);
    vi.mocked(deps.confirm).mockReturnValue(true);
    expect(await ctl.saveMasterPreset("")).toBe("live A");
    expect(api.savePreset.mock.calls[0].slice(0, 2)).toEqual(["master", "live A"]);
    vi.mocked(deps.prompt).mockReturnValue("take1");
    expect(await ctl.saveSession()).toBe("take1");
    expect(api.saveSession.mock.calls[0][0]).toBe("take1");
  });

  it("PUTs to one session are ordered: a second autosave waits for the first, and re-loading that session waits for both (#5)", async () => {
    vi.useFakeTimers();
    const { api, ctl } = harness();
    api.session.mockResolvedValue(project("take1", "T1"));
    await ctl.loadSession("take1");
    const first = deferred<unknown>();
    api.saveSession.mockReturnValueOnce(first.promise);
    arrangement.master.gain = 90;
    ctl.observe();
    vi.advanceTimersByTime(2000);                     // PUT #1 in flight
    arrangement.master.gain = 91;
    ctl.observe();
    vi.advanceTimersByTime(2000);                     // PUT #2 due -- queued behind #1, not sent
    expect(api.saveSession).toHaveBeenCalledTimes(1);
    const reload = ctl.loadSession("take1");
    expect(api.session).toHaveBeenCalledTimes(1);     // the GET waits for take1's PUTs too
    first.resolve({ ok: true });
    await reload;
    expect(api.saveSession).toHaveBeenCalledTimes(2);
    expect(api.saveSession.mock.calls[1][1].master.gain).toBe(91);
    expect(api.session).toHaveBeenCalledTimes(2);
  });

  it("a load superseded mid-rebuild by one that fails: the timeline goes unsaved and STAGE follows the server, not the orphaned project (#6, #9)", async () => {
    vi.useFakeTimers();
    const { api, ctl } = harness();
    const rebuild = deferred<unknown>();
    const take2 = deferred<unknown>();
    api.session
      .mockResolvedValueOnce(project("take1", "T1"))
      .mockResolvedValueOnce(project("post-set", "P", "POST"))
      .mockReturnValueOnce(take2.promise);
    api.setBackbone.mockReturnValue(rebuild.promise);
    await ctl.loadSession("take1");
    const loadA = ctl.loadSession("post-set");
    await vi.waitFor(() => expect(api.setBackbone).toHaveBeenCalledWith("medium"));
    const loadB = ctl.loadSession("take2");
    take2.reject(new Error("404 take2"));
    await loadB;                                      // B applied nothing; A's project is in the stores
    expect(ctl.loading).toBe(false);
    expect(ctl.session).toBe("");                     // settle's orphan branch: no session owns them
    expect(loadedCrops()).toEqual(["P"]);
    rebuild.reject(new Error("rebuild failed"));
    await loadA;
    await vi.waitFor(() => expect(settings.stage).toBe("BASE"));   // the server never left BASE
    arrangement.master.gain = 90;
    ctl.observe();
    vi.advanceTimersByTime(10_000);
    expect(api.saveSession).not.toHaveBeenCalled();   // nothing armed: neither take1 nor post-set
  });

  it("a SAVE whose PUT is still pending when a load commits names and arms nothing -- the load owns the stores (#9)", async () => {
    vi.useFakeTimers();
    const { api, ctl } = harness();
    api.session.mockResolvedValueOnce(project("take1", "T1")).mockResolvedValueOnce(project("take2", "T2"));
    await ctl.loadSession("take1");
    const put = deferred<unknown>();
    api.saveSession.mockReturnValueOnce(put.promise);
    const saving = ctl.saveSession();
    await ctl.loadSession("take2");
    expect(ctl.session).toBe("take2");
    put.resolve({ ok: true });
    expect(await saving).toBe("take1");               // it did save, under its own name ...
    expect(ctl.session).toBe("take2");                // ... and renamed nothing
    arrangement.master.gain = 90;
    ctl.observe();
    vi.advanceTimersByTime(2000);
    expect(api.saveSession).toHaveBeenCalledTimes(2);
    expect(api.saveSession.mock.calls[1][0]).toBe("take2");
    expect(savedCrops(api.saveSession.mock.calls[1][1])).toEqual(["T2"]);
  });

  it("an apply that throws anyway leaves the timeline unsaved: nothing is named, armed or PUT (#9)", async () => {
    vi.useFakeTimers();
    const { api, ctl } = harness();
    api.session.mockResolvedValueOnce(project("take1", "T1")).mockResolvedValueOnce(project("take2", "T2"));
    await ctl.loadSession("take1");
    const restoreUi = vi.spyOn(view, "restoreUi").mockImplementationOnce(() => {
      throw new Error("boom");                        // applyProject's LAST write: every store is take2's by now
    });
    await ctl.loadSession("take2");
    restoreUi.mockRestore();
    expect(ctl.session).toBe("");
    expect(ctl.loading).toBe(false);
    arrangement.master.gain = 90;
    ctl.observe();
    vi.advanceTimersByTime(10_000);
    expect(api.saveSession).not.toHaveBeenCalled();   // not take1 (its content is gone), not take2 (half-applied)
  });

  it("MASTER PRESET recall applies nothing mid-load, nothing a load overtook, and nothing malformed -- validated whole first (#2, #12)", async () => {
    const { api, ctl } = harness();
    const take1 = project("take1", "T1");
    const take2 = project("take2", "T2");
    const pending = deferred<unknown>();
    api.session.mockReturnValueOnce(pending.promise).mockResolvedValueOnce(take2);
    const loading = ctl.loadSession("take1");
    expect(await ctl.recallMasterPreset("live A")).toBe(false);   // refused while take1 loads
    expect(api.preset).not.toHaveBeenCalled();
    pending.resolve(take1);
    await loading;
    const preset = deferred<unknown>();
    api.preset.mockReturnValueOnce(preset.promise);
    const recall = ctl.recallMasterPreset("live A");
    await ctl.loadSession("take2");                   // picked while the preset was in flight
    const late: MasterPresetPayload = { ...buildMasterPresetPayload(), master: { ...MASTER_DEFAULT, gain: 99 } };
    preset.resolve(late);
    expect(await recall).toBe(false);                 // take1's pick never lands on take2's stores
    expect(arrangement.master.gain).toBe(MASTER_DEFAULT.gain);
    const broken = JSON.parse(JSON.stringify(late)) as Record<string, unknown>;
    (broken.lanes as MasterPresetPayload["lanes"])[0].chain.latch_on = true;
    delete broken.defaults;                           // read LAST by applyMasterPreset
    api.preset.mockResolvedValueOnce(broken);
    expect(await ctl.recallMasterPreset("broken")).toBe(false);
    expect(arrangement.lanes[0].chain.latch_on).toBe(false);   // not half-applied
    expect(arrangement.master.gain).toBe(MASTER_DEFAULT.gain);
    api.preset.mockResolvedValueOnce(late);
    expect(await ctl.recallMasterPreset("live A")).toBe(true);
    expect(arrangement.master.gain).toBe(99);
  });

  it("a load never overlaps M4's STAGE rebuild: refused while one runs, and it holds settings.stageLocked throughout (reconcile pass, OQ 32)", async () => {
    const { api, deps, ctl } = harness();
    settings.stageRebuilding = true;                  // M4 T9's confirmStage is awaiting setBackbone
    try {
      await ctl.loadSession("take1");
      await ctl.importProjectFile({ name: "x.json", text: async () => "{}" });
      expect(api.session).not.toHaveBeenCalled();     // refused before the fetch
      expect(ctl.loading).toBe(false);
      expect(settings.stageLocked).toBe(false);
      expect(deps.log).toHaveBeenCalledWith(expect.stringContaining("MODEL STAGE is rebuilding"), "error");
    } finally {
      settings.stageRebuilding = false;
    }
    const take1 = project("take1", "T1");
    const pending = deferred<unknown>();
    api.session.mockReturnValueOnce(pending.promise);
    const loading = ctl.loadSession("take1");
    expect(settings.stageLocked).toBe(true);          // M4's MODEL STAGE offers no switch now
    pending.resolve(take1);
    await loading;
    expect(ctl.session).toBe("take1");
    expect(settings.stageLocked).toBe(false);         // released when the load settles
  });

  it("the stage lock outlives a superseded load's rebuild: M4's STAGE stays locked until that setBackbone settles (critic follow-up #3)", async () => {
    const { api, ctl } = harness();
    const rebuild = deferred<unknown>();
    const take2 = deferred<unknown>();
    api.session
      .mockResolvedValueOnce(project("post-set", "P", "POST"))
      .mockReturnValueOnce(take2.promise);
    api.setBackbone.mockReturnValue(rebuild.promise);
    const loadA = ctl.loadSession("post-set");
    await vi.waitFor(() => expect(api.setBackbone).toHaveBeenCalledWith("medium"));
    const loadB = ctl.loadSession("take2");
    take2.reject(new Error("404 take2"));
    await loadB;                                      // the LATEST load ended early ...
    expect(ctl.loading).toBe(false);
    expect(settings.stageLocked).toBe(true);          // ... but A's rebuild is still on the server: no STAGE yet
    rebuild.reject(new Error("rebuild failed"));
    await loadA;
    await vi.waitFor(() => expect(settings.stageLocked).toBe(false));   // released once it settled
    expect(api.setBackbone).toHaveBeenCalledTimes(1);   // and nothing sent a second, parallel one
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

  it("a pick leaves the select on the committed session (and master preset) until the parent changes it (a failed load never shows the picked name)", async () => {
    const onsession = vi.fn();
    const onmasterpreset = vi.fn();
    const two = [...SESSIONS, { name: "take2", updated: 2, n_clips: 1 }];
    const presets = { masterPresets: ["live A", "live B"], masterPreset: "live A", onmasterpreset };
    const { getByTestId, rerender } = render(TopBar, { props: { ...base, ...presets, sessions: two, session: "take1", onsession } });
    const select = getByTestId("session-select") as HTMLSelectElement;
    await fireEvent.change(select, { target: { value: "take2" } });
    expect(onsession).toHaveBeenCalledWith("take2");
    expect(select.value).toBe("take1");   // take2 is not loaded yet -- maybe never
    await rerender({ ...base, ...presets, sessions: two, session: "take2", onsession });
    expect(select.value).toBe("take2");   // the controller committed it (step 9)
    // the MASTER PRESET select follows the same rule: highlighted only once the recall applied (critic pass 3 #2)
    const preset = getByTestId("master-preset-select") as HTMLSelectElement;
    await fireEvent.change(preset, { target: { value: "live B" } });
    expect(onmasterpreset).toHaveBeenCalledWith("live B");
    expect(preset.value).toBe("live A");
  });

  it("while a load is in flight it says which session is loading and disables SAVE; the select keeps the committed name (critic pass 3 #11)", async () => {
    const { getByTestId, queryByTestId, rerender } = render(TopBar, {
      props: { ...base, sessions: SESSIONS, session: "take1", loadingName: "take2" },
    });
    expect(getByTestId("session-loading").textContent).toContain("loading take2");
    expect((getByTestId("session-save") as HTMLButtonElement).disabled).toBe(true);
    expect((getByTestId("session-select") as HTMLSelectElement).value).toBe("take1");
    await rerender({ ...base, sessions: SESSIONS, session: "take1", loadingName: "" });
    expect(queryByTestId("session-loading")).toBeNull();
    expect((getByTestId("session-save") as HTMLButtonElement).disabled).toBe(false);
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
import { cleanup, render, waitFor } from "@testing-library/svelte";
import { tick } from "svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CHAIN_DEFAULTS } from "../../../lib/forge/defaults";
import { arrangement } from "../../../lib/stores/arrangement.svelte";
import { settings } from "../../../lib/stores/settings.svelte";
import { view } from "../../../lib/stores/view.svelte";
import RightPaneModules from "../RightPaneModules.svelte";

// The REAL ModuleShell. Its lit dot is pinned by M1 T9 since the reconcile pass of 2026-09-25:
// [data-module-dot=<id>] carrying data-lit="true"|"false" (Open questions 27). The probe this suite
// used to mock ModuleShell with, because no plan pinned that markup, is gone.
const lit = (container: HTMLElement, id: string) =>
  container.querySelector(`[data-module-dot="${id}"]`)!.getAttribute("data-lit");

const RMS_BASS = { name: "rms_energy_bass", family: "medium", default_gain: 512, health: "ok",
  supports_kinds: ["constant"], slider_min: -35.2, slider_max: -0.13, value_default: -12 };

beforeEach(() => {
  // Every module body fetches on mount (FILES, LANE CHAIN, MASTER CHAIN), and so does this file's
  // own head list; answer all of them with one valid body so nothing rejects on jsdom's relative URLs.
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({
    ok: true, roots: [], files: [], names: [], latch_heads: [RMS_BASS], models: [], slots: [],
  }))));
  arrangement.clips.splice(0, arrangement.clips.length);
});

afterEach(() => {
  cleanup();
  view.clearSelection();
  view.closeModule("overlap");
  view.closeModule("advanced-sampling");
  arrangement.clips.splice(0, arrangement.clips.length);
  for (const lane of arrangement.lanes) lane.chain = structuredClone(CHAIN_DEFAULTS);
  vi.unstubAllGlobals();
});

describe("RightPaneModules after M7 T9", () => {
  it("lights LANE CHAIN's dot from the active lane's live chain, and relights on an in-place edit", async () => {
    view.setActiveLane(0);
    const { container } = render(RightPaneModules);
    expect(lit(container, "lane-chain")).toBe("false");
    arrangement.lanes[0].chain.latch_on = true;   // in place -- Global Constraint #1
    await tick();
    expect(lit(container, "lane-chain")).toBe("true");
    expect(lit(container, "master-chain")).toBe("false");
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

  it("hands ADVANCED SAMPLING only registry-known LatCH slots, so a deleted head does not force Euler", async () => {
    // M4's activeSlots counts any non-"none", non-zero-weight head; chainRequest (T1) sends a head
    // /info does not list as "none" (the server 400s on it). Passing it through would show "euler
    // (forced by LatCH)" for a request that sends no active LatCH slot at all (critic pass 2 #8).
    view.setActiveLane(0);
    const chain = arrangement.lanes[0].chain;
    chain.latch_on = true;
    chain.slots[0] = { head: "deleted_head", kind: "constant", value: 0, weight: 1, start_pct: 0, end_pct: 0.6 };
    view.openModule("advanced-sampling");
    const { findByTestId } = render(RightPaneModules);
    const sampler = (await findByTestId("adv-sampler")) as HTMLSelectElement;   // M4's own testid
    expect(sampler.disabled).toBe(false);
    chain.slots[0].head = "rms_energy_bass";   // a head the registry lists: now it really forces Euler
    await waitFor(() => expect(sampler.disabled).toBe(true));
  });

  it("wires M4 to M5: a selected clip's OWN render lights ADVANCED SAMPLING, and its A2A NOISE reaches σ MAX (reconcile pass, OQ 19/20)", async () => {
    settings.attach(arrangement.settingsSource);   // App.svelte does this once at startup (Step 4)
    try {
      const clip = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: { kind: "crop", crop_id: "A" } });
      arrangement.ensureA2A(clip.id);
      arrangement.setNoise(clip.id, 0.4);
      view.select({ kind: "clip", id: clip.id });
      view.openModule("advanced-sampling");
      const { container, findByLabelText } = render(RightPaneModules);
      expect(lit(container, "advanced-sampling")).toBe("false");
      // M4 T11: σ MAX mirrors the selected A2A clip's NOISE -- only if `a2a` reaches the module.
      expect(((await findByLabelText("σ MAX")) as HTMLInputElement).value).toBe("0.40");
      const before = settings.defaults.steps;
      clip.render.steps = 40;                      // the CLIP's settings, in place, not session.defaults
      await tick();
      expect(lit(container, "advanced-sampling")).toBe("true");
      expect(settings.defaults.steps).toBe(before);
    } finally {
      settings.detach();
    }
  });
});
```

- [ ] **Step 2: Run them, expect failure**

```bash
cd /home/kim/Projects/sa3-studio-review/latent-forge && npx vitest run src/lib/forge/__tests__/sessionName.test.ts src/lib/forge/__tests__/autosave.test.ts src/lib/forge/__tests__/projectSerializer.test.ts src/lib/forge/__tests__/sessionController.test.ts src/lib/help/__tests__/sessionHelp.test.ts src/ui/shell/__tests__/topBarSessions.test.ts src/ui/shell/__tests__/rightPaneModules.test.ts src/ui/prompt/__tests__/promptSigmaTabClip.test.ts
```

Expected: `promptSigmaTabClip.test.ts` fails at `c.a2a?.on` being `undefined` (M4's propless
`PromptSigmaTab` hands TargetBar a no-op `onA2AToggle`); `Failed to resolve import "../sessionName"`, `"../autosave"`, `"../projectSerializer.svelte"`,
`"../sessionController.svelte"`; `HELP.masterPresetSave`/`.sessionSave`/`.sessionImportV1` undefined;
the seven `topBarSessions.test.ts` cases fail against the pre-T9 `TopBar.svelte` (SAVE/LOAD project
buttons still present, no `unsaved` option, no `session-save`/`session-import`/`session-loading`
test ids, `master-preset-save` still hard-disabled, the selects left on the picked name);
`rightPaneModules.test.ts` fails its lit-dot case (M1's constant snapshot passes `lit=false` to every
shell), its LatCH case (M1 renders `<AdvancedSampling />`, so a known head never forces Euler) and
its M4/M5 wiring case (no `a2a` reaches the module, so σ MAX reads 1.00; `sampling` is `null`, so
the dot never lights). `sessionController.test.ts`'s stage-lock case fails with the rest of that
file (no controller yet).
Its overlap case already passes at this point, because Task 7's body already reads through
`peekOverlapParams` — it is the regression guard for Step 5's snapshot, which is the other place that
must never call the seeding `overlapParams`. Summary: `Test Files  8 failed (8)`.

- [ ] **Step 3: Write `sessionName.ts`, `autosave.ts`, `projectSerializer.svelte.ts`, `sessionController.svelte.ts`**

`latent-forge/src/lib/forge/sessionName.ts`:

```ts
// Spec §6.3, verbatim: the server 400s a name outside this pattern, so the
// client validates before the PUT rather than round-tripping a guaranteed error.
export const SESSION_NAME_RE = /^[A-Za-z0-9._-]{1,80}$/;

// The pattern admits "." and "..", which the server refuses on their own (WINTERMUTE 2026-09-25;
// M2's `name in (".", "..") or not _NAME_RE.match(name)`) -- critic follow-up #8.
export function isValidSessionName(name: string): boolean {
  return name !== "." && name !== ".." && SESSION_NAME_RE.test(name);
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
 * The session autosave. Three guarantees the bare debounce cannot give on its own:
 *  1. a tab that has not loaded or saved a session never writes one -- the launch arrangement is
 *     blank, and PUTting it over a listed session would destroy that session;
 *  2. a re-run of the watching effect that changed nothing saves nothing;
 *  3. a save whose promise rejects is not lost (critic pass 3 #5): it stays pending against the
 *     last snapshot the server confirmed, so the next observe() re-queues it and arming another
 *     session flushes it. No timer is restarted for it, so a server that keeps failing is not
 *     retried in a loop -- the next change, or the next load, retries it.
 */
export function createSnapshotAutosave(
  save: (name: string, snapshot: string) => Promise<unknown> | void,
  delayMs = 2000,
): SnapshotAutosave {
  let armedName = "";
  let baseline = "";
  /** The last snapshot of `armedName` the server is known to hold: armed, or a save that resolved. */
  let confirmed = "";
  let pending: { name: string; snapshot: string } | null = null;

  function write(name: string, snapshot: string): void {
    Promise.resolve(save(name, snapshot)).then(
      () => {
        if (name === armedName) confirmed = snapshot;
      },
      () => {
        // Superseded by a newer save of this name, or by a re-arm: that one carries the state now.
        if (name !== armedName || baseline !== snapshot) return;
        baseline = confirmed;
        if (!pending) pending = { name, snapshot };
      },
    );
  }

  const debounce = createAutosave(() => {
    if (!pending) return;
    const { name, snapshot } = pending;
    pending = null;
    if (name === armedName) baseline = snapshot;
    write(name, snapshot);
  }, delayMs);

  return {
    arm(name, snapshot) {
      if (pending && pending.name !== name) {
        const p = pending;
        pending = null;
        debounce.cancel();
        write(p.name, p.snapshot);   // a failure now is only logged by the caller: the name is disarmed
      }
      armedName = name;
      baseline = snapshot;
      confirmed = snapshot;
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
import { settings, STAGE_BACKBONE, STAGE_FIELDS, type ModelStage } from "../stores/settings.svelte";
import { view } from "../stores/view.svelte";
import { durableChain } from "../chains/modulePresets";
import { SNAP_MODES } from "../math/snap";
import { BASE_DEFAULTS, CHAIN_DEFAULTS, cloneRenderSettings, POST_DEFAULTS } from "./defaults";
import { isAudioRef, isEnvelope } from "./guards";
import type {
  ForgeClip, ForgeLane, LaneChain, MasterChain, MixSpec, OverlapParams, ProjectV2, RenderSettings,
} from "./types";

/** `backbone` overrides settings.backboneId: SessionController's pin (Task 9 WHY, step 8) keeps a
 *  loaded session's own backbone in what is saved while a failed rebuild has the client reverted. */
export function serializeProject(opts: { name: string; backbone?: string }): ProjectV2 {
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
    // durableChain: lora.slot is a transient /slots resolution, never saved (contract table).
    lanes: ($state.snapshot(arrangement.lanes) as ForgeLane[]).map((l) => ({ ...l, chain: durableChain(l.chain) })),
    // previewAudio is in-memory only (spec §9.2 "Not serialised", M1 Normative row): the field is
    // required on ForgeClip, so it is written as null -- the live ref never reaches the JSON.
    clips: ($state.snapshot(arrangement.clips) as ForgeClip[]).map((c) => ({ ...c, previewAudio: null })),
    overlaps,
    mix: $state.snapshot(arrangement.mix) as MixSpec,
    master: $state.snapshot(arrangement.master) as MasterChain,
    defaults: $state.snapshot(settings.defaults) as RenderSettings,
    backbone: opts.backbone ?? settings.backboneId,
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

function isObj(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function isNum(v: unknown): boolean {
  return typeof v === "number" && Number.isFinite(v);
}

const isBool = (v: unknown): boolean => typeof v === "boolean";
const isStrOrNull = (v: unknown): boolean => v === null || typeof v === "string";
const isLaneIndex = (v: unknown): boolean => [0, 1, 2, 3].includes(v as number);

// Shape checks for validateProjectV2 / validateMasterPreset, one per M1 type (M1 plan lines
// 428-624): every saved field of LaneChain, ForgeLane, ForgeClip (not the in-memory previewAudio),
// OverlapParams, MixSpec and MasterChain.

/** RenderSettings, as far as cloneRenderSettings dereferences it (the nested objects it copies). */
function isRender(r: unknown): boolean {
  return isObj(r) && isObj(r.schedule) && Array.isArray(r.cfg_interval_progress);
}

function isLaneChain(c: unknown): boolean {
  if (!isObj(c) || !Array.isArray(c.slots) || !isObj(c.hparams) || !isObj(c.film) || !isObj(c.lora)) return false;
  const h = c.hparams;
  const film = c.film;
  const lora = c.lora;
  return c.slots.length === 2
    && c.slots.every((s: unknown) => isObj(s) && typeof s.head === "string" && typeof s.kind === "string"
      && isNum(s.value) && isNum(s.weight) && isNum(s.start_pct) && isNum(s.end_pct))
    && isBool(c.latch_on) && isBool(c.film_on) && isBool(c.lora_on) && isBool(c.bungee_on) && isNum(c.semitones)
    && isNum(h.rho) && isNum(h.mu) && isNum(h.gamma) && isNum(h.n_iter) && isBool(h.log_norms)
    && isStrOrNull(film.ckpt) && isNum(film.gain) && isNum(film.value)
    && isStrOrNull(lora.ckpt_path) && (lora.slot === null || isNum(lora.slot)) && isNum(lora.strength);
}

function isA2A(a: unknown): boolean {
  return a === null || (isObj(a) && isBool(a.on) && isNum(a.noise) && isEnvelope(a.envelope));
}

/** The clip-layout fields a master preset carries (and every clip has). */
function isClipLayout(c: Record<string, unknown>): boolean {
  return typeof c.id === "string" && isLaneIndex(c.lane) && isNum(c.start_sec) && isNum(c.offset_sec)
    && isNum(c.dur_sec) && isBool(c.loop) && (c.native_bpm === null || isNum(c.native_bpm))
    && isNum(c.detune_cents) && isA2A(c.a2a);
}

function isClip(c: unknown): boolean {
  return isObj(c) && isClipLayout(c) && isAudioRef(c.audio) && isRender(c.render)
    && Array.isArray(c.downbeats_sec) && c.downbeats_sec.every(isNum)
    && ["none", "valid", "stale"].includes(c.latentState as string)
    && Array.isArray(c.history) && c.history.every(isAudioRef);
}

function isOverlapParams(o: unknown): boolean {
  return isObj(o) && isEnvelope(o.curve) && isBool(o.chroma_xfade) && isBool(o.override)
    && isNum(o.steps) && isNum(o.cfg) && isRender(o.render);
}

function isMix(m: unknown): boolean {
  if (!isObj(m) || !isObj(m.nodes) || !Array.isArray(m.quad_weights)) return false;
  const nodes = m.nodes;
  return ["tree", "cascade", "quad"].includes(m.order as string)
    && (["M1", "M2", "MX"] as const).every((k) => {
      const n = nodes[k];
      return isObj(n) && (n.interp === "lerp" || n.interp === "slerp") && isNum(n.t);
    })
    && m.quad_weights.length === 4 && m.quad_weights.every(isNum);
}

function isMaster(m: unknown): boolean {
  return isObj(m) && isBool(m.latch_on) && typeof m.head === "string" && isNum(m.gain) && isBool(m.norm_on);
}

/**
 * A `version: 2` object from the server or a file, checked as a WHOLE before applyProject touches
 * any store (critic pass 2 #1). Every field applyProject -- or a reader it hands data to
 * (cloneRenderSettings, view.restoreUi, the lane-chain, clip, overlap, mix and master components)
 * -- dereferences is checked, down to each lane, clip, overlap entry, mix node and master field
 * (critic pass 3 #8: `ui: {modules: "files"}` used to pass and then throw in restoreUi, the LAST
 * line of the apply, after every store was written). So an object that passes cannot throw
 * half-way through the apply. Throws naming the first bad field; returns the same object, typed.
 */
export function validateProjectV2(raw: unknown): ProjectV2 {
  const bad = (field: string) => new Error(`not a v2 project: ${field} is missing or the wrong type`);
  if (!isObj(raw) || raw.version !== 2) throw bad("version");
  const p = raw;
  if (!isObj(p.meter) || !isNum(p.meter.bpm) || !isNum(p.meter.beatsPerBar)) throw bad("meter");
  if (!SNAP_MODES.some((m) => m.value === p.snap)) throw bad("snap");
  if (!isObj(p.view) || !isNum(p.view.pxPerSec) || !isNum(p.view.scrollSec)) throw bad("view");
  if (!Array.isArray(p.lanes) || p.lanes.length !== 4) throw bad("lanes");
  p.lanes.forEach((l: unknown, i: number) => {
    if (!isObj(l) || !isLaneIndex(l.index) || typeof l.name !== "string" || !isNum(l.gain)
      || !isBool(l.muted) || !isBool(l.solo)) {
      throw bad(`lanes[${i}]`);
    }
    if (!isLaneChain(l.chain)) throw bad(`lanes[${i}].chain`);
  });
  if (!Array.isArray(p.clips)) throw bad("clips");
  p.clips.forEach((c: unknown, i: number) => {
    if (!isClip(c)) throw bad(`clips[${i}]`);
  });
  if (!isObj(p.overlaps)) throw bad("overlaps");
  for (const [key, o] of Object.entries(p.overlaps)) {
    if (!isOverlapParams(o)) throw bad(`overlaps.${key}`);
  }
  if (!isMix(p.mix)) throw bad("mix");
  if (!isMaster(p.master)) throw bad("master");
  if (!isRender(p.defaults)) throw bad("defaults");
  if (typeof p.backbone !== "string") throw bad("backbone");
  if (!isStrOrNull(p.ckpt_path)) throw bad("ckpt_path");
  // M1's restoreUi calls `.filter` on modules; the other three it reads through includes()/Boolean().
  if (!isObj(p.ui) || !Array.isArray(p.ui.modules)) throw bad("ui");
  return raw as unknown as ProjectV2;
}

/** M4's own field copy (settings.svelte.ts `assign`), for STAGE_FIELDS: a typed assignment per key. */
function copyField<K extends keyof RenderSettings>(into: RenderSettings, from: RenderSettings, k: K): void {
  into[k] = from[k];
}

/** `project` is plain data (a server response, a parsed file, or serializeProject's output) that
 *  has already passed validateProjectV2 or come out of convertProjectV1. `restoreModel: false`
 *  (converted v1 input) keeps the current stage and ckpt: v1 records neither (critic pass 2 #7) --
 *  and so keeps that stage's STAGE_FIELDS too (critic pass 3 #7). */
export function applyProject(project: ProjectV2, opts: { restoreModel?: boolean } = {}): void {
  // Nothing selected survives a load: the old selection's clip/overlap key may not exist here, and a
  // stale overlap key would keep OVERLAP-INPAINT mounted (critic pass 2 #5).
  view.clearSelection();
  // Overlap params are replaced wholesale, not merged: a key this project does not set must not
  // inherit the previous project's edits (a v1 import keeps its clip ids, so keys can repeat).
  arrangement.clearOverlapParams();
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
  // The caller (SessionController, step 8) rebuilds the server model if this changed it.
  if (opts.restoreModel ?? true) {
    const stage = stageForBackbone(project.backbone);
    if (stage) settings.stage = stage;
    settings.ckptPath = project.ckpt_path;
  }
  settings.defaults = cloneRenderSettings(project.defaults);
  if (!(opts.restoreModel ?? true)) {
    // The stage stayed, so its steps/sampler/schedule stay matched to it, exactly as M4's setStage
    // keeps them: the converter fills `defaults` from BASE_DEFAULTS, which under POST would put 24
    // Euler steps on the model schedule into a distilled session.
    const stageDefaults = cloneRenderSettings(settings.stage === "POST" ? POST_DEFAULTS : BASE_DEFAULTS);
    for (const k of STAGE_FIELDS) copyField(settings.defaults, stageDefaults, k);
  }
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
    lanes: arrangement.lanes.map((l) => ({ chain: durableChain($state.snapshot(l.chain) as LaneChain) })),
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

/**
 * A master preset from the server, checked as a WHOLE before applyMasterPreset writes anything
 * (critic pass 3 #12): a payload missing `defaults` used to throw on the last two lines, after the
 * lanes, clips, mix and master were already recalled -- and an armed session then autosaved that
 * half recall. Every field applyMasterPreset writes is checked. Throws naming the first bad field.
 */
export function validateMasterPreset(raw: unknown): MasterPresetPayload {
  const bad = (field: string) => new Error(`not a master preset: ${field} is missing or the wrong type`);
  if (!isObj(raw)) throw bad("payload");
  if (!Array.isArray(raw.lanes) || raw.lanes.length !== 4) throw bad("lanes");
  raw.lanes.forEach((l: unknown, i: number) => {
    if (!isObj(l) || !isLaneChain(l.chain)) throw bad(`lanes[${i}].chain`);
  });
  if (!Array.isArray(raw.clips)) throw bad("clips");
  raw.clips.forEach((c: unknown, i: number) => {
    if (!isObj(c) || !isClipLayout(c)) throw bad(`clips[${i}]`);
  });
  if (!isMix(raw.mix)) throw bad("mix");
  if (!isMaster(raw.master)) throw bad("master");
  if (!isObj(raw.defaults) || !isObj(raw.defaults.schedule) || typeof raw.defaults.prompt !== "string") {
    throw bad("defaults");
  }
  return raw as unknown as MasterPresetPayload;
}

/** Recall replaces the whole slice (spec §9.3): matched by clip id within the
 *  CURRENT session's arrangement, since a master preset is a snapshot of one
 *  session's layout, not a transplant of clips into a different one. A clip id
 *  the preset names that no longer exists is skipped, not an error.
 *  `payload` is plain data that passed validateMasterPreset (a server response),
 *  or buildMasterPresetPayload's output. */
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

`latent-forge/src/lib/forge/sessionController.svelte.ts` — the numbered comments are the WHY's
steps; keep them in this order:

```ts
// The ONE session load / IMPORT / SAVE sequence (spec §9.2), plus MASTER PRESET recall and save,
// outside App.svelte so every ordering guarantee is unit-tested (sessionController.test.ts). Task
// 9's WHY states the order as steps 1-9; the numbered comments below are those steps. Invariant,
// whenever `loading` is false: either `session` is "" and autosave is disarmed, or `session` is X,
// autosave is armed on X, and the stores hold X's content (possibly edited).
import { scheduleStretch as m5ScheduleStretch } from "../clips/lifecycle";
import { arrangement } from "../stores/arrangement.svelte";
import { settings, STAGE_BACKBONE, type ModelStage } from "../stores/settings.svelte";
import { createSnapshotAutosave, type SnapshotAutosave } from "./autosave";
import { convertProjectV1 } from "./convertProjectV1";
import {
  applyMasterPreset, applyProject, buildMasterPresetPayload, serializeProject, validateMasterPreset,
  validateProjectV2, type MasterPresetPayload,
} from "./projectSerializer.svelte";
import { isValidSessionName } from "./sessionName";
import type { ProjectV2 } from "./types";

export interface SessionDeps {
  api: {
    session(name: string): Promise<unknown>;
    saveSession(name: string, project: ProjectV2): Promise<unknown>;
    setBackbone(id: string): Promise<unknown>;
    preset(level: string, name: string): Promise<unknown>;
    savePreset(level: string, name: string, payload: unknown): Promise<unknown>;
  };
  log(text: string, level?: "info" | "error"): void;
  prompt(message: string): string | null;
  /** Yes/no before unsaved work is replaced or a listed name overwritten (critic pass 3 #3, #4). */
  confirm(message: string): boolean;
  /** Whether the TopBar already lists a session / master preset of that name (App reads its lists). */
  exists(kind: "session" | "master", name: string): boolean;
  /** M5 T10's debounced per-clip stretch; defaults to the real one, tests pass a spy. */
  scheduleStretch?: (clipId: string) => void;
  delayMs?: number;
}

const errText = (e: unknown) => (e instanceof Error ? e.message : String(e));

interface Loaded { project: ProjectV2; kind: "v1" | "v2" }

/** Step 3. v2 is validated as a whole (throws on a malformed object, before anything is touched);
 *  v1 goes through the converter (Task 8, never throws); ANY other version -- missing, "2", 3 -- is
 *  refused, never converted as if it were v1 (critic pass 3 #1: the converter would read v1 field
 *  names off it and empty the timeline). v1's own loadJSON refuses the same way. */
function toLoaded(raw: unknown): Loaded {
  const version = (raw as { version?: unknown } | null)?.version;
  if (version === 2) return { project: validateProjectV2(raw), kind: "v2" };
  if (version === 1) return { project: convertProjectV1(raw), kind: "v1" };
  throw new Error(`unsupported project version ${JSON.stringify(version) ?? "(none)"}`);
}

/** What counts as work for step 3's "replace unsaved work?" (critic pass 3 #3): everything saved
 *  except the name, the viewport, the ui slice and the model -- scrolling, opening a module or a
 *  STAGE revert is not work anyone would lose. */
function workKey(p: ProjectV2): string {
  return JSON.stringify({ ...p, name: "", view: null, ui: null, backbone: "", ckpt_path: null });
}

export class SessionController {
  /** The session the TopBar shows. See the invariant above. */
  session = $state("");
  /** A load or import is in flight. SAVE is refused meanwhile. */
  loading = $state(false);
  /** What is loading, for the TopBar's `loading <name>…` note (critic pass 3 #11); "" when idle. */
  loadingName = $state("");

  private seq = 0;
  /** A superseded load wrote its project into the stores and never armed: they belong to no one. */
  private orphaned = false;
  /** Step 8's pin: a loaded session's own backbone, serialised in place of settings.backboneId
   *  while the stage is still `underStage` (a failed rebuild, or a backbone with no stage). */
  private pin: { backbone: string; underStage: ModelStage } | null = null;
  /** workKey of what the stores held when last loaded (or at launch): step 3's reference. */
  private unsavedKey: string;
  /** Step 8. The stage the server holds while a rebuild this controller started is unsettled or
   *  unreconciled; null = trust settings.stage (M4: with nothing rebuilding, the client stage IS
   *  the loaded model -- so M4's own STAGE control, used between loads, stays authoritative). */
  private serverStage: ModelStage | null = null;
  /** The last rebuild this controller started. The next one waits for it: rebuilds never overlap. */
  private rebuildTail: Promise<void> = Promise.resolve();
  /** A setBackbone this controller started has not settled. settings.stageLocked outlives `loading`
   *  while it is true (critic follow-up #3): a superseded load's rebuild can still be running after
   *  the latest load ended, and M4's STAGE must not send a parallel setBackbone meanwhile. */
  private rebuildInFlight = false;
  /** The latest PUT per session name, settled. The next PUT to that name, and a load of it, wait. */
  private puts = new Map<string, Promise<void>>();
  private autosave: SnapshotAutosave;
  // A plain field, not a `constructor(private deps)` parameter property: that is TS-only emit,
  // which Svelte's type-stripping of rune modules does not promise to support.
  private deps: SessionDeps;

  constructor(deps: SessionDeps) {
    this.deps = deps;
    this.unsavedKey = workKey(serializeProject({ name: "" }));   // the blank launch project
    this.autosave = createSnapshotAutosave(
      (name, json) =>
        this.put(name, JSON.parse(json) as ProjectV2).catch((e) => {
          deps.log(`[forge] autosave of ${name} failed: ${errText(e)}`, "error");
          throw e;                               // createSnapshotAutosave keeps it pending (critic pass 3 #5)
        }),
      deps.delayMs,
    );
  }

  /** The project as it would be saved under `name` right now. */
  private current(name: string): ProjectV2 {
    if (this.pin && settings.stage !== this.pin.underStage) this.pin = null;   // the user changed STAGE
    return serializeProject({ name, backbone: this.pin?.backbone });
  }

  /** Every session PUT goes through here (critic pass 3 #5): PUTs to one name are chained, so they
   *  reach the server in the order they were made, and loadSession(name) waits for them. The first
   *  PUT to an idle name is sent synchronously -- no extra tick. */
  private put(name: string, project: ProjectV2): Promise<unknown> {
    const before = this.puts.get(name);
    const req = before
      ? before.then(() => this.deps.api.saveSession(name, project))
      : this.deps.api.saveSession(name, project);
    const settled = req.then(() => undefined, () => undefined);
    this.puts.set(name, settled);
    void settled.then(() => {
      if (this.puts.get(name) === settled) this.puts.delete(name);
    });
    return req;
  }

  /** App's $effect body. serializeProject reads every saved field through $state.snapshot, so the
   *  effect re-runs on ANY in-place edit (Global Constraint #1); observe() compares strings, so a
   *  re-run that changed nothing saves nothing. */
  observe(): void {
    this.autosave.observe(this.session, JSON.stringify(this.current(this.session)));
  }

  /** M4's stage lock (reconcile pass 2026-09-25, Open questions 32): a load never starts while M4's
   *  own POST/BASE rebuild is in flight, and holds settings.stageLocked for as long as `loading` --
   *  and past it while a rebuild this controller started is still running (critic follow-up #3) --
   *  so MODEL STAGE offers no switch mid-load. True when the load may start. */
  private begin(name: string): boolean {
    if (settings.stageRebuilding) {
      this.deps.log(`[forge] MODEL STAGE is rebuilding -- load ${name} again once it finishes`, "error");
      return false;
    }
    this.loading = true;
    this.loadingName = name;
    settings.stageLocked = true;
    return true;
  }

  async loadSession(name: string): Promise<void> {
    if (!name) return;                       // the `unsaved` option is never a load
    if (!this.begin(name)) return;           //     refused before (1): nothing is superseded
    const mySeq = ++this.seq;                // (1) any earlier load/import is stale from here
    try {
      const inflight = this.puts.get(name);
      if (inflight) await inflight;          // (2) a PUT to this name still in flight lands first
      if (mySeq !== this.seq) return;
      let raw: unknown;
      try {
        raw = await this.deps.api.session(name);   //     stores untouched, previous session still armed
      } catch (e) {
        if (mySeq === this.seq) this.deps.log(`[forge] failed to load session ${name}: ${errText(e)}`, "error");
        return;
      }
      if (mySeq !== this.seq) return;
      await this.commit(mySeq, raw, name, `session ${name}`);
    } finally {
      this.settle(mySeq);
    }
  }

  async importProjectFile(file: { name: string; text(): Promise<string> }): Promise<void> {
    if (!this.begin(file.name)) return;
    const mySeq = ++this.seq;                // (1)
    try {
      let raw: unknown;
      try {
        raw = JSON.parse(await file.text());
      } catch (e) {
        if (mySeq === this.seq) this.deps.log(`[forge] could not import ${file.name}: ${errText(e)}`, "error");
        return;
      }
      if (mySeq !== this.seq) return;
      if (await this.commit(mySeq, raw, "", file.name)) {
        this.deps.log(`[forge] imported ${file.name} -- unsaved until you SAVE it under a session name`);
      }
    } finally {
      this.settle(mySeq);
    }
  }

  /** Steps 3-9. `target` is the session to name and arm ("" for an IMPORT). True when committed. */
  private async commit(mySeq: number, raw: unknown, target: string, what: string): Promise<boolean> {
    let loaded: Loaded;
    try {
      loaded = toLoaded(raw);                // (3) validate -- nothing touched yet
    } catch (e) {
      this.deps.log(`[forge] ${what} was not loaded: ${errText(e)}`, "error");
      return false;                          //     session, autosave and stores all unchanged
    }
    //     ... then ask before replacing work no session owns: autosave never wrote it (critic pass 3 #3)
    if ((!this.session || this.orphaned) && workKey(this.current("")) !== this.unsavedKey
      && !this.deps.confirm(`Replace the unsaved timeline with ${what}? Its edits were never saved.`)) {
      this.deps.log(`[forge] kept the unsaved timeline; ${what} was not loaded`);
      return false;                          //     a refusal touches nothing either
    }
    this.autosave.arm("", "");               // (4) disarm; flushes the outgoing session's pending
                                             //     save under ITS name, with ITS (untouched) content
    if (!target) this.session = "";          //     an IMPORT belongs to no session from here on
    this.orphaned = true;                    //     the stores are about to hold content nobody is armed on
    this.pin = null;
    if (this.serverStage === null) this.serverStage = settings.stage;   //     what the server holds, before (5) moves it
    try {
      applyProject(loaded.project, { restoreModel: loaded.kind === "v2" });   // (5) clears selection + overlap params first
    } catch (e) {
      this.orphaned = false;
      this.session = "";                     //     half-applied: the stores match no session, never name one
      this.unsavedKey = workKey(this.current(""));   //     and half-applied content is not work to protect
      this.deps.log(`[forge] ${what} failed part-way and is now unsaved: ${errText(e)}`, "error");
      void this.reconcileStage(mySeq);       //     STAGE follows the server, not the half-applied file
      return false;
    }
    const stretch = this.deps.scheduleStretch ?? ((id: string) => m5ScheduleStretch(id));
    for (const c of arrangement.clips) stretch(c.id);   // (6) previewAudio is re-derived on load
    const savedBackbone = loaded.kind === "v2" ? loaded.project.backbone : undefined;
    const loadedSnap = serializeProject({ name: target, backbone: savedBackbone });   // (7)
    const baseline = JSON.stringify(loadedSnap);
    this.unsavedKey = workKey(loadedSnap);   //     step 3's "was it edited?" reference from now on
    if (loaded.kind === "v2") await this.syncBackbone(mySeq);   // (8) rebuild to the saved stage
    else await this.reconcileStage(mySeq);   //     v1 keeps the model the server holds
    if (mySeq !== this.seq) return false;    // (9) superseded during the wait: the newer one owns the stores
    this.serverStage = null;                 //     client and server agree again
    this.pin = savedBackbone !== undefined && savedBackbone !== settings.backboneId
      ? { backbone: savedBackbone, underStage: settings.stage }
      : null;
    this.orphaned = false;
    this.session = target;
    this.autosave.arm(target, baseline);
    this.observe();                          //     an edit made during steps 5-8 differs from the baseline
    return true;
  }

  /** Step 8, v2. Stage is session-level and rebuilds the model (M4 T9 confirmStage). applyProject
   *  moved the client stage; move the server to match, or put the client back on the SERVER's stage
   *  if the rebuild fails (M4: never claim a model the server did not load). It first waits for any
   *  earlier load's rebuild, and compares against the server's stage, not the client's -- which a
   *  superseded load may have moved (critic pass 3 #6). The pin, set by commit(), keeps a revert out
   *  of the saved session. */
  private async syncBackbone(mySeq: number): Promise<void> {
    await this.rebuildTail;                  // an older load's rebuild settles first: serverStage is now true
    if (mySeq !== this.seq) return;          // superseded while waiting: the newer load decides
    const server = this.serverStage ?? settings.stage;
    const wanted = settings.stage;
    if (wanted === server) return;
    this.rebuildInFlight = true;             // the stage lock waits for this, even past `loading` (#3)
    const rebuild = this.deps.api.setBackbone(STAGE_BACKBONE[wanted]).then(
      () => {
        this.serverStage = wanted;
      },
      (e) => {
        if (mySeq !== this.seq) return;      // superseded: the newer load, or settle(), reconciles
        settings.stage = server;
        this.deps.log(
          `[forge] project wants backbone ${STAGE_BACKBONE[wanted]}; rebuild failed, staying on ` +
          `${STAGE_BACKBONE[server]}. The session keeps ${STAGE_BACKBONE[wanted]} and its own sampling ` +
          `defaults; change STAGE to retry: ${errText(e)}`,
          "error",
        );
      },
    ).finally(() => {
      this.rebuildInFlight = false;          // superseded or not: this rebuild is over
      this.releaseStageLock();
    });
    this.rebuildTail = rebuild;
    await rebuild;
  }

  /** settings.stageLocked goes only when no load is in flight AND no rebuild this controller started
   *  is still running (critic follow-up #3). Before, settle() dropped it with `loading`, so a
   *  superseded load's setBackbone could still be pending while M4 offered STAGE again. */
  private releaseStageLock(): void {
    if (!this.loading && !this.rebuildInFlight) settings.stageLocked = false;
  }

  /** Once every rebuild this controller started has settled, put the client stage on what the
   *  server holds (critic pass 3 #6). For stores no rebuild of their own will fix: an orphaned or
   *  half-applied project, and a converted v1 file, which keeps the loaded model. */
  private async reconcileStage(mySeq: number): Promise<void> {
    await this.rebuildTail;
    if (mySeq !== this.seq) return;          // a newer load decides
    const server = this.serverStage;
    this.serverStage = null;
    if (server === null || settings.stage === server) return;
    settings.stage = server;
    this.deps.log(
      `[forge] an interrupted load's rebuild did not land; STAGE follows the server (${STAGE_BACKBONE[server]})`,
      "error",
    );
  }

  /** End of the LATEST load/import only. If it did not commit after a superseded load had already
   *  written the stores, those stores match no session: show `unsaved`, keep autosave off, and let
   *  STAGE follow the server once that load's rebuild settles. */
  private settle(mySeq: number): void {
    if (mySeq !== this.seq) return;
    this.loading = false;
    this.loadingName = "";
    this.releaseStageLock();                 //     M4's MODEL STAGE is offered again -- unless a
                                             //     superseded load's rebuild is still running (#3)
    if (!this.orphaned) return;
    this.orphaned = false;
    this.session = "";
    this.autosave.arm("", "");
    this.deps.log("[forge] an interrupted load left its project in the timeline -- unsaved until you SAVE it", "error");
    void this.reconcileStage(mySeq);
  }

  /** SAVE. Returns the name saved under, or null. */
  async saveSession(): Promise<string | null> {
    if (this.loading) {
      // Step 1's rule: mid-load the stores are either the previous session's or not yet armed as
      // the target's, so a SAVE could write the wrong content under either name. Refuse, say why.
      this.deps.log("[forge] a session is still loading -- SAVE again once it has", "error");
      return null;
    }
    let name = this.session;
    let typed = false;
    if (!name) {
      const answer = this.deps.prompt("Session name (letters, numbers, . _ - only):");
      if (!answer) return null;
      name = answer;
      typed = true;
    }
    if (!isValidSessionName(name)) {
      this.deps.log(`[forge] "${name}" is not a valid session name (spec §6.3)`, "error");
      return null;
    }
    // A typed name that is already listed would be replaced by the PUT: ask (critic pass 3 #4).
    if (typed && this.deps.exists("session", name)
      && !this.deps.confirm(`Session ${name} already exists -- overwrite it?`)) {
      return null;
    }
    const mySeq = this.seq;
    const project = this.current(name);
    try {
      await this.put(name, project);
    } catch (e) {
      this.deps.log(`[forge] session save failed: ${errText(e)}`, "error");
      return null;
    }
    // A load or import that started during the PUT owns the stores and the name now.
    if (mySeq !== this.seq) return name;
    this.session = name;
    this.autosave.arm(name, JSON.stringify(project));
    this.observe();                          // an edit made during the PUT is saved, not lost
    return name;
  }

  /** MASTER PRESET recall (spec §9.3). Refused while a load is in flight, dropped if one started
   *  during the fetch -- it would land in the NEW session's stores, which count as edits after step
   *  9 and autosave (critic pass 3 #2) -- and validated whole before the first write (critic pass 3
   *  #12). True when applied: App highlights the name only then. */
  async recallMasterPreset(name: string): Promise<boolean> {
    if (!name) return false;
    if (this.loading) {
      this.deps.log(`[forge] a session is still loading -- pick ${name} again once it has`, "error");
      return false;
    }
    const mySeq = this.seq;
    let payload: MasterPresetPayload;
    try {
      payload = validateMasterPreset(await this.deps.api.preset("master", name));
    } catch (e) {
      this.deps.log(`[forge] failed to load master preset ${name}: ${errText(e)}`, "error");
      return false;
    }
    if (mySeq !== this.seq || this.loading) {
      this.deps.log(`[forge] a session load started while master preset ${name} was loading -- pick it again`, "error");
      return false;
    }
    applyMasterPreset(payload);
    return true;
  }

  /** MASTER PRESET SAVE, under `current` (the highlighted name) or a typed one; a typed name that
   *  is already listed asks before it is overwritten (critic pass 3 #4). The name saved, or null. */
  async saveMasterPreset(current: string): Promise<string | null> {
    let name = current;
    if (!name) {
      const answer = this.deps.prompt("Master preset name:");
      if (!answer) return null;
      if (this.deps.exists("master", answer)
        && !this.deps.confirm(`Master preset ${answer} already exists -- overwrite it?`)) {
        return null;
      }
      name = answer;
    }
    try {
      await this.deps.api.savePreset("master", name, buildMasterPresetPayload());
    } catch (e) {
      this.deps.log(`[forge] master preset save failed: ${errText(e)}`, "error");
      return null;
    }
    return name;
  }
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
    /** The session or file a load/import is fetching or applying; "" when idle (critic pass 3 #11). */
    loadingName?: string;
```

to the destructuring, `onsessionsave = () => {}, onimportv1 = () => {}, onmasterpresetsave = () => {},
loadingName = "",`; and below it:

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

and replace the SESSION select's `onchange` (M1 T10's
`onchange={(e) => onsession((e.currentTarget as HTMLSelectElement).value)}`) so the select snaps back to the
committed `session` prop after a pick — the controller moves that prop only at step 9, so a load
that fails, or is still in flight, never shows the name it has not loaded (critic pass 2 #2):

```svelte
    onchange={(e) => {
      const el = e.currentTarget as HTMLSelectElement;
      onsession(el.value);
      el.value = session;   // the committed name; a successful load changes the prop and the select follows
    }}
```

and, immediately after the SESSION select (the exact spot the removed buttons occupied) — the
`loading` note is what keeps Global Constraint #10 true while the select still shows the previous,
disarmed name during steps 5-8 (critic pass 3 #11). It is a span beside the select rather than a
transient option inside it: an option that appears and must become selected in the same flush is a
different `<select value>` behaviour from the snap-back the critic verified on Svelte 5.57.0, and a
span needs no such claim.

```svelte
  {#if loadingName}<span class="notice" data-testid="session-loading">loading {loadingName}…</span>{/if}
  <button class="save" data-testid="session-save" data-help={HELP.sessionSave}
    disabled={!!loadingName} onclick={onsessionsave}>SAVE</button>
  <button class="save" data-testid="session-import" data-help={HELP.sessionImportV1}
    onclick={() => importInput?.click()}>IMPORT</button>
  <input bind:this={importInput} data-testid="session-import-file" type="file"
    accept="application/json,.json" onchange={onImportPicked} hidden />
```

(`class="notice"` is the class M1 T15's removed status span used; M1 T15 now gives it a style rule
in `TopBar.svelte`'s `<style>` — reconcile pass 2026-09-25 — which this note reuses unchanged. Keep
that rule when the span it was written for is removed above.)
Replace the MASTER PRESET select's `onchange` (M1 T10's
`onchange={(e) => onmasterpreset((e.currentTarget as HTMLSelectElement).value)}`) the same way, so a recall that is
refused or fails never leaves the picked name highlighted — App moves `masterPreset` only once
`recallMasterPreset` applied (critic pass 3 #2):

```svelte
      onchange={(e) => {
        const el = e.currentTarget as HTMLSelectElement;
        onmasterpreset(el.value);
        el.value = masterPreset;   // the applied preset; a successful recall changes the prop
      }}
```

and change the MASTER PRESET `SAVE` button from hard-`disabled` to:

```svelte
    <button class="save" data-testid="master-preset-save" data-help={HELP.masterPresetSave} onclick={onmasterpresetsave}>SAVE</button>
```

(also delete the `<!-- Saving a master preset is M7 (spec §9.3); the copy is final here. -->`
comment above it).

In `latent-forge/src/ui/shell/__tests__/topBar.test.ts` (M1 T10), the test titled `"disables SAVE
on the master preset until M7 owns presets, and keeps the MIXDOWN frame"` is retitled `"enables
SAVE on the master preset now that M7 owns presets, and keeps the MIXDOWN frame"`, and in its body
`.disabled).toBe(true);` becomes `.disabled).toBe(false);` (delete the three-line comment above it
that says this task will do exactly that). Nothing else in that file changes (it keeps its 3 tests).
The assertion lives in M1's file because it is true at M1's end state; this task owns the flip.

**`App.svelte`'s starting state is M1 T15's end state.** The reconcile pass of 2026-09-25 made M1
T15 *extend* App instead of replacing its `<script>`, so App already holds M1 T15's `onMount`
(`project.connect()`, `installGlobalKeys({…})`, `void loadTopBar();`) and `onDestroy`; M1 T10 Step
4's three imports, seven `$state`s and `loadTopBar()`; the view-store import, as `view` (M1 uses
that name throughout now); and M1 T10's `<TopBar …>` element with every binding it lists. (Critic
pass 3 #10 found that the old literal T15 dropped all of that; this step used to restate it and say
to restore it. Nothing needs restoring now — `npm run check` passes on the unedited file.) Then:

In `latent-forge/src/App.svelte`, inside `loadTopBar()`, **delete** the auto-select line (M1 T10
Step 4, quoted below) — this is what makes `unsaved` reachable and keeps launch from ever naming a session:

```ts
      if (!session && sessions.length > 0) session = sessions[0].name;
```

and **delete** M1's own `let session = $state("");` (M1 T10 Step 4, that line verbatim): the session name now
lives in `SessionController` (step 9 is the only place it moves), and a second copy in App would
be exactly the "select says B, stores hold A" split critic pass 2 found.

`forgeApi` is imported by M1 T10's block. Then add — App holds **no** load/import/save or
master-preset logic of its own; every step of Task 9's order is `SessionController`'s — and attach
M4's settings seam to M5's source, which nothing did in production before (Global Constraint #6):

```ts
  import { cloneRenderSettings } from "./lib/forge/defaults";
  import { SessionController } from "./lib/forge/sessionController.svelte";
  import { arrangement } from "./lib/stores/arrangement.svelte";
  import { settings } from "./lib/stores/settings.svelte";

  // M4's seam (M4 T1 `attach`) + M5's source (M5 T1 `settingsSource`, never seeding): PROMPT +
  // SIGMA and ADVANCED SAMPLING now read and write the selected clip's / overlap's own `render`,
  // not always session.defaults. Once, at startup; M4 and M5 cannot import each other (§12), so
  // the composition root joins them (reconcile pass 2026-09-25).
  settings.attach(arrangement.settingsSource);
  // ... and a new clip starts from the session defaults, which follow STAGE (M4 setStage), not from
  // BASE_DEFAULTS: under POST a BASE-seeded clip showed and saved BASE's steps/sampler/schedule
  // (critic follow-up #4; Task 3's hook, tested in arrangementMixMaster.test.ts).
  arrangement.renderSeed = () => cloneRenderSettings(settings.defaults);

  // Task 9's load/import/save order lives here, unit-tested (sessionController.test.ts).
  const sessionCtl = new SessionController({
    api: forgeApi,
    log: (text, level) => view.appendLog(text, level),
    prompt: (message) => window.prompt(message, ""),
    confirm: (message) => window.confirm(message),
    // The lists the TopBar shows; a name created in another tab since they loaded is not known here.
    exists: (kind, name) =>
      kind === "session" ? sessions.some((s) => s.name === name) : masterPresets.includes(name),
  });

  // Autosave (spec §9.2): 2 s after the last change, to the current session -- only once that
  // session has been loaded or explicitly saved. observe() reads every saved field through
  // serializeProject's $state.snapshot, so this re-runs on ANY in-place edit (Global Constraint #1).
  $effect(() => {
    sessionCtl.observe();
  });

  async function saveSession() {
    const name = await sessionCtl.saveSession();
    if (name && !sessions.some((s) => s.name === name)) {
      // `updated` in epoch SECONDS (a float), the server's own unit (file mtime; WINTERMUTE 2026-09-25).
      sessions = [...sessions, { name, updated: Date.now() / 1000, n_clips: arrangement.clips.length }];
    }
  }

  // The recall is refused mid-load, dropped if a load started during its fetch, and validated whole
  // before its first write -- all in the controller (critic pass 3 #2, #12). The name is highlighted
  // only once it applied; the TopBar select snaps back until then.
  async function loadMasterPreset(name: string) {
    if (await sessionCtl.recallMasterPreset(name)) masterPreset = name;
  }

  async function saveMasterPreset() {
    const name = await sessionCtl.saveMasterPreset(masterPreset);
    if (!name) return;
    masterPreset = name;
    if (!masterPresets.includes(name)) masterPresets = [...masterPresets, name];
  }
```

Then replace the `{session}` / `onsession` / `onmasterpreset` bindings on `<TopBar>` with:

```svelte
    session={sessionCtl.session}
    loadingName={sessionCtl.loadingName}
    onsession={(name) => sessionCtl.loadSession(name)}
    onsessionsave={saveSession}
    onimportv1={(file) => sessionCtl.importProjectFile(file)}
    onmasterpreset={loadMasterPreset}
    onmasterpresetsave={saveMasterPreset}
```

- [ ] **Step 5: Wire `RightPaneModules.svelte`'s lit snapshot and M4's three handoffs**

This is the edit Tasks 2, 4 and 7 each stated an expression for, plus the two M4 handoffs that need
M5's `arrangement` and so could land in neither M4 nor M5 (§12 keeps the two from importing each
other; reconcile pass 2026-09-25, Open questions 19/20). In
`latent-forge/src/ui/shell/RightPaneModules.svelte` (M1 T12's `RightPaneModules.svelte` block — M4 never
changed it, M4 plan line 4712), add the imports:

```ts
  import { arrangement } from "../../lib/stores/arrangement.svelte";
  import { settings } from "../../lib/stores/settings.svelte";
  import { fetchLatchHeads, type LatchHeadInfo } from "../../lib/chains/latch";
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
  //  - sampling: the selected target's own settings. settings.current() reads through M5's
  //    never-seeding settingsSource once App has attached it (Step 4), so it is safe in a $derived.
  //    M4 never wired this (M4 plan line 4712); the reconcile pass put it here (Open questions 19).
  const snapshot = $derived<ModuleStateSnapshot>({
    overlap: view.selection.kind === "overlap" ? arrangement.peekOverlapParams(view.selection.key) : null,
    chain: arrangement.lanes[view.activeLane].chain,
    sampling: settings.current(view.selection),
    master: arrangement.master,
  });
  const lit = $derived(litModules(snapshot));

  // M4's handoff (M4 T11): ADVANCED SAMPLING's `latch` prop is the active lane's LatCH state --
  // but ONLY the slots whose head /info.latch_heads lists (critic pass 2 #8). M4's activeSlots
  // counts any non-"none", non-zero-weight head; chainRequest (T1) sends a head the registry does
  // not list as "none", because the server 400s on it. Passing the raw slots would show "euler
  // (forced by LatCH)" for a request that sends no active LatCH slot at all. Before the heads
  // arrive nothing is known, which is also what chainRequest would send.
  let latchHeads = $state<Record<string, LatchHeadInfo>>({});
  $effect(() => {
    fetchLatchHeads().then((h) => (latchHeads = h)).catch(() => {});
  });
  const activeLatch = $derived.by(() => {
    const chain = arrangement.lanes[view.activeLane].chain;
    return {
      latch_on: chain.latch_on,
      slots: chain.slots.filter((s) => Object.prototype.hasOwnProperty.call(latchHeads, s.head)),
    };
  });

  // M4's other handoff (M4 T11 `a2a` prop; "M5 and M7 exist to wire them"): the selected clip's
  // A2A state, which sets σ MAX. Only a clip has one; null otherwise (Open questions 20).
  const selectedA2A = $derived.by(() => {
    const sel = view.selection;
    if (sel.kind !== "clip") return null;
    const clip = arrangement.clips.find((c) => c.id === sel.id);
    return clip?.a2a ? { on: clip.a2a.on, noise: clip.a2a.noise } : null;
  });
```

and in the markup replace `<AdvancedSampling />` with:

```svelte
        <AdvancedSampling latch={activeLatch} a2a={selectedA2A} />
```

Nothing else in the file changes (`lit[id]` is already what `<ModuleShell>` reads). Known limit,
not fixed: M1's `litModules` compares `sampling` against `BASE_DEFAULTS`, so while the stage is
POST an untouched session's defaults (POST's) light ADVANCED SAMPLING (Open questions 19).

In `latent-forge/src/ui/prompt/PromptSigmaTab.svelte` (M4 T10, M4 plan lines 4575-4633), M4's
other handoff (M4 plan line 4076: "M7 passes the active lane's real two slots"): add the import

```ts
  import { arrangement } from "../../lib/stores/arrangement.svelte";
```

and, below `const target = $derived(view.selection);`:

```ts
  // M7 T9: the active lane's LatCH slots for the sigma graph's slot lanes -- only while that lane's
  // LATCH GUIDANCE is on (M4 plan line 1982: the caller passes slots when there is something to draw).
  // Unfiltered by the head registry, unlike RightPaneModules' `activeLatch`: here it only decides
  // what is DRAWN, so a deleted head can at worst draw one lane that will not be sent (Open questions 28).
  const latchSlots = $derived.by(() => {
    const chain = arrangement.lanes[view.activeLane].chain;
    return chain.latch_on ? chain.slots : [];
  });
```

and change `<SigmaColumn {target} {length} {a2a} />` to:

```svelte
    <SigmaColumn {target} {length} a2a={barA2A} slots={latchSlots} />
```

**The clip-shaped props, in the same file (critic follow-up #2).** M4 T10 left `lane`, `a2a`,
`clipHasLatent`, `onA2AToggle` and `onNoise` as props for "M5 to wire", and `BottomPane` mounts
`<PromptSigmaTab />` with none — so TargetBar's A2A toggle called M4's `() => {}` default, and M5
T12's "envelope overlay is inert until A2A is on" could never pass. M5 cannot import M4's component
and M4 cannot import M5's store (§12), so this file, which already reads `arrangement` for the
slots above, sources them from the selected clip. A prop a caller passes still wins (M4's own
component tests pass them). In the `$props()` destructuring, drop the five defaults so "not
passed" is `undefined`:

```ts
  let {
    clipName = null, lane, a2a, clipHasLatent,
    onA2AToggle, onNoise, op = null, onOp = () => {},
  }: Props = $props();
```

and below `latchSlots`:

```ts
  // M7 T9 (critic follow-up #2): the selected clip, read from M5's store -- never seeded.
  const clip = $derived.by(() => {
    const sel = view.selection;
    return sel.kind === "clip" ? (arrangement.clips.find((c) => c.id === sel.id) ?? null) : null;
  });

  /** A2A on/off through M5 (T1 `ensureA2A(id)`: creates {on: true, noise, envelope} once, a no-op
   *  if the clip already has one), then the flag in place (Global Constraint #1). */
  function toggleA2A(on: boolean): void {
    const c = clip;
    if (!c) return;
    if (on) arrangement.ensureA2A(c.id);
    if (c.a2a) c.a2a.on = on;
  }

  function setClipNoise(v: number): void {
    if (clip) arrangement.setNoise(clip.id, v);   // M5 T1: rescales the envelope proportionally
  }

  const barLane = $derived(lane ?? clip?.lane ?? 0);
  const barA2A = $derived(a2a !== undefined ? a2a : clip?.a2a ? { on: clip.a2a.on, noise: clip.a2a.noise } : null);
  // "has a latent" = one exists at all; staleness is informational only (spec §7.3).
  const barHasLatent = $derived(clipHasLatent ?? (clip ? clip.latentState !== "none" : false));
  const barOnA2AToggle = $derived(onA2AToggle ?? toggleA2A);
  const barOnNoise = $derived(onNoise ?? setClipNoise);
```

and change the `<TargetBar …>` element to:

```svelte
    <TargetBar
      {target} {clipName} lane={barLane} a2a={barA2A} clipHasLatent={barHasLatent}
      onA2AToggle={barOnA2AToggle} onNoise={barOnNoise} {op} {onOp}
    />
```

`clipName` and `op`/`onOp` stay M4's defaults on purpose: M1's `ForgeClip` has no name field
(TargetBar already falls back to the clip id) and no `op` field (Task 8 WHY item 2 — the OP select
is M9's to back). Both are recorded in Open questions 20.

`latent-forge/src/ui/prompt/__tests__/promptSigmaTabClip.test.ts` (new — the wiring guard):

```ts
// @vitest-environment jsdom
// Critic follow-up #2: PromptSigmaTab sources TargetBar's clip props from M5's arrangement, so the
// A2A toggle M5 T12's Playwright gate clicks really turns A2A on.
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { scheduleClient } from "../../../lib/sampling/scheduleClient.svelte";
import { arrangement } from "../../../lib/stores/arrangement.svelte";
import { view } from "../../../lib/stores/view.svelte";
import PromptSigmaTab from "../PromptSigmaTab.svelte";

beforeEach(() => {
  // SigmaColumn fetches /schedule and draws a canvas: the same seams as M4's PromptSigmaTab test.
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({
    ok: true, sigmas: [1, 0.5, 0], steps: 24, duration: 30, sigma_max: 1.0, dist_shift: "model", latent_len: 322,
  }), { status: 200, headers: { "content-type": "application/json" } })));
  scheduleClient.result = null;
  scheduleClient.error = null;
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
    save: () => {}, restore: () => {}, beginPath: () => {}, moveTo: () => {}, lineTo: () => {},
    stroke: () => {}, fill: () => {}, fillRect: () => {}, setTransform: () => {},
    setLineDash: () => {}, scale: () => {}, measureText: () => ({ width: 0 }), fillText: () => {},
  } as unknown as CanvasRenderingContext2D);
});

afterEach(() => {
  cleanup();
  view.clearSelection();
  arrangement.clips.splice(0, arrangement.clips.length);
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("PromptSigmaTab after M7 T9: the target bar reads the selected clip (critic follow-up #2)", () => {
  it("the A2A toggle turns the SELECTED clip's A2A on and off through M5, and NOISE shows the clip's own", async () => {
    const c = arrangement.addClip({ lane: 2, startSec: 0, durSec: 4, audio: { kind: "crop", crop_id: "A" } });
    view.select({ kind: "clip", id: c.id });
    const { getByTestId } = render(PromptSigmaTab);   // propless, exactly as BottomPane mounts it
    const toggle = getByTestId("target-a2a-toggle");
    expect(toggle.textContent).toBe("A2A OFF");
    await fireEvent.click(toggle);
    expect(c.a2a?.on).toBe(true);                     // what MasterStrip's envelope overlay reads
    expect(getByTestId("target-a2a-toggle").textContent).toBe("A2A ON");
    expect((getByTestId("target-noise") as HTMLInputElement).value).toBe(String(c.a2a!.noise));
    await fireEvent.click(getByTestId("target-a2a-toggle"));
    expect(c.a2a?.on).toBe(false);                    // off again, envelope kept
    expect(c.a2a?.envelope).toBeTruthy();
  });
});
```

- [ ] **Step 6: Run them, expect pass**

```bash
cd /home/kim/Projects/sa3-studio-review/latent-forge && npx vitest run src/lib/forge/__tests__/sessionName.test.ts src/lib/forge/__tests__/autosave.test.ts src/lib/forge/__tests__/projectSerializer.test.ts src/lib/forge/__tests__/sessionController.test.ts src/lib/help/__tests__/sessionHelp.test.ts src/ui/shell/__tests__/topBarSessions.test.ts src/ui/shell/__tests__/rightPaneModules.test.ts src/ui/prompt/__tests__/promptSigmaTabClip.test.ts
```

Expected: `Test Files  8 passed (8)` / `Tests  51 passed (51)` — 4 in `sessionName.test.ts` (3 + critic
follow-up #8's `.`/`..` case), 8 in
`autosave.test.ts`, 9 in `projectSerializer.test.ts` (3 `serializeProject` + 2 `applyProject` + 2
`validateProjectV2` + 2 `buildMasterPresetPayload`/`applyMasterPreset`), 16 in
`sessionController.test.ts` (6 from critic pass 2 + 8 from critic pass 3 + 1 stage-lock test from
the reconcile pass + critic follow-up #3's superseded-rebuild lock), 2 in `sessionHelp.test.ts`, 7 in
`topBarSessions.test.ts`, 4 in
`rightPaneModules.test.ts` (3 + the reconcile pass's M4/M5 wiring test), 1 in
`promptSigmaTabClip.test.ts` (critic follow-up #2):
4+8+9+16+2+7+4+1 = 51, counted mechanically with `grep -c '^  it('` over this task's own test blocks.

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
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M7 T9: sessions load/save/import through one SessionController sequence (validate before any store write, disarm before apply, name+arm only after apply and rebuild, SAVE refused mid-load, failed rebuild pinned out of the session, stretches re-derived, v1 keeps the stage and its sampling fields, unsupported versions refused, unsaved work and listed names not replaced without confirm, PUTs chained per name, rebuilds serialised against the server's stage), snapshot-gated 2s autosave with failed saves kept pending that never writes before a load or SAVE, M1's sessions[0] auto-select removed, master preset recall/save against spec 9.3's literal slice (validated whole, dropped if a load overtakes it), RightPaneModules lit snapshot + M4's LatCH/a2a/sampling handoffs wired, settings.attach(arrangement.settingsSource) in App, loads refused mid-STAGE-rebuild and holding settings.stageLocked, removes M1 T15's temporary SAVE/LOAD project buttons, HELP total 112"
```
---

### Task 10: Playwright fragment, recorded-response contract tests, and self-review

**WHY.** Every prior milestone's own Playwright fragment extends M1 T15's `tests/layout.spec.ts`
rather than replacing it, and none of them may weaken M1's frozen assertion that
`[data-module="overlap"]` has count 0 when nothing is selected as an overlap
(`docs/superpowers/plans/2026-09-16-latent-forge-m1-foundation-shell.md:8341-8348`). This task adds
one new spec file covering what Tasks 6-9 built, plus the mandated self-review table and Known
Incomplete note every milestone plan ends with (M6's own Task 11 is the template followed here).

**Files:**
- Create: `latent-forge/tests/sessionsFilesOverlap.spec.ts`
- Create: `latent-forge/src/lib/forge/__tests__/recordedContract.test.ts` (Step 4 — reconcile pass
  2026-09-25, WINTERMUTE's recorded-response requirement)

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
  (M5 plan lines 5853-5854). **M5's `ClipBox`/`OverlapBox` emit no `data-testid`**, so this spec
  selects `.clip[role="button"]`/`.overlap[role="button"]` — the markup those components actually
  have (the `role` keeps `.overlap` from also matching OverlapInpaint's own root `<div
  class="overlap">`). M5's own `timeline.spec.ts` now uses the same selectors (fixed at source by
  the reconcile pass of 2026-09-25; Open questions 21).
- Consumes, for Step 4's contract tests (vitest, not Playwright): M1 T6's fixture directory and
  its `preferRecorded(available, name)` rule (a recorded `<name>.json` beats
  `handmade-<name>.json`; fixture shape `{status, body}`) — **restated inline**, not imported from
  `latent-forge/mock/plugin.ts`, because M1 keeps `mock/` out of `tsconfig.json`'s `include` and a
  `src/` test importing it would pull it into `svelte-check` (critic follow-up #12) — and the recorded
  fixture names M2 T15's `record_fixtures.py` `EXPECTED` writes (`ebaf823` for the last five):
  `info`, `models_adapters`, `slots`, `forge_files_crops`, `forge_files_renders`,
  `models_control_adapters`, `forge_sessions_list`, `forge_session_get`,
  `forge_presets_latch_list`, `forge_preset_latch_get`. The four session/preset fixtures are a
  round trip on a throwaway `_fixture_probe` name, so the GET bodies are real server objects.

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
  // a never-edited overlap renders OVERLAP_DEFAULT (chroma crossfade on). OverlapBox's click has
  // already created its params (M5 T7), so this does NOT guard the body's no-seed rule --
  // rightPaneModules.test.ts's overlap case does, selecting through view.select (critic follow-up #11).
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
`loadSession` stops applying — including if T9's "replace unsaved work?" check ever fires on an
untouched launch (Playwright dismisses a `confirm` it has no handler for, so the pick would be
refused and no clip would appear; tests 1 and 2 are the end-to-end guard that nothing writes a saved
field at mount); test 2 fails at the poll if autosave stops seeing in-place edits;
test 3 if `master-preset-save` is disabled again; test 4 if a FILES `data-help` goes missing; test 6
if OVERLAP-INPAINT's body throws or renders other than `OVERLAP_DEFAULT` for a never-edited overlap.
Test 6 cannot catch the body **seeding** on first render: M5 T7's `OverlapBox` creates the params in
the click handler that selects the overlap, before the body mounts (critic follow-up #11). That rule
is guarded only by Task 9's `rightPaneModules.test.ts` overlap case, which selects with
`view.select` and asserts the params are still unstored.

- [ ] **Step 3: Run the layout suite beside it**

```bash
cd /home/kim/Projects/sa3-studio-review/latent-forge && npx playwright test tests/layout.spec.ts tests/sessionsFilesOverlap.spec.ts
```

Expected: **`17 passed`** — M1 T15's 11 layout tests plus this task's 6. M1's `each bottom tab
opens`, which used to be the one expected failure here, was fixed at source by the reconcile pass
of 2026-09-25 (it now clicks `[data-testid="bottom-tab-<id>"]`; Global Constraint #5).

Not run here, but changed by this milestone: M5's `tests/timeline.spec.ts` goes from `2 failed, 3
passed` to `1 failed, 4 passed` once Task 9 Step 5 wires TargetBar's A2A toggle through
`ensureA2A` ("the envelope overlay is inert until A2A is on" passes). The one left failing is "a
clip drags and lands snapped": no plan emits its `[data-testid="snap-select"]` (M5 T12 Step 4,
Open questions 21; critic follow-up #2).

- [ ] **Step 4: Recorded-response contract tests (vitest)**

WINTERMUTE's requirement (2026-09-25): for every route this milestone touches, one contract test
that loads the response **recorded from the real server** instead of a hand-written mock —
`fetchAdapters()` read `ckpts` through two milestones because its mock agreed with it. The
recordings are M2 **Task 15**'s `eval/forge/record_fixtures.py` (W's first DM said "Task 12"; he
corrected it on 2026-09-25 21:05 — M2's Task 12 is SAME chroma), written to
`docs/latent-forge/contract/fixtures/<name>.json` as `{status, body}`. The loader is M1 T6's own
recorded-wins rule, `preferRecorded(available, name)` (restated in the file, critic follow-up #12);
a hand-made hit counts as **not recorded**,
because the hand-made file is exactly what these tests check the client against, so every test
**skips, with the reason in its title,** until M2 T15 has run — it never passes against the mock.
A recording that is **empty** skips too, with that reason (critic follow-up #6): an empty
`models`/`slots`/`files`/`sessions`/`names` list, or a raw GET body with no keys, makes every length
and per-row check pass vacuously — M2 T15 GETs `/slots` without loading any adapter, so
`slots.json` may well be `slots: []`. FiLM has one more condition: a `models_control_adapters`
recording with no `control_mode: "scalar"` row holds nothing `fetchFilmCkpts` may return, so it
skips as well.

Which routes have a recording (M2 T15's `EXPECTED`) — one test each:

| route this milestone touches | recorded fixture | client code under test |
|---|---|---|
| `GET /info` (`latch_heads`, `film_default`) | `info` | `fetchLatchHeads` (T1), `CHAIN_DEFAULTS.film.gain` |
| `GET /models?family=adapter&loadable=1` | `models_adapters` | `fetchAdapters` (M1) |
| `GET /models?family=control_adapter` | `models_control_adapters` (capped at 20 rows) | `fetchFilmCkpts` (T2): exactly the `control_mode: "scalar"` rows, never the adapter recording (critic follow-up #1, Open questions 36) |
| `GET /slots` | `slots` | `fetchSlots` (T2) |
| `GET /forge/files` | `forge_files_crops`, `forge_files_renders` | `forgeApi.files` (M1 T5, T6's module) |
| `GET /forge/sessions` | `forge_sessions_list` (wrapped: `{ok, sessions}`) | `forgeApi.sessions()` (M1 T5; the SESSION list App's `loadTopBar` fills, M1 T10) |
| `GET /forge/sessions/{name}` | `forge_session_get` (raw, no `{ok}`) | `forgeApi.session(name)` (M1 T5; `SessionController`'s fetch, T9) |
| `GET /forge/presets/{level}` | `forge_presets_latch_list` (wrapped: `{ok, names}`) | `forgeApi.presets(level)` (M1 T5; the module preset selects, T2) |
| `GET /forge/presets/{level}/{name}` | `forge_preset_latch_get` (raw, no `{ok}`) | `forgeApi.preset(level, name)` (M1 T5; module and master recall, T2/T9) |
| `PUT /forge/sessions/{name}`, `PUT`/`DELETE /forge/presets/{level}/{name}` | **none** — M2 T15 issues them to set up the probe but saves only the GETs | no test (none invented) |

The session and preset GETs were Open questions 35; WINTERMUTE added them to M2 T15 (`ebaf823`),
recorded as a round trip on a throwaway `_fixture_probe` name (the preset is deleted afterwards;
the session stays, because M2 has no session DELETE route). The PUT/DELETE disagreements M1's mock
has (its `session_put` accepts any body, its `preset_delete` answers 200 for a missing name — M1's
reconcile note) are still not caught: nothing records a refused PUT or a missing-name DELETE.

`latent-forge/src/lib/forge/__tests__/recordedContract.test.ts`:

```ts
// The client against RESPONSES RECORDED FROM THE REAL SERVER (WINTERMUTE 2026-09-25), never the
// hand-written mock: a mock that agrees with its client is how fetchAdapters read `ckpts` for two
// milestones. Recordings: M2 T15's record_fixtures.py -> docs/latent-forge/contract/fixtures/<name>.json.
// Only a RECORDED file counts; preferRecorded()'s hand-made fallback is the thing under test, so a
// hand-made hit skips -- with the reason in the title -- and never passes.
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchLatchHeads } from "../../chains/latch";
import { forgeApi } from "../api";
import { CHAIN_DEFAULTS } from "../defaults";
import { isAudioRef, isLatentRef } from "../guards";
import { fetchAdapters, fetchFilmCkpts, fetchSlots } from "../models";

interface Fixture { status: number; body: unknown }

// M1 T6's FIXTURE_DIR and preferRecorded, RESTATED rather than imported from mock/plugin.ts: M1
// keeps mock/ out of tsconfig's include, and importing it from src/ would pull it into svelte-check
// (critic follow-up #12). Same directory (repo docs/latent-forge/contract/fixtures), same rule.
const FIXTURE_DIR = resolve(dirname(fileURLToPath(import.meta.url)), "../../../../../docs/latent-forge/contract/fixtures");
function preferRecorded(available: string[], name: string): string | null {
  if (available.includes(`${name}.json`)) return `${name}.json`;
  if (available.includes(`handmade-${name}.json`)) return `handmade-${name}.json`;
  return null;
}

function recorded(name: string): Fixture | null {
  const available = existsSync(FIXTURE_DIR) ? readdirSync(FIXTURE_DIR) : [];
  if (preferRecorded(available, name) !== `${name}.json`) return null;
  return JSON.parse(readFileSync(resolve(FIXTURE_DIR, `${name}.json`), "utf8")) as Fixture;
}

/** Where each recording keeps the rows its checks run over (critic follow-up #6): a list key, or
 *  RAW for a raw-object GET, whose own keys are its rows. An empty one makes every length and
 *  field assertion pass vacuously, so it skips instead. */
const RAW = "";
const ROWS: Record<string, string> = {
  models_adapters: "models", models_control_adapters: "models", slots: "slots",
  forge_files_crops: "files", forge_files_renders: "files",
  forge_sessions_list: "sessions", forge_presets_latch_list: "names",
  forge_session_get: RAW, forge_preset_latch_get: RAW,
};

function rowCount(name: string): number {
  const body = recorded(name)?.body;
  if (body === null || typeof body !== "object") return 0;
  if (ROWS[name] === RAW) return Object.keys(body).length;
  const rows = (body as Record<string, unknown>)[ROWS[name]];
  return Array.isArray(rows) ? rows.length : 0;
}

/** Recorded, and not empty where rows are what is under test. */
function ready(...names: string[]): boolean {
  return names.every((n) => recorded(n) !== null && (!(n in ROWS) || rowCount(n) > 0));
}

/** The test title, plus why it is skipped: a recording is missing, or holds no rows to check. */
function title(desc: string, ...names: string[]): string {
  const missing = names.filter((n) => recorded(n) === null);
  if (missing.length > 0) {
    return `${desc} [SKIPPED: ${missing.map((n) => `${n}.json`).join(", ")} not recorded yet -- run M2 T15's ` +
      `record_fixtures.py against the live server; a hand-made mock is not a contract]`;
  }
  const empty = names.filter((n) => n in ROWS && rowCount(n) === 0);
  return empty.length === 0
    ? desc
    : `${desc} [SKIPPED: ${empty.map((n) => `${n}.json has no ${ROWS[n] === RAW ? "fields" : `${ROWS[n]} rows`}`).join(", ")} ` +
      `-- re-record against a server that has some; an empty recording proves nothing]`;
}

/** Answer every fetch with the recorded response, status and all. */
function serve(f: Fixture): void {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(f.body), {
    status: f.status, headers: { "content-type": "application/json" },
  })));
}

const INFO = recorded("info");
const MODELS = recorded("models_adapters");
const SLOTS = recorded("slots");
const CROPS = recorded("forge_files_crops");
const RENDERS = recorded("forge_files_renders");
const CTRL = recorded("models_control_adapters");
const SESSIONS = recorded("forge_sessions_list");
const SESSION = recorded("forge_session_get");
const PRESETS = recorded("forge_presets_latch_list");
const PRESET = recorded("forge_preset_latch_get");
const PROBE = "_fixture_probe";   // M2 T15's throwaway session/preset name

/** How many recorded control adapters FiLM may use: control_mode "scalar" only (WINTERMUTE
 *  2026-09-25). Zero means the recording cannot show the filter works, so the FiLM test skips. */
const SCALAR_ROWS = ((CTRL?.body as { models?: { control_mode?: unknown }[] } | undefined)?.models ?? [])
  .filter((m) => m.control_mode === "scalar").length;

afterEach(() => vi.unstubAllGlobals());

describe("the client against recorded real-server responses (M2 T15 fixtures)", () => {
  it.skipIf(!INFO)(title("GET /info: every latch head has the fields LatchHeadInfo reads, and film_default.gain is CHAIN_DEFAULTS.film.gain", "info"), async () => {
    serve(INFO!);
    const heads = Object.values(await fetchLatchHeads());
    expect(heads.length).toBeGreaterThan(0);
    for (const h of heads) {
      expect(typeof h.name).toBe("string");
      expect(typeof h.family).toBe("string");
      expect(typeof h.default_gain).toBe("number");
      expect(typeof h.health).toBe("string");
      expect(Array.isArray(h.supports_kinds)).toBe(true);
      expect(typeof h.slider_min).toBe("number");
      expect(typeof h.slider_max).toBe("number");
      expect(typeof h.value_default).toBe("number");
    }
    const info = (await forgeApi.info()) as { film_default?: { gain?: unknown } };
    expect(info.film_default?.gain).toBe(CHAIN_DEFAULTS.film.gain);   // 1.75 on both sides
  });

  it.skipIf(!ready("models_adapters"))(title("GET /models: the rows are under `models`, and fetchAdapters returns every one with the path and label the MODEL select reads", "models_adapters"), async () => {
    const body = MODELS!.body as { models?: { path?: unknown }[] };
    expect(Array.isArray(body.models)).toBe(true);   // not `ckpts` -- M1's old mock
    serve(MODELS!);
    const adapters = await fetchAdapters();
    expect(adapters.length).toBeGreaterThan(0);      // ready() skipped an empty recording
    expect(adapters).toHaveLength(body.models!.length);
    for (const a of adapters) {
      expect(typeof a.path).toBe("string");
      expect(typeof a.label).toBe("string");         // model_db writes `label` (= arm); `name` is optional
    }
  });

  // FiLM (critic follow-up #1): its OWN recording, /models?family=control_adapter -- the adapter
  // recording would pass whatever query the client sent. Only control_mode "scalar" rows may come
  // back (WINTERMUTE 2026-09-25: _install_film loads a ScalarAttributeEncoder).
  const ctrlRecorded = ready("models_control_adapters");
  it.skipIf(!ctrlRecorded || SCALAR_ROWS === 0)(
    ctrlRecorded && SCALAR_ROWS === 0
      ? "GET /models?family=control_adapter: fetchFilmCkpts [SKIPPED: models_control_adapters.json has no " +
        "control_mode \"scalar\" row -- nothing FiLM can load was recorded; an empty result proves nothing]"
      : title("GET /models?family=control_adapter: fetchFilmCkpts returns exactly the control_mode \"scalar\" rows, with the path and label FILM CKPT reads", "models_control_adapters"),
    async () => {
      const body = CTRL!.body as { models: { path?: unknown; control_mode?: unknown }[] };
      serve(CTRL!);
      const film = await fetchFilmCkpts();
      expect(film.length).toBeGreaterThan(0);         // the skip condition guarantees a scalar row
      expect(film.map((f) => f.path)).toEqual(
        body.models.filter((m) => m.control_mode === "scalar").map((m) => m.path),
      );
      for (const f of film) {
        expect(typeof f.path).toBe("string");
        expect(typeof f.label).toBe("string");
      }
    },
  );

  it.skipIf(!ready("slots"))(title("GET /slots: fetchSlots keeps every resident slot, with the fields LORA/DORA reads", "slots"), async () => {
    const body = SLOTS!.body as Record<string, unknown>;
    for (const k of ["active", "backbone", "slots", "max_slots", "vram_floor_gb", "free_gb"]) {
      expect(Object.prototype.hasOwnProperty.call(body, k), `/slots has no ${k}`).toBe(true);
    }
    serve(SLOTS!);
    const out = await fetchSlots();
    expect(out.ok).toBe(true);
    expect(out.slots.length).toBeGreaterThan(0);     // ready() skipped an empty recording
    expect(out.slots).toHaveLength((body.slots as unknown[]).length);
    for (const s of out.slots) {
      expect(typeof s.index).toBe("number");
      expect(typeof s.path).toBe("string");
      expect(typeof s.label).toBe("string");
      expect(typeof s.family).toBe("string");
      expect(typeof s.cost_gb).toBe("number");
      expect(typeof s.strength).toBe("number");
    }
  });

  it.skipIf(!ready("forge_files_crops", "forge_files_renders"))(title("GET /forge/files (crops, renders): roots are {id,label,available}, rows are {root,rel,kind,size,mtime,ref} with a real ref", "forge_files_crops", "forge_files_renders"), async () => {
    for (const f of [CROPS!, RENDERS!]) {
      serve(f);
      const res = await forgeApi.files({ root: "crops", limit: 5 });   // the query is not what is under test
      expect(res.roots.length).toBeGreaterThan(0);
      expect(res.files.length).toBeGreaterThan(0);   // ready() skipped an empty recording
      for (const r of res.roots) {
        expect(typeof r.id).toBe("string");
        expect(typeof r.label).toBe("string");
        expect(typeof r.available).toBe("boolean");
      }
      for (const row of res.files) {
        expect(typeof row.root).toBe("string");
        expect(typeof row.rel).toBe("string");
        expect(["audio", "latent"]).toContain(row.kind);
        expect(typeof row.size).toBe("number");
        expect(typeof row.mtime).toBe("number");
        expect(isAudioRef(row.ref) || isLatentRef(row.ref)).toBe(true);
      }
    }
  });

  // Sessions and presets (Open questions 35, resolved by M2 T15 in ebaf823): the LIST routes wrap,
  // the GET-one routes return the stored object RAW -- and M1's request() must neither require nor
  // strip an `ok` it will not find.
  it.skipIf(!ready("forge_sessions_list"))(title("GET /forge/sessions: wrapped {ok, sessions}; each row is {name, updated in epoch SECONDS, n_clips}, the probe listed", "forge_sessions_list"), async () => {
    expect((SESSIONS!.body as Record<string, unknown>).ok).toBe(true);
    serve(SESSIONS!);
    const res = await forgeApi.sessions();
    expect(res.sessions.length).toBeGreaterThan(0);   // ready() skipped an empty recording
    for (const s of res.sessions) {
      expect(typeof s.name).toBe("string");
      expect(typeof s.updated).toBe("number");
      expect(s.updated).toBeLessThan(1e11);           // seconds, not ms (M1 T5's note, W 2026-09-25)
      expect(typeof s.n_clips).toBe("number");
    }
    expect(res.sessions.map((s) => s.name)).toContain(PROBE);
  });

  it.skipIf(!ready("forge_session_get"))(title("GET /forge/sessions/{name}: the stored project RAW, no {ok} wrapper, and forgeApi.session returns it as is", "forge_session_get"), async () => {
    const body = SESSION!.body as Record<string, unknown>;
    expect(Object.prototype.hasOwnProperty.call(body, "ok")).toBe(false);   // raw, not enveloped
    expect(body.version).toBe(2);                     // what SessionController's validate step reads first
    serve(SESSION!);
    expect(await forgeApi.session(PROBE)).toEqual(body);
  });

  it.skipIf(!ready("forge_presets_latch_list"))(title("GET /forge/presets/{level}: wrapped {ok, names}; every name a string, the probe listed", "forge_presets_latch_list"), async () => {
    serve(PRESETS!);
    const res = await forgeApi.presets("latch");
    expect(res.ok).toBe(true);
    expect(res.names.length).toBeGreaterThan(0);      // ready() skipped an empty recording
    for (const n of res.names) expect(typeof n).toBe("string");
    expect(res.names).toContain(PROBE);
  });

  it.skipIf(!ready("forge_preset_latch_get"))(title("GET /forge/presets/{level}/{name}: the stored payload RAW, no {ok} wrapper, and forgeApi.preset returns it as is", "forge_preset_latch_get"), async () => {
    const body = PRESET!.body as Record<string, unknown>;
    expect(Object.prototype.hasOwnProperty.call(body, "ok")).toBe(false);   // raw, not enveloped
    expect(body.latch_on).toBe(false);                // exactly what M2 T15 PUT
    serve(PRESET!);
    expect(await forgeApi.preset("latch", PROBE)).toEqual(body);
  });
});
```

Run it:

```bash
cd /home/kim/Projects/sa3-studio-review/latent-forge && npx vitest run src/lib/forge/__tests__/recordedContract.test.ts
```

Expected **before M2 T15 has recorded** (the state on 2026-09-25 — no recorded fixture exists
yet; `docs/latent-forge/contract/fixtures/` itself only appears with M1 T6's hand-made files): `Test Files  1 skipped (1)` /
`Tests  9 skipped (9)`, each title naming the missing recording. **After** it has, against a server
with rows in every recording: `Test Files  1 passed (1)` / `Tests  9 passed (9)`. Each recording
with nothing under test (an empty list, a raw body with no fields, or no `control_mode: "scalar"`
control adapter) turns one pass into a skip, its title saying which (critic follow-up #6) — M2
T15's `slots.json` is likely `slots: []`, so `8 passed | 1 skipped (9)` is the probable first
result. A **failure** is the point of the file — the client disagrees
with the real server — and is fixed in the client (or raised with WINTERMUTE), never by editing the
recorded fixture.

- [ ] **Step 5: Commit**

```bash
Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M7 T10: sessions/presets/FILES/OVERLAP Playwright fragment against dev:mock (seeded session, real autosave round trip, positive OVERLAP-INPAINT case via M5's dropClip); recorded-response contract tests for /info, /models (adapters + FiLM control_adapter/scalar), /slots, /forge/files and the session/preset GETs (skipped until M2 T15 records, or while a recording is empty); self-review below"
```

- [ ] **Step 6: Self-review**

| Requirement | Where | State |
|---|---|---|
| §4.6.1 OVERLAP-INPAINT: info line, 64px curve, chroma xfade, local STEPS/CFG, INPAINT OVERLAP button (no-op) | T7 `OverlapInpaint.svelte`; T10 test 6 in the real app | done |
| §4.6.2 FILES: root header, root select, filter field, draggable list | T15 (M1) real body; T6 adds the two missing `data-help`s | done |
| §6.3 FILES roots `crops`/`renders`/`uploads`, unavailable shown not hidden | T15 (M1), verified by T6's own test | done |
| §9.2 sessions: SESSION select loads through `convertProjectV1` when it says `version: 1` (v2 validated whole first; any other version refused) | T9 `SessionController.loadSession`; T10 test 1 | done |
| §9.2 no load or import can autosave or SAVE a half-applied or mismatched project | T9's numbered order in `SessionController`; `sessionController.test.ts` (16 cases: critic pass 2's 6, plus pass 3's unsupported version, superseded-then-failed load, SAVE outliving a load, apply that throws, ordered PUTs, plus the reconcile pass's M4 stage lock and its critic follow-up's lock outliving a superseded load's rebuild) | done |
| (authored guard) unsaved work and listed names are not replaced without asking; a failed autosave is retried | T9 `confirm`/`exists` deps, `createSnapshotAutosave`'s pending retry; `sessionController.test.ts`, `autosave.test.ts` | done (placeholders: `window.confirm`, Open questions 31) |
| §9.2 v1 files load through a converter | T9 IMPORT button → `SessionController.importProjectFile` → `convertProjectV1` | done (file import; the server only ever stores v2; the stage is kept) |
| §9.2 `previewAudio` re-derived on load | T9 step 6, M5's `scheduleStretch` per clip | done |
| §9.2 autosave 2s after the last change, `unsaved` until named | T9 `createSnapshotAutosave` + the `unsaved` option; T10 tests 1-2 | done |
| §9.2 `previewAudio` not serialised | T9 `serializeProject` writes `null`; T8 converter writes `null` | done |
| §9.2 `backbone` restored on load | T9 `applyProject` → `settings.stage`, `SessionController` step 8 rebuilds, a failed rebuild is pinned out of the saved session | done (`small-music*` backbones leave the stage alone and are pinned — see Open questions 7, 29) |
| §9.2 v1→v2: lane rename, `RenderSettings` default-fill | T8 `convertProjectV1` | done |
| §9.3 module presets (`latch`/`film`/`lora`/`bungee`): recall, SAVE, DEL, active lane only | T2 `modulePresets.ts` + `LaneChain.svelte` | done |
| §9.3 master scope: lane chains, clip layout+A2A (no audio), mix, master chain, schedule+prompt | T9 `buildMasterPresetPayload`/`applyMasterPreset` | done, against the literal enumeration (see Open Questions on the two-reading conflict) |
| §9.3 master recall replaces the whole slice — never half of it, never into a session loaded meanwhile | T9 `validateMasterPreset` + `SessionController.recallMasterPreset` (seq re-check after the fetch) | done |
| §6.3 session name regex validated client-side before the PUT | T9 `sessionName.ts` | done |
| M1's frozen `[data-module="overlap"]` count-0 assertion | T10 test 5, untouched | done |
| RightPaneModules' lit dots (`chain`, `master`, `overlap`, `sampling`) | T9 Step 5 | done; `sampling` added by the reconcile pass (POST lights it while untouched — Open questions 19) |
| M4 → M7 handoffs: `SigmaColumn slots`, `AdvancedSampling latch` and `a2a` | T9 Step 5 | done (`a2a` by the reconcile pass) |
| M4's settings seam wired in production (`settings.attach`) | T9 Step 4, M5 T1's `settingsSource` | done (reconcile pass); a new clip's `render` seeds from `settings.defaults` via T3's `renderSeed` (critic follow-up #4 — existing clips keep their stage, Open questions 19) |
| a session load and M4's STAGE rebuild never overlap | T9 `SessionController.begin` + M4 T9's `stageLocked`/`stageRebuilding` | done (reconcile pass; the lock outlives a superseded load's rebuild since critic follow-up #3) |
| M5 T12's A2A toggle really turns A2A on (TargetBar's clip props wired) | T9 Step 5 `PromptSigmaTab.svelte`; `promptSigmaTabClip.test.ts` | done (critic follow-up #2; `clipName`/`op` have no `ForgeClip` field — Open questions 20) |
| the lane chain goes to the server as M8's `parse_chain` takes it | T1 `chainRequest` | done (reconcile pass; M9 submits it; crossed START%/END% go out as `end_pct = start_pct` since critic follow-up #5) |
| every route this milestone touches is checked against a RECORDED real-server response | T10 Step 4 `recordedContract.test.ts` | `/info`, `/models` (adapters, and FiLM's `control_adapter`/scalar rows — Open questions 36), `/slots`, `/forge/files`, and the four session/preset GETs (Open questions 35) done — skipped until M2 T15 records, or while a recording is empty; the session/preset PUT and DELETE have no recording |

**Known incomplete.**

1. **Autosave's end-to-end test costs real time.** T10 test 1 waits 2.6 s on purpose (to prove
   launch does not write), and test 2 polls for up to 6 s for the real 2 s debounce. Together they
   add roughly 5 s to the Playwright run; the debounce's own edge cases stay in `autosave.test.ts`
   (Task 9, fake timers).
2. **The v1 store's orphaned state (`App.svelte`/`keyboard.ts`/transport possibly still reading
   `sa3-studio`'s `project` singleton instead of `arrangement`)** is a verified cross-milestone gap
   (see Task 9's WHY) that this task cannot close — rewiring the keyboard/transport is outside
   "FILES, OVERLAP-INPAINT, sessions, presets, autosave, v1→v2." M5's Normative table now says so
   instead of naming its Task 7 (reconcile pass 2026-09-25); the rewire itself is still unowned
   (Open questions 3).
3. ~~**M1's `each bottom tab opens` stays red**~~ — **fixed at source by the reconcile pass
   (2026-09-25)** (Global Constraint #5); Step 3 expects no failure.
4. ~~**FILM SCALE does not start at `/info.film_default.gain`**~~ — **closed by the reconcile pass
   (2026-09-25):** M1's `CHAIN_DEFAULTS.film.gain` is now 1.75, the server's value (Open questions 26).
5. ~~**The lit dot's real markup is untested.**~~ — **closed by the reconcile pass:** M1 T9 pins
   the dot (`[data-module-dot=<id>]` + `data-lit`), and `rightPaneModules.test.ts` reads it off the
   real `ModuleShell`; the probe is gone (Open questions 27).
6. **Two loads racing through a model rebuild are now reconciled (critic pass 3 #6), but only the
   superseded-then-failed case is tested.** Rebuilds are serialised, the newer load compares
   against the server's stage once the older rebuild settled, and a latest load that ends without
   committing lets STAGE follow the server. The "older rebuild succeeds, newer load rebuilds back"
   ordering is covered by reasoning, not by its own test.
7. ~~**M4's own STAGE control is not guarded against a load in flight**~~ — **closed by the
   reconcile pass:** M4 T1's `stageLocked`/`stageRebuilding` pair; M4 T9 offers no switch while a load
   holds the lock, and `SessionController` refuses to start a load while M4's rebuild runs (Open
   questions 32). Not covered: a rebuild M4 starts in another browser tab — the lock is per tab.
8. **A step-4 flush that fails is logged, not retried.** Once the outgoing session is disarmed, its
   flushed PUT has no armed name to fall back to (`autosave.ts`); the edit is lost if that one PUT
   fails. An in-session failure is retried (critic pass 3 #5).
9. **The "replace unsaved work?" reference is the project as last loaded, or the blank launch
   project** (critic pass 3 #3). It ignores the name, viewport, `ui` slice and model, so anything
   that writes another saved field at mount would make every first pick ask; T10 tests 1-2 would
   fail on it (see Step 2).
10. **The recorded-response contract tests skip until M2 T15 runs** (Step 4), and skip again for
    any recording that is empty. M2 T15 now records the session and preset GETs (Open questions
    35), but only the GETs: the mock's known PUT/DELETE disagreements (M1's reconcile note —
    `session_put` accepts any body, `preset_delete` answers 200 for a missing name) stay uncaught.
11. ~~**FILM CKPT lists nothing but the server default against the real server**~~ — **closed by
    the critic follow-up (#1):** `fetchFilmCkpts` asks `family=control_adapter` and keeps the
    `control_mode: "scalar"` rows (WINTERMUTE 2026-09-25), checked against the recorded
    `models_control_adapters.json` (Open questions 36).
12. **The legacy `Inspector` / `ServerPanel` modules are still mounted** (M1 T15 keeps them; critic
    follow-up #7, WINTERMUTE 2026-09-25). They go in an explicit later task, once this milestone's
    replacements have passed their Playwright gates — no plan holds that task yet (Open questions
    37).

## Open questions

1. ~~**`NEW_STRINGS` is edited by both writers in parallel; `strings.test.ts`'s `toHaveLength(87)`
   is updated once at assembly.**~~ — **closed by critic pass 1.** The "each task is independently
   green" claim was false for the whole suite: M1's `strings.test.ts` went red at Task 2's first
   entry and no step ever edited it. Every string-adding task (2, 4, 5, 6, 9) now updates that
   assertion to its cumulative total in execution order — 100, 104, 107, 109, **112** — and the
   `RightPaneModules.svelte` edit is a real step (Task 9 Step 5), not an assembly note.

2. **[Reconcile pass 2026-09-25: M5's row is corrected at source; the rewire stays unowned.]** **M5's own Normative-names table is wrong about where the v1 `project` store gets rewired/
   deleted.** It says "Task 7 is the swap point" (`2026-09-17-latent-forge-m5-timeline-fidelity.md
   :5925`); I read M5 Task 7's actual body in full and it never touches `App.svelte`, `TopBar.svelte`
   or `keyboard.ts`, and a full-file grep of the M5 plan for edits to those three files returns
   nothing. As of "M5 done, reviewed, reconciled," the v1 `project` store (`sa3-studio/src/lib/
   store.svelte.ts`) may still be what `App.svelte`'s keyboard actions and `RulerTransport.svelte`'s
   transport buttons read/write, disconnected from `arrangement`. Task 9 does not depend on
   `project` (it removes the one place in `TopBar.svelte` that referenced it), but this is a real,
   verified defect worth a line to WINTERMUTE, the same class as the `ModuleShell`/`viewStore`
   defects the brief already flags.

3. **[Reconcile pass 2026-09-25: wired — M5 T1's `settingsSource`, attached by Task 9 Step 4's App.]** **`settings.attach(source: TargetSettingsSource)` (M4) is never called in production code
   anywhere across M1/M4/M5** — every occurrence outside a `__tests__` file is zero, checked by a
   full grep of both plans. This means PROMPT + SIGMA / ADVANCED SAMPLING may currently always
   resolve to `session.defaults` regardless of the selected clip/overlap, never actually reading or
   writing a clip's own `render`. It does not block Task 9 (clip/overlap `render` fields exist and
   serialise independently of whether `settings` is wired to edit them), but it is a real
   integration gap between M4 and M5 worth flagging to WINTERMUTE.

4. **[Reconcile pass 2026-09-25: M5's Normative row is corrected at source; Task 8's defensive table is harmless and stays.]** **The v1 `SnapMode` spelling the brief and M5's own Normative table cite ("8"/"16"/"32" bare
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
Task 10). Items 18-24 were added by critic pass 1, items 25-30 by critic pass 2, items 31-34 by
critic pass 3, item 35 by the reconcile pass of 2026-09-25, which also resolved items 1-4, 8, 9,
19-21, 26, 27 and 32 at their source plans; items 36-37 by the critic follow-up to that pass
(`docs/latent-forge/RECONCILE_CRITIC_FINDINGS.md`), which, with WINTERMUTE's answers of
2026-09-25 21:05, resolved 35 and 36 and corrected 19, 20 and 32. Item 37's removal task is still
open.

1. **RESOLVED (WINTERMUTE, 2026-09-25; reconcile pass).** The old `LatchRequest`
   (`{slots: active only; rho; mu; gamma; n_iter; log_norms}` with §5.5's gains applied client-side)
   was FLATLINE's own invention, and M8 keys the request differently: `parse_chain` →
   `chain_to_request` (M8 plan lines 331-395) take **the chain object** and do the mapping
   server-side. An active-only slot list is a 400 (`chain.slots must have exactly 2 entries`), and a
   pre-multiplied `rho`/`mu` fails `parse_chain`'s 0..30 check or is scaled twice. Task 1's
   `chainRequest` now sends exactly `{latch_on, slots:[s0, s1], hparams:{rho, mu, gamma, n_iter,
   log_norms}, film_on, film, lora_on, lora, bungee_on, semitones}`, built key by key (an unknown key
   is also a 400), with an unknown head rewritten to `"none"` in place and `lora.slot: null`. No
   client display needed the gain math, so none is kept. M9 puts `chainRequest(...)` under each
   lane's `chain` key.
2. **RESOLVED (reconcile pass): `settings.attach()` is wired in production.** It was called only
   in test fixtures across M1, M4 and M5, so PROMPT + SIGMA / ADVANCED SAMPLING always resolved to
   `session.defaults`. M5 T1 now exposes `arrangement.settingsSource` (M4's `TargetSettingsSource`,
   structurally, never seeding; M5 T7's `OverlapBox` creates an overlap's params in its select
   handler), and Task 9 Step 4's `App.svelte` calls `settings.attach(arrangement.settingsSource)`.
   It lands in M7 rather than M4 or M5 because M7 is the first plan that depends on both, and §12
   keeps those two from importing each other. Tested in `rightPaneModules.test.ts`.
3. **Half resolved (reconcile pass).** M5's Normative table no longer names its Task 7 as the
   legacy v1 `project` store's swap point — no M5 task is. The store is still what M1 T15's
   keyboard actions (`installGlobalKeys`) and `project.connect()` use, beside `arrangement`; this
   milestone's Task 9 removes the one `TopBar.svelte` reference. **The keyboard rewire and the
   store's deletion have no owner** — for Kim/WINTERMUTE to assign (M9 is the obvious candidate).
4. **RESOLVED (reconcile pass).** v1 already spells `SnapMode` `"1/8"|"1/16"|"1/32"`
   (`sa3-studio/src/lib/musictime.ts:52`, re-verified); only `"off"` → `"free"` maps. M5's Normative
   row is corrected at source. Task 8's converter still accepts both spellings — harmless.
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
   backbone has no stage and leaves `stage` alone. Critic pass 2 added the pin — in both cases the
   session's own backbone stays in what is saved, so an edit no longer rewrites it; items 29-30.)
   Wiring `App.svelte`'s model state through
   `settings` is a follow-up — not attempted here, outside "sessions, master preset, autosave."
8. **RESOLVED (reconcile pass): `fetchAdapters()` reads `models`** (Global Constraints #4), its
   M1 mock test seeds the real envelope, and Task 10's contract test checks it against the recorded
   `models_adapters.json`.
9. **RESOLVED (reconcile pass): M1's tab test clicks the tab button** (Global Constraints #5), so
   Task 10's whole-suite gate expects no failure.
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
    exact type `chainRequest` consumes and both LaneChain and MasterChain need the identical shape.
    Flag if a different placement is preferred.
17. **§9.3's "three levels, four bullets" slip** — reproduced as found, shipped against the four
    bullets (matching the HTTP contract's `level` enum), not silently corrected.
18. **The spec spells S4's idle note two ways**: §5.5 (spec line 474) `chain idle — no A2A clip in
    lane`, §8.1 S4 (spec line 788) `chain idle — no A2A clip`. Shipped §5.5's, since §5.5 is the
    normative LANE CHAIN section and the longer form says which thing lacks the clip. The spec should
    be made to agree with itself; `signalPath.ts` and its test change one string if §8.1 wins.
19. **RESOLVED (reconcile pass): ADVANCED SAMPLING's lit dot is live.** M4 never edited
    `RightPaneModules.svelte` (M4 plan line 4712), and wiring it needs M5's store too, so Task 9
    Step 5 now passes `sampling: settings.current(view.selection)` — safe in a `$derived` because
    M5's `settingsSource` never seeds. **Known limit, not fixed:** M1's `litModules` compares
    `sampling` against `BASE_DEFAULTS`, so while the stage is POST an untouched session (whose
    defaults are POST's) lights the dot. The fix would be a stage-aware default in M1's
    `nonDefault.ts` (M1 T12 is frozen here; flagged). **Critic follow-up #4 (the real symptom, and
    what is fixed):** with the source attached, a clip's own `render` is what PROMPT + SIGMA and
    ADVANCED SAMPLING show, edit and serialise — and M5's `addClip` seeded it from `BASE_DEFAULTS`,
    so under POST every new clip showed and saved BASE's `steps`/`sampler_type`/`schedule`, with
    the dot dark for it and lit only for `kind: "none"`. New clips now seed from
    `settings.defaults` (Task 3's `arrangement.renderSeed`, set by App). **Still open:** (a) M4's
    `setStage` rewrites only `defaults`, so a STAGE switch leaves every existing clip on the stage
    it was created under; (b) an overlap's `render` is still seeded from `OVERLAP_DEFAULT.render`
    (BASE) by M5's `overlapParams`; (c) under POST a POST-seeded clip now lights the dot like an
    untouched session does — the same `BASE_DEFAULTS` comparison as above. Re-seeding STAGE fields
    on `setStage` (M4) is the fix for (a) and needs M4's owner to decide whether a switch may
    rewrite clip settings the user already edited.
20. **RESOLVED (reconcile pass): `AdvancedSampling`'s `a2a` prop is wired** in Task 9 Step 5 from
    the selected clip's `a2a` (`{on, noise}`), so σ MAX mirrors an A2A clip's NOISE. It needs M5's
    store and M4's component, so it lands here, beside `latch`. ~~PromptSigmaTab's own clip-shaped
    props are still unwired~~ — **wired by the critic follow-up (#2), Task 9 Step 5:** `lane`,
    `a2a`, `clipHasLatent`, `onA2AToggle` (M5 T1 `ensureA2A(id)`, then `a2a.on` in place) and
    `onNoise` (`setNoise`) come from the selected clip, a passed prop still winning; without it
    M5 T12's A2A toggle was a no-op and its envelope-overlay test could never pass.
    **Still unwired, with the reason:** `clipName` (M1's `ForgeClip` has no name; TargetBar shows
    the clip id) and `op`/`onOp` (no `op` field on `ForgeClip`, Task 8 WHY item 2 — the OP select
    changes nothing until M9 gives it a home). Kim/WINTERMUTE: say if a clip name or op field is
    wanted in the project shape.
21. **RESOLVED (reconcile pass): M5's Playwright selectors match M5's markup** — `.clip[role=
    "button"]`, `.overlap[role="button"]`, `[data-module="overlap"]`, M4's `target-a2a-toggle` — as
    Task 10's already did. M5's `[data-testid="snap-select"]` still has no emitter in any plan (M5's
    reconcile note).
22. **v1 files come in through an IMPORT button, not a server session.** Task 9 removes M1 T15's
    LOAD button with the v1 store it read, and server sessions are always v2, so §9.2's "version 1
    files … load through a converter" needed a new way in. IMPORT (a hidden file input) is the
    smallest one: the drawing has no such control, so it is spec-only, like FILES' root select. An
    imported file stays `unsaved` until SAVE names it. A v1 clip with a `serverPath` now converts to
    a `path` ref instead of being dropped (critic pass 2 #11).
23. **The client does not validate module- or master-preset names**, only session names (spec §6.3's
    regex is stated for sessions). A bad preset name comes back as the server's refusal. If §6.3
    means the same pattern for presets, `isValidSessionName` is the check to reuse.
24. **The `unsaved` label is an option inside the SESSION select**, not a span beside it — §9.2 says
    the select itself "shows `unsaved` until named". Picking a real session removes the option.
25. **`LaneChain.lora.ckpt_path` is the durable adapter identity; `lora.slot` is a transient
    resolution** (critic pass 2 #14, unconfirmed → decided here). A `/slots` index depends on what
    the server has resident now, so a saved one could point at a different adapter than `ckpt_path`
    after a restart. Every saved payload writes `slot: null` (`durableChain`, `modulePresetPayload`);
    LORA/DORA re-resolves it by path on a pick or a preset recall. **M9 must resolve from `ckpt_path`
    at submit and treat `slot` as a hint at most**; if M9 wants a stable slot handle, the server's
    `/slots` would need one keyed by path. M1's `LaneChain` type keeps the field (frozen).
26. **RESOLVED (WINTERMUTE, 2026-09-25; reconcile pass): M1's FILM default is now 1.75.** Spec
    §5.5 says SCALE defaults to `/info.film_default.gain`; the server's is `FILM_DEFAULT_GAIN = 1.75`
    (`eval/explorer_render_server.py:150`, re-verified), and M8's `CHAIN_DEFAULTS.film.gain` is
    already 1.75 (M8 plan line 268), so M1's 1.0 was the odd one out. `film.gain: null` was rejected
    because M8's `_num(None)` 400s. No session exists yet, so the "changes every saved session" cost
    is zero now. M1 T4's `CHAIN_DEFAULTS` and its test, M1 T6's `handmade-info.json`, Task 1's
    tests, Task 2's `/info` mock and `HELP.filmScale` ("Safe value: 1.75") all moved together;
    `litModules`/M5's lane dot compare against `CHAIN_DEFAULTS` itself, so an untouched lane stays dark.
27. **RESOLVED (reconcile pass): the lit dot is pinned.** M1 T9 now has one `ModuleShell`, the
    Normative `{id, title, lit, children}` one, and its dot is `[data-module-dot=<id>]` with
    `data-lit="true" | "false"` (M1 T9's Interfaces and code). T9's `rightPaneModules.test.ts`
    reads that selector off the real component; `ModuleShellProbe.svelte` is deleted from this plan.
28. **M4's `activeSlots` and T1's `chainRequest` disagree on an unknown head** (critic pass 2 #8). M4
    counts any non-`none`, non-zero-weight head (M4 plan lines 657-660); T1 sends a head
    `/info.latch_heads` does not list as `"none"`, since the server 400s on it. T9 passes ADVANCED SAMPLING only
    registry-known slots, so the forced-Euler label matches what is sent; `SigmaColumn` still gets
    the raw slots (drawing only — at worst one lane drawn that is not sent). The clean fix is one
    shared predicate taking the registry — an M4 change, flagged.
29. **A failed model rebuild during a load keeps the session's backbone and sampling defaults**
    (critic pass 2 #3). The client stage reverts (M4's rule), the saved backbone is pinned into what
    autosave writes, and the loaded `defaults` (e.g. POST's steps 8 / `pingpong`) stay as saved — so
    until the rebuild succeeds the client renders the reverted backbone with the other stage's
    defaults, the mismatch M4 plan lines 463-470 warn about. Chosen over resetting them to the
    reverted stage's defaults, because that would rewrite the user's session on the first edit;
    M4's `resetSampling` is the explicit way out. Logged when it happens. Confirm the choice.
30. **A v1 IMPORT keeps the current stage and ckpt** (critic pass 2 #7). v1 records no model;
    `convertProjectV1` still writes `backbone: "medium-base"` to fill the required field, and the
    loader ignores it (`restoreModel: false`). A later SAVE records the backbone actually loaded.
    Critic pass 3 #7 added the matching rule for `defaults`: the kept stage's `STAGE_FIELDS`
    (`steps`, `sampler_type`, `schedule`) overlay the converter's BASE values, as M4's `setStage`
    would.
31. **`confirm` and `exists` are placeholders, like item 5's `window.prompt`** (critic pass 3 #3,
    #4). App passes `window.confirm`, and `exists` reads the lists the TopBar already holds, so a
    session or preset created in another tab since those lists loaded is not known and can still be
    overwritten — `forgeApi.saveSession`/`savePreset` send a plain PUT with no create-only
    condition (M1 plan lines 1248-1251). The "unsaved work" check ignores the
    name, viewport, `ui` slice and model. Confirm the wording and whether a real dialog is wanted.
32. **RESOLVED (reconcile pass): a load and M4's STAGE rebuild never overlap.** M4 cannot import
    this milestone's controller, so the flag lives on M4's own store: `settings.stageLocked` (held by
    `SessionController` exactly as long as `loading`; M4 T9 offers no switch and starts no rebuild
    while it is set) and `settings.stageRebuilding` (held by M4 T9 while its rebuild runs;
    `SessionController.begin` refuses to start a load or import meanwhile, with a log line). One M4
    T9 test and one `sessionController.test.ts` test. Not covered: a STAGE change in another browser
    tab (the lock is per tab). **Critic follow-up #3:** "exactly as long as `loading`" left a gap —
    a superseded load's `setBackbone` can outlive the latest load, and M4 then offered STAGE while it
    ran. The lock is now released only when no load is in flight **and** no rebuild the controller
    started is pending (`releaseStageLock`); one more `sessionController.test.ts` test.
33. **The mid-load indicator is a `loading <name>…` span, not a transient option in the SESSION
    select** (critic pass 3 #11 offered either, or rewording Global Constraint #10). Chosen because
    the critic verified the select's snap-back on Svelte 5.57.0, not an option that appears and must
    be selected in the same flush; Global Constraint #10 is reworded to what is guaranteed (never
    armed or saved to, SAVE disabled) and names the indicator.
34. **A project whose `version` is neither 1 nor 2 is refused, not converted** (critic pass 3 #1).
    That includes a hand-edited v1 file that lost its `version` field; v1's own `loadJSON` refuses
    it too (`sa3-studio/src/lib/store.svelte.ts:633`), so no working v1 file is newly rejected.
35. **RESOLVED (WINTERMUTE, 2026-09-25, M2 `ebaf823`; critic follow-up).** M2 T15's
    `record_fixtures.py` now records `forge_sessions_list`, `forge_session_get`,
    `forge_presets_latch_list` and `forge_preset_latch_get`, a round trip on a throwaway
    `_fixture_probe` name, so the GET bodies are real raw objects (the preset is deleted afterwards;
    the session stays, because M2 has no session DELETE route). Task 10 Step 4 tests all four
    (`it.skipIf`, skipped while missing or empty): wrapped lists, raw GET-one bodies with no `ok`,
    `updated` in epoch seconds. **Still uncovered:** nothing records a refused PUT or a
    missing-name DELETE, so the mock's two known disagreements there (it stores a non-v2 session
    PUT, and 200s a DELETE of a missing preset) are not caught. W confirmed the recorder is M2
    **Task 15**, not Task 12.
36. **RESOLVED (WINTERMUTE, 2026-09-25; critic follow-up #1): FiLM checkpoints are `family:
    "control_adapter"` with `control_mode: "scalar"`.** There is no `film` family (`eval/ckpt_probe.py`
    `FAMILIES`), so the reconcile pass's `/models?family=film` always answered `[]`, and its claim
    that the adapter recording covered it ("same envelope") was wrong. `fetchFilmCkpts()` (Task 2)
    now asks `/models?family=control_adapter` and keeps only `control_mode === "scalar"` rows. The
    filter is **required**: every `model_db` row carries `control_mode` (`eval/model_db.py`), and
    the server's `_install_film` builds a `ScalarAttributeEncoder`, so a `melody_contour`,
    `metrical_position`, `fingerprint`, `dual_scalar` or `attribute` adapter would load the wrong
    encoder. `/info.film_default.ckpt` stays the preselected default (the "server default" option);
    that checkpoint also lives under `sa3_control_runs`, a model root, so it can appear as a row
    too. Tests: Task 2's `models.test.ts` excludes every non-scalar row, and Task 10 checks the
    client against M2 T15's `models_control_adapters` recording (capped at 20 rows), skipping when it
    has no scalar row.
37. **The legacy `Inspector` / `ServerPanel` modules stay mounted through M1 (WINTERMUTE,
    2026-09-25; critic follow-up #7) — their removal is still an open item.** M1 T15's Step 4 used to
    delete both, against M1's own Normative row and self-review ("stay mounted … through M1"). W:
    the Normative row stands, the deletion is dropped, and both go **in an explicit later task, once
    this milestone's replacements have passed their Playwright gates** — deleting working shells
    before the replacements are proven buys nothing. No plan holds that task yet: M4 never removes
    `legacy-inspector`, and M9 is not written. Nothing in this milestone depends on either being
    present or gone.

*Two writers, dispatched in parallel this time (the split is by feature area, not by layer — see
"Architecture" above), each independently re-verified every v3 line number and HELP id their tasks
cite against the real handoff file and M1's real table; no discrepancy was found in either half
beyond items 10-11 above, both already resolved with a shipped reading.*
