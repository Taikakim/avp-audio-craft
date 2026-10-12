// Spec §4.5's HISTORY option text. Pure so the ordering rule -- the store holds newest LAST and the
// select shows newest FIRST -- is tested once, here, rather than being re-derived in markup.

import type { RenderHistoryEntry } from "../forge/types";

/** M1's own placeholder copy, kept verbatim so the frame reads the same before and after M9. */
export const HISTORY_EMPTY_LABEL = "no renders yet";

export interface HistoryOption {
  /** Index into `history.renders` (storage order), which is what `history.select` takes. */
  index: number;
  label: string;
}

/**
 * `0` means "the result carried no duration_sec in meta" (Writer A's `durationOf` returns 0 there),
 * not "a zero-length render". Printing `0.0 s` would be a claim the server never made.
 */
export function lengthLabel(durSec: number | null): string {
  if (durSec === null || !Number.isFinite(durSec) || durSec <= 0) return "—";
  return `${durSec.toFixed(1)} s`;
}

/**
 * The tag (`GEN`/`A2A`/`INPAINT`/`MIX`) is already the first word of `entry.label`, which Writer A's
 * `jobs.submit` builds from the job's own kind; the length §4.5 asks for is appended here.
 */
export function historyOptions(renders: RenderHistoryEntry[]): HistoryOption[] {
  return renders
    .map((e, index) => ({ index, label: `${e.label} · ${lengthLabel(e.dur_sec)}` }))
    .reverse();
}
