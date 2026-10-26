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

// ---------------------------------------------------------------- AdamW
// state: null on the first call, else the `state` returned by the previous call.
// opts.w: current weights, only needed when wd > 0 (decoupled weight decay).
export function adamwStep(state, grad, opts = {}) {
  const { lr = 1e-3, beta1 = 0.9, beta2 = 0.999, eps = 1e-8, wd = 0, w = null } = opts;
  const [r, c] = shape(grad);
  const prev = state ?? { t: 0, m: zeros(r, c), v: zeros(r, c) };
  const t = prev.t + 1;
  const m = map2(prev.m, grad, (m0, g) => beta1 * m0 + (1 - beta1) * g);
  const v = map2(prev.v, grad, (v0, g) => beta2 * v0 + (1 - beta2) * g * g);
  const c1 = 1 - Math.pow(beta1, t);
  const c2 = 1 - Math.pow(beta2, t);
  const update = m.map((row, i) => row.map((mi, j) => {
    const adaptive = (mi / c1) / (Math.sqrt(v[i][j] / c2) + eps);
    const decay = wd > 0 && w ? wd * w[i][j] : 0;
    return lr * (adaptive + decay);
  }));
  return { update, state: { t, m, v } };
}

// ---------------------------------------------------------------- Newton-Schulz / Muon
// Quintic iteration X <- a X + (b A + c A^2) X with A = X X^T. Frobenius-normalise first;
// work on the wide orientation (rows <= cols) like the reference Muon code.
export function newtonSchulz(M, iters = 5, coeffs = NS_COEFFS) {
  const [a, b, c] = coeffs;
  const [r, cc] = shape(M);
  const tall = r > cc;
  let X = scale(M, 1 / (frobenius(M) + 1e-7));
  if (tall) X = transpose(X);
  for (let k = 0; k < iters; k++) {
    const A = matmul(X, transpose(X));
    const B = add(scale(A, b), scale(matmul(A, A), c));
    X = add(scale(X, a), matmul(B, X));
  }
  return tall ? transpose(X) : X;
}
export function newtonSchulz5(M) { return newtonSchulz(M, 5, NS_COEFFS); }

// scaleMode: 'moonlight' = 0.2*sqrt(max(rows, cols)) (every matrix moves ~0.2*lr per weight, like AdamW);
//            'keller'    = sqrt(max(1, rows/cols)) (original Muon code); 'none' = 1.
export function muonScale(rows, cols, mode) {
  if (mode === 'moonlight') return 0.2 * Math.sqrt(Math.max(rows, cols));
  if (mode === 'keller') return Math.sqrt(Math.max(1, rows / cols));
  return 1;
}
export function muonStep(state, grad, opts = {}) {
  const { lr = 0.02, momentum = 0.95, scaleMode = 'moonlight' } = opts;
  const [r, c] = shape(grad);
  const prev = state ?? { buf: zeros(r, c) };
  const buf = map2(prev.buf, grad, (b0, g) => momentum * b0 + g);
  const o = newtonSchulz5(buf);
  const update = scale(o, lr * muonScale(r, c, scaleMode));
  return { update, state: { buf } };
}

// ---------------------------------------------------------------- number formats
// minExp = exponent of the smallest normal number (subnormals share its spacing).
export const DTYPES = {
  fp32: { mant: 23, minExp: -126, max: 3.4028234663852886e38, label: 'fp32' },
  bf16: { mant: 7, minExp: -126, max: 3.3895313892515355e38, label: 'bf16' },
  fp16: { mant: 10, minExp: -14, max: 65504, label: 'fp16' },
  fp8e4m3: { mant: 3, minExp: -6, max: 448, label: 'fp8 (e4m3)' },
};

const f32 = new Float32Array(1);
const u32 = new Uint32Array(f32.buffer);

function roundHalfEven(x) {
  const f = Math.floor(x);
  const d = x - f;
  if (d < 0.5) return f;
  if (d > 0.5) return f + 1;
  return f % 2 === 0 ? f : f + 1;
}
function exponentOf(a) {
  let e = Math.floor(Math.log2(a));
  while (Math.pow(2, e) > a) e--;
  while (Math.pow(2, e + 1) <= a) e++;
  return e;
}
// Generic round-to-nearest-even onto a (mant, minExp, max) grid. Overflow: fp8 saturates, others go to infinity.
function quantize(x, dt, saturate) {
  if (!Number.isFinite(x) || x === 0) return x;
  const sign = x < 0 ? -1 : 1;
  const a = Math.abs(x);
  const e = Math.max(exponentOf(a), dt.minExp);
  const spacing = Math.pow(2, e - dt.mant);
  const q = roundHalfEven(a / spacing) * spacing;
  if (q > dt.max) return sign * (saturate ? dt.max : Infinity);
  return sign * q;
}
function roundBf16(x) {
  f32[0] = x;
  let b = u32[0];
  if (((b >>> 23) & 0xff) === 0xff) return f32[0]; // inf / nan
  b = (b + 0x7fff + ((b >>> 16) & 1)) >>> 0;
  u32[0] = (b & 0xffff0000) >>> 0;
  return f32[0];
}

export function roundTo(x, dtype) {
  switch (dtype) {
    case 'fp32': return Math.fround(x);
    case 'bf16': return roundBf16(x);
    case 'fp16': return quantize(x, DTYPES.fp16, false);
    case 'fp8e4m3': return quantize(x, DTYPES.fp8e4m3, true);
    default: throw new Error(`unknown dtype ${dtype}`);
  }
}
// Spacing between representable numbers around |w|.
export function ulp(w, dtype) {
  const dt = DTYPES[dtype];
  if (!dt) throw new Error(`unknown dtype ${dtype}`);
  const a = Math.abs(w);
  if (a === 0) return Math.pow(2, dt.minExp - dt.mant);
  return Math.pow(2, Math.max(exponentOf(a), dt.minExp) - dt.mant);
}
// Does storing w + dw in this format change the stored weight at all?
export function survivesUpdate(w, dw, dtype) {
  if (dw === 0) return false;
  const stored = roundTo(w, dtype);
  return roundTo(stored + dw, dtype) !== stored;
}
