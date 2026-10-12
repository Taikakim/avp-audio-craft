// SAME chroma bin geometry (spec §5.4). Three octave-band chromagrams of 128
// bins each; pitch class C sits at bin 2.0, not bin 0, and each semitone spans
// 128/12 = 10.666... bins (the `same_chroma` PITFALL). Everything here mirrors
// the server's own harmonic/same_chroma.py so the client and the server agree
// bin for bin:
//
//   centre(s) = (128*(s+3)/12 - 3*floor(128/12)) mod 128   -> C = 2.0, A = 98.0
//   fold_to_12 SUMS each fine bin into its nearest centre by CIRCULAR distance
//
// Pure: no canvas, no store, no network, so vitest pins the numbers directly.

export const BINS_PER_BAND = 128;
export const BANDS = 3;
export const BINS_PER_SEMITONE = BINS_PER_BAND / 12;
export const C_BIN = 2.0;

/** Sharp spellings, C first -- the y-axis labels and the hover readout (§5.4). */
export const NOTE_NAMES: readonly string[] = [
  "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B",
];

function mod(x: number, n: number): number {
  return ((x % n) + n) % n;
}

const centreCache = new Map<number, readonly number[]>();

function centresFor(binsPerBand: number): readonly number[] {
  const hit = centreCache.get(binsPerBand);
  if (hit) return hit;
  const out: number[] = [];
  for (let s = 0; s < 12; s++) {
    // The server's exact expression, kept verbatim: base_c's integer roll is
    // what puts C at 2.0 rather than 0.0 for a 128-bin band.
    out.push(mod((binsPerBand * (s + 3)) / 12 - 3 * Math.floor(binsPerBand / 12), binsPerBand));
  }
  centreCache.set(binsPerBand, out);
  return out;
}

const assignCache = new Map<number, readonly number[]>();

/** bin -> nearest semitone centre, by circular distance, ties to the lower class. */
function assignmentFor(binsPerBand: number): readonly number[] {
  const hit = assignCache.get(binsPerBand);
  if (hit) return hit;
  const out: number[] = [];
  for (let b = 0; b < binsPerBand; b++) out.push(binToPitchClass(b, binsPerBand));
  assignCache.set(binsPerBand, out);
  return out;
}

/** The twelve semitone centres, C..B, in bins. A fresh array each call. */
export function semitoneBinCenters(): number[] {
  return [...centresFor(BINS_PER_BAND)];
}

/**
 * Nearest pitch class for a (possibly fractional) bin index, by CIRCULAR
 * distance -- the band wraps, so bin 125 is nearer to C's centre at 2.0 (going
 * up over the top: 128 - 123 = 5) than to B's at 119.333 (5.667). The boundary
 * is 2.0 + 11.5*(128/12) = 124.667.
 *
 * Ties break to the LOWER class because the comparison is strict `<`, which is
 * what numpy's argmin does in the server's fold_to_12. Bins 18, 50, 82 and 114
 * are the only exact ties -- the midpoint between centres s and s+1 is
 * 2 + (2s+1)*16/3, an integer only when 3 divides (2s+1), i.e. s in {1,4,7,10}
 * -- and Math.round() on (bin - 2)/(128/12) sends all four the other
 * way -- hence this loop rather than the one-line formula.
 */
export function binToPitchClass(bin: number, binsPerBand: number = BINS_PER_BAND): number {
  const centres = centresFor(binsPerBand);
  let best = Infinity;
  let bestClass = 0;
  for (let s = 0; s < 12; s++) {
    const raw = Math.abs(bin - centres[s]);
    const d = Math.min(raw, binsPerBand - raw);
    if (d < best) {
      best = d;
      bestClass = s;
    }
  }
  return bestClass;
}

/** The inverse: a pitch class's exact bin centre (fractional for most classes). */
export function pitchClassToBin(pitchClass: number, binsPerBand: number = BINS_PER_BAND): number {
  return centresFor(binsPerBand)[mod(Math.trunc(pitchClass), 12)];
}

/**
 * Fold one band's 128 bins onto 12 classes by SUMMING each bin into its
 * nearest centre -- the server's fold_to_12, not a mean and not a max.
 */
export function foldTo12(band: Float32Array, binsPerBand: number = BINS_PER_BAND): Float32Array {
  if (band.length !== binsPerBand) {
    throw new RangeError(`foldTo12: expected ${binsPerBand} bins, got ${band.length}`);
  }
  const assign = assignmentFor(binsPerBand);
  const out = new Float32Array(12);
  for (let b = 0; b < binsPerBand; b++) out[assign[b]] += band[b];
  return out;
}

/**
 * One frame of the server's own 12-class fold, which arrives as [12,T] in C
 * order, T fastest: class p, frame t = fold12[p*T + t]. Transposed from the
 * shape a caller intuitively wants, so it lives here once rather than in each
 * of the three places that need a column.
 *
 * This is ALSO the GLOBAL view's own array (§5.4's "sum the three bands
 * through fold_to_12, then per-frame normalise to max 1" is exactly what the
 * server computes and transports here — M2 T12's `chroma_payload` ships it at
 * `scale: 1.0` because the values are already in [0,1] per frame, not because
 * 1.0 is a whole-clip scale). There is no separate client-side fold: the
 * display, the match score, the detune scan and the clip score all read this
 * one array. See the plan's Normative table, "which 12-class fold feeds
 * what" — this used to be two arrays (`foldFrameTo12` locally re-folded
 * `bands` for the display) and WINTERMUTE's 2026-09-22 ruling collapsed that
 * to the one below.
 */
export function fold12Column(fold12: Float32Array, T: number, frame: number): Float32Array {
  if (fold12.length !== 12 * T) {
    throw new RangeError(`fold12Column: expected ${12 * T} values for [12,${T}], got ${fold12.length}`);
  }
  if (frame < 0 || frame >= T) {
    throw new RangeError(`fold12Column: frame ${frame} out of range for T=${T}`);
  }
  const out = new Float32Array(12);
  for (let p = 0; p < 12; p++) out[p] = fold12[p * T + frame];
  return out;
}

/** Every frame of a [12,T] fold, in order. */
export function fold12Columns(fold12: Float32Array, T: number): Float32Array[] {
  const out: Float32Array[] = [];
  for (let t = 0; t < T; t++) out.push(fold12Column(fold12, T, t));
  return out;
}
