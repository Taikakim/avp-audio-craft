<script lang="ts">
  // Spec §4.2. 42 px, box-sizing: border-box so the 1 px bottom border is inside
  // the height the layout test measures. `overflow: hidden` plus `min-width: 0` on
  // every flexible child keeps the row from ever giving the page a horizontal
  // scrollbar (spec §11.3).
  //
  // This file is the 42 px frame plus the controls that need no server data
  // (WORKSPACE / STATISTICS / HELP / DARK). Task 10 adds SESSION, MODEL, the
  // model folder field, MASTER PRESET and the MIXDOWN slot between the
  // wordmark and the view tabs.
  type ForgeView = "workspace" | "statistics";

  interface Props {
    view: ForgeView;
    onview: (v: ForgeView) => void;
    helpMode: boolean;
    onhelp: () => void;
    theme: "light" | "dark";
    ontheme: () => void;
  }
  let { view, onview, helpMode, onhelp, theme, ontheme }: Props = $props();
</script>

<header class="topbar" data-region="topbar">
  <div class="wordmark">LATENT FORGE</div>
  <div class="spacer"></div>
  <div class="tabs">
    <button class="tab" class:on={view === "workspace"} onclick={() => onview("workspace")}
      >WORKSPACE</button>
    <button class="tab" class:on={view === "statistics"} onclick={() => onview("statistics")}
      >STATISTICS</button>
    <button
      class="toggle"
      class:on={helpMode}
      data-testid="help-toggle"
      data-help="Help mode. While on, hovering a control shows what it does."
      onclick={onhelp}>HELP</button>
    <button
      class="toggle"
      class:on={theme === "dark"}
      data-testid="dark-toggle"
      data-help="Light or dark ground. The choice is kept in this browser. Canvases read their colours from the theme, so the waveforms, the ruler and the sigma graph follow it too."
      onclick={ontheme}>DARK</button>
  </div>
</header>

<style>
  .topbar {
    box-sizing: border-box;
    height: 42px;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 0 12px;
    background: var(--panel);
    border-bottom: 1px solid var(--border);
    overflow: hidden;
  }
  .wordmark {
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.16em;
    color: var(--turq-strong);
    flex-shrink: 0;
  }
  .spacer {
    flex: 1;
    min-width: 0;
  }
  .tabs {
    display: flex;
    gap: 3px;
    flex-shrink: 0;
  }
  .tab,
  .toggle {
    background: transparent;
    border: 1px solid transparent;
    color: var(--text-dim);
    font-family: inherit;
    font-size: 10px;
    letter-spacing: 0.04em;
    padding: 6px 10px;
    cursor: pointer;
  }
  .tab.on {
    background: var(--panel2);
    border-color: var(--turq-strong);
    color: var(--turq-strong);
  }
  .toggle {
    border-color: var(--border);
  }
  .toggle.on {
    background: var(--purple-strong);
    border-color: var(--purple-strong);
    color: white;
  }
</style>
