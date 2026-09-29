<script lang="ts">
  // Spec 4.3: left 250px cell (playhead labels + transport), right 30px
  // canvas (bars, seconds, latent frames). Click locates the playhead;
  // middle-drag zooms/scrolls; shift+wheel scrolls; plain wheel is left to
  // the page (spec 4.3; §10 X1 for why the transport is here at all).
  import { arrangement } from "../../lib/stores/arrangement.svelte";
  import { playback } from "../../lib/stores/transport.svelte";
  import { view } from "../../lib/stores/view.svelte";
  import { HELP } from "../../lib/help/strings";
  import { formatBarsBeats, formatClock } from "../../lib/musictime";
  import {
    barNumberAt, frameAt, middleDragScrollDeltaSec, middleDragZoomFactor, rulerTicks,
  } from "../../lib/math/ruler";
  import { pxToSec, secToPx } from "../../lib/math/viewport";
  // The ruler-transport cell and every lane header (Timeline.svelte, Task 4)
  // sit in the same column and must be pixel-identical -- read the shared
  // constant, never hardcode 250 again (M1's final-review fix for the
  // ruler/lane alignment regression this same number caused once already).
  import { RULER_GUTTER_PX } from "../../lib/timelineLayout";

  let canvasEl = $state<HTMLCanvasElement>();
  let raf = 0;

  function cssVar(name: string, el: HTMLElement): string {
    return getComputedStyle(el).getPropertyValue(name).trim();
  }

  function fitCanvas(canvas: HTMLCanvasElement): CanvasRenderingContext2D | null {
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    if (w <= 0 || h <= 0) return null;
    if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
    }
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    return ctx;
  }

  $effect(() => {
    const canvas = canvasEl;
    const pxPerSec = arrangement.pxPerSec;
    const scrollSec = arrangement.scrollSec;
    const bpm = arrangement.bpm;
    const beatsPerBar = arrangement.beatsPerBar;
    const playheadSec = playback.playheadSec;
    void view.theme; // re-draw on DARK toggle -- colours are read via getComputedStyle below
    if (!canvas) return;
    const ctx = fitCanvas(canvas);
    if (!ctx) return;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    const dim = cssVar("--text-dim", canvas);
    const fg = cssVar("--text", canvas);
    const border = cssVar("--border", canvas);
    const accent = cssVar("--purple-strong", canvas);

    const fromSec = scrollSec;
    const toSec = scrollSec + w / pxPerSec;
    ctx.font = "9px 'Space Grotesk', ui-monospace, monospace";
    ctx.textBaseline = "top";
    for (const tick of rulerTicks(fromSec, toSec, bpm, beatsPerBar, pxPerSec)) {
      const x = Math.round(secToPx(tick.sec, scrollSec, pxPerSec)) + 0.5;
      ctx.strokeStyle = tick.kind === "bar" ? border : dim;
      ctx.beginPath();
      ctx.moveTo(x, tick.kind === "bar" ? 0 : h * 0.55);
      ctx.lineTo(x, h);
      ctx.stroke();
      if (tick.kind === "bar") {
        ctx.fillStyle = fg;
        ctx.fillText(String(barNumberAt(tick.sec, bpm, beatsPerBar)), x + 3, 0);
        ctx.fillStyle = dim;
        ctx.fillText(`${tick.sec.toFixed(1)}s`, x + 3, 11);
        ctx.fillText(`${frameAt(tick.sec)}f`, x + 3, 21);
      }
    }

    const px = Math.round(secToPx(playheadSec, scrollSec, pxPerSec)) + 0.5;
    if (px >= 0 && px <= w) {
      ctx.strokeStyle = accent;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(px, 0);
      ctx.lineTo(px, h);
      ctx.stroke();
    }
  });

  $effect(() => {
    function tick() {
      playback.syncPlayhead();
      raf = requestAnimationFrame(tick);
    }
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  });

  // ---------------------------------------------------------------- gestures

  type Drag = { mode: "seek" } | { mode: "zoom"; startX: number; startY: number; startPxPerSec: number; startScrollSec: number };
  let drag: Drag | null = null;

  function onPointerDown(e: PointerEvent) {
    if (!canvasEl) return;
    if (e.button === 1) {
      e.preventDefault();
      drag = { mode: "zoom", startX: e.clientX, startY: e.clientY, startPxPerSec: arrangement.pxPerSec, startScrollSec: arrangement.scrollSec };
      canvasEl.setPointerCapture(e.pointerId);
      return;
    }
    if (e.button !== 0) return;
    const rect = canvasEl.getBoundingClientRect();
    void playback.seek(pxToSec(e.clientX - rect.left, arrangement.scrollSec, arrangement.pxPerSec));
    drag = { mode: "seek" };
    canvasEl.setPointerCapture(e.pointerId);
  }

  function onPointerMove(e: PointerEvent) {
    if (!drag || !canvasEl) return;
    if (drag.mode === "zoom") {
      // middleDragZoomFactor is relative to the START of the drag, not the
      // previous event, so re-derive the absolute target each move rather
      // than compounding zoomBy's own multiplicative step.
      const targetPxPerSec = drag.startPxPerSec * middleDragZoomFactor(e.clientY - drag.startY);
      arrangement.zoomBy(targetPxPerSec / arrangement.pxPerSec);
      arrangement.setScrollSec(drag.startScrollSec + middleDragScrollDeltaSec(e.clientX - drag.startX, drag.startPxPerSec));
      return;
    }
    const rect = canvasEl.getBoundingClientRect();
    void playback.seek(pxToSec(e.clientX - rect.left, arrangement.scrollSec, arrangement.pxPerSec));
  }

  function onPointerUp() {
    drag = null;
  }

  function onWheel(e: WheelEvent) {
    if (!e.shiftKey) return; // plain wheel is left to the page (spec 4.3)
    e.preventDefault();
    arrangement.setScrollSec(arrangement.scrollSec + e.deltaY / arrangement.pxPerSec);
  }

  /**
   * Turning LOOP on with no region set yet (loopEndSec <= loopStartSec, the
   * store's initial state) defaults to the whole arrangement so the toggle
   * does something the first time it is pressed. Drag-to-define a custom
   * region is not spec'd anywhere this milestone reads and is left for a
   * later task if wanted (FLATLINE, 2026-09-17).
   */
  function onLoopClick() {
    if (!playback.loopOn && playback.loopEndSec <= playback.loopStartSec) {
      playback.setLoopRegion(0, Math.max(4, arrangement.arrangementEndSec));
    }
    playback.toggleLoop();
  }
</script>

<div class="ruler-row">
  <div class="transport" data-region="ruler-transport" style="width: {RULER_GUTTER_PX}px; flex: 0 0 {RULER_GUTTER_PX}px">
    <div class="buttons">
      <button
        class="primary"
        data-testid="transport-play"
        data-help={HELP.transportPlay}
        onclick={() => playback.togglePlay()}>{playback.playing ? "❚❚" : "▶"}</button
      >
      <button data-testid="transport-stop" data-help={HELP.transportStop} onclick={() => playback.stop()}>■</button>
      <button
        data-testid="transport-loop"
        data-help={HELP.transportLoop}
        class:active={playback.loopOn}
        onclick={onLoopClick}>LOOP</button
      >
    </div>
    <div class="readout">
      <span class="big">{formatClock(playback.playheadSec)}</span>
      <span class="sub"
        >bar {formatBarsBeats(playback.playheadSec, { bpm: arrangement.bpm, beatsPerBar: arrangement.beatsPerBar })} · frame {frameAt(
          playback.playheadSec,
        )}</span
      >
    </div>
  </div>
  <canvas
    class="ruler-canvas"
    data-region="ruler-canvas"
    data-help={HELP.ruler}
    bind:this={canvasEl}
    onpointerdown={onPointerDown}
    onpointermove={onPointerMove}
    onpointerup={onPointerUp}
    onwheel={onWheel}
  ></canvas>
</div>

<style>
  .ruler-row {
    display: flex;
    align-items: stretch;
    border-bottom: 1px solid var(--border);
    /* Every Timeline.svelte .lane-row carries a 3px lane-color border-left
       (inline style). This transparent match keeps the ruler-transport/
       ruler-canvas gutter the same width as the lane-header/lane-canvas
       gutter -- otherwise the ruler and the lane grid start 3px apart.
       Preserved from Timeline.svelte's pre-Task-3 .ruler-row (M1's
       final-review fix for the same regression) now that this component
       owns the row. */
    border-left: 3px solid transparent;
  }
  .transport {
    box-sizing: border-box;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 0 6px;
    background: var(--panel2);
    border-right: 1px solid var(--border);
  }
  .buttons {
    display: flex;
    gap: 3px;
  }
  button {
    background: var(--panel);
    border: 1px solid var(--border);
    color: var(--text);
    font-family: inherit;
    font-size: 10px;
    letter-spacing: 0.04em;
    padding: 3px 6px;
    cursor: pointer;
  }
  button.primary {
    background: var(--turq-strong);
    border-color: var(--turq-strong);
    color: var(--panel);
  }
  button.active {
    border-color: var(--purple-strong);
    color: var(--purple-strong);
  }
  .readout {
    display: flex;
    flex-direction: column;
    line-height: 1.15;
    font-variant-numeric: tabular-nums;
    margin-left: auto;
    text-align: right;
  }
  .big {
    font-size: 12px;
    color: var(--text);
  }
  .sub {
    font-size: 9px;
    color: var(--text-dim);
  }
  .ruler-canvas {
    flex: 1;
    min-width: 0;
    height: 30px;
    display: block;
    cursor: crosshair;
  }
</style>
