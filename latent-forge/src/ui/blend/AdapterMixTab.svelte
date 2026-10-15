<script lang="ts">
  // Owner: KUANG (created 2026-10-15), from WINTERMUTE's phase-1 plan
  // ADAPTER MIX, phase 1 (spec 2026-10-15-adapter-mixer-design §4.2): the active lane's LoRA/DoRA as a
  // per-DiT-block curve. Edits arrangement.lanes[view.activeLane].chain.lora IN PLACE (the $state proxy
  // rule in LaneChain.svelte); the curve array itself is replaced on every edit.
  import { arrangement } from "../../lib/stores/arrangement.svelte";
  import { view } from "../../lib/stores/view.svelte";
  import { BLEND_IDEAS } from "../../lib/blend/registry";
  import {
    CURVE_SHAPES, N_BLOCKS, flatCurve, invertCurve, scaleCurve, smoothCurve, soloCurve,
  } from "../../lib/blend/curves";
  import type { BlendMode } from "../../lib/forge/types";
  import CurveEditor from "./CurveEditor.svelte";

  const chain = $derived(arrangement.lanes[view.activeLane].chain);
  const blend = $derived(chain.lora.blend ?? null);
  const missing = $derived(!chain.lora_on || !chain.lora.ckpt_path);
  let solo = $state(0);
  let shapePick = $state("");

  function toggleFx() {
    if (!chain.lora.blend) chain.lora.blend = { on: true, mode: "amount", curve: flatCurve(1) };
    else chain.lora.blend.on = !chain.lora.blend.on;
  }
  function setCurve(c: number[]) {
    if (chain.lora.blend) chain.lora.blend.curve = c;
  }
  function setMode(m: string) {
    if (chain.lora.blend) chain.lora.blend.mode = m as BlendMode;
  }
  function applyShape(id: string) {
    const s = CURVE_SHAPES.find((x) => x.id === id);
    if (s) setCurve(s.make());
    shapePick = "";
  }
</script>

<div class="adapter-mix">
  <div class="row">
    <button data-testid="adapter-fx-toggle" class:on={blend?.on} onclick={toggleFx}>
      ADVANCED FX {blend?.on ? "ON" : "OFF"}
    </button>
    <span class="lane">lane {view.activeLane + 1}</span>
    {#if blend?.on && blend.mode === "direction"}
      <span class="note" data-testid="adapter-direction-note">direction: for DoRA only an exact 0 turns a block off</span>
    {/if}
    {#if missing}
      <span class="warn" data-testid="adapter-missing">turn on LORA / DORA and pick an adapter in LANE CHAIN first</span>
    {/if}
  </div>
  {#if blend}
    <div class="row" class:dim={!blend.on}>
      <select data-testid="adapter-mode" value={blend.mode} onchange={(e) => setMode((e.currentTarget as HTMLSelectElement).value)}>
        {#each BLEND_IDEAS as b (b.id)}<option value={b.id} title={b.help}>{b.label}</option>{/each}
      </select>
      <select data-testid="adapter-shape" value={shapePick} onchange={(e) => applyShape((e.currentTarget as HTMLSelectElement).value)}>
        <option value="">shape…</option>
        {#each CURVE_SHAPES as s (s.id)}<option value={s.id}>{s.label}</option>{/each}
      </select>
      <label>solo <input data-testid="adapter-solo" type="number" min="0" max={N_BLOCKS - 1} step="1" bind:value={solo}
        onchange={() => setCurve(soloCurve(Math.max(0, Math.min(N_BLOCKS - 1, Math.round(solo)))))} /></label>
      <button data-testid="adapter-invert" onclick={() => setCurve(invertCurve(blend.curve))}>invert</button>
      <button data-testid="adapter-smooth" onclick={() => setCurve(smoothCurve(blend.curve))}>smooth</button>
      <button data-testid="adapter-half" onclick={() => setCurve(scaleCurve(blend.curve, 0.5))}>×½</button>
      <button data-testid="adapter-double" onclick={() => setCurve(scaleCurve(blend.curve, 2))}>×2</button>
      <button data-testid="adapter-reset" onclick={() => setCurve(flatCurve(1))}>reset</button>
    </div>
    <CurveEditor values={blend.curve} onChange={setCurve} height={96} />
  {/if}
</div>

<style>
  .adapter-mix { padding: 4px 8px; font-size: 12px; }
  .row { display: flex; gap: 6px; align-items: center; margin-bottom: 4px; flex-wrap: wrap; }
  .dim { opacity: 0.5; }
  .on { background: #2f5d2f; }
  .warn { color: #e0a040; }
  .lane { color: #888; }
  .note { color: #9a9aa6; }
  input[type="number"] { width: 44px; }
</style>
