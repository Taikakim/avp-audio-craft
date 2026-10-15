import { describe, expect, it } from "vitest";
import {
  CURVE_MAX, CURVE_MIN, CURVE_SHAPES, N_BLOCKS, clampValue, drawSegment, flatCurve, invertCurve, isFlatOne,
  scaleCurve, smoothCurve, soloCurve,
} from "../curves";

describe("curve shapes", () => {
  it("every shape has 24 values inside the range", () => {
    for (const s of CURVE_SHAPES) {
      const c = s.make();
      expect(c, s.id).toHaveLength(N_BLOCKS);
      expect(c.every((v) => v >= CURVE_MIN && v <= CURVE_MAX), s.id).toBe(true);
    }
  });
  it("has the spec's shapes", () => {
    expect(CURVE_SHAPES.map((s) => s.id)).toEqual([
      "flat", "early_ramp_down", "late_ramp_down", "middle_bell", "ascending_exp", "descending_exp",
      "early_only", "last8_off", "alternating",
    ]);
  });
  it("early ramp-down falls 1 -> 0 and last-8-off zeroes blocks 16..23", () => {
    const r = CURVE_SHAPES.find((s) => s.id === "early_ramp_down")!.make();
    expect(r[0]).toBe(1); expect(r[23]).toBe(0);
    const l = CURVE_SHAPES.find((s) => s.id === "last8_off")!.make();
    expect(l.slice(0, 16).every((v) => v === 1) && l.slice(16).every((v) => v === 0)).toBe(true);
  });
  it("solo lights exactly one block", () => {
    const s = soloCurve(5);
    expect(s.filter((v) => v === 1)).toHaveLength(1);
    expect(s[5]).toBe(1);
  });
});

describe("transforms", () => {
  it("invert mirrors around 0.5 and clamps", () => {
    expect(invertCurve(flatCurve(1))).toEqual(flatCurve(0));
    expect(invertCurve(flatCurve(-0.5))[0]).toBe(CURVE_MAX);
  });
  it("scale clamps into the range", () => {
    expect(scaleCurve(flatCurve(1), 2)).toEqual(flatCurve(1.5));
  });
  it("smooth keeps length and averages neighbours", () => {
    const c = soloCurve(10);
    const s = smoothCurve(c);
    expect(s).toHaveLength(N_BLOCKS);
    expect(s[10]).toBeCloseTo(1 / 3);
    expect(s[9]).toBeCloseTo(1 / 3);
  });
  it("clampValue bounds", () => {
    expect(clampValue(9)).toBe(CURVE_MAX);
    expect(clampValue(-9)).toBe(CURVE_MIN);
  });
});

describe("drawSegment (freehand drag)", () => {
  it("fills skipped columns with a straight line", () => {
    const c = drawSegment(flatCurve(1), 2, 0, 6, 1);
    expect(c.slice(2, 7)).toEqual([0, 0.25, 0.5, 0.75, 1]);
    expect(c[1]).toBe(1);
    expect(c[7]).toBe(1);
  });
  it("works right-to-left and clamps", () => {
    const c = drawSegment(flatCurve(1), 6, 3, 2, -3);
    expect(c[6]).toBe(CURVE_MAX);
    expect(c[2]).toBe(CURVE_MIN);
  });
  it("does not mutate its input", () => {
    const base = flatCurve(1);
    drawSegment(base, 0, 0, 23, 0);
    expect(isFlatOne(base)).toBe(true);
  });
});
