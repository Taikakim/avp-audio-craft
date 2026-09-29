<script lang="ts">
  import { arrangement } from "../../lib/stores/arrangement.svelte";
  import { view } from "../../lib/stores/view.svelte";
  import { playback } from "../../lib/stores/transport.svelte";
  import { forgeApi } from "../../lib/forge/api";
  import { laneDownbeats } from "../../lib/math/downbeats";
  import type { SnapContext, SnapMode } from "../../lib/math/snap";
  import { snapDelta } from "../../lib/math/snap";
  import { bpmLabel, edgeHitTest, laneForDrag, SCORE_PLACEHOLDER, scrubOffsetSec } from "../../lib/math/clipBox";
  import { clipSpanPx, pxToSec } from "../../lib/math/viewport";
  import type { ForgeClip } from "../../lib/forge/types";

  const LANE_HEIGHT_PX = 62;

  interface Props {
    clip: ForgeClip;
  }
  let { clip }: Props = $props();

  const span = $derived(clipSpanPx(clip.start_sec, clip.dur_sec, arrangement.scrollSec, arrangement.pxPerSec));
  const selected = $derived(view.selection.kind === "clip" && view.selection.id === clip.id);
  const label = $derived(bpmLabel(clip, arrangement.bpm));
  const showBpmLabel = $derived(span.width > 150);
  const showLoop = $derived(span.width > 70);

  type Drag =
    | { mode: "move"; grabOffsetSec: number; startLane: 0 | 1 | 2 | 3; startY: number; wrapperLeftPx: number }
    | { mode: "trim-start" | "trim-end"; wrapperLeftPx: number }
    | { mode: "scrub" };
  let drag: Drag | null = null;

  function snapCtx(): SnapContext {
    const edges: number[] = [];
    for (const c of arrangement.clips) {
      if (c.id === clip.id) continue;
      edges.push(c.start_sec, c.start_sec + c.dur_sec);
    }
    const magnets = arrangement.lanes
      .filter((l) => l.index !== clip.lane)
      .flatMap((l) => laneDownbeats(arrangement.clips, l.index));
    return { bpm: arrangement.bpm, beatsPerBar: arrangement.beatsPerBar, pxPerSec: arrangement.pxPerSec, edges, magnets };
  }

  function onPointerDown(e: PointerEvent) {
    if (e.button !== 0) return;
    e.stopPropagation(); // never also fire the lane body's own seek/select
    view.select({ kind: "clip", id: clip.id });
    view.activeLane = clip.lane;
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    if (e.altKey) {
      drag = { mode: "scrub" };
      void playback.scrubClip(
        forgeApi.audioUrl(clip.audio),
        scrubOffsetSec(e.clientX, rect.left, rect.width, clip.offset_sec, clip.dur_sec),
      );
    } else {
      const wrapperLeftPx = rect.left - span.left; // the lane body's own left edge, held fixed for the drag
      const hit = edgeHitTest(e.clientX, rect.left, rect.width);
      if (hit === "body") {
        const pointerSec = pxToSec(e.clientX - wrapperLeftPx, arrangement.scrollSec, arrangement.pxPerSec);
        drag = {
          mode: "move", grabOffsetSec: pointerSec - clip.start_sec,
          startLane: clip.lane, startY: e.clientY, wrapperLeftPx,
        };
      } else {
        drag = { mode: hit === "start" ? "trim-start" : "trim-end", wrapperLeftPx };
      }
    }
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  }

  function onPointerMove(e: PointerEvent) {
    if (!drag) return;
    if (drag.mode === "scrub") {
      const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
      void playback.scrubClip(
        forgeApi.audioUrl(clip.audio),
        scrubOffsetSec(e.clientX, rect.left, rect.width, clip.offset_sec, clip.dur_sec),
      );
      return;
    }
    const pointerSec = pxToSec(e.clientX - drag.wrapperLeftPx, arrangement.scrollSec, arrangement.pxPerSec);
    const mode = arrangement.snap as SnapMode;
    if (drag.mode === "move") {
      const target = snapDelta(pointerSec - drag.grabOffsetSec, mode, snapCtx()).sec;
      arrangement.moveClip(clip.id, target);
      const newLane = laneForDrag(drag.startLane, e.clientY - drag.startY, LANE_HEIGHT_PX);
      if (newLane !== clip.lane) arrangement.moveClipToLane(clip.id, newLane);
    } else {
      const target = snapDelta(pointerSec, mode, snapCtx()).sec;
      arrangement.trimClip(clip.id, drag.mode === "trim-start" ? "start" : "end", target);
    }
  }

  function onPointerUp() {
    if (drag?.mode === "scrub") playback.stopScrub();
    drag = null;
  }
</script>

<div
  class="clip"
  class:selected
  style="left:{span.left}px;width:{span.width}px;border-color:var(--lane{clip.lane + 1})"
  role="button"
  tabindex="0"
  onpointerdown={onPointerDown}
  onpointermove={onPointerMove}
  onpointerup={onPointerUp}
>
  <div class="row">
    <span class="score">{SCORE_PLACEHOLDER}</span>
    {#if showLoop}
      <button
        class="loop"
        class:active={clip.loop}
        style="--lane-color: var(--lane{clip.lane + 1})"
        onclick={(e) => {
          e.stopPropagation();
          arrangement.setLoop(clip.id, !clip.loop);
        }}>LOOP</button
      >
    {/if}
    {#if showBpmLabel && label}
      <span class="bpm">{label}</span>
    {/if}
  </div>
  {#if clip.latentState === "stale"}
    <span class="stale" title="latent validity at this offset (spec §10 X13)">stale</span>
  {/if}
</div>

<style>
  .clip {
    position: absolute;
    top: 0;
    height: 100%;
    box-sizing: border-box;
    border: 1px solid;
    background: transparent;
    overflow: hidden;
    cursor: grab;
    touch-action: none;
    z-index: 2;
  }
  .clip.selected {
    /* Global constraint: no shadows -- an inset outline gives the same ring
       (matches the legacy ClipView.svelte selection treatment) without one. */
    outline: 1px solid currentColor;
    outline-offset: -2px;
  }
  .row {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 2px 3px;
    min-width: 0;
  }
  .score {
    flex-shrink: 0;
    font-size: 9px;
    padding: 0 3px;
    color: white;
    white-space: nowrap;
    background: var(--purple-strong);
  }
  .loop {
    flex-shrink: 0;
    font-size: 9px;
    padding: 1px 5px;
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text-dim);
    cursor: pointer;
    font-family: inherit;
  }
  .loop.active {
    background: var(--lane-color);
    border-color: var(--lane-color);
    color: white;
  }
  .bpm {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    font-size: 9px;
    color: var(--text);
    white-space: nowrap;
  }
  .stale {
    position: absolute;
    right: 2px;
    bottom: 2px;
    font-size: 9px;
    padding: 0 3px;
    background: var(--warm);
    color: white;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
</style>
