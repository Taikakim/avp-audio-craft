export type CfgUnit = "progress" | "steps";

function sigma0(sigmas: readonly number[]): number {
  return sigmas.length > 0 ? sigmas[0] : 0;
}

/**
 * Spec 5.3: progress = 1 - sigma/sigma0. An empty array has no schedule to report progress
 * over, and sigma0 === 0 (an A2A clip at NOISE 0 — spec 5.1 requires this field to mirror NOISE
 * exactly, unclamped) has no noise range to traverse: 0/0 and x/0 are not "the pass hasn't
 * started", they are "there is nothing to measure", so both are defined as progress 0 rather
 * than NaN.
 */
export function progressAt(sigmas: readonly number[], i: number): number {
  const s0 = sigma0(sigmas);
  if (sigmas.length === 0 || s0 === 0) return 0;
  const idx = Math.max(0, Math.min(sigmas.length - 1, i));
  return 1 - sigmas[idx] / s0;
}

/**
 * First step index whose progress reaches p — the drawing's _stepAtProgress (v3 1347-1351). p is
 * clamped into [0, 1] first, matching the drawing's own Math.max(0, Math.min(1, ...)) at every
 * call site: an out-of-range bound must still chart something rather than throw or search past
 * the array.
 */
export function stepAtProgress(sigmas: readonly number[], p: number): number {
  const n = sigmas.length - 1;
  if (n < 0) return 0;
  const target = Math.max(0, Math.min(1, p));
  for (let i = 0; i <= n; i++) {
    if (progressAt(sigmas, i) >= target) return i;
  }
  return n;
}

/** The inverse direction: what progress a given step index sits at. Clamped to the array's own
 * bounds so a step index left over from a longer schedule (STEPS was lowered since it was
 * recorded) still reads as something rather than undefined. */
export function progressAtStep(sigmas: readonly number[], step: number): number {
  return progressAt(sigmas, step);
}

/**
 * Display only. Nothing in this module, or anywhere this milestone's stores touch, writes a
 * step count back into `cfg_interval_progress` — the store only ever holds progress, and this
 * function's "steps" branch exists purely so the UNIT toggle can show one without ever
 * persisting it.
 */
export function formatCfgBound(sigmas: readonly number[], p: number, unit: CfgUnit): string {
  if (unit === "progress") return p.toFixed(2);
  return String(stepAtProgress(sigmas, p));
}

/** The 0..1 x-fractions of the CFG band, for the graph to fill (Task 6). */
export function cfgBandFraction(
  sigmas: readonly number[], lo: number, hi: number,
): { lo: number; hi: number } {
  const n = sigmas.length - 1;
  if (n <= 0) return { lo: 0, hi: 0 };
  return { lo: stepAtProgress(sigmas, lo) / n, hi: stepAtProgress(sigmas, hi) / n };
}
