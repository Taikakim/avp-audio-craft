import { describe, expect, it } from "vitest";
import { gridIntervalSec, MAGNET_PX, snapDelta, snapSec, SNAP_MODES } from "../snap";

// 120 BPM, 4/4 -> beat 0.5 s, bar 2 s. 80 px/s -> the 5 px magnet is 0.0625 s.
const ctx = { bpm: 120, beatsPerBar: 4, pxPerSec: 80, edges: [] as number[], magnets: [] as number[] };

describe("the snap menu is the spec 4.3 list, in order", () => {
  it("offers eight modes with downbeats magnetic among them", () => {
    expect(SNAP_MODES.map((m) => m.value)).toEqual(
      ["bar", "beat", "1/8", "1/16", "1/32", "lane", "edge", "free"],
    );
    expect(SNAP_MODES.find((m) => m.value === "lane")!.label).toBe("downbeats (magnetic)");
  });
});

describe("grid intervals at 120 BPM 4/4", () => {
  it("computes each division from the meter", () => {
    expect(gridIntervalSec("bar", 120, 4)).toBeCloseTo(2, 12);
    expect(gridIntervalSec("beat", 120, 4)).toBeCloseTo(0.5, 12);
    expect(gridIntervalSec("1/8", 120, 4)).toBeCloseTo(0.25, 12);
    expect(gridIntervalSec("1/16", 120, 4)).toBeCloseTo(0.125, 12);
    expect(gridIntervalSec("1/32", 120, 4)).toBeCloseTo(0.0625, 12);
  });

  it("has no interval for the non-grid modes", () => {
    expect(gridIntervalSec("lane", 120, 4)).toBeNull();
    expect(gridIntervalSec("edge", 120, 4)).toBeNull();
    expect(gridIntervalSec("free", 120, 4)).toBeNull();
  });

  it("follows a 3/4 meter", () => {
    expect(gridIntervalSec("bar", 120, 3)).toBeCloseTo(1.5, 12);
  });
});

describe("grid snapping rounds to the nearest division", () => {
  it("pulls 1.3 s to the bar at 2 s, and 2.9 s back to 2 s", () => {
    expect(snapSec(1.3, "bar", ctx)).toBeCloseTo(2, 12);
    expect(snapSec(2.9, "bar", ctx)).toBeCloseTo(2, 12);
    expect(snapSec(3.1, "bar", ctx)).toBeCloseTo(4, 12);
  });

  it("never returns a negative position", () => {
    expect(snapSec(-3, "bar", ctx)).toBe(0);
    expect(snapSec(-3, "free", ctx)).toBe(0);
  });

  it("leaves free mode untouched", () => {
    expect(snapSec(1.234567, "free", ctx)).toBeCloseTo(1.234567, 12);
  });
});

describe("clip-edge snapping is magnetic, not absolute", () => {
  const withEdges = { ...ctx, edges: [0, 4.0, 9.5] };

  it("snaps to an edge inside the tolerance", () => {
    expect(snapSec(4.04, "edge", withEdges)).toBeCloseTo(4.0, 12);
  });

  it("lets go once dragged past it", () => {
    expect(snapSec(4.5, "edge", withEdges)).toBeCloseTo(4.5, 12);
  });

  it("widens in seconds as you zoom out", () => {
    const zoomedOut = { ...withEdges, pxPerSec: 8 };   // 5 px = 0.625 s
    expect(snapSec(4.4, "edge", zoomedOut)).toBeCloseTo(4.0, 12);
  });
});

describe("downbeats (magnetic) is the spec's default mode", () => {
  const withMagnets = { ...ctx, magnets: [2.0, 6.0] };

  it("jumps to another lane's downbeat within 5 px", () => {
    expect(snapSec(2.05, "lane", withMagnets)).toBeCloseTo(2.0, 12);
  });

  it("pulls free when dragged further", () => {
    expect(snapSec(2.4, "lane", withMagnets)).toBeCloseTo(2.4, 12);
  });

  it("chooses the nearer of two magnets", () => {
    const close = { ...ctx, magnets: [2.0, 2.05], pxPerSec: 8 };
    expect(snapSec(2.04, "lane", close)).toBeCloseTo(2.05, 12);
  });

  it("falls through to free when there is nothing to snap to", () => {
    expect(snapSec(3.333, "lane", ctx)).toBeCloseTo(3.333, 12);
  });
});

describe("snapDelta reports what happened, for the magnet indicator", () => {
  it("names the target it locked onto", () => {
    expect(snapDelta(2.05, "lane", { ...ctx, magnets: [2.0] })).toEqual({ sec: 2.0, snapped: true, to: 2.0 });
  });

  it("reports no snap when it let go", () => {
    const r = snapDelta(2.4, "lane", { ...ctx, magnets: [2.0] });
    expect(r.snapped).toBe(false);
    expect(r.to).toBeNull();
  });

  it("MAGNET_PX is the spec's 5", () => {
    expect(MAGNET_PX).toBe(5);
  });
});
