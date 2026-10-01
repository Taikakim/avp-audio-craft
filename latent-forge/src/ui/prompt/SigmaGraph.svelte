<script lang="ts">
  import { HELP } from "../../lib/help/strings";
  import { LANE_H, PAD, sigmaGraphGeometry } from "../../lib/sampling/sigmaGraph";
  import type { SigmaGraphInput } from "../../lib/sampling/sigmaGraph";

  interface Props {
    input: SigmaGraphInput | null;
    note: string | null;
    pending: boolean;
    error: string | null;
  }
  let { input, note, pending, error }: Props = $props();

  let canvas: HTMLCanvasElement | undefined = $state();

  /**
   * One token read, with a REQUIRED fallback. Measured against real jsdom (the probe in
   * docs/latent-forge/M4_CRITIC_FINDINGS.md): an undefined custom property returns `""`, and
   * `ctx.fillStyle = ""` is a SILENT no-op — the context keeps whatever colour it last held and
   * nothing anywhere reports a problem. In the shipped app tokens.css is loaded and no fallback
   * ever fires; in a bare render (a test, a thumbnail, a stylesheet that failed to load) the
   * difference is between a readable graph and one painted entirely in the last colour used.
   * The two slot fallbacks are spec 5.3's own literals; the rest are plain DARK-ish stand-ins.
   */
  function token(el: Element, name: string, fallback: string): string {
    const v = getComputedStyle(el).getPropertyValue(name).trim();
    return v === "" ? fallback : v;
  }

  function draw(): void {
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const cssW = input?.width ?? canvas.clientWidth ?? 320;
    const cssH = input?.height ?? canvas.clientHeight ?? 180;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.max(1, Math.round(cssW * dpr));
    canvas.height = Math.max(1, Math.round(cssH * dpr));
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    // Resolved once per frame, never cached across frames -- a theme switch must be picked up
    // by the next draw without this component knowing a switch happened (Global Constraints).
    const c = {
      panel2: token(canvas, "--panel2", "oklch(18% 0.01 250)"),
      turq: token(canvas, "--turq-strong", "oklch(72% 0.13 190)"),
      warm: token(canvas, "--warm", "oklch(75% 0.14 65)"),
      textDim: token(canvas, "--text-dim", "oklch(62% 0.01 250)"),
      text: token(canvas, "--text", "oklch(92% 0.01 250)"),
      slots: [
        token(canvas, "--slot1", "oklch(72% 0.15 75)"),
        token(canvas, "--slot2", "oklch(62% 0.14 330)"),
      ] as const,
    };

    ctx.globalAlpha = 1;
    ctx.fillStyle = c.panel2;
    ctx.fillRect(0, 0, cssW, cssH);

    // `note` and `error` are DOM siblings below, not fillText: a canvas is opaque to every DOM
    // query, and Task 10 asserts the note's text with Testing Library.
    if (error !== null) return;
    if (input === null || input.sigmas.length === 0) return;

    const g = sigmaGraphGeometry(input);

    ctx.globalAlpha = 0.16;
    ctx.fillStyle = c.turq;
    ctx.fillRect(g.cfgBand.x0, 0, g.cfgBand.x1 - g.cfgBand.x0, g.plotHeight);
    ctx.globalAlpha = 1;
    ctx.strokeStyle = c.turq;
    ctx.lineWidth = 1;
    for (const x of [g.cfgBand.x0, g.cfgBand.x1]) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, g.plotHeight);
      ctx.stroke();
    }

    for (const band of g.slotBands) {
      const slotColor = c.slots[band.index];
      ctx.globalAlpha = 0.26;
      ctx.fillStyle = slotColor;
      ctx.fillRect(band.x0, 0, band.w, g.plotHeight);
      ctx.globalAlpha = 1;
      ctx.fillStyle = slotColor;
      ctx.fillRect(band.x0, band.laneY, band.w, LANE_H);
      if (band.hatch) {
        ctx.save();
        ctx.beginPath();
        ctx.rect(band.hatch.x0, band.laneY, band.hatch.w, LANE_H);
        ctx.clip();
        ctx.globalAlpha = 0.85;
        ctx.strokeStyle = c.panel2;
        for (let x = band.hatch.x0 - LANE_H; x < band.hatch.x0 + band.hatch.w + LANE_H; x += 3) {
          ctx.beginPath();
          ctx.moveTo(x, band.laneY + LANE_H);
          ctx.lineTo(x + LANE_H, band.laneY);
          ctx.stroke();
        }
        ctx.restore();
        ctx.globalAlpha = 1;
      }
    }

    if (g.rescaleY !== null) {
      ctx.globalAlpha = 1;
      ctx.strokeStyle = c.warm;
      ctx.setLineDash([2, 3]);
      ctx.beginPath();
      ctx.moveTo(0, g.rescaleY);
      ctx.lineTo(cssW, g.rescaleY);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // sigma + progress dim together while a fresher response is on the way (pending), so the
    // curve on screen visibly admits it might be stale without disappearing outright.
    ctx.globalAlpha = pending ? 0.4 : 1;
    ctx.strokeStyle = c.turq;
    ctx.setLineDash([3, 2]);
    ctx.beginPath();
    g.progressPath.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)));
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.strokeStyle = c.text;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    g.sigmaPath.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)));
    ctx.stroke();
    ctx.globalAlpha = 1;

    ctx.strokeStyle = c.textDim;
    ctx.lineWidth = 1;
    for (const t of g.ticks) {
      ctx.beginPath();
      ctx.moveTo(t.x, t.y - 2.5);
      ctx.lineTo(t.x, t.y + 2.5);
      ctx.stroke();
    }

    ctx.fillStyle = c.textDim;
    const label = "sigma + progress";
    ctx.fillText(label, PAD, g.plotHeight - 4);
    const stepText = g.stepLabel;
    const stepW = ctx.measureText(stepText).width;
    ctx.fillText(stepText, cssW - stepW - PAD, g.plotHeight - 4);
  }

  $effect(() => {
    void input;
    void note;
    void pending;
    void error;
    draw();
  });
</script>

<canvas
  bind:this={canvas}
  class="sigma-graph"
  data-testid="sigma-graph"
  data-canvas="sigma"
  data-help={HELP.sigmaGraph}
  width={input?.width ?? 320}
  height={input?.height ?? 180}
></canvas>
{#if error !== null}
  <span class="err" data-graph-error>{error}</span>
{:else if note !== null}
  <span class="note" data-graph-note>{note}</span>
{/if}

<style>
  .sigma-graph {
    width: 100%;
    height: 100%;
    display: block;
    box-sizing: border-box;
    border: 1px solid var(--border);
  }
  .err,
  .note {
    display: block;
    font-size: 10px;
    color: var(--text-dim);
  }
  .err {
    color: var(--warm);
  }
</style>
