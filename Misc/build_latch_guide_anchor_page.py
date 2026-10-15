#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-15)
"""build_latch_guide_anchor_page.py -- listening page for the LatCH loudness fixes (guide_anchor, guide_rescale).

Both tests render the onset head E04 under the four ways of spending guidance from latch_early_budget (alpha/flat x
window 0-1 / 0-0.2) at gains 512/2048/4096, requests 2 and 10 onsets/s, two seeds. Section 1: the trajectory anchor
(eval/latch_guide_anchor_test.py, s0 off / 1.2 / 1.4). Section 2: the per-edit rescale (eval/latch_guide_rescale_test.py,
phi 0 / 0.7 / 1), the negative result kept for comparison. Per cell: onset spread (request 10 minus request 2,
seed mean), raw RMS before normalisation, final latent std, and per-clip buttons. Gate vs the unguided clip of the
same seed (control_head_disintegration_eval.gate, PQ leg |dPQ| > 1.5).
Writes ~/evals_aac/latch_guide_anchor.html. No checkpoint filenames or drive paths on the page.
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

RUNS = [("latch_guide_anchor", "/run/media/kim/Mantu/sa3_control_runs/latch_guide_anchor_20261015", "anchor", "anchor s0",
         "Trajectory anchor: after every step the latent's std is capped at the healthy value for that noise level (s0 = target level "
         "of the finished latent; 0 = off). Normal states are untouched."),
        ("latch_guide_rescale", "/run/media/kim/Mantu/sa3_control_runs/latch_guide_rescale_20261015", "phi", "rescale φ",
         "Per-edit rescale (negative result, kept for comparison): after each guidance edit the std is put back to its pre-edit value. "
         "Level and loudness barely move, because the inflation builds through the model's own later steps, not in the edits.")]
STAGE = os.path.join(os.path.expanduser("~"), "evals_aac")
DB = os.path.join(HERE, "..", "eval", "clip_metrics.db")
PQ_DRIFT = 1.5

con = sqlite3.connect(DB)
cols = [r[1] for r in con.execute("PRAGMA table_info(metrics)")]
sections, audited = [], False
for sub, src, knob, knob_lbl, desc in RUNS:
    rows = [json.loads(l) for l in open(f"{src}/cells.jsonl") if l.strip()]
    audited = audited or bool(json.load(open(f"{src}/run_meta.json")).get("kim_feedback"))
    met = {os.path.basename(r[0])[:-4]: dict(zip(cols, r)) for r in con.execute("SELECT * FROM metrics WHERE path LIKE ?", (f"%/{sub}/%",))}
    base = {c["seed"]: c for c in rows if not c["gain"]}
    for c in rows:
        c["f"] = f"{sub}/{c['id']}.m4a"
        m, b = met.get(c["id"], {}), base.get(c["seed"])
        c["fail"], c["why"], c["dpq"] = False, [], None
        if c["gain"] and b and m and b["id"] in met:
            bm = met[b["id"]]
            bad, why, _ = gate({**m, "ce": None}, {**bm, "ce": None}, rhythmic=True)
            if m.get("pq") is not None and bm.get("pq") is not None:
                c["dpq"] = m["pq"] - bm["pq"]
                if abs(c["dpq"]) > PQ_DRIFT:
                    why.append(f"pq-drift({bm['pq']:.2f}->{m['pq']:.2f})")
                    bad = True
            c["fail"], c["why"] = bad, why
    g = [c for c in rows if c["gain"]]
    gains, kv = sorted({c["gain"] for c in g}), sorted({c[knob] for c in g})
    configs = [("alpha", 1.0), ("flat", 1.0), ("alpha", 0.2), ("flat", 0.2)]
    table = []
    for sched, end in configs:
        line = {"label": f"{sched} · 0–{end:g}", "cells": []}
        for gn in gains:
            for k in kv:
                cc = sorted([c for c in g if c["sched"] == sched and c["end"] == end and c["gain"] == gn and c[knob] == k],
                            key=lambda c: (c["seed"], c["req"]))
                hi = [c["onsets"] for c in cc if c["req"] == 10]
                lo = [c["onsets"] for c in cc if c["req"] == 2]
                line["cells"].append({"gain": gn, "k": k, "spread": float(np.mean(hi) - np.mean(lo)) if hi and lo else None,
                                      "rms": float(np.mean([c["raw_rms_db"] for c in cc])), "z": float(np.mean([c["latent_std"] for c in cc])),
                                      "n_fail": sum(c["fail"] for c in cc), "n": len(cc),
                                      "clips": [{x: c.get(x) for x in ("id", "f", "seed", "req", "onsets", "dpq", "fail", "why", "raw_rms_db")} for c in cc]})
        table.append(line)
    bl = [{"id": b["id"], "f": f"{sub}/{b['id']}.m4a", "seed": b["seed"], "onsets": b["onsets"], "rms": b["raw_rms_db"], "z": b["latent_std"]}
          for b in sorted(base.values(), key=lambda b: b["seed"])]
    sections.append({"title": knob_lbl, "desc": desc, "gains": gains, "kv": kv, "rows": table, "base": bl, "knob": knob})
    print(f"{sub}: {len(rows)} clips, {sum(c['fail'] for c in g)} gate fails")

DATA = json.dumps({"sections": sections, "pq": PQ_DRIFT})
T = r"""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>LatCH Loudness Anchor</title><style>
body{font:13px system-ui;margin:0;background:#0e0e10;color:#e0e0e0}
#bar{position:sticky;top:0;background:#16181c;padding:7px 12px;border-bottom:1px solid #2a2a30;z-index:9}
#wrap{padding:14px;max-width:1500px}h1{font-size:18px}h2{font-size:15px;margin:24px 0 4px;color:#cde}.muted{color:#888}
.explain{background:#1a140c;border:1px solid #433;border-left:3px solid #d90;padding:10px 12px;font-size:12.5px;color:#dcd;margin:10px 0;line-height:1.45}.explain b{color:#fc6}
.legd{font-size:12.5px;color:#bbc;margin:2px 0 6px;max-width:1100px}
table{border-collapse:collapse;font-size:11.5px;margin:4px 0;display:block;overflow-x:auto}td,th{border:1px solid #2a2a30;padding:3px 5px;text-align:center;white-space:nowrap;vertical-align:top}
th{background:#1c1c22;color:#aaa}td:first-child{text-align:left;color:#9ab}th.g{border-left:2px solid #555}td.g{border-left:2px solid #555}
.sp{font-weight:bold;display:block;font-variant-numeric:tabular-nums}.lv{display:block;font-size:10.5px;font-variant-numeric:tabular-nums}
.b{display:inline-block;cursor:pointer;border:1px solid #333;border-radius:3px;padding:0 3px;margin:1px;font-size:10.5px;font-variant-numeric:tabular-nums;background:#18181c}
.b:hover{outline:1px solid #7cf}.play{outline:2px solid #5d5 !important}.bad{background:#2a1214;border-color:#733}.un{color:#e44;font-weight:bold;cursor:help}
</style></head><body>
<div id=bar>&#9654; <b id=np>click a clip to play</b> <span id=pos class=muted></span> <span class=muted>· switching keeps the playhead · re-click stops</span></div>
<div id=wrap><h1>LatCH guidance without the loudness push</h1>
<div class=explain><b>Why this page exists.</b> On the early-budget page, flat weighting and early-only windows steered onsets harder but pushed the volume up into clipping
and distortion; the default alpha weighting over the whole run stayed clean. The finished latent of those renders had 2&ndash;5 times its normal spread. Two fixes were tried
on the same onset head and settings. <b>How to read it.</b> Rows: way of spending the guidance. Column groups: gain; inside each, the fix off and at two strengths. Per cell:
the onset <b>spread</b> (measured density for the 10/s request minus the 2/s request, seed mean), then the raw loudness before any normalisation (dB RMS) and the latent's
spread (std; unguided ≈ 1.1), coloured red when louder than the unguided clips by more than 2 dB. Buttons: seed · request → measured. Red buttons failed the disintegration
gate against the unguided clip of the same seed (whitening, buzz, noise, beat loss, or PQ moving more than __PQ__). <b>What it cannot tell you.</b> Whether the steered clips
sound clean or musical: level and onset counts are screens, the ear decides. __UN__</div>
<div id=out></div></div><audio id=au_el></audio>
<script>const D=__DATA__;
const au=document.getElementById('au_el'),npx=document.getElementById('np');let cur=null;
au.addEventListener('timeupdate',()=>{document.getElementById('pos').textContent=cur?('· '+au.currentTime.toFixed(1)+'s'):'';});
au.addEventListener('ended',()=>{cur=null;mark();});
function mark(){document.querySelectorAll('.b.play').forEach(e=>e.classList.remove('play'));if(cur){const e=document.getElementById(cur);if(e)e.classList.add('play');}}
function play(id,f){if(cur===id){au.pause();cur=null;mark();npx.textContent='stopped';return;}
 if(window.noteSet)noteSet({model:'latch_guide_anchor',ckpt:'',clip:id});
 const pos=(cur!==null&&!au.paused)?au.currentTime:0;cur=id;mark();npx.textContent=id;au.src=f;
 const go=()=>{try{au.currentTime=Math.min(pos,(au.duration||1e9)-0.05);}catch(e){}au.play();};
 if(au.readyState>=1)go();else au.addEventListener('loadedmetadata',go,{once:true});}
const f1=(v,d)=>v==null?'–':v.toFixed(d);
const btn=(c,lbl)=>`<span class="b ${c.fail?'bad':''}" id="${c.id}" title="${(c.why||[]).join('; ')}" onclick="play('${c.id}','${c.f}')">${lbl}</span>`;
let h='';
D.sections.forEach((S,si)=>{
 const ref=S.base.reduce((a,b)=>a+b.rms,0)/S.base.length;
 h+=`<h2>${si+1}. ${S.title}</h2><div class=legd>${S.desc}</div><div class=muted>unguided: `+S.base.map(b=>btn(b,`&#9654; s${b.seed} → ${f1(b.onsets,1)}/s · ${f1(b.rms,1)} dB · std ${f1(b.z,2)}`)).join(' ')+'</div>';
 h+='<table><tr><th rowspan=2>weighting · window</th>'+S.gains.map(g=>`<th class=g colspan=${S.kv.length}>gain ${g}</th>`).join('')+'</tr><tr>'+
   S.gains.map(()=>S.kv.map((k,i)=>`<th class="${i?'':'g'}">${k?S.title.split(' ').pop()+' '+k:'off'}</th>`).join('')).join('')+'</tr>';
 S.rows.forEach(r=>{h+=`<tr><td>${r.label}</td>`;
  r.cells.forEach((x,i)=>{const loud=x.rms>ref+2;
   h+=`<td class="${i%S.kv.length?'':'g'}"><span class=sp>${f1(x.spread,1)}/s${x.n_fail?` <span style="color:#e66">${x.n_fail}/${x.n}✗</span>`:''}</span>`+
    `<span class=lv style="color:${loud?'#e66':'#9b9'}">${f1(x.rms,1)} dB · ${f1(x.z,2)}</span>`+
    x.clips.map(c=>btn(c,`s${c.seed} ${c.req}→${f1(c.onsets,1)}`)).join('<br>')+'</td>';});
  h+='</tr>';});
 h+='</table>';});
document.getElementById('out').innerHTML=h;
</script>
__NOTES__
<footer style="margin:18px 12px;color:#666;font-size:11px">evals &middot; LatCH loudness fixes (trajectory anchor, per-edit rescale) &middot; clips: sa3_control_runs (internal) &middot; gate: control-head disintegration gate, quality leg = Audiobox PQ</footer>
</body></html>"""
UN = "" if audited else '<span class=un title="No listening verdict recorded yet (unaudited).">&#10071;</span> No listening verdict recorded yet.'
T = T.replace("__PQ__", str(PQ_DRIFT)).replace("__UN__", UN).replace(
    "__NOTES__", notes_block("latch_guide_anchor", levels=[("clip", "this clip"), ("page", "page")], hint="click a clip, then note what you hear"))
out = os.path.join(STAGE, "latch_guide_anchor.html")
open(out, "w").write(inject(T.replace("__DATA__", DATA)))
print(f"wrote {out}")
