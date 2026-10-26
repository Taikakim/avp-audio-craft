// Owner: WINTERMUTE (created 2026-10-26)
// Seeded randomness and the minibatch-gradient noise model. Pure functions, no DOM.
export function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Standard normal numbers from a uniform generator (Box-Muller, spare value cached).
export function makeGauss(rng) {
  let spare = null;
  return function () {
    if (spare !== null) { const s = spare; spare = null; return s; }
    let u = 0;
    while (u === 0) u = rng();
    const v = rng();
    const rad = Math.sqrt(-2 * Math.log(u));
    spare = rad * Math.sin(2 * Math.PI * v);
    return rad * Math.cos(2 * Math.PI * v);
  };
}
