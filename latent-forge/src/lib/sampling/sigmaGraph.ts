import type { LatchSlot } from "../forge/types";
import { cfgBandFraction, progressAt } from "./cfgInterval";
import { activeSlots } from "./samplers";
import type { LatchState } from "./samplers";

export const LANE_H = 7;
export const LANE_GAP = 2;
export const PAD = 4;
export const MAX_TICKS = 200;

/**
 * The drawing's RESERVED = 2*LANE_H + LANE_GAP + 2 (v3:1355) reserves for TWO lanes
 * unconditionally, so a slot appearing or disappearing never reflows the sigma curve above it.
 * `nSlots` is accepted for callers that want to name what they are reserving for, but the
 * returned number never depends on it.
 */
export function reservedHeight(nSlots: number): number {
  void nSlots;
  return 2 * LANE_H + LANE_GAP + 2;
}

export interface SigmaGraphInput {
  sigmas: number[];
  steps: number;
  cfgLo: number;
  cfgHi: number;
  stepped: boolean;
  scalePhi: number;
  slots: readonly LatchSlot[];
  width: number;
  height: number;
}

export interface SlotBand {
  index: 0 | 1;
  x0: number;
  w: number;
  laneY: number;
  hatch: { x0: number; w: number } | null;
}

export interface SigmaGraphGeometry {
  plotHeight: number;
  cfgBand: { x0: number; x1: number };
  sigmaPath: { x: number; y: number }[];
  progressPath: { x: number; y: number }[];
  ticks: { x: number; y: number }[];
  rescaleY: number | null;
  slotBands: SlotBand[];
  stepLabel: string;
}

function emptyGeometry(steps: number, plotHeight: number): SigmaGraphGeometry {
  return {
    plotHeight: Math.max(0, plotHeight),
    cfgBand: { x0: 0, x1: 0 },
    sigmaPath: [],
    progressPath: [],
    ticks: [],
    rescaleY: null,
    slotBands: [],
    stepLabel: String(steps),
  };
}

/**
 * Pure geometry for SigmaGraph.svelte (Task 7). Every y-coordinate below comes from indexing
 * `sigmas` -- the array `/schedule` returned -- never from re-deriving sigma with a formula
 * (spec 5.3, last paragraph; the drawing's own _sigmaAt is exactly what this milestone must NOT
 * port).
 */
export function sigmaGraphGeometry(input: SigmaGraphInput): SigmaGraphGeometry {
  const { sigmas, steps, cfgLo, cfgHi, stepped, scalePhi, slots, width, height } = input;
  const n = sigmas.length - 1;
  const drawnSlots = activeSlots({ latch_on: true, slots } satisfies LatchState).slice(0, 2);
  const plotHeight = height - reservedHeight(drawnSlots.length);

  if (sigmas.length === 0 || width <= 0 || plotHeight <= 0) {
    return emptyGeometry(steps, plotHeight);
  }

  const sigma0 = sigmas[0];
  const { lo, hi } = cfgBandFraction(sigmas, cfgLo, cfgHi);
  const cfgBand = { x0: lo * width, x1: hi * width };

  const sigmaAtIndex = (idx: number): number => sigmas[Math.max(0, Math.min(n, idx))];
  const yFromSigma = (s: number): number =>
    plotHeight - PAD - (sigma0 > 0 ? s / sigma0 : 0) * (plotHeight - 2 * PAD);
  const yFromProgress = (p: number): number => plotHeight - PAD - p * (plotHeight - 2 * PAD);

  const sigmaPath: { x: number; y: number }[] = [];
  let prevY: number | null = null;
  for (let px = 0; px <= width; px++) {
    const idx = Math.round((px / width) * n);
    const y = yFromSigma(sigmaAtIndex(idx));
    if (stepped && prevY !== null) sigmaPath.push({ x: px, y: prevY });
    sigmaPath.push({ x: px, y });
    prevY = y;
  }

  const progressPath: { x: number; y: number }[] = [];
  for (let px = 0; px <= width; px++) {
    const idx = Math.round((px / width) * n);
    progressPath.push({ x: px, y: yFromProgress(progressAt(sigmas, idx)) });
  }

  const nTicks = Math.min(MAX_TICKS, Math.max(1, steps));
  const ticks: { x: number; y: number }[] = [];
  for (let i = 0; i <= nTicks; i++) {
    const u = i / nTicks;
    const idx = Math.round(u * n);
    ticks.push({ x: u * width, y: yFromSigma(sigmaAtIndex(idx)) });
  }

  const rescaleY = scalePhi > 0 ? yFromProgress(scalePhi) : null;

  const slotBands: SlotBand[] = drawnSlots.map((s, k) => {
    const index = k as 0 | 1;
    const x0 = s.start_pct * width;
    const w = Math.max(0, s.end_pct - s.start_pct) * width;
    const laneY = plotHeight + 2 + k * (LANE_H + LANE_GAP);
    const oLo = Math.max(s.start_pct, lo);
    const oHi = Math.min(s.end_pct, hi);
    const hatch = oHi > oLo ? { x0: oLo * width, w: (oHi - oLo) * width } : null;
    return { index, x0, w, laneY, hatch };
  });

  return {
    plotHeight, cfgBand, sigmaPath, progressPath, ticks, rescaleY, slotBands,
    stepLabel: String(steps),
  };
}
