// Owner: WINTERMUTE (created 2026-10-26)
import test from 'node:test';
import { mulberry32, makeGauss, randnMatrix, snrGate } from '../lib/noise.js';
import { adamwStep } from '../lib/optim.js';
import { near } from './helpers.mjs';

test('pure-noise m / sqrt(v) settles near sqrt((1-b)/(1+b)) = 0.23 at beta1 0.9', () => {
  const g = makeGauss(mulberry32(21));
  let st = null;
  for (let t = 0; t < 3000; t++) st = adamwStep(st, randnMatrix(20, 20, g), { lr: 1e-3 }).state;
  const c2 = 1 - Math.pow(0.999, st.t), c1 = 1 - Math.pow(0.9, st.t);
  const v = st.v.map((row) => row.map((x) => x / c2));
  const m = st.m.map((row) => row.map((x) => x / c1));
  near(snrGate(m, v), Math.sqrt(0.1 / 1.9), 0.035, 'noise floor');
});

test('snrGate is about 1 for a clean constant signal', () => {
  let st = null;
  for (let t = 0; t < 200; t++) st = adamwStep(st, [[2, -3], [1, 4]], { lr: 1e-3 }).state;
  const c2 = 1 - Math.pow(0.999, st.t), c1 = 1 - Math.pow(0.9, st.t);
  near(snrGate(st.m.map((r) => r.map((x) => x / c1)), st.v.map((r) => r.map((x) => x / c2))), 1, 1e-6);
});
