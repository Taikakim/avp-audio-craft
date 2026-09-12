<script lang="ts">
  import { project } from "./store.svelte";
  import { sourceLabel, type Clip } from "./types";
  import { drawPeaks, peaksFor } from "./waveform";

  interface Props {
    clip: Clip;
    laneColor: string;
    pxPerSec: number;
    onGrab: (e: PointerEvent, mode: "move" | "trim-start" | "trim-end") => void;
  }
  let { clip, laneColor, pxPerSec, onGrab }: Props = $props();

  let canvasEl = $state<HTMLCanvasElement>();
  let loadState = $state<"idle" | "loading" | "ready" | "error">("idle");
  let errorMsg = $state<string | null>(null);

  const widthPx = $derived(Math.max(2, clip.durationSec * pxPerSec));
  const label = $derived(
    clip.source.kind === "empty"
      ? clip.render.prompt.trim() || "empty — set a prompt, then RENDER"
      : sourceLabel(clip.source),
  );

  // Load the clip's audio, reduce it to peaks over exactly the trimmed span,
  // and draw. Re-runs on zoom (more columns) and on trim (different span).
  $effect(() => {
    const url = clip.previewUrl;
    const canvas = canvasEl;
    const cols = Math.round(widthPx);
    const from = clip.offsetSec;
    const to = clip.offsetSec + clip.durationSec;
    if (!url || !canvas) return;

    let cancelled = false;
    loadState = "loading";
    project.transport
      .preload(url)
      .then((buffer) => {
        if (cancelled || !canvasEl) return;
        // First decode is also when we learn the real length -- crop metadata
        // can be absent and a generate's duration is the requested one.
        if (clip.offsetSec === 0 && Math.abs(buffer.duration - clip.durationSec) > 0.05) {
          project.setClipDurationFromBuffer(clip.id, buffer.duration);
        }
        const peaks = peaksFor(url, buffer, cols, from, to);
        drawPeaks(canvasEl, peaks, laneColor);
        loadState = "ready";
        errorMsg = null;
      })
      .catch((e) => {
        if (cancelled) return;
        loadState = "error";
        errorMsg = e instanceof Error ? e.message : String(e);
      });
    return () => {
      cancelled = true;
    };
  });
</script>

<div
  class="clip"
  class:selected={project.selectedClipId === clip.id}
  class:stale={clip.latentState === "stale"}
  class:pending={!!clip.pendingJobId}
  class:empty={clip.source.kind === "empty"}
  style="left: {clip.startSec * pxPerSec}px; width: {widthPx}px; border-color: {laneColor}"
  role="button"
  tabindex="0"
  aria-pressed={project.selectedClipId === clip.id}
  onpointerdown={(e) => onGrab(e, "move")}
  onkeydown={(e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      project.selectClip(clip.id);
    }
  }}
>
  <canvas class="wave" bind:this={canvasEl}></canvas>

  <div class="overlay">
    <span class="name">{label}</span>
    {#if clip.latentState !== "none"}
      <span class="badge {clip.latentState}" title="latent validity at this offset">{clip.latentState}</span>
    {/if}
    {#if clip.pendingJobId}
      <span class="badge pending">rendering</span>
    {:else if loadState === "error"}
      <span class="badge error" title={errorMsg ?? ""}>no audio</span>
    {/if}
  </div>

  <!-- Trim handles. Separate pointer targets so a grab near the edge resizes
       rather than moving the whole clip. -->
  <div
    class="handle start"
    role="separator"
    aria-label="trim clip start"
    onpointerdown={(e) => {
      e.stopPropagation();
      onGrab(e, "trim-start");
    }}
  ></div>
  <div
    class="handle end"
    role="separator"
    aria-label="trim clip end"
    onpointerdown={(e) => {
      e.stopPropagation();
      onGrab(e, "trim-end");
    }}
  ></div>
</div>

<style>
  .clip {
    position: absolute;
    top: 3px;
    bottom: 3px;
    background: var(--clip-bg);
    border: 1px solid var(--clip-border);
    overflow: hidden;
    cursor: grab;
    touch-action: none;
  }
  .clip.selected {
    outline: 2px solid var(--accent);
    outline-offset: -1px;
  }
  .clip.stale {
    border-style: dashed;
  }
  .clip.pending {
    opacity: 0.65;
  }
  /* Nothing rendered into it yet -- reads as a slot, not as silent audio. */
  .clip.empty {
    background: transparent;
    border-style: dashed;
    opacity: 0.85;
  }
  .wave {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    display: block;
    opacity: 0.75;
    pointer-events: none;
  }
  .overlay {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: flex-start;
    gap: 4px;
    padding: 2px 4px;
    pointer-events: none;
  }
  .name {
    font-size: 10px;
    color: var(--fg);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    text-shadow: 0 0 3px var(--panel-bg);
  }
  .badge {
    font-size: 9px;
    padding: 0 3px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    flex: 0 0 auto;
  }
  .badge.valid {
    background: var(--ok);
    color: var(--ok-fg);
  }
  .badge.stale {
    background: var(--warn);
    color: var(--warn-fg);
  }
  .badge.pending {
    background: var(--accent);
    color: var(--accent-fg);
  }
  .badge.error {
    background: var(--red);
    color: var(--accent-fg);
  }
  .handle {
    position: absolute;
    top: 0;
    bottom: 0;
    width: 6px;
    cursor: ew-resize;
  }
  .handle.start {
    left: 0;
  }
  .handle.end {
    right: 0;
  }
  .clip:hover .handle {
    background: var(--accent);
    opacity: 0.5;
  }
</style>
