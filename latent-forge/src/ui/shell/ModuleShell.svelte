<script lang="ts">
  import type { Snippet } from "svelte";
  import { view, type ModuleId } from "../../lib/stores/view.svelte";

  // Spec §4.6: right-pane modules are collapsible and keep a lit dot while they
  // hold non-default settings. Geometry and colours are v3's `menuHead` / `dot`
  // helpers (lines 1649-1650). Whether the dot is lit is the owning milestone's
  // decision (litModules, Task 12), so it arrives as a prop.
  //
  // NORMATIVE (Normative-names table): props {id, title, lit, children}; open
  // state is the view store's, so it is what ui.modules persists (§9.2).
  //
  // PINNED DOM CONTRACT -- later milestones select on these, never on a class:
  //   [data-module={id}]                          the wrapper
  //   [data-module-toggle={id}]                   the header button (data-testid="module-head")
  //   [data-module-dot={id}][data-lit=true|false] the lit dot      (data-testid="module-dot")
  //   [data-module-body={id}]                     the body, rendered only while open
  interface Props {
    id: ModuleId;
    title: string;
    lit: boolean;
    children: Snippet;
  }
  let { id, title, lit, children }: Props = $props();

  // The drawing's accents: purple for OVERLAP, lane 1's colour for LANE CHAIN.
  const ACCENT: Partial<Record<ModuleId, string>> = {
    overlap: "var(--purple-strong)",
    "lane-chain": "var(--lane1)",
  };
  const accent = $derived(ACCENT[id] ?? "var(--border)");
  const dotColour = $derived(ACCENT[id] ?? "var(--turq-strong)");
  const open = $derived(view.isModuleOpen(id));
</script>

<section class="module" data-module={id}>
  <button
    class="head"
    data-testid="module-head"
    data-module-toggle={id}
    style:border-left-color={accent}
    onclick={() => view.toggleModule(id)}
  >
    <span>{open ? "▾" : "▸"} {title}</span>
    <span
      class="dot"
      data-testid="module-dot"
      data-module-dot={id}
      data-lit={lit ? "true" : "false"}
      style:background={lit ? dotColour : "transparent"}
      style:border-color={lit ? dotColour : "var(--border)"}
    ></span>
  </button>
  {#if open}
    <div class="body" data-module-body={id} style:border-left-color={accent}>
      {@render children()}
    </div>
  {/if}
</section>

<style>
  .module {
    border-bottom: 1px solid var(--border);
  }
  .head {
    width: 100%;
    box-sizing: border-box;
    display: flex;
    justify-content: space-between;
    align-items: center;
    text-align: left;
    background: transparent;
    border: none;
    border-left: 3px solid var(--border);
    color: var(--text);
    font-family: inherit;
    font-size: 11px;
    font-weight: 600;
    padding: 8px 10px;
    cursor: pointer;
  }
  .dot {
    width: 6px;
    height: 6px;
    border: 1px solid var(--border);
    flex-shrink: 0;
  }
  .body {
    padding: 6px 10px 10px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    border-left: 3px solid transparent;
  }
</style>
