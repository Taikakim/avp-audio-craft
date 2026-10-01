import { describe, expect, it } from "vitest";
import { BINS_PER_SEMITONE } from "../bins";
import type { ChromaResult } from "../chromaClient.svelte";
import {
  BODY_Y,
  CHROMA_VIEWS,
  MIN_VISIBLE_FRAMES,
  REF_GAP,
  REF_ROW_H,
  VIEW_LABELS,
  bandIndexFor,
  cellValue,
  clampWindow,
  frameColumn,
  frameToX,
  fullWindow,
  rowCents,
  rowCount,
  rowHeight,
  rowPitchClass,
  rowToY,
  scrollWindow,
  xToFrame,
  yToRow,
  zoomWindow,
} from "../heatmapGeometry";

function result(T: number): ChromaResult {
  const bands = new Float32Array(3 * 128 * T);
  const fold12 = new Float32Array(12 * T);
  // A value that identifies all three coordinates it was read from.
  for (let b = 0; b < 3; b++) {
    for (let i = 0; i < 128; i++) {
      for (let t = 0; t < T; t++) bands[(b * 128 + i) * T + t] = (b + 1) / 10 + i / 1000 + t / 100000;
    }
  }
  for (let p = 0; p < 12; p++) for (let t = 0; t < T; t++) fold12[p * T + t] = p / 100 + t / 10000;
  return { frames: T, fps: 10.7666015625, bands, fold12, T };
}

describe("the four views spec §5.4 names", () => {
  it("is GLOBAL, BASS oct1, MID oct5, HIGH oct9 in the drawing's order (v3 2012-2015)", () => {
    expect(CHROMA_VIEWS).toEqual(["global", "bass", "mid", "high"]);
    expect(CHROMA_VIEWS.map((v) => VIEW_LABELS[v])).toEqual([
      "GLOBAL",
      "BASS oct1",
      "MID oct5",
      "HIGH oct9",
    ]);
  });

  it("maps the three band views onto bands 0, 1 and 2 and GLOBAL onto none", () => {
    expect(bandIndexFor("global")).toBe(null);
    expect(bandIndexFor("bass")).toBe(0);
    expect(bandIndexFor("mid")).toBe(1);
    expect(bandIndexFor("high")).toBe(2);
  });

  it("is 12 rows for GLOBAL and 128 for every band view", () => {
    expect(rowCount("global")).toBe(12);
    expect(rowCount("bass")).toBe(128);
    expect(rowCount("mid")).toBe(128);
    expect(rowCount("high")).toBe(128);
  });
});

describe("the reference row at the top (v3 1174: refH = 9, bodyY = refH + 2)", () => {
  it("is 9 px with a 2 px gap, so the body starts at 11", () => {
    expect(REF_ROW_H).toBe(9);
    expect(REF_GAP).toBe(2);
    expect(BODY_Y).toBe(11);
  });
});

describe("the visible frame window under middle-drag zoom/scroll (v3 331)", () => {
  it("starts as the whole clip", () => {
    expect(fullWindow(96)).toEqual({ from: 0, to: 96 });
  });

  it("never zooms in past MIN_VISIBLE_FRAMES and never out past the clip", () => {
    expect(zoomWindow({ from: 0, to: 96 }, 1000, 0.5, 96).to - zoomWindow({ from: 0, to: 96 }, 1000, 0.5, 96).from)
      .toBe(MIN_VISIBLE_FRAMES);
    expect(zoomWindow({ from: 20, to: 40 }, 0.001, 0.5, 96)).toEqual({ from: 0, to: 96 });
  });

  it("holds the anchored frame still while zooming in", () => {
    const w = zoomWindow({ from: 0, to: 96 }, 2, 0.5, 96);
    expect(w.to - w.from).toBeCloseTo(48, 9);
    expect(w.from + 0.5 * (w.to - w.from)).toBeCloseTo(48, 9);
  });

  it("scrolls so the content follows the hand, and stops at both ends", () => {
    expect(scrollWindow({ from: 40, to: 60 }, 50, 100, 96)).toEqual({ from: 30, to: 50 });
    expect(scrollWindow({ from: 0, to: 20 }, 500, 100, 96)).toEqual({ from: 0, to: 20 });
    expect(scrollWindow({ from: 76, to: 96 }, -500, 100, 96)).toEqual({ from: 76, to: 96 });
  });

  it("clamps a window wider than the clip, or one hanging off its end", () => {
    expect(clampWindow({ from: -10, to: 500 }, 40)).toEqual({ from: 0, to: 40 });
    expect(clampWindow({ from: 38, to: 44 }, 40)).toEqual({ from: 32, to: 40 });
  });
});

describe("frame <-> x over the visible window", () => {
  it("puts the window's first frame at x = 0 and its end at the right edge", () => {
    expect(frameToX(20, { from: 20, to: 40 }, 200)).toBe(0);
    expect(frameToX(40, { from: 20, to: 40 }, 200)).toBe(200);
    expect(frameToX(30, { from: 20, to: 40 }, 200)).toBe(100);
  });

  it("round-trips a pixel back to its frame, clamped inside the window", () => {
    expect(xToFrame(0, { from: 20, to: 40 }, 200)).toBe(20);
    expect(xToFrame(105, { from: 20, to: 40 }, 200)).toBe(30);
    expect(xToFrame(1e6, { from: 20, to: 40 }, 200)).toBe(39);
    expect(xToFrame(-50, { from: 20, to: 40 }, 200)).toBe(20);
  });
});

describe("row <-> y, with pitch class 0 (C) at the BOTTOM (v3 1184)", () => {
  it("spreads the rows over the body, below the reference row", () => {
    expect(rowHeight("global", 131)).toBeCloseTo(10, 9);
    expect(rowToY(0, "global", 131)).toBeCloseTo(BODY_Y + 110, 9);
    expect(rowToY(11, "global", 131)).toBeCloseTo(BODY_Y, 9);
  });

  it("reads a y back to its row and refuses the reference row entirely", () => {
    expect(yToRow(BODY_Y - 1, "global", 131)).toBe(null);
    expect(yToRow(BODY_Y + 0.5, "global", 131)).toBe(11);
    expect(yToRow(BODY_Y + 110.5, "global", 131)).toBe(0);
    expect(yToRow(1e6, "global", 131)).toBe(0);
  });
});

describe("row -> pitch class, honouring C at bin 2.0 (the same_chroma PITFALL)", () => {
  it("is the row itself in GLOBAL, which has no sub-semitone detail", () => {
    expect(rowPitchClass(0, "global")).toBe(0);
    expect(rowPitchClass(9, "global")).toBe(9);
    expect(rowCents(9, "global")).toBe(null);
  });

  it("puts C at bin 2 and A at bin 98 in a band view, not C at bin 0", () => {
    expect(rowPitchClass(2, "bass")).toBe(0);
    expect(rowPitchClass(98, "mid")).toBe(9);
    expect(rowCents(2, "bass")).toBe(0);
    expect(rowCents(98, "mid")).toBe(0);
  });

  it("reports cents off the class centre, wrapping over the top of the band", () => {
    expect(rowCents(3, "bass")).toBe(Math.round((1 / BINS_PER_SEMITONE) * 100));
    expect(rowCents(3, "bass")).toBe(9);
    expect(rowCents(124, "high")).toBe(44);   // B's centre is 119.333
    expect(rowCents(125, "high")).toBe(-47);  // C again, 5 bins below 2 + 128
  });
});

describe("cellValue reads the right axis out of a C-order payload", () => {
  it("takes GLOBAL directly from the transported fold12, not a local re-fold of bands", () => {
    // WINTERMUTE, 2026-09-22: §5.4's GLOBAL (the three bands summed through
    // fold_to_12, per-frame normalised to max 1) IS the server's transported
    // fold12 -- the client never re-derives it from `bands`. So this fixture's
    // fold12 (p/100 + t/10000, see result() above) is what cellValue must
    // return verbatim; there is no local normalisation left to assert on.
    const res = result(4);
    // 7 digits, not 9: fold12 is a Float32Array, so a hand-computed double differs by ~1e-9.
    const col = Array.from({ length: 12 }, (_, p) => cellValue(res, "global", 2, p));
    for (let p = 0; p < 12; p++) expect(col[p]).toBeCloseTo(p / 100 + 2 / 10000, 7);
  });

  it("takes a band view from that band's own 128 raw bins", () => {
    const res = result(4);
    expect(cellValue(res, "bass", 3, 7)).toBeCloseTo(0.1 + 7 / 1000 + 3 / 100000, 6);
    expect(cellValue(res, "mid", 3, 7)).toBeCloseTo(0.2 + 7 / 1000 + 3 / 100000, 6);
    expect(cellValue(res, "high", 3, 7)).toBeCloseTo(0.3 + 7 / 1000 + 3 / 100000, 6);
  });

  it("frameColumn folds the frame ONCE and agrees with cellValue row for row", () => {
    // The heatmap draws a whole column per frame, so the folding cellValue
    // does per row is repeated twelve times for one frame's worth of pixels.
    // frameColumn is the same numbers computed once -- pinned here so the two
    // paths can never drift apart.
    const res = result(4);
    const global = frameColumn(res, "global", 2);
    expect(global).toHaveLength(12);
    for (let r = 0; r < 12; r++) expect(global[r]).toBeCloseTo(cellValue(res, "global", 2, r), 9);
    const bass = frameColumn(res, "bass", 3);
    expect(bass).toHaveLength(128);
    for (let r = 0; r < 128; r++) expect(bass[r]).toBeCloseTo(cellValue(res, "bass", 3, r), 9);
  });
});
