// Owner: WINTERMUTE (created 2026-10-26)
import test from 'node:test';
import assert from 'node:assert/strict';
import { roundTo, survivesUpdate, ulp } from '../lib/optim.js';
import { mulberry32, makeGauss } from '../lib/noise.js';

test('roundTo is exact on known values', () => {
  assert.equal(roundTo(1.00390625, 'bf16'), 1.0);          // exact tie, goes to the even neighbour
  assert.equal(roundTo(1.01171875, 'bf16'), 1.015625);     // tie above an odd neighbour rounds up
  assert.equal(roundTo(1.00391, 'bf16'), 1.0078125);       // just above the tie
  assert.equal(roundTo(0.1, 'fp32'), Math.fround(0.1));
  assert.equal(roundTo(65504, 'fp16'), 65504);
  assert.equal(roundTo(65519, 'fp16'), 65504);
  assert.equal(roundTo(65520, 'fp16'), Infinity);
  assert.equal(roundTo(1 + 2 ** -11, 'fp16'), 1);          // half the spacing at 1.0, tie goes to even
  assert.equal(roundTo(2 ** -24, 'fp16'), 2 ** -24);       // smallest fp16 subnormal
  assert.equal(roundTo(2 ** -26, 'fp16'), 0);
  assert.equal(roundTo(448, 'fp8e4m3'), 448);
  assert.equal(roundTo(1000, 'fp8e4m3'), 448);             // saturates
  assert.equal(roundTo(-0.3, 'fp8e4m3'), -0.3125);
  assert.equal(roundTo(2 ** -9, 'fp8e4m3'), 2 ** -9);      // smallest subnormal
  assert.throws(() => roundTo(1, 'int8'));
});

test('bf16 rounding is within half a spacing and idempotent on random values', () => {
  const g = makeGauss(mulberry32(77));
  for (let i = 0; i < 2000; i++) {
    const x = Math.fround(g() * Math.pow(10, Math.floor(g() * 3)));
    const q = roundTo(x, 'bf16');
    assert.ok(Math.abs(q - x) <= ulp(x, 'bf16') / 2 + 1e-30, `bf16(${x}) = ${q}`);
    assert.equal(roundTo(q, 'bf16'), q);
  }
});

test('survivesUpdate: a step under half the spacing is rounded away', () => {
  const w = 0.05;                                   // bf16 spacing near 0.05 is 2^-5 * 2^-7 = 2^-12
  assert.equal(ulp(w, 'bf16'), 2 ** -12);
  assert.equal(survivesUpdate(w, 0.4 * 2 ** -12, 'bf16'), false);
  assert.equal(survivesUpdate(w, 0.6 * 2 ** -12, 'bf16'), true);
  assert.equal(survivesUpdate(w, 6e-5, 'fp32'), true);
  assert.equal(survivesUpdate(w, 6e-5, 'fp8e4m3'), false);
  assert.equal(survivesUpdate(w, 0, 'fp32'), false);
});
