// Owner: WINTERMUTE (created 2026-10-27)
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  QKV, KSCALES, stack, split, makeWeights, makeInput, projectFused, projectSeparate, maxAbsDiff, makeGrads, rms, orthSizes,
} from '../lib/qkv.js';

const G = makeGrads();
const sizes = (ks) => orthSizes(G, ks);

test('1. split(stack(A,B,C)) returns A, B, C exactly; a 5-row matrix throws', () => {
  const W = makeWeights();
  const [A, B, C] = split(stack(W.Wq, W.Wk, W.Wv));
  assert.deepEqual([A, B, C], [W.Wq, W.Wk, W.Wv]);
  assert.throws(() => split(Array.from({ length: 5 }, () => [0, 0])));
});

test('2. fused and separate projections agree to 1e-12 for 10 inputs', () => {
  const W = makeWeights();
  for (let s = 100; s < 110; s++) {
    const x = makeInput(s);
    assert.equal(x.length, QKV.d);
    assert.ok(maxAbsDiff(projectFused(W, x), projectSeparate(W, x)) < 1e-12, `seed ${s}`);
  }
});

test('3. separate sizes do not depend on kscale', () => {
  const base = sizes(1).separate;
  for (const ks of KSCALES) {
    const s = sizes(ks).separate;
    assert.ok(s[0] === base[0] && s[2] === base[2], `q/v at ${ks}`);
    assert.ok(Math.abs(s[1] - base[1]) < 1e-6, `k at ${ks}`);
  }
});

test('4. coupling: fused q and v at kscale 10 are under 0.3 x their size at 0.01', () => {
  const lo = sizes(0.01).fused, hi = sizes(10).fused;
  console.log('fused at 0.01', lo, 'fused at 10', hi);
  assert.ok(hi[0] < 0.3 * lo[0], `q ${hi[0]} vs ${lo[0]}`);
  assert.ok(hi[2] < 0.3 * lo[2], `v ${hi[2]} vs ${lo[2]}`);
});

test('5. starvation: fused k at kscale 0.01 is under 0.05 x separate k', () => {
  const s = sizes(0.01);
  console.log('fused k', s.fused[1], 'separate k', s.separate[1]);
  assert.ok(s.fused[1] < 0.05 * s.separate[1]);
});

test('6. determinism: makeWeights(7) repeats, makeWeights(8) differs', () => {
  assert.deepEqual(makeWeights(7), makeWeights(7));
  assert.notDeepEqual(makeWeights(8), makeWeights(7));
});

test('7. every size at every kscale is finite and positive', () => {
  for (const ks of KSCALES) {
    const s = sizes(ks);
    for (const v of [...s.fused, ...s.separate]) assert.ok(Number.isFinite(v) && v > 0, `${ks}: ${v}`);
  }
  assert.ok(rms([[3, 4]]) > 0);
});
