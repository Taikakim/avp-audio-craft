#!/usr/bin/env python3
# Owner: GHOST-NOTE (created 2026-10-16)
"""build_bass_grid_page.py -- listening page for eval/bass_head_grid.py: bass head (production, B2 lr 1e-2, B3 lr 1e-3, B4 lr 1e-4; final epoch) x target value x weight (gain multiple),
on the punch 'cleanest' preset, seeds 764 and 3050. Run: python3 Misc/build_bass_grid_page.py -> ~/evals_aac/bass_grid.html (+ bass_grid/*.m4a, AAC 256k). No checkpoint filenames or drive paths."""
import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comment_notes_block import notes_block
from float_player import inject
RUN = "/run/media/kim/Mantu/latch_sweep/bass_lr_2026-10-16/grid"
STAGE = os.path.join(os.path.expanduser("~"), "evals_aac"); OUT = f"{STAGE}/bass_grid"; os.makedirs(OUT, exist_ok=True)
rows = json.load(open(f"{RUN}/grid.json"))
base = {r["seed"]: r["bass_share_db"] for r in rows if r["arm"] == "base"}
cells, jobs = {}, []
for r in rows:
    key = f"s{r['seed']}_{r['arm']}"; f = f"bass_grid/{key}.m4a"
    jobs.append((f"{RUN}/{key}" + ("" if r["arm"] == "base" else "_matched") + ".wav", f"{STAGE}/{f}"))
    cells[key] = {"f": f, "bass": r["bass_share_db"] - base[r["seed"]], "crest": r["crest"], "clk": r["clicks_per_1e4"], "on": r["onset_rate"]}
def enc(j):
    if not os.path.exists(j[1]): subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", j[0], "-c:a", "aac", "-b:a", "256k", j[1]], check=True)
with ThreadPoolExecutor(8) as ex: list(ex.map(enc, jobs))
DATA = json.dumps({"cells": cells, "seeds": sorted(base), "heads": [["production", "production bass head"], ["B2", "B2 lr 1e-2"], ["B3", "B3 lr 1e-3"], ["B4", "B4 lr 1e-4"]],
                   "values": [-16, -10, -4], "mults": [1, 2, 4, 8]})
T = r"""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Bass Head Weight and Target</title><style>
body{font:13px system-ui;margin:0;background:#0e0e10;color:#e0e0e0;max-width:1100px}
#bar{position:sticky;top:0;background:#16181c;padding:7px 12px;border-bottom:1px solid #2a2a30;z-index:9}
#wrap{padding:14px}h1{font-size:18px}h2{font-size:15px;color:#9cf;margin:20px 0 4px}.muted{color:#888}
.explain{background:#1a140c;border:1px solid #433;border-left:3px solid #d90;padding:10px 12px;font-size:12.5px;color:#dcd;margin:10px 0}.explain b{color:#fc6}
table{border-collapse:collapse;font-size:12px;margin:4px 0}td,th{border:1px solid #2a2a30;padding:4px 10px;text-align:center;white-space:nowrap}
th{background:#1c1c22;color:#aaa}td:first-child,th:first-child{text-align:left;color:#9ab}
.c{cursor:pointer;font-variant-numeric:tabular-nums}.c:hover{outline:2px solid #7cf}.play{outline:2px solid #5d5 !important}.loading{outline:2px solid #fa5 !important}
.num{font-size:10.5px;color:#9a9;display:block}select{background:#16181c;color:#e0e0e0;border:1px solid #333}
</style></head><body>
<div id=bar>&#9654; <b id=np>click a cell to play</b> <span id=pos class=muted></span> <span id=ld style="color:#fa5"></span> <span class=muted>&middot; switching keeps the playhead &middot; loops until stopped</span></div>
<div id=wrap><h1>Bass head: weight and target</h1>
<div class=explain><b>What this tests.</b> The first bass page (bass_lr) rendered every retrained bass head at the preset's own setting, where each moved the low end by under 0.4&nbsp;dB, so everything sounded the same.
Here each head is tried across a grid: <b>target</b> = the bass level asked for (&minus;16, &minus;10, &minus;4&nbsp;dB; higher asks for more bass) and <b>weight</b> = guidance gain as a multiple of the preset's 8448 (1&times;, 2&times;, 4&times;, 8&times;).
The punch clip with its usual body head, one seed at a time (pick below). Heads: the production bass head, and the retrained B2 (lr 1e-2), B3 (lr 1e-3), B4 (lr 1e-4), each at its final epoch with a one-epoch EMA.
<b>How to read it:</b> compare a retrained head with the production head in the same cell; look for where each stops sounding like the original (more bass, rounder) and where it goes off (distortion, loss of punch). <b>bass</b> under a cell = change in the share of
energy below 150&nbsp;Hz against the original clip, level-matched (dB); <i>crest</i> = peak to RMS (lower = more compressed); <i>clk</i> = glitch screen (it has missed audible dropouts: listen first). More bass at a lower crest is volume, not improvement: judge the sound.</div>
Seed <select id=sd></select>
<div id=out></div></div><audio id=au_el></audio>
<script>const D=__DATA__;
const au=document.getElementById('au_el'),npx=document.getElementById('np');let cur=null;au.loop=true;
au.addEventListener('timeupdate',()=>{document.getElementById('pos').textContent=cur?('· '+au.currentTime.toFixed(1)+'s'):'';});
au.addEventListener('waiting',()=>{document.getElementById('ld').textContent='loading…';markLoading(true);});
au.addEventListener('playing',()=>{document.getElementById('ld').textContent='';markLoading(false);});
function mark(){document.querySelectorAll('.c.play').forEach(e=>e.classList.remove('play'));if(cur){const e=document.getElementById(cur);if(e)e.classList.add('play');}}
function markLoading(on){document.querySelectorAll('.c.loading').forEach(e=>e.classList.remove('loading'));if(on&&cur){const e=document.getElementById(cur);if(e)e.classList.add('loading');}}
function startClip(id,f,l,clip){
 if(window.noteSet)noteSet({model:'bass_grid',ckpt:'',clip:clip});
 const pos=(cur!==null&&!au.paused)?au.currentTime:0;cur=id;mark();npx.textContent='▶ '+l;
 document.getElementById('ld').textContent='loading…';markLoading(true);
 au.src=f;const go=()=>{try{au.currentTime=((au.duration&&pos>au.duration-1)?0:Math.min(pos,(au.duration||1e9)-0.05));}catch(e){}au.play();};
 if(au.readyState>=1)go();else au.addEventListener('loadedmetadata',go,{once:true});}
function play(id,f,l,clip){if(cur===id){au.pause();cur=null;mark();npx.textContent='stopped';document.getElementById('ld').textContent='';return;}startClip(id,f,l,clip);}
const sg=(v,d)=>(v>=0?'+':'')+v.toFixed(d);
const sel=document.getElementById('sd');D.seeds.forEach(s=>{sel.innerHTML+=`<option>${s}</option>`;});
function cell(key,label){const c=D.cells[key];if(!c)return '<td class=muted>·</td>';
 return `<td class=c id="${key}" onclick="play('${key}','${c.f}','${label}','${key}')">&#9654;<span class=num>bass ${sg(c.bass,2)}</span><span class=num>crest ${c.crest.toFixed(2)}</span><span class=num>clk ${c.clk.toFixed(2)}</span></td>`;}
function draw(){const s=sel.value;let h='<h2>References</h2><table><tr>'+cell('s'+s+'_base','original').replace('&#9654;','&#9654; original')+cell('s'+s+'_preset','preset (production bass+body)').replace('&#9654;','&#9654; preset')+'</tr></table>';
 D.heads.forEach(([k,lab])=>{h+=`<h2>${lab}</h2><table><tr><th>target \\ weight</th>`;D.mults.forEach(m=>h+=`<th>${m}&times; (${8448*m})</th>`);h+='</tr>';
  D.values.forEach(v=>{h+=`<tr><td>${v} dB</td>`;D.mults.forEach(m=>{h+=cell(`s${s}_${k}_v${v}_x${m}`,`${lab} target ${v} dB, ${m}x`);});h+='</tr>';});h+='</table>';});
 document.getElementById('out').innerHTML=h;mark();}
sel.onchange=draw;draw();
</script>
__NOTES__
<footer style="margin:18px 12px;color:#666;font-size:11px">evals &middot; bass head weight x target &middot; clips: latch_sweep bass_lr grid (internal)</footer>
</body></html>"""
T = T.replace("__NOTES__", notes_block("bass_grid", levels=[("clip", "this clip"), ("page", "page")], hint="click a cell, then note what you hear"))
open(os.path.join(STAGE, "bass_grid.html"), "w").write(inject(T.replace("__DATA__", DATA)))
print(f"wrote bass_grid.html: {len(jobs)} clips")
