// The seam between the CHROMA tab and the timeline. Two facts, both written by
// the tab and read by M5's components, and nothing else:
//
//   hover  -- which clip is being hovered and how far into it, so the lane
//             canvas can draw the red vertical line spec §5.4 asks for;
//   scores -- the mean frame match per clip, so the clip box can replace M5
//             T6's SCORE_PLACEHOLDER with a real number.
//
// It is a store rather than a prop chain because the two sides are three
// components apart (CHROMA tab -> BottomPane -> App -> Timeline -> LaneCanvas)
// and M5's components take no props from anything above the timeline. Adding
// this singleton costs LaneCanvas one import and nine lines; threading props
// would have meant editing four M5 files.
//
// Note the $state proxy rule does not bite here: nothing appends an object to
// a $state array. `scores` is a plain record whose values are numbers, and a
// deep-proxied assignment to a property is exactly what we want.

import { SCORE_PLACEHOLDER } from "../math/clipBox";

export class ChromaLink {
  hover = $state<{ clipId: string; frac: number } | null>(null);
  scores = $state<Record<string, number>>({});

  setHover(clipId: string, frac: number): void {
    const f = Number.isFinite(frac) ? (frac < 0 ? 0 : frac > 1 ? 1 : frac) : 0;
    this.hover = { clipId, frac: f };
  }

  clearHover(): void {
    this.hover = null;
  }

  setScore(clipId: string, score: number): void {
    this.scores[clipId] = score;
  }

  clearScore(clipId: string): void {
    delete this.scores[clipId];
  }

  reset(): void {
    this.hover = null;
    this.scores = {};
  }
}

export const chromaLink = new ChromaLink();

/**
 * The clip box's score label. `undefined` -- a clip nothing has analysed --
 * keeps M5 T6's own placeholder, which is what it is for: §5.4's number needs
 * a /forge/chroma round trip per clip, and only the selected clip and the
 * TARGET lane's clips are analysed.
 */
export function clipScoreLabel(score: number | undefined): string {
  return score === undefined || !Number.isFinite(score) ? SCORE_PLACEHOLDER : `χ ${score.toFixed(2)}`;
}

/** Timeline seconds for a hover fraction into a clip. */
export function markerSecFor(clip: { start_sec: number; dur_sec: number }, frac: number): number {
  return clip.start_sec + frac * clip.dur_sec;
}
