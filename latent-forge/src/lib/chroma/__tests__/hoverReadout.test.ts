import { describe, expect, it } from "vitest";
import type { ChromaResult } from "../chromaClient.svelte";
import {
  HOVER_DETAIL_PX,
  HOVER_NOTE_PX,
  hoverDetailText,
  hoverNoteText,
  readHover,
} from "../hoverReadout";

/** C loud everywhere; G a little quieter; bass band has its energy at bin 2. */
function result(T: number): ChromaResult {
  const bands = new Float32Array(3 * 128 * T);
  const fold12 = new Float32Array(12 * T);
  for (let t = 0; t < T; t++) {
    bands[(0 * 128 + 2) * T + t] = 0.8;
    fold12[0 * T + t] = 1;
    fold12[7 * T + t] = 0.5;
  }
  return { frames: T, fps: 10.7666015625, bands, fold12, T };
}

const TARGET = Float32Array.from([1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0]);

const base = {
  result: result(96),
  target: TARGET,
  win: { from: 0, to: 96 },
  widthPx: 480,
  heightPx: 131,
  detuneCents: 0,
};

describe("the two readout sizes spec §5.4 pins", () => {
  it("is a 14 px note over a 9 px detail (v3 339-340)", () => {
    expect(HOVER_NOTE_PX).toBe(14);
    expect(HOVER_DETAIL_PX).toBe(9);
  });
});

describe("readHover turns a pointer into a frame and a pitch class", () => {
  it("reads the frame from x across the visible window", () => {
    const h = readHover({ ...base, view: "global", x: 240, y: 60 })!;
    expect(h.frame).toBe(48);
    expect(h.frames).toBe(96);
  });

  it("refuses the reference row, which is the target's and not the clip's", () => {
    expect(readHover({ ...base, view: "global", x: 240, y: 3 })).toBe(null);
  });

  it("reads the class from y, with C at the bottom", () => {
    const h = readHover({ ...base, view: "global", x: 0, y: 130 })!;
    expect(h.pitchClass).toBe(0);
    expect(h.cents).toBe(null);
    expect(h.value).toBeCloseTo(1, 6);
  });

  it("reads a band view's own bin, with its cents off the class centre", () => {
    const h = readHover({ ...base, view: "bass", x: 0, y: 131 - ((131 - 11) / 128) * 2.5 })!;
    expect(h.pitchClass).toBe(0);
    expect(h.cents).toBe(0);
    expect(h.value).toBeCloseTo(0.8, 6);
  });

  it("names the frame's strongest class and its own match, at the ANALYSIS detune", () => {
    // `detuneCents` is the detune NOT already in the analysed audio: 0 for the
    // usual stretched-preview case, the clip's own only when the chroma came
    // from the raw source. 100 below is that second case.
    const h = readHover({ ...base, view: "global", x: 0, y: 130 })!;
    expect(h.top).toBe(0);
    expect(h.topValue).toBeCloseTo(1, 6);
    expect(h.match).toBeGreaterThan(0);
    const rotated = readHover({ ...base, view: "global", x: 0, y: 130, detuneCents: 100 })!;
    expect(rotated.match).not.toBeCloseTo(h.match, 6);
  });

  it("gives the frame's time from the latent frame rate, not from the clip's length", () => {
    const h = readHover({ ...base, view: "global", x: 240, y: 60 })!;
    expect(h.sec).toBeCloseTo(48 / 10.7666015625, 6);
  });
});

describe("the two readout strings (v3 1968-1973)", () => {
  it("is note, cents when a band view has them, then the value", () => {
    const flat = readHover({ ...base, view: "global", x: 0, y: 130 })!;
    expect(hoverNoteText(flat)).toBe("C  1.00");
    const banded = { ...flat, cents: 9, value: 0.8 };
    expect(hoverNoteText(banded)).toBe("C +9¢  0.80");
    expect(hoverNoteText({ ...flat, cents: -12 })).toBe("C -12¢  1.00");
  });

  it("is strongest / match / frame (1-based) / seconds", () => {
    const h = readHover({ ...base, view: "global", x: 240, y: 60 })!;
    expect(hoverDetailText(h)).toBe(
      `strongest C 1.00 · match ${h.match.toFixed(2)} · frame 49/96 · ${h.sec.toFixed(2)} s`,
    );
  });
});
