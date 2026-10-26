// Owner: WINTERMUTE (created 2026-10-26)
// Test fixtures: matrices with known singular values.
import { zeros } from '../lib/optim.js';

// n random orthonormal vectors (Gram-Schmidt of gaussian vectors).
export function orth(n, gauss) {
  const Q = [];
  for (let i = 0; i < n; i++) {
    let v = Array.from({ length: n }, () => gauss());
    for (const q of Q) {
      const d = v.reduce((s, x, k) => s + x * q[k], 0);
      v = v.map((x, k) => x - d * q[k]);
    }
    const nv = Math.sqrt(v.reduce((s, x) => s + x * x, 0));
    Q.push(v.map((x) => x / nv));
  }
  return Q;
}
// An r x c matrix whose singular values are exactly svs (length min(r, c)).
export function withSingularValues(r, c, svs, gauss) {
  const U = orth(r, gauss), V = orth(c, gauss);
  const M = zeros(r, c);
  svs.forEach((s, k) => {
    for (let i = 0; i < r; i++) for (let j = 0; j < c; j++) M[i][j] += s * U[k][i] * V[k][j];
  });
  return M;
}
