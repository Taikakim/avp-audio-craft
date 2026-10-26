// Owner: WINTERMUTE (created 2026-10-26)
import test from 'node:test';
import assert from 'node:assert/strict';
import { mulberry32, makeGauss } from '../lib/noise.js';
import { near, mean } from './helpers.mjs';

test('seeded RNG is reproducible and roughly standard normal', () => {
  const a = makeGauss(mulberry32(42)), b = makeGauss(mulberry32(42)), c = makeGauss(mulberry32(43));
  const xs = Array.from({ length: 5000 }, a), ys = Array.from({ length: 5000 }, b);
  assert.deepEqual(xs, ys);
  assert.notEqual(c(), xs[0]);
  near(mean(xs), 0, 0.05, 'mean');
  near(mean(xs.map((x) => x * x)), 1, 0.08, 'variance');
});

test('mulberry32 stays inside [0, 1)', () => {
  const r = mulberry32(1);
  for (let i = 0; i < 10000; i++) { const x = r(); assert.ok(x >= 0 && x < 1); }
});
