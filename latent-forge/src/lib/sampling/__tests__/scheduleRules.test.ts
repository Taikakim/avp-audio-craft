import { describe, expect, it } from "vitest";
import { SCHEDULE_DEFAULT } from "../../forge/defaults";
import type { ScheduleSpec } from "../../forge/types";
import {
  FLAT_PLATEAU_NOTE, POST_CFG_NOTE, RANGES, SCHEDULE_SHAPES, flatPlateauNote, validateSchedule,
} from "../scheduleRules";

function spec(over: Partial<ScheduleSpec> = {}): ScheduleSpec {
  return { ...SCHEDULE_DEFAULT, ...over };
}

const errs = (s: ScheduleSpec, sm = 1.0, sampler = "euler") =>
  validateSchedule(s, sm, sampler).filter((i) => i.severity === "error").map((i) => i.field);

describe("ranges are the spec's 5.1 table", () => {
  it("has the rectified-flow sigma ranges, not the drawing's k-diffusion ones (10 X6)", () => {
    expect(RANGES.sigma_min).toEqual({ min: 0.001, max: 0.5 });
    expect(RANGES.sigma_max).toEqual({ min: 0.01, max: 1 });
    expect(RANGES.rho).toEqual({ min: 0.1, max: 15 });
    expect(RANGES.lam_min).toEqual({ min: -12, max: 0 });
    expect(RANGES.lam_max).toEqual({ min: 0, max: 6 });
    expect(RANGES.plateaus).toEqual({ min: 2, max: 24, int: true });
    expect(RANGES.tilt).toEqual({ min: 0, max: 1 });
    expect(RANGES.steps).toEqual({ min: 1, max: 150, int: true });
    expect(RANGES.cfg_scale).toEqual({ min: 0, max: 64 });
    expect(RANGES.length_sec).toEqual({ min: 1, max: 184 });
    expect(RANGES.seed).toEqual({ min: 0, max: 999999, int: true });
    expect(RANGES.cfg_interval).toEqual({ min: 0, max: 1 });
    expect(RANGES.noise).toEqual({ min: 0, max: 1 });
    expect(RANGES.detune_cents).toEqual({ min: -100, max: 100, int: true });
  });

  it("knows the seven shapes", () => {
    expect(SCHEDULE_SHAPES).toEqual(
      ["model", "logsnr", "geometric", "linear", "log", "exponential", "cosine"],
    );
  });
});

describe("validateSchedule", () => {
  it("passes the default", () => {
    expect(validateSchedule(spec(), 1.0, "euler")).toEqual([]);
  });

  it("rejects an unknown shape", () => {
    expect(errs(spec({ shape: "karras" as ScheduleSpec["shape"] }))).toContain("shape");
  });

  it("rejects every out-of-range number", () => {
    expect(errs(spec({ rho: 0 }))).toContain("rho");
    expect(errs(spec({ rho: 15.1 }))).toContain("rho");
    expect(errs(spec({ sigma_min: 0.6 }))).toContain("sigma_min");
    expect(errs(spec({ lam_min: -13 }))).toContain("lam_min");
    expect(errs(spec({ lam_max: 7 }))).toContain("lam_max");
    expect(errs(spec({ plateaus: 1 }))).toContain("plateaus");
    expect(errs(spec({ tilt: 1.5 }))).toContain("tilt");
  });

  it("rejects a non-integer plateau count", () => {
    expect(errs(spec({ plateaus: 6.5 }))).toContain("plateaus");
  });

  it("requires sigma_min < sigma_max", () => {
    expect(errs(spec({ sigma_min: 0.4 }), 0.3)).toContain("sigma_min");
    expect(errs(spec({ sigma_min: 0.3 }), 0.3)).toContain("sigma_min");
    expect(errs(spec({ sigma_min: 0.2 }), 0.3)).toEqual([]);
  });

  it("requires lam_max > lam_min", () => {
    // 0/0 is the only violation both fields can express in range: lam_min is
    // -12..0 and lam_max is 0..6, so they meet only at zero.
    expect(errs(spec({ shape: "logsnr", lam_min: 0, lam_max: 0 }))).toContain("lam_max");
    expect(errs(spec({ shape: "logsnr", lam_min: -1, lam_max: 0 }))).not.toContain("lam_max");
  });

  it("refuses stepped + tilt 0 + dpmpp — h = 0 divides by zero and NaNs the latents", () => {
    const s = spec({ stepped: true, tilt: 0 });
    expect(errs(s, 1.0, "dpmpp")).toContain("tilt");
    expect(errs(s, 1.0, "euler")).toEqual([]);
    expect(errs(s, 1.0, "rk4")).toEqual([]);
  });

  it("checks sigma_min even on shapes that ignore it, because the server does", () => {
    expect(errs(spec({ shape: "logsnr", sigma_min: 0.9 }))).toContain("sigma_min");
  });
});

describe("the flat-plateau note (spec 5.3)", () => {
  it("is absent unless the plateaus really are flat", () => {
    expect(flatPlateauNote(spec(), "euler")).toBeNull();
    expect(flatPlateauNote(spec({ stepped: true, tilt: 0.15 }), "euler")).toBeNull();
    expect(flatPlateauNote(spec({ stepped: false, tilt: 0 }), "euler")).toBeNull();
  });

  it("warns on the ODE samplers", () => {
    const s = spec({ stepped: true, tilt: 0 });
    expect(flatPlateauNote(s, "euler")).toBe(FLAT_PLATEAU_NOTE);
    expect(flatPlateauNote(s, "rk4")).toBe(FLAT_PLATEAU_NOTE);
    expect(FLAT_PLATEAU_NOTE).toBe("flat plateaus are no-op steps on ODE samplers");
    // 5.3's exact wording, em dash included -- the pane shows it verbatim.
    expect(POST_CFG_NOTE).toBe("POST: guidance is distilled in \u2014 CFG is off");
  });

  it("says nothing for pingpong, which uses them as churn steps", () => {
    expect(flatPlateauNote(spec({ stepped: true, tilt: 0 }), "pingpong")).toBeNull();
  });

  it("is an error, not a note, on dpmpp — and the two agree", () => {
    const s = spec({ stepped: true, tilt: 0 });
    expect(flatPlateauNote(s, "dpmpp")).toBeNull();
    expect(errs(s, 1.0, "dpmpp")).toContain("tilt");
  });

  it("surfaces as a warning issue too, so one list can drive the UI", () => {
    const issues = validateSchedule(spec({ stepped: true, tilt: 0 }), 1.0, "euler");
    expect(issues).toEqual([
      { field: "tilt", severity: "warning", message: FLAT_PLATEAU_NOTE },
    ]);
  });
});
