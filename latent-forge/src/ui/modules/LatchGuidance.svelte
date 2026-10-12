<script lang="ts">
  // LatCH guidance as ONE paradigm: the toggle, two head slots (head, kind, target or ramp ends, weight,
  // window) and the guidance hyperparameters. LANE CHAIN edits a lane's chain with it and MASTER CHAIN
  // edits the master's, so the two cannot drift apart again (the master's LatCH used to be one head and
  // one gain; Kim, 2026-10-09: "it should have the same ones than the lane ones ... a single paradigm
  // that both call").
  //
  // `block` is anything with the three LatCH keys -- a LaneChain and a MasterChain both are -- and every
  // field mutates it IN PLACE: it is a $state-proxied object owned by the arrangement store, so never
  // replace it or copy it and edit the copy (both silently stop being reactive).
  //
  // The host decides what is host-specific: `toggleTestId` / `toggleHelp` for the toggle, `namePrefix`
  // so two instances on screen at once keep distinct accessible names ("MASTER HEAD — slot 1"), and an
  // optional `header` snippet beside the toggle (the lane's preset controls).
  import type { Snippet } from "svelte";
  import { arrangement } from "../../lib/stores/arrangement.svelte";
  import { fetchLatchHeads, type LatchHeadInfo } from "../../lib/chains/latch";
  import {
    defaultRamp, isRamp, posToWeight, rampEnds, roundWeight, setRampFrom, setRampTo,
    targetReadout, targetScale, unitsOf, usableMaxWeight, weightReadout, weightToPos, WEIGHT_MAX,
  } from "../../lib/chains/latchScale";
  import type { LatchBlock, LatchSlot } from "../../lib/forge/types";
  import { HELP } from "../../lib/help/strings";
  import type { HelpId } from "../../lib/help/strings";
  import ParamField from "./ParamField.svelte";

  interface Props {
    block: LatchBlock;
    /** The row title beside the toggle. */
    label?: string;
    toggleTestId: string;
    toggleHelp: HelpId;
    /** Prepended to every accessible name, e.g. "MASTER ". */
    namePrefix?: string;
    header?: Snippet;
  }
  let { block, label = "LATCH GUIDANCE", toggleTestId, toggleHelp, namePrefix = "", header }: Props = $props();

  let heads = $state<Record<string, LatchHeadInfo>>({});

  // .catch(): an unmounted root, a dead server or (in jsdom) a relative URL must leave the select
  // empty, not raise an unhandled rejection.
  $effect(() => {
    fetchLatchHeads().then((h) => (heads = h)).catch(() => {});
  });

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
    const slot = block.slots[i];
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
    const slot = block.slots[i];
    const was = slot.kind;
    slot.kind = kind;
    if (kind === "beat_grid" && was !== "beat_grid") slot.value = Math.max(60, Math.min(200, Math.round(arrangement.bpm)));
    else if (kind !== "beat_grid" && was === "beat_grid") slot.value = heads[slot.head]?.value_default ?? slot.value;
    applyRampDefaults(slot, was);
  }

  /** The line under a target field: its distance from the head's mean, or the out-of-range warning. */
  function targetNote(i: number, v: number) {
    const slot = block.slots[i];
    return targetReadout(v, heads[slot.head], slot.kind);
  }
</script>

<div class="latch-guidance">
  <div class="row">
    <button data-testid={toggleTestId} class:on={block.latch_on} data-help={HELP[toggleHelp]}
      onclick={() => (block.latch_on = !block.latch_on)}>{block.latch_on ? "ON" : "OFF"}</button>
    <span>{label}</span>
    {@render header?.()}
  </div>

  {#each [0, 1] as i (i)}
    {@const slot = block.slots[i]}
    {@const head = heads[slot.head]}
    {@const scale = targetScale(head, slot.kind)}
    {@const units = unitsOf(head, slot.kind)}
    {@const ramp = isRamp(slot.kind)}
    {@const ends = rampEnds(slot)}
    {@const limit = usableMaxWeight(head)}
    {@const wr = weightReadout(head, slot.weight, block.hparams)}
    {@const toNote = targetNote(i, ramp ? ends.to : slot.value)}
    {@const fromNote = ramp ? targetNote(i, ends.from) : null}
    <fieldset class="slot">
      <legend>SLOT {i + 1}</legend>
      <div class="pair">
        <select aria-label="{namePrefix}HEAD — slot {i + 1}" data-help={HELP.latchHead}
          value={slot.head} onchange={(e) => setHead(i, (e.currentTarget as HTMLSelectElement).value)}>
          <option value="none">none</option>
          {#each Object.values(heads) as h (h.name)}
            <option value={h.name}>{h.name} · {h.family}{h.health !== "ok" ? " ⚠" : ""}</option>
          {/each}
        </select>
        <select aria-label="{namePrefix}KIND — slot {i + 1}" data-help={HELP.latchTargetKind}
          value={slot.kind} onchange={(e) => setKind(i, (e.currentTarget as HTMLSelectElement).value)}>
          {#each (head?.supports_kinds ?? ["constant"]) as k (k)}<option value={k}>{k}</option>{/each}
        </select>
      </div>
      {#if ramp}
        <!-- A ramp has two ends. The sampler's own ramp runs 0 -> value, which is a wall of noise on a
             head whose range is nowhere near 0 (hardness: 66 +/- 3.5), so both ends are shown and
             both are in the head's unit. -->
        <ParamField label="FROM" name="{namePrefix}FROM — slot {i + 1}" help={HELP.latchTargetFrom}
          value={ends.from} onValue={(v) => setRampFrom(slot, v)}
          min={scale.min} max={scale.max} step={scale.step} lo={-1e6} hi={1e6}
          unit={units} decimals={scale.decimals}
          note={fromNote ? fromNote.text : ""} warn={fromNote?.warn ?? false} />
      {/if}
      <ParamField label={ramp ? "TO" : "TARGET"} name="{namePrefix}TARGET — slot {i + 1}" help={HELP.latchTargetValue}
        value={ramp ? ends.to : slot.value}
        onValue={(v) => (ramp ? setRampTo(slot, v) : (slot.value = v))}
        min={scale.min} max={scale.max} step={scale.step} lo={-1e6} hi={1e6}
        unit={units} decimals={scale.decimals}
        note={toNote ? toNote.text : ""} warn={toNote?.warn ?? false} />
      <ParamField label="WEIGHT" name="{namePrefix}WEIGHT — slot {i + 1}" help={HELP.latchWeight}
        value={slot.weight} onValue={(v) => (slot.weight = v)}
        min={0} max={WEIGHT_MAX} step={0.01} decimals={2}
        toPos={weightToPos} fromPos={posToWeight}
        mark={limit} markTitle="the weight past which this head's output breaks up"
        note={wr.text} warn={wr.warn} />
      <!-- The two sliders are independent; wireSlot sends end_pct = max(start_pct, end_pct), so crossed
           sliders never reach parse_chain's start <= end check (critic follow-up #5). Stored as a
           fraction of the step schedule, shown as a percentage. -->
      <ParamField label="START" name="{namePrefix}START % — slot {i + 1}" help={HELP.latchStartPct}
        value={slot.start_pct} onValue={(v) => (slot.start_pct = v)}
        min={0} max={1} step={0.01} factor={100} decimals={0} unit="%" />
      <ParamField label="END" name="{namePrefix}END % — slot {i + 1}" help={HELP.latchEndPct}
        value={slot.end_pct} onValue={(v) => (slot.end_pct = v)}
        min={0} max={1} step={0.01} factor={100} decimals={0} unit="%" />
    </fieldset>
  {/each}

  <p class="section">GUIDANCE HYPERPARAMETERS</p>
  <ParamField label="ρ VAR" name="{namePrefix}ρ VARIANCE" help={HELP.latchRho}
    value={block.hparams.rho} onValue={(v) => (block.hparams.rho = v)} min={0} max={30} step={0.1} decimals={2} />
  <ParamField label="μ MEAN" name="{namePrefix}μ MEAN" help={HELP.latchMu}
    value={block.hparams.mu} onValue={(v) => (block.hparams.mu = v)} min={0} max={30} step={0.1} decimals={2} />
  <ParamField label="γ NOISE" name="{namePrefix}γ NOISE" help={HELP.latchGamma}
    value={block.hparams.gamma} onValue={(v) => (block.hparams.gamma = v)} min={0} max={20} step={0.05} decimals={2} />
  <ParamField label="ITER" name="{namePrefix}MEAN ITER" help={HELP.latchMeanIter}
    value={block.hparams.n_iter} onValue={(v) => (block.hparams.n_iter = Math.round(v))} min={1} max={80} step={1} decimals={0} />
  <button data-help={HELP.latchLogNorms} class:on={block.hparams.log_norms}
    onclick={() => (block.hparams.log_norms = !block.hparams.log_norms)}>LOG GRADIENT NORMS</button>
</div>

<style>
  .latch-guidance { display: flex; flex-direction: column; gap: 6px; }
  .row { display: flex; align-items: center; gap: 5px; }
  .section { margin: 0; font-size: 10px; color: var(--text-dim); }
  button.on { background: var(--turq-strong); color: white; border-color: var(--turq-strong); }
  select, button { background: var(--panel2); border: 1px solid var(--border); color: var(--text); font-size: 10px; }
  .slot { display: flex; flex-direction: column; gap: 4px; margin: 0; padding: 4px 6px 6px; border: 1px solid var(--border); min-width: 0; }
  .slot legend { font-size: 9px; letter-spacing: 0.08em; color: var(--text-dim); padding: 0 3px; }
  .pair { display: flex; gap: 4px; min-width: 0; }
  .pair select { flex: 1 1 0; min-width: 0; }
</style>
