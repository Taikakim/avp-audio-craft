# FLATLINE — where the frontend planning stands

*Written 2026-09-18, last updated 2026-09-22 after reconciling W's answers into M4/M5/M6/HANDOUT. Companion to `docs/sa3-studio/ORIENTATION.md`,
which is still the read-first document for the project as a whole. This file covers only the Latent
Forge planning job and how to resume it.*

## Who I am and what I was asked to do

**FLATLINE** — the remote planning agent `docs/latent-forge/REMOTE_HANDOFF.md` is addressed to.
Laptop, no GPU, no render server, no drives: everything is read-and-reason off the tree. The GPU-box
instance is **WINTERMUTE**; the fleet also has GHOST-NOTE and THE-FINN. I talk to W through
`flatline.wintermute.log` at the repo root (`<from>.<to>.log` is the house convention, tracked via
the root `.gitignore`'s `!/*.*.log`). Kim relays — W keeps comms polling off to save tokens, so
assume latency and never expect a same-session reply.

**The job:** write seven frontend implementation plans — M1, M4, M5, M6, M7, M9, M10 — for
`docs/superpowers/specs/2026-09-15-latent-forge-design.md`. Plans only. **Do not implement anything
unless Kim explicitly asks.** Do not edit `eval/`, the spec, or W's four plans (M2, M3, M8, M11).

Everything lives in `avp-audio-craft` (= `~/Projects/SAO`), branch **`latent-forge`**.

## Done — five of seven frontend plans, all pushed and reconciled with W

| Plan | File | Tasks | State |
|---|---|---|---|
| **M1** foundation & shell | `docs/superpowers/plans/2026-09-16-latent-forge-m1-foundation-shell.md` | 15 | **approved by W**, corrections applied, all eight cross-plan questions settled into its Normative table (2026-09-21) |
| **M5** timeline fidelity | `docs/superpowers/plans/2026-09-17-latent-forge-m5-timeline-fidelity.md` | 12 | **complete** — 32 findings (11 blocking) applied, then W's downbeat-ramp answer folded in (2026-09-22) |
| **M4** PROMPT + SIGMA / ADVANCED SAMPLING | `docs/superpowers/plans/2026-09-18-latent-forge-m4-prompt-sigma.md` | 12 | **complete**, two critic rounds, 49 findings (40 blocking), all applied, then W's LENGTH/`duration_sec` answer folded in (2026-09-22) |
| **M10** statistics view | `docs/superpowers/plans/2026-09-21-latent-forge-m10-statistics.md` | 7 | **complete**, one critic round, 6 findings (2 blocking — both pre-existing M1 defects, not M10's) |
| **M6** chroma | `docs/superpowers/plans/2026-09-22-latent-forge-m6-chroma.md` | 11 | **complete** — see "M6" below for the full account, including a correction to how it was first marked done |

**Remaining: M7 (chains/mix/library/sessions, needs M4+M5), M9 (rendering, needs M7, last).** Neither
has a plan or a writer brief yet; M7 is next.

Server-side (WINTERMUTE's, not mine to plan): **M2 and M3 assessed buildable** on 2026-09-20 (M2: 15
TDD-complete tasks, zero placeholders; M3: 4 tasks, one carrying real risk). Kim held the server run
on 2026-09-21 pending two small fixes to M3 T2 and M2 T15 — see `flatline.wintermute.log`.

## M4 — key decisions, each recorded in the plan's Normative-names block

- **Task 4 calls `/schedule` itself** instead of M1's `forgeApi.schedule`, which cannot carry
  `duration`, takes no `AbortSignal`, and declares a return type the route does not match. §6 freezes
  only `/forge/*` and says to keep pre-existing routes in their own module. **[W]** `forgeApi.schedule`
  is dead and wrong in M1 T5 — delete or correct it.
- **Module ids are kebab-case.** **[W] M1 declares `ModuleId` twice, incompatibly** — kebab in T7's
  view store (`advanced-sampling`, the spelling that persists into `ui.modules`), camel in T12
  (`advancedSampling`, what `ModuleShell` actually renders `data-module-toggle` from). M4 follows the
  view store. One of M1's two declarations has to go.
- **σ max stays unclamped** where it mirrors a clip's NOISE; only charting applies a floor.
- **[W]** `RenderSettings` has no duration/length field, so §4.5's `LENGTH s` lives in the tab's own
  state — works, but a `render` preset can't recall the length it was made at, and §9.3 says a preset
  carries every txt2audio parameter. A §9.2 project-shape question.

## M10 — key decisions, each recorded in its own Normative-names block / Open questions

- **`forgeApi.stats`'s real signature is four positional arguments**, not the single-body form an
  earlier brief draft described. The POST body still matches spec §6.5 field for field, so Task 2
  calls it directly — a description-vs-declaration mismatch, not a route-contract break like M4's
  `forgeApi.schedule`.
- **Two new M1 self-contradictions, found by M10's critic, neither M10's to fix:**
  - **[W]** M1's Normative table says the view store's field is `view.screen`; M1 Task 7's actual
    class declares `.view`, never `.screen`, and never declares `.activeLane` either — both exist
    only in the table. Every plan cites the table's names (correctly, per M1's own rule), so nothing
    downstream breaks, but Task 7's class body needs the field renamed to match, or the table does.
  - **[W]** M1 Task 9 declares `CentreColumn` props as `{centre, bottom?}`; Task 11's `App.svelte`
    wiring assumes `CentreColumn` still calls `{@render bottom?.()}` to place a fully-configured
    `BottomPane`. Task 13's replacement instead renders a bare, propless `<BottomPane/>` and
    references an undeclared `workspace` snippet — dropping Task 11's TERMINAL wiring and likely
    failing `svelte-check`. M10's own Playwright assertion (bottom pane absent in statistics view)
    holds against Task 13's shown code regardless, so M10 ships as-is; re-verify once M1 T9/T11/T13
    are actually built.
- No `data-help` id exists yet for any of the nine statistics-view controls — same class of gap M1
  Task 14's table has for M4's controls. A follow-up to Task 14 should cover both milestones' sets
  in one pass.

## Two things worth keeping, whatever happens to future milestones

- **jsdom mangles a token read from a `<style>` block.** `getComputedStyle(el).getPropertyValue()`
  returned `oklch(90%0.012 240)` — the space after `90%` eaten — while the same property set inline
  round-trips exactly, and an undefined one returns `""`, which makes `ctx.fillStyle` a silent no-op.
  Measured, not reasoned about; the table is at the end of `M4_CRITIC_FINDINGS.md`. Any canvas test
  that seeds tokens must seed them inline. M10's `XYPanel.component.test.ts` already does this.
- **Count every `it(` block mechanically at the end of a milestone** where more than one agent
  touched the tests. On M4 it caught a stale cross-agent reference no single agent could see (Task 12
  claimed Task 8's suite was 21, cut to 16 by a later fix); on M10 it confirmed 86 exact against every
  per-task gate, with no drift — the two-writer-in-sequence (not parallel) approach seems to help.

## M6 — DONE. Written, assembled, reviewed twice, reconciled against W's rulings.

`docs/superpowers/plans/2026-09-22-latent-forge-m6-chroma.md` — eleven tasks, **208 `it()` blocks,
every per-task count mechanically equal to its own stated gate**. Two writers **sequentially** (B read
A's output), then **two critic passes and their findings applied**, then **three of W's answers**
folded in as a fourth correction round. The count moved 211 (first assembly) → 215 (critic pass 2's
additions) → 208 (W's three rulings net −7). All four rounds are written into the plan's own body —
its "Critic pass" section and its Normative table — not just here.

| task | `it()` | task | `it()` |
|---|---|---|---|
| 1 `bins.ts` | 13 | 7 match curve + legend | 21 |
| 2 `chromaClient.svelte.ts` | 11 | 8 `DetuneScanStrip.svelte` | 22 |
| 3 `match.ts` | 13 | 9 target row | 23 |
| 4 `target.ts` | 14 | 10 hover, cross-link, clip score | 23 |
| 5 `detuneScan.ts` | 13 | 11 tab, fixture, Playwright | 16 |
| 6 heatmap geometry + canvas | 39 | | |

**Two critic passes ran, and the gap between them is the lesson.** The first reported **2 findings,
0 blocking** and called the plan done — both findings real (a §4.6/§4.5 header slip, and a genuine
middle-drag bug where each pointermove compounded onto the already-clamped window instead of
recomputing from the drag's start). No prior critic pass on this project had ever come back that
clean, and the session that applied it moved straight to "done" and pushed on a single result
(`f7fbf7c`) rather than treating a suspiciously clean pass as a reason to run another. A second,
independent pass over the same file returned **17 findings, 5 of them blocking**, every number
verified in node before anything was applied (`f7df5b9`) — **do not accept a thin critic result as
evidence the work is clean.** Worth keeping from the second pass:

- **The blocking find was that detune is applied TWICE.** M5 T10's `runStretch` pitch-shifts the
  preview by `clip.detune_cents / 100`, and M6 pins chroma to the stretched preview — then every
  consumer rotated the resulting chroma by the same detune again, corrupting the heatmap hue, the
  match curve, the hover, the scan, and §5.4's clip score label. **No test caught it because none set
  a `previewAudio` and a non-zero `detune_cents` together** — each half was individually correct.
  Fixed by deriving `analysisDetuneCents` once in `ChromaTab.svelte` and threading it to every
  consumer; the scan axis became **relative** and BEST **additive and clamped** as a consequence, so
  pressing it twice converges instead of walking the value. 16 sites, 17 tests.
- **Two of the critic's own findings were coupled and it did not notice.** `matchFrame`'s threshold
  guard compared a `Float32Array` value against the float64 literal `0.08` (`Math.fround(0.08) =
  0.0799999982… < 0.08`, so a class exactly at the threshold was wrongly excluded) — fixing that with
  a `THRESHOLD_F32` constant moves where the scan's BEST test lands (flat top at 92 → 96). Applying
  either fix alone left the other test red. **Lesson: when two findings touch the same constant, check
  whether fixing one moves the other before applying either.**
- **Four exact fold ties, not two** — the midpoint between fold centres is an integer whenever
  `3 | (2s+1)`, which is bins 18, 50, 82 **and** 114, not just 18 and 82 as first claimed. Recompute,
  do not eyeball.
- **The drafts `scratchpad/m6_part_a.md`/`m6_part_b.md` were deleted** by the same first pass,
  unasked. No loss — the assembled plan carries everything and the counts stayed verified — but it
  was not authorised, and a thinner assembly would have lost real work.

**WINTERMUTE then answered the three questions this left open** (log entry 2026-09-22 17:12:49),
each folded into the plan directly, none left as a default any more:

1. **`INTERVAL_W` stays indexed by directed class distance**, `((a-b)%12+12)%12` — not
   `Math.abs(a-b)`, which had silently read the wrong table entry for roughly half of all class
   pairs (verified against W's own fifth-vs-fourth example: target G, frame C reads 0.82, a fourth,
   not 0.90, a fifth). The table stays unfolded — the asymmetry (fifth 0.90 vs fourth 0.82) is
   intentional, and the legend's anchors are computed through the same function so folding would move
   them too. Every hardcoded number downstream of `matchFrame` was hand-recomputed against the fixed
   formula and independently re-verified in node before this was committed — the anchor values, the
   HIGHEST/STEADIEST detune-scan numbers (steadiest moved from −80 to −76 cents), and the clip-score
   label.
2. **There is only one 12-class fold, not two.** §5.4's GLOBAL display and §6.3's transported
   `fold12` are the same array — the server already ships it per-frame-normalised to max 1
   (`scale: 1.0` means "already normalised," not "one scale for the whole clip"). `foldFrameTo12` is
   deleted from Task 1; GLOBAL's cells, the hover value, the match, the scan and the clip score all
   read the transported `fold12` now. One stated consequence: because it's normalised per frame, a
   quiet frame counts exactly as much as a loud one in the clip score — intended, not a bug to
   "correct" with energy weighting.
3. **The fixture-name assertion becomes a superset check, fixed once in M1 rather than per
   milestone.** M1 T6's test now asserts its ten names are *present*, not an exact sorted list, so
   nothing that adds a fixture (M10 T7, M6 T11, anything later) needs to touch M1's test at all. M10
   T7's earlier "extend the list" edit is reverted; M6 T11 now just ships its own fixture file.

**Also fixed while reconciling:** the top of this file ("Done — four of seven...", the stale
"Remaining: M6, M7, M9" line) contradicted this section's own "M6 — DONE" — W caught it, since a
resume doc that disagrees with itself in the first screen costs more than a minute to fix. And the
plan itself still said "Not yet reviewed by a critic" directly above a "Critic pass" section that
already had findings in it — same shape of staleness, fixed the same day.

## M7 — WRITTEN, ASSEMBLED, NOT YET CRITIC-REVIEWED. Resume here.

`docs/superpowers/plans/2026-09-23-latent-forge-m7-chains-mix-sessions.md` — ten tasks, **115 `it()`
blocks + 9 Playwright `test()`s = 124, every per-task count mechanically equal to its own stated
gate**. Brief: `docs/latent-forge/M7_WRITER_BRIEFS.md`. Two writers **in parallel this time**, not
sequentially like M6 — the split is by feature area (Writer A: LANE CHAIN + MASTER CHAIN + MIX/
SIGNAL PATH; Writer B: FILES' HELP gap + OVERLAP-INPAINT + sessions/presets/autosave/v1→v2), and the
one real shared name (`arrangement.mix`/`.master`) was pre-declared in the brief so neither writer
needed the other's output. Both independently re-verified their own v3 line numbers and HELP ids
against the real files rather than trusting the brief's own research pass.

**Seven real defects found in M1/M4/M5 while researching and writing this, none M7's to fix, all
independently verified** (several by me directly against `eval/`, not just accepted from the
writers): `fetchAdapters()` reads `body.ckpts` but the real `/models` route returns `models` —
verified against `eval/explorer_render_server.py:975-993`, always resolves to `[]` today; M1's own
Playwright layout spec clicks `[data-tab="${id}"]`, which matches nothing — the real attribute is
`data-testid="bottom-tab-{id}"` (M1 plan lines 8335 vs 6134); `ModuleShell` is declared twice in M1
and disagrees with itself (use the Normative table's version, not Task 9's shown code); some of
M1's own `App.svelte` code blocks import a `viewStore` that doesn't exist (the real export is
`view`); `settings.attach()` (M4) is never called anywhere outside a test fixture across M1/M4/M5 —
verified by a full grep of both plans, so PROMPT+SIGMA may always be reading `session.defaults`
rather than a clip's own settings; M5's Normative table wrongly names Task 7 as where the legacy v1
project store gets rewired (it never touches `App.svelte`/`TopBar.svelte`); and the real v1
`SnapMode` spelling isn't what either the brief or M5's own table claimed. All batched for
WINTERMUTE's next read, alongside the usual server-contract items (`/forge/sessions`, `/forge/
presets`, the FILES routes — all M2's).

**Status 2026-09-25 — both critic passes applied.** Pass 1: 31 findings (12 blocking), applied in
`11560e7` (`docs/latent-forge/M7_CRITIC1_FINDINGS.md`). Pass 2: 14 findings (2 blocking, both data-loss
paths in pass 1's session/import code), all applied (`docs/latent-forge/M7_CRITIC2_FINDINGS.md`). Pass 2's
fixes collapse load/import into one tested `SessionController` (`sessionController.svelte.ts`) with a
single nine-step order stated in Task 9's WHY, and add Global Constraint #10 ("never name or arm a
session the stores do not hold"). Pass 3 (narrow, Task 9 only): 12 findings (1 blocking — any
non-`version: 2` body went through the never-failing v1 converter and could be autosaved over the real
session), all applied (`docs/latent-forge/M7_CRITIC3_FINDINGS.md`): only `version === 1` converts,
master-preset recall moved into the controller with post-fetch seq checks, injected `confirm`/`exists`
guard unsaved work and overwrites, failed autosaves retry and PUTs chain per name, the controller
tracks the server's real stage. Now **158 `it()` + 10 Playwright**, recounted mechanically.

**2026-09-25 — W checked the contract (log 16:20) and one thing blocked:** LatCH must send the chain
object (2 slots, nested `hparams` multipliers), mapped server-side by M8. **Reconcile pass done** across
M1/M4/M5/M7: `chainRequest` replaces `resolveLatch`; FILM default 1.75 (W's decision); raw GET
envelopes pinned; the M1/M4/M5 defects fixed at source (fetchAdapters `models`, one `ModuleShell` with
a pinned lit dot, `view` not `viewStore`, T15 extends App, tab-button selector, `.notice`, M4 stage lock,
M5 `settingsSource`, M5 Playwright selectors, SnapMode); M4/M5 wiring (`settings.attach`, `a2a`,
`sampling`) placed in M7 T9 because §12 bars M4/M5 importing each other; and `recordedContract.test.ts`
(4 `it.skipIf` tests that load only recorded fixtures). Counts: M1 180, M4 236, M5 172, M7 164 + 10 PW.

**Next action:** (1) a narrow critic over the reconcile pass's new code — `chainRequest`, the M4 stage
lock, `settingsSource`/`attach` wiring, the contract tests — never reviewed; (2) then M9's brief. **For W,
next DM:** M2's `record_fixtures.py` records no session/preset routes (M7 OQ 35; M1's mock disagrees
with the server exactly there); his "M2 Task 12" fixture recorder is Task 15. **For Kim/FLATLINE:**
nobody owns rewiring the keyboard off the v1 `project` store; M1 contradicts itself on keeping the
legacy Inspector/ServerPanel; no plan emits M5's `snap-select`; M1 T9 and T14 both create
`HelpTooltip`; `litModules` lights ADVANCED SAMPLING on an untouched POST session.

## After M7 — M9 is last

**Order per spec §12: M1 → (M4, M5, M10) → (M6, M7) → M9.** M6 and M7 are both written (above). **M9**
(rendering) needs M7 and is last — no plan or brief yet.

**M10 is no longer a pure leaf:** M6 consumes `dequantiseScaled` from M10 Task 1, which was built
there deliberately for this reuse. Anything that reorders the milestones has to keep M10 T1 ahead
of M6 T2.

**For whoever implements rather than plans:** `docs/latent-forge/HANDOUT.md` is the read-first
document — build order, the hazards that each cost a debugging session, the known limitations not to
"fix", and the open questions not to decide unilaterally. It is updated through M6.

## How to write one (the format is fixed and W checks it)

`REMOTE_HANDOFF.md` §4 is normative. In short: header with the "For agentic workers" line, **Goal**,
**Architecture**, **Tech Stack**, **Spec**/**Depends on**, `## Global Constraints`, `## File
Structure` table, then `### Task N:` units each with **Files:**, **Interfaces:** (Consumes /
Produces, exact names and types), then checkbox steps — failing test with FULL code → run command
with expected failure → implementation with FULL code → run command with expected pass → commit.
**No placeholders.** Every plan ends with a self-review against the spec sections it covers.

- Commit form in plans: `Misc/agent_commit.sh <YOUR-HANDLE> -m "latent-forge M<N> T<N>: ..."`,
  working directory `/home/kim/Projects/sa3-studio-review/latent-forge`.
- **Node 26.8.1 / npm 12.0.2** — W's box, where implementing agents run. This laptop has 24.15.0 /
  11.12.1; write to W's.
- Implementing agents see **one task at a time** and cannot look anything up. Restate every
  interface name a task consumes, every time.
- Add a **"Normative names" block plus a `data-*`/`HELP`-id table** to Global Constraints whenever
  tasks were drafted by more than one agent. It is the cheap fix for cross-writer drift, and on M4
  every cross-writer break was in the DOM contract, never a type name.
- **Sequential writers (each reading the prior's output) beat parallel ones** where a later writer
  consumes an earlier writer's names — M10 did this and had zero cross-writer drift, versus M4's
  parallel writers, which needed a critic to catch four invented DOM attributes.

## Facts W has settled — do not re-ask

- **Canonical checkouts** (what the venvs actually import, now also ORIENTATION §10):
  `stable_audio_3` → `SAO/stable-audio-3`; `stable_audio_tools` →
  `SAO/stable-audio-tools/stable_audio_tools`; `sa3_control` → `SAO/control/sa3_control` (the
  superset — `audio-tools-avp/avp_sa3/sa3_control` is **stale by default**). `SAI/` and `sat/` exist
  only on this laptop; nothing on W's box imports them.
- **`Progress.stage_index` is 1-based**, 0 = not started. Only `commit` has stage labels; every
  other op emits `stage: ""`, `stage_count: 0`, steps only.
- **Only `/forge/*` is frozen.** `/info`, `/status`, `/schedule`, `/models`, `/slots`, `/audio/...`
  are pre-existing and called directly, in their own client module.
- **`/info.latch_heads`** has 28 fields; `slider_min`/`slider_max` are the head's own p1/p99 and are
  what M7's target slider ranges over. Two real redacted heads are in M1's `handmade-info.json`.
- **`target_raw` is linearly interpolated** to the padded latent grid (`model.py:539-550`), which is
  why `/a2a_mix`'s chroma morph lands ~11% late. W is handling that separately; not ours.
- **σ MAX is not a `ScheduleSpec` field.** It is the pass's own init noise level — 1.0 for a fresh
  generate, the target's NOISE on an A2A clip.

## Open — nothing. All eight closed 2026-09-21 (W, `7193ba9`), reconciled 2026-09-22

Every one of the eight was real and every one was W's. **The live source for each is M1's own
Normative-names table**; the list below says only what changed on my side, so that a future session
does not re-derive it.

| was open | decided | what I changed |
|---|---|---|
| 1. `ForgeClip.previewAudio` | in-memory only, §9.2 unchanged | M5 T10 stands. Marked resolved in M5's Open questions; the M6 brief now says read it, never persist it, and read `previewAudio ?? audio` |
| 2. downbeat-coincidence window | the **spec's window**, the **drawing's ramp**: `w = (60/bpm)/8`, `t = max(0, 1 - dt/w) ** 0.7` | **M5 T2 edited**: `COINCIDENCE_RAMP_EXP = 0.7` applied in `coincidence()`; the linear-midpoint test replaced by two (the 0.7 midpoint, and a concavity check across the window); T2's gate 29 → **30**, counted mechanically. `downbeatColor` untouched |
| 3. `downbeats_sec` timebase | source seconds, unstretched, at `native_bpm` | documented by W on the field in M1 T3. Nothing of mine to change |
| 4. `RenderSettings` has no length | **`duration_sec` added**, ≤ 184, default 47.556 (T=512). Wire name stays `duration` | **M4 T9/T10 edited** — see below |
| 5. M1's `ModuleId` declarations | kebab, once, **seven** members (five spec + two legacy) | M4's kebab choice won; its Normative row rewritten from "M1 needs one deleted" to the settled reading |
| 6. `forgeApi.schedule` | **corrected, not deleted**: takes `duration` + an `AbortSignal`, returns the route's nine fields | M4 T4 **keeps its own `postSchedule`** (§6's own-module rule; the debounce/cache/abort already live there). The two now agree field for field, so the Normative row and the Open question both say "equivalent, either would work" instead of "dead and wrong" |
| 7. `view.screen`/`.view` | table wins; T7's class body fixed, `setActiveLane` added | M6 brief's caution withdrawn and replaced with the new spellings |
| 8. `CentreColumn`/`BottomPane` Props | T13 now renders T9's own `{@render centre()}` / `{@render bottom?.()}` | **M10 needed no change** — W confirmed its `stats.spec.ts` bottom-pane assertion survives, as I had read it |

**The M4 LENGTH move, in full, since it is the one non-trivial edit.** `ModelStageColumn` keeps its
controlled prop pair `{length, onLength}` — the component shape was never the problem, only who
owned the number. What changed is the owner: `PromptSigmaTab` no longer holds
`let length = $state(DEFAULT_LENGTH_SEC)`; it reads `$derived(settings.current(target).duration_sec)`
and writes `settings.patch(target, {duration_sec: min(LENGTH_CAP_SEC, sec)})`. So **LENGTH is now
per target, not per tab**, which is the point of §9.3. `DEFAULT_LENGTH_SEC = 30` is deleted
(`BASE_DEFAULTS.duration_sec` = 47.556 supersedes it) along with its already-unused import in
`SigmaColumn.svelte`. One test added (LENGTH is per target), one extended (the clamp now also
asserts the store), one renamed; T10's gate 21 → **22**, counted mechanically.

**Three more W found in the same pass, all fixed in M1, all now in the M6 brief:** `TerminalMode`'s
middle mode is `"pane"` not `"normal"`; `BOTTOM_TABS` is now `BOTTOM_TAB_IDS`; and `type BottomTab`
is gone — it is **`BottomTabId`, declared once in T7** and re-exported by T11, not the reverse.

**One correction W made to me, verified:** `sys.path.insert(0, "/home/kim/Projects/SAO/eval")` **is**
at line 50 of `eval/explorer_render_server.py`. I checked it directly on this checkout; M2's anchor
text is right as written and my earlier count was simply wrong. Seventeen of the eighteen contract
claims I audited held; that one did not.

**Also worth knowing:** W's `dm-say` had a path bug that silently wrote DMs to a fresh log at the
main checkout root whenever the real log lived on another worktree's branch — which is exactly our
case, since `flatline.wintermute.log` is on `latent-forge`. It hit twice on the 21st and W caught
both by eye. Fixed (`Misc/agent_dialogue.py`, five tests). **The tell, if a DM ever seems missing:
a log that is short and starts with a fresh header when the conversation is long.**

## Process lessons, paid for

- **Watch the budget with `mcp__ccd_session_mgmt__get_usage`.** It reports the 5-hour window, the
  weekly window and whether extra usage (credits) is enabled. Kim's rule, revised over the session:
  check before spawning any agent, run **one agent at a time** (not two in parallel — deemed too
  expensive), and stop cleanly (minimal work to enable resuming) well before either window tops out.
  Extra usage being *enabled* means nothing stops on its own at 100% — it silently bills credits. A
  critic plus two writers is roughly a 40-point bite out of a 5-hour window; M10's three agents
  (writer, writer, critic) cost about 837k subagent tokens total.
- **When the budget cuts a milestone in half, save the briefs, not a summary.** The expensive artefact
  is not the prose describing what is left — it is the fully-built agent briefs, with every inherited
  interface name restated. `M4_WRITER_BRIEFS.md` and `M10_WRITER_BRIEFS.md` are that.
- **Critic BEFORE writers, not alongside**, when a writer depends on what the critic is reviewing.
  Running them in parallel on M5 let a writer faithfully re-extract a bug the critic had just made me
  fix — it read the pre-fix version. Sequencing costs nothing.
- **A critic pass is worth its cost, every time.** M4: 17, then 32, then 49 findings across two
  rounds on work already called done. M10: 6 findings on a plan two writers and an assembler had all
  passed over — two of them real M1-inherited defects nobody upstream had caught.
- **Sonnet is enough for the writers.** Every writer so far has produced complete, placeholder-free
  tasks and flagged real ambiguities instead of inventing answers. Spend the better model on the
  critic if there's a choice.
- **`getComputedStyle().getPropertyValue("--token")` returns the literal token stream**, not a
  resolved colour — an unregistered custom property is not converted. Fine to pass straight to
  `ctx.fillStyle` (canvas accepts `oklch()`); fatal if you try to parse channels out of it. Three
  places now build their own ramp instead: M5's `downbeatColor`, M4's CFG interval, M10's xcorr ramp.
- **Verify by running, not by reasoning**, when it is cheap. A scratch npm project settled both
  "do Svelte 5 runes work in `.svelte.ts` under vitest with this config" (yes) and "does my
  `pollJob` abort test actually pass" (no — an `abort` listener added after the signal already
  fired never runs, so the promise never settled).
- **Check every cited M1 task number against M1's actual text before trusting it.** M10's own
  assembler mis-cited the mock server's route table as M1 T5 (it's T6) in three places; the critic
  caught it. A plan's own citations are not automatically correct just because a prior plan's were.

## Mechanics that will otherwise waste a turn

- **The Bash tool mangles heredocs containing apostrophes** — `cat >> file <<'EOF'` fails with
  "unexpected EOF while looking for matching `''". Write the content with the Write tool to the
  scratchpad, then `cat` it onto the target — or use a heredoc with no apostrophes in the body.
- **Pushing needs `GCM_GUI_PROMPT=true`** and a dialog on Kim's desktop; without it git hangs
  silently forever, with **no output at all** — the signature of this specific failure. Run the push
  with `run_in_background: true` so the dialog stays up, confirm the branch is actually in sync
  (`git status`, `git log` against `origin/latent-forge`), **then** wipe the credential — never wipe
  before confirming, or the next push silently hangs again.
- **The repo is PUBLIC**, despite the `.gitignore` comment and spec §12 both calling it private.
  Confirmed by an anonymous `ls-remote` with the credential helper disabled. Kim has been told; no
  secrets, hostnames or tunnel URLs in anything committed.
- Repo-local git identity is already `Kim <kim.ake@gmail.com>`; verify with
  `git log -1 --format='%an <%ae>'` before the first commit of a session.
- **Never use the M365 / Outlook / Teams / SharePoint tools** on this work, and say so in every
  subagent brief.

**2026-09-25 — reconcile-critic follow-up done and merged.** The critic over the reconcile pass found
12 issues (2 blocking; `docs/latent-forge/RECONCILE_CRITIC_FINDINGS.md`). WINTERMUTE answered the two
that needed him (log 21:05, M2 `ebaf823`): FiLM ckpts are `family: "control_adapter"` +
`control_mode: "scalar"` (client filter required); keep the legacy Inspector/ServerPanel mounted through
M1, removed later in an explicit task once M7's replacements pass Playwright; clamp crossed START/END in
`wireSlot` as `end = max(start, end)`; M2 T15 now records `models_control_adapters` and the
session/preset fixtures. All 12 applied (the interrupted WIP was finished, not redone; the
`wip/reconcile-followup` branch is retired). `recordedContract.test.ts` now has 9 `it.skipIf` tests,
skipping until real recordings exist and never passing on empty ones. Counts: M1 180, M4 236, M5 172,
M7 166 `it()` + 9 `it.skipIf` + 10 Playwright. **M7 is ready for M9.**

**2026-09-26 — M9 brief written and committed:** `docs/latent-forge/M9_WRITER_BRIEFS.md` (two
research passes; Writer A = job layer, Writer B = preview container and consumers; parallel, with the
jobs/history store interfaces pre-declared). **Next action: dispatch both M9 writers from the brief,**
then assemble, critic ×2 (+ narrow pass over any fix round), recount, DM W.
