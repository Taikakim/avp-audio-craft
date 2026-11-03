#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-11-03)
"""build_f0_contour_page.py -- listening page for EXPERIMENTS E4, E4b and D16: the melody (f0) heads, to docs/eval-page-standard.md.
Copies the clips it uses to ~/evals_aac/f0_contour/ and writes ~/evals_aac/f0_contour.html."""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from comment_notes_block import notes_block
from float_player import inject

R = os.path.expanduser("~/evals_aac/control_runs")
E4, E4B, D16 = f"{R}/e4_f0_gate_20261103", f"{R}/e4b_f0_shapes_20261103", f"{R}/d16_contour_ceiling_20261103"
ST = os.path.expanduser("~/evals_aac")
SUB = "f0_contour"
os.makedirs(f"{ST}/{SUB}", exist_ok=True)
a = json.load(open(f"{E4}/report.json"))["table"]
b = json.load(open(f"{E4B}/report.json"))
d = json.load(open(f"{D16}/report.json"))
ca = [json.loads(l) for l in open(f"{E4}/cells.jsonl")]
cb = [json.loads(l) for l in open(f"{E4B}/cells.jsonl")]
cd = [json.loads(l) for l in open(f"{D16}/cells.jsonl")]


def link(src, cid):
    dst = f"{ST}/{SUB}/{cid}.m4a"
    if not os.path.exists(dst):
        shutil.copy2(f"{src}/{cid}.m4a", dst)
    return f"<span class=b data-f='{cid}.m4a'>"


keys = sorted({(c["pid"], c["seed"]) for c in cb})
shape_rows = ""
for pid, seed in keys:
    base = f"{pid}__s{seed}__base0"
    shape_rows += f"<tr><td class=l>{pid} · s{seed}</td><td>{link(E4, base)}no steering</span></td>"
    for s in ("up", "down", "arch", "valley"):
        cells = "".join(link(E4B, f"{pid}__s{seed}__{s}__g{g}") + f"{g // 1024}k</span> " for g in (8192, 16384))
        shape_rows += f"<td>{cells}</td>"
    shape_rows += "</tr>"
bass_rows = ""
for pid, seed in keys[:6]:
    base = f"{pid}__s{seed}__base0"
    cells = "".join(f"<td>{link(E4, f'{pid}__s{seed}__{h}__{dr}__g8192')}{h} {dr}</span></td>" for h in ("bass",) for dr in ("up", "down"))
    bass_rows += f"<tr><td class=l>{pid} · s{seed}</td><td>{link(E4, base)}no steering</span></td>{cells}</tr>"
per_rows = ""
for pid, seed in keys[:4]:
    base = f"{pid}__s{seed}__base0"
    per_rows += f"<tr><td class=l>{pid} · s{seed}</td><td>{link(E4, base)}no steering</span></td>" + "".join(f"<td>{link(D16, f'{pid}__s{seed}__p{p}__in')}{p} s</span></td>" for p in (10.0, 5.0, 2.5, 1.25, 0.625)) + "</tr>"
t1 = "".join(f"<tr><td>{r['head']}</td><td>{r['gain']}</td><td class=n><b>{r['sep']:+.1f}</b> st [{r['ci'][0]:+.1f}, {r['ci'][1]:+.1f}]</td><td>{r['positive']}/{r['n']}</td><td>{r['fails']}/{r['gated']}</td></tr>" for r in a)
t2 = "".join(f"<tr><td>{r['gain']}</td><td>{r['shapes']}</td><td class=n><b>{r['follow']:+.2f}</b> [{r['ci'][0]:+.2f}, {r['ci'][1]:+.2f}]</td><td>{r['positive']}/{r['n']}</td><td class=n>{r['bright']:+.2f}</td><td class=n>{r['octave']:.4f} / {r['base_octave']:.4f}</td><td>{r['fails']}/{r['gated']}</td><td class=n>{r['dce']:+.2f}</td></tr>" for r in b)
t3 = "".join(f"<tr><td>{r['period']} s</td><td class=n><b>{r['follow']:+.2f}</b> [{r['ci'][0]:+.2f}, {r['ci'][1]:+.2f}]</td><td>{r['positive']}/{r['n']}</td><td>{r['fails']}/{r['n']}</td></tr>" for r in d)
T = f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Melody Head Contours</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet"><link rel="stylesheet" href="evals.css">
<style>.wrap{{max-width:1300px}}.ex{{background:#fff;border:1px solid var(--rule);border-left:3px solid var(--edge);padding:10px 12px;font-size:12.5px;margin:10px 0}}.ex b{{color:var(--ink)}}
table{{border-collapse:collapse;font-size:12px;margin:6px 0;display:block;overflow-x:auto;max-width:100%}}td,th{{border:1px solid var(--rule);padding:4px 6px;text-align:center;white-space:nowrap}}td.l{{text-align:left}}th{{background:var(--paper-dim);color:var(--dim);font-weight:500}}
.n{{font-variant-numeric:tabular-nums}}.b{{display:inline-block;cursor:pointer;border:1px solid var(--rule);border-radius:2px;padding:2px 6px;font-size:11px;background:var(--paper-dim);margin:1px}}.b:hover{{border-color:var(--edge)}}.play{{background:var(--edge) !important;color:#fff}}.un{{color:#e33;font-weight:bold}}</style></head><body>
<div class=wrap><p class=over>VIBE ON THE EDG3 · EVALS</p><p class=nav><a href="index.html">← all evals</a></p><h1>Melody heads: can guidance set a pitch contour? <span class=un title="No listening verdict recorded yet">&#10071;</span></h1>
<div class=ex><b>What this tests.</b> Whether the melody (f0) heads make the generated music follow a requested pitch line, measured with a pitch tracker on the rendered mix, and whether the clips survive the disintegration gate.<br>
<b>Result (measured, not yet heard).</b> The <b>lead head moves pitch over a whole 20 s clip</b>, in the requested direction, including non-monotonic arch and valley shapes, and the clips pass the gate up to about gain 8192. Pitch follows far more strongly than brightness, and octave errors do not rise. <b>It does not follow faster shapes:</b> with a triangle wave at a 10 s period the effect is nearly gone, and at 5 s and below it is not distinguishable from zero. So this is control of register or direction across a clip, not of a melody. The <b>bass head shows no effect</b> at the gains tested.<br>
<b>Limits.</b> A pitch tracker on a full mix is noisy, and it may read a voice that was already there getting louder. 6 prompts, 2 seeds, base model. Whether it sounds like a line going up is the question for your ears.</div>
<h2>Direction: rising vs falling target</h2><div class=dim>Separation = measured pitch slope on the rising target minus the falling one, semitones per clip; interval over prompts; a real effect is positive.</div>
<table><tr><th>head</th><th>gain</th><th>separation</th><th>positive</th><th>gate fails</th></tr>{t1}</table>
<h2>Shape: is it following, or drifting?</h2><div class=dim>Follow = correlation with the target minus correlation with its mirror, in voiced semitones. Chance 0, maximum 2. Brightness = the same on the spectral centroid. Lead head.</div>
<table><tr><th>gain</th><th>shapes</th><th>follow</th><th>positive</th><th>brightness</th><th>octave jumps, steered / unsteered</th><th>gate fails</th><th>CE change</th></tr>{t2}</table>
<h2>Listen: shapes, lead head</h2><div class=dim>Gains 8192 and 16384. Target range about 15 semitones, 300 to 700 Hz.</div>
<table><tr><th>prompt · seed</th><th>baseline</th><th>up</th><th>down</th><th>arch</th><th>valley</th></tr>{shape_rows}</table>
<h2>How fast? Triangle waves</h2><div class=dim>Gain 16384. Follow = in phase minus antiphase. The unsteered clips, scored against the same targets, reach 0.52 at 10 s and 0.36 at 5 s by chance, so short clips of slow targets are a weak test.</div>
<table><tr><th>period</th><th>follow</th><th>positive</th><th>gate fails</th></tr>{t3}</table>
<table><tr><th>prompt · seed</th><th>baseline</th><th colspan=5>period</th></tr>{per_rows}</table>
<h2>Listen: bass head</h2><div class=dim>Gain 8192. No separation measured.</div>
<table><tr><th>prompt · seed</th><th>baseline</th><th>up</th><th>down</th></tr>{bass_rows}</table></div><audio id=au></audio>
<script>const a=document.getElementById('au');let cur=null;document.addEventListener('click',e=>{{const b=e.target.closest('.b');if(!b)return;const f=b.dataset.f;document.querySelectorAll('.play').forEach(x=>x.classList.remove('play'));if(cur===f){{a.pause();cur=null;return}}const pos=(cur&&!a.paused)?a.currentTime:0;cur=f;b.classList.add('play');a.src='{SUB}/'+f;if(window.noteSet)noteSet({{model:'f0_contour',ckpt:'',clip:f}});a.addEventListener('loadedmetadata',()=>{{try{{a.currentTime=Math.min(pos,(a.duration||1e9)-.05)}}catch(x){{}}a.play()}},{{once:true}});a.load()}});</script>
{notes_block("f0_contour", levels=[("clip", "this clip"), ("page", "page")], hint="click a clip, then note what you hear")}
<footer style="margin:18px 12px 70px">evals · EXPERIMENTS E4, E4b, D16</footer></body></html>"""
open(f"{ST}/f0_contour.html", "w").write(inject(T))
print("wrote", len(os.listdir(f"{ST}/{SUB}")), "clips")
