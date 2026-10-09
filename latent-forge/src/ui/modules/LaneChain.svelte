<script lang="ts">
  // Spec §5.5. Every field below mutates arrangement.lanes[view.activeLane].chain IN PLACE -- it
  // is a $state-proxied object (M5's defaultLanes() seeds it from structuredClone(CHAIN_DEFAULTS)).
  // Never do `lane.chain = {...}` or capture `const chain = lane.chain` and mutate the capture only
  // -- both silently stop being reactive. M5's lane-header chain dot
  // (docs/superpowers/plans/.../m5-timeline-fidelity.md:2546) already derives off this same object,
  // so nothing here needs to "light" anything itself.
  import { arrangement } from "../../lib/stores/arrangement.svelte";
  import { view } from "../../lib/stores/view.svelte";
  import { forgeApi } from "../../lib/forge/api";
  import { fetchAdapters, fetchFilmCkpts, fetchSlots, type SlotEntry } from "../../lib/forge/models";
  // AdapterEntry is declared in modelOptions.ts; models.ts only `import type`s it (M1 T10).
  import type { AdapterEntry } from "../topbar/modelOptions";
  import { applyModulePreset, modulePresetPayload, type ModuleLevel } from "../../lib/chains/modulePresets";
  import { HELP } from "../../lib/help/strings";
  import { dragScale } from "../../lib/actions/dragScale";
  import LatchGuidance from "./LatchGuidance.svelte";
  import ParamField from "./ParamField.svelte";

  const chain = $derived(arrangement.lanes[view.activeLane].chain);

  let filmCkpts = $state<AdapterEntry[]>([]);
  let filmDefaultCkpt = $state<string | null>(null);
  let residentSlots = $state<SlotEntry[]>([]);
  let loraOptions = $state<AdapterEntry[]>([]);
  let presetNames = $state<Record<ModuleLevel, string[]>>({ latch: [], film: [], lora: [], bungee: [] });
  // The picked preset per LANE, not per component (critic pass 2 #4): recall "dub" on lane 1,
  // switch to lane 2, and SAVE must not overwrite "dub" with lane 2's settings, nor DEL delete a
  // preset lane 2 never used. Indexed by view.activeLane.
  const blankPicked = (): Record<ModuleLevel, string> => ({ latch: "", film: "", lora: "", bungee: "" });
  let presetPicked = $state<Record<ModuleLevel, string>[]>([blankPicked(), blankPicked(), blankPicked(), blankPicked()]);
  const picked = $derived(presetPicked[view.activeLane]);

  const LEVELS: readonly ModuleLevel[] = ["latch", "film", "lora", "bungee"];

  // Every fetch .catch()es: an unmounted root, a dead server or (in jsdom) a relative URL must
  // leave the control empty, not raise an unhandled rejection.
  $effect(() => {
    fetchFilmCkpts().then((c) => (filmCkpts = c)).catch(() => {});
    // Only the ckpt is read here. SCALE already starts at the server's gain: M1's
    // CHAIN_DEFAULTS.film.gain is 1.75, the same FILM_DEFAULT_GAIN /info.film_default reports
    // (reconcile pass 2026-09-25, Open questions 26), so an untouched lane stays default.
    forgeApi.info().then((info) => {
      const fd = (info as { film_default?: { ckpt: string | null } }).film_default;
      filmDefaultCkpt = fd?.ckpt ?? null;
    }).catch(() => {});
    fetchSlots()
      .then(async (s) => {
        residentSlots = s.slots;
        const resident: AdapterEntry[] = s.slots.map((sl) => ({ path: sl.path, name: sl.label, label: sl.label, family: sl.family }));
        const a = await fetchAdapters().catch(() => [] as AdapterEntry[]);
        const seen = new Set(resident.map((r) => r.path));
        loraOptions = [...resident, ...a.filter((x) => !seen.has(x.path))];
      })
      .catch(() => {});
    for (const level of LEVELS) {
      // Block body, not `(r) => (presetNames[level] = r.names)`: returning an assignment to $state
      // makes Svelte warn assignment_value_stale (one warning per level at mount).
      forgeApi.presets(level).then((r) => { presetNames[level] = r.names; }).catch(() => {});
    }
  });

  // --- LORA / DORA ----------------------------------------------------------------------------
  /** ckpt_path is the durable identity; the slot index is resolved from it against what /slots
   *  says is resident NOW (contract table, critic pass 2 #14), never trusted from a saved payload. */
  function slotFor(path: string | null): number | null {
    return path ? (residentSlots.find((s) => s.path === path)?.index ?? null) : null;
  }

  function setLoraModel(path: string) {
    chain.lora.ckpt_path = path || null;
    // a resident /slots entry also records its slot index, so switching to it is the cheap path
    chain.lora.slot = slotFor(chain.lora.ckpt_path);
  }

  // --- module presets (spec §9.3: recall applies to the ACTIVE lane) -----------------------------
  // Every handler captures the lane (and its chain) BEFORE its first await: a response must land
  // in the lane the user acted on, even if view.activeLane changed while it was in flight.
  async function recallModulePreset(level: ModuleLevel, name: string) {
    const lane = view.activeLane;
    const target = arrangement.lanes[lane].chain;
    presetPicked[lane][level] = name;
    if (!name) return;
    try {
      const payload = await forgeApi.preset(level, name);
      applyModulePreset(target, level, payload);
      if (level === "lora") target.lora.slot = slotFor(target.lora.ckpt_path);
    } catch {
      // a preset deleted elsewhere, or a dead server: the lane keeps what it has
    }
  }

  async function saveModulePreset(level: ModuleLevel) {
    const lane = view.activeLane;
    const source = arrangement.lanes[lane].chain;
    let name = presetPicked[lane][level];
    if (!name) {
      const typed = window.prompt(`${level} preset name:`, "");
      if (!typed) return;
      name = typed;
    }
    const payload = modulePresetPayload(source, level);   // taken before the await, from that lane
    try {
      await forgeApi.savePreset(level, name, payload);
      if (!presetNames[level].includes(name)) presetNames[level] = [...presetNames[level], name];
      presetPicked[lane][level] = name;
    } catch {
      // the server's refusal (bad name, disk) is surfaced by forgeApi's own error; nothing to undo
    }
  }

  async function deleteModulePreset(level: ModuleLevel) {
    const name = presetPicked[view.activeLane][level];
    if (!name) return;
    try {
      await forgeApi.deletePreset(level, name);
      presetNames[level] = presetNames[level].filter((n) => n !== name);
      // gone from the server, so gone from every lane that had it picked
      for (const p of presetPicked) if (p[level] === name) p[level] = "";
    } catch {
      // leave the list as it is if the server refused
    }
  }
</script>

{#snippet presetControls(level: ModuleLevel, label: string, help: string)}
  <select aria-label="{label} preset" data-help={help} value={picked[level]}
    onchange={(e) => recallModulePreset(level, (e.currentTarget as HTMLSelectElement).value)}>
    <option value=""></option>
    {#each presetNames[level] as name (name)}<option value={name}>{name}</option>{/each}
  </select>
  <button data-testid="{level}-preset-save" data-help={HELP.modulePresetSave} onclick={() => saveModulePreset(level)}>SAVE</button>
  <button data-testid="{level}-preset-delete" data-help={HELP.modulePresetDelete}
    disabled={!picked[level]} onclick={() => deleteModulePreset(level)}>DEL</button>
{/snippet}

<div class="lane-chain">
  <p class="hint">latent chain for the selected lane — click another lane header to switch</p>

  <!-- LATCH GUIDANCE: the same component the MASTER CHAIN uses -->
  <LatchGuidance block={chain} toggleTestId="latch-toggle" toggleHelp="latchToggle">
    {#snippet header()}
      {@render presetControls("latch", "LATCH GUIDANCE", HELP.modulePreset)}
    {/snippet}
  </LatchGuidance>

  <!-- FILM -->
  <div class="row">
    <button data-testid="film-toggle" class:on={chain.film_on} data-help={HELP.filmToggle}
      onclick={() => (chain.film_on = !chain.film_on)}>{chain.film_on ? "ON" : "OFF"}</button>
    <span>FILM</span>
    {@render presetControls("film", "FILM", HELP.filmPreset)}
  </div>
  <select aria-label="FILM CKPT" data-help={HELP.filmCkpt} value={chain.film.ckpt ?? ""}
    onchange={(e) => (chain.film.ckpt = (e.currentTarget as HTMLSelectElement).value || null)}>
    <option value="">server default{filmDefaultCkpt ? ` (${filmDefaultCkpt})` : ""}</option>
    {#each filmCkpts as c (c.path)}<option value={c.path}>{c.label || c.name || c.path}</option>{/each}
  </select>
  <ParamField label="SCALE" name="FILM SCALE" help={HELP.filmScale}
    value={chain.film.gain} onValue={(v) => (chain.film.gain = v)} min={0} max={2} step={0.05} decimals={2} />
  <ParamField label="TARGET" name="FILM TARGET" help={HELP.filmTarget}
    value={chain.film.value} onValue={(v) => (chain.film.value = v)} min={0} max={16} step={0.1} decimals={1} />

  <!-- LORA / DORA -->
  <div class="row">
    <button data-testid="lora-toggle" class:on={chain.lora_on} data-help={HELP.loraToggle}
      onclick={() => (chain.lora_on = !chain.lora_on)}>{chain.lora_on ? "ON" : "OFF"}</button>
    <span>LORA / DORA</span>
    {@render presetControls("lora", "LORA / DORA", HELP.loraPreset)}
  </div>
  <!-- An explicit "none": without it a null ckpt_path would display as the first adapter. -->
  <select aria-label="LORA / DORA MODEL" data-help={HELP.loraModel} value={chain.lora.ckpt_path ?? ""}
    onchange={(e) => setLoraModel((e.currentTarget as HTMLSelectElement).value)}>
    <option value="">none</option>
    {#each loraOptions as o (o.path)}<option value={o.path}>{o.label || o.name || o.path}</option>{/each}
  </select>
  <ParamField label="SCALE" name="LORA / DORA SCALE" help={HELP.loraScale}
    value={chain.lora.strength} onValue={(v) => (chain.lora.strength = v)} min={0} max={1} step={0.01} decimals={2} />

  <!-- BUNGEE -->
  <div class="row">
    <button data-testid="bungee-toggle" class:on={chain.bungee_on} data-help={HELP.bungeeToggle}
      onclick={() => (chain.bungee_on = !chain.bungee_on)}>{chain.bungee_on ? "ON" : "OFF"}</button>
    <span>BUNGEE STRETCH / PITCH</span>
  </div>
  <div class="row">
    {@render presetControls("bungee", "BUNGEE", HELP.bungeePreset)}
  </div>
  <label>SEMITONES
    <input type="number" step="0.5" aria-label="SEMITONES" data-help={HELP.bungeeSemitones}
      value={chain.semitones}
      use:dragScale={{ min: -24, max: 24, value: chain.semitones, onValue: (v) => (chain.semitones = v) }}
      onchange={(e) => (chain.semitones = Number((e.currentTarget as HTMLInputElement).value))} />
  </label>
</div>

<style>
  .lane-chain { display: flex; flex-direction: column; gap: 6px; padding: 6px 10px 8px; }
  .row { display: flex; align-items: center; gap: 5px; }
  .hint { margin: 0; font-size: 10px; color: var(--text-dim); }
  button.on { background: var(--turq-strong); color: white; border-color: var(--turq-strong); }
  select, input, button { background: var(--panel2); border: 1px solid var(--border); color: var(--text); font-size: 10px; }
</style>
