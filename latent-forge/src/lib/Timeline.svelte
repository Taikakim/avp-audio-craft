<script lang="ts">
  import ClipView from "./ClipView.svelte";
  import { gridLines, LATENT_FPS, secPerBar, SNAP_MODES } from "./musictime";
  import { project } from "./store.svelte";
  import type { LaneId } from "./types";

  const LANE_HEADER_PX = 150;

  let laneEl = $state<Record<string, HTMLDivElement>>({});
  let rulerEl = $state<HTMLCanvasElement>();
  let gridEl = $state<Record<string, HTMLCanvasElement>>({});

  type DragMode = "move" | "trim-start" | "trim-end";
  let drag: { clipId: string; mode: DragMode; grabOffsetSec: number; moved: boolean } | null = null;

  const contentSec = $derived(Math.max(60, project.arrangementEndSec + 20));
  const contentPx = $derived(contentSec * project.pxPerSec);

  function pxToSec(px: number) {
    return Math.max(0, px / project.pxPerSec);
  }

  function secAtClientX(clientX: number, laneId: LaneId): number {
    const rect = laneEl[laneId].getBoundingClientRect();
    return pxToSec(clientX - rect.left);
  }

  // ------------------------------------------------------------- ruler + grid

  function cssVar(name: string, el: HTMLElement): string {
    return getComputedStyle(el).getPropertyValue(name).trim();
  }

  function fitCanvas(canvas: HTMLCanvasElement): CanvasRenderingContext2D | null {
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    if (w <= 0 || h <= 0) return null;
    if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
    }
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    return ctx;
  }

  // Ruler: bars/beats from the project meter, seconds, and the latent frame
  // clock (10.767 Hz). The latent row is informational -- placement is NOT
  // quantised to it (ORIENTATION.md §3) -- but it shows where a commit-time
  // encode will land.
  $effect(() => {
    const canvas = rulerEl;
    const pxPerSec = project.pxPerSec;
    const meter = project.meter;
    void contentPx;
    if (!canvas) return;
    const ctx = fitCanvas(canvas);
    if (!ctx) return;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    const dim = cssVar("--fg-dim", canvas);
    const fg = cssVar("--fg", canvas);
    const accent = cssVar("--accent", canvas);

    ctx.font = "9px 'Space Grotesk', ui-monospace, monospace";
    ctx.textBaseline = "top";

    // Bars
    const bar = secPerBar(meter);
    if (bar * pxPerSec > 22) {
      ctx.strokeStyle = dim;
      ctx.fillStyle = fg;
      for (let i = 0, t = 0; t * pxPerSec < w; i++, t = i * bar) {
        const x = Math.round(t * pxPerSec) + 0.5;
        ctx.globalAlpha = 0.6;
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, 8);
        ctx.stroke();
        ctx.globalAlpha = 1;
        ctx.fillText(String(i + 1), x + 2, 0);
      }
    }

    // Seconds
    const secStep = pxPerSec > 40 ? 1 : pxPerSec > 12 ? 5 : 15;
    ctx.fillStyle = dim;
    for (let t = 0; t * pxPerSec < w; t += secStep) {
      ctx.fillText(`${t}s`, Math.round(t * pxPerSec) + 2, 11);
    }

    // Latent frames -- only once they are far enough apart to read.
    const framePx = pxPerSec / LATENT_FPS;
    if (framePx > 5) {
      ctx.strokeStyle = accent;
      ctx.globalAlpha = 0.45;
      ctx.beginPath();
      for (let f = 0; (f / LATENT_FPS) * pxPerSec < w; f++) {
        const x = Math.round((f / LATENT_FPS) * pxPerSec) + 0.5;
        ctx.moveTo(x, h - (f % 10 === 0 ? 7 : 4));
        ctx.lineTo(x, h);
      }
      ctx.stroke();
      ctx.globalAlpha = 1;
    }
  });

  // Per-lane background grid.
  $effect(() => {
    const pxPerSec = project.pxPerSec;
    const meter = project.meter;
    void contentPx;
    for (const lane of project.lanes) {
      const canvas = gridEl[lane.id];
      if (!canvas) continue;
      const ctx = fitCanvas(canvas);
      if (!ctx) continue;
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      const border = cssVar("--border", canvas);
      for (const line of gridLines(0, w / pxPerSec, meter, pxPerSec)) {
        const x = Math.round(line.sec * pxPerSec) + 0.5;
        ctx.strokeStyle = border;
        ctx.globalAlpha = line.kind === "bar" ? 0.9 : line.kind === "beat" ? 0.45 : 0.2;
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, h);
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
    }
  });

  // ------------------------------------------------------------- interaction

  function onLaneClick(e: MouseEvent, laneId: LaneId) {
    if (drag?.moved) return; // finished a drag, not a seek click
    project.seek(secAtClientX(e.clientX, laneId));
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
      project.togglePlay();
    }
  }

  function onGrab(e: PointerEvent, clipId: string, laneId: LaneId, mode: DragMode) {
    const clip = project.clips.find((c) => c.id === clipId);
    if (!clip) return;
    project.selectClip(clipId);
    drag = { clipId, mode, grabOffsetSec: secAtClientX(e.clientX, laneId) - clip.startSec, moved: false };
    (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
  }

  function onLanePointerMove(e: PointerEvent, laneId: LaneId) {
    if (!drag) return;
    const at = secAtClientX(e.clientX, laneId);
    drag.moved = true;
    if (drag.mode === "move") {
      project.moveClip(drag.clipId, at - drag.grabOffsetSec, !e.altKey);
      const clip = project.clips.find((c) => c.id === drag!.clipId);
      if (clip && clip.laneId !== laneId) project.moveClipToLane(drag.clipId, laneId);
    } else {
      project.trimClip(drag.clipId, drag.mode === "trim-start" ? "start" : "end", at);
    }
  }

  function onLanePointerUp() {
    // Defer so the click handler that fires right after can see `moved`.
    const finished = drag;
    setTimeout(() => {
      if (drag === finished) drag = null;
    }, 0);
  }

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
    <div class="ruler-row">
      <div class="ruler-gutter"></div>
      <canvas class="ruler" bind:this={rulerEl} style="width: {contentPx}px"></canvas>
    </div>

    {#each project.lanes as lane (lane.id)}
      <div class="lane-row" style="border-left: 3px solid {lane.color}">
        <div class="lane-header">
          <span class="lane-chip" style="background: {lane.color}"></span>
          <span class="lane-label">{lane.label}</span>
          <span class="lane-count">{project.clips.filter((c) => c.laneId === lane.id).length}</span>
          <button class:active={lane.muted} onclick={() => project.toggleMute(lane.id)} title="Mute">M</button>
          <button class:active={lane.solo} onclick={() => project.toggleSolo(lane.id)} title="Solo">S</button>
          <input
            type="range"
            min="0"
            max="1"
            step="0.01"
            value={lane.gain}
            oninput={(e) => project.setLaneGain(lane.id, +(e.target as HTMLInputElement).value)}
            title="preview gain (audio-domain only — never sent to the server)"
          />
        </div>
        <div
          class="lane-track"
          role="slider"
          aria-label="{lane.label} lane — click to move the playhead, drop audio or a crop to add a clip"
          aria-valuenow={project.playheadSec}
          tabindex="0"
          bind:this={laneEl[lane.id]}
          style="width: {contentPx}px"
          onclick={(e) => onLaneClick(e, lane.id)}
          ondblclick={(e) => project.addEmptyClip(lane.id, secAtClientX(e.clientX, lane.id))}
          onkeydown={onLaneKeydown}
          ondragover={(e) => e.preventDefault()}
          ondrop={async (e) => {
            e.preventDefault();
            const startSec = secAtClientX(e.clientX, lane.id);
            const cropId = e.dataTransfer?.getData("text/sa3-crop-id");
            if (cropId) {
              await project.addClipFromCrop(cropId, lane.id, startSec);
              return;
            }
            for (const file of Array.from(e.dataTransfer?.files ?? [])) {
              if (!file.type.startsWith("audio/")) continue;
              // Length is corrected as soon as the buffer decodes; this is just
              // a placeholder so the clip has a box to draw in.
              project.addClipFromFile(file, lane.id, startSec, 8);
            }
          }}
          onpointermove={(e) => onLanePointerMove(e, lane.id)}
          onpointerup={onLanePointerUp}
        >
          <canvas class="grid" bind:this={gridEl[lane.id]} style="width: {contentPx}px"></canvas>
          <div class="playhead" style="left: {project.playheadSec * project.pxPerSec}px"></div>
          {#each project.clips.filter((c) => c.laneId === lane.id) as clip (clip.id)}
            <ClipView
              {clip}
              laneColor={lane.color}
              pxPerSec={project.pxPerSec}
              onGrab={(e, mode) => onGrab(e, clip.id, lane.id, mode)}
            />
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
  .ruler-row {
    display: flex;
    align-items: stretch;
    border-bottom: 1px solid var(--border);
  }
  .ruler-gutter {
    width: 150px;
    flex: 0 0 150px;
    border-right: 1px solid var(--border);
  }
  .ruler {
    height: 30px;
    display: block;
  }
  .lane-row {
    display: flex;
    align-items: stretch;
    border-bottom: 1px solid var(--border);
  }
  .lane-header {
    width: 150px;
    flex: 0 0 150px;
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 5px 8px;
    background: var(--panel2);
    border-right: 1px solid var(--border);
    position: sticky;
    left: 0;
    z-index: 6;
  }
  .lane-chip {
    display: inline-block;
    width: 9px;
    height: 9px;
    flex-shrink: 0;
  }
  .lane-label {
    font-size: 11px;
    font-weight: 600;
    color: var(--fg);
  }
  .lane-count {
    font-size: 9px;
    color: var(--fg-dim);
    margin-right: auto;
  }
  .lane-header button {
    width: 17px;
    height: 17px;
    font-size: 9px;
    padding: 0;
    background: var(--panel-bg);
    border: 1px solid var(--border);
    color: var(--fg-dim);
    cursor: pointer;
    font-family: inherit;
  }
  .lane-header button.active {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--accent-fg);
  }
  .lane-header input[type="range"] {
    width: 100%;
    accent-color: var(--accent);
  }
  .lane-track {
    position: relative;
    height: 68px;
    background: var(--track-bg);
    cursor: pointer;
  }
  .grid {
    position: absolute;
    inset: 0;
    height: 100%;
    display: block;
    pointer-events: none;
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
</style>
