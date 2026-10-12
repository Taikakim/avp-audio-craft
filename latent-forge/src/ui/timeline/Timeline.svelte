<script lang="ts">
  import LaneCanvas from "./LaneCanvas.svelte";
  import LaneHeader from "./LaneHeader.svelte";
  import { SNAP_MODES, type SnapMode } from "../../lib/math/snap";
  import { project } from "../../lib/store.svelte";
  import { arrangement } from "../../lib/stores/arrangement.svelte";
  import { playback } from "../../lib/stores/transport.svelte";
  import { view } from "../../lib/stores/view.svelte";
  import { addClip } from "../../lib/clips/lifecycle";
  import { readForgeDrag } from "../../lib/math/laneHeader";
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

  // I1 fix wave: both branches used to call `arrangement.addClip` directly,
  // bypassing lib/clips/lifecycle.ts's upload -> analyze -> debounced-stretch
  // pipeline entirely (Task 10, built and tested, never actually wired in).
  // Consequence: native_bpm/downbeats_sec were always empty on every real
  // clip, which makes the downbeat glow, magnetic snap and both MATCH actions
  // inert even after C1's rewire. `addClip` here is lifecycle.ts's entry
  // point, not arrangement's method of the same name.
  async function onLaneBodyDrop(e: DragEvent, laneIndex: 0 | 1 | 2 | 3) {
    e.preventDefault();
    const el = e.currentTarget as HTMLElement;
    const rect = el.getBoundingClientRect();
    const atSec = pxToSec(e.clientX - rect.left, arrangement.scrollSec, arrangement.pxPerSec);
    const drag = readForgeDrag(e.dataTransfer ?? null);
    if (drag) {
      // M9 T10: the drag source's own length rides beside the ref (FORGE_DUR_MIME); a FILES row has
      // none, and lifecycle.addClip then decodes the audio for it instead of assuming 4 s.
      const { clip } = await addClip({
        lane: laneIndex, startSec: atSec, ref: drag.ref, durationSec: drag.durationSec ?? undefined,
      });
      view.select({ kind: "clip", id: clip.id });
      return;
    }
    const file = e.dataTransfer?.files?.[0];
    if (!file) return;
    const { clip } = await addClip({ lane: laneIndex, startSec: atSec, file });
    view.select({ kind: "clip", id: clip.id });
  }

  // ------------------------------------------------------------- top bar / scroller
  // C1 fix wave (2026-09-30): the header/SNAP/zoom row was still reading and
  // writing the v1 `project` store, which has held zero clips since Task 5 --
  // nothing downstream (grid/ruler/stretch/ClipBox snap) ever read it. Rewired
  // onto `arrangement`, the only store with real clip data. `project.lanes` is
  // still used below purely as a static id/color source for the lane loop --
  // it never gets clips, mute/solo, or gain from here, so leaving that alone
  // loses nothing.

  function onWheel(e: WheelEvent) {
    // Ctrl/⌘+wheel zooms around the pointer, like every DAW and map. Plain
    // wheel is left to the page so the timeline never traps scrolling.
    if (!(e.ctrlKey || e.metaKey)) return;
    e.preventDefault();
    arrangement.zoomBy(e.deltaY < 0 ? 1.15 : 1 / 1.15);
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
        value={arrangement.bpm}
        onchange={(e) => {
          // Commit once (Enter/blur), clamped to the input's own range: an
          // oninput handler rescaled every clip through each keystroke's
          // transient value ("1", "14", "140") and left a nonsense live BPM
          // if the field was cleared or abandoned mid-entry.
          const el = e.target as HTMLInputElement;
          const v = Math.min(300, Math.max(20, +el.value || arrangement.bpm));
          el.value = String(v);
          arrangement.setBpm(v);
        }}
      />
    </label>

    <label class="inline">
      SNAP
      <select
        data-testid="snap-select"
        value={arrangement.snap}
        onchange={(e) => arrangement.setSnap((e.target as HTMLSelectElement).value as SnapMode)}
      >
        {#each SNAP_MODES as m}
          <option value={m.value}>{m.label}</option>
        {/each}
      </select>
    </label>

    <button
      class="ghost"
      title="Meet at the mean of the clips' native tempos — least stretch for all of them. Needs a BPM set on at least one clip."
      onclick={() => arrangement.matchBpm()}>MATCH BPM</button
    >
    <button
      class="ghost purple"
      title="Shift every clip by the shortest path so its downbeat lands on the common phase. Needs a downbeat set on at least two clips."
      onclick={() => arrangement.matchDownbeats()}>MATCH DOWNBEATS</button
    >

    <span class="spacer"></span>
    <button class="ghost" onclick={() => arrangement.zoomBy(1 / 1.4)} aria-label="zoom out">−</button>
    <span class="zoom">{Math.round(arrangement.pxPerSec)} px/s</span>
    <button class="ghost" onclick={() => arrangement.zoomBy(1.4)} aria-label="zoom in">+</button>
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
