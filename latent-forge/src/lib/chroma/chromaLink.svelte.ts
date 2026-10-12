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
  /** `fileSec` is the hovered position in the ANALYSED FILE (seconds), when the tab knows it. */
  hover = $state<{ clipId: string; frac: number; fileSec?: number } | null>(null);
  scores = $state<Record<string, number>>({});

  setHover(clipId: string, frac: number, fileSec?: number): void {
    const f = Number.isFinite(frac) ? (frac < 0 ? 0 : frac > 1 ? 1 : frac) : 0;
    this.hover = fileSec !== undefined && Number.isFinite(fileSec) ? { clipId, frac: f, fileSec } : { clipId, frac: f };
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

/**
 * Timeline seconds for a hover into a clip, or null when that point of the file is not on the
 * timeline. With `fileSec` (the hovered second of the analysed file) the clip's trim is honoured:
 * the analysed file is the stretched previewAudio (or the unstretched source), so its seconds are
 * timeline-scale and `offset_sec` is where the clip starts reading it. A looping clip shows the
 * first repeat. Without `fileSec` it falls back to frac x dur_sec, which assumes an untrimmed clip
 * -- the old behaviour, wrong for any trimmed clip (review 2026-10-01).
 */
export function markerSecFor(
  clip: { start_sec: number; dur_sec: number; offset_sec?: number },
  frac: number,
  fileSec?: number,
): number | null {
  if (fileSec === undefined) return clip.start_sec + frac * clip.dur_sec;
  const into = fileSec - (clip.offset_sec ?? 0);
  if (into < 0 || into > clip.dur_sec) return null;
  return clip.start_sec + into;
}

/** The analysed file's frame range [t0, t1) that a trimmed clip actually plays (clamped to T). */
export function clipFrameRange(
  clip: { dur_sec: number; offset_sec?: number }, T: number, fps: number,
): [number, number] {
  const t0 = Math.max(0, Math.min(T, Math.floor((clip.offset_sec ?? 0) * fps)));
  const t1 = Math.max(t0, Math.min(T, Math.ceil(((clip.offset_sec ?? 0) + clip.dur_sec) * fps)));
  return t1 > t0 ? [t0, t1] : [0, T];
}
