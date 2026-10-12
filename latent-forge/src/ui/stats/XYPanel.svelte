<script lang="ts">
  // XY view (spec §4.4): dataset scatter with X/Y selects populated from
  // /forge/dataset_scalars's own `fields` (never hard-coded past the initial
  // M1 default of bpm/lufs/rel_pos -- the server may report more numeric
  // crop-sidecar scalars). M1 T13 drew the axes and the empty state; this
  // task wires statsClient.scalars in, requests a fresh pair whenever X or Y
  // changes, and highlights the selected lane's clips.
  //
  // /forge/dataset_scalars does not depend on ANALYSE or on `latents` at all
  // (spec §6.5), so this panel drives its own requests from its own X/Y
  // selects rather than waiting for StatisticsView's ANALYSE handler (M10 T7).
  //
  // Highlighting needs to know which crop_ids are in the selected lane. M10
  // must not depend on M5's arrangement store (the milestone's own
  // constraint), so that mapping arrives as the laneCropIds prop -- with no
  // prop (the default before Task 7 or a later milestone wires a real
  // source) nothing is highlighted, never everything.
  import { linScale, niceTicks } from "../../lib/math/axis";
  import { fitPanelCanvas, panelColour } from "./panelCanvas";
  import { statsClient } from "../../lib/stats/statsClient.svelte";
  import { domainOf, finitePoints } from "../../lib/stats/xyDomain";

  /** The three the contract always provides (spec §4.4) -- the default
   *  before the first /forge/dataset_scalars response, and the fallback if a
   *  response somehow reports zero fields. */
  const DEFAULT_FIELDS = ["bpm", "lufs", "rel_pos"];

  interface Props {
    /** crop_ids belonging to the currently selected lane (M10 T7's LaneSel).
     *  null/undefined = no highlighting, never "highlight everything". */
    laneCropIds?: ReadonlySet<string> | null;
  }
  let { laneCropIds = null }: Props = $props();

  let x = $state("bpm");
  let y = $state("lufs");
  let canvasEl = $state<HTMLCanvasElement>();

  const scalars = $derived(statsClient.scalars);
  const scalarsPending = $derived(statsClient.scalarsPending);
  const scalarsError = $derived(statsClient.scalarsError);
  const fields = $derived(scalars?.fields.length ? scalars.fields : DEFAULT_FIELDS);
  const points = $derived(scalars ? finitePoints(scalars.points) : []);

  const PAD = { left: 34, right: 8, top: 8, bottom: 20 };

  // Fires on mount (x/y start at their defaults) and again on every X/Y
  // change -- independent of ANALYSE, per the header comment above.
  $effect(() => {
    void statsClient.requestScalars(x, y);
  });

  $effect(() => {
    const canvas = canvasEl;
    const pts = points;
    const highlight = laneCropIds;
    if (!canvas) return;
    const ctx = fitPanelCanvas(canvas);
    if (!ctx) return;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    const border = panelColour(canvas, "--border");
    const dim = panelColour(canvas, "--text-dim");
    const turq = panelColour(canvas, "--turq-strong");

    const [xLo, xHi] = domainOf(pts, "x");
    const [yLo, yHi] = domainOf(pts, "y");
    const sx = linScale([xLo, xHi], [PAD.left, w - PAD.right]);
    const sy = linScale([yLo, yHi], [h - PAD.bottom, PAD.top]);

    ctx.strokeStyle = border;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(PAD.left + 0.5, PAD.top);
    ctx.lineTo(PAD.left + 0.5, h - PAD.bottom + 0.5);
    ctx.lineTo(w - PAD.right, h - PAD.bottom + 0.5);
    ctx.stroke();

    ctx.fillStyle = dim;
    ctx.font = "9px 'Space Grotesk', ui-monospace, monospace";
    for (const t of niceTicks(xLo, xHi, 5)) {
      const px = Math.round(sx(t)) + 0.5;
      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      ctx.fillText(t.toFixed(1), px, h - PAD.bottom + 4);
    }
    for (const t of niceTicks(yLo, yHi, 5)) {
      const py = Math.round(sy(t)) + 0.5;
      ctx.textAlign = "right";
      ctx.textBaseline = "middle";
      ctx.fillText(t.toFixed(1), PAD.left - 4, py);
    }

    // Dim points first, highlighted points on top, so a highlighted clip is
    // never hidden under an unhighlighted one sharing its pixel.
    ctx.fillStyle = dim;
    for (const p of pts) {
      if (highlight?.has(p.crop_id)) continue;
      ctx.beginPath();
      ctx.arc(sx(p.x), sy(p.y), 2, 0, Math.PI * 2);
      ctx.fill();
    }
    if (highlight) {
      ctx.fillStyle = turq;
      for (const p of pts) {
        if (!highlight.has(p.crop_id)) continue;
        ctx.beginPath();
        ctx.arc(sx(p.x), sy(p.y), 3, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  });
</script>

<section class="panel" data-stats-panel="xy">
  <header>
    <span class="label">XY VIEW</span>
    <label>X <select bind:value={x}>{#each fields as f}<option value={f}>{f}</option>{/each}</select></label>
    <label>Y <select bind:value={y}>{#each fields as f}<option value={f}>{f}</option>{/each}</select></label>
  </header>
  <div class="body">
    <canvas bind:this={canvasEl}></canvas>
    {#if scalarsError}
      <p class="empty error" data-testid="xy-error">{scalarsError}</p>
    {:else if scalarsPending && !scalars}
      <p class="empty">loading…</p>
    {:else if scalars && points.length === 0}
      <p class="empty">no scalar data for this pair</p>
    {/if}
  </div>
</section>

<style>
  .panel {
    border: 1px solid var(--border);
    background: var(--panel);
    display: flex;
    flex-direction: column;
    flex: 1;
    min-height: 220px;
    min-width: 0;
  }
  header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 8px;
    background: var(--panel2);
    border-bottom: 1px solid var(--border);
  }
  .label {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.08em;
    color: var(--text-dim);
  }
  label {
    font-size: 10px;
    color: var(--text-dim);
    display: flex;
    align-items: center;
    gap: 4px;
  }
  select {
    background: var(--panel2);
    border: 1px solid var(--border);
    color: var(--text);
    font-family: inherit;
    font-size: 10px;
    padding: 2px 4px;
  }
  .body {
    position: relative;
    flex: 1;
    min-height: 0;
  }
  canvas {
    display: block;
    width: 100%;
    height: 100%;
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
  .empty.error {
    color: var(--red);
  }
</style>
