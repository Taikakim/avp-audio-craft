#!/usr/bin/env python3
# Owner: GHOST-NOTE (created 2026-10-14)
# Last edited: WINTERMUTE 2026-10-14 — drop run_meta related.heads (drive path) from the page data; floating transport bar
"""build_latch_phaseE_page.py -- listening/evaluation page for the Phase E LatCH density heads (E5 bracket), built from eval/latch_phaseE_render.py's clips.

Kim 2026-10-14: "prepare an evaluation page for the recent models with the clips generated". Follows the three-audience standard (eval-tables spec s14):
  1. a TOOL: same-playhead audio cells (switching keeps the position, re-click stops), baseline row per prompt, steered cells grouped arm x target x gain;
  2. a RESOURCE for engineers: every arm's training flags + val losses, the render recipe, script names, the metrics each cell carries;
  3. a LEARNING block: what the head is, what 'steering to +2 sigma' means, how to read the cells, and what the numbers can NOT tell you.
Per-cell numbers are DSP screens against the same-seed baseline (eval/latch_drift_check.py, results in phaseE_drift.json), NOT the disintegration gate (that reads
clip_metrics.db, which these clips are not in). A cell whose loudness fell >3 dB gets a warning mark meaning 'listen for collapse'. Every arm carries the red
unaudited mark until a kim_feedback exists (MASTER MANIFEST v2). No checkpoint filenames or drive paths are written into the page (public-page redaction seam).
Run: python3 Misc/build_latch_phaseE_page.py   -> ~/evals_aac/latch_phaseE.html (+ ~/evals_aac/latch_phaseE/*.m4a)
"""
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comment_notes_block import notes_block
from float_player import inject

BR = "/run/media/kim/Mantu/latch_sweep/modular_2026-09-30"
CLIPS = f"{BR}/phaseE_eval_clips"
STAGE = os.path.join(os.path.expanduser("~"), "evals_aac")
OUTDIR = os.path.join(STAGE, "latch_phaseE")
DRIFT = os.environ.get("PHASEE_DRIFT", "/tmp/battery/phaseE_drift.json")
if not os.path.exists(DRIFT):
    DRIFT = f"/run/media/kim/Mantu/latch_sweep/modular_2026-09-30/head_checks_2026-10-14/phaseE_drift.json"
os.makedirs(OUTDIR, exist_ok=True)

man = json.load(open(f"{CLIPS}/manifest.json"))["cells"]
meta = json.load(open(f"{CLIPS}/run_meta.json"))
# the sidecar's related.heads is an absolute drive path; it must not reach the public page
meta.get("related", {}).pop("heads", None)
drift = {r["id"]: r for r in json.load(open(DRIFT))["rows"]}
summ = {l.split("\t")[0]: l.split("\t") for l in open(f"{BR}/phaseE/SUMMARY.tsv").read().splitlines() if l.strip()}


def arm_flags(line):
    d = {}
    for k, pat in (("dim", r"--dim (\d+)"), ("depth", r"--depth (\d+)"), ("batch", r"--batch-size (\d+)"), ("lr", r"--lr ([\d.e+-]+)"), ("seed", r"--seed (\d+)"),
                   ("epochs", r"--epochs (\d+)"), ("warmup", r"--mod-warmup (\d+)")):
        m = re.search(pat, line)
        d[k] = m.group(1) if m else None
    d["dim"] = d["dim"] or "256 (default)"
    d["depth"] = d["depth"] or "4 (default)"
    return d


arms = {}
for l in open(f"{BR}/phaseE_arms.txt"):
    if l.strip() and not l.startswith("#"):
        name = l.split()[0]
        s = summ.get(name, [name, "", "", "", ""])
        arms[name] = {"name": name, **arm_flags(l), "wall_s": s[1], "best_val": s[2], "last_val": s[3], "rc": s[4] if len(s) > 4 else ""}

cells = []
for c in man:
    src = f"{CLIPS}/{c['clip'][:-4]}.m4a"
    dst = f"{OUTDIR}/{c['clip'][:-4]}.m4a"
    if os.path.exists(src) and not os.path.exists(dst):
        shutil.copy(src, dst)
    row = {k: c.get(k) for k in ("clip", "arm", "k", "gain", "prompt_id", "target", "val_loss", "epoch")}
    row["f"] = f"latch_phaseE/{c['clip'][:-4]}.m4a"
    d = drift.get(c["clip"][:-4])
    if d:
        row["d_onset"] = round(d["delta"]["onset_rate"], 2)
        row["d_hat"] = round(d["delta"]["hat_rate"], 2)
        row["d_bpm"] = round(d["delta"]["bpm"], 2)
        row["d_rms"] = round(d["delta"]["rms_db"], 2)
        row["rhythm"] = round(d["sims"]["rhythm_sim"], 2)
        row["onset"] = round(d["steered"]["onset_rate"], 2)
        row["warn"] = d["delta"]["rms_db"] < -3.0
    cells.append(row)
prompts = {c["prompt_id"]: c["prompt"] for c in man if c["arm"] == "baseline"}
DATA = json.dumps({"cells": cells, "arms": list(arms.values()), "prompts": prompts, "meta": meta})

T = r"""<!doctype html><html><head><meta charset=utf-8><title>LatCH Phase E density heads</title><style>
body{font:13px system-ui;margin:0;background:#0e0e10;color:#e0e0e0;max-width:1250px}
#bar{position:sticky;top:0;background:#16181c;padding:7px 12px;border-bottom:1px solid #2a2a30;z-index:9}
#wrap{padding:14px}h1{font-size:18px}h2{font-size:15px;color:#9cf;margin:22px 0 4px}h3{font-size:13px;color:#bcd;margin:12px 0 2px}.muted{color:#888}
.explain{background:#1a140c;border:1px solid #433;border-left:3px solid #d90;padding:10px 12px;font-size:12.5px;color:#dcd;margin:10px 0}.explain b{color:#fc6}
.res{background:#10161c;border:1px solid #234;border-left:3px solid #48c;padding:10px 12px;font-size:12px;color:#cde;margin:10px 0}
table{border-collapse:collapse;font-size:12px;margin:4px 0}td,th{border:1px solid #2a2a30;padding:4px 8px;text-align:center}
th{background:#1c1c22;color:#aaa}td:first-child,th:first-child{text-align:left;color:#9ab}
.c{cursor:pointer;font-variant-numeric:tabular-nums}.c:hover{outline:2px solid #7cf}.play{outline:2px solid #5d5 !important}.loading{outline:2px solid #fa5 !important}
.num{font-size:10.5px;color:#9a9;display:block}.warn{color:#e66;cursor:help}.un{color:#e44;font-weight:bold;cursor:help}
td.warncell{background:#2a1414}.sec{margin:14px 0;padding:10px 12px;border:1px solid #26262c;border-radius:6px;background:#131316}
</style></head><body>
<div id=bar>&#9654; <b id=np>click a cell to play</b> <span id=pos class=muted></span> <span id=ld class=muted style="color:#fa5"></span> <span class=muted>· switching keeps the playhead · loops until stopped</span></div>
<div id=wrap>
<h1>LatCH Phase E &mdash; density heads, listening page</h1>
<div class=explain><b>What this tests:</b> six small steering heads, all trained to read <i>onsets per beat</i> from the SA3 latent (the density of the rhythm, tempo-normalised), differing in width, depth, batch size or learning rate. Each one is used at generation time as a gradient guide: the sampler is nudged, step by step, until the head reads the target density. <b>Why:</b> the training loss (held-out regression error) of these six differs by less than the project's 0.004 noise rule, apart from depth&nbsp;8, so it cannot say which head <i>steers</i> better. <b>How to read a cell:</b> every steered clip uses the same prompt and seed as the unsteered baseline of its column block, so the only difference is the head. The target is the head's own training mean plus k standard deviations (k&nbsp;=&nbsp;&minus;1 sparser, +1 denser, +2 much denser). The small numbers under each &#9654; are screens against that baseline (full-band onsets per second, hi-hat-band onsets per second, kick-band rhythm similarity, loudness change), not quality scores. <b>What it cannot tell you:</b> whether the clip sounds <i>better</i>. That is the listening. The two gains (512, 2048) are a guess for this head: no density gain ladder existed.</div>
<div class=res><b>Resource.</b> Training: <code>latch/run_modular_bracket.sh</code> on <code>phaseE_arms.txt</code>, modular optimizer (Shampoo whitening, lr&nbsp;1e-2 unless stated, 500 warmup steps, radial brake 0.8, escape velocity), 20 epochs, goa bigset (12,524 crops, track-grouped 5% validation). Rendering: <code>eval/latch_phaseE_render.py</code> (medium-base, 24 steps, cfg 7, 47.56&nbsp;s, T=512). Screens: <code>eval/latch_drift_check.py</code> (the tempo estimate reads the kick band; rhythm similarity is confounded when a head changes the bass, so read it with the loudness). Reading rule from the bracket: compare within 20 epochs, and a validation difference below 0.004 is noise. Findings go in <code>EXPERIMENTS.md</code> E5; the next step, retraining the best setup with the new controls, is registered there as proposed.</div>
<h2>The six arms</h2><div id=arms></div>
<div id=out></div></div>
<audio id=au_el></audio>
<script>const D=__DATA__;
const au=document.getElementById('au_el'),npx=document.getElementById('np');let cur=null;au.loop=true;
au.addEventListener('timeupdate',()=>{document.getElementById('pos').textContent=cur?('· '+au.currentTime.toFixed(1)+'s'):'';});
au.addEventListener('waiting',()=>{document.getElementById('ld').textContent='loading…';markLoading(true);});
au.addEventListener('playing',()=>{document.getElementById('ld').textContent='';markLoading(false);});
function mark(){document.querySelectorAll('.c.play').forEach(e=>e.classList.remove('play'));if(cur){const e=document.getElementById(cur);if(e)e.classList.add('play');}}
function markLoading(on){document.querySelectorAll('.c.loading').forEach(e=>e.classList.remove('loading'));if(on&&cur){const e=document.getElementById(cur);if(e)e.classList.add('loading');}}
function startClip(id,f,l,arm,clip){
 if(window.noteSet)noteSet({model:'latch_phaseE',ckpt:arm,clip:clip});
 const pos=(cur!==null&&!au.paused)?au.currentTime:0;cur=id;mark();npx.textContent='▶ '+l;
 document.getElementById('ld').textContent='loading…';markLoading(true);
 au.src=f;const go=()=>{try{au.currentTime=((au.duration&&pos>au.duration-1)?0:Math.min(pos,(au.duration||1e9)-0.05));}catch(e){}au.play();};
 if(au.readyState>=1)go();else au.addEventListener('loadedmetadata',go,{once:true});}
function play(id,f,l,arm,clip){if(cur===id){au.pause();cur=null;mark();npx.textContent='stopped';document.getElementById('ld').textContent='';return;}startClip(id,f,l,arm,clip);}
let a='<table><tr><th></th><th>arm</th><th>dim</th><th>depth</th><th>batch</th><th>lr</th><th>seed</th><th>epochs</th><th>best val</th><th>last val</th><th>wall</th><th>exit</th></tr>';
D.arms.forEach(r=>{a+=`<tr><td><span class=un title="No listening verdict recorded yet (unaudited) — the mark clears when a kim_feedback is written to the manifest.">&#10071;</span></td><td>${r.name}</td><td>${r.dim}</td><td>${r.depth}</td><td>${r.batch||'16'}</td><td>${r.lr||'1e-2'}</td><td>${r.seed}</td><td>${r.epochs}</td><td>${r.best_val}</td><td>${r.last_val}</td><td>${r.wall_s?Math.round(r.wall_s/60)+' min':''}</td><td title="${r.rc==='rc=134'?'abort at teardown AFTER the epochs finished and the best checkpoint was saved':''}">${r.rc}</td></tr>`;});
a+='</table><div class=muted>Validation = held-out regression loss on onset_per_beat_ts (lower is better). Depth 8 is the only arm beyond the 0.004 noise rule; the E02/E03 pair (same recipe, two seeds) differ by 0.002.</div>';
document.getElementById('arms').innerHTML=a;
const fmt=(c)=>c.d_onset==null?'':`<span class=num>${c.d_onset>=0?'+':''}${c.d_onset} on/s · hat ${c.d_hat>=0?'+':''}${c.d_hat}<br>rhythm ${c.rhythm} · ${c.d_rms>=0?'+':''}${c.d_rms} dB${c.d_bpm?` · ${c.d_bpm>=0?'+':''}${c.d_bpm} bpm`:''}</span>`;
let h='';
Object.entries(D.prompts).forEach(([pid,text])=>{
 h+=`<div class=sec><h2>prompt ${pid}</h2><div class=muted>${text.slice(0,200)}${text.length>200?'…':''}</div>`;
 const base=D.cells.find(c=>c.arm==='baseline'&&c.prompt_id===pid);
 h+=`<h3>unsteered baseline</h3><table><tr><td class=c id="b_${pid}" onclick="play('b_${pid}','${base.f}','baseline ${pid}','baseline','${base.clip}')">&#9654; baseline</td></tr></table>`;
 h+='<table><tr><th>arm</th><th>target</th><th>gain 512</th><th>gain 2048</th></tr>';
 D.arms.forEach(ar=>{[-1,1,2].forEach(k=>{
  const cell=(g)=>{const c=D.cells.find(x=>x.arm===ar.name&&x.k===k&&x.gain===g&&x.prompt_id===pid);if(!c)return'<td>·</td>';
    const id=`${ar.name}_${k}_${g}_${pid}`;
    return `<td class="c ${c.warn?'warncell':''}" id="${id}" onclick="play('${id}','${c.f}','${ar.name} k${k>0?'+':''}${k} g${g} ${pid}','${ar.name}','${c.clip}')">${c.warn?'<span class=warn title="loudness fell by more than 3 dB against the baseline: listen for collapse (DSP screen, not the disintegration gate)">&#9888;</span> ':''}&#9654;${fmt(c)}</td>`;};
  h+=`<tr><td>${k===-1?ar.name:''}</td><td>${k>0?'+':''}${k}&sigma;</td>${cell(512)}${cell(2048)}</tr>`;});});
 h+='</table></div>';});
document.getElementById('out').innerHTML=h;
</script>
__NOTES__
<footer style="margin:18px 12px;color:#666;font-size:11px">evals &middot; LatCH Phase E &middot; clips and metrics: sa3_control_runs/latch_phaseE (internal)</footer>
</body></html>"""
T = T.replace("__NOTES__", notes_block("latch_phaseE", levels=[("clip", "this clip"), ("model", "this arm"), ("page", "page")], hint="click a cell, then note what you hear"))
out = os.path.join(STAGE, "latch_phaseE.html")
open(out, "w").write(inject(T.replace("__DATA__", DATA)))
print(f"wrote {out}: {len(arms)} arms, {len(cells)} cells, {len(os.listdir(OUTDIR))} audio files")
