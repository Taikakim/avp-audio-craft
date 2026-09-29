import { describe, expect, it } from "vitest";
import { clipSpanPx, pxToSec, secToPx } from "../viewport";

describe("secToPx / pxToSec are inverses of each other", () => {
  it("maps a timeline second to a screen pixel, offset by scroll", () => {
    expect(secToPx(10, 2, 80)).toBe(640);
    expect(secToPx(2, 2, 80)).toBe(0);
  });

  it("maps a screen pixel back to a timeline second", () => {
    expect(pxToSec(640, 2, 80)).toBeCloseTo(10, 10);
    expect(pxToSec(0, 2, 80)).toBeCloseTo(2, 10);
  });

  it("never returns a second before zero, even scrolled past the start", () => {
    expect(pxToSec(-1000, 2, 80)).toBe(0);
  });
});

describe("clipSpanPx", () => {
  it("gives left from secToPx and width from duration * pxPerSec", () => {
    expect(clipSpanPx(10, 4, 2, 80)).toEqual({ left: 640, width: 320 });
  });

  it("floors width at 1px so a near-zero clip still shows", () => {
    expect(clipSpanPx(0, 0.001, 0, 80)).toEqual({ left: 0, width: 1 });
  });
});
