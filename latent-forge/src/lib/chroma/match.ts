// The harmonic-overlap match score (spec §5.4; the drawing's _matchFrame at
// v3 925-937, _rotate at 895-903, _anchors at 915-922). Pure -- no canvas, no
// store, no network -- so vitest pins the exact numbers the spec specifies.
//
// The score is a weighted average, not a dot product: every pair of ACTIVE
// pitch classes (both sides above MATCH_THRESHOLD) contributes
// frame[a]*target[b]*INTERVAL_W[((a-b)%12+12)%12] to the numerator and
// frame[a]*target[b] to the denominator -- a DIRECTED, wrapped distance from
// the target's class to the frame's, not Math.abs(a-b) (see matchFrame's own
// comment for why the two disagree and WINTERMUTE's fifth-vs-fourth example).
// So a fifth reads high and a semitone low even though the semitone is nearer
// in pitch, and the result is always in [0.10, 1.0] when anything is active
// at all.

export const INTERVAL_W: readonly number[] = [
  1.0, 0.10, 0.35, 0.62, 0.70, 0.82, 0.18, 0.90, 0.66, 0.72, 0.30, 0.22,
];

/** Pitch classes at or above this count; below it they are not there at all. */
export const MATCH_THRESHOLD = 0.08;

/**
 * MATCH_THRESHOLD rounded to float32, which is what the guards below actually
 * compare against. This is NOT pedantry: every chroma array in this milestone
 * is a `Float32Array`, so a value written as `0.08` is stored as
 * `Math.fround(0.08) = 0.079999998211860657`. Comparing that against the
 * float64 literal `0.08 = 0.080000000000000002` makes `value < MATCH_THRESHOLD`
 * TRUE for a class the caller set to exactly the threshold -- so "at exactly
 * 0.08" would be excluded, which is the opposite of the documented rule.
 * Rounding the threshold the same way makes the comparison happen in one
 * precision. `0.0799` still rounds to 0.079899996, which is strictly below, so
 * "just under the threshold is excluded" is unaffected.
 */
const THRESHOLD_F32 = Math.fround(MATCH_THRESHOLD);

function require12(name: string, v: Float32Array): void {
  if (v.length !== 12) throw new RangeError(`${name}: expected 12 pitch classes, got ${v.length}`);
}

/**
 * Harmonic-overlap score of one 12-class frame against a 12-class target.
 *
 * INTERVAL_W is indexed by the DIRECTED, wrapped class distance from the
 * TARGET class to the FRAME class -- `((a - b) % 12 + 12) % 12`, `a` the
 * frame's class and `b` the target's -- never `Math.abs(a - b)`. The two are
 * not the same table lookup: `Math.abs` is symmetric, so it depends only on
 * which of the two class numbers happens to be larger, not on a consistent
 * "distance from target to frame" direction, and for roughly half of all
 * pairs it silently reads the wrong entry. WINTERMUTE's own example (plan log,
 * 2026-09-22 17:12:49) is the one to keep in mind: target class 7 (G), frame
 * class 0 (C) -- `Math.abs(7-0) = 7` reads `INTERVAL_W[7] = 0.90` ("a fifth"),
 * but the ascending distance from G up to C is 5 semitones ("a fourth",
 * `INTERVAL_W[5] = 0.82`), and `((0 - 7) % 12 + 12) % 12 = 5` is what gets
 * that right.
 *
 * The table stays UNFOLDED on purpose -- do not "fix" this into
 * `INTERVAL_W[Math.min(ic, 12-ic)]`. A minor second up (index 1, weight 0.10)
 * and a major seventh (index 11, weight 0.22) are both interval class 1 and
 * are deliberately weighted differently; folding would average pairs like
 * that and would also move the legend's anchors, since `anchors()` computes
 * them through this same function. §5.4 names `_matchFrame` as the score's
 * definition and pins these twelve weights to it; the indexing above is what
 * WINTERMUTE settled as the correct, directed reading of that definition. See
 * the Normative table's `INTERVAL_W`'s index row, which carries this as
 * resolved rather than as an open question.
 */
export function matchFrame(frame: Float32Array, target: Float32Array): number {
  require12("matchFrame(frame)", frame);
  require12("matchFrame(target)", target);
  let num = 0;
  let den = 0;
  for (let a = 0; a < 12; a++) {
    const fa = frame[a];
    if (fa < THRESHOLD_F32) continue;
    for (let b = 0; b < 12; b++) {
      const tb = target[b];
      if (tb < THRESHOLD_F32) continue;
      const w = fa * tb;
      const distance = (((a - b) % 12) + 12) % 12;
      num += w * INTERVAL_W[distance];
      den += w;
    }
  }
  return den ? num / den : 0;
}

/**
 * Rotate a 12-class frame by a fractional number of classes -- detune in cents
 * divided by 100 (spec §5.4). The energy of each class is split LINEARLY
 * between the two classes it lands between, so the total is preserved and a
 * 50-cent detune reads as half in each neighbour. Negative rotations wrap.
 *
 * Always returns a fresh array: v3 returns its input unchanged at 0, which
 * makes the caller's array aliasable. Purity is cheaper than that bug.
 */
export function rotate(frame: Float32Array, classes: number): Float32Array {
  require12("rotate(frame)", frame);
  const out = new Float32Array(12);
  const i = Math.floor(classes);
  const fr = classes - i;
  for (let p = 0; p < 12; p++) {
    const a = (((p - i) % 12) + 12) % 12;
    const b = (((p - i - 1) % 12) + 12) % 12;
    out[p] = frame[a] * (1 - fr) + frame[b] * fr;
  }
  return out;
}

export interface MatchAnchors {
  unison: number;
  fifth: number;
  tritone: number;
}

/**
 * The legend's three reference marks (§5.4, `_anchors`): what the score reads
 * when the target's own chroma is heard at a unison, a fifth and a tritone
 * away. They are properties of the target alone, which is why the legend can
 * draw them before any clip is selected.
 */
export function anchors(target: Float32Array): MatchAnchors {
  require12("anchors(target)", target);
  return {
    unison: matchFrame(target, target),
    fifth: matchFrame(rotate(target, 7), target),
    tritone: matchFrame(rotate(target, 6), target),
  };
}
