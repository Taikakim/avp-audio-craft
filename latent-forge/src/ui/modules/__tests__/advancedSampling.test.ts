import { describe, expect, it } from "vitest";
import type { ScheduleIssue } from "../../../lib/sampling/scheduleRules";
import { fieldIssue, shapeUsesLambda } from "../advancedSampling";

describe("shapeUsesLambda (spec 5.3: lambda min/max are logsnr-only)", () => {
  it("is true only for logsnr", () => {
    expect(shapeUsesLambda("logsnr")).toBe(true);
  });

  it("is false for every other shape", () => {
    for (const s of ["model", "geometric", "linear", "log", "exponential", "cosine"]) {
      expect(shapeUsesLambda(s)).toBe(false);
    }
  });
});

describe("fieldIssue", () => {
  const issues: ScheduleIssue[] = [
    { field: "rho", severity: "error", message: "rho must be between 0.1 and 15" },
    { field: "tilt", severity: "warning", message: "flat plateaus are no-op steps on ODE samplers" },
  ];

  it("returns null when the field has no issue", () => {
    expect(fieldIssue(issues, "sigma_min")).toBeNull();
    expect(fieldIssue([], "rho")).toBeNull();
  });

  it("returns the matching issue's severity and message", () => {
    expect(fieldIssue(issues, "rho")).toEqual({ severity: "error", message: "rho must be between 0.1 and 15" });
    expect(fieldIssue(issues, "tilt")).toEqual({
      severity: "warning", message: "flat plateaus are no-op steps on ODE samplers",
    });
  });

  it("returns only the first match for a field", () => {
    const dup: ScheduleIssue[] = [
      { field: "rho", severity: "error", message: "first" },
      { field: "rho", severity: "warning", message: "second" },
    ];
    expect(fieldIssue(dup, "rho")).toEqual({ severity: "error", message: "first" });
  });
});
