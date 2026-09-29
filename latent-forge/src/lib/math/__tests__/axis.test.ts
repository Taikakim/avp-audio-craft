import { describe, expect, it } from "vitest";
import { linScale, niceTicks, xcorrCellSize } from "../axis";

describe("niceTicks picks round numbers that cover the domain", () => {
  it("ticks 0..10 in twos", () => {
    expect(niceTicks(0, 10, 5)).toEqual([0, 2, 4, 6, 8, 10]);
  });

  it("ticks a unit interval in fifths without floating-point dust", () => {
    expect(niceTicks(0, 1, 5)).toEqual([0, 0.2, 0.4, 0.6, 0.8, 1]);
  });

  it("ticks a symmetric correlation domain through zero", () => {
    expect(niceTicks(-1, 1, 5)).toEqual([-1, -0.5, 0, 0.5, 1]);
  });

  it("ticks a 256-dimension axis in hundreds", () => {
    expect(niceTicks(0, 255, 5)).toEqual([0, 100, 200, 300]);
  });

  it("degrades safely on an empty or non-finite domain", () => {
    expect(niceTicks(3, 3, 5)).toEqual([3]);
    expect(niceTicks(0, Number.NaN, 5)).toEqual([0]);
    expect(niceTicks(5, 1, 5)).toEqual([5]);
  });
});

describe("linScale maps a domain onto pixels", () => {
  it("maps ends and midpoint", () => {
    const s = linScale([0, 1], [0, 300]);
    expect(s(0)).toBe(0);
    expect(s(1)).toBe(300);
    expect(s(0.5)).toBe(150);
  });

  it("handles an inverted pixel range, which is how y axes are drawn", () => {
    const s = linScale([0, 1], [300, 0]);
    expect(s(0)).toBe(300);
    expect(s(1)).toBe(0);
  });

  it("puts a degenerate domain in the middle of the range instead of dividing by zero", () => {
    const s = linScale([2, 2], [0, 300]);
    expect(s(2)).toBe(150);
    expect(Number.isFinite(s(99))).toBe(true);
  });
});

describe("xcorrCellSize fits a 256x256 matrix into the panel", () => {
  it("is 1 px per cell in the 300 px panel of spec §4.4", () => {
    expect(xcorrCellSize(300, 256)).toBe(1);
  });

  it("grows to whole pixels when there is room", () => {
    expect(xcorrCellSize(512, 256)).toBe(2);
    expect(xcorrCellSize(1024, 256)).toBe(4);
  });

  it("never drops below 1 px, however small the panel", () => {
    expect(xcorrCellSize(10, 256)).toBe(1);
    expect(xcorrCellSize(0, 256)).toBe(1);
  });
});
