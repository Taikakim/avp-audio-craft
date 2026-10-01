/**
 * Spec 5.1's range row, as WINTERMUTE settled it on 2026-09-17: sigma max is NOT
 * a ScheduleSpec field. It is the level the pass starts its noise at -- 1.0 for a
 * fresh generate, and the target's own NOISE when the target is an A2A clip. It
 * goes on the wire as the request's `sigma_max`, next to `schedule`, never inside
 * it. The server agrees: /schedule's docstring says "For a2a previews pass
 * sigma_max=init_noise_level (schedule truncates there)".
 */
export const SIGMA_MAX_FIXED = 1.0;

/** The part of a clip's `a2a` this needs; `null` = no clip, or no a2a block. */
export interface A2AState {
  on: boolean;
  noise: number;
}

export function sigmaMaxFor(a2a: A2AState | null): number {
  if (!a2a || !a2a.on) return SIGMA_MAX_FIXED;
  // UNCLAMPED, deliberately. This is what the request carries and what the
  // read-only sigma max field displays, and 5.1 requires it to be the same
  // number as NOISE -- a silent floor here would show 0.01 next to a NOISE of 0
  // and send a pass the user did not ask for. NOISE 0 means "keep the audio",
  // which is a legal thing to commit. Only CHARTING needs a floor, because a
  // schedule from sigma 0 has no curve; `chartableSigmaMax` is that floor and it
  // is the only place the value is altered.
  return a2a.noise;
}

/** The value to chart with, or null when there is no curve to draw. */
export function chartableSigmaMax(sigmaMax: number): number | null {
  return sigmaMax >= 0.01 ? Math.min(1, sigmaMax) : null;
}
