// Pure geometry for the chroma heatmap (spec §5.4). Kept out of the component
// for the reason M5 T5 gives for the lane canvas: jsdom has no
// CanvasRenderingContext2D, so every piece of DECIDABLE geometry lives here
// where vitest can pin it, and the component only turns these answers into
// fillRect calls.
//
// Two coordinate facts everything else depends on:
//   * pitch class 0 (C) is drawn at the BOTTOM row, as the drawing does it
//     (v3 1184: bodyY + (rows - 1 - r) * rowH);
//   * in a band view the row index IS the raw bin index, and C sits at bin
//     2.0, not 0 -- the same_chroma PITFALL. Row -> class goes through Task
//     1's binToPitchClass, never through (row / 128) * 12, which is what the
//     drawing's own hover does and which is wrong by two bins everywhere.

import { BINS_PER_BAND, BINS_PER_SEMITONE, binToPitchClass, fold12Column, pitchClassToBin } from "./bins";
import type { ChromaResult } from "./chromaClient.svelte";

/** The target's reference row, v3 1174. */
export const REF_ROW_H = 9;
export const REF_GAP = 2;
export const BODY_Y = REF_ROW_H + REF_GAP;

/** Zooming past this stops being a heatmap and starts being a bar chart. */
export const MIN_VISIBLE_FRAMES = 8;

/** v3 1187 skips a cell below this; at 128 rows that is most of them. */
export const CELL_FLOOR = 0.04;

export type ChromaView = "global" | "bass" | "mid" | "high";

export const CHROMA_VIEWS: readonly ChromaView[] = ["global", "bass", "mid", "high"];

export const VIEW_LABELS: Record<ChromaView, string> = {
  global: "GLOBAL",
  bass: "BASS oct1",
  mid: "MID oct5",
  high: "HIGH oct9",
};

export function bandIndexFor(view: ChromaView): 0 | 1 | 2 | null {
  return view === "bass" ? 0 : view === "mid" ? 1 : view === "high" ? 2 : null;
}

export function rowCount(view: ChromaView): number {
  return view === "global" ? 12 : BINS_PER_BAND;
}

/** Half-open [from, to), in frames. */
export interface FrameWindow {
  from: number;
  to: number;
}

export function clampWindow(win: FrameWindow, T: number): FrameWindow {
  const total = Math.max(1, Math.floor(T));
  const floor = Math.min(MIN_VISIBLE_FRAMES, total);
  const span = Math.min(total, Math.max(floor, win.to - win.from));
  const from = Math.min(Math.max(0, win.from), total - span);
  return { from, to: from + span };
}

export function fullWindow(T: number): FrameWindow {
  return clampWindow({ from: 0, to: Math.max(1, Math.floor(T)) }, T);
}

/**
 * `factor > 1` zooms IN (fewer frames), matching M5 T3's
 * middleDragZoomFactor, which returns > 1 for a negative deltaY (an upward
 * drag). `anchorFrac` is the pointer's position across the canvas, 0..1; the
 * frame under it stays put.
 */
export function zoomWindow(win: FrameWindow, factor: number, anchorFrac: number, T: number): FrameWindow {
  const total = Math.max(1, Math.floor(T));
  const span = win.to - win.from;
  const anchor = win.from + anchorFrac * span;
  const floor = Math.min(MIN_VISIBLE_FRAMES, total);
  const f = Number.isFinite(factor) && factor > 0 ? factor : 1;
  const next = Math.min(total, Math.max(floor, span / f));
  const from = anchor - anchorFrac * next;
  return clampWindow({ from, to: from + next }, T);
}

/** Content follows the hand: a rightward drag reveals EARLIER frames. */
export function scrollWindow(win: FrameWindow, deltaPx: number, widthPx: number, T: number): FrameWindow {
  const span = win.to - win.from;
  const perPx = span / Math.max(1, widthPx);
  const from = win.from - deltaPx * perPx;
  return clampWindow({ from, to: from + span }, T);
}

export function frameToX(frame: number, win: FrameWindow, widthPx: number): number {
  const span = Math.max(1e-9, win.to - win.from);
  return ((frame - win.from) / span) * widthPx;
}

export function xToFrame(x: number, win: FrameWindow, widthPx: number): number {
  const span = Math.max(1e-9, win.to - win.from);
  const raw = Math.floor(win.from + (x / Math.max(1, widthPx)) * span);
  const lo = Math.floor(win.from);
  const hi = Math.ceil(win.to) - 1;
  return raw < lo ? lo : raw > hi ? hi : raw;
}

export function rowHeight(view: ChromaView, heightPx: number): number {
  return Math.max(0, heightPx - BODY_Y) / rowCount(view);
}

/** Row 0 (C, or bin 0) sits at the BOTTOM -- v3 1184. */
export function rowToY(row: number, view: ChromaView, heightPx: number): number {
  return BODY_Y + (rowCount(view) - 1 - row) * rowHeight(view, heightPx);
}

/** null inside the reference row, which is the target's, not the clip's. */
export function yToRow(y: number, view: ChromaView, heightPx: number): number | null {
  if (y < BODY_Y) return null;
  const rows = rowCount(view);
  const rh = rowHeight(view, heightPx);
  if (rh <= 0) return null;
  const row = rows - 1 - Math.floor((y - BODY_Y) / rh);
  return row < 0 ? 0 : row > rows - 1 ? rows - 1 : row;
}

export function rowPitchClass(row: number, view: ChromaView): number {
  return view === "global" ? ((row % 12) + 12) % 12 : binToPitchClass(row);
}

/** Cents off the class centre for a band row; null for GLOBAL, which has none. */
export function rowCents(row: number, view: ChromaView): number | null {
  if (view === "global") return null;
  const centre = pitchClassToBin(binToPitchClass(row));
  let d = row - centre;
  // The band wraps: bin 125 is five bins BELOW C's next centre at 2 + 128.
  while (d > BINS_PER_BAND / 2) d -= BINS_PER_BAND;
  while (d < -BINS_PER_BAND / 2) d += BINS_PER_BAND;
  return Math.round((d / BINS_PER_SEMITONE) * 100);
}

/**
 * The value drawn in one cell. GLOBAL reads the server's own transported
 * fold12 -- §5.4's definition ("sum the three bands through fold_to_12, then
 * per-frame normalise to max 1") is exactly what the server computes and
 * ships as fold12 (M2 T12's chroma_payload, at `scale: 1.0` because the
 * values are already in [0,1] per frame, not because 1.0 is a whole-clip
 * scale). WINTERMUTE's 2026-09-22 ruling: this is the SAME array the
 * match/scan/clip-score path reads, so there is no second, client-side fold
 * to compute here. A band view is that band's raw 128 bins, untouched.
 */
export function cellValue(result: ChromaResult, view: ChromaView, frame: number, row: number): number {
  const band = bandIndexFor(view);
  if (band === null) return fold12Column(result.fold12, result.T, frame)[((row % 12) + 12) % 12];
  return result.bands[(band * BINS_PER_BAND + row) * result.T + frame];
}

/**
 * The whole column for one frame -- rowCount(view) values, in the same order
 * cellValue returns them row by row.
 *
 * For a band view this is a genuine batching win, unchanged by the fold
 * decision below: cellValue's band branch is already a single array read, so
 * nothing here saves it any work beyond what materialising the 128 bins once
 * always saved.
 *
 * For GLOBAL the saving is smaller than it used to be, but it has not gone
 * away. Before WINTERMUTE's 2026-09-22 ruling, cellValue's GLOBAL branch
 * re-folded all 3 x 128 raw bins on every call; now that GLOBAL just reads the
 * transported fold12, cellValue's GLOBAL branch is fold12Column(...)[row] --
 * but fold12Column still allocates and fills a fresh Float32Array(12) on
 * EVERY call, regardless of which single row the caller wanted. A row loop
 * over GLOBAL's twelve rows would still call fold12Column twelve times for
 * one frame's pixels -- including on every pointermove of a middle-drag.
 * Fold once, index twelve times: frameColumn keeps exactly that shape, even
 * though what it now saves is "one Float32Array(12) build" per frame rather
 * than "one 384-bin sum" per frame. Dropping it because the saving got
 * smaller would still be dropping a real, reachable cost.
 *
 * cellValue stays the hover path's accessor (Task 10), which reads one cell
 * and has no row loop to batch.
 */
export function frameColumn(result: ChromaResult, view: ChromaView, frame: number): Float32Array {
  const band = bandIndexFor(view);
  if (band === null) return fold12Column(result.fold12, result.T, frame);
  const out = new Float32Array(BINS_PER_BAND);
  for (let i = 0; i < BINS_PER_BAND; i++) {
    out[i] = result.bands[(band * BINS_PER_BAND + i) * result.T + frame];
  }
  return out;
}
