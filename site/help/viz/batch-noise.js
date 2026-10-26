// Owner: WINTERMUTE (created 2026-10-26)
// Animation module "batch-noise": a ball rolls down a valley; one bold arrow is the true step direction, a cloud of thin arrows is
// what 24 different minibatches of the chosen size would suggest. Used by the glossary entry "momentum".
import { mulberry32, makeGauss, CALIBRATION } from './lib/noise.js';
import { VALLEY, BATCHES, grad, loss, sampleCloud, readouts, noiselessPath, createValleySim } from './lib/valley.js';
import { svg, el, injectStyle, applyColors, loop, realNote } from './lib/kit.js';

const CSS = `
.vz-noise{font:14px/1.45 system-ui,sans-serif;color:var(--vz-fg);background:var(--vz-bg);padding:8px;max-width:100%;box-sizing:border-box}
.vz-noise .vz-controls{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center;margin-bottom:8px}
.vz-noise .vz-group{display:flex;flex-wrap:wrap;gap:4px;align-items:center}
.vz-noise .vz-btn{font:inherit;color:var(--vz-fg);background:transparent;border:1px solid var(--vz-muted);border-radius:4px;padding:3px 9px;cursor:pointer}
.vz-noise .vz-btn[aria-pressed="true"]{background:var(--vz-fg);border-color:var(--vz-accent);color:var(--vz-bg);box-shadow:inset 0 -3px 0 var(--vz-accent)}
.vz-noise .vz-slider{display:flex;align-items:center;gap:8px;flex:1 1 220px;min-width:0}
.vz-noise .vz-slider input{flex:1 1 90px;min-width:0;accent-color:var(--vz-accent)}
.vz-noise .vz-slider output{min-width:3ch;font-weight:600;text-align:right}
.vz-noise svg.vz-valley{width:100%;height:auto;display:block;border:1px solid var(--vz-muted);border-radius:4px}
.vz-noise .vz-legend{display:flex;flex-wrap:wrap;gap:2px 14px;font-size:13px;margin:6px 0}
.vz-noise .vz-sw{display:inline-block;width:16px;height:0;border-top:3px solid;margin-right:5px;vertical-align:middle}
.vz-noise .vz-sw.thin{border-top-width:1px}
.vz-noise .vz-sw.dash{border-top-style:dashed;border-top-width:2px}
.vz-noise .vz-reads{margin:6px 0;font-size:13px}
.vz-noise .vz-reads p{margin:2px 0}
.vz-noise .vz-reads b{color:var(--vz-fg);font-variant-numeric:tabular-nums}
.vz-noise .vz-reads .vz-why{color:var(--vz-muted);font-size:12px}
.vz-noise .vz-tag{display:inline-block;margin:2px 0;padding:1px 8px;border:1px solid var(--vz-muted);border-radius:10px;font-size:12px}
.vz-noise .vz-key{font-size:12px;color:var(--vz-muted);margin:6px 0}
.vz-noise .vz-real{margin-top:10px;border-top:1px solid var(--vz-muted);padding-top:6px;font-size:13px}
.vz-noise .vz-real h4{margin:0 0 4px;font-size:13px}
.vz-noise .vz-real dt{font-weight:600;margin-top:4px}
.vz-noise .vz-real dd{margin:0}
.vz-noise .vz-real p{margin:2px 0}
`;

// Plot geometry: world x in [-4, 4], y in [-1.73, 1.73], same scale on both axes so arrow directions are true.
const W = 420, H = 180, PX = 52, CX = W / 2, CY = H / 2, MARGIN = 10;
const XMAX = (W / 2 - MARGIN) / PX, YMAX = (H / 2 - MARGIN) / PX;   // world limits the drawn ball and path are held inside
const clampPt = ([x, y]) => [Math.max(-XMAX, Math.min(XMAX, x)), Math.max(-YMAX, Math.min(YMAX, y))];
const offChart = ([x, y]) => Math.abs(x) > XMAX || Math.abs(y) > YMAX;
const sx = (x) => CX + x * PX;
const sy = (y) => CY - y * PX;
const LEVELS = [0.2, 0.8, 2, 4.5, 8, 12];
const STAGES = { early: 'Early in training', late: 'Late in training' };
const MAX_ARROW = 110;                                   // pixels; longer arrows are cut to this
const g0 = Math.hypot(...grad(VALLEY.start));
const ARROW_SCALE = (0.25 * W) / g0;                     // pixels per unit of gradient: start arrow = a quarter of the width
const fmt = (v) => (v >= 10 ? v.toFixed(1) : v.toFixed(2));

export function mount(container, params = {}, help = {}) {
  injectStyle('vz-noise-style', CSS);
  const colors = { accent: '#2b6cb0', fg: '#1a1a1a', muted: '#777', bg: '#fff', good: '#2f855a', bad: '#c53030', ...(help.colors || {}) };
  // rule: series are told apart by swatches beside their names; text never names a colour
  const reducedMotion = !!help.reducedMotion;
  let batchIdx = BATCHES.includes(params.batch) ? BATCHES.indexOf(params.batch) : BATCHES.indexOf(8);
  let momentum = typeof params.momentum === 'boolean' ? params.momentum : false;
  let stage = params.stage === 'early' || params.stage === 'late' ? params.stage : 'late';
  let sim = null, gauss = null;
  const seed = 11;

  const root = el('div', { class: 'vz-noise' });
  applyColors(root, colors);
  container.append(root);

  // ---- controls
  const slider = el('input', { id: 'vz-noise-batch', type: 'range', min: 0, max: BATCHES.length - 1, step: 1 });
  slider.value = String(batchIdx);
  const out = el('output', { id: 'vz-noise-batch-out', for: 'vz-noise-batch' });
  slider.addEventListener('input', () => { batchIdx = Number(slider.value); restart(); });
  const sliderBox = el('div', { class: 'vz-slider' }, [el('label', { for: 'vz-noise-batch', text: 'Batch size' }), slider, out]);

  const momBtn = el('button', { type: 'button', class: 'vz-btn', text: 'Momentum', 'aria-pressed': 'false' });
  momBtn.addEventListener('click', () => { momentum = !momentum; restart(); });

  const stageBtns = {};
  const stageGroup = el('div', { class: 'vz-group', role: 'group', 'aria-label': 'Noise level' });
  for (const id of ['early', 'late']) {
    stageBtns[id] = el('button', { type: 'button', class: 'vz-btn', text: STAGES[id], 'aria-pressed': 'false' });
    stageBtns[id].addEventListener('click', () => { stage = id; restart(); });
    stageGroup.append(stageBtns[id]);
  }
  const replay = el('button', { type: 'button', class: 'vz-btn', text: 'Replay' });
  replay.addEventListener('click', () => restart());
  const controls = el('div', { class: 'vz-controls' }, [sliderBox, momBtn, stageGroup, replay]);
  root.append(controls);

  // ---- the valley
  const board = svg('svg', {
    class: 'vz-valley', viewBox: `0 0 ${W} ${H}`, role: 'img',
    'aria-label': 'A valley seen from above with a ball rolling toward its lowest point. A bold arrow shows the true downhill direction; thin arrows show the directions that 24 random minibatches would suggest.',
  });
  const mk = (id, color) => svg('marker', { id, viewBox: '0 0 10 10', refX: 8, refY: 5, markerWidth: 6, markerHeight: 6, orient: 'auto-start-reverse', markerUnits: 'strokeWidth' },
    [svg('path', { d: 'M0,0 L10,5 L0,10 z', fill: color })]);
  board.append(svg('defs', {}, [mk('vz-noise-ah-true', colors.accent), mk('vz-noise-ah-cloud', colors.muted), mk('vz-noise-ah-used', colors.good)]));
  for (const L of LEVELS) {
    board.append(svg('ellipse', { class: 'contour', cx: sx(0), cy: sy(0), rx: Math.sqrt(2 * L / VALLEY.a) * PX, ry: Math.sqrt(2 * L / VALLEY.b) * PX, fill: 'none', stroke: colors.muted, 'stroke-opacity': 0.4 }));
  }
  board.append(svg('path', { d: `M${sx(0) - 5},${sy(0)}h10M${sx(0)},${sy(0) - 5}v10`, stroke: colors.muted, 'stroke-width': 1.5 }));
  board.append(svg('polyline', {
    class: 'noiseless', fill: 'none', stroke: colors.muted, 'stroke-width': 1.6, 'stroke-dasharray': '5 4',
    points: noiselessPath().map(([x, y]) => `${sx(x).toFixed(1)},${sy(y).toFixed(1)}`).join(' '),
  }));
  const pathLine = svg('polyline', { class: 'path', fill: 'none', stroke: colors.fg, 'stroke-width': 1.8, 'stroke-linejoin': 'round', points: '' });
  board.append(pathLine);
  const cloud = [];
  for (let i = 0; i < VALLEY.cloudSize; i++) {
    const ln = svg('line', { class: 'cloud', stroke: colors.muted, 'stroke-width': 1.1, 'stroke-opacity': 0.75, 'marker-end': 'url(#vz-noise-ah-cloud)', x1: 0, y1: 0, x2: 0, y2: 0 });
    cloud.push(ln); board.append(ln);
  }
  const usedLine = svg('line', { class: 'used-step', stroke: colors.good, 'stroke-width': 2, 'marker-end': 'url(#vz-noise-ah-used)', visibility: 'hidden', x1: 0, y1: 0, x2: 0, y2: 0 });
  const trueLine = svg('line', { class: 'true-grad', stroke: colors.accent, 'stroke-width': 3.2, 'marker-end': 'url(#vz-noise-ah-true)', x1: 0, y1: 0, x2: 0, y2: 0 });
  const ball = svg('circle', { class: 'ball', r: 6, fill: colors.fg, stroke: colors.bg, 'stroke-width': 2, cx: sx(VALLEY.start[0]), cy: sy(VALLEY.start[1]) });
  const offMark = svg('text', { class: 'off-chart', 'font-size': 12, 'font-weight': 600, fill: colors.bad, visibility: 'hidden', 'text-anchor': 'middle', text: 'flung off the chart' });
  board.append(usedLine, trueLine, ball, offMark);
  root.append(board);

  const swatch = (c, cls = '') => el('span', { class: `vz-sw ${cls}`, style: `border-top-color:${c}`, 'aria-hidden': 'true' });
  const usedLegend = el('span', { hidden: true }, [swatch(colors.good), 'Direction the ball actually steps (averaged)']);
  root.append(el('div', { class: 'vz-legend' }, [
    el('span', {}, [swatch(colors.accent), 'True downhill direction']),
    el('span', {}, [swatch(colors.muted, 'thin'), `${VALLEY.cloudSize} minibatch guesses`]),
    usedLegend,
    el('span', {}, [swatch(colors.fg), 'Ball\'s path']),
    el('span', {}, [swatch(colors.muted, 'dash'), 'Path with no noise']),
  ]));

  // ---- readouts
  const snrEl = el('b', { id: 'vz-noise-snr' });
  const cosEl = el('b', { id: 'vz-noise-cos' });
  const msnrEl = el('b', { id: 'vz-noise-msnr' });
  const msnrRow = el('p', { hidden: true }, ['With momentum, at most: ', msnrEl, ' ',
    el('span', { class: 'vz-why', text: '(averaging helps this much only if the true direction holds still)' })]);
  const lossEl = el('b', { id: 'vz-noise-loss' });
  const tagEl = el('span', { id: 'vz-noise-tag', class: 'vz-tag' });
  root.append(el('div', { class: 'vz-reads' }, [
    el('p', {}, ['Signal to noise of one minibatch gradient: ', snrEl, ' ',
      el('span', { class: 'vz-why', text: '(above 1, the real direction beats the noise)' })]),
    el('p', {}, ['Two half batches agree (cosine): ', cosEl, ' ',
      el('span', { class: 'vz-why', text: '(1 = same direction, 0 = unrelated)' })]),
    msnrRow,
    el('p', {}, ['Height above the bottom of the valley (loss): ', lossEl, ' ',
      el('span', { class: 'vz-why', text: `(starts at ${fmt(loss(VALLEY.start))}; lower is better)` })]),
    el('p', {}, [tagEl]),
  ]));
  root.append(el('p', { class: 'vz-key', text: 'Arrows point where each guess would move the ball. Arrows longer than the limit are cut short; the noise at small batches is much bigger than shown. With very small batches the noise can throw the ball off the chart.' }));

  realNote(root, {
    live: [
      'The descent and every minibatch gradient: the ball takes real gradient steps on the valley, and each thin arrow is the true gradient plus seeded random noise, redrawn every step.',
      'The signal-to-noise ratio and the half-batch cosine are computed from the noise model at the ball\'s current position.',
    ],
    measured: [
      `The two noise levels are set so that at batch ${CALIBRATION.batch} two half batches agree as in our runs: a cosine of ${CALIBRATION.early} early in training and ${CALIBRATION.late} late (${CALIBRATION.source}).`,
      `Only batch ${CALIBRATION.batch} is measured. Every other size is extrapolated with the 1/sqrt(batch) noise model.`,
      `The momentum gain sqrt((1 + ${VALLEY.beta}) / (1 - ${VALLEY.beta})) = ${Math.sqrt((1 + VALLEY.beta) / (1 - VALLEY.beta)).toFixed(1)} assumes a steady signal, which is why it is shown as "at most".`,
    ],
    illustrative: [
      'The valley has two weights; real heads have millions. The learning rate is chosen for the picture.',
      'The noise is set at the starting point. As the ball nears the bottom the true gradient shrinks and the noise takes over: that is the qualitative point, not a measured curve.',
    ],
  });

  // ---- drawing
  const setArrow = (ln, x, y, gx, gy) => {          // arrow from world (x, y) along minus (gx, gy), in pixels
    let dx = -gx * ARROW_SCALE, dy = gy * ARROW_SCALE;   // screen y points down
    const len = Math.hypot(dx, dy);
    if (len > MAX_ARROW) { dx *= MAX_ARROW / len; dy *= MAX_ARROW / len; }
    ln.setAttribute('x1', sx(x).toFixed(1)); ln.setAttribute('y1', sy(y).toFixed(1));
    ln.setAttribute('x2', (sx(x) + dx).toFixed(1)); ln.setAttribute('y2', (sy(y) + dy).toFixed(1));
  };
  let lastUsed = null;
  function render() {
    const [x, y] = clampPt(sim.pos);
    const away = offChart(sim.pos);
    ball.setAttribute('cx', sx(x).toFixed(1)); ball.setAttribute('cy', sy(y).toFixed(1));
    ball.setAttribute('stroke', away ? colors.bad : colors.bg);
    ball.setAttribute('stroke-width', away ? 3 : 2);
    offMark.setAttribute('visibility', away ? 'visible' : 'hidden');
    if (away) {
      offMark.setAttribute('x', String(W / 2)); offMark.setAttribute('y', '16');
    }
    pathLine.setAttribute('points', sim.path.map((q) => { const [px, py] = clampPt(q); return `${sx(px).toFixed(1)},${sy(py).toFixed(1)}`; }).join(' '));
    const tg = grad(sim.pos);
    setArrow(trueLine, x, y, tg[0], tg[1]);
    const samples = sampleCloud(sim.pos, sim.sigma1, BATCHES[batchIdx], VALLEY.cloudSize, gauss);
    cloud.forEach((ln, i) => setArrow(ln, x, y, samples[i][0], samples[i][1]));
    if (momentum && lastUsed) { setArrow(usedLine, x, y, lastUsed[0], lastUsed[1]); usedLine.setAttribute('visibility', 'visible'); }
    else usedLine.setAttribute('visibility', 'hidden');
    const r = readouts(sim.pos, sim.sigma1, BATCHES[batchIdx], momentum ? VALLEY.beta : 0);
    snrEl.textContent = fmt(r.snr);
    cosEl.textContent = r.halfCos.toFixed(2);
    msnrEl.textContent = momentum && r.momentumSnr !== null ? fmt(r.momentumSnr) : '';
    msnrRow.hidden = !momentum;
    lossEl.textContent = fmt(loss(sim.pos));
    tagEl.textContent = r.measured ? 'measured at this batch size' : 'extrapolated with the noise model (1/sqrt(batch))';
    root.setAttribute('data-step', String(sim.t));
  }
  function syncControls() {
    const B = BATCHES[batchIdx];
    out.textContent = String(B);
    slider.setAttribute('aria-valuetext', `batch ${B}`);
    momBtn.setAttribute('aria-pressed', momentum ? 'true' : 'false');
    for (const [k, b] of Object.entries(stageBtns)) b.setAttribute('aria-pressed', k === stage ? 'true' : 'false');
    usedLegend.hidden = !momentum;
    root.setAttribute('data-batch', String(B));
    root.setAttribute('data-momentum', momentum ? 'on' : 'off');
    root.setAttribute('data-stage', stage);
  }
  function restart() {
    sim = createValleySim({ stage, batch: BATCHES[batchIdx], momentum, seed });
    gauss = makeGauss(mulberry32(seed + 1000));      // cloud draws: separate stream so they never disturb the descent
    lastUsed = null;
    syncControls();
    render();
    handle.resume();
  }
  function advance() {
    if (sim.done) return false;
    const s = sim.step();
    lastUsed = s.usedGrad;
    render();
    return !sim.done;
  }

  const handle = loop(root, () => advance(), { reducedMotion, controls });
  restart();

  return {
    destroy() {
      handle.destroy();
      root.remove();
    },
  };
}
