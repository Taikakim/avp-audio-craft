// Ruler geometry: bars, beats and the latent-frame clock, plus the middle-drag
// zoom/scroll gesture's arithmetic. The latent row is informational only --
// ORIENTATION §3, restated in spec 4.3: placement is never quantised to it.

export const FRAME_HZ = 44100 / 4096; // 10.7666...Hz, i.e. 92.9ms/frame

export interface RulerTick {
  sec: number;
  kind: "bar" | "beat";
}

export function secPerBeat(bpm: number): number {
  return 60 / bpm;
}

export function secPerBar(bpm: number, beatsPerBar: number): number {
  return secPerBeat(bpm) * beatsPerBar;
}

export function barNumberAt(sec: number, bpm: number, beatsPerBar: number): number {
  return Math.floor(sec / secPerBar(bpm, beatsPerBar)) + 1;
}

/** Latent frame index a given timeline second falls in (informational — never snaps anything). */
export function frameAt(sec: number): number {
  return Math.floor(sec * FRAME_HZ);
}

/**
 * Bar and beat lines visible in [fromSec, toSec]. Beat lines are dropped once
 * they are under 8px apart on screen, matching the drawing's own thinning
 * (v3 1038-1041) so the ruler never turns into a grey wash when zoomed out.
 */
export function rulerTicks(
  fromSec: number,
  toSec: number,
  bpm: number,
  beatsPerBar: number,
  pxPerSec: number,
): RulerTick[] {
  const bar = secPerBar(bpm, beatsPerBar);
  const beat = secPerBeat(bpm);
  const drawBeats = beat * pxPerSec > 8;
  const step = drawBeats ? beat : bar;
  const out: RulerTick[] = [];
  const start = Math.max(0, Math.floor(fromSec / step) * step);
  for (let t = start; t <= toSec + 1e-9; t += step) {
    const inBar = Math.abs((t / bar) % 1);
    const isBar = inBar < 1e-6 || inBar > 1 - 1e-6;
    out.push({ sec: Math.max(0, t), kind: isBar ? "bar" : "beat" });
  }
  return out;
}

/**
 * Spec 4.3: middle-drag zooms vertically and scrolls horizontally in one
 * gesture. `deltaY`/`deltaX` are `clientY - startY` / `clientX - startX`.
 * Dragging up zooms in (more px/sec); dragging right scrolls the view
 * earlier, as if the hand were dragging the content itself.
 */
export function middleDragZoomFactor(deltaY: number): number {
  return Math.pow(1.012, -deltaY);
}

export function middleDragScrollDeltaSec(deltaX: number, pxPerSec: number): number {
  // `|| 0` normalises -0 (deltaX === 0 divides to -0) to +0 -- Object.is-sensitive
  // callers (vitest's toBe) and any downstream "is this exactly zero" check
  // should never see the sign bit for a no-op drag.
  return -deltaX / Math.max(1e-6, pxPerSec) || 0;
}
