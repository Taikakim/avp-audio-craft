<script lang="ts">
  // Spec §4.4. Centre-only view; the bottom pane stays hidden in this view
  // (CentreColumn, M1 T13, already does that on view.screen === "statistics"
  // -- nothing here touches that switch). This task wires the real ANALYSE
  // flow: StatsHeader (M10 T3) reports a LaneSel, this component resolves it
  // to LatentRef[] through the laneLatents prop.
  //
  // M10 must not depend on M5's arrangement store (the milestone's own
  // constraint), so which latents a lane holds arrives as a callback, never
  // by reaching into an arrangement. The default returns no latents, which
  // reads honestly as "nothing to analyse" rather than throwing; M5/M7 wire
  // the real one.
  import { untrack } from "svelte";
  import type { LatentRef } from "../../lib/forge/types";
  import { statsClient } from "../../lib/stats/statsClient.svelte";
  import { view } from "../../lib/stores/view.svelte";
  import StatsHeader from "./StatsHeader.svelte";
  import type { LaneSel } from "./statsHeader";
  import { indexLabelsFor, laneCropIdSet } from "./statisticsWiring";
  import TimeSeriesPanel from "./TimeSeriesPanel.svelte";
  import XcorrPanel from "./XcorrPanel.svelte";
  import XYPanel from "./XYPanel.svelte";

  /** rms/onset_strength/spectral_centroid are the only feature names a
   *  caller can request without first discovering a crop's own *_ts field
   *  names (spec §6.5) -- no task before this one adds that discovery step,
   *  so ANALYSE always asks for exactly these three. Flagged at the end of
   *  this file for the assembler's Open questions. */
  const REQUEST_FEATURES = ["rms", "onset_strength", "spectral_centroid"];

  interface Props {
    /** Resolves a lane selection to the latents it currently holds. M10 must
     *  not depend on M5's arrangement store, so this is a prop, never a
     *  direct import; the default is "nothing selected yet". */
    laneLatents?: (sel: LaneSel) => LatentRef[];
  }
  let { laneLatents = () => [] }: Props = $props();

  let selection = $state<LaneSel>("all");
  /** The exact latents array of the last ANALYSE press -- NOT re-derived
   *  from the live `selection`, because timeseries[].index (spec §6.5)
   *  indexes into the array that produced the CURRENT result, which can be
   *  older than whatever `selection` has moved on to since. */
  let lastRequestLatents = $state<LatentRef[]>([]);

  const laneCropIds = $derived(laneCropIdSet(laneLatents(selection)));
  const indexLabels = $derived(indexLabelsFor(lastRequestLatents));

  function handleAnalyse(sel: LaneSel): void {
    const latents = laneLatents(sel);
    lastRequestLatents = latents;
    void statsClient.requestStats({ latents, features: REQUEST_FEATURES });
  }

  // Server error -> TERMINAL gains a red line (spec §9.7). Each field is its
  // own effect: requestStats and requestScalars are independent calls (M10
  // T2), and either can fail without the other.
  //
  // untrack(): appendLog reads AND writes the terminal's line list, so called bare inside an
  // effect it subscribes the effect to its own write and re-runs forever (found by a hanging
  // StatisticsView test, Electro-Sheep 1). The effect should depend on the error alone.
  $effect(() => {
    const e = statsClient.error;
    if (e) untrack(() => view.appendLog(`[stats] ${e}`, "error"));
  });
  $effect(() => {
    const e = statsClient.scalarsError;
    if (e) untrack(() => view.appendLog(`[stats] ${e}`, "error"));
  });
</script>

<div class="stats" data-region="stats-view">
  <StatsHeader {selection} onSelectionChange={(s) => (selection = s)} onAnalyse={handleAnalyse} />

  <div class="panels">
    <XcorrPanel />
    <div class="row">
      <XYPanel {laneCropIds} />
      <TimeSeriesPanel {indexLabels} />
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
