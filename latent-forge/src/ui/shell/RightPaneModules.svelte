<script lang="ts">
  // The accordion itself (spec §4.6): five modules in a fixed order, each in a
  // ModuleShell that owns its own open/closed state. This component decides
  // only (a) which modules are present, (b) their titles, (c) their lit dots.
  import { litModules, MODULE_ORDER, moduleTitle, type ModuleStateSnapshot } from "../../lib/forge/nonDefault";
  import { arrangement } from "../../lib/stores/arrangement.svelte";
  import { settings } from "../../lib/stores/settings.svelte";
  import { fetchLatchHeads, type LatchHeadInfo } from "../../lib/chains/latch";
  import { view } from "../../lib/stores/view.svelte";
  import ModuleShell from "./ModuleShell.svelte";
  import AdvancedSampling from "../modules/AdvancedSampling.svelte";
  import Files from "../modules/Files.svelte";
  import LaneChain from "../modules/LaneChain.svelte";
  import MasterChain from "../modules/MasterChain.svelte";
  import OverlapInpaint from "../modules/OverlapInpaint.svelte";

  // M7 T9: live. Every field is read inside the $derived (and litModules' deepEqual reads through
  // the proxies), so a module's dot relights on any in-place edit.
  //  - overlap: peekOverlapParams, NEVER overlapParams -- that one seeds the store, and a write
  //    during a $derived throws state_unsafe_mutation (Global Constraint #8).
  //  - sampling: the selected target's own settings. settings.current() reads through M5's
  //    never-seeding settingsSource once App has attached it (Step 4), so it is safe in a $derived.
  //    M4 never wired this (M4 plan line 4712); the reconcile pass put it here (Open questions 19).
  const snapshot = $derived<ModuleStateSnapshot>({
    overlap: view.selection.kind === "overlap" ? arrangement.peekOverlapParams(view.selection.key) : null,
    chain: arrangement.lanes[view.activeLane].chain,
    sampling: settings.current(view.selection),
    master: arrangement.master,
  });
  const lit = $derived(litModules(snapshot));

  // M4's handoff (M4 T11): ADVANCED SAMPLING's `latch` prop is the active lane's LatCH state --
  // but ONLY the slots whose head /info.latch_heads lists (critic pass 2 #8). M4's activeSlots
  // counts any non-"none", non-zero-weight head; chainRequest (T1) sends a head the registry does
  // not list as "none", because the server 400s on it. Passing the raw slots would show "euler
  // (forced by LatCH)" for a request that sends no active LatCH slot at all. Before the heads
  // arrive nothing is known, which is also what chainRequest would send.
  let latchHeads = $state<Record<string, LatchHeadInfo>>({});
  $effect(() => {
    fetchLatchHeads().then((h) => (latchHeads = h)).catch(() => {});
  });
  const activeLatch = $derived.by(() => {
    const chain = arrangement.lanes[view.activeLane].chain;
    return {
      latch_on: chain.latch_on,
      slots: chain.slots.filter((s) => Object.prototype.hasOwnProperty.call(latchHeads, s.head)),
    };
  });

  // M4's other handoff (M4 T11 `a2a` prop; "M5 and M7 exist to wire them"): the selected clip's
  // A2A state, which sets σ MAX. Only a clip has one; null otherwise (Open questions 20).
  const selectedA2A = $derived.by(() => {
    const sel = view.selection;
    if (sel.kind !== "clip") return null;
    const clip = arrangement.clips.find((c) => c.id === sel.id);
    return clip?.a2a ? { on: clip.a2a.on, noise: clip.a2a.noise } : null;
  });

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
        <AdvancedSampling latch={activeLatch} a2a={selectedA2A} />
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
