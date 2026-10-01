import { describe, expect, it } from "vitest";
import type { LatchSlot } from "../../forge/types";
import {
  LANE_H, PAD, reservedHeight, sigmaGraphGeometry,
} from "../sigmaGraph";
import type { SigmaGraphInput } from "../sigmaGraph";

const SIGMAS = [1, 0.6, 0.3, 0.1, 0]; // sigma0=1, 4 steps

// start_pct/end_pct chosen as exact binary fractions (0.25, 0.75, 0.5) throughout this file so
// every expected x0/w below is an exact integer, never a 0.1-plus-0.2-style rounding artefact.
function slot(over: Partial<LatchSlot> = {}): LatchSlot {
  return { head: "onsets", kind: "value", value: 0.5, weight: 1, start_pct: 0.25, end_pct: 0.75, ...over };
}

function input(over: Partial<SigmaGraphInput> = {}): SigmaGraphInput {
  return {
    sigmas: SIGMAS, steps: 4, cfgLo: 0, cfgHi: 1, stepped: false, scalePhi: 0,
    slots: [], width: 100, height: 118, ...over,
  };
}

describe("reservedHeight (drawing's RESERVED = 2*LANE_H + LANE_GAP + 2)", () => {
  it("is 18 for zero, one or two slots alike — it reserves for two lanes unconditionally", () => {
    expect(reservedHeight(0)).toBe(18);
    expect(reservedHeight(1)).toBe(18);
    expect(reservedHeight(2)).toBe(18);
  });
});

describe("sigmaGraphGeometry with no slots, a full-width CFG band, no rescale", () => {
  const g = sigmaGraphGeometry(input());

  it("computes plotHeight by subtracting the two-lane reservation from height", () => {
    expect(g.plotHeight).toBe(100);
  });

  it("samples the sigma curve by nearest-index lookup, one point per pixel column", () => {
    expect(g.sigmaPath).toHaveLength(101);
    expect(g.sigmaPath[0]).toEqual({ x: 0, y: 4 });
    expect(g.sigmaPath[100]).toEqual({ x: 100, y: 96 });
  });

  it("computes the progress curve as the sigma curve's mirror image", () => {
    expect(g.progressPath[0]).toEqual({ x: 0, y: 96 });
    expect(g.progressPath[100]).toEqual({ x: 100, y: 4 });
  });

  it("places one tick per step, capped, at the step's own sigma value", () => {
    expect(g.ticks).toHaveLength(5);
    expect(g.ticks[0]).toEqual({ x: 0, y: 4 });
    expect(g.ticks[2]).toEqual({ x: 50, y: 68.4 });
    expect(g.ticks[4]).toEqual({ x: 100, y: 96 });
  });

  it("fills the CFG band across the whole width when the interval is [0,1]", () => {
    expect(g.cfgBand).toEqual({ x0: 0, x1: 100 });
  });

  it("reports rescaleY null when scale_phi is 0", () => {
    expect(g.rescaleY).toBeNull();
  });

  it("carries the step count as the label", () => {
    expect(g.stepLabel).toBe("4");
  });
});

describe("sigmaGraphGeometry with an active LatCH slot", () => {
  it("places the slot's band at its own start/end fraction of the width", () => {
    const g = sigmaGraphGeometry(input({ cfgLo: 0.5, cfgHi: 1, slots: [slot()] }));
    expect(g.slotBands).toHaveLength(1);
    expect(g.slotBands[0].index).toBe(0);
    expect(g.slotBands[0].x0).toBe(25);
    expect(g.slotBands[0].w).toBe(50);
    expect(g.slotBands[0].laneY).toBe(102);
  });

  it("hatches only the intersection of the slot's window and the CFG band", () => {
    const g = sigmaGraphGeometry(input({ cfgLo: 0.5, cfgHi: 1, slots: [slot()] }));
    expect(g.slotBands[0].hatch).toEqual({ x0: 50, w: 25 });
  });

  it("omits an inert slot (head none or weight 0)", () => {
    const g = sigmaGraphGeometry(input({ slots: [slot({ head: "none" }), slot({ weight: 0 })] }));
    expect(g.slotBands).toEqual([]);
  });

  it("keeps the same plotHeight whether zero, one or two slots are active", () => {
    const none = sigmaGraphGeometry(input({ slots: [] }));
    const one = sigmaGraphGeometry(input({ slots: [slot()] }));
    const two = sigmaGraphGeometry(input({ slots: [slot(), slot({ start_pct: 0, end_pct: 0.1 })] }));
    expect(one.plotHeight).toBe(none.plotHeight);
    expect(two.plotHeight).toBe(none.plotHeight);
  });
});

describe("sigmaGraphGeometry, stepped vs continuous", () => {
  it("adds a vertical jump between pixel columns when stepped", () => {
    const g = sigmaGraphGeometry(input({ stepped: true }));
    expect(g.sigmaPath.length).toBeGreaterThan(101);
    const hasJump = g.sigmaPath.some((p, i) => i > 0 && p.x === g.sigmaPath[i - 1].x && p.y !== g.sigmaPath[i - 1].y);
    expect(hasJump).toBe(true);
  });

  it("draws a smooth line with no repeated x when not stepped", () => {
    const g = sigmaGraphGeometry(input({ stepped: false }));
    expect(g.sigmaPath).toHaveLength(101);
    const xs = g.sigmaPath.map((p) => p.x);
    expect(new Set(xs).size).toBe(xs.length);
  });
});

describe("sigmaGraphGeometry, rescale line", () => {
  it("places rescaleY proportionally to scale_phi", () => {
    const g = sigmaGraphGeometry(input({ scalePhi: 0.25 }));
    expect(g.rescaleY).toBe(73);
  });

  it("is null for scale_phi <= 0", () => {
    expect(sigmaGraphGeometry(input({ scalePhi: 0 })).rescaleY).toBeNull();
    expect(sigmaGraphGeometry(input({ scalePhi: -0.1 })).rescaleY).toBeNull();
  });
});

describe("sigmaGraphGeometry, empty input", () => {
  it("returns empty paths and no crash for an empty sigmas array", () => {
    const g = sigmaGraphGeometry(input({ sigmas: [] }));
    expect(g.sigmaPath).toEqual([]);
    expect(g.progressPath).toEqual([]);
    expect(g.ticks).toEqual([]);
    expect(g.slotBands).toEqual([]);
    expect(g.cfgBand).toEqual({ x0: 0, x1: 0 });
  });
});
