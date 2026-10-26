// Owner: WINTERMUTE (created 2026-10-27)
// The maths behind the qkv-line animation: fused vs separate Q/K/V projections, and orthogonalising a stack vs each block.
import { matmul, frobenius, newtonSchulz5, scale } from './optim.js';
import { mulberry32, makeGauss, randnMatrix } from './noise.js';

export const QKV = { d: 4, seed: 7 };
export const KSCALES = [0.01, 0.03, 0.1, 0.3, 1, 3, 10];

export function stack(A, B, C) { return [...A, ...B, ...C].map((r) => r.slice()); }

export function split(M) {
  if (M.length % 3 !== 0) throw new Error(`cannot split ${M.length} rows into 3 equal blocks`);
  const n = M.length / 3;
  return [M.slice(0, n), M.slice(n, 2 * n), M.slice(2 * n)].map((B) => B.map((r) => r.slice()));
}

function threeMatrices(seed) {
  const g = makeGauss(mulberry32(seed));
  const a = randnMatrix(QKV.d, QKV.d, g);
  const b = randnMatrix(QKV.d, QKV.d, g);
  const c = randnMatrix(QKV.d, QKV.d, g);
  return [a, b, c];
}

export function makeWeights(seed = QKV.seed) {
  const [Wq, Wk, Wv] = threeMatrices(seed);
  return { Wq, Wk, Wv };
}

export function makeInput(seed) {
  const g = makeGauss(mulberry32(seed));
  return Array.from({ length: QKV.d }, () => g());
}

const col = (x) => x.map((v) => [v]);
const flat = (M) => M.map((r) => r[0]);

export function projectFused(W, x) {
  const y = flat(matmul(stack(W.Wq, W.Wk, W.Wv), col(x)));
  const d = x.length === y.length / 3 ? x.length : y.length / 3;
  return { q: y.slice(0, d), k: y.slice(d, 2 * d), v: y.slice(2 * d) };
}

export function projectSeparate(W, x) {
  return { q: flat(matmul(W.Wq, col(x))), k: flat(matmul(W.Wk, col(x))), v: flat(matmul(W.Wv, col(x))) };
}

export function maxAbsDiff(a, b) {
  let m = 0;
  for (const key of ['q', 'k', 'v']) for (let i = 0; i < a[key].length; i++) m = Math.max(m, Math.abs(a[key][i] - b[key][i]));
  return m;
}

export function makeGrads(seed = QKV.seed + 1) {
  const [Gq, Gk, Gv] = threeMatrices(seed);
  return { Gq, Gk, Gv };
}

export function rms(M) { return frobenius(M) / Math.sqrt(M.length * M[0].length); }

export function orthSizes(G, kscale) {
  const Gk = scale(G.Gk, kscale);
  return {
    fused: split(newtonSchulz5(stack(G.Gq, Gk, G.Gv))).map(rms),
    separate: [G.Gq, Gk, G.Gv].map((M) => rms(newtonSchulz5(M))),
  };
}
