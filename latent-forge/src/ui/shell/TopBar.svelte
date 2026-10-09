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
  import { epochLabel, modelMenu, type ModelOption } from "../topbar/modelOptions";
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
    onsessionsave?: () => void;
    onimportv1?: (file: File) => void;
    onmasterpresetsave?: () => void;
    /** The session or file a load/import is fetching or applying; "" when idle (critic pass 3 #11). */
    loadingName?: string;
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
    onsessionsave = () => {},
    onimportv1 = () => {},
    onmasterpresetsave = () => {},
    loadingName = "",
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

  // One entry per adapter RUN in the MODEL select, its epochs in the select beside it.
  const menu = $derived(modelMenu(models, model));

  let importInput = $state<HTMLInputElement>();

  function onImportPicked(e: Event) {
    const input = e.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    if (file) onimportv1(file);
    input.value = ""; // picking the same file twice still fires change
  }
</script>

<header class="topbar" data-region="topbar">
  <div class="wordmark">LATENT FORGE</div>

  <select
    class="session"
    data-testid="session-select"
    data-help={HELP.session}
    value={session}
    onchange={(e) => {
      const el = e.currentTarget as HTMLSelectElement;
      onsession(el.value);
      el.value = session; // the committed name; a successful load changes the prop and the select follows
    }}
  >
    {#if !session}<option value="">unsaved</option>{/if}
    {#each sessions as s (s.name)}
      <option value={s.name}>{s.name}</option>
    {/each}
  </select>

  {#if loadingName}<span class="notice" data-testid="session-loading">loading {loadingName}…</span>{/if}
  <button class="save" data-testid="session-save" data-help={HELP.sessionSave}
    disabled={!!loadingName} onclick={onsessionsave}>SAVE</button>
  <button class="save" data-testid="session-import" data-help={HELP.sessionImportV1}
    onclick={() => importInput?.click()}>IMPORT</button>
  <input bind:this={importInput} data-testid="session-import-file" type="file"
    accept="application/json,.json" onchange={onImportPicked} hidden />

  <select
    class="model"
    data-testid="model-select"
    data-help={HELP.model}
    value={model}
    onchange={(e) => onmodel((e.currentTarget as HTMLSelectElement).value)}
  >
    {#each menu.primary as m (m.value)}
      <option value={m.value}>{m.label}</option>
    {/each}
  </select>

  {#if menu.epochs.length > 0}
    <select
      class="epoch"
      aria-label="EPOCH"
      data-testid="epoch-select"
      data-help={HELP.modelEpoch}
      value={model}
      onchange={(e) => onmodel((e.currentTarget as HTMLSelectElement).value)}
    >
      {#each menu.epochs as m (m.value)}
        <option value={m.value}>{epochLabel(m)}</option>
      {/each}
    </select>
  {/if}

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
      onchange={(e) => {
        const el = e.currentTarget as HTMLSelectElement;
        onmasterpreset(el.value);
        el.value = masterPreset; // the applied preset; a successful recall changes the prop
      }}
    >
      {#each masterPresets as name (name)}
        <option value={name}>{name}</option>
      {/each}
    </select>
    <button class="save" data-testid="master-preset-save" data-help={HELP.masterPresetSave} onclick={onmasterpresetsave}>SAVE</button>
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
  .epoch,
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
  .epoch {
    flex: 0 1 112px;
    max-width: 112px;
    border-color: var(--turq-strong);
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
