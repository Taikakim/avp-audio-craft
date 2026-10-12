import { describe, expect, it } from "vitest";
import { xcorrCellAt } from "../xcorrHover";

describe("xcorrCellAt maps a pixel to its (row, col) -- spec §4.4's hover readout", () => {
  it("maps the top-left pixel to (0, 0)", () => {
    expect(xcorrCellAt(0, 0, 150, 2)).toEqual({ row: 0, col: 0 });
  });

  it("maps a pixel in the second cell on each axis", () => {
    expect(xcorrCellAt(160, 10, 150, 2)).toEqual({ row: 0, col: 1 });
    expect(xcorrCellAt(10, 160, 150, 2)).toEqual({ row: 1, col: 0 });
  });

  it("returns null past the grid's edge, even inside a larger panel", () => {
    expect(xcorrCellAt(310, 10, 150, 2)).toBeNull();
    expect(xcorrCellAt(10, 310, 150, 2)).toBeNull();
  });

  it("returns null for a negative offset", () => {
    expect(xcorrCellAt(-1, 0, 150, 2)).toBeNull();
  });

  it("returns null for a non-finite or non-positive cell size or n", () => {
    expect(xcorrCellAt(10, 10, 0, 2)).toBeNull();
    expect(xcorrCellAt(10, 10, 150, 0)).toBeNull();
    expect(xcorrCellAt(10, 10, Number.NaN, 2)).toBeNull();
  });

  it("is exact at a cell boundary -- the boundary pixel belongs to the next cell", () => {
    expect(xcorrCellAt(150, 0, 150, 2)).toEqual({ row: 0, col: 1 });
    expect(xcorrCellAt(149, 0, 150, 2)).toEqual({ row: 0, col: 0 });
  });
});
