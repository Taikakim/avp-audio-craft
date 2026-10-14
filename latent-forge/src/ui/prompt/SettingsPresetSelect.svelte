<script lang="ts">
  import { api } from "../../lib/api";
  import { forgeApi, ForgeApiError } from "../../lib/forge/api";
  import { requestPresetModel } from "../../lib/forge/presetModel";
  import { HELP } from "../../lib/help/strings";
  import {
    applyPromptPreset, applyRenderPreset, applyServerPreset, presetComment, presetOptions,
    PROMPT_GROUP_LABEL, RENDER_GROUP_LABEL, SERVER_GROUP_LABEL, TEST_GROUP_LABEL, TEST_PREFIX, type PresetOption,
  } from "../../lib/presets/renderPresets";
  import { promptNotes } from "../../lib/stores/promptNotes.svelte";
  // Last edited: WINTERMUTE 2026-10-13 — test prompts group; a recalled preset's comment is shown
  import { settings } from "../../lib/stores/settings.svelte";
  import type { Target } from "../../lib/forge/types";

  let { target, disabled = false }: { target: Target; disabled?: boolean } = $props();

  let options = $state<PresetOption[]>([]);
  let serverOptions = $state<{ name: string; notes?: string }[]>([]);
  let value = $state("");
  let message = $state<string | null>(null);

  const renderOptions = $derived(options.filter((o) => o.group === RENDER_GROUP_LABEL));
  const promptOptions = $derived(options.filter((o) => o.level === "prompt"));
  const testOptions = $derived(options.filter((o) => o.group === TEST_GROUP_LABEL));

  async function load(): Promise<void> {
    // The server's own recipe store (GET /presets) is separate from the Forge one and
    // best-effort: a failure there must not hide the Forge presets.
    void api.presets().then((r) => { serverOptions = r.presets; }).catch(() => {});
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
    if (level === "server") {
      try {
        const body = await api.presetGet(name);
        const r = applyServerPreset(settings.editable(target), body);
        const notes = (body as { notes?: unknown }).notes;
        promptNotes.showComment(name, typeof notes === "string" ? notes : "");
        // Asks before switching, like a master preset (presetModel.ts); backbone unknown here.
        if (r.ckptPath !== undefined) await requestPresetModel({ backbone: null, ckpt_path: r.ckptPath }, name);
        message = r.rejected.length > 0 ? `ignored: ${r.rejected.join(", ")}` : null;
      } catch (e) {
        message = e instanceof Error ? e.message : String(e);
      }
      return;
    }
    try {
      // `forgeApi.preset` resolves to the preset payload itself (M1 T5), so `res` IS the
      // body to validate. There is no `{ok, preset}` envelope to unwrap.
      const res = await forgeApi.preset(level, name);
      const into = settings.editable(target);
      const r = level === "prompt"
        ? applyPromptPreset(into, res)
        : applyRenderPreset(into, res);
      promptNotes.showComment(name, presetComment(res));
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
    {#if testOptions.length > 0}
      <optgroup label={TEST_GROUP_LABEL}>
        {#each testOptions as o (o.name)}
          <option value={`render:${o.name}`}>{o.name.slice(TEST_PREFIX.length)}</option>
        {/each}
      </optgroup>
    {/if}
    {#if serverOptions.length > 0}
      <optgroup label={SERVER_GROUP_LABEL}>
        {#each serverOptions as o (o.name)}
          <option value={`server:${o.name}`} title={o.notes ?? ""}>{o.name}</option>
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
