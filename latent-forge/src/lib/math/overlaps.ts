// Where two clips in the same lane overlap (spec 4.3; v3 1601-1611's
// `_overlaps()`). Extracted from Task 1's inline `arrangement.overlaps`
// derived, verbatim -- this file's job is the extraction and the store
// refactor to call it, not a behaviour change.

import type { ForgeClip } from "../forge/types";

const LANE_COUNT = 4;

export interface Overlap {
  key: string;
  lane: 0 | 1 | 2 | 3;
  start_sec: number;
  end_sec: number;
  a_id: string;
  b_id: string;
}

/**
 * ALL pairs per lane, not sorted-adjacent ones. The drawing's `_overlaps`
 * (v3:1601-1611) checked adjacency only, but there an overlap was just a
 * purple box; here it feeds 6.9's commit payload and 8.1 S3 equal-power-
 * crossfades an overlap instead of summing it, so a missed one is a louder,
 * possibly clipping render with no inpaint pass. Task 1 deliberately widened
 * the scan to catch the case adjacency-only misses: a clip spanning two
 * later clips that do not overlap each other (e.g. lane [A: 0-20s, B: 2-4s,
 * C: 10-12s] -- A/C is missed by an adjacency-only scan since B sits between
 * them in start order, but A genuinely overlaps C and this scan finds it).
 * Verified against Task 1's own store code and its "finds a non-adjacent
 * pair" test (`arrangement.test.ts`) -- preserved here verbatim, not
 * reverted to the adjacency-only behaviour.
 */
export function findOverlaps(clips: ForgeClip[]): Overlap[] {
  const out: Overlap[] = [];
  for (let lane = 0; lane < LANE_COUNT; lane++) {
    const inLane = clips.filter((c) => c.lane === lane).sort((a, b) => a.start_sec - b.start_sec);
    for (let i = 0; i < inLane.length; i++) {
      for (let j = i + 1; j < inLane.length; j++) {
        const a = inLane[i];
        const b = inLane[j];
        const aEnd = a.start_sec + a.dur_sec;
        if (aEnd > b.start_sec + 1e-9) {
          out.push({
            key: `${a.id}-${b.id}`,
            lane: lane as 0 | 1 | 2 | 3,
            start_sec: b.start_sec,
            end_sec: Math.min(aEnd, b.start_sec + b.dur_sec),
            a_id: a.id,
            b_id: b.id,
          });
        }
      }
    }
  }
  return out;
}

/** Spec 4.3: the purple overlap box's label. */
export function overlapLabel(startSec: number, endSec: number, bpm: number, beatsPerBar: number): string {
  const secPerBar = (60 / bpm) * beatsPerBar;
  const bars = (endSec - startSec) / secPerBar;
  return `INPAINT ${bars.toFixed(2)} bar`;
}
