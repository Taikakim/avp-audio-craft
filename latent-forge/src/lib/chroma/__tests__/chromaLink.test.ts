import { afterEach, describe, expect, it } from "vitest";
import { SCORE_PLACEHOLDER } from "../../math/clipBox";
import { chromaLink, clipScoreLabel, markerSecFor } from "../chromaLink.svelte";

afterEach(() => chromaLink.reset());

describe("the hover cross-link the lane canvas reads", () => {
  it("remembers which clip and how far into it, and forgets on clear", () => {
    chromaLink.setHover("clip-1", 0.25);
    expect(chromaLink.hover).toEqual({ clipId: "clip-1", frac: 0.25 });
    chromaLink.clearHover();
    expect(chromaLink.hover).toBe(null);
  });

  it("clamps a fraction that came from a pointer off the end of the canvas", () => {
    chromaLink.setHover("clip-1", 9);
    expect(chromaLink.hover!.frac).toBe(1);
    chromaLink.setHover("clip-1", -2);
    expect(chromaLink.hover!.frac).toBe(0);
  });
});

describe("markerSecFor (the red vertical line's position in the lane)", () => {
  it("is the clip's own start plus that fraction of its duration", () => {
    expect(markerSecFor({ start_sec: 8, dur_sec: 4 }, 0.5)).toBeCloseTo(10, 9);
    expect(markerSecFor({ start_sec: 8, dur_sec: 4 }, 0)).toBeCloseTo(8, 9);
    expect(markerSecFor({ start_sec: 8, dur_sec: 4 }, 1)).toBeCloseTo(12, 9);
  });
});

describe("the clip score label (spec §4.3, filling M5 T6's slot)", () => {
  it("falls back to M5's own placeholder for a clip nothing has analysed", () => {
    expect(clipScoreLabel(undefined)).toBe(SCORE_PLACEHOLDER);
    expect(SCORE_PLACEHOLDER).toBe("χ —");
  });

  it("shows the real mean frame match to two places, keeping the χ", () => {
    chromaLink.setScore("clip-1", 0.6234);
    expect(clipScoreLabel(chromaLink.scores["clip-1"])).toBe("χ 0.62");
  });

  it("drops a clip's score when its analysis is no longer valid", () => {
    chromaLink.setScore("clip-1", 0.5);
    chromaLink.clearScore("clip-1");
    expect(clipScoreLabel(chromaLink.scores["clip-1"])).toBe(SCORE_PLACEHOLDER);
  });

  it("reset clears both the hover and every score, so a test cannot leak into the next", () => {
    chromaLink.setHover("clip-1", 0.5);
    chromaLink.setScore("clip-1", 0.5);
    chromaLink.reset();
    expect(chromaLink.hover).toBe(null);
    expect(Object.keys(chromaLink.scores)).toEqual([]);
  });
});
