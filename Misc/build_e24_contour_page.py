#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-11-03, updated 2026-11-05 for MIDI target preview and D15 comparison)
"""build_e24_contour_page.py -- listening page for EXPERIMENTS E24 & D15: melody contour & pianoroll through per-block inlets.
Copies clips to ~/evals_aac/e24_contour/, writes ~/evals_aac/e24_contour.html.
"""
import json
import os
import re
import shutil
import sys
from html import escape

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from comment_notes_block import notes_block
from float_player import inject

ST = os.path.expanduser("~/evals_aac")
SUB = "e24_contour"
os.makedirs(f"{ST}/{SUB}", exist_ok=True)

RUNS = {
    "C": f"{ST}/control_runs/e24_contourC_eval2_20261103",
    "A": f"{ST}/control_runs/e24_contourA_eval2_20261104",
    "B": f"{ST}/control_runs/e24_contourB_eval2_20261103",
    "P_full": f"{ST}/control_runs/pianoroll_cfgnull_goa_t256_step2688_20261103",
    "P_skyline": f"{ST}/control_runs/d15_skyline_cfgnull_goa_t256_step2688_20261105",
}

NAMES = {
    "C": "Arm C: centred pitch (1D skyline, continuous pitch-invariant, 2-ch)",
    "A": "Arm A: interval-from-previous-note (1D skyline, discrete semitone steps, 26-ch)",
    "B": "Arm B: K&amp;P L3 shapes (1D skyline, discrete rank tokens, 15-ch)",
    "P_full": "D15: Pianoroll Full MIDI (128-ch polyphonic notes: chords, bass & melody)",
    "P_skyline": "D15: Pianoroll Highest Line (1D skyline on 128-ch inlet, absolute pitch)",
}

ARMS = [
    ("ref", "the source crop"),
    ("zero", "no stream"),
    ("true_null", "stream, CFG scales it"),
    ("shuf_null", "shuffled, CFG scales it"),
    ("true", "stream, both branches"),
    ("shuffled", "shuffled, both branches"),
]

def section(arm, out):
    if not os.path.exists(f"{out}/scores.json"):
        return ""
    rows = json.load(open(f"{out}/scores.json"))
    crops = json.load(open(f"{out}/crops.json"))
    by = {(r["stem"], r["arm"]): r for r in rows}
    head = "<th>🎵 target melody</th>" + "".join(f"<th>{lab}</th>" for _, lab in ARMS)
    body = ""
    for i, c in enumerate(crops):
        s = c["stem"]
        mel_file = f"melody__{s}.m4a"
        mel_td = f"<td><span class='cell mel' data-f='{mel_file}'>▶ melody</span></td>"
        body += f"<tr><td class=l title='{escape(c['prompt'])}'>{i + 1} · {escape(c['prompt'][:34])}</td>{mel_td}"
        for a, _ in ARMS:
            r = by.get((s, a))
            if not r:
                body += "<td>·</td>"
                continue
            f = r["id"]
            dst = f"{ST}/{SUB}/{arm}__{f}.m4a"
            if not os.path.exists(dst):
                src = f"{out}/{f}.m4a"
                if os.path.exists(src):
                    shutil.copy2(src, dst)
            fed, oth = r.get("r_fed") or 0, r.get("r_other") or 0
            body += f"<td><span class=cell data-f='{arm}__{f}.m4a'>{fed:+.2f} / {oth:+.2f}</span></td>"
        body += "</tr>"
    rep_path = f"{out}/report.txt"
    rep = open(rep_path).read() if os.path.exists(rep_path) else ""
    rep = re.sub(r"^run .*?, step", "step", rep)
    return f"""<h2>{NAMES[arm]}</h2><div class=dim>Each cell: correlation with the stream it was fed / with the one it was not. Click to play. Hover a row for its prompt.</div>
<table><tr><th>crop · prompt</th>{head}</tr>{body}</table><pre>{rep}</pre>"""

secs = "".join(section(a, o) for a, o in RUNS.items() if os.path.exists(f"{o}/scores.json"))

T = f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Melody Contour & Pianoroll Comparison</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet"><link rel="stylesheet" href="evals.css">
<style>.wrap{{max-width:1380px}}.ex{{background:#fff;border:1px solid var(--rule);border-left:3px solid var(--edge);padding:10px 14px;font-size:12.5px;margin:10px 0;line-height:1.6}}.ex b{{color:var(--ink)}}
table{{border-collapse:collapse;font-size:12px;margin:6px 0;display:block;overflow-x:auto;max-width:100%}}td,th{{border:1px solid var(--rule);padding:4px 6px;text-align:center;white-space:nowrap}}td.l{{text-align:left}}
.cell{{display:inline-block;cursor:pointer;border:1px solid var(--rule);border-radius:2px;padding:2px 6px;font-size:11px;background:var(--paper-dim);font-variant-numeric:tabular-nums}}.cell:hover{{background:var(--rule)}}.cell.playing{{outline:2px solid var(--edge)}}
.cell.mel{{background:#e8f5e9;border-color:#c8e6c9;color:#1b5e20;font-weight:600}}.cell.mel:hover{{background:#c8e6c9;border-color:#81c784}}
pre{{font-size:11px;white-space:pre-wrap;color:var(--dim)}}.un{{color:#c0392b}}</style></head><body>
<div class=wrap><p class=over>VIBE ON THE EDG3 · EVALS</p><p class=nav><a href="index.html">← all evals</a></p><h1>Melody contour through per-block inlets (E24 & D15 Comparison)</h1>
<div class=ex>
<b>What this tests:</b> Melody conditioning through DiT per-block inlets (blocks 12–23) on the same 24 paired crops (shared prompts and seeds).
<ul style="margin:4px 0 6px 18px;padding:0">
<li><b>🎵 Target Melody Column:</b> A plain additive synthesizer rendition of the extracted MuScriptor MIDI skyline (the exact pitch sequence the model was asked to follow), allowing direct auditory comparison of the target melody line in isolation against the generated music.</li>
<li><b>E24 Arm C (Centred Pitch):</b> Pitch minus median note (continuous pitch-invariant). The reigning champion for macro-phrase steering (+0.467 [+0.392, +0.543], 46/48 pos).</li>
<li><b>E24 Arm A (Interval Steps):</b> Relative semitone step from previous note (&plusmn;12 semitones) + onset flag (26-ch). Decisively outperforms Arm B on note-scale follow (+0.065 vs +0.003).</li>
<li><b>E24 Arm B (K&P L3 Shapes):</b> Discrete rank tokens on the note grid (15-ch). Fails to steer note-scale movement (+0.003 flat noise).</li>
<li><b>D15 Pianoroll Full MIDI:</b> 128-channel binary matrix carrying all polyphonic notes (chords, bass, arpeggios, and lead). Steers both melody (+0.636) and harmony, but locks to absolute key and pitches.</li>
<li><b>D15 Pianoroll Highest Line:</b> Fed into D15's 128-key inlet, but with <i>only</i> the monophonic melody skyline active on the keyboard grid. Directly tests whether the pianoroll inlet can generalize to isolated single-voice steering.</li>
</ul>
<b>Scoring:</b> MuScriptor transcribes each render; the top line is correlated with the fed stream (r<sub>fed</sub>) and with the permuted stream (r<sub>other</sub>). Following appears as r<sub>fed</sub> well above r<sub>other</sub>.
</div>
{secs}</div><audio id=au></audio>
<script>const a=document.getElementById('au');a.loop=true;let cur=null;document.addEventListener('click',e=>{{const b=e.target.closest('.cell');if(!b)return;const f='{SUB}/'+b.dataset.f;if(cur===b){{a.pause();b.classList.remove('playing');cur=null;return}}const t=a.currentTime;if(cur)cur.classList.remove('playing');a.src=f;a.addEventListener('loadedmetadata',()=>{{a.currentTime=Math.min(t,(a.duration||1e9)-.05);a.play()}},{{once:true}});cur=b;b.classList.add('playing')}});</script>
{notes_block("e24_contour", levels=[("clip", "this clip"), ("page", "page")], hint="click a clip, then note what you hear")}
<footer style="margin:18px 12px 70px">evals · EXPERIMENTS E24 & D15</footer></body></html>"""

out_html = f"{ST}/e24_contour.html"
open(out_html, "w").write(inject(T))
print(f"Wrote {out_html} with {len(os.listdir(f'{ST}/{SUB}'))} clips and float player injected.")
