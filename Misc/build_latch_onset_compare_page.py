#!/usr/bin/env python3
# Owner: GHOST-NOTE (created 2026-10-14)
# Last edited: WINTERMUTE 2026-10-14 — floating transport bar (float_player.inject)
"""build_latch_onset_compare_page.py -- onset_eval.html-style comparison: the FiLM control adapter (existing page data) vs the six Phase E LatCH density heads, same targets.

Kim 2026-10-14: "create a comparison with the same targets as onset_eval.html ... how do the gain and target amounts used compare to what we are now using?"
Reads sa3_control_runs/onset_eval_54000_inrange + onset_eval_54000_g11to20 (FiLM reference: requested onsets/s 2..9 at adapter strengths 0.1..2; the run pair that holds the 'strength 1.5-2 for low densities, 1 for high' pattern) and onset_eval_latchE_<arm> (eval/latch_onset_eval.py).
Shows (1) the unit/gain mapping, (2) a measured-vs-requested grid per run with same-playhead cells, (3) per run and gain: correlation, span and error vs the request,
(4) the gain that lands closest to each request ("which weight is best at which density", the finding Kim recalled for the adapter), and (5) a DSP screen per clip
(loudness fall, flatness, hf ratio vs the unguided clip) -- a SCREEN for 'cleaner', not the disintegration gate and not an ear.
Run: SAO/.venv/bin/python Misc/build_latch_onset_compare_page.py -> ~/evals_aac/latch_onset_compare.html (+ latch_onset_compare/*.m4a)
"""
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.append("/home/kim/Projects/SAO")
from comment_notes_block import notes_block
from float_player import inject

R = "/run/media/kim/Mantu/sa3_control_runs"
STAGE = os.path.join(os.path.expanduser("~"), "evals_aac")
OUTD = os.path.join(STAGE, "latch_onset_compare")
os.makedirs(OUTD, exist_ok=True)
FILM_RUNS = [("onset_eval_54000_inrange", "FiLM adapter, strength 0.1-1 (54000-step run)"), ("onset_eval_54000_g11to20", "FiLM adapter, strength 1.1-2 (54000-step run)")]
runs = FILM_RUNS + [(d, "LatCH " + d.replace("onset_eval_latchE_", "")) for d in sorted(os.listdir(R)) if d.startswith("onset_eval_latchE_")]


def enc(src, dst):
    if not os.path.exists(dst):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-c:a", "aac", "-b:a", "192k", dst])


def screen(path):
    import librosa
    y, sr = librosa.load(path, sr=22050, mono=True)
    S = np.abs(librosa.stft(y, n_fft=2048)); f = librosa.fft_frequencies(sr=sr, n_fft=2048); P = S ** 2
    return {"rms_db": float(20 * np.log10(np.sqrt((y ** 2).mean()) + 1e-9)), "flat": float(librosa.feature.spectral_flatness(S=S).mean()), "hf": float(P[f >= 6000].sum() / (P.sum() + 1e-9))}


data = []
jobs = []
for d, label in runs:
    p = f"{R}/{d}/onset_eval.json"
    if not os.path.exists(p):
        continue
    rows = json.load(open(p))
    ref = {}
    for r in rows:
        wav = f"{R}/{d}/onset_g{r['gain']:g}_d{r['requested']:g}.wav"
        m4a = f"{OUTD}/{d}__g{r['gain']:g}_d{r['requested']:g}.m4a"
        if os.path.exists(wav):
            jobs.append((wav, m4a))
            r["f"] = f"latch_onset_compare/{os.path.basename(m4a)}"
            r["wav"] = wav
    data.append({"dir": d, "label": label, "rows": rows})
with ThreadPoolExecutor(max_workers=8) as ex:
    list(ex.map(lambda j: enc(*j), jobs))
with ThreadPoolExecutor(max_workers=6) as ex:
    scr = dict(zip([j[0] for j in jobs], ex.map(lambda j: screen(j[0]), jobs)))
out = []
for run in data:
    rows = run["rows"]
    gains = sorted({r["gain"] for r in rows}); reqs = sorted({r["requested"] for r in rows})
    base = next((scr[r["wav"]] for r in rows if r["gain"] == 0 and r.get("wav") in scr), None)
    per_gain = []
    for g in gains:
        gr = sorted([r for r in rows if r["gain"] == g], key=lambda r: r["requested"])
        xs = [r["requested"] for r in gr]; ys = [r["measured"] for r in gr]
        corr = float(np.corrcoef(xs, ys)[0, 1]) if len(set(ys)) > 1 else 0.0
        per_gain.append({"gain": g, "corr": corr, "span": ys[-1] - ys[0], "mae": float(np.mean([abs(a - b) for a, b in zip(xs, ys)]))})
    best = {}
    for q in reqs:
        c = [r for r in rows if r["requested"] == q and r["gain"] != 0]
        if c:
            b = min(c, key=lambda r: abs(r["measured"] - q)); best[str(q)] = {"gain": b["gain"], "measured": b["measured"]}
    for r in rows:
        s = scr.get(r.get("wav"))
        r["flag"] = bool(s and base and r["gain"] != 0 and (s["rms_db"] < base["rms_db"] - 3 or s["flat"] > 2 * base["flat"] + 0.01 or s["hf"] > 2 * base["hf"] + 0.01))
        r["screen"] = s
        r.pop("wav", None)
    out.append({"dir": run["dir"], "label": run["label"], "gains": gains, "reqs": reqs, "rows": rows, "per_gain": per_gain, "best": best, "base": base,
                "unguided": next((r["measured"] for r in rows if r["gain"] == 0), None)})
DATA = json.dumps(out)

T = r"""<!doctype html><html><head><meta charset=utf-8><title>Onset response: FiLM adapter vs LatCH heads</title><style>
body{font:13px system-ui;margin:0;background:#0e0e10;color:#e0e0e0;max-width:1250px}
#bar{position:sticky;top:0;background:#16181c;padding:7px 12px;border-bottom:1px solid #2a2a30;z-index:9}
#wrap{padding:14px}h1{font-size:18px}h2{font-size:15px;color:#9cf;margin:20px 0 3px}.muted{color:#888}
.explain{background:#1a140c;border:1px solid #433;border-left:3px solid #d90;padding:10px 12px;font-size:12.5px;color:#dcd;margin:10px 0}.explain b{color:#fc6}
table{border-collapse:collapse;font-size:12px;margin:4px 0}td,th{border:1px solid #2a2a30;padding:4px 8px;text-align:center}
th{background:#1c1c22;color:#aaa}td:first-child,th:first-child{text-align:left;color:#9ab}
.c{cursor:pointer;font-variant-numeric:tabular-nums}.c:hover{outline:2px solid #7cf}.play{outline:2px solid #5d5 !important}.loading{outline:2px solid #fa5 !important}
.warn{color:#e66;cursor:help}.sec{margin:14px 0;padding:10px 12px;border:1px solid #26262c;border-radius:6px;background:#131316}.good{color:#5d9}.un{color:#e44;font-weight:bold}
</style></head><body>
<div id=bar>&#9654; <b id=np>click a cell to play</b> <span id=pos class=muted></span> <span id=ld class=muted style="color:#fa5"></span> <span class=muted>· switching keeps the playhead · loops until stopped</span></div>
<div id=wrap><h1>Onset response &mdash; FiLM control adapter vs the Phase E LatCH density heads</h1>
<div class=explain><b>What this tests:</b> whether asking for a rendered onset density of 2&ndash;10 onsets per second gets you that density, for the FiLM adapter (the 54000-step runs of the onset_eval page, requests 2&ndash;9) and for the six LatCH heads of Phase E (requests 2, 4, 6, 8, 10; 2, 4, 6, 8 are common to both). <b>Same setup:</b> prompt &ldquo;psytrance, 140 bpm&rdquo;, seed 1234, cfg 7, 50 steps, 20 s, euler, medium-base; measured with librosa onset detection (onsets divided by duration), the page's own function. <b>Different dials:</b> the adapter has a <i>strength</i> (0&ndash;6); the heads have a <i>guidance gain</i> (rho = mu, 128&ndash;8192), and a head is trained on onsets <i>per beat</i>, so each request is converted at 140 bpm: opb = density &times; 60 / 140 (2 &rarr; 0.86, 4 &rarr; 1.71, 6 &rarr; 2.57, 8 &rarr; 3.43, 10 &rarr; 4.29). The two gains are not on a common scale; compare the <i>response curves</i>, not the numbers. <b>Reading a cell:</b> the value is the measured onsets/s; green = within 1 of the request; &#9888; = loudness fell &gt;3 dB, or the clip is much noisier than the unguided one (a DSP screen for &ldquo;not clean&rdquo;, not the disintegration gate, not an ear).</div>
<div id=map></div><div id=out></div></div><audio id=au_el></audio>
<script>const D=__DATA__;
const au=document.getElementById('au_el'),npx=document.getElementById('np');let cur=null;au.loop=true;
au.addEventListener('timeupdate',()=>{document.getElementById('pos').textContent=cur?('· '+au.currentTime.toFixed(1)+'s'):'';});
au.addEventListener('waiting',()=>{document.getElementById('ld').textContent='loading…';markLoading(true);});
au.addEventListener('playing',()=>{document.getElementById('ld').textContent='';markLoading(false);});
function mark(){document.querySelectorAll('.c.play').forEach(e=>e.classList.remove('play'));if(cur){const e=document.getElementById(cur);if(e)e.classList.add('play');}}
function markLoading(on){document.querySelectorAll('.c.loading').forEach(e=>e.classList.remove('loading'));if(on&&cur){const e=document.getElementById(cur);if(e)e.classList.add('loading');}}
function play(id,f,l,run){if(cur===id){au.pause();cur=null;mark();npx.textContent='stopped';return;}
 if(window.noteSet)noteSet({model:'latch_onset_compare',ckpt:run,clip:f});
 const pos=(cur!==null&&!au.paused)?au.currentTime:0;cur=id;mark();npx.textContent='▶ '+l;au.src=f;
 const go=()=>{try{au.currentTime=((au.duration&&pos>au.duration-1)?0:Math.min(pos,(au.duration||1e9)-0.05));}catch(e){}au.play();};
 if(au.readyState>=1)go();else au.addEventListener('loadedmetadata',go,{once:true});}
let m='<h2>Targets and gains side by side</h2><table><tr><th>requested onsets/s</th>'+[2,4,6,8,10].map(d=>`<th>${d}</th>`).join('')+'</tr><tr><td>head target, onsets/beat (140 bpm)</td>'+[2,4,6,8,10].map(d=>`<td>${(d*60/140).toFixed(2)}</td>`).join('')+'</tr></table>'+
 '<table><tr><th>earlier Phase E render targets (mean + k&sigma;, mean 2.94 / sd 1.18 opb)</th><th>k=&minus;1</th><th>k=+1</th><th>k=+2</th></tr><tr><td>onsets/beat</td><td>1.76</td><td>4.12</td><td>5.30</td></tr><tr><td>= onsets/s at 140 bpm</td><td>4.1</td><td>9.6</td><td>12.4</td></tr></table>'+
 '<div class=muted>So the Phase E clips from earlier covered roughly 4, 10 and 12 onsets/s: two inside this page\'s 2&ndash;10 range, one above it. Gains used earlier: 512 and 2048; this comparison sweeps 128, 512, 2048 and 8192 against the adapter\'s 0&ndash;6.</div>';
document.getElementById('map').innerHTML=m;
let h='';
D.forEach(run=>{
 h+=`<div class=sec><h2>${run.label}</h2><div class=muted>unguided: ${run.unguided!=null?run.unguided.toFixed(1):'?'} onsets/s · ${run.dir.includes('latchE')?'<span class=un title="No listening verdict recorded (unaudited).">&#10071;</span> unaudited':'reference run, existing page data'}</div>`;
 h+='<table><tr><th>gain</th>'+run.reqs.map(q=>`<th>ask ${q}</th>`).join('')+'<th>corr</th><th>span</th><th>mean |err|</th></tr>';
 run.gains.forEach(g=>{const pg=run.per_gain.find(x=>x.gain===g);
  h+=`<tr><td>${g===0?'0 (unguided)':'g'+g}</td>`+run.reqs.map(q=>{const r=run.rows.find(x=>x.gain===g&&x.requested===q);if(!r)return'<td>·</td>';
    const id=`${run.dir}_${g}_${q}`;const ok=g!==0&&Math.abs(r.measured-q)<=1;
    return `<td class=c id="${id}" style="${ok?'background:#12301f':''}" onclick="play('${id}','${r.f||''}','${run.label} g${g} ask ${q}','${run.dir}')">${r.flag?'<span class=warn title="loudness fell >3 dB, or much noisier than the unguided clip (DSP screen)">&#9888;</span> ':''}${r.measured.toFixed(1)}</td>`;}).join('')+
   `<td>${pg.corr.toFixed(2)}</td><td>${pg.span.toFixed(1)}</td><td>${pg.mae.toFixed(1)}</td></tr>`;});
 h+='</table><div class=muted>closest gain per request: '+Object.entries(run.best).map(([q,b])=>`ask ${q} &rarr; g${b.gain} (${b.measured.toFixed(1)})`).join(' · ')+'</div></div>';});
document.getElementById('out').innerHTML=h;
</script>
__NOTES__
<footer style="margin:18px 12px;color:#666;font-size:11px">evals &middot; onset response comparison &middot; data: sa3_control_runs (internal)</footer></body></html>"""
T = T.replace("__NOTES__", notes_block("latch_onset_compare", levels=[("clip", "this clip"), ("model", "this run"), ("page", "page")], hint="click a cell, then note what you hear"))
op = os.path.join(STAGE, "latch_onset_compare.html")
open(op, "w").write(inject(T.replace("__DATA__", DATA)))
print(f"wrote {op}: {len(out)} runs, {len(jobs)} clips")
for run in out:
    print(f"\n{run['label']}  (unguided {run['unguided'] if run['unguided'] is None else round(run['unguided'], 1)}/s)")
    for pg in run["per_gain"]:
        if pg["gain"] != 0: print(f"   g{pg['gain']:<6g} corr {pg['corr']:+.2f}  span {pg['span']:+.1f}  mean|err| {pg['mae']:.1f}")
    print("   closest gain per request:", {q: f"g{b['gain']:g}->{b['measured']:.1f}" for q, b in run["best"].items()})
