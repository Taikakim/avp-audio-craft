<script lang="ts">
  // The detune scan strip (spec §5.4; v3 332-337). Task 5's scanDetune gives
  // 51 points across ±100 ¢; this draws them, marks the clip's current detune
  // in red, and writes a new detune back on click or drag.
  //
  // Detune is written ONLY through arrangement.setDetune, which clamps to ±100
  // and rounds. Writing clip.detune_cents directly would appear to work -- the
  // clip is a $state deep proxy -- while silently skipping both.
  //
  // This component does NOT debounce a /forge/stretch. M5 T10 already owns
  // that (scheduleStretch, 400 ms), and the lane header's DETUNE ¢ field
  // writes detune too, so Task 11's tab arms it once for BOTH writers.
  //
  // THE AXIS IS RELATIVE. The fold this strip scans is normally the fold of
  // the clip's STRETCHED preview, which runStretch has already pitch-shifted
  // by clip.detune_cents / 100 -- so scan step c means "the clip's current
  // detune, plus c". Hence: the red mark sits at the strip's CENTRE, both
  // writers ADD (clip.detune_cents + …), and the label names the origin. The
  // `detuneCents` prop is the ANALYSIS detune (Task 11's analysisDetuneCents),
  // which is 0 for a stretched preview and clip.detune_cents for a clip that
  // has none -- passing it to scanDetune is what keeps the axis relative in
  // both cases. See the plan's Normative block and Open question 6.
  import {
    DETUNE_MAX,
    DETUNE_MIN,
    type DetuneScan,
    type ScanCriterion,
    bestDetune,
    scanDetune,
  } from "../../lib/chroma/detuneScan";
  import type { ChromaResult } from "../../lib/chroma/chromaClient.svelte";
  import {
    SCAN_GRID_CENTS,
    SCAN_H,
    SCAN_W,
    centsAtX,
    criterionLabel,
    criterionValues,
    nextCriterion,
    scanLabel,
    scanRange,
    scanY,
    xForCents,
  } from "../../lib/chroma/scanStrip";
  import type { ForgeClip } from "../../lib/forge/types";
  import { HELP } from "../../lib/help/strings";
  import { arrangement } from "../../lib/stores/arrangement.svelte";
  import { chromaColour, fitChromaCanvas } from "./chromaCanvas";

  interface Props {
    clip: ForgeClip | null;
    result: ChromaResult | null;
    target: Float32Array;
    criterion: ScanCriterion;
    /** The ANALYSIS detune (Task 11's `analysisDetuneCents`), never the clip's. */
    detuneCents?: number;
    oncriterion?: (c: ScanCriterion) => void;
  }
  let { clip, result, target, criterion, detuneCents = 0, oncriterion }: Props = $props();

  let canvasEl = $state<HTMLCanvasElement>();
  let dragging = false;
  /** The clip's detune when the drag began. A drag sets start + pointer offset (absolute within
   *  the drag); adding the offset to the LIVE detune on every move compounded it to ±100 within a
   *  few events (review 2026-10-01). */
  let dragStartCents = 0;

  const scan = $derived<DetuneScan | null>(
    result ? scanDetune(result.fold12, result.T, target, detuneCents) : null,
  );
  // `0` because the axis is relative: the clip's current detune IS the centre.
  // Its absolute value goes in as the origin the label names.
  const label = $derived(
    !clip || !scan ? "detune scan · no clip" : scanLabel(scan, 0, criterion, clip.detune_cents),
  );

  /** Every write is an OFFSET from where the clip already is. */
  function applyOffset(offsetCents: number): void {
    if (!clip) return;
    const next = clip.detune_cents + offsetCents;
    // setDetune clamps and rounds too (M5 T1); clamping here says out loud
    // that an additive write can leave the range that an absolute one cannot.
    arrangement.setDetune(clip.id, Math.min(DETUNE_MAX, Math.max(DETUNE_MIN, next)));
  }

  function draw(): void {
    const canvas = canvasEl;
    if (!canvas) return;
    const ctx = fitChromaCanvas(canvas);
    if (!ctx) return;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;

    ctx.fillStyle = chromaColour(canvas, "--panel2");
    ctx.fillRect(0, 0, w, h);
    if (!clip || !scan) return;

    ctx.strokeStyle = chromaColour(canvas, "--border");
    ctx.lineWidth = 1;
    for (const c of SCAN_GRID_CENTS) {
      const x = Math.round(xForCents(c, w)) + 0.5;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
    }

    const values = criterionValues(scan, criterion);
    const range = scanRange(values);
    ctx.beginPath();
    values.forEach((v, i) => {
      const x = xForCents(scan.cents[i], w);
      const y = scanY(v, range, h);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.strokeStyle = chromaColour(canvas, "--turq-strong");
    ctx.lineWidth = 1.6;
    ctx.stroke();

    // The clip's current detune is the axis ORIGIN, so the mark is at 0
    // relative -- the centre of the strip -- whatever that detune is.
    const bx = Math.round(xForCents(0, w)) + 0.5;
    ctx.strokeStyle = chromaColour(canvas, "--red");
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(bx, 0);
    ctx.lineTo(bx, h);
    ctx.stroke();
  }

  function setFromPointer(e: PointerEvent): void {
    const canvas = canvasEl;
    if (!canvas || !clip) return;
    const rect = canvas.getBoundingClientRect();
    const next = dragStartCents + centsAtX(e.clientX - rect.left, rect.width);
    arrangement.setDetune(clip.id, Math.min(DETUNE_MAX, Math.max(DETUNE_MIN, next)));
  }

  function onPointerDown(e: PointerEvent): void {
    if (e.button !== 0 || !clip) return;
    e.preventDefault();
    dragging = true;
    dragStartCents = clip.detune_cents;
    canvasEl?.setPointerCapture?.(e.pointerId);
    setFromPointer(e);
  }

  function onPointerMove(e: PointerEvent): void {
    if (!dragging) return;
    setFromPointer(e);
  }

  function onPointerUp(e: PointerEvent): void {
    dragging = false;
    canvasEl?.releasePointerCapture?.(e.pointerId);
  }

  function onBest(): void {
    if (!clip || !scan) return;
    // ADDITIVE. bestDetune returns a step on the relative axis, so assigning
    // it bare made a second press walk the detune (d -> best -> best + best)
    // instead of converging on it.
    applyOffset(bestDetune(scan, criterion));
  }

  $effect(() => {
    void clip?.detune_cents;
    void scan;
    void criterion;
    void detuneCents;
    draw();
  });
</script>

<canvas
  bind:this={canvasEl}
  data-testid="chroma-scan-strip"
  data-help={HELP.chromaDetuneScan}
  width={SCAN_W}
  height={SCAN_H}
  onpointerdown={onPointerDown}
  onpointermove={onPointerMove}
  onpointerup={onPointerUp}
  onpointercancel={onPointerUp}
></canvas>
<div class="row">
  <span class="label" data-testid="chroma-scan-label">{label}</span>
  <button
    type="button"
    data-testid="chroma-best-criterion"
    data-help={HELP.chromaBestCriterion}
    onclick={() => oncriterion?.(nextCriterion(criterion))}>{criterionLabel(criterion)}</button
  >
  <button type="button" data-testid="chroma-best" data-help={HELP.chromaBest} onclick={onBest}>BEST</button>
</div>

<style>
  canvas {
    display: block;
    box-sizing: border-box;
    width: 100%;
    height: 30px;
    flex-shrink: 0;
    border: 1px solid var(--border);
    cursor: ew-resize;
    margin-top: 2px;
  }
  .row {
    display: flex;
    align-items: center;
    gap: 5px;
  }
  .label {
    flex: 1;
    font-size: 9px;
    color: var(--text-dim);
  }
  button {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text);
    font-size: 9px;
    padding: 2px 5px;
    cursor: pointer;
  }
</style>
