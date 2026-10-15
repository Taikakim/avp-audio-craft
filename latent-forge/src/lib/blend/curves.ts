// Owner: KUANG (created 2026-10-15), from WINTERMUTE's phase-1 plan
// Per-DiT-block curves for the adapter mixer (spec 2026-10-15-adapter-mixer-design §4.2). Pure: every
// function returns a new array, so a curve held in a $state proxy is replaced, never mutated in place.
export const N_BLOCKS = 24;
export const CURVE_MIN = -0.5;
export const CURVE_MAX = 1.5;

export function clampValue(v: number): number {
  return v < CURVE_MIN ? CURVE_MIN : v > CURVE_MAX ? CURVE_MAX : v;
}

const make = (f: (i: number) => number): number[] =>
  Array.from({ length: N_BLOCKS }, (_, i) => clampValue(Number(f(i).toFixed(6))));

export function flatCurve(v = 1): number[] {
  return make(() => v);
}

export interface CurveShape { id: string; label: string; make(): number[] }

const LAST = N_BLOCKS - 1;
const E3 = Math.exp(3) - 1;

export const CURVE_SHAPES: readonly CurveShape[] = [
  { id: "flat", label: "flat", make: () => flatCurve(1) },
  { id: "early_ramp_down", label: "early ramp down", make: () => make((i) => 1 - i / LAST) },
  { id: "late_ramp_down", label: "late ramp down", make: () => make((i) => (i < 12 ? 1 : 1 - (i - 11) / 12)) },
  { id: "middle_bell", label: "middle bell", make: () => make((i) => Math.exp(-(((i - LAST / 2) / 5) ** 2))) },
  { id: "ascending_exp", label: "ascending exp", make: () => make((i) => (Math.exp((3 * i) / LAST) - 1) / E3) },
  { id: "descending_exp", label: "descending exp", make: () => make((i) => (Math.exp((3 * (LAST - i)) / LAST) - 1) / E3) },
  { id: "early_only", label: "early only", make: () => make((i) => (i < 8 ? 1 : 0)) },
  { id: "last8_off", label: "last 8 off", make: () => make((i) => (i < 16 ? 1 : 0)) },
  { id: "alternating", label: "alternating", make: () => make((i) => (i % 2 === 0 ? 1 : 0)) },
];

export function soloCurve(block: number): number[] {
  return make((i) => (i === block ? 1 : 0));
}

export function invertCurve(c: number[]): number[] {
  return c.map((v) => clampValue(Number((1 - v).toFixed(6))));
}

export function scaleCurve(c: number[], k: number): number[] {
  return c.map((v) => clampValue(Number((v * k).toFixed(6))));
}

/** 3-tap moving average, edges replicated. */
export function smoothCurve(c: number[]): number[] {
  return c.map((v, i) => {
    const a = c[Math.max(0, i - 1)];
    const b = c[Math.min(c.length - 1, i + 1)];
    return clampValue(Number(((a + v + b) / 3).toFixed(6)));
  });
}

/** A freehand stroke from (i0, v0) to (i1, v1): every column between is set on the straight line. */
export function drawSegment(c: number[], i0: number, v0: number, i1: number, v1: number): number[] {
  const out = [...c];
  const lo = Math.max(0, Math.min(i0, i1));
  const hi = Math.min(N_BLOCKS - 1, Math.max(i0, i1));
  for (let i = lo; i <= hi; i++) {
    const t = i1 === i0 ? 1 : (i - i0) / (i1 - i0);
    out[i] = clampValue(Number((v0 + (v1 - v0) * t).toFixed(6)));
  }
  return out;
}

export function isFlatOne(c: number[]): boolean {
  return c.length === N_BLOCKS && c.every((v) => v === 1);
}
