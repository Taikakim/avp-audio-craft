#!/usr/bin/env python3
"""build_headb_bracket_page.py -- Head B (melody-conditioning FiLM adapter) BRACKET
eval page (Kim direct 2026-07-28: "these should have an eval page", re: the
headb_bracket sweep synced down from LUMI).

Source: CONTINUITY's design (control/sa3_control/headb_bracket_eval.sh, spec
docs/superpowers/specs/2026-07-22-melodic-latch-film.md SS2/SS8), GHOST-NOTE ran the
analyze phase (renders had already landed from a LUMI job -- see
Misc/headb_analyze.log-style chain) against the actual LUMI-pull location.

Grid: 8 checkpoints (step5940..step9900, final) x cfg{1,7,16} x gain{1.0,1.5} = 48
cells, each with 4 motif-conditioned renders (pedal4/descrun/oct_osc/m3_osc) + 4
seed-matched null (all-rest) controls. Master table reuses headb_bracket_eval.sh's
own per-cell aggregation (adopt_moving vs null-floor vs gate-clean fraction, NEVER
pooled across cells -- board-rep rule).

Run: python3 Misc/build_headb_bracket_page.py -> ~/evals_aac/headb_bracket.html
"""
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comment_notes_block import notes_block  # noqa: E402

ROOT = "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/renders/headb_bracket"
STAGE = os.path.join(os.path.expanduser("~"), "evals_aac")
CLIPS = os.path.join(STAGE, "headb_bracket")
os.makedirs(CLIPS, exist_ok=True)

CKPTS = ["riffer_step5940", "riffer_step6600", "riffer_step7260", "riffer_step7920",
         "riffer_step8580", "riffer_step9240", "riffer_step9900", "riffer_final"]
CFGS = [1, 7, 16]
GAINS = [1.0, 1.5]
MOTIFS = {"pedal4": "pedal (same note 16ths)", "descrun": "descending run",
          "oct_osc": "octave oscillation", "m3_osc": "minor-3rd oscillation"}


def enc(src, dst):
    if not os.path.exists(dst):
        subprocess.run(["ffmpeg", "-y", "-i", src, "-c:a", "aac", "-b:a", "192k", dst],
                        capture_output=True)


jobs = []
cells = []
for ck in CKPTS:
    for c in CFGS:
        for g in GAINS:
            cell_dir = os.path.join(ROOT, f"{ck}_cfg{c}_g{g}")
            renders = os.path.join(cell_dir, "renders")
            if not os.path.isdir(renders):
                continue
            results_path = os.path.join(cell_dir, "results.json")
            results = json.loads(open(results_path).read()) if os.path.exists(results_path) else []
            by_clip = {r["clip"]: r for r in results}
            clips_out = []
            for fn in sorted(os.listdir(renders)):
                if not fn.endswith(".wav"):
                    continue
                stem = fn[:-4]
                src = os.path.join(renders, fn)
                dst_rel = f"headb_bracket/{ck}_cfg{c}_g{g}__{stem}.m4a"
                dst = os.path.join(STAGE, dst_rel)
                jobs.append((src, dst))
                r = by_clip.get(stem, {})
                clips_out.append({"stem": stem, "f": dst_rel, **r})
            # per-cell aggregate: conditioned adopt_moving vs the null floor, gate-clean frac
            cond = [r for r in clips_out if r.get("cell") and r.get("conditioned")]
            null = [r for r in clips_out if r.get("conditioned") is False]

            def mean(xs):
                xs = [x for x in xs if isinstance(x, (int, float))]
                return round(sum(xs) / len(xs), 3) if xs else None

            adopt_mv = mean([r.get("adopt_moving") for r in cond])
            null_mv = mean([r.get(f"null_{t}_moving") for r in null for t in MOTIFS])
            gclean = (round(sum(1 for r in cond if r.get("gate") == "clean") / len(cond), 2)
                      if cond else None)
            cells.append({"ckpt": ck, "cfg": c, "gain": g, "clips": clips_out,
                          "adopt_mv": adopt_mv, "null_mv": null_mv, "gclean": gclean,
                          "n_cond": len(cond), "n_analyzed": len(by_clip)})

with ThreadPoolExecutor(max_workers=8) as ex:
    list(ex.map(lambda j: enc(*j), jobs))
print(f"encoded {len(jobs)} clips, {len(cells)} cells")

analyzed = sum(1 for c in cells if c["n_analyzed"] > 0)
print(f"{analyzed}/{len(cells)} cells have adoption/gate analysis so far")

DATA = json.dumps({"cells": cells, "ckpts": CKPTS, "cfgs": CFGS, "gains": GAINS,
                    "motifs": MOTIFS})

T = r"""<!doctype html><html><head><meta charset=utf-8><title>Head B melody-conditioning bracket -- SA3 medium</title><style>
body{font:13px system-ui;margin:0;background:#0e0e10;color:#e0e0e0;max-width:1280px}
#bar{position:sticky;top:0;background:#16181c;padding:7px 12px;border-bottom:1px solid #2a2a30;z-index:9}
#wrap{padding:14px}h1{font-size:18px}h2{font-size:15px;color:#9cf;margin:20px 0 3px}.muted{color:#888}
#explain{background:#1a140c;border:1px solid #433;border-left:3px solid #d90;padding:10px 12px;font-size:12.5px;color:#dcd;margin:10px 0}#explain b{color:#fc6}
#repro{background:#101418;border:1px solid #234;border-left:3px solid #38a;padding:8px 12px;font-size:11.5px;color:#9bd;margin:10px 0}#repro code{color:#bdf;background:#152030;padding:1px 4px;border-radius:3px}
table{border-collapse:collapse;font-size:12px;margin:4px 0}td,th{border:1px solid #2a2a30;padding:4px 7px;text-align:center}
th{background:#1c1c22;color:#aaa}td:first-child,th:first-child{text-align:left;color:#9ab}
.c{cursor:pointer;font-variant-numeric:tabular-nums}.c:hover{outline:2px solid #7cf}.play{outline:2px solid #5d5 !important}.loading{outline:2px solid #fa5 !important}
.sec{margin:14px 0;padding:10px 12px;border:1px solid #26262c;border-radius:6px;background:#131316}
.steers{color:#5d9}.weak{color:#e88}.pending{color:#667;font-style:italic}
.mot{font-size:10.5px;color:#899}
</style></head><body>
<div id=bar>&#9654; <b id=np>click a cell to play</b> <span id=pos class=muted></span> <span id=ld class=muted style="color:#fa5"></span> <span class=muted>&middot; switching keeps the playhead &middot; loops until stopped</span></div>
<div id=wrap>
<h1>Head B melody-conditioning bracket -- SA3 medium</h1>
<div id=explain><b>What this tests:</b> a FiLM adapter (control_mode=melody_contour) that takes a per-frame melodic skeleton -- 4 motifs from the corpus's own vocabulary (pedal repeats, a descending run, an octave oscillation, a minor-3rd oscillation) -- and asks the model to render it in-style, instead of hoping the model invents a hook on its own. This is the direct answer to "goa leads rarely repeat a memorable phrase": <b>hand it the hook</b>.
<br><b>How to read a cell:</b> each (checkpoint step &times; cfg &times; guidance-gain) combination renders the 4 conditioned motifs plus 4 seed-matched <i>null</i> clips (no melody stream, same seed/prompt) -- the null clips set the empirical chance floor for how much of any random contour a muscriptor transcription "sees" by accident. <b>adopt (moving)</b> = fraction of non-pedal frames where the transcribed output actually matches the requested motif, averaged over the 4 conditioned clips; <b>null floor</b> = the same match rate for the null clips against all 4 motifs (chance level). Conditioning "took" when adopt clearly clears the null floor <i>and</i> the disintegration gate stays clean (the adapter didn't fake the contour as a noise artifact instead of a real melodic change -- see the MASTER SS4 disintegration-gate note). cfg1 is a melody-dominant anchor (little classifier-free pull away from the condition); cfg16 tests whether the motif survives the model's usual strong style guidance.
<br><b>Checkpoints:</b> step5940 through step9900 are training-progress snapshots (~9-15 effective epochs); "final" is the last saved step. Only steps past 5280 are in this bracket -- CONTINUITY's design skips the early-training region where the pilot showed nothing had adopted yet.</div>
<div id=repro>reproduce: render -- <code>control/sa3_control/melody_pilot_eval.py render</code> (spec: docs/superpowers/specs/2026-07-22-melodic-latch-film.md &sect;2); analyze -- <code>control/sa3_control/melody_pilot_eval.py analyze</code> + <code>eval/hook_eval_renders.py</code> (muscriptor transcription); bracket driver -- <code>control/sa3_control/headb_bracket_eval.sh</code>. Prompt: "psychedelic goa trance, hypnotic melodic acid lead line, driving rolling bassline, 143 BPM" &middot; T=512 (47.554s) &middot; steps=24 &middot; seeds 1111/2222/3333/4444 &middot; checkpoints: LUMI run <code>headb_melody</code> (internal).</div>
<div id=summary></div>
<div id=out></div></div>
<audio id=au_el></audio>
<script>const D=__DATA__;
const au=document.getElementById('au_el'),npx=document.getElementById('np');let cur=null;
au.loop=true;
au.addEventListener('timeupdate',()=>{document.getElementById('pos').textContent=cur?('&middot; '+au.currentTime.toFixed(1)+'s'):'';});
au.addEventListener('waiting',()=>{document.getElementById('ld').textContent='loading...';markLoading(true);});
au.addEventListener('playing',()=>{document.getElementById('ld').textContent='';markLoading(false);});
function mark(){document.querySelectorAll('.c.play').forEach(e=>e.classList.remove('play'));if(cur){const e=document.getElementById(cur);if(e)e.classList.add('play');}}
function markLoading(on){document.querySelectorAll('.c.loading').forEach(e=>e.classList.remove('loading'));if(on&&cur){const e=document.getElementById(cur);if(e)e.classList.add('loading');}}
function startClip(id,f,l,ckpt,clip){
 if(window.noteSet)noteSet({model:'headb_bracket',ckpt:ckpt,clip:clip});
 const pos=(cur!==null&&!au.paused)?au.currentTime:0;cur=id;mark();npx.textContent='▶ '+l;
 document.getElementById('ld').textContent='loading...';markLoading(true);
 au.src=f;const go=()=>{try{au.currentTime=((au.duration&&pos>au.duration-1)?0:Math.min(pos,(au.duration||1e9)-0.05));}catch(e){}au.play();};
 if(au.readyState>=1)go();else au.addEventListener('loadedmetadata',go,{once:true});}
function play(id,f,l,ckpt,clip){
 if(cur===id){au.pause();cur=null;mark();npx.textContent='stopped';document.getElementById('ld').textContent='';return;}
 startClip(id,f,l,ckpt,clip);}
function verdict(a,n){if(a==null)return'<span class=pending>pending</span>';if(n==null)return a.toFixed(3);
 return a>n*1.5+0.03?`<span class=steers>${a.toFixed(3)}</span>`:`<span class=weak>${a.toFixed(3)}</span>`;}
let h='';
// master summary
h+='<div class=sec><h2>master table (per-cell, never pooled)</h2><table><tr><th>checkpoint</th><th>cfg</th><th>gain</th><th>adopt (moving)</th><th>null floor</th><th>gate clean</th></tr>';
D.cells.forEach(c=>{
 h+=`<tr><td>${c.ckpt}</td><td>${c.cfg}</td><td>${c.gain}</td><td>${verdict(c.adopt_mv,c.null_mv)}</td><td>${c.null_mv!=null?c.null_mv.toFixed(3):'<span class=pending>pending</span>'}</td><td>${c.gclean!=null?(c.gclean*100).toFixed(0)+'%':'<span class=pending>pending</span>'}</td></tr>`;});
h+='</table></div>';
document.getElementById('summary').innerHTML=h;
h='';
D.ckpts.forEach(ck=>{
 const ckCells=D.cells.filter(c=>c.ckpt===ck);
 if(!ckCells.length)return;
 h+=`<div class=sec><h2>${ck}</h2>`;
 ckCells.forEach(c=>{
  h+=`<div style="margin:8px 0"><b>cfg${c.cfg} g${c.gain}</b> <span class=muted>adopt ${verdict(c.adopt_mv,c.null_mv)} vs null ${c.null_mv!=null?c.null_mv.toFixed(3):'?'} &middot; gate-clean ${c.gclean!=null?(c.gclean*100).toFixed(0)+'%':'?'}</span><br>`;
  c.clips.forEach(cl=>{
   const id=`${ck}_${c.cfg}_${c.gain}_${cl.stem}`;
   const lab=cl.conditioned?`cond ${D.motifs[cl.cell]||cl.cell}`:'null';
   const seed=cl.stem.split('__s')[1]||'';
   const metric=cl.conditioned?(cl.adopt_moving!=null?` adopt=${cl.adopt_moving}`:''):'';
   const gt=cl.gate?` [${cl.gate}]`:'';
   h+=`<span class="c mot" id="${id}" onclick="play('${id}','${cl.f}','${ck} cfg${c.cfg} g${c.gain} ${lab} s${seed}','${ck}','${cl.stem}')" style="margin-right:8px">&#9654; ${lab} s${seed}${metric}${gt}</span>`;});
  h+='</div>';});
 h+='</div>';});
document.getElementById('out').innerHTML=h;
</script>
__NOTES__
<footer style="margin:18px 12px;color:#666;font-size:11px">aavepyora.online &middot; evals &middot; Head B melody-conditioning bracket &middot; clips + metrics: headb_bracket run (internal)</footer>
</body></html>"""

T = T.replace("__NOTES__", notes_block(
    "headb_bracket",
    levels=[("clip", "this clip"), ("ckpt", "this checkpoint"), ("page", "whole page")],
    hint="click a cell then note the verdict here"))
out = os.path.join(STAGE, "headb_bracket.html")
open(out, "w").write(T.replace("__DATA__", DATA))
print(f"wrote {out}: {len(cells)} cells, {len(jobs)} clips")
