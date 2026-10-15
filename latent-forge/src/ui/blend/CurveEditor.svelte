<script lang="ts">
  // Owner: KUANG (created 2026-10-15), from WINTERMUTE's phase-1 plan
  // The drawable per-DiT-block curve (spec 2026-10-15-adapter-mixer-design §4.2). Drag across the
  // columns to draw (every column between two pointer samples is filled), double-click a column to
  // type its value. Emits a NEW array on every change; never mutates `values`.
  import { CURVE_MAX, CURVE_MIN, N_BLOCKS, clampValue, drawSegment } from "../../lib/blend/curves";

  interface Props {
    values: number[];
    onChange: (v: number[]) => void;
    /** Grey bars behind the curve, same scale (e.g. the adapter's per-block change size). */
    underlay?: number[] | null;
    height?: number;
  }
  let { values, onChange, underlay = null, height = 110 }: Props = $props();

  const W = 240;                      // viewBox width: 10 units per block
  const COL = W / N_BLOCKS;
  const SPAN = CURVE_MAX - CURVE_MIN;
  const yOf = (v: number) => ((CURVE_MAX - v) / SPAN) * 100;
  const zeroY = yOf(0);
  const oneY = yOf(1);

  let svgEl: SVGSVGElement | undefined = $state();
  let last: { i: number; v: number } | null = null;
  let working: number[] = [];
  // The curve before the current stroke, and whether the pointer moved: a double-click's first click is a
  // one-column tap, which startEdit undoes so typing starts from the value the user saw (KUANG 2026-10-15).
  let before: number[] | null = null;
  let moved = false;
  let editing = $state<number | null>(null);
  let typed = $state<number | string>("");   // bind:value on a number input yields a number

  function sample(e: PointerEvent): { i: number; v: number } {
    const r = svgEl!.getBoundingClientRect();
    const i = Math.max(0, Math.min(N_BLOCKS - 1, Math.floor(((e.clientX - r.left) / r.width) * N_BLOCKS)));
    const v = clampValue(Number((CURVE_MAX - ((e.clientY - r.top) / r.height) * SPAN).toFixed(2)));
    return { i, v };
  }
  function down(e: PointerEvent) {
    if (editing !== null) return;
    (e.currentTarget as Element).setPointerCapture?.(e.pointerId);
    const s = sample(e);
    before = [...values];
    moved = false;
    working = drawSegment(values, s.i, s.v, s.i, s.v);
    last = s;
    onChange(working);
  }
  function move(e: PointerEvent) {
    if (!last) return;
    const s = sample(e);
    if (s.i !== last.i) moved = true;
    working = drawSegment(working, last.i, last.v, s.i, s.v);
    last = s;
    onChange(working);
  }
  function up() {
    last = null;
  }
  function startEdit(i: number) {
    let cur = values;
    if (before && !moved) {                 // undo the tap that the double-click's first click drew
      cur = before;
      onChange(before);
    }
    before = null;
    editing = i;
    typed = String(cur[i]);
  }
  function commit() {
    const v = Number(typed);
    if (editing !== null && Number.isFinite(v)) {
      const next = [...values];
      next[editing] = clampValue(v);
      onChange(next);
    }
    editing = null;
  }
</script>

<div class="curve">
  <svg bind:this={svgEl} data-testid="curve-svg" viewBox="0 0 {W} 100" preserveAspectRatio="none"
    style="height:{height}px" role="application" aria-label="per-block curve"
    onpointerdown={down} onpointermove={move} onpointerup={up} onpointercancel={up}>
    <line x1="0" x2={W} y1={oneY} y2={oneY} class="ref" />
    <line x1="0" x2={W} y1={zeroY} y2={zeroY} class="zero" />
    {#each values as v, i (i)}
      {#if underlay}
        <rect class="under" x={i * COL + 1} width={COL - 2}
          y={Math.min(yOf(underlay[i] ?? 0), zeroY)} height={Math.abs(yOf(underlay[i] ?? 0) - zeroY)} />
      {/if}
      <rect class="col" data-testid="curve-col-{i}" data-value={String(v)} role="button" tabindex="-1"
        aria-label="block {i}: {v}"
        x={i * COL + 1.5} width={COL - 3}
        y={Math.min(yOf(v), zeroY)} height={Math.max(0.5, Math.abs(yOf(v) - zeroY))}
        ondblclick={() => startEdit(i)} />
    {/each}
  </svg>
  <div class="axis"><span>block 0</span><span>12</span><span>23</span></div>
  {#if editing !== null}
    <label class="edit">block {editing}
      <input data-testid="curve-value-input" type="number" step="0.05" min={CURVE_MIN} max={CURVE_MAX}
        bind:value={typed} onkeydown={(e) => { if (e.key === "Enter") commit(); if (e.key === "Escape") editing = null; }}
        onblur={commit} />
    </label>
  {/if}
</div>

<style>
  .curve { position: relative; user-select: none; }
  svg { width: 100%; display: block; background: #121318; border: 1px solid #2a2a30; cursor: crosshair; touch-action: none; }
  .col { fill: #6aa8ff; }
  .under { fill: #3a3d46; }
  .ref { stroke: #444; stroke-dasharray: 2 2; stroke-width: 0.5; }
  .zero { stroke: #777; stroke-width: 0.6; }
  .axis { display: flex; justify-content: space-between; font-size: 10px; color: #888; }
  .edit { position: absolute; right: 4px; top: 4px; font-size: 11px; background: #1c1d22; padding: 2px 4px; }
  .edit input { width: 56px; }
</style>
