// MATCH BPM / MATCH DOWNBEATS (spec §4.3), ported from the v1 store's
// matchBpm/matchDownbeats (sa3-studio/src/lib/store.svelte.ts) and
// musictime's meanBpm/circularMeanPhase/shortestPhaseDelta, onto the M5
// ForgeClip shape and lib/math/downbeats.ts's clipDownbeats. Pure: the two
// arrangement methods below are the only thing that touches the store.

import type { ForgeClip } from "../forge/types";
import { clipDownbeats } from "./downbeats";

/**
 * MATCH BPM: the mean of the clips' native tempos -- least stretch for all
 * of them. Only clips with a known native_bpm participate; null with none.
 */
export function meanNativeBpm(clips: ForgeClip[]): number | null {
  const valid = clips
    .map((c) => c.native_bpm)
    .filter((b): b is number => b != null && Number.isFinite(b) && b > 0);
  if (!valid.length) return null;
  return valid.reduce((a, b) => a + b, 0) / valid.length;
}

/** Circular mean of phases in [0,1) (each a fraction of a bar). */
export function circularMeanPhase(phases: number[]): number | null {
  if (!phases.length) return null;
  let x = 0;
  let y = 0;
  for (const p of phases) {
    const a = p * 2 * Math.PI;
    x += Math.cos(a);
    y += Math.sin(a);
  }
  if (Math.abs(x) < 1e-12 && Math.abs(y) < 1e-12) return null; // phases cancel exactly
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

/**
 * MATCH DOWNBEATS: shift every participating clip by the shortest path so
 * its downbeat lands on the common phase (spec §4.3) -- the circular mean of
 * all clips' phases. Tempo is left alone. A clip participates only if it has
 * at least one downbeat visible on the timeline (`clipDownbeats`); its phase
 * is taken from the earliest one. Fewer than two participating clips: there
 * is nothing to align to, so the map is empty.
 */
export function downbeatPhaseShifts(
  clips: ForgeClip[],
  bpm: number,
  beatsPerBar: number,
): Map<string, number> {
  const barSec = (60 / bpm) * beatsPerBar;
  const entries = clips
    .map((c) => ({ id: c.id, downbeats: clipDownbeats(c) }))
    .filter((e) => e.downbeats.length > 0);
  if (entries.length < 2) return new Map();

  const phaseOf = (sec: number) => (((sec / barSec) % 1) + 1) % 1;
  const phases = entries.map((e) => phaseOf(e.downbeats[0]));
  const mean = circularMeanPhase(phases);
  if (mean === null) return new Map();

  const out = new Map<string, number>();
  entries.forEach((e, i) => {
    const delta = shortestPhaseDelta(phases[i], mean) * barSec;
    if (Math.abs(delta) > 1e-9) out.set(e.id, delta);
  });
  return out;
}
