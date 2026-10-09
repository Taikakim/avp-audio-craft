import { describe, expect, it } from "vitest";
import {
  clamp, decimalsFor, DRAG_PX_PER_RANGE, dragRaw, dragValue, hasMoved, INERTIA_AUTO_MS, inertiaMs,
  MAX_DRAG_RANGE, MOVE_THRESHOLD_PX, quantize, settleDistance, SHIFT_FACTOR,
} from "../dragScale";

describe("the constants of spec §5.1", () => {
  it("is 260 px per full range, 1 px of slop, 1% under shift", () => {
    expect(DRAG_PX_PER_RANGE).toBe(260);
    expect(MOVE_THRESHOLD_PX).toBe(1);
    expect(SHIFT_FACTOR).toBe(0.01);
  });
});

describe("decimals: dec = clamp(3 - floor(log10(|range| || 1)), 0, 4)", () => {
  it("gives each field range of the spec table its own precision", () => {
    expect(decimalsFor(60, 200)).toBe(1);       // project / clip BPM, range 140
    expect(decimalsFor(0, 64)).toBe(2);         // CFG, range 64
    expect(decimalsFor(0, 1)).toBe(3);          // CFG LO/HI progress, tilt, rescale, noise
    expect(decimalsFor(0.001, 0.5)).toBe(4);    // sigma min, range 0.499 -> clamped at 4
    expect(decimalsFor(0.01, 1)).toBe(4);       // sigma max, range 0.99 -> log10 is still negative
    expect(decimalsFor(0.1, 15)).toBe(2);       // rho, range 14.9
    expect(decimalsFor(1, 184)).toBe(1);        // length s, range 183
    expect(decimalsFor(-24, 24)).toBe(2);       // semitones, range 48
    expect(decimalsFor(-12, 0)).toBe(2);        // lambda min, range 12
  });

  it("gives integer fields zero decimals", () => {
    expect(decimalsFor(1, 150, true)).toBe(0);  // steps
    expect(decimalsFor(0, 999999, true)).toBe(0); // seed
    expect(decimalsFor(2, 24, true)).toBe(0);   // plateaus
    expect(decimalsFor(-100, 100, true)).toBe(0); // detune cents
  });

  it("treats a zero range as 1", () => {
    expect(decimalsFor(5, 5)).toBe(3);
  });
});

describe("dragValue", () => {
  it("moves the full range over 260 px", () => {
    // BPM 60..200, range 140; half the drag distance is half the range
    expect(dragValue({ startVal: 120, dx: DRAG_PX_PER_RANGE / 2, min: 60, max: 200 })).toBe(190);
    expect(dragValue({ startVal: 120, dx: -DRAG_PX_PER_RANGE / 2, min: 60, max: 200 })).toBe(60);
  });

  it("goes 100x finer with shift, at dec + 2 decimals capped at 5", () => {
    expect(dragValue({ startVal: 120, dx: 130, min: 60, max: 200, shift: true })).toBe(120.7);
    // sigma min: dec is already 4, so shift rounds at 5 decimals, not 6.
    // raw = 0.25 + (100/260)*0.499*0.01 = 0.2519192... -> 0.25192 at 5, 0.251919 at 6
    expect(dragValue({ startVal: 0.25, dx: 100, min: 0.001, max: 0.5, shift: true })).toBe(0.25192);
  });

  it("clamps at both ends", () => {
    expect(dragValue({ startVal: 120, dx: 10000, min: 60, max: 200 })).toBe(200);
    expect(dragValue({ startVal: 120, dx: -10000, min: 60, max: 200 })).toBe(60);
  });

  it("rounds integer fields to whole numbers", () => {
    // steps 1..150, range 149; 26 px = 0.1 of the range = 14.9 steps
    expect(dragValue({ startVal: 24, dx: 26, min: 1, max: 150, int: true })).toBe(39);
    expect(dragValue({ startVal: 24, dx: -26, min: 1, max: 150, int: true })).toBe(9);
  });

  it("returns the start value for a zero drag", () => {
    expect(dragValue({ startVal: 24, dx: 0, min: 1, max: 150, int: true })).toBe(24);
    expect(dragValue({ startVal: 0.15, dx: 0, min: 0, max: 1 })).toBe(0.15);
  });
});

describe("the moved flag", () => {
  it("needs strictly more than 1 px", () => {
    expect(hasMoved(0)).toBe(false);
    expect(hasMoved(1)).toBe(false);
    expect(hasMoved(-1)).toBe(false);
    expect(hasMoved(1.5)).toBe(true);
    expect(hasMoved(-4)).toBe(true);
  });
});

describe("clamp", () => {
  it("bounds both ways and passes the middle through", () => {
    expect(clamp(-1, 0, 1)).toBe(0);
    expect(clamp(2, 0, 1)).toBe(1);
    expect(clamp(0.5, 0, 1)).toBe(0.5);
  });
});

describe("wide ranges (SEED 0..999999)", () => {
  it("never maps more than MAX_DRAG_RANGE onto one drag, so a pixel is a few seeds and not thousands", () => {
    expect(MAX_DRAG_RANGE).toBe(5000);
    // 26 px is a tenth of the 260 px drag: 500 seeds, where the old rule gave 99 999
    expect(dragValue({ startVal: 1000, dx: 26, min: 0, max: 999999, int: true })).toBe(1500);
    expect(dragRaw({ startVal: 0, dx: 260, min: 0, max: 999999 })).toBe(5000);
  });

  it("leaves every range of the spec table alone", () => {
    expect(dragRaw({ startVal: 120, dx: 130, min: 60, max: 200 })).toBe(190);
    expect(dragRaw({ startVal: 24, dx: 26, min: 1, max: 150 })).toBeCloseTo(38.9, 5);
  });

  it("still clamps to the field's own range", () => {
    expect(dragValue({ startVal: 999000, dx: 5000, min: 0, max: 999999, int: true })).toBe(999999);
    expect(dragValue({ startVal: 10, dx: -5000, min: 0, max: 999999, int: true })).toBe(0);
  });

  it("dragValue is quantize(dragRaw)", () => {
    const i = { startVal: 24, dx: 26, min: 1, max: 150, int: true };
    expect(dragValue(i)).toBe(quantize(dragRaw(i), i));
  });
});

describe("inertia", () => {
  it("glides only on ranges wider than 1 000 unless a field asks for it", () => {
    expect(inertiaMs({ min: 0, max: 999999 })).toBe(INERTIA_AUTO_MS);
    expect(inertiaMs({ min: 1, max: 184 })).toBe(0);
    expect(inertiaMs({ min: 0, max: 1000 })).toBe(0);
    expect(inertiaMs({ min: 0, max: 64, inertia: 120 })).toBe(120);
    expect(inertiaMs({ min: 0, max: 999999, inertia: 0 })).toBe(0);
    expect(inertiaMs({ min: 0, max: 64, inertia: -5 })).toBe(0);
  });

  it("settles within half a unit on integers and 0.01 % of the range otherwise", () => {
    expect(settleDistance(0, 999999, true)).toBe(0.5);
    expect(settleDistance(0, 64)).toBeCloseTo(0.0064, 10);
  });
});
