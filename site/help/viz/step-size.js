// Owner: WINTERMUTE (created 2026-10-26)
// Animation module "step-size": AdamW (left) and Muon (right) on the same gradients; wire thickness = size of the step.
import { survivesUpdate, ulp, DTYPES } from './lib/optim.js';
import { CALIBRATION } from './lib/noise.js';
import { createSim, SCENARIOS, STEP_AT, TOTAL_STEPS, LR, WEIGHT_RMS } from './lib/step-sim.js';
import { svg, el, injectStyle, applyColors, loop, realNote, lineChart } from './lib/kit.js';

const CSS = `
.vz-step{font:14px/1.45 system-ui,sans-serif;color:var(--vz-fg);background:var(--vz-bg);padding:8px;max-width:100%}
.vz-step .vz-controls{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center;margin-bottom:8px}
.vz-step .vz-group{display:flex;flex-wrap:wrap;gap:4px;align-items:center}
.vz-step .vz-btn{font:inherit;color:var(--vz-fg);background:transparent;border:1px solid var(--vz-muted);border-radius:4px;padding:3px 9px;cursor:pointer}
.vz-step .vz-btn[aria-pressed="true"]{background:var(--vz-accent);border-color:var(--vz-accent);color:var(--vz-bg)}
.vz-step select{font:inherit;color:var(--vz-fg);background:var(--vz-bg);border:1px solid var(--vz-muted);border-radius:4px;padding:2px 4px}
.vz-step .vz-panels{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px}
.vz-step .vz-panel h4{margin:0 0 2px;font-size:14px}
.vz-step .vz-panel svg,.vz-step .vz-chart{width:100%;height:auto;display:block}
.vz-step .vz-read{margin:2px 0 0;font-size:13px;color:var(--vz-muted)}
.vz-step .vz-read b{color:var(--vz-fg)}
.vz-step .vz-key{font-size:12px;color:var(--vz-muted);margin:6px 0}
.vz-step .vz-real{margin-top:10px;border-top:1px solid var(--vz-muted);padding-top:6px;font-size:13px}
.vz-step .vz-real h4{margin:0 0 4px;font-size:13px}
.vz-step .vz-real dt{font-weight:600;margin-top:4px}
.vz-step .vz-real dd{margin:0}
.vz-step .vz-real p{margin:2px 0}
`;

const SCENARIO_HELP = {
  steady: 'The gradient keeps its size; the noise is what an early run has.',
  noisy: 'The gradient keeps its size; the noise is what a late run has, so most of each gradient is noise.',
  drop: `At step ${STEP_AT} every gradient becomes 100 times smaller.`,
  rise: `At step ${STEP_AT} every gradient becomes 100 times larger.`,
};
const PRECISIONS = ['fp32', 'bf16', 'fp16', 'fp8e4m3'];
const COLS = 4, ROWS = 4;
const STEPS_PER_FRAME = 2, STEPS_PER_CLICK = 10;
const MAX_WIDTH = 9;

export function mount(container, params = {}, help = {}) {
  injectStyle('vz-step-style', CSS);
  const colors = { accent: '#2b6cb0', fg: '#1a1a1a', muted: '#777', bg: '#fff', good: '#2f855a', bad: '#c53030', ...(help.colors || {}) };
  const reducedMotion = !!help.reducedMotion;
  let scenario = SCENARIOS[params.scenario] ? params.scenario : 'noisy';
  let dtype = PRECISIONS.includes(params.precision) ? params.precision : 'fp32';
  let sim = createSim(scenario);
  let last = null;

  const root = el('div', { class: 'vz-step' });
  applyColors(root, colors);
  container.append(root);

  // ---- controls
  const scenBtns = {};
  const scenGroup = el('div', { class: 'vz-group', role: 'group', 'aria-label': 'Scenario' });
  for (const id of Object.keys(SCENARIOS)) {
    scenBtns[id] = el('button', { type: 'button', class: 'vz-btn', text: SCENARIOS[id].label, 'aria-pressed': 'false' });
    scenBtns[id].addEventListener('click', () => setScenario(id));
    scenGroup.append(scenBtns[id]);
  }
  const precSelect = el('select', { id: 'vz-step-prec', 'aria-label': 'Number format the weights are stored in' },
    PRECISIONS.map((p) => el('option', { value: p, text: DTYPES[p].label })));
  precSelect.value = dtype;
  precSelect.addEventListener('change', () => { dtype = precSelect.value; if (last) render(last); updateKey(); });
  const replay = el('button', { type: 'button', class: 'vz-btn', text: 'Replay' });
  replay.addEventListener('click', () => setScenario(scenario));
  const controls = el('div', { class: 'vz-controls' }, [
    scenGroup,
    el('label', { for: 'vz-step-prec' }, ['Number format of the weights: ']),
    precSelect, replay,
  ]);
  const status = el('p', { class: 'vz-key', 'aria-live': 'polite' });
  root.append(controls, status);

  // ---- two networks
  function makePanel(title, color) {
    const W = 220, H = 150, xi = 34, xo = 186;
    const yAt = (k) => 22 + k * 36;
    const s = svg('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': `${title}: wires between four inputs and four outputs, thickness is the size of the step` });
    const base = [], wires = [];
    for (let i = 0; i < ROWS; i++) for (let j = 0; j < COLS; j++) {
      const geo = { x1: xi, y1: yAt(j), x2: xo, y2: yAt(i) };
      base.push(svg('line', { ...geo, stroke: colors.muted, 'stroke-opacity': 0.25, 'stroke-width': 0.6 }));
      wires.push(svg('line', { ...geo, class: 'wire', 'data-i': i, 'data-j': j, 'data-lost': '0', stroke: color, 'stroke-linecap': 'round', 'stroke-width': 0 }));
    }
    s.append(...base, ...wires);
    for (let k = 0; k < 4; k++) {
      s.append(svg('circle', { cx: xi, cy: yAt(k), r: 7, fill: colors.bg, stroke: colors.fg, 'stroke-width': 1.5 }));
      s.append(svg('circle', { cx: xo, cy: yAt(k), r: 7, fill: colors.bg, stroke: colors.fg, 'stroke-width': 1.5 }));
    }
    const read = el('p', { class: 'vz-read' });
    const panel = el('div', { class: 'vz-panel' }, [el('h4', { text: title }), s, read]);
    return { panel, wires, read };
  }
  const adamP = makePanel('AdamW', colors.accent);
  const muonP = makePanel('Muon', colors.good);
  const panels = el('div', { class: 'vz-panels' }, [adamP.panel, muonP.panel]);
  root.append(panels);

  const key = el('p', { class: 'vz-key' });
  root.append(key);

  // ---- chart
  const chartBox = el('div');
  root.append(el('h4', { text: 'Typical step per weight, over time', style: 'margin:8px 0 2px;font-size:14px' }), chartBox);
  const chart = lineChart(chartBox, {
    series: [{ key: 'adam', color: colors.accent }, { key: 'muon', color: colors.good }],
    xMax: TOTAL_STEPS, yMin: 0.003, yMax: 3, yLog: true, yTicks: [0.01, 0.1, 1],
    xLabel: 'training steps (blue AdamW, green Muon)', yLabel: 'fraction of learning rate', fg: colors.fg, muted: colors.muted,
  });
  root.append(el('p', { class: 'vz-key', text: 'A step of 1 means the weight moves by the full learning rate; the scale is logarithmic.' }));

  realNote(root, {
    live: [
      'Both optimisers run on the same stream of gradients: the real AdamW update and the real Muon update (five Newton-Schulz iterations), recomputed every step.',
      'Which wires are greyed is computed by rounding the weight and the weight plus the step to the chosen number format.',
    ],
    measured: [
      `The two noise levels are set so that two half batches of 32 examples agree as often as in our runs: a cosine of ${CALIBRATION.early} early in training and ${CALIBRATION.late} late (${CALIBRATION.source}). It is one number for the whole run, applied here to every weight.`,
      'Steady has less noise than our runs, so AdamW sits nearer a full sign step (about 0.6 x the learning rate); the 0.2 to 0.4 the guide measured is what Noisy shows.',
      `The learning rate, ${LR}, is the best AdamW setting for our heads (Muon survival guide, section 4).`,
    ],
    illustrative: [
      `The network is only ${ROWS} by ${COLS}; real matrices are hundreds wide. Muon's update is scaled so that its average (RMS) step is about 0.2 x the learning rate, the level the guide measured for AdamW under noise. On a toy 4 by 4 matrix the per-weight values differ from real 256-wide matrices, so compare the shapes of the curves, not the exact numbers.`,
      `The weights are random numbers of typical size ${WEIGHT_RMS} and do not change while the animation runs; the gradients are made up (a fixed pattern plus noise).`,
    ],
  });

  // ---- drawing
  const widthFor = (u) => Math.min(MAX_WIDTH, 8 * Math.abs(u) / sim.lr);
  function paint(p, update) {
    let kept = 0;
    p.wires.forEach((w, n) => {
      const i = Math.floor(n / COLS), j = n % COLS;
      const ok = survivesUpdate(sim.W[i][j], update[i][j], dtype);
      if (ok) kept++;
      w.setAttribute('stroke-width', widthFor(update[i][j]).toFixed(2));
      w.setAttribute('data-lost', ok ? '0' : '1');
      w.setAttribute('stroke-opacity', ok ? 1 : 0.35);
      w.setAttribute('stroke-dasharray', ok ? '' : '2 3');
      w.setAttribute('stroke', ok ? p.color : colors.muted);
    });
    return kept;
  }
  adamP.color = colors.accent; muonP.color = colors.good;
  function render(f) {
    const n = ROWS * COLS;
    const ka = paint(adamP, f.adamUpdate), km = paint(muonP, f.muonUpdate);
    adamP.read.replaceChildren('Typical step: ', el('b', { text: f.adamMean.toFixed(2) }), ` x learning rate. Steps that survive rounding: ${ka} of ${n}.`);
    muonP.read.replaceChildren('Typical step: ', el('b', { text: f.muonMean.toFixed(2) }), ` x learning rate. Steps that survive rounding: ${km} of ${n}.`);
    root.setAttribute('data-step', String(f.t));
  }
  function updateKey() {
    const half = ulp(WEIGHT_RMS, dtype) / 2;
    key.textContent = `Greyed, dashed wires: the step is smaller than half the gap between numbers the format can store near a weight of size ${WEIGHT_RMS} (${half.toExponential(1)}), so storing the new weight changes nothing.`;
  }
  function setScenario(id) {
    scenario = id;
    sim = createSim(id);
    last = null;
    chart.clear();
    chart.setMarker(id === 'drop' || id === 'rise' ? STEP_AT : null);
    for (const [k, b] of Object.entries(scenBtns)) b.setAttribute('aria-pressed', k === id ? 'true' : 'false');
    status.textContent = `${SCENARIOS[id].label}: ${SCENARIO_HELP[id]}`;
    root.setAttribute('data-scenario', id);
    root.setAttribute('data-step', '0');
    handle.resume();
  }
  function advance(n) {
    for (let k = 0; k < n && !sim.done; k++) {
      last = sim.step();
      chart.push({ adam: last.adamMean, muon: last.muonMean });
    }
    if (last) render(last);
    return !sim.done;
  }

  const handle = loop(root, ({ manual }) => advance(manual ? STEPS_PER_CLICK : STEPS_PER_FRAME), { reducedMotion, controls });
  updateKey();
  setScenario(scenario);
  if (reducedMotion) advance(1);   // start still, but show a first frame

  return {
    destroy() {
      handle.destroy();
      chart.destroy();
      root.remove();
    },
  };
}
