import { describe, expect, it } from "vitest";
import {
  cfgBandFraction, formatCfgBound, progressAt, progressAtStep, stepAtProgress,
} from "../cfgInterval";

// sigma0 = 1, four steps: progress at each index is 0, 0.4, 0.7, 0.9, 1
const SIGMAS = [1, 0.6, 0.3, 0.1, 0];

describe("progressAt (spec 5.3: progress = 1 - sigma/sigma0)", () => {
  it("is 0 at the first index and 1 where sigma reaches 0", () => {
    expect(progressAt(SIGMAS, 0)).toBe(0);
    expect(progressAt(SIGMAS, 4)).toBe(1);
  });

  it("matches the intermediate steps", () => {
    expect(progressAt(SIGMAS, 1)).toBeCloseTo(0.4);
    expect(progressAt(SIGMAS, 2)).toBeCloseTo(0.7);
    expect(progressAt(SIGMAS, 3)).toBeCloseTo(0.9);
  });

  it("returns 0 for an empty array — the pane renders before the first response", () => {
    expect(progressAt([], 0)).toBe(0);
  });

  it("returns 0 for a single-element array", () => {
    expect(progressAt([0.7], 0)).toBe(0);
  });

  it("returns 0 for every index when sigma0 is 0 — an A2A clip at NOISE 0 has nothing to measure", () => {
    expect(progressAt([0, 0, 0], 0)).toBe(0);
    expect(progressAt([0, 0, 0], 2)).toBe(0);
  });

  it("clamps an out-of-range index to the array's own bounds", () => {
    expect(progressAt(SIGMAS, 99)).toBe(1);
    expect(progressAt(SIGMAS, -5)).toBe(0);
  });
});

describe("stepAtProgress (the drawing's _stepAtProgress, v3 1347-1351)", () => {
  it("finds the first step whose progress reaches p", () => {
    expect(stepAtProgress(SIGMAS, 0.5)).toBe(2);
  });

  it("returns 0 for p <= 0", () => {
    expect(stepAtProgress(SIGMAS, 0)).toBe(0);
  });

  it("returns the last index for p >= 1", () => {
    expect(stepAtProgress(SIGMAS, 1)).toBe(4);
  });

  it("clamps a negative p to 0 and a p above 1 to 1", () => {
    expect(stepAtProgress(SIGMAS, -0.3)).toBe(0);
    expect(stepAtProgress(SIGMAS, 1.5)).toBe(4);
  });

  it("returns 0 for an empty array", () => {
    expect(stepAtProgress([], 0.5)).toBe(0);
  });

  it("returns 0 for a single-element array", () => {
    expect(stepAtProgress([0.7], 0.5)).toBe(0);
  });
});

describe("progressAtStep", () => {
  it("agrees with progressAt for an in-range step", () => {
    expect(progressAtStep(SIGMAS, 2)).toBe(progressAt(SIGMAS, 2));
  });

  it("clamps a step index beyond the array's own length", () => {
    expect(progressAtStep(SIGMAS, 50)).toBe(1);
  });
});

describe("formatCfgBound", () => {
  it("formats progress to two decimals", () => {
    expect(formatCfgBound(SIGMAS, 0.5, "progress")).toBe("0.50");
  });

  it("formats the steps unit as the crossing step index", () => {
    expect(formatCfgBound(SIGMAS, 0.5, "steps")).toBe("2");
  });

  it("does not clamp the progress display — a caller feeding it 1.5 sees 1.50", () => {
    expect(formatCfgBound(SIGMAS, 1.5, "progress")).toBe("1.50");
  });
});

describe("cfgBandFraction", () => {
  it("returns the 0..1 x-fractions the graph fills", () => {
    expect(cfgBandFraction(SIGMAS, 0, 1)).toEqual({ lo: 0, hi: 1 });
    expect(cfgBandFraction(SIGMAS, 0.5, 0.9)).toEqual({ lo: 0.5, hi: 0.75 });
  });

  it("returns {lo:0, hi:0} for an empty array", () => {
    expect(cfgBandFraction([], 0, 1)).toEqual({ lo: 0, hi: 0 });
  });

  it("returns {lo:0, hi:0} for a single-element array, which has no band to draw", () => {
    expect(cfgBandFraction([0.7], 0, 1)).toEqual({ lo: 0, hi: 0 });
  });
});

describe("a stored progress is never converted into a stored step (spec 5.3)", () => {
  it("round-tripping a progress through the step unit loses precision — why storage stays in progress", () => {
    const p = 0.5;
    const roundTripped = progressAtStep(SIGMAS, stepAtProgress(SIGMAS, p));
    expect(roundTripped).not.toBe(p);
    expect(roundTripped).toBeCloseTo(0.7);
  });
});
