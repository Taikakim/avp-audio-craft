// The MATCH CURVE overlay's arithmetic and the consonance legend's marks
// (spec §5.4; v3 _drawCurve 1262-1302 and legendTicks 2029-2037).
//
// The y-axis is anchored to the TARGET's own anchors -- what the target scores
// against itself at a unison, a fifth and a tritone -- and never to the data.
// That is the whole point: the same height means the same thing from clip to
// clip, so a dip in the curve is a dissonant passage rather than "the quietest
// part of this particular clip".
//
// The three anchor colours are literals, not tokens: they are the drawing's
// own (v3 _anchors 910-917), they must survive on a canvas, and there is no
// token for "a fifth" to read.

import { fold12Column } from "./bins";
import type { ChromaResult } from "./chromaClient.svelte";
import type { FrameWindow } from "./heatmapGeometry";
import { type MatchAnchors, matchFrame, rotate } from "./match";

/** Top gutter, so the curve never collides with the reference row. */
export const CURVE_TOP_PX = 13;
export const CURVE_BOTTOM_PAD_PX = 4;
/** Floor on the anchor span, so a degenerate target cannot divide by zero. */
export const CURVE_SPAN_MIN = 0.06;
export const CURVE_PAD_LO = 0.22;
export const CURVE_PAD_HI = 0.12;

/** v3 2039. CONSONANCE COLOUR has no toggle: v3 729 says it is always on. */
export const CONSONANCE_SCALE_LABEL = "consonance colour";

export const ANCHOR_COLORS: Readonly<Record<"unison" | "fifth" | "tritone", string>> = {
  unison: "oklch(58% 0.13 155)",
  fifth: "oklch(60% 0.12 90)",
  tritone: "oklch(58% 0.17 25)",
};

export interface CurveAxis {
  lo: number;
  hi: number;
}

export function curveAxis(a: MatchAnchors): CurveAxis {
  const span = Math.max(CURVE_SPAN_MIN, a.unison - a.tritone);
  return { lo: a.tritone - span * CURVE_PAD_LO, hi: a.unison + span * CURVE_PAD_HI };
}

export function curveY(match: number, axis: CurveAxis, heightPx: number): number {
  const span = Math.max(1e-9, axis.hi - axis.lo);
  const usable = Math.max(1, heightPx - CURVE_TOP_PX - CURVE_BOTTOM_PAD_PX);
  const y = heightPx - CURVE_BOTTOM_PAD_PX - ((match - axis.lo) / span) * usable;
  return y < CURVE_TOP_PX ? CURVE_TOP_PX : y > heightPx ? heightPx : y;
}

/**
 * One score per VISIBLE frame, at the ANALYSIS detune. The window is clamped
 * to the clip, so a stale window after a shorter clip lands cannot read past
 * the end of the array.
 *
 * `analysisDetuneCents` is NOT `clip.detune_cents`. M5 T10's runStretch
 * already pitch-shifts the preview by `clip.detune_cents / 100`, and this
 * milestone analyses that preview, so `result.fold12` is ALREADY detuned:
 * rotating it again by the clip's detune would apply the detune twice. Task 11
 * derives the one right number (`analysisDetuneCents`: 0 for a previewAudio,
 * `clip.detune_cents` for the raw clip.audio) and passes it here. The
 * parameter stays because the raw-audio case is real -- runStretch returns
 * early when `clip.native_bpm == null`, leaving previewAudio null.
 */
export function windowScores(
  result: ChromaResult,
  target: Float32Array,
  win: FrameWindow,
  analysisDetuneCents: number,
): number[] {
  const from = Math.max(0, Math.floor(win.from));
  const to = Math.min(result.T, Math.ceil(win.to));
  const semis = analysisDetuneCents / 100;
  const out: number[] = [];
  for (let f = from; f < to; f++) {
    out.push(matchFrame(rotate(fold12Column(result.fold12, result.T, f), semis), target));
  }
  return out;
}

export interface LegendTick {
  label: "unison" | "fifth" | "tritone";
  value: number;
  pct: number;
}

/** Ascending by value, as the drawing sorts them, each clamped onto the strip. */
export function legendTicks(a: MatchAnchors): LegendTick[] {
  const raw: LegendTick[] = [
    { label: "unison", value: a.unison, pct: 0 },
    { label: "fifth", value: a.fifth, pct: 0 },
    { label: "tritone", value: a.tritone, pct: 0 },
  ];
  return raw
    .sort((x, y) => x.value - y.value)
    .map((t) => ({ ...t, pct: Math.min(99, Math.max(1, t.value * 100)) }));
}

/** Plain words for a score, against this target's own three reference points. */
export function matchVerdict(score: number, a: MatchAnchors): string {
  if (score >= a.unison - 0.02) return "at unison";
  if (score >= a.fifth) return "above a fifth";
  if (score >= a.tritone) return "between fifth and tritone";
  return "below a tritone";
}
