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
// I3 fix wave: the canonical SnapMode now lives in math/snap.ts (below).
import type { SnapMode } from "./math/snap";

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

// I3 fix wave (2026-09-30): `SnapMode`/`SNAP_MODES` used to be declared here
// too -- a second, DIFFERENT list from lib/math/snap.ts's (missing "lane"
// magnetic-downbeats and "free", spec 4.3's two most-used modes) that could,
// and did, silently disagree with the one the UI actually renders. Deleted;
// `store.svelte.ts` below imports the type from math/snap.ts now. `snapSec`
// just below still takes a plain SnapMode string, so it keeps working
// unchanged against the unified type -- "bar"/"beat"/"1/8"/"1/16"/"1/32"/"edge"
// exist in both; store.svelte.ts's own default ("bar") is one of them.

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
  if (mode === "free") return Math.max(0, sec);
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

// I3 fix wave: `gridLines` used to live here, computed from this module's own
// secPerBar/secPerBeat. LaneCanvas.svelte's background grid now uses the copy
// in lib/math/snap.ts, built on that module's own gridIntervalSec -- one
// canonical source for "how long is a bar/beat" instead of two.

// I3 fix wave: meanBpm/circularMeanPhase/shortestPhaseDelta below are NOT
// deleted, unlike SnapMode/SNAP_MODES/gridLines above -- lib/math/tempoMatch.ts
// has its own circularMeanPhase/shortestPhaseDelta (identical bodies) plus
// meanNativeBpm, but meanNativeBpm takes ForgeClip[] (reads .native_bpm),
// while store.svelte.ts's OWN matchBpm/matchDownbeats (below, still compiled,
// though unreachable from any live-mounted UI once C1's rewire moved the
// header/keyboard/Save off this store) operate on the v1 `Clip[]` shape
// (`.bpm`) from lib/types.ts -- a genuinely different domain, not just a
// copy-paste. Retiring store.svelte.ts's clip-arrangement surface entirely is
// a bigger, separate call (flagged in this store's own TODO at the top of the
// file) than this fix wave's scope.
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
