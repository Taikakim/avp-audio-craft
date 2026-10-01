import { describe, expect, it } from "vitest";
import {
  BANDS,
  BINS_PER_BAND,
  BINS_PER_SEMITONE,
  C_BIN,
  NOTE_NAMES,
  binToPitchClass,
  fold12Column,
  fold12Columns,
  foldTo12,
  pitchClassToBin,
  semitoneBinCenters,
} from "../bins";

describe("the bin geometry spec §5.4 pins", () => {
  it("is 128 bins per band, 3 bands, 128/12 bins per semitone, C at bin 2.0", () => {
    expect(BINS_PER_BAND).toBe(128);
    expect(BANDS).toBe(3);
    expect(BINS_PER_SEMITONE).toBe(128 / 12);
    expect(BINS_PER_SEMITONE).toBeCloseTo(10.666666666666666, 12);
    expect(C_BIN).toBe(2.0);
  });

  it("puts C at bin 2.0 and A at 98, with twelve centres all inside the band", () => {
    const c = semitoneBinCenters();
    expect(c).toHaveLength(12);
    expect(c[0]).toBe(2.0);      // C
    expect(c[3]).toBe(34.0);     // D#
    expect(c[6]).toBe(66.0);     // F#
    expect(c[9]).toBe(98.0);     // A
    for (const v of c) {
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThan(BINS_PER_BAND);
    }
    // A fresh array every call: a caller may not mutate the module's own table.
    expect(semitoneBinCenters()).not.toBe(c);
  });

  it("spaces the centres 128/12 apart, C# at 12.667 and B at 119.333", () => {
    const c = semitoneBinCenters();
    for (let s = 1; s < 12; s++) {
      expect(c[s] - c[s - 1]).toBeCloseTo(BINS_PER_SEMITONE, 10);
    }
    expect(c[1]).toBeCloseTo(12.666666666666666, 10);
    expect(c[11]).toBeCloseTo(119.33333333333333, 10);
  });

  it("names the twelve pitch classes with sharp spellings, C first", () => {
    expect(NOTE_NAMES).toEqual(["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]);
  });
});

describe("binToPitchClass and its inverse", () => {
  it("maps every centre back to its own pitch class", () => {
    const c = semitoneBinCenters();
    for (let s = 0; s < 12; s++) expect(binToPitchClass(c[s])).toBe(s);
  });

  it("round-trips pitchClassToBin -> binToPitchClass for all twelve classes", () => {
    const c = semitoneBinCenters();
    for (let s = 0; s < 12; s++) {
      expect(pitchClassToBin(s)).toBe(c[s]);
      expect(binToPitchClass(pitchClassToBin(s))).toBe(s);
    }
  });

  it("folds bin 2.0 to class 0, and bin 0 with it", () => {
    expect(binToPitchClass(2.0)).toBe(0);
    expect(binToPitchClass(0)).toBe(0);
    expect(binToPitchClass(7)).toBe(0);      // still inside C's half-semitone
    expect(binToPitchClass(8)).toBe(1);      // 7.333 is the C/C# boundary
  });

  it("wraps at the top of the band: the boundary is 124.667, so 124 is B and 125..127 are C again", () => {
    // B's centre is 119.333; C's next centre is 2.0 + 128 = 130. The midpoint
    // is 2.0 + 11.5*(128/12) = 124.6667, so every bin above it is nearer to C
    // going UP over the top of the band than to B going down.
    expect(2.0 + 11.5 * (128 / 12)).toBeCloseTo(124.66666666666667, 10);
    expect(binToPitchClass(124)).toBe(11);
    expect(binToPitchClass(125)).toBe(0);
    expect(binToPitchClass(126)).toBe(0);
    expect(binToPitchClass(127)).toBe(0);
  });

  it("breaks an exact tie to the LOWER pitch class, as the reference fold_to_12's argmin does", () => {
    // Bins 18, 50, 82 and 114 are the only four of the 128 that sit exactly halfway
    // between two centres (5.3333 from each). numpy's argmin keeps the first,
    // so they belong to C# and G -- Math.round() would send both the other way.
    expect(binToPitchClass(18)).toBe(1);
    expect(binToPitchClass(82)).toBe(7);
    expect(Math.round((18 - C_BIN) / BINS_PER_SEMITONE)).toBe(2);   // the trap
    expect(Math.round((82 - C_BIN) / BINS_PER_SEMITONE)).toBe(8);   // the trap
  });
});

describe("foldTo12 — one band of 128 bins to 12 classes", () => {
  it("sums each bin into its nearest class: an all-ones band folds to the per-class bin counts", () => {
    const band = new Float32Array(128).fill(1);
    const out = foldTo12(band);
    expect(Array.from(out)).toEqual([11, 11, 10, 11, 11, 10, 11, 11, 10, 11, 11, 10]);
    expect(Array.from(out).reduce((a, b) => a + b, 0)).toBe(128);
  });

  it("puts a single hot bin entirely in one class", () => {
    const band = new Float32Array(128);
    band[66] = 0.5;                                   // F#'s centre
    const out = foldTo12(band);
    expect(out[6]).toBeCloseTo(0.5, 6);
    expect(Array.from(out).filter((v) => v !== 0)).toHaveLength(1);
  });

  it("throws when the band is not binsPerBand long", () => {
    expect(() => foldTo12(new Float32Array(127))).toThrow(/expected 128 bins/);
  });
});

describe("fold12Column / fold12Columns — the server's [12,T] fold", () => {
  it("reads class p, frame t as fold12[p*T + t]", () => {
    const T = 3;
    const fold12 = new Float32Array(12 * T);
    for (let p = 0; p < 12; p++) for (let t = 0; t < T; t++) fold12[p * T + t] = p + t / 10;
    const col1 = fold12Column(fold12, T, 1);
    expect(col1).toHaveLength(12);
    expect(col1[0]).toBeCloseTo(0.1, 6);
    expect(col1[11]).toBeCloseTo(11.1, 6);
    const cols = fold12Columns(fold12, T);
    expect(cols).toHaveLength(3);
    expect(Array.from(cols[2])).toEqual(Array.from(fold12Column(fold12, T, 2)));
    expect(() => fold12Column(fold12, T, 3)).toThrow(/frame 3 out of range/);
  });
});
