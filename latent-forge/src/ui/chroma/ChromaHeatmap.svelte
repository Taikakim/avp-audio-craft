<script lang="ts">
  // The chroma heatmap (spec §5.4; v3 markup 343-344, logic _drawChroma
  // 1160-1215). Four views; the target's profile as a reference row across the
  // top; middle-drag zooms the frame axis (up/down) and scrolls it
  // (left/right) in one gesture, as the timeline ruler does -- INCLUDING M5
  // T3's convention that the gesture is anchored to the START of the drag,
  // not the previous pointermove: re-derive the absolute window from the
  // window the drag started with every move, rather than compounding onto
  // the already-clamped prop from the last move. Compounding onto `win`
  // (which clampWindow may already have floored or ceilinged) makes the
  // gesture non-reversible once a drag hits either bound and the pointer
  // reverses -- the same bug M5 T3's own comment exists to prevent.
  //
  // This component owns NO state but the gesture: the window arrives as a prop
  // and goes back out through onwin, so Task 11's tab is its single owner and
  // the match-curve overlay (Task 7) is guaranteed to be drawing the same
  // frames underneath the same pixels.
  //
  // Colours: the CELL ramp builds its own oklch() string (consonanceColor.ts,
  // whose comment says why); every flat colour goes through chromaColour(),
  // which has a per-token fallback because ctx.fillStyle = "" silently keeps
  // whatever colour was there before.
  //
  // DETUNE: `detuneCents` is the ANALYSIS detune (Task 11's
  // analysisDetuneCents), not the clip's. When the analysed audio was the
  // stretched preview it is 0, because M5 T10's runStretch already shifted
  // that audio by clip.detune_cents / 100 and rotating the fold again would
  // apply the detune twice.
  import { fold12Column } from "../../lib/chroma/bins";
  import type { ChromaResult } from "../../lib/chroma/chromaClient.svelte";
  import { consonanceColor, targetRowColor } from "../../lib/chroma/consonanceColor";
  import {
    BODY_Y,
    CELL_FLOOR,
    type ChromaView,
    type FrameWindow,
    REF_ROW_H,
    cellValue,
    frameColumn,
    frameToX,
    rowCount,
    rowHeight,
    rowToY,
    scrollWindow,
    zoomWindow,
  } from "../../lib/chroma/heatmapGeometry";
  import { matchFrame, rotate } from "../../lib/chroma/match";
  import { HELP } from "../../lib/help/strings";
  import { middleDragZoomFactor } from "../../lib/math/ruler";
  import { chromaColour, fitChromaCanvas } from "./chromaCanvas";

  interface Props {
    view: ChromaView;
    win: FrameWindow;
    result: ChromaResult | null;
    target: Float32Array;
    /**
     * The ANALYSIS detune, NOT `clip.detune_cents`. Task 11 derives it as
     * `analysisDetuneCents`: 0 when the analysed ref was `clip.previewAudio`
     * (M5 T10's runStretch already pitch-shifted that audio by the clip's
     * detune, so the fold12 in `result` is already detuned and rotating it
     * again would apply the detune twice), and `clip.detune_cents` when the
     * analysed ref was the raw `clip.audio`. Never re-derive the rule here.
     */
    detuneCents?: number;
    onwin?: (w: FrameWindow) => void;
  }
  let { view, win, result, target, detuneCents = 0, onwin }: Props = $props();

  let canvasEl = $state<HTMLCanvasElement>();
  // startWin is `win` AS IT STOOD when the drag began -- every move below
  // recomputes from it, never from the current `win` prop, so the gesture
  // stays reversible even after clampWindow has floored or ceilinged it.
  let drag: { startX: number; startY: number; anchorFrac: number; startWin: FrameWindow } | null = null;

  function draw(): void {
    const canvas = canvasEl;
    if (!canvas) return;
    const ctx = fitChromaCanvas(canvas);
    if (!ctx) return;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;

    ctx.fillStyle = chromaColour(canvas, "--panel2");
    ctx.fillRect(0, 0, w, h);
    if (!result) return;

    // The reference row: the target itself, twelve cells wide.
    const refW = w / 12;
    for (let p = 0; p < 12; p++) {
      ctx.fillStyle = targetRowColor(target[p] ?? 0);
      ctx.fillRect(p * refW, 0, refW, REF_ROW_H);
    }

    const rows = rowCount(view);
    const rh = rowHeight(view, h);
    const semis = detuneCents / 100;
    const from = Math.max(0, Math.floor(win.from));
    const to = Math.min(result.T, Math.ceil(win.to));
    const colW = Math.max(0.5, w / Math.max(1, to - from));

    for (let f = from; f < to; f++) {
      const m = matchFrame(rotate(fold12Column(result.fold12, result.T, f), semis), target);
      const x = frameToX(f, win, w);
      // GLOBAL: fold this frame ONCE. cellValue's GLOBAL branch folds all 384
      // bins and returns one class, so calling it inside the row loop folded
      // the same frame twelve times per repaint -- including on every
      // pointermove of a middle-drag. A band view's rows are single array
      // reads, so it keeps cellValue and materialises nothing.
      const col = view === "global" ? frameColumn(result, view, f) : null;
      for (let r = 0; r < rows; r++) {
        const v = col ? col[r] : cellValue(result, view, f, r);
        if (v < CELL_FLOOR) continue;
        ctx.fillStyle = consonanceColor(v, m);
        ctx.fillRect(x, rowToY(r, view, h), colW + 0.6, Math.max(0.7, rh + 0.4));
      }
    }

    // Pitch-class separators, so 128 raw bins stay readable as twelve classes.
    ctx.strokeStyle = chromaColour(canvas, "--border");
    ctx.lineWidth = 1;
    ctx.globalAlpha = 0.55;
    for (let p = 1; p < 12; p++) {
      const y = Math.round(BODY_Y + (h - BODY_Y) * (1 - p / 12)) + 0.5;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  }

  function onPointerDown(e: PointerEvent): void {
    if (e.button !== 1) return; // middle only: left is hover (Task 10)
    e.preventDefault();
    const canvas = canvasEl;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    drag = {
      startX: e.clientX, startY: e.clientY, startWin: win,
      anchorFrac: (e.clientX - rect.left) / Math.max(1, rect.width),
    };
    canvas.setPointerCapture?.(e.pointerId);
  }

  function onPointerMove(e: PointerEvent): void {
    const canvas = canvasEl;
    if (!drag || !canvas || !result) return;
    const rect = canvas.getBoundingClientRect();
    // Both deltas are measured from the START of the drag (drag.startX/Y),
    // never from the previous move, and both apply to drag.startWin, never
    // to the current `win` prop -- see the WHY comment above the component.
    const totalDy = e.clientY - drag.startY;
    const totalDx = e.clientX - drag.startX;
    let next = zoomWindow(drag.startWin, middleDragZoomFactor(totalDy), drag.anchorFrac, result.T);
    next = scrollWindow(next, totalDx, Math.max(1, rect.width), result.T);
    onwin?.(next);
  }

  function onPointerUp(e: PointerEvent): void {
    drag = null;
    canvasEl?.releasePointerCapture?.(e.pointerId);
  }

  $effect(() => {
    void view;
    void win;
    void result;
    void target;
    void detuneCents;
    draw();
  });
</script>

<div class="wrap">
  <canvas
    bind:this={canvasEl}
    data-testid="chroma-heatmap"
    data-help={HELP.chromaHeatmap}
    onpointerdown={onPointerDown}
    onpointermove={onPointerMove}
    onpointerup={onPointerUp}
    onpointercancel={onPointerUp}
  ></canvas>
  {#if !result}
    <p class="empty" data-testid="chroma-heatmap-empty">no chroma yet</p>
  {/if}
</div>

<style>
  .wrap {
    position: relative;
    flex: 1;
    min-width: 0;
    min-height: 0;
  }
  canvas {
    display: block;
    width: 100%;
    height: 100%;
    box-sizing: border-box;
    border: 1px solid var(--border);
  }
  .empty {
    position: absolute;
    inset: 0;
    margin: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 10px;
    color: var(--text-dim);
    pointer-events: none;
  }
</style>
