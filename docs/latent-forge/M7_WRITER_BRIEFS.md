# M7 — the two writer briefs, ready to dispatch

*Written 2026-09-23 by FLATLINE. M7 = "chains, mix, library, sessions" (spec line 999): LANE CHAIN,
MASTER CHAIN, MIX + SIGNAL PATH, FILES, SESSION / MASTER PRESET, module presets, autosave,
project v1→v2. Depends on M4, M5 (both done, reviewed, reconciled).*

**This milestone is split differently from M6.** M6 split by LAYER (Writer A = math, Writer B = UI)
because the two layers had one clean, narrow contract between them. M7 splits by FEATURE AREA
instead — LANE/MASTER/MIX are one vertical slice (math + UI together), FILES/OVERLAP/SESSIONS are
another — because that is where the real seams are: RightPaneModules.svelte already imports and
renders all five right-pane modules with **no props**, so filling in LaneChain.svelte's body and
filling in Files.svelte's body touch different files and need nothing from each other. **The two
writers run in parallel, not sequentially** — check the "Names both writers inherit" section below
before you start; it pre-declares the two field names both of you read or write, so neither of you
needs the other's output to begin.

## Shared preamble — binding on both writers

- **NEVER use the m365 / Outlook / Teams / SharePoint tools.** Not for any reason.
- Work only inside `avp-audio-craft`, branch `latent-forge`. You write ONE file:
  `scratchpad/m7_part_a.md` (Writer A) or `scratchpad/m7_part_b.md` (Writer B) — task bodies only, no
  document header, starting directly with `### Task N:`.
- **Do not edit `eval/`, the spec, or M1/M4/M5/M6/M10's plans.** Where you need a fact from one of
  them, cite it with a line number and verify it against the actual file — several "facts" believed
  about M1 have turned out to be wrong or self-contradictory (see below); check, don't trust.
- **Do not touch `RightPaneModules.svelte`.** It already mounts your module by fixed name with no
  props; you do not need to edit it to make your module appear. The ONE place it does need editing
  (turning its `litModules` snapshot from hardcoded nulls into real derived state) is FLATLINE's own
  assembly task, because it needs both your domain's expression and the other writer's — each of you
  states your own expression in your own task (see "Names both writers inherit"), neither of you
  edits the file.
- **This is a TDD plan.** Each task: WHY paragraph, Files, Interfaces (restate everything you
  consume, with its source), then write-failing-tests → run → expect-failure → implement → run →
  expect-pass → commit. An implementing agent sees ONE task and can look nothing up.
- **Two real defects in M1 (approved, frozen) were found while researching this brief.** Neither
  blocks you — a reading is given for each — but both are yours to work around, not to "fix" in M1:
  1. **`ModuleShell` is declared twice, and they disagree.** Task 9's own code block
     (`ModuleShell.svelte`) takes props `{label, open, ontoggle, lit, accent, help, children}` and
     emits `data-module={label}` — but M1's own Normative-names table (which the file says wins over
     any task body) and every real consumer (`RightPaneModules.svelte`, the Playwright e2e spec)
     assume a DIFFERENT version: props `{id, title, lit, children}`, self-driven off
     `view.isModuleOpen(id)`/`view.toggleModule(id)`, emitting `data-module={id}`,
     `data-module-toggle={id}`, `data-module-body={id}`. **Use the second version** — it is what
     your module actually mounts inside, and it is what the frozen Playwright spec
     (`[data-module-toggle="lane-chain"]` etc.) already asserts against. Do not import or reference
     Task 9's shown `ModuleShell.svelte` code at all.
  2. **The view store singleton is `view`, not `viewStore`.** Task 7's real code
     (`view.svelte.ts`) exports `export const view = new ViewStore();` — there is no `viewStore`
     binding anywhere in the module. Some of Task 9/10/11's own `App.svelte` code blocks import
     `viewStore` (which does not exist) and use stale module-id spellings (`"chain"`/`"advanced"`/
     `"master"` instead of the real `ModuleId` union). If you edit `App.svelte` or `TopBar.svelte`,
     import `view` and use the real `ModuleId` spellings (`"lane-chain"`, `"advanced-sampling"`,
     `"master-chain"`) — never `viewStore`, never the camelCase ones.

## Names both writers inherit — pre-declared so neither of you waits on the other

- **`arrangement.mix: MixSpec`** and **`arrangement.master: MasterChain`** — two new `$state` fields
  on M5's `ArrangementStore` (`src/lib/stores/arrangement.svelte.ts`), seeded
  `structuredClone(MIX_DEFAULT)` / `structuredClone(MASTER_DEFAULT)` (both already declared and
  defaulted in M1 T3/T4 — do not redeclare the types or the defaults, import them). **Writer A adds
  these two fields** (Task 3, below) as a `Modify:` to M5's frozen store — the same "extend a
  finished milestone's file" pattern M4 used on M1's `AdvancedSampling.svelte` stub, except this is
  two new fields on an existing class, not a stub body. **Writer B's session serialiser reads both**
  (`ProjectV2.mix`/`ProjectV2.master`) without needing to know how they got there.
- **`arrangement.lanes[n].chain: LaneChain`** already exists, seeded from `CHAIN_DEFAULTS`, since M5
  day one (`defaultLanes()`, M5's own file) — neither of you adds this, both of you read/write it.
- **`view.activeLane: 0|1|2|3`** (M1 T7, current) — which lane's header/chain the right pane and the
  LANE CHAIN module title follow.
- **`ModuleId`** is kebab, declared once in the view store, seven members: the five spec modules plus
  `legacy-inspector`/`legacy-server`. `MODULE_IDS` (all seven, the persisted vocabulary) and
  `MODULE_ORDER`/`SpecModuleId` (the five, render order, M1 T12's `nonDefault.ts`) are DIFFERENT
  lists — do not conflate them.
- **`litModules(snapshot: ModuleStateSnapshot): Record<SpecModuleId, boolean>`** (M1 T12,
  `nonDefault.ts`) already does the "is this non-default" deep-comparison for you, keyed against
  `CHAIN_DEFAULTS`/`MASTER_DEFAULT`/`OVERLAP_DEFAULT`. Neither of you calls this directly — you each
  just need to know what expression, in your own domain, `RightPaneModules.svelte`'s snapshot should
  read for your module(s), and state it in your own task so FLATLINE can wire it at assembly. Writer
  A states the `chain`/`master` expressions; Writer B states the `overlap` expression.
- **`forgeApi`** (M1 T5, current, frozen) already has the FULL CRUD surface both of you need — do
  not add methods to it, do not write a parallel client:
  - `forgeApi.files({root?, q?, limit?})`, `forgeApi.audioUrl(ref): string`, `forgeApi.upload(file)`
  - `forgeApi.sessions()`, `forgeApi.session(name)`, `forgeApi.saveSession(name, project)`
  - `forgeApi.presets(level)`, `forgeApi.preset(level, name)`, `forgeApi.savePreset(level, name, payload)`, `forgeApi.deletePreset(level, name)` — `level` is a plain string; the route accepts
    `prompt | render | latch | film | lora | bungee | master`.
- **`fetchAdapters(): Promise<AdapterEntry[]>`** (M1 T10, `src/lib/forge/models.ts`) already calls
  `/models?family=adapter&loadable=1` for the LORA/DORA model select. `AdapterEntry = {path: string;
  name: string; label?: string; family?: string}`. **`/models?family=film` (for FILM's CKPT select)
  has no client function yet** — Writer A adds a sibling `fetchFilmCkpts()` in the same file, same
  shape, falling back to `/info.film_default` per spec 5.5.
- **`/slots` has no client function anywhere yet**, and its response shape is not in the spec or in
  M1 — verified directly against `eval/adapter_slots.py:150-160` and
  `eval/explorer_render_server.py:901-903` (the real server, not a guess): `GET /slots` →
  `{ok: true, active: number|null, backbone: string|null, slots: [{index, path, label, family,
  cost_gb, strength}], max_slots: number, vram_floor_gb: number, free_gb: number}`. Writer A adds a
  `fetchSlots()` alongside `fetchAdapters()` for LORA/DORA's "resident `/slots` first" ordering.
- **Prompt-level and render-level presets are already wired — M4 built them.** M4 Task 12 states
  explicitly ("module and master levels are M7's") that it already handles the PROMPT+SIGMA tab's
  SETTINGS PRESET (render) and prompt-only preset selects. **Neither of you touches those.** M7's
  preset work is exactly two things: the four MODULE-level presets (`latch`/`film`/`lora`/`bungee`),
  which live inside Writer A's `LaneChain.svelte` because §5.5 draws each module preset select next
  to its own toggle; and the MASTER-level preset (TopBar's existing MASTER PRESET select), which is
  Writer B's, alongside sessions.
- **§9.3 lists `bungee` as a preset level with an HTTP route, but the drawing has no preset select
  for it** (v3 557-560 has only the BUNGEE toggle and SEMITONES field, no select). Ship one anyway —
  the level exists in the frozen contract (`level ∈ ... | bungee | ...`), so an implementer following
  the spec literally needs somewhere to put it. Writer A adds a small preset select beside BUNGEE's
  toggle, undrawn but spec-required; flag it as an open question in case Kim would rather leave it
  out until the level is actually used.
- **The FILES module is NOT a stub** — M1 Task 15 already replaced it with a real implementation
  (`forgeApi.files`, `$effect`-driven fetch, draggable rows with `data-file-row`/`HELP.filesRow`,
  setting both `application/x-forge-ref` and `text/sa3-crop-id` on drag). **Read Task 15's actual
  current code first** (`src/ui/modules/Files.svelte`) before writing anything — the research pass
  for this brief could not confirm from the plan text alone whether Task 15's template already
  renders a root `<select>` and filter `<input>`, or only the internal `root`/`q` state without
  markup for them. If the markup is missing, Writer B adds it; if it already exists, Writer B's task
  reduces to verifying it against the spec's exact wording and fixing anything that disagrees. Do
  not assume either way — check the real file.

---

## The v3 handoff drawing — line ranges for this milestone (`docs/sa3-studio/design_handoff/SA3 Studio v3.dc.html`)

| region | v3 lines | `data-help` present? |
|---|---|---|
| top bar SESSION / MASTER PRESET | 25–52 | session (27), masterPreset (40); MASTER PRESET label (39) and SAVE button (43) have none |
| FILES module | 474–484 | only the draggable row (480); **the drawing has no root select or filter field at all** — §4.6.2's description of them is spec-only, not drawn |
| LANE CHAIN module | 501–563 | LatCH's ten controls all have ids; **FILM's three controls (538, 540, 544) and LORA/DORA's four (546, 548, 552, 555) have none** |
| MASTER CHAIN module | 601–620 | only LATENT NORMALISE's label (616); the toggle, LATCH HEAD label, head select and GAIN (607, 608, 610, 613) have none |
| MIX + SIGNAL PATH | 211–282 | fold (216), MIX ORDER (218), node T slider (248), signal-path row (262), expand (274); **quad-weight sliders (227–229) and both LERP/SLERP buttons (245, 246) have none** |

## The `data-help` ids that already exist — use these, invent none of them again

From M1 T14's `KEYS` (`docs/superpowers/plans/2026-09-16-latent-forge-m1-foundation-shell.md:7672-7753`),
verified line-for-line against the real v3 file — all correct as M1 cites them:

`session`(27), `masterPreset`(40), `renderButton`(45), `mixFold`(216), `mixOrder`(218),
`mixNodeT`(248), `signalPath`(262), `mixExpand`(274), `filesRow`(480), `modulePreset`(509),
`latchHead`(516), `latchTargetKind`(519), `latchTargetValue`(522), `latchWeight`(523),
`latchStartPct`(524), `latchEndPct`(525), `latchRho`(529), `latchMu`(530), `latchGamma`(531),
`latchMeanIter`(532), `latchLogNorms`(534), `bungeeSemitones`(560), `latentNormalise`(616),
`overlapChromaXfade`(460), `overlapOverride`(464), `overlapSteps`(466), `overlapCfg`(467). Also
`filmTarget` in M1's `NEW_STRINGS` block — a brand-new string for §10 X9's added TARGET field, not
an extracted id, and it does not cover FILM's other three controls.

## Controls with NO id anywhere — you author brand-new strings for these, `NEW_STRINGS`-style

**FILM**: the toggle (538), the module preset select (540), SCALE (544). **LORA/DORA**: the toggle
(546), the module preset select (548), the model select (552), SCALE (555). **MASTER CHAIN**: the
LATCH toggle (607), the LATCH HEAD label (608), the head select (610), GAIN (613). **FILES**: the
root select and the filter field (neither exists in the drawing at all — spec-only controls).
**MIX**: the quad-weight sliders (227–229), LERP (245), SLERP (246). **Top bar**: the MASTER PRESET
SAVE button (43). **BUNGEE**: its new preset select (undrawn, see above). Write these the way M1's
own `NEW_STRINGS` block does — plain, in the handoff's voice, no `// handoff: "..."` comment since
there is no original to quote.

---

## The numbers §5.5 pins — copy them exactly, do not re-derive

- **Mapping to the server's LatCH request** (verbatim, spec 468–471): for the active slots in order,
  `gain_k = head.default_gain · weight_k`; request `rho = ρ · gain_0`, `mu = μ · gain_0`, `gamma`,
  `n_iter`, `log_norms` passed through unmodified. With ρ = μ = weight = 1 this reproduces today's
  server defaults exactly. **A slot whose head is `"none"` or whose weight is 0 is omitted from the
  request entirely** — not sent with a zero weight.
- Slot ranges: WEIGHT 0–50 (default 1), START %/END % 0–1 (defaults 0/0.6). Shared hyperparameters:
  ρ VARIANCE 0–30 (1), μ MEAN 0–30 (1), γ NOISE 0–20 (0.3), MEAN ITER 1–80 (4).
- FILM: SCALE 0–2 (→ gain, default from `/info.film_default.gain`), TARGET 0–16 onsets/s (default
  4.0, §10 X9 — a control the drawing never had).
- LORA/DORA: SCALE 0–1 (→ strength).
- BUNGEE: SEMITONES ±24.
- MASTER CHAIN: GAIN 0–120 (default 64).
- **The lane chain applies during that lane's A2A pass (§8.1 S4–S5).** A lane with an active chain
  but no A2A clip shows `chain idle — no A2A clip in lane` in the signal path — this exact string,
  lowercase, is the one piece of copy the spec pins verbatim for the SIGNAL PATH list.
- **Autosave: 2 s after the last change.** SESSION select shows `unsaved` until the project is named
  (§9.2). Session name regex `^[A-Za-z0-9._-]{1,80}$` (§6.3) — validate client-side before the PUT,
  since the server 400s otherwise.
- **Master preset scope** (§9.3, verbatim): "the whole project minus `clips[*].audio` refs and
  `renders` — every lane chain, clip layout (positions, trims, BPM, detune, A2A settings), mix order
  and node values, master chain, sampling schedule and default prompt." Recall replaces that whole
  slice; module recall applies to the **active lane only**.
- **§9.3's own heading says "three levels" but lists four** (prompt, render, module, master) — a
  spec-internal slip, not yours to silently "correct." Cite it as found in your open questions;
  ship against the four bullets, which is what the HTTP contract's `level` enum also has.

---

## Two constraints that shape the whole milestone

1. **You are filling in real seams M1/M4/M5 already left, not designing from scratch.** Every type
   (`LaneChain`, `MasterChain`, `MixSpec`, `OverlapParams`, `ProjectV2`, their defaults) is already
   declared and defaulted; every store field you need either already exists (`arrangement.lanes[n]
   .chain`) or is pre-declared above (`arrangement.mix`/`.master`); the entire API client surface
   already exists (`forgeApi`). If you find yourself declaring a type this brief already names, you
   are re-deriving something — stop and use the real one.
2. **The v1→v2 converter's actual v1 SOURCE shape is not in this brief, because no research pass has
   read it yet.** `project.toJSON()`/`project.loadJSON()` on the legacy `src/lib/store.svelte.ts`
   (or wherever the pre-M1 project store lives — check both `latent-forge/` and the original
   `sa3-studio/` tree, since M1 renamed the app directory) is the real v1 shape you convert FROM.
   Writer B's converter task must locate and read that file directly before writing a single test —
   do not guess the v1 JSON shape from the spec's one paragraph (867–869) alone, which only names
   the lane rename and the `RenderSettings` default-fill, not the full shape.

---

## Writer A — Tasks 1-5: LANE CHAIN, MASTER CHAIN, MIX + SIGNAL PATH

Read this whole brief first, especially "Names both writers inherit." Do not read Writer B's brief
section or wait for its output — you do not depend on it.

**Task 1 — `src/lib/chains/latch.ts`, pure.** `resolveLatch(chain: LaneChain, heads: Record<string,
LatchHeadInfo>): LatchRequest | null` implementing the mapping formula above exactly, returning
`null` when `!chain.latch_on` or every slot is omitted (head `"none"` or weight 0). Also
`chainIsIdle(chain: LaneChain, hasA2AClip: boolean): boolean` for the SIGNAL PATH's
`chain idle — no A2A clip in lane` note (true iff the chain has any active feature on — LatCH, FiLM,
LoRA or Bungee — and `!hasA2AClip`). You will need `/info.latch_heads`' real shape (`name · family`
label, `health`, `supports_kinds`, `slider_min`/`slider_max`/`value_default`) — restate it from M1's
`/info` typing if declared, or from spec §5.5/§6.4 directly, and say which.

**Task 2 — `src/ui/modules/LaneChain.svelte`**, replacing M1's stub in full: LATCH GUIDANCE toggle +
module preset select (`forgeApi.presets("latch")`/`preset`/`savePreset`/`deletePreset`, direct — no
intermediate client), two LatCH slots (head/kind/target/weight/start%/end%), the shared hyperparameter
row, FILM (toggle + preset + CKPT select via the new `fetchFilmCkpts()` + SCALE + TARGET), LORA/DORA
(toggle + preset + model select via `fetchSlots()`-then-`fetchAdapters()` + SCALE), BUNGEE (toggle +
SEMITONES + the undrawn preset select noted above). Every control writes through
`arrangement.lanes[view.activeLane].chain` in place (a `$state` object — mutate fields, do not
reassign the lane). State the exact `chain: $derived(...)` expression `RightPaneModules.svelte`'s
snapshot should use for FLATLINE's assembly task.

**Task 3 — `src/lib/mix/mixMath.ts` + `src/lib/mix/signalPath.ts`, pure, plus the `arrangement.mix`/
`.master` field addition.** `mixMath.ts`: node-tree resolution for `MIX ORDER` (`tree` = `(1+2)+(3+4)`,
`cascade` = `((1+2)+3)+4`, `quad` = `weighted 4-way, lerp only`), each node's `{interp: "lerp"|"slerp";
t: number}` from `MixSpec.nodes`. `signalPath.ts`: derive the nine §8.1 stage rows (label, lit/dimmed,
note) from the current lanes' chains, overlaps, mix and master state — cite §8.1's own nine stage
labels rather than inventing new ones. **Modify `src/lib/stores/arrangement.svelte.ts`**: add
`mix = $state<MixSpec>(structuredClone(MIX_DEFAULT))` and
`master = $state<MasterChain>(structuredClone(MASTER_DEFAULT))` fields — nothing else in that file
changes; M5's existing fields, tests and the `overlaps` derivation are untouched.

**Task 4 — `src/ui/modules/MasterChain.svelte`**, replacing M1's stub: LATCH HEAD toggle + head
select + GAIN (0–120, default 64), LATENT NORMALISE toggle (default on). Writes through
`arrangement.master` in place. State the `master: $derived(arrangement.master)` expression for
assembly.

**Task 5 — `src/ui/mix/MixSignalPath.svelte`** (new) + the `BottomPane.svelte` mount (the same
`data-region="bottom-tab-body"` edit pattern M4/M6/M10 used for their own tabs) + your own Playwright
fragment covering LANE CHAIN, MASTER CHAIN and MIX + SIGNAL PATH's reachability and basic behaviour
(the tab renders, the fold/summary toggle works, a lane's chain dot lights when non-default). Compose
`mixMath`/`signalPath` into the MIX ORDER select, node boxes or quad sliders (per `isQuad`), the
SIGNAL PATH list, the fold toggle, and a `▸ MIXDOWN` button that is **UI only** — clicking it in this
milestone should be a no-op with a comment saying M9 wires the actual `commit` job submission, the
same boundary as OVERLAP-INPAINT's render button (Writer B's Task 7).

Write Tasks 1-5 to `scratchpad/m7_part_a.md`, starting directly with `### Task 1:`.
Reply one line: `A: tasks=1-5 lines=<n> its=T1:<n>,T2:<n>,T3:<n>,T4:<n>,T5:<n> openq=<n>`.

---

## Writer B — Tasks 6-10: FILES, OVERLAP-INPAINT, sessions, presets, autosave, v1→v2

Read this whole brief first, especially "Names both writers inherit." Do not read Writer A's brief
section or wait for its output — you do not depend on it, except that your session serialiser cites
`arrangement.mix`/`.master` by the exact names pre-declared above (you do not need Writer A's file to
exist yet to write your own tests against those field names).

**Task 6 — extend `src/ui/modules/Files.svelte`.** Read Task 15's actual current file first (per
"Names both writers inherit," above) — it already fetches and renders draggable rows; your job is
whatever of §4.6.2's "root header, root select, filter field" is not already there. The mock's
`/forge/files` roots are `crops`/`renders`/`uploads` (§6.3) — an unavailable root
(`available: false`) is shown, not hidden or errored.

**Task 7 — `src/ui/modules/OverlapInpaint.svelte`**, replacing M1's stub: info line (which overlap,
its two clip names), the 64 px CROSSFADE CURVE editor (reuse M5's envelope geometry/component rather
than rebuilding one — cite the exact M5 file and export), CHROMA CROSSFADE toggle (default on),
LOCAL STEPS/CFG toggle (default off) + STEPS (drag 1–100, default 28) + CFG (drag 0–64, default 3.0),
and the `▸ INPAINT OVERLAP` button. **The button is UI only in this milestone** — M1's own table says
so explicitly ("its `▸ INPAINT OVERLAP` button wired in M9") — clicking it is a no-op with a comment
saying M9 wires the actual preview-job submission. Reads/writes through
`arrangement.overlapParams(key)`/`setOverlapParams(key, patch)` (both already exist, M5). State the
`overlap: $derived(...)` expression for `RightPaneModules.svelte`'s snapshot (`null` when
`view.selection.kind !== "overlap"`, else the current `OverlapParams` for the selected key).

**Task 8 — the v1→v2 project converter, pure function(s).** First, locate and read the actual legacy
v1 project shape (`project.toJSON()`/`loadJSON()` — check both `latent-forge/src/lib/` and the
pre-rename `sa3-studio/` tree for wherever this still lives) and restate its real fields in your
Interfaces block, not a guessed shape. Then write `convertProjectV1(raw: unknown): ProjectV2`
covering everything §9.2/M5's Normative table name: lanes `drums/bass/other/vocals` → `LANE 1..4`;
`clip.render` → `RenderSettings` with defaults filled (`cloneRenderSettings(BASE_DEFAULTS)`, M1 T4);
`snap` `"off"` → `"free"`, `"8"/"16"/"32"` → `"1/8"/"1/16"/"1/32"`; `ForgeClip.previewAudio` is
**never read or written** by the converter (in-memory only, per M5's Normative table). A v1 file with
no `mix`/`master`/`chain` data at all should convert to `MIX_DEFAULT`/`MASTER_DEFAULT`/
`CHAIN_DEFAULTS` per lane, not throw.

**Task 9 — sessions, master preset, autosave.** Wire `TopBar.svelte`'s existing SESSION select (it
already lists names and calls a no-op `onsession`) to actually load: `forgeApi.session(name)`, run the
result through `convertProjectV1` when it isn't already `version: 2`, apply it to `arrangement`/
`settings`/`view`. Wire save (a new explicit action, not the select itself — the select only chooses
*which* name is highlighted per M1's own comment) through `forgeApi.saveSession(name, project)`,
serialising the live stores into `ProjectV2` (including `arrangement.mix`/`.master` by the names
pre-declared above). Wire the MASTER PRESET select the same way through
`forgeApi.presets("master")`/`preset`/`savePreset`/`deletePreset`, building/applying exactly §9.3's
master-slice definition (quoted above). **Autosave**: a 2 s debounce after the last change, writing to
the *current* session name; the SESSION select shows `unsaved` until the project has one. **Remove**
the temporary `saveProject`/`loadProject` download/upload buttons and their handlers (M1's own
comment says these are temporary, replaced by this exact task) — say so in your Files list as a
`Modify:` that deletes code, not just adds it.

**Task 10 — your own Playwright fragment + self-review.** Cover: a session appears in the SESSION
select and loading it changes the arrangement; autosave fires after an edit and the `unsaved` label
clears once named; the MASTER PRESET SAVE button is enabled and a saved preset round-trips; the FILES
module lists mock files and they remain draggable after your Task 6 changes; OVERLAP-INPAINT's module
frame renders only while an overlap is selected (do not weaken M1's frozen `[data-module="overlap"]`
count-0 assertion). Finish with a self-review table against §9.2, §9.3 and §6.3, plus a **Known
incomplete** note.

Write Tasks 6-10 to `scratchpad/m7_part_b.md`, starting directly with `### Task 6:`.
Reply one line: `B: tasks=6-10 lines=<n> its=T6:<n>,T7:<n>,T8:<n>,T9:<n>,T10:<n> openq=<n>`.

---

## After both

1. Assemble: header + Global Constraints + File Structure + "Status of this plan" (FLATLINE writes
   these) + both parts, open questions merged into one section.
2. **FLATLINE makes the one `RightPaneModules.svelte` edit** neither writer touches: turn the
   `litModules` snapshot's `chain`/`master` (from A) and `overlap` (from B) from hardcoded nulls into
   the derived expressions each writer stated in their own task.
3. Add a **Normative names and decisions** block including the `data-*`/`data-testid`/`HELP`-id
   table — this milestone invents more brand-new HELP strings than any before it (FILM, LORA/DORA,
   MASTER CHAIN's three, FILES' two, the mix quad/LERP/SLERP controls, the master-preset SAVE
   button, BUNGEE's preset) — get every one of them into the table so a critic can check both
   directions in one pass.
4. **Run one critic over the whole plan, apply findings, run a second — do not stop after a clean
   first pass.** M6's own history is the reason: a first pass that returns unusually few findings is
   a reason to run another, not a reason to call the milestone done.
5. Route anything that touches the server contract as one batch to WINTERMUTE at assembly time —
   `/forge/sessions`, `/forge/presets`, the FILES routes are all M2's, and W checks them field for
   field the way he checked `/forge/chroma` for M6. Also flag the two M1-internal defects (the
   `ModuleShell` duplicate declaration, the `viewStore`/`view` mismatch) and the §9.3 "three levels,
   four bullets" slip — none of these are M7's to fix, all are worth a line in the DM.
6. Verify the counts mechanically (`grep -c '  it('` against every stated gate) before calling it
   done, the same as every milestone so far.
