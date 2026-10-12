// The chroma target (spec §5.4), in both of its modes, as one 12-class
// Float32Array so the match layer never has to know which mode is on:
//
//   lane mode -- the TARGET lane's clips' 12-class folds, SUMMED over frames
//                and then max-normalised (_targetProfile, v3 877-891)
//   set  mode -- twelve piano-key toggles, flat 1/0, optionally filled in by a
//                chord symbol
//
// Pure and store-free: the caller reads the TARGET lane from `arrangement` and
// hands the frames in, which keeps every chord spelling testable without a
// timeline.

export type ChromaTargetMode = "lane" | "set";

/**
 * Lane mode: sum the frames, then divide by the summed maximum. Summing first
 * means a long clip weighs more than a short one, which is what "the lane's
 * profile" should mean. An empty lane and an all-silent lane both give an
 * all-zero profile -- never NaN, and the caller is expected to say so honestly
 * rather than draw it as if it were data.
 */
export function targetProfile(frames: readonly Float32Array[]): Float32Array {
  const out = new Float32Array(12);
  for (const fr of frames) {
    if (fr.length !== 12) {
      throw new RangeError(`targetProfile: expected 12 pitch classes per frame, got ${fr.length}`);
    }
    for (let p = 0; p < 12; p++) out[p] += fr[p];
  }
  let max = 0;
  for (let p = 0; p < 12; p++) if (out[p] > max) max = out[p];
  if (max > 0) for (let p = 0; p < 12; p++) out[p] /= max;
  return out;
}

/** SEMITONE SET mode: the twelve toggles, flat. On is 1, off is 0. */
export function setProfile(keys: readonly boolean[]): Float32Array {
  if (keys.length !== 12) {
    throw new RangeError(`setProfile: expected 12 keys, got ${keys.length}`);
  }
  const out = new Float32Array(12);
  for (let p = 0; p < 12; p++) out[p] = keys[p] ? 1 : 0;
  return out;
}

/** Semitone offset of each natural letter from C. */
const LETTER_SEMITONE = new Map<string, number>([
  ["c", 0], ["d", 2], ["e", 4], ["f", 5], ["g", 7], ["a", 9], ["b", 11],
]);

/**
 * The nine qualities §5.4 lists, and only those. A Map, not an object literal:
 * an object lookup on arbitrary user text finds inherited keys, so "Cconstructor"
 * would return a truthy function and the parser would crash downstream.
 */
const QUALITY_INTERVALS = new Map<string, readonly number[]>([
  ["", [0, 4, 7]],
  ["m", [0, 3, 7]],
  ["7", [0, 4, 7, 10]],
  ["maj7", [0, 4, 7, 11]],
  ["m7", [0, 3, 7, 10]],
  ["dim", [0, 3, 6]],
  ["aug", [0, 4, 8]],
  ["sus2", [0, 2, 7]],
  ["sus4", [0, 5, 7]],
]);

const CHORD_RE = /^([A-Ga-g])([#b]?)\s*(.*)$/;

/**
 * Parse a chord symbol into twelve key toggles, or null if it is not one of
 * the nine qualities over one of the twelve roots. Never throws -- the field
 * is typed into character by character, so half-finished text is the normal
 * case and null simply means "the key row does not change yet".
 *
 * The root letter is case-insensitive and the quality is lowercased (as v3
 * does), so `CDIM` works. The accidental is case-SENSITIVE: a lowercase `b`
 * after the letter is a flat. Roots are computed from the letter's semitone
 * plus the accidental rather than looked up in a sharp-spelling table, so E#,
 * B# and Cb resolve instead of failing (v3's NOTES.indexOf("E#") is -1).
 */
export function parseChord(text: string): boolean[] | null {
  const m = CHORD_RE.exec(text.trim());
  if (!m) return null;
  const letter = LETTER_SEMITONE.get(m[1].toLowerCase());
  if (letter === undefined) return null;
  const accidental = m[2] === "#" ? 1 : m[2] === "b" ? -1 : 0;
  const root = (((letter + accidental) % 12) + 12) % 12;
  const intervals = QUALITY_INTERVALS.get(m[3].toLowerCase());
  if (!intervals) return null;
  const keys = new Array<boolean>(12).fill(false);
  for (const iv of intervals) keys[(root + iv) % 12] = true;
  return keys;
}
