// The one coordinate transform every timeline surface shares: a timeline
// second to an on-screen pixel, and back. There is no native browser scroll
// here -- arrangement.scrollSec IS the scroll position, so every canvas and
// every clip box positions itself off this pair of functions and nothing else.

export function secToPx(sec: number, scrollSec: number, pxPerSec: number): number {
  return (sec - scrollSec) * pxPerSec;
}

export function pxToSec(px: number, scrollSec: number, pxPerSec: number): number {
  return Math.max(0, scrollSec + px / pxPerSec);
}

/** Left/width of a clip's box in screen pixels, floored at 1px so a near-zero clip still shows. */
export function clipSpanPx(
  startSec: number,
  durSec: number,
  scrollSec: number,
  pxPerSec: number,
): { left: number; width: number } {
  return { left: secToPx(startSec, scrollSec, pxPerSec), width: Math.max(1, durSec * pxPerSec) };
}
