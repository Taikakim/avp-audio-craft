<script lang="ts">
  // Spec §4.4. Centre-only view; the bottom pane is hidden (CentreColumn does
  // that). The lane buttons record a selection and nothing else in M1 -- M10
  // turns ANALYSE into the /forge/stats and /forge/dataset_scalars calls.
  import TimeSeriesPanel from "./TimeSeriesPanel.svelte";
  import XcorrPanel from "./XcorrPanel.svelte";
  import XYPanel from "./XYPanel.svelte";

  type LaneSel = 0 | 1 | 2 | 3 | "all";
  let lanes = $state<LaneSel>("all");
</script>

<div class="stats" data-region="stats-view">
  <div class="head">
    <span class="label">ANALYSE</span>
    {#each [0, 1, 2, 3] as n}
      <button
        data-stats-lane={String(n + 1)}
        class:active={lanes === n}
        onclick={() => (lanes = n as LaneSel)}>LANE {n + 1}</button
      >
    {/each}
    <button data-stats-lane="all" class:active={lanes === "all"} onclick={() => (lanes = "all")}>ALL</button>
    <span class="note">features read from the sidecars (.TIMESERIES.npz, .json)</span>
  </div>

  <div class="panels">
    <XcorrPanel />
    <div class="row">
      <XYPanel />
      <TimeSeriesPanel />
    </div>
  </div>
</div>

<style>
  .stats {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 10px;
    overflow-y: auto;
  }
  .head {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .label {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.08em;
    color: var(--text-dim);
  }
  .note {
    margin-left: auto;
    font-size: 10px;
    color: var(--text-dim);
  }
  button {
    background: var(--panel);
    border: 1px solid var(--border);
    color: var(--text-dim);
    font-family: inherit;
    font-size: 10px;
    letter-spacing: 0.04em;
    padding: 3px 8px;
    cursor: pointer;
  }
  button.active {
    border-color: var(--turq-strong);
    color: var(--turq-strong);
  }
  .panels {
    display: flex;
    flex-direction: column;
    gap: 8px;
    flex: 1;
    min-height: 0;
  }
  .row {
    display: flex;
    gap: 8px;
    flex: 1;
    min-height: 0;
  }
</style>
