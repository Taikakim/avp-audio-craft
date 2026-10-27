// Owner: WINTERMUTE (created 2026-10-27)
// The maths behind the lora-a-rotation animation: a rank-1 adapter b aT on a 2-D input and output, trained with
// fixed-size (normalised) steps, to show why a large A barely turns while B (zero at the start) does the learning.
export const ROT = { steps: 300, lrA: 0.002, lrB: 0.02, aStart: [3, 0], targetDeg: 70, bTarget: [0.6, 0.8], early: 50 };

const RAD = Math.PI / 180;
const norm = (v) => Math.hypot(v[0], v[1]);
const dot = (u, v) => u[0] * v[0] + u[1] * v[1];

export function targetA() { return [Math.cos(ROT.targetDeg * RAD), Math.sin(ROT.targetDeg * RAD)]; }

export function angleDeg(v) { return Math.atan2(v[1], v[0]) / RAD; }

export function overlap(u, v) {
  const nu = norm(u);
  const nv = norm(v);
  if (nu === 0 || nv === 0) return 0;
  const c = dot(u, v) / (nu * nv);
  return c * c;
}

// Error matrix E = b aT - T, with T = b* a*T.
function errMatrix(a, b) {
  const as = targetA();
  const bs = ROT.bTarget;
  return [
    [b[0] * a[0] - bs[0] * as[0], b[0] * a[1] - bs[0] * as[1]],
    [b[1] * a[0] - bs[1] * as[0], b[1] * a[1] - bs[1] * as[1]],
  ];
}

export function lossOf(a, b) {
  const E = errMatrix(a, b);
  return E[0][0] ** 2 + E[0][1] ** 2 + E[1][0] ** 2 + E[1][1] ** 2;
}

export function createRotSim({ mult = 1 } = {}) {
  let a = ROT.aStart.slice();
  let b = [0, 0];
  let t = 0;
  let aEarly = null;
  const trail = { a: [a.slice()], b: [b.slice()] };
  const losses = [lossOf(a, b)];

  function step() {
    const f = 1 - t / ROT.steps;
    const E = errMatrix(a, b);
    const gb = [E[0][0] * a[0] + E[0][1] * a[1], E[1][0] * a[0] + E[1][1] * a[1]];
    const ga = [E[0][0] * b[0] + E[1][0] * b[1], E[0][1] * b[0] + E[1][1] * b[1]];
    const nb = norm(gb);
    const na = norm(ga);
    let stepB = 0;
    let stepA = 0;
    let nextB = b;
    let nextA = a;
    if (nb >= 1e-12) {
      const k = ROT.lrB * f / nb;
      nextB = [b[0] - k * gb[0], b[1] - k * gb[1]];
      stepB = Math.hypot(nextB[0] - b[0], nextB[1] - b[1]);
    }
    if (na >= 1e-12) {
      const k = ROT.lrA * mult * f / na;
      nextA = [a[0] - k * ga[0], a[1] - k * ga[1]];
      stepA = Math.hypot(nextA[0] - a[0], nextA[1] - a[1]);
    }
    a = nextA;
    b = nextB;
    t += 1;
    if (t === ROT.early) aEarly = a.slice();
    const loss = lossOf(a, b);
    trail.a.push(a.slice());
    trail.b.push(b.slice());
    losses.push(loss);
    return { t, a: a.slice(), b: b.slice(), loss, stepA, stepB };
  }

  return {
    get t() { return t; },
    get done() { return t >= ROT.steps; },
    get a() { return a.slice(); },
    get b() { return b.slice(); },
    get aEarly() { return aEarly ? aEarly.slice() : null; },
    trail,
    losses,
    step,
  };
}
