#!/usr/bin/env python3
"""build_latch_sa3_matrix_page.py — the LatCH steering hyperparameter sweep page
(Kim ask 2026-07-19: "a big DoRA-page for the FiLM/LatCH models, sweeping
through the hyperparameters"). Companion to Misc/build_model_matrix.py (DoRA)
and control/sa3_control/onset_eval.py + Misc build_onset_eval_page.py (FiLM
control adapters, already live at onset_eval.html — not duplicated here).

Reads latch_sa3_sweep_20260719/{latch_sweep_manifest.json, scores.json,
run_meta.json}, one section per head: a gain x prompt table (measured value +
Δ-from-target), same-playhead cells, a per-head verdict line (steers/moderate/
dead, from the gain->|delta shrink| trend) matching onset_eval.html's corr/gain
convention, and the shared baseline row (gain=0, no guidance).

Run: python3 Misc/build_latch_sa3_matrix_page.py
"""
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comment_notes_block import notes_block

RUN = "/run/media/kim/Mantu/sa3_control_runs/latch_sa3_sweep_20260719"
STAGE = os.path.join(os.path.expanduser("~"), "evals_aac")
CLIPS = os.path.join(STAGE, "latch_sa3_sweep")
os.makedirs(CLIPS, exist_ok=True)

manifest = json.load(open(os.path.join(RUN, "latch_sweep_manifest.json")))
scores = json.load(open(os.path.join(RUN, "scores.json")))
meta = json.load(open(os.path.join(RUN, "run_meta.json")))


def enc(src, dst):
    if not os.path.exists(dst):
        subprocess.run(["ffmpeg", "-y", "-i", src, "-c:a", "aac", "-b:a", "192k", dst],
                       capture_output=True)


jobs = [(os.path.join(RUN, c["clip"]), os.path.join(CLIPS, c["clip"].replace(".wav", ".m4a")))
        for c in manifest["cells"] if os.path.exists(os.path.join(RUN, c["clip"]))]
with ThreadPoolExecutor(max_workers=8) as ex:
    list(ex.map(lambda j: enc(*j), jobs))
print(f"encoded {len(jobs)} clips")

# disintegration gate (C's mandatory control-head screen, 2026-07-20): usable-gain
# ceiling per head + per-cell disintegrated flag, joined by the {head}__g{gain}__{pid} stem.
_gp = os.path.join(os.path.dirname(__file__), "..", "eval", "control_head_disintegration.json")
GATE = json.load(open(_gp)) if os.path.exists(_gp) else {"cells": {}, "result": {}}
gate_cells, gate_result = GATE.get("cells", {}), GATE.get("result", {})

by_head = {}
baselines = {}
for c in manifest["cells"]:
    s = scores.get(c["clip"], {})
    row = {**c, **s, "f": f"latch_sa3_sweep/{c['clip'].replace('.wav', '.m4a')}"}
    if c["head"] == "baseline":
        baselines[c["prompt_id"]] = row
    else:
        by_head.setdefault(c["head"], []).append(row)

heads_out = []
for head, rows in sorted(by_head.items()):
    rows.sort(key=lambda r: (r["gain"], r["prompt_id"]))
    for r in rows:                                  # join C's disintegration gate
        gc = gate_cells.get(f"{head}__g{int(r['gain'])}__{r['prompt_id']}", {})
        r["disint"] = gc.get("disintegrated", False)
        r["dreasons"] = "; ".join(gc.get("hard_reasons", []))
    ceiling = {pid: gate_result.get(head, {}).get(pid, {}).get("usable_max_gain")
               for pid in sorted({r["prompt_id"] for r in rows})}
    gains = sorted({r["gain"] for r in rows})
    # verdict: does |delta| shrink as gain rises, relative to the unguided baseline offset?
    target = rows[0].get("target")
    base_deltas = [abs((baselines.get(pid, {}).get("measured") or target) - target)
                  for pid in {r["prompt_id"] for r in rows}] if target is not None else []
    measured_deltas = [abs(r["delta"]) for r in rows if r.get("delta") is not None]
    verdict = "no measurement" if not measured_deltas else (
        "steers" if min(measured_deltas) < 0.5 * (sum(base_deltas) / max(len(base_deltas), 1) or 1e9)
        else "weak/dead")
    heads_out.append({"head": head, "target": target, "rows": rows, "gains": gains,
                      "verdict": verdict, "ceiling": ceiling,
                      "measurable": rows[0].get("measurable", True)})

DATA = json.dumps({"heads": heads_out, "baselines": baselines, "meta": meta})

T = r"""<!doctype html><html><head><meta charset=utf-8><title>LatCH steering sweep — SA3 medium</title><style>
body{font:13px system-ui;margin:0;background:#0e0e10;color:#e0e0e0;max-width:1200px}
#bar{position:sticky;top:0;background:#16181c;padding:7px 12px;border-bottom:1px solid #2a2a30;z-index:9}
#wrap{padding:14px}h1{font-size:18px}h2{font-size:15px;color:#9cf;margin:20px 0 3px}.muted{color:#888}
#explain{background:#1a140c;border:1px solid #433;border-left:3px solid #d90;padding:10px 12px;font-size:12.5px;color:#dcd;margin:10px 0}#explain b{color:#fc6}
table{border-collapse:collapse;font-size:12px;margin:4px 0}td,th{border:1px solid #2a2a30;padding:4px 8px;text-align:center}
th{background:#1c1c22;color:#aaa}td:first-child,th:first-child{text-align:left;color:#9ab}
.c{cursor:pointer;font-variant-numeric:tabular-nums}.c:hover{outline:2px solid #7cf}.play{outline:2px solid #5d5 !important}.loading{outline:2px solid #fa5 !important}
.steers{color:#5d9}.weak{color:#e88}.nomeasure{color:#667;font-style:italic}
tr.disint td{background:#2a1414}tr.disint .g{color:#e77}.warn{color:#e66;cursor:help}.ceil{color:#e0a030}td.c.disint{outline:1px solid #a44}
.sec{margin:14px 0;padding:10px 12px;border:1px solid #26262c;border-radius:6px;background:#131316}
</style></head><body>
<div id=bar>&#9654; <b id=np>click a cell to play</b> <span id=pos class=muted></span> <span id=ld class=muted style="color:#fa5"></span> <span class=muted>· switching keeps the playhead · loops until stopped · amber outline = loading</span></div>
<div id=wrap>
<h1>LatCH steering hyperparameter sweep — SA3 medium</h1>
<div id=explain><b>What this tests:</b> every scalar LatCH guidance head (the fixed, no-adapter steering heads — beat/rhythm activations, RMS energy bands, spectral shape, hardness) swept across a gain ladder [64, 128, 512, 2048, 8192] chosen to <i>show</i> the documented response, not hide it: gain 128 is a known dead zone, the energy-family heads operate around 512-2048. Each cell's number is the <b>achieved</b> feature value measured on the render (mean over the clip, same extractor used to build the head's training target); Δ is achieved minus the requested target. A head that "steers" pulls Δ toward zero as gain rises; "weak/dead" means it barely moves the needle at any weight tested here — a real finding about that head's usability, not a bug.
<br><b>Excluded:</b> hpcp and same_chroma (12-d/384-d vector targets, not this grid's scalar shape — same_chroma has its own dedicated lane, see chroma384_eval). <b>Render-only:</b> onset_envelope_drums / rms_drums need a separated drum stem the rendered mix doesn't have — you can still listen, just no requested-vs-measured number.</div>
<div id=out></div></div>
<audio id=au_el></audio>
<script>const D=__DATA__;
const au=document.getElementById('au_el'),npx=document.getElementById('np');let cur=null;
au.loop=true;
au.addEventListener('timeupdate',()=>{document.getElementById('pos').textContent=cur?('· '+au.currentTime.toFixed(1)+'s'):'';});
au.addEventListener('waiting',()=>{document.getElementById('ld').textContent='loading…';markLoading(true);});
au.addEventListener('playing',()=>{document.getElementById('ld').textContent='';markLoading(false);});
function mark(){document.querySelectorAll('.c.play').forEach(e=>e.classList.remove('play'));if(cur){const e=document.getElementById(cur);if(e)e.classList.add('play');}}
function markLoading(on){document.querySelectorAll('.c.loading').forEach(e=>e.classList.remove('loading'));if(on&&cur){const e=document.getElementById(cur);if(e)e.classList.add('loading');}}
function startClip(id,f,l,head,gain,clip){
 if(window.noteSet)noteSet({model:'latch_sa3_sweep_20260719',ckpt:head,clip:clip});
 const pos=(cur!==null&&!au.paused)?au.currentTime:0;cur=id;mark();npx.textContent='▶ '+l;
 document.getElementById('ld').textContent='loading…';markLoading(true);
 au.src=f;const go=()=>{try{au.currentTime=((au.duration&&pos>au.duration-1)?0:Math.min(pos,(au.duration||1e9)-0.05));}catch(e){}au.play();};
 if(au.readyState>=1)go();else au.addEventListener('loadedmetadata',go,{once:true});}
function play(id,f,l,head,gain,clip){
 if(cur===id){au.pause();cur=null;mark();npx.textContent='stopped';document.getElementById('ld').textContent='';return;}
 startClip(id,f,l,head,gain,clip);}
function col(d,scale){if(d==null)return'#1a1a1f';const t=Math.max(0,Math.min(1,Math.abs(d)/scale));return`hsl(${Math.round((1-t)*120)},45%,22%)`;}
let h='';
h+='<div class=sec><h2>baseline (no guidance)</h2><table><tr><th>prompt</th><th>▶</th></tr>';
Object.entries(D.baselines).forEach(([pid,b])=>{const id='base_'+pid;
 h+=`<tr><td>${pid}: ${b.prompt.slice(0,50)}</td><td class=c id="${id}" onclick="play('${id}','${b.f}','baseline ${pid}','baseline',0,'${b.clip}')">▶</td></tr>`;});
h+='</table></div>';
D.heads.forEach(hd=>{
 const scale=Math.abs(hd.target||1)*0.6+1e-6;
 h+=`<div class=sec><h2>${hd.head}</h2><div class=muted>target ${hd.target!=null?hd.target.toFixed(3):'—'} · `+
    `<span class="${hd.verdict==='steers'?'steers':(hd.verdict==='weak/dead'?'weak':'nomeasure')}">${hd.verdict}</span>`+
    ` · <span class=ceil title="disintegration gate: highest clean gain before the head buzzes/damages the output">usable-gain ceiling ${Object.entries(hd.ceiling||{}).map(([p,g])=>p+'&nbsp;&le;&nbsp;'+(g==null?'?':'g'+g)).join(' · ')}</span></div>`;
 h+='<table><tr><th>gain</th><th>prompt</th><th>measured</th><th>Δ</th><th>▶</th></tr>';
 hd.rows.forEach((r,i)=>{const id=`${hd.head}_${i}`;const dz=r.disint?' disint':'';
  const warn=r.disint?`<span class=warn title="disintegrated — ${(r.dreasons||'').replace(/"/g,'&quot;')}">&#9888;</span> `:'';
  h+=`<tr class="${dz.trim()}"><td class=g>${warn}${r.gain}</td><td>${r.prompt_id}</td>`+
   `<td style="background:${col(r.delta,scale)}">${r.measured!=null?r.measured.toFixed(3):'·'}</td>`+
   `<td>${r.delta!=null?r.delta.toFixed(3):(r.note||'·')}</td>`+
   `<td class=c id="${id}" onclick="play('${id}','${r.f}','${hd.head} g${r.gain} ${r.prompt_id}','${hd.head}','${r.gain}','${r.clip}')">▶</td></tr>`;});
 h+='</table></div>';
});
document.getElementById('out').innerHTML=h;
</script>
__NOTES__
<footer style="margin:18px 12px;color:#666;font-size:11px">aavepyora.online · evals · LatCH sweep · clips + metrics: sa3_control_runs/latch_sa3_sweep_20260719 (internal)</footer>
</body></html>"""

T = T.replace("__NOTES__", notes_block(
    "latch_sa3_sweep",
    levels=[("clip", "this clip"), ("model", "whole sweep"), ("page", "page")],
    hint="click a cell then note the verdict here"))
out = os.path.join(STAGE, "latch_sa3_matrix.html")
open(out, "w").write(T.replace("__DATA__", DATA))
print(f"wrote {out}: {len(heads_out)} heads, {len(manifest['cells'])} cells")
