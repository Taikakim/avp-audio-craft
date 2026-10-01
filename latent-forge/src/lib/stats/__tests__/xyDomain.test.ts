import { describe, expect, it } from "vitest";
import { domainOf, finitePoints } from "../xyDomain";

describe("finitePoints drops a point that is null on either axis at runtime", () => {
  it("keeps only points with a finite x and y", () => {
    const points = [
      { crop_id: "a", x: 1, y: 2, label: "a" },
      { crop_id: "b", x: null as unknown as number, y: 2, label: "b" },
      { crop_id: "c", x: 3, y: null as unknown as number, label: "c" },
      { crop_id: "d", x: Number.NaN, y: 4, label: "d" },
    ];
    expect(finitePoints(points)).toEqual([{ crop_id: "a", x: 1, y: 2, label: "a" }]);
  });

  it("passes through an already-clean list unchanged", () => {
    const points = [{ crop_id: "a", x: 1, y: 2, label: "a" }];
    expect(finitePoints(points)).toEqual(points);
  });
});

describe("domainOf", () => {
  it("returns [0, 1] furniture for an empty list", () => {
    expect(domainOf([], "x")).toEqual([0, 1]);
  });

  it("returns the min and max of the given axis", () => {
    const points = [
      { crop_id: "a", x: 5, y: -2, label: "a" },
      { crop_id: "b", x: 1, y: 9, label: "b" },
    ];
    expect(domainOf(points, "x")).toEqual([1, 5]);
    expect(domainOf(points, "y")).toEqual([-2, 9]);
  });

  it("collapses to a degenerate [v, v] domain when every value is identical -- linScale centres that, this never divides by zero", () => {
    const points = [
      { crop_id: "a", x: 7, y: 1, label: "a" },
      { crop_id: "b", x: 7, y: 1, label: "b" },
    ];
    expect(domainOf(points, "x")).toEqual([7, 7]);
  });

  it("handles a single point", () => {
    expect(domainOf([{ crop_id: "a", x: 3, y: 4, label: "a" }], "x")).toEqual([3, 3]);
  });
});
