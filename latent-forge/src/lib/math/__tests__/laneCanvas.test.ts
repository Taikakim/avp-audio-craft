import { describe, expect, it } from "vitest";
import type { Overlap } from "../../stores/arrangement.svelte";
import { darkenInk, isClipping, overlapSpansInLane } from "../laneCanvas";

describe("darkenInk (spec 4.3: overlapping ink at lightness × 0.75)", () => {
  it("scales each rgb channel by the given factor", () => {
    expect(darkenInk("rgb(200, 100, 40)", 0.75)).toBe("rgb(150, 75, 30)");
  });

  it("rounds to whole channel values", () => {
    expect(darkenInk("rgb(10, 11, 12)", 0.75)).toBe("rgb(8, 8, 9)");
  });

  it("passes an unparseable colour through unchanged", () => {
    expect(darkenInk("not-a-colour", 0.75)).toBe("not-a-colour");
  });

  // Every colour token in tokens.css is an UNREGISTERED custom property
  // written as oklch(...), so getComputedStyle hands back that literal
  // string, never a browser-normalised rgb() (downbeats.ts documents the
  // same fact for --downbeat). Scaling L/C/H as if they were R/G/B would
  // not compute "lightness × factor" -- these vectors are the actual inputs
  // LaneCanvas.svelte feeds this function (e.g. --lane1: oklch(54% 0.10 300)).
  describe("oklch() input (the real getComputedStyle shape in this app)", () => {
    it("scales only the lightness channel, keeping chroma and hue", () => {
      expect(darkenInk("oklch(54% 0.10 300)", 0.75)).toBe("oklch(40.50% 0.10 300)");
    });

    it("preserves an alpha component untouched", () => {
      expect(darkenInk("oklch(56% 0.11 150 / 0.10)", 0.75)).toBe("oklch(42.00% 0.11 150 / 0.10)");
    });

    it("rounds the lightness to two decimal places", () => {
      expect(darkenInk("oklch(78% 0.08 250)", 0.75)).toBe("oklch(58.50% 0.08 250)");
    });
  });
});

describe("isClipping (spec 4.3: red 2px marks where |x| > 1)", () => {
  it("flags a peak or trough beyond unity", () => {
    expect(isClipping(-0.5, 1.02)).toBe(true);
    expect(isClipping(-1.3, 0.4)).toBe(true);
  });

  it("passes ordinary peaks", () => {
    expect(isClipping(-0.9, 0.95)).toBe(false);
  });

  it("is exclusive at exactly 1", () => {
    expect(isClipping(-1, 1)).toBe(false);
  });
});

describe("overlapSpansInLane", () => {
  it("keeps only the requested lane's spans, dropping the clip ids", () => {
    const overlaps: Overlap[] = [
      { key: "a-b", lane: 0, start_sec: 1, end_sec: 2, a_id: "a", b_id: "b" },
      { key: "c-d", lane: 1, start_sec: 3, end_sec: 4, a_id: "c", b_id: "d" },
    ];
    expect(overlapSpansInLane(overlaps, 1)).toEqual([{ start_sec: 3, end_sec: 4 }]);
  });

  it("is empty when nothing overlaps in that lane", () => {
    expect(overlapSpansInLane([], 0)).toEqual([]);
  });
});
