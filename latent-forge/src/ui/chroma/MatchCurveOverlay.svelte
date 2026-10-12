<script lang="ts">
  // The MATCH CURVE overlay (spec §5.4, v3 345-346 and _drawCurve 1262-1302):
  // a second canvas stacked over the heatmap, transparent where it has nothing
  // to say, with pointer events off so the heatmap below still hovers.
  //
  // It clears rather than fills -- a filled background would hide exactly the
  // heatmap it is supposed to annotate.
  import type { ChromaResult } from "../../lib/chroma/chromaClient.svelte";
  import { type FrameWindow, frameToX } from "../../lib/chroma/heatmapGeometry";
  import { ANCHOR_COLORS, curveAxis, curveY, windowScores } from "../../lib/chroma/matchCurve";
  import { anchors } from "../../lib/chroma/match";
  import { HELP } from "../../lib/help/strings";
  import { chromaColour, fitChromaCanvas } from "./chromaCanvas";

  interface Props {
    result: ChromaResult | null;
    target: Float32Array;
    win: FrameWindow;
    /**
     * The ANALYSIS detune (Task 11's `analysisDetuneCents`), not the clip's:
     * 0 when `result` came from the already-stretched `clip.previewAudio`,
     * `clip.detune_cents` when it came from the raw `clip.audio`. Rotating an
     * already-stretched fold by the clip's detune applies it twice.
     */
    detuneCents?: number;
  }
  let { result, target, win, detuneCents = 0 }: Props = $props();

  let canvasEl = $state<HTMLCanvasElement>();

  function draw(): void {
    const canvas = canvasEl;
    if (!canvas) return;
    const ctx = fitChromaCanvas(canvas);
    if (!ctx) return;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;

    const anch = anchors(target);
    const axis = curveAxis(anch);

    // The three reference lines first, so the curve draws over them.
    ctx.lineWidth = 1;
    for (const key of ["unison", "fifth", "tritone"] as const) {
      const y = Math.round(curveY(anch[key], axis, h)) + 0.5;
      ctx.setLineDash([4, 4]);
      ctx.strokeStyle = ANCHOR_COLORS[key];
      ctx.globalAlpha = 0.75;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.globalAlpha = 1;
    }
    if (!result) return;

    const scores = windowScores(result, target, win, detuneCents);
    if (scores.length === 0) return;
    const from = Math.max(0, Math.floor(win.from));
    ctx.beginPath();
    scores.forEach((m, i) => {
      const x = frameToX(from + i, win, w);
      const y = curveY(m, axis, h);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.strokeStyle = chromaColour(canvas, "--purple-strong");
    ctx.lineWidth = 1.7;
    ctx.stroke();
  }

  $effect(() => {
    void result;
    void target;
    void win;
    void detuneCents;
    draw();
  });
</script>

<canvas
  bind:this={canvasEl}
  data-testid="chroma-match-curve"
  data-help={HELP.chromaMatchCurve}
></canvas>

<style>
  canvas {
    position: absolute;
    inset: 1px;
    display: block;
    width: calc(100% - 2px);
    height: calc(100% - 2px);
    pointer-events: none;
  }
</style>
