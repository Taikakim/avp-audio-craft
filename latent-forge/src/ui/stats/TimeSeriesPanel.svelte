<script lang="ts">
  // TIME SERIES view (spec §4.4): feature select, one line per clip of the
  // selected lane(s) over latent frames. M1 T13 drew the axes and the empty
  // state; this task wires statsClient.result.timeseries in.
  //
  // Two rules from spec §6.5: a feature a latent lacks is ALL-null, and a
  // null anywhere is a GAP, never a zero -- lib/stats/timeseriesGeometry.ts's
  // `segments` breaks the line there rather than drawing through it. And
  // `values` is resampled to at most max_points, so the frame axis comes
  // from `n_frames` (`frameOf`), never from `values.length`.
  //
  // Series are named by `index` into the /forge/stats request's own
  // `latents` array (spec §6.5) -- this component has no idea what a given
  // index IS (a crop_id, a lane, a name), so that mapping arrives as the
  // `indexLabels` prop from M10 T7, which built the request. No label (or a
  // short one) falls back to "series <n>" for that index.
  import { linScale, niceTicks } from "../../lib/math/axis";
  import { fitPanelCanvas, panelColour } from "./panelCanvas";
  import { statsClient } from "../../lib/stats/statsClient.svelte";
  import { frameOf, segments } from "../../lib/stats/timeseriesGeometry";

  /** Computed for renders and uploads, so always offered (spec §4.4); the
   *  default before the first ANALYSE response. */
  const DEFAULT_FEATURES = ["rms", "onset_strength", "spectral_centroid"];

  interface Props {
    /** Label per `index` into the /forge/stats request's `latents` array. */
    indexLabels?: readonly string[];
  }
  let { indexLabels = [] }: Props = $props();

  let feature = $state("rms");
  let canvasEl = $state<HTMLCanvasElement>();

  const result = $derived(statsClient.result);
  const pending = $derived(statsClient.pending);
  const error = $derived(statsClient.error);
  const features = $derived(result?.features_available.length ? result.features_available : DEFAULT_FEATURES);
  const series = $derived(result ? result.timeseries.filter((s) => s.feature === feature) : []);

  const PAD = { left: 34, right: 8, top: 8, bottom: 20 };

  $effect(() => {
    const canvas = canvasEl;
    const res = result;
    const ser = series;
    if (!canvas) return;
    const ctx = fitPanelCanvas(canvas);
    if (!ctx) return;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    const border = panelColour(canvas, "--border");
    const dim = panelColour(canvas, "--text-dim");

    // The x axis is the LONGEST series, each drawn over its own length. res.n_frames is pooled over
    // every latent (the xcorr's count), so using it for each series stretched short clips; it is
    // only the fallback for a server that does not send per-series n_frames (review 2026-10-01).
    const lenOf = (s: { n_frames?: number }) => s.n_frames ?? res?.n_frames ?? 1;
    const nFrames = ser.length ? Math.max(...ser.map(lenOf)) : (res?.n_frames ?? 1);
    let yLo = Infinity;
    let yHi = -Infinity;
    for (const s of ser) {
      for (const v of s.values) {
        if (v === null || !Number.isFinite(v)) continue;
        if (v < yLo) yLo = v;
        if (v > yHi) yHi = v;
      }
    }
    if (!Number.isFinite(yLo) || !Number.isFinite(yHi)) { yLo = 0; yHi = 1; }

    const sx = linScale([0, Math.max(1, nFrames - 1)], [PAD.left, w - PAD.right]);
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
    for (const t of niceTicks(yLo, yHi, 5)) {
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
    ctx.fillText("latent frame", Math.round(sx((nFrames - 1) / 2)), h - PAD.bottom + 4);

    for (const s of ser) {
      ctx.strokeStyle = panelColour(canvas, `--lane${(s.index % 4) + 1}`);
      ctx.lineWidth = 1.5;
      for (const run of segments(s.values)) {
        ctx.beginPath();
        run.forEach(([i, v], j) => {
          const px = sx(frameOf(i, s.values.length, lenOf(s)));
          const py = sy(v);
          if (j === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
        });
        ctx.stroke();
      }
    }
  });

  function labelFor(index: number): string {
    return indexLabels[index] ?? `series ${index}`;
  }
</script>

<section class="panel" data-stats-panel="timeseries">
  <header>
    <span class="label">TIME SERIES</span>
    <label>FEATURE <select bind:value={feature}>{#each features as f}<option value={f}>{f}</option>{/each}</select></label>
  </header>
  <div class="body">
    <canvas bind:this={canvasEl}></canvas>
    {#if error}
      <p class="empty error" data-testid="timeseries-error">{error}</p>
    {:else if pending}
      <p class="empty">analysing…</p>
    {:else if !result}
      <p class="empty">no analysis yet — choose lanes and press ANALYSE</p>
    {:else if series.length === 0}
      <p class="empty">no data for this feature</p>
    {/if}
  </div>
  {#if series.length > 0}
    <ul class="legend" data-testid="timeseries-legend">
      {#each series as s (s.index)}
        <li>{labelFor(s.index)}</li>
      {/each}
    </ul>
  {/if}
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
  .legend {
    list-style: none;
    margin: 0;
    padding: 4px 8px;
    display: flex;
    flex-wrap: wrap;
    gap: 4px 12px;
    font-size: 10px;
    color: var(--text-dim);
    border-top: 1px solid var(--border);
  }
</style>
