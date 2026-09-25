# M9 — the two writer briefs (Rendering client)

*Written 2026-09-26 by FLATLINE from two read-only research passes. Spec line 1001: render controls
§7.1, job polling, SAMPLING labels, raster border §9.5, render preview container (HISTORY, scrub, drag
to lane, USE SETTINGS, REPLACE CLIP), MIXDOWN slot (latest mix, scrub, drag to lane), PREVIEW/MIXDOWN
A/B, error surfaces §9.7. Depends on M7 (done, three critic passes + reconcile). Last frontend plan.*

**Split:** Writer A = the job layer and everything that submits (jobs store, payload builders, history
store, raster border, MIXDOWN surfaces, errors/TERMINAL). Writer B = the preview container and
everything that consumes a finished render (RENDER dispatch UI, HISTORY, USE SETTINGS, REPLACE CLIP,
master-strip A/B, INPAINT OVERLAP, drag-to-lane, assembly). **They run in parallel.** The shared
store interfaces are pre-declared below; neither writer invents them and neither waits for the other.

## Shared preamble — binding on both
- **NEVER use m365 / Outlook / Teams / SharePoint or Atlassian tools**, and say so to any subagent.
- Write ONE file: `scratchpad/m9_part_a.md` (A) or `scratchpad/m9_part_b.md` (B); task bodies only,
  starting `### Task N:`. Do not edit any plan, the spec or `eval/`. No git writes. Repo is PUBLIC.
- **Use Edit/Write, never shell heredocs/`python -c` with backticks** (bash has corrupted plan text here).
- TDD format as every prior plan: WHY, Files, Interfaces (restate everything consumed with source
  task + current line), failing tests → expected failure → implementation → `Tests N passed (N)` → commit.
- **Verify every claim against the source file; cite by quoted text, not only line numbers** (M1 was
  lengthened on 2026-09-25; many older line refs are stale).
- Read `docs/latent-forge/HANDOUT.md` "Things that will bite you", M7's Global Constraints
  (`$state` proxy rule, no writes inside `$derived`, abort-listener ordering, `$state.snapshot` only in
  `.svelte.ts`), and the three `docs/latent-forge/M7_CRITIC*_FINDINGS.md` — the same classes of bug
  will recur in job/history code.
- Contract authority: spec §6.1/6.2/6.7–6.9, W's M2 (T5 queue, T8 routes, T15 fixtures) and M8
  (`parse_render`, `parse_chain`, `validate_commit`, a2a_clip/inpaint validators). Where spec and M8
  differ, **M8 wins** and you say so.

## Pre-declared shared interfaces (both writers cite these exactly)
```ts
// src/lib/render/jobs.svelte.ts  — Writer A T1
export type RenderKind = "gen" | "a2a" | "inpaint" | "mix";
export interface ActiveJob { forgeJobId: string; op: JobOp; kind: RenderKind; sourceClipId: string | null;
  targetKey: string; progress: Progress | null; }
export class JobsStore {
  active = $state<ActiveJob | null>(null);          // at most one — §7.1: every render control disabled while a job runs
  lastError = $state<{ targetKey: string; message: string } | null>(null);   // §9.7 inline error, cleared by the next render
  get busy(): boolean;                               // active !== null || gpuBusyOther !== null
  gpuBusyOther = $state<string | null>(null);        // /status.busy with a non-forge job → "GPU busy — <job_id>"
  get stepsLeft(): number | null;                    // active?.progress?.steps_left_total ?? null
  submit(req: { op: JobOp; payload: unknown; kind: RenderKind; sourceClipId: string | null; targetKey: string }): Promise<RenderHistoryEntry | null>;
  cancel(): Promise<void>;                           // queued only; running → 409 surfaced, not thrown
}
export const jobs: JobsStore;

// src/lib/render/history.svelte.ts — Writer A T3
export class HistoryStore {
  renders = $state<RenderHistoryEntry[]>([]);        // newest LAST in storage; UI shows newest first
  mixdown = $state<number | null>(null);             // index into renders — always the newest commit
  preview = $state<number | null>(null);             // index into renders — what the preview container shows
  add(e: RenderHistoryEntry): RenderHistoryEntry;    // returns renders[renders.length - 1] ($state proxy rule)
  select(index: number): void;                       // loads audio only (§4.5, X15) — never touches settings
  refOf(e: RenderHistoryEntry): AudioRef;            // {kind:"render", job_id: e.job_id, file: e.file}
  jobRecord(e: RenderHistoryEntry): Promise<JobRecord>;   // forgeApi.job(e.forge_job_id) — USE SETTINGS reads .payload
  clear(): void; restore(renders: RenderHistoryEntry[], mixdown: number | null, preview: number | null): void;
}
export const history: HistoryStore;
```
`RenderHistoryEntry` is M1's (`{job_id, forge_job_id, file, label, kind, dur_sec, source_clip_id, created}`).
Result → entry: `job_id = result.job_id`, `file = result.urls[0].split("/").pop()`, the render AudioRef
is `{kind:"render", job_id, file}` (M2 T15 / M8 T11 build it this way). `created` in epoch seconds.

## Facts both writers must honour (verified in the research)
1. **M8 `parse_render` rejects unknown keys** (`_merge` → 400 `unknown render field(s)`), and
   `duration_sec` is not in `RENDER_DEFAULTS`. Strip `duration_sec` from every `render`/`defaults`
   object in `a2a_clip`/`inpaint`/`commit`. For `generate` the wire name is **`duration`**
   (M1 Normative). `commit` has a top-level **`duration_sec`** (≤184). Schedule keys are exactly
   M3 `parse_spec`'s.
2. **Commit** (`validate_commit`): `lanes` = indexes 0–3 exactly once; `clips` **non-empty** (disable
   MIXDOWN with an honest hint on an empty arrangement); clip `a2a` is `null | {render, envelope}`
   (client stores `{on, noise, envelope}` + `clip.render` — map it); `overlaps` is a LIST of
   `{key, lane, start_sec, end_sec, a_id, b_id, curve, chroma_xfade, render}` with LOCAL steps/cfg
   already applied (client stores `Record<key, OverlapParams>` + derived `Overlap[]`);
   `native_bpm` ratio must be 0.5..2; `detune_cents` ±100; lane `chain` = M7's `chainRequest(...)`;
   `master.head` must be a known head when `latch_on`.
3. **`a2a_clip`** takes the **whole source file** — no offset/dur/stretch (M8). `envelope` null →
   flat `noise_level`. `chain` = `chainRequest(...)`; `ckpt_path` from settings.
4. **`inpaint`**: `a`/`b` `{audio, start_sec, offset_sec, dur_sec}`, `region`, `pad_sec` (default 8),
   `curve`, `chroma_xfade`, `render`. Result audio spans `[region.start − pad, region.end + pad]`
   (`meta.span_start_sec`).
5. **Progress**: `stage_index` 1-based, 0 = not started; only `commit` has the nine §8.1 labels;
   other ops `stage:""`, `stage_count:0`. `progress` is present only while running. **`steps_total`
   can be 0** (commit with no a2a/inpaint passes, `decode`, `bend`) — every division guards it.
6. **Mock vs real server** (M1 T6 vs M2 T5/T8): list rows trimmed on the server (no payload/result/
   progress); cancelling a finished job is 200 on the server, 409 in the mock; 404 text differs;
   `position` live on the server, fixed in the mock. Code must be correct against the SERVER; tests
   that depend on these go in the recorded-contract file and skip until recorded.
7. **Fixtures**: M2 T15 records `forge_job_submit`, `forge_job_running` (a GET 2 s after submit — state
   not guaranteed `running`), `forge_job_generate_done`, `forge_error_cap`, `status_busy`; M8 T11 records
   `forge_job_a2a_clip_done`, `forge_job_inpaint_done`, `forge_job_commit_done`. The hand-made
   `handmade-forge_job_running.json` contradicts the Normative progress rule (`"SAMPLE"`, stage_count 1)
   — don't pin tests to it. Recorded-contract tests follow M7 T10's `it.skipIf` rule (skip when missing
   or empty; never pass on the hand-made mock). Note for W: M2 `EXPECTED` has 25 names but its
   docstring/Step 6 still say 20.
8. **TERMINAL shows `logStore.lines` only; M6/M7/M10 write errors via `view.appendLog(…, "error")`
   into `view.logLines`, which nothing renders.** Writer A T5 fixes this in one place (route
   `view.appendLog` into what TERMINAL renders, or render both) and M9's own errors use it. Also M1
   OQ 16: if M9's poller owns `/status`, the log store drops its own `/status` call.
9. **HELP**: almost no M9 control has a `KEYS` id. M1 already wrote literal help strings on the
   frames (MIXDOWN button/waveform, preview RENDER/HISTORY/drag/USE SETTINGS/REPLACE CLIP) — promote
   each to a `NEW_STRINGS` id and use `HELP.x`; `previewMixdownToggle` exists but M5's toggle doesn't
   attach it. M7's MIX-tab MIXDOWN buttons use `HELP.renderButton` ("Runs the current target") —
   switch them to the MIXDOWN id so both MIXDOWN surfaces say the same thing. Update `strings.test.ts`
   (M7 left 112) in the last string-adding task, running totals per task.
10. **Frames already in place** (keep their testids): M1 `MixdownSlot` (`mixdown-button`,
    `mixdown-canvas` 220×26, `mixdown-play`; props `busy`, `stepsLeft` exist on TopBar but App doesn't
    pass them), `mixdownLabel(busy, stepsLeft)` → `SAMPLING · N steps left`; M1 `PreviewContainer`
    (`preview-render`, `preview-history`, `preview-wave` 900×30, `preview-play`, `preview-length`,
    `preview-drag-handle`, `preview-use-settings`, `preview-replace-clip`), mounted propless in
    BottomPane; M1 root `canvas.raster-border` (300×170, `data-region="raster-border"`); M5 master
    strip toggle (`master-source-preview`/`master-source-mixdown`, MIXDOWN disabled, always visible);
    M7 MIX-tab MIXDOWN buttons (no testid, `onMixdown` no-op) and `inpaint-overlap-button` (no-op).
11. **Serialisation**: M7's `serializeProject` hardcodes `renders: [], mixdown: null, preview: null`;
    `applyProject`/`validateProjectV2` ignore them; `workKey` includes `renders` (history entries count
    as unsaved work — decide and state whether that is wanted).
12. **No drawing** for the MIXDOWN slot, preview container, HISTORY/USE SETTINGS/REPLACE CLIP, the
    PREVIEW/MIXDOWN toggle or an error line — the spec text and M1/M5 frames are the design.

---

## Writer A — Tasks 1-5 (job layer)
1. **`src/lib/render/jobs.svelte.ts` + `src/lib/render/payloads.ts`.** `JobsStore` exactly as
   pre-declared: one active job; `forgeApi.submitJob` then `forgeApi.pollJob` with an AbortSignal;
   on done build the history entry and `history.add` it; on error set `lastError` and log a red line;
   409 queue-full/cannot-cancel surfaced as messages; `/status` polling for `gpuBusyOther` while idle
   (coordinate with M1 OQ 16). `payloads.ts`: pure builders `generatePayload`, `opPayload`
   (`decode`/`longform`/`bend` — read what each existing `_*_impl` needs from M2's validators),
   `a2aClipPayload`, `inpaintPayload`, `commitPayload`, all honouring Facts 1–4 (strip `duration_sec`,
   `chainRequest`, a2a/overlap mapping, LOCAL override). Contract tests: builders' output accepted by a
   port of M8's validators' key sets (key-set equality, ranges) plus recorded `forge_job_*` fixtures.
2. **Raster border.** Copy `docs/sa3-studio/design_handoff/phosphor-border.js` verbatim to
   `src/lib/fx/phosphor-border.js` with a hand-written `.d.ts`. API: `createPhosphorBorder(canvas,
   options)` → `{start, stop, set(patch), resize, destroy}`; `PALETTES` export. Mismatches to handle:
   `palette` must be an ARRAY (`PALETTES.teal`, not `"teal"`); `sweepStart`/`sweepEnd` are app-side —
   compute `sweepHz = sweepStart + (sweepEnd − sweepStart)·(1 − left/total)` (guard total 0) and call
   `set({sweepHz})`; pass `alphaOut: true`. Driver starts on `jobs.active`, stops+destroys when idle.
3. **`src/lib/render/history.svelte.ts`** as pre-declared, plus the serialiser changes in M7's
   `projectSerializer.svelte.ts` / `applyProject` / `validateProjectV2` (write, restore and validate
   `renders`/`mixdown`/`preview`; state the `workKey` decision).
4. **MIXDOWN.** Wire the top-bar `MixdownSlot` (pass `busy`/`stepsLeft`; submit `commit`; latest-mix
   waveform from `history.mixdown`, play/stop, click-to-scrub, `draggable` with the
   `application/x-forge-ref` payload) and M7's MIX-tab buttons (same action; add testids; HELP per
   Fact 9). After a finished commit, feed `meta.stages` into the SIGNAL PATH (M7 OQ 12: decide replace
   vs reconcile and say so).
5. **Errors and TERMINAL.** Fact 8's single fix; §9.7 inline one-line error under the target bar until
   the next render (from `jobs.lastError`); `GPU busy — <job_id>`; unmounted-drive errors keep the
   server's hint text; blocked-target reasons (the v1 `renderBlock` idea, extended to the new ops —
   define them as a pure `renderBlock(target, state): string | null`, shared with Writer B).

Reply: `A: tasks=1-5 lines=<n> its=T1:<n>,…,T5:<n> skipif=<n> openq=<n>`.

## Writer B — Tasks 6-10 (preview container and consumers)
6. **`▸ RENDER` in `PreviewContainer`** dispatching per §7.1's table: nothing selected → `generate`
   (`duration = LENGTH`, session defaults); clip + A2A on → `a2a_clip`; clip + A2A off → the clip's OP,
   disabled with `turn A2A on or choose an op` when it has neither; overlap → `inpaint`. Uses
   `jobs.submit` + Writer A's builders and `renderBlock`. Label `SAMPLING · N steps left` on the
   control that started the job; all render controls disabled while `jobs.busy`. **The OP has no home**
   (`ForgeClip` has no `op`; M4's `op`/`onOp` unwired): propose the smallest home, state it as an open
   question for WINTERMUTE (a `ForgeClip` field is a §9.2 spec change, as `previewAudio` was).
7. **HISTORY, waveform, play, length, drag handle.** HISTORY newest first, tagged GEN/A2A/INPAINT/MIX
   with length; selecting loads audio only (X15). Waveform with click/drag scrub and playhead; play/stop
   independent of the timeline transport — starting one stops the other (§4.5, M1 `transportPlay` help).
   Drag handle sets `application/x-forge-ref` with the render AudioRef.
8. **USE SETTINGS and REPLACE CLIP.** USE SETTINGS copies the previewed render's job **payload**
   settings into the current target — note M4's `applyRenderPreset` ignores `duration`/`duration_sec`,
   so LENGTH needs its own handling; payload shape differs per op. REPLACE CLIP (enabled only when
   `source_clip_id` is the selected clip) needs a NEW `arrangement.replaceClipAudio(id, ref)` that
   pushes the old ref onto `clip.history` (no such method exists; add it to M5's store as a `Modify:`)
   and re-runs analyze/stretch as needed.
9. **Master strip A/B and INPAINT OVERLAP.** Wire M5's toggle: MIXDOWN enabled when
   `history.mixdown !== null`; decide the visibility rule (spec: only when the MIXDOWN slot holds a
   render; M5 built it always visible) and state it; switch strip + transport to `mix.wav` (§9.6);
   attach `HELP.previewMixdownToggle`. Wire `inpaint-overlap-button` to the same path as RENDER on an
   overlap.
10. **Drag-to-lane, assembly, Playwright, self-review.** Replace M5's two lane drop handlers' hardcoded
    `addClip({durSec: 4})` with `lifecycle.addClip({ref, durationSec})` so drops from the preview
    container, MIXDOWN slot and FILES get real length, analyze and stretch. Playwright over the mock:
    render → progress label → history entry → drag to lane; MIXDOWN → SIGNAL PATH lit; A/B toggle;
    inline error on a 400. Also the **explicit legacy-removal task** W asked for (log 2026-09-25 21:05):
    remove `legacy-server` (and `legacy-inspector` if its replacement is proven) only after the M7/M9
    Playwright gates pass — gate the step on that. Self-review vs §4.2/4.3/4.5/7/9.5–9.7 + Known incomplete.

Reply: `B: tasks=6-10 lines=<n> its=T6:<n>,…,T10:<n> skipif=<n> pw=<n> openq=<n>`.

## After both
Assemble (header, Global Constraints, Names inherited, Normative incl. data-*/testid/HELP table, File
Structure, Status), two critic passes minimum plus a narrow one over any fix round's new code, recount
mechanically, then one batched DM to WINTERMUTE (OP home, `EXPECTED` 25 vs 20, any M8 payload doubts).
