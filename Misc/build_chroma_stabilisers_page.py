#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-11-04)
"""build_chroma_stabilisers_page.py -- listening page for EXPERIMENTS D6, to docs/eval-page-standard.md.
Copies the clips to ~/evals_aac/chroma_stabilisers/, writes ~/evals_aac/chroma_stabilisers.html and the eval dir's result in run_meta.json."""
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from comment_notes_block import notes_block
from float_player import inject

ST = os.path.expanduser("~/evals_aac")
SUB = "chroma_stabilisers"
OUT = f"{ST}/control_runs/chroma_stabilisers_d6_20261104"
ARMS = [("raw", "no stabiliser"), ("clipA", "cap 1%"), ("clipB", "cap 0.3%"), ("stopR95", "stop 95%"), ("stopR90", "stop 90%"), ("stopR80", "stop 80%"), ("tier2", "band weights"), ("midonly", "mid band only")]
GAINS = (4096, 16384)
os.makedirs(f"{ST}/{SUB}", exist_ok=True)
rows = [json.loads(line) for line in open(f"{OUT}/cells.jsonl")]
base = {(c["prompt"], c["seed"]): c for c in rows if c["gain"] == 0}
idx = {(c["arm"], c["prompt"], c["target"], c["gain"], c["seed"]): c for c in rows if c["gain"]}


def copy(clip):
    if not os.path.exists(f"{ST}/{SUB}/{clip}"):
        shutil.copy2(f"{OUT}/{clip}", f"{ST}/{SUB}/{clip}")
    return clip


def table(g):
    head = "<th>prompt · target · seed</th><th>no guidance</th>" + "".join(f"<th>{lab}</th>" for _, lab in ARMS)
    body = ""
    for p, s in sorted(base):
        for t in sorted({c["target"] for c in rows if c["gain"]}):
            b = base[(p, s)]
            body += f"<tr><td class=l>{p} · {t} · {s}</td><td><span class=cell data-f='{copy(b['clip'])}'>play</span></td>"
            for a, _ in ARMS:
                c = idx.get((a, p, t, g, s))
                if not c:
                    body += "<td>·</td>"
                    continue
                v = c["m"][t]["mid"]["hit"] - b["m"][t]["mid"]["hit"]
                body += f"<td><span class=cell data-f='{copy(c['clip'])}'>{v:+.2f}</span></td>"
            body += "</tr>"
    return f"<h2>Gain {g}</h2><table><tr>{head}</tr>{body}</table>"


rep = re.sub(r"\{.*?\}", "", open(f"{OUT}/report.txt").read())
secs = "".join(table(g) for g in GAINS)
T = f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Chroma Guidance Stabilisers</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet"><link rel="stylesheet" href="evals.css">
<style>.wrap{{max-width:1300px}}.ex{{background:#fff;border:1px solid var(--rule);border-left:3px solid var(--edge);padding:10px 12px;font-size:12.5px;margin:10px 0}}.ex b{{color:var(--ink)}}
table{{border-collapse:collapse;font-size:12px;margin:6px 0;display:block;overflow-x:auto;max-width:100%}}td,th{{border:1px solid var(--rule);padding:4px 6px;text-align:center;white-space:nowrap}}td.l{{text-align:left}}
.cell{{display:inline-block;cursor:pointer;border:1px solid var(--rule);border-radius:2px;padding:2px 6px;font-size:11px;background:var(--paper-dim);font-variant-numeric:tabular-nums}}.cell:hover{{background:var(--rule)}}.cell.playing{{outline:2px solid var(--edge)}}
pre{{font-size:11px;white-space:pre-wrap;color:var(--dim)}}.un{{color:#c0392b}}</style></head><body>
<div class=wrap><p class=over>VIBE ON THE EDG3 · EVALS</p><p class=nav><a href="index.html">← all evals</a></p><h1>Chroma guidance stabilisers <span class=un title="No listening verdict yet">❗</span></h1>
<div class=ex><b>What this tests.</b> Three ideas for steadier chroma guidance on the base model, with our best chroma head: a soft cap on the size of each guidance step, stopping guidance once the melody is mostly recovered, and weighting the chroma bands by how reliable they are. Do any of them land more frames on the requested note for the same cleanliness?
<br><b>How.</b> 3 prompts, 4 chord targets, 2 seeds, 24 steps, cfg 7, 24 clips per cell. Each number below is the change in strongest-note hit rate in the mid band, against the same prompt and seed with no steering. Stopping late moves the guidance budget to earlier steps. 99% recovery is never reached on this schedule, so the stops are 95, 90 and 80%.
<br><b>Result (measured, not yet heard): no. Nothing here lands more frames on the note than plain guidance</b> (+0.212 at gain 4096, +0.154 at 16384), and plain guidance was already clean: 1 of 24 and 0 of 24 clips fail the gate, so there was little to stabilise. The 1% cap leaves hit rate where it was and lowers mid-band cosine by 0.05. The 0.3% cap costs far more: hit -0.107 [-0.147, -0.072] and cosine -0.19 at gain 4096. Stopping at 95% changes nothing measurable. Stopping at 80% at gain 16384 gives cosine +0.022 and bass hit +0.036, but 6 of 24 clips fail the gate on latent level. Mid band only raises its own cosine by about 0.02 while hit falls by 0.064, so the chroma gets closer in shape without more frames on the note. Tier-2 band weights change almost nothing.
<br><b>Limits.</b> One head on the base model, two gains, 14 comparisons with no correction, chroma meter only, which is what the head was trained to predict. E13 and a later check found that this head does not collapse up to gain 32768, so a cap might matter more on a weaker head.
</div>
{secs}<h2>Summary</h2><pre>{rep}</pre></div><audio id=au></audio>
<script>const a=document.getElementById('au');let cur=null;document.addEventListener('click',e=>{{const b=e.target.closest('.cell');if(!b)return;const f='{SUB}/'+b.dataset.f;if(cur===b){{a.pause();b.classList.remove('playing');cur=null;return}}const t=a.currentTime;if(cur)cur.classList.remove('playing');a.src=f;a.addEventListener('loadedmetadata',()=>{{a.currentTime=Math.min(t,(a.duration||1e9)-.05);a.play()}},{{once:true}});b.classList.add('playing');cur=b;if(window.noteSet)noteSet({{clip:b.dataset.f}})}});</script>
{notes_block(SUB, levels=[("clip", "this clip"), ("page", "page")], hint="click a clip, then note what you hear")}
<footer style="margin:18px 12px 70px">evals · EXPERIMENTS D6</footer></body></html>"""
open(f"{ST}/{SUB}.html", "w").write(inject(T))

p = f"{OUT}/run_meta.json"
meta = json.load(open(p))
meta["result"] = {"verdict": "negative: no stabiliser lands more frames on the note at equal cleanliness; plain guidance is already clean", "raw": "hit mid +0.212 (g4096), +0.154 (g16384), gate 1/24, 0/24", "report": "report.txt"}
meta["paths"] = {"script": "eval/d6_stabilisers.py", "page": "Misc/build_chroma_stabilisers_page.py", "experiment": "EXPERIMENTS D6"}
json.dump(meta, open(p, "w"), indent=1)
print("clips", len(os.listdir(f"{ST}/{SUB}")))
