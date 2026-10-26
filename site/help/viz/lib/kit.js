// Owner: WINTERMUTE (created 2026-10-26)
// DOM helpers shared by the animation modules. Importing this file touches no DOM; only calls do.
// Last edited: WINTERMUTE 2026-10-26 -- module rules below (colours, openTerm)
//
// Rules for every module:
//  * Never name a colour in text ("the blue line"). The pane's colours differ from page to page; tell series apart with a
//    swatch drawn beside the name (and by position or label), using the colours passed in help.colors.
//  * A module may only call help.openTerm(id) for ids that appear in its own glossary entry's text, so the publish gate's
//    reachable() set (which follows marked terms in the entry text) already covers every entry the module can open.

const SVG_NS = 'http://www.w3.org/2000/svg';

function applyAttrs(node, attrs) {
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'text') node.textContent = v;
    else if (k === 'class') node.setAttribute('class', v);
    else if (k.startsWith('on') && typeof v === 'function') node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v === true ? '' : String(v));
  }
}
function appendChildren(node, children) {
  for (const ch of [].concat(children ?? [])) {
    if (ch === null || ch === undefined || ch === false) continue;
    node.append(ch);
  }
  return node;
}
export function svg(tag, attrs, children) {
  const n = document.createElementNS(SVG_NS, tag);
  applyAttrs(n, attrs);
  return appendChildren(n, children);
}
export function el(tag, attrs, children) {
  const n = document.createElement(tag);
  applyAttrs(n, attrs);
  return appendChildren(n, children);
}

export function injectStyle(id, css) {
  if (document.getElementById(id)) return;
  const s = el('style', { id });
  s.textContent = css;
  document.head.append(s);
}
export function applyColors(root, colors) {
  for (const [k, v] of Object.entries(colors || {})) root.style.setProperty(`--vz-${k}`, v);
}

// Animation loop. step({manual}) is called once per animation frame while the container is visible;
// return false from step to go idle (call handle.resume() to continue).
// With reducedMotion nothing runs by itself: a Step button calls step({manual: true}).
export function loop(container, step, { reducedMotion = false, stepLabel = 'Step', controls = null } = {}) {
  let raf = 0, visible = true, alive = true, idle = false, io = null, btn = null;

  const tick = () => {
    raf = 0;
    if (!alive || !visible || reducedMotion) return;
    let r;
    try { r = step({ manual: false }); } catch (e) { console.error(e); return; }
    if (r === false) { idle = true; return; }
    raf = requestAnimationFrame(tick);
  };
  const kick = () => {
    if (alive && visible && !reducedMotion && !raf && !idle) raf = requestAnimationFrame(tick);
  };

  if (reducedMotion) {
    btn = el('button', { type: 'button', class: 'vz-btn', text: stepLabel });
    btn.addEventListener('click', () => { try { step({ manual: true }); } catch (e) { console.error(e); } });
    (controls || container).append(btn);
  }
  if (typeof IntersectionObserver !== 'undefined') {
    io = new IntersectionObserver((entries) => {
      visible = entries[entries.length - 1].isIntersecting;
      if (visible) kick();
      else if (raf) { cancelAnimationFrame(raf); raf = 0; }
    });
    io.observe(container);
  }
  kick();

  return {
    resume() { idle = false; kick(); },
    destroy() {
      alive = false;
      if (raf) { cancelAnimationFrame(raf); raf = 0; }
      if (io) io.disconnect();
      if (btn) btn.remove();
    },
  };
}

// The required "What's real here" note. Each of live / measured / illustrative is a string or a list of strings.
export function realNote(container, { live, measured, illustrative }) {
  const rows = [
    ['Computed live', live, 'Nothing is computed live.'],
    ['From our own runs', measured, 'No numbers from our own runs are shown.'],
    ['Illustration only', illustrative, 'Nothing here is only an illustration.'],
  ];
  const dl = el('dl', { class: 'vz-real-list' });
  for (const [label, val, none] of rows) {
    const items = [].concat(val ?? []).filter(Boolean);
    dl.append(el('dt', { text: label }));
    const dd = el('dd');
    if (items.length === 0) dd.textContent = none;
    else for (const it of items) dd.append(el('p', { text: it }));
    dl.append(dd);
  }
  const note = el('section', { class: 'vz-real', 'aria-label': "What's real here" }, [
    el('h4', { text: "What's real here" }), dl,
  ]);
  container.append(note);
  return note;
}

// Small line chart (SVG). series: [{key, color, label}]. push({key: value, ...}) adds one point per call.
// yLog uses a log10 axis between yMin and yMax (values are clamped into range for drawing).
export function lineChart(parent, {
  width = 420, height = 150, series, xMax, yMin, yMax, yLog = false, yTicks = [], xLabel = '', yLabel = '', fg = '#222', muted = '#888',
}) {
  const pad = { l: 44, r: 8, t: 8, b: 26 };
  const iw = width - pad.l - pad.r, ih = height - pad.t - pad.b;
  const fy = (v) => {
    const lo = yLog ? Math.log10(yMin) : yMin, hi = yLog ? Math.log10(yMax) : yMax;
    const x = yLog ? Math.log10(Math.max(v, yMin)) : v;
    return pad.t + ih * (1 - Math.min(1, Math.max(0, (x - lo) / (hi - lo))));
  };
  const fx = (i) => pad.l + (iw * Math.min(i, xMax)) / xMax;
  const root = svg('svg', { viewBox: `0 0 ${width} ${height}`, class: 'vz-chart', role: 'img', 'aria-label': `${yLabel} over ${xLabel}` });
  for (const t of yTicks) {
    root.append(svg('line', { x1: pad.l, x2: width - pad.r, y1: fy(t), y2: fy(t), stroke: muted, 'stroke-opacity': 0.3 }));
    root.append(svg('text', { x: pad.l - 4, y: fy(t) + 3, 'text-anchor': 'end', 'font-size': 9, fill: muted, text: String(t) }));
  }
  root.append(svg('text', { x: pad.l + iw / 2, y: height - 4, 'text-anchor': 'middle', 'font-size': 10, fill: muted, text: xLabel }));
  root.append(svg('text', { x: 10, y: pad.t + ih / 2, 'text-anchor': 'middle', 'font-size': 10, fill: muted, transform: `rotate(-90 10 ${pad.t + ih / 2})`, text: yLabel }));
  const marker = svg('line', { y1: pad.t, y2: pad.t + ih, stroke: muted, 'stroke-dasharray': '3 3', visibility: 'hidden' });
  root.append(marker);
  const lines = {}, pts = {};
  for (const s of series) {
    pts[s.key] = [];
    lines[s.key] = svg('polyline', { fill: 'none', stroke: s.color, 'stroke-width': 2, points: '' });
    root.append(lines[s.key]);
  }
  parent.append(root);
  return {
    el: root,
    push(values) {
      for (const s of series) {
        const arr = pts[s.key];
        arr.push(`${fx(arr.length).toFixed(1)},${fy(values[s.key]).toFixed(1)}`);
        lines[s.key].setAttribute('points', arr.join(' '));
      }
    },
    clear() { for (const s of series) { pts[s.key] = []; lines[s.key].setAttribute('points', ''); } },
    setMarker(x) {
      if (x === null || x === undefined) marker.setAttribute('visibility', 'hidden');
      else { marker.setAttribute('x1', fx(x)); marker.setAttribute('x2', fx(x)); marker.setAttribute('visibility', 'visible'); }
    },
    destroy() { root.remove(); },
  };
}
