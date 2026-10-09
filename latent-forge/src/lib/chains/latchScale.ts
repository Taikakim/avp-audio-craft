// How the LANE CHAIN's LatCH controls are scaled and read out. Pure: no DOM, no store, no fetch.
//
// Why this exists (Kim, 2026-10-09: "look at the weight and target scaling for the RMS heads and
// hardness ... hardness has a quite narrow useable range ... latch targets should show unit and
// value ... the ramp does not work with hardness, it becomes a wall of sound"):
//
//  * WEIGHT was a linear 0..50 slider in steps of 0.1. The weight is a multiple of the head's default
//    gain (512), and eval/latch_bracket_quality.json says where each head's output breaks up:
//    weight 16 for most heads, 1 for rms_energy_air and spectral_flatness on ambient material,
//    and 0.25 for hardness (it broke at weight 1 on goa -- Kim's "concrete slab"). On the old slider
//    hardness's whole usable range was the first half percent of the travel and the 0.1 step could
//    reach three values of it. The slider is now cubic, so the first fifth of the travel is 0..0.4.
//  * The sampler's ramp_up / ramp_down run 0 -> value in RAW feature units. That is fine for a dB head
//    near -30 and nonsense for hardness (66.2 +/- 3.5), whose ramp starts 19 sigma outside the data.
//    A ramp here has explicit ends (value_from -> value), built server-side as target_raw.

import type { LatchHeadInfo } from "./latch";
import type { LatchSlot } from "../forge/types";

// ------------------------------------------------------------------ weight

/** parse_chain's own bound on a slot weight. */
export const WEIGHT_MAX = 50;

/** weight = WEIGHT_MAX * position^3: 0.25 sits at 17 % of the travel, 1 at 27 %, 16 at 68 %. */
const WEIGHT_POWER = 3;

function clamp(v: number, lo: number, hi: number): number {
  return v < lo ? lo : v > hi ? hi : v;
}

export function weightToPos(weight: number): number {
  return Math.pow(clamp(weight, 0, WEIGHT_MAX) / WEIGHT_MAX, 1 / WEIGHT_POWER);
}

/** Two decimals under 10, one above: what the cubic slider can actually resolve, and no false precision. */
export function roundWeight(w: number): number {
  return w < 10 ? Math.round(w * 100) / 100 : Math.round(w * 10) / 10;
}

export function posToWeight(pos: number): number {
  return roundWeight(WEIGHT_MAX * Math.pow(clamp(pos, 0, 1), WEIGHT_POWER));
}

/** The head's default gain; /info carries it, 512 is every medium head's. */
export function defaultGain(head: LatchHeadInfo | undefined): number {
  return head && Number.isFinite(head.default_gain) && head.default_gain > 0 ? head.default_gain : 512;
}

/**
 * The weight past which the head's output breaks up, or null when nothing is known. /info reports it
 * as usable_max_weight (usable_max_gain / default_gain); a server that predates it sends neither.
 */
export function usableMaxWeight(head: LatchHeadInfo | undefined): number | null {
  if (!head) return null;
  if (typeof head.usable_max_weight === "number" && head.usable_max_weight >= 0) return head.usable_max_weight;
  if (typeof head.usable_max_gain === "number" && head.usable_max_gain >= 0) return head.usable_max_gain / defaultGain(head);
  return null;
}

/**
 * The guidance strength a slot really applies: max(rho, mu) x default gain x weight. The server turns
 * rho/mu into hparams x (slot-1 gain) and then weights each slot by gain_k / gain_1, so every slot's
 * own strength comes out as hparam x gain_k x weight_k. It is the same unit as the bracket's "gain".
 */
export function effectiveGain(head: LatchHeadInfo | undefined, weight: number, hparams: { rho: number; mu: number }): number {
  return Math.max(hparams.rho, hparams.mu) * defaultGain(head) * weight;
}

/** Whole-number gains read better than 512.0000001. */
export function formatGain(g: number): string {
  if (g >= 100) return String(Math.round(g));
  return String(Math.round(g * 10) / 10);
}

export interface WeightReadout {
  text: string;
  /** true when the strength is past the head's clean limit */
  warn: boolean;
}

export function weightReadout(
  head: LatchHeadInfo | undefined, weight: number, hparams: { rho: number; mu: number },
): WeightReadout {
  const gain = effectiveGain(head, weight, hparams);
  const usable = usableMaxWeight(head);
  if (!head || usable === null) return { text: `gain ${formatGain(gain)}`, warn: false };
  // compared in gain, so a raised ρ/μ counts as much as a raised weight
  const limit = usable * defaultGain(head);
  if (gain > limit + 1e-9) return { text: `gain ${formatGain(gain)} · past ${formatGain(limit)}, breaks up`, warn: true };
  return { text: `gain ${formatGain(gain)} · limit ${formatGain(limit)}`, warn: false };
}

// ------------------------------------------------------------------ target

export function isRamp(kind: string): boolean {
  return kind === "ramp_up" || kind === "ramp_down";
}

/** The feature's unit: the server's, else dB for the rms family and bpm for a beat grid; "" otherwise. */
export function unitsOf(head: LatchHeadInfo | undefined, kind: string): string {
  if (kind === "beat_grid") return "bpm";
  if (!head) return "";
  if (typeof head.units === "string") return head.units;
  return head.name.startsWith("rms_") ? "dB" : "";
}

export interface TargetScale {
  min: number;
  max: number;
  step: number;
  /** decimals a value of this step needs */
  decimals: number;
}

/** A power of ten at or below x: 0.351 -> 0.1, 0.0099 -> 0.001. */
function niceStep(x: number): number {
  if (!(x > 0) || !Number.isFinite(x)) return 0.01;
  return Math.pow(10, Math.floor(Math.log10(x)));
}

/** The TARGET slider: the head's own slider_min..slider_max (its training mean +/- 2 sigma); 60..200 for a beat grid. */
export function targetScale(head: LatchHeadInfo | undefined, kind: string): TargetScale {
  if (kind === "beat_grid") return { min: 60, max: 200, step: 1, decimals: 0 };
  const min = head?.slider_min ?? 0;
  const max = head?.slider_max ?? 1;
  const step = niceStep((max - min) / 100);
  return { min, max, step, decimals: Math.max(0, -Math.floor(Math.log10(step) + 1e-9)) };
}

/** "-12.0" or "66.2": at the slider's own precision, never more. */
export function formatValue(v: number, decimals: number): string {
  return v.toFixed(Math.max(0, decimals));
}

/** How many standard deviations of the head's training data a value is from its mean; null if unknown. */
export function zScore(value: number, head: LatchHeadInfo | undefined, kind: string): number | null {
  if (kind === "beat_grid" || !head) return null;
  const m = head.std_mean;
  const s = head.std_std;
  if (typeof m !== "number" || typeof s !== "number" || !(s > 0)) return null;
  return (value - m) / s;
}

/** Past this many sigma the head is extrapolating, and guidance towards it is violent. */
export const Z_WARN = 3;

export interface TargetReadout {
  text: string;
  warn: boolean;
}

/** "+0.4σ" under the field, or the warning that the value is outside anything the head was trained on. */
export function targetReadout(value: number, head: LatchHeadInfo | undefined, kind: string): TargetReadout | null {
  const z = zScore(value, head, kind);
  if (z === null) return null;
  const sign = z >= 0 ? "+" : "−";
  const text = `${sign}${Math.abs(z).toFixed(1)}σ`;
  if (Math.abs(z) > Z_WARN) return { text: `${text} · outside the trained range`, warn: true };
  return { text, warn: false };
}

// ------------------------------------------------------------------ ramp

type RampSlot = Pick<LatchSlot, "kind" | "value"> & { value_from?: number | null };

/**
 * The two ends as the request will build them. A slot with no value_from is the sampler's own ramp,
 * 0 -> value (ramp_up) or value -> 0 (ramp_down), and is shown as exactly that so that nothing about
 * an old session changes until a field is touched.
 */
export function rampEnds(slot: RampSlot): { from: number; to: number } {
  if (typeof slot.value_from === "number") return { from: slot.value_from, to: slot.value };
  return slot.kind === "ramp_down" ? { from: slot.value, to: 0 } : { from: 0, to: slot.value };
}

/** Edit the start; the end is written out explicitly so an old slot keeps its meaning. */
export function setRampFrom(slot: LatchSlot, from: number): void {
  const { to } = rampEnds(slot);
  slot.value_from = from;
  slot.value = to;
}

/** Edit the end (TARGET). */
export function setRampTo(slot: LatchSlot, to: number): void {
  const { from } = rampEnds(slot);
  slot.value_from = from;
  slot.value = to;
}

/**
 * Ends for a freshly chosen ramp: the middle half of the head's slider range (about its mean +/- 1
 * sigma), rising for ramp_up and falling for ramp_down. null when the head is not known, in which
 * case the slot keeps the sampler's 0 start.
 */
export function defaultRamp(head: LatchHeadInfo | undefined, kind: string): { from: number; to: number } | null {
  if (!head || !isRamp(kind)) return null;
  const { min, max, decimals } = targetScale(head, kind);
  const lo = Number((min + (max - min) * 0.25).toFixed(decimals + 1));
  const hi = Number((min + (max - min) * 0.75).toFixed(decimals + 1));
  return kind === "ramp_down" ? { from: hi, to: lo } : { from: lo, to: hi };
}
