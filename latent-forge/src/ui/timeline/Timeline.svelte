<script lang="ts">
  import LaneCanvas from "./LaneCanvas.svelte";
  import LaneHeader from "./LaneHeader.svelte";
  import { SNAP_MODES } from "../../lib/musictime";
  import { project } from "../../lib/store.svelte";
  import { arrangement } from "../../lib/stores/arrangement.svelte";
  import { playback } from "../../lib/stores/transport.svelte";
  import { view } from "../../lib/stores/view.svelte";
  import { forgeApi } from "../../lib/forge/api";
  import { parseForgeRefPayload } from "../../lib/math/laneHeader";
  import { middleDragScrollDeltaSec, middleDragZoomFactor } from "../../lib/math/ruler";
  import { pxToSec } from "../../lib/math/viewport";
  import { LANE_IDS } from "../../lib/types";
  import ClipBox from "./ClipBox.svelte";
  import OverlapBox from "./OverlapBox.svelte";
  import Ruler from "./Ruler.svelte";

  // ------------------------------------------------------------- lane body

  let laneBodyEl = $state<Record<number, HTMLDivElement>>({});
  type LaneDrag =
    | { mode: "seek" }
    | { mode: "zoom"; startX: number; startY: number; startPxPerSec: number; startScrollSec: number };
  let laneDrag: LaneDrag | null = null;

  function onLaneBodyPointerDown(e: PointerEvent, laneIndex: 0 | 1 | 2 | 3) {
    const el = e.currentTarget as HTMLElement;
    if (e.button === 1) {
      e.preventDefault();
      laneDrag = {
        mode: "zoom",
        startX: e.clientX,
        startY: e.clientY,
        startPxPerSec: arrangement.pxPerSec,
        startScrollSec: arrangement.scrollSec,
      };
      el.setPointerCapture(e.pointerId);
      return;
    }
    if (e.button !== 0) return;
    // ClipBox/OverlapBox (Tasks 6/7) stopPropagation their own pointerdown,
    // so reaching here means the click landed on bare canvas.
    view.activeLane = laneIndex;
    const rect = el.getBoundingClientRect();
    void playback.seek(pxToSec(e.clientX - rect.left, arrangement.scrollSec, arrangement.pxPerSec));
    laneDrag = { mode: "seek" };
    el.setPointerCapture(e.pointerId);
  }

  function onLaneBodyPointerMove(e: PointerEvent) {
    if (!laneDrag) return;
    const el = e.currentTarget as HTMLElement;
    const rect = el.getBoundingClientRect();
    if (laneDrag.mode === "zoom") {
      const targetPxPerSec = laneDrag.startPxPerSec * middleDragZoomFactor(e.clientY - laneDrag.startY);
      arrangement.zoomBy(targetPxPerSec / arrangement.pxPerSec);
      arrangement.setScrollSec(
        laneDrag.startScrollSec + middleDragScrollDeltaSec(e.clientX - laneDrag.startX, laneDrag.startPxPerSec),
      );
      return;
    }
    void playback.seek(pxToSec(e.clientX - rect.left, arrangement.scrollSec, arrangement.pxPerSec));
  }

  function onLaneBodyWheel(e: WheelEvent) {
    if (!e.shiftKey) return;
    e.preventDefault();
    arrangement.setScrollSec(arrangement.scrollSec + e.deltaY / arrangement.pxPerSec);
  }

  async function onLaneBodyDrop(e: DragEvent, laneIndex: 0 | 1 | 2 | 3) {
    e.preventDefault();
    const el = e.currentTarget as HTMLElement;
    const rect = el.getBoundingClientRect();
    const atSec = pxToSec(e.clientX - rect.left, arrangement.scrollSec, arrangement.pxPerSec);
    const raw = e.dataTransfer?.getData("application/x-forge-ref");
    const ref = raw ? parseForgeRefPayload(raw) : null;
    if (ref) {
      const c = arrangement.addClip({ lane: laneIndex, startSec: atSec, durSec: 4, audio: ref });
      view.select({ kind: "clip", id: c.id });
      return;
    }
    const file = e.dataTransfer?.files?.[0];
    if (!file) return;
    const uploaded = await forgeApi.upload(file);
    const c = arrangement.addClip({
      lane: laneIndex,
      startSec: atSec,
      durSec: uploaded.duration_sec,
      audio: uploaded.ref,
    });
    view.select({ kind: "clip", id: c.id });
  }

  // ------------------------------------------------------------- top bar / scroller
  // (Still driven by the v1 `project` store -- BPM/SNAP/MATCH/zoom-readout
  // migration off `project` is not in this task's file scope, only the lane
  // body wrapper is. See the task report for what remains.)

  function onWheel(e: WheelEvent) {
    // Ctrl/⌘+wheel zooms around the pointer, like every DAW and map. Plain
    // wheel is left to the page so the timeline never traps scrolling.
    if (!(e.ctrlKey || e.metaKey)) return;
    e.preventDefault();
    project.zoomBy(e.deltaY < 0 ? 1.15 : 1 / 1.15);
  }
</script>

<div class="timeline">
  <div class="tl-header">
    <span class="section-label">Timeline</span>

    <label class="inline">
      BPM
      <input
        type="number"
        step="0.1"
        min="20"
        max="300"
        value={project.meter.bpm}
        oninput={(e) => (project.meter = { ...project.meter, bpm: +(e.target as HTMLInputElement).value || 120 })}
      />
    </label>

    <label class="inline">
      SNAP
      <select value={project.snap} onchange={(e) => (project.snap = (e.target as HTMLSelectElement).value as typeof project.snap)}>
        {#each SNAP_MODES as m}
          <option value={m.value}>{m.label}</option>
        {/each}
      </select>
    </label>

    <button
      class="ghost"
      title="Meet at the mean of the clips' native tempos — least stretch for all of them. Needs a BPM set on at least one clip."
      onclick={() => project.matchBpm()}>MATCH BPM</button
    >
    <button
      class="ghost purple"
      title="Shift every clip by the shortest path so its downbeat lands on the common phase. Needs a downbeat set on at least two clips."
      onclick={() => project.matchDownbeats()}>MATCH DOWNBEATS</button
    >

    <span class="spacer"></span>
    <button class="ghost" onclick={() => project.zoomBy(1 / 1.4)} aria-label="zoom out">−</button>
    <span class="zoom">{Math.round(project.pxPerSec)} px/s</span>
    <button class="ghost" onclick={() => project.zoomBy(1.4)} aria-label="zoom in">+</button>
  </div>

  <div class="scroller" onwheel={onWheel}>
    <Ruler />

    {#each project.lanes as lane (lane.id)}
      {@const aLane = arrangement.lanes[LANE_IDS.indexOf(lane.id)]}
      <div class="lane-row" style="border-left: 3px solid {lane.color}">
        <LaneHeader lane={aLane} />
        <div
          class="lane-body"
          bind:this={laneBodyEl[aLane.index]}
          onpointerdown={(e) => onLaneBodyPointerDown(e, aLane.index)}
          onpointermove={(e) => onLaneBodyPointerMove(e)}
          onpointerup={() => (laneDrag = null)}
          onwheel={onLaneBodyWheel}
          ondragover={(e) => e.preventDefault()}
          ondrop={(e) => onLaneBodyDrop(e, aLane.index)}
        >
          <LaneCanvas lane={aLane} />
          {#each arrangement.clips.filter((c) => c.lane === aLane.index) as clip (clip.id)}
            <ClipBox {clip} />
          {/each}
          {#each arrangement.overlaps.filter((o) => o.lane === aLane.index) as overlap (overlap.key)}
            <OverlapBox {overlap} />
          {/each}
        </div>
      </div>
    {/each}
  </div>
</div>

<style>
  .timeline {
    background: var(--panel-bg);
    border: 1px solid var(--border);
    min-width: 0;
  }
  .tl-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 5px 8px;
    background: var(--panel2);
    border-bottom: 1px solid var(--border);
    flex-wrap: wrap;
  }
  .section-label {
    font-size: 10px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--fg-dim);
  }
  .inline {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 10px;
    letter-spacing: 0.05em;
    color: var(--fg-dim);
  }
  .inline input,
  .inline select {
    background: var(--panel-bg);
    border: 1px solid var(--border);
    color: var(--fg);
    font-family: inherit;
    font-size: 11px;
    padding: 2px 4px;
  }
  .inline input {
    width: 56px;
  }
  button.ghost {
    background: var(--panel-bg);
    border: 1px solid var(--accent);
    color: var(--accent);
    font-family: inherit;
    font-size: 10px;
    letter-spacing: 0.04em;
    padding: 3px 8px;
    cursor: pointer;
  }
  button.ghost.purple {
    border-color: var(--purple);
    color: var(--purple);
  }
  .spacer {
    flex: 1;
  }
  .zoom {
    font-size: 10px;
    color: var(--accent);
    min-width: 54px;
    text-align: center;
  }
  .scroller {
    overflow-x: auto;
    overflow-y: hidden;
  }
  .lane-row {
    display: flex;
    align-items: stretch;
    border-bottom: 1px solid var(--border);
  }
  .lane-body {
    position: relative;
    flex: 1;
    min-width: 0;
    height: 62px;
    overflow: hidden;
    touch-action: none;
    cursor: crosshair;
  }
</style>
