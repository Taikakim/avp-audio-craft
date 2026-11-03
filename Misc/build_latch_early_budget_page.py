#!/usr/bin/env python3
# Last edited: THE-FINN 2026-11-03 — paths updated for the sa3_control_runs/__theme reorganisation
# Owner: WINTERMUTE (created 2026-10-15)
"""build_latch_early_budget_page.py -- listening page for eval/latch_early_budget_bracket.py.

Question: does a LatCH head steer once guidance gets a real EARLY budget (flat per-step weight
instead of TFG's alpha = 1 - sigma weight, a window that ends early, a sigma schedule that lingers
at high noise)? Every row is one way of spending the guidance; every column a gain; every cell holds
the sparse and the dense request (onset head) or the dark and bright request (air head), per seed.
The headline number is the SPREAD (dense minus sparse measured, averaged over seeds): how far the
request actually moves the output. Gate: control_head_disintegration_eval.gate() vs the same
leg/model/shape/seed unguided clip, quality leg = Audiobox PQ (|dPQ| > 1.5), as latch_onset_grid.
Inputs: Mantu2/sa3_control_runs/__latch/latch_early_budget_20261015/cells.jsonl, eval/clip_metrics.db rows
for ~/evals_aac/latch_early_budget/**.m4a (eval/run_latch_early_budget.sh does both).
Writes ~/evals_aac/latch_early_budget.html. No checkpoint filenames or drive paths on the page.
"""
import json
import os
import sqlite3
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "eval"))
from comment_notes_block import notes_block
from control_head_disintegration_eval import gate
from float_player import inject

SRC = "/run/media/kim/Mantu/sa3_control_runs/__latch/latch_early_budget_20261015"
STAGE = os.path.join(os.path.expanduser("~"), "evals_aac")
SUB = "latch_early_budget"
DB = os.path.join(HERE, "..", "eval", "clip_metrics.db")
PQ_DRIFT = 1.5
LEGS = {
    "A": ("Onset head, base model: weighting × window", "Phase E onset head (E04), model-default sigma schedule, 50 Euler steps. "
          "<i>alpha</i> = the TFG weighting every earlier eval used (almost no guidance in the first steps); <i>flat</i> = equal weight on every step in the window. "
          "Window 0&ndash;0.2 = guidance only in the first fifth of the steps. Requests: 2 vs 10 onsets per second."),
    "B": ("Onset head, base model: sigma schedule warped toward the early steps", "Flat weighting. <i>flux3</i> = Flux distribution shift a=3; <i>logsnr_rho2</i> = logSNR schedule with rho=2. "
          "Both spend more of the 50 steps at high noise, where rhythm forms. Each shape has its own unguided baseline (the schedule alone changes the sound)."),
    "C": ("Air head, base model: weighting × window", "The high-band (2.5 kHz+) RMS head with constant vs alpha weighting. Requests: &minus;55 dB (dark) vs &minus;10 dB (bright); "
          "the number in a cell is the measured air level in dB."),
    "D": ("Onset head, post-trained model (ping-pong, 24 steps)", "Same onset head on the post-trained model, with the model-default and flux3 schedules. One seed."),
}

rows = [json.loads(l) for l in open(f"{SRC}/cells.jsonl") if l.strip()]
con = sqlite3.connect(DB)
cols = [r[1] for r in con.execute("PRAGMA table_info(metrics)")]
met = {os.path.basename(r[0])[:-4]: dict(zip(cols, r)) for r in con.execute("SELECT * FROM metrics WHERE path LIKE ?", (f"%/{SUB}/%",))}

base = {(c["leg"], c["shape"], c["seed"]): c for c in rows if not c["gain"]}
for c in rows:
    c["f"] = f"{SUB}/{c['leg']}/{c['id']}.m4a"
    m = met.get(c["id"], {})
    c["pq"] = m.get("pq")
    c["fail"], c["why"] = False, []
    b = base.get((c["leg"], c["shape"], c["seed"]))
    c["value"] = c["air_db"] if c.get("head") == "air" else c["onsets"]
    if c["gain"] and b and m and b["id"] in met:
        bm = met[b["id"]]
        bad, why, _ = gate({**m, "ce": None}, {**bm, "ce": None}, rhythmic=True)
        if m.get("pq") is not None and bm.get("pq") is not None and abs(m["pq"] - bm["pq"]) > PQ_DRIFT:
            why.append(f"pq-drift({bm['pq']:.2f}->{m['pq']:.2f})")
            bad = True
        c["fail"], c["why"] = bad, why
        c["dpq"] = (m["pq"] - bm["pq"]) if m.get("pq") is not None and bm.get("pq") is not None else None

legs = {}
for leg in sorted({c["leg"] for c in rows}):
    lc = [c for c in rows if c["leg"] == leg]
    g = [c for c in lc if c["gain"]]
    gains = sorted({c["gain"] for c in g})
    reqs = sorted({c["req"] for c in g})
    keys = sorted({(c["shape"], c["sched"], c["end"]) for c in g}, key=lambda k: (k[0] != "model", k[0], k[1], k[2]))
    table = []
    for k in keys:
        r = {"shape": k[0], "sched": k[1], "end": k[2], "cells": []}
        for gain in gains:
            cc = [c for c in g if (c["shape"], c["sched"], c["end"]) == k and c["gain"] == gain]
            by = defaultdict(dict)
            for c in cc:
                by[c["seed"]][c["req"]] = c
            spreads = [d[reqs[-1]]["value"] - d[reqs[0]]["value"] for d in by.values() if reqs[0] in d and reqs[-1] in d]
            r["cells"].append({"gain": gain, "spread": sum(spreads) / len(spreads) if spreads else None,
                               "n_fail": sum(c["fail"] for c in cc), "n": len(cc),
                               "clips": [{k2: c.get(k2) for k2 in ("id", "f", "seed", "req", "value", "pq", "dpq", "fail", "why")} for c in sorted(cc, key=lambda c: (c["seed"], c["req"]))]})
        table.append(r)
    bl = [{k2: b.get(k2) for k2 in ("id", "f", "seed", "shape", "value", "pq")} | {"f": f"{SUB}/{leg}/{b['id']}.m4a", "value": b["air_db"] if leg == "C" else b["onsets"]}
          for b in sorted([c for c in lc if not c["gain"]], key=lambda c: (c["shape"], c["seed"]))]
    legs[leg] = {"title": LEGS[leg][0], "desc": LEGS[leg][1], "gains": gains, "reqs": reqs, "rows": table, "baselines": bl,
                 "unit": "dB air" if leg == "C" else "onsets/s"}
    best = max((x for r in table for x in r["cells"] if x["spread"] is not None and x["n_fail"] == 0), key=lambda x: x["spread"], default=None)
    print(f"{leg}: {len(lc)} clips; widest clean spread " + (f"{best['spread']:.2f} at gain {best['gain']}" if best else "none"))

meta = json.load(open(f"{SRC}/run_meta.json"))
DATA = json.dumps({"legs": legs, "audited": bool(meta.get("kim_feedback")), "pq": PQ_DRIFT})
T = r"""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>LatCH Early Budget</title><style>
body{font:13px system-ui;margin:0;background:#0e0e10;color:#e0e0e0}
#bar{position:sticky;top:0;background:#16181c;padding:7px 12px;border-bottom:1px solid #2a2a30;z-index:9}
#wrap{padding:14px;max-width:1400px}h1{font-size:18px}h2{font-size:15px;margin:24px 0 4px;color:#cde}.muted{color:#888}
.explain{background:#1a140c;border:1px solid #433;border-left:3px solid #d90;padding:10px 12px;font-size:12.5px;color:#dcd;margin:10px 0;line-height:1.45}.explain b{color:#fc6}
.legd{font-size:12.5px;color:#bbc;margin:2px 0 6px;max-width:1100px}
table{border-collapse:collapse;font-size:12px;margin:4px 0;display:block;overflow-x:auto}td,th{border:1px solid #2a2a30;padding:4px 6px;text-align:center;white-space:nowrap;vertical-align:top}
th{background:#1c1c22;color:#aaa}td:first-child{text-align:left;color:#9ab}
.sp{font-weight:bold;font-variant-numeric:tabular-nums;display:block;margin-bottom:3px}.hot{color:#7e7}
.b{display:inline-block;cursor:pointer;border:1px solid #333;border-radius:3px;padding:1px 4px;margin:1px;font-size:11px;font-variant-numeric:tabular-nums;background:#18181c}
.b:hover{outline:1px solid #7cf}.play{outline:2px solid #5d5 !important}.bad{background:#2a1214;border-color:#733}.un{color:#e44;font-weight:bold;cursor:help}
</style></head><body>
<div id=bar>&#9654; <b id=np>click a clip to play</b> <span id=pos class=muted></span> <span class=muted>· switching keeps the playhead · re-click stops</span></div>
<div id=wrap><h1>LatCH guidance: does an early budget let the heads steer?</h1>
<div class=explain><b>Why this page exists.</b> The guidance weighting inherited from TFG (and the LatCH paper) gives each sampling step a share proportional to how much signal it has,
so the first 20% of steps, where rhythm and arrangement are decided, received about 0.2% of the guidance and the last 20% about 62%. Every onset-head test so far used it,
and the verdict was that the heads barely change the sound except where it collapses. Here the same heads get <b>flat</b> weighting, <b>early-only windows</b>, and
<b>sigma schedules that linger at high noise</b>. <b>How to read it.</b> Each cell is one gain for one way of spending the guidance. The big number is the <b>spread</b>:
measured value for the high request minus the low request, averaged over seeds (for reference, the FiLM onset adapter spans roughly 2&ndash;11 onsets/s on these requests;
the alpha-weighted heads at clean gains managed about 2&ndash;3). The small buttons play each clip: seed · request → measured · PQ change. Red = failed the disintegration gate
against the unguided clip of the same leg, schedule and seed (whitening, buzz, noise, beat loss, or PQ moving more than __PQ__); hover for the reason.
<b>What it cannot tell you.</b> Whether the groove changes musically: onset counts and PQ are screens, the ear decides. __UN__</div>
<div id=out></div></div><audio id=au_el></audio>
<script>const D=__DATA__;
const au=document.getElementById('au_el'),npx=document.getElementById('np');let cur=null;
au.addEventListener('timeupdate',()=>{document.getElementById('pos').textContent=cur?('· '+au.currentTime.toFixed(1)+'s'):'';});
au.addEventListener('ended',()=>{cur=null;mark();});
function mark(){document.querySelectorAll('.b.play').forEach(e=>e.classList.remove('play'));if(cur){const e=document.getElementById(cur);if(e)e.classList.add('play');}}
function play(id,f){if(cur===id){au.pause();cur=null;mark();npx.textContent='stopped';return;}
 if(window.noteSet)noteSet({model:'latch_early_budget',ckpt:'',clip:id});
 const pos=(cur!==null&&!au.paused)?au.currentTime:0;cur=id;mark();npx.textContent=id;au.src=f;
 const go=()=>{try{au.currentTime=Math.min(pos,(au.duration||1e9)-0.05);}catch(e){}au.play();};
 if(au.readyState>=1)go();else au.addEventListener('loadedmetadata',go,{once:true});}
const f1=(v,d)=>v==null?'–':v.toFixed(d),sg=(v,d)=>v==null?'':(v>=0?'+':'')+v.toFixed(d);
const btn=(c,lbl)=>`<span class="b ${c.fail?'bad':''}" id="${c.id}" title="${(c.why||[]).join('; ')}" onclick="play('${c.id}','${c.f}')">${lbl}</span>`;
let h='';
Object.entries(D.legs).forEach(([k,L])=>{
 h+=`<h2>${k}. ${L.title}</h2><div class=legd>${L.desc}</div><div class=muted>unguided: `+L.baselines.map(b=>btn({...b,fail:false},`&#9654; ${b.shape} s${b.seed} → ${f1(b.value,1)}`)).join(' ')+'</div>';
 const all=L.rows.flatMap(r=>r.cells).filter(x=>x.spread!=null&&x.n_fail===0).map(x=>x.spread),mx=Math.max(...all,0);
 h+='<table><tr><th>schedule · weighting · window</th>'+L.gains.map(g=>`<th>gain ${g}</th>`).join('')+'</tr>';
 L.rows.forEach(r=>{h+=`<tr><td>${r.shape} · ${r.sched} · 0&ndash;${r.end}</td>`;
  r.cells.forEach(x=>{h+=`<td><span class="sp ${x.n_fail===0&&x.spread!=null&&x.spread>=0.8*mx?'hot':''}">${f1(x.spread,2)} <span class=muted style="font-weight:normal">${L.unit}${x.n_fail?` · ${x.n_fail}/${x.n} ✗`:''}</span></span>`+
   x.clips.map(c=>btn(c,`s${c.seed} ${c.req}→${f1(c.value,1)} ${sg(c.dpq,1)}`)).join('')+'</td>';});
  h+='</tr>';});
 h+='</table>';});
document.getElementById('out').innerHTML=h;
</script>
__NOTES__
<footer style="margin:18px 12px;color:#666;font-size:11px">evals &middot; LatCH early-budget bracket &middot; clips: sa3_control_runs (internal) &middot; gate: control-head disintegration gate, quality leg = Audiobox PQ</footer>
</body></html>"""
UN = "" if meta.get("kim_feedback") else '<span class=un title="No listening verdict recorded yet (unaudited).">&#10071;</span> No listening verdict recorded yet.'
T = T.replace("__PQ__", str(PQ_DRIFT)).replace("__UN__", UN).replace("__NOTES__", notes_block("latch_early_budget", levels=[("clip", "this clip"), ("page", "page")], hint="click a clip, then note what you hear"))
out = os.path.join(STAGE, "latch_early_budget.html")
open(out, "w").write(inject(T.replace("__DATA__", DATA)))
print(f"wrote {out}: {len(rows)} clips")
