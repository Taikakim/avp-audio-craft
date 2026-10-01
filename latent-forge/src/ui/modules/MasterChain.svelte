<script lang="ts">
  // Spec §4.6.5, §8.1 S8. arrangement.master is $state -- every control mutates a field on it in
  // place (Task 3 adds the field; this task never reassigns it).
  import { arrangement } from "../../lib/stores/arrangement.svelte";
  import { fetchLatchHeads, type LatchHeadInfo } from "../../lib/chains/latch";
  import { HELP } from "../../lib/help/strings";

  const master = $derived(arrangement.master);
  let heads = $state<Record<string, LatchHeadInfo>>({});

  $effect(() => {
    // .catch: a dead /info leaves the select at "none" rather than an unhandled rejection
    fetchLatchHeads().then((h) => (heads = h)).catch(() => {});
  });
</script>

<div class="master-chain">
  <p class="note">applied to the mixed latent, after the lane chains</p>

  <div class="row">
    <button data-testid="master-latch-toggle" class:on={master.latch_on} data-help={HELP.masterLatchToggle}
      onclick={() => (master.latch_on = !master.latch_on)}>{master.latch_on ? "ON" : "OFF"}</button>
    <span data-help={HELP.masterLatchHeadLabel}>LATCH HEAD</span>
  </div>

  <select aria-label="MASTER LATCH HEAD" data-help={HELP.masterHead} value={master.head}
    onchange={(e) => (master.head = (e.currentTarget as HTMLSelectElement).value)}>
    <option value="none">none</option>
    {#each Object.values(heads) as h (h.name)}
      <option value={h.name}>{h.name} · {h.family}{h.health !== "ok" ? " ⚠" : ""}</option>
    {/each}
  </select>

  <label>GAIN
    <input type="range" aria-label="GAIN" data-help={HELP.masterGain} min="0" max="120"
      value={master.gain} oninput={(e) => (master.gain = Number((e.currentTarget as HTMLInputElement).value))} />
  </label>

  <div class="row">
    <button data-testid="master-norm-toggle" class:on={master.norm_on}
      onclick={() => (master.norm_on = !master.norm_on)}>{master.norm_on ? "ON" : "OFF"}</button>
    <span data-help={HELP.latentNormalise}>LATENT NORMALISE</span>
  </div>
</div>

<style>
  .master-chain { display: flex; flex-direction: column; gap: 6px; padding: 6px 10px 8px; }
  .row { display: flex; align-items: center; gap: 5px; }
  .note { margin: 0; font-size: 10px; color: var(--text-dim); }
  button.on { background: var(--turq-strong); color: white; border-color: var(--turq-strong); }
  select, input, button { background: var(--panel2); border: 1px solid var(--border); color: var(--text); font-size: 10px; }
</style>
