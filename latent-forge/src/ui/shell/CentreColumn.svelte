<script lang="ts">
  import type { Snippet } from "svelte";
  import { view } from "../../lib/stores/view.svelte";
  import type { LatentRef } from "../../lib/forge/types";
  import { arrangement } from "../../lib/stores/arrangement.svelte";
  import StatisticsView from "../stats/StatisticsView.svelte";
  import type { LaneSel } from "../stats/statsHeader";

  // M10's ANALYSE asks "which latents does this lane hold?" through a prop (M10 may not import the
  // arrangement store, M5/M7 may), and this shell file is the first place allowed to know both.
  // Skeleton rule: a clip is analysed by whatever identifies its audio -- a crop id when it came
  // from the crop library (the server resolves that to its stored latent), otherwise the audio ref.
  // A clip with no latent yet is still listed; the server reports what it cannot resolve (spec 9.7).
  // LaneSel is 1-based (LANE 1..4) or "all"; ForgeClip.lane is 0-based.
  function laneLatents(sel: LaneSel): LatentRef[] {
    return arrangement.clips
      .filter((c) => sel === "all" || c.lane === sel - 1)
      .map((c): LatentRef =>
        c.audio.kind === "crop"
          ? { kind: "crop", crop_id: c.audio.crop_id }
          : { kind: "audio", audio: c.audio });
  }

  // Spec §4.1: centre column = scrolling centre (flex 1, padding 10, gap 8) plus,
  // in WORKSPACE, the 248 px bottom pane.
  //
  // `position: relative` is load-bearing: it is the containing block for the
  // TERMINAL tab's FULL SCREEN mode (Task 11), which is `position: absolute;
  // inset: 0`. An absolutely positioned element is not clipped by ancestors that
  // are not in its containing-block chain, so the bottom pane's `overflow: hidden`
  // does not cut it off, and it covers the centre column and nothing else — which
  // is what spec §4.5 asks for, rather than v3's `inset: 42px 0 0 0` (line 2280)
  // that also covered the right pane.
  interface Props {
    centre: Snippet;
    bottom?: Snippet;
  }
  let { centre, bottom }: Props = $props();
</script>

<div class="centre-column" data-region="centre-column">
  {#if view.screen === "statistics"}
    <StatisticsView {laneLatents} />
  {:else}
    <div class="scrolling-centre" data-region="centre">
      {@render centre()}
    </div>
    {#if bottom}{@render bottom()}{/if}
  {/if}
</div>

<style>
  .centre-column {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    position: relative;
  }
  .scrolling-centre {
    flex: 1;
    min-height: 0;
    padding: 10px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    overflow: auto;
  }
</style>
