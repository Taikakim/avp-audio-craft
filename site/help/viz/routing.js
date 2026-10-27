// Owner: WINTERMUTE (created 2026-10-27)
// Animation module "routing": our optimizer sends each parameter to a group by its NAME. Shows the real rules (lib/routing.js, a port
// of the trainer's routing.py) applied to the real parameter names of one of our heads, and again to the names the rules expect.
// Used by the glossary entries "adaln" and "parameter-group".
import {
  ROWS, GROUPS, rowRouting, differingRows, summary, renamed,
} from './lib/routing.js';
import { svg, el, injectStyle, applyColors, loop, realNote } from './lib/kit.js';

const CSS = `
.vz-route{font:14px/1.45 system-ui,sans-serif;color:var(--vz-fg);background:var(--vz-bg);padding:8px;max-width:100%;box-sizing:border-box;container-type:inline-size}
.vz-route [hidden]{display:none!important}
.vz-route .vz-controls{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center;margin-bottom:8px}
.vz-route .vz-group{display:flex;flex-wrap:wrap;gap:4px;align-items:center}
.vz-route .vz-btn{font:inherit;color:var(--vz-fg);background:transparent;border:1px solid var(--vz-muted);border-radius:4px;padding:3px 9px;cursor:pointer}
.vz-route .vz-btn[aria-pressed="true"]{background:var(--vz-fg);border-color:var(--vz-accent);color:var(--vz-bg);box-shadow:inset 0 -3px 0 var(--vz-accent)}
.vz-route .vz-head{font-size:12px;color:var(--vz-muted);margin:0 0 6px}
.vz-route .vz-route-body{display:grid;grid-template-columns:minmax(0,1fr) 120px 190px;align-items:stretch}
.vz-route ul.vz-route-rows{list-style:none;margin:0;padding:0}
.vz-route ul.vz-route-rows li{margin:0 0 4px}
.vz-route .vz-route-row{display:block;width:100%;box-sizing:border-box;min-height:44px;text-align:left;font:inherit;font-size:13px;line-height:1.3;color:var(--vz-fg);background:transparent;border:1px solid var(--vz-muted);border-left-width:5px;border-radius:4px;padding:4px 8px;cursor:pointer}
.vz-route .vz-route-row[aria-pressed="true"]{background:var(--vz-fg);color:var(--vz-bg);border-color:var(--vz-accent)}
.vz-route .vz-route-row:focus-visible{outline:2px solid var(--vz-accent);outline-offset:1px}
.vz-route .vz-rb{display:inline-block;margin-left:6px;font-size:11px;font-weight:600;border:1px solid currentColor;border-radius:8px;padding:0 6px;white-space:nowrap}
.vz-route .vz-rm{display:block;font-size:11px;opacity:.8}
.vz-route .vz-gutter{position:relative;min-width:0}
.vz-route svg.vz-route-wires{position:absolute;left:0;top:0;width:100%;height:100%;overflow:visible;pointer-events:none}
.vz-route .vz-stations{display:flex;flex-direction:column;justify-content:space-around;gap:8px;min-width:0}
.vz-route .vz-station{border:1px solid var(--vz-muted);border-radius:6px;padding:8px;min-height:84px;display:flex;flex-direction:column;justify-content:center;gap:2px}
.vz-route .vz-station b{font-size:13px}
.vz-route .vz-station .vz-sc{font-size:12px;color:var(--vz-muted)}
.vz-route .vz-sw{display:inline-block;width:12px;height:12px;border:1px solid var(--vz-muted);margin-right:6px;vertical-align:-1px}
.vz-route .vz-reads{margin:8px 0;font-size:13px}
.vz-route .vz-reads p{margin:2px 0}
.vz-route #vz-route-detail{border:1px solid var(--vz-muted);border-radius:4px;padding:6px 8px;min-height:3em;font-size:13px}
.vz-route #vz-route-detail h4{margin:0 0 4px;font-size:13px}
.vz-route #vz-route-detail p{margin:3px 0}
.vz-route #vz-route-detail code{font-size:12px;overflow-wrap:anywhere}
.vz-route .vz-key{font-size:12px;color:var(--vz-muted);margin:6px 0}
.vz-route .vz-real{margin-top:10px;border-top:1px solid var(--vz-muted);padding-top:6px;font-size:13px}
.vz-route .vz-real h4{margin:0 0 4px;font-size:13px}
.vz-route .vz-real dt{font-weight:600;margin-top:4px}
.vz-route .vz-real dd{margin:0}
.vz-route .vz-real p{margin:2px 0}
@container (max-width:520px){
  .vz-route .vz-route-body{grid-template-columns:minmax(0,1fr) 52px 112px}
  .vz-route .vz-station{padding:6px;min-height:76px}
  .vz-route .vz-station b{font-size:12px}
}
`;

const STATION = {
  spectral: 'Muon (orthogonalised)',
  sign: 'Sign step',
  colnorm: 'Column normalisation',
};
const SHORT = { spectral: 'Muon', sign: 'Sign step', colnorm: 'Column normalisation' };
const VIEWS = { ours: "Our head's names", expected: 'Names the rules expect' };
// the name patterns as the table shows them (N = block number)
const PATTERN = {
  input: ['latent_proj.weight'],
  time1: ['t_embedder.mlp.0.weight'],
  time2: ['t_embedder.mlp.2.weight'],
  adaln: ['blocks.N.adaLN_mod.1.weight'],
  qkv: ['blocks.N.attn.qkv.weight'],
  'attn-out': ['blocks.N.attn.proj.weight'],
  'mlp-up': ['blocks.N.mlp.0.weight'],
  'mlp-down': ['blocks.N.mlp.2.weight'],
  biases: ['every 1-D *.bias except norm_final.bias'],
  'final-norm': ['norm_final.weight', 'norm_final.bias'],
  output: ['out_proj.weight'],
};
const NOTES = {
  qkv: 'The rule splits a stacked attention matrix only if its name contains `to_qkv` (or `to_kv`, `to_q`), and it needs an output projection named `to_out` to know the width. Ours are called `qkv` and `proj`, so Q, K and V were orthogonalised as one matrix. When the rule does split, our optimizer keeps the whole stack\'s scale factor (the square root of 3) for each block, so the split would make each block\'s step about 1.7 times larger as well as change its direction (see the QKV entry).',
  adaln: 'The rule sends AdaLN emitters to the sign step and splits them into their 6 pieces (shift, scale and gate, twice), but only if the name contains `modulation`. Ours is `adaLN_mod`, so it went to Muon whole. The guide\'s view that it should be split is reasoning, not a tested result.',
  time: 'Any 2-D name containing `embed` goes to column normalisation, the rule for input embedding tables. These are ordinary hidden layers that process the noise level; the rename `time_mlp` is our reading of what they should be.',
  input: 'Routed to Muon in both views. The Muon post sends embeddings to the second optimizer; whether an input projection counts as one is our reading (guide section 3).',
  oneD: '1-D parameters always take the sign step, which moves each one by the full learning rate: 16 times more per step than a 256-wide matrix (guide section 4).',
  output: 'A 1 x 256 matrix: too narrow for Muon (fewer than 64 rows), so it takes the sign step, scaled by 1/sqrt(256).',
  other: 'An ordinary hidden matrix: Muon, as intended.',
};
const noteFor = (id) => ({
  qkv: NOTES.qkv, adaln: NOTES.adaln, time1: NOTES.time, time2: NOTES.time, input: NOTES.input,
  biases: NOTES.oneD, 'final-norm': NOTES.oneD, output: NOTES.output,
}[id] || NOTES.other);
const LANE_LABELS = { 3: ['Q', 'K', 'V'], 6: ['1', '2', '3', '4', '5', '6'] };
const PIECES = 'shift, scale, gate, shift, scale, gate';

const DUR = 2600;                                // ms for one dot to cross the wire
const EASE_MS = 130;                             // time constant of the wire re-routing (settles in about 400 ms)
const T0 = 0.35;                                 // dots travel the wire from this fraction on; the labels sit before it
const STEP_LO = 3e-4, STEP_HI = 1e-2;            // one fixed log scale for the update-dot size, whole diagram
const R_LO = 2, R_HI = 5.5;
const clamp01 = (x) => Math.max(0, Math.min(1, x));
const frac = (x) => x - Math.floor(x);
const fmtStep = (v) => (v * (1 + 1e-9)).toExponential(1);
const rOf = (step) => R_LO + (R_HI - R_LO) * clamp01(Math.log(step / STEP_LO) / Math.log(STEP_HI / STEP_LO));

export function mount(container, params = {}, help = {}) {
  injectStyle('vz-route-style', CSS);
  const colors = { accent: '#2b6cb0', fg: '#1a1a1a', muted: '#777', bg: '#fff', good: '#2f855a', bad: '#c53030', ...(help.colors || {}) };
  // rule: stations are told apart by their name text and a swatch; text never names a colour
  const gcol = { spectral: colors.accent, sign: colors.good, colnorm: colors.fg };
  const reducedMotion = !!help.reducedMotion;
  const ids = ROWS.map((r) => r.id);
  let view = params.view === 'expected' || params.view === 'ours' ? params.view : 'ours';
  let selected = ids.includes(params.row) ? params.row : '';
  let phase = reducedMotion ? 0.5 : 0;
  let tick = 0;
  let last = 0;

  const routing = { ours: rowRouting('ours'), expected: rowRouting('expected') };
  const counts = { ours: summary('ours'), expected: summary('expected') };
  const differs = new Set(differingRows());
  const maxLanes = (id) => (id === 'adaln' ? 6 : id === 'qkv' ? 3 : 1);

  const root = el('div', { class: 'vz-route' });
  applyColors(root, colors);
  container.append(root);

  // ---- controls
  const viewBtns = {};
  const viewGroup = el('div', { class: 'vz-group', role: 'group', 'aria-label': 'Names' });
  for (const id of ['ours', 'expected']) {
    viewBtns[id] = el('button', { type: 'button', class: 'vz-btn', text: VIEWS[id], 'aria-pressed': 'false' });
    viewBtns[id].addEventListener('click', () => { setView(id); handle.resume(); });
    viewGroup.append(viewBtns[id]);
  }
  const controls = el('div', { class: 'vz-controls' }, [viewGroup]);
  root.append(controls);
  root.append(el('p', { class: 'vz-head', text: 'One of our heads: width 256, 2 blocks. One block is drawn; the rows marked with N exist in both (× 2). Input at the top, output at the bottom.' }));

  // ---- rows | wires | stations
  const body = el('div', { class: 'vz-route-body' });
  const list = el('ul', { class: 'vz-route-rows' });
  const rowBtn = {}, rowMeta = {};
  for (const r of ROWS) {
    const b = el('button', { type: 'button', class: 'vz-route-row', 'data-row': r.id, 'aria-pressed': 'false' });
    const meta = el('span', { class: 'vz-rm' });
    const badge = differs.has(r.id) ? el('span', { class: 'vz-rb', text: 'differs' }) : null;
    b.append(el('span', { class: 'vz-rl', text: r.label }));
    if (badge) b.append(badge);
    b.append(meta);
    b.addEventListener('click', () => select(r.id));
    b.addEventListener('focus', () => select(r.id));
    rowBtn[r.id] = b; rowMeta[r.id] = meta;
    list.append(el('li', {}, [b]));
  }
  const gutter = el('div', { class: 'vz-gutter' });
  const wires = svg('svg', { class: 'vz-route-wires', 'aria-hidden': 'true', width: 52, height: 100, viewBox: '0 0 52 100' });
  gutter.append(wires);
  const stationsBox = el('div', { class: 'vz-stations' });
  const stationEl = {}, countEl = {};
  for (const g of GROUPS) {
    countEl[g] = el('span', { class: 'vz-sc' });
    const s = el('div', { class: 'vz-station', 'data-group': g }, [
      el('b', {}, [el('span', { class: 'vz-sw', style: `background:${gcol[g]}`, 'aria-hidden': 'true' }), STATION[g]]),
      countEl[g],
    ]);
    stationEl[g] = s; stationsBox.append(s);
  }
  body.append(list, gutter, stationsBox);
  root.append(body);

  // ---- wires: one path per row, dots per lane
  const wire = {};                                // id -> { path, lanes: [{grad, upd, label}], cur, tgt, y0 }
  for (const r of ROWS) {
    const path = svg('path', { class: 'wire', 'data-row': r.id, fill: 'none', 'stroke-width': 1.5 });
    wires.append(path);
    wire[r.id] = { path, lanes: [], cur: null, tgt: 0, y0: 0, w: 52 };
  }
  for (const r of ROWS) {
    const w = wire[r.id];
    for (let k = 0; k < maxLanes(r.id); k++) {
      const grad = svg('circle', { class: 'grad', 'data-row': r.id, r: 2.5 });
      const upd = svg('circle', { class: 'upd', 'data-row': r.id, r: 3 });
      const label = svg('text', { 'font-size': 11, fill: colors.fg, 'dominant-baseline': 'middle' });
      wires.append(grad, upd, label);
      w.lanes.push({ grad, upd, label });
    }
  }

  // ---- readouts
  const summaryEl = el('b', { id: 'vz-route-summary', 'aria-live': 'polite' });
  const detailEl = el('div', { id: 'vz-route-detail', 'aria-live': 'polite' });
  root.append(el('div', { class: 'vz-reads' }, [
    el('p', {}, ['All 28 parameters in this view: ', summaryEl]),
    detailEl,
  ]));
  root.append(el('p', { class: 'vz-key', text: 'Small dots ride in along the wire (gradients); larger or smaller dots ride back (the update). The size of an update dot shows the step per weight, on one log scale for the whole diagram; a hollow dot means that size is not worked out. A row marked "differs" is routed differently in the other view.' }));

  realNote(root, {
    live: [
      'The routing: our optimizer\'s own rules (copied from its source, 2026-10-27) applied to the real parameter names of one of our heads.',
      'The step per weight, as arithmetic from each group\'s scale.',
    ],
    measured: [
      'Every modular run of these heads used the routing in the first view (routing check of 2026-10-17). Its effect on training is not measured; changing it means new runs.',
    ],
    illustrative: [
      'The renamed names are hypothetical, what a fixed rule would see; renaming the time-embedding layers is our reading.',
      'The step sizes leave out momentum and our optimizer\'s row normalisation (which makes wide matrices 2 to 3.6 times larger, guide section 4).',
      'The moving dots are decoration.',
    ],
  });

  // ---- layout: wire start/end heights follow the row buttons and stations
  let gw = 52, gh = 100;
  function layout() {
    const gr = gutter.getBoundingClientRect();
    if (!gr.width) return;
    gw = gr.width; gh = gr.height;
    wires.setAttribute('viewBox', `0 0 ${gw} ${gh}`);
    wires.setAttribute('width', String(gw)); wires.setAttribute('height', String(gh));
    for (const r of ROWS) {
      const b = rowBtn[r.id].getBoundingClientRect();
      wire[r.id].y0 = b.top + b.height / 2 - gr.top;
      wire[r.id].w = gw;
    }
    retarget(true);
  }
  // end heights: each station spreads the wires that arrive in it over its height
  function retarget(jump) {
    const gr = gutter.getBoundingClientRect();
    const rt = routing[view];
    for (const g of GROUPS) {
      const mine = ids.filter((id) => rt[id].group === g);
      const sr = stationEl[g].getBoundingClientRect();
      const mid = sr.top + sr.height / 2 - gr.top;
      const gap = Math.min(7, (sr.height - 16) / Math.max(1, mine.length));
      mine.forEach((id, k) => { wire[id].tgt = mid + (k - (mine.length - 1) / 2) * gap; });
    }
    for (const id of ids) {
      const w = wire[id];
      if (jump || reducedMotion || w.cur === null) w.cur = w.tgt;
    }
    renderWires();
  }

  const laneOff = (n, k) => (k - (n - 1) / 2) * (n > 3 ? 7 : 11);
  function renderWires() {
    const rt = routing[view];
    const anySel = !!selected;
    for (const id of ids) {
      const w = wire[id], R = rt[id];
      const x1 = gw, y1 = w.cur, y0 = w.y0;
      const col = gcol[R.group];
      w.path.setAttribute('d', `M0,${y0.toFixed(1)}C${(x1 / 2).toFixed(1)},${y0.toFixed(1)} ${(x1 / 2).toFixed(1)},${y1.toFixed(1)} ${x1.toFixed(1)},${y1.toFixed(1)}`);
      w.path.setAttribute('data-group', R.group);
      w.path.setAttribute('stroke', col);
      w.path.setAttribute('stroke-width', id === selected ? 3.5 : 1.5);
      w.path.setAttribute('stroke-opacity', anySel && id !== selected ? 0.4 : 1);
      const bez = (t, a, b2, c, d) => { const u = 1 - t; return u * u * u * a + 3 * u * u * t * b2 + 3 * u * t * t * c + t * t * t * d; };
      const rUpd = R.step === null ? 3 : rOf(R.step);
      w.lanes.forEach((ln, k) => {
        const on = k < R.blocks;
        for (const n of [ln.grad, ln.upd, ln.label]) n.setAttribute('visibility', on ? 'visible' : 'hidden');
        if (!on) return;
        const off = laneOff(R.blocks, k);
        const lane = reducedMotion ? 0 : (k * 0.09 + ids.indexOf(id) * 0.037);
        const place = (node, s, back) => {
          const t = T0 + (1 - T0) * (back ? 1 - s : s);
          const x = bez(t, 0, x1 / 2, x1 / 2, x1);
          const y = bez(t, y0, y0, y1, y1) + off * (1 - 0.6 * t);
          node.setAttribute('cx', x.toFixed(1)); node.setAttribute('cy', y.toFixed(1));
          node.setAttribute('opacity', String(clamp01(Math.min(s * 6, (1 - s) * 6)).toFixed(2)));
        };
        const sg = reducedMotion ? 0.5 : frac(phase + lane);
        const su = reducedMotion ? frac(phase + 0.25) : frac(phase + lane + 0.5);
        place(ln.grad, sg, false);
        place(ln.upd, su, true);
        ln.grad.setAttribute('fill', col);
        ln.upd.setAttribute('r', rUpd.toFixed(2));
        ln.upd.setAttribute('data-step', R.step === null ? '' : String(R.step));
        if (R.step === null) { ln.upd.setAttribute('fill', 'none'); ln.upd.setAttribute('stroke', col); ln.upd.setAttribute('stroke-width', 1.5); }
        else { ln.upd.setAttribute('fill', col); ln.upd.setAttribute('stroke', 'none'); }
        const labels = LANE_LABELS[R.blocks];
        if (labels) {
          const lx = R.blocks > 3 ? 1 + (k % 2) * 8 : 2;
          ln.label.setAttribute('x', String(lx));
          ln.label.setAttribute('y', (y0 + off).toFixed(1));
          ln.label.textContent = labels[k];
        } else ln.label.textContent = '';
      });
    }
  }

  // ---- state
  function syncText() {
    const rt = routing[view];
    root.setAttribute('data-view', view);
    root.setAttribute('data-selected', selected);
    for (const [k, b] of Object.entries(viewBtns)) b.setAttribute('aria-pressed', k === view ? 'true' : 'false');
    for (const r of ROWS) {
      const R = rt[r.id], b = rowBtn[r.id];
      b.setAttribute('data-group', R.group);
      b.setAttribute('data-blocks', String(R.blocks));
      b.setAttribute('data-differs', differs.has(r.id) ? 'yes' : 'no');
      b.setAttribute('aria-pressed', r.id === selected ? 'true' : 'false');
      b.style.borderLeftColor = gcol[R.group];
      rowMeta[r.id].textContent = r.id === 'adaln' && R.blocks === 6 ? '6 pieces'
        : r.id === 'qkv' && R.blocks === 3 ? '3 blocks: Q, K, V' : (R.blocks > 1 ? `${R.blocks} blocks` : '');
      rowMeta[r.id].hidden = !rowMeta[r.id].textContent;
    }
    const c = counts[view];
    for (const g of GROUPS) countEl[g].textContent = c[g] === 0 ? 'no parameters' : `${c[g]} parameters`;
    summaryEl.textContent = GROUPS.map((g) => `${SHORT[g]}: ${c[g]}`).join(', ');
    renderDetail();
  }
  function renderDetail() {
    detailEl.replaceChildren();
    if (!selected) { detailEl.append(el('p', { text: 'Pick a row' })); return; }
    const r = ROWS.find((x) => x.id === selected);
    const R = routing[view][selected];
    const pat = PATTERN[selected];
    const sh = R.shape.length === 1 ? (selected === 'biases' ? '1-D, one value per output' : String(R.shape[0])) : `${R.shape[0]} × ${R.shape[1]}`;
    const code = (arr) => { const p = el('span'); arr.forEach((n, i) => { if (i) p.append(', '); p.append(el('code', { text: n })); }); return p; };
    detailEl.append(el('h4', { text: r.label }));
    detailEl.append(el('p', {}, ['Real name: ', code(pat)]));
    if (view === 'expected') detailEl.append(el('p', {}, ['Renamed: ', code(pat.map(renamed))]));
    detailEl.append(el('p', { text: `Shape: ${sh}` }));
    detailEl.append(el('p', { text: `Group in this view: ${STATION[R.group]}` }));
    const blockText = R.blocks === 1 ? '1 (not split)'
      : selected === 'adaln' ? `${R.blocks} (${PIECES})` : `${R.blocks} (Q, K, V)`;
    detailEl.append(el('p', { text: `Blocks: ${blockText}` }));
    detailEl.append(el('p', { text: R.step === null ? 'Step per weight at lr 1e-2: not worked out in the guide' : `Step per weight at lr 1e-2: ${fmtStep(R.step)}` }));
    detailEl.append(el('p', { text: noteFor(selected) }));
  }
  function select(id) {
    if (id === selected) return;
    selected = id;
    syncText(); renderWires();
  }
  function setView(v) {
    if (v === view) return;
    view = v;
    syncText(); retarget(false);
  }

  function advance({ manual } = {}) {
    if (manual) { phase = frac(phase + 0.25); tick += 1; root.setAttribute('data-tick', String(tick)); renderWires(); return true; }
    const now = performance.now();
    const dt = last ? Math.min(100, now - last) : 16;
    last = now;
    phase = frac(phase + dt / DUR);
    const k = 1 - Math.exp(-dt / EASE_MS);
    for (const id of ids) { const w = wire[id]; w.cur += (w.tgt - w.cur) * k; if (Math.abs(w.tgt - w.cur) < 0.05) w.cur = w.tgt; }
    tick += 1;
    root.setAttribute('data-tick', String(tick));
    renderWires();
    return true;
  }

  const handle = loop(root, advance, { reducedMotion, controls });
  root.setAttribute('data-tick', '0');
  syncText();
  layout();
  let ro = null;
  if (typeof ResizeObserver !== 'undefined') { ro = new ResizeObserver(() => layout()); ro.observe(body); }

  return {
    destroy() {
      handle.destroy();
      if (ro) ro.disconnect();
      root.remove();
    },
  };
}
