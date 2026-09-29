<script lang="ts">
  // The ruler's left cell: bar label, time label and the transport. Spec §4.3
  // puts the transport here and §10 X1 records why the drawing has none.
  // LOOP is a frame in M1 -- the loop region itself is M5 -- but the button is
  // present and toggles, so the cell never changes size later.
  import { HELP } from "../../lib/help/strings";
  import { formatBarsBeats, formatClock, frameAt } from "../../lib/musictime";
  import { project } from "../../lib/store.svelte";

  let loop = $state(false);
</script>

<div class="cell" data-region="ruler-transport">
  <div class="buttons">
    <button
      class="primary"
      data-testid="transport-play"
      data-help={HELP.transportPlay}
      onclick={() => project.togglePlay()}>{project.playing ? "❚❚" : "▶"}</button
    >
    <button data-testid="transport-stop" data-help={HELP.transportStop} onclick={() => project.stop()}>■</button>
    <button
      data-testid="transport-loop"
      data-help={HELP.transportLoop}
      class:active={loop}
      onclick={() => (loop = !loop)}>LOOP</button
    >
  </div>
  <div class="readout">
    <span class="big">{formatClock(project.playheadSec)}</span>
    <span class="sub">bar {formatBarsBeats(project.playheadSec, project.meter)} · frame {frameAt(project.playheadSec)}</span>
  </div>
</div>

<style>
  .cell {
    width: 250px;
    flex: 0 0 250px;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 0 6px;
    background: var(--panel2);
    border-right: 1px solid var(--border);
  }
  .buttons {
    display: flex;
    gap: 3px;
  }
  button {
    background: var(--panel);
    border: 1px solid var(--border);
    color: var(--text);
    font-family: inherit;
    font-size: 10px;
    letter-spacing: 0.04em;
    padding: 3px 6px;
    cursor: pointer;
  }
  button.primary {
    background: var(--turq-strong);
    border-color: var(--turq-strong);
    color: var(--panel);
  }
  button.active {
    border-color: var(--turq-strong);
    color: var(--turq-strong);
  }
  .readout {
    display: flex;
    flex-direction: column;
    line-height: 1.15;
    font-variant-numeric: tabular-nums;
    margin-left: auto;
    text-align: right;
  }
  .big {
    font-size: 12px;
    color: var(--text);
  }
  .sub {
    font-size: 9px;
    color: var(--text-dim);
  }
</style>
