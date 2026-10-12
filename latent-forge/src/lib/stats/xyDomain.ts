// Pure axis-domain and point-filtering helpers for the XY scatter panel
// (spec §4.4). Kept out of the component so "all points share one value"
// and "a point is null on this field at runtime" can be pinned under vitest
// without a canvas.

export interface ScalarPoint {
  crop_id: string;
  x: number;
  y: number;
  label: string;
}

/**
 * Only points with a finite x AND y. M10 T2's DatasetScalars types x/y as
 * plain `number` (matching spec §6.5's shape line for line), but a crop can
 * still lack one sidecar scalar at runtime -- the same class of
 * declared-vs-actual mismatch this project has hit before (forgeApi.schedule,
 * M4). Number.isFinite(null) is false regardless of what the type claims, so
 * this excludes a runtime-null point without trusting the declared type.
 */
export function finitePoints(points: readonly ScalarPoint[]): ScalarPoint[] {
  return points.filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y));
}

/**
 * [min, max] over one axis, or [0, 1] -- the same "furniture, not a lie
 * about values" default M1's stub axes already use -- when there is nothing
 * finite to plot.
 */
export function domainOf(points: readonly ScalarPoint[], key: "x" | "y"): [number, number] {
  if (points.length === 0) return [0, 1];
  let lo = Infinity;
  let hi = -Infinity;
  for (const p of points) {
    const v = p[key];
    if (v < lo) lo = v;
    if (v > hi) hi = v;
  }
  return [lo, hi];
}
