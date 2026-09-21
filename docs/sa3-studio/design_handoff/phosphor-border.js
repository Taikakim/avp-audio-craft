/**
 * C64 loader-border effect with CRT phosphor simulation.
 *
 *   const fx = createPhosphorBorder(canvas, { thickness: 4, palette: PALETTES.teal });
 *   fx.start();
 *   fx.set({ linesPerColour: 20 });
 *   fx.stop();
 *   fx.destroy();
 *
 * The full raster is simulated but only the border ring is stored and drawn.
 * Set thickness >= height/2 and the ring fills the canvas, giving a solid strip
 * instead of a frame — same code path.
 */

export const PALETTES = {
  teal:  ['#000000', '#06201f', '#0d3d3b', '#1f7a7a', '#3aa8a4', '#7fd8d2',
          '#3aa8a4', '#1f7a7a', '#0d3d3b', '#06201f'],
  amber: ['#000000', '#1a0d00', '#4d2900', '#a35c00', '#e89c1a', '#ffc766',
          '#e89c1a', '#a35c00', '#4d2900', '#1a0d00'],
  accent: ['#000000', '#000000', '#1f7a7a', '#000000', '#6b5b95', '#000000',
           '#4a8a4a', '#000000', '#d4900f', '#000000'],
  sparse: ['#000000', '#000000', '#000000', '#000000',
           '#000000', '#000000', '#000000', '#ffffff'],
  c64:   ['#000000', '#ffffff', '#883932', '#67b6bd', '#8b3f96', '#55a049',
          '#40318d', '#bfce72', '#8b5429', '#574200', '#b86962', '#505050',
          '#787878', '#94e089', '#7869c4', '#9f9f9f'],
};

const DEFAULTS = {
  thickness: 4,
  linesPerColour: 3,
  jitter: 0.59,
  persistence: 0.002,
  chromaBleed: 1.5,
  supersample: 8,
  sweepHz: 95,
  gain: 0.8,
  spotSpread: 0.16,
  // When true the canvas is left transparent where the phosphor is dark, so an
  // unlit border settles to whatever is behind it instead of to black.
  alphaOut: false,
  palette: PALETTES.teal,
};

// Green phosphor persists longest, blue decays fastest, so a white flash
// trails toward green. Multipliers on the base persistence.
const TAU_R = 1.0, TAU_G = 1.6, TAU_B = 0.6;

const hexToRgb = (h) => [
  parseInt(h.slice(1, 3), 16) / 255,
  parseInt(h.slice(3, 5), 16) / 255,
  parseInt(h.slice(5, 7), 16) / 255,
];

export function createPhosphorBorder(canvas, options = {}) {
  const cfg = { ...DEFAULTS, ...options };
  const ctx = canvas.getContext('2d');

  let RW = 0, RH = 0, N = 0, T = -1;
  let map, ringPix, ring, ringCount, img, px;
  let beam = 0, toWrite = 0, idx = 0;
  let fY = 0, fU = 0, fV = 0, tY = 0, tU = 0, tV = 0;
  let raf = null, last = 0;

  function buildRing() {
    RW = canvas.width; RH = canvas.height; N = RW * RH;
    if (!N) return false;
    T = Math.max(1, Math.min(cfg.thickness, Math.ceil(RH / 2)));

    map = new Int32Array(N).fill(-1);
    const pixels = [];
    for (let y = 0; y < RH; y++) {
      const edgeRow = y < T || y >= RH - T;
      for (let x = 0; x < RW; x++) {
        if (edgeRow || x < T || x >= RW - T) {
          map[y * RW + x] = pixels.length;
          pixels.push(y * RW + x);
        }
      }
    }
    ringCount = pixels.length;
    ringPix = Int32Array.from(pixels);
    ring = new Float32Array(ringCount * 3);
    img = ctx.createImageData(RW, RH);
    px = img.data;
    if (beam >= N) beam = 0;
    return true;
  }

  function nextColour() {
    const list = cfg.palette;
    idx = (idx + 1) % list.length;
    const [r, g, b] = hexToRgb(list[idx]);
    tY =  0.299 * r + 0.587 * g + 0.114 * b;
    tU = -0.147 * r - 0.289 * g + 0.436 * b;
    tV =  0.615 * r - 0.515 * g - 0.100 * b;
  }

  function writeInterval() {
    // The ratio that defines the whole look: how many raster lines one colour
    // survives before the next register write. Independent of canvas size.
    const base = cfg.linesPerColour * RW;
    return base * (1 + cfg.jitter * (Math.random() * 2 - 1));
  }

  function addEnergy(p, r, g, b, dose, spread) {
    let i = map[p];
    if (i >= 0) {
      const o = i * 3;
      ring[o] += r * dose; ring[o + 1] += g * dose; ring[o + 2] += b * dose;
    }
    if (spread <= 0) return;
    const d = dose * spread;
    if (p >= RW) {
      i = map[p - RW];
      if (i >= 0) { const o = i * 3; ring[o] += r * d; ring[o + 1] += g * d; ring[o + 2] += b * d; }
    }
    if (p < N - RW) {
      i = map[p + RW];
      if (i >= 0) { const o = i * 3; ring[o] += r * d; ring[o + 1] += g * d; ring[o + 2] += b * d; }
    }
  }

  // Distance to the next change in visibility along the current line. The beam is
  // simulated across the whole raster — colour can change mid-line, inside the
  // hidden interior — and addEnergy() is what masks the result down to the ring.
  function spanToEdge(x, y) {
    if (y < T || y >= RH - T) return RW - x;
    if (x < T) return T - x;
    if (x < RW - T) return RW - T - x;
    return RW - x;
  }

  function step(dt) {
    const S = Math.max(1, cfg.supersample | 0);
    const bleed = Math.max(0.2, cfg.chromaBleed);
    const aC = 1 - Math.exp(-1 / bleed);
    const aY = 1 - Math.exp(-1 / (bleed * 0.35));
    const spread = cfg.spotSpread;
    const dose = cfg.gain / (1 + 2 * spread);

    const dtS = dt / S;
    const fr = Math.exp(-dtS / (cfg.persistence * TAU_R));
    const fg = Math.exp(-dtS / (cfg.persistence * TAU_G));
    const fb = Math.exp(-dtS / (cfg.persistence * TAU_B));
    const stepPx = (cfg.sweepHz * N * dt) / S;

    for (let s = 0; s < S; s++) {
      for (let i = 0; i < ring.length; i += 3) {
        ring[i] *= fr; ring[i + 1] *= fg; ring[i + 2] *= fb;
      }

      let remain = stepPx, guard = 40000;
      while (remain > 1e-4 && guard-- > 0) {
        const y = (beam / RW) | 0;
        const x = beam - y * RW;

        if (toWrite <= 0) { nextColour(); toWrite += writeInterval(); }
        const run = Math.max(1, Math.round(
          Math.min(remain, toWrite, spanToEdge(x, y))
        ));

        for (let i = 0; i < run; i++) {
          // One-pole low-pass along the beam path, chroma slower than luma.
          // This is the video amplifier's bandwidth limit and it is what makes
          // the colour rips soft instead of hard-edged.
          fY += (tY - fY) * aY;
          fU += (tU - fU) * aC;
          fV += (tV - fV) * aC;
          const r = fY + 1.140 * fV;
          const g = fY - 0.395 * fU - 0.581 * fV;
          const b = fY + 2.032 * fU;
          addEnergy(beam, r > 0 ? r : 0, g > 0 ? g : 0, b > 0 ? b : 0, dose, spread);
          beam++; if (beam >= N) beam = 0;
        }
        remain -= run; toWrite -= run;
      }
    }

    const alphaOut = cfg.alphaOut;
    for (let i = 0; i < ringCount; i++) {
      const o = i * 3, j = ringPix[i] * 4;
      const r = ring[o], g = ring[o + 1], b = ring[o + 2];
      px[j]     = 255 * (r / (1 + r));
      px[j + 1] = 255 * (g / (1 + g));
      px[j + 2] = 255 * (b / (1 + b));
      if (alphaOut) {
        const m = r > g ? (r > b ? r : b) : (g > b ? g : b);
        px[j + 3] = 255 * (m / (1 + m));
      } else {
        px[j + 3] = 255;
      }
    }
    ctx.putImageData(img, 0, 0);
  }

  function frame(now) {
    let dt = (now - last) / 1000;
    last = now;
    if (dt > 0.05) dt = 0.05;
    if (dt < 0.002) dt = 0.002;
    step(dt);
    raf = requestAnimationFrame(frame);
  }

  buildRing();

  return {
    start() {
      if (raf !== null) return;
      last = performance.now();
      raf = requestAnimationFrame(frame);
    },
    stop() {
      if (raf === null) return;
      cancelAnimationFrame(raf);
      raf = null;
    },
    set(patch) {
      const needsRebuild = patch.thickness !== undefined && patch.thickness !== cfg.thickness;
      Object.assign(cfg, patch);
      if (needsRebuild) buildRing();
    },
    resize(w, h) {
      canvas.width = w; canvas.height = h;
      T = -1;
      buildRing();
    },
    destroy() {
      this.stop();
      map = ringPix = ring = img = px = null;
      ctx.clearRect(0, 0, RW, RH);
    },
  };
}
