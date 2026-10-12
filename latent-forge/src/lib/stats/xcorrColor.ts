// Diverging colour ramp for the 256x256 DIM CROSS-CORRELATION panel (spec
// §4.4): xcorr values run -1..+1 (spec §6.5's dequantised range, M10 T1's
// dequantiseXcorr), and this is the one canvas colour in the statistics view
// that does NOT come from getComputedStyle. HANDOUT.md: an unregistered
// custom property's computed value is its literal token stream --
// getComputedStyle(el).getPropertyValue("--token") hands back the STRING
// "oklch(78% 0.08 250)", not a colour with channels to interpolate. A ramp
// needs three channels to mix per step, so this builds its own oklch()
// string exactly as M5's downbeatColor does (lib/math/downbeats.ts) and
// nobody should "fix" it back to a token read.
//
// Zero must be visibly neutral (low chroma, high lightness) and the two
// poles must differ in HUE, not only lightness, so the sign of a correlation
// still reads even in a colour-blind-unfriendly rendering. Negative uses the
// app's own turq hue (195, matching --turq-strong), positive uses its red
// hue (25, matching --red) -- the same two accent hues the rest of the app
// already uses for "cool" and "warm", chosen here as literals because this
// ramp cannot read the tokens (see above).

export const XCORR_NEG = { l: 55, c: 0.16, h: 195 } as const;
export const XCORR_ZERO = { l: 92, c: 0.012, h: 195 } as const;
export const XCORR_POS = { l: 55, c: 0.18, h: 25 } as const;

/** Diverging ramp over -1..+1 (spec §6.5's xcorr range). Clamps outside it. */
export function xcorrColor(v: number): string {
  const k = Math.max(-1, Math.min(1, Number.isFinite(v) ? v : 0));
  const pole = k < 0 ? XCORR_NEG : XCORR_POS;
  const t = Math.abs(k); // 0 at zero, 1 at either pole
  const l = XCORR_ZERO.l + (pole.l - XCORR_ZERO.l) * t;
  const c = XCORR_ZERO.c + (pole.c - XCORR_ZERO.c) * t;
  const h = XCORR_ZERO.h + (pole.h - XCORR_ZERO.h) * t;
  return `oklch(${l.toFixed(2)}% ${c.toFixed(3)} ${h.toFixed(1)})`;
}
