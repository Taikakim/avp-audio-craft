// Downbeat positions on the timeline, and how strongly one agrees with another
// lane's. Spec 4.3: markers interpolate from --downbeat toward --downbeat-hit
// for downbeats coinciding with another lane's within one 32nd note at mean
// project tempo, on a `** 0.7` ramp across that window.

import type { ForgeClip } from "../forge/types";

export const COINCIDENCE_DIVISION = 32;

/**
 * Spec 4.3's ramp exponent. The WINDOW is the spec's (one 32nd note, half the
 * drawing's quarter-beat, because a quarter-beat lights markers that are
 * audibly not together); the CURVE is the drawing's `_dbColor`, because a
 * linear ramp makes a near miss almost invisible. Settled 2026-09-21 and now
 * stated once and exactly in the spec.
 */
export const COINCIDENCE_RAMP_EXP = 0.7;

/**
 * A clip's analysed downbeats in TIMELINE seconds: scaled from SOURCE seconds
 * (clip.downbeats_sec, unstretched, at the clip's own native_bpm -- forge/types.ts's
 * doc comment on `downbeats_sec`) into the STRETCHED timeline domain that
 * start_sec/offset_sec/dur_sec live in, THEN shifted by the clip's position and
 * cropped to what its trim actually leaves visible.
 *
 * The scale factor is native_bpm/projectBpm (arrangement.setBpm's own ratio,
 * generalised to an absolute native->current conversion): a clip native to a
 * faster tempo than the project is stretched slower, i.e. longer in time, so
 * its downbeats land later than their raw SOURCE-second value. `native_bpm ==
 * null` (never analysed, or analysis found nothing) is the identity -- there
 * is nothing to scale against, so the raw value already IS the timeline value
 * (this is also why every existing fixture with `native_bpm: null` could not
 * have caught this scaling bug).
 */
export function clipDownbeats(clip: ForgeClip, projectBpm: number): number[] {
  const scale = clip.native_bpm == null || clip.native_bpm <= 0 ? 1 : clip.native_bpm / projectBpm;
  const out: number[] = [];
  for (const d of clip.downbeats_sec ?? []) {
    const rel = d * scale - clip.offset_sec;
    if (rel < -1e-9 || rel > clip.dur_sec + 1e-9) continue;
    out.push(clip.start_sec + rel);
  }
  return out;
}

export function laneDownbeats(clips: ForgeClip[], lane: number, projectBpm: number): number[] {
  return clips
    .filter((c) => c.lane === lane)
    .flatMap((c) => clipDownbeats(c, projectBpm))
    .sort((a, b) => a - b);
}

/** One 32nd note at the project tempo; a whole note is 4 beats. */
export function coincidenceToleranceSec(bpm: number): number {
  const beat = 60 / bpm;
  return (beat * 4) / COINCIDENCE_DIVISION;
}

/**
 * 1 when `sec` lands exactly on one of `others`, falling to 0 at one 32nd away:
 * spec 4.3's `t = max(0, 1 - dt / w) ** 0.7`. The ramp is what makes a near
 * miss visibly a near miss instead of flicking between two colours, and the
 * exponent is what keeps it visible rather than almost-off.
 */
export function coincidence(sec: number, others: number[], bpm: number): number {
  const tol = coincidenceToleranceSec(bpm);
  let best = 0;
  for (const o of others) {
    const d = Math.abs(o - sec);
    if (d >= tol) continue;
    best = Math.max(best, (1 - d / tol) ** COINCIDENCE_RAMP_EXP);
  }
  return best;
}

/**
 * The marker colour at coincidence `t`, built directly in OKLCH.
 *
 * It does NOT read a CSS custom property. An unregistered custom property's
 * computed value is its literal token stream, so
 * `getComputedStyle(el).getPropertyValue("--downbeat")` hands back the STRING
 * `"oklch(78% 0.08 250)"` -- there are no channels to mix, and scraping the
 * digits out of it yields `rgb(78, 0, 250)`, an indigo. Canvas accepts an
 * `oklch()` string directly, so we build one.
 *
 * Endpoints are the spec's (4.3) and the interpolation is per channel IN
 * OKLCH, as the drawing does it (`_dbColor`, v3:1155-1158): an sRGB lerp
 * between these two passes through a desaturated grey-green that OKLCH does
 * not. Hue 95 is the spec's; the drawing says 100 -- the spec wins, recorded in
 * this milestone's Open questions.
 *
 * The rule "canvas colours come from getComputedStyle, never literal oklch"
 * still holds for every FLAT colour. This is the one ramp, and a ramp needs
 * channels; the endpoints live here because nothing can interpolate a token
 * stream.
 */
export const DOWNBEAT_DIM = { l: 78, c: 0.08, h: 250 } as const;
export const DOWNBEAT_HIT = { l: 85, c: 0.17, h: 95 } as const;

export function downbeatColor(t: number): string {
  const k = Math.max(0, Math.min(1, t));
  const l = DOWNBEAT_DIM.l + (DOWNBEAT_HIT.l - DOWNBEAT_DIM.l) * k;
  const c = DOWNBEAT_DIM.c + (DOWNBEAT_HIT.c - DOWNBEAT_DIM.c) * k;
  const h = DOWNBEAT_DIM.h + (DOWNBEAT_HIT.h - DOWNBEAT_DIM.h) * k;
  return `oklch(${l.toFixed(2)}% ${c.toFixed(3)} ${h.toFixed(1)})`;
}
