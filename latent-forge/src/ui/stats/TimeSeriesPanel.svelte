<script lang="ts">
  // TIME SERIES view (spec §4.4): feature select, one line per clip of the
  // selected lane(s) over latent frames. M1 draws the axes and the empty state.
  // M10 loads /forge/stats and adds the crop `*_ts` fields to the select.
  import { linScale, niceTicks } from "../../lib/math/axis";
  import { fitPanelCanvas, panelColour } from "./panelCanvas";
  import { view } from "../../lib/stores/view.svelte";

  /** Computed for renders and uploads, so always offered (spec §4.4). */
  const FEATURES = ["rms", "onset_strength", "spectral_centroid"];

  let feature = $state("rms");
  let canvasEl = $state<HTMLCanvasElement>();

  const PAD = { left: 34, right: 8, top: 8, bottom: 20 };

  $effect(() => {
    const canvas = canvasEl;
    void feature;
    void view.theme; // re-draw on DARK toggle -- colours are read via getComputedStyle below
    if (!canvas) return;
    const ctx = fitPanelCanvas(canvas);
    if (!ctx) return;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    const border = panelColour(canvas, "--border");
    const dim = panelColour(canvas, "--text-dim");

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
      const py = Math.round(sy(t)) + 0.5;
      ctx.globalAlpha = 0.35;
      ctx.beginPath();
      ctx.moveTo(PAD.left, py);
      ctx.lineTo(w - PAD.right, py);
      ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.textAlign = "right";
      ctx.textBaseline = "middle";
      ctx.fillText(t.toFixed(1), PAD.left - 4, py);
    }
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    ctx.fillText("latent frame", Math.round(sx(0.5)), h - PAD.bottom + 4);
  });
</script>

<section class="panel" data-stats-panel="timeseries">
  <header>
    <span class="label">TIME SERIES</span>
    <label>FEATURE <select bind:value={feature}>{#each FEATURES as f}<option value={f}>{f}</option>{/each}</select></label>
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
