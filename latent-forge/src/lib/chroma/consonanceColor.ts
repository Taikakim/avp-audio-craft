// The chroma heatmap's colour ramp (spec §5.4; v3 _drawChroma 1183-1190 and
// legendStops 2025-2028).
//
// THIS IS THE ONE DOCUMENTED EXCEPTION to "canvas colours come from
// getComputedStyle" (docs/latent-forge/HANDOUT.md). An unregistered custom
// property is NOT resolved by the engine, so
// getComputedStyle(el).getPropertyValue("--token") hands back the literal
// token STREAM -- the string "oklch(78% 0.08 250)" -- with no channels in it.
// That string is fine to assign straight to ctx.fillStyle, and FATAL to parse:
// a digit regex over it yields rgb(78, 0, 250), an indigo. A ramp needs three
// channels to interpolate, so it builds its own oklch() string, exactly as
// M5's downbeatColor (lib/math/downbeats.ts) and M10's xcorrColor
// (lib/stats/xcorrColor.ts) do. Do not "fix" this back into a token read.
//
// Two axes, deliberately independent:
//   HUE  carries the FRAME's harmonic match against the target -- consonant
//        frames run warm (60), dissonant ones cold (260).
//   L/C  carry the CELL's own energy, so a loud bin is dark and saturated and
//        a quiet one nearly disappears into the panel.

/** Hue at match = 1. */
export const CONSONANT_HUE = 60;
/** Hue at match = 0. v3: 60 + (1 - m) * 200. */
export const DISSONANT_HUE = 260;

export const CELL_L_TOP = 94;
export const CELL_L_SPAN = 48;
export const CELL_C_BASE = 0.02;
export const CELL_C_SPAN = 0.19;

/** The target reference row has its own hue so it never reads as a score. */
export const TARGET_ROW_HUE = 300;
export const TARGET_L_TOP = 90;
export const TARGET_L_SPAN = 46;
export const TARGET_C_BASE = 0.02;
export const TARGET_C_SPAN = 0.12;

/** The legend strip: one lightness and chroma, the hue axis alone (v3 2027). */
export const LEGEND_L = 58;
export const LEGEND_C = 0.17;
export const LEGEND_STOPS = 9;

function unit(v: number): number {
  return Number.isFinite(v) ? (v < 0 ? 0 : v > 1 ? 1 : v) : 0;
}

function oklch(l: number, c: number, h: number): string {
  return `oklch(${l.toFixed(2)}% ${c.toFixed(3)} ${h.toFixed(1)})`;
}

/** Hue for a harmonic-overlap score in 0..1. Clamped; NaN reads as dissonant. */
export function consonanceHue(match: number): number {
  return DISSONANT_HUE + (CONSONANT_HUE - DISSONANT_HUE) * unit(match);
}

/** One heatmap cell: `value` is the bin/class energy, `match` its frame's score. */
export function consonanceColor(value: number, match: number): string {
  const v = unit(value);
  return oklch(CELL_L_TOP - CELL_L_SPAN * v, CELL_C_BASE + CELL_C_SPAN * v, consonanceHue(match));
}

/** One cell of the target's reference row across the top of the heatmap. */
export function targetRowColor(value: number): string {
  const v = unit(value);
  return oklch(TARGET_L_TOP - TARGET_L_SPAN * v, TARGET_C_BASE + TARGET_C_SPAN * v, TARGET_ROW_HUE);
}

/** One stop of the legend gradient; `t` runs 0 (dissonant) .. 1 (consonant). */
export function legendColor(t: number): string {
  return oklch(LEGEND_L, LEGEND_C, consonanceHue(t));
}
