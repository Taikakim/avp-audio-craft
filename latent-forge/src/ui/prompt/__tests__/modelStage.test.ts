import { describe, expect, it, vi } from "vitest";
import { RANGES } from "../../../lib/sampling/scheduleRules";
import { randomSeed, stageConfirmMessage } from "../modelStage";

describe("randomSeed (spec 5.1's seed range, RANGES.seed)", () => {
  it("returns the range's minimum when rand returns 0", () => {
    expect(randomSeed(() => 0)).toBe(RANGES.seed.min);
  });

  it("returns the range's maximum when rand returns just under 1", () => {
    expect(randomSeed(() => 0.999999999)).toBe(RANGES.seed.max);
  });

  it("stays within range for a value in between", () => {
    const v = randomSeed(() => 0.5);
    expect(v).toBeGreaterThanOrEqual(RANGES.seed.min);
    expect(v).toBeLessThanOrEqual(RANGES.seed.max);
    expect(Number.isInteger(v)).toBe(true);
  });

  it("uses Math.random by default", () => {
    const spy = vi.spyOn(Math, "random").mockReturnValue(0);
    expect(randomSeed()).toBe(RANGES.seed.min);
    spy.mockRestore();
  });
});

describe("stageConfirmMessage (spec 5.3)", () => {
  it("is the spec's exact wording, unconditional on direction", () => {
    expect(stageConfirmMessage("POST")).toBe("rebuilds the model — continue?");
    expect(stageConfirmMessage("BASE")).toBe("rebuilds the model — continue?");
  });
});
