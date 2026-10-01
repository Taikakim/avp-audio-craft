import { describe, expect, it } from "vitest";
import { frameOf, segments } from "../timeseriesGeometry";

describe("frameOf maps a resampled sample onto the n_frames axis, not values.length (spec §6.5)", () => {
  it("spreads samples evenly across n_frames when the server has resampled down", () => {
    expect(frameOf(0, 5, 1000)).toBe(0);
    expect(frameOf(4, 5, 1000)).toBe(999);
    expect(frameOf(2, 5, 1000)).toBeCloseTo(499.5, 5);
  });

  it("is exact when values.length already equals n_frames", () => {
    expect(frameOf(3, 10, 10)).toBe(3);
  });

  it("returns 0 for a single sample or a degenerate n_frames, rather than dividing by zero", () => {
    expect(frameOf(0, 1, 1000)).toBe(0);
    expect(frameOf(0, 5, 1)).toBe(0);
    expect(frameOf(0, 5, 0)).toBe(0);
  });
});

describe("segments breaks the line at a null -- a gap, never a zero (spec §6.5)", () => {
  it("returns one run for a gap-free series", () => {
    expect(segments([1, 2, 3])).toEqual([[[0, 1], [1, 2], [2, 3]]]);
  });

  it("splits into two runs around one null", () => {
    expect(segments([1, 2, null, 4, 5])).toEqual([[[0, 1], [1, 2]], [[3, 4], [4, 5]]]);
  });

  it("returns no runs for an all-null series (a feature the latent lacks)", () => {
    expect(segments([null, null, null])).toEqual([]);
  });

  it("drops a leading and trailing null without an empty run", () => {
    expect(segments([null, 1, 2, null])).toEqual([[[1, 1], [2, 2]]]);
  });

  it("treats a single non-null sample as its own one-point run", () => {
    expect(segments([null, 5, null])).toEqual([[[1, 5]]]);
  });
});
