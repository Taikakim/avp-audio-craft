// Drag-to-scale arithmetic, spec §5.1 -- a port of the design handoff's _numDrag
// plus the `num` branch of _onMove (v3 lines 1540-1546, 1569-1581). Pure: no DOM,
// no events. The Svelte action in lib/actions/dragScale.ts is the only caller that
// touches a pointer.

/** A full range is traversed by 260 px of horizontal drag. */
export const DRAG_PX_PER_RANGE = 260;

/** |dx| must exceed this for the gesture to count as a drag rather than a click. */
export const MOVE_THRESHOLD_PX = 1;

/** Shift is the fine mode: 1% of the normal sensitivity. */
export const SHIFT_FACTOR = 0.01;

export function clamp(v: number, lo: number, hi: number): number {
  return v < lo ? lo : v > hi ? hi : v;
}

/**
 * dec = int ? 0 : clamp(3 - floor(log10(|range| || 1)), 0, 4)
 *
 * So a wide range rounds coarsely (BPM 60..200 -> 1 decimal) and a narrow one finely
 * (sigma min 0.001..0.5 -> 4 decimals), without any per-field table.
 */
export function decimalsFor(min: number, max: number, int = false): number {
  if (int) return 0;
  const range = Math.abs(max - min) || 1;
  return clamp(3 - Math.floor(Math.log10(range)), 0, 4);
}

/** True once the pointer has moved far enough that this is a drag, not a click. */
export function hasMoved(dx: number): boolean {
  return Math.abs(dx) > MOVE_THRESHOLD_PX;
}

export interface DragValueInput {
  /** the field's value when the drag started */
  startVal: number;
  /** pointer x now, minus pointer x at pointerdown */
  dx: number;
  min: number;
  max: number;
  int?: boolean;
  shift?: boolean;
}

/**
 * raw   = startVal + (dx / 260) * range * (shift ? 0.01 : 1)
 * value = clamp(int ? round(raw) : +raw.toFixed(shift ? min(5, dec + 2) : dec), min, max)
 */
export function dragValue({ startVal, dx, min, max, int = false, shift = false }: DragValueInput): number {
  const range = max - min;
  const dec = decimalsFor(min, max, int);
  const raw = startVal + (dx / DRAG_PX_PER_RANGE) * range * (shift ? SHIFT_FACTOR : 1);
  const rounded = int
    ? Math.round(raw)
    : Number(raw.toFixed(shift ? Math.min(5, dec + 2) : dec));
  return clamp(rounded, min, max);
}
