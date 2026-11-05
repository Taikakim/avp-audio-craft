#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-11-04, updated 2026-11-05 for 90s Island + 4-Bar Inpaint Bridge)
"""build_mixtape_trackpool_v3_page.py -- tagging page for the re-rendered DJ-mix track pool v3.

Reads cells_islands.jsonl (and cells.jsonl if available) from /run/media/kim/Mantu/sa3_lora_runs/mixtape_trackpool_v3/
and writes ~/evals_aac/mixtape_trackpool_v3.html following docs/eval-page-standard.md.
"""
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from html import escape

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from float_player import inject

POOL = "/run/media/kim/Mantu/sa3_lora_runs/mixtape_trackpool_v3"
NAME = "mixtape_trackpool_v3"
ST = os.path.expanduser("~/evals_aac")
SUB = "mixtape_trackpool_v3"
os.makedirs(f"{ST}/{SUB}", exist_ok=True)

manifest_islands = f"{POOL}/cells_islands.jsonl"
if not os.path.exists(manifest_islands):
    print("No cells_islands.jsonl found yet.")
    sys.exit(1)

cells = [json.loads(l) for l in open(manifest_islands) if l.strip()]

def fmt_time(s):
    s_int = int(s)
    frac = int(round((s - s_int) * 10))
    m = s_int // 60
    sec = s_int % 60
    return f"{m}:{sec:02d}.{frac}"

# Sort cells by prompt index, then mode
def sort_key(c):
    return (c.get("pid", ""), 0 if c.get("mode") == "4bar_direct" else 1)

cells.sort(key=sort_key)

cards = ""
for c in cells:
    is_direct = (c["mode"] == "4bar_direct")
    mode_label = "Mode A: Direct 4-Bar Inpaint Bridge" if is_direct else "Mode B: A2A (0.60 noise) + 4-Bar Bridge"
    mode_class = "badge-direct" if is_direct else "badge-a2a"
    mode_desc = "Clean 16-beat inpaint bridge between 12-bar Island A & Island B from same 90s parent" if is_direct else "Island B restyled via A2A (0.60 noise) with ext prompt, then 4-bar inpaint bridge"
    
    pid = c["pid"]
    dur = c["dur"]
    dur_a = c["dur_a"]
    dur_gap = c["dur_gap"]
    dur_b = c["dur_b"]
    gap_start = c["gap_start"]
    gap_end = c["gap_end"]
    
    cards += f"""<div class=card id="{c['id']}" data-pid="{escape(pid)}" data-mode="{escape(c['mode'])}"><div class=top><span class=tid>{c['id']}</span> <span class="badge {mode_class}">{mode_label}</span> <span class="badge bpm">{c['bpm']:.1f} BPM</span> <span class="badge model">Full-FT ep80 (Base Med)</span> <span class=dim>Dur {dur:.1f}s · Seed {c['seed']}</span></div>
<div class=mode-desc>{mode_desc}</div>
<div class=prompt><b>Prompt Core:</b> {escape(c['prompt_core'])}</div>
<div class=prompt-ext><b>Prompt Ext:</b> {escape(c['prompt_ext'])}</div>
<div class=subinfo>
  <b>Timeline:</b>
  <span class="part-badge part-island">Island A (Core): 0:00 – {fmt_time(gap_start)} ({dur_a:.1f}s / 12 bars)</span> ➔ 
  <span class="part-badge part-bridge">Inpaint Bridge: {fmt_time(gap_start)} – {fmt_time(gap_end)} ({dur_gap:.1f}s / 16 beats)</span> ➔ 
  <span class="part-badge part-island">Island B (Latter): {fmt_time(gap_end)} – {fmt_time(dur)} ({dur_b:.1f}s / 12 bars)</span>
</div>
<div class=junctions>
  <b>Bilateral Seams:</b>
  <span class="junc-badge">⚡ Bridge In @ <b>{fmt_time(gap_start)}</b></span>
  <span class="junc-badge">⚡ Bridge Out @ <b>{fmt_time(gap_end)}</b></span>
  <span class=dim style="margin-left:auto">Zero-crossing beat snap · CFG 10.0 · 24 steps</span>
</div>
<div class=row>
  <button class="cell pl" data-f="{c['id']}.m4a">▶ Play Full Bridge ({dur:.1f}s)</button>
  <button class="cell core" data-f="{pid}_core.m4a">🎯 Island A Core ({dur_a:.1f}s)</button>
  <button class="cell parent" data-f="{pid}_parent_90s.m4a">🏛️ 90s Parent Reference</button>
  <span class=gap></span>
  <button class="tag in" data-p=in>into the mix</button>
  <button class="tag maybe" data-p=maybe>maybe</button>
  <button class="tag no" data-p=no>no</button>
</div>
</div>
"""

pids = sorted({c["pid"] for c in cells})
pid_opts = "".join(f"<option value=\"{escape(p)}\">{escape(p)}</option>" for p in pids)

T = f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Mix Track Pool v3 (90s Islands · 4-Bar Inpaint Bridge & A2A)</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet"><link rel="stylesheet" href="evals.css">
<style>.wrap{{max-width:920px;padding-bottom:100px}}.ex{{background:#fff;border:1px solid var(--rule);border-left:3px solid var(--edge);padding:10px 12px;font-size:12.5px;margin:10px 0;line-height:1.6}}.un{{color:#c0392b}}
#bar{{position:sticky;top:0;background:var(--paper);padding:8px 0;border-bottom:1px solid var(--rule);z-index:5;font-size:13px}}#bar select,#bar button{{font:inherit;font-size:12px;padding:5px 8px;margin:2px 2px 2px 0}}#bar b{{color:var(--ink)}}
.card{{border:1px solid var(--rule);background:#fff;padding:12px 14px;margin:10px 0;border-left:4px solid var(--rule);border-radius:4px}}.card.p-in{{border-left-color:var(--edge)}}.card.p-maybe{{border-left-color:#c9a227}}.card.p-no{{opacity:.5}}.card.now{{outline:2px solid var(--edge)}}
.top{{display:flex;align-items:center;flex-wrap:wrap;gap:6px;margin-bottom:4px}}
.tid{{font-weight:600;color:var(--ink);font-size:13px}}
.badge{{font-size:11px;padding:2px 6px;border-radius:3px;font-weight:500;border:1px solid var(--rule)}}
.badge.badge-direct{{background:#e8f5e9;color:#1b5e20;border-color:#c8e6c9}}
.badge.badge-a2a{{background:#f3e5f5;color:#4a148c;border-color:#e1bee7}}
.badge.bpm{{background:#e0f7fa;color:#006064;border-color:#b2ebf2}}
.badge.model{{background:var(--paper-dim);color:var(--ink)}}
.mode-desc{{font-size:11.5px;color:#555;margin:2px 0 6px;font-style:italic}}
.dim{{color:var(--dim);font-size:11.5px;margin-left:auto}}
.prompt{{font-size:12.5px;margin:4px 0 2px;overflow-wrap:anywhere;color:var(--body);line-height:1.4}}
.prompt-ext{{font-size:12px;margin:2px 0 4px;overflow-wrap:anywhere;color:#4a148c;line-height:1.4}}
.subinfo{{font-size:11.5px;color:var(--dim);margin:6px 0 4px;display:flex;align-items:center;flex-wrap:wrap;gap:4px}}
.part-badge{{font-size:11px;padding:2px 6px;border-radius:3px;border:1px solid #ddd}}
.part-island{{background:#f0f4f8;color:#2c3e50;border-color:#cfd8dc;font-weight:500}}
.part-bridge{{background:#fff8e1;color:#b78103;border-color:#ffe082;font-weight:600}}
.junctions{{font-size:11.5px;color:var(--ink);margin:4px 0 8px;display:flex;align-items:center;flex-wrap:wrap;gap:6px}}
.junc-badge{{background:#fff3e0;color:#d84315;border:1px solid #ffcc80;padding:2px 6px;border-radius:3px;font-size:11px}}
.row{{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-top:8px}}
button.cell{{font:inherit;font-size:12px;padding:6px 12px;cursor:pointer;border:1px solid var(--rule);background:var(--paper-dim);color:var(--ink);border-radius:3px}}button.cell:hover{{border-color:var(--edge);background:#fff}}
button.cell.core{{background:#fff8e1;border-color:#ffe082;color:#f57f17}}button.cell.core:hover{{background:#fffde7;border-color:#f57f17}}
button.cell.parent{{background:#e0f2f1;border-color:#b2dfdb;color:#00796b}}button.cell.parent:hover{{background:#e8f5e9;border-color:#80cbc4}}
button.cell.playing{{background:var(--edge);color:#fff;border-color:var(--edge)}}
.gap{{flex:1}}
button.tag{{font:inherit;font-size:12px;padding:4px 10px;cursor:pointer;border:1px solid var(--rule);background:#fff;border-radius:3px}}button.tag:hover{{border-color:var(--ink)}}
button.tag.in.active{{background:var(--edge);color:#fff;border-color:var(--edge)}}
button.tag.maybe.active{{background:#c9a227;color:#fff;border-color:#c9a227}}
button.tag.no.active{{background:#c0392b;color:#fff;border-color:#c0392b}}
#err{{display:none;background:#fde8e8;color:#9b1c1c;padding:6px 10px;margin-bottom:8px;border:1px solid #f8b4b4;font-size:12px}}
</style></head>
<body><div class=wrap>
<div style="font-size:12px;color:var(--dim);margin-bottom:4px"><a href="index.html">← evaluations index</a></div>
<h1>Mix Track Pool v3 (90s Islands · 4-Bar Inpaint Bridge & A2A)</h1>
<p class=dim style="margin:2px 0 10px">100% AVP Full-FT ep80 (Kim's music) · Zero-crossing beat-quantized islands · Exact 16-beat inpainting · Bilateral harmonic context</p>

<div id=err>A tag did not save. Check the connection and tap it again.</div>

<div class=ex>
<b>Architecture & Why It Fixes Beat Map Disintegration:</b>
<ul style="margin:4px 0 6px 18px;padding:0">
<li><b>Shared Harmonic DNA:</b> Rather than stitching independent renders, two non-overlapping 12-bar blocks (divisible by 4 beats) are harvested from the <i>same</i> 90s parent render at zero crossings. Island A provides the opening groove; Island B provides the destination groove.</li>
<li><b>Bilateral Context Inpainting:</b> The generator receives context from <b>both sides</b>. Instead of an open-ended continuation running blind, the 4-bar gap (exact 16 beats) is inpainted between Island A and Island B using the extension prompt.</li>
<li><b>Mode A (Direct Inpaint Bridge):</b> Direct 16-beat inpainting with the extension prompt (max 2 terms) connecting Island A and original Island B.</li>
<li><b>Mode B (A2A 0.60 + Inpaint Bridge):</b> Island B is first restyled via Audio-to-Audio (sigma = 0.60 noise) using the extension prompt (introducing hardware leads/timbre while preserving groove), then bridged with the 16-beat inpaint.</li>
<li><b>Backing Reference:</b> Every card includes direct buttons to audition Island A alone or the entire 90s parent reference render.</li>
</ul>
</div>

<div class=ex style="border-left-color:#7b1fa2;background:#fdf7ff">
<b>🧪 A/B Laboratory: Inpainting & Bridge Architectures (Prompt <code>p00</code>, 143 BPM)</b>
<p style="margin:4px 0 8px;font-size:12px;color:var(--dim)">
Reference testbed comparing bilateral inpainting vs. unquantized continuation.
</p>
<div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(260px, 1fr));gap:10px;margin-top:6px">
  <div style="background:#fff;border:1px solid #ce93d8;padding:9px 12px;border-radius:4px">
    <b style="color:#1b5e20">1. Mode A: Direct 4-Bar Bridge (47.0s)</b><br>
    <span style="font-size:11px;color:var(--dim)">Exact 16-beat inpaint bridge connecting two 12-bar islands from same 90s parent.</span>
    <div style="margin-top:6px">
      <button class="cell pl" data-f="p00_islands_4bar_direct.m4a">▶ Play Mode A Bridge</button>
    </div>
  </div>

  <div style="background:#fff;border:1px solid #ba68c8;padding:9px 12px;border-radius:4px">
    <b style="color:#4a148c">2. Mode B: A2A (0.60) + Bridge (47.0s)</b><br>
    <span style="font-size:11px;color:var(--dim)">Island B pre-noised to 0.60 to restyle timbre with ext prompt while locking groove, then bridged.</span>
    <div style="margin-top:6px">
      <button class="cell pl" data-f="p00_islands_a2a_060_bridge.m4a">▶ Play Mode B (A2A + Bridge)</button>
    </div>
  </div>

  <div style="background:#fff;border:1px solid #80deea;padding:9px 12px;border-radius:4px">
    <b style="color:#00695c">3. Full 90s Parent Render (90.0s)</b><br>
    <span style="font-size:11px;color:var(--dim)">Single-pass continuous 90s generation of <code>p00</code> with core prompt. Reference for macro-structure.</span>
    <div style="margin-top:6px">
      <button class="cell pl" data-f="p00_parent_90s.m4a">▶ Play Full 90s Parent</button>
    </div>
  </div>

  <div style="background:#fff;border:1px solid #e0e0e0;padding:9px 12px;border-radius:4px">
    <b style="color:#555">4. Unsynced Gap Baseline (44.1s)</b><br>
    <span style="font-size:11px;color:var(--dim)">Arbitrary 5.17s unquantized gap without bar alignment (control condition).</span>
    <div style="margin-top:6px">
      <button class="cell pl" data-f="ab_test_p00_unsynced_gap.m4a">▶ Play Unsynced Gap Baseline</button>
    </div>
  </div>
</div>
</div>

<div id=bar>
  <b>Track:</b> <select id=f-track><option value="">all tracks (p00–p09)</option>{pid_opts}</select>
  <b>Mode:</b> <select id=f-mode><option value="">all modes</option><option value="4bar_direct">Mode A (Direct 4-Bar Bridge)</option><option value="a2a_060_bridge">Mode B (A2A 0.60 + 4-Bar Bridge)</option></select>
  <b>Tag:</b> <select id=f-tag><option value="">all</option><option value="in">into the mix</option><option value="maybe">maybe</option><option value="no">no</option><option value="untagged">untagged</option></select>
  <span style="margin-left:auto;float:right;color:var(--dim)" id=cnt></span>
</div>

<div id=cards>{cards}</div>
<audio id=au preload=none loop></audio>

</div>
<script>
const POOL = "mixtape_trackpool_v3";
const SUB = "mixtape_trackpool_v3";
const API = "/files/ratings.php";
let picks = {{}};
const a = document.getElementById('au');
a.loop = true;
window.a = a;
if (window.__fp_attach) window.__fp_attach(a);
let cur = null;
let isSwitching = false;
let wasPaused = false;
let manualSeek = false;
const card = b => b.closest('.card');

a.addEventListener('ended', () => {{
  a.currentTime = 0;
  a.play().catch(e => console.error("Loop error:", e));
}});

a.addEventListener('pause', () => {{
  if (!isSwitching) {{
    wasPaused = true;
    manualSeek = false;
  }}
  if (cur) {{
    cur.classList.remove('playing');
    if (card(cur)) card(cur).classList.remove('now');
  }}
}});

a.addEventListener('seeking', () => {{
  if (a.paused) {{
    manualSeek = true;
  }}
}});

a.addEventListener('play', () => {{
  if (wasPaused && !isSwitching) {{
    if (!manualSeek) {{
      a.currentTime = 0;
    }}
    wasPaused = false;
    manualSeek = false;
  }}
  if (cur) {{
    cur.classList.add('playing');
    if (card(cur)) card(cur).classList.add('now');
  }}
}});

function paint() {{
  document.querySelectorAll('.card').forEach(c => {{
    const p = picks[c.id] || '';
    c.classList.remove('p-in', 'p-maybe', 'p-no');
    if (p) c.classList.add('p-' + p);
    c.querySelectorAll('button.tag').forEach(b => {{
      b.classList.toggle('active', b.dataset.p === p);
    }});
  }});
  updateFilter();
}}

async function loadPicks() {{
  try {{
    const r = await fetch(API + '?trackpicks=' + encodeURIComponent(POOL), {{cache: 'no-store'}});
    if (r.ok) {{
      const d = await r.json();
      picks = d.picks || {{}};
      paint();
    }}
  }} catch(e) {{
    document.getElementById('cnt').textContent = 'could not load tags';
  }}
}}

function start(b) {{
  const f = SUB + '/' + b.dataset.f;
  const c = card(b);
  const same = a.src.endsWith('/' + f);
  const isPlaying = !a.paused && !a.ended && a.currentTime > 0;
  const t = isPlaying ? a.currentTime : 0;

  if (cur && cur !== b) {{
    cur.classList.remove('playing');
    if (card(cur)) card(cur).classList.remove('now');
  }}
  cur = b;
  b.classList.add('playing');
  if (c) c.classList.add('now');

  if (same) {{
    // Was paused/stopped: restart from beginning
    a.currentTime = 0;
    wasPaused = false;
    manualSeek = false;
    a.play().catch(e => console.error("Play error:", e));
    return;
  }}

  if (isPlaying && t > 0) {{
    // Keep playing and preserve playhead when switching
    isSwitching = true;
    wasPaused = false;
    manualSeek = false;
    a.src = f;

    let seekDone = false;
    const applySeek = () => {{
      if (seekDone) return;
      const d = a.duration;
      if (d && isFinite(d) && d > 0) {{
        a.currentTime = (t < d) ? t : (t % d);
        seekDone = true;
      }}
    }};

    a.addEventListener('loadedmetadata', applySeek, {{ once: true }});
    a.addEventListener('canplay', applySeek, {{ once: true }});

    const p = a.play();
    if (p !== undefined) {{
      p.then(() => {{
        applySeek();
        setTimeout(() => {{ isSwitching = false; }}, 80);
      }}).catch(err => {{
        console.error("Audio playback error:", err);
        isSwitching = false;
      }});
    }} else {{
      setTimeout(() => {{ isSwitching = false; }}, 80);
    }}
  }} else {{
    // Was paused/stopped: restart from beginning
    isSwitching = false;
    wasPaused = false;
    manualSeek = false;
    a.src = f;
    a.currentTime = 0;

    a.addEventListener('loadedmetadata', () => {{
      a.currentTime = 0;
    }}, {{ once: true }});

    const p = a.play();
    if (p !== undefined) {{
      p.then(() => {{
        a.currentTime = 0;
      }}).catch(err => console.error("Playback error:", err));
    }}
  }}
}}

document.addEventListener('click', async e => {{
  const b = e.target.closest('button');
  if (!b) return;
  if (b.classList.contains('cell')) {{
    if (cur === b && !a.paused) {{
      a.pause();
      b.classList.remove('playing');
      if (card(b)) card(b).classList.remove('now');
      cur = null;
      return;
    }}
    start(b);
    return;
  }}
  if (b.classList.contains('tag')) {{
    const c = card(b);
    if (!c) return;
    const id = c.id;
    const was = picks[id] || '';
    const p = (was === b.dataset.p) ? '' : b.dataset.p;
    if (p) picks[id] = p; else delete picks[id];
    paint();
    const payload = {{
      type: 'trackpick',
      pool: POOL,
      id: id,
      pick: p || 'clear',
      source: 'v3_islands'
    }};
    try {{
      let res = await fetch(API, {{
        method: "POST",
        headers: {{"Content-Type": "application/json"}},
        body: JSON.stringify(payload)
      }});
      if (res.status === 429) {{
        await new Promise(r => setTimeout(r, 200));
        res = await fetch(API, {{
          method: "POST",
          headers: {{"Content-Type": "application/json"}},
          body: JSON.stringify(payload)
        }});
      }}
      if (!res.ok) throw new Error('Save failed: ' + res.status);
      document.getElementById('err').style.display = 'none';
    }} catch(err) {{
      if (was) picks[id] = was; else delete picks[id];
      paint();
      document.getElementById('err').style.display = 'block';
    }}
  }}
}});

a.addEventListener('pause', () => {{
  if (cur) {{
    cur.classList.remove('playing');
    if (card(cur)) card(cur).classList.remove('now');
  }}
}});

function updateFilter() {{
  const trk = document.getElementById("f-track").value;
  const mod = document.getElementById("f-mode").value;
  const tg = document.getElementById("f-tag").value;
  let vis = 0, tot = 0;
  document.querySelectorAll(".card").forEach(c => {{
    tot++;
    let show = true;
    if (trk && c.dataset.pid !== trk) show = false;
    if (mod && c.dataset.mode !== mod) show = false;
    if (tg) {{
      const p = picks[c.id];
      if (tg === "untagged" && p) show = false;
      else if (tg !== "untagged" && p !== tg) show = false;
    }}
    c.style.display = show ? "" : "none";
    if (show) vis++;
  }});
  document.getElementById("cnt").textContent = `${{vis}} / ${{tot}} shown`;
}}

document.getElementById("f-track").addEventListener("change", updateFilter);
document.getElementById("f-mode").addEventListener("change", updateFilter);
document.getElementById("f-tag").addEventListener("change", updateFilter);

loadPicks();
</script>
<footer style="margin:18px 12px 70px;font-size:11.5px;color:var(--dim)">evals · EXPERIMENTS F7 · AVP ONLY</footer>
</body></html>"""

out_html = f"{ST}/{SUB}.html"
with open(out_html, "w") as f:
    f.write(inject(T))

print(f"Wrote {out_html} with float player injected.")
