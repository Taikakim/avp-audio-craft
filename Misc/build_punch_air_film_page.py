#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-15)
"""build_punch_air_film_page.py -- listening page for eval/punch_air_film_matrix.py.

The 2026-10-09 "cleanest" punch combo (bass + body LatCH heads on the k5 DoRA) plus the air-band LatCH head as a gain x
target matrix, three tables: the retrained A2 head, the A2 head with the FiLM density adapter on top (gain 1.0 @ 6/s), and
the old production air head. Per cell: air-band level change (dB above 2.5 kHz) and spectral-centroid change (Hz) against
the same seed's combo without the air head (with FiLM, against the combo + FiLM), seed mean, gate fails, and one button
per seed. Gate: control_head_disintegration_eval.gate() vs that reference, PQ leg |dPQ| > 1.5.
Writes ~/evals_aac/punch_air_film.html. No checkpoint filenames or drive paths on the page.
"""
import json
import os
import sqlite3
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "eval"))
from comment_notes_block import notes_block
from control_head_disintegration_eval import gate
from float_player import inject

SRC = "/run/media/kim/Mantu/sa3_control_runs/punch_air_film_matrix_20261015"
SUB = "punch_air_film_matrix"
STAGE = os.path.join(os.path.expanduser("~"), "evals_aac")
DB = os.path.join(HERE, "..", "eval", "clip_metrics.db")
PQ_DRIFT = 1.5

rows = [json.loads(l) for l in open(f"{SRC}/cells.jsonl") if l.strip()]
meta = json.load(open(f"{SRC}/run_meta.json"))
con = sqlite3.connect(DB)
cols = [r[1] for r in con.execute("PRAGMA table_info(metrics)")]
met = {os.path.basename(r[0])[:-4]: dict(zip(cols, r)) for r in con.execute("SELECT * FROM metrics WHERE path LIKE ?", (f"%/{SUB}/%",))}
ref = {(c["seed"], c["film"]): c for c in rows if c["head"] is None}
for c in rows:
    c["f"] = f"{SUB}/{c['id']}.m4a"
    c["fail"], c["why"], c["dpq"] = False, [], None
    r = ref.get((c["seed"], c["film"]))
    if c["head"] is None or r is None:
        continue
    c["d_air"] = c["air_db"] - r["air_db"]
    c["d_cent"] = c["centroid_hz"] - r["centroid_hz"]
    m, b = met.get(c["id"]), met.get(r["id"])
    if m and b:
        bad, why, _ = gate({**m, "ce": None}, {**b, "ce": None}, rhythmic=True)
        if m.get("pq") is not None and b.get("pq") is not None:
            c["dpq"] = m["pq"] - b["pq"]
            if abs(c["dpq"]) > PQ_DRIFT:
                why.append(f"pq-drift({b['pq']:.2f}->{m['pq']:.2f})")
                bad = True
        c["fail"], c["why"] = bad, why

gains = sorted({c["gain"] for c in rows if c["head"]})
targets = sorted({c["target"] for c in rows if c["head"]})
tables = []
for head, film, title in (("a2", False, "Retrained air head (A2)"), ("a2", True, "A2 air head + FiLM on top (gain 1.0, 6 onsets/s)"),
                          ("old", False, "Old production air head (reference)")):
    grid = []
    for t in targets:
        line = []
        for g in gains:
            cc = sorted([c for c in rows if c["head"] == head and c["film"] == film and c["gain"] == g and c["target"] == t],
                        key=lambda c: c["seed"])
            line.append({"d_air": float(np.mean([c["d_air"] for c in cc])) if cc else None,
                         "d_cent": float(np.mean([c["d_cent"] for c in cc])) if cc else None,
                         "n_fail": sum(c["fail"] for c in cc), "n": len(cc),
                         "clips": [{k: c.get(k) for k in ("id", "f", "seed", "d_air", "d_cent", "dpq", "fail", "why")} for c in cc]})
        grid.append({"target": t, "cells": line})
    tables.append({"title": title, "film": film, "grid": grid})
refs = [{"id": c["id"], "f": c["f"], "seed": c["seed"], "film": c["film"], "air_db": c["air_db"], "centroid_hz": c["centroid_hz"]}
        for c in sorted(ref.values(), key=lambda c: (c["film"], c["seed"]))]
print(f"{len(rows)} clips, {sum(c['fail'] for c in rows)} gate fails")

# Seed 764 + FiLM with the trajectory anchor (eval/punch_air_film_anchor.py, Last edited WINTERMUTE 2026-10-15): the
# listening verdict heard these cells distorted/saturated; the anchor caps the latent's level per step. Shown side by
# side with the same cells without it; the gate for anchored clips is against the anchored combo + FiLM reference.
ANC_SRC = SRC.replace("punch_air_film_matrix_20261015", "punch_air_film_anchor_20261015")
anchor = None
if os.path.exists(f"{ANC_SRC}/cells.jsonl"):
    arows = [json.loads(l) for l in open(f"{ANC_SRC}/cells.jsonl") if l.strip()]
    amet = {os.path.basename(r[0])[:-4]: dict(zip(cols, r)) for r in con.execute("SELECT * FROM metrics WHERE path LIKE ?", ("%/punch_air_film_anchor/%",))}
    aref = next((c for c in arows if c["head"] is None), None)
    orig = {c["id"]: c for c in rows}
    for c in arows:
        c["f"] = f"punch_air_film_anchor/{c['id']}.m4a"
        c["fail"], c["why"], c["dpq"] = False, [], None
        m, b = amet.get(c["id"]), amet.get(aref["id"]) if aref else None
        if c["head"] and m and b:
            bad, why, _ = gate({**m, "ce": None}, {**b, "ce": None}, rhythmic=True)
            if m.get("pq") is not None and b.get("pq") is not None:
                c["dpq"] = m["pq"] - b["pq"]
                if abs(c["dpq"]) > PQ_DRIFT:
                    why.append(f"pq-drift({b['pq']:.2f}->{m['pq']:.2f})")
                    bad = True
            c["fail"], c["why"] = bad, why
    pick = lambda c: {k: c.get(k) for k in ("id", "f", "air_db", "centroid_hz", "dpq", "fail", "why")}
    agrid = []
    for t in targets:
        line = []
        for g in gains:
            a = next((c for c in arows if c["head"] == "a2" and c["gain"] == g and c["target"] == t), None)
            o = orig.get(a["id"][:-len("_anc")]) if a else None
            line.append({"anc": pick(a) if a else None, "off": pick(o) if o else None})
        agrid.append({"target": t, "cells": line})
    anchor = {"grid": agrid, "ref_anc": pick(aref) if aref else None,
              "ref_off": pick(orig["s764__punch_film"]) if "s764__punch_film" in orig else None}
    print(f"anchor section: {len(arows)} clips, {sum(c['fail'] for c in arows)} gate fails")
DATA = json.dumps({"gains": gains, "tables": tables, "refs": refs, "pq": PQ_DRIFT, "anchor": anchor})

T = r"""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Punch + Air + FiLM</title><style>
body{font:13px system-ui;margin:0;background:#0e0e10;color:#e0e0e0}
#bar{position:sticky;top:0;background:#16181c;padding:7px 12px;border-bottom:1px solid #2a2a30;z-index:9}
#wrap{padding:14px;max-width:1400px}h1{font-size:18px}h2{font-size:15px;margin:24px 0 4px;color:#cde}.muted{color:#888}
.explain{background:#1a140c;border:1px solid #433;border-left:3px solid #d90;padding:10px 12px;font-size:12.5px;color:#dcd;margin:10px 0;line-height:1.45}.explain b{color:#fc6}
table{border-collapse:collapse;font-size:12px;margin:4px 0;display:block;overflow-x:auto}td,th{border:1px solid #2a2a30;padding:4px 6px;text-align:center;white-space:nowrap;vertical-align:top}
th{background:#1c1c22;color:#aaa}td:first-child{text-align:right;color:#9ab}
.m{display:block;font-weight:bold;font-variant-numeric:tabular-nums}.c{display:block;font-size:11px;color:#aab;font-variant-numeric:tabular-nums}
.b{display:inline-block;cursor:pointer;border:1px solid #333;border-radius:3px;padding:0 3px;margin:1px;font-size:10.5px;background:#18181c}
.b:hover{outline:1px solid #7cf}.play{outline:2px solid #5d5 !important}.bad{background:#2a1214;border-color:#733}.un{color:#e44;font-weight:bold;cursor:help}
</style></head><body>
<div id=bar>&#9654; <b id=np>click a clip to play</b> <span id=pos class=muted></span> <span class=muted>· switching keeps the playhead · re-click stops</span></div>
<div id=wrap><h1>The punch combo + the air head (gain × target), with and without FiLM</h1>
<div class=explain><b>Why this page exists.</b> The "cleanest" punch render steers the bass and body bands with two LatCH heads on a DoRA. The retrained
air-band head was heard at one target and two weights; here it is mapped as a full gain × target matrix on top of that combo, once with the FiLM density
adapter on top as well, and once with the old air head for comparison. <b>How to read it.</b> Rows: the air level the head is asked for (its training data
sits around −30 dB). Columns: guidance gain. Per cell: the change in air-band level (dB above 2.5 kHz) and in spectral centroid (Hz) against the same seed's
combo without the air head (for the FiLM table, against combo + FiLM), averaged over two seeds; positive = brighter. Red = failed the disintegration gate
against that reference (whitening, buzz, noise, beat loss, or PQ moving more than __PQ__). <b>What it cannot tell you.</b> Whether brighter is better, or
whether the glitches the old head made at high weights are gone: level and centroid are screens, the ear decides. __UN__</div>
<div id=out></div></div><audio id=au_el></audio>
<script>const D=__DATA__;
const au=document.getElementById('au_el'),npx=document.getElementById('np');let cur=null;
au.addEventListener('timeupdate',()=>{document.getElementById('pos').textContent=cur?('· '+au.currentTime.toFixed(1)+'s'):'';});
au.addEventListener('ended',()=>{cur=null;mark();});
function mark(){document.querySelectorAll('.b.play').forEach(e=>e.classList.remove('play'));if(cur){const e=document.getElementById(cur);if(e)e.classList.add('play');}}
function play(id,f){if(cur===id){au.pause();cur=null;mark();npx.textContent='stopped';return;}
 if(window.noteSet)noteSet({model:'punch_air_film',ckpt:'',clip:id});
 const pos=(cur!==null&&!au.paused)?au.currentTime:0;cur=id;mark();npx.textContent=id;au.src=f;
 const go=()=>{try{au.currentTime=Math.min(pos,(au.duration||1e9)-0.05);}catch(e){}au.play();};
 if(au.readyState>=1)go();else au.addEventListener('loadedmetadata',go,{once:true});}
const sg=(v,d)=>v==null?'–':(v>=0?'+':'')+v.toFixed(d);
const btn=(c,lbl)=>`<span class="b ${c.fail?'bad':''}" id="${c.id}" title="${(c.why||[]).join('; ')}" onclick="play('${c.id}','${c.f}')">${lbl}</span>`;
const col=v=>v==null?'#ccc':`hsl(${v>0?40:210},70%,${Math.min(75,50+Math.abs(v)*4)}%)`;
let h='<div class=muted>references: '+D.refs.map(r=>btn(r,`&#9654; ${r.film?'combo + FiLM':'combo'} s${r.seed} · air ${r.air_db.toFixed(1)} dB · ${Math.round(r.centroid_hz)} Hz`)).join(' ')+'</div>';
D.tables.forEach(T=>{
 h+=`<h2>${T.title}</h2><table><tr><th>target ↓ · gain →</th>`+D.gains.map(g=>`<th>${g/1000}k</th>`).join('')+'</tr>';
 T.grid.forEach(r=>{h+=`<tr><td>${r.target} dB</td>`;
  r.cells.forEach(x=>{h+=`<td><span class=m style="color:${col(x.d_air)}">${sg(x.d_air,1)} dB${x.n_fail?` <span style="color:#e66">${x.n_fail}/${x.n}✗</span>`:''}</span><span class=c>${sg(x.d_cent,0)} Hz</span>`+
   x.clips.map(c=>btn(c,`s${c.seed} ${sg(c.d_air,1)}`)).join(' ')+'</td>';});
  h+='</tr>';});
 h+='</table>';});
if(D.anchor){const A=D.anchor;
 h+='<h2>Seed 764 + FiLM: trajectory anchor off vs on (s0 1.2)</h2><div class=muted style="max-width:1000px">The listening verdict heard these cells distorted/saturated on seed 764. '+
  'The anchor caps the latent\'s level after every sampling step at its normal value for that noise level. Per cell: the same render without (off) and with (anc) the anchor; '+
  'numbers = air-band level (dB) · centroid (Hz). Red = the anchored clip failed the gate against the anchored combo + FiLM.</div>';
 const ab=(c,tag)=>c?btn(c,`${tag} ${c.air_db.toFixed(1)} dB · ${Math.round(c.centroid_hz)}`):'–';
 h+='<div class=muted>references: '+ab(A.ref_off,'&#9654; combo+FiLM off')+' '+ab(A.ref_anc,'&#9654; combo+FiLM anc')+'</div>';
 h+='<table><tr><th>target ↓ · gain →</th>'+D.gains.map(g=>`<th>${g/1000}k</th>`).join('')+'</tr>';
 A.grid.forEach(r=>{h+=`<tr><td>${r.target} dB</td>`+r.cells.map(x=>`<td>${ab(x.off,'off')}<br>${ab(x.anc,'anc')}</td>`).join('')+'</tr>';});
 h+='</table>';}
document.getElementById('out').innerHTML=h;
</script>
__NOTES__
<footer style="margin:18px 12px;color:#666;font-size:11px">evals &middot; punch combo + air head + FiLM &middot; clips: sa3_control_runs (internal) &middot; gate: control-head disintegration gate, quality leg = Audiobox PQ</footer>
</body></html>"""
UN = "" if meta.get("kim_feedback") else '<span class=un title="No listening verdict recorded yet (unaudited).">&#10071;</span> No listening verdict recorded yet.'
T = T.replace("__PQ__", str(PQ_DRIFT)).replace("__UN__", UN).replace(
    "__NOTES__", notes_block("punch_air_film", levels=[("clip", "this clip"), ("page", "page")], hint="click a clip, then note what you hear"))
out = os.path.join(STAGE, "punch_air_film.html")
open(out, "w").write(inject(T.replace("__DATA__", DATA)))
print(f"wrote {out}")
