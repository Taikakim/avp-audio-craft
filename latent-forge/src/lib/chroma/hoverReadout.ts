// The hover readout's content (spec §5.4: "reads note name + frame index into
// the readout (14 px note, 9 px detail)"; v3 onChromaHover 1944-1965 and the
// two strings at 1968-1973).
//
// Pure, and deliberately NOT a component: what a pixel means is the part that
// breaks, and it can be pinned here without a canvas. The component below does
// nothing but put the two strings in two elements.
//
// One correction to the drawing. v3's hover derives the pitch class from
// (row / 128) * 12, which assumes C sits at bin 0. It does not -- C is at bin
// 2.0 (the same_chroma PITFALL, spec §5.4) -- so the drawing's readout names
// the wrong note near every class boundary. This goes through Task 6's
// rowPitchClass/rowCents, which go through Task 1's binToPitchClass.

import { NOTE_NAMES, fold12Column } from "./bins";
import type { ChromaResult } from "./chromaClient.svelte";
import { type ChromaView, type FrameWindow, cellValue, rowCents, rowPitchClass, xToFrame, yToRow } from "./heatmapGeometry";
import { matchFrame, rotate } from "./match";

/** Spec §5.4, and v3 339-340. */
export const HOVER_NOTE_PX = 14;
export const HOVER_DETAIL_PX = 9;

export interface ChromaHover {
  /** 0-based frame index into the clip's analysis. */
  frame: number;
  frames: number;
  /** Where in the clip, 0..1 -- what the lane's red marker is drawn from. */
  frac: number;
  pitchClass: number;
  /** Cents off the class centre in a band view; null in GLOBAL. */
  cents: number | null;
  /** The value of the cell actually under the pointer. */
  value: number;
  /** The frame's strongest 12-class entry, and its value. */
  top: number;
  topValue: number;
  match: number;
  sec: number;
}

export interface HoverArgs {
  result: ChromaResult;
  target: Float32Array;
  view: ChromaView;
  win: FrameWindow;
  x: number;
  y: number;
  widthPx: number;
  heightPx: number;
  /**
   * The ANALYSIS detune, not the clip's: 0 when `result` came from the
   * already-stretched `clip.previewAudio` (M5 T10's runStretch pitch-shifted
   * that audio by clip.detune_cents / 100, so the fold is already detuned and
   * rotating it again applies the detune twice), and clip.detune_cents when
   * `result` came from the raw clip.audio. Task 11 derives it once as
   * `analysisDetuneCents`; never re-derive it here.
   */
  detuneCents: number;
}

export function readHover(args: HoverArgs): ChromaHover | null {
  const { result, target, view, win, x, y, widthPx, heightPx, detuneCents } = args;
  const row = yToRow(y, view, heightPx);
  if (row === null) return null;            // the target's reference row
  if (result.T <= 0) return null;

  const frame = xToFrame(x, win, widthPx);
  const col = fold12Column(result.fold12, result.T, frame);
  let top = 0;
  for (let p = 1; p < 12; p++) if (col[p] > col[top]) top = p;

  return {
    frame,
    frames: result.T,
    frac: result.T > 1 ? frame / (result.T - 1) : 0,
    pitchClass: rowPitchClass(row, view),
    cents: rowCents(row, view),
    value: cellValue(result, view, frame, row),
    top,
    topValue: col[top],
    match: matchFrame(rotate(col, detuneCents / 100), target),
    sec: frame / result.fps,
  };
}

export function hoverNoteText(h: ChromaHover): string {
  // `h.cents` is `number | null`, and 0 is falsy: a band-view hover landing
  // exactly on a class centre (bins 2, 34, 66, 98) has cents === 0 and must
  // still show "0¢", or it is indistinguishable from a GLOBAL hover, where
  // cents genuinely do not exist. Test the null, never the truthiness.
  const cents = h.cents === null ? "" : `${h.cents > 0 ? "+" : ""}${h.cents}¢ `;
  return `${NOTE_NAMES[h.pitchClass]} ${cents} ${h.value.toFixed(2)}`.replace(/\s{3,}/g, "  ");
}

export function hoverDetailText(h: ChromaHover): string {
  return `strongest ${NOTE_NAMES[h.top]} ${h.topValue.toFixed(2)} · match ${h.match.toFixed(2)} · frame ${h.frame + 1}/${h.frames} · ${h.sec.toFixed(2)} s`;
}
