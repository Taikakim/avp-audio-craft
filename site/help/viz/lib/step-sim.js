// Owner: WINTERMUTE (created 2026-10-26)
// The scenarios behind the step-size animation: one gradient stream feeds AdamW and Muon side by side.
import { adamwStep, muonStep, meanAbs, scale } from './optim.js';
import {
  mulberry32, makeGauss, randnMatrix, CALIBRATION, sigmaForHalfBatchCosine, minibatchNoiseStd,
} from './noise.js';

export const STEP_AT = 150;     // step at which "drops" / "rises" happen
export const TOTAL_STEPS = 450;
export const LR = 3e-4;         // AdamW's best learning rate for our heads (guide section 4)
export const WEIGHT_RMS = 0.05; // illustrative weight size

export const SCENARIOS = {
  steady: { label: 'Steady', noise: 'early', gain: () => 1 },
  noisy: { label: 'Noisy', noise: 'late', gain: () => 1 },
  drop: { label: 'Gradient drops 100x', noise: 'early', gain: (t) => (t < STEP_AT ? 1 : 0.01) },
  rise: { label: 'Gradient rises 100x', noise: 'early', gain: (t) => (t < STEP_AT ? 1 : 100) },
};

export function createSim(id, { seed = 7, rows = 4, cols = 4, lr = LR, momentum = 0.95 } = {}) {
  const sc = SCENARIOS[id];
  if (!sc) throw new Error(`unknown scenario ${id}`);
  const gauss = makeGauss(mulberry32(seed));
  const G = randnMatrix(rows, cols, gauss);                       // fixed "true" gradient, rms 1
  const W = scale(randnMatrix(rows, cols, gauss), WEIGHT_RMS);    // weights shown (not evolved)
  const sigma1 = sigmaForHalfBatchCosine(CALIBRATION[sc.noise], CALIBRATION.batch);
  const noiseStd = minibatchNoiseStd(sigma1, CALIBRATION.batch);
  let t = 0, adam = null, muon = null;
  return {
    id, rows, cols, lr, W, noiseStd,
    get t() { return t; },
    get done() { return t >= TOTAL_STEPS; },
    step() {
      const gain = sc.gain(t);
      const g = G.map((row) => row.map((x) => gain * (x + noiseStd * gauss())));
      const a = adamwStep(adam, g, { lr });
      const m = muonStep(muon, g, { lr, momentum });
      adam = a.state; muon = m.state; t++;
      return {
        t, gain, adamUpdate: a.update, muonUpdate: m.update,
        adamMean: meanAbs(a.update) / lr, muonMean: meanAbs(m.update) / lr,
      };
    },
  };
}
