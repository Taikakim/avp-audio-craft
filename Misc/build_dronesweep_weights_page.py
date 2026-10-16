#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-16)
"""build_dronesweep_weights_page.py -- listening page for eval/dronesweep_weights_test.py.

AVP drone sweep full finetunes (plain_s2 ep7, bf16_plain_s2 ep9, force_scalar_s1 ep7) re-rendered locally from their checkpoints:
EMA vs online weights, online blended with base medium-base at 25 / 33 %, and the unguided trajectory anchor (s0 1.2) on EMA and online.
4 prompts with the LUMI clips' own seeds, cfg 7, 24 steps, 20 s. The LUMI original (an EMA render) is shown first for reference.
Per clip: final latent std (healthy ~1.0-1.15), onsets/s, Audiobox PQ. Writes ~/evals_aac/dronesweep_weights.html.
"""
import glob
import json
import os
import sqlite3
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from comment_notes_block import notes_block
from float_player import inject

SRC = "/run/media/kim/Mantu/sa3_control_runs/dronesweep_weights_20261016"
PULL = "/home/kim/Projects/SAO/renders_pull/dronesweep"
STAGE = os.path.join(os.path.expanduser("~"), "evals_aac")
SUB = "dronesweep_weights"
EP = {"plain_s2": "ep7", "bf16_plain_s2": "ep9", "force_scalar_s1": "ep7"}
VARIANTS = ["ema", "online", "online_b25", "online_b33", "ema_anc", "online_anc"]
VLABEL = {"lumi": "LUMI original (EMA)", "ema": "EMA", "online": "online", "online_b25": "online + 25% base",
          "online_b33": "online + 33% base", "ema_anc": "EMA + anchor 1.2", "online_anc": "online + anchor 1.2"}
os.makedirs(f"{STAGE}/{SUB}", exist_ok=True)
meta = json.load(open(f"{SRC}/run_meta.json"))
con = sqlite3.connect("/home/kim/Projects/SAO/eval/clip_metrics.db")
pq = {os.path.basename(p)[:-4]: (ce, q) for p, ce, q in con.execute("SELECT path, ce, pq FROM metrics WHERE path LIKE ?", (f"%/{SUB}/%",))}


def enc(src, name):
    dst = f"{STAGE}/{SUB}/{name}.m4a"
    if not os.path.exists(dst):
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", src, "-c:a", "aac", "-b:a", "128k", dst], check=True)
    return f"{SUB}/{name}.m4a"


cells = {}
for l in open(f"{SRC}/cells.jsonl"):
    if l.strip():
        c = json.loads(l)
        c["f"] = f"{SUB}/{c['id']}.m4a"
        c["ce"], c["pq"] = pq.get(c["id"], (None, None))
        cells[(c["arm"], c["prompt"], c["variant"])] = c
rows = []
for arm in EP:
    for pid in sorted({k[1] for k in cells if k[0] == arm}):
        r = {"arm": arm, "prompt": pid, "cells": {}}
        lum = sorted(glob.glob(f"{PULL}/dronesweep_{arm}__{EP[arm]}__cfg7__w100__{pid}__s*.wav"))
        if lum:
            name = f"lumi__{arm}__{pid}"
            r["cells"]["lumi"] = {"id": name, "f": enc(lum[0], name)}
            z = lum[0][:-4] + ".z0.npy"
            if os.path.exists(z):
                import numpy as np
                r["cells"]["lumi"]["z_std"] = round(float(np.load(z).astype(np.float64).std()), 3)
        for v in VARIANTS:
            c = cells.get((arm, pid, v))
            if c:
                r["cells"][v] = {k: c.get(k) for k in ("id", "f", "z_std", "onsets", "pq", "ce")}
        rows.append(r)
DATA = json.dumps({"rows": rows, "cols": ["lumi"] + VARIANTS, "vlabel": VLABEL, "ep": EP})
T = r"""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Drone Sweep Weights</title><style>
body{font:13px system-ui;margin:0;background:#0e0e10;color:#e0e0e0}#bar{position:sticky;top:0;background:#16181c;padding:7px 12px;border-bottom:1px solid #2a2a30;z-index:9}
#wrap{padding:14px;max-width:1400px}h1{font-size:18px}h2{font-size:14px;color:#abc;margin-top:18px}.muted{color:#888}
.explain{background:#1a140c;border:1px solid #433;border-left:3px solid #d90;padding:10px 12px;font-size:12.5px;color:#dcd;margin:10px 0;line-height:1.45}.explain b{color:#fc6}
table{border-collapse:collapse;font-size:12px;margin:6px 0;display:block;overflow-x:auto}td,th{border:1px solid #2a2a30;padding:4px 6px;text-align:center;white-space:nowrap}th{background:#1c1c22;color:#aaa}td:first-child{text-align:left;color:#9ab}
.b{display:inline-block;cursor:pointer;border:1px solid #333;border-radius:3px;padding:1px 5px;background:#18181c;font-size:11px}.b:hover{outline:1px solid #7cf}.play{outline:2px solid #5d5 !important}.un{color:#e44;font-weight:bold}
</style></head><body><div id=bar>&#9654; <b id=np>click a clip to play</b> <span id=pos class=muted></span> <span class=muted>· switching keeps the playhead · re-click stops</span></div>
<div id=wrap><h1>AVP drone sweep: EMA vs online weights, base blends, anchor</h1>
<div class=explain><b>Why this page exists.</b> Every LUMI clip of the drone sweep is an EMA render, and the EMA (0.9999) is only ~40-45% trained weights
after these short runs, carrying the earlier epochs along. Here the same checkpoints are rendered locally with the EMA, with the ONLINE (current) weights, with the
online weights blended 25 / 33 % toward base medium-base, and with the trajectory anchor (1.2) on EMA and online. Same prompts and seeds as on LUMI, cfg 7, 24 steps, 20 s.
<b>How to read it.</b> Each button: z = final latent std (healthy ~1.0-1.15, red above 1.5) · onsets/s · Audiobox PQ. <b>What it cannot tell you.</b> Which weights sound
musical; that is the ear. __UN__</div><div id=out></div></div><audio id=au_el></audio>
<script>const D=__DATA__;const au=document.getElementById('au_el'),npx=document.getElementById('np');let cur=null;
au.addEventListener('timeupdate',()=>{document.getElementById('pos').textContent=cur?('· '+au.currentTime.toFixed(1)+'s'):'';});au.addEventListener('ended',()=>{cur=null;mark();});
function mark(){document.querySelectorAll('.b.play').forEach(e=>e.classList.remove('play'));if(cur){const e=document.getElementById(cur);if(e)e.classList.add('play');}}
function play(id,f){if(cur===id){au.pause();cur=null;mark();npx.textContent='stopped';return;}if(window.noteSet)noteSet({model:'dronesweep_weights',ckpt:'',clip:id});
 const pos=(cur!==null&&!au.paused)?au.currentTime:0;cur=id;mark();npx.textContent=id;au.src=f;const go=()=>{try{au.currentTime=Math.min(pos,(au.duration||1e9)-0.05);}catch(e){}au.play();};
 if(au.readyState>=1)go();else au.addEventListener('loadedmetadata',go,{once:true});}
const lab=c=>{const z=c.z_std!=null?`<span style="color:${c.z_std>1.5?'#e66':'#8a8'}">z ${c.z_std.toFixed(2)}</span>`:'';
 return [z,c.onsets!=null?c.onsets.toFixed(1)+'/s':'',c.pq!=null?'PQ '+c.pq.toFixed(2):''].filter(Boolean).join(' · ')||'&#9654;';};
const btn=c=>c?`<span class=b id="${c.id}" onclick="play('${c.id}','${c.f}')">&#9654; ${lab(c)}</span>`:'–';
let h='';[...new Set(D.rows.map(r=>r.arm))].forEach(a=>{h+=`<h2>${a} (${D.ep[a]})</h2><table><tr><th>prompt</th>`+D.cols.map(c=>`<th>${D.vlabel[c]}</th>`).join('')+'</tr>';
 D.rows.filter(r=>r.arm===a).forEach(r=>{h+=`<tr><td>${r.prompt}</td>`+D.cols.map(c=>`<td>${btn(r.cells[c])}</td>`).join('')+'</tr>';});h+='</table>';});
document.getElementById('out').innerHTML=h;</script>
__NOTES__
<footer style="margin:18px 12px;color:#666;font-size:11px">evals &middot; AVP drone sweep full finetunes, weights test &middot; clips: internal</footer></body></html>"""
UN = "" if meta.get("kim_feedback") else '<span class=un>&#10071;</span> No listening verdict recorded yet.'
T = T.replace("__UN__", UN).replace("__NOTES__", notes_block("dronesweep_weights", levels=[("clip", "this clip"), ("page", "page")], hint="click a clip, then note what you hear"))
open(f"{STAGE}/dronesweep_weights.html", "w").write(inject(T.replace("__DATA__", DATA)))
print(f"wrote {STAGE}/dronesweep_weights.html ({len(rows)} rows)")
