// Owner: WINTERMUTE (created 2026-10-26)
import test from 'node:test';
import assert from 'node:assert/strict';
import { matmul, transpose, singularValues, frobenius } from '../lib/optim.js';
import { mulberry32, makeGauss } from '../lib/noise.js';
import { withSingularValues } from './matrices.mjs';
import { near } from './helpers.mjs';

test('matmul and transpose on a small example', () => {
  const A = [[1, 2, 3], [4, 5, 6]];
  assert.deepEqual(transpose(A), [[1, 4], [2, 5], [3, 6]]);
  assert.deepEqual(matmul(A, transpose(A)), [[14, 32], [32, 77]]);
  assert.throws(() => matmul(A, A));
});

test('singularValues recovers values built into a tall, wide and square matrix', () => {
  const g = makeGauss(mulberry32(1));
  for (const [r, c, svs] of [[6, 4, [3, 2, 1, 0.5]], [4, 6, [3, 2, 1, 0.5]], [5, 5, [4, 3, 2, 1, 0.1]]]) {
    const M = withSingularValues(r, c, svs, g);
    const sv = singularValues(M);
    svs.forEach((s, k) => near(sv[k], s, 1e-8, `${r}x${c} sv${k}`));
    near(Math.sqrt(sv.reduce((s, x) => s + x * x, 0)), frobenius(M), 1e-9, 'frobenius');
  }
});
