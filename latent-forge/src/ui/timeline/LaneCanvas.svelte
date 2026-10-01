<script lang="ts">
  // Spec 4.3 / File Structure: waveform ink, grid, downbeat markers, clip
  // marks -- one canvas per LANE, not per clip (unlike v1's ClipView), so
  // the overlap region's ink can be redarkened in a single second pass
  // rather than layering per-clip canvases. ClipBox (Task 6) draws no
  // waveform of its own; it only carries label chrome on top of this.
  import { arrangement } from "../../lib/stores/arrangement.svelte";
  import { playback } from "../../lib/stores/transport.svelte";
  import { view } from "../../lib/stores/view.svelte";
  import { forgeApi } from "../../lib/forge/api";
  import { coincidence, downbeatColor, laneDownbeats } from "../../lib/math/downbeats";
  import { darkenInk, isClipping, overlapSpansInLane } from "../../lib/math/laneCanvas";
  import { clipSpanPx, secToPx } from "../../lib/math/viewport";
  import { chromaLink, markerSecFor } from "../../lib/chroma/chromaLink.svelte";
  // I3 fix wave: was lib/musictime.ts's gridLines (retired there) -- this is
  // the canonical copy, built on this module's own gridIntervalSec.
  import { gridLines } from "../../lib/math/snap";
  import type { Peaks } from "../../lib/audio/waveform";
  import { peaksFor } from "../../lib/audio/waveform";
  import type { ForgeLane } from "../../lib/forge/types";

  interface Props {
    lane: ForgeLane;
  }
  let { lane }: Props = $props();

  let canvasEl = $state<HTMLCanvasElement>();
  const bufferCache = new Map<string, AudioBuffer>();

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

  /**
   * Paints peaks for x in [drawFrom, drawTo), mapping columns against the
   * CLIP's own [refLeft, refLeft+refWidth) -- so a darkened overlap redraw
   * of a sub-range still samples the right columns.
   */
  function paintPeaks(
    ctx: CanvasRenderingContext2D,
    drawFrom: number,
    drawTo: number,
    refLeft: number,
    refWidth: number,
    h: number,
    color: string,
    peaks: Peaks,
  ) {
    const mid = h / 2;
    ctx.fillStyle = color;
    const x0 = Math.max(0, Math.floor(drawFrom));
    const x1 = Math.max(x0, Math.ceil(drawTo));
    for (let x = x0; x < x1; x++) {
      const frac = (x - refLeft) / Math.max(1, refWidth);
      const i = Math.min(peaks.columns - 1, Math.max(0, Math.floor(frac * peaks.columns)));
      const lo = peaks.data[i * 2];
      const hi = peaks.data[i * 2 + 1];
      const yTop = mid - hi * mid * 0.9;
      ctx.fillRect(x, yTop, 1, Math.max(1, (hi - lo) * mid * 0.9));
    }
  }

  function paintClipMarks(
    ctx: CanvasRenderingContext2D,
    left: number,
    width: number,
    h: number,
    color: string,
    peaks: Peaks,
  ) {
    const x0 = Math.max(0, Math.floor(left));
    const x1 = Math.max(x0, Math.ceil(left + width));
    ctx.fillStyle = color;
    for (let x = x0; x < x1; x++) {
      const frac = (x - left) / Math.max(1, width);
      const i = Math.min(peaks.columns - 1, Math.max(0, Math.floor(frac * peaks.columns)));
      if (isClipping(peaks.data[i * 2], peaks.data[i * 2 + 1])) {
        ctx.fillRect(x, 0, 1, 2);
        ctx.fillRect(x, h - 2, 1, 2);
      }
    }
  }

  function redraw() {
    const canvas = canvasEl;
    if (!canvas) return;
    const ctx = fitCanvas(canvas);
    if (!ctx) return;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    const scrollSec = arrangement.scrollSec;
    const pxPerSec = arrangement.pxPerSec;
    const bg = cssVar("--panel2", canvas);
    const border = cssVar("--border", canvas);
    const laneColor = cssVar(`--lane${lane.index + 1}`, canvas);
    const red = cssVar("--red", canvas);

    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, w, h);

    for (const line of gridLines(scrollSec, scrollSec + w / pxPerSec, arrangement.bpm, arrangement.beatsPerBar, pxPerSec)) {
      const x = Math.round(secToPx(line.sec, scrollSec, pxPerSec)) + 0.5;
      ctx.strokeStyle = border;
      ctx.globalAlpha = line.kind === "bar" ? 0.9 : line.kind === "beat" ? 0.45 : 0.2;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;

    const laneClips = arrangement.clips.filter((c) => c.lane === lane.index);
    const overlapSpans = overlapSpansInLane(arrangement.overlaps, lane.index);
    const darkColor = darkenInk(laneColor, 0.75);

    for (const clip of laneClips) {
      // I2 fix wave: draw the stretched preview's waveform once one exists,
      // not the raw source -- otherwise the ink shows the WRONG material once
      // a clip's tempo/detune has ever diverged from its native values.
      const url = forgeApi.audioUrl(clip.previewAudio ?? clip.audio);
      const buffer = bufferCache.get(url);
      if (!buffer) continue;
      const { left, width } = clipSpanPx(clip.start_sec, clip.dur_sec, scrollSec, pxPerSec);
      const columns = Math.max(1, Math.round(width));
      const peaks = peaksFor(url, buffer, columns, clip.offset_sec, clip.offset_sec + clip.dur_sec);
      paintPeaks(ctx, left, left + width, left, width, h, laneColor, peaks);
      for (const span of overlapSpans) {
        const oLeft = secToPx(Math.max(span.start_sec, clip.start_sec), scrollSec, pxPerSec);
        const oRight = secToPx(Math.min(span.end_sec, clip.start_sec + clip.dur_sec), scrollSec, pxPerSec);
        if (oRight > oLeft) paintPeaks(ctx, oLeft, oRight, left, width, h, darkColor, peaks);
      }
      paintClipMarks(ctx, left, width, h, red, peaks);
    }

    // downbeatColor is built directly in OKLCH (see lib/math/downbeats.ts) --
    // it does not read a CSS var, so there is nothing to resolve for it here.
    const mine = laneDownbeats(arrangement.clips, lane.index, arrangement.bpm);
    const otherLaneIndices = arrangement.lanes.map((l) => l.index).filter((i) => i !== lane.index);
    const others = otherLaneIndices.flatMap((i) => laneDownbeats(arrangement.clips, i, arrangement.bpm));
    for (const sec of mine) {
      const x = secToPx(sec, scrollSec, pxPerSec);
      if (x < 0 || x > w) continue;
      const t = coincidence(sec, others, arrangement.bpm);
      ctx.strokeStyle = downbeatColor(t);
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(x + 0.5, 0);
      ctx.lineTo(x + 0.5, h);
      ctx.stroke();
    }
    // Spec §5.4: hovering the chroma heatmap draws a red vertical line at that
    // frame on the selected clip, in its own lane. Last, so it sits over the
    // waveform and the downbeats.
    const mark = chromaLink.hover;
    if (mark) {
      const marked = laneClips.find((c) => c.id === mark.clipId);
      if (marked) {
        const sec = markerSecFor(marked, mark.frac, mark.fileSec);
        const x = sec === null ? -1 : Math.round(secToPx(sec, scrollSec, pxPerSec)) + 0.5;
        if (x >= 0 && x <= w) {
          ctx.strokeStyle = red;
          ctx.lineWidth = 1.5;
          ctx.beginPath();
          ctx.moveTo(x, 0);
          ctx.lineTo(x, h);
          ctx.stroke();
        }
      }
    }
  }

  // Preload every clip's audio once; a fresh buffer triggers its own redraw
  // independently of the draw effect below, so a slow decode never blocks
  // the grid from appearing.
  $effect(() => {
    let cancelled = false;
    for (const clip of arrangement.clips.filter((c) => c.lane === lane.index)) {
      // I2 fix wave: preload/cache the stretched preview when one exists, so
      // the key here matches the one `redraw()` looks up above.
      const url = forgeApi.audioUrl(clip.previewAudio ?? clip.audio);
      if (bufferCache.has(url)) continue;
      playback
        .preload(url)
        .then((buf) => {
          if (cancelled) return;
          bufferCache.set(url, buf);
          redraw();
        })
        .catch(() => {
          // no audio for this ref (yet) -- the clip just draws with no ink
        });
    }
    return () => {
      cancelled = true;
    };
  });

  // Canvas colour rule (Global Constraint): every draw effect resolves
  // colours through getComputedStyle AND reads view.theme here so Svelte
  // tracks it as a dependency -- a canvas that only has view.theme in scope
  // without READING it inside the effect body silently stops redrawing on
  // the DARK toggle (the exact M1 regression this rule exists to prevent).
  $effect(() => {
    void arrangement.pxPerSec;
    void arrangement.scrollSec;
    void arrangement.bpm;
    void arrangement.beatsPerBar;
    void arrangement.clips;
    void arrangement.overlaps;
    void arrangement.lanes;
    void view.theme;
    void chromaLink.hover;
    redraw();
  });
</script>

<canvas class="lane-canvas" data-region="lane-canvas" bind:this={canvasEl}></canvas>

<style>
  .lane-canvas {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    display: block;
  }
</style>
