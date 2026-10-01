// Generates docs/latent-forge/contract/fixtures/handmade-forge_chroma_render.json,
// the mock server's answer for POST /forge/chroma (spec §6.3). M1 T6 maps that
// route to the fixture name `forge_chroma_render`; without this file the route
// 501s with "no fixture ... yet", which is what the whole CHROMA tab would have
// hit on every selection.
//
// Run:  node mock/makeChromaFixture.mjs
//
// The content is a plain C major triad (C, E, G) with a slow swell, so the
// heatmap, the match curve and the detune scan all have something honest to
// draw against a C-ish target. No paths of any kind, so the fixture cannot leak
// a server path (M1's own fixture rule).

import { writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const T = 24;
const BANDS = 3;
const BINS = 128;
const BINS_PER_SEMITONE = BINS / 12;
const C_BIN = 2.0;

/** The server's own centres: C at 2.0, each semitone 128/12 apart. */
function centre(pc) {
  return (C_BIN + pc * BINS_PER_SEMITONE) % BINS;
}

/** Triangular bump of half-width one semitone around a bin, wrapping. */
function bump(bin, at) {
  let d = Math.abs(bin - at);
  d = Math.min(d, BINS - d);
  return Math.max(0, 1 - d / BINS_PER_SEMITONE);
}

const CHORD = [0, 4, 7];
const BAND_GAIN = [0.9, 1.0, 0.6]; // oct 1 / oct 5 / oct 9

const bands = new Float64Array(BANDS * BINS * T);
for (let b = 0; b < BANDS; b++) {
  for (let i = 0; i < BINS; i++) {
    for (let t = 0; t < T; t++) {
      const swell = 0.55 + 0.45 * Math.sin((t / T) * Math.PI);
      let v = 0;
      for (let k = 0; k < CHORD.length; k++) {
        v += bump(i, centre(CHORD[k])) * (1 - k * 0.18);
      }
      bands[(b * BINS + i) * T + t] = v * BAND_GAIN[b] * swell;
    }
  }
}

// One scale per band, over that band's own slice -- spec §6.3.
const per = BINS * T;
const bandBytes = new Uint8Array(BANDS * per);
const bandScale = [];
for (let b = 0; b < BANDS; b++) {
  let max = 0;
  for (let i = 0; i < per; i++) max = Math.max(max, bands[b * per + i]);
  const scale = max > 0 ? Number(max.toFixed(6)) : 1;
  bandScale.push(scale);
  for (let i = 0; i < per; i++) {
    bandBytes[b * per + i] = Math.round(Math.min(255, (bands[b * per + i] / scale) * 255));
  }
}

// The 12-class fold: sum each bin into its nearest centre, then normalise the
// whole clip to 1 so the single fold12 scale of 1.0 is exact.
const fold = new Float64Array(12 * T);
for (let b = 0; b < BANDS; b++) {
  for (let i = 0; i < BINS; i++) {
    let best = 0;
    let bd = Infinity;
    for (let pc = 0; pc < 12; pc++) {
      const raw = Math.abs(i - centre(pc));
      const d = Math.min(raw, BINS - raw);
      if (d < bd) {
        bd = d;
        best = pc;
      }
    }
    for (let t = 0; t < T; t++) fold[best * T + t] += bands[(b * BINS + i) * T + t];
  }
}
let fmax = 0;
for (const v of fold) fmax = Math.max(fmax, v);
const foldBytes = new Uint8Array(12 * T);
for (let i = 0; i < fold.length; i++) {
  foldBytes[i] = Math.round(Math.min(255, (fold[i] / (fmax || 1)) * 255));
}

const fixture = {
  status: 200,
  body: {
    ok: true,
    frames: T,
    fps: 10.7666015625,
    bands: {
      shape: [BANDS, BINS, T],
      scale: bandScale,
      data_b64: Buffer.from(bandBytes).toString("base64"),
    },
    fold12: {
      shape: [12, T],
      scale: 1.0,
      data_b64: Buffer.from(foldBytes).toString("base64"),
    },
  },
};

const out = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../../docs/latent-forge/contract/fixtures/handmade-forge_chroma_render.json",
);
writeFileSync(out, `${JSON.stringify(fixture, null, 2)}\n`, "utf8");
console.log(`wrote ${out}: ${T} frames, band scales ${bandScale.join(", ")}`);
