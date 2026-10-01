import { describe, expect, it } from "vitest";
import { isQuad, mixTree, normalizedQuadWeights } from "../mixMath";

describe("mixTree (spec §4.5/§8.1 S7)", () => {
  it("tree: M1=(L1,L2), M2=(L3,L4), MX=(M1,M2)", () => {
    expect(mixTree("tree")).toEqual([
      { id: "M1", a: "L1", b: "L2" },
      { id: "M2", a: "L3", b: "L4" },
      { id: "MX", a: "M1", b: "M2" },
    ]);
  });

  it("cascade: M1=(L1,L2), M2=(M1,L3), MX=(M2,L4)", () => {
    expect(mixTree("cascade")).toEqual([
      { id: "M1", a: "L1", b: "L2" },
      { id: "M2", a: "M1", b: "L3" },
      { id: "MX", a: "M2", b: "L4" },
    ]);
  });

  it("quad has no intermediate node tree", () => {
    expect(mixTree("quad")).toBeNull();
  });
});

describe("isQuad", () => {
  it("is true only for the weighted 4-way order", () => {
    expect(isQuad("quad")).toBe(true);
    expect(isQuad("tree")).toBe(false);
    expect(isQuad("cascade")).toBe(false);
  });
});

describe("normalizedQuadWeights (spec §8.1 S7's own fallback)", () => {
  it("normalises to fractions summing to 1", () => {
    expect(normalizedQuadWeights([1, 1, 1, 1])).toEqual([0.25, 0.25, 0.25, 0.25]);
    expect(normalizedQuadWeights([2, 2, 0, 0])).toEqual([0.5, 0.5, 0, 0]);
  });

  it("falls back to equal weights when every weight is zero", () => {
    expect(normalizedQuadWeights([0, 0, 0, 0])).toEqual([0.25, 0.25, 0.25, 0.25]);
  });
});
