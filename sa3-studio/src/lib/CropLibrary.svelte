<script lang="ts">
  import { project } from "./store.svelte";

  function onDragStart(e: DragEvent, cropId: string) {
    e.dataTransfer?.setData("text/sa3-crop-id", cropId);
    e.dataTransfer!.effectAllowed = "copy";
  }
</script>

<div class="library">
  <h3>Crops</h3>
  <p class="hint">server-known latents (GET /crops) — drag one onto a lane</p>
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
  <p class="hint">or drop an audio file straight onto a lane to import it directly</p>
  <p class="hint">double-click an empty lane to place a slot for a text → audio generate</p>
</div>

<style>
  .library {
    padding: 10px 12px;
    background: var(--panel-bg);
    border: 1px solid var(--border);
    min-width: 220px;
  }
  h3 {
    margin: 0 0 4px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.08em;
    color: var(--fg-dim);
    text-transform: uppercase;
  }
  .hint {
    color: var(--fg-dim);
    font-size: 10px;
    letter-spacing: 0.02em;
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
    background: var(--panel2);
    border: 1px solid var(--border);
    padding: 4px 8px;
    font-size: 12px;
    font-family: ui-monospace, monospace;
    cursor: grab;
    color: var(--fg);
  }
</style>
