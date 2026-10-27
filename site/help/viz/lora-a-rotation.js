// Owner: WINTERMUTE (created 2026-10-27)
// Animation module "lora-a-rotation": a rank-1 toy adapter (one row a in A, one column b in B) is trained with fixed-size steps.
// With A's step size x1 the arrow of A hardly turns; with x20 it turns toward the target. Used by the glossary entry "lora-a".
import { ROT, targetA, angleDeg, overlap, lossOf, createRotSim } from './lib/lora-rot.js';
import { svg, el, injectStyle, applyColors, loop, realNote, lineChart } from './lib/kit.js';

const CSS = `
.vz-rot{font:14px/1.45 system-ui,sans-serif;color:var(--vz-fg);background:var(--vz-bg);padding:8px;max-width:100%;box-sizing:border-box}
.vz-rot .vz-controls{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center;margin-bottom:8px}
.vz-rot .vz-group{display:flex;flex-wrap:wrap;gap:4px;align-items:center}
.vz-rot .vz-group-label{font-size:13px;margin-right:2px}
.vz-rot .vz-btn{font:inherit;color:var(--vz-fg);background:transparent;border:1px solid var(--vz-muted);border-radius:4px;padding:3px 9px;cursor:pointer}
.vz-rot .vz-btn[aria-pressed="true"]{background:var(--vz-fg);border-color:var(--vz-accent);color:var(--vz-bg);box-shadow:inset 0 -3px 0 var(--vz-accent)}
.vz-rot .vz-sw{display:inline-block;width:14px;height:0;border-top:3px solid;margin-right:5px;vertical-align:middle}
.vz-rot .vz-panels{display:flex;flex-wrap:wrap;gap:10px}
.vz-rot .vz-panel{flex:1 1 250px;min-width:0}
.vz-rot .vz-panel h4{margin:0 0 3px;font-size:13px}
.vz-rot svg.vz-pan{width:100%;max-width:300px;height:auto;display:block;border:1px solid var(--vz-muted);border-radius:4px}
.vz-rot svg.vz-chart{width:100%;max-width:340px;height:auto;display:block;margin-top:6px}
.vz-rot .vz-key{font-size:12px;color:var(--vz-muted);margin:6px 0}
.vz-rot .vz-reads{margin:6px 0;font-size:13px}
.vz-rot .vz-reads p{margin:2px 0}
.vz-rot .vz-reads b{font-variant-numeric:tabular-nums}
.vz-rot .vz-charthead{font-size:13px;margin:8px 0 0;display:flex;flex-wrap:wrap;gap:2px 14px}
.vz-rot .vz-real{margin-top:10px;border-top:1px solid var(--vz-muted);padding-top:6px;font-size:13px}
.vz-rot .vz-real h4{margin:0 0 4px;font-size:13px}
.vz-rot .vz-real dt{font-weight:600;margin-top:4px}
.vz-rot .vz-real dd{margin:0}
.vz-rot .vz-real p{margin:2px 0}
`;

const S = 200, C = S / 2;                 // each panel is a 200 x 200 square, origin in the middle
const PX = { a: 26, b: 80 };              // pixels per unit: |a| ~ 3 and |b| <= 1 both fit with a margin
const MULTS = [1, 20];
const STEPS_MANUAL = 25;
const fx = (k, v) => (C + v[0] * PX[k]).toFixed(1);
const fy = (k, v) => (C - v[1] * PX[k]).toFixed(1);
const pt = (k, v) => `${fx(k, v)},${fy(k, v)}`;

export function mount(container, params = {}, help = {}) {
  injectStyle('vz-rot-style', CSS);
  const colors = { accent: '#2b6cb0', fg: '#1a1a1a', muted: '#777', bg: '#fff', good: '#2f855a', bad: '#c53030', ...(help.colors || {}) };
  const reducedMotion = !!help.reducedMotion;
  let mult = MULTS.includes(params.mult) ? params.mult : 1;
  let sim = null;
  const runs = {};                         // mult -> losses of a finished run, for the faint comparison line
  const seriesColor = { 1: colors.accent, 20: colors.good };

  const root = el('div', { class: 'vz-rot' });
  applyColors(root, colors);
  container.append(root);

  // ---- controls
  const swatch = (c) => el('span', { class: 'vz-sw', style: `border-top-color:${c}`, 'aria-hidden': 'true' });
  const multBtns = {};
  const multGroup = el('div', { class: 'vz-group', role: 'group', 'aria-label': "A's step size" }, [el('span', { class: 'vz-group-label', 'aria-hidden': 'true', text: "A's step size" })]);
  for (const m of MULTS) {
    multBtns[m] = el('button', { type: 'button', class: 'vz-btn', 'aria-pressed': 'false' }, [swatch(seriesColor[m]), `×${m}`]);
    multBtns[m].addEventListener('click', () => { mult = m; restart(); });
    multGroup.append(multBtns[m]);
  }
  const replay = el('button', { type: 'button', class: 'vz-btn', text: 'Replay' });
  replay.addEventListener('click', () => restart());
  const controls = el('div', { class: 'vz-controls' }, [multGroup, replay]);
  root.append(controls);

  // ---- the two panels
  const panels = {};
  const row = el('div', { class: 'vz-panels' });
  const target = targetA(), bT = ROT.bTarget;
  const tdir = { a: target, b: bT };
  const tlen = { a: 3.3, b: 1.1 };
  for (const [k, title, desc] of [['a', 'A (reads the input)', 'The row of A as an arrow'], ['b', 'B (writes the correction)', 'The column of B as an arrow']]) {
    const board = svg('svg', {
      class: `vz-pan vz-rot-${k}`, viewBox: `0 0 ${S} ${S}`, role: 'img',
      'aria-label': `${desc} in a plane, with a thin trail of where its tip has been and a dashed line for the target direction.`,
    });
    board.append(svg('defs', {}, [svg('marker', { id: `vz-rot-ah-${k}`, viewBox: '0 0 10 10', refX: 8, refY: 5, markerWidth: 5, markerHeight: 5, orient: 'auto-start-reverse', markerUnits: 'strokeWidth' },
      [svg('path', { d: 'M0,0 L10,5 L0,10 z', fill: colors.fg })])]));
    board.append(svg('path', { d: `M4,${C}H${S - 4}M${C},4V${S - 4}`, stroke: colors.muted, 'stroke-opacity': 0.3 }));
    const d = tdir[k], L = tlen[k];
    board.append(svg('line', {
      class: 'target', stroke: colors.muted, 'stroke-width': 1.6, 'stroke-dasharray': '5 4',
      x1: fx(k, [-d[0] * L, -d[1] * L]), y1: fy(k, [-d[0] * L, -d[1] * L]), x2: fx(k, [d[0] * L, d[1] * L]), y2: fy(k, [d[0] * L, d[1] * L]),
    }));
    board.append(svg('text', {
      class: 'target-label', 'font-size': 8, fill: colors.muted, 'text-anchor': 'start',
      x: (C - d[0] * L * PX[k] * 0.95 + 9).toFixed(1), y: (C + d[1] * L * PX[k] * 0.95 - 2).toFixed(1), text: 'target direction',
    }));
    const trail = svg('polyline', { class: 'trail', fill: 'none', stroke: colors.fg, 'stroke-opacity': 0.5, 'stroke-width': 1.2, 'stroke-linejoin': 'round', points: '' });
    board.append(trail);
    let early = null;
    if (k === 'a') {
      early = svg('g', { class: 'early', visibility: 'hidden' }, [
        svg('circle', { r: 3, fill: colors.bg, stroke: colors.fg, 'stroke-width': 1.2 }),
        svg('text', { class: 'early-label', 'font-size': 8, fill: colors.muted, x: 5, y: -4, text: `step ${ROT.early}` }),
      ]);
      board.append(early);
    }
    const arrow = svg('line', { class: 'arrow', stroke: colors.fg, 'stroke-width': 2, 'marker-end': `url(#vz-rot-ah-${k})`, x1: C, y1: C, x2: C, y2: C });
    board.append(arrow);
    panels[k] = { board, trail, arrow, early };
    row.append(el('div', { class: 'vz-panel' }, [el('h4', { text: title }), board]));
  }
  root.append(row);
  root.append(el('p', { class: 'vz-key', text: 'Bold arrow: the vector now. Thin line: where its tip has been. Dashed line: the direction that would give the target change. A starts long (3) and B starts at zero.' }));

  // ---- readouts
  const stepEl = el('b', { id: 'vz-rot-step' });
  const turnEl = el('b', { id: 'vz-rot-turn' });
  const ovEl = el('b', { id: 'vz-rot-overlap' });
  const ovNote = el('span', { class: 'vz-why' });
  const lossEl = el('b', { id: 'vz-rot-loss' });
  const baEl = el('b', { id: 'vz-rot-ba' });
  root.append(el('div', { class: 'vz-reads' }, [
    el('p', {}, ['Step ', stepEl]),
    el('p', {}, ['A has turned ', turnEl]),
    el('p', {}, [`A's direction since step ${ROT.early}: `, ovEl, ' unchanged ', ovNote]),
    el('p', {}, ['Loss left: ', lossEl]),
    el('p', {}, ['Size of B·A: ', baEl, ' (target 1)']),
    el('p', { class: 'vz-key', text: 'In our run: A 99.2% unchanged, B 35%. With A\'s step × 20, A turned, but B·A grew 2.3 times and one render failed.' }),
  ]));

  // ---- loss chart
  const CW = 320;
  root.append(el('div', { class: 'vz-charthead' }, [
    el('span', {}, ['Loss over steps']),
    ...MULTS.map((m) => el('span', {}, [swatch(seriesColor[m]), `×${m}`])),
  ]));
  const chart = lineChart(root, {
    width: CW, height: 150, series: MULTS.map((m) => ({ key: `m${m}`, color: seriesColor[m] })),
    xMax: ROT.steps, yMin: 0, yMax: 1, yTicks: [0, 0.5, 1], xLabel: 'training step', yLabel: 'loss', fg: colors.fg, muted: colors.muted,
  });
  chart.el.querySelectorAll('text').forEach((t) => t.setAttribute('font-size', '11'));
  const chartLines = chart.el.querySelectorAll('polyline');

  realNote(root, {
    live: [
      'A toy adapter with one row in A and one column in B, trained live with fixed-size steps (each step is normalised to the same length, as Muon-family steps are for a single row or column). A is large at the start and B is zero, as in our adapters.',
    ],
    measured: [
      'On one DoRA run, A\'s input directions were 99.2% unchanged between steps 240 and 1,440, against 35% for B. A took about 7% of the step energy.',
      'With A\'s step 20 times larger, A turned, but the adapter\'s product grew 2.3 times and one render failed, so that result is not clean. We have no AdamW comparison, and an imbalance between A and B is known for AdamW too (LoRA+).',
    ],
    illustrative: [
      'The toy is 2-D with rank 1; its numbers are not our run\'s.',
      'In the toy B\'s direction is set by its first step, so it shows B growing, not turning.',
      'The toy\'s ×20 run does not grow too large or fail.',
    ],
  });

  // ---- drawing
  const setArrow = (k, v) => {
    panels[k].arrow.setAttribute('x2', fx(k, v)); panels[k].arrow.setAttribute('y2', fy(k, v));
  };
  function render() {
    const a = sim.a, b = sim.b;
    setArrow('a', a); setArrow('b', b);
    panels.a.arrow.setAttribute('data-angle', String(angleDeg(a)));
    panels.a.trail.setAttribute('points', sim.trail.a.map((p) => pt('a', p)).join(' '));
    panels.b.trail.setAttribute('points', sim.trail.b.map((p) => pt('b', p)).join(' '));
    const ea = sim.aEarly;
    if (ea) {
      panels.a.early.setAttribute('transform', `translate(${fx('a', ea)} ${fy('a', ea)})`);
      const lab = panels.a.early.querySelector('.early-label'), right = Number(fx('a', ea)) > S - 60;
      lab.setAttribute('text-anchor', right ? 'end' : 'start'); lab.setAttribute('x', right ? -5 : 5); lab.setAttribute('y', right ? 12 : -4);
      panels.a.early.setAttribute('visibility', 'visible');
    } else panels.a.early.setAttribute('visibility', 'hidden');
    stepEl.textContent = `${sim.t} of ${ROT.steps}`;
    turnEl.textContent = `${Math.abs(angleDeg(a) - angleDeg(ROT.aStart)).toFixed(1)}°`;
    if (ea) { ovEl.textContent = `${(100 * overlap(a, ea)).toFixed(1)}%`; ovNote.textContent = ''; }
    else { ovEl.textContent = '–'; ovNote.textContent = `(measured from step ${ROT.early})`; }
    lossEl.textContent = lossOf(a, b).toFixed(3);
    baEl.textContent = (Math.hypot(...a) * Math.hypot(...b)).toFixed(2);
    root.setAttribute('data-step', String(sim.t));
  }
  function pushChart() {
    const i = sim.t, other = runs[mult === 1 ? 20 : 1];
    chart.push({ [`m${mult}`]: sim.losses[i], [`m${mult === 1 ? 20 : 1}`]: other ? other[i] : 0 });
  }
  function syncControls() {
    for (const m of MULTS) multBtns[m].setAttribute('aria-pressed', m === mult ? 'true' : 'false');
    root.setAttribute('data-mult', String(mult));
    const other = runs[mult === 1 ? 20 : 1];
    MULTS.forEach((m, i) => {
      chartLines[i].setAttribute('stroke-opacity', m === mult ? 1 : 0.35);
      chartLines[i].setAttribute('visibility', m === mult || other ? 'visible' : 'hidden');
    });
  }
  function restart() {
    sim = createRotSim({ mult });
    chart.clear();
    syncControls();
    pushChart();
    render();
    handle.resume();
  }
  function advance(manual) {
    const n = manual ? STEPS_MANUAL : 1;
    for (let i = 0; i < n && !sim.done; i++) { sim.step(); pushChart(); }
    if (sim.done) runs[mult] = sim.losses.slice();
    render();
    return !sim.done;
  }

  const handle = loop(root, ({ manual }) => advance(manual), { reducedMotion, controls });
  restart();

  return {
    destroy() {
      handle.destroy();
      root.remove();
    },
  };
}
