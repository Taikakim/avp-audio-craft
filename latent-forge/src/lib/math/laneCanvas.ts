// Lane-canvas geometry that does not need a CanvasRenderingContext2D: the
// overlap-ink darkening, the clipping threshold, and which overlaps belong to
// a given lane. The component turns these answers into fillRect calls; jsdom
// has no canvas, so that part is left to Playwright (tests/timeline.spec.ts).

import type { Overlap } from "../stores/arrangement.svelte";

/**
 * Spec 4.3: "overlapping ink at lightness × 0.75". Colours arrive already
 * resolved through getComputedStyle -- but for this app's UNREGISTERED
 * custom properties (tokens.css has no `@property` block) that call returns
 * the literal token stream, not a browser-normalised rgb()/rgba() string
 * (the same fact downbeats.ts's own comment documents for `--downbeat`).
 * Every colour token here is written as `oklch(L% C H)`, so a channel-wise
 * scale of three regex-matched numbers -- treating L/C/H as if they were
 * R/G/B -- would not compute "lightness × factor" at all; it would produce
 * an unrelated colour. Handle both shapes explicitly:
 *   - `rgb()`/`rgba()`: scale each channel (kept for the unit tests below,
 *     and any future literal-rgb caller).
 *   - `oklch()`: scale ONLY the L channel, which IS "lightness × factor".
 *   - anything else: passed through unchanged.
 */
export function darkenInk(css: string, factor: number): string {
  const rgb = css.match(/^rgba?\(([^)]+)\)$/i);
  if (rgb) {
    const nums = rgb[1].match(/-?\d+(\.\d+)?/g);
    if (!nums || nums.length < 3) return css;
    const [r, g, b] = nums.slice(0, 3).map(Number);
    return `rgb(${Math.round(r * factor)}, ${Math.round(g * factor)}, ${Math.round(b * factor)})`;
  }
  const oklch = css.match(
    /^oklch\(\s*(-?\d+(?:\.\d+)?)%\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s*(\/[^)]+)?\)$/i,
  );
  if (oklch) {
    const l = Number(oklch[1]) * factor;
    const rest = oklch[4] ? ` ${oklch[4].trim()}` : "";
    return `oklch(${l.toFixed(2)}% ${oklch[2]} ${oklch[3]}${rest})`;
  }
  return css;
}

/** Spec 4.3: red 2px clip marks at top/bottom where |x| > 1. */
export function isClipping(lo: number, hi: number): boolean {
  return Math.abs(hi) > 1 || Math.abs(lo) > 1;
}

export function overlapSpansInLane(
  overlaps: Overlap[],
  laneIndex: number,
): { start_sec: number; end_sec: number }[] {
  return overlaps
    .filter((o) => o.lane === laneIndex)
    .map((o) => ({ start_sec: o.start_sec, end_sec: o.end_sec }));
}
