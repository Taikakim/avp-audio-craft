// Owner: WINTERMUTE (created 2026-10-26)
// Seeded randomness and the minibatch-gradient noise model. Pure functions, no DOM.
import { zeros, map2 } from './optim.js';
export function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Standard normal numbers from a uniform generator (Box-Muller, spare value cached).
export function makeGauss(rng) {
  let spare = null;
  return function () {
    if (spare !== null) { const s = spare; spare = null; return s; }
    let u = 0;
    while (u === 0) u = rng();
    const v = rng();
    const rad = Math.sqrt(-2 * Math.log(u));
    spare = rad * Math.sin(2 * Math.PI * v);
    return rad * Math.cos(2 * Math.PI * v);
  };
}

// Our measured numbers: cosine between the gradients of two half batches (32 + 32 of a batch of 64).
export const CALIBRATION = {
  batch: 64,
  early: 0.37,
  late: 0.08,
  source: 'EB64 half-batch gradient cosine, onset head, 2026-10-21',
};

export function randnMatrix(r, c, gauss) {
  const M = zeros(r, c);
  for (let i = 0; i < r; i++) for (let j = 0; j < c; j++) M[i][j] = gauss();
  return M;
}

// Noise model: one example's gradient = true gradient + sigma1 * z (per element, z standard normal);
// a minibatch of B examples averages that noise down by sqrt(B).
export function minibatchNoiseStd(sigma1, B) { return sigma1 / Math.sqrt(B); }
export function minibatchGrad(gTrue, sigma1, B, gauss) {
  const s = minibatchNoiseStd(sigma1, B);
  return gTrue.map((row) => row.map((g) => g + s * gauss()));
}

// Two independent half batches (B/2 each) have cosine delta^2 / (1 + delta^2), delta = |g| / |noise of a half batch|.
// gRms = rms of the true gradient per element; sigma1 is in the same units.
export function halfBatchCosine(sigma1, B = CALIBRATION.batch, gRms = 1) {
  const delta = (gRms * Math.sqrt(B / 2)) / sigma1;
  return (delta * delta) / (1 + delta * delta);
}
export function sigmaForHalfBatchCosine(c, B = CALIBRATION.batch, gRms = 1) {
  if (!(c > 0 && c < 1)) throw new Error('cosine must be in (0, 1)');
  const delta = Math.sqrt(c / (1 - c));
  return (gRms * Math.sqrt(B / 2)) / delta;
}

// The optimiser's own readout: root-mean-square of m / sqrt(v) over all elements
// (about 1 for a clean signal, about sqrt((1-b)/(1+b)) = 0.23 for pure noise at beta 0.9).
export function snrGate(m, v, eps = 1e-12) {
  let s = 0, n = 0;
  map2(m, v, (mi, vi) => { const r = mi / Math.sqrt(vi + eps); s += r * r; n++; return 0; });
  return Math.sqrt(s / n);
}
