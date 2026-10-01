import { describe, expect, it } from "vitest";
import {
  bestDetune,
  DETUNE_MAX,
  DETUNE_MIN,
  DETUNE_STEP,
  FRAME_STRIDE,
  meanMatchAtDetune,
  scanDetune,
} from "../detuneScan";

function profile(entries: Record<number, number>): Float32Array {
  const out = new Float32Array(12);
  for (const [k, v] of Object.entries(entries)) out[Number(k)] = v;
  return out;
}

/** Pack per-frame 12-class columns into the server's [12,T] C-order layout. */
function packFold12(columns: Float32Array[]): Float32Array {
  const T = columns.length;
  const out = new Float32Array(12 * T);
  for (let t = 0; t < T; t++) for (let p = 0; p < 12; p++) out[p * T + t] = columns[t][p];
  return out;
}

describe("the scan grid §5.4 pins", () => {
  it("is cents -100..100 step 4 and every 3rd frame", () => {
    expect(DETUNE_MIN).toBe(-100);
    expect(DETUNE_MAX).toBe(100);
    expect(DETUNE_STEP).toBe(4);
    expect(FRAME_STRIDE).toBe(3);
  });

  it("gives a cents axis of exactly 51 points: (100 - -100)/4 + 1", () => {
    const scan = scanDetune(packFold12([profile({ 0: 1 })]), 1, profile({ 0: 1 }));
    expect((DETUNE_MAX - DETUNE_MIN) / DETUNE_STEP + 1).toBe(51);
    expect(scan.cents).toHaveLength(51);
    expect(scan.cents[0]).toBe(-100);
    expect(scan.cents[1]).toBe(-96);
    expect(scan.cents[25]).toBe(0);
    expect(scan.cents[50]).toBe(100);
    expect(scan.cents.every((c) => Number.isInteger(c))).toBe(true);
  });

  it("returns mean and sd arrays the same length as cents", () => {
    const scan = scanDetune(packFold12([profile({ 0: 1 }), profile({ 4: 1 })]), 2, profile({ 0: 1 }));
    expect(scan.mean).toHaveLength(51);
    expect(scan.sd).toHaveLength(51);
    expect(scan.mean.every(Number.isFinite)).toBe(true);
    expect(scan.sd.every(Number.isFinite)).toBe(true);
  });
});

describe("scanDetune", () => {
  it("samples every 3rd frame, so frames 1 and 2 change nothing", () => {
    const target = profile({ 0: 1 });
    const kept = [profile({ 0: 1 }), profile({ 6: 1 })];              // frames 0 and 3
    const a = scanDetune(packFold12([kept[0], new Float32Array(12), new Float32Array(12), kept[1]]), 4, target);
    const b = scanDetune(packFold12([kept[0], profile({ 3: 1 }), profile({ 9: 1 }), kept[1]]), 4, target);
    expect(b.mean).toEqual(a.mean);
    expect(b.sd).toEqual(a.sd);
  });

  it("reads the unison at 0 cents when the only sampled frame is the target", () => {
    const target = profile({ 0: 1 });
    const scan = scanDetune(packFold12([profile({ 0: 1 })]), 1, target);
    expect(scan.mean[25]).toBeCloseTo(1.0, 10);    // cents 0
    expect(scan.sd[25]).toBe(0);
    expect(scan.mean[50]).toBeCloseTo(0.10, 10);   // +100 cents: one class up, INTERVAL_W[1]
  });

  it("gives sd 0 at every cent for a single sampled frame, so the criteria agree", () => {
    const target = profile({ 0: 1.0, 4: 0.8, 7: 0.9 });
    const scan = scanDetune(packFold12([profile({ 0: 1.0, 4: 0.8, 7: 0.9 })]), 1, target);
    expect(scan.sd.every((v) => v === 0)).toBe(true);
    expect(bestDetune(scan, "highest")).toBe(bestDetune(scan, "steadiest"));
  });

  it("rotates by the ANALYSIS detune plus each step, so the axis is RELATIVE to it", () => {
    // The scan runs on audio the stretch has usually already detuned, so step
    // c means "the clip's current detune, plus c". The base argument is what
    // keeps that true in the OTHER case too -- a clip with no native_bpm,
    // whose previewAudio is null and whose fold is therefore undetuned.
    const target = profile({ 0: 1 });
    const fold12 = packFold12([profile({ 0: 1 })]);
    const flat = scanDetune(fold12, 1, target);
    const shifted = scanDetune(fold12, 1, target, 100);
    expect(shifted.cents).toEqual(flat.cents);                 // the axis itself never moves
    expect(shifted.mean[25]).toBeCloseTo(flat.mean[50], 9);    //    0 rel = +100 absolute
    expect(shifted.mean[0]).toBeCloseTo(flat.mean[25], 9);     // -100 rel =    0 absolute
  });

  it("returns zeros rather than NaN for an all-zero target", () => {
    const scan = scanDetune(packFold12([profile({ 0: 1 }), profile({ 4: 1 })]), 2, new Float32Array(12));
    expect(scan.mean.every((v) => v === 0)).toBe(true);
    expect(scan.sd.every((v) => v === 0)).toBe(true);
    expect(bestDetune(scan, "highest")).toBe(-100);   // first argmax of a flat curve
  });

  it("returns a 51-point scan of zeros for T = 0 rather than dividing by no frames", () => {
    const scan = scanDetune(new Float32Array(0), 0, profile({ 0: 1 }));
    expect(scan.cents).toHaveLength(51);
    expect(scan.mean.every((v) => v === 0)).toBe(true);
    expect(scan.sd.every((v) => v === 0)).toBe(true);
  });
});

describe("HIGHEST and STEADIEST", () => {
  it("disagree on a constructed clip: -12 cents is highest, -76 cents is steadiest", () => {
    // Target: a C major triad. Frame 0 is C-ish (scores well at no detune);
    // frame 3 is F/B-ish (scores badly there). HIGHEST nudges to where the
    // average is best; STEADIEST goes to where BOTH frames score alike.
    //
    // The steadiest step moved from -80 to -76 when Task 3's INTERVAL_W
    // indexing became the directed distance rather than Math.abs(a-b)
    // (WINTERMUTE, 2026-09-22): this fixture's cross terms (frame class vs a
    // non-equal target class) read different table entries under the
    // corrected formula, which reshapes the mean-sd curve enough to move its
    // argmax by one step. Recomputed by hand against the fixed matchFrame,
    // not eyeballed.
    const target = profile({ 0: 1.0, 4: 0.8, 7: 0.9 });
    const fold12 = packFold12([
      profile({ 0: 1.0, 4: 0.6 }),
      new Float32Array(12),
      new Float32Array(12),
      profile({ 5: 1.0, 11: 0.5 }),
    ]);
    const scan = scanDetune(fold12, 4, target);

    expect(bestDetune(scan, "highest")).toBe(-12);
    expect(bestDetune(scan, "steadiest")).toBe(-76);

    const hi = scan.cents.indexOf(-12);
    const st = scan.cents.indexOf(-76);
    expect(scan.mean[hi]).toBeCloseTo(0.6563495680089630, 6);
    expect(scan.mean[st]).toBeCloseTo(0.6166814814814815, 6);
    expect(scan.sd[st]).toBeLessThan(scan.sd[hi]);            // steadier, as claimed
    expect(scan.mean[st]).toBeLessThan(scan.mean[hi]);        // and lower, as claimed
    expect(scan.mean[st] - scan.sd[st]).toBeGreaterThan(scan.mean[hi] - scan.sd[hi]);
  });

  it("reads the arrays directly: argmax of mean, or of mean - sd, first wins a tie", () => {
    const scan = {
      cents: [-8, -4, 0, 4],
      mean: [0.5, 0.9, 0.9, 0.2],
      sd: [0.5, 0.5, 0.4, 0.0],
    };
    expect(bestDetune(scan, "highest")).toBe(-4);      // 0.9 first, at index 1
    // mean - sd = [0.0, 0.4, 0.5, 0.2]: a UNIQUE max at index 2. The earlier
    // sd of [0.0, 0.5, 0.4, 0.0] gave [0.5, 0.4, 0.5, 0.2] -- a tie between
    // index 0 and index 2 -- and first-wins would have returned -8, not 0.
    expect(bestDetune(scan, "steadiest")).toBe(0);
    expect(bestDetune({ cents: [-4, 0], mean: [0.3, 0.3], sd: [0, 0] }, "highest")).toBe(-4);
  });
});

describe("meanMatchAtDetune — the clip score label", () => {
  it("averages EVERY frame, not every 3rd, at the clip's own detune", () => {
    const target = profile({ 0: 1.0, 4: 0.8, 7: 0.9 });
    const fold12 = packFold12([
      profile({ 0: 1.0, 4: 0.6 }),
      new Float32Array(12),
      new Float32Array(12),
      profile({ 5: 1.0, 11: 0.5 }),
    ]);
    const scan = scanDetune(fold12, 4, target);
    const all = meanMatchAtDetune(fold12, 4, target, 0);
    // The two silent frames score 0 and the scan never sees them, so the label
    // is exactly half the scan's mean here -- the difference is the point.
    // (0.3320679012345679 before Task 3's directed-distance fix; recomputed.)
    expect(all).toBeCloseTo(0.3263966049382716, 6);
    expect(all).toBeCloseTo(scan.mean[scan.cents.indexOf(0)] / 2, 6);
  });

  it("is 0 for no frames and follows the detune it is given", () => {
    const target = profile({ 0: 1 });
    expect(meanMatchAtDetune(new Float32Array(0), 0, target, 0)).toBe(0);
    const fold12 = packFold12([profile({ 0: 1 })]);
    expect(meanMatchAtDetune(fold12, 1, target, 0)).toBeCloseTo(1.0, 10);
    expect(meanMatchAtDetune(fold12, 1, target, 100)).toBeCloseTo(0.10, 10);
    expect(meanMatchAtDetune(fold12, 1, target, -100)).toBeCloseTo(0.22, 10);
  });
});
