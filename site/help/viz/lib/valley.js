// Owner: WINTERMUTE (created 2026-10-26)
// Last edited: WINTERMUTE 2026-10-26 -- valley a=2, lr 0.01, 300 steps: at lr 0.08 our measured late noise flung the ball to 100x the start loss
// The maths behind the batch-noise animation: a 2-D loss valley, noisy minibatch gradients, optional momentum.
import {
  mulberry32, makeGauss, CALIBRATION, sigmaForHalfBatchCosine, halfBatchCosine, minibatchNoiseStd,
} from './noise.js';

export const VALLEY = { a: 2, b: 8, start: [-2.6, 0.9], lr: 0.01, steps: 300, cloudSize: 24, beta: 0.9 };
export const BATCHES = [1, 2, 4, 8, 16, 32, 64, 128, 256];

export function loss([x, y]) { return 0.5 * (VALLEY.a * x * x + VALLEY.b * y * y); }
export function grad([x, y]) { return [VALLEY.a * x, VALLEY.b * y]; }

const norm = (g) => Math.hypot(g[0], g[1]);

export function sigmaForStage(stage) {
  if (stage !== 'early' && stage !== 'late') throw new Error(`unknown stage ${stage}`);
  const gRms = norm(grad(VALLEY.start)) / Math.SQRT2;
  return sigmaForHalfBatchCosine(CALIBRATION[stage], CALIBRATION.batch, gRms);
}

export function noisyGrad(p, sigma1, B, gauss) {
  const g = grad(p), s = minibatchNoiseStd(sigma1, B);
  return [g[0] + s * gauss(), g[1] + s * gauss()];
}

export function sampleCloud(p, sigma1, B, n, gauss) {
  const out = [];
  for (let i = 0; i < n; i++) out.push(noisyGrad(p, sigma1, B, gauss));
  return out;
}

export function readouts(p, sigma1, B, beta) {
  const g = norm(grad(p));
  const snr = g / (minibatchNoiseStd(sigma1, B) * Math.SQRT2);
  return {
    snr,
    halfCos: halfBatchCosine(sigma1, B, g / Math.SQRT2),
    momentumSnr: beta > 0 ? snr * Math.sqrt((1 + beta) / (1 - beta)) : null,
    measured: B === CALIBRATION.batch,
  };
}

export function noiselessPath(steps = VALLEY.steps) {
  let p = [...VALLEY.start];
  const path = [p];
  for (let i = 0; i < steps; i++) {
    const g = grad(p);
    p = [p[0] - VALLEY.lr * g[0], p[1] - VALLEY.lr * g[1]];
    path.push(p);
  }
  return path;
}

export function createValleySim({ stage = 'late', batch = 8, momentum = false, seed = 11 } = {}) {
  const sigma1 = sigmaForStage(stage);
  const beta = momentum ? VALLEY.beta : 0;
  const gauss = makeGauss(mulberry32(seed));
  let pos = [...VALLEY.start], m = [0, 0], t = 0;
  const path = [pos];
  return {
    sigma1, batch, beta, path,
    get t() { return t; },
    get done() { return t >= VALLEY.steps; },
    get pos() { return pos; },
    step() {
      const trueGrad = grad(pos);
      const g = noisyGrad(pos, sigma1, batch, gauss);
      let used = g;
      if (beta > 0) { m = [beta * m[0] + (1 - beta) * g[0], beta * m[1] + (1 - beta) * g[1]]; used = m; }
      pos = [pos[0] - VALLEY.lr * used[0], pos[1] - VALLEY.lr * used[1]];
      path.push(pos);
      t++;
      return { t, pos, trueGrad, usedGrad: used, loss: loss(pos) };
    },
  };
}
