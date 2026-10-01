// The detune scan strip's own arithmetic (spec §5.4; v3 markup 332, logic
// _drawScan 1224-1260 and scanLabel 1912-1918). Task 5 computes the curve;
// this turns it into pixels, and pixels back into cents.
//
// Nothing here touches a store or a canvas, so the boundary cases that
// actually bite -- a dead-flat curve, a pointer dragged off the end of the
// strip, a detune that is not one of the 51 sampled steps -- are pinned under
// vitest rather than discovered on screen.

import { DETUNE_MAX, DETUNE_MIN, type DetuneScan, type ScanCriterion, bestDetune } from "./detuneScan";

/** The drawing's canvas, v3 332. */
export const SCAN_W = 500;
export const SCAN_H = 30;

/** Vertical guides, v3 1233. */
export const SCAN_GRID_CENTS: readonly number[] = [-50, 0, 50];

/** A curve flatter than this is opened out rather than divided by (v3 1231). */
export const SCAN_RANGE_FLOOR = 0.01;

export function criterionValues(scan: DetuneScan, criterion: ScanCriterion): number[] {
  return scan.mean.map((m, i) => (criterion === "steadiest" ? m - scan.sd[i] : m));
}

export function criterionLabel(criterion: ScanCriterion): "HIGHEST" | "STEADIEST" {
  return criterion === "steadiest" ? "STEADIEST" : "HIGHEST";
}

export function nextCriterion(criterion: ScanCriterion): ScanCriterion {
  return criterion === "steadiest" ? "highest" : "steadiest";
}

const SPAN = DETUNE_MAX - DETUNE_MIN;

/** Whole cents, clamped to ±100: a drag off the end of the strip pins there. */
export function centsAtX(x: number, widthPx: number): number {
  const frac = Math.min(1, Math.max(0, x / Math.max(1, widthPx)));
  return Math.round(frac * SPAN + DETUNE_MIN);
}

export function xForCents(cents: number, widthPx: number): number {
  const c = Math.min(DETUNE_MAX, Math.max(DETUNE_MIN, cents));
  return ((c - DETUNE_MIN) / SPAN) * widthPx;
}

export interface ScanRange {
  lo: number;
  hi: number;
}

export function scanRange(values: readonly number[]): ScanRange {
  if (values.length === 0) return { lo: 0, hi: 1 };
  let lo = Infinity;
  let hi = -Infinity;
  for (const v of values) {
    if (v < lo) lo = v;
    if (v > hi) hi = v;
  }
  if (hi - lo < SCAN_RANGE_FLOOR) return { lo: lo - SCAN_RANGE_FLOOR, hi: hi + SCAN_RANGE_FLOOR };
  return { lo, hi };
}

export function scanY(v: number, range: ScanRange, heightPx: number): number {
  const span = Math.max(1e-9, range.hi - range.lo);
  return heightPx - 2 - ((v - range.lo) / span) * (heightPx - 5);
}

/** The sampled step nearest a (possibly un-sampled) detune value. */
export function nearestScanIndex(scan: DetuneScan, cents: number): number {
  let best = 0;
  let d = Infinity;
  for (let i = 0; i < scan.cents.length; i++) {
    const dd = Math.abs(scan.cents[i] - cents);
    if (dd < d) {
      d = dd;
      best = i;
    }
  }
  return best;
}

/**
 * v3 1917: `now <n>¢ · mean <m> ± <sd> · peak <±n>¢`, plus the clause v3 did
 * not need.
 *
 * `relCents` and the peak are offsets on the strip's RELATIVE axis -- the scan
 * runs on audio the stretch has already detuned, so step c means "the clip's
 * current detune plus c". Without naming that origin, a reader of "peak +40¢"
 * cannot tell 40 from what. `currentCents` is the clip's own detune, and the
 * trailing clause states the axis and its origin together.
 */
export function scanLabel(
  scan: DetuneScan,
  relCents: number,
  criterion: ScanCriterion,
  currentCents: number,
): string {
  const i = nearestScanIndex(scan, relCents);
  const peak = bestDetune(scan, criterion);
  const sign = peak > 0 ? "+" : "";
  return `now ${relCents}¢ · mean ${scan.mean[i].toFixed(2)} ± ${scan.sd[i].toFixed(2)} · peak ${sign}${peak}¢ · ±${DETUNE_MAX}¢ relative to ${currentCents}¢`;
}
