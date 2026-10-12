import type { ScheduleSpec } from "../forge/types";

export const SCHEDULE_SHAPES = [
  "model", "logsnr", "geometric", "linear", "log", "exponential", "cosine",
] as const;

/**
 * Spec 5.1's table. Rectified-flow units throughout (10 X6): the drawing's
 * k-diffusion ranges (sigma min 0.001..1, sigma max 1..100) are wrong for SA3,
 * whose time axis is [0, 1].
 */
export const RANGES = {
  rho: { min: 0.1, max: 15 },
  sigma_min: { min: 0.001, max: 0.5 },
  sigma_max: { min: 0.01, max: 1 },
  lam_min: { min: -12, max: 0 },
  lam_max: { min: 0, max: 6 },
  plateaus: { min: 2, max: 24, int: true },
  tilt: { min: 0, max: 1 },
  steps: { min: 1, max: 150, int: true },
  cfg_scale: { min: 0, max: 64 },
  scale_phi: { min: 0, max: 1 },
  length_sec: { min: 1, max: 184 },
  seed: { min: 0, max: 999999, int: true },
  // 4.5's own fields, kept here so tasks 4-11 do not each re-read 5.1's table.
  // The CFG interval is STORED as progress; its step-unit range is 0..steps and
  // is therefore computed, not constant (see cfgInterval.ts).
  cfg_interval: { min: 0, max: 1 },
  noise: { min: 0, max: 1 },
  detune_cents: { min: -100, max: 100, int: true },
} as const satisfies Record<string, { min: number; max: number; int?: boolean }>;

/**
 * Two of 5.3's validation rules are deliberately NOT mirrored here.
 *
 * "the sigma sequence must be non-increasing" is a property of the array the
 * server built; the client has no array until /schedule answers, and when it
 * does, a decreasing check belongs next to the response (Task 4), not next to
 * the spec that asked for it. "sending both a non-model shape and a non-null
 * dist_shift is a 400" cannot happen from this client at all: nothing here ever
 * sets dist_shift.
 */
export const FLAT_PLATEAU_NOTE = "flat plateaus are no-op steps on ODE samplers";
export const POST_CFG_NOTE = "POST: guidance is distilled in — CFG is off";

export interface ScheduleIssue {
  field: string;
  severity: "error" | "warning";
  message: string;
}

function rangeIssue(
  field: keyof typeof RANGES,
  v: number,
): ScheduleIssue | null {
  const r: { min: number; max: number; int?: boolean } = RANGES[field];
  if (!Number.isFinite(v)) return { field, severity: "error", message: `${field} must be a number` };
  if (r.int && !Number.isInteger(v)) {
    return { field, severity: "error", message: `${field} must be a whole number` };
  }
  if (v < r.min || v > r.max) {
    return { field, severity: "error", message: `${field} must be between ${r.min} and ${r.max}` };
  }
  return null;
}

/**
 * Spec 5.3: the note appears when STEPPED is on with no tilt, on a sampler that
 * integrates an ODE -- the plateau's repeated sigma makes those steps do nothing.
 * pingpong re-noises between steps, so a flat plateau is a churn step there and
 * is deliberate. dpmpp is not warned about here because it is REFUSED (h = 0 is a
 * division by zero); `validateSchedule` raises that as an error instead.
 */
export function flatPlateauNote(spec: ScheduleSpec, samplerType: string | null): string | null {
  if (!spec.stepped || spec.tilt !== 0) return null;
  return samplerType === "euler" || samplerType === "rk4" ? FLAT_PLATEAU_NOTE : null;
}

/**
 * The client's mirror of 5.3's validation list. It exists to stop a doomed
 * request and to drive the pane's inline messages; the server still validates,
 * and where the two ever disagree the server is right.
 */
export function validateSchedule(
  spec: ScheduleSpec,
  sigmaMax: number,
  samplerType: string | null,
): ScheduleIssue[] {
  const out: ScheduleIssue[] = [];

  if (!(SCHEDULE_SHAPES as readonly string[]).includes(spec.shape)) {
    out.push({ field: "shape", severity: "error", message: `unknown shape "${spec.shape}"` });
  }

  // Every numeric field is range-checked whatever the shape uses, because the
  // server validates the whole ScheduleSpec it is sent, not the subset in play.
  for (const f of ["rho", "sigma_min", "lam_min", "lam_max", "plateaus", "tilt"] as const) {
    const issue = rangeIssue(f, spec[f] as number);
    if (issue) out.push(issue);
  }

  if (spec.sigma_min >= sigmaMax) {
    out.push({
      field: "sigma_min",
      severity: "error",
      message: `sigma min must be below sigma max (${sigmaMax})`,
    });
  }

  if (spec.lam_max <= spec.lam_min) {
    out.push({ field: "lam_max", severity: "error", message: "lam max must be above lam min" });
  }

  if (spec.stepped && spec.tilt === 0 && samplerType === "dpmpp") {
    out.push({
      field: "tilt",
      severity: "error",
      message: "dpmpp cannot take flat plateaus — h = 0 divides by zero and NaNs the latents",
    });
  }

  const note = flatPlateauNote(spec, samplerType);
  if (note) out.push({ field: "tilt", severity: "warning", message: note });

  return out;
}
