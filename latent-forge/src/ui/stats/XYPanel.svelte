<script lang="ts">
  // XY view (spec §4.4): dataset scatter with X/Y selects. M1 draws the axes and
  // the empty state. M10 loads /forge/dataset_scalars, adds every numeric
  // crop-sidecar scalar to the selects, and highlights the selected lane's clips.
  import { linScale, niceTicks } from "../../lib/math/axis";
  import { fitPanelCanvas, panelColour } from "./panelCanvas";
  import { view } from "../../lib/stores/view.svelte";

  /** The three the contract always provides (spec §4.4). M10 appends the rest. */
  const FIELDS = ["bpm", "lufs", "rel_pos"];

  let x = $state("bpm");
  let y = $state("lufs");
  let canvasEl = $state<HTMLCanvasElement>();

  const PAD = { left: 34, right: 8, top: 8, bottom: 20 };

  $effect(() => {
    const canvas = canvasEl;
    void x;
    void y;
    void view.theme; // re-draw on DARK toggle -- colours are read via getComputedStyle below
    if (!canvas) return;
    const ctx = fitPanelCanvas(canvas);
    if (!ctx) return;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    const border = panelColour(canvas, "--border");
    const dim = panelColour(canvas, "--text-dim");

    // No data yet, so both axes run 0..1: the furniture, not a lie about values.
    const sx = linScale([0, 1], [PAD.left, w - PAD.right]);
    const sy = linScale([0, 1], [h - PAD.bottom, PAD.top]);

    ctx.strokeStyle = border;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(PAD.left + 0.5, PAD.top);
    ctx.lineTo(PAD.left + 0.5, h - PAD.bottom + 0.5);
    ctx.lineTo(w - PAD.right, h - PAD.bottom + 0.5);
    ctx.stroke();

    ctx.fillStyle = dim;
    ctx.font = "9px 'Space Grotesk', ui-monospace, monospace";
    for (const t of niceTicks(0, 1, 5)) {
      const px = Math.round(sx(t)) + 0.5;
      const py = Math.round(sy(t)) + 0.5;
      ctx.globalAlpha = 0.35;
      ctx.beginPath();
      ctx.moveTo(px, PAD.top);
      ctx.lineTo(px, h - PAD.bottom);
      ctx.moveTo(PAD.left, py);
      ctx.lineTo(w - PAD.right, py);
      ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      ctx.fillText(t.toFixed(1), px, h - PAD.bottom + 4);
      ctx.textAlign = "right";
      ctx.textBaseline = "middle";
      ctx.fillText(t.toFixed(1), PAD.left - 4, py);
    }
  });
</script>

<section class="panel" data-stats-panel="xy">
  <header>
    <span class="label">XY VIEW</span>
    <label>X <select bind:value={x}>{#each FIELDS as f}<option value={f}>{f}</option>{/each}</select></label>
    <label>Y <select bind:value={y}>{#each FIELDS as f}<option value={f}>{f}</option>{/each}</select></label>
  </header>
  <div class="body">
    <canvas bind:this={canvasEl}></canvas>
    <p class="empty">no analysis yet — choose lanes and press ANALYSE</p>
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
</style>
