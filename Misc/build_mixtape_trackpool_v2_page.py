#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-11-03, v2 updated 2026-11-04)
"""build_mixtape_trackpool_v2_page.py -- tagging page for the re-rendered DJ-mix track pool v2.

Encodes each WAV to AAC 192k into ~/evals_aac/mixtape_trackpool_v2/ (skips existing)
and writes ~/evals_aac/mixtape_trackpool_v2.html following docs/eval-page-standard.md.

Features:
- 100% AVP models (Kim's own music).
- 80s renders: 30s core at 25s–55s, extended 25s backward and 25s forward.
- Full-FT weight math: static 1.0, SLERP 0.75, magnitude-anchored 1.25.
- Both Base Medium (24 steps, CFG 6.0) and Post-Trained Medium (8 steps, CFG 1.0).
- Checkpoint filename provenance cleanly noted per clip (no filesystem drive leaks).
- Filter controls for Engine, Model, and Rating tags.
- Tagging synchronised with /files/ratings.php (pool: mixtape_trackpool_v2).
- Same-playhead tracking and float_player transport bar.
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

POOL = "/run/media/kim/Mantu/sa3_lora_runs/mixtape_trackpool_v2"
NAME = "mixtape_trackpool_v2"
ST = os.path.expanduser("~/evals_aac")
SUB = "mixtape_trackpool_v2"
CORE_S = 25.0
os.makedirs(f"{ST}/{SUB}", exist_ok=True)

manifest_file = f"{POOL}/cells.jsonl"
if not os.path.exists(manifest_file):
    print("No manifest found yet.")
    sys.exit(0)

cells = [json.loads(l) for l in open(manifest_file) if l.strip()]

def encode(c):
    dst = f"{ST}/{SUB}/{c['id']}.m4a"
    src = f"{POOL}/{c['id']}.wav"
    if os.path.exists(src) and not os.path.exists(dst):
        subprocess.run(["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-i", src, "-c:a", "aac", "-b:a", "192k", dst], check=True)
    return dst

print(f"Encoding {len(cells)} clips to AAC 192k in {ST}/{SUB}...")
with ThreadPoolExecutor(8) as ex:
    list(ex.map(encode, cells))

# Sort cells by prompt index, backend, then weight
def sort_key(c):
    return (c.get("pid", ""), 0 if c["backend"] == "base" else 1, c["weight"])

cells.sort(key=sort_key)

cards = ""
for c in cells:
    b_label = "Base Medium (24st, CFG 6)" if c["backend"] == "base" else "PTM (8st, CFG 1)"
    b_class = "eng-base" if c["backend"] == "base" else "eng-ptm"
    w_label = f"w {c['weight']:.2f}"
    if c.get("kind") == "fullft":
        if abs(c["weight"] - 0.75) < 1e-4: w_label += " (slerp)"
        elif abs(c["weight"] - 1.0) < 1e-4: w_label += " (static)"
        elif abs(c["weight"] - 1.25) < 1e-4: w_label += " (mag-anchored)"
    else:
        w_label += " (adapter)"

    # Clean checkpoint representation without drive leaks
    ckpt_full = c.get("ckpt", "")
    ckpt_name = os.path.basename(ckpt_full)

    cards += f"""<div class=card id="{c['id']}" data-engine="{c['backend']}" data-model="{escape(c['model'])}" data-arm="{escape(c['model'])}"><div class=top><span class=tid>{c['id']}</span> <span class="badge {b_class}">{b_label}</span> <span class="badge arm">{escape(c['model'])}</span> <span class="badge wgt">{w_label}</span> <span class=dim>RMS {c.get('rms_db', 0):.1f} dB · Peak {c.get('peak', 0):.3f}</span></div>
<div class=prompt><b>[{c['pid']}]</b> {escape(c['prompt'])}</div>
<div class=ckpt><b>Checkpoint:</b> <code>{escape(ckpt_name)}</code></div>
<div class=row><button class="cell pl" data-f="{c['id']}.m4a">▶ play (80s)</button> <button class="cell core" data-f="{c['id']}.m4a" data-core="{CORE_S}">🎯 core (25s)</button><span class=gap></span><button class="tag in" data-p=in>into the mix</button> <button class="tag maybe" data-p=maybe>maybe</button> <button class="tag no" data-p=no>no</button></div></div>
"""

models = sorted({c["model"] for c in cells})
model_opts = "".join(f"<option value=\"{escape(m)}\">{escape(m)}</option>" for m in models)

T = f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Mix Track Pool v2 (100% AVP · Correct Math)</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet"><link rel="stylesheet" href="evals.css">
<style>.wrap{{max-width:860px;padding-bottom:90px}}.ex{{background:#fff;border:1px solid var(--rule);border-left:3px solid var(--edge);padding:10px 12px;font-size:12.5px;margin:10px 0;line-height:1.6}}.un{{color:#c0392b}}
#bar{{position:sticky;top:0;background:var(--paper);padding:8px 0;border-bottom:1px solid var(--rule);z-index:5;font-size:13px}}#bar select,#bar button{{font:inherit;font-size:12px;padding:5px 8px;margin:2px 2px 2px 0}}#bar b{{color:var(--ink)}}
.card{{border:1px solid var(--rule);background:#fff;padding:10px 12px;margin:8px 0;border-left:4px solid var(--rule)}}.card.p-in{{border-left-color:var(--edge)}}.card.p-maybe{{border-left-color:#c9a227}}.card.p-no{{opacity:.5}}.card.now{{outline:2px solid var(--edge)}}
.top{{display:flex;align-items:center;flex-wrap:wrap;gap:6px;margin-bottom:4px}}
.tid{{font-weight:600;color:var(--ink);font-size:12.5px}}
.badge{{font-size:11px;padding:2px 6px;border-radius:2px;font-weight:500;border:1px solid var(--rule)}}
.badge.eng-base{{background:#e8eaf6;color:#283593;border-color:#c5cae9}}
.badge.eng-ptm{{background:#e0f2f1;color:#004d40;border-color:#b2dfdb}}
.badge.arm{{background:var(--paper-dim);color:var(--ink)}}
.badge.wgt{{background:#f3e5f5;color:#4a148c;border-color:#e1bee7}}
.dim{{color:var(--dim);font-size:11.5px;margin-left:auto}}
.prompt{{font-size:12.5px;margin:4px 0 3px;overflow-wrap:anywhere;color:var(--body);line-height:1.4}}
.ckpt{{font-size:11px;color:var(--dim);margin-bottom:6px}}
.ckpt code{{font-size:11px;color:var(--ink);background:var(--paper-dim)}}
.row{{display:flex;flex-wrap:wrap;gap:6px;align-items:center}}.gap{{flex-basis:100%;height:0}}.row button{{font:inherit;font-size:12px;padding:7px 11px;min-height:36px;cursor:pointer;border:1px solid var(--rule);border-radius:3px;background:var(--paper-dim);color:var(--ink)}}
.row .cell.playing{{background:var(--edge);color:#fff}}.tag.on.in{{background:var(--edge);color:#fff;border-color:var(--edge)}}.tag.on.maybe{{background:#c9a227;color:#000;border-color:#c9a227}}.tag.on.no{{background:#555;color:#fff;border-color:#555}}
#err{{display:none;background:#c0392b;color:#fff;padding:4px 10px;font-weight:600;margin:6px 0}}
</style></head><body>
<div class=wrap><p class=over>VIBE ON THE EDG3 · EVALS</p><p class=nav><a href="index.html">← all evals</a> &nbsp; <a href="mixtape_trackpool.html">← v1 trackpool (linear delta)</a></p><h1>Mix track pool v2: 100% AVP models <span class=un title="Not tagged yet">❗</span></h1>
<div class=ex><b>What this is for.</b> Re-render of the mixtape track pool ({len(cells)} clips, 10 prompts) addressing the comb-filter delay artifact discovered in v1.
<br><b>Root cause & fix.</b> Naive linear delta extrapolation (<code>base + w*(ft - base)</code>) destroyed attention head orthogonality. Fixed using <b>SLERP</b> for interpolation (w=0.75) and <b>magnitude-anchored task vectors</b> for extrapolation (w=1.25), preserving tensor norm and subspace geometry.
<br><b>100% AVP models.</b> Replaced non-AVP runs with native AVP equivalents: <code>subloss_k24_avpaug</code> and <code>dora128adj_avp_8ep_final</code>. All models here are trained strictly on Kim's music.
<br><b>Engines.</b> Each prompt/model is rendered with both <b>Base Medium</b> (24 steps, CFG 6.0, Flux distribution shift) and <b>Post-Trained Medium</b> (8 steps, CFG 1.0, uniform logSNR schedule $\lambda \in [-6.2, 2.0]$ per SA3 paper §4).
<br><b>Clips & Core.</b> 80 seconds per clip: 30s core generated at 25s–55s, extended 25s forward and backward. Tap <b>core</b> to jump directly to the 25s core.
<br><b>Presets.</b> Matching GUI-compatible preset JSON files generated in <code>eval/presets/mixtape_v2_10prompts/</code> and verified for exact roundtrip reproduction.
</div>
<div id=bar><b id=cnt>loading tags…</b><br>
<select id=fe><option value="">all engines</option><option value="base">Base Medium</option><option value="ptm">Post-Trained Medium</option></select>
<select id=fa><option value="">all models</option>{model_opts}</select>
<select id=ft><option value="">all tags</option><option value=none>untagged</option><option value=in>into the mix</option><option value=maybe>maybe</option><option value=no>no</option></select>
</div>
<div id=err>A tag did not save. Check the connection and tap it again.</div>
{cards}</div><audio id=au></audio>
<script>
const POOL={json.dumps(NAME)},API='/files/ratings.php',a=document.getElementById('au'),SUB={json.dumps(SUB)},CORE={CORE_S};
let picks={{}},cur=null;
function card(el){{return el.closest('.card')}}
function paint(){{
  document.querySelectorAll('.card').forEach(c=>{{
    const p=picks[c.id]||'';
    c.classList.remove('p-in','p-maybe','p-no');
    if(p) c.classList.add('p-'+p);
    c.querySelectorAll('.tag').forEach(t=>t.classList.toggle('on',t.dataset.p===p));
  }});
  const n=k=>Object.values(picks).filter(v=>v===k).length,t=document.querySelectorAll('.card').length;
  document.getElementById('cnt').textContent=n('in')+' into the mix · '+n('maybe')+' maybe · '+n('no')+' no · '+(t-Object.keys(picks).length)+' untagged, of '+t;
  filt();
}}
function filt(){{
  const fe=document.getElementById('fe').value;
  const fa=document.getElementById('fa').value;
  const ft=document.getElementById('ft').value;
  document.querySelectorAll('.card').forEach(c=>{{
    const p=picks[c.id]||'none';
    const matchE = !fe || c.dataset.engine === fe;
    const matchA = !fa || c.dataset.arm === fa;
    const matchT = !ft || p === ft;
    c.style.display = (matchE && matchA && matchT) ? '' : 'none';
  }});
}}
document.getElementById('fe').onchange=filt;
document.getElementById('fa').onchange=filt;
document.getElementById('ft').onchange=filt;

fetch(API+'?trackpicks='+encodeURIComponent(POOL),{{cache:'no-store'}}).then(r=>r.json()).then(j=>{{picks=j.picks||{{}};paint();}}).catch(()=>{{document.getElementById('cnt').textContent='could not load tags';}});

function start(b,pos){{
  const f=SUB+'/'+b.dataset.f;
  const c=card(b);
  const same=a.src.endsWith('/'+f);
  if(cur&&cur!==b){{cur.classList.remove('playing');card(cur).classList.remove('now');}}
  cur=b;b.classList.add('playing');c.classList.add('now');
  if(same){{if(pos!=null)a.currentTime=pos;a.play();return;}}
  const t=pos!=null?pos:a.currentTime;
  a.src=f;
  a.addEventListener('loadedmetadata',()=>{{
    a.currentTime=Math.min(t,(a.duration||1e9)-.05);
    a.play();
  }},{{once:true}});
}}

document.addEventListener('click',e=>{{
  const b=e.target.closest('button');
  if(!b)return;
  if(b.classList.contains('pl')){{
    if(cur===b&&!a.paused){{a.pause();b.classList.remove('playing');card(b).classList.remove('now');cur=null;return;}}
    start(b,null);
    return;
  }}
  if(b.classList.contains('core')){{
    const cpos = parseFloat(b.dataset.core) || CORE;
    start(b,cpos);
    return;
  }}
  if(b.classList.contains('tag')){{
    const id=card(b).id,was=picks[id]||'',p=was===b.dataset.p?'clear':b.dataset.p;
    if(p==='clear')delete picks[id];else picks[id]=p;
    paint();
    fetch(API,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{type:'trackpick',pool:POOL,id:id,pick:p,source:'trackpool_v2'}})}}).then(r=>{{
      if(!r.ok)throw 0;
      document.getElementById('err').style.display='none';
    }}).catch(()=>{{
      if(was)picks[id]=was;else delete picks[id];
      paint();
      document.getElementById('err').style.display='block';
    }});
  }}
}});
</script>
<footer style="margin:18px 12px 70px">evals · EXPERIMENTS F7 · AVP ONLY</footer></body></html>"""

out_html = f"{ST}/mixtape_trackpool_v2.html"
with open(out_html, "w") as f:
    f.write(inject(T))
print(f"Page generated at {out_html} ({len(cells)} tracks, {len(os.listdir(f'{ST}/{SUB}'))} clips)")
