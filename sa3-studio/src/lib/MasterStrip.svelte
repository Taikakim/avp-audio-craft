<script lang="ts">
  import { project } from "./store.svelte";
  import { computePeaks, drawPeaks } from "./waveform";

  let canvasEl = $state<HTMLCanvasElement>();
  let busy = $state(false);
  let error = $state<string | null>(null);

  const clipping = $derived(project.masterPeakLevel >= 0.999);
  const dbfs = $derived(
    project.masterPeakLevel > 0 ? (20 * Math.log10(project.masterPeakLevel)).toFixed(1) : null,
  );

  async function refresh() {
    busy = true;
    error = null;
    try {
      await project.renderMasterPreview();
      draw();
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      busy = false;
    }
  }

  function draw() {
    const canvas = canvasEl;
    const buffer = project.masterBuffer;
    if (!canvas) return;
    if (!buffer) {
      const ctx = canvas.getContext("2d");
      ctx?.clearRect(0, 0, canvas.width, canvas.height);
      return;
    }
    const cols = Math.max(1, Math.round(canvas.clientWidth));
    const color = getComputedStyle(canvas).getPropertyValue("--accent").trim();
    drawPeaks(canvas, computePeaks(buffer, cols), color);
  }

  // Redraw (not re-render) when the buffer or the element size changes.
  $effect(() => {
    void project.masterBuffer;
    void canvasEl;
    draw();
  });
</script>

<div class="master">
  <div class="head">
    <span class="section-label">Master — mix result</span>
    <span class="note">
      audio-domain preview mixdown — this is NOT the eventual output, it's the alignment check
    </span>
    <span class="spacer"></span>
    {#if dbfs}
      <span class="peak" class:clipping>peak {dbfs} dBFS{clipping ? " · CLIPPING" : ""}</span>
    {/if}
    {#if project.masterStale}
      <span class="stale-dot" title="the arrangement changed since this was rendered">stale</span>
    {/if}
    <button onclick={refresh} disabled={busy}>{busy ? "MIXING…" : "▸ MIX PREVIEW"}</button>
  </div>
  <canvas bind:this={canvasEl} class="wave"></canvas>
  {#if error}
    <p class="error">{error}</p>
  {:else if !project.masterBuffer}
    <p class="empty">no mix yet — add clips, then hit MIX PREVIEW</p>
  {/if}
</div>

<style>
  .master {
    background: var(--panel-bg);
    border: 1px solid var(--border);
  }
  .head {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 5px 8px;
    background: var(--panel2);
    border-bottom: 1px solid var(--border);
    flex-wrap: wrap;
  }
  .section-label {
    font-size: 10px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--fg-dim);
  }
  .note {
    font-size: 10px;
    color: var(--fg-dim);
  }
  .spacer {
    flex: 1;
  }
  .peak {
    font-size: 10px;
    color: var(--fg-dim);
    font-variant-numeric: tabular-nums;
  }
  .peak.clipping {
    color: var(--red);
    font-weight: 600;
  }
  .stale-dot {
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    background: var(--warn);
    color: var(--warn-fg);
    padding: 1px 4px;
  }
  button {
    background: var(--panel-bg);
    border: 1px solid var(--accent);
    color: var(--accent);
    font-family: inherit;
    font-size: 10px;
    letter-spacing: 0.04em;
    padding: 3px 8px;
    cursor: pointer;
  }
  button:disabled {
    opacity: 0.5;
    cursor: default;
  }
  .wave {
    display: block;
    width: 100%;
    height: 56px;
  }
  .error {
    margin: 0;
    padding: 4px 8px;
    font-size: 11px;
    color: var(--red);
  }
  .empty {
    margin: 0;
    padding: 4px 8px;
    font-size: 10px;
    color: var(--fg-dim);
  }
</style>
