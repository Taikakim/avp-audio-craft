<script module lang="ts">
  // I4 fix wave: the drag gesture's state and its pointermove/pointerup
  // handlers live at MODULE scope (shared by every ClipBox instance, and
  // outliving any one of them), not as per-instance fields.
  //
  // Why: ClipBox is mounted inside a PER-LANE keyed {#each} (Timeline.svelte).
  // Dragging a clip across a lane boundary calls arrangement.moveClipToLane,
  // which removes the clip from the OLD lane's {#each} and adds it to the
  // NEW lane's -- Svelte destroys THIS component instance and mounts a fresh
  // one for that clip. A component-local `let drag` (or `setPointerCapture`
  // on this instance's own DOM element, which is destroyed right along with
  // it) resets/is lost on that remount, so the drag silently stops responding
  // after exactly one lane crossing (confirmed live -- the actual bug this
  // fix wave exists to close). Module state, and `window`-level listeners
  // added imperatively (not `setPointerCapture`), both survive the remount:
  // `window` is never unmounted, and the handlers below look the clip up
  // fresh from `arrangement.clips` by id on every event rather than closing
  // over a particular component instance's `clip` prop.
  import { arrangement } from "../../lib/stores/arrangement.svelte";
  import { playback } from "../../lib/stores/transport.svelte";
  import { forgeApi } from "../../lib/forge/api";
  import { laneDownbeats } from "../../lib/math/downbeats";
  import type { SnapContext, SnapMode } from "../../lib/math/snap";
  import { snapDelta } from "../../lib/math/snap";
  import { edgeHitTest, laneForDrag, scrubOffsetSec } from "../../lib/math/clipBox";
  import { pxToSec } from "../../lib/math/viewport";

  // Last-resort fallback only, when no ".lane-row" ancestor can be measured
  // (e.g. a unit-test harness with no real layout) -- the real number is
  // measured per-drag from the DOM in startDrag() below. The header row is
  // spec-UNCONSTRAINED in height (Global Constraint), so a hardcoded pitch is
  // wrong by construction the moment the header's content makes it taller
  // than the 62px canvas -- confirmed live at 83px, not 62.
  const FALLBACK_LANE_HEIGHT_PX = 62;

  type DragState =
    | {
        mode: "move"; grabOffsetSec: number; startLane: 0 | 1 | 2 | 3; startY: number;
        wrapperLeftPx: number; laneHeightPx: number;
      }
    | { mode: "trim-start" | "trim-end"; wrapperLeftPx: number }
    | { mode: "scrub"; boxEl: HTMLElement };

  let activeDrag: { clipId: string; state: DragState } | null = null;

  function snapCtxFor(clipId: string): SnapContext {
    const clip = arrangement.clips.find((c) => c.id === clipId);
    const edges: number[] = [];
    for (const c of arrangement.clips) {
      if (c.id === clipId) continue;
      edges.push(c.start_sec, c.start_sec + c.dur_sec);
    }
    const magnets = arrangement.lanes
      .filter((l) => l.index !== clip?.lane)
      .flatMap((l) => laneDownbeats(arrangement.clips, l.index, arrangement.bpm));
    return { bpm: arrangement.bpm, beatsPerBar: arrangement.beatsPerBar, pxPerSec: arrangement.pxPerSec, edges, magnets };
  }

  /** Called from a ClipBox instance's own onPointerDown -- the only point in
   *  the gesture where we still need that instance's specific DOM element. */
  function startDrag(clipId: string, e: PointerEvent, boxEl: HTMLElement, wrapperLeftPx: number) {
    const clip = arrangement.clips.find((c) => c.id === clipId);
    if (!clip) return;
    if (e.altKey) {
      activeDrag = { clipId, state: { mode: "scrub", boxEl } };
      // I2 fix wave: scrub the stretched preview once one exists -- offset_sec/
      // dur_sec are already in that STRETCHED timeline domain (spec §7.3), so
      // they only line up correctly against previewAudio, not the raw source.
      const rect = boxEl.getBoundingClientRect();
      void playback.scrubClip(
        forgeApi.audioUrl(clip.previewAudio ?? clip.audio),
        scrubOffsetSec(e.clientX, rect.left, rect.width, clip.offset_sec, clip.dur_sec),
      );
      return;
    }
    const rect = boxEl.getBoundingClientRect();
    const hit = edgeHitTest(e.clientX, rect.left, rect.width);
    if (hit === "body") {
      const pointerSec = pxToSec(e.clientX - wrapperLeftPx, arrangement.scrollSec, arrangement.pxPerSec);
      // I4 fix wave: measure the REAL row pitch from the DOM -- the header's
      // height is unconstrained, so ".lane-row"'s rendered height (header +
      // canvas) is the true vertical distance between lanes, not the
      // canvas's own fixed 62px. Captured once per drag; row heights don't
      // change mid-gesture.
      const laneRowEl = boxEl.closest(".lane-row") as HTMLElement | null;
      const laneHeightPx = laneRowEl?.getBoundingClientRect().height || FALLBACK_LANE_HEIGHT_PX;
      activeDrag = {
        clipId,
        state: {
          mode: "move", grabOffsetSec: pointerSec - clip.start_sec,
          startLane: clip.lane, startY: e.clientY, wrapperLeftPx, laneHeightPx,
        },
      };
    } else {
      activeDrag = { clipId, state: { mode: hit === "start" ? "trim-start" : "trim-end", wrapperLeftPx } };
    }
  }

  function onWindowPointerMove(e: PointerEvent) {
    if (!activeDrag) return;
    const { clipId, state } = activeDrag;
    const clip = arrangement.clips.find((c) => c.id === clipId);
    if (!clip) {
      stopDrag();
      return;
    }
    if (state.mode === "scrub") {
      const rect = state.boxEl.getBoundingClientRect();
      void playback.scrubClip(
        forgeApi.audioUrl(clip.previewAudio ?? clip.audio),
        scrubOffsetSec(e.clientX, rect.left, rect.width, clip.offset_sec, clip.dur_sec),
      );
      return;
    }
    const pointerSec = pxToSec(e.clientX - state.wrapperLeftPx, arrangement.scrollSec, arrangement.pxPerSec);
    const mode = arrangement.snap as SnapMode;
    if (state.mode === "move") {
      const target = snapDelta(pointerSec - state.grabOffsetSec, mode, snapCtxFor(clipId)).sec;
      arrangement.moveClip(clipId, target);
      const newLane = laneForDrag(state.startLane, e.clientY - state.startY, state.laneHeightPx);
      if (newLane !== clip.lane) arrangement.moveClipToLane(clipId, newLane);
    } else {
      const target = snapDelta(pointerSec, mode, snapCtxFor(clipId)).sec;
      arrangement.trimClip(clipId, state.mode === "trim-start" ? "start" : "end", target);
    }
  }

  function onWindowPointerUp() {
    if (activeDrag?.state.mode === "scrub") playback.stopScrub();
    stopDrag();
  }

  // A cancelled pointer (touch/pen, OS stealing the gesture) never sends
  // pointerup; without this the drag stays live with no button held.
  const onWindowPointerCancel = onWindowPointerUp;

  function stopDrag() {
    activeDrag = null;
    window.removeEventListener("pointermove", onWindowPointerMove);
    window.removeEventListener("pointerup", onWindowPointerUp);
    window.removeEventListener("pointercancel", onWindowPointerCancel);
  }
</script>

<script lang="ts">
  import { view } from "../../lib/stores/view.svelte";
  import { bpmLabel } from "../../lib/math/clipBox";
  import { chromaLink, clipScoreLabel } from "../../lib/chroma/chromaLink.svelte";
  import { clipSpanPx } from "../../lib/math/viewport";
  import type { ForgeClip } from "../../lib/forge/types";

  interface Props {
    clip: ForgeClip;
  }
  let { clip }: Props = $props();

  const span = $derived(clipSpanPx(clip.start_sec, clip.dur_sec, arrangement.scrollSec, arrangement.pxPerSec));
  const selected = $derived(view.selection.kind === "clip" && view.selection.id === clip.id);
  const label = $derived(bpmLabel(clip, arrangement.bpm));
  const showBpmLabel = $derived(span.width > 150);
  const showLoop = $derived(span.width > 70);

  function onPointerDown(e: PointerEvent) {
    if (e.button !== 0) return;
    e.stopPropagation(); // never also fire the lane body's own seek/select
    view.select({ kind: "clip", id: clip.id });
    view.activeLane = clip.lane;
    const boxEl = e.currentTarget as HTMLElement;
    const rect = boxEl.getBoundingClientRect();
    const wrapperLeftPx = rect.left - span.left; // the lane body's own left edge, held fixed for the drag
    startDrag(clip.id, e, boxEl, wrapperLeftPx);
    // I4 fix wave: window-level listeners, not setPointerCapture on this
    // element. Capture ties future events to THIS element; once it's removed
    // from the DOM (a lane-crossing remount) capture is implicitly released
    // and there is no element left to resume it on. `window` never unmounts,
    // so listening there survives the remount regardless of which ClipBox
    // instance (if any) is currently mounted for this clip.
    window.addEventListener("pointermove", onWindowPointerMove);
    window.addEventListener("pointerup", onWindowPointerUp);
    window.addEventListener("pointercancel", onWindowPointerCancel);
  }
</script>

<div
  class="clip"
  class:selected
  style="left:{span.left}px;width:{span.width}px;border-color:var(--lane{clip.lane + 1})"
  role="button"
  tabindex="0"
  onpointerdown={onPointerDown}
>
  <div class="row">
    <span class="score" data-testid="clip-score">{clipScoreLabel(chromaLink.scores[clip.id])}</span>
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
