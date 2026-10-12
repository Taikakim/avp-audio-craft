# M9 Writer B — continuation brief, Tasks 8-10 only

*Written 2026-09-27 by FLATLINE. Writer B's first run produced Tasks 6-7 and stopped at the budget
line. This brief covers ONLY Tasks 8, 9 and 10. Tasks 6 and 7 are DONE — do not rewrite them.*

## Absolute rules (read these first, they have all cost real work here)

1. **NEVER use m365 / Outlook / Teams / SharePoint tools, and never use Atlassian / Jira / Confluence
   tools.** Not for any reason. If you spawn a subagent, repeat this to it verbatim.
2. **Write each task to its own file on disk the moment you finish it, BEFORE you start the next
   one.** This is the single most important instruction in this brief. Three earlier runs lost
   everything because they read a pile of files and then died before writing anything. The one run
   that survived did so only because it wrote incrementally. Targets, in the repo (tracked, not
   scratchpad — the gitignored scratchpad has eaten three runs):
   - Task 8 → `docs/latent-forge/M9_PART_B_TASK8.md`
   - Task 9 → `docs/latent-forge/M9_PART_B_TASK9.md`
   - Task 10 → `docs/latent-forge/M9_PART_B_TASK10.md`
   Each file holds that task body only, starting `### Task N:`. Do not create one big file.
3. **Use Edit/Write, never shell heredocs and never `python -c "..."` containing backticks.** Bash
   command-substitutes backticks and has silently blanked identifiers out of plan text here.
4. **No git writes. Do not edit any plan, the spec, or `eval/`.** The repo is PUBLIC: no secrets,
   hostnames, tunnel URLs or credential paths anywhere in what you write.
5. **Budget your reading.** Do NOT read six large files before writing. Read what Task 8 needs, write
   Task 8, then read what Task 9 needs. Prefer `grep -n` over whole-file reads.

## What already exists — read these for real names, do not re-derive

- `docs/latent-forge/M9_WRITER_BRIEFS.md` — the original brief. Its **Shared preamble**,
  **Pre-declared shared interfaces** (`JobsStore`, `HistoryStore` — cite them exactly as written) and
  the twelve numbered **Facts both writers must honour** are binding on you. Items 8, 9, 10, 11 and 12
  bear directly on Tasks 8-10.
- `docs/latent-forge/M9_PART_B_DRAFT_PARTIAL.md` — your own Tasks 6 and 7 (1,782 lines, 37 `it()`).
  **Read this for the names you already introduced** — component props, testids, helper functions,
  the `op`-on-`ForgeClip` shape from Task 6, the waveform/scrub/play helpers from Task 7. Tasks 8-10
  consume them and must use the identical names.
- `docs/latent-forge/M9_PART_A_DRAFT.md` — Writer A's complete Tasks 1-5 (3,715 lines). Grep it for
  the real `jobs`/`history` member names, the payload builders, `renderBlock`, the TERMINAL/error
  surface from A's T5, and A's MIXDOWN wiring, which Task 9's A/B toggle sits next to.
- `docs/latent-forge/HANDOUT.md` — "Things that will bite you".
- `docs/latent-forge/M7_CRITIC1_FINDINGS.md`, `M7_CRITIC2_FINDINGS.md`, `M7_CRITIC3_FINDINGS.md` —
  the same bug classes recur in history/session code. Critic 2 found two data-loss paths a fix round
  had just introduced; critic 3 found a non-`version: 2` body running through the v1 converter.

## Format (as every prior plan in `docs/superpowers/plans/`)

Per task: **WHY** → **Files** → **Interfaces** (restate everything you consume, with its source task
and current line) → failing tests → expected failure → implementation → `Tests N passed (N)` → commit
message. Verify every claim against the source file and **cite by quoted text, not line number alone**
— M1 was lengthened on 2026-09-25 and many older line references are stale.

Svelte 5 runes traps that must be honoured in the test and implementation text: the `$state` proxy
rule (a store method appending to a `$state` array returns `arr[arr.length - 1]`, not the local
variable); `structuredClone` on a `$state` proxy throws `DataCloneError` — use `$state.snapshot`,
which only exists in `.svelte.ts`/`.svelte`; writing state inside `$derived` throws
`state_unsafe_mutation`; effects need `await tick()`; an abort listener added after the signal already
fired never runs, so check `signal.aborted` first; never `fillText` a label a test asserts on, because
`findByText` cannot see canvas text.

---

## Task 8 — USE SETTINGS and REPLACE CLIP

USE SETTINGS copies the previewed render's job **payload** settings into the current target. Note that
M4's `applyRenderPreset` ignores `duration`/`duration_sec`, so LENGTH needs its own handling, and the
payload shape differs per op (`generate` uses the wire name `duration`; `a2a_clip`/`inpaint` carry a
nested `render` object with no `duration_sec`; `commit` has a top-level `duration_sec`). The payload
comes from `history.jobRecord(e)` → `.payload`.

REPLACE CLIP is enabled only when the previewed render's `source_clip_id` is the currently selected
clip. It needs a NEW `arrangement.replaceClipAudio(id, ref)` which pushes the old ref onto
`clip.history` — no such method exists, so add it to M5's store as a `Modify:` entry — and re-runs
analyze/stretch as needed.

## Task 9 — Master strip A/B and INPAINT OVERLAP

Wire M5's existing toggle (`master-source-preview` / `master-source-mixdown`, currently MIXDOWN-disabled
and always visible). MIXDOWN is enabled when `history.mixdown !== null`. **Decide the visibility rule
and state your decision with its reason**: the spec says the toggle appears only when the MIXDOWN slot
holds a render, M5 built it always visible. Switching to MIXDOWN switches both the master strip and the
transport to `mix.wav` (§9.6). Attach `HELP.previewMixdownToggle` (it exists but M5's toggle does not
attach it). Wire `inpaint-overlap-button` — presently a no-op — to the same dispatch path RENDER uses
for an overlap.

## Task 10 — Drag-to-lane, Playwright, self-review, gated legacy removal

Replace M5's two lane drop handlers' hardcoded `addClip({durSec: 4})` with
`lifecycle.addClip({ref, durationSec})` so drops from the preview container, the MIXDOWN slot and FILES
get real length, analyze and stretch.

Playwright over the mock server: render → progress label → history entry → drag to lane; MIXDOWN →
SIGNAL PATH lit; A/B toggle; inline error on a 400.

The **explicit legacy-removal step** W asked for (log 2026-09-25 21:05): remove `legacy-server`, and
`legacy-inspector` too if its replacement is proven, **only after the M7 and M9 Playwright gates pass
— write the step gated on that**, not unconditionally.

Self-review against spec §4.2, §4.3, §4.5, §7, §9.5-9.7, plus a "Known incomplete" list.

Recorded-fixture contract tests follow M7 T10's `it.skipIf` rule: skip when the fixture is missing or
empty, never pass against the hand-made mock.

---

## Reply format

When all three files are on disk, reply with one line and nothing else:

`B-cont: tasks=8-10 files=3 its=T8:<n>,T9:<n>,T10:<n> skipif=<n> pw=<n> openq=<n>`

Count `it()` mechanically per task with `grep -c` against each task's own file before you report.
There is no working `python` on PATH on this machine (it is the Microsoft Store stub) — use `py`, or
`grep`/`awk`.
