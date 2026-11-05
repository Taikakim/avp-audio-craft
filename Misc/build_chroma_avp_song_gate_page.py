#!/usr/bin/env python3
# Owner: THE-FINN (created 2026-11-04)
"""Listening page for eval/chroma_avp_song_gate.py: ~/evals_aac/chroma_avp_song_gate.html (local, not published)."""
import html as H
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from comment_notes_block import notes_block
from float_player import inject

OUT = Path("/run/media/kim/Mantu/sa3_control_runs/__chroma/chroma_avp_song_gate_20261104")
SUB = "chroma_avp_song_gate"
STAGE = Path.home() / "evals_aac"
HEADS = ["avp_song_ep20", "avp_song_ep10", "goa_e13"]
GAINS = [512, 2048, 8192]
COLS = [(p, s) for p in ("goa", "suomi") for s in (5678, 1234)]
TARGETS = [("i-VI-III-VII", "Am F C G"), ("keylift", "C, Eb, F# rising"), ("Am", "hold A minor")]

rows = [json.loads(l) for l in (OUT / "cells.jsonl").read_text().splitlines() if l.strip()]
rep = json.loads((OUT / "report.json").read_text())
base = {(r["prompt_id"], r["seed"]): r for r in rows if r["gain"] == 0}
by = {(r["head"], r["target"], r["gain"], r["prompt_id"], r["seed"]): r for r in rows if r["gain"]}


def audio(fn):
    return f'<audio controls preload="none" src="{SUB}/{H.escape(fn)}"></audio>'


def cell(r, tid):
    if r is None:
        return "<td></td>"
    lift = r["fcos_mid"] - base[(r["prompt_id"], r["seed"])]["measured_all"][tid]["mid"]["fcos"]
    return f'<td>{audio(r["fn"])}<div class="m">cos {lift:+.3f} · hit {r["hit_mid"]:.2f}</div></td>'


head = "".join(f"<th>{p} s{s}</th>" for p, s in COLS)
parts = []
for tid, label in TARGETS:
    t = [f"<h2>{H.escape(tid)} <small>{H.escape(label)}</small></h2><div class=w><table><tr><th></th>{head}</tr>"]
    t.append("<tr><th>no steering</th>" + "".join(f'<td>{audio(base[c]["fn"])}</td>' for c in COLS) + "</tr>")
    for h in HEADS:
        for g in GAINS:
            t.append(f"<tr><th>{h}<br>gain {g}</th>" + "".join(cell(by.get((h, tid, g, *c)), tid) for c in COLS) + "</tr>")
    parts.append("".join(t) + "</table></div>")
summ = "".join(
    f"<tr><td>{h}</td><td>{g}</td><td>{rep[f'{h}@{g}']['lift_fcos']:+.3f}</td><td>{rep[f'{h}@{g}']['lift_hit']:+.3f}</td>"
    f"<td>{rep[f'{h}@{g}']['specific']:+.3f}</td><td>{rep[f'{h}@{g}']['blown']}/{rep[f'{h}@{g}']['n']}</td>"
    f"<td>{rep[f'{h}@{g}']['z_ratio']:.3f}</td></tr>" for h in HEADS for g in GAINS)
page = f"""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>AVP chroma head check</title><style>
:root{{color-scheme:light dark}}body{{font:15px/1.5 system-ui;max-width:1500px;margin:auto;padding:16px}}
table{{border-collapse:collapse}}td,th{{border:1px solid #8884;padding:6px;text-align:left;font-weight:400}}th{{white-space:nowrap}}
audio{{width:210px;height:32px;display:block}}.m{{font-size:12px;opacity:.75}}small{{font-weight:400;opacity:.7}}.w{{overflow-x:auto}}</style></head><body>
<h1>AVP chroma head check</h1>
<p><b>Measured, not heard.</b> medium-base with the AVP DoRA (dora128adj_avp_aug10_lr1e4 ep74), 20 s clips, 50 steps, cfg 7.
avp_song is trained only on the project's own music, with whole songs held out. goa_e13 is the private reference and cannot ship. Listen for: does the harmony follow the target, and does the music survive?</p>
<div class=w><table><tr><th>head</th><th>gain</th><th>target cosine lift</th><th>hit lift</th><th>specificity</th><th>screen fails</th><th>latent std ratio</th></tr>{summ}</table></div>
<p>Lift is against the unsteered clip of the same prompt and seed, mid band. Specificity is the fed target against the other targets on the same clip. n = 12 per row: 3 targets, 2 prompts, 2 seeds.</p>
{''.join(parts)}
{notes_block("chroma_avp_song_gate_20261104")}
</body></html>"""
(STAGE / f"{SUB}.html").write_text(inject(page))
print(STAGE / f"{SUB}.html")
