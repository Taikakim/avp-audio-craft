// Owner: WINTERMUTE (created 2026-10-27)
// The maths behind the lora-rank animation: adapter size, energy a rank keeps, and a 12 x 12 toy weight change.
import { matmul, transpose, frobenius, zeros } from './optim.js';
import { mulberry32, makeGauss, randnMatrix } from './noise.js';

export const LORA = { width: 1536, toy: 12, seed: 5, changeScale: 0.3 };
export const RANKS = [16, 32, 64, 128, 256, 512, 1024, 1536];
// Whole-model energy kept by a uniform rank, over the 229 weight matrices of a full fine-tune of the medium model
// (width 1536): WORKLOG.md 2026-07-24 (CONTINUITY, "xft distillation TAIL CONFIRMED"), model_index.md line 41.
// The same within 0.2 points across all 10 full fine-tunes.
export const MEASURED = [
  { r: 16, e: 0.045 }, { r: 64, e: 0.148 }, { r: 128, e: 0.257 }, { r: 512, e: 0.65 }, { r: 1024, e: 0.895 },
];

const KNOWN = [...MEASURED, { r: LORA.width, e: 1 }];

export function energyAt(r) {
  if (!(r >= 16 && r <= LORA.width)) throw new Error(`rank ${r} outside [16, ${LORA.width}]`);
  if (r === LORA.width) return { e: 1, kind: 'full' };
  for (const p of MEASURED) if (p.r === r) return { e: p.e, kind: 'measured' };
  for (let i = 0; i < KNOWN.length - 1; i++) {
    const a = KNOWN[i], b = KNOWN[i + 1];
    if (r > a.r && r < b.r) {
      const t = (Math.log2(r) - Math.log2(a.r)) / (Math.log2(b.r) - Math.log2(a.r));
      return { e: a.e + t * (b.e - a.e), kind: 'interpolated', between: [a.r, b.r] };
    }
  }
  throw new Error(`rank ${r} not placed`);
}

export function adapterParams(r, m = LORA.width, n = LORA.width) { return r * (m + n); }
export function fullParams(m = LORA.width, n = LORA.width) { return m * n; }
export function toyRank(r) { return Math.max(1, Math.round(LORA.toy * r / LORA.width)); }

export function toySpectrum() {
  const e128 = energyAt(128).e, e512 = energyAt(512).e, e1024 = energyAt(1024).e;
  const shares = [e128];
  for (let i = 0; i < 3; i++) shares.push((e512 - e128) / 3);
  for (let i = 0; i < 4; i++) shares.push((e1024 - e512) / 4);
  for (let i = 0; i < 4; i++) shares.push((1 - e1024) / 4);
  return shares.map(Math.sqrt);
}

// n x n orthogonal matrix: modified Gram-Schmidt on the columns of a Gaussian matrix.
export function orthogonal(n, gauss) {
  const R = randnMatrix(n, n, gauss);
  const cols = [];
  for (let j = 0; j < n; j++) {
    const v = R.map((row) => row[j]);
    for (const q of cols) {
      let d = 0;
      for (let i = 0; i < n; i++) d += v[i] * q[i];
      for (let i = 0; i < n; i++) v[i] -= d * q[i];
    }
    let nv = 0;
    for (let i = 0; i < n; i++) nv += v[i] * v[i];
    nv = Math.sqrt(nv);
    cols.push(v.map((x) => x / nv));
  }
  return Array.from({ length: n }, (_, i) => cols.map((c) => c[i]));
}

function lowRankSum(U, V, s, k) {
  const n = U.length, m = V.length;
  const M = zeros(n, m);
  for (let t = 0; t < k; t++)
    for (let i = 0; i < n; i++) for (let j = 0; j < m; j++) M[i][j] += s[t] * U[i][t] * V[j][t];
  return M;
}

export function makeToy(seed = LORA.seed) {
  const n = LORA.toy;
  const gauss = makeGauss(mulberry32(seed));
  const W0 = randnMatrix(n, n, gauss).map((row) => row.map((x) => x / Math.sqrt(n)));
  const U = orthogonal(n, gauss);
  const V = orthogonal(n, gauss);
  const raw = toySpectrum();
  const norm = Math.sqrt(raw.reduce((a, x) => a + x * x, 0));
  const f = LORA.changeScale * frobenius(W0) / norm;
  const s = raw.map((x) => x * f);
  const dW = matmul(matmul(U, s.map((si, i) => s.map((_, j) => (i === j ? si : 0)))), transpose(V));
  return { W0, U, V, s, dW };
}

export function truncate(toy, k) { return lowRankSum(toy.U, toy.V, toy.s, k); }

export function keptEnergy(toy, k) {
  let kept = 0, all = 0;
  toy.s.forEach((x, i) => { all += x * x; if (i < k) kept += x * x; });
  return kept / all;
}

export function rowNorms(M) { return M.map((row) => Math.sqrt(row.reduce((a, x) => a + x * x, 0))); }

export function rowLengths(toy, k) {
  const sum = (A, B) => A.map((row, i) => row.map((x, j) => x + B[i][j]));
  const target = rowNorms(sum(toy.W0, toy.dW));
  const lora = rowNorms(sum(toy.W0, truncate(toy, k)));
  const meanRelErr = target.reduce((a, t, i) => a + Math.abs(lora[i] - t) / t, 0) / target.length;
  return { target, lora, meanRelErr };
}
