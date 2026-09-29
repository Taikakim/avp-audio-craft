<script lang="ts">
  import { arrangement } from "../../lib/stores/arrangement.svelte";
  import { view } from "../../lib/stores/view.svelte";
  import { overlapLabel } from "../../lib/math/overlaps";
  import { secToPx } from "../../lib/math/viewport";
  import type { Overlap } from "../../lib/stores/arrangement.svelte";

  interface Props {
    overlap: Overlap;
  }
  let { overlap }: Props = $props();

  const left = $derived(secToPx(overlap.start_sec, arrangement.scrollSec, arrangement.pxPerSec));
  const right = $derived(secToPx(overlap.end_sec, arrangement.scrollSec, arrangement.pxPerSec));
  const width = $derived(Math.max(1, right - left));
  const label = $derived(overlapLabel(overlap.start_sec, overlap.end_sec, arrangement.bpm, arrangement.beatsPerBar));
  const selected = $derived(view.selection.kind === "overlap" && view.selection.key === overlap.key);

  function select(e: PointerEvent) {
    if (e.button !== 0) return;
    e.stopPropagation(); // never also fire the lane body's own seek/select
    // Create this overlap's params HERE, in an event handler, before it becomes the render target:
    // `arrangement.settingsSource` never seeds (a $state write inside M4's $derived reads throws
    // state_unsafe_mutation), so an overlap that was never created would resolve to the session
    // defaults and PROMPT + SIGMA would edit the wrong object (reconcile pass 2026-09-25).
    arrangement.overlapParams(overlap.key);
    view.select({ kind: "overlap", key: overlap.key });
  }
</script>

<div
  class="overlap"
  class:selected
  style="left:{left}px;width:{width}px"
  role="button"
  tabindex="0"
  onpointerdown={select}
>
  <span class="label">{label}</span>
</div>

<style>
  .overlap {
    position: absolute;
    top: 0;
    bottom: 0;
    box-sizing: border-box;
    border-left: 1px solid var(--purple-strong);
    border-right: 1px solid var(--purple-strong);
    background: color-mix(in srgb, var(--purple-strong) 16%, transparent);
    display: flex;
    align-items: flex-end;
    justify-content: center;
    cursor: pointer;
    z-index: 3;
  }
  .overlap.selected {
    /* Global constraint: no shadows -- an inset outline gives the same ring
       (matches ClipBox's / the legacy ClipView.svelte's selection treatment)
       without one. */
    outline: 1px solid var(--purple-strong);
    outline-offset: -2px;
    background: color-mix(in srgb, var(--purple-strong) 30%, transparent);
  }
  .label {
    font-size: 9px;
    color: white;
    background: var(--purple-strong);
    padding: 0 3px;
  }
</style>
