import { describe, expect, it } from "vitest";
import type { ChromaResult } from "../chromaClient.svelte";
import {
  CONSONANCE_SCALE_LABEL,
  CURVE_SPAN_MIN,
  CURVE_TOP_PX,
  curveAxis,
  curveY,
  legendTicks,
  matchVerdict,
  windowScores,
} from "../matchCurve";

const ANCH = { unison: 1, fifth: 0.8, tritone: 0.4 };

function result(T: number, cls: number): ChromaResult {
  const fold12 = new Float32Array(12 * T);
  for (let t = 0; t < T; t++) fold12[cls * T + t] = 1;
  return { frames: T, fps: 10.7666015625, bands: new Float32Array(3 * 128 * T), fold12, T };
}

describe("the curve's y-axis is anchored to the target, not to the data (v3 1272-1276)", () => {
  it("spans from below the tritone anchor to above the unison anchor", () => {
    const axis = curveAxis(ANCH);
    expect(axis.lo).toBeLessThan(ANCH.tritone);
    expect(axis.hi).toBeGreaterThan(ANCH.unison);
  });

  it("keeps a minimum span so a degenerate target does not divide by zero", () => {
    const axis = curveAxis({ unison: 0.5, fifth: 0.5, tritone: 0.5 });
    expect(axis.hi - axis.lo).toBeGreaterThanOrEqual(CURVE_SPAN_MIN * 0.3);
    expect(Number.isFinite(curveY(0.5, axis, 120))).toBe(true);
  });

  it("maps a high score near the top of the canvas and a low one near the bottom", () => {
    const axis = curveAxis(ANCH);
    const hi = curveY(axis.hi, axis, 120);
    const lo = curveY(axis.lo, axis, 120);
    expect(hi).toBeLessThan(lo);
    expect(hi).toBeGreaterThanOrEqual(CURVE_TOP_PX);
    expect(lo).toBeLessThanOrEqual(120);
  });
});

describe("windowScores plots exactly the frames the heatmap is showing", () => {
  it("returns one score per visible frame, not per clip frame", () => {
    expect(windowScores(result(96, 0), Float32Array.from([1,0,0,0,0,0,0,0,0,0,0,0]), { from: 10, to: 20 }, 0))
      .toHaveLength(10);
  });

  it("scores a frame identical to the target at the unison anchor", () => {
    const target = Float32Array.from([1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]);
    const scores = windowScores(result(4, 0), target, { from: 0, to: 4 }, 0);
    expect(scores.every((s) => Math.abs(s - 1) < 1e-9)).toBe(true);
  });

  it("applies the ANALYSIS detune, so 100 cents rotates the frame a whole class", () => {
    // The argument is the analysis detune, not the clip's: it is 0 whenever
    // the chroma came from the already-stretched previewAudio, and only
    // carries the clip's detune when the chroma came from the raw source. 100
    // here is the raw-source case.
    const target = Float32Array.from([0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]);
    const at0 = windowScores(result(2, 0), target, { from: 0, to: 2 }, 0)[0];
    const at100 = windowScores(result(2, 0), target, { from: 0, to: 2 }, 100)[0];
    expect(at100).toBeGreaterThan(at0);
    expect(at100).toBeCloseTo(1, 9);
  });

  it("clamps a window that runs past the clip rather than reading out of bounds", () => {
    expect(windowScores(result(4, 0), Float32Array.from([1,0,0,0,0,0,0,0,0,0,0,0]), { from: -5, to: 99 }, 0))
      .toHaveLength(4);
  });
});

describe("legendTicks (v3 2029-2037: the three marks, sorted, clamped into the strip)", () => {
  it("is the three anchors in ascending order", () => {
    expect(legendTicks(ANCH).map((t) => t.label)).toEqual(["tritone", "fifth", "unison"]);
    expect(legendTicks(ANCH).map((t) => t.value)).toEqual([0.4, 0.8, 1]);
  });

  it("clamps each mark's position into 1..99 per cent so it stays on the strip", () => {
    const ticks = legendTicks({ unison: 5, fifth: 0.5, tritone: -3 });
    expect(ticks[0].pct).toBe(1);
    expect(ticks[2].pct).toBe(99);
  });
});

describe("matchVerdict (v3 2040-2044) says what a score means against this target", () => {
  it("names the band the score falls into", () => {
    expect(matchVerdict(1, ANCH)).toBe("at unison");
    expect(matchVerdict(0.85, ANCH)).toBe("above a fifth");
    expect(matchVerdict(0.6, ANCH)).toBe("between fifth and tritone");
    expect(matchVerdict(0.1, ANCH)).toBe("below a tritone");
  });
});

describe("the consonance scale label", () => {
  it("is a constant, because CONSONANCE COLOUR is always on (v3 729)", () => {
    expect(CONSONANCE_SCALE_LABEL).toBe("consonance colour");
  });
});
