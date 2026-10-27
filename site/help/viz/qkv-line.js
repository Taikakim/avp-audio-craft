// Owner: WINTERMUTE (created 2026-10-27)
// Animation module "qkv-line": scene 1 is an assembly line that turns one input into the three packets Q, K, V (one fused machine
// or three separate ones); scene 2 shows what orthogonalising the stack as one matrix does to the three step sizes.
// Used by the glossary entries "qkv" and "fused-matrix". Maths in lib/qkv.js.
import {
  QKV, KSCALES, makeWeights, makeInput, makeGrads, projectFused, projectSeparate, maxAbsDiff, orthSizes,
} from './lib/qkv.js';
import { svg, el, injectStyle, applyColors, loop, realNote } from './lib/kit.js';

const CSS = `
.vz-qkv{font:14px/1.45 system-ui,sans-serif;color:var(--vz-fg);background:var(--vz-bg);padding:8px;max-width:100%;box-sizing:border-box}
.vz-qkv [hidden]{display:none!important}
.vz-qkv .vz-controls{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center;margin-bottom:8px}
.vz-qkv .vz-group{display:flex;flex-wrap:wrap;gap:4px;align-items:center}
.vz-qkv .vz-btn{font:inherit;color:var(--vz-fg);background:transparent;border:1px solid var(--vz-muted);border-radius:4px;padding:3px 9px;cursor:pointer}
.vz-qkv .vz-btn[aria-pressed="true"]{background:var(--vz-fg);border-color:var(--vz-accent);color:var(--vz-bg);box-shadow:inset 0 -3px 0 var(--vz-accent)}
.vz-qkv .vz-slider{display:flex;align-items:center;gap:8px;flex:1 1 220px;min-width:0;margin-bottom:8px}
.vz-qkv .vz-slider input{flex:1 1 90px;min-width:0;accent-color:var(--vz-accent)}
.vz-qkv .vz-slider output{min-width:4ch;font-weight:600;text-align:right}
.vz-qkv svg.vz-line,.vz-qkv svg.vz-bars{width:100%;height:auto;display:block;border:1px solid var(--vz-muted);border-radius:4px}
.vz-qkv .vz-legend{display:flex;flex-wrap:wrap;gap:2px 14px;font-size:13px;margin:6px 0}
.vz-qkv .vz-sw{display:inline-block;width:12px;height:12px;border:1px solid var(--vz-muted);margin-right:5px;vertical-align:-1px}
.vz-qkv .vz-reads{margin:6px 0;font-size:13px}
.vz-qkv .vz-reads p{margin:2px 0}
.vz-qkv .vz-reads b{font-variant-numeric:tabular-nums}
.vz-qkv .vz-reads .vz-why{color:var(--vz-muted);font-size:12px}
.vz-qkv .vz-key{font-size:12px;color:var(--vz-muted);margin:6px 0}
.vz-qkv .vz-real{margin-top:10px;border-top:1px solid var(--vz-muted);padding-top:6px;font-size:13px}
.vz-qkv .vz-real h4{margin:0 0 4px;font-size:13px}
.vz-qkv .vz-real dt{font-weight:600;margin-top:4px}
.vz-qkv .vz-real dd{margin:0}
.vz-qkv .vz-real p{margin:2px 0}
`;

const SCENES = { make: 'Making Q, K, V', orth: 'Orthogonalising the step' };
const MODES = { fused: 'One fused machine', separate: 'Three machines' };
const BLOCKS = ['q', 'k', 'v'];
const WORDS = { q: 'query', k: 'key', v: 'value' };

// Scene 1 geometry (viewBox units).
const W = 400, H = 200;
const LANES = [45, 100, 155];
const MX = 105, MW = 130;                       // machine room: left edge and width
const PW = 84, PH = 36, PX_END = 300;           // packet size and final x
const PX_START = MX + MW - PW;                  // packets appear inside the machine
const INPUT_X0 = 4, INPUT_X1 = 52;
const DUR = 2200;                               // ms per input
const P_REST = 0.9;                             // phase shown by the Step button and in the first frame with reduced motion
const BAR_MS = 300;

const clamp01 = (x) => Math.max(0, Math.min(1, x));
const easeOut = (x) => 1 - (1 - clamp01(x)) ** 3;
const num2 = (v) => (v === 0 ? '0' : Number(v).toPrecision(2));

export function mount(container, params = {}, help = {}) {
  injectStyle('vz-qkv-style', CSS);
  const colors = { accent: '#2b6cb0', fg: '#1a1a1a', muted: '#777', bg: '#fff', good: '#2f855a', bad: '#c53030', ...(help.colors || {}) };
  // rule: Q, K, V are told apart by their letters and by swatches beside their names; text never names a colour
  const bcol = { q: colors.accent, k: colors.good, v: colors.fg };
  const reducedMotion = !!help.reducedMotion;
  let scene = params.scene === 'orth' || params.scene === 'make' ? params.scene : 'make';
  let mode = params.mode === 'fused' || params.mode === 'separate' ? params.mode : 'fused';
  let kidx = KSCALES.includes(params.kscale) ? KSCALES.indexOf(params.kscale) : KSCALES.indexOf(1);
  let inputs = 1;
  let phase = reducedMotion ? P_REST : 0;
  let last = 0;
  let cur = null;                                // { fused, separate, diff } for the current input

  const W3 = makeWeights();
  const G3 = makeGrads();
  const ref = orthSizes(G3, 1);
  let ymax = 0;                                  // one fixed bar scale: the largest size at any strength, so a bar never changes scale
  for (const k of KSCALES) { const s = orthSizes(G3, k); ymax = Math.max(ymax, ...s.fused, ...s.separate); }
  ymax *= 1.15;

  const root = el('div', { class: 'vz-qkv' });
  applyColors(root, colors);
  container.append(root);

  // ---- scene buttons
  const sceneBtns = {};
  const sceneGroup = el('div', { class: 'vz-group', role: 'group', 'aria-label': 'Scene' });
  for (const id of ['make', 'orth']) {
    sceneBtns[id] = el('button', { type: 'button', class: 'vz-btn', text: SCENES[id], 'aria-pressed': 'false' });
    sceneBtns[id].addEventListener('click', () => { scene = id; syncAll(); handle.resume(); });
    sceneGroup.append(sceneBtns[id]);
  }
  const controls = el('div', { class: 'vz-controls' }, [sceneGroup]);
  root.append(controls);

  // ================= scene 1
  const makePanel = el('div', { class: 'vz-qkv-make' });
  const modeBtns = {};
  const modeGroup = el('div', { class: 'vz-group', role: 'group', 'aria-label': 'Machines' });
  for (const id of ['fused', 'separate']) {
    modeBtns[id] = el('button', { type: 'button', class: 'vz-btn', text: MODES[id], 'aria-pressed': 'false' });
    modeBtns[id].addEventListener('click', () => { mode = id; restartLine(); handle.resume(); });
    modeGroup.append(modeBtns[id]);
  }
  makePanel.append(el('div', { class: 'vz-controls' }, [modeGroup]));

  const line = svg('svg', {
    class: 'vz-line', viewBox: `0 0 ${W} ${H}`, role: 'img',
    'aria-label': 'An assembly line. One input, a row of four small cells, rides a conveyor into a machine room and comes out as three packets labelled Q, K and V. The room holds either one wide machine or three separate ones.',
  });
  const belts = svg('g', { class: 'belts' });
  const machines = svg('g', { class: 'machines' });
  line.append(belts, machines);

  const CW = 12, CH = 22;                        // input cells
  const inputG = svg('g', { class: 'input' });
  const inputCells = [];
  for (let i = 0; i < QKV.d; i++) {
    const r = svg('rect', { x: i * CW, y: -CH / 2, width: CW, height: CH, fill: colors.bg, stroke: colors.fg, 'stroke-width': 1 });
    const bar = svg('rect', { x: i * CW + 2, y: 0, width: CW - 4, height: 0, fill: colors.fg });
    inputG.append(r, bar); inputCells.push(bar);
  }
  inputG.append(svg('text', { x: 0, y: -CH / 2 - 5, 'font-size': 11, fill: colors.fg, text: 'input' }));
  line.append(inputG);

  const packets = {}, packetBars = {};
  for (const b of BLOCKS) {
    const g = svg('g', { class: `packet ${b}` });
    g.append(svg('rect', { x: 0, y: -PH / 2, width: PW, height: PH, rx: 4, fill: colors.bg, stroke: bcol[b], 'stroke-width': 2.5 }));
    g.append(svg('rect', { x: 0, y: -PH / 2, width: 7, height: PH, fill: bcol[b] }));
    g.append(svg('text', { x: 17, y: 5, 'font-size': 15, 'font-weight': 700, 'text-anchor': 'middle', fill: colors.fg, text: b.toUpperCase() }));
    packetBars[b] = [];
    for (let i = 0; i < QKV.d; i++) {
      const bar = svg('rect', { x: 30 + i * 13, y: 0, width: 9, height: 0, fill: bcol[b] });
      g.append(bar); packetBars[b].push(bar);
    }
    packets[b] = g; line.append(g);
  }
  makePanel.append(line);

  const legend = el('div', { class: 'vz-legend' });
  for (const b of BLOCKS) {
    legend.append(el('span', {}, [el('span', { class: 'vz-sw', style: `background:${bcol[b]}`, 'aria-hidden': 'true' }), `${b.toUpperCase()} = ${WORDS[b]}`]));
  }
  makePanel.append(legend);

  const diffEl = el('b', { id: 'vz-qkv-diff' });
  const opsEl = el('b', { id: 'vz-qkv-ops' });
  makePanel.append(el('div', { class: 'vz-reads' }, [
    el('p', {}, ['This room does: ', opsEl]),
    el('p', {}, ['Largest difference between the fused and the separate outputs for this input: ', diffEl, ' ',
      el('span', { class: 'vz-why', text: '(0, or rounding noise near 1e-16)' })]),
    el('p', { class: 'vz-why', text: 'Same numbers out; the fused one is faster on a GPU because it is one call.' }),
  ]));
  makePanel.append(el('p', { class: 'vz-key', text: 'Each packet shows its four numbers as small bars (up is positive, down is negative). A new input enters about every two seconds.' }));
  root.append(makePanel);

  // ================= scene 2
  const orthPanel = el('div', { class: 'vz-qkv-orth' });
  const slider = el('input', { id: 'vz-qkv-kscale', type: 'range', min: 0, max: KSCALES.length - 1, step: 1 });
  slider.value = String(kidx);
  const out = el('output', { id: 'vz-qkv-kscale-out', for: 'vz-qkv-kscale' });
  slider.addEventListener('input', () => { kidx = Number(slider.value); syncOrth(true); handle.resume(); });
  orthPanel.append(el('div', { class: 'vz-slider' }, [el('label', { for: 'vz-qkv-kscale', text: 'Key gradient strength' }), slider, out]));

  const BW = 400, BH = 230, BASE = 190, TOP = 52;   // bar chart: baseline y and the height of the tallest possible bar
  const BARH = BASE - TOP;
  const bars = svg('svg', {
    class: 'vz-bars', viewBox: `0 0 ${BW} ${BH}`, role: 'img',
    'aria-label': 'Two groups of three bars, Q, K and V, showing the size of the step each block gets after orthogonalising. In the left group the stack is orthogonalised as one matrix; in the right group each block on its own.',
  });
  const barEls = [];                                // { rect, label, how, block, from, to, t0 }
  const groups = [
    { how: 'fused', x0: 14, title: ['Stack orthogonalised', 'as one'], tag: 'ours' },
    { how: 'separate', x0: 214, title: ['Each orthogonalised', 'on its own'], tag: null },
  ];
  for (const gr of groups) {
    const t = svg('text', { x: gr.x0, y: 16, 'font-size': 12, 'font-weight': 700, fill: colors.fg });
    t.append(svg('tspan', { x: gr.x0, text: gr.title[0] }), svg('tspan', { x: gr.x0, dy: 14, text: gr.title[1] }));
    bars.append(t);
    if (gr.tag) {
      bars.append(svg('rect', { x: gr.x0 + 62, y: 18, width: 34, height: 16, rx: 8, fill: 'none', stroke: colors.muted }));
      bars.append(svg('text', { x: gr.x0 + 79, y: 30, 'font-size': 11, 'text-anchor': 'middle', fill: colors.fg, text: gr.tag }));
    }
    bars.append(svg('line', { x1: gr.x0, x2: gr.x0 + 172, y1: BASE, y2: BASE, stroke: colors.muted }));
    BLOCKS.forEach((b, i) => {
      const x = gr.x0 + 10 + i * 56;
      const rect = svg('rect', { class: 'bar', x, y: BASE, width: 40, height: 0, fill: bcol[b], 'data-block': b, 'data-how': gr.how, 'data-size': '0' });
      const refY = BASE - (ref[gr.how][i] / ymax) * BARH;
      const tick = svg('line', { class: 'ref', x1: x - 4, x2: x + 44, y1: refY, y2: refY, stroke: colors.fg, 'stroke-width': 1.5, 'stroke-dasharray': '3 2' });
      const label = svg('text', { x: x + 20, y: BASE - 4, 'font-size': 11, 'text-anchor': 'middle', fill: colors.fg, text: '' });
      bars.append(rect, tick, label,
        svg('text', { x: x + 20, y: BASE + 16, 'font-size': 14, 'font-weight': 700, 'text-anchor': 'middle', fill: colors.fg, text: b.toUpperCase() }));
      barEls.push({ rect, label, how: gr.how, block: b, idx: i, from: 0, to: 0, t0: 0, h: 0 });
    });
  }
  orthPanel.append(bars);
  const legend2 = el('div', { class: 'vz-legend' });
  for (const b of BLOCKS) {
    legend2.append(el('span', {}, [el('span', { class: 'vz-sw', style: `background:${bcol[b]}`, 'aria-hidden': 'true' }), `${b.toUpperCase()} = ${WORDS[b]}`]));
  }
  legend2.append(el('span', {}, ['Dashed tick = size at strength 1']));
  orthPanel.append(legend2);

  const fusedEl = el('span', { id: 'vz-qkv-fused' });
  const sepEl = el('span', { id: 'vz-qkv-sep' });
  const changeEl = el('span', { id: 'vz-qkv-change' });
  orthPanel.append(el('div', { class: 'vz-reads' }, [
    el('p', {}, ['Stacked, step sizes Q, K, V: ', fusedEl]),
    el('p', {}, ['On their own, step sizes Q, K, V: ', sepEl]),
    el('p', {}, [el('b', {}, [changeEl])]),
  ]));
  orthPanel.append(el('p', { class: 'vz-key', text: 'Bar height = the size of the step each block gets (RMS per weight of its orthogonalised gradient). Orthogonalising removes scale, so on its own each block keeps its size. Stacked, one strong block takes the shared budget and squeezes the others; a weak one is starved. Muon\'s shape-based scale factor is left out: the bars compare directions only.' }));
  root.append(orthPanel);

  realNote(root, {
    live: [
      'The three outputs both ways (one 12 × 4 multiplication and three 4 × 4 ones) and their difference, for the input on the line.',
      'Both orthogonalisations: 5 Newton-Schulz steps with Muon\'s coefficients, on the stacked 12 × 4 gradient and on each 4 × 4 block, at the chosen key gradient strength.',
    ],
    measured: [
      'No numbers. Our heads store Q, K and V as one stacked matrix, and a routing check of our heads (2026-10-17) found that our optimizer orthogonalised that stack as one matrix. What that did to training is not measured.',
    ],
    illustrative: [
      'The matrices are random and 4 wide (real blocks are 256 wide), and the gradient strengths are chosen for the picture.',
      'The bars leave out Muon\'s shape-based scale factor, which also differs between a 12 × 4 stack and a 4 × 4 block.',
    ],
  });

  // ---- scene 1 drawing
  function buildMachines() {
    belts.replaceChildren(); machines.replaceChildren();
    const belt = (d) => belts.append(svg('path', { d, fill: 'none', stroke: colors.muted, 'stroke-width': 2, 'stroke-dasharray': '6 4' }));
    if (mode === 'fused') {
      belt(`M0,100H${MX}`);
      const g = svg('g', { class: 'machine' });
      g.append(svg('rect', { class: 'body', x: MX, y: 20, width: MW, height: 160, rx: 8, fill: colors.bg, stroke: colors.fg, 'stroke-width': 2 }));
      g.append(svg('text', { x: MX + MW / 2, y: 40, 'font-size': 11, 'text-anchor': 'middle', fill: colors.fg, text: 'stacked matrix, 12 × 4' }));
      g.append(svg('text', { x: MX + MW / 2, y: 106, 'font-size': 11, 'text-anchor': 'middle', fill: colors.muted, text: 'one call' }));
      machines.append(g);
    } else {
      belt(`M0,100H70M70,100L70,45H${MX}M70,100H${MX}M70,100L70,155H${MX}`);
      for (const y of LANES) {
        const g = svg('g', { class: 'machine' });
        g.append(svg('rect', { class: 'body', x: MX, y: y - 22, width: MW, height: 44, rx: 8, fill: colors.bg, stroke: colors.fg, 'stroke-width': 2 }));
        g.append(svg('text', { x: MX + MW / 2, y: y + 4, 'font-size': 12, 'text-anchor': 'middle', fill: colors.fg, text: '4 × 4' }));
        machines.append(g);
      }
    }
    for (const y of LANES) belts.append(svg('path', { d: `M${MX + MW},${y}H${W - 6}`, fill: 'none', stroke: colors.muted, 'stroke-width': 2, 'stroke-dasharray': '6 4' }));
  }
  function newInput() {
    const x = makeInput(100 + inputs);
    const f = projectFused(W3, x), s = projectSeparate(W3, x);
    cur = { x, out: mode === 'fused' ? f : s, diff: maxAbsDiff(f, s) };
    diffEl.textContent = cur.diff === 0 ? '0' : cur.diff.toExponential(1);
    root.setAttribute('data-inputs', String(inputs));
  }
  const setBars = (bars_, vals) => vals.forEach((v, i) => {
    const h = Math.max(-1, Math.min(1, v / 3)) * 14;
    bars_[i].setAttribute('y', String(h >= 0 ? -h : 0)); bars_[i].setAttribute('height', String(Math.abs(h)));
  });
  function renderLine() {
    const p = phase;
    // input: rides in during 0..0.35, hidden afterwards
    const ti = clamp01(p / 0.35);
    inputG.setAttribute('transform', `translate(${(INPUT_X0 + (INPUT_X1 - INPUT_X0) * easeOut(ti)).toFixed(1)},100)`);
    inputG.setAttribute('visibility', p < 0.36 ? 'visible' : 'hidden');
    setBars(inputCells, cur.x);
    // stamp: the machines flash between 0.35 and 0.5
    const stamp = p >= 0.35 && p < 0.5;
    for (const m of machines.querySelectorAll('.body')) {
      m.setAttribute('stroke-width', stamp ? 5 : 2);
      m.setAttribute('fill-opacity', '1');
    }
    // packets: slide out during 0.5..0.8, then rest
    const tp = easeOut((p - 0.5) / 0.3);
    BLOCKS.forEach((b, i) => {
      const g = packets[b];
      g.setAttribute('transform', `translate(${(PX_START + (PX_END - PX_START) * tp).toFixed(1)},${LANES[i]})`);
      g.setAttribute('visibility', p >= 0.5 ? 'visible' : 'hidden');
      g.setAttribute('opacity', String(clamp01((p - 0.5) / 0.08)));
      setBars(packetBars[b], cur.out[b]);
    });
  }
  function restartLine() {
    inputs = 1; phase = reducedMotion ? P_REST : 0; last = 0;
    buildMachines(); newInput(); syncAll(); renderLine();
  }
  const OPS = {
    fused: '1 multiplication by a 12 × 4 matrix',
    separate: '3 multiplications by 4 × 4 matrices',
  };

  // ---- scene 2 drawing
  const sizesCache = new Map();
  const sizesFor = (i) => { if (!sizesCache.has(i)) sizesCache.set(i, orthSizes(G3, KSCALES[i])); return sizesCache.get(i); };
  function paintBar(b) {
    b.rect.setAttribute('y', (BASE - b.h).toFixed(2));
    b.rect.setAttribute('height', Math.max(0, b.h).toFixed(2));
    b.label.setAttribute('y', String(Math.min(BASE - b.h - 4, BASE - 4).toFixed(2)));
  }
  function syncOrth(animate) {
    const s = sizesFor(kidx);
    const now = performance.now();
    for (const b of barEls) {
      const size = s[b.how][b.idx];
      b.rect.setAttribute('data-size', String(size));
      b.label.textContent = num2(size);
      b.from = b.h; b.to = (size / ymax) * BARH; b.t0 = now;
      if (!animate || reducedMotion) { b.h = b.to; b.from = b.to; }
      paintBar(b);
    }
    barsMoving = animate && !reducedMotion;
    out.textContent = String(KSCALES[kidx]);
    slider.setAttribute('aria-valuetext', `key gradient × ${KSCALES[kidx]}`);
    root.setAttribute('data-kscale', String(KSCALES[kidx]));
    fusedEl.textContent = s.fused.map(num2).join(', ');
    sepEl.textContent = s.separate.map(num2).join(', ');
    const pct = (s.fused[0] / ref.fused[0]) * 100;
    const pctText = pct >= 10 ? String(Math.round(pct)) : pct.toPrecision(2);
    changeEl.textContent = `Stacked: the query step is ${pctText}% of its size at strength 1. On its own: 100%.`;
  }
  let barsMoving = false;
  function stepBars(now) {
    let moving = false;
    for (const b of barEls) {
      const t = (now - b.t0) / BAR_MS;
      b.h = b.from + (b.to - b.from) * easeOut(t);
      if (t < 1) moving = true; else b.h = b.to;
      paintBar(b);
    }
    barsMoving = moving;
    return moving;
  }

  // ---- shared state sync
  function syncAll() {
    root.setAttribute('data-scene', scene);
    root.setAttribute('data-mode', mode);
    for (const [k, b] of Object.entries(sceneBtns)) b.setAttribute('aria-pressed', k === scene ? 'true' : 'false');
    for (const [k, b] of Object.entries(modeBtns)) b.setAttribute('aria-pressed', k === mode ? 'true' : 'false');
    makePanel.hidden = scene !== 'make';
    orthPanel.hidden = scene !== 'orth';
    opsEl.textContent = OPS[mode];
    root.setAttribute('data-inputs', String(inputs));
  }

  function advance({ manual } = {}) {
    if (manual) {                                   // reduced motion: one Step = the next input at its end positions
      if (scene === 'make') { inputs += 1; phase = P_REST; newInput(); renderLine(); }
      return true;
    }
    const now = performance.now();
    if (scene === 'orth') {
      last = 0;
      return stepBars(now) ? true : false;           // idle once the bars have arrived
    }
    const dt = last ? Math.min(100, now - last) : 16;
    last = now;
    phase += dt / DUR;
    if (phase >= 1) { phase -= 1; inputs += 1; newInput(); }
    renderLine();
    return true;
  }

  const handle = loop(root, advance, { reducedMotion, controls });
  buildMachines(); newInput(); syncOrth(false); syncAll(); renderLine();

  return {
    destroy() {
      handle.destroy();
      root.remove();
    },
  };
}
