import { describe, expect, it } from "vitest";
import { SIGMA_MAX_FIXED, chartableSigmaMax, sigmaMaxFor } from "../sigmaMax";

describe("sigma max is the pass's init noise level, not a schedule field", () => {
  it("is 1.0 for a fresh generate", () => {
    expect(sigmaMaxFor(null)).toBe(1.0);
    expect(SIGMA_MAX_FIXED).toBe(1.0);
  });

  it("is 1.0 for a clip whose A2A is off — the op starts from noise", () => {
    expect(sigmaMaxFor({ on: false, noise: 0.4 })).toBe(1.0);
  });

  it("is the clip's NOISE when A2A is on", () => {
    expect(sigmaMaxFor({ on: true, noise: 0.4 })).toBe(0.4);
  });

  it("does NOT clamp — the field must mirror NOISE exactly (5.1)", () => {
    expect(sigmaMaxFor({ on: true, noise: 0 })).toBe(0);
  });
});

describe("charting is where the floor lives, not the value", () => {
  it("has nothing to chart below the sigma max range", () => {
    expect(chartableSigmaMax(0)).toBeNull();
    expect(chartableSigmaMax(0.009)).toBeNull();
  });

  it("charts anything in range, capped at 1", () => {
    expect(chartableSigmaMax(0.01)).toBe(0.01);
    expect(chartableSigmaMax(0.4)).toBe(0.4);
    expect(chartableSigmaMax(1)).toBe(1);
  });
});
