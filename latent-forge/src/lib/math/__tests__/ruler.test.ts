import { describe, expect, it } from "vitest";
import {
  barNumberAt, frameAt, FRAME_HZ, middleDragScrollDeltaSec, middleDragZoomFactor,
  rulerTicks, secPerBar, secPerBeat,
} from "../ruler";

describe("meter arithmetic at 120 BPM 4/4", () => {
  it("gives beat 0.5s and bar 2s", () => {
    expect(secPerBeat(120)).toBeCloseTo(0.5, 12);
    expect(secPerBar(120, 4)).toBeCloseTo(2, 12);
  });

  it("follows a 3/4 meter", () => {
    expect(secPerBar(120, 3)).toBeCloseTo(1.5, 12);
  });

  it("numbers bars from 1", () => {
    expect(barNumberAt(0, 120, 4)).toBe(1);
    expect(barNumberAt(2, 120, 4)).toBe(2);
    expect(barNumberAt(3.9, 120, 4)).toBe(2);
    expect(barNumberAt(4, 120, 4)).toBe(3);
  });
});

describe("the latent frame clock (spec 4.3: FRAME_HZ = 44100/4096)", () => {
  it("is exactly 44100/4096", () => {
    expect(FRAME_HZ).toBeCloseTo(10.7666015625, 10);
  });

  it("floors to the frame a second falls in", () => {
    expect(frameAt(0)).toBe(0);
    expect(frameAt(1)).toBe(10);
  });
});

describe("rulerTicks thins beat lines below 8px (matches the drawing, v3 1038-1041)", () => {
  it("draws bar and beat ticks when beats are wide enough apart", () => {
    const ticks = rulerTicks(0, 2.1, 120, 4, 80); // beat = 0.5s * 80px/s = 40px
    expect(ticks.map((t) => t.kind)).toEqual(["bar", "beat", "beat", "beat", "bar"]);
    expect(ticks.map((t) => t.sec)).toEqual([0, 0.5, 1, 1.5, 2]);
  });

  it("drops to bar-only ticks once beats are under 8px", () => {
    const ticks = rulerTicks(0, 4.1, 120, 4, 10); // beat = 0.5s * 10px/s = 5px
    expect(ticks).toEqual([
      { sec: 0, kind: "bar" },
      { sec: 2, kind: "bar" },
      { sec: 4, kind: "bar" },
    ]);
  });
});

describe("the middle-drag gesture (spec 4.3: vertical zooms, horizontal scrolls, one gesture)", () => {
  it("zooms in on an upward drag (negative deltaY) and out on a downward one", () => {
    expect(middleDragZoomFactor(0)).toBe(1);
    expect(middleDragZoomFactor(-100)).toBeGreaterThan(1);
    expect(middleDragZoomFactor(100)).toBeLessThan(1);
  });

  it("scrolls left on a rightward drag (content follows the hand)", () => {
    expect(middleDragScrollDeltaSec(0, 80)).toBe(0);
    expect(middleDragScrollDeltaSec(80, 80)).toBe(-1);
    expect(middleDragScrollDeltaSec(-80, 80)).toBe(1);
  });
});
