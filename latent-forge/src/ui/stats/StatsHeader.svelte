<script lang="ts">
  // Spec §4.4 header row: ANALYSE, LANE 1..4, ALL, and the sidecar note. M1
  // T13 built this as static decoration on purpose ("the data wiring is
  // M10's, not this task's") -- this component is the real, wired version:
  // ANALYSE fires a callback and the LANE/ALL buttons report a selection.
  //
  // Fully controlled: `selection` is a prop, not local state, because Task 7
  // (StatisticsView) has to hand the same selection to the XY panel for lane
  // highlighting, and that has to update as soon as a LANE/ALL button is
  // clicked -- /forge/dataset_scalars does not depend on ANALYSE at all
  // (spec §6.5), so XY highlighting cannot wait for an ANALYSE press. The
  // selection therefore lives in StatisticsView's own state, never in
  // view.activeLane: activeLane is 0|1|2|3 and has no "all" case, which §4.4
  // requires.
  //
  // No data-help on any of these six controls. M1 Task 14 extracted exactly
  // 80 data-help strings from the design handoff and none of them cover
  // ANALYSE, LANE n or ALL. Inventing an id here was the exact class of
  // blocking defect M4 shipped four of, so these controls ship without
  // data-help until M1's table gains one (flagged for the milestone's Open
  // questions).
  import { LANE_SELECTIONS, laneSelAttr, laneSelLabel, type LaneSel } from "./statsHeader";

  interface Props {
    selection: LaneSel;
    onSelectionChange: (s: LaneSel) => void;
    onAnalyse: (selection: LaneSel) => void;
  }
  let { selection, onSelectionChange, onAnalyse }: Props = $props();
</script>

<div class="head">
  <button
    type="button"
    class="analyse"
    data-testid="stats-analyse"
    onclick={() => onAnalyse(selection)}
  >ANALYSE</button>
  {#each LANE_SELECTIONS as sel (sel)}
    <button
      type="button"
      data-stats-lane={laneSelAttr(sel)}
      class:active={selection === sel}
      onclick={() => onSelectionChange(sel)}
    >{laneSelLabel(sel)}</button>
  {/each}
  <span class="note">features read from the sidecars (.TIMESERIES.npz, .json)</span>
</div>

<style>
  .head {
    display: flex;
    align-items: center;
    gap: 6px;
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
  button.analyse {
    color: var(--turq-strong);
    border-color: var(--turq-strong);
    font-weight: 700;
  }
  button.active {
    border-color: var(--turq-strong);
    color: var(--turq-strong);
  }
  .note {
    margin-left: auto;
    font-size: 10px;
    color: var(--text-dim);
  }
</style>
