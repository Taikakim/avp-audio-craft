import { describe, expect, it } from "vitest";
import { clipFrameRange, markerSecFor } from "../chromaLink.svelte";
import { meanMatchAtDetune } from "../detuneScan";

// Review 2026-10-01: the hover marker and the clip score ignored the clip's trim.
describe("markerSecFor with a trimmed clip", () => {
  const clip = { start_sec: 100, dur_sec: 10, offset_sec: 30 };
  it("maps file seconds through offset_sec", () => {
    expect(markerSecFor(clip, 0, 35)).toBeCloseTo(105, 9);
  });
  it("returns null for a file position the clip does not play", () => {
    expect(markerSecFor(clip, 0, 10)).toBeNull();
    expect(markerSecFor(clip, 0, 41)).toBeNull();
  });
  it("keeps the untrimmed fallback when no file seconds are known", () => {
    expect(markerSecFor({ start_sec: 2, dur_sec: 4 }, 0.5)).toBe(4);
  });
});

describe("clip score over the played frames only", () => {
  it("clipFrameRange covers offset .. offset + dur", () => {
    expect(clipFrameRange({ offset_sec: 1, dur_sec: 2 }, 100, 10)).toEqual([10, 30]);
    expect(clipFrameRange({ offset_sec: 0, dur_sec: 50 }, 100, 10)).toEqual([0, 100]);
  });
  it("meanMatchAtDetune averages only the range", () => {
    const T = 4;
    const fold12 = new Float32Array(12 * T);
    fold12[0 * T + 0] = 1; fold12[0 * T + 1] = 1;   // frames 0-1: C
    fold12[1 * T + 2] = 1; fold12[1 * T + 3] = 1;   // frames 2-3: C#
    const target = Float32Array.from([1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]);
    const all = meanMatchAtDetune(fold12, T, target, 0);
    const firstHalf = meanMatchAtDetune(fold12, T, target, 0, [0, 2]);
    expect(firstHalf).toBeGreaterThan(all);
    expect(meanMatchAtDetune(fold12, T, target, 0, [0, T])).toBeCloseTo(all, 9);
  });
});
