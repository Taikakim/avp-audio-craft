<script lang="ts">
  // Spec §4.6.1. Present only while view.selection.kind === "overlap"
  // (RightPaneModules.svelte's own filter, M1 T12) -- this component does not
  // re-check that; it derives the CURRENT overlap from the selection so it
  // never throws if it is ever mounted transiently during a selection change.
  import { overlapInfoLine } from "../../lib/forge/overlapLabel";
  import { arrangement } from "../../lib/stores/arrangement.svelte";
  import { view } from "../../lib/stores/view.svelte";
  import { renderLabel, renderRequest } from "../../lib/render/dispatch";
  import { dispatchWorld } from "../../lib/render/dispatchWorld";
  import { renderBlock } from "../../lib/render/renderBlock";
  import { jobs } from "../../lib/render/jobs.svelte";
  import { PayloadError } from "../../lib/render/payloads";
  import { dragScale } from "../../lib/actions/dragScale";
  import { HELP } from "../../lib/help/strings";
  import EnvelopeEditor from "../master/EnvelopeEditor.svelte";

  const key = $derived(view.selection.kind === "overlap" ? view.selection.key : null);
  const overlap = $derived(key ? arrangement.overlaps.find((o) => o.key === key) ?? null : null);
  // peekOverlapParams, NEVER overlapParams, inside a $derived: overlapParams seeds the store on
  // first read, and a write during a derived throws state_unsafe_mutation (Global Constraint #8).
  // Edits go through patch() -> setOverlapParams, which seeds; this derived then re-runs.
  const params = $derived(key ? arrangement.peekOverlapParams(key) : null);
  const clipA = $derived(overlap ? arrangement.clips.find((c) => c.id === overlap.a_id) : undefined);
  const clipB = $derived(overlap ? arrangement.clips.find((c) => c.id === overlap.b_id) : undefined);
  const info = $derived(overlap ? overlapInfoLine(overlap, clipA, clipB) : "");

  function patch(p: Parameters<typeof arrangement.setOverlapParams>[1]) {
    if (key) arrangement.setOverlapParams(key, p);
  }

  const target = $derived(view.selection);
  // inpaintPayload has no `chain` field, so the LatCH head registry is not read on this path and
  // fetching it here would be a network call whose result is discarded.
  const world = $derived.by(() => dispatchWorld(target, {}));

  const blocked = $derived(
    renderBlock(target, {
      busy: jobs.active !== null,
      gpuBusyOther: jobs.gpuBusyOther,
      settings: world.settings,
      clip: null,
      clipOp: null,
      arcPrompt: world.arcPrompt,
      bendOpCount: 0,
      overlapSpanSec: world.overlap ? world.overlap.end_sec - world.overlap.start_sec : 0,
      padSec: world.padSec,
    }),
  );

  /** Same rule as Task 6's `mine`: the SAMPLING count belongs to the control that started the job,
   *  identified by targetKey so selecting elsewhere mid-render does not move the label. */
  const mine = $derived(jobs.active !== null && jobs.active.targetKey === view.selectionKey);
  const label = $derived(renderLabel(mine, jobs.stepsLeft));

  async function onInpaint(): Promise<void> {
    if (blocked !== null) return;
    try {
      await jobs.submit(renderRequest(target, world));
    } catch (e) {
      jobs.lastError = {
        targetKey: view.selectionKey,
        message: e instanceof PayloadError ? e.message : String(e),
      };
    }
  }
</script>

<!-- Both, not `params` alone: peekOverlapParams never returns null, so a selected key that no
     longer names an overlap (after a load or a clip move) would otherwise still render a body. -->
{#if overlap && params}
  <div class="overlap">
    <p class="info">{info}</p>

    <span class="caption">CROSSFADE CURVE — drag a node or bend a segment</span>
    <div class="curve-editor">
      <EnvelopeEditor envelope={params.curve} active={true} onChange={(env) => patch({ curve: env })} />
    </div>

    <div class="row">
      <button
        class="toggle"
        class:on={params.chroma_xfade}
        data-testid="overlap-chroma-xfade"
        data-help={HELP.overlapChromaXfade}
        onclick={() => patch({ chroma_xfade: !params.chroma_xfade })}
      >{params.chroma_xfade ? "[ON]" : "[OFF]"}</button>
      <span class="label">CHROMA CROSSFADE</span>
    </div>

    <div class="row">
      <button
        class="toggle"
        class:on={params.override}
        data-testid="overlap-override"
        data-help={HELP.overlapOverride}
        onclick={() => patch({ override: !params.override })}
      >{params.override ? "[ON]" : "[OFF]"}</button>
      <span class="label">LOCAL STEPS / CFG</span>
    </div>

    <div class="field">
      <span class="fieldlabel">STEPS</span>
      <input
        type="number"
        data-testid="overlap-steps"
        data-help={HELP.overlapSteps}
        disabled={!params.override}
        value={params.steps}
        use:dragScale={{ min: 1, max: 100, int: true, value: params.steps, onValue: (v) => patch({ steps: v }) }}
        onchange={(e) => patch({ steps: parseInt((e.currentTarget as HTMLInputElement).value, 10) || 0 })}
      />
    </div>

    <div class="field">
      <span class="fieldlabel">CFG</span>
      <input
        type="number"
        step="0.1"
        data-testid="overlap-cfg"
        data-help={HELP.overlapCfg}
        disabled={!params.override}
        value={params.cfg}
        use:dragScale={{ min: 0, max: 64, value: params.cfg, onValue: (v) => patch({ cfg: v }) }}
        onchange={(e) => patch({ cfg: parseFloat((e.currentTarget as HTMLInputElement).value) || 0 })}
      />
    </div>

    <!-- M9 wires the real preview-job submission (spec §7.1); this milestone's
         button is a frame only, the same boundary as MIXDOWN (M1 T10) and the
         MIX tab's own ▸ MIXDOWN (M7 Writer A T5). -->
    <button
      class="inpaint"
      data-testid="inpaint-overlap-button"
      title={blocked ?? ""}
      disabled={blocked !== null}
      onclick={onInpaint}>{mine ? label : "▸ INPAINT OVERLAP"}</button>
  </div>
{/if}

<style>
  .overlap {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 8px 10px 12px;
    border-left: 3px solid var(--purple-strong);
    background: oklch(54% 0.10 300 / 0.08);
  }
  .info,
  .caption {
    margin: 0;
    font-size: 10px;
    color: var(--text-dim);
  }
  .curve-editor {
    position: relative;
    width: 100%;
    height: 64px;
    background: var(--panel2);
    border: 1px solid var(--border);
  }
  .row {
    display: flex;
    align-items: center;
    gap: 5px;
  }
  .label {
    font-size: 10px;
  }
  .toggle {
    background: var(--panel2);
    border: 1px solid var(--border);
    color: var(--text-dim);
    font-family: inherit;
    font-size: 10px;
    padding: 2px 6px;
    cursor: pointer;
  }
  .toggle.on {
    border-color: var(--purple-strong);
    color: var(--purple-strong);
  }
  .field {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .fieldlabel {
    width: 52px;
    font-size: 10px;
    color: var(--text-dim);
  }
  .field input {
    flex: 1;
    background: var(--panel2);
    border: 1px solid var(--border);
    color: var(--text);
    font-size: 10px;
    padding: 3px;
    cursor: ew-resize;
  }
  .field input:disabled {
    cursor: default;
    opacity: 0.5;
  }
  .inpaint {
    background: var(--purple-strong);
    border: 1px solid var(--purple-strong);
    color: white;
    font-size: 11px;
    font-weight: 600;
    padding: 6px;
    cursor: pointer;
  }
</style>
