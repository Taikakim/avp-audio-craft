#!/usr/bin/env python3
"""eval_grid.py — shared rich renderer for gain x density control-response evals,
PLUS (2026-07-06) the human-first sortable table + dual-checkpoint compare view.
See docs/superpowers/specs/2026-07-05-eval-grid-rich-renderer.md and
docs/superpowers/specs/2026-07-06-eval-tables-human-first.md.

Restores + generalizes Misc/build_onset_eval_page.py's gold layout (gain rows x
density columns, heatmap-colored, per-gain correlation, same-playhead player,
provenance box) as a reusable module any grid-style eval dir can call — the
generic per-folder pages build_evals.py emits AND (eventually) the curated
riffer pages.

Data contract (per merged clip record, see merge_records()):
  checkpoint, prompt_idx, prompt, seed, gain, density, measured, error_delta,
  flatness, spectral_balance, CE, CU, PC, PQ, broke, clip (served-relative path or None)

A grid dir is any dir with onset_eval.json. pq_scores.json is optional — the
renderer degrades gracefully (missing metrics render as "·"), but every
present metric is used for color + sort.

A DoRA-audition dir is any dir whose pq_scores.json rows carry a `checkpoint`
key (see control/sa3_control/pq_score.py's DoRA filename convention) — one row
per (checkpoint, prompt, seed) clip, no gain/density axis. See load_dora_data()
and render_table_compare_page() for the sortable-table + dual-pane-compare view.
"""
import html
import json
import os
import re


# ── clip-name parsing (mirrors control/sa3_control/pq_score.py's conventions,
#    but also has to construct the STAGED .m4a name for a given onset_eval.json
#    row, whose own fields don't include the exact source filename) ──────────
def _fmt_num(x):
    """0.1 -> '0.1', 12.0 -> '12', matching the %g style pq_score.py/onset_eval.py use."""
    return f"{x:g}"


def clip_stem_for_row(run_name: str, row: dict) -> list[str]:
    """Candidate staged-clip stems (without extension) for an onset_eval.json row,
    most-specific first. A row may match any of these depending on which naming
    convention the source run used."""
    g, d = row.get("gain"), row.get("requested", row.get("density"))
    p, s = row.get("prompt_idx"), row.get("seed")
    candidates = []
    if p is not None and s is not None:
        candidates.append(f"{run_name}_p{p}_s{s}_g{_fmt_num(g)}_d{_fmt_num(d)}")
    if p is not None:
        candidates.append(f"onset_p{p}_g{_fmt_num(g)}_d{_fmt_num(d)}")
    candidates.append(f"onset_g{_fmt_num(g)}_d{_fmt_num(d)}")
    return candidates


def _pq_key(row: dict):
    return (row.get("prompt_idx"), row.get("seed"), row.get("gain"), row.get("density"))


def merge_records(run_name: str, onset_rows: list[dict], pq_rows: list[dict],
                   clip_lookup) -> list[dict]:
    """Join onset_eval.json rows with pq_scores.json rows.

    clip_lookup(stem) -> served-relative clip path or None; called with each
    candidate stem from clip_stem_for_row() until one hits, so callers don't
    need to know which naming convention a given run used.
    """
    # Full (prompt_idx, seed, gain, density) index, plus a (gain, density)-only
    # fallback for pq rows written by the pre-2026-07-05 schema (no p/s/spectral_balance).
    pq_full = {}
    pq_gd = {}
    for r in pq_rows:
        pq_full[_pq_key(r)] = r
        pq_gd.setdefault((r.get("gain"), r.get("density")), r)

    out = []
    for row in onset_rows:
        g = row.get("gain")
        d = row.get("requested", row.get("density"))
        p, s = row.get("prompt_idx"), row.get("seed")
        pq = pq_full.get((p, s, g, d)) or pq_gd.get((g, d)) or {}

        clip = None
        for stem in clip_stem_for_row(run_name, row):
            clip = clip_lookup(stem)
            if clip:
                break

        measured = row.get("measured")
        error_delta = (measured - d) if (measured is not None and d is not None) else None

        out.append({
            "checkpoint": run_name,
            "prompt_idx": p, "prompt": row.get("prompt"), "seed": s,
            "gain": g, "density": d, "measured": measured, "error_delta": error_delta,
            "flatness": row.get("flatness"),
            "spectral_balance": pq.get("spectral_balance"),
            "CE": pq.get("CE"), "CU": pq.get("CU"), "PC": pq.get("PC"), "PQ": pq.get("PQ"),
            "broke": pq.get("broke", False),
            "clip": clip,
        })
    return out


# ── DoRA-audition data layer (checkpoint x prompt x seed, no gain/density) ────
# Prompt text mirrors Misc/build_dora_audition_page.py's PROMPTS (index = p<i>);
# kept here too so load_dora_data() doesn't need that script as a dependency.
DORA_PROMPTS = [
    "aggressive upbeat goa trance",
    "energetic acid techno, 130 BPM, analog bassline",
    "psytrance, 140 bpm",
]


def load_dora_data(source_dir: str, clip_lookup) -> list[dict] | None:
    """Load pq_scores.json DoRA-flavored rows (checkpoint/epoch/step, no gain/density,
    see pq_score.py's `_DORA` filename convention) from source_dir into per-clip
    records carrying an explicit `checkpoint` key. Returns None if pq_scores.json is
    absent or has no checkpoint-tagged rows (not a DoRA-audition dir)."""
    pq_path = os.path.join(source_dir, "pq_scores.json")
    if not os.path.exists(pq_path):
        return None
    try:
        rows = json.load(open(pq_path))
    except Exception:
        return None
    # `checkpoint` alone isn't a unique marker -- prompt-style rows (pq_score.py's
    # `_PROMPTSTYLE` convention) also carry a `checkpoint` (the arm name), so
    # exclude those explicitly and let load_promptstyle_data() claim them instead.
    rows = [r for r in rows if r.get("checkpoint") and not r.get("prompt_key")]
    if not rows:
        return None
    out = []
    for r in rows:
        rel = r.get("rel_path", "")
        run_label = rel.split("/")[0] if "/" in rel else ""
        stem = os.path.splitext(os.path.basename(rel))[0] if rel else None
        clip = None
        if stem:
            clip = clip_lookup(f"{run_label}/{stem}" if run_label else stem)
        pi = r.get("prompt_idx")
        prompt = DORA_PROMPTS[pi] if (pi is not None and pi < len(DORA_PROMPTS)) else None
        out.append({
            "checkpoint": r["checkpoint"], "run_label": run_label,
            "epoch": r.get("epoch"), "step": r.get("step"),
            "prompt_idx": pi, "prompt": prompt, "seed": r.get("seed"),
            "CE": r.get("CE"), "CU": r.get("CU"), "PC": r.get("PC"), "PQ": r.get("PQ"),
            "spectral_balance": r.get("spectral_balance"), "broke": r.get("broke", False),
            "clip": clip,
        })
    return out


# ── prompt-style A/B data layer (checkpoint x prompt x seed, plain vs styled) ─
def load_promptstyle_data(source_dir: str, clip_lookup, extra_stems=None) -> list[dict] | None:
    """Load pq_scores.json prompt-style rows (checkpoint=arm, prompt_key, style
    -- see pq_score.py's `_PROMPTSTYLE` filename convention) and PAIR each
    (checkpoint, prompt_key, seed)'s plain + styled rows into one record, so
    the compare view can show them side by side per Kim's ask. Prompt text
    (plain/styled) is read from the source dir's run_meta.json (written by the
    render script) if present. Returns None if pq_scores.json is absent or has
    no prompt_key-tagged rows (not a prompt-style dir). extra_stems: optional
    iterable of staged clip stems not yet covered by pq_scores.json (a new arm
    rendered ahead of the scoring pass) -- backfilled as unscored rows."""
    pq_path = os.path.join(source_dir, "pq_scores.json")
    if not os.path.exists(pq_path):
        return None
    try:
        rows = json.load(open(pq_path))
    except Exception:
        return None
    rows = [r for r in rows if r.get("prompt_key")]
    if not rows:
        return None

    prompt_text = {}  # prompt_key -> {"plain": ..., "styled": ...}
    meta_path = os.path.join(source_dir, "run_meta.json")
    if os.path.exists(meta_path):
        try:
            meta = json.load(open(meta_path))
            prompt_text = meta.get("prompts", {})
        except Exception:
            pass

    paired = {}  # (checkpoint, prompt_key, seed) -> {"plain": row, "styled": row}
    for r in rows:
        key = (r["checkpoint"], r["prompt_key"], r.get("seed"))
        paired.setdefault(key, {})[r["style"]] = r

    # Backfill combos that have staged clips but no pq_scores.json row yet -- a
    # new arm/seed can land (re-rendered) before the Audiobox scoring pass has
    # caught up, and without this the compare page's dropdown would silently
    # omit it entirely rather than showing it unscored (Kim, 2026-07-07: the
    # evr3x_w033 arm's 12 clips existed on disk with pq_scores.json still only
    # covering the original 5 arms). Filename convention (see
    # eval/eval_prompt_styles.py / density_control_eval.py):
    # {checkpoint}__{prompt_key}_{style}_s{seed}.wav
    if extra_stems:
        seen = {(ck, pk, s) for (ck, pk, s) in paired}
        stem_re = re.compile(r"^(?P<ck>.+)__(?P<pk>.+)_(?P<style>plain|styled)_s(?P<seed>\d+)$")
        for stem in extra_stems:
            m = stem_re.match(stem)
            if not m:
                continue
            key = (m["ck"], m["pk"], int(m["seed"]))
            if key in seen:
                continue
            paired.setdefault(key, {})[m["style"]] = {"rel_path": f"{stem}.wav"}

    out = []
    for (checkpoint, prompt_key, seed), by_style in paired.items():
        plain, styled = by_style.get("plain"), by_style.get("styled")

        def clip_for(row):
            if row is None:
                return None
            rel = row.get("rel_path", "")
            stem = os.path.splitext(os.path.basename(rel))[0] if rel else None
            return clip_lookup(stem) if stem else None

        texts = prompt_text.get(prompt_key, {})
        out.append({
            "checkpoint": checkpoint, "prompt_key": prompt_key, "seed": seed,
            "prompt_plain": texts.get("plain"), "prompt_styled": texts.get("styled"),
            "CE_plain": plain.get("CE") if plain else None, "CE_styled": styled.get("CE") if styled else None,
            "CU_plain": plain.get("CU") if plain else None, "CU_styled": styled.get("CU") if styled else None,
            "PC_plain": plain.get("PC") if plain else None, "PC_styled": styled.get("PC") if styled else None,
            "PQ_plain": plain.get("PQ") if plain else None, "PQ_styled": styled.get("PQ") if styled else None,
            "clip_plain": clip_for(plain), "clip_styled": clip_for(styled),
        })
    return out


# ── density-control grid (arm x prompt x style x seed x condition x density) ──
# See eval/density_control_eval.py (LatCH vs FusionCC-FiLM vs both-at-half) and
# eval/measure_density_control_onsets.py (the librosa onset_density() readout,
# same approach as sa3_control/multi_eval.py) for the producer + measurer.
def load_density_control_data(measurements: dict, prompt_text: dict,
                               clip_lookup) -> list[dict] | None:
    """Build records straight from clip filenames + the _onset_measurements.json
    sidecar (no pq_scores.json axis here -- Audiobox scoring hasn't run on this
    grid). Filename convention: {arm}__{prompt}_{style}_s{seed}__{cond}_d{density}.wav
    Returns None if there's nothing measured (grid not yet ready)."""
    if not measurements:
        return None
    out = []
    for stem, m in measurements.items():
        clip = clip_lookup(stem)
        measured = m.get("measured_density")
        requested = m.get("requested_density")
        texts = prompt_text.get(m["prompt"], {})
        out.append({
            "checkpoint": m["arm"], "prompt_idx": m["prompt"], "prompt": texts.get(m["style"]) or m["prompt"],
            "style": m["style"], "seed": m["seed"], "condition": m["condition"],
            "density": requested, "measured": measured,
            "error_delta": (measured - requested) if (measured is not None and requested is not None) else None,
            "clip": clip,
        })
    return out or None


DENSITY_CTRL_CSS = ".aud-bar .faint2{color:var(--faint);font-size:10.5px}"

DENSITY_CTRL_JS_TEMPLATE = r"""
(function(){
const D = __DATA__;
const ARMS = __ARMS__;
const COLS = [
  { key: 'prompt', label: 'prompt', get: r => r.prompt, kind: 'str' },
  { key: 'style', label: 'style', get: r => r.style, kind: 'str' },
  { key: 'seed', label: 'seed', get: r => r.seed, kind: 'num' },
  { key: 'condition', label: 'condition', get: r => r.condition, kind: 'str' },
  { key: 'density', label: 'requested', get: r => r.density, kind: 'num' },
  { key: 'measured', label: 'measured', get: r => r.measured, kind: 'num' },
  { key: 'error_delta', label: 'error', get: r => r.error_delta, kind: 'num' },
];
const byArm = {};
D.forEach(r => { (byArm[r.checkpoint] ||= []).push(r); });

const wrap = document.getElementById(__WRAP_ID__);
const audio = new Audio(); let curKey = null;
audio.addEventListener('ended', () => { markPlaying(null); curKey = null; });
function markPlaying(key) {
  document.querySelectorAll('.tc-table tr[data-key]').forEach(tr => {
    tr.classList.toggle('playing', tr.dataset.key === key && key !== null);
  });
}
function seekAndPlay(a, pos) {
  const go = () => { try { a.currentTime = ((a.duration && pos > a.duration - 1) ? 0 : Math.min(pos, (a.duration || 1e9) - 0.05)); } catch (e) {} a.play(); };
  if (a.readyState >= 3) { go(); return; }
  let done = false;
  const fire = () => { if (done) return; done = true; go(); };
  a.addEventListener('canplay', fire, { once: true });
  setTimeout(fire, 1200);
}
function play(key, src, label) {
  if (!src) return;
  if (curKey === key) { audio.pause(); markPlaying(null); curKey = null; return; }
  const pos = (curKey !== null && !audio.paused) ? audio.currentTime : 0;
  curKey = key; markPlaying(key);
  audio.pause();
  audio.src = src;
  seekAndPlay(audio, pos);
  document.getElementById(__INFO_ID__).textContent = label;
}

let arm = ARMS[0];
let sort = { col: 'error_delta', dir: 1 };

function realizedRange(rows, key) {
  const vals = rows.map(r => COLS.find(c => c.key === key).get(r)).filter(v => v != null);
  return vals.length ? [Math.min(...vals), Math.max(...vals)] : null;
}
function colorFor(v, range, invert) {
  if (v == null || !range) return '#eee';
  const [lo, hi] = range;
  let t = hi > lo ? (v - lo) / (hi - lo) : 0.5;
  if (invert) t = 1 - t;
  return `hsl(${Math.round(t * 130)},50%,80%)`;
}

function render() {
  wrap.innerHTML = '';
  const bar = document.createElement('div'); bar.className = 'aud-bar';
  const select = document.createElement('select');
  ARMS.forEach(tag => {
    const opt = document.createElement('option');
    opt.value = tag; opt.textContent = tag;
    if (tag === arm) opt.selected = true;
    select.appendChild(opt);
  });
  select.onchange = () => { arm = select.value; render(); };
  bar.appendChild(select);
  const rows = byArm[arm] || [];
  const meta = document.createElement('span'); meta.className = 'aud-meta';
  meta.textContent = `${rows.length} clips for this arm`;
  bar.appendChild(meta);
  wrap.appendChild(bar);

  const col = COLS.find(c => c.key === sort.col);
  const sorted = rows.slice().sort((a, b) => {
    const va = col.get(a), vb = col.get(b);
    if (va == null && vb == null) return 0;
    if (va == null) return 1;
    if (vb == null) return -1;
    return col.kind === 'str' ? sort.dir * String(va).localeCompare(String(vb)) : sort.dir * (va - vb);
  });
  const ranges = {}; COLS.forEach(c => { if (c.kind === 'num') ranges[c.key] = realizedRange(rows, c.key); });

  const table = document.createElement('table'); table.className = 'tc-table';
  const headRow = document.createElement('tr');
  COLS.forEach(c => {
    const on = sort.col === c.key;
    const arrow = on ? (sort.dir === 1 ? '↑' : '↓') : '';
    const th = document.createElement('th');
    th.innerHTML = `${c.label} <span class="arrow">${arrow}</span>`;
    th.onclick = () => { sort = { col: c.key, dir: sort.col === c.key ? -sort.dir : (c.key === 'error_delta' ? 1 : -1) }; render(); };
    headRow.appendChild(th);
  });
  headRow.appendChild(document.createElement('th'));
  table.appendChild(headRow);

  sorted.forEach((r, i) => {
    const tr = document.createElement('tr'); tr.dataset.key = arm + '-' + i;
    COLS.forEach(c => {
      const td = document.createElement('td');
      const v = c.get(r);
      if (c.kind === 'num' && ranges[c.key]) td.style.background = colorFor(v, ranges[c.key], c.key === 'error_delta');
      td.textContent = v == null ? '·' : (typeof v === 'number' ? (Math.abs(v) < 10 ? v.toFixed(2) : v.toFixed(1)) : v);
      tr.appendChild(td);
    });
    const playTd = document.createElement('td'); playTd.textContent = '▶'; playTd.style.cursor = r.clip ? 'pointer' : 'default';
    if (r.clip) playTd.onclick = () => play(arm + '-' + i, r.clip, `${arm} · ${r.prompt || ''} (${r.style}) · ${r.condition} d${r.density} s${r.seed} -> ${r.measured==null?'·':r.measured.toFixed(2)}`);
    tr.appendChild(playTd);
    table.appendChild(tr);
  });
  wrap.appendChild(table);
}
render();
})();
"""


def render_density_control_page(*, head_html: str, title: str, label: str, purpose: str,
                                 date_str: str, records: list[dict], footer_html: str,
                                 findings: str = None, status: str = None,
                                 known_pages: dict = None) -> str:
    """One dropdown over arm, one sortable table (condition/density/measured/error)
    per arm -- the control-authority readout for the density_control_eval.py grid.
    Same single-pane pattern as render_checkpoint_audit_page, swapping gain for
    condition+density since there's no gain axis here."""
    arms = sorted({r["checkpoint"] for r in records})
    n_measured = sum(1 for r in records if r["measured"] is not None)
    doc = head_html
    doc += f'<h1>{html.escape(label)}</h1>'
    if date_str:
        doc += f'<p class="faint">{html.escape(date_str)}</p>'
    if purpose:
        doc += f'<p class="lede">{html.escape(purpose)}</p>'
    doc += provenance_html(findings, status, known_pages)
    doc += (f'<p class="faint">{len(arms)} arms · {len(records)} clips ({n_measured} onset-density '
            'measured via librosa) · pick an arm, click a column header to sort · click ▶ to play '
            '(shared playhead) · error = measured − requested onsets/sec (green≈0, the control-authority '
            'readout) · colour = min→max within the shown arm only</p>')
    doc += '<div class="eg-info" id="dc-info">click a row for its readout</div>'
    doc += '<div id="dc-wrap"></div>'
    js = (DENSITY_CTRL_JS_TEMPLATE
          .replace("__DATA__", json.dumps(records))
          .replace("__ARMS__", json.dumps(arms))
          .replace("__WRAP_ID__", "'dc-wrap'")
          .replace("__INFO_ID__", "'dc-info'"))
    doc += f'<script>{js}</script>'
    doc += footer_html
    return doc


# ── rendering ────────────────────────────────────────────────────────────────
PROVENANCE_CSS = """
.status-banner{padding:8px 14px;margin:0 0 14px;font-size:11.5px;border-left:3px solid;border-radius:2px}
.status-banner.historical{background:#fdf6e3;border-color:#c9a227;color:#7a5c00}
.status-banner.superseded{background:#fdecea;border-color:#c0392b;color:#8a2e22}
.findings-box{border:1px solid var(--rule);border-left:3px solid var(--edge-ink);background:#fff;
padding:8px 12px;margin:0 0 14px;font-size:11.5px;color:var(--body)}
.findings-box .lbl{font-size:10px;letter-spacing:.15em;text-transform:uppercase;color:var(--edge-ink);
margin:0 0 4px;display:block}
"""


def provenance_html(findings=None, status=None, known_pages=None):
    """'What we learned' box + a HISTORICAL/SUPERSEDED banner (Kim, 2026-07-07:
    casual viewers should immediately see when a page reflects earlier,
    superseded work, with a pointer to whatever replaced it). Silent no-op for
    status='current'/None -- only historical/superseded states get a banner.
    known_pages: optional {name: href} used to auto-linkify a mention of
    another known page's name inside the status text."""
    h = ""
    if status:
        s = status.strip()
        sl = s.lower()
        if sl.startswith("historical") or "superseded" in sl:
            cls = "superseded" if "superseded" in sl else "historical"
            text = html.escape(s)
            if known_pages:
                # word-boundary match only -- a short key like "mp" (the
                # multiprompt curated page) must not match mid-word inside
                # "ramp"/"tempo" (Kim, 2026-07-07: caught on chroma_morph_barsnap)
                hits = [n for n in known_pages if re.search(rf"\b{re.escape(n)}\b", s)]
                if hits:
                    best = max(hits, key=len)
                    esc = html.escape(best)
                    text = re.sub(rf"\b{re.escape(esc)}\b",
                                  f'<a href="{html.escape(known_pages[best])}">{esc}</a>', text, count=1)
            h += f'<div class="status-banner {cls}">⚠ {text}</div>'
    if findings:
        h += f'<div class="findings-box"><span class="lbl">What we learned</span>{html.escape(findings)}</div>'
    return h


GRID_CSS = """
.eg-bar{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:10px 0 16px;
font-size:11px;color:var(--dim)}
.eg-sort{background:var(--paper-dim);border:1px solid var(--rule);color:var(--body);
padding:4px 9px;cursor:pointer;border-radius:2px;font-family:var(--mono);font-size:11px}
.eg-sort.on{background:var(--edge);color:#fff;border-color:var(--edge)}
.eg-view{background:var(--paper-dim);border:1px solid var(--rule);color:var(--edge-ink);
padding:4px 9px;cursor:pointer;border-radius:2px;font-family:var(--mono);font-size:11px;margin-left:auto}
.eg-info{border:1px solid var(--rule);border-left:3px solid var(--edge);background:#fff;
padding:8px 12px;margin:0 0 14px;font-size:11.5px;color:var(--body)}
.eg-info b{color:var(--ink)}
.eg-block{margin:0 0 18px}
.eg-glabel{font-size:11px;color:var(--dim);margin:0 0 4px}
.eg-glabel .corr{color:var(--edge-ink)}
.eg-row{display:flex;align-items:center;gap:5px;margin:2px 0;flex-wrap:wrap}
.eg-plabel{width:190px;flex:0 0 auto;font-size:10.5px;color:var(--faint);
overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.eg-cell{position:relative;font-family:var(--mono);font-size:11px;color:#1a1a1a;
padding:6px 10px;cursor:pointer;border-radius:2px;min-width:38px;text-align:center;
border:1px solid rgba(0,0,0,.15)}
.eg-cell.playing{outline:2px solid var(--edge-ink)}
.eg-badge{position:absolute;top:-4px;right:-4px;width:9px;height:9px;border-radius:50%;
border:1px solid #fff}
.eg-table{border-collapse:collapse;font-size:11px;width:100%}
.eg-table td,.eg-table th{border:1px solid var(--rule);padding:4px 8px;text-align:right}
.eg-table th{background:var(--paper-dim);color:var(--dim);font-weight:600}
.eg-table td:first-child,.eg-table th:first-child{text-align:left}
.eg-table tr.eg-cell{cursor:pointer}
"""

GRID_JS_TEMPLATE = r"""
(function(){
const D = __DATA__;
const wrap = document.getElementById(__WRAP_ID__);
const audio = new Audio(); let curEl = null, curKey = null, playhead = 0;
audio.addEventListener('timeupdate', () => { if (!audio.paused) playhead = audio.currentTime; });
audio.addEventListener('ended', () => { if (curEl) curEl.classList.remove('playing'); curEl = null; curKey = null; });

function seekAndPlay(a, pos) {
  // Seeking as soon as metadata loads (readyState>=1/HAVE_METADATA) can seek
  // into a not-yet-buffered part of a compressed stream and produce an
  // audible stutter/glitch right at playback start (Kim, 2026-07-07). Wait
  // for readyState>=3 (HAVE_FUTURE_DATA -- enough buffered to play forward
  // without stalling) or the 'canplay' event, whichever comes first; a
  // fallback timer keeps this from hanging if neither fires.
  const go = () => { try { a.currentTime = ((a.duration && pos > a.duration - 1) ? 0 : Math.min(pos, (a.duration || 1e9) - 0.05)); } catch (e) {} a.play(); };
  if (a.readyState >= 3) { go(); return; }
  let done = false;
  const fire = () => { if (done) return; done = true; go(); };
  a.addEventListener('canplay', fire, { once: true });
  setTimeout(fire, 1200);
}
function play(el, key, src, label) {
  if (!src) return;
  if (curKey === key) { audio.pause(); el.classList.remove('playing'); curEl = null; curKey = null; return; }
  if (curEl) curEl.classList.remove('playing');
  curEl = el; curKey = key; el.classList.add('playing');
  audio.pause();
  audio.src = src;
  seekAndPlay(audio, playhead);
  showInfo(label);
}
function showInfo(label) {
  const box = document.getElementById(__INFO_ID__);
  box.textContent = label;
}

const METRICS = {
  measured:  { label: 'onset density', get: r => r.measured, dir: 1, heat: 'measured' },
  gain:      { label: 'gain',          get: r => r.gain,     dir: 1, heat: 'plain' },
  density:   { label: 'density',       get: r => r.density,  dir: 1, heat: 'plain' },
  CE:        { label: 'content enjoyment', get: r => r.CE,   dir: -1, heat: 'ce' },
  error:     { label: '|error|',       get: r => r.error_delta == null ? null : Math.abs(r.error_delta), dir: 1, heat: 'error' },
  spectral_balance: { label: 'spectral balance', get: r => r.spectral_balance, dir: -1, heat: 'sb' },
};
let activeMetric = 'measured';
let rankedMode = true;  // sortable table is the default view (Kim, 2026-07-06) -- the heatmap is a toggle-away alternate, not the entry point

function colorFor(r, metricKey) {
  const m = METRICS[metricKey];
  const v = m.get(r);
  if (v == null) return '#eee';
  if (m.heat === 'measured') { const t = Math.max(0, Math.min(1, v / 14)); return `hsl(${Math.round(t * 130)},55%,72%)`; }
  if (m.heat === 'ce') { const t = Math.max(0, Math.min(1, v / 10)); return `hsl(${Math.round(t * 130)},55%,72%)`; }
  if (m.heat === 'error') { const t = Math.max(0, Math.min(1, v / 8)); return `hsl(${Math.round((1 - t) * 130)},55%,72%)`; }
  if (m.heat === 'sb') { const t = Math.max(0, Math.min(1, v / 0.4)); return `hsl(${Math.round(t * 45 + 200)},55%,78%)`; }
  return '#eee';
}
function badgeColor(r) {
  if (r.broke) return '#c0392b';
  if (r.CE == null) return 'transparent';
  if (r.CE >= 6.5) return '#2e8b57';
  if (r.CE >= 5.0) return '#c9a227';
  return '#c0392b';
}
function badgeTip(r) {
  const f = v => v == null ? '·' : v.toFixed(1);
  return `CE ${f(r.CE)} · PC ${f(r.PC)} · PQ ${f(r.PQ)}`;
}
function fmtVal(r) {
  const v = METRICS[activeMetric].get(r);
  return v == null ? '·' : (Math.abs(v) < 10 ? v.toFixed(2) : v.toFixed(1));
}
function cellLabel(r) {
  return `${r.prompt ? r.prompt + ' · ' : ''}g${r.gain} d${r.density} -> ${r.measured == null ? '·' : r.measured.toFixed(2)}`
    + (r.CE != null ? ` · CE ${r.CE.toFixed(1)}` : '');
}

function corrOf(rows) {
  const xs = rows.map(r => r.density), ys = rows.map(r => r.measured).filter((v,i)=>rows[i].measured!=null);
  const pairs = rows.filter(r => r.measured != null);
  if (pairs.length < 2) return null;
  const mx = pairs.reduce((a,r)=>a+r.density,0)/pairs.length, my = pairs.reduce((a,r)=>a+r.measured,0)/pairs.length;
  let cov=0, vx=0, vy=0;
  pairs.forEach(r => { const dx=r.density-mx, dy=r.measured-my; cov+=dx*dy; vx+=dx*dx; vy+=dy*dy; });
  if (vx===0||vy===0) return null;
  return cov/Math.sqrt(vx*vy);
}

function cellEl(r, idx) {
  const key = 'c'+idx;
  const el = document.createElement('span');
  el.className = 'eg-cell';
  el.style.background = colorFor(r, activeMetric);
  el.dataset.key = key;
  el.innerHTML = `${fmtVal(r)}<span class="eg-badge" style="background:${badgeColor(r)}" title="${badgeTip(r)}"></span>`;
  el.title = badgeTip(r) + (r.clip ? '' : ' (no clip)');
  el.onclick = () => play(el, key, r.clip, cellLabel(r));
  return el;
}

function renderGrid() {
  wrap.innerHTML = '';
  const gains = [...new Set(D.map(r => r.gain))].sort((a,b)=>a-b);
  gains.forEach(g => {
    const gRows = D.filter(r => r.gain === g);
    const prompts = [...new Set(gRows.map(r => r.prompt_idx))];
    const block = document.createElement('div'); block.className = 'eg-block';
    const corr = corrOf(gRows);
    const label = document.createElement('div'); label.className = 'eg-glabel';
    label.innerHTML = `gain ${g} &nbsp; <span class="corr">corr ${corr==null?'·':corr.toFixed(2)}</span>`;
    block.appendChild(label);
    prompts.forEach(pi => {
      const pRows = gRows.filter(r => r.prompt_idx === pi).sort((a,b)=>a.density-b.density);
      const row = document.createElement('div'); row.className = 'eg-row';
      if (pi != null) {
        const pl = document.createElement('span'); pl.className = 'eg-plabel';
        pl.textContent = pRows[0].prompt || ('prompt ' + pi); pl.title = pl.textContent;
        row.appendChild(pl);
      }
      pRows.forEach((r) => row.appendChild(cellEl(r, D.indexOf(r))));
      block.appendChild(row);
    });
    wrap.appendChild(block);
  });
}

// Excel-style sortable table (2026-07-06, human-first spec, reused here for
// control grids per Kim: the heatmap-only view is dense/hard to scan -- this
// gives the same clips as a click-to-sort table with per-column colour
// grading, self-normalized over the whole page since a grid page is always
// one checkpoint). Columns intentionally superset the METRICS bar above.
const TABLE_COLS = [
  { key: 'prompt', label: 'prompt', get: r => r.prompt, kind: 'str' },
  { key: 'seed', label: 'seed', get: r => r.seed, kind: 'num' },
  { key: 'gain', label: 'gain', get: r => r.gain, kind: 'num' },
  { key: 'density', label: 'density', get: r => r.density, kind: 'num' },
  { key: 'measured', label: 'measured', get: r => r.measured, kind: 'num' },
  { key: 'error_delta', label: 'error', get: r => r.error_delta, kind: 'num' },
  { key: 'CE', label: 'CE', get: r => r.CE, kind: 'num' },
  { key: 'CU', label: 'CU', get: r => r.CU, kind: 'num' },
  { key: 'PC', label: 'PC', get: r => r.PC, kind: 'num' },
  { key: 'PQ', label: 'PQ', get: r => r.PQ, kind: 'num' },
  { key: 'spectral_balance', label: 'spectral bal.', get: r => r.spectral_balance, kind: 'num' },
];
let tableSort = { col: 'measured', dir: -1 };

function tableRange(col) {
  const vals = D.map(col.get).filter(v => v != null);
  return vals.length ? [Math.min(...vals), Math.max(...vals)] : null;
}
function tableColorFor(v, range) {
  if (v == null || !range) return '#eee';
  const [lo, hi] = range;
  const t = hi > lo ? (v - lo) / (hi - lo) : 0.5;
  return `hsl(${Math.round(t * 130)},50%,80%)`;
}
function renderRanked() {
  wrap.innerHTML = '';
  const col = TABLE_COLS.find(c => c.key === tableSort.col);
  const dir = tableSort.dir;
  const rows = D.slice().sort((a, b) => {
    const va = col.get(a), vb = col.get(b);
    if (va == null && vb == null) return 0;
    if (va == null) return 1;
    if (vb == null) return -1;
    return col.kind === 'str' ? dir * String(va).localeCompare(String(vb)) : dir * (va - vb);
  });
  const ranges = {}; TABLE_COLS.forEach(c => { if (c.kind === 'num') ranges[c.key] = tableRange(c); });
  const table = document.createElement('table'); table.className = 'tc-table';
  const headRow = document.createElement('tr');
  TABLE_COLS.forEach(c => {
    const on = tableSort.col === c.key;
    const arrow = on ? (dir === 1 ? '↑' : '↓') : '';
    const th = document.createElement('th');
    th.className = on ? 'on' : '';
    th.innerHTML = `${c.label} <span class="arrow">${arrow}</span>`;
    th.onclick = () => {
      tableSort = { col: c.key, dir: tableSort.col === c.key ? -tableSort.dir : -1 };
      renderRanked();
    };
    headRow.appendChild(th);
  });
  headRow.appendChild(document.createElement('th'));
  table.appendChild(headRow);
  rows.forEach((r) => {
    const idx = D.indexOf(r);
    const tr = document.createElement('tr'); tr.dataset.key = 'c' + idx;
    let cells = '';
    TABLE_COLS.forEach(c => {
      const v = c.get(r);
      const style = (c.kind === 'num' && ranges[c.key]) ? ` style="background:${tableColorFor(v, ranges[c.key])}"` : '';
      const text = v == null ? '·' : (typeof v === 'number' ? (Math.abs(v) < 10 ? v.toFixed(2) : v.toFixed(1)) : v);
      cells += `<td${style}>${text}</td>`;
    });
    tr.innerHTML = cells + '<td class="tc-play">▶</td>';
    tr.onclick = () => play(tr, 'c' + idx, r.clip, cellLabel(r));
    table.appendChild(tr);
  });
  wrap.appendChild(table);
}

function render() { rankedMode ? renderRanked() : renderGrid(); }

document.querySelectorAll('.eg-sort').forEach(btn => {
  btn.onclick = () => {
    document.querySelectorAll('.eg-sort').forEach(b => b.classList.remove('on'));
    btn.classList.add('on');
    activeMetric = btn.dataset.metric;
    render();
  };
});
document.getElementById(__VIEW_TOGGLE_ID__).onclick = (e) => {
  rankedMode = !rankedMode;
  e.target.textContent = rankedMode ? '☰ grid view' : '⊞ sortable table';
  render();
};
render();
})();
"""


def render_grid_page(*, head_html: str, css_extra: str, title: str, label: str,
                      purpose: str, date_str: str, records: list[dict],
                      footer_html: str, findings: str = None, status: str = None,
                      known_pages: dict = None) -> str:
    """Build a full standalone HTML page for one grid-style eval dir.

    head_html: pre-rendered <head>...<body><div class="wrap"> prologue (caller's
    head()/CSS, so this stays visually consistent with whatever site it's embedded in).
    """
    n_scored = sum(1 for r in records if r["CE"] is not None)
    doc = head_html
    doc += f'<h1>{html.escape(label)}</h1>'
    if date_str:
        doc += f'<p class="faint">{html.escape(date_str)}</p>'
    if purpose:
        doc += f'<p class="lede">{html.escape(purpose)}</p>'
    doc += provenance_html(findings, status, known_pages)
    doc += (f'<p class="faint">{len(records)} clips, ONE checkpoint (this page is a single trained '
            'adapter) · rows vary by prompt / seed / gain / density -- not by checkpoint · '
            'click any column header to sort · click a row to play (shared playhead) · '
            'switch to the gain×density heatmap to see the response SHAPE instead of the numbers</p>')
    doc += '<div class="eg-bar">'
    doc += '<span class="faint" style="margin-right:6px">heatmap colours by:</span>'
    for key, lbl in (("measured", "onset density"), ("gain", "gain"), ("density", "density"),
                      ("CE", "content enjoyment"), ("error", "error delta"),
                      ("spectral_balance", "spectral balance")):
        cls = "eg-sort on" if key == "measured" else "eg-sort"
        doc += f'<span class="{cls}" data-metric="{key}">{html.escape(lbl)}</span>'
    doc += '<span class="eg-view" id="eg-view-toggle">☰ gain×density grid</span>'
    doc += '</div>'
    doc += '<div class="eg-info" id="eg-info">click a cell for its readout</div>'
    doc += '<div id="eg-wrap"></div>'
    data_json = json.dumps(records)
    js = (GRID_JS_TEMPLATE
          .replace("__DATA__", data_json)
          .replace("__WRAP_ID__", "'eg-wrap'")
          .replace("__INFO_ID__", "'eg-info'")
          .replace("__VIEW_TOGGLE_ID__", "'eg-view-toggle'"))
    doc += f'<script>{js}</script>'
    doc += footer_html
    return doc


def load_grid_data(source_dir: str, clip_lookup) -> list[dict] | None:
    """Load + merge onset_eval.json (+ optional pq_scores.json) from source_dir.
    Returns None if onset_eval.json is absent (not a grid dir)."""
    oe_path = os.path.join(source_dir, "onset_eval.json")
    if not os.path.exists(oe_path):
        return None
    try:
        onset_rows = json.load(open(oe_path))
    except Exception:
        return None
    pq_rows = []
    pq_path = os.path.join(source_dir, "pq_scores.json")
    if os.path.exists(pq_path):
        try:
            pq_rows = json.load(open(pq_path))
        except Exception:
            pq_rows = []
    run_name = os.path.basename(source_dir.rstrip("/"))
    return merge_records(run_name, onset_rows, pq_rows, clip_lookup)


# ── human-first sortable table + dual-checkpoint compare (2026-07-06 spec) ────
# Two tables (side-by-side desktop / stacked phone), each with its own checkpoint
# dropdown, showing the SAME param-combo rows (prompt x seed) in the SAME order.
# Sorting either table's column reorders both (Kim's design: read straight across
# to compare checkpoint A vs B for the same combo). Per-column colour grading is
# self-normalized to the shown checkpoint's realized range (deliberately NOT
# comparable across checkpoints — the ear is the final arbiter, this is just a
# glance-level "where does this sit in its own spread" cue).
TABLE_CSS = """
.tc-wrap{margin:6px 0 18px;width:min(2200px,94vw);position:relative;left:50%;transform:translateX(-50%);box-sizing:border-box}
.tc-panes{display:grid;grid-template-columns:1fr 1fr;gap:18px}
@media (max-width:820px){.tc-panes{grid-template-columns:1fr}}
.tc-pane{border:1px solid var(--rule);background:#fff;padding:10px 12px}
.tc-pane select{font-family:var(--mono);font-size:11.5px;color:var(--ink);
background:var(--paper-dim);border:1px solid var(--rule);padding:5px 8px;
width:100%;margin:0 0 10px;border-radius:2px}
.tc-table{border-collapse:collapse;font-size:12px;width:100%}
.tc-table td,.tc-table th{border:1px solid var(--rule);padding:5px 8px;text-align:right;
white-space:nowrap}
.tc-table th{background:var(--paper-dim);color:var(--dim);font-weight:600;cursor:pointer;
user-select:none}
.tc-table th.on{color:var(--edge-ink)}
.tc-table th.on .arrow{color:var(--edge)}
.tc-table td:first-child,.tc-table th:first-child{text-align:left;white-space:normal;max-width:220px}
.tc-table td.tc-play{cursor:pointer;text-align:center;width:24px}
.tc-table tr.playing td.tc-play{color:var(--edge-ink);font-weight:700}
.tc-table td.tc-blank{color:var(--faint)}
.tc-meta{font-size:10.5px;color:var(--faint);margin:0 0 8px}
.tc-table tr.tc-sweet td:first-child{background:var(--edge);color:#fff;font-weight:700}
.tc-table tr.tc-sweet td:first-child::after{content:" \2605";font-size:9px}
.prompt-legend{font-size:11.5px;color:var(--body);margin:4px 0 8px;background:var(--paper-dim);
  border-radius:6px;padding:6px 10px}
.prompt-legend b{color:var(--ink)}
.prompt-legend ul{margin:4px 0 0;padding-left:18px}
.prompt-legend li{margin:1px 0}
.prompt-legend code{background:var(--paper);border-radius:3px;padding:0 3px}
"""

TABLE_JS_TEMPLATE = r"""
(function(){
const D = __DATA__;
const CHECKPOINTS = __CHECKPOINTS__;   // [{tag, label}], sorted
const ROW_KEYS = __ROW_KEYS__;         // [[prompt_idx, seed], ...]
const COLS = [
  {key:'prompt', label:'prompt', get:r=>r.prompt, kind:'str'},
  {key:'seed',   label:'seed',   get:r=>r.seed,   kind:'num'},
  {key:'CE',     label:'CE',     get:r=>r.CE,     kind:'num'},
  {key:'CU',     label:'CU',     get:r=>r.CU,     kind:'num'},
  {key:'PC',     label:'PC',     get:r=>r.PC,     kind:'num'},
  {key:'PQ',     label:'PQ',     get:r=>r.PQ,     kind:'num'},
  {key:'spectral_balance', label:'spectral bal.', get:r=>r.spectral_balance, kind:'num'},
];
const byCombo = {}; // checkpoint -> "pi|seed" -> record
D.forEach(r => {
  (byCombo[r.checkpoint] ||= {})[r.prompt_idx + '|' + r.seed] = r;
});
function rowsFor(checkpoint) {
  const m = byCombo[checkpoint] || {};
  return ROW_KEYS.map(([pi, seed]) => m[pi + '|' + seed] || null);
}

const audio = new Audio(); let curKey = null, curRow = null;
audio.addEventListener('ended', () => { markPlaying(null); curKey = null; });
function markPlaying(key) {
  document.querySelectorAll('.tc-table tr[data-key]').forEach(tr => {
    tr.classList.toggle('playing', tr.dataset.key === key && key !== null);
  });
}
function seekAndPlay(a, pos) {
  // Seeking as soon as metadata loads can land on a not-yet-buffered part of
  // a compressed stream and glitch right at playback start (Kim, 2026-07-07).
  // Wait for readyState>=3 (HAVE_FUTURE_DATA) or 'canplay', whichever first;
  // a fallback timer keeps this from hanging if neither fires.
  const go = () => { try { a.currentTime = ((a.duration && pos > a.duration - 1) ? 0 : Math.min(pos, (a.duration || 1e9) - 0.05)); } catch (e) {} a.play(); };
  if (a.readyState >= 3) { go(); return; }
  let done = false;
  const fire = () => { if (done) return; done = true; go(); };
  a.addEventListener('canplay', fire, { once: true });
  setTimeout(fire, 1200);
}
function play(key, src, label) {
  if (!src) return;
  if (curKey === key) { audio.pause(); markPlaying(null); curKey = null; return; }
  const pos = (curKey !== null && !audio.paused) ? audio.currentTime : 0;
  curKey = key; markPlaying(key);
  audio.pause();
  audio.src = src;
  seekAndPlay(audio, pos);
  document.getElementById(__INFO_ID__).textContent = label;
}

let order = ROW_KEYS.map((_, i) => i);
let sort = { col: 'CE', dir: -1, src: 'a' };
let sel = { a: __DEFAULT_A__, b: __DEFAULT_B__ };

function realizedRange(checkpoint, col) {
  const rows = rowsFor(checkpoint).filter(Boolean);
  const vals = rows.map(col.get).filter(v => v != null);
  if (!vals.length) return null;
  return [Math.min(...vals), Math.max(...vals)];
}
function colorFor(v, range) {
  if (v == null || !range) return '#eee';
  const [lo, hi] = range;
  const t = hi > lo ? (v - lo) / (hi - lo) : 0.5;
  return `hsl(${Math.round(t * 130)},50%,80%)`;
}

function resort(pane, colKey) {
  const col = COLS.find(c => c.key === colKey);
  const dir = (sort.col === colKey && sort.src === pane) ? -sort.dir : -1;
  sort = { col: colKey, dir, src: pane };
  const checkpoint = sel[pane];
  const rows = rowsFor(checkpoint);
  order = ROW_KEYS.map((_, i) => i).sort((ia, ib) => {
    const ra = rows[ia], rb = rows[ib];
    const va = ra ? col.get(ra) : null, vb = rb ? col.get(rb) : null;
    if (va == null && vb == null) return 0;
    if (va == null) return 1;
    if (vb == null) return -1;
    if (col.kind === 'str') return dir * String(va).localeCompare(String(vb));
    return dir * (va - vb);
  });
  renderBoth();
}

function renderPane(pane) {
  const el = document.getElementById('tc-pane-' + pane);
  const checkpoint = sel[pane];
  const rows = rowsFor(checkpoint);
  const ranges = {}; COLS.forEach(c => { if (c.kind === 'num') ranges[c.key] = realizedRange(checkpoint, c); });
  let h = `<select onchange="window.__tcSelect('${pane}', this.value)">`;
  CHECKPOINTS.forEach(c => { h += `<option value="${c.tag}"${c.tag === checkpoint ? ' selected' : ''}>${c.label}</option>`; });
  h += '</select>';
  const nScored = rows.filter(r => r && r.CE != null).length;
  h += `<p class="tc-meta">${rows.filter(Boolean).length} clips (${nScored} scored)</p>`;
  h += '<table class="tc-table"><tr><th></th>';
  COLS.forEach(c => {
    const on = sort.col === c.key && sort.src === pane;
    const arrow = on ? (sort.dir === 1 ? '↑' : '↓') : '';
    h += `<th class="${on ? 'on' : ''}" onclick="window.__tcSort('${pane}','${c.key}')">${c.label} <span class="arrow">${arrow}</span></th>`;
  });
  h += '</tr>';
  order.forEach(i => {
    const r = rows[i];
    const key = pane + '-' + i;
    if (!r) { h += `<tr data-key="${key}"><td class="tc-blank">·</td>` + COLS.map(() => '<td class="tc-blank">·</td>').join('') + '</tr>'; return; }
    const label = `${checkpoint} · ${r.prompt || 'p' + r.prompt_idx} · seed${r.seed}`;
    h += `<tr data-key="${key}" onclick="window.__tcPlay('${key}', ${JSON.stringify(r.clip)}, ${JSON.stringify(label)})"><td class="tc-play">▶</td>`;
    COLS.forEach(c => {
      const v = c.get(r);
      const style = (c.kind === 'num' && ranges[c.key]) ? ` style="background:${colorFor(v, ranges[c.key])}"` : '';
      const text = v == null ? '·' : (typeof v === 'number' ? (Math.abs(v) < 10 ? v.toFixed(2) : v.toFixed(1)) : v);
      h += `<td${style}>${text}</td>`;
    });
    h += '</tr>';
  });
  h += '</table>';
  el.innerHTML = h;
}
function renderBoth() { renderPane('a'); renderPane('b'); }

window.__tcSelect = (pane, tag) => { sel[pane] = tag; renderBoth(); };
window.__tcSort = (pane, col) => resort(pane, col);
window.__tcPlay = (key, src, label) => play(key, src, label);

renderBoth();
})();
"""


# ── epoch-progression dual-pane (2026-07-07) ──────────────────────────────────
# For unscored checkpoint sweeps (no pq_scores.json/Audiobox pass yet) where the
# comparison axis IS training progress -- e.g. every epoch of a run vs a single
# pinned Hall-of-Fame reference checkpoint. Same dual-pane-by-prompt mechanic as
# render_table_compare_page, but without the CE/CU/PC/PQ columns (which would
# just show empty "·" for every row here) -- prompt/seed/play only.
def load_epoch_progress_data(source_dir: str, clip_lookup) -> list[dict] | None:
    """Parse `{checkpoint_tag}__p{N}_seed{S}.wav` filenames directly (no
    pq_scores.json needed -- these are raw, unscored renders). checkpoint_tag
    is everything before the first `__` (may itself contain `-` / `_`, e.g.
    `dora16_goa_newstack_8ep_epoch3-step5400` or `x20b3ygb_epoch3-step5400`)."""
    stem_re = re.compile(r"^(?P<ck>.+)__p(?P<pi>\d+)_seed(?P<seed>\d+)$")
    out = []
    for f in os.listdir(source_dir):
        if not f.endswith(".wav"):
            continue
        stem = f[:-4]
        m = stem_re.match(stem)
        if not m:
            continue
        out.append({
            "checkpoint": m["ck"], "prompt_idx": int(m["pi"]), "prompt": None,
            "seed": int(m["seed"]), "clip": clip_lookup(stem),
        })
    return out or None


EPOCH_PROGRESS_JS_TEMPLATE = r"""
(function(){
const D = __DATA__;
const CHECKPOINTS = __CHECKPOINTS__;   // [{tag, label}], sorted
const ROW_KEYS = __ROW_KEYS__;         // [[prompt_idx, seed], ...]
const byCombo = {};
D.forEach(r => { (byCombo[r.checkpoint] ||= {})[r.prompt_idx + '|' + r.seed] = r; });
function rowsFor(checkpoint) {
  const m = byCombo[checkpoint] || {};
  return ROW_KEYS.map(([pi, seed]) => m[pi + '|' + seed] || null);
}

const audio = new Audio(); let curKey = null;
audio.addEventListener('ended', () => { markPlaying(null); curKey = null; });
function markPlaying(key) {
  document.querySelectorAll('.tc-table tr[data-key]').forEach(tr => {
    tr.classList.toggle('playing', tr.dataset.key === key && key !== null);
  });
}
function seekAndPlay(a, pos) {
  const go = () => { try { a.currentTime = ((a.duration && pos > a.duration - 1) ? 0 : Math.min(pos, (a.duration || 1e9) - 0.05)); } catch (e) {} a.play(); };
  if (a.readyState >= 3) { go(); return; }
  let done = false;
  const fire = () => { if (done) return; done = true; go(); };
  a.addEventListener('canplay', fire, { once: true });
  setTimeout(fire, 1200);
}
function play(key, src, label) {
  if (!src) return;
  if (curKey === key) { audio.pause(); markPlaying(null); curKey = null; return; }
  const pos = (curKey !== null && !audio.paused) ? audio.currentTime : 0;
  curKey = key; markPlaying(key);
  audio.pause();
  audio.src = src;
  seekAndPlay(audio, pos);
  document.getElementById(__INFO_ID__).textContent = label;
}

let sel = { a: __DEFAULT_A__, b: __DEFAULT_B__ };

function renderPane(pane) {
  const el = document.getElementById('tc-pane-' + pane);
  const checkpoint = sel[pane];
  const rows = rowsFor(checkpoint);
  let h = `<select onchange="window.__epSelect('${pane}', this.value)">`;
  CHECKPOINTS.forEach(c => { h += `<option value="${c.tag}"${c.tag === checkpoint ? ' selected' : ''}>${c.label}</option>`; });
  h += '</select>';
  h += `<p class="tc-meta">${rows.filter(Boolean).length} clips</p>`;
  h += '<table class="tc-table"><tr><th>prompt</th><th>seed</th><th></th></tr>';
  ROW_KEYS.forEach(([pi, seed], i) => {
    const r = rows[i];
    const key = pane + '-' + i;
    if (!r) { h += `<tr data-key="${key}"><td class="tc-blank">·</td><td class="tc-blank">·</td><td class="tc-blank">·</td></tr>`; return; }
    const label = `${checkpoint} · p${pi} · seed${seed}`;
    h += `<tr data-key="${key}" onclick="window.__epPlay('${key}', ${JSON.stringify(r.clip)}, ${JSON.stringify(label)})">`
       + `<td>${r.prompt || ('prompt ' + pi)}</td><td>${seed}</td><td class="tc-play">▶</td></tr>`;
  });
  h += '</table>';
  el.innerHTML = h;
}
function renderBoth() { renderPane('a'); renderPane('b'); }
window.__epSelect = (pane, tag) => { sel[pane] = tag; renderBoth(); };
window.__epPlay = (key, src, label) => play(key, src, label);
renderBoth();
})();
"""


def render_epoch_progress_page(*, head_html: str, title: str, label: str, purpose: str,
                                date_str: str, records: list[dict], footer_html: str,
                                prompt_text: dict = None, pinned_tag: str = None,
                                default_a: str = None,
                                findings: str = None, status: str = None,
                                known_pages: dict = None) -> str:
    """Dual-pane compare for an unscored epoch-progression sweep: pane A scrubs
    through checkpoints (default: the requested default_a, e.g. the LAST
    epoch), pane B defaults to a pinned reference checkpoint (e.g. the
    Hall-of-Fame pick) -- both panes stay freely switchable, "pinned" just
    means that's where it starts. No CE/CU/PC/PQ columns since there's no
    pq_scores.json here (raw, unscored renders)."""
    if prompt_text:
        for r in records:
            r["prompt"] = prompt_text[r["prompt_idx"]] if r["prompt_idx"] < len(prompt_text) else None
    checkpoints = sorted({r["checkpoint"] for r in records})
    ck_objs = [{"tag": t, "label": t} for t in checkpoints]
    row_keys = sorted({(r["prompt_idx"], r["seed"]) for r in records})
    default_a = default_a if default_a in checkpoints else (checkpoints[0] if checkpoints else None)
    default_b = pinned_tag if pinned_tag in checkpoints else (checkpoints[-1] if len(checkpoints) > 1 else default_a)

    doc = head_html
    doc += f'<h1>{html.escape(label)}</h1>'
    if date_str:
        doc += f'<p class="faint">{html.escape(date_str)}</p>'
    if purpose:
        doc += f'<p class="lede">{html.escape(purpose)}</p>'
    doc += provenance_html(findings, status, known_pages)
    doc += (f'<p class="faint">{len(checkpoints)} checkpoints · {len(records)} clips, unscored (no Audiobox '
            'pass yet) · pane B defaults to the pinned reference checkpoint · pick any checkpoint per pane, '
            'click a row to play (shared playhead)</p>')
    doc += '<div class="tc-wrap"><div class="eg-info" id="tc-info">click a row for its readout</div>'
    doc += '<div class="tc-panes"><div class="tc-pane" id="tc-pane-a"></div><div class="tc-pane" id="tc-pane-b"></div></div></div>'
    js = (EPOCH_PROGRESS_JS_TEMPLATE
          .replace("__DATA__", json.dumps(records))
          .replace("__CHECKPOINTS__", json.dumps(ck_objs))
          .replace("__ROW_KEYS__", json.dumps(row_keys))
          .replace("__DEFAULT_A__", json.dumps(default_a))
          .replace("__DEFAULT_B__", json.dumps(default_b))
          .replace("__INFO_ID__", "'tc-info'"))
    doc += f'<script>{js}</script>'
    doc += footer_html
    return doc


def render_table_compare_page(*, head_html: str, title: str, label: str, purpose: str,
                               date_str: str, records: list[dict], footer_html: str,
                               findings: str = None, status: str = None,
                               known_pages: dict = None) -> str:
    """Dual-pane sortable-table checkpoint comparison (2026-07-06 human-first spec).
    records: flat list from load_dora_data() (or any loader whose rows carry a
    `checkpoint` key + prompt_idx/seed as the row-identity axis)."""
    checkpoints = sorted({r["checkpoint"] for r in records})

    def ck_label(tag):
        rs = [r for r in records if r["checkpoint"] == tag]
        run_label = rs[0].get("run_label") or ""
        epoch = rs[0].get("epoch")
        step = rs[0].get("step")
        bits = [b for b in (run_label, f"ep{epoch}" if epoch is not None else None) if b]
        lbl = " · ".join(bits) if bits else tag
        if step is not None:
            lbl += f" (step {step})"
        return lbl

    ck_objs = [{"tag": t, "label": ck_label(t)} for t in checkpoints]
    row_keys = sorted({(r["prompt_idx"], r["seed"]) for r in records},
                       key=lambda k: (k[0] if k[0] is not None else -1, k[1] if k[1] is not None else -1))
    default_a = checkpoints[0] if checkpoints else None
    default_b = checkpoints[-1] if len(checkpoints) > 1 else default_a

    n_scored = sum(1 for r in records if r["CE"] is not None)
    doc = head_html
    doc += f'<h1>{html.escape(label)}</h1>'
    if date_str:
        doc += f'<p class="faint">{html.escape(date_str)}</p>'
    if purpose:
        doc += f'<p class="lede">{html.escape(purpose)}</p>'
    doc += provenance_html(findings, status, known_pages)
    doc += (f'<p class="faint">{len(checkpoints)} checkpoints · {len(records)} clips '
            f'({n_scored} quality-scored) · pick a checkpoint per pane, click a column '
            'header to sort (sorts both panes together) · click a row to play (shared '
            'playhead) · colour = min→max within the shown checkpoint only</p>')
    doc += '<div class="tc-wrap"><div class="eg-info" id="tc-info">click a row for its readout</div>'
    doc += '<div class="tc-panes"><div class="tc-pane" id="tc-pane-a"></div><div class="tc-pane" id="tc-pane-b"></div></div></div>'
    js = (TABLE_JS_TEMPLATE
          .replace("__DATA__", json.dumps(records))
          .replace("__CHECKPOINTS__", json.dumps(ck_objs))
          .replace("__ROW_KEYS__", json.dumps(row_keys))
          .replace("__DEFAULT_A__", json.dumps(default_a))
          .replace("__DEFAULT_B__", json.dumps(default_b))
          .replace("__INFO_ID__", "'tc-info'"))
    doc += f'<script>{js}</script>'
    doc += footer_html
    return doc


# ── prompt-style A/B compare (2026-07-07) ─────────────────────────────────────
# Dual-pane (arm A vs arm B, e.g. evr1x vs evr3x) LIKE render_table_compare_page,
# but each row is one (prompt, seed) combo showing PLAIN and STYLED side by
# side -- two play buttons + paired CE/PC columns + a delta -- since "the
# plain-vs-styled columns side by side per arm is the key comparison" (Kim,
# relayed by CONTINUITY 2026-07-06). Reuses .tc-panes/.tc-pane/.tc-table so no
# new CSS families are needed, just a couple of extra classes for the
# plain/styled column grouping and the delta cell.
STYLE_CSS = """
.tc-table td.sc-delta{font-weight:600}
.tc-table th.sc-plain,.tc-table td.sc-plain{border-left:2px solid var(--edge)}
.tc-table th.sc-styled,.tc-table td.sc-styled{border-left:2px solid var(--edge-ink)}
.tc-pane{overflow-x:auto}
"""

STYLE_JS_TEMPLATE = r"""
(function(){
const D = __DATA__;
const CHECKPOINTS = __CHECKPOINTS__;
const ROW_KEYS = __ROW_KEYS__;   // [[prompt_key, seed], ...]
const COLS = [
  {key:'prompt', label:'prompt', kind:'str'},
  {key:'seed', label:'seed', kind:'num'},
  {key:'play_plain', label:'▶ plain', kind:'play', variant:'plain'},
  {key:'CE_plain', label:'CE', kind:'num', variant:'plain'},
  {key:'PC_plain', label:'PC', kind:'num', variant:'plain'},
  {key:'play_styled', label:'▶ styled', kind:'play', variant:'styled'},
  {key:'CE_styled', label:'CE', kind:'num', variant:'styled'},
  {key:'PC_styled', label:'PC', kind:'num', variant:'styled'},
  {key:'delta_CE', label:'ΔCE (styled-plain)', kind:'num'},
];
const byCombo = {};
D.forEach(r => { (byCombo[r.checkpoint] ||= {})[r.prompt_key + '|' + r.seed] = r; });
function rowsFor(checkpoint) {
  const m = byCombo[checkpoint] || {};
  return ROW_KEYS.map(([pk, seed]) => m[pk + '|' + seed] || null);
}
function getVal(r, key) {
  if (!r) return null;
  if (key === 'prompt') return r.prompt_plain || r.prompt_key;
  if (key === 'seed') return r.seed;
  if (key === 'delta_CE') return (r.CE_styled == null || r.CE_plain == null) ? null : r.CE_styled - r.CE_plain;
  if (key.startsWith('play_')) return null;
  return r[key];
}

const audio = new Audio(); let curKey = null;
audio.addEventListener('ended', () => { markPlaying(null); curKey = null; });
function markPlaying(key) {
  document.querySelectorAll('.tc-table td[data-playkey]').forEach(td => {
    td.classList.toggle('playing', td.dataset.playkey === key && key !== null);
  });
}
function seekAndPlay(a, pos) {
  // Seeking as soon as metadata loads can land on a not-yet-buffered part of
  // a compressed stream and glitch right at playback start (Kim, 2026-07-07).
  // Wait for readyState>=3 (HAVE_FUTURE_DATA) or 'canplay', whichever first;
  // a fallback timer keeps this from hanging if neither fires.
  const go = () => { try { a.currentTime = ((a.duration && pos > a.duration - 1) ? 0 : Math.min(pos, (a.duration || 1e9) - 0.05)); } catch (e) {} a.play(); };
  if (a.readyState >= 3) { go(); return; }
  let done = false;
  const fire = () => { if (done) return; done = true; go(); };
  a.addEventListener('canplay', fire, { once: true });
  setTimeout(fire, 1200);
}
function play(key, src, label) {
  if (!src) return;
  if (curKey === key) { audio.pause(); markPlaying(null); curKey = null; return; }
  const pos = (curKey !== null && !audio.paused) ? audio.currentTime : 0;
  curKey = key; markPlaying(key);
  audio.pause();
  audio.src = src;
  seekAndPlay(audio, pos);
  document.getElementById(__INFO_ID__).textContent = label;
}

let order = ROW_KEYS.map((_, i) => i);
let sort = { col: 'CE_plain', dir: -1, src: 'a' };
let sel = { a: __DEFAULT_A__, b: __DEFAULT_B__ };

function realizedRange(checkpoint, key) {
  const rows = rowsFor(checkpoint).filter(Boolean);
  const vals = rows.map(r => getVal(r, key)).filter(v => v != null);
  return vals.length ? [Math.min(...vals), Math.max(...vals)] : null;
}
function colorFor(v, range) {
  if (v == null || !range) return '#eee';
  const [lo, hi] = range;
  const t = hi > lo ? (v - lo) / (hi - lo) : 0.5;
  return `hsl(${Math.round(t * 130)},50%,80%)`;
}

function resort(pane, colKey) {
  const dir = (sort.col === colKey && sort.src === pane) ? -sort.dir : -1;
  sort = { col: colKey, dir, src: pane };
  const checkpoint = sel[pane];
  const rows = rowsFor(checkpoint);
  order = ROW_KEYS.map((_, i) => i).sort((ia, ib) => {
    const va = getVal(rows[ia], colKey), vb = getVal(rows[ib], colKey);
    if (va == null && vb == null) return 0;
    if (va == null) return 1;
    if (vb == null) return -1;
    const kind = COLS.find(c => c.key === colKey).kind;
    return kind === 'str' ? dir * String(va).localeCompare(String(vb)) : dir * (va - vb);
  });
  renderBoth();
}

function fmtVal(v) {
  return v == null ? '·' : (typeof v === 'number' ? (Math.abs(v) < 10 ? v.toFixed(2) : v.toFixed(1)) : v);
}

function renderPane(pane) {
  const el = document.getElementById('tc-pane-' + pane);
  const checkpoint = sel[pane];
  const rows = rowsFor(checkpoint);
  const ranges = {};
  COLS.forEach(c => { if (c.kind === 'num') ranges[c.key] = realizedRange(checkpoint, c.key); });

  el.innerHTML = '';
  const select = document.createElement('select');
  CHECKPOINTS.forEach(c => {
    const opt = document.createElement('option');
    opt.value = c.tag; opt.textContent = c.label;
    if (c.tag === checkpoint) opt.selected = true;
    select.appendChild(opt);
  });
  select.onchange = () => { sel[pane] = select.value; renderBoth(); };
  el.appendChild(select);

  const nScored = rows.filter(r => r && r.CE_plain != null).length;
  const meta = document.createElement('p'); meta.className = 'tc-meta';
  meta.textContent = `${rows.filter(Boolean).length} combos (${nScored} scored)`;
  el.appendChild(meta);

  const table = document.createElement('table'); table.className = 'tc-table';
  const headRow = document.createElement('tr');
  COLS.forEach(c => {
    const on = sort.col === c.key;
    const arrow = on ? (sort.dir === 1 ? '↑' : '↓') : '';
    const th = document.createElement('th');
    if (c.variant) th.className = 'sc-' + c.variant;
    if (on) th.className = (th.className + ' on').trim();
    th.innerHTML = `${c.label} <span class="arrow">${arrow}</span>`;
    th.onclick = () => resort(pane, c.key);
    headRow.appendChild(th);
  });
  table.appendChild(headRow);

  order.forEach((i) => {
    const r = rows[i];
    const tr = document.createElement('tr');
    COLS.forEach(c => {
      const td = document.createElement('td');
      if (c.variant) td.className = 'sc-' + c.variant;
      if (c.kind === 'play') {
        const src = r ? (c.variant === 'plain' ? r.clip_plain : r.clip_styled) : null;
        const key = pane + '-' + i + '-' + c.variant;
        td.textContent = '▶';
        td.dataset.playkey = key;
        td.style.cursor = src ? 'pointer' : 'default';
        if (src) {
          const label = r ? `${checkpoint} · ${r.prompt_key} (${c.variant}) · seed${r.seed}` : '';
          td.onclick = () => play(key, src, label);
        }
      } else {
        const v = getVal(r, c.key);
        if (c.kind === 'num' && ranges[c.key]) td.style.background = colorFor(v, ranges[c.key]);
        td.textContent = fmtVal(v);
      }
      tr.appendChild(td);
    });
    table.appendChild(tr);
  });
  el.appendChild(table);
}
function renderBoth() { renderPane('a'); renderPane('b'); }
renderBoth();
})();
"""


def render_style_compare_page(*, head_html: str, title: str, label: str, purpose: str,
                               date_str: str, records: list[dict], footer_html: str,
                               findings: str = None, status: str = None,
                               known_pages: dict = None) -> str:
    """Dual-pane checkpoint (arm) compare where each row pairs a PLAIN and
    STYLED prompt variant side by side (2026-07-07 prompt-style A/B spec).
    records: flat list from load_promptstyle_data()."""
    checkpoints = sorted({r["checkpoint"] for r in records})
    ck_objs = [{"tag": t, "label": t} for t in checkpoints]
    row_keys = sorted({(r["prompt_key"], r["seed"]) for r in records})
    default_a = checkpoints[0] if checkpoints else None
    default_b = checkpoints[-1] if len(checkpoints) > 1 else default_a

    n_scored = sum(1 for r in records if r["CE_plain"] is not None or r["CE_styled"] is not None)
    doc = head_html
    doc += f'<h1>{html.escape(label)}</h1>'
    if date_str:
        doc += f'<p class="faint">{html.escape(date_str)}</p>'
    if purpose:
        doc += f'<p class="lede">{html.escape(purpose)}</p>'
    doc += provenance_html(findings, status, known_pages)
    doc += (f'<p class="faint">{len(checkpoints)} arms · {len(row_keys)} prompt×seed combos each '
            f'({len(records)} renders total, {n_scored} scored) · pick an arm per pane, click a column '
            'header to sort (syncs both panes) · click ▶ to play plain or styled (shared playhead) · '
            'colour = min→max within the shown arm only · ΔCE = styled minus plain '
            '(positive = styled scored higher)</p>')
    doc += '<div class="tc-wrap"><div class="eg-info" id="tc-info">click a ▶ for its readout</div>'
    doc += '<div class="tc-panes"><div class="tc-pane" id="tc-pane-a"></div><div class="tc-pane" id="tc-pane-b"></div></div></div>'
    js = (STYLE_JS_TEMPLATE
          .replace("__DATA__", json.dumps(records))
          .replace("__CHECKPOINTS__", json.dumps(ck_objs))
          .replace("__ROW_KEYS__", json.dumps(row_keys))
          .replace("__DEFAULT_A__", json.dumps(default_a))
          .replace("__DEFAULT_B__", json.dumps(default_b))
          .replace("__INFO_ID__", "'tc-info'"))
    doc += f'<script>{js}</script>'
    doc += footer_html
    return doc


# ── composed-sweep compare (2026-07-07) ───────────────────────────────────────
# Kim: "composed_sweep has NO eval page" -- A_cc/A_cc_v2/E_fusion/E_fusion_v2
# (control-DiT adapter +/- LatCH guidance, gain x density onset_eval.json grids)
# were each only reachable as their own generically-labeled landing entry
# ("Stage 1 cell E re-render..."), nothing said "composed sweep". Unlike the
# 64-checkpoint onset-control audit (independent unrelated experiments -> flat
# sortable table only), these 4 are directly comparable stages of ONE sweep and
# Kim explicitly wants "the full grid treatment (gain x density cells + corr
# coloring)" -- so this reuses the GRID heatmap/table view (not the audit's
# table-only view), with a dropdown across the 4 members instead of one fixed
# checkpoint per page.
COMPOSED_JS_TEMPLATE = r"""
(function(){
const D = __DATA__;
const MEMBERS = __MEMBERS__;
const wrap = document.getElementById(__WRAP_ID__);
const audio = new Audio(); let curEl = null, curKey = null, playhead = 0;
audio.addEventListener('timeupdate', () => { if (!audio.paused) playhead = audio.currentTime; });
audio.addEventListener('ended', () => { if (curEl) curEl.classList.remove('playing'); curEl = null; curKey = null; });

function seekAndPlay(a, pos) {
  const go = () => { try { a.currentTime = ((a.duration && pos > a.duration - 1) ? 0 : Math.min(pos, (a.duration || 1e9) - 0.05)); } catch (e) {} a.play(); };
  if (a.readyState >= 3) { go(); return; }
  let done = false;
  const fire = () => { if (done) return; done = true; go(); };
  a.addEventListener('canplay', fire, { once: true });
  setTimeout(fire, 1200);
}
function play(el, key, src, label) {
  if (!src) return;
  if (curKey === key) { audio.pause(); el.classList.remove('playing'); curEl = null; curKey = null; return; }
  if (curEl) curEl.classList.remove('playing');
  curEl = el; curKey = key; el.classList.add('playing');
  audio.pause();
  audio.src = src;
  seekAndPlay(audio, playhead);
  showInfo(label);
}
function showInfo(label) { document.getElementById(__INFO_ID__).textContent = label; }

const METRICS = {
  measured: { label: 'onset density', get: r => r.measured, heat: 'measured' },
  gain: { label: 'gain', get: r => r.gain, heat: 'plain' },
  density: { label: 'density', get: r => r.density, heat: 'plain' },
  CE: { label: 'content enjoyment', get: r => r.CE, heat: 'ce' },
  error: { label: '|error|', get: r => r.error_delta == null ? null : Math.abs(r.error_delta), heat: 'error' },
  spectral_balance: { label: 'spectral balance', get: r => r.spectral_balance, heat: 'sb' },
};
let activeMetric = 'measured';
let rankedMode = true;
let member = MEMBERS[0];

function colorFor(r, metricKey) {
  const m = METRICS[metricKey];
  const v = m.get(r);
  if (v == null) return '#eee';
  if (m.heat === 'measured') { const t = Math.max(0, Math.min(1, v / 14)); return `hsl(${Math.round(t * 130)},55%,72%)`; }
  if (m.heat === 'ce') { const t = Math.max(0, Math.min(1, v / 10)); return `hsl(${Math.round(t * 130)},55%,72%)`; }
  if (m.heat === 'error') { const t = Math.max(0, Math.min(1, v / 8)); return `hsl(${Math.round((1 - t) * 130)},55%,72%)`; }
  if (m.heat === 'sb') { const t = Math.max(0, Math.min(1, v / 0.4)); return `hsl(${Math.round(t * 45 + 200)},55%,78%)`; }
  return '#eee';
}
function badgeColor(r) {
  if (r.broke) return '#c0392b';
  if (r.CE == null) return 'transparent';
  if (r.CE >= 6.5) return '#2e8b57';
  if (r.CE >= 5.0) return '#c9a227';
  return '#c0392b';
}
function badgeTip(r) {
  const f = v => v == null ? '·' : v.toFixed(1);
  return `CE ${f(r.CE)} · PC ${f(r.PC)} · PQ ${f(r.PQ)}`;
}
function fmtVal(r) {
  const v = METRICS[activeMetric].get(r);
  return v == null ? '·' : (Math.abs(v) < 10 ? v.toFixed(2) : v.toFixed(1));
}
function cellLabel(r) {
  return `${member} · ${r.prompt ? r.prompt + ' · ' : ''}g${r.gain} d${r.density} -> ${r.measured == null ? '·' : r.measured.toFixed(2)}`
    + (r.CE != null ? ` · CE ${r.CE.toFixed(1)}` : '');
}
function corrOf(rows) {
  const pairs = rows.filter(r => r.measured != null);
  if (pairs.length < 2) return null;
  const mx = pairs.reduce((a,r)=>a+r.density,0)/pairs.length, my = pairs.reduce((a,r)=>a+r.measured,0)/pairs.length;
  let cov=0, vx=0, vy=0;
  pairs.forEach(r => { const dx=r.density-mx, dy=r.measured-my; cov+=dx*dy; vx+=dx*dx; vy+=dy*dy; });
  if (vx===0||vy===0) return null;
  return cov/Math.sqrt(vx*vy);
}
function cellEl(rows, r) {
  const idx = rows.indexOf(r);
  const key = member + '-c' + idx;
  const el = document.createElement('span');
  el.className = 'eg-cell';
  el.style.background = colorFor(r, activeMetric);
  el.innerHTML = `${fmtVal(r)}<span class="eg-badge" style="background:${badgeColor(r)}" title="${badgeTip(r)}"></span>`;
  el.title = badgeTip(r) + (r.clip ? '' : ' (no clip)');
  el.onclick = () => play(el, key, r.clip, cellLabel(r));
  return el;
}
function renderGrid(rows) {
  wrap.innerHTML = '';
  const gains = [...new Set(rows.map(r => r.gain))].sort((a,b)=>a-b);
  gains.forEach(g => {
    const gRows = rows.filter(r => r.gain === g);
    const prompts = [...new Set(gRows.map(r => r.prompt_idx))];
    const block = document.createElement('div'); block.className = 'eg-block';
    const corr = corrOf(gRows);
    const label = document.createElement('div'); label.className = 'eg-glabel';
    label.innerHTML = `gain ${g} &nbsp; <span class="corr">corr ${corr==null?'·':corr.toFixed(2)}</span>`;
    block.appendChild(label);
    prompts.forEach(pi => {
      const pRows = gRows.filter(r => r.prompt_idx === pi).sort((a,b)=>a.density-b.density);
      const row = document.createElement('div'); row.className = 'eg-row';
      if (pi != null) {
        const pl = document.createElement('span'); pl.className = 'eg-plabel';
        pl.textContent = pRows[0].prompt || ('prompt ' + pi); pl.title = pl.textContent;
        row.appendChild(pl);
      }
      pRows.forEach((r) => row.appendChild(cellEl(rows, r)));
      block.appendChild(row);
    });
    wrap.appendChild(block);
  });
}
const TABLE_COLS = [
  { key: 'prompt', label: 'prompt', get: r => r.prompt, kind: 'str' },
  { key: 'seed', label: 'seed', get: r => r.seed, kind: 'num' },
  { key: 'gain', label: 'gain', get: r => r.gain, kind: 'num' },
  { key: 'density', label: 'density', get: r => r.density, kind: 'num' },
  { key: 'measured', label: 'measured', get: r => r.measured, kind: 'num' },
  { key: 'error_delta', label: 'error', get: r => r.error_delta, kind: 'num' },
  { key: 'CE', label: 'CE', get: r => r.CE, kind: 'num' },
  { key: 'CU', label: 'CU', get: r => r.CU, kind: 'num' },
  { key: 'PC', label: 'PC', get: r => r.PC, kind: 'num' },
  { key: 'PQ', label: 'PQ', get: r => r.PQ, kind: 'num' },
  { key: 'spectral_balance', label: 'spectral bal.', get: r => r.spectral_balance, kind: 'num' },
];
let tableSort = { col: 'measured', dir: -1 };
function tableRange(rows, col) {
  const vals = rows.map(col.get).filter(v => v != null);
  return vals.length ? [Math.min(...vals), Math.max(...vals)] : null;
}
function tableColorFor(v, range) {
  if (v == null || !range) return '#eee';
  const [lo, hi] = range;
  const t = hi > lo ? (v - lo) / (hi - lo) : 0.5;
  return `hsl(${Math.round(t * 130)},50%,80%)`;
}
function renderRanked(rows) {
  wrap.innerHTML = '';
  const col = TABLE_COLS.find(c => c.key === tableSort.col);
  const dir = tableSort.dir;
  const sorted = rows.slice().sort((a, b) => {
    const va = col.get(a), vb = col.get(b);
    if (va == null && vb == null) return 0;
    if (va == null) return 1;
    if (vb == null) return -1;
    return col.kind === 'str' ? dir * String(va).localeCompare(String(vb)) : dir * (va - vb);
  });
  const ranges = {}; TABLE_COLS.forEach(c => { if (c.kind === 'num') ranges[c.key] = tableRange(rows, c); });
  const table = document.createElement('table'); table.className = 'tc-table';
  const headRow = document.createElement('tr');
  TABLE_COLS.forEach(c => {
    const on = tableSort.col === c.key;
    const arrow = on ? (dir === 1 ? '↑' : '↓') : '';
    const th = document.createElement('th');
    th.className = on ? 'on' : '';
    th.innerHTML = `${c.label} <span class="arrow">${arrow}</span>`;
    th.onclick = () => { tableSort = { col: c.key, dir: tableSort.col === c.key ? -tableSort.dir : -1 }; render(); };
    headRow.appendChild(th);
  });
  headRow.appendChild(document.createElement('th'));
  table.appendChild(headRow);
  sorted.forEach((r) => {
    const idx = rows.indexOf(r);
    const tr = document.createElement('tr'); tr.dataset.key = member + '-c' + idx;
    let cells = '';
    TABLE_COLS.forEach(c => {
      const v = c.get(r);
      const style = (c.kind === 'num' && ranges[c.key]) ? ` style="background:${tableColorFor(v, ranges[c.key])}"` : '';
      const text = v == null ? '·' : (typeof v === 'number' ? (Math.abs(v) < 10 ? v.toFixed(2) : v.toFixed(1)) : v);
      cells += `<td${style}>${text}</td>`;
    });
    tr.innerHTML = cells + '<td class="tc-play">▶</td>';
    tr.onclick = () => play(tr, member + '-c' + idx, r.clip, cellLabel(r));
    table.appendChild(tr);
  });
  wrap.appendChild(table);
}
function render() {
  const rows = D.filter(r => r.checkpoint === member);
  rankedMode ? renderRanked(rows) : renderGrid(rows);
}
document.getElementById(__SELECT_ID__).onchange = (e) => { member = e.target.value; render(); };
document.querySelectorAll('.eg-sort').forEach(btn => {
  btn.onclick = () => {
    document.querySelectorAll('.eg-sort').forEach(b => b.classList.remove('on'));
    btn.classList.add('on');
    activeMetric = btn.dataset.metric;
    render();
  };
});
document.getElementById(__VIEW_TOGGLE_ID__).onclick = (e) => {
  rankedMode = !rankedMode;
  e.target.textContent = rankedMode ? '☰ grid view' : '⊞ sortable table';
  render();
};
render();
})();
"""


def render_composed_sweep_page(*, head_html: str, title: str, label: str, purpose: str,
                                date_str: str, records: list[dict], footer_html: str,
                                findings: str = None, status: str = None,
                                known_pages: dict = None) -> str:
    """Dropdown across the composed_sweep members + the FULL grid heatmap/table
    view per selection (Kim: 'the full grid treatment -- gain x density cells +
    corr coloring', not the flat audit table). records: concatenation of
    load_grid_data() calls, one per member (same shape as the checkpoint audit)."""
    members = sorted({r["checkpoint"] for r in records})
    n_scored = sum(1 for r in records if r["CE"] is not None)
    doc = head_html
    doc += f'<h1>{html.escape(label)}</h1>'
    if date_str:
        doc += f'<p class="faint">{html.escape(date_str)}</p>'
    if purpose:
        doc += f'<p class="lede">{html.escape(purpose)}</p>'
    doc += provenance_html(findings, status, known_pages)
    doc += (f'<p class="faint">{len(members)} sweep stages · {len(records)} clips total '
            f'({n_scored} quality-scored) · pick a stage, toggle grid/table, same-playhead</p>')
    doc += '<div class="aud-bar"><select id="cs-select">'
    for m in members:
        doc += f'<option value="{html.escape(m)}">{html.escape(m)}</option>'
    doc += '</select></div>'
    doc += '<div class="eg-bar">'
    doc += '<span class="faint" style="margin-right:6px">heatmap colours by:</span>'
    for key, lbl in (("measured", "onset density"), ("gain", "gain"), ("density", "density"),
                      ("CE", "content enjoyment"), ("error", "error delta"),
                      ("spectral_balance", "spectral balance")):
        cls = "eg-sort on" if key == "measured" else "eg-sort"
        doc += f'<span class="{cls}" data-metric="{key}">{html.escape(lbl)}</span>'
    doc += '<span class="eg-view" id="cs-view-toggle">☰ gain×density grid</span>'
    doc += '</div>'
    doc += '<div class="eg-info" id="cs-info">click a cell for its readout</div>'
    doc += '<div id="cs-wrap"></div>'
    js = (COMPOSED_JS_TEMPLATE
          .replace("__DATA__", json.dumps(records))
          .replace("__MEMBERS__", json.dumps(members))
          .replace("__WRAP_ID__", "'cs-wrap'")
          .replace("__INFO_ID__", "'cs-info'")
          .replace("__SELECT_ID__", "'cs-select'")
          .replace("__VIEW_TOGGLE_ID__", "'cs-view-toggle'"))
    doc += f'<script>{js}</script>'
    doc += footer_html
    return doc


# ── multi-checkpoint onset-control audit (2026-07-07) ─────────────────────────
# Kim: dozens of individually-linked "onset control N" grids on the landing
# page is "messy AF" -- aggregate them into ONE page with "some way of
# auditing all of the checkpoints from one GUI". Unlike the DoRA/prompt-style
# dual-pane compares, these are INDEPENDENT experiments (different gain/density
# sweep ranges, different scalar targets) -- forcing a shared row identity
# across them would produce a sparse, mostly-blank union table. So: ONE
# dropdown (all checkpoints) + ONE sortable table for whichever is selected,
# self-normalized colour grading per checkpoint (same principle as the compare
# pages, just single-pane since there's no meaningful shared row axis to sync
# a second pane against). Still lets Kim browse every checkpoint from one GUI
# without a page reload per run -- that's the actual ask.
AUDIT_CSS = """
.aud-bar{display:flex;gap:10px;align-items:center;margin:10px 0 14px;flex-wrap:wrap}
.aud-bar select{font-family:var(--mono);font-size:12px;color:var(--ink);
background:var(--paper-dim);border:1px solid var(--rule);padding:6px 10px;
min-width:280px;border-radius:2px}
.aud-bar button{font-family:var(--mono);font-size:12px;color:var(--ink);
background:var(--paper-dim);border:1px solid var(--rule);padding:6px 12px;
border-radius:2px;cursor:pointer}
.aud-bar button.on{background:var(--edge);color:#fff;border-color:var(--edge)}
.aud-meta{font-size:10.5px;color:var(--faint)}
"""

AUDIT_JS_TEMPLATE = r"""
(function(){
const D = __DATA__;
const CHECKPOINTS = __CHECKPOINTS__;  // [tag, ...] sorted
const COLS = [
  { key: 'prompt', label: 'prompt', get: r => r.prompt, kind: 'str' },
  { key: 'seed', label: 'seed', get: r => r.seed, kind: 'num' },
  { key: 'gain', label: 'gain', get: r => r.gain, kind: 'num' },
  { key: 'density', label: 'density', get: r => r.density, kind: 'num' },
  { key: 'measured', label: 'measured', get: r => r.measured, kind: 'num' },
  { key: 'error_delta', label: 'error', get: r => r.error_delta, kind: 'num' },
  { key: 'CE', label: 'CE', get: r => r.CE, kind: 'num' },
  { key: 'CU', label: 'CU', get: r => r.CU, kind: 'num' },
  { key: 'PC', label: 'PC', get: r => r.PC, kind: 'num' },
  { key: 'PQ', label: 'PQ', get: r => r.PQ, kind: 'num' },
  { key: 'spectral_balance', label: 'spectral bal.', get: r => r.spectral_balance, kind: 'num' },
];
const byCheckpoint = {};
D.forEach(r => { (byCheckpoint[r.checkpoint] ||= []).push(r); });

const wrap = document.getElementById(__WRAP_ID__);
const audio = new Audio(); let curKey = null;
audio.addEventListener('ended', () => { markPlaying(null); curKey = null; });
function markPlaying(key) {
  document.querySelectorAll('.tc-table tr[data-key]').forEach(tr => {
    tr.classList.toggle('playing', tr.dataset.key === key && key !== null);
  });
}
function seekAndPlay(a, pos) {
  const go = () => { try { a.currentTime = ((a.duration && pos > a.duration - 1) ? 0 : Math.min(pos, (a.duration || 1e9) - 0.05)); } catch (e) {} a.play(); };
  if (a.readyState >= 3) { go(); return; }
  let done = false;
  const fire = () => { if (done) return; done = true; go(); };
  a.addEventListener('canplay', fire, { once: true });
  setTimeout(fire, 1200);
}
function play(key, src, label) {
  if (!src) return;
  if (curKey === key) { audio.pause(); markPlaying(null); curKey = null; return; }
  const pos = (curKey !== null && !audio.paused) ? audio.currentTime : 0;
  curKey = key; markPlaying(key);
  audio.pause();
  audio.src = src;
  seekAndPlay(audio, pos);
  document.getElementById(__INFO_ID__).textContent = label;
}

let checkpoint = CHECKPOINTS[0];
let sort = { col: 'CE', dir: -1 };

function realizedRange(rows, key) {
  const vals = rows.map(r => COLS.find(c => c.key === key).get(r)).filter(v => v != null);
  return vals.length ? [Math.min(...vals), Math.max(...vals)] : null;
}
function colorFor(v, range) {
  if (v == null || !range) return '#eee';
  const [lo, hi] = range;
  const t = hi > lo ? (v - lo) / (hi - lo) : 0.5;
  return `hsl(${Math.round(t * 130)},50%,80%)`;
}

function render() {
  wrap.innerHTML = '';
  const bar = document.createElement('div'); bar.className = 'aud-bar';
  const select = document.createElement('select');
  CHECKPOINTS.forEach(tag => {
    const opt = document.createElement('option');
    opt.value = tag; opt.textContent = tag;
    if (tag === checkpoint) opt.selected = true;
    select.appendChild(opt);
  });
  select.onchange = () => { checkpoint = select.value; render(); };
  bar.appendChild(select);
  const rows = byCheckpoint[checkpoint] || [];
  const meta = document.createElement('span'); meta.className = 'aud-meta';
  meta.textContent = `${rows.length} clips in this checkpoint`;
  bar.appendChild(meta);
  wrap.appendChild(bar);

  const col = COLS.find(c => c.key === sort.col);
  const sorted = rows.slice().sort((a, b) => {
    const va = col.get(a), vb = col.get(b);
    if (va == null && vb == null) return 0;
    if (va == null) return 1;
    if (vb == null) return -1;
    return col.kind === 'str' ? sort.dir * String(va).localeCompare(String(vb)) : sort.dir * (va - vb);
  });
  const ranges = {}; COLS.forEach(c => { if (c.kind === 'num') ranges[c.key] = realizedRange(rows, c.key); });

  const table = document.createElement('table'); table.className = 'tc-table';
  const headRow = document.createElement('tr');
  COLS.forEach(c => {
    const on = sort.col === c.key;
    const arrow = on ? (sort.dir === 1 ? '↑' : '↓') : '';
    const th = document.createElement('th');
    th.innerHTML = `${c.label} <span class="arrow">${arrow}</span>`;
    th.onclick = () => { sort = { col: c.key, dir: sort.col === c.key ? -sort.dir : -1 }; render(); };
    headRow.appendChild(th);
  });
  headRow.appendChild(document.createElement('th'));
  table.appendChild(headRow);

  sorted.forEach((r, i) => {
    const tr = document.createElement('tr'); tr.dataset.key = checkpoint + '-' + i;
    COLS.forEach(c => {
      const td = document.createElement('td');
      const v = c.get(r);
      if (c.kind === 'num' && ranges[c.key]) td.style.background = colorFor(v, ranges[c.key]);
      td.textContent = v == null ? '·' : (typeof v === 'number' ? (Math.abs(v) < 10 ? v.toFixed(2) : v.toFixed(1)) : v);
      tr.appendChild(td);
    });
    const playTd = document.createElement('td'); playTd.textContent = '▶'; playTd.style.cursor = r.clip ? 'pointer' : 'default';
    if (r.clip) playTd.onclick = () => play(checkpoint + '-' + i, r.clip, `${checkpoint} · ${r.prompt || ''} · g${r.gain} d${r.density} s${r.seed}`);
    tr.appendChild(playTd);
    table.appendChild(tr);
  });
  wrap.appendChild(table);
}
render();
})();
"""


# Kim, 2026-07-12 (eval-tables spec §15): aggregation-page dropdowns order by
# Kim's PREFERENCE first, then date -- not alphabetically. The preference
# registry lives in docs/onset-density-control-narrative.md §3 (the verdict
# section) -- this list mirrors it; update THAT doc first when a new ear-verdict
# lands, then sync this list, so the doc stays the source of truth rather than
# the ordering being invented fresh in page JS.
#
# Entries are the checkpoint identifiers as they appear in THIS audit page
# (the onset_eval_* eval-run dir names, not the underlying training-run dir
# names the narrative doc uses -- e.g. narrative's "onset_Fusion_lr1e-4_
# randomcrop" is evaluated as "onset_eval_Fusion_baseline" here; confirmed by
# matching corr_per_gain numbers, 2026-07-12). A trailing "*" prefix-matches a
# whole family instead of one exact name -- used for onset_FUSION_lr2e5_40epoch,
# which has no single "the" checkpoint (Gap #3, unresolved per the narrative:
# many per-step eval dirs, none singled out as canonical) -- the whole family
# is pulled into its preference rank as a block, newest-step first.
ONSET_CHECKPOINT_PREFERENCE = [
    "onset_eval_Fusion_baseline",   # 07-07 ear-verdict, the named recipe (plain Fusion)
    "onset_eval_lr2e5_*",           # "the favourite... by ear", unreconciled 2nd claim (Gap #3)
    "onset_eval_FusionCC",          # metric winner (corr .880 @g2), not ear-picked
]


def order_checkpoints(names, dates=None, preference=ONSET_CHECKPOINT_PREFERENCE):
    """Preference-listed names first (in listed order; a "prefix*" entry pulls
    in every matching name as a date-sorted block at that rank), then the rest
    by date descending (newest first) if `dates` (name -> sortable date/mtime)
    is given, else alphabetically as a last-resort fallback."""
    names = set(names)
    claimed = set()
    pref = []
    for p in preference:
        if p.endswith("*"):
            group = sorted((n for n in names if n.startswith(p[:-1]) and n not in claimed),
                            key=lambda n: dates.get(n, 0) if dates else n, reverse=bool(dates))
            pref.extend(group)
            claimed.update(group)
        elif p in names and p not in claimed:
            pref.append(p)
            claimed.add(p)
    rest = [n for n in names if n not in claimed]
    rest.sort(key=lambda n: dates.get(n, 0), reverse=True) if dates else rest.sort()
    return pref + rest


def render_checkpoint_audit_page(*, head_html: str, title: str, label: str, purpose: str,
                                  date_str: str, records: list[dict], footer_html: str,
                                  checkpoint_dates: dict = None) -> str:
    """Single-pane multi-checkpoint browser: one dropdown over every checkpoint
    (independent experiments, e.g. many onset-control training runs), one
    sortable table for whichever is selected. records: concatenation of
    load_grid_data() calls across many source dirs, one call per checkpoint."""
    checkpoints = order_checkpoints({r["checkpoint"] for r in records}, checkpoint_dates)
    n_scored = sum(1 for r in records if r["CE"] is not None)
    doc = head_html
    doc += f'<h1>{html.escape(label)}</h1>'
    if date_str:
        doc += f'<p class="faint">{html.escape(date_str)}</p>'
    if purpose:
        doc += f'<p class="lede">{html.escape(purpose)}</p>'
    doc += (f'<p class="faint">{len(checkpoints)} checkpoints (independent runs) · {len(records)} clips total '
            f'({n_scored} quality-scored) · pick a checkpoint, click a column header to sort · '
            'click ▶ to play (shared playhead) · colour = min→max within the shown checkpoint only '
            '(NOT comparable across checkpoints -- different runs, different sweep ranges)</p>')
    doc += '<div class="eg-info" id="aud-info">click a row for its readout</div>'
    doc += '<div id="aud-wrap"></div>'
    js = (AUDIT_JS_TEMPLATE
          .replace("__DATA__", json.dumps(records))
          .replace("__CHECKPOINTS__", json.dumps(checkpoints))
          .replace("__WRAP_ID__", "'aud-wrap'")
          .replace("__INFO_ID__", "'aud-info'"))
    doc += f'<script>{js}</script>'
    doc += footer_html
    return doc
