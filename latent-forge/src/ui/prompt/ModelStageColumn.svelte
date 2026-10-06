<script lang="ts">
  // Spec 4.5 item 2. MODEL STAGE is session-level (spec 10 X4): it rebuilds
  // the backbone on the render server (~10s), so it is confirmed inline
  // (spec 5.3's exact wording lives in modelStage.ts) and the store's stage
  // is switched ONLY after the rebuild call resolves -- a failed rebuild must
  // leave settings.stage on the backbone actually loaded, per this
  // milestone's settings store (Task 1) and spec 5.3.
  //
  // LENGTH is settings.duration_sec (see this task's WHY paragraph), but this
  // column never writes it: it is a controlled prop pair, {length, onLength},
  // whose single owner is the tab (Task 10), so that the sigma column building
  // /schedule's `duration` and this input can never disagree mid-edit. The
  // clamp and the settings.patch both live up there.
  import { dragScale } from "../../lib/actions/dragScale";
  import { forgeApi } from "../../lib/forge/api";
  import { LENGTH_CAP_SEC } from "../../lib/forge/defaults";
  import type { Target } from "../../lib/forge/types";
  import { HELP } from "../../lib/help/strings";
  import { flatPlateauNote, POST_CFG_NOTE, RANGES } from "../../lib/sampling/scheduleRules";
  import { settings, STAGE_BACKBONE, type ModelStage } from "../../lib/stores/settings.svelte";
  import { randomSeed, stageConfirmMessage } from "./modelStage";

  interface Props {
    target: Target;
    length: number;
    onLength: (sec: number) => void;
  }
  let { target, length, onLength }: Props = $props();

  const current = $derived(settings.current(target));
  const flatWarn = $derived(flatPlateauNote(current.schedule, current.sampler_type));

  let pendingStage = $state<ModelStage | null>(null);
  let rebuilding = $state(false);
  let rebuildError = $state<string | null>(null);

  // settings.stageLocked: a session load owns the stage (M7 SessionController) -- no switch is
  // offered or started. settings.stageRebuilding: this column's rebuild is in flight -- M7 will
  // not start a load until it clears. Together they keep a rebuild and a load from overlapping.
  function clickStage(next: ModelStage): void {
    if (settings.stage === next || rebuilding || settings.stageLocked) return;
    pendingStage = next;
    rebuildError = null;
  }

  async function confirmStage(): Promise<void> {
    const next = pendingStage;
    if (next === null || settings.stageLocked) return;
    rebuilding = true;
    settings.stageRebuilding = true;
    try {
      await forgeApi.setBackbone(STAGE_BACKBONE[next]);
      settings.setStage(next);
      settings.activeBackbone = STAGE_BACKBONE[next];
      pendingStage = null;
    } catch (e) {
      rebuildError = e instanceof Error ? e.message : String(e);
    } finally {
      rebuilding = false;
      settings.stageRebuilding = false;
    }
  }

  function cancelStage(): void {
    pendingStage = null;
  }

  function onSteps(e: Event): void {
    settings.patch(target, { steps: Number((e.target as HTMLInputElement).value) });
  }
  function onCfg(e: Event): void {
    settings.patch(target, { cfg_scale: Number((e.target as HTMLInputElement).value) });
  }
  function onLengthTyped(e: Event): void {
    onLength(Number((e.target as HTMLInputElement).value));
  }
  function onSeed(e: Event): void {
    settings.patch(target, { seed: Number((e.target as HTMLInputElement).value) });
  }
  function onRnd(): void {
    settings.patch(target, { seed: randomSeed() });
  }
</script>

<div class="model-stage-column">
  <div class="stage-row">
    <div class="stage-buttons">
      <span class="label">MODEL STAGE</span>
      <div class="buttons">
        <button
          type="button" class="stage-btn" class:on={settings.stage === "POST"}
          data-testid="stage-post" data-help={HELP.modelStagePost} disabled={rebuilding || settings.stageLocked}
          onclick={() => clickStage("POST")}
        >POST</button>
        <button
          type="button" class="stage-btn" class:on={settings.stage === "BASE"}
          data-testid="stage-base" data-help={HELP.modelStageBase} disabled={rebuilding || settings.stageLocked}
          onclick={() => clickStage("BASE")}
        >BASE</button>
      </div>
    </div>
    <div class="field steps">
      <span class="label">STEPS</span>
      <input
        type="number" aria-label="STEPS" data-testid="stage-steps" data-help={HELP.steps}
        value={current.steps} onchange={onSteps}
        use:dragScale={{
          min: RANGES.steps.min, max: RANGES.steps.max, int: true, value: current.steps,
          onValue: (v) => settings.patch(target, { steps: v }),
        }}
      />
    </div>
    <div class="field cfg">
      <span class="label">CFG</span>
      <input
        type="number" step="0.1" aria-label="CFG" data-testid="stage-cfg" data-help={HELP.cfg}
        value={current.cfg_scale} disabled={settings.cfgDisabled} onchange={onCfg}
        use:dragScale={{
          min: RANGES.cfg_scale.min, max: RANGES.cfg_scale.max, value: current.cfg_scale,
          onValue: (v) => settings.patch(target, { cfg_scale: v }),
        }}
      />
    </div>
  </div>

  {#if pendingStage !== null}
    <div class="stage-confirm" data-testid="stage-confirm">
      <span>{stageConfirmMessage(pendingStage)}</span>
      <button type="button" data-testid="stage-confirm-continue" disabled={rebuilding || settings.stageLocked} onclick={confirmStage}>CONTINUE</button>
      <button type="button" data-testid="stage-confirm-cancel" disabled={rebuilding} onclick={cancelStage}>CANCEL</button>
    </div>
  {/if}
  {#if rebuildError !== null}
    <div class="stage-error" data-testid="stage-error">{rebuildError}</div>
  {/if}
  {#if settings.cfgDisabled}
    <div class="cfg-note" data-testid="cfg-note">{POST_CFG_NOTE}</div>
  {/if}
  {#if flatWarn !== null}
    <div class="flat-warn" data-testid="flat-warn">{flatWarn}</div>
  {/if}

  <div class="length-seed-row">
    <div class="field length">
      <span class="label">LENGTH s</span>
      <input
        type="number" aria-label="LENGTH s" data-testid="stage-length" data-help={HELP.length}
        value={length} onchange={onLengthTyped}
        use:dragScale={{ min: RANGES.length_sec.min, max: LENGTH_CAP_SEC, value: length, onValue: onLength }}
      />
    </div>
    <div class="field seed">
      <span class="label">SEED</span>
      <div class="seed-row">
        <input
          type="number" aria-label="SEED" data-testid="stage-seed" data-help={HELP.seed}
          value={current.seed} onchange={onSeed}
          use:dragScale={{
            min: RANGES.seed.min, max: RANGES.seed.max, int: true, value: current.seed,
            onValue: (v) => settings.patch(target, { seed: v }),
          }}
        />
        <button type="button" class="rnd" data-testid="stage-seed-rnd" data-help={HELP.seedRandom} onclick={onRnd}>RND</button>
      </div>
    </div>
  </div>
</div>

<style>
  .model-stage-column {
    display: flex;
    flex-direction: column;
    gap: 5px;
    min-height: 0;
  }
  .stage-row {
    display: flex;
    gap: 6px;
    align-items: flex-end;
  }
  .label {
    display: block;
    color: var(--text-dim);
    font-size: 10px;
    margin-bottom: 2px;
  }
  .buttons {
    display: flex;
    gap: 3px;
  }
  .stage-btn {
    background: var(--panel2);
    border: 1px solid var(--border);
    color: var(--text-dim);
    font-size: 10px;
    padding: 3px 6px;
    cursor: pointer;
  }
  .stage-btn.on {
    background: var(--turq-strong);
    border-color: var(--turq-strong);
    color: white;
  }
  .field input {
    width: 100%;
    box-sizing: border-box;
    background: var(--panel2);
    color: var(--text);
    border: 1px solid var(--border);
    padding: 4px;
    font-size: 11px;
    cursor: ew-resize;
  }
  .field input:disabled {
    color: var(--text-dim);
    cursor: default;
  }
  .steps {
    width: 46px;
  }
  .cfg {
    width: 40px;
  }
  .length {
    width: 56px;
  }
  .seed {
    width: 84px;
  }
  .seed-row {
    display: flex;
    gap: 3px;
  }
  .rnd {
    background: var(--panel2);
    border: 1px solid var(--border);
    color: var(--text-dim);
    font-size: 10px;
    padding: 0 5px;
    cursor: pointer;
  }
  .length-seed-row {
    display: flex;
    gap: 6px;
    align-items: flex-end;
  }
  .stage-confirm,
  .stage-error,
  .cfg-note,
  .flat-warn {
    font-size: 10px;
  }
  .stage-confirm {
    display: flex;
    align-items: center;
    gap: 6px;
    color: var(--warm);
  }
  .stage-confirm button {
    background: var(--panel2);
    border: 1px solid var(--border);
    color: var(--text);
    font-size: 10px;
    padding: 2px 6px;
    cursor: pointer;
  }
  .stage-error {
    color: var(--red);
  }
  .cfg-note,
  .flat-warn {
    color: var(--text-dim);
  }
</style>
