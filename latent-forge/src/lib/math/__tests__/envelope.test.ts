import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import type { Envelope } from "../../forge/types";
import { envelopeGeometry, nodeDragValue, sampleEnvelope, segmentDragValue } from "../envelope";

const FLAT: Envelope = { points: [0.4, 0.4, 0.4, 0.4], curves: [0, 0, 0] };

describe("geometry (spec §5.2, exact port of _envelope, v3 1583-1596)", () => {
  it("places the four nodes at the spec's x positions and y(v) = 90 - 80v", () => {
    const geo = envelopeGeometry({ points: [0, 0.5, 1, 0.25], curves: [0, 0, 0] });
    expect(geo.nodes.map((n) => n.x)).toEqual([0, 133.33, 266.67, 400]);
    expect(geo.nodes.map((n) => n.y)).toEqual([90, 50, 10, 70]);
  });

  it("puts each segment's control point at the chord midpoint, offset by -curve*60", () => {
    const geo = envelopeGeometry({ points: [0, 1, 1, 1], curves: [1, -1, 0] });
    // segment 0: (0,90)-(133.33,10), midpoint (66.665,50), curve 1 -> cy = 50-60 = -10
    expect(geo.segments[0]).toEqual({ x1: 0, y1: 90, cx: 66.665, cy: -10, x2: 133.33, y2: 10 });
    // segment 1: (133.33,10)-(266.67,10), midpoint (200,10), curve -1 -> cy = 10+60 = 70
    expect(geo.segments[1]).toEqual({ x1: 133.33, y1: 10, cx: 200, cy: 70, x2: 266.67, y2: 10 });
  });

  it("builds the single visible path exactly as _envelope's `d` string", () => {
    const geo = envelopeGeometry(FLAT);
    expect(geo.pathD).toBe("M 0,58 Q 66.665,58 133.33,58 Q 200,58 266.67,58 Q 333.335,58 400,58 ");
  });
});

describe("sampleEnvelope (spec §5.2)", () => {
  it("is flat regardless of n when every point and curve is flat", () => {
    // Float32Array can't hold 0.4 losslessly (it round-trips as
    // 0.4000000059604645), so this checks per-element closeness like every
    // other sampleEnvelope assertion below, not exact equality.
    const got = Array.from(sampleEnvelope(FLAT, 5));
    expect(got).toHaveLength(5);
    for (const v of got) expect(v).toBeCloseTo(0.4, 6);
    expect(sampleEnvelope(FLAT, 1)[0]).toBeCloseTo(0.4, 6);
  });

  it("is piecewise-linear when every curve is 0 (the control point is the chord midpoint)", () => {
    const env: Envelope = { points: [0, 1 / 3, 2 / 3, 1], curves: [0, 0, 0] };
    const got = Array.from(sampleEnvelope(env, 4));
    expect(got[0]).toBeCloseTo(0, 5);
    expect(got[1]).toBeCloseTo(1 / 3, 5);
    expect(got[2]).toBeCloseTo(2 / 3, 5);
    expect(got[3]).toBeCloseTo(1, 5);
  });

  it("bulges toward a bent segment's curve, evaluated at the segment's own midpoint", () => {
    // points [0,1,1,1], curve[0] = 1: segment 0 control y = -10 (see geometry test above).
    // n=7 -> x = k/6; k=1 gives x=1/6, which is s=0.5 of segment 0.
    const env: Envelope = { points: [0, 1, 1, 1], curves: [1, 0, 0] };
    const got = sampleEnvelope(env, 7);
    expect(got[0]).toBeCloseTo(0, 6);
    expect(got[1]).toBeCloseTo(0.875, 6);
    expect(got[6]).toBeCloseTo(1, 6);
  });

  it("clamps to [0,1] even if a bend would overshoot", () => {
    const env: Envelope = { points: [1, 1, 1, 1], curves: [1, 0, 0] };
    // segment 0 control y = 10 - 1*60 = -50 -> raw v at s=0.5 would be 1.375
    const got = sampleEnvelope(env, 7);
    expect(got[1]).toBe(1);
  });
});

describe("shared vectors with the server -- TS and Python must agree (spec §5.2)", () => {
  const vectorPath = fileURLToPath(
    new URL("../../../../../docs/latent-forge/contract/vectors/envelope.json", import.meta.url),
  );
  if (!existsSync(vectorPath)) {
    it.skip("vector file not recorded yet", () => {});
  } else {
    // The server's write_vectors.py (M2 T3) names the envelope key `env`; this test used to read
    // `envelope`, so the first time the file existed it threw on undefined.points. The generated file
    // is the contract (spec 5.2), so the reader follows it. (Electro-Sheep 1, 2026-10-01)
    const vectors = JSON.parse(readFileSync(vectorPath, "utf-8")) as {
      name?: string; env: Envelope; n: number; values: number[];
    }[];
    it("matches every recorded (envelope, n) -> values vector", () => {
      for (const v of vectors) {
        const got = sampleEnvelope(v.env, v.n);
        for (let k = 0; k < v.n; k++) expect(got[k]).toBeCloseTo(v.values[k], 5);
      }
    });
  }
});

describe("node and segment drag value math (spec §5.2)", () => {
  it("node: v = clamp((90 - (clientY-top)/height*100)/80, 0, 1)", () => {
    expect(nodeDragValue(232.48, 200, 56)).toBeCloseTo(0.4, 9);
    expect(nodeDragValue(200, 200, 56)).toBe(1); // pointer at the very top -> clamped at 1
    expect(nodeDragValue(256, 200, 56)).toBe(0); // pointer at the very bottom -> clamped at 0
  });

  it("segment: c = clamp(c_start + (startY-clientY)/60, -1, 1)", () => {
    expect(segmentDragValue(0, 300, 330)).toBeCloseTo(-0.5, 9);
    expect(segmentDragValue(0, 300, 240)).toBe(1); // clamped at the top
    expect(segmentDragValue(0, 300, 360)).toBe(-1); // clamped at the bottom
  });
});
