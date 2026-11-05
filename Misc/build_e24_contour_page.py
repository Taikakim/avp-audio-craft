#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-11-03)
"""build_e24_contour_page.py -- listening page for EXPERIMENTS E24: melody contour through the per-block inlet, to docs/eval-page-standard.md.
Copies the clips to ~/evals_aac/e24_contour/, writes ~/evals_aac/e24_contour.html and the eval dir's run_meta.json. Arm B joins the page when its eval exists."""
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
SUB = "e24_contour"
RUNS = {
    "C": f"{ST}/control_runs/e24_contourC_eval2_20261103",
    "B": f"{ST}/control_runs/e24_contourB_eval2_20261103",
    "A": f"{ST}/control_runs/e24_contourA_eval2_20261104",
}
NAMES = {
    "C": "Arm C: centred pitch",
    "B": "Arm B: K&amp;P L3 shapes",
    "A": "Arm A: interval-from-previous-note",
}
ARMS = [("ref", "the source crop"), ("zero", "no stream"), ("true_null", "stream, CFG scales it"), ("shuf_null", "shuffled, CFG scales it"), ("true", "stream, both branches"), ("shuffled", "shuffled, both branches")]
os.makedirs(f"{ST}/{SUB}", exist_ok=True)


def section(arm, out):
    rows = json.load(open(f"{out}/scores.json"))
    crops = json.load(open(f"{out}/crops.json"))
    by = {(r["stem"], r["arm"]): r for r in rows}
    head = "".join(f"<th>{lab}</th>" for _, lab in ARMS)
    body = ""
    for i, c in enumerate(crops):
        s = c["stem"]
        body += f"<tr><td class=l title='{c['prompt']}'>{i + 1} · {c['prompt'][:34]}</td>"
        for a, _ in ARMS:
            r = by.get((s, a))
            if not r:
                body += "<td>·</td>"
                continue
            f = r["id"]
            dst = f"{ST}/{SUB}/{arm}__{f}.m4a"
            if not os.path.exists(dst):
                shutil.copy2(f"{out}/{f}.m4a", dst)
            fed, oth = r["r_fed"] or 0, r["r_other"] or 0
            body += f"<td><span class=cell data-f='{arm}__{f}.m4a'>{fed:+.2f} / {oth:+.2f}</span></td>"
        body += "</tr>"
    rep = open(f"{out}/report.txt").read()
    rep = re.sub(r"^run .*?, step", "step", rep)
    return f"""<h2>{NAMES[arm]}</h2><div class=dim>Each cell: correlation with the stream it was fed / with the one it was not. Click to play. Hover a row for its prompt.</div>
<table><tr><th>crop · prompt</th>{head}</tr>{body}</table><pre>{rep}</pre>"""


secs = "".join(section(a, o) for a, o in RUNS.items() if os.path.exists(f"{o}/scores.json"))
T = f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Melody Contour Inlet</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet"><link rel="stylesheet" href="evals.css">
<style>.wrap{{max-width:1300px}}.ex{{background:#fff;border:1px solid var(--rule);border-left:3px solid var(--edge);padding:10px 12px;font-size:12.5px;margin:10px 0}}.ex b{{color:var(--ink)}}
table{{border-collapse:collapse;font-size:12px;margin:6px 0;display:block;overflow-x:auto;max-width:100%}}td,th{{border:1px solid var(--rule);padding:4px 6px;text-align:center;white-space:nowrap}}td.l{{text-align:left}}
.cell{{display:inline-block;cursor:pointer;border:1px solid var(--rule);border-radius:2px;padding:2px 6px;font-size:11px;background:var(--paper-dim);font-variant-numeric:tabular-nums}}.cell:hover{{background:var(--rule)}}.cell.playing{{outline:2px solid var(--edge)}}
pre{{font-size:11px;white-space:pre-wrap;color:var(--dim)}}.un{{color:#c0392b}}</style></head><body>
<div class=wrap><p class=over>VIBE ON THE EDG3 · EVALS</p><p class=nav><a href="index.html">← all evals</a></p><h1>Melody contour through the per-block inlet <span class=un title="No listening verdict yet">❗</span></h1>
<div class=ex><b>What this tests.</b> A fine-tune trained with a melody stream made from MuScriptor notes: the pitch of the top line, centred so key does not matter, added directly at each frame in DiT blocks 12-23. Does the generated music follow the stream it is given?
<br><b>How.</b> MuScriptor transcribes each render, and the top line is correlated with the stream. Each render is scored against the stream it was fed and against the same notes in shuffled 3 s blocks. Following shows as the first number well above the second. 24 crops, each with its own prompt and seed, shared by that crop's arms. Step 2400 of training.
<br><b>Result (measured, not yet heard).</b> With zeros for the stream in CFG's uncond branch, so that CFG scales the stream as well as the text: <b>fed minus other +0.467 [+0.392, +0.543], 46 of 48 clips, 0 of 48 fail the gate against the no-stream clip.</b> The top line reaches +0.57 with its fed stream, where the source crop itself reads +0.54. With the stream in both branches, as every mir_ctrl eval before this: +0.151.
<br><b>Limits.</b> This is the shape over seconds. With each curve's running mean over 1.5 s removed, leaving note-scale movement: +0.103 [+0.059, +0.147], against about +0.19 for the source crop. Within a semitone of the fed line: 14%, no-stream clips 12%, source crop 39%. So it follows the contour, not the notes. Scaled CFG also lowers Audiobox PQ by 0.25 and raises CE by 0.4. The transcriber may favour what the stream made loudest, and only ears can say whether this sounds like a melody following a line. Training stops at 2,400 steps, 7 epochs.
<br><b>Arm B, K&amp;P L3 shapes from the same notes through the same inlet (same recipe and length).</b> Scored on centred pitch: +0.055 [-0.011, +0.120], 33 of 48. L3 carries no interval size, so that score favours arm C. Scored on L3 shape agreement, B's own measure: B +0.020 [+0.006, +0.037], C +0.028 [+0.014, +0.041], decoded source crops +0.209. So L3 is no better than centred pitch on its own measure, and both follow local note shape at about a tenth of the source crop's level. Gate 0 of 48.</div>
{secs}</div><audio id=au></audio>
<script>const a=document.getElementById('au');let cur=null;document.addEventListener('click',e=>{{const b=e.target.closest('.cell');if(!b)return;const f='{SUB}/'+b.dataset.f;if(cur===b){{a.pause();b.classList.remove('playing');cur=null;return}}const t=a.currentTime;if(cur)cur.classList.remove('playing');a.src=f;a.addEventListener('loadedmetadata',()=>{{a.currentTime=Math.min(t,(a.duration||1e9)-.05);a.play()}},{{once:true}});cur=b;b.classList.add('playing')}});</script>
{notes_block("e24_contour", levels=[("clip", "this clip"), ("page", "page")], hint="click a clip, then note what you hear")}
<footer style="margin:18px 12px 70px">evals · EXPERIMENTS E24</footer></body></html>"""
open(f"{ST}/e24_contour.html", "w").write(inject(T))

meta_path = f"{RUNS['C']}/run_meta.json"
prev = json.load(open(meta_path)) if os.path.exists(meta_path) else {}
json.dump({**prev, "purpose": "E24 arm C: does a key-free melody stream from MuScriptor notes, added per frame at blocks 12-23, make generated music follow it?",
           "hypothesis": "D15 showed note events through this inlet steer at inference. Centred pitch keeps interval size and ignores key.",
           "paths": {"checkpoint": "UUID drive sa3_lora_runs/e24_contourC_r128_2026-11-03/step=2400.ckpt", "script": "eval/e24_eval2.py", "train": "latch/run_e24_contourC.sh", "page": "Misc/build_e24_contour_page.py", "experiment": "EXPERIMENTS E24"},
           "training": {"recipe": "DoRA r128, ModularOptimizer shampoo, lr 3e-4, T=256, batch 16, 2400 steps, stream dropout 0.2, blocks 12-23", "dataset": "latents_sa3, 5400 goa crops, no augmentation; stream from Kosmos/muscriptor_full"},
           "result": {"follow_null_uncond": "+0.467 [+0.392,+0.543] 46/48", "follow_both_branches": "+0.151 [+0.050,+0.249] 30/48", "note_scale_null_uncond": "+0.103 [+0.059,+0.147] 34/48", "gate": "0/48 null uncond, 0/48 both branches", "control_decoded_crops": "+0.542"},
           "kim_feedback": prev.get("kim_feedback")}, open(meta_path, "w"), indent=1)
print("wrote", len(os.listdir(f"{ST}/{SUB}")), "clips")
