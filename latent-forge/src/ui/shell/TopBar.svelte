<script lang="ts">
  // Spec §4.2, left to right: wordmark · SESSION · MODEL · model folder · MASTER
  // PRESET + SAVE · MIXDOWN slot · WORKSPACE / STATISTICS · HELP · DARK.
  //
  // 42 px, box-sizing: border-box so the 1 px bottom border is inside the height
  // the layout test measures. `overflow: hidden` plus `min-width: 0` on every
  // flexible child keeps the row from ever giving the page a horizontal scrollbar
  // (spec §11.3).
  //
  // Every prop after `ontheme` has a default, so the bar renders before the three
  // fetches in App.svelte have answered.
  import MixdownSlot from "../topbar/MixdownSlot.svelte";
  import type { ModelOption } from "../topbar/modelOptions";

  type ForgeView = "workspace" | "statistics";

  interface SessionSummary {
    name: string;
    /** File mtime in epoch SECONDS (float) -- `new Date(updated * 1000)` if it is ever shown. */
    updated: number;
    n_clips: number;
  }

  interface Props {
    view: ForgeView;
    onview: (v: ForgeView) => void;
    helpMode: boolean;
    onhelp: () => void;
    theme: "light" | "dark";
    ontheme: () => void;
    sessions?: SessionSummary[];
    session?: string;
    onsession?: (name: string) => void;
    models?: ModelOption[];
    model?: string;
    onmodel?: (value: string) => void;
    modelFolder?: string;
    onmodelfolder?: (value: string) => void;
    masterPresets?: string[];
    masterPreset?: string;
    onmasterpreset?: (name: string) => void;
    mixdownBusy?: boolean;
    mixdownStepsLeft?: number | null;
  }
  let {
    view,
    onview,
    helpMode,
    onhelp,
    theme,
    ontheme,
    sessions = [],
    session = "",
    onsession = () => {},
    models = [],
    model = "",
    onmodel = () => {},
    modelFolder = "",
    onmodelfolder = () => {},
    masterPresets = [],
    masterPreset = "",
    onmasterpreset = () => {},
    mixdownBusy = false,
    mixdownStepsLeft = null,
  }: Props = $props();
</script>

<header class="topbar" data-region="topbar">
  <div class="wordmark">LATENT FORGE</div>

  <select
    class="session"
    data-testid="session-select"
    data-help="Session — clips rendered in one working session."
    value={session}
    onchange={(e) => onsession((e.currentTarget as HTMLSelectElement).value)}
  >
    {#each sessions as s (s.name)}
      <option value={s.name}>{s.name}</option>
    {/each}
  </select>

  <select
    class="model"
    data-testid="model-select"
    data-help="Checkpoint used for generation, a2a, inpainting and the encode/decode round trip. The first four entries are backbones and switching one rebuilds the model; the rest are adapters and set the session's default checkpoint path."
    value={model}
    onchange={(e) => onmodel((e.currentTarget as HTMLSelectElement).value)}
  >
    {#each models as m (m.value)}
      <option value={m.value}>{m.label}</option>
    {/each}
  </select>

  <input
    class="folder"
    type="text"
    data-testid="model-folder"
    data-help="Direct checkpoint folder — any path the loader can read."
    value={modelFolder}
    onchange={(e) => onmodelfolder((e.currentTarget as HTMLInputElement).value)}
  />

  <div class="preset-group">
    <span class="caption">MASTER PRESET</span>
    <select
      class="preset"
      data-testid="master-preset-select"
      data-help="Master preset — every lane chain, the clip layout, mix order and node values, master chain, sigma schedule and prompt in one recall."
      value={masterPreset}
      onchange={(e) => onmasterpreset((e.currentTarget as HTMLSelectElement).value)}
    >
      {#each masterPresets as name (name)}
        <option value={name}>{name}</option>
      {/each}
    </select>
    <!-- Saving a master preset is M7 (spec §9.3); the copy is final here. -->
    <button class="save" data-testid="master-preset-save" disabled>SAVE</button>
  </div>

  <MixdownSlot busy={mixdownBusy} stepsLeft={mixdownStepsLeft} />

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
  .session,
  .model,
  .preset {
    background: var(--panel2);
    color: var(--text);
    border: 1px solid var(--border);
    font-family: inherit;
    font-size: 11px;
    padding: 4px 6px;
    min-width: 0;
  }
  .session {
    flex: 1;
    max-width: 165px;
  }
  .model {
    flex: 1;
    max-width: 170px;
  }
  .folder {
    flex: 2;
    min-width: 60px;
    background: var(--panel2);
    color: var(--text);
    border: 1px solid var(--border);
    font-family: inherit;
    font-size: 11px;
    padding: 4px 6px;
  }
  .preset-group {
    display: flex;
    align-items: center;
    gap: 4px;
    flex-shrink: 0;
    border-left: 1px solid var(--border);
    padding-left: 8px;
  }
  .caption {
    font-size: 10px;
    color: var(--text-dim);
  }
  .preset {
    font-size: 10px;
    padding: 3px 5px;
    max-width: 135px;
    border-color: var(--purple-strong);
  }
  .save {
    background: var(--panel2);
    border: 1px solid var(--border);
    color: var(--text-dim);
    font-family: inherit;
    font-size: 10px;
    padding: 3px 6px;
    cursor: pointer;
  }
  .save:disabled {
    cursor: default;
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
