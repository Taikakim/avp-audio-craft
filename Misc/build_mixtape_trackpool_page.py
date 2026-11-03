#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-11-03)
"""build_mixtape_trackpool_page.py -- tagging page for the replacement DJ-mix track pool (GHOST-NOTE, eval/mixtape_track_pool.py), to docs/eval-page-standard.md.

Encodes each tNNN.wav to AAC 192 k in ~/evals_aac/mixtape_trackpool/ (skips what exists) and writes ~/evals_aac/mixtape_trackpool.html, phone-friendly.
Tags go to /files/ratings.php as type trackpick (pool, id, pick) and load back from ?trackpicks=<pool>, so they follow you between devices. Checkpoint paths stay off the page.
The tagged list is read with the ratings export; each id joins back to cells.jsonl for its recipe.
"""
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from html import escape

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from float_player import inject

POOL = "/run/media/kim/Mantu/sa3_lora_runs/mixtape_trackpool_2026-11-03"
NAME = "mixtape_trackpool_2026-11-03"
ST = os.path.expanduser("~/evals_aac")
SUB = "mixtape_trackpool"
CORE_S = 45
os.makedirs(f"{ST}/{SUB}", exist_ok=True)
cells = [json.loads(l) for l in open(f"{POOL}/cells.jsonl")]


def encode(c):
    dst = f"{ST}/{SUB}/{c['id']}.m4a"
    if not os.path.exists(dst):
        subprocess.run(["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-i", f"{POOL}/{c['id']}.wav", "-c:a", "aac", "-b:a", "192k", dst], check=True)
    return dst


with ThreadPoolExecutor(8) as ex:
    list(ex.map(encode, cells))

cards = ""
for c in cells:
    cards += f"""<div class=card id={c['id']} data-arm="{escape(c['arm'])}"><div class=top><span class=tid>{c['id']}</span> <span class=arm>{escape(c['arm'])}</span> <span class=dim>w {c['w']:.2f} · cfg {c['cfg']:.1f} · {escape(c['prompt_src'])}</span></div>
<div class=prompt>{escape(c['prompt'])}</div>
<div class=row><button class="cell pl" data-f="{c['id']}.m4a">play</button> <button class="cell core" data-f="{c['id']}.m4a">core</button><span class=gap></span><button class="tag in" data-p=in>into the mix</button> <button class="tag maybe" data-p=maybe>maybe</button> <button class="tag no" data-p=no>no</button></div></div>
"""
arms = sorted({c["arm"] for c in cells})
arm_opts = "".join(f"<option>{escape(a)}</option>" for a in arms)
T = f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Mix Track Pool</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet"><link rel="stylesheet" href="evals.css">
<style>.wrap{{max-width:820px;padding-bottom:90px}}.ex{{background:#fff;border:1px solid var(--rule);border-left:3px solid var(--edge);padding:10px 12px;font-size:12.5px;margin:10px 0}}.un{{color:#c0392b}}
#bar{{position:sticky;top:0;background:var(--paper);padding:8px 0;border-bottom:1px solid var(--rule);z-index:5;font-size:13px}}#bar select,#bar button{{font:inherit;font-size:12px;padding:5px 8px;margin:2px 2px 2px 0}}#bar b{{color:var(--ink)}}
.card{{border:1px solid var(--rule);background:#fff;padding:9px 11px;margin:8px 0;border-left:4px solid var(--rule)}}.card.p-in{{border-left-color:var(--edge)}}.card.p-maybe{{border-left-color:#c9a227}}.card.p-no{{opacity:.5}}.card.now{{outline:2px solid var(--edge)}}
.tid{{font-weight:600;color:var(--ink)}}.arm{{font-size:12px}}.dim{{color:var(--dim);font-size:11.5px}}.prompt{{font-size:12.5px;margin:5px 0 8px;overflow-wrap:anywhere}}
.row{{display:flex;flex-wrap:wrap;gap:6px;align-items:center}}.gap{{flex-basis:100%;height:0}}.row button{{font:inherit;font-size:13px;padding:9px 12px;min-height:40px;cursor:pointer;border:1px solid var(--rule);border-radius:3px;background:var(--paper-dim);color:var(--ink)}}
.row .cell.playing{{background:var(--edge);color:#fff}}.tag.on.in{{background:var(--edge);color:#fff;border-color:var(--edge)}}.tag.on.maybe{{background:#c9a227;color:#000;border-color:#c9a227}}.tag.on.no{{background:#555;color:#fff;border-color:#555}}
#err{{display:none;background:#c0392b;color:#000;padding:4px 10px;font-weight:600;margin:6px 0}}</style></head><body>
<div class=wrap><p class=over>VIBE ON THE EDG3 · EVALS</p><p class=nav><a href="index.html">← all evals</a></p><h1>Mix track pool: pick the tracks <span class=un title="Not tagged yet">❗</span></h1>
<div class=ex><b>What this is for.</b> A replacement pool for the DJ mix: {len(cells)} tracks from {len(arms)} models, tested against the old 16 by ear. Each track is 120 s: a 30 s generated core at 45-75 s, extended 45 s each side by the same model and prompt.
<br><b>What to do.</b> Play a track, or press <b>core</b> to jump to its 45 s core. Tap <b>into the mix</b>, <b>maybe</b> or <b>no</b>; tap again to clear. Tags save to the server at once and show on any device. Switching tracks keeps the playhead.
<br><b>Not measured.</b> No disintegration gate, as nothing here steers. Audio checked finite by its renderer. {sum(c['peak'] >= 0.999 for c in cells)} of {len(cells)} tracks peak at full scale, which the ear should judge. w = adapter or fine-tune weight.</div>
<div id=bar><b id=cnt>loading tags…</b><br><select id=fa><option value="">all models</option>{arm_opts}</select><select id=ft><option value="">all</option><option value=none>untagged</option><option value=in>into the mix</option><option value=maybe>maybe</option><option value=no>no</option></select></div>
<div id=err>A tag did not save. Check the connection and tap it again.</div>
{cards}</div><audio id=au></audio>
<script>
const POOL={json.dumps(NAME)},API='/files/ratings.php',a=document.getElementById('au'),SUB={json.dumps(SUB)},CORE={CORE_S};
let picks={{}},cur=null;
function card(el){{return el.closest('.card')}}
function paint(){{document.querySelectorAll('.card').forEach(c=>{{const p=picks[c.id]||'';c.classList.remove('p-in','p-maybe','p-no');if(p)c.classList.add('p-'+p);c.querySelectorAll('.tag').forEach(t=>t.classList.toggle('on',t.dataset.p===p));}});
 const n=k=>Object.values(picks).filter(v=>v===k).length,t=document.querySelectorAll('.card').length;
 document.getElementById('cnt').textContent=n('in')+' into the mix · '+n('maybe')+' maybe · '+n('no')+' no · '+(t-Object.keys(picks).length)+' untagged, of '+t;filt();}}
function filt(){{const fa=document.getElementById('fa').value,ft=document.getElementById('ft').value;document.querySelectorAll('.card').forEach(c=>{{const p=picks[c.id]||'none';c.style.display=((!fa||c.dataset.arm===fa)&&(!ft||p===ft))?'':'none';}});}}
document.getElementById('fa').onchange=filt;document.getElementById('ft').onchange=filt;
fetch(API+'?trackpicks='+encodeURIComponent(POOL),{{cache:'no-store'}}).then(r=>r.json()).then(j=>{{picks=j.picks||{{}};paint();}}).catch(()=>{{document.getElementById('cnt').textContent='could not load tags';}});
function start(b,pos){{const f=SUB+'/'+b.dataset.f;const c=card(b);const same=a.src.endsWith('/'+f);
 if(cur&&cur!==b){{cur.classList.remove('playing');card(cur).classList.remove('now');}}
 cur=b;b.classList.add('playing');c.classList.add('now');
 if(same){{if(pos!=null)a.currentTime=pos;a.play();return;}}
 const t=pos!=null?pos:a.currentTime;a.src=f;a.addEventListener('loadedmetadata',()=>{{a.currentTime=Math.min(t,(a.duration||1e9)-.05);a.play();}},{{once:true}});}}
document.addEventListener('click',e=>{{const b=e.target.closest('button');if(!b)return;
 if(b.classList.contains('pl')){{if(cur===b&&!a.paused){{a.pause();b.classList.remove('playing');card(b).classList.remove('now');cur=null;return;}}start(b,null);return;}}
 if(b.classList.contains('core')){{start(b,CORE);return;}}
 if(b.classList.contains('tag')){{const id=card(b).id,was=picks[id]||'',p=was===b.dataset.p?'clear':b.dataset.p;
  if(p==='clear')delete picks[id];else picks[id]=p;paint();
  fetch(API,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{type:'trackpick',pool:POOL,id:id,pick:p,source:'trackpool'}})}}).then(r=>{{if(!r.ok)throw 0;document.getElementById('err').style.display='none';}}).catch(()=>{{if(was)picks[id]=was;else delete picks[id];paint();document.getElementById('err').style.display='block';}});}}}});
</script>
<footer style="margin:18px 12px 70px">evals · EXPERIMENTS F7</footer></body></html>"""
open(f"{ST}/mixtape_trackpool.html", "w").write(inject(T))
print("wrote", len(cells), "cards,", len(os.listdir(f"{ST}/{SUB}")), "clips")
