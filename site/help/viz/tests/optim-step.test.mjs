// Owner: WINTERMUTE (created 2026-10-26)
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  newtonSchulz, newtonSchulz5, singularValues, matmul, transpose, adamwStep, muonStep, meanAbs, frobenius, scale,
} from '../lib/optim.js';
import { mulberry32, makeGauss, randnMatrix } from '../lib/noise.js';
import { withSingularValues } from './matrices.mjs';
import { near } from './helpers.mjs';

test('Newton-Schulz (5 iterations) pushes singular values into roughly [0.68, 1.32]', () => {
  const g = makeGauss(mulberry32(5));
  for (const [r, c] of [[8, 8], [8, 4], [4, 8]]) {
    for (let trial = 0; trial < 20; trial++) {
      const k = Math.min(r, c);
      // singular values spread 5x apart, like a trained gradient (a pure gaussian matrix has a near-zero tail)
      const svs = Array.from({ length: k }, (_, i) => 1 - (0.8 * i) / (k - 1));
      const sv = singularValues(newtonSchulz5(withSingularValues(r, c, svs, g)));
      assert.ok(sv[0] <= 1.32 && sv[k - 1] >= 0.68, `${r}x${c} trial ${trial}: ${sv[0].toFixed(3)} .. ${sv[k - 1].toFixed(3)}`);
    }
  }
});

test('Newton-Schulz with the classic cubic coefficients converges to an orthogonal matrix', () => {
  const g = makeGauss(mulberry32(9));
  const O = newtonSchulz(randnMatrix(6, 4, g), 60, [1.5, -0.5, 0]);
  const OtO = matmul(transpose(O), O);
  for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++) near(OtO[i][j], i === j ? 1 : 0, 1e-6, `OtO[${i}][${j}]`);
});

test('Newton-Schulz output does not depend on the size of the input', () => {
  const g = makeGauss(mulberry32(3));
  const M = randnMatrix(5, 5, g);
  const A = newtonSchulz5(M), B = newtonSchulz5(scale(M, 1e-2));
  for (let i = 0; i < 5; i++) for (let j = 0; j < 5; j++) near(A[i][j], B[i][j], 1e-3);
});

test('AdamW first step is lr * sign(g)', () => {
  const G = randnMatrix(4, 4, makeGauss(mulberry32(11)));
  const first = adamwStep(null, G, { lr: 1e-3 });
  for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++) near(first.update[i][j], 1e-3 * Math.sign(G[i][j]), 1e-9);
});

test('after a 100x gradient drop AdamW steps shrink while the Muon update norm stays constant', () => {
  const g = makeGauss(mulberry32(11));
  const G = randnMatrix(4, 4, g);
  const lr = 1e-3;
  let a = null, m = null, aBefore = 0, mBefore = 0, aAfter = 0, mAfter = 0;
  for (let t = 0; t < 400; t++) {
    const gain = t < 200 ? 1 : 0.01;
    const grad = G.map((row) => row.map((x) => gain * (x + 0.5 * g())));
    const ra = adamwStep(a, grad, { lr }); a = ra.state;
    const rm = muonStep(m, grad, { lr }); m = rm.state;
    if (t === 199) { aBefore = meanAbs(ra.update); mBefore = frobenius(rm.update); }
    if (t === 399) { aAfter = meanAbs(ra.update); mAfter = frobenius(rm.update); }
  }
  assert.ok(aAfter < 0.1 * aBefore, `AdamW should shrink: ${aBefore} -> ${aAfter}`);
  near(mAfter / mBefore, 1, 0.25, 'Muon update norm ratio');
});

test('AdamW weight decay adds lr * wd * w to the update', () => {
  const G = [[1, -1]], w = [[0.5, 0.5]];
  const plain = adamwStep(null, G, { lr: 0.1 }).update;
  const decayed = adamwStep(null, G, { lr: 0.1, wd: 0.2, w }).update;
  near(decayed[0][0] - plain[0][0], 0.1 * 0.2 * 0.5, 1e-12);
});

test('Muon with the Moonlight scale moves a square matrix about 0.2 lr per weight', () => {
  const G = randnMatrix(8, 8, makeGauss(mulberry32(2)));
  const { update } = muonStep(null, G, { lr: 1, momentum: 0.95 });
  near(Math.sqrt(frobenius(update) ** 2 / 64), 0.2, 0.06);
});
