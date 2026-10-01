<script lang="ts">
  // Spec §4.5. Height budget, asserted by the layout test:
  //   248 − 1 (border-top) − 6 (padding-top) − 8 (padding-bottom) = 233
  //   233 − 162 (tab body) − 44 (preview container)               = 27 (tab row)
  //
  // The tab bodies for CHROMA, PROMPT + SIGMA and MIX + SIGNAL PATH are empty here
  // and are built by M6, M4 and M7 respectively. TERMINAL is live in M1.
  import { logStore } from "../../lib/stores/log.svelte";
  import PromptSigmaTab from "../prompt/PromptSigmaTab.svelte";
  import PreviewContainer from "../prompt/PreviewContainer.svelte";
  import { BOTTOM_TABS, bottomHint, type BottomTabId } from "./bottomTabs";
  import Terminal from "./Terminal.svelte";

  type TerminalMode = "collapsed" | "pane" | "full";

  interface Props {
    visible?: boolean;
    tab?: BottomTabId;
    ontab?: (t: BottomTabId) => void;
    terminalMode?: TerminalMode;
    onterminalmode?: (m: TerminalMode) => void;
  }
  let {
    visible = true,
    tab = "prompt",
    ontab = () => {},
    terminalMode = "pane",
    onterminalmode = () => {},
  }: Props = $props();

  // Poll /forge/log only while the TERMINAL tab is the one on screen: an idle
  // CHROMA session makes no requests at all.
  $effect(() => {
    if (!visible || tab !== "terminal") return;
    logStore.start(1000);
    return () => logStore.stop();
  });
</script>

<div class="bottom-pane" class:hidden={!visible} data-region="bottom-pane">
  <div class="tab-row" data-region="bottom-tab-row">
    {#each BOTTOM_TABS as t (t.id)}
      <button
        class="tab"
        class:on={tab === t.id}
        data-testid="bottom-tab-{t.id}"
        onclick={() => ontab(t.id)}>{t.label}</button>
    {/each}
    <div class="spacer"></div>
    <span class="hint" data-testid="bottom-hint">{bottomHint(tab)}</span>
  </div>

  <div class="tab-body" data-region="bottom-tab-body" data-tab={tab}>
    {#if tab === "chroma"}
      <!-- body: M6 (spec §5.4) -->
      <div class="tab-empty"></div>
    {:else if tab === "prompt"}
      <PromptSigmaTab />
    {:else if tab === "mix"}
      <!-- body: M7 (spec §4.5 MIX ORDER + SIGNAL PATH, §8.1 stage labels) -->
      <div class="tab-empty"></div>
    {:else}
      <Terminal
        mode={terminalMode}
        busy={logStore.busy}
        lines={logStore.lines}
        onmode={onterminalmode}
      />
    {/if}
  </div>

  <PreviewContainer />
</div>

<style>
  .bottom-pane {
    box-sizing: border-box;
    flex-shrink: 0;
    height: 248px;
    padding: 6px 10px 8px;
    background: var(--bg);
    border-top: 1px solid var(--border);
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }
  .bottom-pane.hidden {
    display: none;
  }
  .tab-row {
    box-sizing: border-box;
    flex: 0 0 27px;
    display: flex;
    align-items: center;
    gap: 3px;
    padding-bottom: 5px;
  }
  .tab {
    background: transparent;
    border: 1px solid transparent;
    color: var(--text-dim);
    font-family: inherit;
    font-size: 10px;
    letter-spacing: 0.04em;
    padding: 0 10px;
    height: 22px;
    cursor: pointer;
  }
  .tab.on {
    background: var(--panel2);
    border-color: var(--turq-strong);
    color: var(--turq-strong);
  }
  .spacer {
    flex: 1;
  }
  .hint {
    font-size: 10px;
    color: var(--text-dim);
  }
  .tab-body {
    box-sizing: border-box;
    flex: 0 0 162px;
    min-height: 0;
    overflow: hidden;
  }
  .tab-empty {
    height: 100%;
  }
</style>
