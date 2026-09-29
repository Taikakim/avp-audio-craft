<script lang="ts">
  // Port of the handoff's a2a envelope overlay (v3 lines 68-81, `_envelope`
  // 1583-1596): 4 draggable nodes, 3 bendable segments, positioned over the
  // master strip's 56px canvas. Spec §4.3: inactive (28% opacity, no pointer
  // events) unless the selected clip has A2A on. All geometry and drag math
  // comes from lib/math/envelope.ts (Task 8) -- this file only wires DOM
  // events to it.
  import { envelopeGeometry, nodeDragValue, segmentDragValue } from "../../lib/math/envelope";
  import type { Envelope } from "../../lib/forge/types";

  let { envelope, active, onChange }: {
    envelope: Envelope;
    active: boolean;
    onChange: (env: Envelope) => void;
  } = $props();

  let root = $state<HTMLDivElement>();
  const geo = $derived(envelopeGeometry(envelope));

  /**
   * Same float64-ULP guard as envelope.ts's own `clean()` (Task 8's report:
   * `(266.67+400)/2` prints `333.33500000000004`, not `333.335`) -- here it's
   * `nodeDragValue`/`segmentDragValue`'s subtraction-then-division chasing a
   * `clientY - top` that isn't exactly representable (e.g. 216.8-200 lands on
   * 16.799999999999997), which lands a drag to a point-blank stop at
   * 0.7499999999999998 instead of 0.75. Applied here, not inside envelope.ts,
   * because that module is Task 8's committed contract surface (its docblock
   * warns of a server-side Python mirror for `sampleEnvelope`); this rounding
   * is purely a UI-drag-value concern, scoped to the one file that owns it.
   */
  function clean(v: number): number {
    return Math.round(v * 1e6) / 1e6;
  }

  type Drag =
    | { mode: "point"; idx: number }
    | { mode: "segment"; idx: number; startY: number; startCurve: number };
  let drag: Drag | null = null;

  function onNodeDown(i: number, e: PointerEvent) {
    if (e.button !== 0 || !active) return;
    e.stopPropagation();
    drag = { mode: "point", idx: i };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp, { once: true });
  }

  function onSegmentDown(i: number, e: PointerEvent) {
    if (e.button !== 0 || !active) return;
    e.stopPropagation();
    drag = { mode: "segment", idx: i, startY: e.clientY, startCurve: envelope.curves[i] };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp, { once: true });
  }

  function onMove(e: PointerEvent) {
    if (!drag || !root) return;
    if (drag.mode === "point") {
      const rect = root.getBoundingClientRect();
      const v = clean(nodeDragValue(e.clientY, rect.top, rect.height));
      const points = [...envelope.points] as Envelope["points"];
      points[drag.idx] = v;
      onChange({ points, curves: envelope.curves });
    } else {
      const c = clean(segmentDragValue(drag.startCurve, drag.startY, e.clientY));
      const curves = [...envelope.curves] as Envelope["curves"];
      curves[drag.idx] = c;
      onChange({ points: envelope.points, curves });
    }
  }

  function onUp() {
    drag = null;
    window.removeEventListener("pointermove", onMove);
  }
</script>

<div
  bind:this={root}
  class="envelope"
  data-region="envelope-overlay"
  data-active={active}
  style="opacity: {active ? 1 : 0.28}; pointer-events: {active ? 'auto' : 'none'};"
>
  <svg viewBox="0 0 400 100" preserveAspectRatio="none">
    <path d={geo.pathD} class="curve" />
    {#each geo.segments as seg, i}
      <path
        d="M {seg.x1},{seg.y1} L {seg.x2},{seg.y2}"
        class="hit"
        role="separator"
        aria-label="bend envelope segment {i + 1}"
        data-testid="envelope-segment-{i}"
        onpointerdown={(e) => onSegmentDown(i, e)}
      />
    {/each}
  </svg>
  {#each geo.nodes as node, i}
    <div
      class="node"
      role="separator"
      aria-label="envelope node {i + 1}"
      data-testid="envelope-node-{i}"
      style="left: calc({(i / 3) * 100}% - 4.5px); top: {node.y}%;"
      onpointerdown={(e) => onNodeDown(i, e)}
    ></div>
  {/each}
</div>

<style>
  /* Global constraint: no border radius anywhere (spec §4.1, tokens.css) --
     the handoff drew round dots here (v3 lines 68-81); this app's design
     language is rectilinear everywhere else (see ClipView's trim handles),
     so the node handle is a small square, not a circle. */
  .envelope {
    position: absolute;
    inset: 0;
  }
  svg {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
  }
  .curve {
    stroke: var(--purple-strong);
    stroke-width: 2;
    fill: none;
    vector-effect: non-scaling-stroke;
  }
  .hit {
    stroke: transparent;
    stroke-width: 16;
    cursor: ns-resize;
  }
  .node {
    position: absolute;
    width: 9px;
    height: 9px;
    margin-top: -4.5px;
    background: var(--purple-strong);
    border: 1.5px solid var(--bg);
    box-sizing: border-box;
    cursor: ns-resize;
  }
</style>
