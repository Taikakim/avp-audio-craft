<script lang="ts">
  // Spec §4.5's render preview container — FRAME ONLY, 44 px, full width.
  //
  // M9 owns every behaviour here: running the pane's current target (§7.1),
  // filling HISTORY with the session's renders newest first tagged GEN / A2A /
  // INPAINT / MIX with length, drawing and scrubbing the waveform (reading its
  // colours through getComputedStyle so DARK works), play/stop independent of the
  // timeline transport, `draggable` with a dragstart payload so the render drops
  // onto a lane, USE SETTINGS copying the previewed render's job payload into the
  // current target, and REPLACE CLIP swapping a clip's audio while keeping the
  // previous ref in clip.history.
  import { HELP } from "../../lib/help/strings";
  import { fetchLatchHeads, type LatchHeadInfo } from "../../lib/chains/latch";
  import { PAD_SEC, renderLabel, renderRequest } from "../../lib/render/dispatch";
  import { dispatchWorld } from "../../lib/render/dispatchWorld";
  import { jobs } from "../../lib/render/jobs.svelte";
  import { MIXDOWN_TARGET_KEY } from "../../lib/render/mixdown.svelte";
  import { renderBlock } from "../../lib/render/renderBlock";
  import { PayloadError } from "../../lib/render/payloads";
  import { arrangement } from "../../lib/stores/arrangement.svelte";
  import { settings } from "../../lib/stores/settings.svelte";
  import { view } from "../../lib/stores/view.svelte";

  // One fetch per mounted container, resolving {} on failure (M7 T1). The heads only decide which
  // LatCH slots survive into the chain, so an empty registry sends a chain with no slots rather
  // than blocking a render.
  let heads = $state<Record<string, LatchHeadInfo>>({});
  $effect(() => {
    fetchLatchHeads().then((h) => (heads = h)).catch(() => {});
  });

  const target = $derived(view.selection);

  const clip = $derived.by(() => {
    const sel = view.selection;
    return sel.kind === "clip" ? (arrangement.clips.find((c) => c.id === sel.id) ?? null) : null;
  });

  const overlap = $derived.by(() => {
    const sel = view.selection;
    return sel.kind === "overlap" ? (arrangement.overlaps.find((o) => o.key === sel.key) ?? null) : null;
  });

  const world = $derived.by(() => dispatchWorld(target, heads));

  const blocked = $derived(
    renderBlock(target, {
      busy: jobs.active !== null,
      gpuBusyOther: jobs.gpuBusyOther,
      settings: world.settings,
      clip,
      clipOp: clip?.op ?? null,
      arcPrompt: world.arcPrompt,
      bendOpCount: world.bendOps.length,
      overlapSpanSec: overlap ? overlap.end_sec - overlap.start_sec : 0,
      padSec: PAD_SEC,
    }),
  );

  /** The SAMPLING count belongs to the control that STARTED the job (§7.1). A commit runs under
   *  MIXDOWN_TARGET_KEY, so the top-bar slot counts it and this button only greys out; anything
   *  else was started from here. Comparing against the key rather than the live selection means
   *  selecting a different clip mid-render does not move the label. */
  const mine = $derived(jobs.active !== null && jobs.active.targetKey !== MIXDOWN_TARGET_KEY);
  const label = $derived(renderLabel(mine, jobs.stepsLeft));

  async function onRender(): Promise<void> {
    if (blocked !== null) return;
    try {
      await jobs.submit(renderRequest(target, world));
    } catch (e) {
      // A PayloadError here is a field the server would 400 on; §9.7 wants it on the target bar,
      // and jobs.lastError is that surface (Writer A T5 renders it).
      jobs.lastError = { targetKey: view.selectionKey, message: e instanceof PayloadError ? e.message : String(e) };
    }
  }


  import { computePeaks, drawPeaks } from "../../lib/audio/waveform";
  import { Transport } from "../../lib/audio/transport";
  import { forgeApi } from "../../lib/forge/api";
  import { history } from "../../lib/render/history.svelte";
  import { HISTORY_EMPTY_LABEL, historyOptions, lengthLabel } from "../../lib/render/historyLabel";
  import { previewPlayer } from "../../lib/render/previewPlayer.svelte";

  const options = $derived(historyOptions(history.renders));

  const entry = $derived(
    history.preview !== null ? (history.renders[history.preview] ?? null) : null,
  );

  const previewUrl = $derived(entry ? forgeApi.audioUrl(history.refOf(entry)) : null);

  // §4.5: "A finished render lands here" -- history.add already moved `preview`, so this effect is
  // what makes a finished render audible without the operator touching HISTORY.
  $effect(() => {
    if (previewUrl !== null && entry !== null) previewPlayer.load(previewUrl, entry.dur_sec);
  });

  let canvasEl = $state<HTMLCanvasElement>();        // M1 already declares this; keep the one line
  let buffer = $state<AudioBuffer | null>(null);
  let scrubbing = $state(false);

  /** Decode-only Transport, M5's own pattern -- this warms the same URL-keyed cache the player
   *  reads, and never plays. Lazily built so jsdom's missing AudioContext costs a waveform, not
   *  the component. */
  let _decoder: Transport | null | undefined;
  function decoder(): Transport | null {
    if (_decoder === undefined) {
      try { _decoder = new Transport(); } catch { _decoder = null; }
    }
    return _decoder;
  }

  $effect(() => {
    const url = previewUrl;
    buffer = null;                 // same invalidation as the MIXDOWN slot — keep the two copies identical
    if (url === null) return;
    let live = true;
    decoder()?.preload(url).then((b) => { if (live) buffer = b; }).catch(() => { if (live) buffer = null; });
    return () => { live = false; };
  });

  function draw(): void {
    const canvas = canvasEl;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!buffer) return;
    const color = getComputedStyle(canvas).getPropertyValue("--accent").trim() || "#4ec9b0";
    drawPeaks(canvas, computePeaks(buffer, Math.max(1, canvas.width)), color);
    // Playhead. A LINE, not a label: nothing a test reads is ever painted here (M4's finding).
    // CSS pixels, not device pixels: `drawPeaks` resizes the backing store to `clientWidth * dpr`
    // and leaves `setTransform(dpr, 0, 0, dpr, 0, 0)` installed (waveform.ts:85-97), drawing its
    // own body in CSS pixels. Using `canvas.width` here would multiply the position by dpr a
    // second time and walk the playhead off the canvas at 25% on a dpr:2 display. M5's own
    // post-drawPeaks overlay stays in CSS pixels for the same reason (m5 plan:4813-4817).
    const total = previewPlayer.durationSec;
    if (total > 0) {
      const cssW = canvas.clientWidth;
      const cssH = canvas.clientHeight;
      const x = Math.round((previewPlayer.playheadSec / total) * cssW);
      ctx.fillStyle = getComputedStyle(canvas).getPropertyValue("--fg").trim() || "#fff";
      ctx.fillRect(x, 0, 1, cssH);
    }
  }

  $effect(() => {
    void buffer;
    void canvasEl;
    void previewPlayer.playheadSec;
    draw();
  });

  // The playhead clock, the same shape as M5's Ruler loop and stopped with the component.
  $effect(() => {
    if (!previewPlayer.playing) return;
    let frame = 0;
    const tick = () => { previewPlayer.syncPlayhead(); frame = requestAnimationFrame(tick); };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  });

  function secAt(e: { clientX: number }): number {
    const canvas = canvasEl;
    if (!canvas || previewPlayer.durationSec <= 0) return 0;
    const rect = canvas.getBoundingClientRect();
    const ratio = rect.width > 0 ? (e.clientX - rect.left) / rect.width : 0;
    return Math.max(0, Math.min(1, ratio)) * previewPlayer.durationSec;
  }

  function onWavePointerDown(e: PointerEvent): void {
    if (previewUrl === null) return;
    scrubbing = true;
    (e.currentTarget as HTMLCanvasElement).setPointerCapture?.(e.pointerId);
    void previewPlayer.scrubAt(secAt(e));
  }

  function onWavePointerMove(e: PointerEvent): void {
    if (scrubbing) void previewPlayer.scrubAt(secAt(e));
  }

  function onWavePointerUp(): void {
    if (!scrubbing) return;
    scrubbing = false;
    previewPlayer.stop();
  }

  function onHistoryChange(e: Event): void {
    // Audio only (§4.5, §10 X15). `history.select` sets exactly one field, and this handler
    // deliberately calls nothing else -- a settings write here is the regression X15 exists to stop.
    history.select(Number((e.currentTarget as HTMLSelectElement).value));
  }

  function onHandleDragStart(e: DragEvent): void {
    if (!entry || !e.dataTransfer) return;
    e.dataTransfer.setData("application/x-forge-ref", JSON.stringify(history.refOf(entry)));
    e.dataTransfer.effectAllowed = "copy";
  }

  import {
    applyPayloadSettings, NO_SETTINGS_HINT, payloadSettings, replaceClipBlock, useSettingsBlock,
  } from "../../lib/render/previewActions";
  import { replaceAudio } from "../../lib/clips/lifecycle";

  /** Post-click state, not a block reason: what the last USE SETTINGS actually did. Cleared the
   *  moment the previewed render changes, so the hint can never describe a different render. */
  let useSettingsNote = $state<string | null>(null);
  let acting = $state(false);

  $effect(() => {
    // Read `entry` so this re-runs on a HISTORY change; never write state that this same effect
    // reads, or Svelte throws state_unsafe_mutation.
    void entry;
    useSettingsNote = null;
  });

  const useBlock = $derived(useSettingsBlock(entry, jobs.busy || acting));
  const replaceBlock = $derived(replaceClipBlock(entry, target, jobs.busy || acting));

  async function onUseSettings(): Promise<void> {
    if (entry === null || useBlock !== null) return;
    // Capture BEFORE the await. `history.jobRecord` is a real round trip (GET /forge/jobs/<id>),
    // `target` is `view.selection` itself, and `entry` is a $derived over HISTORY -- either can
    // change while the fetch is in flight. `acting` only stops a second CLICK. Writing the
    // render's settings into a target the operator did not pick is an edit, so M7's autosave
    // would then save it 2 s later; this is M7 critic pass 3 #2's shape, and the fix there was
    // the same superseded check.
    const forTarget = view.selection;
    const forKey = view.selectionKey;      // compare by KEY: every selection click builds a fresh object
    const forEntry = entry;
    acting = true;
    try {
      const record = await history.jobRecord(forEntry);
      if (view.selectionKey !== forKey || entry !== forEntry) return;   // superseded
      const ps = payloadSettings(record.op, record.payload);
      if (ps.body === null && ps.durationSec === null) {
        useSettingsNote = NO_SETTINGS_HINT;
        return;
      }
      const out = applyPayloadSettings(forTarget, ps);
      useSettingsNote = null;
      const parts = [`${out.applied.length} field(s)`];
      if (out.lengthSec !== null) parts.push(`LENGTH ${out.lengthSec.toFixed(3)} s`);
      view.appendLog(`[render] USE SETTINGS: ${parts.join(", ")} from ${forEntry.label}`);
      if (out.rejected.length > 0) {
        view.appendLog(`[render] USE SETTINGS ignored: ${out.rejected.join(", ")}`, "error");
      }
    } catch (e) {
      // §9.7: the job fetch is the failure the operator must see, and jobs.lastError is that surface.
      jobs.lastError = { targetKey: forKey, message: e instanceof Error ? e.message : String(e) };
    } finally {
      acting = false;
    }
  }

  async function onReplaceClip(): Promise<void> {
    if (entry === null || replaceBlock !== null || target.kind !== "clip") return;
    acting = true;
    try {
      const out = await replaceAudio({
        clipId: target.id, ref: history.refOf(entry), durationSec: entry.dur_sec || null,
      });
      if (out.analyzeError) {
        view.appendLog(`[render] REPLACE CLIP: analysis failed — ${out.analyzeError.message}`, "error");
      }
    } finally {
      acting = false;
    }
  }
</script>

<div class="preview" data-region="preview-container">
  <button
    class="render"
    data-testid="preview-render"
    data-help={HELP.previewRender}
    data-blocked={blocked}
    title={blocked ?? ""}
    disabled={blocked !== null}
    onclick={onRender}>{label}</button>

  <select
    class="history"
    data-testid="preview-history"
    data-help={HELP.previewHistory}
    disabled={options.length === 0}
    value={history.preview === null ? "" : String(history.preview)}
    onchange={onHistoryChange}
  >
    {#if options.length === 0}
      <option value="">{HISTORY_EMPTY_LABEL}</option>
    {:else}
      {#each options as o (o.index)}
        <option value={String(o.index)}>{o.label}</option>
      {/each}
    {/if}
  </select>

  <canvas
    class="wave"
    data-testid="preview-wave"
    bind:this={canvasEl}
    width="900"
    height="30"
    onpointerdown={onWavePointerDown}
    onpointermove={onWavePointerMove}
    onpointerup={onWavePointerUp}
    onpointercancel={onWavePointerUp}
  ></canvas>

  <button
    class="transport"
    data-testid="preview-play"
    aria-label="play the previewed render"
    disabled={previewUrl === null}
    onclick={() => void previewPlayer.toggle()}>{previewPlayer.playing ? "■" : "▶"}</button>
  <span class="length" data-testid="preview-length">{lengthLabel(entry?.dur_sec ?? null)}</span>

  <span
    class="handle"
    data-testid="preview-drag-handle"
    data-help={HELP.previewDragToLane}
    draggable={entry !== null}
    ondragstart={onHandleDragStart}
    >⠿ drag to lane</span>

  <button
    class="action"
    data-testid="preview-use-settings"
    data-help={HELP.previewUseSettings}
    title={useSettingsNote ?? useBlock ?? ""}
    disabled={useBlock !== null}
    onclick={onUseSettings}>USE SETTINGS</button>
  <button
    class="action"
    data-testid="preview-replace-clip"
    data-help={HELP.previewReplaceClip}
    title={replaceBlock ?? ""}
    disabled={replaceBlock !== null}
    onclick={onReplaceClip}>REPLACE CLIP</button>
</div>

<style>
  .preview {
    box-sizing: border-box;
    height: 44px;
    width: 100%;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 0 8px;
    background: var(--panel);
    border: 1px solid var(--border);
  }
  .render {
    background: var(--turq-strong);
    border: 1px solid var(--turq-strong);
    color: white;
    font-family: inherit;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.04em;
    padding: 5px 12px;
    flex-shrink: 0;
    cursor: pointer;
  }
  .render:disabled {
    background: var(--panel2);
    color: var(--turq-strong);
    cursor: default;
  }
  .history {
    background: var(--panel2);
    border: 1px solid var(--border);
    color: var(--text);
    font-family: inherit;
    font-size: 10px;
    padding: 3px 5px;
    max-width: 170px;
    flex-shrink: 0;
  }
  .wave {
    box-sizing: border-box;
    flex: 1;
    min-width: 0;
    height: 30px;
    display: block;
    border: 1px solid var(--border);
    background: var(--panel2);
  }
  .transport,
  .action {
    background: var(--panel2);
    border: 1px solid var(--border);
    color: var(--text-dim);
    font-family: inherit;
    font-size: 10px;
    padding: 4px 7px;
    flex-shrink: 0;
    cursor: pointer;
  }
  .transport:disabled,
  .action:disabled {
    cursor: default;
  }
  .length,
  .handle {
    font-size: 10px;
    color: var(--text-dim);
    flex-shrink: 0;
  }
  .handle {
    cursor: grab;
  }
</style>
