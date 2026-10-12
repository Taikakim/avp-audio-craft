<script lang="ts">
  // TARGET + the two mode buttons (v3 310-313), and in SEMITONE SET mode the
  // twelve piano-key toggles plus the chord field (v3 317-325).
  //
  // No data-help on the mode buttons or the keys: M1 T14's table has an id for
  // the chord field (chromaChord, v3 323) and none for these. Inventing one
  // was a blocking M4 defect, four times over, so they ship bare.
  //
  // In lane mode with no TARGET lane chosen, this says so rather than showing
  // an all-zero profile as if it were data.
  import { NOTE_NAMES } from "../../lib/chroma/bins";
  import { chromaTarget, keysLabel, laneTargetLabel } from "../../lib/chroma/targetStore.svelte";
  import { HELP } from "../../lib/help/strings";
  import { arrangement } from "../../lib/stores/arrangement.svelte";

  const laneLabel = $derived(laneTargetLabel(arrangement.targetLane));
  const noLane = $derived(chromaTarget.mode === "lane" && arrangement.targetLane === null);
</script>

<div class="row" data-region="chroma-target-row">
  <span class="label">TARGET</span>
  <button
    type="button"
    class:on={chromaTarget.mode === "lane"}
    data-testid="chroma-target-mode-lane"
    onclick={() => chromaTarget.setMode("lane")}>{laneLabel}</button
  >
  <button
    type="button"
    class:on={chromaTarget.mode === "set"}
    data-testid="chroma-target-mode-set"
    onclick={() => chromaTarget.setMode("set")}>SEMITONE SET</button
  >
</div>

{#if noLane}
  <p class="note" data-testid="chroma-target-empty">no TARGET lane — press TARGET in a lane header</p>
{/if}

{#if chromaTarget.mode === "set"}
  <div class="keys-row">
    <div class="keys">
      {#each NOTE_NAMES as name, p (name)}
        <button
          type="button"
          data-chroma-key={p}
          class:on={chromaTarget.keys[p]}
          class:black={name.includes("#")}
          onclick={() => chromaTarget.toggleKey(p)}>{name}</button
        >
      {/each}
    </div>
    <input
      type="text"
      data-testid="chroma-chord"
      data-help={HELP.chromaChord}
      placeholder="chord symbol"
      aria-invalid={chromaTarget.chordOk ? undefined : "true"}
      value={chromaTarget.chordText}
      oninput={(e) => chromaTarget.setChordText((e.currentTarget as HTMLInputElement).value)}
    />
    <span class="hint" data-testid="chroma-chord-hint">{keysLabel(chromaTarget.keys)}</span>
  </div>
{/if}

<style>
  .row {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .label {
    font-size: 10px;
    color: var(--text-dim);
  }
  button {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text);
    font-size: 9px;
    padding: 3px 4px;
    cursor: pointer;
  }
  button.on {
    border-color: var(--turq-strong);
    color: var(--turq-strong);
  }
  .keys-row {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .keys {
    display: flex;
    gap: 2px;
  }
  .keys button {
    min-width: 20px;
  }
  .keys button.black {
    background: var(--panel2);
  }
  .keys button.on {
    background: var(--warm);
    border-color: var(--warm);
  }
  input {
    width: 110px;
    box-sizing: border-box;
    background: var(--panel2);
    border: 1px solid var(--border);
    color: var(--text);
    font-size: 10px;
    padding: 3px 5px;
  }
  input[aria-invalid="true"] {
    border-color: var(--red);
  }
  .hint,
  .note {
    margin: 0;
    font-size: 10px;
    color: var(--text-dim);
  }
</style>
