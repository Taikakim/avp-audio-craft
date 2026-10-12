// Spec §9.5, the C64 loader border, driven by REAL progress rather than a timer:
//   "sweepHz = sweepStart + (sweepEnd − sweepStart) · (1 − steps_left_total / steps_total),
//    polling /forge/jobs/{id} every 500 ms while running."
// The polling is M1 T5's pollJob (POLL_MS = 500); this file only owns the arithmetic and the
// effect's lifetime.
//
// The spec's settled config is corrected in two places against the module's own DEFAULTS:
// `palette` is an ARRAY (PALETTES.teal), not the name "teal", and `sweepStart`/`sweepEnd` are not
// module config at all -- the module knows only `sweepHz`. See the task's WHY.

import type { Progress } from "../forge/types";
import { PALETTES, createPhosphorBorder, type PhosphorBorder, type PhosphorOptions } from "./phosphor-border.js";

/** Full raster sweeps per second at the first step and at the last (spec §9.5). */
export const SWEEP_START = 95;
export const SWEEP_END = 0;

/** Spec §9.5's settled config. `sweepHz` starts at SWEEP_START; the driver rewrites it per tick. */
export const RASTER_CONFIG: PhosphorOptions = {
  thickness: 4,
  linesPerColour: 3,
  jitter: 0.59,
  persistence: 0.002,
  chromaBleed: 1.5,
  supersample: 8,
  gain: 0.8,
  spotSpread: 0.16,
  palette: PALETTES.teal,
  alphaOut: true,
  sweepHz: SWEEP_START,
};

/**
 * THE guarded division of this milestone. `steps_total` is 0 for a commit with no sampling passes
 * and for `decode`/`bend` (Fact 5), and `null` progress means the job has not reported yet -- both
 * mean "no measurable progress", which is the START of the ramp, not NaN and not the end.
 */
export function sweepHzFor(p: Progress | null | undefined): number {
  const total = p?.steps_total ?? 0;
  if (!p || !Number.isFinite(total) || total <= 0) return SWEEP_START;
  const left = Number.isFinite(p.steps_left_total) ? p.steps_left_total : total;
  const fraction = Math.min(1, Math.max(0, left / total));
  return SWEEP_START + (SWEEP_END - SWEEP_START) * (1 - fraction);
}

type CreateFn = (canvas: HTMLCanvasElement, options?: PhosphorOptions) => PhosphorBorder;

export interface RasterDriver {
  /** Called with the active job's progress, or null when nothing is rendering. */
  update(progress: Progress | null | undefined): void;
  stop(): void;
}

/**
 * Owns the effect's lifetime: built and started on the first tick of a job, `set({sweepHz})` on
 * every tick after, stopped and DESTROYED the moment nothing is running. Destroying rather than
 * only stopping matters because the effect holds an Int32Array/Float32Array pair sized to the
 * canvas plus an ImageData, and a long session would otherwise keep one per render.
 *
 * `create` is a parameter so the driver is testable without a 2d context (jsdom has none).
 */
export function createRasterDriver(canvas: HTMLCanvasElement, create: CreateFn = createPhosphorBorder): RasterDriver {
  let fx: PhosphorBorder | null = null;

  function teardown(): void {
    if (fx === null) return;
    // A METHOD call: the module's destroy() body is `this.stop()`, so a destructured handle throws.
    fx.destroy();
    fx = null;
  }

  return {
    update(progress) {
      if (progress === null || progress === undefined) {
        teardown();
        return;
      }
      if (fx === null) {
        // buildRing() bails out when width*height is 0 and leaves `ring`/`img` unallocated, after
        // which the first step() throws on ring.length. Never hand it an unsized canvas.
        if (canvas.width <= 0 || canvas.height <= 0) return;
        fx = create(canvas, { ...RASTER_CONFIG });
        fx.start();
      }
      fx.set({ sweepHz: sweepHzFor(progress) });
    },
    stop: teardown,
  };
}
