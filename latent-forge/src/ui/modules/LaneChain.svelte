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
  import { fetchLatchHeads, type LatchHeadInfo } from "../../lib/chains/latch";
  import { applyModulePreset, modulePresetPayload, type ModuleLevel } from "../../lib/chains/modulePresets";
  import { HELP } from "../../lib/help/strings";
  import { dragScale } from "../../lib/actions/dragScale";
  import {
    defaultRamp, isRamp, posToWeight, rampEnds, roundWeight, setRampFrom, setRampTo,
    targetReadout, targetScale, unitsOf, usableMaxWeight, weightReadout, weightToPos, WEIGHT_MAX,
  } from "../../lib/chains/latchScale";
  import type { LatchSlot } from "../../lib/forge/types";
  import ParamField from "./ParamField.svelte";

  const chain = $derived(arrangement.lanes[view.activeLane].chain);

  let heads = $state<Record<string, LatchHeadInfo>>({});
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
    fetchLatchHeads().then((h) => (heads = h)).catch(() => {});
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

  // --- LatCH slot helpers (spec §5.5) ---------------------------------------------------------
  // The scale of TARGET / WEIGHT, their units and the ramp ends live in lib/chains/latchScale.ts.

  /** The ends of a ramp are explicit (value_from -> value) and inside the head's range; anything
   *  else drops value_from, which is only read for a ramp. */
  function applyRampDefaults(slot: LatchSlot, was: string) {
    if (!isRamp(slot.kind)) {
      delete slot.value_from;
      return;
    }
    if (!isRamp(was)) {
      const r = defaultRamp(heads[slot.head], slot.kind);
      if (r) {
        slot.value_from = r.from;
        slot.value = r.to;
      } else {
        delete slot.value_from;   // head not known: the sampler's own 0 -> value ramp
      }
    } else if (was !== slot.kind && typeof slot.value_from === "number") {
      // ramp_up <-> ramp_down with explicit ends: flip the direction
      const { from, to } = rampEnds(slot);
      slot.value_from = to;
      slot.value = from;
    }
  }

  /** New head: kind falls back to the head's first supported kind, value starts at value_default. A
   *  weight above the head's clean limit comes down to it: hardness at the default weight 1 is the
   *  gain-512 setting that buzzed on goa (WORKLOG 2026-07-10), and its limit is 0.25. */
  function setHead(i: number, name: string) {
    const slot = chain.slots[i];
    const was = slot.kind;
    slot.head = name;
    const h = heads[name];
    if (!h) {   // "none"
      delete slot.value_from;
      return;
    }
    if (!h.supports_kinds.includes(slot.kind)) slot.kind = h.supports_kinds[0] ?? "constant";
    slot.value = slot.kind === "beat_grid"
      ? Math.max(60, Math.min(200, Math.round(arrangement.bpm)))
      : h.value_default;
    delete slot.value_from;
    applyRampDefaults(slot, isRamp(slot.kind) ? "constant" : was);
    const limit = usableMaxWeight(h);
    if (limit !== null && slot.weight > limit) slot.weight = roundWeight(limit);
  }

  function setKind(i: number, kind: string) {
    const slot = chain.slots[i];
    const was = slot.kind;
    slot.kind = kind;
    if (kind === "beat_grid" && was !== "beat_grid") slot.value = Math.max(60, Math.min(200, Math.round(arrangement.bpm)));
    else if (kind !== "beat_grid" && was === "beat_grid") slot.value = heads[slot.head]?.value_default ?? slot.value;
    applyRampDefaults(slot, was);
  }

  /** The line under a target field: its distance from the head's mean, or the out-of-range warning. */
  function targetNote(i: number, v: number) {
    const slot = chain.slots[i];
    return targetReadout(v, heads[slot.head], slot.kind);
  }

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

  <!-- LATCH GUIDANCE -->
  <div class="row">
    <button data-testid="latch-toggle" class:on={chain.latch_on} data-help={HELP.latchToggle}
      onclick={() => (chain.latch_on = !chain.latch_on)}>{chain.latch_on ? "ON" : "OFF"}</button>
    <span>LATCH GUIDANCE</span>
    {@render presetControls("latch", "LATCH GUIDANCE", HELP.modulePreset)}
  </div>

  {#each [0, 1] as i (i)}
    {@const slot = chain.slots[i]}
    {@const head = heads[slot.head]}
    {@const scale = targetScale(head, slot.kind)}
    {@const units = unitsOf(head, slot.kind)}
    {@const ramp = isRamp(slot.kind)}
    {@const ends = rampEnds(slot)}
    {@const limit = usableMaxWeight(head)}
    {@const wr = weightReadout(head, slot.weight, chain.hparams)}
    {@const toNote = targetNote(i, ramp ? ends.to : slot.value)}
    {@const fromNote = ramp ? targetNote(i, ends.from) : null}
    <fieldset class="slot">
      <legend>SLOT {i + 1}</legend>
      <div class="pair">
        <select aria-label="HEAD — slot {i + 1}" data-help={HELP.latchHead}
          value={slot.head} onchange={(e) => setHead(i, (e.currentTarget as HTMLSelectElement).value)}>
          <option value="none">none</option>
          {#each Object.values(heads) as h (h.name)}
            <option value={h.name}>{h.name} · {h.family}{h.health !== "ok" ? " ⚠" : ""}</option>
          {/each}
        </select>
        <select aria-label="KIND — slot {i + 1}" data-help={HELP.latchTargetKind}
          value={slot.kind} onchange={(e) => setKind(i, (e.currentTarget as HTMLSelectElement).value)}>
          {#each (head?.supports_kinds ?? ["constant"]) as k (k)}<option value={k}>{k}</option>{/each}
        </select>
      </div>
      {#if ramp}
        <!-- A ramp has two ends. The sampler's own ramp runs 0 -> value, which is a wall of noise on a
             head whose range is nowhere near 0 (hardness: 66 +/- 3.5), so both ends are shown and
             both are in the head's unit. -->
        <ParamField label="FROM" name="FROM — slot {i + 1}" help={HELP.latchTargetFrom}
          value={ends.from} onValue={(v) => setRampFrom(slot, v)}
          min={scale.min} max={scale.max} step={scale.step} lo={-1e6} hi={1e6}
          unit={units} decimals={scale.decimals}
          note={fromNote ? fromNote.text : ""} warn={fromNote?.warn ?? false} />
      {/if}
      <ParamField label={ramp ? "TO" : "TARGET"} name="TARGET — slot {i + 1}" help={HELP.latchTargetValue}
        value={ramp ? ends.to : slot.value}
        onValue={(v) => (ramp ? setRampTo(slot, v) : (slot.value = v))}
        min={scale.min} max={scale.max} step={scale.step} lo={-1e6} hi={1e6}
        unit={units} decimals={scale.decimals}
        note={toNote ? toNote.text : ""} warn={toNote?.warn ?? false} />
      <ParamField label="WEIGHT" name="WEIGHT — slot {i + 1}" help={HELP.latchWeight}
        value={slot.weight} onValue={(v) => (slot.weight = v)}
        min={0} max={WEIGHT_MAX} step={0.01} decimals={2}
        toPos={weightToPos} fromPos={posToWeight}
        mark={limit} markTitle="the weight past which this head's output breaks up"
        note={wr.text} warn={wr.warn} />
      <!-- The two sliders are independent; Task 1's wireSlot sends end_pct = max(start_pct, end_pct),
           so crossed sliders never reach parse_chain's start <= end check (critic follow-up #5).
           Stored as a fraction of the step schedule, shown as a percentage. -->
      <ParamField label="START" name="START % — slot {i + 1}" help={HELP.latchStartPct}
        value={slot.start_pct} onValue={(v) => (slot.start_pct = v)}
        min={0} max={1} step={0.01} factor={100} decimals={0} unit="%" />
      <ParamField label="END" name="END % — slot {i + 1}" help={HELP.latchEndPct}
        value={slot.end_pct} onValue={(v) => (slot.end_pct = v)}
        min={0} max={1} step={0.01} factor={100} decimals={0} unit="%" />
    </fieldset>
  {/each}

  <p class="section">GUIDANCE HYPERPARAMETERS</p>
  <ParamField label="ρ VAR" name="ρ VARIANCE" help={HELP.latchRho}
    value={chain.hparams.rho} onValue={(v) => (chain.hparams.rho = v)} min={0} max={30} step={0.1} decimals={2} />
  <ParamField label="μ MEAN" name="μ MEAN" help={HELP.latchMu}
    value={chain.hparams.mu} onValue={(v) => (chain.hparams.mu = v)} min={0} max={30} step={0.1} decimals={2} />
  <ParamField label="γ NOISE" name="γ NOISE" help={HELP.latchGamma}
    value={chain.hparams.gamma} onValue={(v) => (chain.hparams.gamma = v)} min={0} max={20} step={0.05} decimals={2} />
  <ParamField label="ITER" name="MEAN ITER" help={HELP.latchMeanIter}
    value={chain.hparams.n_iter} onValue={(v) => (chain.hparams.n_iter = Math.round(v))} min={1} max={80} step={1} decimals={0} />
  <button data-help={HELP.latchLogNorms} class:on={chain.hparams.log_norms}
    onclick={() => (chain.hparams.log_norms = !chain.hparams.log_norms)}>LOG GRADIENT NORMS</button>

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
  .hint, .section { margin: 0; font-size: 10px; color: var(--text-dim); }
  button.on { background: var(--turq-strong); color: white; border-color: var(--turq-strong); }
  select, input, button { background: var(--panel2); border: 1px solid var(--border); color: var(--text); font-size: 10px; }
  .slot { display: flex; flex-direction: column; gap: 4px; margin: 0; padding: 4px 6px 6px; border: 1px solid var(--border); min-width: 0; }
  .slot legend { font-size: 9px; letter-spacing: 0.08em; color: var(--text-dim); padding: 0 3px; }
  .pair { display: flex; gap: 4px; min-width: 0; }
  .pair select { flex: 1 1 0; min-width: 0; }
</style>
