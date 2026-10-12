// The detune scan (spec §5.4, the drawing's _detuneScan at v3 947-957). Match
// as a function of detune across +/-100 cents, in two readings:
//
//   HIGHEST   -> argmax of mean          : the match sits high on average
//   STEADIEST -> argmax of (mean - sd)   : the match holds level through the
//                                          clip, which is what matters before a
//                                          crossfade or an inpainted join
//
// A flat curve on its own is not a good match -- it can be uniformly
// dissonant -- which is why the scan reports both and the criterion chooses.
//
// The grid is pinned by the spec: cents -100..100 step 4 (51 points) sampling
// every 3rd frame. The stride is a cost decision, not a modelling one, so the
// clip score label (meanMatchAtDetune) deliberately does NOT stride: §5.4 says
// the label is the mean frame match at the clip's detune, over the clip.

import { fold12Column } from "./bins";
import { matchFrame, rotate } from "./match";

export const DETUNE_MIN = -100;
export const DETUNE_MAX = 100;
export const DETUNE_STEP = 4;
export const FRAME_STRIDE = 3;

export type ScanCriterion = "highest" | "steadiest";

export interface DetuneScan {
  /** 51 points: -100, -96, ... 96, 100. */
  cents: number[];
  /** Mean match over the sampled frames, one per cents step. */
  mean: number[];
  /** Population sd of the same samples (divided by n, as v3 does). */
  sd: number[];
}

/** The 51 cents steps, as integers. */
function centsAxis(): number[] {
  const out: number[] = [];
  for (let c = DETUNE_MIN; c <= DETUNE_MAX; c += DETUNE_STEP) out.push(c);
  return out;
}

/**
 * Scan the clip's 12-class fold against the target across the detune range.
 * `fold12` is the server's [12,T] C-order array; `T` its frame count.
 * Rotation is by `cents/100` classes -- 100 cents is exactly one pitch class.
 *
 * `analysisDetuneCents` is the detune NOT already present in the analysed
 * audio: 0 when the fold came from the stretched preview (M5 T10's runStretch
 * has already pitch-shifted it by clip.detune_cents / 100), and
 * clip.detune_cents when it came from the raw source. Each step therefore
 * rotates by (analysisDetuneCents + c) / 100, which makes the 51-point cents
 * axis RELATIVE to the clip's current detune in BOTH cases -- step c means
 * "clip.detune_cents + c". So `bestDetune`'s answer is an OFFSET the caller
 * adds to the clip's detune, never a value it assigns. See the plan's
 * Normative block and Open question 6.
 */
export function scanDetune(
  fold12: Float32Array,
  T: number,
  target: Float32Array,
  analysisDetuneCents = 0,
): DetuneScan {
  const cents = centsAxis();
  const mean: number[] = [];
  const sd: number[] = [];

  // Extract the sampled columns once: 51 steps would otherwise re-slice them.
  const columns: Float32Array[] = [];
  for (let t = 0; t < T; t += FRAME_STRIDE) columns.push(fold12Column(fold12, T, t));

  for (const c of cents) {
    if (columns.length === 0) {
      mean.push(0);
      sd.push(0);
      continue;
    }
    const semis = (analysisDetuneCents + c) / 100;
    const vals: number[] = [];
    let sum = 0;
    for (const col of columns) {
      const v = matchFrame(rotate(col, semis), target);
      vals.push(v);
      sum += v;
    }
    const m = sum / vals.length;
    let acc = 0;
    for (const v of vals) acc += (v - m) * (v - m);
    mean.push(m);
    sd.push(Math.sqrt(acc / vals.length));
  }

  return { cents, mean, sd };
}

/**
 * The scan step BEST moves by -- an OFFSET from the clip's current detune, not
 * an absolute detune, because scanDetune's axis is relative (see above). Ties
 * keep the FIRST (most negative) step --
 * the comparison is strict `>` -- so the button is deterministic on the flat
 * stretches the 0.08 threshold creates near a whole-class rotation.
 */
export function bestDetune(scan: DetuneScan, criterion: ScanCriterion): number {
  const score = (i: number): number =>
    criterion === "steadiest" ? scan.mean[i] - scan.sd[i] : scan.mean[i];
  let best = 0;
  for (let i = 1; i < scan.cents.length; i++) if (score(i) > score(best)) best = i;
  return scan.cents[best];
}

/**
 * The clip's score label (§5.4): the mean frame match at the clip's detune,
 * over EVERY frame -- no stride. M5 T6's `SCORE_PLACEHOLDER = "chi —"` is
 * replaced by this number.
 */
export function meanMatchAtDetune(
  fold12: Float32Array,
  T: number,
  target: Float32Array,
  cents: number,
  range: [number, number] = [0, T],
): number {
  // `range` limits the mean to the frames the clip actually plays (its trim); the default is
  // every frame, as before (review 2026-10-01).
  const t0 = Math.max(0, range[0]);
  const t1 = Math.min(T, range[1]);
  if (t1 <= t0) return 0;
  const semis = cents / 100;
  let sum = 0;
  for (let t = t0; t < t1; t++) sum += matchFrame(rotate(fold12Column(fold12, T, t), semis), target);
  return sum / (t1 - t0);
}
