// Owner: WINTERMUTE (created 2026-10-26)
import test from 'node:test';
import assert from 'node:assert/strict';
import { CALIBRATION, halfBatchCosine, minibatchNoiseStd, mulberry32, makeGauss } from '../lib/noise.js';
import {
  VALLEY, BATCHES, loss, grad, sigmaForStage, noisyGrad, readouts, noiselessPath, createValleySim,
} from '../lib/valley.js';
import { near, mean } from './helpers.mjs';

const gRmsStart = Math.hypot(...grad(VALLEY.start)) / Math.SQRT2;
const finalLoss = (opts) => { const s = createValleySim(opts); while (!s.done) s.step(); return loss(s.pos); };
const meanFinal = (opts) => mean(Array.from({ length: 20 }, (_, i) => finalLoss({ ...opts, seed: i + 1 })));

test('1. calibration round trip: half-batch cosine at start, batch 64, equals the measured value', () => {
  for (const s of ['early', 'late']) {
    near(halfBatchCosine(sigmaForStage(s), CALIBRATION.batch, gRmsStart), CALIBRATION[s], 1e-12, s);
  }
  assert.throws(() => sigmaForStage('mid'));
});

test('2. SNR scales with sqrt(batch); measured only at 64', () => {
  const s1 = sigmaForStage('late');
  const r = readouts(VALLEY.start, s1, 256, 0).snr / readouts(VALLEY.start, s1, 1, 0).snr;
  near(r, 16, 1e-9);
  for (const B of BATCHES) assert.equal(readouts(VALLEY.start, s1, B, 0).measured, B === 64);
});

test('3. momentum SNR gain is sqrt(19) at beta 0.9, null when off', () => {
  const s1 = sigmaForStage('early');
  const on = readouts(VALLEY.start, s1, 8, VALLEY.beta);
  near(on.momentumSnr / on.snr, Math.sqrt(19), 1e-12);
  assert.equal(readouts(VALLEY.start, s1, 8, 0).momentumSnr, null);
});

test('4. noisyGrad empirical std matches minibatchNoiseStd', () => {
  const s1 = sigmaForStage('late'), gauss = makeGauss(mulberry32(5)), p = [1, 0.5];
  const g0 = grad(p);
  for (const B of [1, 64]) {
    const xs = Array.from({ length: 20000 }, () => noisyGrad(p, s1, B, gauss)[0] - g0[0]);
    const sd = Math.sqrt(mean(xs.map((x) => x * x)) - mean(xs) ** 2);
    const want = minibatchNoiseStd(s1, B);
    assert.ok(Math.abs(sd / want - 1) < 0.03, `B=${B} std ${sd} vs ${want}`);
  }
});

test('5. noiseless path converges', () => {
  const path = noiselessPath();
  assert.equal(path.length, VALLEY.steps + 1);
  assert.ok(loss(path[path.length - 1]) < 1e-3 * loss(VALLEY.start));
});

test('6. determinism: same arguments same path, different seed differs', () => {
  const run = (o) => { const s = createValleySim(o); while (!s.done) s.step(); return s.path; };
  assert.deepEqual(run({ batch: 4, seed: 3 }), run({ batch: 4, seed: 3 }));
  assert.notDeepEqual(run({ batch: 4, seed: 3 }), run({ batch: 4, seed: 4 }));
  assert.equal(run({}).length, VALLEY.steps + 1);
});

test('7. late noise: larger batch settles closer (mean final loss over 20 seeds)', () => {
  const big = meanFinal({ stage: 'late', batch: 256 }), small = meanFinal({ stage: 'late', batch: 1 });
  assert.ok(big < small, `batch 256 ${big} vs batch 1 ${small}`);
});

test('8. late noise, batch 4: momentum lowers mean final loss over 20 seeds', () => {
  const on = meanFinal({ stage: 'late', batch: 4, momentum: true });
  const off = meanFinal({ stage: 'late', batch: 4, momentum: false });
  assert.ok(on < off, `momentum on ${on} vs off ${off}`);
});
