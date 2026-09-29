<script lang="ts">
  // Spec §4.5's render preview container — FRAME ONLY, 44 px, full width.
  //
  // M9 owns every behaviour here: running the pane's current target (§7.1),
  // filling HISTORY with the session's renders newest first tagged GEN / A2A /
  // INPAINT / MIX with length, drawing and scrubbing the waveform (reading its
  // colours through getComputedStyle so DARK works), play/stop independent of the
  // timeline transport, `draggable` with a dragstart payload so the render drops
  // onto a lane, USE SETTINGS copying the previewed render's job payload into the
  // current target, and REPLACE CLIP swapping a clip's audio while keeping the
  // previous ref in clip.history.
  import { HELP } from "../../lib/help/strings";

  interface Props {
    lengthSec?: number | null;
    history?: { id: string; label: string }[];
  }
  let { lengthSec = null, history = [] }: Props = $props();

  let canvasEl = $state<HTMLCanvasElement>();
</script>

<div class="preview" data-region="preview-container">
  <button
    class="render"
    data-testid="preview-render"
    data-help={HELP.previewRender}
    disabled>▸ RENDER</button>

  <select
    class="history"
    data-testid="preview-history"
    data-help={HELP.previewHistory}
    disabled
  >
    {#if history.length === 0}
      <option value="">no renders yet</option>
    {:else}
      {#each history as h (h.id)}
        <option value={h.id}>{h.label}</option>
      {/each}
    {/if}
  </select>

  <canvas class="wave" data-testid="preview-wave" bind:this={canvasEl} width="900" height="30"
  ></canvas>

  <button class="transport" data-testid="preview-play" aria-label="play the previewed render" disabled
    >▶</button>
  <span class="length" data-testid="preview-length"
    >{lengthSec === null ? "—" : `${lengthSec.toFixed(1)} s`}</span>

  <span
    class="handle"
    data-testid="preview-drag-handle"
    data-help={HELP.previewDragToLane}
    >⠿ drag to lane</span>

  <button
    class="action"
    data-testid="preview-use-settings"
    data-help={HELP.previewUseSettings}
    disabled>USE SETTINGS</button>
  <button
    class="action"
    data-testid="preview-replace-clip"
    data-help={HELP.previewReplaceClip}
    disabled>REPLACE CLIP</button>
</div>

<style>
  .preview {
    box-sizing: border-box;
    height: 44px;
    width: 100%;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 0 8px;
    background: var(--panel);
    border: 1px solid var(--border);
  }
  .render {
    background: var(--turq-strong);
    border: 1px solid var(--turq-strong);
    color: white;
    font-family: inherit;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.04em;
    padding: 5px 12px;
    flex-shrink: 0;
    cursor: pointer;
  }
  .render:disabled {
    background: var(--panel2);
    color: var(--turq-strong);
    cursor: default;
  }
  .history {
    background: var(--panel2);
    border: 1px solid var(--border);
    color: var(--text);
    font-family: inherit;
    font-size: 10px;
    padding: 3px 5px;
    max-width: 170px;
    flex-shrink: 0;
  }
  .wave {
    box-sizing: border-box;
    flex: 1;
    min-width: 0;
    height: 30px;
    display: block;
    border: 1px solid var(--border);
    background: var(--panel2);
  }
  .transport,
  .action {
    background: var(--panel2);
    border: 1px solid var(--border);
    color: var(--text-dim);
    font-family: inherit;
    font-size: 10px;
    padding: 4px 7px;
    flex-shrink: 0;
    cursor: pointer;
  }
  .transport:disabled,
  .action:disabled {
    cursor: default;
  }
  .length,
  .handle {
    font-size: 10px;
    color: var(--text-dim);
    flex-shrink: 0;
  }
  .handle {
    cursor: grab;
  }
</style>
