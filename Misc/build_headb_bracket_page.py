#!/usr/bin/env python3
"""build_headb_bracket_page.py -- Head B (melody-conditioning FiLM adapter) BRACKET
eval page (Kim direct 2026-07-28: "these should have an eval page", re: the
headb_bracket sweep synced down from LUMI).

Source: CONTINUITY's design (control/sa3_control/headb_bracket_eval.sh, spec
docs/superpowers/specs/2026-07-22-melodic-latch-film.md SS2/SS8), GHOST-NOTE ran the
first analyze pass (renders had already landed from a LUMI job). CONTINUITY then
re-analyzed with a CFG-ROBUST metric (2026-07-29, findings.json): the original
null-floor comparison was inconclusive at high cfg because rest-conditioned null
clips stop producing any lead there. Her metric is OWN-vs-WRONG-contour confusion
(conditioned clip's adoption of its OWN requested motif minus its mean adoption of
the 3 OTHER motifs) -- stays meaningful across the whole cfg range. Verdict: steers
at cfg16 only, modestly, strengthening with training; cfg1 inert, cfg7 weak; gates
4/4 clean on all 48 cells (real adoption, not disintegration-buzz). This build reads
her bracket_summary.tsv + findings.json as the source of truth for the verdict/conf
columns (my earlier adopt_moving/null_floor per-clip numbers stay as supplementary
per-clip detail, not the headline).

Grid: 8 checkpoints (step5940..step9900, final) x cfg{1,7,16} x gain{1.0,1.5} = 48
cells, each with 4 motif-conditioned renders (pedal4/descrun/oct_osc/m3_osc) + 4
seed-matched null (all-rest) controls.

Run: python3 Misc/build_headb_bracket_page.py -> ~/evals_aac/headb_bracket.html
"""
import csv
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

UNAUDITED_MARK = ('<span class="unaudited" title="unaudited -- no kim_feedback in the '
                   'manifest yet">&#10071;</span>')


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


findings = json.loads(open(os.path.join(ROOT, "findings.json")).read())
summary_by_key = {}
with open(os.path.join(ROOT, "bracket_summary.tsv")) as f:
    for row in csv.DictReader(f, delimiter="\t"):
        key = (row["ckpt"], int(float(row["cfg"])), float(row["gain"]))
        summary_by_key[key] = {"adopt_act": num(row.get("adopt_act")),
                               "wrong_act": num(row.get("wrong_act")),
                               "conf": num(row.get("conf")),
                               "z0_cos": num(row.get("z0_cos")),
                               "lead_cov": num(row.get("lead_cov")),
                               "gates_clean": row.get("gates_clean"),
                               "null_floor": num(row.get("null_floor")),
                               "margin": num(row.get("margin"))}


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
            conf_row = summary_by_key.get((ck, c, g), {})
            cells.append({"ckpt": ck, "cfg": c, "gain": g, "clips": clips_out,
                          "adopt_mv": adopt_mv, "null_mv": null_mv, "gclean": gclean,
                          "n_cond": len(cond), "n_analyzed": len(by_clip), **conf_row})

with ThreadPoolExecutor(max_workers=8) as ex:
    list(ex.map(lambda j: enc(*j), jobs))
print(f"encoded {len(jobs)} clips, {len(cells)} cells")

analyzed = sum(1 for c in cells if c["n_analyzed"] > 0)
print(f"{analyzed}/{len(cells)} cells have adoption/gate analysis so far")

DATA = json.dumps({"cells": cells, "ckpts": CKPTS, "cfgs": CFGS, "gains": GAINS,
                    "motifs": MOTIFS, "findings": findings})

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
#verdict{background:#0c1c14;border:1px solid #274;border-left:3px solid #4a6;padding:10px 12px;font-size:13px;color:#cfe;margin:10px 0}#verdict b{color:#6d9}
.unaudited{color:#e77;cursor:help;margin-left:6px}
.cfg1{color:#e88}.cfg7{color:#eb5}.cfg16{color:#5d9}
</style></head><body>
<div id=bar>&#9654; <b id=np>click a cell to play</b> <span id=pos class=muted></span> <span id=ld class=muted style="color:#fa5"></span> <span class=muted>&middot; switching keeps the playhead &middot; loops until stopped</span></div>
<div id=wrap>
<h1>Head B melody-conditioning bracket -- SA3 medium <span id=auditmark></span></h1>
<div id=verdict></div>
<div id=explain><b>What this tests:</b> a FiLM adapter (control_mode=melody_contour) that takes a per-frame melodic skeleton -- 4 motifs from the corpus's own vocabulary (pedal repeats, a descending run, an octave oscillation, a minor-3rd oscillation) -- and asks the model to render it in-style, instead of hoping the model invents a hook on its own. This is the direct answer to "goa leads rarely repeat a memorable phrase": <b>hand it the hook</b>.
<br><b>Why cfg16:</b> classifier-free guidance pulls generation toward the model's strong learned style prior; at low cfg that pull is weak, so you might expect the melody condition to come through MORE easily at cfg1, not less. The opposite happened here -- at cfg1 the conditioning barely enters the latent at all (z0_cos to the unconditioned clip &asymp;0.99, i.e. almost no change), and only at cfg16 does the conditioning signal actually compete with the style prior enough to move the output. Read that as: this adapter needs strong guidance to engage, not weak guidance to avoid being overridden.
<br><b>How to read "conf":</b> for each conditioned clip, muscriptor-transcribe the render and score how well its contour matches its OWN requested motif vs the OTHER 3 motifs it wasn't asked for. <b>conf = own-motif adoption &minus; mean of the other three</b> -- positive means the render moved toward what it was actually told to play, not just toward "some contour." (The board's original metric -- adoption vs a null/no-condition floor -- looked inconclusive at high cfg because null clips stop producing any lead there at all, which isn't a fair floor; conf stays meaningful across the full cfg range.) <b>gate</b> = the disintegration-gate check (does the conditioned render diverge from its seed-matched null in ways that look like noise/buzz rather than real melodic change) -- clean everywhere in this bracket, so the cfg16 adoption is real conditioning, not the adapter faking a metric win.
<br><b>Checkpoints:</b> step5940 through step9900 are training-progress snapshots (~9-15 effective epochs); "final" is the last saved step. Only steps past 5280 are in this bracket -- CONTINUITY's design skips the early-training region where the pilot showed nothing had adopted yet.</div>
<div id=repro>reproduce: render -- <code>control/sa3_control/melody_pilot_eval.py render</code> (spec: docs/superpowers/specs/2026-07-22-melodic-latch-film.md &sect;2); analyze (confusion metric) -- CONTINUITY's bracket_summary/findings pass, LUMI render job 20336044; bracket driver -- <code>control/sa3_control/headb_bracket_eval.sh</code>. Prompt: "psychedelic goa trance, hypnotic melodic acid lead line, driving rolling bassline, 143 BPM" &middot; T=512 (47.554s) &middot; steps=24 &middot; seeds 1111/2222/3333/4444 &middot; checkpoints: LUMI run <code>headb_melody</code> (internal).</div>
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
function confClass(conf){if(conf==null)return'';return conf>0.1?'steers':(conf<-0.05?'weak':'');}
// audit mark + verdict block, from CONTINUITY's findings.json
document.getElementById('auditmark').innerHTML = D.findings.kim_feedback ? '' :
 '<span class="unaudited" title="unaudited -- no kim_feedback in the manifest yet">&#10071;</span>';
document.getElementById('verdict').innerHTML =
 `<b>Verdict (${D.findings.by}, ${D.findings.date}):</b> ${D.findings.result}`;
let h='';
// master summary -- CONTINUITY's cfg-robust confusion metric is the headline column
h+='<div class=sec><h2>master table (per-cell, never pooled)</h2><div class=muted>conf = own-motif adoption &minus; mean of the 3 wrong motifs (cfg-robust; see explainer). gate = disintegration check vs seed-matched null.</div><table><tr><th>checkpoint</th><th>cfg</th><th>gain</th><th>conf</th><th>own adopt</th><th>wrong adopt</th><th>z0 cos</th><th>gate</th></tr>';
D.cells.forEach(c=>{
 const cc=confClass(c.conf);
 h+=`<tr><td>${c.ckpt}</td><td class="cfg${c.cfg}">${c.cfg}</td><td>${c.gain}</td>`+
    `<td class="${cc}">${c.conf!=null?c.conf.toFixed(3):'<span class=pending>pending</span>'}</td>`+
    `<td>${c.adopt_act!=null?c.adopt_act.toFixed(3):'-'}</td>`+
    `<td>${c.wrong_act!=null?c.wrong_act.toFixed(3):'-'}</td>`+
    `<td>${c.z0_cos!=null?c.z0_cos.toFixed(3):'-'}</td>`+
    `<td>${c.gates_clean||'-'}</td></tr>`;});
h+='</table></div>';
document.getElementById('summary').innerHTML=h;
h='';
D.ckpts.forEach(ck=>{
 const ckCells=D.cells.filter(c=>c.ckpt===ck);
 if(!ckCells.length)return;
 h+=`<div class=sec><h2>${ck}</h2>`;
 ckCells.forEach(c=>{
  const cc=confClass(c.conf);
  h+=`<div style="margin:8px 0"><b class="cfg${c.cfg}">cfg${c.cfg} g${c.gain}</b> <span class=muted>conf <span class="${cc}">${c.conf!=null?c.conf.toFixed(3):'?'}</span> (own ${c.adopt_act!=null?c.adopt_act.toFixed(3):'?'} vs wrong ${c.wrong_act!=null?c.wrong_act.toFixed(3):'?'}) &middot; z0_cos ${c.z0_cos!=null?c.z0_cos.toFixed(3):'?'} &middot; gate ${c.gates_clean||'?'}</span><br>`;
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
