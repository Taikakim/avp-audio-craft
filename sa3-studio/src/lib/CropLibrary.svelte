<script lang="ts">
  import { project } from "./store.svelte";

  function onDragStart(e: DragEvent, cropId: string) {
    e.dataTransfer?.setData("text/sa3-crop-id", cropId);
    e.dataTransfer!.effectAllowed = "copy";
  }
</script>

<div class="library">
  <h3>Crops</h3>
  <p class="hint">Server-known latents (GET /crops). Drag one onto a lane.</p>
  {#if project.availableCrops.length === 0}
    <p class="hint">none reported by the server yet</p>
  {/if}
  <div class="chips">
    {#each project.availableCrops as cropId}
      <div class="chip" role="listitem" draggable="true" ondragstart={(e) => onDragStart(e, cropId)}>
        {cropId}
      </div>
    {/each}
  </div>
  <p class="hint">Or drop an audio file straight onto a lane to import it directly.</p>
</div>

<style>
  .library {
    padding: 12px;
    background: var(--panel-bg);
    border-radius: 6px;
    min-width: 220px;
  }
  h3 {
    margin: 0 0 4px;
    font-size: 13px;
    color: var(--fg);
  }
  .hint {
    color: var(--fg-dim);
    font-size: 11px;
    margin: 4px 0;
  }
  .chips {
    display: flex;
    flex-direction: column;
    gap: 4px;
    max-height: 240px;
    overflow-y: auto;
  }
  .chip {
    background: var(--track-bg);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
    font-family: ui-monospace, monospace;
    cursor: grab;
    color: var(--fg);
  }
</style>
