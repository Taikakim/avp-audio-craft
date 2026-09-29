<script lang="ts">
  import type { Snippet } from "svelte";
  import RightPaneModules from "./RightPaneModules.svelte";
  import { HELP } from "../../lib/help/strings";

  // Spec §4.1: 296 px, collapsible to a 24 px strip holding the ▸/◂ toggle,
  // overflow-y auto. box-sizing: border-box so the 1 px left border is inside
  // the 296 the layout test measures.
  //
  // `children` is optional: Task 12 moved the five spec modules into
  // RightPaneModules (always mounted below); a caller only supplies children
  // for anything extra it still owns (App's two legacy modules).
  interface Props {
    open: boolean;
    ontoggle: () => void;
    children?: Snippet;
  }
  let { open, ontoggle, children }: Props = $props();
</script>

<aside
  class="right-pane"
  data-region="right-pane"
  data-testid="right-pane"
  style:width={open ? "296px" : "24px"}
>
  <button
    class="side-toggle"
    class:collapsed={!open}
    data-testid="side-toggle"
    data-help={HELP.sidePaneToggle}
    onclick={ontoggle}
  >{open ? "◂ CONTEXT" : "▸"}</button>
  {#if open}
    <div class="modules" data-region="right-pane-modules">
      <RightPaneModules />
      {@render children?.()}
    </div>
  {/if}
</aside>

<style>
  .right-pane {
    box-sizing: border-box;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    background: var(--panel);
    border-left: 1px solid var(--border);
    overflow: hidden;
  }
  .side-toggle {
    width: 100%;
    box-sizing: border-box;
    flex-shrink: 0;
    text-align: left;
    background: var(--panel2);
    border: none;
    border-bottom: 1px solid var(--border);
    color: var(--text-dim);
    font-family: inherit;
    font-size: 10px;
    letter-spacing: 0.08em;
    padding: 7px 9px;
    cursor: pointer;
  }
  .side-toggle.collapsed {
    text-align: center;
    padding: 7px 0;
  }
  .modules {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
  }
</style>
