// Drag-to-scale arithmetic, spec §5.1 -- a port of the design handoff's _numDrag
// plus the `num` branch of _onMove (v3 lines 1540-1546, 1569-1581). Pure: no DOM,
// no events. The Svelte action in lib/actions/dragScale.ts is the only caller that
// touches a pointer.

/** A full range is traversed by 260 px of horizontal drag. */
export const DRAG_PX_PER_RANGE = 260;

/**
 * One 260 px drag never maps more than this much range. SEED runs 0..999999, so the plain rule moved
 * it about 3 850 per pixel -- every pixel of mouse travel landed on an unrelated seed. A field wider
 * than this is reached by typing; the drag stays usable for nearby values.
 */
export const MAX_DRAG_RANGE = 5000;

/** A range wider than this follows the pointer through the glide below instead of jumping to it. */
export const INERTIA_AUTO_RANGE = 1000;

/** Default time constant (ms) of that glide. */
export const INERTIA_AUTO_MS = 90;

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
 * The unrounded, unclamped value a drag asks for:
 *   raw = startVal + (dx / 260) * min(range, MAX_DRAG_RANGE) * (shift ? 0.01 : 1)
 * Split out so the inertia glide can ease through it before it is rounded.
 */
export function dragRaw({ startVal, dx, min, max, shift = false }: Omit<DragValueInput, "int">): number {
  const span = Math.min(max - min, MAX_DRAG_RANGE);
  return startVal + (dx / DRAG_PX_PER_RANGE) * span * (shift ? SHIFT_FACTOR : 1);
}

/** value = clamp(int ? round(raw) : +raw.toFixed(shift ? min(5, dec + 2) : dec), min, max) */
export function quantize(
  raw: number, { min, max, int = false, shift = false }: { min: number; max: number; int?: boolean; shift?: boolean },
): number {
  const dec = decimalsFor(min, max, int);
  const rounded = int
    ? Math.round(raw)
    : Number(raw.toFixed(shift ? Math.min(5, dec + 2) : dec));
  return clamp(rounded, min, max);
}

export function dragValue({ startVal, dx, min, max, int = false, shift = false }: DragValueInput): number {
  return quantize(dragRaw({ startVal, dx, min, max, shift }), { min, max, int, shift });
}

/**
 * Time constant (ms) of the drag's follow-through; 0 means the value sits exactly where the pointer
 * puts it. An explicit `inertia` wins, otherwise only wide ranges glide -- the narrow ones keep the
 * spec §5.1 behaviour of being exactly under the pointer.
 */
export function inertiaMs(o: { min: number; max: number; inertia?: number }): number {
  if (o.inertia !== undefined) return Math.max(0, o.inertia);
  return o.max - o.min > INERTIA_AUTO_RANGE ? INERTIA_AUTO_MS : 0;
}

/** How close the glide must get to its target before it snaps there and stops. */
export function settleDistance(min: number, max: number, int = false): number {
  return int ? 0.5 : Math.abs(max - min) * 1e-4;
}
