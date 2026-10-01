<script lang="ts">
  import { forgeApi, ForgeApiError } from "../../lib/forge/api";
  import { HELP } from "../../lib/help/strings";
  import {
    applyPromptPreset, applyRenderPreset, presetOptions,
    PROMPT_GROUP_LABEL, RENDER_GROUP_LABEL, type PresetOption,
  } from "../../lib/presets/renderPresets";
  import { settings } from "../../lib/stores/settings.svelte";
  import type { Target } from "../../lib/forge/types";

  let { target, disabled = false }: { target: Target; disabled?: boolean } = $props();

  let options = $state<PresetOption[]>([]);
  let value = $state("");
  let message = $state<string | null>(null);

  const renderOptions = $derived(options.filter((o) => o.level === "render"));
  const promptOptions = $derived(options.filter((o) => o.level === "prompt"));

  async function load(): Promise<void> {
    try {
      const [r, p] = await Promise.all([forgeApi.presets("render"), forgeApi.presets("prompt")]);
      options = presetOptions(r.names, p.names);
      message = null;
    } catch (e) {
      // 9.7: the server's own hint text is kept. An unreadable preset directory
      // is not a reason to disable the control -- saving one is how it is created.
      message = e instanceof ForgeApiError ? e.message : String(e);
    }
  }

  $effect(() => {
    void load();
  });

  async function choose(ev: Event): Promise<void> {
    const v = (ev.currentTarget as HTMLSelectElement).value;
    value = v;
    if (v === "") return;
    const sep = v.indexOf(":");
    const level = v.slice(0, sep);
    const name = v.slice(sep + 1);
    try {
      // `forgeApi.preset` resolves to the preset payload itself (M1 T5), so `res` IS the
      // body to validate. There is no `{ok, preset}` envelope to unwrap.
      const res = await forgeApi.preset(level, name);
      const into = settings.editable(target);
      const r = level === "prompt"
        ? applyPromptPreset(into, res)
        : applyRenderPreset(into, res);
      message = r.rejected.length > 0 ? `ignored: ${r.rejected.join(", ")}` : null;
    } catch (e) {
      message = e instanceof ForgeApiError ? e.message : String(e);
    }
  }
</script>

<!-- `promptPreset` is the id M1 T14's table gives this control (v3:361), and the id Task 8's
     placeholder select already carried. There is no `settingsPreset` id. -->
<label class="wrap" data-help={HELP.promptPreset}>
  <span class="lab">SETTINGS PRESET</span>
  <select aria-label="SETTINGS PRESET" {disabled} {value} onchange={choose}>
    <option value="">—</option>
    {#if renderOptions.length > 0}
      <optgroup label={RENDER_GROUP_LABEL}>
        {#each renderOptions as o (o.name)}
          <option value={`render:${o.name}`}>{o.name}</option>
        {/each}
      </optgroup>
    {/if}
    {#if promptOptions.length > 0}
      <optgroup label={PROMPT_GROUP_LABEL}>
        {#each promptOptions as o (o.name)}
          <option value={`prompt:${o.name}`}>{o.name}</option>
        {/each}
      </optgroup>
    {/if}
  </select>
</label>
{#if message}<span class="msg">{message}</span>{/if}

<style>
  .wrap { display: flex; flex-direction: column; gap: 2px; }
  .lab { color: var(--text-dim); font-size: 10px; }
  select {
    background: var(--panel2);
    color: var(--text);
    border: 1px solid var(--border);
    padding: 4px;
    font-size: 11px;
  }
  .msg { color: var(--red); font-size: 10px; align-self: center; }
</style>
