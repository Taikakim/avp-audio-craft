#!/usr/bin/env python3
# Owner: GHOST-NOTE (created 2026-10-15)
# Last edited: WINTERMUTE 2026-10-15 — floating transport bar (float_player.inject)
"""build_air_heads_page.py -- listening page: the retrained air-RMS heads vs the production AdamW head, 4 seeds x 2 guidance gains.

Kim 2026-10-15: "build a listening page for them". Clips and numbers from eval/air_head_compare.py (compare/compare.json, level-matched wavs). Three-audience
standard: same-playhead cells; an explainer; the training recipe and validation loss of every bracket arm (crashed arms included, they are results). Cells carry
the numbers that matter for Kim's two complaints (glitches: click rate; content change: onset / hi-hat / tempo versus bass+body alone). No checkpoint filenames or
drive paths are written. Run: python3 Misc/build_air_heads_page.py -> ~/evals_aac/air_heads.html (+ air_heads/*.m4a, AAC 256k)
"""
import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comment_notes_block import notes_block
from float_player import inject

AH = "/run/media/kim/Mantu2/latch_sweep/air_head_2026-10-14"
CMP = f"{AH}/compare"
STAGE = os.path.join(os.path.expanduser("~"), "evals_aac")
OUT = os.path.join(STAGE, "air_heads")
os.makedirs(OUT, exist_ok=True)
rows = json.load(open(f"{CMP}/compare.json"))
REAL = json.load(open(f"{CMP}/realised.json"))   # band RMS (dB) of each RAW render, mir multiband_rms extractor = the training-target definition
R = {(r["seed"], r["arm"]): r for r in rows}
seeds = sorted({r["seed"] for r in rows})
HEADS = [("old_adamw", "old head (AdamW, 20 ep)"), ("A2", "A2 modular, dim 512, lr 1e-2"), ("A5", "A5 modular, dim 256, lr 1e-2"),
         ("A4", "A4 modular, dim 512, lr 1e-3"), ("A6_soap", "A6 modular + SOAP, dim 512")]
GAINS = [8448, 24000]
SUMMARY = [l.rstrip("\n").split("\t") for l in open(f"{AH}/SUMMARY.tsv")]
arms = [{"name": s[0], "secs": s[1], "best": s[2], "rc": s[4]} for s in SUMMARY]
jobs, cells = [], {}
for s in seeds:
    for arm in ["base", "bass_body"] + [f"{h}_g{g}" for h, _ in HEADS for g in GAINS]:
        if (s, arm) not in R:
            continue
        src = f"{CMP}/s{s}_{arm}" + ("" if arm == "base" else "_matched") + ".wav"
        f = f"air_heads/s{s}_{arm}.m4a"
        jobs.append((src, f"{STAGE}/{f}"))
        r, b, bb = R[(s, arm)], R[(s, "base")], R[(s, "bass_body")]
        cells[f"{s}|{arm}"] = {"f": f, "air": r["air_share_db"] - b["air_share_db"], "clk": r["clicks_per_1e4"], "crest": r["crest"],
                               "real_air": REAL[f"s{s}_{arm}"]["air"], "real_bass": REAL[f"s{s}_{arm}"]["bass"], "real_body": REAL[f"s{s}_{arm}"]["body"], "on": r["onset_rate"] - bb["onset_rate"], "hat": r["hat_rate"] - bb["hat_rate"], "bpm": r["bpm"] - bb["bpm"]}


def enc(j):
    if not os.path.exists(j[1]):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", j[0], "-c:a", "aac", "-b:a", "256k", j[1]], check=True)


with ThreadPoolExecutor(8) as ex:
    list(ex.map(enc, jobs))
DATA = json.dumps({"seeds": seeds, "heads": HEADS, "gains": GAINS, "cells": cells, "arms": arms})
T = r"""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Air Head Retrain</title><style>
body{font:13px system-ui;margin:0;background:#0e0e10;color:#e0e0e0;max-width:1300px}
#bar{position:sticky;top:0;background:#16181c;padding:7px 12px;border-bottom:1px solid #2a2a30;z-index:9}
#wrap{padding:14px}h1{font-size:18px}h2{font-size:15px;color:#9cf;margin:20px 0 4px}.muted{color:#888}
.explain{background:#1a140c;border:1px solid #433;border-left:3px solid #d90;padding:10px 12px;font-size:12.5px;color:#dcd;margin:10px 0}.explain b{color:#fc6}
table{border-collapse:collapse;font-size:12px;margin:4px 0;display:block;overflow-x:auto}td,th{border:1px solid #2a2a30;padding:4px 8px;text-align:center;white-space:nowrap}
th{background:#1c1c22;color:#aaa}td:first-child,th:first-child{text-align:left;color:#9ab}
.c{cursor:pointer;font-variant-numeric:tabular-nums}.c:hover{outline:2px solid #7cf}.play{outline:2px solid #5d5 !important}.loading{outline:2px solid #fa5 !important}
.num{font-size:10.5px;color:#9a9;display:block}.bad{color:#e66}.un{color:#e44;font-weight:bold;cursor:help}
</style></head><body>
<div id=bar>&#9654; <b id=np>click a cell to play</b> <span id=pos class=muted></span> <span id=ld style="color:#fa5"></span> <span class=muted>· switching keeps the playhead · loops until stopped</span></div>
<div id=wrap><h1>Retrained air-band heads</h1>
<div class=explain><b>What this tests.</b> The air head steers the level of the 2.5&nbsp;kHz-and-up band. The original, trained with plain AdamW, glitched at large guidance weights and changed the
musical content (hi-hats, tempo), which the bass, mid and body heads do not. It was retrained with the modular optimiser (Shampoo whitening, Schedule-Free, Muon on every 2-D tensor,
overtraining-aware weight decay, damping switched on after epoch 1, EMA). Each cell is the same seed with bass and body heads fixed and an air head as the third guide at a target of &minus;10&nbsp;dB, at
two guidance gains. <b>How to read the numbers</b> (level-matched; under each cell): <i>air</i> = change in the high-band share versus the original, in dB (0 means the brightness balance is back);
<i>clk</i> = clicks per 10&nbsp;000 samples, a screen for glitches (higher is worse); <i>on/hat/bpm</i> = change in onset rate, hi-hat rate and tempo versus the bass+body clip, so it isolates what the
air head itself changed. <b>What the numbers cannot tell you:</b> whether it sounds better, or whether a glitch is audible. Listen first. <span class=un title="No listening verdict recorded yet (unaudited).">&#10071;</span> = no verdict recorded yet.</div>
<div class=explain><b>Requested versus realised.</b> The bass, body and air heads are asked for constant band levels of &minus;10.0, &minus;4.3 and &minus;10 dB (RMS, dB relative to full scale; the training set averages &minus;21.9, &minus;24.8 and &minus;33.0). <b>Realised</b> = the same band RMS, measured on the raw rendered clip with the project's feature extractor (the definition the heads were trained on). Absolute levels depend on how loud the render is, so read them as a comparison between cells, not as calibrated dB. The base, bass+body and head cells in a row show where each landed; none reaches its request, the guidance pulls toward it.</div>
<h2>Training bracket</h2><div id=arms></div>
<h2>Clips</h2><div id=out></div></div><audio id=au_el></audio>
<script>const D=__DATA__;
const au=document.getElementById('au_el'),npx=document.getElementById('np');let cur=null;au.loop=true;
au.addEventListener('timeupdate',()=>{document.getElementById('pos').textContent=cur?('· '+au.currentTime.toFixed(1)+'s'):'';});
au.addEventListener('waiting',()=>{document.getElementById('ld').textContent='loading…';markLoading(true);});
au.addEventListener('playing',()=>{document.getElementById('ld').textContent='';markLoading(false);});
function mark(){document.querySelectorAll('.c.play').forEach(e=>e.classList.remove('play'));if(cur){const e=document.getElementById(cur);if(e)e.classList.add('play');}}
function markLoading(on){document.querySelectorAll('.c.loading').forEach(e=>e.classList.remove('loading'));if(on&&cur){const e=document.getElementById(cur);if(e)e.classList.add('loading');}}
function startClip(id,f,l,clip){
 if(window.noteSet)noteSet({model:'air_heads',ckpt:'',clip:clip});
 const pos=(cur!==null&&!au.paused)?au.currentTime:0;cur=id;mark();npx.textContent='▶ '+l;
 document.getElementById('ld').textContent='loading…';markLoading(true);
 au.src=f;const go=()=>{try{au.currentTime=((au.duration&&pos>au.duration-1)?0:Math.min(pos,(au.duration||1e9)-0.05));}catch(e){}au.play();};
 if(au.readyState>=1)go();else au.addEventListener('loadedmetadata',go,{once:true});}
function play(id,f,l,clip){if(cur===id){au.pause();cur=null;mark();npx.textContent='stopped';document.getElementById('ld').textContent='';return;}startClip(id,f,l,clip);}
let a='<table><tr><th>arm</th><th>training time</th><th>best validation loss</th><th>result</th></tr>';
D.arms.forEach(r=>{a+=`<tr><td>${r.name}</td><td>${Math.round(r.secs/60)} min</td><td>${r.best}</td><td>${r.rc==='rc=0'?'finished':'<span class=bad>crashed (optimiser instability)</span>'}</td></tr>`;});
document.getElementById('arms').innerHTML=a+'</table><div class=muted>Validation = held-out regression loss on the air-band level (lower is better). The old head ended its AdamW run at a training loss of 0.030, on a different scale.</div>';
const sg=(v,d)=>(v>=0?'+':'')+v.toFixed(d);
let h='<table><tr><th>seed</th><th>original</th><th>bass+body</th>';
D.heads.forEach(([k,l])=>D.gains.forEach(g=>{h+=`<th>${l}<br>gain ${g}</th>`;}));h+='</tr>';
D.seeds.forEach(s=>{
 const cell=(arm,label,full,ref)=>{const c=D.cells[s+'|'+arm];if(!c)return'<td>·</td>';const id=arm+'_'+s;
  const nums=ref?`<span class=num>got: bass ${c.real_bass.toFixed(1)} · body ${c.real_body.toFixed(1)} · air ${c.real_air.toFixed(1)} dB</span>`:full?`<span class=num><b>air asked −10 → got ${c.real_air.toFixed(1)} dB</b><br>air ${sg(c.air,1)} dB vs orig · clk ${c.clk.toFixed(2)}<br>on ${sg(c.on,2)} hat ${sg(c.hat,2)} bpm ${sg(c.bpm,1)}</span>`:'';
  return `<td class=c id="${id}" onclick="play('${id}','${c.f}','${s} ${label}','${s}_${arm}')">&#9654; ${full?'':label}${nums}</td>`;};
 h+=`<tr><td>${s}</td>${cell('base','original',false,true)}${cell('bass_body','bass+body',false,true)}`;
 D.heads.forEach(([k,l])=>D.gains.forEach(g=>{h+=cell(k+'_g'+g,l+' g'+g,true);}));
 h+='</tr>';});
document.getElementById('out').innerHTML=h+'</table>';
</script>
__NOTES__
<footer style="margin:18px 12px;color:#666;font-size:11px">evals &middot; air-band head retrain &middot; clips and metrics: latch_sweep air_head (internal)</footer>
</body></html>"""
T = T.replace("__NOTES__", notes_block("air_heads", levels=[("clip", "this clip"), ("page", "page")], hint="click a cell, then note what you hear"))
open(os.path.join(STAGE, "air_heads.html"), "w").write(inject(T.replace("__DATA__", DATA)))
print(f"wrote air_heads.html: {len(seeds)} seeds, {len(jobs)} clips, {sum(os.path.getsize(f'{OUT}/{f}') for f in os.listdir(OUT))/1e6:.0f} MB")
