// Axis furniture for the statistics panels (spec §4.4). Pure, so the panels can
// be drawn and their ticks asserted without a canvas.

/** Heckbert's "nice number": the round number nearest `range`. */
function niceNum(range: number, round: boolean): number {
  const exp = Math.floor(Math.log10(range));
  const f = range / Math.pow(10, exp);
  const nf = round
    ? f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10
    : f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10;
  return nf * Math.pow(10, exp);
}

/**
 * Round tick values covering [min, max], roughly `target` of them. Returns a
 * single-element array for an empty or non-finite domain so a caller can draw
 * the frame of an axis it has no data for.
 */
export function niceTicks(min: number, max: number, target = 5): number[] {
  if (!Number.isFinite(min) || !Number.isFinite(max) || max <= min) return [min];
  const span = niceNum(max - min, false);
  const step = niceNum(span / Math.max(1, target - 1), true);
  const lo = Math.floor(min / step + 1e-9) * step;
  const hi = Math.ceil(max / step - 1e-9) * step;
  const n = Math.round((hi - lo) / step);
  const out: number[] = [];
  // toFixed(10) then back: 0.1 + 0.2 arithmetic otherwise prints 0.30000000000000004
  // on an axis label and fails an equality test for no reason.
  for (let i = 0; i <= n; i++) out.push(Number((lo + i * step).toFixed(10)));
  return out;
}

/** Linear map from a data domain to a pixel range; the range may be inverted. */
export function linScale(domain: [number, number], range: [number, number]): (v: number) => number {
  const [d0, d1] = domain;
  const [r0, r1] = range;
  if (d1 === d0) {
    const mid = (r0 + r1) / 2;
    return () => mid;
  }
  const k = (r1 - r0) / (d1 - d0);
  return (v: number) => r0 + (v - d0) * k;
}

/** Whole-pixel cell size for an n x n matrix in a px-wide panel; never below 1. */
export function xcorrCellSize(px: number, n: number): number {
  if (!Number.isFinite(px) || !Number.isFinite(n) || n <= 0) return 1;
  return Math.max(1, Math.floor(px / n));
}
