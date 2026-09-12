// Bar/beat/latent-frame arithmetic for the timeline.
//
// Three clocks matter here and they are NOT the same:
//   - seconds        the audio clock; what the transport actually plays
//   - bars/beats     the musical clock, derived from the project BPM
//   - latent frames  44100/4096 = 10.7666 Hz (92.9 ms), the encoder's clock
//
// The latent clock is shown, never enforced: audio-domain placement is free
// (ORIENTATION.md §3). It appears in the ruler and the readouts only so you can
// see where a commit-time encode will land.

import { LATENT_HOP, SAMPLE_RATE } from "./types";

export const LATENT_FPS = SAMPLE_RATE / LATENT_HOP; // 10.7666...

export interface Meter {
  bpm: number;
  beatsPerBar: number;
}

export const DEFAULT_METER: Meter = { bpm: 120, beatsPerBar: 4 };

export function secPerBeat(m: Meter): number {
  return 60 / m.bpm;
}

export function secPerBar(m: Meter): number {
  return (60 / m.bpm) * m.beatsPerBar;
}

/** Latent frame index a given timeline second falls in. */
export function frameAt(sec: number): number {
  return Math.floor((sec * SAMPLE_RATE) / LATENT_HOP);
}

/** "bar.beat.ticks" in the design handoff's readout style (bar 2.1.00). */
export function formatBarsBeats(sec: number, m: Meter): string {
  const beats = sec / secPerBeat(m);
  const bar = Math.floor(beats / m.beatsPerBar) + 1;
  const beatInBar = Math.floor(beats % m.beatsPerBar) + 1;
  const ticks = Math.floor(((beats % 1) + 1e-9) * 100);
  return `${bar}.${beatInBar}.${String(ticks).padStart(2, "0")}`;
}

export function formatClock(sec: number): string {
  const sign = sec < 0 ? "-" : "";
  const s = Math.abs(sec);
  const mm = Math.floor(s / 60);
  return `${sign}${mm}:${(s % 60).toFixed(2).padStart(5, "0")}`;
}

export type SnapMode = "bar" | "beat" | "1/8" | "1/16" | "1/32" | "edge" | "off";

export const SNAP_MODES: { value: SnapMode; label: string }[] = [
  { value: "bar", label: "bar" },
  { value: "beat", label: "beat" },
  { value: "1/8", label: "1/8" },
  { value: "1/16", label: "1/16" },
  { value: "1/32", label: "1/32" },
  { value: "edge", label: "clip edges" },
  { value: "off", label: "free" },
];

/** Grid interval in seconds for the divisions that are pure meter maths. */
function gridInterval(mode: SnapMode, m: Meter): number | null {
  switch (mode) {
    case "bar":
      return secPerBar(m);
    case "beat":
      return secPerBeat(m);
    case "1/8":
      return secPerBeat(m) / 2;
    case "1/16":
      return secPerBeat(m) / 4;
    case "1/32":
      return secPerBeat(m) / 8;
    default:
      return null;
  }
}

/**
 * Snap a candidate position. `edges` are other clips' start/end times, used by
 * the "clip edges" mode and ignored otherwise. `toleranceSec` keeps edge-snap
 * magnetic rather than absolute -- drag far enough and it lets go.
 */
export function snapSec(
  sec: number,
  mode: SnapMode,
  m: Meter,
  edges: number[] = [],
  toleranceSec = 0.12,
): number {
  if (mode === "off") return Math.max(0, sec);
  if (mode === "edge") {
    let best = sec;
    let bestDist = toleranceSec;
    for (const e of edges) {
      const d = Math.abs(e - sec);
      if (d < bestDist) {
        best = e;
        bestDist = d;
      }
    }
    return Math.max(0, best);
  }
  const interval = gridInterval(mode, m);
  if (!interval) return Math.max(0, sec);
  return Math.max(0, Math.round(sec / interval) * interval);
}

/** Grid lines to draw across a visible span, coarsest first so bars can be drawn stronger. */
export function gridLines(
  fromSec: number,
  toSec: number,
  m: Meter,
  pxPerSec: number,
): { sec: number; kind: "bar" | "beat" | "sub" }[] {
  const out: { sec: number; kind: "bar" | "beat" | "sub" }[] = [];
  const bar = secPerBar(m);
  const beat = secPerBeat(m);
  // Don't draw a grid finer than ~8px or it turns into a grey wash.
  const drawBeats = beat * pxPerSec > 8;
  const drawSubs = (beat / 4) * pxPerSec > 8;
  const step = drawSubs ? beat / 4 : drawBeats ? beat : bar;
  const start = Math.floor(fromSec / step) * step;
  for (let t = start; t <= toSec; t += step) {
    if (t < 0) continue;
    const inBar = Math.abs((t / bar) % 1);
    const inBeat = Math.abs((t / beat) % 1);
    const isBar = inBar < 1e-6 || inBar > 1 - 1e-6;
    const isBeat = inBeat < 1e-6 || inBeat > 1 - 1e-6;
    out.push({ sec: t, kind: isBar ? "bar" : isBeat ? "beat" : "sub" });
  }
  return out;
}

/**
 * The least-stretch meeting tempo: the mean of the clips' native BPMs.
 * Mirrors MATCH BPM in the design handoff -- "the clips meet at their mean
 * native BPM, so each is stretched as little as possible."
 */
export function meanBpm(bpms: number[]): number | null {
  const valid = bpms.filter((b) => Number.isFinite(b) && b > 0);
  if (!valid.length) return null;
  return valid.reduce((a, b) => a + b, 0) / valid.length;
}

/**
 * Circular mean of downbeat phases (each in [0,1) of a bar), and the shift that
 * moves a given phase onto it by the shortest path. MATCH DOWNBEATS in the
 * handoff shifts every clip by this, leaving tempo alone.
 */
export function circularMeanPhase(phases: number[]): number | null {
  if (!phases.length) return null;
  let x = 0;
  let y = 0;
  for (const p of phases) {
    const a = p * 2 * Math.PI;
    x += Math.cos(a);
    y += Math.sin(a);
  }
  if (Math.abs(x) < 1e-12 && Math.abs(y) < 1e-12) return null;
  const mean = Math.atan2(y / phases.length, x / phases.length) / (2 * Math.PI);
  return (mean + 1) % 1;
}

/** Shortest signed distance from phase `from` to phase `to`, in [-0.5, 0.5). */
export function shortestPhaseDelta(from: number, to: number): number {
  let d = (to - from) % 1;
  if (d >= 0.5) d -= 1;
  if (d < -0.5) d += 1;
  return d;
}
