// Owner: WINTERMUTE (created 2026-10-26)
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  mulberry32, makeGauss, randnMatrix, sigmaForHalfBatchCosine, halfBatchCosine, CALIBRATION, minibatchGrad,
} from '../lib/noise.js';
import { near } from './helpers.mjs';

test('randnMatrix has the requested shape', () => {
  const M = randnMatrix(3, 2, makeGauss(mulberry32(4)));
  assert.equal(M.length, 3);
  assert.equal(M[0].length, 2);
});

test('calibration constants are the measured ones', () => {
  assert.equal(CALIBRATION.batch, 64);
  assert.equal(CALIBRATION.early, 0.37);
  assert.equal(CALIBRATION.late, 0.08);
  assert.match(CALIBRATION.source, /EB64/);
});

test('sigmaForHalfBatchCosine round-trips and rejects impossible cosines', () => {
  for (const c of [0.08, 0.37, 0.8]) near(halfBatchCosine(sigmaForHalfBatchCosine(c)), c, 1e-12, `c=${c}`);
  assert.throws(() => sigmaForHalfBatchCosine(0));
  assert.throws(() => sigmaForHalfBatchCosine(1));
  assert.ok(sigmaForHalfBatchCosine(0.08) > sigmaForHalfBatchCosine(0.37));   // a lower cosine means more noise
});

test('simulated half batches reproduce the calibrated cosine', () => {
  const sigma1 = sigmaForHalfBatchCosine(CALIBRATION.early, CALIBRATION.batch);
  const g = makeGauss(mulberry32(31));
  const D = 4000, G = [Array.from({ length: D }, () => g())];       // true gradient, rms about 1
  const half = () => minibatchGrad(G, sigma1, CALIBRATION.batch / 2, g)[0];
  const a = half(), b = half();
  const dot = a.reduce((s, x, i) => s + x * b[i], 0);
  const cos = dot / Math.sqrt(a.reduce((s, x) => s + x * x, 0) * b.reduce((s, x) => s + x * x, 0));
  near(cos, CALIBRATION.early, 0.04, 'simulated half-batch cosine');
});
