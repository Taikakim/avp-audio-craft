<script lang="ts">
  // Spec 4.6 item 4, 5.3. M1 T12 left this file as a frame naming this exact task. Every
  // field writes through Task 1's settings store for view.selection -- an M1 store, read the
  // same way M1 T12's own RightPaneModules.svelte already reads it, so this component takes
  // no props from that file and needs it untouched. `a2a` and `latch` are upstream facts
  // (M5's clip store, M7's lane-chain store) that do not exist yet, so both are props with
  // safe defaults, the same pattern Task 8's TargetBar uses for `a2a`.
  import { dragScale } from "../../lib/actions/dragScale";
  import type { LatchSlot, ScheduleSpec, Target } from "../../lib/forge/types";
  import {
    formatCfgBound, progressAtStep, stepAtProgress, type CfgUnit,
  } from "../../lib/sampling/cfgInterval";
  import { scheduleClient } from "../../lib/sampling/scheduleClient.svelte";
  import { RANGES, SCHEDULE_SHAPES, validateSchedule } from "../../lib/sampling/scheduleRules";
  import { resolveSampler, type LatchState } from "../../lib/sampling/samplers";
  import { sigmaMaxFor } from "../../lib/sampling/sigmaMax";
  import { HELP } from "../../lib/help/strings";
  import { settings } from "../../lib/stores/settings.svelte";
  import { view } from "../../lib/stores/view.svelte";
  import { fieldIssue, shapeUsesLambda } from "./advancedSampling";

  interface Props {
    a2a?: { on: boolean; noise: number } | null;
    latch?: LatchState;
  }
  let { a2a = null, latch = { latch_on: false, slots: [] as readonly LatchSlot[] } }: Props = $props();

  const target = $derived<Target>(view.selection);
  const current = $derived(settings.current(target));
  const scheduleSnapshot = $derived<ScheduleSpec>({ ...current.schedule });
  const sigmaMax = $derived(sigmaMaxFor(a2a));
  const sampler = $derived(resolveSampler(settings.objective, current.sampler_type, latch));
  const usesLambda = $derived(shapeUsesLambda(scheduleSnapshot.shape));
  const issues = $derived(validateSchedule(scheduleSnapshot, sigmaMax, sampler.value));

  // The sigma array the graph is drawing, read from the shared client (Task 4's singleton).
  // This module never calls request() -- Task 10's SigmaColumn owns that -- but it must count
  // steps on the SAME array, or the UNIT toggle would answer "which step does progress 0.7
  // reach" differently from the band drawn on the canvas.
  const sigmas = $derived<readonly number[]>(scheduleClient.result?.sigmas ?? []);
  const hasSchedule = $derived(sigmas.length > 0);
  const steps = $derived(scheduleClient.result?.steps ?? current.steps);

  let cfgUnit = $state<CfgUnit>("progress");
  const cfgLoText = $derived(formatCfgBound(sigmas, current.cfg_interval_progress[0], cfgUnit));
  const cfgHiText = $derived(formatCfgBound(sigmas, current.cfg_interval_progress[1], cfgUnit));
  // Spec 5.1: the steps unit drags over 0..steps as integers; progress stays on RANGES.cfg_interval.
  const cfgRange = $derived(
    cfgUnit === "steps"
      ? { min: 0, max: steps, int: true }
      : { min: RANGES.cfg_interval.min, max: RANGES.cfg_interval.max, int: false },
  );
  // What the drag action should carry: the displayed number, which is a step index in the
  // steps unit and the progress itself in the progress unit.
  const cfgLoDrag = $derived(
    cfgUnit === "steps"
      ? stepAtProgress(sigmas, current.cfg_interval_progress[0])
      : current.cfg_interval_progress[0],
  );
  const cfgHiDrag = $derived(
    cfgUnit === "steps"
      ? stepAtProgress(sigmas, current.cfg_interval_progress[1])
      : current.cfg_interval_progress[1],
  );

  /**
   * Spec 5.3 and this plan's Normative block: the stored value is ALWAYS progress. The steps
   * unit is a display, so every write from it converts back through the same sigma array it
   * was displayed from. Without this, typing 3 in the steps unit stored progress 3.0.
   */
  function toProgress(displayed: number): number {
    return cfgUnit === "steps" ? progressAtStep(sigmas, displayed) : displayed;
  }

  function onSampler(e: Event): void {
    settings.patch(target, { sampler_type: (e.target as HTMLSelectElement).value });
  }
  function onShape(e: Event): void {
    settings.patchSchedule(target, { shape: (e.target as HTMLSelectElement).value as ScheduleSpec["shape"] });
  }
  function setCfgLo(v: number): void {
    settings.patch(target, { cfg_interval_progress: [v, current.cfg_interval_progress[1]] });
  }
  function setCfgHi(v: number): void {
    settings.patch(target, { cfg_interval_progress: [current.cfg_interval_progress[0], v] });
  }
  function onCfgLo(e: Event): void {
    setCfgLo(toProgress(Number((e.target as HTMLInputElement).value)));
  }
  function onCfgHi(e: Event): void {
    setCfgHi(toProgress(Number((e.target as HTMLInputElement).value)));
  }
  function toggleCfgUnit(): void {
    if (!hasSchedule) return;
    cfgUnit = cfgUnit === "progress" ? "steps" : "progress";
  }
</script>

<div class="advanced-sampling">
  <div class="row">
    <div class="field wide">
      <span class="label">SAMPLER</span>
      <select
        data-testid="adv-sampler" data-help={HELP.sampler}
        disabled={sampler.disabled} value={sampler.value} onchange={onSampler}
      >
        {#if sampler.forced}
          <option value={sampler.value}>{sampler.label}</option>
        {:else}
          {#each sampler.options as o (o)}
            <option value={o}>{o}</option>
          {/each}
        {/if}
      </select>
    </div>
    <div class="field wide">
      <span class="label">SHAPE</span>
      <select data-testid="adv-shape" data-help={HELP.scheduleShape} value={scheduleSnapshot.shape} onchange={onShape}>
        {#each SCHEDULE_SHAPES as s (s)}
          <option value={s}>{s}</option>
        {/each}
      </select>
      {#if fieldIssue(issues, "shape") !== null}
        <span class="issue" data-testid="adv-issue-shape">{fieldIssue(issues, "shape")?.message}</span>
      {/if}
    </div>
    <div class="field">
      <span class="label">σ CURVE</span>
      <input
        type="number" step="0.1" data-testid="adv-rho" data-help={HELP.scheduleRho}
        value={scheduleSnapshot.rho}
        use:dragScale={{
          min: RANGES.rho.min, max: RANGES.rho.max, value: scheduleSnapshot.rho,
          onValue: (v) => settings.patchSchedule(target, { rho: v }),
        }}
        onchange={(e) => settings.patchSchedule(target, { rho: Number((e.target as HTMLInputElement).value) })}
      />
      {#if fieldIssue(issues, "rho") !== null}
        <span class="issue" data-testid="adv-issue-rho">{fieldIssue(issues, "rho")?.message}</span>
      {/if}
    </div>
  </div>

  <div class="row">
    <div class="field">
      <span class="label">λ MIN</span>
      <input
        type="number" step="0.1" data-testid="adv-lam-min" data-help={HELP.lamMin}
        disabled={!usesLambda} value={scheduleSnapshot.lam_min}
        use:dragScale={{
          min: RANGES.lam_min.min, max: RANGES.lam_min.max, value: scheduleSnapshot.lam_min,
          onValue: (v) => settings.patchSchedule(target, { lam_min: v }),
        }}
        onchange={(e) => settings.patchSchedule(target, { lam_min: Number((e.target as HTMLInputElement).value) })}
      />
    </div>
    <div class="field">
      <span class="label">λ MAX</span>
      <input
        type="number" step="0.1" data-testid="adv-lam-max" data-help={HELP.lamMax}
        disabled={!usesLambda} value={scheduleSnapshot.lam_max}
        use:dragScale={{
          min: RANGES.lam_max.min, max: RANGES.lam_max.max, value: scheduleSnapshot.lam_max,
          onValue: (v) => settings.patchSchedule(target, { lam_max: v }),
        }}
        onchange={(e) => settings.patchSchedule(target, { lam_max: Number((e.target as HTMLInputElement).value) })}
      />
    </div>
    {#if !usesLambda}
      <span class="note" data-testid="adv-lam-note">λ MIN / λ MAX are meaningful only for the logsnr shape</span>
    {/if}
  </div>

  <div class="row">
    <div class="field">
      <span class="label">σ MIN</span>
      <input
        type="number" step="0.01" data-testid="adv-sigma-min" data-help={HELP.sigmaMin}
        value={scheduleSnapshot.sigma_min}
        use:dragScale={{
          min: RANGES.sigma_min.min, max: RANGES.sigma_min.max, value: scheduleSnapshot.sigma_min,
          onValue: (v) => settings.patchSchedule(target, { sigma_min: v }),
        }}
        onchange={(e) => settings.patchSchedule(target, { sigma_min: Number((e.target as HTMLInputElement).value) })}
      />
      {#if fieldIssue(issues, "sigma_min") !== null}
        <span class="issue" data-testid="adv-issue-sigma_min">{fieldIssue(issues, "sigma_min")?.message}</span>
      {/if}
    </div>
    <div class="field">
      <span class="label">σ MAX</span>
      <input
        type="number" aria-label="σ MAX" data-testid="adv-sigma-max" data-help={HELP.sigmaMax}
        readonly value={sigmaMax.toFixed(2)}
      />
    </div>
    <div class="field toggle">
      <span class="label">STEPPED</span>
      <button
        type="button" class="stepped" class:on={scheduleSnapshot.stepped}
        data-testid="adv-stepped" data-help={HELP.stepped}
        onclick={() => settings.patchSchedule(target, { stepped: !scheduleSnapshot.stepped })}
      >{scheduleSnapshot.stepped ? "ON" : "OFF"}</button>
    </div>
  </div>

  <div class="row">
    <div class="field">
      <span class="label">PLATEAUS</span>
      <input
        type="number" step="1" data-testid="adv-plateaus" data-help={HELP.plateaus}
        value={scheduleSnapshot.plateaus}
        use:dragScale={{
          min: RANGES.plateaus.min, max: RANGES.plateaus.max, int: true, value: scheduleSnapshot.plateaus,
          onValue: (v) => settings.patchSchedule(target, { plateaus: v }),
        }}
        onchange={(e) => settings.patchSchedule(target, { plateaus: Number((e.target as HTMLInputElement).value) })}
      />
      {#if fieldIssue(issues, "plateaus") !== null}
        <span class="issue" data-testid="adv-issue-plateaus">{fieldIssue(issues, "plateaus")?.message}</span>
      {/if}
    </div>
    <div class="field">
      <span class="label">TILT</span>
      <input
        type="number" step="0.05" data-testid="adv-tilt" data-help={HELP.tilt}
        value={scheduleSnapshot.tilt}
        use:dragScale={{
          min: RANGES.tilt.min, max: RANGES.tilt.max, value: scheduleSnapshot.tilt,
          onValue: (v) => settings.patchSchedule(target, { tilt: v }),
        }}
        onchange={(e) => settings.patchSchedule(target, { tilt: Number((e.target as HTMLInputElement).value) })}
      />
      {#if fieldIssue(issues, "tilt") !== null}
        <span class="issue" data-testid="adv-issue-tilt">{fieldIssue(issues, "tilt")?.message}</span>
      {/if}
    </div>
    <div class="field">
      <span class="label">RESCALE</span>
      <input
        type="number" step="0.01" data-testid="adv-rescale" data-help={HELP.rescale}
        value={current.scale_phi}
        use:dragScale={{
          min: RANGES.scale_phi.min, max: RANGES.scale_phi.max, value: current.scale_phi,
          onValue: (v) => settings.patch(target, { scale_phi: v }),
        }}
        onchange={(e) => settings.patch(target, { scale_phi: Number((e.target as HTMLInputElement).value) })}
      />
    </div>
  </div>

  <div class="row">
    <div class="field">
      <span class="label">CFG LO</span>
      <input
        type="number" step={cfgUnit === "steps" ? 1 : 0.01}
        data-testid="adv-cfg-lo" data-help={HELP.cfgLo}
        value={cfgLoText}
        use:dragScale={{
          min: cfgRange.min, max: cfgRange.max, int: cfgRange.int, value: cfgLoDrag,
          onValue: (v) => setCfgLo(toProgress(v)),
        }}
        onchange={onCfgLo}
      />
    </div>
    <div class="field">
      <span class="label">CFG HI</span>
      <input
        type="number" step={cfgUnit === "steps" ? 1 : 0.01}
        data-testid="adv-cfg-hi" data-help={HELP.cfgHi}
        value={cfgHiText}
        use:dragScale={{
          min: cfgRange.min, max: cfgRange.max, int: cfgRange.int, value: cfgHiDrag,
          onValue: (v) => setCfgHi(toProgress(v)),
        }}
        onchange={onCfgHi}
      />
    </div>
    <div class="field">
      <span class="label">UNIT</span>
      <!-- Disabled, with a reason, until a schedule exists: the step index is computed from
           the server's sigma array, and showing a confident "0" instead would be a lie the
           person has no way to see through. -->
      <button
        type="button" class="unit" data-testid="adv-cfg-unit" data-help={HELP.cfgUnit}
        disabled={!hasSchedule}
        title={hasSchedule ? "" : "the step index needs a schedule from the server"}
        onclick={toggleCfgUnit}
      >{cfgUnit === "progress" ? "PROGRESS" : "STEPS"}</button>
    </div>
  </div>
</div>

<style>
  .advanced-sampling {
    padding: 6px 10px 10px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .row {
    display: flex;
    gap: 6px;
    align-items: flex-end;
    flex-wrap: wrap;
  }
  .field {
    display: flex;
    flex-direction: column;
    width: 60px;
  }
  .field.wide {
    width: 110px;
  }
  .label {
    color: var(--text-dim);
    font-size: 10px;
    margin-bottom: 2px;
  }
  input,
  select {
    box-sizing: border-box;
    background: var(--panel2);
    color: var(--text);
    border: 1px solid var(--border);
    padding: 4px;
    font-size: 11px;
    width: 100%;
  }
  input:not([readonly]) {
    cursor: ew-resize;
  }
  input:disabled,
  input[readonly] {
    color: var(--text-dim);
  }
  .stepped,
  .unit {
    background: var(--panel2);
    border: 1px solid var(--border);
    color: var(--text-dim);
    font-size: 10px;
    padding: 4px 6px;
    cursor: pointer;
    width: 100%;
  }
  .stepped.on {
    background: var(--turq-strong);
    border-color: var(--turq-strong);
    color: white;
  }
  .issue {
    font-size: 10px;
    color: var(--red);
  }
  .note {
    font-size: 10px;
    color: var(--text-dim);
  }
</style>
