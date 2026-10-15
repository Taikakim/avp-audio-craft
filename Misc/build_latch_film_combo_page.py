#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-15)
"""build_latch_film_combo_page.py -- listening page for EXPERIMENTS E7 (onset LatCH x FiLM) and E8 (time-gated FiLM).

E7 (eval/latch_film_combo_e7.py): per context (base psytrance, the punch example's prompt + DoRA, deep house) a table of
FiLM gain (rows) x LatCH gain (columns). Per cell: SPREAD = measured onsets/s for the 9/s request minus the 3/s request
(seed mean), DRIFT = 1 - CLAP cosine to the same-seed unguided render (character change), gate fails, and one button per
seed x request. E8 (eval/latch_film_e8.py), shown when its cells exist: FiLM gated to the high-noise steps, rows = FiLM
gain x gate, compared with E7's ungated FiLM at the same gain. Gate: control_head_disintegration_eval.gate() vs the
same-seed unguided render, PQ leg |dPQ| > 1.5 (as on the other LatCH pages).
Writes ~/evals_aac/latch_film_combo.html. No checkpoint filenames or drive paths on the page.
"""
import json
import os
import sqlite3
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "eval"))
from comment_notes_block import notes_block
from control_head_disintegration_eval import gate
from float_player import inject

E7 = "/run/media/kim/Mantu/sa3_control_runs/latch_film_combo_e7_20261015"
E8 = "/run/media/kim/Mantu/sa3_control_runs/latch_film_e8_20261015"
STAGE = os.path.join(os.path.expanduser("~"), "evals_aac")
DB = os.path.join(HERE, "..", "eval", "clip_metrics.db")
PQ_DRIFT = 1.5
CTX_LABEL = {"base": "psytrance, 140 bpm (base model)", "punch": "the punch example's prompt + its DoRA (48 s)",
             "house": "deep house, 122 bpm (far from the training style)"}

con = sqlite3.connect(DB)
cols = [r[1] for r in con.execute("PRAGMA table_info(metrics)")]


def metrics(sub):
    return {os.path.basename(r[0])[:-4]: dict(zip(cols, r))
            for r in con.execute("SELECT * FROM metrics WHERE path LIKE ?", (f"%/{sub}/%",))}


def load(src):
    if not os.path.exists(f"{src}/cells.jsonl"):
        return [], {}
    rows = [json.loads(l) for l in open(f"{src}/cells.jsonl") if l.strip()]
    clap = json.load(open(f"{src}/clap.json")) if os.path.exists(f"{src}/clap.json") else {"drift": {}}
    return rows, clap


e7_rows, e7_clap = load(E7)
e8_rows, e8_clap = load(E8)
m7, m8 = metrics("latch_film_combo_e7"), metrics("latch_film_e8")
base_id = {(c["ctx"], c["seed"]): c["id"] for c in e7_rows if c["dens"] is None}


def annotate(rows, met, clap, sub):
    for c in rows:
        c["f"] = f"{sub}/{c['ctx']}/{c['id']}.m4a"
        c["drift"] = clap.get("drift", {}).get(c["id"])
        c["fail"], c["why"], c["dpq"] = False, [], None
        m, b = met.get(c["id"]), m7.get(base_id.get((c["ctx"], c["seed"]), ""))
        if c.get("dens") is None or not m or not b:
            continue
        bad, why, _ = gate({**m, "ce": None}, {**b, "ce": None}, rhythmic=True)
        if m.get("pq") is not None and b.get("pq") is not None:
            c["dpq"] = m["pq"] - b["pq"]
            if abs(c["dpq"]) > PQ_DRIFT:
                why.append(f"pq-drift({b['pq']:.2f}->{m['pq']:.2f})")
                bad = True
        c["fail"], c["why"] = bad, why


annotate(e7_rows, m7, e7_clap, "latch_film_combo_e7")
annotate(e8_rows, m8, e8_clap, "latch_film_e8")


def summarize(cs):
    hi = [c["onsets"] for c in cs if c["dens"] == 9]
    lo = [c["onsets"] for c in cs if c["dens"] == 3]
    dr = [c["drift"] for c in cs if c["drift"] is not None]
    return {"spread": float(np.mean(hi) - np.mean(lo)) if hi and lo else None,
            "drift": float(np.mean(dr)) if dr else None, "n_fail": sum(c["fail"] for c in cs), "n": len(cs),
            "clips": [{k: c.get(k) for k in ("id", "f", "seed", "dens", "onsets", "drift", "dpq", "fail", "why")}
                      for c in sorted(cs, key=lambda c: (c["seed"], c["dens"]))]}


ctxs = [k for k in CTX_LABEL if any(c["ctx"] == k for c in e7_rows)]
e7 = {}
for ctx in ctxs:
    g = defaultdict(list)
    for c in e7_rows:
        if c["ctx"] == ctx and c["dens"] is not None:
            g[(c["film"], c["latch"])].append(c)
    films = sorted({k[0] for k in g} | {0.0})
    latches = sorted({k[1] for k in g} | {0})
    e7[ctx] = {"films": films, "latches": latches,
               "cells": {f"{f:g}|{l}": summarize(g[(f, l)]) for f in films for l in latches if (f, l) in g},
               "base": [{"id": base_id[(ctx, s)], "f": f"latch_film_combo_e7/{ctx}/{base_id[(ctx, s)]}.m4a", "seed": s,
                         "onsets": next(c["onsets"] for c in e7_rows if c["id"] == base_id[(ctx, s)])}
                        for (cx, s) in sorted(base_id) if cx == ctx],
               "seed_ref": e7_clap.get("seed_reference", {}).get(ctx)}
e8 = {}
for ctx in sorted({c["ctx"] for c in e8_rows}):
    g = defaultdict(list)
    for c in e8_rows:
        if c["ctx"] == ctx:
            g[(c["film"], c["gate"], c["latch"])].append(c)
    e8[ctx] = [{"film": k[0], "gate": k[1], "latch": k[2], **summarize(v),
                "ungated": e7.get(ctx, {}).get("cells", {}).get(f"{k[0]:g}|0", {}).get("spread"),
                "ungated_drift": e7.get(ctx, {}).get("cells", {}).get(f"{k[0]:g}|0", {}).get("drift")}
               for k, v in sorted(g.items())]

meta7 = json.load(open(f"{E7}/run_meta.json"))
DATA = json.dumps({"ctx_label": CTX_LABEL, "e7": e7, "e8": e8, "pq": PQ_DRIFT,
                   "audited": bool(meta7.get("kim_feedback"))})
print(f"E7: {len(e7_rows)} clips, {sum(c['fail'] for c in e7_rows)} gate fails; E8: {len(e8_rows)} clips")

T = r"""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>LatCH + FiLM Density</title><style>
body{font:13px system-ui;margin:0;background:#0e0e10;color:#e0e0e0}
#bar{position:sticky;top:0;background:#16181c;padding:7px 12px;border-bottom:1px solid #2a2a30;z-index:9}
#wrap{padding:14px;max-width:1400px}h1{font-size:18px}h2{font-size:15px;margin:24px 0 4px;color:#cde}h3{font-size:13px;margin:14px 0 4px;color:#abc}.muted{color:#888}
.explain{background:#1a140c;border:1px solid #433;border-left:3px solid #d90;padding:10px 12px;font-size:12.5px;color:#dcd;margin:10px 0;line-height:1.45}.explain b{color:#fc6}
table{border-collapse:collapse;font-size:12px;margin:4px 0;display:block;overflow-x:auto}td,th{border:1px solid #2a2a30;padding:4px 6px;text-align:center;white-space:nowrap;vertical-align:top}
th{background:#1c1c22;color:#aaa}td:first-child{text-align:left;color:#9ab}
.sp{font-weight:bold;display:block;font-variant-numeric:tabular-nums}.dr{display:block;font-size:11px;font-variant-numeric:tabular-nums}
.b{display:inline-block;cursor:pointer;border:1px solid #333;border-radius:3px;padding:0 3px;margin:1px;font-size:10.5px;font-variant-numeric:tabular-nums;background:#18181c}
.b:hover{outline:1px solid #7cf}.play{outline:2px solid #5d5 !important}.bad{background:#2a1214;border-color:#733}.un{color:#e44;font-weight:bold;cursor:help}
</style></head><body>
<div id=bar>&#9654; <b id=np>click a clip to play</b> <span id=pos class=muted></span> <span class=muted>· switching keeps the playhead · re-click stops</span></div>
<div id=wrap><h1>Density control: onset LatCH and the FiLM adapter, alone and together</h1>
<div class=explain><b>Why this page exists.</b> The onset LatCH head changes density transparently but only a little; the FiLM density adapter has the
range but pulls the music toward the training set's style. E7 asks whether using both gives more range for less style change than FiLM alone; E8 (below,
when rendered) asks whether running FiLM only on the early, noisy sampling steps keeps its density effect while dropping the style pull.
<b>How to read it.</b> Each cell asks for 3, 6 and 9 onsets per second. <b>Spread</b> = what came out for 9/s minus what came out for 3/s (bigger = more
control). <b>Drift</b> = how far the sound moved from the same seed rendered with no control (CLAP embedding distance; the two unguided seeds differ by the
"seed reference" amount, so drift below that is within ordinary seed variation). Green drift = below the seed reference. Buttons: seed · request → measured.
Red = failed the disintegration gate against the unguided render (whitening, buzz, noise, beat loss, or PQ moving more than __PQ__).
<b>What it cannot tell you.</b> Whether it sounds good: onset counts and CLAP are screens, the ear decides. __UN__</div>
<div id=out></div></div><audio id=au_el></audio>
<script>const D=__DATA__;
const au=document.getElementById('au_el'),npx=document.getElementById('np');let cur=null;
au.addEventListener('timeupdate',()=>{document.getElementById('pos').textContent=cur?('· '+au.currentTime.toFixed(1)+'s'):'';});
au.addEventListener('ended',()=>{cur=null;mark();});
function mark(){document.querySelectorAll('.b.play').forEach(e=>e.classList.remove('play'));if(cur){const e=document.getElementById(cur);if(e)e.classList.add('play');}}
function play(id,f){if(cur===id){au.pause();cur=null;mark();npx.textContent='stopped';return;}
 if(window.noteSet)noteSet({model:'latch_film_combo',ckpt:'',clip:id});
 const pos=(cur!==null&&!au.paused)?au.currentTime:0;cur=id;mark();npx.textContent=id;au.src=f;
 const go=()=>{try{au.currentTime=Math.min(pos,(au.duration||1e9)-0.05);}catch(e){}au.play();};
 if(au.readyState>=1)go();else au.addEventListener('loadedmetadata',go,{once:true});}
const f1=(v,d)=>v==null?'–':v.toFixed(d);
const btn=(c,lbl)=>`<span class="b ${c.fail?'bad':''}" id="${c.id}" title="${(c.why||[]).join('; ')}" onclick="play('${c.id}','${c.f}')">${lbl}</span>`;
const cell=(x,ref)=>!x?'<td class=muted>–</td>':`<td><span class=sp>${f1(x.spread,1)}/s${x.n_fail?` <span style="color:#e66">${x.n_fail}/${x.n}✗</span>`:''}</span>`+
 `<span class=dr style="color:${ref!=null&&x.drift!=null&&x.drift<ref?'#7d7':'#ccc'}">drift ${f1(x.drift,3)}</span>`+x.clips.map(c=>btn(c,`s${c.seed} ${c.dens}→${f1(c.onsets,1)}`)).join(' ')+'</td>';
let h='<h2>E7 — onset LatCH × FiLM</h2>';
Object.entries(D.e7).forEach(([ctx,E])=>{
 h+=`<h3>${D.ctx_label[ctx]} <span class=muted style="font-weight:normal">· seed reference ${f1(E.seed_ref,3)}</span></h3><div class=muted>unguided: `+
   E.base.map(b=>btn(b,`&#9654; s${b.seed} → ${f1(b.onsets,1)}/s`)).join(' ')+'</div>';
 h+='<table><tr><th>FiLM gain ↓ · LatCH gain →</th>'+E.latches.map(l=>`<th>${l?'LatCH '+l:'LatCH off'}</th>`).join('')+'</tr>';
 E.films.forEach(f=>{h+=`<tr><td>${f?'FiLM '+f:'FiLM off'}</td>`+E.latches.map(l=>(!f&&!l)?'<td class=muted>unguided ↑</td>':cell(E.cells[`${f}|${l}`],E.seed_ref)).join('')+'</tr>';});
 h+='</table>';});
if(Object.keys(D.e8).length){
 h+='<h2>E8 — FiLM only while the noise is high (gated), vs E7\'s ungated FiLM</h2><div class=muted>gate = FiLM runs while the noise level σ is above this value (1 = first step), fading out over 0.1 below it.</div>';
 Object.entries(D.e8).forEach(([ctx,rows])=>{
  h+=`<h3>${D.ctx_label[ctx]}</h3><table><tr><th>arm</th><th>gated: spread · drift · clips</th><th>ungated FiLM (E7)</th></tr>`;
  rows.forEach(r=>{h+=`<tr><td>FiLM ${r.film} · gate σ≥${r.gate}${r.latch?' + LatCH '+r.latch:''}</td>${cell(r,D.e7[ctx]&&D.e7[ctx].seed_ref)}<td>${f1(r.ungated,1)}/s · drift ${f1(r.ungated_drift,3)}</td></tr>`;});
  h+='</table>';});}
document.getElementById('out').innerHTML=h;
</script>
__NOTES__
<footer style="margin:18px 12px;color:#666;font-size:11px">evals &middot; LatCH + FiLM density (EXPERIMENTS E7/E8) &middot; clips: sa3_control_runs (internal) &middot; gate: control-head disintegration gate, quality leg = Audiobox PQ</footer>
</body></html>"""
UN = "" if meta7.get("kim_feedback") else '<span class=un title="No listening verdict recorded yet (unaudited).">&#10071;</span> No listening verdict recorded yet.'
T = T.replace("__PQ__", str(PQ_DRIFT)).replace("__UN__", UN).replace(
    "__NOTES__", notes_block("latch_film_combo", levels=[("clip", "this clip"), ("page", "page")], hint="click a clip, then note what you hear"))
out = os.path.join(STAGE, "latch_film_combo.html")
open(out, "w").write(inject(T.replace("__DATA__", DATA)))
print(f"wrote {out}")
