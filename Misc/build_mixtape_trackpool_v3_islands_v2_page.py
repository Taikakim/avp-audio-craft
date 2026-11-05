#!/usr/bin/env python3
"""build_mixtape_trackpool_v3_islands_v2_page.py -- tagging page for Mixtape Track Pool V3 Islands V2.

Features:
- Reads cells_islands_v2.jsonl from /run/media/kim/Mantu/sa3_lora_runs/mixtape_trackpool_v3_islands_v2/
- Follows docs/eval-page-standard.md (floating player, keyboard hotkeys, localStorage, pure relative URLs).
- Generates clean HTML at ~/evals_aac/mixtape_trackpool_v3_islands_v2.html.
"""
import json
import os
import sys
from html import escape

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from float_player import inject

POOL = "/run/media/kim/Mantu/sa3_lora_runs/mixtape_trackpool_v3_islands_v2"
NAME = "mixtape_trackpool_v3_islands_v2"
ST = os.path.expanduser("~/evals_aac")
SUB = "mixtape_trackpool_v3_islands_v2"
os.makedirs(f"{ST}/{SUB}", exist_ok=True)

manifest = f"{POOL}/cells_islands_v2.jsonl"
if not os.path.exists(manifest):
    print(f"Manifest not found yet: {manifest}")
    sys.exit(0)

cells = [json.loads(l) for l in open(manifest) if l.strip()]

def fmt_time(s):
    s_int = int(s)
    frac = int(round((s - s_int) * 10))
    m = s_int // 60
    sec = s_int % 60
    return f"{m}:{sec:02d}.{frac}"

def sort_key(c):
    mode_order = {"direct_20s_bridge": 0, "a2a_b1_050_bridge": 1, "a2a_b2_050_bridge": 2}
    return (c.get("pid", ""), mode_order.get(c.get("mode", ""), 9))

cells.sort(key=sort_key)

cards = ""
for c in cells:
    mode = c.get("mode", "")
    if mode == "direct_20s_bridge":
        mode_label = "Mode A: Direct 20s+ Div4 Bridge"
        mode_class = "badge-direct"
        mode_desc = f"Clean {c['bridge_bars']}-bar inpaint bridge ({c['dur_gap']:.1f}s) between Island A & Island B from same 90s parent"
    elif mode == "a2a_b1_050_bridge":
        mode_label = "Mode B1: A2A (0.50 Noise, Seed+88) + Bridge"
        mode_class = "badge-b1"
        mode_desc = f"Island B restyled via A2A (0.50 noise, Seed+88) with enriched prompt, then {c['bridge_bars']}-bar bridge"
    elif mode == "a2a_b2_050_bridge":
        mode_label = "Mode B2: A2A (0.50 Noise, Seed+89) + Bridge"
        mode_class = "badge-b2"
        mode_desc = f"Island B restyled via A2A (0.50 noise, Seed+89) with enriched prompt, then {c['bridge_bars']}-bar bridge"
    else:
        mode_label = mode
        mode_class = "badge-other"
        mode_desc = ""

    pid = c["pid"]
    dur = c["dur"]
    dur_a = c["dur_a"]
    dur_gap = c["dur_gap"]
    dur_b = c["dur_b"]
    gap_start = c["gap_start"]
    gap_end = c["gap_end"]

    cards += f"""<div class=card id="{c['id']}" data-pid="{escape(pid)}" data-mode="{escape(mode)}"><div class=top><span class=tid>{c['id']}</span> <span class="badge {mode_class}">{mode_label}</span> <span class="badge bpm">{c['bpm']:.1f} BPM</span> <span class="badge key">{c.get('key', 'unknown')}</span> <span class="badge model">Full-FT w={c.get('fullft_w', 1.0):.2f}</span> <span class=dim>Dur {dur:.1f}s · Seed {c['seed']}</span></div>
<div class=mode-desc>{mode_desc}</div>
<div class=prompt><b>Prompt Core:</b> {escape(c.get('prompt_core', ''))}</div>
<div class=prompt-ext><b>Prompt Ext:</b> {escape(c.get('prompt_ext', ''))}</div>
<div class=prompt-bridge><b>Bridge Prompt:</b> {escape(c.get('prompt_bridge', ''))}</div>
<div class=subinfo>
  <b>Timeline:</b>
  <span class="part-badge part-island">Island A: 0:00 – {fmt_time(gap_start)} ({dur_a:.1f}s / 8 bars)</span> ➔ 
  <span class="part-badge part-bridge">Inpaint Bridge: {fmt_time(gap_start)} – {fmt_time(gap_end)} ({dur_gap:.1f}s / {c['bridge_bars']} bars)</span> ➔ 
  <span class="part-badge part-island">Island B: {fmt_time(gap_end)} – {fmt_time(dur)} ({dur_b:.1f}s / 8 bars)</span>
</div>
<div class=junctions>
  <b>Bilateral Seams:</b>
  <span class="junc-badge">⚡ Bridge In @ <b>{fmt_time(gap_start)}</b></span>
  <span class="junc-badge">⚡ Bridge Out @ <b>{fmt_time(gap_end)}</b></span>
  <span class=dim style="margin-left:auto">Madmom/Librosa beat snap · CFG 10.0 · 24 steps · A2A noise {c.get('a2a_noise', 0.50)}</span>
</div>
<div class=row>
  <button class="cell pl" data-f="{SUB}/{c['id']}.m4a">▶ Play Full Track ({dur:.1f}s)</button>
  <button class="cell core" data-f="{SUB}/{pid}_core.m4a">🎯 Island A Core ({dur_a:.1f}s)</button>
  <button class="cell parent" data-f="{SUB}/{pid}_parent_90s.m4a">🏛️ 90s Parent Reference</button>
  <span class=gap></span>
  <button class="tag in" data-p=in>into the mix</button>
  <button class="tag maybe" data-p=maybe>maybe</button>
  <button class="tag no" data-p=no>no</button>
</div>
</div>
"""

pids = sorted({c["pid"] for c in cells})
pid_opts = "".join(f"<option value=\"{escape(p)}\">{escape(p)}</option>" for p in pids)

T = f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Mix Track Pool v3 (Islands V2: 20s+ Div4 Bridge · 0.50 Denoising · Dual Island B)</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet"><link rel="stylesheet" href="evals.css">
<style>.wrap{{max-width:940px;padding-bottom:100px}}.ex{{background:#fff;border:1px solid var(--rule);border-left:3px solid var(--edge);padding:10px 12px;font-size:12.5px;margin:10px 0;line-height:1.6}}.un{{color:#c0392b}}
#bar{{position:sticky;top:0;background:var(--paper);padding:8px 0;border-bottom:1px solid var(--rule);z-index:5;font-size:13px}}#bar select,#bar button{{font:inherit;font-size:12px;padding:5px 8px;margin:2px 2px 2px 0}}#bar b{{color:var(--ink)}}
.card{{border:1px solid var(--rule);background:#fff;padding:12px 14px;margin:10px 0;border-left:4px solid var(--rule);border-radius:4px}}.card.p-in{{border-left-color:var(--edge)}}.card.p-maybe{{border-left-color:#c9a227}}.card.p-no{{opacity:.5}}.card.now{{outline:2px solid var(--edge)}}
.top{{display:flex;align-items:center;flex-wrap:wrap;gap:6px;margin-bottom:4px}}
.tid{{font-weight:600;color:var(--ink);font-size:13px}}
.badge{{font-size:11px;padding:2px 6px;border-radius:3px;font-weight:500;border:1px solid var(--rule)}}
.badge.badge-direct{{background:#e8f5e9;color:#1b5e20;border-color:#c8e6c9}}
.badge.badge-b1{{background:#e1f5fe;color:#01579b;border-color:#b3e5fc}}
.badge.badge-b2{{background:#f3e5f5;color:#4a148c;border-color:#e1bee7}}
.badge.bpm{{background:#fff3e0;color:#e65100;border-color:#ffe0b2}}
.badge.key{{background:#fbe9e7;color:#bf360c;border-color:#ffccbc}}
.badge.model{{background:#ede7f6;color:#311b92;border-color:#d1c4e9}}
.dim{{color:var(--muted);font-size:11px}}
.mode-desc{{font-size:11.5px;color:#2c3e50;margin:3px 0 6px;font-style:italic}}
.prompt,.prompt-ext,.prompt-bridge{{font-size:12px;color:var(--ink);margin:2px 0;line-height:1.4}}
.subinfo{{font-size:11.5px;color:var(--muted);margin:6px 0 4px;padding:4px 6px;background:#fcfcfc;border-radius:3px;border:1px dashed var(--rule);display:flex;align-items:center;flex-wrap:wrap;gap:4px}}
.part-badge{{display:inline-block;padding:2px 5px;border-radius:3px;font-size:11px;font-weight:500}}
.part-island{{background:#e8f4fd;color:#0d47a1}}
.part-bridge{{background:#fff9c4;color:#f57f17;font-weight:600}}
.junctions{{font-size:11px;color:#444;margin:4px 0 8px;display:flex;align-items:center;flex-wrap:wrap;gap:8px}}
.junc-badge{{background:#fff3e0;color:#d84315;padding:1px 6px;border-radius:3px;border:1px solid #ffe0b2}}
.row{{display:flex;gap:6px;align-items:center;margin-top:6px;flex-wrap:wrap}}
.cell{{background:#fff;border:1px solid var(--rule);padding:5px 9px;border-radius:3px;cursor:pointer;font:inherit;font-size:11.5px;color:var(--ink)}}.cell:hover{{border-color:var(--edge);color:var(--edge)}}
.cell.pl{{background:var(--edge);color:#fff;border-color:var(--edge);font-weight:500}}.cell.pl:hover{{opacity:.9}}
.cell.core{{background:#f8f9fa;color:#333;font-weight:500}}
.cell.parent{{background:#f8f9fa;color:#666}}
.cell.playing{{background:#000!important;color:#fff!important;border-color:#000!important}}
.gap{{flex:1}}
.tag{{border:1px solid var(--rule);background:#fff;padding:4px 8px;border-radius:3px;cursor:pointer;font:inherit;font-size:11px;color:var(--muted)}}
.tag.in.on{{background:var(--edge);color:#fff;border-color:var(--edge)}}
.tag.maybe.on{{background:#c9a227;color:#fff;border-color:#c9a227}}
.tag.no.on{{background:#e74c3c;color:#fff;border-color:#e74c3c}}
</style></head><body>
<div class=wrap>
<p><a href="index.html">&larr; back to all evaluations</a></p>
<h1>Mix Track Pool v3 (Islands V2: 20s+ Div4 Bridge · 0.50 Denoising · Dual Island B)</h1>
<div class=ex>
  <b>Audit Improvements Applied:</b><br>
  1. <b>Long Compositional Bridge (&ge; 20.0s, Divisible by 4 Bars):</b> Middle inpaint section expanded to 12-16 bars (20.1s – 28.2s). The bridge now constitutes 43–50% of the entire track, providing a genuine compositional transition rather than an abrupt 6s seam.<br>
  2. <b>Moderate A2A Denoising (0.50):</b> Lowered from 0.60 to 0.50 to anchor pitch center, key, and steady tempo while restyling synth textures.<br>
  3. <b>Dual Destination Islands (Island B1 & Island B2):</b> Two distinct destination targets (Seed+88 and Seed+89) with dedicated inpaint bridges.<br>
  4. <b>Dynamic Bridge Steering:</b> Mode A utilizes dedicated transitional prompting and seed differentiation to generate active build-ups rather than repeating parent loops.
</div>
<div id=bar>
  <label>Filter: <select id=filter-pid><option value="">All Prompts</option>{pid_opts}</select></label>
  <label><select id=filter-mode><option value="">All Modes</option><option value="direct_20s_bridge">Mode A: Direct 20s+ Bridge</option><option value="a2a_b1_050_bridge">Mode B1: A2A (0.50 Seed+88) + Bridge</option><option value="a2a_b2_050_bridge">Mode B2: A2A (0.50 Seed+89) + Bridge</option></select></label>
  <label><select id=filter-tag><option value="">All Tags</option><option value=in>Into mix</option><option value=maybe>Maybe</option><option value=no>No</option><option value=untagged>Untagged</option></select></label>
  <span style="margin-left:12px"><b>Counts:</b> In: <span id=cnt-in>0</span> · Maybe: <span id=cnt-maybe>0</span> · No: <span id=cnt-no>0</span> / <span id=cnt-tot>0</span></span>
  <span style="float:right"><button id=btn-export>Export JSON</button></span>
</div>
<div id=cardlist>
{cards}
</div>
</div>
<script>
const NAME = '{NAME}';
let picks = JSON.parse(localStorage.getItem(NAME + '_picks') || '{{}}');

function save() {{
  localStorage.setItem(NAME + '_picks', JSON.stringify(picks));
  render();
}}

function render() {{
  let inC = 0, maybeC = 0, noC = 0, tot = 0;
  const selPid = document.getElementById('filter-pid').value;
  const selMode = document.getElementById('filter-mode').value;
  const selTag = document.getElementById('filter-tag').value;

  document.querySelectorAll('.card').forEach(card => {{
    const id = card.id;
    const pid = card.dataset.pid;
    const mode = card.dataset.mode;
    const p = picks[id];

    if (p === 'in') inC++;
    else if (p === 'maybe') maybeC++;
    else if (p === 'no') noC++;
    tot++;

    card.classList.remove('p-in', 'p-maybe', 'p-no');
    if (p) card.classList.add('p-' + p);

    card.querySelectorAll('.tag').forEach(t => {{
      t.classList.toggle('on', t.dataset.p === p);
    }});

    let show = true;
    if (selPid && pid !== selPid) show = false;
    if (selMode && mode !== selMode) show = false;
    if (selTag) {{
      if (selTag === 'untagged' && p) show = false;
      else if (selTag !== 'untagged' && p !== selTag) show = false;
    }}
    card.style.display = show ? '' : 'none';
  }});

  document.getElementById('cnt-in').textContent = inC;
  document.getElementById('cnt-maybe').textContent = maybeC;
  document.getElementById('cnt-no').textContent = noC;
  document.getElementById('cnt-tot').textContent = tot;
}}

document.addEventListener('click', e => {{
  if (e.target.matches('.tag')) {{
    const card = e.target.closest('.card');
    const id = card.id;
    const p = e.target.dataset.p;
    picks[id] = (picks[id] === p) ? undefined : p;
    if (!picks[id]) delete picks[id];
    save();
  }}
}});

document.getElementById('filter-pid').addEventListener('change', render);
document.getElementById('filter-mode').addEventListener('change', render);
document.getElementById('filter-tag').addEventListener('change', render);

document.getElementById('btn-export').addEventListener('click', () => {{
  const blob = new Blob([JSON.stringify(picks, null, 2)], {{type: 'application/json'}});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = NAME + '_picks.json';
  a.click();
}});

window.addEventListener('keydown', e => {{
  if (e.target.matches('input, select, textarea')) return;
  const now = document.querySelector('.card.now') || document.querySelector('.card');
  if (!now) return;
  const id = now.id;
  if (e.key === '1') {{ picks[id] = 'in'; save(); }}
  else if (e.key === '2') {{ picks[id] = 'maybe'; save(); }}
  else if (e.key === '3') {{ picks[id] = 'no'; save(); }}
  else if (e.key === 'j') {{
    const next = now.nextElementSibling;
    if (next && next.classList.contains('card')) {{
      now.classList.remove('now');
      next.classList.add('now');
      next.scrollIntoView({{block: 'nearest'}});
    }}
  }}
  else if (e.key === 'k') {{
    const prev = now.previousElementSibling;
    if (prev && prev.classList.contains('card')) {{
      now.classList.remove('now');
      prev.classList.add('now');
      prev.scrollIntoView({{block: 'nearest'}});
    }}
  }}
}});

render();
</script>
</body></html>
"""

html_out = f"{ST}/{NAME}.html"
final_html = inject(T)
with open(html_out, "w") as f:
    f.write(final_html)

print(f"Generated evaluation page: {html_out}")
