# FLATLINE — where the frontend planning stands

*Written 2026-09-18 before a context compact, for my next self. Companion to
`docs/sa3-studio/ORIENTATION.md`, which is still the read-first document for the project as a
whole. This file covers only the Latent Forge planning job and how to resume it.*

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

## Done

| Plan | File | State |
|---|---|---|
| **M1** foundation & shell, 15 tasks, ~9k lines | `docs/superpowers/plans/2026-09-16-latent-forge-m1-foundation-shell.md` | **approved by W**, corrections applied |
| **M5** timeline fidelity, 12 tasks, ~6k lines | `docs/superpowers/plans/2026-09-17-latent-forge-m5-timeline-fidelity.md` | pushed, awaiting W's read |

| **M4** PROMPT + SIGMA, 12 tasks planned | `docs/superpowers/plans/2026-09-18-latent-forge-m4-prompt-sigma.md` | **Tasks 1-3 only**, critic-reviewed, 8 blocking findings fixed |

M1 and M5 are pushed. M4 is partial — see below.

## M4 — done

**Complete and reviewed**, 6199 lines, twelve tasks, `docs/superpowers/plans/2026-09-18-latent-forge-m4-prompt-sigma.md`.
Two critic rounds, 49 findings, 40 blocking, all applied; the second round is kept in full in
`docs/latent-forge/M4_CRITIC_FINDINGS.md`. Test counts verified mechanically rather than by eye.

Three decisions taken while finishing it, each recorded in the plan's Normative-names block:

- **Task 4 calls `/schedule` itself** instead of M1's `forgeApi.schedule`, which cannot carry
  `duration`, takes no `AbortSignal`, and declares a return type the route does not match. §6 freezes
  only `/forge/*` and says to keep pre-existing routes in their own module, so this needs no edit to
  an approved plan. **[W]** `forgeApi.schedule` is now dead and wrong in M1 T5 — delete or correct it.
- **Module ids are kebab-case.** **[W] M1 declares `ModuleId` twice, incompatibly** — kebab in T7's
  view store (`advanced-sampling`, and it is this spelling that persists into the project JSON's
  `ui.modules`), camel in T12 (`advancedSampling`), with `ModuleShell` rendering
  `data-module-toggle={id}` from the camel list. No plan can be correct against both. M4 follows the
  view store. One of M1's two declarations has to go.
- **σ max stays unclamped** where it mirrors a clip's NOISE; only charting applies a floor.

**A third question for W**, alongside `ForgeClip.previewAudio` and the downbeat pair from M5:
`RenderSettings` has no duration or length field, so §4.5's `LENGTH s` lives in the tab's own state.
It works, but a `render` preset then cannot recall the length it was made at, and §9.3 says a render
preset carries the txt2audio parameters. A §9.2 project-shape question, not a client detail.

## Two things worth keeping, whatever happens to M4

- **jsdom mangles a token read from a `<style>` block.** `getComputedStyle(el).getPropertyValue()`
  returned `oklch(90%0.012 240)` — the space after `90%` eaten — while the same property set inline
  round-trips exactly, and an undefined one returns `""`, which makes `ctx.fillStyle` a silent no-op.
  Measured, not reasoned about; the table is at the end of `M4_CRITIC_FINDINGS.md`. Any canvas test
  in M6 or M10 that seeds tokens must seed them inline.
- **Count every `it(` block mechanically at the end of a milestone** where more than one agent
  touched the tests. Doing that caught a stale cross-agent reference no single agent could see: Task
  12 stated "Task 8's suite stays at 21", written before a later fix cut Task 8 to 16. It also caught
  a wrong count of my own.

## After M4 — M10 is next, and it is ready to start

**M10** (statistics view, first version) is a leaf: only M1 and fixtures, nothing depends on it.
**Its two writer briefs are written and waiting in `docs/latent-forge/M10_WRITER_BRIEFS.md`** —
dispatch Writer A (Tasks 1-3, the data layer), then Writer B (Tasks 4-7, the panels; it consumes A's
client, so they are sequential), then one critic, then verify counts mechanically. Roughly four
agents. Check the **weekly** window first; it has bound every time, not the 5-hour one.

Then M6 (chroma, needs M5) and M7 (chains/mix/library/sessions, needs M4 + M5), then M9 (rendering,
needs M7, last).

Two things M10 inherits that are already solved: M1 T13 publishes the DOM contract the panels and the
Playwright spec share (`[data-region="stats-view"]`, `[data-stats-panel]`, `[data-stats-lane]`), and
M10's xcorr heatmap is a **ramp**, so it builds its own `oklch()` per channel rather than reading a
token — the same exception M5's `downbeatColor` needed. M6's chroma heatmap is the third instance;
the decoder for it is built in M10 Task 1 deliberately.

**For whoever implements rather than plans:** `docs/latent-forge/HANDOUT.md` is the read-first
document — build order, the hazards that each cost a debugging session, the known limitations not to
"fix", and the open questions not to decide unilaterally.

## Done

| Plan | File | State |
|---|---|---|
| **M1** foundation & shell, 15 tasks, ~9k lines | `docs/superpowers/plans/2026-09-16-latent-forge-m1-foundation-shell.md` | **approved by W**, corrections applied |
| **M5** timeline fidelity, 12 tasks, ~6k lines | `docs/superpowers/plans/2026-09-17-latent-forge-m5-timeline-fidelity.md` | pushed, awaiting W's read |

| **M4** PROMPT + SIGMA, 12 tasks planned | `docs/superpowers/plans/2026-09-18-latent-forge-m4-prompt-sigma.md` | **Tasks 1-3 only**, critic-reviewed, 8 blocking findings fixed |

M1 and M5 are pushed. M4 is partial — see below.

## Resuming M4 (this is the live one)

**Tasks 1, 2, 3, 8, 9 and 12 exist. Tasks 4, 5, 6, 7, 10 and 11 do not.** The plan's own
"Status of this plan" block at the top of its task section says the same thing in more detail and is
the authority; keep the two in step if either changes.

- **1-3** (settings store and the M5 seam, sampler availability, schedule validation and sigma max)
  are written AND critic-reviewed: 17 findings, 8 blocking, all applied.
- **8, 9** (target bar; prompt column and the MODEL STAGE / STEPS / CFG / LENGTH / SEED column) and
  **12** (settings presets, the Playwright layout spec, the self-review table) are written but have
  had **no critic pass**. Do not hand them to an implementing agent first. A critic has returned
  blocking defects on every batch it has ever seen — never once zero — so assume wrong test counts,
  imports of names M1 does not export, and tests that pass on a broken implementation.
- **4-7** (the `/schedule` client, the CFG interval conversion, the sigma graph geometry and its
  canvas) and **10, 11** (the sigma column and tab assembly, the ADVANCED SAMPLING module) were never
  started — the writer producing 4-7 was killed before it wrote anything.

Both writer briefs are saved verbatim in `docs/latent-forge/M4_WRITER_BRIEFS.md`. Writer A's is still
wholly unused; Writer B's covers 8-11, of which only 8 and 9 came back, so re-dispatch it scoped to
**Tasks 10 and 11 only**. Then run one critic over 4-12 together before calling M4 done.

**Order for the next session:** re-dispatch Writer A (4-7) and Writer B scoped to 10-11, in parallel;
assemble; then one critic over Tasks 4-12. Roughly a 40-point bite out of a 5-hour window, and the
weekly window is what actually binds — check both before starting.

**One open question this raised, for W:** `RenderSettings` has no duration or length field, so §4.5's
`LENGTH s` control has nowhere in the per-target settings to live. Task 9 lifted it to the tab's own
state, which works but means a `render` preset cannot recall the length it was made at — and §9.3
says a render preset carries "every ADVANCED SAMPLING field" alongside the txt2audio parameters.
That is a §9.2 project-shape question, and it is the same shape as M5's `ForgeClip.previewAudio`
question. Both are waiting on him.

Three things M4 established that are worth carrying even if the plan is rewritten:

- **Today's `/schedule` ignores `schedule` and `sampler_type`** (`explorer_render_server.py:1022-1049`
  reads only `steps`, `duration`, `sigma_max`, `dist_shift`). M3 adds them. So until M3 lands, every
  shape charts the model curve and rho/STEPPED/PLATEAUS/TILT move nothing. M4 sends the full body
  anyway and shows `schedule shape is charted from M3 onward`. It does **not** compute the curve
  locally to cover the gap -- 5.3 says the canvas never computes sigma, and a graph that disagrees
  with the server is worse than one that admits it is behind.
- **`/schedule` takes `duration` and it matters.** The model shape's dist shift is length-dependent
  (`latent_len = ceil(duration*SR/DS)`). M1's `forgeApi.schedule` omits the field, so it would
  silently chart the server's 47 s default at every LENGTH. M4's client sends it.
- **M1's `forgeApi.schedule` return type is wrong**: it declares `{ok, sigmas, shape, warnings}`, but
  today's route returns `{ok, steps, duration, sigma_max, dist_shift, latent_len, sigmas}` -- no
  `shape`, no `warnings`. M4 types them optional rather than editing approved M1. If W ever reopens
  M1, that is the correction.

## Done

## Remaining, in the spec's dependency order (§12)

**M1 → (M4, M5, M10) → (M6, M7) → M9.** M5 is done, so:

1. **M4** — PROMPT + SIGMA and ADVANCED SAMPLING. Spec §4.5, §5.3, §7.2. The natural next one:
   only needs M1, and unblocks M7. Note W's ruling that **σ MAX is not a `ScheduleSpec` field** —
   it is the pass's own init noise level (1.0 for a fresh generate, the target's NOISE on an A2A
   target), and M4 binds the field to the target's NOISE where one exists, read-only 1.00
   otherwise. §5.1's range row now says this.
2. **M10** — statistics view, first version. Spec §4.4. Leaf; only needs M1 + fixtures.
3. **M6** — CHROMA tab. Spec §5.4. Needs M5.
4. **M7** — chains, mix, library, sessions. Spec §4.6, §5.5, §9.2, §9.3. Needs M4 + M5.
5. **M9** — rendering. Spec §7.1, §9.5, §9.7. Needs M7. Last.

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
- Add a **"Normative names"** block to Global Constraints whenever tasks were drafted in parallel.
  It is the cheap fix for agents independently guessing at the same shared surface, and it works
  because a one-task reader still gets the plan header.

## Facts W has settled — do not re-ask

- **Canonical checkouts** (what the venvs actually import, now also ORIENTATION §10):
  `stable_audio_3` → `SAO/stable-audio-3`; `stable_audio_tools` →
  `SAO/stable-audio-tools/stable_audio_tools`; `sa3_control` → `SAO/control/sa3_control` (the
  superset — `audio-tools-avp/avp_sa3/sa3_control` is **stale by default**). `SAI/` and `sat/` exist
  only on this laptop; nothing on W's box imports them.
- **`Progress.stage_index` is 1-based**, 0 = not started. Only `commit` has stage labels; every
  other op emits `stage: ""`, `stage_count: 0`, steps only.
- **Only `/forge/*` is frozen.** `/info`, `/status`, `/schedule`, `/models`, `/slots`, `/audio/...`
  are pre-existing and called directly.
- **`/info.latch_heads`** has 28 fields; `slider_min`/`slider_max` are the head's own p1/p99 and are
  what M7's target slider ranges over. Two real redacted heads are in M1's `handmade-info.json`.
- **`target_raw` is linearly interpolated** to the padded latent grid (`model.py:539-550`), which is
  why `/a2a_mix`'s chroma morph lands ~11% late. W is handling that separately; not ours.

## Open — waiting on W, do not decide unilaterally

1. **`ForgeClip.previewAudio`** — M5 T10 needs it for the stretched preview, but `ForgeClip` is
   pinned by §9.2 and read by M7's v1→v2 converter, so it is a spec change.
2. **Downbeat-coincidence window** — §4.3 says one 32nd note, linear; the drawing's `_dbColor`
   (v3:1155-1158) uses a quarter-beat with a `^0.7` ramp. M5 ships the spec's reading.
3. **`downbeats_sec` timebase** — `/forge/analyze` returns it unstretched at `native_bpm` while
   `offset_sec`/`dur_sec` are stretched (§7.3). M5 currently mixes them. The fix belongs in
   `ForgeClip.downbeats_sec`'s doc comment in M1's `types.ts`, and M1 is approved, so it needs W.

## Process lessons, paid for

- **Watch the budget with `mcp__ccd_session_mgmt__get_usage`.** It reports the 5-hour window, the
  weekly window and whether extra usage (credits) is enabled. Kim's rule, 2026-09-18: **at 90% of the
  5-hour window the agents stop** and the session does only enough work to be resumable. Extra usage
  being *enabled* means nothing stops on its own at 100% -- it silently bills credits, which is what
  happened the night before. Check before spawning any fleet and between stages; a critic plus two
  writers is roughly a 40-point bite out of a 5-hour window, so it does not fit below ~50%.
- **When the budget cuts a milestone in half, save the briefs, not a summary.** The expensive artefact
  is not the prose describing what is left -- it is the fully-built agent briefs, with every inherited
  interface name restated. `M4_WRITER_BRIEFS.md` is that, and it is why M4 can resume in one turn.

- **Critic BEFORE writers, not alongside.** Running them in parallel on M5 let Task 7 faithfully
  re-extract an overlap bug the critic had just made me fix — it read the pre-fix version. Sequencing
  costs nothing.
- **A critic pass is worth its cost.** On two tasks I had called done it returned 32 findings, 11
  blocking, including three green tests sitting on a feature that could never have worked.
- **Sonnet is enough for the writers.** Both M5 writers produced complete, placeholder-free tasks and
  flagged real ambiguities instead of inventing answers. Spend the better model on the critic.
- **`getComputedStyle().getPropertyValue("--token")` returns the literal token stream**, not a
  resolved colour — an unregistered custom property is not converted. Fine to pass straight to
  `ctx.fillStyle` (canvas accepts `oklch()`); fatal if you try to parse channels out of it. M6's
  chroma heatmap will hit this next.
- **Verify by running, not by reasoning**, when it is cheap. A scratch npm project settled both
  "do Svelte 5 runes work in `.svelte.ts` under vitest with this config" (yes) and "does my
  `pollJob` abort test actually pass" (no — an `abort` listener added after the signal already
  fired never runs, so the promise never settled).

## Mechanics that will otherwise waste a turn

- **The Bash tool mangles heredocs containing apostrophes** — `cat >> file <<'EOF'` fails with
  "unexpected EOF while looking for matching `''". Write the content with the Write tool to the
  scratchpad, then `cat` it onto the target.
- **Pushing needs `GCM_GUI_PROMPT=true`** and a dialog on Kim's desktop; without it git hangs
  silently forever. Run the push with `run_in_background: true` so the dialog stays up. Then
  `cmdkey /delete:git:https://github.com` and verify `cmdkey /list | grep -ci github` is 0.
- **The repo is PUBLIC**, despite the `.gitignore` comment and spec §12 both calling it private.
  Confirmed by an anonymous `ls-remote` with the credential helper disabled. Kim has been told; no
  secrets, hostnames or tunnel URLs in anything committed.
- Repo-local git identity is already `Kim <kim.ake@gmail.com>`; verify with
  `git log -1 --format='%an <%ae>'` before the first commit of a session.
- **Never use the M365 / Outlook / Teams / SharePoint tools** on this work, and say so in every
  subagent brief.
