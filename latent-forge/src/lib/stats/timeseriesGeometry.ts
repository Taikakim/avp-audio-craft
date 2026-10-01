// Pure geometry for the TIME SERIES panel (spec §4.4): where a resampled
// sample falls on the frame axis, and where a null value breaks a line into
// separate segments rather than being plotted as zero.

/**
 * Maps sample index `i` of a `values` array of length `len` onto the frame
 * axis `[0, nFrames - 1]`. The server resamples to at most max_points (spec
 * §6.5), so the axis comes from `n_frames`, never from `values.length` -- a
 * single point occupies frame 0.
 */
export function frameOf(i: number, len: number, nFrames: number): number {
  if (len <= 1 || nFrames <= 1) return 0;
  return (i / (len - 1)) * (nFrames - 1);
}

/**
 * Splits `values` into runs of consecutive non-null samples, each as
 * `[index, value]` pairs -- a null is a GAP (spec §6.5: "a feature a latent
 * lacks yields all-null values", not a zero), so each run is drawn as its
 * own path with a moveTo at its start, never a lineTo across the gap.
 */
export function segments(values: readonly (number | null)[]): Array<Array<[number, number]>> {
  const out: Array<Array<[number, number]>> = [];
  let current: Array<[number, number]> = [];
  for (let i = 0; i < values.length; i++) {
    const v = values[i];
    if (v === null || !Number.isFinite(v)) {
      if (current.length > 0) { out.push(current); current = []; }
      continue;
    }
    current.push([i, v]);
  }
  if (current.length > 0) out.push(current);
  return out;
}
