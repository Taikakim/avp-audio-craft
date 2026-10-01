import { describe, expect, it } from "vitest";
import { anchors, INTERVAL_W, matchFrame, MATCH_THRESHOLD, rotate } from "../match";

/** A 12-class profile from {class: value} pairs. */
function profile(entries: Record<number, number>): Float32Array {
  const out = new Float32Array(12);
  for (const [k, v] of Object.entries(entries)) out[Number(k)] = v;
  return out;
}

describe("the constants §5.4 pins", () => {
  it("is the twelve interval weights, in order, and a 0.08 threshold", () => {
    expect(Array.from(INTERVAL_W)).toEqual([
      1.0, 0.10, 0.35, 0.62, 0.70, 0.82, 0.18, 0.90, 0.66, 0.72, 0.30, 0.22,
    ]);
    expect(INTERVAL_W).toHaveLength(12);
    expect(MATCH_THRESHOLD).toBe(0.08);
  });
});

describe("matchFrame", () => {
  it("scores a frame identical to the target at the unison anchor", () => {
    const t = profile({ 0: 1.0, 4: 0.8, 7: 0.9 });
    expect(matchFrame(t, t)).toBe(anchors(t).unison);
    // 8 digits, not 10: profiles are Float32Array, so the sums carry ~1e-9 of float32 rounding
    // against the double-precision hand value (the anchors test below uses 8 for the same reason).
    expect(matchFrame(t, t)).toBeCloseTo(0.8300137174211248, 8);
  });

  it("reads INTERVAL_W by the distance between the two classes: 1.0, 0.90, 0.18", () => {
    // A single-class target makes the weight visible on its own: the frame a
    // fifth above reads INTERVAL_W[7] = 0.90 and the tritone INTERVAL_W[6] = 0.18.
    const t = profile({ 0: 1.0 });
    expect(matchFrame(profile({ 0: 1.0 }), t)).toBeCloseTo(1.0, 10);
    expect(matchFrame(profile({ 7: 1.0 }), t)).toBeCloseTo(0.90, 10);
    expect(matchFrame(profile({ 6: 1.0 }), t)).toBeCloseTo(0.18, 10);
    expect(matchFrame(profile({ 1: 1.0 }), t)).toBeCloseTo(0.10, 10);
    expect(matchFrame(profile({ 11: 1.0 }), t)).toBeCloseTo(0.22, 10);
  });

  it("counts nothing when the whole frame sits below the threshold", () => {
    const t = profile({ 0: 1.0, 7: 0.9 });
    const quiet = profile({ 0: 0.07, 4: 0.05, 7: 0.079 });
    expect(matchFrame(quiet, t)).toBe(0);
  });

  it("includes a class at exactly 0.08 and excludes one just below it", () => {
    const t = profile({ 0: 1.0 });
    // `profile` writes into a Float32Array, so 0.08 arrives as 0.079999998.
    // The guard compares against Math.fround(MATCH_THRESHOLD) for exactly this
    // reason -- against the float64 literal, this assertion returns 0.
    expect(matchFrame(profile({ 6: MATCH_THRESHOLD }), t)).toBeCloseTo(0.18, 10);
    expect(matchFrame(profile({ 6: 0.0799 }), t)).toBe(0);
    // and the same rule applies on the target side
    expect(matchFrame(profile({ 0: 1.0 }), profile({ 0: 0.0799 }))).toBe(0);
  });

  it("returns 0, not NaN, for an all-zero target", () => {
    const out = matchFrame(profile({ 0: 1.0 }), new Float32Array(12));
    expect(out).toBe(0);
    expect(Number.isNaN(out)).toBe(false);
  });

  it("rejects a frame that is not twelve classes long", () => {
    expect(() => matchFrame(new Float32Array(11), new Float32Array(12))).toThrow(/expected 12/);
    expect(() => matchFrame(new Float32Array(12), new Float32Array(13))).toThrow(/expected 12/);
  });
});

describe("rotate — cents/100 classes with a linear energy split", () => {
  it("is a pure permutation for a whole number of classes: no energy lost", () => {
    const f = profile({ 0: 1.0, 4: 0.8, 7: 0.9 });
    const r = rotate(f, 7);
    expect(Array.from(r).reduce((a, b) => a + b, 0)).toBeCloseTo(2.7, 6);
    expect(r[7]).toBeCloseTo(1.0, 6);
    expect(r[11]).toBeCloseTo(0.8, 6);
    expect(r[2]).toBeCloseTo(0.9, 6);   // 7 + 7 = 14 -> class 2
  });

  it("splits evenly between the two neighbours at half a class", () => {
    const f = profile({ 0: 1.0 });
    const r = rotate(f, 0.5);
    expect(r[0]).toBeCloseTo(0.5, 6);
    expect(r[1]).toBeCloseTo(0.5, 6);
    expect(Array.from(r).reduce((a, b) => a + b, 0)).toBeCloseTo(1.0, 6);
    const q = rotate(f, 0.25);
    expect(q[0]).toBeCloseTo(0.75, 6);
    expect(q[1]).toBeCloseTo(0.25, 6);
  });

  it("wraps downward for a negative rotation", () => {
    const f = profile({ 0: 1.0 });
    expect(rotate(f, -1)[11]).toBeCloseTo(1.0, 6);
    const r = rotate(f, -0.5);
    expect(r[11]).toBeCloseTo(0.5, 6);
    expect(r[0]).toBeCloseTo(0.5, 6);
  });

  it("copies at 0 classes and is the identity at 12", () => {
    const f = profile({ 0: 1.0, 3: 0.4 });
    const zero = rotate(f, 0);
    expect(Array.from(zero)).toEqual(Array.from(f));
    expect(zero).not.toBe(f);                       // never hands back the caller's array
    expect(Array.from(rotate(f, 12))).toEqual(Array.from(f));
  });
});

describe("anchors — the legend's three marks, the target against itself", () => {
  it("orders unison > fifth > tritone for a non-degenerate target", () => {
    const t = profile({ 0: 1.0, 4: 0.8, 7: 0.9 });
    const a = anchors(t);
    expect(a.unison).toBeCloseTo(0.8300137174211248, 8);
    expect(a.fifth).toBeCloseTo(0.6600823045267491, 8);
    expect(a.tritone).toBeCloseTo(0.30367626886145405, 8);
    expect(a.unison).toBeGreaterThan(a.fifth);
    expect(a.fifth).toBeGreaterThan(a.tritone);
  });

  it("is 1.0 / 0.90 / 0.18 for a single-class target, and all zero for an empty one", () => {
    const single = anchors(profile({ 0: 1.0 }));
    expect(single.unison).toBeCloseTo(1.0, 10);
    expect(single.fifth).toBeCloseTo(0.90, 10);
    expect(single.tritone).toBeCloseTo(0.18, 10);
    expect(anchors(new Float32Array(12))).toEqual({ unison: 0, fifth: 0, tritone: 0 });
  });
});
