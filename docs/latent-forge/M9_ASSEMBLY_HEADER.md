# Latent Forge M9 — rendering

**Goal:** build spec line 1001's rendering client: the `▸ RENDER` controls and their per-target
dispatch (§7.1), job submission and polling against the forge queue, the `SAMPLING · N steps left`
labels, the raster border (§9.5), the render preview container (HISTORY, waveform scrub, drag to
lane, USE SETTINGS, REPLACE CLIP), the MIXDOWN slot (latest mix, scrub, drag to lane), the
PREVIEW/MIXDOWN A/B toggle, and the error surfaces (§9.7). This is the last frontend plan.

**Architecture:** split by LAYER at the job boundary. Writer A took the job layer and everything
that submits — the jobs store, the per-op payload builders, the history store, the raster border,
the MIXDOWN surfaces and the errors/TERMINAL fix. Writer B took the preview container and
everything that consumes a finished render — RENDER dispatch, HISTORY, USE SETTINGS, REPLACE CLIP,
the master-strip A/B, INPAINT OVERLAP and drag-to-lane. The two store interfaces that cross the
seam (`JobsStore`, `HistoryStore`) were pre-declared by exact name and signature in the brief
before either writer started, so neither waited on the other.

**Tech stack:** Vite + Svelte 5 (runes) + TypeScript 5.6, vitest 2, Playwright 1.

**Spec:** `docs/superpowers/specs/2026-09-15-latent-forge-design.md` — §7.1 is the render control
table and the per-target dispatch rule; §6.1/6.2 are the forge job contract; §6.7-6.9 are the
queue, status and cancel routes; §8.1 is the nine commit stages; §9.5 is the raster border; §9.6 is
the PREVIEW/MIXDOWN A/B rule; §9.7 is the error surfaces; §4.5 is the preview container and the
independent-transport rule; §4.2/§4.3 are the frames this milestone fills.

**Depends on:** **M1** (foundation) — `RenderHistoryEntry`, `AudioRef`, `forgeApi`'s job routes and
every frame this milestone fills (`MixdownSlot`, `PreviewContainer`, the root `canvas.raster-border`)
are already declared there. **M4** (PROMPT + SIGMA) — the `settings` store and `applyRenderPreset`,
which USE SETTINGS extends. **M5** (timeline) — `arrangement`, the lane drop handlers and the clip
lifecycle. **M7** (chains, mix, sessions) — `chainRequest(...)`, the MIX-tab MIXDOWN buttons, the
`inpaint-overlap-button` frame, and the session serialiser this milestone extends with history.
**M8** (server render routes, WINTERMUTE's) — the payload contract every builder here targets.
**M2** (server queue and fixtures, WINTERMUTE's) — the job lifecycle and the recorded fixtures the
contract tests skip against.

**Blocks:** nothing. M9 is the last frontend milestone in §12's build order
(M1 → M4, M5, M10 → M6, M7 → M9).

---

## Global constraints

**Read these before Task 1. Each one cost a debugging session, or is a defect a writer or critic
found and independently verified while researching this milestone.**

1. **The `$state` proxy rule.** A store method that appends to a `$state` array must return
   `arr[arr.length - 1]`, not the local object it just pushed — the pushed local is not the proxy
   the store now holds, and a caller that keeps it has a dead handle. `HistoryStore.add` returns
   the proxy for exactly this reason, and every caller uses the returned value.
2. **An abort listener added after the signal already fired never runs.** Check `signal.aborted`
   first. The job poller and the preview audio loader can both be superseded before they resolve.
3. **Serialise `$state` with `$state.snapshot`, never `structuredClone`.** `structuredClone` of a
   `$state` proxy throws `DataCloneError` (verified on Svelte 5.57.0). `$state.snapshot` is a rune,
   so any module calling it must be a `.svelte.ts` file.
4. **Nothing may write `$state` while a `$derived` or a template expression is being evaluated**
   (`state_unsafe_mutation`, verified on Svelte 5.57.0). Anything that seeds on first read must be
   called from an event handler, never from a `$derived`.
5. **`getComputedStyle().getPropertyValue("--token")` returns the token stream, not a colour.**
   The raster border builds its own `oklch()` string rather than parsing channels out of a token.
   In jsdom a `<style>` block on `:root` eats the space after `90%`, and an undefined token returns
   `""` — which makes `ctx.fillStyle = ""` a silent no-op that passes a naive test. Seed tokens
   inline in the test.
6. **Never `fillText` a label that a test asserts on.** `findByText` cannot see canvas text. Every
   label this milestone gates a test on is DOM text, not a canvas draw. (This blocked M4.)
7. **`steps_total` can be 0** — a commit with no a2a or inpaint passes, and the `decode` and `bend`
   ops, all report it. Every division by it guards first, and the progress label falls back rather
   than rendering `NaN`.
8. **Code must be correct against the SERVER, not the mock.** M1 T6's mock and M2 T5/T8's real
   routes disagree in four known places: the server trims list rows (no payload, result or
   progress), cancelling a finished job is 200 on the server and 409 in the mock, the 404 text
   differs, and `position` is live on the server but fixed in the mock. Tests that depend on any of
   these live in the recorded-contract file and skip until the fixture is recorded.
9. **Recorded-fixture contract tests follow M7 T10's `it.skipIf` rule**: skip when the fixture is
   missing or empty, never pass against a hand-written mock. In particular
   `handmade-forge_job_running.json` contradicts the Normative progress rule (`"SAMPLE"`,
   `stage_count: 1`) — no test pins to it.
10. **Where the spec and M8 differ, M8 wins**, and the task says so in prose where it happens.

---

## The M8 payload contract — copy it exactly, do not re-derive

These are verified against WINTERMUTE's M8 (`parse_render`, `parse_chain`, `validate_commit`, the
`a2a_clip` and `inpaint` validators) and are the single most common way a render request 400s.

1. **`parse_render` rejects unknown keys** (`_merge` → 400 `unknown render field(s)`), and
   `duration_sec` is **not** in `RENDER_DEFAULTS`. Strip `duration_sec` from every `render` and
   `defaults` object in `a2a_clip`, `inpaint` and `commit`. For `generate` the wire name is
   **`duration`**. `commit` carries a top-level **`duration_sec`** (≤ 184). Schedule keys are
   exactly M3 `parse_spec`'s.
2. **LatCH takes the whole chain object.** `chainRequest(...)` (M7) sends exactly 2 slots with
   nested `hparams`, and `rho`/`mu` as raw 0-30 multipliers mapped server-side. Sending one slot
   400s; pre-multiplying the gains client-side squares them. `parse_chain` validates
   `start_pct <= end_pct` before it checks `latch_on`.
3. **`validate_commit`**: `lanes` must be indexes 0-3 each exactly once; `clips` must be
   **non-empty** (so MIXDOWN is disabled with an honest hint on an empty arrangement); a clip's
   `a2a` is `null | {render, envelope}` (the client stores `{on, noise, envelope}` plus
   `clip.render` — map it); `overlaps` is a **list** of
   `{key, lane, start_sec, end_sec, a_id, b_id, curve, chroma_xfade, render}` with local steps and
   cfg already applied (the client stores a `Record<key, OverlapParams>` plus a derived `Overlap[]`);
   `native_bpm` ratio must be 0.5..2; `detune_cents` ±100; a lane's `chain` is `chainRequest(...)`;
   `master.head` must be a known head when `latch_on`.
4. **`a2a_clip` takes the whole source file** — no offset, dur or stretch. A null `envelope` means
   a flat `noise_level`.
5. **`inpaint`**: `a` and `b` are `{audio, start_sec, offset_sec, dur_sec}`, plus `region`,
   `pad_sec` (default 8), `curve`, `chroma_xfade` and `render`. The result audio spans
   `[region.start − pad, region.end + pad]` (`meta.span_start_sec`) — the preview and any
   REPLACE CLIP must account for the pad rather than assuming the region.
6. **FiLM checkpoints** are `family: "control_adapter"` with `control_mode: "scalar"`. There is no
   `film` family.
7. **Progress**: `stage_index` is 1-based and 0 means not started; only `commit` has the nine §8.1
   stage labels, every other op reports `stage: ""` and `stage_count: 0`; `progress` is present
   only while the job runs.

---

## Names inherited — do not redeclare them

- **Types** (M1): `RenderHistoryEntry` (`{job_id, forge_job_id, file, label, kind, dur_sec,
  source_clip_id, created}`, `created` in epoch seconds), `AudioRef`, `ProjectV2`, `ForgeClip`,
  `OverlapParams`. Import them; do not redeclare any.
- **Result → entry**: `job_id = result.job_id`, `file = result.urls[0].split("/").pop()`, and the
  render AudioRef is `{kind: "render", job_id, file}` — M2 T15 and M8 T11 both build it this way.
- **`forgeApi`** (M1 T5, frozen) already has the job routes this milestone needs. No task here adds
  a method to `forgeApi` itself.
- **`chainRequest(...)`** (M7) — the only supported way to build a LatCH request. Never rebuild the
  §5.5 mapping client-side.
- **`LaneChain.lora.ckpt_path` is the durable identity; `.slot` is a transient resolution** against
  the current `GET /slots` (M7, critic pass 2 #14). This milestone resolves from `ckpt_path` at
  submit time and treats `slot` as a hint at most.
- **`settings` store and `applyRenderPreset`** (M4) — note that `applyRenderPreset` ignores
  `duration`/`duration_sec`, so USE SETTINGS owns LENGTH itself.
- **`arrangement`, the two lane drop handlers, `lifecycle.addClip`, `scheduleStretch`** (M5).
- **`view.selection: Target`, `view.appendLog(…, "error")`, `logStore.lines`** (M1 T7).

### Frames already in place — keep their testids

| frame | owner | testids |
|---|---|---|
| `MixdownSlot` | M1 | `mixdown-button`, `mixdown-canvas` (220×26), `mixdown-play`; `mixdownLabel(busy, stepsLeft)` → `SAMPLING · N steps left`. Props `busy`/`stepsLeft` exist on TopBar but App does not pass them |
| `PreviewContainer` | M1 | `preview-render`, `preview-history`, `preview-wave` (900×30), `preview-play`, `preview-length`, `preview-drag-handle`, `preview-use-settings`, `preview-replace-clip`. Mounted propless in BottomPane |
| root raster border | M1 | `canvas.raster-border`, 300×170, `data-region="raster-border"` |
| master strip A/B toggle | M5 | `master-source-preview`, `master-source-mixdown` — MIXDOWN disabled, always visible |
| MIX-tab MIXDOWN buttons | M7 | no testid, `onMixdown` is a no-op |
| `inpaint-overlap-button` | M7 | a no-op |

**No new drawing.** The MIXDOWN slot, preview container, HISTORY, USE SETTINGS, REPLACE CLIP, the
PREVIEW/MIXDOWN toggle and the error line are all specified by the spec text and the M1/M5 frames.

---

## Two defects this milestone fixes at source

1. **TERMINAL renders `logStore.lines` only.** M6, M7 and M10 write their errors via
   `view.appendLog(…, "error")` into `view.logLines`, which nothing renders — every error those
   milestones report is invisible today. Writer A's Task 5 fixes this in one place, and M9's own
   errors use the fixed path.
2. **`serializeProject` hardcodes `renders: []`, `mixdown: null`, `preview: null`**, and
   `applyProject`/`validateProjectV2` ignore them, so render history never survives a save. This
   milestone serialises it. Note that `workKey` includes `renders`, which means history entries
   count as unsaved work — the task states whether that is wanted and why.

---

## HELP coverage

Almost no M9 control has a `KEYS` id. M1 wrote literal help strings onto the frames (the MIXDOWN
button and waveform; the preview RENDER, HISTORY, drag, USE SETTINGS and REPLACE CLIP) — each is
promoted to a `NEW_STRINGS` id and used as `HELP.x`. `previewMixdownToggle` already exists but M5's
toggle never attached it. M7's MIX-tab MIXDOWN buttons use `HELP.renderButton` ("Runs the current
target") and switch to the MIXDOWN id, so both MIXDOWN surfaces say the same thing.
`strings.test.ts` totals run per task in execution order and are recounted mechanically at assembly.

---

## File structure

*(assembled after all ten tasks land — one row per file created or modified, with its owning task)*

## Status of this plan

*(assembled last: writer runs, critic passes, mechanical test totals, open questions count)*
