<script lang="ts">
  import { project } from "./store.svelte";
  import type { LaneId } from "./types";

  let pxPerSec = $state(80);
  let draggingClipId: string | null = $state(null);
  let dragGrabOffsetSec = 0;
  // $state so `bind:this` per lane doesn't trip Svelte's non-reactive-property warning.
  let laneEl = $state<Record<string, HTMLDivElement>>({});

  function secToPx(sec: number) {
    return sec * pxPerSec;
  }
  function pxToSec(px: number) {
    return Math.max(0, px / pxPerSec);
  }

  function onLaneClick(e: MouseEvent, laneId: LaneId) {
    if (draggingClipId) return; // was a drag, not a seek click
    const rect = (e.currentTarget as HTMLDivElement).getBoundingClientRect();
    project.seek(pxToSec(e.clientX - rect.left));
  }

  function onLaneKeydown(e: KeyboardEvent) {
    const step = e.shiftKey ? 5 : 1;
    if (e.key === "ArrowRight") {
      e.preventDefault();
      project.seek(project.playheadSec + step);
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      project.seek(project.playheadSec - step);
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      project.playing ? project.pause() : project.play();
    }
  }

  function onClipPointerDown(e: PointerEvent, clipId: string, laneId: LaneId) {
    e.stopPropagation();
    const clip = project.clips.find((c) => c.id === clipId);
    if (!clip) return;
    project.selectClip(clipId);
    draggingClipId = clipId;
    const rect = laneEl[laneId].getBoundingClientRect();
    dragGrabOffsetSec = pxToSec(e.clientX - rect.left) - clip.startSec;
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  }

  function onClipPointerMove(e: PointerEvent, laneId: LaneId) {
    if (!draggingClipId) return;
    const rect = laneEl[laneId].getBoundingClientRect();
    const newStart = pxToSec(e.clientX - rect.left) - dragGrabOffsetSec;
    project.moveClip(draggingClipId, newStart);
  }

  function onClipPointerUp() {
    // Defer clearing so the subsequent lane "click" event (which fires right
    // after pointerup) can see we were dragging and skip the seek-on-click.
    setTimeout(() => (draggingClipId = null), 0);
  }

  function onLaneDragOver(e: DragEvent) {
    e.preventDefault();
  }

  async function onLaneDrop(e: DragEvent, laneId: LaneId) {
    e.preventDefault();
    const rect = (e.currentTarget as HTMLDivElement).getBoundingClientRect();
    const startSec = pxToSec(e.clientX - rect.left);
    const cropId = e.dataTransfer?.getData("text/sa3-crop-id");
    if (cropId) {
      await project.addClipFromCrop(cropId, laneId, startSec);
      return;
    }
    const files = e.dataTransfer?.files;
    if (files?.length) {
      for (const file of Array.from(files)) {
        if (!file.type.startsWith("audio/")) continue;
        const durationSec = await probeDuration(file);
        project.addClipFromFile(file, laneId, startSec, durationSec);
      }
    }
  }

  function probeDuration(file: File): Promise<number> {
    return new Promise((resolve) => {
      const audioEl = document.createElement("audio");
      audioEl.src = URL.createObjectURL(file);
      audioEl.addEventListener("loadedmetadata", () => resolve(audioEl.duration || 4), { once: true });
      audioEl.addEventListener("error", () => resolve(4), { once: true });
    });
  }

  const rulerMarks = $derived.by(() => {
    const totalSec = Math.max(60, ...project.clips.map((c) => c.startSec + c.durationSec)) + 10;
    const marks: number[] = [];
    for (let t = 0; t <= totalSec; t += 5) marks.push(t);
    return marks;
  });
</script>

<div class="timeline">
  <div class="ruler" style="width: {secToPx(rulerMarks[rulerMarks.length - 1] ?? 60)}px">
    {#each rulerMarks as t}
      <div class="ruler-mark" style="left: {secToPx(t)}px">{t}s</div>
    {/each}
    <div class="playhead" style="left: {secToPx(project.playheadSec)}px"></div>
  </div>

  {#each project.lanes as lane (lane.id)}
    <div class="lane-row" style="border-left: 3px solid {lane.color}">
      <div class="lane-header">
        <span class="lane-chip" style="background: {lane.color}"></span>
        <span class="lane-label">{lane.label}</span>
        <button class:active={lane.muted} onclick={() => project.toggleMute(lane.id)} title="Mute">M</button>
        <button class:active={lane.solo} onclick={() => project.toggleSolo(lane.id)} title="Solo">S</button>
        <input
          type="range"
          min="0"
          max="1"
          step="0.01"
          value={lane.gain}
          oninput={(e) => project.setLaneGain(lane.id, +(e.target as HTMLInputElement).value)}
        />
      </div>
      <div
        class="lane-track"
        role="slider"
        aria-label="{lane.label} timeline -- click or press an arrow key to move the playhead"
        aria-valuenow={project.playheadSec}
        tabindex="0"
        bind:this={laneEl[lane.id]}
        style="width: {secToPx(rulerMarks[rulerMarks.length - 1] ?? 60)}px"
        onclick={(e) => onLaneClick(e, lane.id)}
        onkeydown={(e) => onLaneKeydown(e)}
        ondragover={onLaneDragOver}
        ondrop={(e) => onLaneDrop(e, lane.id)}
        onpointermove={(e) => onClipPointerMove(e, lane.id)}
        onpointerup={onClipPointerUp}
      >
        <div class="playhead" style="left: {secToPx(project.playheadSec)}px"></div>
        {#each project.clips.filter((c) => c.laneId === lane.id) as clip (clip.id)}
          <div
            class="clip"
            class:selected={project.selectedClipId === clip.id}
            class:stale={clip.latentState === "stale"}
            class:pending={!!clip.pendingJobId}
            style="left: {secToPx(clip.startSec)}px; width: {secToPx(clip.durationSec)}px; border-color: {lane.color}"
            role="button"
            tabindex="0"
            aria-pressed={project.selectedClipId === clip.id}
            onpointerdown={(e) => onClipPointerDown(e, clip.id, lane.id)}
            onkeydown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                project.selectClip(clip.id);
              }
            }}
          >
            <span class="clip-name">
              {clip.source.kind === "audio-file" ? clip.source.name : clip.source.kind === "crop" ? clip.source.cropId : clip.source.filename}
            </span>
            {#if clip.latentState !== "none"}
              <span class="latent-badge {clip.latentState}" title="latent state">{clip.latentState}</span>
            {/if}
          </div>
        {/each}
      </div>
    </div>
  {/each}
</div>

<style>
  .timeline {
    overflow-x: auto;
    background: var(--panel-bg);
    border: 1px solid var(--border);
    padding: 8px 0;
  }
  .ruler {
    position: relative;
    height: 24px;
    margin-left: 140px;
    border-bottom: 1px solid var(--border);
  }
  .ruler-mark {
    position: absolute;
    top: 0;
    font-size: 10px;
    color: var(--fg-dim);
    transform: translateX(-50%);
  }
  .lane-row {
    display: flex;
    align-items: stretch;
    border-bottom: 1px solid var(--border);
  }
  .lane-header {
    width: 140px;
    flex: 0 0 140px;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 5px 8px;
    background: var(--panel2);
  }
  .lane-chip {
    display: inline-block;
    width: 9px;
    height: 9px;
    flex-shrink: 0;
  }
  .lane-label {
    flex: 1;
    font-size: 11px;
    font-weight: 600;
    color: var(--fg);
  }
  .lane-header button {
    width: 18px;
    height: 18px;
    font-size: 10px;
    padding: 0;
    background: var(--panel-bg);
    border: 1px solid var(--border);
    color: var(--fg-dim);
    cursor: pointer;
  }
  .lane-header button.active {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--accent-fg);
  }
  .lane-header input[type="range"] {
    width: 36px;
    accent-color: var(--accent);
  }
  .lane-track {
    position: relative;
    height: 64px;
    background: var(--track-bg);
    cursor: pointer;
  }
  .playhead {
    position: absolute;
    top: 0;
    bottom: 0;
    width: 1px;
    background: var(--accent);
    pointer-events: none;
    z-index: 5;
  }
  .clip {
    position: absolute;
    top: 4px;
    bottom: 4px;
    background: var(--clip-bg);
    border: 1px solid var(--clip-border);
    overflow: hidden;
    cursor: grab;
    touch-action: none;
    display: flex;
    align-items: center;
    padding: 0 6px;
    gap: 6px;
  }
  .clip.selected {
    outline: 2px solid var(--accent);
    outline-offset: -1px;
  }
  .clip.stale {
    border-color: var(--warn) !important;
    border-style: dashed;
  }
  .clip.pending {
    opacity: 0.6;
  }
  .clip-name {
    font-size: 11px;
    color: var(--fg);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .latent-badge {
    font-size: 9px;
    padding: 1px 4px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    flex: 0 0 auto;
  }
  .latent-badge.valid {
    background: var(--ok);
    color: var(--ok-fg);
  }
  .latent-badge.stale {
    background: var(--warn);
    color: var(--warn-fg);
  }
</style>
