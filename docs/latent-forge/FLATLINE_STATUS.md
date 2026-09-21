# FLATLINE — where the frontend planning stands

*Written 2026-09-18, last updated 2026-09-21 after M10. Companion to `docs/sa3-studio/ORIENTATION.md`,
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

## Done — four of seven frontend plans, all pushed

| Plan | File | Tasks | State |
|---|---|---|---|
| **M1** foundation & shell | `docs/superpowers/plans/2026-09-16-latent-forge-m1-foundation-shell.md` | 15 | **approved by W**, corrections applied |
| **M5** timeline fidelity | `docs/superpowers/plans/2026-09-17-latent-forge-m5-timeline-fidelity.md` | 12 | pushed, awaiting W's read (32 findings, 11 blocking, applied) |
| **M4** PROMPT + SIGMA / ADVANCED SAMPLING | `docs/superpowers/plans/2026-09-18-latent-forge-m4-prompt-sigma.md` | 12 | **complete**, two critic rounds, 49 findings (40 blocking), all applied |
| **M10** statistics view | `docs/superpowers/plans/2026-09-21-latent-forge-m10-statistics.md` | 7 | **complete**, one critic round, 6 findings (2 blocking — both pre-existing M1 defects, not M10's) |

**Remaining: M6 (chroma, needs M5), M7 (chains/mix/library/sessions, needs M4+M5), M9 (rendering,
needs M7, last).** None has a plan or a writer brief yet.

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

## M6 — IN PROGRESS, half written. Resume here.

**Writer A is done, Writer B has not run.** Stopped at 86% of the 5-hour window, Kim's kill line.

- **Briefs:** `docs/latent-forge/M6_WRITER_BRIEFS.md` (committed). Eleven tasks, split 5/6.
- **Writer A's output: `scratchpad/m6_part_a.md`** — Tasks 1-5, 1902 lines, **68 `it()` blocks
  (T1:18, T2:11, T3:13, T4:14, T5:12), verified mechanically**, 8 open questions.
  **`scratchpad/` is gitignored**, so that file is on disk only (OneDrive-synced). Do not wipe it.
- **Next action:** dispatch **Writer B (Tasks 6-11)** from the brief's "Writer B" section — it reads
  `scratchpad/m6_part_a.md` first. Then assemble, then one critic, then count `it(` mechanically.
  Roughly two agents, ~20 points of a 5-hour window.

**Three of Writer A's eight open questions are load-bearing and want Kim's or W's answer, not a
default** — full text at the tail of `scratchpad/m6_part_a.md`:

1. **`INTERVAL_W` is indexed by raw class distance, not interval class.** v3's `_matchFrame`
   collapses to `INTERVAL_W[|a-b|]`, so a minor second (0.10) and a major seventh (0.22) score
   differently although both are interval class 1. §5.4 pins the twelve weights and names
   `_matchFrame` as the definition, but never restates the indexing. A ships the drawing's raw
   distance with a comment, because "fixing" it to `min(ic, 12-ic)` would change every score in the
   app — but if the drawing's version is a bug, now is the cheap moment to say so.
2. **Two different 12-class folds exist and §5.4 doesn't say which feeds the match.** §5.4's GLOBAL
   folds the three bands locally and normalises per frame; §6.3 also transports a precomputed
   `fold12` quantised once over the whole clip (so quiet frames keep less resolution, and it is not
   per-frame normalised). A ships display from the local fold and the match/scan/score path from the
   transported one, on performance grounds. If they should be identical, the match path must fold
   the bands too.
3. **The mock server has no chroma fixture, and M1 T6 asserts its handmade set is exactly ten
   files.** Same gap M10 hit on both of its routes. **Writer B's Task 11 must add
   `handmade-forge_chroma_render.json` AND extend M1 T6's ten-file assertion**, or the mock-server
   suite goes red the moment the fixture lands. This is already written into the resume path above.

The other five are settled with a shipped reading: the B/C fold boundary (took the server's
circular-nearest rule, bins 124 vs 125, since client and server must fold identically), chord
aliases (`Cmin` rejected — shipped §5.4's nine exactly), chord-quality case (`CM7` reads as C minor
7, the drawing's lowercasing), enharmonic roots (`E#`→F by arithmetic, correcting a drawing bug that
produced a garbage root), and five helper names the brief did not pre-name.

## After M6 — M7, then M9

**Order per spec §12: M1 → (M4, M5, M10) → (M6, M7) → M9.** M6 is half written (above). **M7**
(chains, mix, library, sessions — §4.6, §5.5, §9.2, §9.3) has its prerequisites in hand but no
writer brief yet; drafting one is its first step, same shape as `M6_WRITER_BRIEFS.md`. M9
(rendering) needs M7 and is last.

**M10 is no longer a pure leaf:** M6 consumes `dequantiseScaled` from M10 Task 1, which was built
there deliberately for this reuse. Anything that reorders the milestones has to keep M10 T1 ahead
of M6 T2.

**For whoever implements rather than plans:** `docs/latent-forge/HANDOUT.md` is the read-first
document — build order, the hazards that each cost a debugging session, the known limitations not to
"fix", and the open questions not to decide unilaterally. It is updated through M10.

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

## Open — waiting on W, do not decide unilaterally

1. **`ForgeClip.previewAudio`** — M5 T10 needs it for the stretched preview, but `ForgeClip` is
   pinned by §9.2 and read by M7's v1→v2 converter, so it is a spec change.
2. **Downbeat-coincidence window** — §4.3 says one 32nd note, linear; the drawing's `_dbColor`
   (v3:1155-1158) uses a quarter-beat with a `^0.7` ramp. M5 ships the spec's reading.
3. **`downbeats_sec` timebase** — `/forge/analyze` returns it unstretched at `native_bpm` while
   `offset_sec`/`dur_sec` are stretched (§7.3). M5 currently mixes them. The fix belongs in
   `ForgeClip.downbeats_sec`'s doc comment in M1's `types.ts`, and M1 is approved, so it needs W.
4. **`RenderSettings` has no length field** (from M4) — a `render` preset can't recall LENGTH.
5. **M1's two `ModuleId` declarations disagree** (from M4) — kebab vs camel.
6. **`forgeApi.schedule`** (from M4) is dead and wrong against the real `/schedule` route.
7. **M1's `view.screen`/`.view` naming mismatch** (from M10) — table vs Task 7's class body.
8. **M1's `CentreColumn`/`BottomPane` Props mismatch across Tasks 9/11/13** (from M10).

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
