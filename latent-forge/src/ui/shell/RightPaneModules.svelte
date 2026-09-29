<script lang="ts">
  // The accordion itself (spec §4.6): five modules in a fixed order, each in a
  // ModuleShell that owns its own open/closed state. This component decides
  // only (a) which modules are present, (b) their titles, (c) their lit dots.
  import { litModules, MODULE_ORDER, moduleTitle, type ModuleStateSnapshot } from "../../lib/forge/nonDefault";
  import { view } from "../../lib/stores/view.svelte";
  import ModuleShell from "./ModuleShell.svelte";
  import AdvancedSampling from "../modules/AdvancedSampling.svelte";
  import Files from "../modules/Files.svelte";
  import LaneChain from "../modules/LaneChain.svelte";
  import MasterChain from "../modules/MasterChain.svelte";
  import OverlapInpaint from "../modules/OverlapInpaint.svelte";

  // M1 has no settings stores, so every dot is dark and the snapshot is a
  // constant. M4 replaces `sampling` with render.settingsFor(view.selection) and
  // M7 replaces `overlap`, `chain` and `master` with the chains store; both turn
  // these two consts into `$derived(...)`. litModules() itself does not change.
  const snapshot: ModuleStateSnapshot = {
    overlap: null,
    chain: null,
    sampling: null,
    master: null,
  };
  const lit = litModules(snapshot);

  // Module 1 exists only while an overlap is the render target (spec §4.6.1).
  const overlapSelected = $derived(view.selection.kind === "overlap");
  const present = $derived(
    MODULE_ORDER.filter((id) => id !== "overlap" || overlapSelected),
  );
</script>

<div class="modules">
  {#each present as id (id)}
    <ModuleShell {id} title={moduleTitle(id, view.activeLane)} lit={lit[id]}>
      {#if id === "overlap"}
        <OverlapInpaint />
      {:else if id === "files"}
        <Files />
      {:else if id === "lane-chain"}
        <LaneChain />
      {:else if id === "advanced-sampling"}
        <AdvancedSampling />
      {:else}
        <MasterChain />
      {/if}
    </ModuleShell>
  {/each}
</div>

<style>
  .modules {
    display: flex;
    flex-direction: column;
  }
</style>
