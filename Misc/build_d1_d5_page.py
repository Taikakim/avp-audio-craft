#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-11-03)
"""build_d1_d5_page.py -- listening page for EXPERIMENTS D1 (SDEdit survival) and D5 (adaptive step grid), to docs/eval-page-standard.md.
Copies clips to ~/evals_aac/d1_d5_tests/ and writes ~/evals_aac/d1_d5_tests.html."""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from comment_notes_block import notes_block
from float_player import inject

R = os.path.expanduser("~/evals_aac/control_runs")
D1, D5 = f"{R}/d1_sdedit_survival_20261103", f"{R}/d5_adaptive_grid_20261103"
ST = os.path.expanduser("~/evals_aac")
SUB = "d1_d5_tests"
os.makedirs(f"{ST}/{SUB}", exist_ok=True)
rep = json.load(open(f"{D1}/report.json"))
LV = ["0.1", "0.2", "0.3", "0.4", "0.5", "0.6", "0.7", "0.8", "0.9", "1.0"]
M = ["phase_bass", "phase_mid", "phase_air", "rhythm_lag_mid", "tiv", "chroma", "mel"]
for s, pat in ((D1, ".m4a"), (D5, ".m4a")):
    for f in os.listdir(s):
        if f.endswith(pat) and not os.path.exists(f"{ST}/{SUB}/{f}") and not (s == D1 and "__s5678" in f):
            shutil.copy2(f"{s}/{f}", f"{ST}/{SUB}/{f}")
rows = [json.loads(l) for l in open(f"{D5}/cells.jsonl")]
pids = sorted({r["pid"] for r in rows})
D5ERR = {f"{r['pid']}|{r['arm']}|{r['n']}": r["err"] for r in rows}
curve = "".join(f"<tr><td>{t}</td>" + "".join(f"<td>{rep['curve'][t][m]:.2f}</td>" for m in M) + "</tr>" for t in LV)
floor = "<tr><td>floor</td>" + "".join(f"<td>{rep['floor'][m]:.2f}</td>" for m in M) + "</tr>"
half = "<tr><td>half point</td>" + "".join(f"<td><b>{rep['half_point'][m]['t_s']:.2f}</b><br><span class=dim>{rep['half_point'][m]['ci'][0]:.2f}&ndash;{rep['half_point'][m]['ci'][1]:.2f}</span></td>" for m in M) + "</tr>"
d1rows = "".join(f"<tr><td>track {i + 1}</td><td><span class=b data-f='t{i:02d}__source.m4a'>source</span></td>" + "".join(f"<td><span class=b data-f='t{i:02d}__ts{t}__s1234.m4a'>{t}</span></td>" for t in LV) + "</tr>" for i in range(12))
d5rows = "".join(f"<tr><td>{p}</td><td><span class=b data-f='{p}__ref256.m4a'>N=256</span></td>" + "".join(f"<td><span class=b data-f='{p}__default__n{n}.m4a'>default {D5ERR[p + '|default|' + str(n)]:.2f}</span> <span class=b data-f='{p}__adaptive__n{n}.m4a'>adaptive {D5ERR[p + '|adaptive|' + str(n)]:.2f}</span></td>" for n in (16, 24, 32)) + "</tr>" for p in pids)
T = f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>SDEdit And Step Grid</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet"><link rel="stylesheet" href="evals.css">
<style>.wrap{{max-width:1300px}}.ex{{background:#fff;border:1px solid var(--rule);border-left:3px solid var(--edge);padding:10px 12px;font-size:12.5px;margin:10px 0}}.ex b{{color:var(--ink)}}
table{{border-collapse:collapse;font-size:12px;margin:6px 0;display:block;overflow-x:auto;max-width:100%}}td,th{{border:1px solid var(--rule);padding:4px 6px;text-align:center;white-space:nowrap}}th{{background:var(--paper-dim);color:var(--dim);font-weight:500}}
.b{{display:inline-block;cursor:pointer;border:1px solid var(--rule);border-radius:2px;padding:2px 6px;font-size:11px;background:var(--paper-dim)}}.b:hover{{border-color:var(--edge)}}.play{{background:var(--edge) !important;color:#fff}}.dim{{color:var(--dim)}}.un{{color:#e33;font-weight:bold}}</style></head><body>
<div class=wrap><p class=over>VIBE ON THE EDG3 · EVALS</p><p class=nav><a href="index.html">← all evals</a></p><h1>Two older tests: SDEdit survival and an adaptive step grid <span class=un title="No listening verdict recorded yet">&#10071;</span></h1>
<div class=ex><b>D1: what survives as SDEdit's start noise rises?</b> If rhythm outlived harmony at some noise level, audio-to-audio could keep one and regenerate the other there. <b>Result: no such band on the base model.</b> Rhythm timing in each band, harmony and timbre all fall together between 0.4 and 0.6, with half points of 0.49 to 0.53 and overlapping intervals. Below 0.3 all stay above 0.8. 12 goa tracks, one prompt, 2 seeds (240 clips; the buttons play seed 1234). An adapter may behave differently.</div>
<table><tr><th>t_s</th><th>rhythm, bass</th><th>rhythm, mid</th><th>rhythm, air</th><th>rhythm, shifted</th><th>harmony (TIV)</th><th>chroma</th><th>timbre (mel)</th></tr>{curve}{floor}{half}</table>
<h2>Listen: D1</h2><table>{d1rows}</table>
<div class=ex><b>D5: does a step grid that follows the flow's curvature reduce error?</b> A paper reports 7 to 16% less discretization error. <b>Result: on our base renders it raised error,</b> by 34% at 16 steps (interval +5 to +80), 15% at 24 (-3 to +36) and 24% at 32 (+2 to +49), and Audiobox quality did not improve. The reference (256 steps) uses our default schedule, which may favour it. Button numbers: error against that reference, lower is closer.</div>
<h2>Listen: D5</h2><table>{d5rows}</table></div><audio id=au></audio>
<script>const a=document.getElementById('au');let cur=null;document.addEventListener('click',e=>{{const b=e.target.closest('.b');if(!b)return;const f=b.dataset.f;document.querySelectorAll('.play').forEach(x=>x.classList.remove('play'));if(cur===f){{a.pause();cur=null;return}}const pos=(cur&&!a.paused)?a.currentTime:0;cur=f;b.classList.add('play');a.src='{SUB}/'+f;if(window.noteSet)noteSet({{model:'d1_d5_tests',ckpt:'',clip:f}});a.addEventListener('loadedmetadata',()=>{{try{{a.currentTime=Math.min(pos,(a.duration||1e9)-.05)}}catch(x){{}}a.play()}},{{once:true}});a.load()}});</script>
{notes_block("d1_d5_tests", levels=[("clip", "this clip"), ("page", "page")], hint="click a clip, then note what you hear")}
<footer style="margin:18px 12px 70px">evals · EXPERIMENTS D1, D5</footer></body></html>"""
open(f"{ST}/d1_d5_tests.html", "w").write(inject(T))
print("wrote", len(os.listdir(f"{ST}/{SUB}")), "clips")
