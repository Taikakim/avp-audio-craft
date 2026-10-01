<script lang="ts">
  // 256 x 256 DIM CROSS-CORRELATION, 300 px (spec §4.4). M1 T13 drew the
  // frame, the dimension ticks, the diagonal and the empty state; this task
  // wires the real data in from statsClient.result.xcorr (M10 T2's decoded
  // Float32Array, cell(r, c) = xcorr[r*n + c]), colours it with a diverging
  // ramp (xcorrColor.ts), and adds the hover readout spec §4.4 asks for.
  //
  // statsClient is a singleton (M10 T2) -- this component reads it directly
  // rather than taking it as a prop, exactly as T2's own header comment says
  // XcorrPanel and TimeSeriesPanel both do (they read one shared result).
  //
  // No data-help: M1 T14's 80-entry HELP table has no id for this canvas or
  // its hover readout (grep of its full key list confirms), so none is
  // invented here -- see this file's closing flags.
  import { niceTicks, xcorrCellSize } from "../../lib/math/axis";
  import { fitPanelCanvas, panelColour } from "./panelCanvas";
  import { statsClient } from "../../lib/stats/statsClient.svelte";
  import { xcorrColor } from "../../lib/stats/xcorrColor";
  import { xcorrCellAt } from "../../lib/stats/xcorrHover";

  const DIMS = 256;
  let canvasEl = $state<HTMLCanvasElement>();
  let hover = $state<{ row: number; col: number; value: number } | null>(null);

  const result = $derived(statsClient.result);
  const pending = $derived(statsClient.pending);
  const error = $derived(statsClient.error);

  $effect(() => {
    const canvas = canvasEl;
    const res = result; // re-run whenever a fresh ANALYSE lands
    if (!canvas) return;
    const ctx = fitPanelCanvas(canvas);
    if (!ctx) return;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    const border = panelColour(canvas, "--border");
    const dim = panelColour(canvas, "--text-dim");
    const n = res ? res.n : DIMS;
    const cell = xcorrCellSize(Math.min(w, h), n);

    if (res) {
      for (let r = 0; r < n; r++) {
        for (let c = 0; c < n; c++) {
          ctx.fillStyle = xcorrColor(res.xcorr[r * n + c]);
          ctx.fillRect(c * cell, r * cell, cell, cell);
        }
      }
    }

    ctx.strokeStyle = border;
    ctx.lineWidth = 1;
    ctx.strokeRect(0.5, 0.5, w - 1, h - 1);

    // Dimension ticks on both axes -- the matrix is square, so one tick set.
    ctx.fillStyle = dim;
    ctx.font = "9px 'Space Grotesk', ui-monospace, monospace";
    ctx.textBaseline = "top";
    for (const t of niceTicks(0, n - 1, 5)) {
      if (t < 0 || t > n - 1) continue;
      const p = Math.round((t / (n - 1)) * (n - 1) * cell) + 0.5;
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

    if (!res) {
      // Leading diagonal, so an empty panel still reads as a correlation matrix.
      ctx.globalAlpha = 0.35;
      ctx.strokeStyle = dim;
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.lineTo((n - 1) * cell, (n - 1) * cell);
      ctx.stroke();
      ctx.globalAlpha = 1;
    }
  });

  function onMove(e: MouseEvent): void {
    const canvas = canvasEl;
    const res = result;
    if (!canvas || !res) { hover = null; return; }
    const rect = canvas.getBoundingClientRect();
    const cell = xcorrCellSize(Math.min(canvas.clientWidth, canvas.clientHeight), res.n);
    const at = xcorrCellAt(e.clientX - rect.left, e.clientY - rect.top, cell, res.n);
    hover = at ? { row: at.row, col: at.col, value: res.xcorr[at.row * res.n + at.col] } : null;
  }

  function onLeave(): void {
    hover = null;
  }
</script>

<section class="panel" data-stats-panel="xcorr">
  <header>
    <span class="label">DIM CROSS-CORRELATION</span>
    <span class="sub">256 × 256</span>
  </header>
  <div class="body">
    <canvas bind:this={canvasEl} onmousemove={onMove} onmouseleave={onLeave}></canvas>
    {#if hover}
      <p class="hover" data-testid="xcorr-hover">row {hover.row} · col {hover.col} · {hover.value.toFixed(3)}</p>
    {:else if error}
      <p class="empty error" data-testid="xcorr-error">{error}</p>
    {:else if pending}
      <p class="empty">analysing…</p>
    {:else if !result}
      <p class="empty">no analysis yet — choose lanes and press ANALYSE</p>
    {/if}
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
  .empty.error {
    color: var(--red);
  }
  .hover {
    position: absolute;
    right: 6px;
    bottom: 6px;
    margin: 0;
    font-size: 10px;
    color: var(--text);
    background: var(--panel2);
    border: 1px solid var(--border);
    padding: 2px 6px;
    pointer-events: none;
  }
</style>
