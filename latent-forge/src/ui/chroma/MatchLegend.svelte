<script lang="ts">
  // The consonance legend (spec §5.4, v3 292-308) and the `match <score> ·
  // <scale>` readout (v3 330).
  //
  // This is DOM, not canvas, for the same reason the hover readout is (Task
  // 10): a fillText label can never be found by findByText, which was a
  // blocking M4 finding. The nine stops are inline background colours from
  // legendColor(), which builds its own oklch() string -- a legend IS a ramp.
  //
  // The three marks are computed from the TARGET alone, which is why the
  // legend can draw them before any clip is selected.
  import { LEGEND_STOPS, legendColor } from "../../lib/chroma/consonanceColor";
  import { anchors } from "../../lib/chroma/match";
  import { CONSONANCE_SCALE_LABEL, legendTicks, matchVerdict } from "../../lib/chroma/matchCurve";
  import { ANCHOR_COLORS } from "../../lib/chroma/matchCurve";
  import { HELP } from "../../lib/help/strings";

  interface Props {
    target: Float32Array;
    clipScore: number | null;
  }
  let { target, clipScore }: Props = $props();

  const anch = $derived(anchors(target));
  const ticks = $derived(legendTicks(anch));
  const stops = $derived(Array.from({ length: LEGEND_STOPS }, (_, i) => legendColor(i / (LEGEND_STOPS - 1))));
  const readout = $derived(
    clipScore === null
      ? `match — · ${CONSONANCE_SCALE_LABEL}`
      : `match ${clipScore.toFixed(2)} · ${matchVerdict(clipScore, anch)} · ${CONSONANCE_SCALE_LABEL}`,
  );
</script>

<div class="legend" data-testid="chroma-legend" data-help={HELP.chromaMatchMarks}>
  <div class="strip">
    <div class="stops">
      {#each stops as colour, i (i)}
        <span data-legend-stop style="background:{colour}"></span>
      {/each}
    </div>
    {#each ticks as tick (tick.label)}
      <span data-legend-tick style="left:{tick.pct}%"></span>
    {/each}
  </div>
  <div class="keys">
    {#each ticks as tick (tick.label)}
      <span style="color:{ANCHOR_COLORS[tick.label]}">{tick.label} {tick.value.toFixed(2)}</span>
    {/each}
  </div>
</div>
<span class="readout" data-testid="chroma-match-readout" data-help={HELP.chromaMatchLegend}>{readout}</span>

<style>
  .legend {
    display: flex;
    align-items: flex-end;
    gap: 5px;
  }
  .strip {
    position: relative;
  }
  .stops {
    display: flex;
  }
  .stops span {
    display: inline-block;
    width: 15px;
    height: 10px;
  }
  [data-legend-tick] {
    position: absolute;
    top: -2px;
    width: 1px;
    height: 14px;
    background: var(--text);
  }
  .keys {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 9px;
    white-space: nowrap;
  }
  .readout {
    font-size: 10px;
    color: var(--turq-strong);
  }
</style>
