// Clip-box gesture geometry and label text. Nothing here touches the DOM or a
// store: callers pass in whatever rect/clientX they already have.

import type { ForgeClip } from "../forge/types";

/** Spec 4.3: "drag within 6px of an edge trims". */
export const EDGE_PX = 6;

export type EdgeHit = "start" | "end" | "body";

export function edgeHitTest(
  clientX: number,
  boxLeft: number,
  boxWidth: number,
  thresholdPx = EDGE_PX,
): EdgeHit {
  const local = clientX - boxLeft;
  if (local <= thresholdPx) return "start";
  if (local >= boxWidth - thresholdPx) return "end";
  return "body";
}

/** Spec 4.3: "vertical drag changes lane". One lane per `laneHeightPx` of travel. */
export function laneForDrag(
  startLane: number,
  dyPx: number,
  laneHeightPx: number,
  laneCount = 4,
): 0 | 1 | 2 | 3 {
  const delta = Math.round(dyPx / laneHeightPx);
  return Math.min(laneCount - 1, Math.max(0, startLane + delta)) as 0 | 1 | 2 | 3;
}

/**
 * Spec §10 X2: Alt+drag scrubs the clip's own audio in a loop. Maps the
 * pointer's position across the box to a position in the clip's SOURCE
 * material -- the box's left edge is the clip's `offset_sec`, the right edge
 * is `offset_sec + dur_sec` -- clamped so a drag past either end keeps
 * scrubbing the nearest still-valid instant rather than running off the clip.
 */
export function scrubOffsetSec(
  clientX: number,
  boxLeft: number,
  boxWidth: number,
  offsetSec: number,
  durSec: number,
): number {
  const frac = Math.min(1, Math.max(0, (clientX - boxLeft) / Math.max(1, boxWidth)));
  return offsetSec + frac * durSec;
}

/** Score label slot (spec 4.3: chroma match vs TARGET) -- M6 fills the number in. */
export const SCORE_PLACEHOLDER = "χ —";

/** "native→project ±stretch%", or null when the clip has no native tempo to stretch from. */
export function bpmLabel(clip: ForgeClip, projectBpm: number): string | null {
  if (clip.native_bpm == null || clip.native_bpm <= 0) return null;
  const stretchPct = (projectBpm / clip.native_bpm - 1) * 100;
  const sign = stretchPct >= 0 ? "+" : "";
  return `${clip.native_bpm.toFixed(1)}→${projectBpm} ${sign}${stretchPct.toFixed(1)}%`;
}
