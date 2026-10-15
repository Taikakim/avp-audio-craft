#!/usr/bin/env python3
# Owner: GHOST-NOTE (created 2026-10-15)
"""build_air_epochs_page.py -- listening page: where did air-head quality PEAK across epochs? One punch clip (seed 764), every finite per-epoch checkpoint of the overnight
runs (O1-O5) + bracket A2. Data from eval/air_epoch_sweep.py (sweep.json, level-matched wavs) and each run's train.log (val loss per epoch).
Run: python3 Misc/build_air_epochs_page.py -> ~/evals_aac/air_epochs.html (+ air_epochs/*.m4a, AAC 256k). No checkpoint filenames or drive paths are written.
"""
import json, os, re, subprocess, sys, glob
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comment_notes_block import notes_block
from float_player import inject
ON = "/run/media/kim/Mantu2/latch_sweep/air_head_2026-10-15_overnight"
A2 = "/run/media/kim/Mantu2/latch_sweep/air_head_2026-10-14/A2_d512dp8_lr1e-2"
SW = f"{ON}/epoch_sweep"
STAGE = os.path.join(os.path.expanduser("~"), "evals_aac"); OUT = f"{STAGE}/air_epochs"; os.makedirs(OUT, exist_ok=True)
FU = "/run/media/kim/Mantu2/latch_sweep/air_head_2026-10-15_followup"
LL = "/run/media/kim/Mantu2/latch_sweep/air_head_2026-10-15_lowlr"
SL = "/run/media/kim/Mantu2/latch_sweep/air_head_2026-10-15_slow"
BG = "/run/media/kim/Mantu2/latch_sweep/air_head_2026-10-15_big"
NS = "/run/media/kim/Mantu2/latch_sweep/air_head_2026-10-15_nosf"
SRC = [(SW, "overnight")] + [(f"{x}/epoch_sweep", n) for x, n in ((FU, "followup"), (LL, "lowlr"), (SL, "slow"), (BG, "big"), (NS, "nosf")) if os.path.exists(f"{x}/epoch_sweep/sweep.json")]
J = {"rows": [], "skipped": []}
for d, _ in SRC:
    j = json.load(open(f"{d}/sweep.json"))
    for r in j["rows"]:
        if r["name"] in ("base", "bass_body") and J["rows"] and any(x["name"] == r["name"] for x in J["rows"]): continue
        r["_dir"] = d; J["rows"].append(r)
    J["skipped"] += j["skipped"]
rows = J["rows"]
def logs(d):
    t = re.sub(r"\x1b\[[0-9;]*m", "", open(f"{d}/train.log").read())
    tl = [float(x) for x in re.findall(r"^epoch \d+/\d+\s+loss=([0-9.na]+)", t, re.M) if x != "nan"] if False else re.findall(r"^epoch \d+/\d+\s+loss=(\S+)", t, re.M)
    vl = re.findall(r"val=(\S+)", t)
    return tl, vl
INFO = {"O1": ("O1", "d256, lr 5e-2, batch 32"), "O2": ("O2", "d256, lr 1e-1, batch 32"), "O3": ("O3", "d256, lr 3e-2, batch 64"), "O4": ("O4", "d256, lr 3e-2, batch 64, early damping"),
        "O5": ("O5", "d512, lr 1e-2, batch 32, 25 ep"), "O6": ("O6", "d256, lr 5e-2, batch 32, damping from ep 1, cosine from ep 3"), "A2b": ("A2b", "A2 recipe re-run, d512, lr 1e-2, 1000 steps"), "A2c": ("A2c", "A2 recipe re-run at batch 8 x 4, d512, lr 1e-2, 1000 steps"), "QA2": ("QA2", "A2 recipe WITHOUT Schedule-Free, lr 1e-2"), "QP64": ("QP64", "big-batch cosine recipe WITHOUT Schedule-Free, batch 64, lr 1e-2"), "QP128": ("QP128", "big-batch cosine recipe WITHOUT Schedule-Free, batch 128, lr 1e-2"), "QP64h": ("QP64h", "faithful lr 1e-1 twin of P64, WITHOUT Schedule-Free"), "P64m": ("P64m", "P64 recipe at lr 3e-2 (insurance), batch 64, EMA 4 ep, cosine to ep 8"), "P64": ("P64", "O2 recipe (lr 1e-1) at d512, batch 64, EMA 4 ep, cosine to ep 8"), "P128": ("P128", "O2 recipe (lr 1e-1) at d512, batch 128, EMA 4 ep, cosine to ep 8"), "S1": ("S1", "O1 recipe at lr 5e-3, 15 ep"), "S2": ("S2", "O2 recipe at lr 1e-2, 15 ep"), "S3": ("S3", "O3 recipe at lr 3e-3, batch 64, 15 ep"), "S4": ("S4", "O4 recipe at lr 3e-3, batch 64, 15 ep"), "S5": ("S5", "O5 recipe at lr 1e-3, d512, 15 ep"), "L2": ("L2", "A2 recipe at lr 2e-3, d512, 1000 steps"), "L5": ("L5", "A2 recipe at lr 5e-3, d512, 1000 steps"), "A2": ("A2", "d512, lr 1e-2, 1000-step bracket")}
VAL = {}
for d in glob.glob(f"{ON}/O*") + [A2] + glob.glob(f"{FU}/O6*") + glob.glob(f"{FU}/A2b*") + glob.glob(f"{LL}/L*") + glob.glob(f"{SL}/S*") + glob.glob(f"{BG}/P*") + glob.glob(f"{NS}/Q*"):
    k = os.path.basename(d).split("_")[0]; tl, vl = logs(d); VAL[k] = {"train": tl, "val": vl}
BASE_AIR = next(r["air_share_db"] for r in rows if r["name"] == "base")   # cells show the change in high-band share vs the ORIGINAL (the page text says so)
jobs, cells = [], {}
for r in rows:
    f = f"air_epochs/{r['name']}.m4a"
    src = f"{r['_dir']}/clips/{r['name']}" + ("" if r["name"] == "base" else "_matched") + ".wav"
    jobs.append((src, f"{STAGE}/{f}"))
    cells[r["name"]] = {"f": f, "arm": r["arm"], "ep": r["epoch"], "tag": r["tag"], "air": r["air_share_db"] - BASE_AIR, "clk": r["clicks_per_1e4"], "crest": r["crest"],
                        "cent": r.get("centroid", r.get("spectral_centroid", 0)), "on": r["onset_rate"], "hat": r["hat_rate"], "bpm": r["bpm"]}
def enc(j):
    if not os.path.exists(j[1]): subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", j[0], "-c:a", "aac", "-b:a", "256k", j[1]], check=True)
with ThreadPoolExecutor(8) as ex: list(ex.map(enc, jobs))
MET = {}
for d, _ in SRC:
    if os.path.exists(f"{d}/metrics.json"): MET.update({k: v for k, v in json.load(open(f"{d}/metrics.json")).items() if k not in MET})
for k, c in cells.items():
    AB = {"ab_production_quality": "ab_PQ", "ab_content_enjoyment": "ab_CE", "ab_content_usefulness": "ab_CU", "ab_production_complexity": "ab_PC"}
    c["m"] = {AB.get(x, x): y for x, y in (MET.get(k) or {}).items() if AB.get(x, x) in ("rms", "crest", "zcr", "centroid", "flatness", "flux") or x in AB}
def lab(arm, tag):
    main = "0.5" if arm == "QA2" else "4" if arm[0] in "PQ" else "2" if arm[0] in "OS" else "0.5"
    if tag == "_online": return f"{arm} online (SF average)"
    if tag.startswith("_ema"): return f"{arm} EMA {tag[4:]} ep"
    return f"{arm} EMA {main} ep"
ROWS = []
for arm in ["P64", "P64m", "P128", "QA2", "QP64", "QP128", "QP64h", "O5", "O6", "A2", "A2b", "A2c", "L2", "L5", "S5", "S1", "S2", "S3", "S4", "O4", "O3", "O1", "O2"]:
    tags = sorted({c["tag"] for c in cells.values() if c["arm"] == arm}, key=lambda t: (t != "", t))
    ROWS += [{"a": arm, "t": t, "label": lab(arm, t)} for t in tags]
DATA = json.dumps({"rows": ROWS, "cells": cells, "val": VAL, "info": INFO, "skipped": J["skipped"]})
T = r"""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Air Head Epochs</title><style>
body{font:13px system-ui;margin:0;background:#0e0e10;color:#e0e0e0;max-width:1300px}
#bar{position:sticky;top:0;background:#16181c;padding:7px 12px;border-bottom:1px solid #2a2a30;z-index:9}
#wrap{padding:14px}h1{font-size:18px}h2{font-size:15px;color:#9cf;margin:20px 0 4px}.muted{color:#888}
.explain{background:#1a140c;border:1px solid #433;border-left:3px solid #d90;padding:10px 12px;font-size:12.5px;color:#dcd;margin:10px 0}.explain b{color:#fc6}
table{border-collapse:collapse;font-size:12px;margin:4px 0;display:block;overflow-x:auto}td,th{border:1px solid #2a2a30;padding:4px 8px;text-align:center;white-space:nowrap}
th{background:#1c1c22;color:#aaa}td:first-child,th:first-child{text-align:left;color:#9ab}
.c{cursor:pointer;font-variant-numeric:tabular-nums}.c:hover{outline:2px solid #7cf}.play{outline:2px solid #5d5 !important}.loading{outline:2px solid #fa5 !important}
.num{font-size:10.5px;color:#9a9;display:block}.bad{color:#e66}.best{background:#18301c}
</style></head><body>
<div id=bar>&#9654; <b id=np>click a cell to play</b> <span id=pos class=muted></span> <span id=ld style="color:#fa5"></span> <span class=muted>· switching keeps the playhead · loops until stopped</span></div>
<div id=wrap><h1>Air head: quality by epoch</h1>
<div class=explain><b>What this tests.</b> The overnight air-head runs saved a checkpoint every epoch. This page renders ONE clip (seed 764, the punch clip) with each of them as the third guide beside the bass and body heads
(air target &minus;10&nbsp;dB, gain 24000), so you can hear where quality peaked and whether the learning rates were too high for Schedule-Free. Rows are runs, columns are epochs. Checkpoints whose weights had already gone to
NaN are not rendered (155 of them); a few finite ones still rendered silent or broken and are marked. Saved weights are the EMA average (half-life 2 epochs; the 1000-step reference A2 used 0.5). <b>Numbers under each cell</b> (level-matched to the original): <i>air</i> = high-band share versus the
original in dB (0 = balance restored); <i>clk</i> = clicks per 10&nbsp;000 samples, a glitch screen that reads low on bright clips; <i>val</i> = held-out loss of that checkpoint. Validation loss and listening can disagree: listen first. One clip, one seed: a peak here is a hypothesis, not a result.</div>
<h2>Validation loss by epoch</h2><div id=val></div>
<h2>Metrics by epoch</h2><div class=muted>Level-matched clips. <select id=msel></select> <span id=mdesc></span></div><div id=met></div>
<h2>Clips</h2><div id=out></div></div><audio id=au_el></audio>
<script>const D=__DATA__;
const au=document.getElementById('au_el'),npx=document.getElementById('np');let cur=null;au.loop=true;
au.addEventListener('timeupdate',()=>{document.getElementById('pos').textContent=cur?('· '+au.currentTime.toFixed(1)+'s'):'';});
au.addEventListener('waiting',()=>{document.getElementById('ld').textContent='loading…';markLoading(true);});
au.addEventListener('playing',()=>{document.getElementById('ld').textContent='';markLoading(false);});
function mark(){document.querySelectorAll('.c.play').forEach(e=>e.classList.remove('play'));if(cur){const e=document.getElementById(cur);if(e)e.classList.add('play');}}
function markLoading(on){document.querySelectorAll('.c.loading').forEach(e=>e.classList.remove('loading'));if(on&&cur){const e=document.getElementById(cur);if(e)e.classList.add('loading');}}
function startClip(id,f,l,clip){
 if(window.noteSet)noteSet({model:'air_epochs',ckpt:'',clip:clip});
 const pos=(cur!==null&&!au.paused)?au.currentTime:0;cur=id;mark();npx.textContent='▶ '+l;
 document.getElementById('ld').textContent='loading…';markLoading(true);
 au.src=f;const go=()=>{try{au.currentTime=((au.duration&&pos>au.duration-1)?0:Math.min(pos,(au.duration||1e9)-0.05));}catch(e){}au.play();};
 if(au.readyState>=1)go();else au.addEventListener('loadedmetadata',go,{once:true});}
function play(id,f,l,clip){if(cur===id){au.pause();cur=null;mark();npx.textContent='stopped';document.getElementById('ld').textContent='';return;}startClip(id,f,l,clip);}
const sg=(v,d)=>(v>=0?'+':'')+v.toFixed(d);
const arms=['P64','P64m','P128','QA2','QP64','QP128','QP64h','O5','O6','A2','A2b','A2c','L2','L5','S5','S1','S2','S3','S4','O4','O3','O1','O2'].filter(a=>D.info[a]);const rows=D.rows;
let maxE=0;Object.values(D.cells).forEach(c=>{if(c.ep>maxE)maxE=c.ep;});
const fv=x=>{const v=parseFloat(x);return isNaN(v)?'NaN':v.toFixed(4);};
let v='<table><tr><th>run</th>';for(let e=1;e<=maxE;e++)v+=`<th>${e}</th>`;v+='</tr>';
arms.forEach(a=>{const V=(D.val[a]||{}).val||[];const nums=V.map(parseFloat).filter(x=>!isNaN(x));const mn=Math.min(...nums);
 v+=`<tr><td>${a}<br><span class=muted>${D.info[a][1]}</span></td>`;
 for(let e=1;e<=maxE;e++){const x=V[e-1];if(x===undefined){v+='<td></td>';continue;}const n=parseFloat(x);v+=`<td class="${n===mn?'best':''}">${isNaN(n)?'<span class=bad>NaN</span>':n.toFixed(4)}</td>`;}
 v+='</tr>';});
document.getElementById('val').innerHTML=v+'</table><div class=muted>Green = lowest validation loss of that run.</div>';
let h='<table><tr><th>run</th>';for(let e=1;e<=maxE;e++)h+=`<th>ep ${e}</th>`;h+='</tr>';
const ref=['base','bass_body'];
h+='<tr><td>references</td>';ref.forEach(r=>{const c=D.cells[r];if(c)h+=`<td class=c id="${r}" onclick="play('${r}','${c.f}','${r}','${r}')">&#9654; ${r==='base'?'original':'bass+body'}<span class=num>clk ${c.clk.toFixed(2)}</span></td>`;});h+='</tr></table>';
h+='<table><tr><th>run</th>';for(let e=1;e<=maxE;e++)h+=`<th>ep ${e}</th>`;h+='</tr>';
rows.forEach(R=>{const a=R.a;h+=`<tr><td>${R.label}<br><span class=muted>${D.info[a][1]}</span></td>`;
 for(let e=1;e<=maxE;e++){const n=a+'_ep'+String(e).padStart(2,'0')+R.t;const c=D.cells[n];
  if(!c){h+='<td class=muted>·</td>';continue;}
  const vv=((D.val[a]||{}).val||[])[e-1];
  if(c.air<-100){h+=`<td class=c id="${n}" onclick="play('${n}','${c.f}','${R.label} ep ${e}','${n}')">&#9654;<span class="num bad">broken render (silent / non-finite)</span><span class=num>val ${fv(((D.val[a]||{}).val||[])[e-1])}</span></td>`;continue;}
  h+=`<td class=c id="${n}" onclick="play('${n}','${c.f}','${R.label} ep ${e}','${n}')">&#9654;<span class=num>air ${sg(c.air,2)}</span><span class=num>clk ${c.clk.toFixed(2)}</span><span class=num>val ${fv(vv)}</span></td>`;}
 h+='</tr>';});
document.getElementById('out').innerHTML=h+'</table>';
const MN={ab_PQ:['PQ (Audiobox production quality, higher = better)',2],ab_CE:['CE (content enjoyment)',2],ab_CU:['CU (content usefulness)',2],ab_PC:['PC (production complexity)',2],zcr:['zero-crossing rate',3],centroid:['spectral centroid, Hz',0],flux:['spectral flux',3],crest:['crest factor',2],rms:['RMS (linear, level-matched)',4],flatness:['whitening = spectral flatness (1 = white noise)',4]};
const ms=document.getElementById('msel');Object.keys(MN).forEach(k=>{ms.innerHTML+=`<option value="${k}">${MN[k][0]}</option>`;});
function drawMet(){const k=ms.value,dg=MN[k][1];let t='<table><tr><th>run</th>';for(let e=1;e<=maxE;e++)t+=`<th>${e}</th>`;t+='</tr>';
 const rf=['base','bass_body'].map(r=>D.cells[r]).filter(Boolean);
 t+='<tr><td>original / bass+body</td><td colspan=4>'+['base','bass_body'].map(r=>{const c=D.cells[r];return c&&c.m&&c.m[k]!==undefined?r+' '+c.m[k].toFixed(dg):r+' ·';}).join(' &nbsp;|&nbsp; ')+'</td></tr>';
 rows.forEach(R=>{const a=R.a;const vals=[];for(let e=1;e<=maxE;e++){const c=D.cells[a+'_ep'+String(e).padStart(2,'0')+R.t];vals.push(c&&c.air>-100&&c.m&&c.m[k]!==undefined?c.m[k]:null);}
  const ok=vals.filter(x=>x!==null);const mx=Math.max(...ok),mn=Math.min(...ok);
  t+=`<tr><td>${R.label}</td>`;vals.forEach(x=>{t+=x===null?'<td class=muted>·</td>':`<td class="${(k==='ab_PQ'&&x===mx)?'best':''}">${x.toFixed(dg)}</td>`;});t+='</tr>';});
 document.getElementById('met').innerHTML=t+'</table><div class=muted>Green = highest PQ of that run. Broken (silent / non-finite) renders are left blank.</div>';}
ms.onchange=drawMet;ms.value='ab_PQ';drawMet();

</script>
__NOTES__
<footer style="margin:18px 12px;color:#666;font-size:11px">evals &middot; air-band head, per-epoch checkpoints &middot; clips and metrics: latch_sweep air_head (internal)</footer>
</body></html>"""
T = T.replace("__NOTES__", notes_block("air_epochs", levels=[("clip", "this clip"), ("page", "page")], hint="click a cell, then note what you hear"))
open(os.path.join(STAGE, "air_epochs.html"), "w").write(inject(T.replace("__DATA__", DATA)))
print(f"wrote air_epochs.html: {len(jobs)} clips")
