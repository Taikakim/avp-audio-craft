// Owner: WINTERMUTE (created 2026-10-27)
// Animation module "lora-rank": a rank slider (16 to 1536) and a DoRA button. Part 1 draws the adapter as a bottleneck and counts
// its numbers; part 2 plots how much of a full fine-tune's change a uniform rank keeps (our measured points); part 3 shows a 12 x 12
// toy change, its rank-k part and what is missing, with DoRA's row-length dials. Used by the glossary entry "rank". Maths in lib/lora.js.
// Last edited: KUANG 2026-10-27 -- the rank slider repeated under the three panels (synced), so the example can be watched
//   while sliding; in the enlarged view only, clips of the June 2026 rank ladder (same recipe at rank 16 / 64 / 128)
import {
  LORA, RANKS, MEASURED, energyAt, adapterParams, fullParams, toyRank, makeToy, truncate, rowLengths,
} from './lib/lora.js';
import { svg, el, injectStyle, applyColors, loop, realNote } from './lib/kit.js';

const CSS = `
.vz-rank{font:14px/1.45 system-ui,sans-serif;color:var(--vz-fg);background:var(--vz-bg);padding:8px;max-width:100%;box-sizing:border-box}
.vz-rank [hidden]{display:none!important}
.vz-rank .vz-controls{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center;margin-bottom:8px}
.vz-rank .vz-slider{display:flex;align-items:center;gap:8px;flex:1 1 220px;min-width:0}
.vz-rank .vz-slider input{flex:1 1 90px;min-width:0;accent-color:var(--vz-accent)}
.vz-rank .vz-slider output{min-width:4ch;font-weight:600;text-align:right;font-variant-numeric:tabular-nums}
.vz-rank .vz-btn{font:inherit;color:var(--vz-fg);background:transparent;border:1px solid var(--vz-muted);border-radius:4px;padding:3px 9px;cursor:pointer}
.vz-rank .vz-btn[aria-pressed="true"]{background:var(--vz-fg);border-color:var(--vz-accent);color:var(--vz-bg);box-shadow:inset 0 -3px 0 var(--vz-accent)}
.vz-rank h4.vz-h{margin:12px 0 4px;font-size:14px}
.vz-rank svg.vz-bottleneck,.vz-rank svg.vz-energy{width:100%;max-width:480px;height:auto;display:block;border:1px solid var(--vz-muted);border-radius:4px}
.vz-rank .vz-heats{display:flex;flex-wrap:wrap;gap:8px}
.vz-rank .vz-heatbox{flex:120 1 110px;min-width:90px;max-width:200px}
.vz-rank .vz-heatbox.kept{flex:168 1 154px;max-width:280px}
.vz-rank .vz-heatbox b{display:block;font-size:13px;margin-bottom:2px}
.vz-rank svg.vz-heat{width:100%;height:auto;display:block;border:1px solid var(--vz-muted)}
.vz-rank .vz-scale{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--vz-muted);margin:6px 0}
.vz-rank .vz-scale i{display:inline-block;width:90px;height:10px;border:1px solid var(--vz-muted)}
.vz-rank .vz-reads{margin:6px 0;font-size:13px}
.vz-rank .vz-reads p{margin:2px 0}
.vz-rank .vz-reads b{font-variant-numeric:tabular-nums}
.vz-rank .vz-why{color:var(--vz-muted);font-size:12px}
.vz-rank .vz-key{font-size:12px;color:var(--vz-muted);margin:4px 0}
.vz-rank .vz-real{margin-top:10px;border-top:1px solid var(--vz-muted);padding-top:6px;font-size:13px}
.vz-rank .vz-real h4{margin:0 0 4px;font-size:13px}
.vz-rank .vz-real dt{font-weight:600;margin-top:4px}
.vz-rank .vz-real dd{margin:0}
.vz-rank .vz-real p{margin:2px 0}
.vz-rank .vz-controls-bottom{margin:10px 0 4px}
.vz-rank .vz-clips{display:none;margin-top:12px;border-top:1px solid var(--vz-muted);padding-top:8px}
.hp-viz-big .vz-rank .vz-clips{display:block}
.vz-rank .vz-clips-hint{font-size:12px;color:var(--vz-muted);margin:6px 0 0}
.hp-viz-big .vz-rank .vz-clips-hint{display:none}
.vz-rank .vz-clips h4{margin:0 0 4px;font-size:14px}
.vz-rank .vz-clips p{margin:2px 0 6px;font-size:13px}
.vz-rank .vz-clip-prompt{font-size:12px;color:var(--vz-muted);margin:10px 0 2px}
.vz-rank .vz-clip-row{display:flex;flex-wrap:wrap;gap:6px 14px}
.vz-rank .vz-clip{display:flex;flex-direction:column;gap:2px;font-size:12px;flex:1 1 180px;min-width:0}
.vz-rank .vz-clip audio{width:100%;height:32px}
`;

const clamp01 = (x) => Math.max(0, Math.min(1, x));
const easeOut = (x) => 1 - (1 - clamp01(x)) ** 3;
const fmt = (n) => Math.round(n).toLocaleString('en-US');
const SLIDE_MS = 300, DORA_MS = 400;
const N = LORA.toy, CELLS = N * N;
const U0 = Math.log2(RANKS[0]), U1 = Math.log2(RANKS[RANKS.length - 1]);

// June 2026 rank ladder, published with every checkpoint on evals/riffer/dora_results.html: DoRA adapters on Stable Audio 3,
// one recipe and corpus, three ranks (AdamW), plus rank 128 with Fusion v1. All clips: same prompt and seed, same step (4,050,
// the end of the third epoch; every run has 1,350 steps per epoch). Paths are relative to this file: help/viz/ -> evals/riffer/.
const LADDER_DIR = new URL('../../evals/riffer/', import.meta.url);
const LADDER = {
  seed: 1234,
  prompts: [
    ['p0', 'aggressive upbeat goa trance'],
    ['p1', 'energetic acid techno, 130 BPM, driving analog bassline, crisp drum machine'],
    ['p2', 'psytrance, 140 bpm'],
  ],
  arms: [
    { label: 'rank 16', tag: 'vjnnndnu_epoch2-step4050' },
    { label: 'rank 64', tag: 'i8nygj4y_epoch2-step4050' },
    { label: 'rank 128', tag: 'dq0egegi_epoch2-step4050' },
    { label: 'rank 128, Fusion v1', tag: 'mqe3ne49_epoch2-step4050' },
  ],
};

function parseColor(c) {
  const s = String(c).trim();
  let m = /^#([0-9a-f]{3})$/i.exec(s);
  if (m) return [...m[1]].map((h) => parseInt(h + h, 16));
  m = /^#([0-9a-f]{6})$/i.exec(s);
  if (m) return [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16));
  m = /^rgba?\(\s*(\d+)[,\s]+(\d+)[,\s]+(\d+)/i.exec(s);
  if (m) return [Number(m[1]), Number(m[2]), Number(m[3])];
  return [128, 128, 128];
}
const mix = (a, b, t) => `rgb(${a.map((x, i) => Math.round(x + (b[i] - x) * t)).join(',')})`;

export function mount(container, params = {}, help = {}) {
  injectStyle('vz-rank-style', CSS);
  const colors = { accent: '#2b6cb0', fg: '#1a1a1a', muted: '#777', bg: '#fff', good: '#2f855a', bad: '#c53030', ...(help.colors || {}) };
  const reducedMotion = !!help.reducedMotion;
  let ridx = RANKS.includes(params.rank) ? RANKS.indexOf(params.rank) : RANKS.indexOf(128);
  let dora = params.dora === true;

  const toy = makeToy();
  const cBad = parseColor(colors.bad), cBg = parseColor(colors.bg), cAcc = parseColor(colors.accent);
  let vmax = 0;
  for (const row of toy.dW) for (const v of row) vmax = Math.max(vmax, Math.abs(v));
  const heatColor = (v) => {
    const t = Math.max(-1, Math.min(1, v / vmax));
    return mix(cBg, t >= 0 ? cAcc : cBad, Math.abs(t));
  };
  // one fixed dial scale: the longest row length at any toy rank, plus the target
  const lens = [];
  for (let k = 1; k <= N; k++) lens.push(rowLengths(toy, k));
  let lmax = 0;
  for (const L of lens) lmax = Math.max(lmax, ...L.target, ...L.lora);
  lmax *= 1.1;
  const angleOf = (len) => (-80 + 160 * clamp01(len / lmax)) * Math.PI / 180;

  const root = el('div', { class: 'vz-rank' });
  applyColors(root, colors);
  container.append(root);

  // ---- controls
  const slider = el('input', { id: 'vz-rank-r', type: 'range', min: 0, max: RANKS.length - 1, step: 1 });
  slider.value = String(ridx);
  const out = el('output', { id: 'vz-rank-r-out', for: 'vz-rank-r' });
  slider.addEventListener('input', () => { ridx = Number(slider.value); setTargets(true); handle.resume(); });
  const doraBtn = el('button', { type: 'button', class: 'vz-btn', text: 'DoRA', 'aria-pressed': 'false' });
  doraBtn.addEventListener('click', () => { dora = !dora; setDora(true); handle.resume(); });
  const controls = el('div', { class: 'vz-controls' }, [
    el('div', { class: 'vz-slider' }, [el('label', { for: 'vz-rank-r', text: 'Rank' }), slider, out]),
    doraBtn,
  ]);
  root.append(controls);

  // ================= part 1: the bottleneck
  root.append(el('h4', { class: 'vz-h', text: '1. The adapter is a narrow bottleneck' }));
  const BW = 340, BH = 172, CX = BW / 2, FULLW = 300;
  const bn = svg('svg', {
    class: 'vz-bottleneck', viewBox: `0 0 ${BW} ${BH}`, role: 'img',
    'aria-label': 'A 1,536-wide input bar narrows through matrix A to a middle as wide as the rank, then widens through matrix B to a 1,536-wide output bar. The wider the rank, the wider the middle.',
  });
  const midW = (u) => 10 + 150 * (u - U0) / (U1 - U0);
  const funA = svg('polygon', { fill: colors.accent, 'fill-opacity': 0.14, stroke: colors.muted });
  const funB = svg('polygon', { fill: colors.accent, 'fill-opacity': 0.14, stroke: colors.muted });
  const mid = svg('rect', { class: 'middle', y: 70, height: 30, fill: colors.accent, stroke: colors.fg, 'stroke-width': 1.5, 'data-r': String(RANKS[ridx]) });
  const midLabel = svg('text', { y: 90, 'font-size': 12, fill: colors.fg, text: '' });
  bn.append(
    svg('rect', { x: CX - FULLW / 2, y: 6, width: FULLW, height: 24, fill: colors.bg, stroke: colors.fg, 'stroke-width': 1.5 }),
    svg('text', { x: CX, y: 22, 'font-size': 12, 'text-anchor': 'middle', fill: colors.fg, text: 'input, 1,536 wide' }),
    funA, funB, mid, midLabel,
    svg('text', { x: CX, y: 54, 'font-size': 12, 'text-anchor': 'middle', fill: colors.fg, text: 'A reads: r × 1,536' }),
    svg('text', { x: CX, y: 124, 'font-size': 12, 'text-anchor': 'middle', fill: colors.fg, text: 'B writes: 1,536 × r' }),
    svg('rect', { x: CX - FULLW / 2, y: 140, width: FULLW, height: 24, fill: colors.bg, stroke: colors.fg, 'stroke-width': 1.5 }),
    svg('text', { x: CX, y: 156, 'font-size': 12, 'text-anchor': 'middle', fill: colors.fg, text: 'output, 1,536 wide' }),
  );
  root.append(bn);
  const paramsEl = el('p', { id: 'vz-rank-params' });
  root.append(el('div', { class: 'vz-reads' }, [paramsEl]));

  // ================= part 2: energy chart
  root.append(el('h4', { class: 'vz-h', text: '2. How much of a full fine-tune\'s change fits' }));
  const EW = 340, EH = 214, PL = 40, PR = 14, PT = 16, PB = 44;
  const iw = EW - PL - PR, ih = EH - PT - PB;
  const fx = (u) => PL + iw * (u - U0) / (U1 - U0);
  const fy = (e) => PT + ih * (1 - e);
  const chart = svg('svg', {
    class: 'vz-energy', viewBox: `0 0 ${EW} ${EH}`, role: 'img',
    'aria-label': 'Energy of a full fine-tune\'s change kept by a uniform rank, against rank on a log scale. Five measured points rise from 4.5 percent at rank 16 to 89.5 percent at rank 1,024; the full matrix at 1,536 keeps 100 percent by definition. A dashed line joins them and a marker shows the chosen rank.',
  });
  for (const t of [0, 0.25, 0.5, 0.75, 1]) {
    chart.append(svg('line', { x1: PL, x2: EW - PR, y1: fy(t), y2: fy(t), stroke: colors.muted, 'stroke-opacity': 0.3 }));
    chart.append(svg('text', { x: PL - 4, y: fy(t) + 4, 'text-anchor': 'end', 'font-size': 12, fill: colors.muted, text: `${t * 100}%` }));
  }
  for (const r of [16, 64, 256, 1024]) {
    chart.append(svg('line', { x1: fx(Math.log2(r)), x2: fx(Math.log2(r)), y1: PT + ih, y2: PT + ih + 4, stroke: colors.muted }));
    chart.append(svg('text', { x: fx(Math.log2(r)), y: PT + ih + 17, 'text-anchor': 'middle', 'font-size': 12, fill: colors.muted, text: String(r) }));
  }
  chart.append(svg('text', { x: PL + iw / 2, y: EH - 6, 'text-anchor': 'middle', 'font-size': 12, fill: colors.muted, text: 'rank (log scale)' }));
  const pts = [...MEASURED, { r: 1536, e: 1 }];
  chart.append(svg('path', {
    class: 'interp', fill: 'none', stroke: colors.muted, 'stroke-width': 1.5, 'stroke-dasharray': '5 4',
    d: pts.map((p, i) => `${i ? 'L' : 'M'}${fx(Math.log2(p.r)).toFixed(1)},${fy(p.e).toFixed(1)}`).join(''),
  }));
  const markLine = svg('line', { y1: PT, y2: PT + ih, stroke: colors.accent, 'stroke-dasharray': '3 3', 'stroke-opacity': 0.7 });
  chart.append(markLine);
  MEASURED.forEach((p, i) => {
    chart.append(svg('circle', { class: 'measured', cx: fx(Math.log2(p.r)), cy: fy(p.e), r: 4, fill: colors.fg, 'data-r': String(p.r), 'data-e': String(p.e) }));
    chart.append(svg('text', {
      x: fx(Math.log2(p.r)) + (i === 0 ? 7 : i === MEASURED.length - 1 ? 0 : -6), y: fy(p.e) + (i === MEASURED.length - 1 ? 19 : i === 0 ? -8 : -7),
      'text-anchor': i === 0 ? 'start' : i === MEASURED.length - 1 ? 'middle' : 'end',
      'font-size': 12, fill: colors.fg, text: `${(p.e * 100).toFixed(1)}%`,
    }));
  });
  chart.append(svg('circle', { class: 'full', cx: fx(U1), cy: fy(1), r: 4.5, fill: colors.bg, stroke: colors.fg, 'stroke-width': 2 }));
  chart.append(svg('text', { x: fx(U1) - 9, y: fy(1) + 4, 'text-anchor': 'end', 'font-size': 12, fill: colors.fg, text: '100% by definition' }));
  const marker = svg('circle', { class: 'marker', r: 7, fill: colors.accent, 'fill-opacity': 0.35, stroke: colors.accent, 'stroke-width': 2.5, 'data-e': '0' });
  chart.append(marker);
  root.append(chart);
  const energyEl = el('b', { id: 'vz-rank-energy' });
  const kindEl = el('span', { id: 'vz-rank-kind' });
  root.append(el('div', { class: 'vz-reads' }, [
    el('p', {}, [energyEl, ' of the change kept (', kindEl, ')']),
    el('p', { class: 'vz-why', text: 'Holding 90% of one matrix\'s change took a median rank of 747 to 1,110.' }),
  ]));

  // ================= part 3: toy example
  root.append(el('h4', { class: 'vz-h', text: '3. A small example' }));
  const heats = el('div', { class: 'vz-heats' });
  const KW = 168, HW = 120;
  const heatSvgs = {}, cellEls = { full: [], kept: [], missing: [] };
  const keptTitle = el('b', { text: 'Kept at rank 1' });
  for (const id of ['full', 'kept', 'missing']) {
    const wv = id === 'kept' ? KW : HW;
    const s = svg('svg', {
      class: `vz-heat ${id}`, viewBox: `0 0 ${wv} ${HW}`, role: 'img', 'shape-rendering': 'crispEdges',
      'aria-label': { full: 'The full 12 by 12 toy change', kept: 'The part of the toy change kept at the chosen rank', missing: 'The part of the toy change that is missing' }[id],
    });
    for (let i = 0; i < N; i++) for (let j = 0; j < N; j++) {
      const c = svg('rect', { class: 'cell', x: j * 10, y: i * 10, width: 10, height: 10, fill: colors.bg });
      s.append(c); cellEls[id].push(c);
    }
    heatSvgs[id] = s;
    const title = id === 'kept' ? keptTitle : el('b', { text: id === 'full' ? 'Full change' : 'Missing' });
    heats.append(el('div', { class: `vz-heatbox ${id}` }, [title, s]));
  }
  // DoRA dials, one per row, beside the kept heatmap
  const dialsG = svg('g', { class: 'dials', visibility: 'hidden', role: 'img', 'aria-label': 'Twelve dials, one per row, showing each row\'s length: a needle for the adapter and a tick for the target' });
  const dials = [];
  const DX = 144, PIV = 8, DR = 5.5;
  for (let i = 0; i < N; i++) {
    const cy = i * 10;
    const g = svg('g', { class: 'dial' });
    g.append(svg('path', { d: `M${DX - DR},${cy + PIV}A${DR},${DR} 0 0 1 ${DX + DR},${cy + PIV}`, fill: 'none', stroke: colors.muted, 'stroke-width': 0.8 }));
    const tick = svg('line', { stroke: colors.accent, 'stroke-width': 2.2 });
    const needle = svg('line', { stroke: colors.fg, 'stroke-width': 1, 'stroke-linecap': 'round' });
    g.append(tick, needle, svg('circle', { cx: DX, cy: cy + PIV, r: 1.1, fill: colors.fg }));
    const a = angleOf(lens[0].target[i]);       // target length is the same at every k
    tick.setAttribute('x1', (DX + 3.4 * Math.sin(a)).toFixed(2)); tick.setAttribute('y1', (cy + PIV - 3.4 * Math.cos(a)).toFixed(2));
    tick.setAttribute('x2', (DX + 7 * Math.sin(a)).toFixed(2)); tick.setAttribute('y2', (cy + PIV - 7 * Math.cos(a)).toFixed(2));
    dialsG.append(g); dials.push({ needle, cy });
  }
  heatSvgs.kept.append(dialsG);
  root.append(heats);

  const scaleKey = el('div', { class: 'vz-scale' }, [
    '−', el('i', { style: `background:linear-gradient(to right,${colors.bad},${colors.bg},${colors.accent})`, 'aria-hidden': 'true' }), '+',
    el('span', { text: '  0 in the middle; one scale for all three' }),
  ]);
  const dialKey = el('p', { class: 'vz-key', text: 'Dials, one per row: needle = with this adapter, tick = target.' });
  root.append(scaleKey, dialKey);
  const toyEl = el('p', { id: 'vz-rank-toy' });
  const rowsEl = el('p', { id: 'vz-rank-rows' });
  root.append(el('div', { class: 'vz-reads' }, [toyEl, rowsEl]));

  // the same slider again under the three panels: sliding at the top hides the example below the fold
  const slider2 = el('input', {
    id: 'vz-rank-r2', type: 'range', min: 0, max: RANKS.length - 1, step: 1,
    'aria-label': 'Rank (the same slider, repeated under the example)',
  });
  slider2.value = String(ridx);
  const out2 = el('output', { id: 'vz-rank-r2-out', for: 'vz-rank-r2' });
  slider2.addEventListener('input', () => { ridx = Number(slider2.value); setTargets(true); handle.resume(); });
  root.append(el('div', { class: 'vz-controls vz-controls-bottom' }, [
    el('div', { class: 'vz-slider' }, [el('label', { for: 'vz-rank-r2', text: 'Rank' }), slider2, out2]),
  ]));

  // ================= heard: the June rank ladder (shown only when the help pane enlarges the animation)
  const audios = [];
  const clips = el('section', { class: 'vz-clips', 'aria-label': 'Clips: the same recipe at three ranks' });
  clips.append(
    el('h4', { text: 'Heard: the same recipe at rank 16, 64 and 128 (June 2026)' }),
    el('p', { text: 'DoRA adapters on Stable Audio 3, trained on the same goa trance data with the same recipe (AdamW), '
      + 'differing only in rank. Each row is one prompt and one seed after the same 4,050 training steps (three epochs). '
      + 'The last column is rank 128 trained with Fusion v1 at twice the learning rate.' }),
    el('p', { class: 'vz-why', text: 'These runs are from June 2026, with the trainer of that time. It had problems fixed '
      + 'since, among them unconstrained weight growth under Schedule-Free averaging, so the clips show what rank did in '
      + 'that setting. They are not indicative of what the current modular optimiser (Fusion v2) produces.' }),
  );
  LADDER.prompts.forEach(([pid, prompt], pi) => {
    clips.append(el('p', { class: 'vz-clip-prompt', text: `Prompt ${pi + 1}: “${prompt}”` }));
    const row = el('div', { class: 'vz-clip-row' });
    for (const arm of LADDER.arms) {
      const a = el('audio', {
        controls: true, preload: 'none',
        src: new URL(`clips_dora_aac/${arm.tag}__${pid}_seed${LADDER.seed}.m4a`, LADDER_DIR).href,
        'aria-label': `${arm.label}, prompt ${pi + 1}`,
      });
      audios.push(a);
      row.append(el('div', { class: 'vz-clip' }, [el('span', { text: arm.label }), a]));
    }
    clips.append(row);
  });
  clips.append(el('p', {}, [
    'Every checkpoint, both seeds and the measured distances: ',
    el('a', { href: new URL('dora_results.html', LADDER_DIR).href, target: '_blank', rel: 'noopener', text: 'DoRA auditions' }),
    '.',
  ]));
  clips.addEventListener('play', (e) => { for (const a of audios) if (a !== e.target) a.pause(); }, true);   // one at a time
  root.append(el('p', { class: 'vz-clips-hint', text: 'Enlarge the animation to hear the same recipe trained at rank 16, 64 and 128.' }));
  root.append(clips);
  // the help pane fires resize when it enlarges or shrinks the animation: stop any clip when the clips are hidden again
  const onResize = () => { if (!root.closest('.hp-viz-big')) for (const a of audios) a.pause(); };
  window.addEventListener('resize', onResize);

  realNote(root, {
    live: [
      'The parameter counts, from the rank and the layer width.',
      'The toy change and its rank-k part, built from the toy\'s own singular vectors (the missing part is the difference).',
      'The row lengths with and without DoRA\'s magnitudes.',
    ],
    measured: [
      'The energy a uniform rank keeps of a full fine-tune of the medium model (229 weight matrices, width 1,536): 4.5% at rank 16, 14.8% at 64, 25.7% at 128, 65% at 512, 89.5% at 1,024, the same within 0.2 points across all 10 of our full fine-tunes (measured 2026-07-24).',
      'Holding 90% of one matrix\'s change took a median rank of 747 (attention output) to 1,110 (MLP).',
    ],
    illustrative: [
      'Values between the measured ranks are interpolated on a log scale.',
      'The toy is 12 wide and its spectrum is shaped to match the measured curve at four ranks.',
      'We have no measured curve for DoRA; in the toy DoRA only fixes row lengths (a trained DoRA also learns its directions with them).',
    ],
  });

  // ---- animated state
  const mk = () => new Float64Array(CELLS);
  const heatCur = { full: mk(), kept: mk(), missing: mk() }, heatFrom = { full: mk(), kept: mk(), missing: mk() }, heatTo = { full: mk(), kept: mk(), missing: mk() };
  const lenCur = new Float64Array(N), lenFrom = new Float64Array(N), lenTo = new Float64Array(N);
  let uCur = Math.log2(RANKS[ridx]), uFrom = uCur, uTo = uCur;
  let t0 = 0, settled = true;
  let dCur = dora ? 1 : 0, dFrom = dCur, dTo = dCur, d0 = 0, dSettled = true;
  let curK = 1, curR = RANKS[ridx];

  const flat = (M) => Float64Array.from(M.flat());
  function setCellValues(arrived) {
    for (const id of ['full', 'kept', 'missing']) {
      const cur = heatCur[id], els = cellEls[id];
      for (let i = 0; i < CELLS; i++) {
        els[i].setAttribute('fill', heatColor(cur[i]));
        if (arrived) els[i].setAttribute('data-v', String(cur[i]));
        else els[i].removeAttribute('data-v');
      }
    }
  }
  function paintBottleneck() {
    const w = midW(uCur);
    mid.setAttribute('x', (CX - w / 2).toFixed(2)); mid.setAttribute('width', w.toFixed(2));
    funA.setAttribute('points', `${CX - FULLW / 2},30 ${CX + FULLW / 2},30 ${(CX + w / 2).toFixed(2)},70 ${(CX - w / 2).toFixed(2)},70`);
    funB.setAttribute('points', `${(CX - w / 2).toFixed(2)},100 ${(CX + w / 2).toFixed(2)},100 ${CX + FULLW / 2},140 ${CX - FULLW / 2},140`);
    midLabel.setAttribute('x', (CX + w / 2 + 8).toFixed(2));
    midLabel.textContent = `r = ${fmt(2 ** uCur)}`;
  }
  function paintMarker() {
    const u = Math.max(U0, Math.min(U1, uCur));
    const e = energyAt(Math.min(1536, Math.max(16, 2 ** u))).e;
    marker.setAttribute('cx', fx(u).toFixed(2)); marker.setAttribute('cy', fy(e).toFixed(2));
    markLine.setAttribute('x1', fx(u).toFixed(2)); markLine.setAttribute('x2', fx(u).toFixed(2));
  }
  function paintDials() {
    for (let i = 0; i < N; i++) {
      const len = lenCur[i] + (lens[0].target[i] - lenCur[i]) * dCur;
      const a = angleOf(len), { needle, cy } = dials[i];
      needle.setAttribute('x1', String(DX)); needle.setAttribute('y1', String(cy + PIV));
      needle.setAttribute('x2', (DX + 5 * Math.sin(a)).toFixed(2)); needle.setAttribute('y2', (cy + PIV - 5 * Math.cos(a)).toFixed(2));
    }
  }
  function textFor() {
    const r = curR, k = curK;
    const total = adapterParams(r), full = fullParams();
    const pct = (total / full) * 100;
    paramsEl.textContent = `Adapter: ${fmt(r)} × (${fmt(LORA.width)} + ${fmt(LORA.width)}) = ${fmt(total)} numbers, ${pct >= 100 ? pct.toFixed(0) : pct.toFixed(1)}% of the full matrix's ${fmt(full)}.`
      + (dora ? ` + ${fmt(LORA.width)} magnitudes (one per row).` : '');
    const en = energyAt(r);
    energyEl.textContent = `${en.e === 1 ? '100' : (en.e * 100).toFixed(1)}%`;
    kindEl.textContent = en.kind === 'measured' ? 'measured'
      : en.kind === 'interpolated' ? `interpolated between r${en.between[0]} and r${en.between[1]}` : 'the full matrix';
    toyEl.textContent = `Toy rank ${k} of ${N} (the toy is 1/${LORA.width / N} of the real width)`
      + (r < 128 ? '; the toy is too small to show ranks below 128, so it shows rank 1.' : '.');
    rowsEl.textContent = dora
      ? 'Row lengths match exactly: DoRA sets each row\'s length with its own number. The directions still come from the rank-' + k + ' part.'
      : `Row lengths are off by ${(rowLengths(toy, k).meanRelErr * 100).toFixed(1)}% on average at toy rank ${k}`;
    keptTitle.textContent = `Kept at rank ${k}`;
    out.textContent = String(r);
    slider.setAttribute('aria-valuetext', `rank ${r}`);
    slider.value = String(ridx); slider2.value = String(ridx);          // keep both sliders on the same rank
    out2.textContent = String(r);
    slider2.setAttribute('aria-valuetext', `rank ${r}`);
    root.setAttribute('data-rank', String(r));
    root.setAttribute('data-toyrank', String(k));
    mid.setAttribute('data-r', String(r));
    marker.setAttribute('data-e', String(en.e));
  }

  function setTargets(animate) {
    const r = RANKS[ridx], k = toyRank(r);
    curR = r; curK = k;
    const kept = truncate(toy, k);
    const full = toy.dW;
    const miss = full.map((row, i) => row.map((v, j) => v - kept[i][j]));
    for (const id of ['full', 'kept', 'missing']) heatFrom[id].set(heatCur[id]);
    heatTo.full = flat(full); heatTo.kept = flat(kept); heatTo.missing = flat(miss);
    lenFrom.set(lenCur); lenTo.set(lens[k - 1].lora);
    uFrom = uCur; uTo = Math.log2(r);
    const jump = !animate || reducedMotion;
    t0 = performance.now(); settled = jump;
    if (jump) arrive(); else setCellValues(false);
    textFor();
  }
  function arrive() {
    for (const id of ['full', 'kept', 'missing']) heatCur[id].set(heatTo[id]);
    lenCur.set(lenTo); uCur = uTo; settled = true;
    setCellValues(true); paintBottleneck(); paintMarker(); paintDials();
  }
  function setDora(animate) {
    dFrom = dCur; dTo = dora ? 1 : 0;
    d0 = performance.now();
    const jump = !animate || reducedMotion;
    dSettled = jump;
    if (jump) dCur = dTo;
    dialsG.setAttribute('visibility', dora ? 'visible' : 'hidden');
    dialKey.hidden = !dora;
    doraBtn.setAttribute('aria-pressed', dora ? 'true' : 'false');
    root.setAttribute('data-dora', dora ? 'on' : 'off');
    paintDials(); textFor();
  }

  function advance({ manual } = {}) {
    if (manual) return true;                        // reduced motion: everything already jumps; Step has nothing to do
    const now = performance.now();
    let moving = false;
    if (!settled) {
      const t = (now - t0) / SLIDE_MS, e = easeOut(t);
      if (t >= 1) arrive();
      else {
        for (const id of ['full', 'kept', 'missing']) {
          const c = heatCur[id], f = heatFrom[id], to = heatTo[id];
          for (let i = 0; i < CELLS; i++) c[i] = f[i] + (to[i] - f[i]) * e;
        }
        for (let i = 0; i < N; i++) lenCur[i] = lenFrom[i] + (lenTo[i] - lenFrom[i]) * e;
        uCur = uFrom + (uTo - uFrom) * e;
        setCellValues(false); paintBottleneck(); paintMarker(); paintDials();
        moving = true;
      }
    }
    if (!dSettled) {
      const t = (now - d0) / DORA_MS;
      if (t >= 1) { dCur = dTo; dSettled = true; } else { dCur = dFrom + (dTo - dFrom) * easeOut(t); moving = true; }
      paintDials();
    }
    return moving;                                  // false = everything has arrived: the loop idles until the next change
  }

  const handle = loop(root, advance, { reducedMotion, controls });
  setTargets(false); setDora(false);

  return {
    destroy() {
      window.removeEventListener('resize', onResize);
      for (const a of audios) a.pause();
      handle.destroy();
      root.remove();
    },
  };
}
