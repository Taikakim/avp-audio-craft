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
  import { project } from "../../lib/store.svelte";
  import MixdownSlot from "../topbar/MixdownSlot.svelte";
  import type { ModelOption } from "../topbar/modelOptions";
  import { HELP } from "../../lib/help/strings";

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

  let fileInput = $state<HTMLInputElement>();
  let notice = $state<string | null>(null);

  // TEMPORARY: M7 replaces both with the SESSION select over /forge/sessions
  // (spec §4.2). Until then this is the only way a project survives a reload,
  // so it is carried over rather than dropped.
  function saveProject() {
    const blob = new Blob([project.toJSON()], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `latent-forge-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "")}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  async function loadProject(e: Event) {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    try {
      const { relinkNeeded } = project.loadJSON(await file.text());
      notice = relinkNeeded
        ? `loaded — ${relinkNeeded} clip(s) need audio relinked`
        : "loaded";
    } catch (err) {
      notice = `load failed: ${err instanceof Error ? err.message : String(err)}`;
    }
    input.value = "";
    setTimeout(() => (notice = null), 6000);
  }
</script>

<header class="topbar" data-region="topbar">
  <div class="wordmark">LATENT FORGE</div>

  <select
    class="session"
    data-testid="session-select"
    data-help={HELP.session}
    value={session}
    onchange={(e) => onsession((e.currentTarget as HTMLSelectElement).value)}
  >
    {#each sessions as s (s.name)}
      <option value={s.name}>{s.name}</option>
    {/each}
  </select>

  <button data-testid="save-project" onclick={saveProject}>SAVE</button>
  <button data-testid="load-project" onclick={() => fileInput?.click()}>LOAD</button>
  <input bind:this={fileInput} type="file" accept="application/json" onchange={loadProject} hidden />
  {#if notice}<span class="notice">{notice}</span>{/if}

  <select
    class="model"
    data-testid="model-select"
    data-help={HELP.model}
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
    data-help={HELP.modelFolder}
    value={modelFolder}
    onchange={(e) => onmodelfolder((e.currentTarget as HTMLInputElement).value)}
  />

  <div class="preset-group">
    <span class="caption">MASTER PRESET</span>
    <select
      class="preset"
      data-testid="master-preset-select"
      data-help={HELP.masterPreset}
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
      data-help={HELP.helpToggle}
      onclick={onhelp}>HELP</button>
    <button
      class="toggle"
      class:on={theme === "dark"}
      data-testid="dark-toggle"
      data-help={HELP.darkToggle}
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
  .notice {
    font-size: 10px;
    color: var(--text-dim);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    min-width: 0;
    flex-shrink: 1;
  }
</style>
