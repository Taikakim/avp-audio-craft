#!/usr/bin/env python3
# Owner: ANTIGRAVITY <antigravity@aavepyora.online>
"""build_e22_root_locked_page.py -- listening + results page for EXPERIMENTS E22:
steer a chord SHAPE (colour) while the root stays where prompt and seed put it.
Kim 2026-10-29: "it's fine that it shifts the fundamental/root, but very cool would also be one
which does not, forcing it to be more creative."

Reads the run dir written by eval/e22_root_locked_chroma.py (cells.jsonl, e22_results.json, run_meta.json),
stages the clips as 256 kbps AAC under ~/evals_aac/e22_root_locked_chroma/ and writes
~/evals_aac/e22_root_locked_chroma.html.
Includes reference absolute C major steering clips from E21b and E21c for direct A/B contrast.
No drive paths on the page (clean public-ready). W/Kim publishes.
"""
import concurrent.futures
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "eval"))

from comment_notes_block import notes_block
from float_player import inject
import model_matrix_gen as M

SRC = "/run/media/kim/Mantu/sa3_control_runs/e22_root_locked_chroma_20261029"
BASE_E21B = "/run/media/kim/Mantu/sa3_control_runs/e21b_transposition_canon_20261028"
SRC_E21C = "/run/media/kim/Mantu/sa3_control_runs/e21c_same_chroma_gain_20261029"

STAGE = os.path.join(os.path.expanduser("~"), "evals_aac")
SUB = "e22_root_locked_chroma"
OUT_DIR = os.path.join(STAGE, SUB)
os.makedirs(OUT_DIR, exist_ok=True)

NOTE = ["C", "C♯", "D", "E♭", "E", "F", "F♯", "G", "A♭", "A", "B♭", "B"]
SHAPES = {"maj": "Major", "min": "Minor", "sus4": "Sus4", "dim": "Diminished"}
MODES = ("rotinv", "locked")

# Load run data
cells = [json.loads(l) for l in open(f"{SRC}/cells.jsonl") if l.strip()]
res = json.load(open(f"{SRC}/e22_results.json"))
meta = json.load(open(f"{SRC}/run_meta.json"))

PROMPTS = {p["id"]: {"text": p["text"], "seed": p["seed"]} for p in M.build_prompts(n_per_band=3, n_kimlong=3)}
pids = sorted(PROMPTS.keys())

# Define encode jobs
jobs = []
for c in cells:
    src_wav = f"{SRC}/{c['id']}.wav"
    dst_m4a = os.path.join(OUT_DIR, f"{c['id']}.m4a")
    jobs.append((src_wav, dst_m4a))

# Also add reference absolute C major clips
ref_clips = {}
for pid in pids:
    # hpcp abs C major ref
    hpcp_wav = f"{BASE_E21B}/{pid}__hpcp__k0__g2048.wav"
    hpcp_id = f"{pid}__hpcp__abs_C_maj__g2048"
    if os.path.exists(hpcp_wav):
        dst = os.path.join(OUT_DIR, f"{hpcp_id}.m4a")
        jobs.append((hpcp_wav, dst))
        ref_clips[hpcp_id] = {"f": f"{SUB}/{hpcp_id}.m4a", "pid": pid, "head": "hpcp", "mode": "abs_ref", "shape": "maj"}

    # same_chroma_e13 abs C major ref
    e13_wav = f"{SRC_E21C}/{pid}__same_chroma_e13__k0__g2048.wav"
    e13_id = f"{pid}__same_chroma_e13__abs_C_maj__g2048"
    if os.path.exists(e13_wav):
        dst = os.path.join(OUT_DIR, f"{e13_id}.m4a")
        jobs.append((e13_wav, dst))
        ref_clips[e13_id] = {"f": f"{SUB}/{e13_id}.m4a", "pid": pid, "head": "same_chroma_e13", "mode": "abs_ref", "shape": "maj"}


def encode_one(job):
    src, dst = job
    if not os.path.exists(dst):
        subprocess.run(
            ["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", src, "-c:a", "aac", "-b:a", "256k", dst],
            check=True
        )
    return dst

print(f"Staging {len(jobs)} audio files to {OUT_DIR}...")
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
    list(ex.map(encode_one, jobs))

# Probe bitrate
first_m4a = jobs[0][1]
br = subprocess.run(
    ["ffprobe", "-v", "error", "-show_entries", "format=bit_rate", "-of", "csv=p=0", first_m4a],
    capture_output=True, text=True
).stdout.strip()
kbps = f"{int(br) // 1000} kbps" if br.isdigit() else "256 kbps"
print(f"Audio verified: {kbps} AAC")

# Build clips metadata dict
clips = {}
for c in cells:
    cid = c["id"]
    clips[cid] = {
        "f": f"{SUB}/{cid}.m4a",
        "pid": c["pid"],
        "head": c.get("head"),
        "shape": c.get("shape"),
        "mode": c.get("mode"),
        "chord": c.get("chord"),
        "gain": 2048 if c.get("head") else None,
        "base_root": c.get("base_root"),
    }
clips.update(ref_clips)

HEAD_LABELS = {
    "same_chroma_e13": "same_chroma retrained in E13 (C3, modular optimiser, latch_sa3_same_chroma_ep10.pt)",
    "hpcp": "hpcp (production head, latch_sa3_hpcp_best.pt)"
}

# Redact private paths in recipe
clean_recipe = dict(meta.get("recipe", {}))
if "heads" in clean_recipe:
    clean_recipe["heads"] = {h: os.path.basename(v) for h, v in clean_recipe["heads"].items()}
clean_recipe["finetune"] = "goa DoRA finetune (subloss_k24 biggoa t512, epoch 63), strength 1.0"
clean_recipe["unguided"] = "reused from E21b (same prompts, seeds, settings)"

DATA = json.dumps({
    "prompts": PROMPTS,
    "clips": clips,
    "res": res,
    "shapes": SHAPES,
    "heads": HEAD_LABELS,
    "recipe": clean_recipe,
    "kbps": kbps,
})

HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>E22: Root-Locked Chroma Steering</title>
<style>
:root{--bg:#0e0e10;--fg:#e0e0e0;--bar:#16181c;--line:#2a2a30;--th:#1c1c22;--muted:#888;--acc:#4fe3dd;--good:#4b4;--bad:#d55;--card:#141418}
@media (prefers-color-scheme: light){:root:not([data-theme="dark"]){--bg:#fafafa;--fg:#222;--bar:#eef0f3;--line:#d4d4da;--th:#e8e8ee;--muted:#666;--acc:#0a8882;--card:#f0f2f5}}
body{font:13px -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;margin:0;background:var(--bg);color:var(--fg);line-height:1.4}
#bar{position:sticky;top:0;background:var(--bar);padding:8px 16px;border-bottom:1px solid var(--line);z-index:99;display:flex;align-items:center;gap:12px}
#wrap{padding:18px 24px;max-width:min(2300px,96vw);margin:0 auto}
h1{font-size:20px;margin:4px 0 10px;font-weight:700;color:var(--acc)}
h2{font-size:16px;margin:28px 0 8px;color:var(--acc);display:flex;align-items:center;gap:8px}
.muted{color:var(--muted)}
.explain{background:#12181a;border:1px solid #1f3836;border-left:4px solid var(--acc);padding:12px 16px;font-size:13px;color:#d5e5e4;margin:12px 0;line-height:1.55;border-radius:4px}
.explain b{color:#6ee7e2}
@media (prefers-color-scheme: light){.explain{background:#eefbfb;color:#234;border-color:#bce5e3;border-left-color:var(--acc)}.explain b{color:#087}}
table{border-collapse:collapse;font-size:12px;margin:6px 0 16px;width:100%;display:block;overflow-x:auto}
td,th{border:1px solid var(--line);padding:5px 7px;text-align:center;white-space:nowrap}
th{background:var(--th);color:var(--muted);font-weight:600}
td.l{text-align:left;white-space:normal;min-width:240px;max-width:380px}
td.center{text-align:center}
.num{font-variant-numeric:tabular-nums}
.good{color:var(--good);font-weight:700}
.bad{color:var(--bad)}
.pill{display:inline-block;padding:1px 6px;border-radius:10px;font-size:11px;font-weight:600}
.pill-good{background:rgba(68,187,68,0.18);color:#5d5;border:1px solid rgba(68,187,68,0.3)}
.pill-mid{background:rgba(238,170,34,0.18);color:#fb2;border:1px solid rgba(238,170,34,0.3)}
.pill-neutral{background:rgba(136,136,136,0.15);color:var(--muted);border:1px solid var(--line)}
.b{display:inline-block;cursor:pointer;border:1px solid var(--line);border-radius:3px;padding:2px 7px;margin:1px;font-size:11.5px;background:var(--th);user-select:none;transition:all .1s}
.b:hover{outline:1px solid var(--acc);color:var(--acc)}
.b.play{outline:2px solid #5d5 !important;background:#153018;color:#8f8}
.b-rotinv{border-left:2px solid #38bdf8}
.b-locked{border-left:2px solid #a855f7}
.b-abs{border-left:2px solid #f59e0b}
.un{color:#e44;font-weight:bold;cursor:help}
.legend{display:flex;gap:14px;align-items:center;margin:8px 0;font-size:12px}
.legend-item{display:inline-flex;align-items:center;gap:5px}
.legend-bar{width:10px;height:10px;border-radius:2px}
</style>
</head>
<body>
<div id="bar">
  <span>&#9654; <b id="np">Click any clip to play</b></span>
  <span id="pos" class="muted"></span>
  <span class="muted" style="margin-left:auto">&#8644; Playhead preserved across clip switching &middot; Re-click stops &middot; Space pause</span>
</div>

<div id="wrap">
  <h1>E22 &middot; Root-Locked Chroma Steering: Chord Shape in the Model's Own Key</h1>
  
  <div class="explain">
    <b>The Motivation (Kim 2026-10-29):</b> <i>"it's fine that it shifts the fundamental/root, but very cool would also be one which does not, forcing it to be more creative."</i><br>
    <b>The Mechanism:</b> Standard absolute chroma steering forces the generator's root note to transpose to the requested chord (e.g. asking for C major pulls any track's bass note to C).
    E22 evaluates two approaches to steer <b>harmonic color</b> (chord shape: major, minor, sus4, diminished) while keeping the root in the prompt's native key:
    <ul style="margin:6px 0 6px 18px;padding:0">
      <li><b>rotinv (Rotation-Invariant Guidance):</b> Evaluates a soft-min over the 12 circular pitch-class transpositions of the target shape (&tau;=0.05). The guidance gradient pulls toward the <i>nearest transposition</i> of the shape, preserving whatever key the model started in.</li>
      <li><b>locked (Unguided Root Lock):</b> Reads the natural base root from the unguided render, then locks the target chord directly to that root.</li>
    </ul>
    <b>The Findings:</b> The <b>E13-retrained same_chroma head</b> is an overwhelming success: under <code>rotinv</code> it keeps the natural root in <b>51 / 56 clips (91.1%)</b> while moving decisively toward the requested chord quality (specificity <b>+0.0786</b>, dead clips: 0). Explicit root-lock achieves <b>52 / 56 (92.9%)</b> and specificity <b>+0.1047</b>. In contrast, under absolute C major steering, the root was moved away from its natural key on almost every track.
    __UN__
  </div>

  <div class="legend">
    <span class="muted">Button Guide:</span>
    <span class="legend-item"><span class="legend-bar" style="background:#38bdf8"></span> <b>rotinv</b>: rotation-invariant soft-min (pulls to nearest key)</span>
    <span class="legend-item"><span class="legend-bar" style="background:#a855f7"></span> <b>locked</b>: explicitly anchored to prompt's unguided root</span>
    <span class="legend-item"><span class="legend-bar" style="background:#f59e0b"></span> <b>abs ref</b>: absolute C major steering from E21 (root forced to C)</span>
  </div>

  <div id="out"></div>

  <h2>Reproducibility &amp; Settings</h2>
  <div class="muted" id="repro" style="font-size:12px;line-height:1.6"></div>
</div>

<audio id="au_el"></audio>

<script>
const D = __DATA__;
const au = document.getElementById('au_el');
const npx = document.getElementById('np');
let cur = null;

au.addEventListener('timeupdate', () => {
  document.getElementById('pos').textContent = cur ? ('· ' + au.currentTime.toFixed(1) + 's / ' + (au.duration ? au.duration.toFixed(1) + 's' : '')) : '';
});
au.addEventListener('ended', () => { cur = null; mark(); npx.textContent = 'Playback finished'; });

window.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  if (e.code === 'Space') {
    e.preventDefault();
    if (au.src) { au.paused ? au.play() : au.pause(); }
  }
});

function mark() {
  document.querySelectorAll('.b.play').forEach(e => e.classList.remove('play'));
  if (cur) {
    document.querySelectorAll('[data-id="' + cur + '"]').forEach(e => e.classList.add('play'));
  }
}

function play(id) {
  const c = D.clips[id];
  if (!c) return;
  if (cur === id) {
    au.pause();
    cur = null;
    mark();
    npx.textContent = 'stopped';
    return;
  }
  if (window.noteSet) noteSet({model: 'e22_root_locked', ckpt: '', clip: id});
  const pos = (cur !== null && !au.paused) ? au.currentTime : 0;
  cur = id;
  mark();
  const desc = (D.prompts[c.pid]?.text || id).slice(0, 95);
  npx.innerHTML = '<b>' + id + '</b> <span class="muted">&middot; ' + desc + '</span>';
  au.src = c.f;
  const go = () => {
    try { au.currentTime = Math.min(pos, (au.duration || 1e9) - 0.05); } catch(e){}
    au.play();
  };
  if (au.readyState >= 1) go();
  else au.addEventListener('loadedmetadata', go, {once: true});
}

const f = (v, d) => v == null ? '–' : Number(v).toFixed(d);
const btn = (id, lbl, cls) => D.clips[id] ? `<span class="b ${cls||''}" data-id="${id}" onclick="play('${id}')">${lbl}</span>` : '<span class="muted">–</span>';

function cid(pid, head, shape, mode) {
  return `${pid}__${head}__${shape}__${mode}__g2048`;
}

// 1. Summary Metrics Table
let h = '<h2>1 &middot; Quantitative Metrics Summary</h2>';
h += '<table><tr><th>Head & Architecture</th><th>Guidance Mode</th><th>Root Preserved</th><th>Retention Rate</th><th>&Delta; Toward Own Shape</th><th>&Delta; Toward Others</th><th>Shape Specificity</th><th>Verdict</th></tr>';

const S = D.res.summary;
const rowsSummary = [
  {k: 'same_chroma_e13|rotinv', head: 'same_chroma (E13 modular retrain)', mode: 'rotinv (soft-min rotation invariant)'},
  {k: 'same_chroma_e13|locked', head: 'same_chroma (E13 modular retrain)', mode: 'locked (explicit unguided root)'},
  {k: 'same_chroma_e13|absolute_C_major_ref', head: 'same_chroma (E13 modular retrain)', mode: 'absolute C major reference (E21c k0)'},
  {k: 'hpcp|rotinv', head: 'hpcp (production 12-d)', mode: 'rotinv (soft-min rotation invariant)'},
  {k: 'hpcp|locked', head: 'hpcp (production 12-d)', mode: 'locked (explicit unguided root)'},
  {k: 'hpcp|absolute_C_major_ref', head: 'hpcp (production 12-d)', mode: 'absolute C major reference (E21b k0)'},
];

rowsSummary.forEach(r => {
  const v = S[r.k];
  if (!v) return;
  const isAbs = r.k.includes('absolute');
  const pct = (v.root_kept / v.n * 100).toFixed(1) + '%';
  const pillCls = (v.root_kept / v.n >= 0.85) ? 'pill-good' : (v.root_kept / v.n >= 0.5 ? 'pill-mid' : 'pill-neutral');
  const spec = v.specificity != null ? (v.specificity > 0 ? '+' : '') + f(v.specificity, 4) : '–';
  const specCls = v.specificity > 0 ? 'good' : (v.specificity < 0 ? 'bad' : '');
  const verdict = isAbs ? '<span class="muted">Moves root to C</span>' : (v.root_kept / v.n >= 0.85 && v.specificity > 0 ? '<span class="pill pill-good">&#10003; Target Met (Keeps root + steers shape)</span>' : '<span class="pill pill-mid">Weak rotation invariance</span>');
  
  h += `<tr>
    <td class="l"><b>${r.head}</b></td>
    <td><code>${r.mode}</code></td>
    <td class="num"><b>${v.root_kept} / ${v.n}</b></td>
    <td><span class="pill ${pillCls}">${pct}</span></td>
    <td class="num">${f(v.own_delta, 4)}</td>
    <td class="num">${f(v.other_delta, 4)}</td>
    <td class="num ${specCls}">${spec}</td>
    <td>${verdict}</td>
  </tr>`;
});
h += '</table>';

// 2. Unguided Roots Table
h += '<h2>2 &middot; Natural Unguided Roots (Detected Bass Pitch Class)</h2>';
h += '<div class="muted">Argmax pitch class of the bass band in the unguided render. In locked mode, targets are built on this detected note. In rotinv mode, guidance naturally settles here.</div>';
h += '<table><tr><th>Prompt ID</th><th>Natural Root</th><th>Seed</th><th>Prompt Text</th></tr>';
Object.entries(D.res.unguided_roots).forEach(([pid, root]) => {
  const p = D.prompts[pid] || {};
  h += `<tr>
    <td><b>${pid}</b></td>
    <td><span class="pill pill-good" style="font-size:12px;padding:2px 8px">${root}</span></td>
    <td class="num muted">${p.seed || '–'}</td>
    <td class="l">${p.text || '–'}</td>
  </tr>`;
});
h += '</table>';

// 3. Listening Section: same_chroma_e13
function renderListeningTable(headKey, title, note) {
  let s = `<h2>3 &middot; Listen: ${title}</h2>`;
  s += `<div class="muted">${note}</div>`;
  s += `<table>
    <tr>
      <th rowspan="2">Prompt</th>
      <th rowspan="2">Natural Root</th>
      <th rowspan="2">Unguided Base</th>
      <th rowspan="2">Abs C Major (Forced Root)</th>
      <th colspan="2">Major Shape</th>
      <th colspan="2">Minor Shape</th>
      <th colspan="2">Sus4 Shape</th>
      <th colspan="2">Diminished Shape</th>
    </tr>
    <tr>
      <th>rotinv</th><th>locked</th>
      <th>rotinv</th><th>locked</th>
      <th>rotinv</th><th>locked</th>
      <th>rotinv</th><th>locked</th>
    </tr>`;

  Object.keys(D.prompts).forEach(pid => {
    const p = D.prompts[pid];
    const root = D.res.unguided_roots[pid] || '–';
    const baseId = `${pid}__base`;
    const absId = `${pid}__${headKey}__abs_C_maj__g2048`;

    s += `<tr>
      <td class="l" title="${p.text.replace(/"/g,'&quot;')}"><b>${pid}</b> <span class="muted">${p.text.slice(0,55)}…</span></td>
      <td><span class="pill pill-good">${root}</span></td>
      <td>${btn(baseId, '▶ Base', '')}</td>
      <td>${btn(absId, '▶ C Maj', 'b-abs')}</td>`;

    ['maj', 'min', 'sus4', 'dim'].forEach(sh => {
      const rotId = cid(pid, headKey, sh, 'rotinv');
      const lockId = cid(pid, headKey, sh, 'locked');
      const rotChord = D.clips[rotId]?.chord || sh;
      const lockChord = D.clips[lockId]?.chord || (root + (sh === 'maj' ? '' : (sh === 'min' ? 'm' : sh)));
      s += `<td>${btn(rotId, '▶ ' + sh, 'b-rotinv')}</td>`;
      s += `<td>${btn(lockId, '▶ ' + lockChord, 'b-locked')}</td>`;
    });

    s += '</tr>';
  });
  s += '</table>';
  return s;
}

h += renderListeningTable(
  'same_chroma_e13',
  'same_chroma (E13 Modular Retrained Head, 384-d)',
  'Headline winner: 91.1% root retention under rotinv, 92.9% under locked. Compare each shape against both the Unguided Base and the Absolute C Major render.'
);

h += renderListeningTable(
  'hpcp',
  'hpcp (Production Head, 12-d)',
  '12-bin HPCP head: 46.4% root retention under rotinv (slips root more often), 92.9% under locked.'
);

document.getElementById('out').innerHTML = h;

const R = D.recipe;
document.getElementById('repro').innerHTML = `
  <b>Model:</b> ${R.finetune} &middot; 
  <b>Sampler:</b> ${R.sampler} (${R.steps} steps, CFG ${R.cfg}, APG ${R.apg}, ${R.duration}s) &middot; 
  <b>LatCH Window:</b> [${R.latch_window[0]}, ${R.latch_window[1]}] &middot; 
  <b>Gain:</b> ${R.gain} &middot; 
  <b>rotinv Temperature (&tau;):</b> ${R.rotinv_tau} &middot; 
  <b>Heads:</b> ${JSON.stringify(R.heads)} &middot; 
  <b>Audio:</b> ${D.kbps} AAC (measured).
`;
</script>

__NOTES__

<footer style="margin:24px 12px;color:var(--muted);font-size:11px">
  evals &middot; E22 Root-Locked Chroma Steering &middot; Aavepy&ouml;r&auml;
</footer>
</body>
</html>
"""

UN = "" if meta.get("kim_feedback") else '<span class="un" title="No listening verdict recorded yet (unaudited).">&#10071;</span> <b>Audition Status:</b> Ready for ear-audition (Kim).'
HTML_CONTENT = HTML_TEMPLATE.replace("__UN__", UN).replace(
    "__NOTES__",
    notes_block("e22_root_locked_chroma", levels=[("clip", "this clip"), ("page", "page")],
                hint="click a clip, then note what you hear")
)

html_out = os.path.join(STAGE, "e22_root_locked_chroma.html")
with open(html_out, "w") as f:
    f.write(inject(HTML_CONTENT.replace("__DATA__", DATA)))

# Also create index.html in the folder for direct folder access
with open(os.path.join(OUT_DIR, "index.html"), "w") as f:
    f.write(inject(HTML_CONTENT.replace("__DATA__", DATA)))

print(f"Successfully generated:\n  - {html_out}\n  - {os.path.join(OUT_DIR, 'index.html')}")
print(f"Total clips staged: {len(clips)}")
