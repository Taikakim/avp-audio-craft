#!/usr/bin/env python3
# Owner: GHOST-NOTE (created 2026-10-16)
"""build_bass_lr_page.py -- listening page for the bass-head learning-rate bracket (latch/run_bass_lr.sh): B3 lr 1e-3, B4 lr 1e-4, B2 lr 1e-2 (control), every saved epoch
(EMA 1 ep, EMA 0.25 ep, online = Schedule-Free average) swapped into the punch preset's bass slot. Data: eval/bass_epoch_sweep.py (sweep.json + level-matched wavs), train.log val loss.
Run: python3 Misc/build_bass_lr_page.py -> ~/evals_aac/bass_lr.html (+ bass_lr/*.m4a, AAC 256k). No checkpoint filenames or drive paths are written.
"""
import json, os, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comment_notes_block import notes_block
from float_player import inject
RUN = "/run/media/kim/Mantu/latch_sweep/bass_lr_2026-10-16"
STAGE = os.path.join(os.path.expanduser("~"), "evals_aac"); OUT = f"{STAGE}/bass_lr"; os.makedirs(OUT, exist_ok=True)
J = json.load(open(f"{RUN}/epoch_sweep/sweep.json")); rows = J["rows"]
INFO = {"B3": "lr 1e-3", "B4": "lr 1e-4", "B2": "lr 1e-2 (control)"}
VAL = {}
for a in INFO:
    d = [x for x in os.listdir(RUN) if x.startswith(a + "_")]
    if d and os.path.exists(f"{RUN}/{d[0]}/train.log"):
        t = re.sub(r"\x1b\[[0-9;]*m", "", open(f"{RUN}/{d[0]}/train.log").read()); VAL[a] = re.findall(r"val=([0-9.na]+)", t)
base = next(r for r in rows if r["name"] == "base"); B0 = base["air_share_db"]   # key name is historic: here it is the <150 Hz share in dB
cells, jobs = {}, []
for r in rows:
    f = f"bass_lr/{r['name']}.m4a"
    src = f"{RUN}/epoch_sweep/clips/{r['name']}" + ("" if r["name"] == "base" else "_matched") + ".wav"
    jobs.append((src, f"{STAGE}/{f}"))
    cells[r["name"]] = {"f": f, "arm": r["arm"], "ep": r["epoch"], "tag": r["tag"], "bass": r["air_share_db"] - B0, "clk": r["clicks_per_1e4"], "crest": r["crest"],
                        "on": r["onset_rate"], "hat": r["hat_rate"]}
def enc(j):
    if not os.path.exists(j[1]): subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", j[0], "-c:a", "aac", "-b:a", "256k", j[1]], check=True)
with ThreadPoolExecutor(8) as ex: list(ex.map(enc, jobs))
ROWS = []
for a in ("B4", "B3", "B2"):
    for t in sorted({c["tag"] for c in cells.values() if c["arm"] == a}, key=lambda t: (t != "", t)):
        ROWS.append({"a": a, "t": t, "label": f"{a} " + ("online (SF average)" if t == "_online" else f"EMA {t[4:]} ep" if t else "EMA 1 ep")})
DATA = json.dumps({"rows": ROWS, "cells": cells, "val": VAL, "info": INFO, "skipped": J["skipped"]})
T = r"""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Bass Head Learning Rates</title><style>
body{font:13px system-ui;margin:0;background:#0e0e10;color:#e0e0e0;max-width:1300px}
#bar{position:sticky;top:0;background:#16181c;padding:7px 12px;border-bottom:1px solid #2a2a30;z-index:9}
#wrap{padding:14px}h1{font-size:18px}h2{font-size:15px;color:#9cf;margin:20px 0 4px}.muted{color:#888}
.explain{background:#1a140c;border:1px solid #433;border-left:3px solid #d90;padding:10px 12px;font-size:12.5px;color:#dcd;margin:10px 0}.explain b{color:#fc6}
table{border-collapse:collapse;font-size:12px;margin:4px 0;display:block;overflow-x:auto}td,th{border:1px solid #2a2a30;padding:4px 8px;text-align:center;white-space:nowrap}
th{background:#1c1c22;color:#aaa}td:first-child,th:first-child{text-align:left;color:#9ab}
.c{cursor:pointer;font-variant-numeric:tabular-nums}.c:hover{outline:2px solid #7cf}.play{outline:2px solid #5d5 !important}.loading{outline:2px solid #fa5 !important}
.num{font-size:10.5px;color:#9a9;display:block}.best{background:#18301c}
</style></head><body>
<div id=bar>&#9654; <b id=np>click a cell to play</b> <span id=pos class=muted></span> <span id=ld style="color:#fa5"></span> <span class=muted>&middot; switching keeps the playhead &middot; loops until stopped</span></div>
<div id=wrap><h1>Bass head: learning rates</h1>
<div class=explain><b>What this tests.</b> LatCH heads have been trained at high learning rates and blown up more often than in the early runs. This page retrains the <b>bass</b> head, which is known to steer well,
with the modular trainer at lr 1e-3, 1e-4 and a 1e-2 control, 10 epochs each, and renders ONE clip (seed 764, the punch clip, 'cleanest' preset) with every saved epoch in the bass slot. The body head stays the production one.
Rows are runs and weight variants, columns are epochs. <b>How to read it:</b> the first row is the original (no heads) and the production bass+body clip; compare each cell to those. <b>bass</b> under a cell is the change in
the share of energy below 150&nbsp;Hz against the original (level-matched, dB); <i>clk</i> is a glitch screen (clicks per 10&nbsp;000 samples) that missed the audible dropouts before, so listen first; <i>crest</i> is peak-to-RMS (lower = more compressed);
<i>val</i> is held-out loss. EMA half-life 1 epoch for the main weights; online = the Schedule-Free average. Judge by ear and note anything off: validation loss has not predicted what sounds best.</div>
<h2>Validation loss by epoch</h2><div id=val></div>
<h2>Clips</h2><div id=out></div></div><audio id=au_el></audio>
<script>const D=__DATA__;
const au=document.getElementById('au_el'),npx=document.getElementById('np');let cur=null;au.loop=true;
au.addEventListener('timeupdate',()=>{document.getElementById('pos').textContent=cur?('· '+au.currentTime.toFixed(1)+'s'):'';});
au.addEventListener('waiting',()=>{document.getElementById('ld').textContent='loading…';markLoading(true);});
au.addEventListener('playing',()=>{document.getElementById('ld').textContent='';markLoading(false);});
function mark(){document.querySelectorAll('.c.play').forEach(e=>e.classList.remove('play'));if(cur){const e=document.getElementById(cur);if(e)e.classList.add('play');}}
function markLoading(on){document.querySelectorAll('.c.loading').forEach(e=>e.classList.remove('loading'));if(on&&cur){const e=document.getElementById(cur);if(e)e.classList.add('loading');}}
function startClip(id,f,l,clip){
 if(window.noteSet)noteSet({model:'bass_lr',ckpt:'',clip:clip});
 const pos=(cur!==null&&!au.paused)?au.currentTime:0;cur=id;mark();npx.textContent='▶ '+l;
 document.getElementById('ld').textContent='loading…';markLoading(true);
 au.src=f;const go=()=>{try{au.currentTime=((au.duration&&pos>au.duration-1)?0:Math.min(pos,(au.duration||1e9)-0.05));}catch(e){}au.play();};
 if(au.readyState>=1)go();else au.addEventListener('loadedmetadata',go,{once:true});}
function play(id,f,l,clip){if(cur===id){au.pause();cur=null;mark();npx.textContent='stopped';document.getElementById('ld').textContent='';return;}startClip(id,f,l,clip);}
const sg=(v,d)=>(v>=0?'+':'')+v.toFixed(d);const fv=x=>{const v=parseFloat(x);return isNaN(v)?'NaN':v.toFixed(4);};
let maxE=0;Object.values(D.cells).forEach(c=>{if(c.ep>maxE)maxE=c.ep;});
let v='<table><tr><th>run</th>';for(let e=1;e<=maxE;e++)v+=`<th>${e}</th>`;v+='</tr>';
['B4','B3','B2'].forEach(a=>{const V=D.val[a]||[];const nums=V.map(parseFloat).filter(x=>!isNaN(x));const mn=Math.min(...nums);
 v+=`<tr><td>${a} <span class=muted>${D.info[a]}</span></td>`;
 for(let e=1;e<=maxE;e++){const x=V[e-1];if(x===undefined){v+='<td></td>';continue;}const n=parseFloat(x);v+=`<td class="${n===mn?'best':''}">${isNaN(n)?'NaN':n.toFixed(4)}</td>`;}
 v+='</tr>';});
document.getElementById('val').innerHTML=v+'</table><div class=muted>Green = lowest validation loss of that run.</div>';
let h='<table><tr><th>reference</th><th colspan=2>clips</th></tr><tr><td>no heads / production bass+body</td>';
[['base','original'],['production_bass_body','production bass+body']].forEach(([r,l])=>{const c=D.cells[r];if(c)h+=`<td class=c id="${r}" onclick="play('${r}','${c.f}','${l}','${r}')">&#9654; ${l}<span class=num>crest ${c.crest.toFixed(2)}</span><span class=num>bass ${sg(c.bass,2)}</span></td>`;});
h+='</tr></table><table><tr><th>run</th>';for(let e=1;e<=maxE;e++)h+=`<th>ep ${e}</th>`;h+='</tr>';
D.rows.forEach(R=>{h+=`<tr><td>${R.label}<br><span class=muted>${D.info[R.a]}</span></td>`;
 for(let e=1;e<=maxE;e++){const n=R.a+'_ep'+String(e).padStart(2,'0')+R.t;const c=D.cells[n];if(!c){h+='<td class=muted>·</td>';continue;}
  const vv=(D.val[R.a]||[])[e-1];
  h+=`<td class=c id="${n}" onclick="play('${n}','${c.f}','${R.label} ep ${e}','${n}')">&#9654;<span class=num>bass ${sg(c.bass,2)}</span><span class=num>crest ${c.crest.toFixed(2)}</span><span class=num>clk ${c.clk.toFixed(2)}</span><span class=num>val ${fv(vv)}</span></td>`;}
 h+='</tr>';});
document.getElementById('out').innerHTML=h+'</table>';
</script>
__NOTES__
<footer style="margin:18px 12px;color:#666;font-size:11px">evals &middot; bass-band head, learning-rate bracket &middot; clips: latch_sweep bass_lr (internal)</footer>
</body></html>"""
T = T.replace("__NOTES__", notes_block("bass_lr", levels=[("clip", "this clip"), ("page", "page")], hint="click a cell, then note what you hear"))
open(os.path.join(STAGE, "bass_lr.html"), "w").write(inject(T.replace("__DATA__", DATA)))
print(f"wrote bass_lr.html: {len(jobs)} clips")
