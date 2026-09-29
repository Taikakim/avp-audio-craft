<script lang="ts">
  // Spec §4.2, FRAME ONLY. Everything here is disabled in M1. M9 adds: loading the
  // newest committed mix, drawing its waveform on this canvas (reading its colours
  // through getComputedStyle so DARK works), play/stop, click-to-scrub, and
  // `draggable` + a dragstart payload so the waveform drops onto a lane like a clip.
  import { mixdownLabel } from "./mixdown";

  interface Props {
    busy?: boolean;
    stepsLeft?: number | null;
  }
  let { busy = false, stepsLeft = null }: Props = $props();

  let canvasEl = $state<HTMLCanvasElement>();
  const label = $derived(mixdownLabel(busy, stepsLeft));
</script>

<div class="mixdown-slot" data-region="mixdown-slot">
  <button
    class="commit"
    class:busy
    data-testid="mixdown-button"
    data-help="Mixes the four lanes in the latent domain and decodes the result — the commit that turns the arrangement into audio. While it samples, the window border runs a C64 loader raster bar whose sweep rate falls with the remaining step count."
    disabled>{label}</button>
  <canvas
    class="wave"
    data-testid="mixdown-canvas"
    data-help="The latest mixdown. Click to scrub it, and drag it onto a lane to use it as a clip. Earlier mixdowns stay in the render history at the bottom of the screen."
    bind:this={canvasEl}
    width="220"
    height="26"
    draggable="false"
  ></canvas>
  <button class="play" data-testid="mixdown-play" aria-label="play the latest mixdown" disabled
    >▶</button>
</div>

<style>
  .mixdown-slot {
    display: flex;
    align-items: center;
    gap: 5px;
    flex-shrink: 0;
    border-left: 1px solid var(--border);
    padding-left: 8px;
  }
  .commit {
    background: var(--turq-strong);
    border: 1px solid var(--turq-strong);
    color: white;
    font-family: inherit;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.04em;
    padding: 5px 14px;
    cursor: pointer;
  }
  .commit.busy,
  .commit:disabled {
    background: var(--panel2);
    color: var(--turq-strong);
    cursor: default;
  }
  .wave {
    box-sizing: border-box;
    width: 220px;
    height: 26px;
    display: block;
    border: 1px solid var(--border);
    background: var(--panel2);
  }
  .play {
    background: var(--panel2);
    border: 1px solid var(--border);
    color: var(--text-dim);
    font-family: inherit;
    font-size: 10px;
    padding: 4px 6px;
    cursor: pointer;
  }
  .play:disabled {
    cursor: default;
  }
</style>
