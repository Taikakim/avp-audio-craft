import { describe, expect, it } from "vitest";
import { DETUNE_MAX, DETUNE_MIN, DETUNE_STEP, type DetuneScan } from "../detuneScan";
import {
  SCAN_H,
  SCAN_W,
  centsAtX,
  criterionLabel,
  criterionValues,
  nearestScanIndex,
  nextCriterion,
  scanLabel,
  scanRange,
  scanY,
  xForCents,
} from "../scanStrip";

function scan(mean: number[], sd: number[]): DetuneScan {
  const cents: number[] = [];
  for (let c = DETUNE_MIN; c <= DETUNE_MAX; c += DETUNE_STEP) cents.push(c);
  return { cents, mean, sd };
}

/** 51 flat points with one peak at the given index. */
function peakAt(i: number, sdAt = 0): DetuneScan {
  const mean = new Array(51).fill(0.5);
  const sd = new Array(51).fill(0);
  mean[i] = 0.9;
  sd[i] = sdAt;
  return scan(mean, sd);
}

describe("the strip's fixed geometry (v3 332)", () => {
  it("is the drawing's 500 x 30 canvas", () => {
    expect(SCAN_W).toBe(500);
    expect(SCAN_H).toBe(30);
  });
});

describe("pixels <-> cents across the ±100 range", () => {
  it("puts -100 at the left edge, 0 at the middle and +100 at the right", () => {
    expect(centsAtX(0, 500)).toBe(-100);
    expect(centsAtX(250, 500)).toBe(0);
    expect(centsAtX(500, 500)).toBe(100);
  });

  it("clamps a pointer that leaves the strip rather than running past ±100", () => {
    expect(centsAtX(-900, 500)).toBe(-100);
    expect(centsAtX(9000, 500)).toBe(100);
  });

  it("round-trips every one of the 51 grid points", () => {
    for (let c = DETUNE_MIN; c <= DETUNE_MAX; c += DETUNE_STEP) {
      expect(centsAtX(xForCents(c, 500), 500)).toBe(c);
    }
  });
});

describe("the criterion chooses which number the strip plots (spec §5.4)", () => {
  it("HIGHEST follows mean and STEADIEST follows mean - sd", () => {
    const s = scan(new Array(51).fill(0.6), new Array(51).fill(0.25));
    expect(criterionValues(s, "highest")[0]).toBeCloseTo(0.6, 9);
    expect(criterionValues(s, "steadiest")[0]).toBeCloseTo(0.35, 9);
  });

  it("labels itself as the drawing does and toggles between exactly two states", () => {
    expect(criterionLabel("highest")).toBe("HIGHEST");
    expect(criterionLabel("steadiest")).toBe("STEADIEST");
    expect(nextCriterion("highest")).toBe("steadiest");
    expect(nextCriterion("steadiest")).toBe("highest");
  });
});

describe("the vertical range (v3 1233: expand a flat curve rather than divide by zero)", () => {
  it("uses the data's own range when it is wide enough", () => {
    expect(scanRange([0.2, 0.8, 0.5])).toEqual({ lo: 0.2, hi: 0.8 });
  });

  it("opens a dead-flat curve out by 0.01 either way", () => {
    const r = scanRange([0.5, 0.5, 0.5]);
    expect(r.hi - r.lo).toBeCloseTo(0.02, 9);
    expect(Number.isFinite(scanY(0.5, r, 30))).toBe(true);
  });

  it("maps the range's top near the top of the strip and its floor near the bottom", () => {
    const r = { lo: 0, hi: 1 };
    expect(scanY(1, r, 30)).toBeLessThan(scanY(0, r, 30));
    expect(scanY(1, r, 30)).toBeGreaterThanOrEqual(0);
    expect(scanY(0, r, 30)).toBeLessThanOrEqual(30);
  });
});

describe("reading the curve at the clip's own detune", () => {
  it("snaps to the nearest of the 51 sampled steps", () => {
    const s = peakAt(25);
    expect(s.cents[nearestScanIndex(s, 0)]).toBe(0);
    expect(s.cents[nearestScanIndex(s, 2)]).toBe(0);
    expect(s.cents[nearestScanIndex(s, 3)]).toBe(4);
    expect(s.cents[nearestScanIndex(s, -100)]).toBe(-100);
  });

  it("reads out now / mean ± sd / peak, signing the peak, and names what the axis is relative to", () => {
    const s = peakAt(28, 0.1); // index 28 -> cents = -100 + 28*4 = 12
    // The axis is RELATIVE: 0 is the clip's own detune, so the strip always
    // reads "now 0¢" and the final clause says what 0 actually is.
    expect(scanLabel(s, 0, "highest", 0)).toBe(
      "now 0¢ · mean 0.50 ± 0.00 · peak +12¢ · ±100¢ relative to 0¢",
    );
    expect(scanLabel(s, 0, "highest", -30)).toBe(
      "now 0¢ · mean 0.50 ± 0.00 · peak +12¢ · ±100¢ relative to -30¢",
    );
  });

  it("reports a negative peak without a plus sign, and follows the criterion", () => {
    const s = peakAt(10, 0.6); // cents = -60; mean - sd = 0.3, below the 0.5 floor
    expect(scanLabel(s, -60, "highest", 20)).toBe(
      "now -60¢ · mean 0.90 ± 0.60 · peak -60¢ · ±100¢ relative to 20¢",
    );
    expect(scanLabel(s, -60, "steadiest", 20)).toBe(
      "now -60¢ · mean 0.90 ± 0.60 · peak -100¢ · ±100¢ relative to 20¢",
    );
  });
});
