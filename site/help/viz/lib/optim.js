// Owner: WINTERMUTE (created 2026-10-26)
// Update maths for the help-pane animations. Pure functions, no DOM.
// A "matrix" is an array of rows (arrays of numbers). Convention: an optimiser's `update`
// is the amount SUBTRACTED from the weights (w_new = w - update).

export const NS_COEFFS = [3.4445, -4.7750, 2.0315];

// ---------------------------------------------------------------- matrix helpers
export function zeros(r, c) {
  return Array.from({ length: r }, () => new Array(c).fill(0));
}
export function shape(M) { return [M.length, M[0].length]; }
export function map(M, f) { return M.map((row) => row.map((x) => f(x))); }
export function map2(A, B, f) { return A.map((row, i) => row.map((x, j) => f(x, B[i][j]))); }
export function scale(M, s) { return map(M, (x) => x * s); }
export function add(A, B) { return map2(A, B, (x, y) => x + y); }
export function transpose(M) {
  const [r, c] = shape(M);
  const T = zeros(c, r);
  for (let i = 0; i < r; i++) for (let j = 0; j < c; j++) T[j][i] = M[i][j];
  return T;
}
export function matmul(A, B) {
  const [r, k] = shape(A);
  const [k2, c] = shape(B);
  if (k !== k2) throw new Error(`matmul shape mismatch ${r}x${k} * ${k2}x${c}`);
  const C = zeros(r, c);
  for (let i = 0; i < r; i++)
    for (let p = 0; p < k; p++) {
      const a = A[i][p];
      if (a === 0) continue;
      for (let j = 0; j < c; j++) C[i][j] += a * B[p][j];
    }
  return C;
}
export function frobenius(M) {
  let s = 0;
  for (const row of M) for (const x of row) s += x * x;
  return Math.sqrt(s);
}
export function meanAbs(M) {
  let s = 0, n = 0;
  for (const row of M) for (const x of row) { s += Math.abs(x); n++; }
  return s / n;
}

// Eigenvalues of a symmetric matrix by cyclic Jacobi rotations (adequate for <= 16x16).
function symmetricEigenvalues(S) {
  const n = S.length;
  const A = S.map((row) => row.slice());
  for (let sweep = 0; sweep < 60; sweep++) {
    let off = 0;
    for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) if (i !== j) off += A[i][j] * A[i][j];
    if (off < 1e-24) break;
    for (let p = 0; p < n - 1; p++)
      for (let q = p + 1; q < n; q++) {
        const apq = A[p][q];
        if (Math.abs(apq) < 1e-300) continue;
        const theta = (A[q][q] - A[p][p]) / (2 * apq);
        const t = (theta >= 0 ? 1 : -1) / (Math.abs(theta) + Math.sqrt(theta * theta + 1));
        const c = 1 / Math.sqrt(t * t + 1);
        const s = t * c;
        for (let k = 0; k < n; k++) {
          const akp = A[k][p], akq = A[k][q];
          A[k][p] = c * akp - s * akq;
          A[k][q] = s * akp + c * akq;
        }
        for (let k = 0; k < n; k++) {
          const apk = A[p][k], aqk = A[q][k];
          A[p][k] = c * apk - s * aqk;
          A[q][k] = s * apk + c * aqk;
        }
      }
  }
  return A.map((row, i) => row[i]);
}

// Singular values, largest first. Uses the smaller of M^T M and M M^T.
export function singularValues(M) {
  const [r, c] = shape(M);
  const S = r >= c ? matmul(transpose(M), M) : matmul(M, transpose(M));
  return symmetricEigenvalues(S).map((e) => Math.sqrt(Math.max(e, 0))).sort((a, b) => b - a);
}
