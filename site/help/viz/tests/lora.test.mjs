// Owner: WINTERMUTE (created 2026-10-27)
import test from 'node:test';
import assert from 'node:assert/strict';
import { frobenius, matmul, transpose } from '../lib/optim.js';
import { mulberry32, makeGauss } from '../lib/noise.js';
import {
  RANKS, MEASURED, energyAt, adapterParams, fullParams, toyRank, makeToy, keptEnergy, orthogonal, truncate, rowLengths,
} from '../lib/lora.js';

const near = (a, b, tol, msg) => assert.ok(Math.abs(a - b) < tol, `${msg ?? ''} ${a} vs ${b}`);

test('1. energyAt: measured, full, interpolated, monotone, range', () => {
  for (const p of MEASURED) assert.deepEqual(energyAt(p.r), { e: p.e, kind: 'measured' });
  assert.deepEqual(energyAt(1536), { e: 1, kind: 'full' });
  const a = energyAt(32);
  assert.equal(a.kind, 'interpolated');
  assert.deepEqual(a.between, [16, 64]);
  near(a.e, (0.045 + 0.148) / 2, 1e-12);
  assert.deepEqual(energyAt(256).between, [128, 512]);
  const es = RANKS.map((r) => energyAt(r).e);
  for (let i = 1; i < es.length; i++) assert.ok(es[i] > es[i - 1]);
  assert.throws(() => energyAt(8));
  assert.throws(() => energyAt(2048));
});

test('2. parameter counts', () => {
  assert.equal(adapterParams(128), 393216);
  assert.equal(fullParams(), 2359296);
});

test('3. toyRank over RANKS', () => {
  assert.deepEqual(RANKS.map(toyRank), [1, 1, 1, 1, 2, 4, 8, 12]);
});

test('4. keptEnergy matches the measured curve; shares non-increasing', () => {
  const toy = makeToy();
  for (const [k, r] of [[1, 128], [4, 512], [8, 1024], [12, 1536]]) near(keptEnergy(toy, k), energyAt(r).e, 1e-12, `k=${k}`);
  for (let i = 1; i < toy.s.length; i++) assert.ok(toy.s[i] <= toy.s[i - 1]);
});

test('5. orthogonal(12) has U^T U = I', () => {
  const U = orthogonal(12, makeGauss(mulberry32(3)));
  const P = matmul(transpose(U), U);
  for (let i = 0; i < 12; i++) for (let j = 0; j < 12; j++) near(P[i][j], i === j ? 1 : 0, 1e-10);
});

test('6. truncate: full rank equals dW; energy ratio equals keptEnergy', () => {
  const toy = makeToy();
  const T = truncate(toy, 12);
  for (let i = 0; i < 12; i++) for (let j = 0; j < 12; j++) near(T[i][j], toy.dW[i][j], 1e-10);
  const tot = frobenius(toy.dW) ** 2;
  for (let k = 1; k <= 12; k++) near(frobenius(truncate(toy, k)) ** 2 / tot, keptEnergy(toy, k), 1e-10, `k=${k}`);
});

test('7. rowLengths error: positive below full rank, zero at 12, smaller at 8 than 1', () => {
  const toy = makeToy();
  for (let k = 1; k < 12; k++) assert.ok(rowLengths(toy, k).meanRelErr > 0, `k=${k}`);
  assert.ok(rowLengths(toy, 12).meanRelErr < 1e-10);
  console.log('meanRelErr k=1', rowLengths(toy, 1).meanRelErr, 'k=8', rowLengths(toy, 8).meanRelErr);
  assert.ok(rowLengths(toy, 8).meanRelErr < rowLengths(toy, 1).meanRelErr);
});

test('8. determinism', () => {
  assert.deepEqual(makeToy(5), makeToy(5));
  assert.notDeepEqual(makeToy(6), makeToy(5));
});
