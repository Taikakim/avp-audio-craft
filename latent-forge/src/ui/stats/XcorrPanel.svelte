<script lang="ts">
  // 256 x 256 DIM CROSS-CORRELATION, 300 px (spec §4.4). M1 draws the frame,
  // the dimension ticks and the empty state. M10 fills it from /forge/stats's
  // `xcorr: {shape, data_b64}`.
  import { niceTicks, xcorrCellSize } from "../../lib/math/axis";
  import { fitPanelCanvas, panelColour } from "./panelCanvas";

  const DIMS = 256;
  let canvasEl = $state<HTMLCanvasElement>();

  $effect(() => {
    const canvas = canvasEl;
    if (!canvas) return;
    const ctx = fitPanelCanvas(canvas);
    if (!ctx) return;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    const border = panelColour(canvas, "--border");
    const dim = panelColour(canvas, "--text-dim");
    const cell = xcorrCellSize(Math.min(w, h), DIMS);

    ctx.strokeStyle = border;
    ctx.lineWidth = 1;
    ctx.strokeRect(0.5, 0.5, w - 1, h - 1);

    // Dimension ticks on both axes -- the matrix is square, so one tick set.
    ctx.fillStyle = dim;
    ctx.font = "9px 'Space Grotesk', ui-monospace, monospace";
    ctx.textBaseline = "top";
    for (const t of niceTicks(0, DIMS - 1, 5)) {
      if (t < 0 || t > DIMS - 1) continue;
      const p = Math.round((t / (DIMS - 1)) * (DIMS - 1) * cell) + 0.5;
      ctx.globalAlpha = 0.5;
      ctx.strokeStyle = border;
      ctx.beginPath();
      ctx.moveTo(p, h - 5);
      ctx.lineTo(p, h);
      ctx.moveTo(0, p);
      ctx.lineTo(5, p);
      ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.fillText(String(t), p + 2, h - 12);
    }

    // Leading diagonal, so an empty panel still reads as a correlation matrix.
    ctx.globalAlpha = 0.35;
    ctx.strokeStyle = dim;
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo((DIMS - 1) * cell, (DIMS - 1) * cell);
    ctx.stroke();
    ctx.globalAlpha = 1;
  });
</script>

<section class="panel" data-stats-panel="xcorr">
  <header>
    <span class="label">DIM CROSS-CORRELATION</span>
    <span class="sub">256 × 256</span>
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
  .sub {
    font-size: 10px;
    color: var(--text-dim);
  }
  .body {
    position: relative;
    height: 300px;
  }
  canvas {
    display: block;
    width: 100%;
    height: 300px;
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
