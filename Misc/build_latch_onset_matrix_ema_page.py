#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-15)
"""build_latch_onset_matrix_ema_page.py -- listening page for eval/latch_onset_matrix_ema.py.

The onset head (Phase E E04 recipe, retrained with EMA) guided with alpha weighting over the full window 0-1, the
setting the 2026-10-15 listening verdict called the cleanest and transparent. Rows = requested density 0..12
onsets/s, columns = gain 32..4096, one table each for the EMA and the online (Schedule-Free averaged) weights of the
same run and epoch. Cell = measured onsets/s averaged over the two seeds, plus one button per seed. Per gain, a
summary row: request-vs-measured correlation, range of the cell means, gate fails. Gate:
control_head_disintegration_eval.gate() vs the unguided clip of the same seed, quality leg = Audiobox PQ
(|dPQ| > 1.5), as on latch_onset_grid / latch_early_budget.
Inputs: Mantu2/sa3_control_runs/latch_onset_matrix_ema_20261015/{cells.jsonl,run_meta.json}, eval/clip_metrics.db
rows for ~/evals_aac/latch_onset_matrix_ema/**.m4a (eval/run_latch_onset_matrix_ema.sh writes both).
Writes ~/evals_aac/latch_onset_matrix_ema.html. No checkpoint filenames or drive paths on the page.
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

SRC = "/run/media/kim/Mantu/sa3_control_runs/latch_onset_matrix_ema_20261015"
STAGE = os.path.join(os.path.expanduser("~"), "evals_aac")
SUB = "latch_onset_matrix_ema"
DB = os.path.join(HERE, "..", "eval", "clip_metrics.db")
PQ_DRIFT = 1.5

rows = [json.loads(l) for l in open(f"{SRC}/cells.jsonl") if l.strip()]
meta = json.load(open(f"{SRC}/run_meta.json"))
con = sqlite3.connect(DB)
cols = [r[1] for r in con.execute("PRAGMA table_info(metrics)")]
met = {os.path.basename(r[0])[:-4]: dict(zip(cols, r)) for r in con.execute("SELECT * FROM metrics WHERE path LIKE ?", (f"%/{SUB}/%",))}

base = {c["seed"]: c for c in rows if not c["gain"]}
for c in rows:
    c["f"] = f"{SUB}/{c['weights']}/{c['id']}.m4a"
    m, b = met.get(c["id"], {}), base.get(c["seed"])
    c["pq"], c["fail"], c["why"], c["dpq"] = m.get("pq"), False, [], None
    if c["gain"] and b and m and b["id"] in met:
        bm = met[b["id"]]
        bad, why, _ = gate({**m, "ce": None}, {**bm, "ce": None}, rhythmic=True)
        if m.get("pq") is not None and bm.get("pq") is not None:
            c["dpq"] = m["pq"] - bm["pq"]
            if abs(c["dpq"]) > PQ_DRIFT:
                why.append(f"pq-drift({bm['pq']:.2f}->{m['pq']:.2f})")
                bad = True
        c["fail"], c["why"] = bad, why

gains = sorted({c["gain"] for c in rows if c["gain"]})
targets = sorted({c["req"] for c in rows if c["gain"]})
tables, summary = {}, {}
for w in ("ema", "online"):
    g_rows = [c for c in rows if c["weights"] == w]
    grid = []
    for r in targets:
        line = []
        for g in gains:
            cc = sorted([c for c in g_rows if c["gain"] == g and c["req"] == r], key=lambda c: c["seed"])
            line.append({"mean": float(np.mean([c["onsets"] for c in cc])) if cc else None, "n_fail": sum(c["fail"] for c in cc),
                         "clips": [{k: c.get(k) for k in ("id", "f", "seed", "onsets", "dpq", "fail", "why")} for c in cc]})
        grid.append({"req": r, "cells": line})
    sm = []
    for j, g in enumerate(gains):
        cc = [c for c in g_rows if c["gain"] == g]
        req, meas = np.array([c["req"] for c in cc], float), np.array([c["onsets"] for c in cc], float)
        means = [grid[i]["cells"][j]["mean"] for i in range(len(targets))]
        sm.append({"gain": g, "corr": float(np.corrcoef(req, meas)[0, 1]), "lo": min(means), "hi": max(means),
                   "n_fail": sum(c["fail"] for c in cc), "n": len(cc)})
    tables[w], summary[w] = grid, sm
    clean = [s["gain"] for s in sm if s["n_fail"] == 0]
    print(f"{w}: fails per gain " + " ".join(f"{s['gain']}:{s['n_fail']}" for s in sm) + f"; highest all-clean gain {max(clean) if clean else None}")

bl = [{"id": b["id"], "f": f"{SUB}/base/{b['id']}.m4a", "seed": b["seed"], "onsets": b["onsets"]} for b in sorted(base.values(), key=lambda b: b["seed"])]
ck = meta.get("checkpoints", {})
DATA = json.dumps({"gains": gains, "tables": tables, "summary": summary, "base": bl,
                   "epoch": {k: v.get("epoch") for k, v in ck.items()}, "pq": PQ_DRIFT})

T = r"""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>LatCH Onset Matrix</title><style>
body{font:13px system-ui;margin:0;background:#0e0e10;color:#e0e0e0}
#bar{position:sticky;top:0;background:#16181c;padding:7px 12px;border-bottom:1px solid #2a2a30;z-index:9}
#wrap{padding:14px;max-width:1500px}h1{font-size:18px}h2{font-size:15px;margin:24px 0 4px;color:#cde}.muted{color:#888}
.explain{background:#1a140c;border:1px solid #433;border-left:3px solid #d90;padding:10px 12px;font-size:12.5px;color:#dcd;margin:10px 0;line-height:1.45}.explain b{color:#fc6}
table{border-collapse:collapse;font-size:11.5px;margin:4px 0;display:block;overflow-x:auto}td,th{border:1px solid #2a2a30;padding:3px 4px;text-align:center;white-space:nowrap;vertical-align:top}
th{background:#1c1c22;color:#aaa}td:first-child{text-align:right;color:#9ab}tr.sum td{background:#15151a;color:#bbc;font-size:11px}
.m{display:block;font-weight:bold;font-variant-numeric:tabular-nums}
.b{display:inline-block;cursor:pointer;border:1px solid #333;border-radius:3px;padding:0 3px;margin:1px;font-size:10.5px;font-variant-numeric:tabular-nums;background:#18181c}
.b:hover{outline:1px solid #7cf}.play{outline:2px solid #5d5 !important}.bad{background:#2a1214;border-color:#733}.un{color:#e44;font-weight:bold;cursor:help}
</style></head><body>
<div id=bar>&#9654; <b id=np>click a clip to play</b> <span id=pos class=muted></span> <span class=muted>· switching keeps the playhead · re-click stops</span></div>
<div id=wrap><h1>Onset LatCH head: requested density × gain, EMA vs online weights</h1>
<div class=explain><b>Why this page exists.</b> On the early-budget page the default TFG weighting over the whole run (alpha, window 0&ndash;1) was the cleanest way to
spend the guidance: noticeable, and transparent (the musical material stays, where the FiLM onset adapter pulls in the training-set style). Gain 512 was quite okay,
2048 not impossible. This maps that one setting finely. The onset head was retrained on the Phase E E04 recipe with an EMA (half-life 0.5 epoch), so the
<b>EMA</b> and the <b>online</b> weights (the optimiser's own averaged weights, no EMA on top) come from the same run and epoch. <b>How to read it.</b> Rows: requested
density in onsets per second. Columns: guidance gain. The bold number is the measured density averaged over two seeds (unguided: __BASE__); the buttons play each seed's
clip and show measured · PQ change. Red = failed the disintegration gate against the unguided clip of the same seed (whitening, buzz, noise, beat loss, or PQ moving more than
__PQ__). The grey row per table: request-vs-measured correlation, the range the cell means cover, and gate fails. <b>What it cannot tell you.</b> Whether the groove changes
musically: onset counts and PQ are screens, the ear decides. __UN__</div>
<div id=out></div></div><audio id=au_el></audio>
<script>const D=__DATA__;
const au=document.getElementById('au_el'),npx=document.getElementById('np');let cur=null;
au.addEventListener('timeupdate',()=>{document.getElementById('pos').textContent=cur?('· '+au.currentTime.toFixed(1)+'s'):'';});
au.addEventListener('ended',()=>{cur=null;mark();});
function mark(){document.querySelectorAll('.b.play').forEach(e=>e.classList.remove('play'));if(cur){const e=document.getElementById(cur);if(e)e.classList.add('play');}}
function play(id,f){if(cur===id){au.pause();cur=null;mark();npx.textContent='stopped';return;}
 if(window.noteSet)noteSet({model:'latch_onset_matrix_ema',ckpt:'',clip:id});
 const pos=(cur!==null&&!au.paused)?au.currentTime:0;cur=id;mark();npx.textContent=id;au.src=f;
 const go=()=>{try{au.currentTime=Math.min(pos,(au.duration||1e9)-0.05);}catch(e){}au.play();};
 if(au.readyState>=1)go();else au.addEventListener('loadedmetadata',go,{once:true});}
const f1=(v,d)=>v==null?'–':v.toFixed(d),sg=(v,d)=>v==null?'':(v>=0?'+':'')+v.toFixed(d);
const btn=(c,lbl)=>`<span class="b ${c.fail?'bad':''}" id="${c.id}" title="${(c.why||[]).join('; ')}" onclick="play('${c.id}','${c.f}')">${lbl}</span>`;
const col=v=>{const t=Math.max(0,Math.min(1,(v-4)/6));return `hsl(${210-170*t},60%,${55+10*t}%)`;};
let h='<div class=muted>unguided: '+D.base.map(b=>btn(b,`&#9654; s${b.seed} → ${f1(b.onsets,1)}`)).join(' ')+'</div>';
[['ema','EMA weights'],['online','Online weights (no EMA)']].forEach(([w,title])=>{
 h+=`<h2>${title} <span class=muted style="font-weight:normal">· epoch ${D.epoch[w]}</span></h2><table><tr><th>request ↓ · gain →</th>`+D.gains.map(g=>`<th>${g}</th>`).join('')+'</tr>';
 D.tables[w].forEach(r=>{h+=`<tr><td>${r.req} /s</td>`;
  r.cells.forEach(x=>{h+=`<td><span class=m style="color:${col(x.mean)}">${f1(x.mean,1)}${x.n_fail?' <span style="color:#e66">✗</span>':''}</span>`+
   x.clips.map(c=>btn(c,`s${c.seed} ${f1(c.onsets,1)} ${sg(c.dpq,1)}`)).join('<br>')+'</td>';});
  h+='</tr>';});
 h+='<tr class=sum><td>corr · range · fails</td>'+D.summary[w].map(s=>`<td>${s.corr.toFixed(2)}<br>${s.lo.toFixed(1)}–${s.hi.toFixed(1)}<br>${s.n_fail?`<span style="color:#e66">${s.n_fail}/${s.n} ✗</span>`:'clean'}</td>`).join('')+'</tr></table>';});
document.getElementById('out').innerHTML=h;
</script>
__NOTES__
<footer style="margin:18px 12px;color:#666;font-size:11px">evals &middot; LatCH onset matrix, EMA vs online &middot; clips: sa3_control_runs (internal) &middot; gate: control-head disintegration gate, quality leg = Audiobox PQ</footer>
</body></html>"""
UN = "" if meta.get("kim_feedback") else '<span class=un title="No listening verdict recorded yet (unaudited).">&#10071;</span> No listening verdict recorded yet.'
BASE = ", ".join(f"seed {b['seed']} {b['onsets']:.1f}/s" for b in bl)
T = (T.replace("__PQ__", str(PQ_DRIFT)).replace("__UN__", UN).replace("__BASE__", BASE)
     .replace("__NOTES__", notes_block("latch_onset_matrix_ema", levels=[("clip", "this clip"), ("page", "page")], hint="click a clip, then note what you hear")))
out = os.path.join(STAGE, "latch_onset_matrix_ema.html")
open(out, "w").write(inject(T.replace("__DATA__", DATA)))
print(f"wrote {out}: {len(rows)} clips")
