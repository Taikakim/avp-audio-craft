import { describe, expect, it } from "vitest";
import { parseChord, setProfile, targetProfile } from "../target";

function profile(entries: Record<number, number>): Float32Array {
  const out = new Float32Array(12);
  for (const [k, v] of Object.entries(entries)) out[Number(k)] = v;
  return out;
}

/** The set of pitch classes a parse turned on, sorted. */
function classesOf(keys: boolean[] | null): number[] {
  expect(keys).not.toBeNull();
  return keys!.flatMap((on, p) => (on ? [p] : []));
}

describe("targetProfile — lane mode", () => {
  it("sums the 12-class folds over frames, then normalises to max 1", () => {
    const out = targetProfile([
      profile({ 0: 0.5, 7: 0.1 }),
      profile({ 0: 0.5, 4: 0.2 }),
      profile({ 7: 0.4 }),
    ]);
    // sums: C 1.0, E 0.2, G 0.5 -> max is C, so divide by 1.0
    expect(out[0]).toBeCloseTo(1.0, 6);
    expect(out[4]).toBeCloseTo(0.2, 6);
    expect(out[7]).toBeCloseTo(0.5, 6);
    expect(Math.max(...Array.from(out))).toBeCloseTo(1.0, 6);
  });

  it("normalises by the summed maximum, not by the per-frame one", () => {
    const out = targetProfile([profile({ 0: 0.25 }), profile({ 0: 0.25 }), profile({ 4: 0.4 })]);
    // sums: C 0.5, E 0.4 -> /0.5
    expect(out[0]).toBeCloseTo(1.0, 6);
    expect(out[4]).toBeCloseTo(0.8, 6);
  });

  it("gives an all-zero profile for a lane with no clips, not NaN", () => {
    const out = targetProfile([]);
    expect(Array.from(out)).toEqual(new Array(12).fill(0));
    expect(Array.from(out).every(Number.isFinite)).toBe(true);
  });

  it("gives an all-zero profile for all-zero frames rather than dividing by zero", () => {
    const out = targetProfile([new Float32Array(12), new Float32Array(12)]);
    expect(Array.from(out)).toEqual(new Array(12).fill(0));
    expect(Array.from(out).every(Number.isFinite)).toBe(true);
  });

  it("rejects a frame that is not twelve classes long", () => {
    expect(() => targetProfile([new Float32Array(11)])).toThrow(/expected 12/);
  });
});

describe("setProfile — SEMITONE SET mode", () => {
  it("turns the twelve toggles into a flat 1/0 profile", () => {
    const keys = new Array(12).fill(false);
    keys[0] = true;
    keys[3] = true;
    keys[7] = true;
    const out = setProfile(keys);
    expect(Array.from(out)).toEqual([1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0]);
    expect(out).toBeInstanceOf(Float32Array);
  });

  it("rejects a key row that is not twelve long", () => {
    expect(() => setProfile([true, false])).toThrow(/expected 12/);
  });
});

describe("parseChord — the nine qualities §5.4 lists", () => {
  it("parses each quality on C", () => {
    expect(classesOf(parseChord("C"))).toEqual([0, 4, 7]);
    expect(classesOf(parseChord("Cm"))).toEqual([0, 3, 7]);
    expect(classesOf(parseChord("C7"))).toEqual([0, 4, 7, 10]);
    expect(classesOf(parseChord("Cmaj7"))).toEqual([0, 4, 7, 11]);
    expect(classesOf(parseChord("Cm7"))).toEqual([0, 3, 7, 10]);
    expect(classesOf(parseChord("Cdim"))).toEqual([0, 3, 6]);
    expect(classesOf(parseChord("Caug"))).toEqual([0, 4, 8]);
    expect(classesOf(parseChord("Csus2"))).toEqual([0, 2, 7]);
    expect(classesOf(parseChord("Csus4"))).toEqual([0, 5, 7]);
  });

  it("transposes every quality to all twelve roots", () => {
    const naturals: Record<string, number> = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
    const qualities: [string, number[]][] = [
      ["", [0, 4, 7]], ["m", [0, 3, 7]], ["7", [0, 4, 7, 10]], ["maj7", [0, 4, 7, 11]],
      ["m7", [0, 3, 7, 10]], ["dim", [0, 3, 6]], ["aug", [0, 4, 8]],
      ["sus2", [0, 2, 7]], ["sus4", [0, 5, 7]],
    ];
    for (const [letter, base] of Object.entries(naturals)) {
      for (const accidental of ["", "#", "b"]) {
        const root = (base + (accidental === "#" ? 1 : accidental === "b" ? -1 : 0) + 12) % 12;
        for (const [q, ivs] of qualities) {
          const expected = ivs.map((i) => (root + i) % 12).sort((a, b) => a - b);
          expect(classesOf(parseChord(`${letter}${accidental}${q}`)), `${letter}${accidental}${q}`)
            .toEqual(expected);
        }
      }
    }
  });

  it("gives Db and C#, and Bb7 and A#7, the same keys", () => {
    expect(parseChord("Db")).toEqual(parseChord("C#"));
    expect(parseChord("Bb7")).toEqual(parseChord("A#7"));
    expect(classesOf(parseChord("F#m"))).toEqual([1, 6, 9]);
    expect(classesOf(parseChord("Gbm"))).toEqual([1, 6, 9]);
  });

  it("wraps E# to F and Cb to B rather than failing on the spelling", () => {
    expect(parseChord("E#")).toEqual(parseChord("F"));
    expect(parseChord("Cb")).toEqual(parseChord("B"));
    expect(parseChord("B#m7")).toEqual(parseChord("Cm7"));
  });

  it("takes the root letter in either case and lowercases the quality", () => {
    expect(parseChord("c")).toEqual(parseChord("C"));
    expect(parseChord("f#M7")).toEqual(parseChord("F#m7"));   // see Open questions
    expect(parseChord("bbSUS4")).toEqual(parseChord("Bbsus4"));
    expect(parseChord("  Cmaj7  ")).toEqual(parseChord("Cmaj7"));
    expect(parseChord("C maj7")).toEqual(parseChord("Cmaj7"));
  });

  it("returns null for an empty, nonsense, unknown or inherited-property input", () => {
    expect(parseChord("")).toBeNull();
    expect(parseChord("   ")).toBeNull();
    expect(parseChord("H")).toBeNull();
    expect(parseChord("Cxyz")).toBeNull();
    expect(parseChord("C11")).toBeNull();
    expect(parseChord("Cmin")).toBeNull();          // an alias §5.4 does not list
    expect(parseChord("Cconstructor")).toBeNull();  // not an inherited Object key
    expect(parseChord("CtoString")).toBeNull();
  });

  it("always returns exactly twelve booleans when it returns at all", () => {
    for (const text of ["C", "F#m7", "Bbsus2", "Adim", "Gaug"]) {
      const keys = parseChord(text);
      expect(keys).toHaveLength(12);
      expect(keys!.every((v) => typeof v === "boolean")).toBe(true);
    }
  });
});
