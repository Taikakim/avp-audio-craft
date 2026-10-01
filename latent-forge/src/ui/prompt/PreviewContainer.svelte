<script lang="ts">
  // Spec §4.5's render preview container — FRAME ONLY, 44 px, full width.
  //
  // M9 owns every behaviour here: running the pane's current target (§7.1),
  // filling HISTORY with the session's renders newest first tagged GEN / A2A /
  // INPAINT / MIX with length, drawing and scrubbing the waveform (reading its
  // colours through getComputedStyle so DARK works), play/stop independent of the
  // timeline transport, `draggable` with a dragstart payload so the render drops
  // onto a lane, USE SETTINGS copying the previewed render's job payload into the
  // current target, and REPLACE CLIP swapping a clip's audio while keeping the
  // previous ref in clip.history.
  import { HELP } from "../../lib/help/strings";
  import { fetchLatchHeads, type LatchHeadInfo } from "../../lib/chains/latch";
  import { PAD_SEC, renderLabel, renderRequest } from "../../lib/render/dispatch";
  import { jobs } from "../../lib/render/jobs.svelte";
  import { MIXDOWN_TARGET_KEY } from "../../lib/render/mixdown.svelte";
  import { renderBlock } from "../../lib/render/renderBlock";
  import { PayloadError } from "../../lib/render/payloads";
  import { arrangement } from "../../lib/stores/arrangement.svelte";
  import { settings } from "../../lib/stores/settings.svelte";
  import { view } from "../../lib/stores/view.svelte";

  // One fetch per mounted container, resolving {} on failure (M7 T1). The heads only decide which
  // LatCH slots survive into the chain, so an empty registry sends a chain with no slots rather
  // than blocking a render.
  let heads = $state<Record<string, LatchHeadInfo>>({});
  $effect(() => {
    fetchLatchHeads().then((h) => (heads = h)).catch(() => {});
  });

  const target = $derived(view.selection);

  const clip = $derived.by(() => {
    const sel = view.selection;
    return sel.kind === "clip" ? (arrangement.clips.find((c) => c.id === sel.id) ?? null) : null;
  });

  const overlap = $derived.by(() => {
    const sel = view.selection;
    return sel.kind === "overlap" ? (arrangement.overlaps.find((o) => o.key === sel.key) ?? null) : null;
  });

  const world = $derived({
    settings: settings.current(target),
    cfgScale: settings.effectiveCfg(target),
    clip,
    lane: clip ? (arrangement.lanes[clip.lane] ?? null) : null,
    heads,
    ckptPath: settings.ckptPath,
    overlap,
    // `peekOverlapParams`, NOT `overlapParams`: the latter SEEDS `OVERLAP_DEFAULT` into the store
    // on first read, and this is a $derived -- Global constraint 4, `state_unsafe_mutation`, the
    // first time an operator selects an overlap they have never opened in INPAINT. The peek
    // returns a fresh default-shaped copy for an unstored key, so no fallback is needed.
    overlapParams: overlap ? arrangement.peekOverlapParams(overlap.key) : null,
    clipById: (id: string) => arrangement.clips.find((c) => c.id === id) ?? null,
    // No prompt-ARC field exists in M9's UI: `longform` reads the target's prompt as its arc, which
    // is what _longform_impl falls back to on the server (`req["schedule"] or req["prompt"]`).
    arcPrompt: settings.current(target).prompt,
    // No bend-op editor exists either -- renderBlock refuses `bend` with an empty list, so this is
    // the honest empty rather than an invented default (Open question B3).
    bendOps: [] as unknown[],
    padSec: PAD_SEC,
  });

  const blocked = $derived(
    renderBlock(target, {
      busy: jobs.active !== null,
      gpuBusyOther: jobs.gpuBusyOther,
      settings: world.settings,
      clip,
      clipOp: clip?.op ?? null,
      arcPrompt: world.arcPrompt,
      bendOpCount: world.bendOps.length,
      overlapSpanSec: overlap ? overlap.end_sec - overlap.start_sec : 0,
      padSec: PAD_SEC,
    }),
  );

  /** The SAMPLING count belongs to the control that STARTED the job (§7.1). A commit runs under
   *  MIXDOWN_TARGET_KEY, so the top-bar slot counts it and this button only greys out; anything
   *  else was started from here. Comparing against the key rather than the live selection means
   *  selecting a different clip mid-render does not move the label. */
  const mine = $derived(jobs.active !== null && jobs.active.targetKey !== MIXDOWN_TARGET_KEY);
  const label = $derived(renderLabel(mine, jobs.stepsLeft));

  async function onRender(): Promise<void> {
    if (blocked !== null) return;
    try {
      await jobs.submit(renderRequest(target, world));
    } catch (e) {
      // A PayloadError here is a field the server would 400 on; §9.7 wants it on the target bar,
      // and jobs.lastError is that surface (Writer A T5 renders it).
      jobs.lastError = { targetKey: view.selectionKey, message: e instanceof PayloadError ? e.message : String(e) };
    }
  }

  interface Props {
    lengthSec?: number | null;
    history?: { id: string; label: string }[];
  }
  let { lengthSec = null, history = [] }: Props = $props();

  let canvasEl = $state<HTMLCanvasElement>();
</script>

<div class="preview" data-region="preview-container">
  <button
    class="render"
    data-testid="preview-render"
    data-help={HELP.previewRender}
    data-blocked={blocked}
    title={blocked ?? ""}
    disabled={blocked !== null}
    onclick={onRender}>{label}</button>

  <select
    class="history"
    data-testid="preview-history"
    data-help={HELP.previewHistory}
    disabled
  >
    {#if history.length === 0}
      <option value="">no renders yet</option>
    {:else}
      {#each history as h (h.id)}
        <option value={h.id}>{h.label}</option>
      {/each}
    {/if}
  </select>

  <canvas class="wave" data-testid="preview-wave" bind:this={canvasEl} width="900" height="30"
  ></canvas>

  <button class="transport" data-testid="preview-play" aria-label="play the previewed render" disabled
    >▶</button>
  <span class="length" data-testid="preview-length"
    >{lengthSec === null ? "—" : `${lengthSec.toFixed(1)} s`}</span>

  <span
    class="handle"
    data-testid="preview-drag-handle"
    data-help={HELP.previewDragToLane}
    >⠿ drag to lane</span>

  <button
    class="action"
    data-testid="preview-use-settings"
    data-help={HELP.previewUseSettings}
    disabled>USE SETTINGS</button>
  <button
    class="action"
    data-testid="preview-replace-clip"
    data-help={HELP.previewReplaceClip}
    disabled>REPLACE CLIP</button>
</div>

<style>
  .preview {
    box-sizing: border-box;
    height: 44px;
    width: 100%;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 0 8px;
    background: var(--panel);
    border: 1px solid var(--border);
  }
  .render {
    background: var(--turq-strong);
    border: 1px solid var(--turq-strong);
    color: white;
    font-family: inherit;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.04em;
    padding: 5px 12px;
    flex-shrink: 0;
    cursor: pointer;
  }
  .render:disabled {
    background: var(--panel2);
    color: var(--turq-strong);
    cursor: default;
  }
  .history {
    background: var(--panel2);
    border: 1px solid var(--border);
    color: var(--text);
    font-family: inherit;
    font-size: 10px;
    padding: 3px 5px;
    max-width: 170px;
    flex-shrink: 0;
  }
  .wave {
    box-sizing: border-box;
    flex: 1;
    min-width: 0;
    height: 30px;
    display: block;
    border: 1px solid var(--border);
    background: var(--panel2);
  }
  .transport,
  .action {
    background: var(--panel2);
    border: 1px solid var(--border);
    color: var(--text-dim);
    font-family: inherit;
    font-size: 10px;
    padding: 4px 7px;
    flex-shrink: 0;
    cursor: pointer;
  }
  .transport:disabled,
  .action:disabled {
    cursor: default;
  }
  .length,
  .handle {
    font-size: 10px;
    color: var(--text-dim);
    flex-shrink: 0;
  }
  .handle {
    cursor: grab;
  }
</style>
