<script lang="ts">
  // Spec §4.6.5, §8.1 S8. arrangement.master is $state -- every control mutates a field on it in
  // place (Task 3 adds the field; this task never reassigns it).
  //
  // The master's LatCH is the lane's: LatchGuidance.svelte edits the same slots and hyperparameters on
  // either, so what a lane can steer with the mix can steer with too. What is the master's own is how
  // deep that guided pass re-noises the mix (NOISE) and LATENT NORMALISE.
  import { arrangement } from "../../lib/stores/arrangement.svelte";
  import { HELP } from "../../lib/help/strings";
  import LatchGuidance from "./LatchGuidance.svelte";
  import ParamField from "./ParamField.svelte";

  const master = $derived(arrangement.master);
</script>

<div class="master-chain">
  <p class="note">applied to the mixed latent, after the lane chains</p>

  <LatchGuidance block={master} toggleTestId="master-latch-toggle" toggleHelp="masterLatchToggle" namePrefix="MASTER " />

  <ParamField label="NOISE" name="MASTER LATCH NOISE" help={HELP.masterNoise}
    value={master.noise} onValue={(v) => (master.noise = v)} min={0} max={1} step={0.01} decimals={2} />

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
  button { background: var(--panel2); border: 1px solid var(--border); color: var(--text); font-size: 10px; }
</style>
