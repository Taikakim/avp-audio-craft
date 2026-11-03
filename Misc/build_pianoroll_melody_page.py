#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-11-03)
"""build_pianoroll_melody_page.py -- listening page for EXPERIMENTS D15 (re-read 2026-11-03): the pianoroll fine-tune plays the notes it is fed, to docs/eval-page-standard.md.
Renders each invented melody alone as a plain synth line, so the ear can compare it with the generated clip. Copies clips to ~/evals_aac/pianoroll_melody/, writes ~/evals_aac/pianoroll_melody.html and the run sidecars."""
import json
import os
import shutil
import subprocess
import sys

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "eval"))
from comment_notes_block import notes_block
from float_player import inject
import d15_new_melodies as D

ST = os.path.expanduser("~/evals_aac")
SUB = "pianoroll_melody"
NEW = f"{ST}/control_runs/pianoroll_newmelody_goa_t256_step2688_20261103"
CRP = f"{ST}/control_runs/pianoroll_cfgnull_goa_t256_step2688_20261103"
os.makedirs(f"{ST}/{SUB}", exist_ok=True)
SR = 44100
HOP = 4096


def synth(line, path):
    """A plain saw-like line, only so the melody can be heard against the render."""
    t = np.arange(len(line) * HOP) / SR
    hz = 440.0 * 2 ** ((np.repeat(line, HOP).astype(np.float64) - 69) / 12)
    ph = 2 * np.pi * np.cumsum(hz) / SR
    x = sum(np.sin(ph * k) / k for k in range(1, 7))
    change = np.flatnonzero(np.diff(line) != 0) + 1
    env = np.ones(len(t))
    for c in np.r_[0, change] * HOP:
        n = min(HOP // 2, len(t) - c)
        env[c:c + n] = np.minimum(env[c:c + n], np.linspace(0.05, 1, n))
    x = x * env
    wav = path[:-4] + ".wav"
    sf.write(wav, 0.35 * x / np.abs(x).max(), SR)
    subprocess.run(["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-i", wav, "-c:a", "aac", "-b:a", "192k", path], check=True)
    os.remove(wav)


def clip(run, cid, pre):
    name = f"{pre}__{cid}.m4a"
    dst = f"{ST}/{SUB}/{name}"
    if not os.path.exists(dst):
        shutil.copy2(f"{run}/{cid}.m4a", dst)
    return name


def cell(name, label):
    return f"<td><span class=cell data-f='{name}'>{label}</span></td>"


rows = json.load(open(f"{NEW}/scores.json"))
new = [r for r in rows if r["kind"] == "new"]
zero = {r["p"]: r for r in rows if r["kind"] == "zero"}
tr = [r for r in rows if r["kind"] == "transp"]
T1 = ""
for r in new:
    m = D.melody(r["melody"])
    mel = f"m{r['melody']}__alone.m4a"
    if not os.path.exists(f"{ST}/{SUB}/{mel}"):
        synth(m, f"{ST}/{SUB}/{mel}")
    T1 += f"<tr><td class=l title='{r['prompt']}'>{r['melody']} · {r['prompt'][:38]}</td>" + cell(mel, "melody alone") + cell(clip(NEW, r["id"], "new"), f"{r['recall_fed']:.0%} / {r['top_fed']:.0%}") + cell(clip(NEW, zero[r["p"]]["id"], "new"), f"{r['recall_other']:.0%} / {r['top_other']:.0%}") + "</tr>"
T2 = ""
crop_scores = {(x["stem"], x["arm"]): x for x in json.load(open(f"{CRP}/scores.json"))}
for p in sorted({r["p"] for r in tr}):
    a = [r for r in tr if r["p"] == p]
    s = a[0]["stem"]
    T2 += f"<tr><td class=l title='{a[0]['prompt']}'>{a[0]['prompt'][:38]}</td>"
    if (s, "ref") in crop_scores:
        T2 += cell(clip(CRP, f"ref__{s}", "crop"), "source crop")
        T2 += cell(clip(CRP, crop_scores[(s, "true_null")]["id"], "crop"), f"{crop_scores[(s, 'true_null')]['f1_fed']:.2f}")
    else:
        T2 += "<td>·</td><td>·</td>"
    for r in sorted(a, key=lambda x: -x["semis"]):
        T2 += cell(clip(NEW, r["id"], "new"), f"{r['semis']:+d} st · {r['f1_fed']:.2f}")
    T2 += "</tr>"
T3 = ""
for s in sorted({k[0] for k in crop_scores}):
    if (s, "true") not in crop_scores:
        continue
    T3 += f"<tr><td class=l title='{crop_scores[(s, 'true')]['id']}'>{s}</td>" + "".join(cell(clip(CRP, crop_scores[(s, a)]["id"], "crop"), f"{crop_scores[(s, a)].get('f1_fed', 0):.2f} / {crop_scores[(s, a)].get('f1_other', 0):.2f}") for a in ("zero", "true", "shuffled", "true_null", "shuf_null")) + "</tr>"
GRID = f"{ST}/control_runs/pianoroll_strength_goa_t256_step2688_20261103"
CHK = f"{ST}/control_runs/pianoroll_checks_goa_t256_20261103"
T4, T5, T6, rep3, rep4 = "", "", "", "", ""
if os.path.exists(f"{GRID}/grid.json"):
    g = {(r["cfg"], r["strength"]): r for r in json.load(open(f"{GRID}/grid.json"))}
    cfgs, strs = sorted({k[0] for k in g}), sorted({k[1] for k in g})
    T4 = "<tr><th>cfg</th>" + "".join(f"<th>notes x{s:g}</th>" for s in strs) + "</tr>"
    for c in cfgs:
        T4 += f"<tr><td>{c:g}</td>" + "".join(f"<td>{g[(c, s)]['recall']:.0%} / {g[(c, s)]['top']:.0%}<br>gate {g[(c, s)]['fails']}/{g[(c, s)]['n']} · CE {g[(c, s)]['ce']:.2f}</td>" for s in strs) + "</tr>"
    grows = json.load(open(f"{GRID}/scores.json"))
    by = {(r["p"], r.get("melody"), r["cfg"], r["strength"]): r for r in grows}
    for m, p in ((0, 0), (1, 0), (2, 1), (3, 1)):
        mel = f"m{m}__alone.m4a"
        if not os.path.exists(f"{ST}/{SUB}/{mel}"):
            synth(D.melody(m), f"{ST}/{SUB}/{mel}")
        T5 += f"<h3>Melody {m}: <span class=cell data-f='{mel}'>melody alone</span></h3><table><tr><th>cfg</th><th>no stream</th>" + "".join(f"<th>x{s:g}</th>" for s in strs) + "</tr>"
        for c in cfgs:
            z = by[(p, None, c, 0.0)]
            T5 += f"<tr><td>{c:g}</td>" + cell(clip(GRID, z["id"], "grid"), "play")
            for s in strs:
                r = by[(p, m, c, s)]
                T5 += cell(clip(GRID, r["id"], "grid"), f"{r['recall']:.0%} / {r['top']:.0%}")
            T5 += "</tr>"
        T5 += "</table>"
    rep3 = open(f"{GRID}/report.txt").read()
if os.path.exists(f"{CHK}/report.txt"):
    rep4 = open(f"{CHK}/report.txt").read()
    crows = json.load(open(f"{CHK}/scores.json"))
    cb = {(r["arm"], r.get("melody")): r for r in crows if r["kind"] == "new"}
    T6 = "<table><tr><th>melody</th><th>the line</th><th>notes in both CFG branches</th><th>CFG on the notes, second seed</th><th>EMA weights</th><th>second training seed</th></tr>"
    for m in sorted({k[1] for k in cb})[:12]:
        mel = f"m{m}__alone.m4a"
        if not os.path.exists(f"{ST}/{SUB}/{mel}"):
            synth(D.melody(m), f"{ST}/{SUB}/{mel}")
        T6 += f"<tr><td>{m}</td>" + cell(mel, "melody alone") + "".join(cell(clip(CHK, cb[(a, m)]["id"], "chk"), f"{cb[(a, m)]['recall']:.0%} / {cb[(a, m)]['top']:.0%}") for a in ("both", "seed2", "ema", "s2")) + "</tr>"
    T6 += "</table>"
rep = open(f"{NEW}/report.txt").read()
rep2 = open(f"{CRP}/report.txt").read().split("\n", 1)[1]
T = f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Melody From Notes</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet"><link rel="stylesheet" href="evals.css">
<style>.wrap{{max-width:1300px}}.ex{{background:#fff;border:1px solid var(--rule);border-left:3px solid var(--edge);padding:10px 12px;font-size:12.5px;margin:10px 0}}.ex b{{color:var(--ink)}}
table{{border-collapse:collapse;font-size:12px;margin:6px 0;display:block;overflow-x:auto;max-width:100%}}td,th{{border:1px solid var(--rule);padding:4px 6px;text-align:center;white-space:nowrap}}td.l{{text-align:left}}
.cell{{display:inline-block;cursor:pointer;border:1px solid var(--rule);border-radius:2px;padding:2px 6px;font-size:11px;background:var(--paper-dim);font-variant-numeric:tabular-nums}}.cell:hover{{background:var(--rule)}}.cell.playing{{outline:2px solid var(--edge)}}
pre{{font-size:11px;white-space:pre-wrap;color:var(--dim)}}.un{{color:#c0392b}}</style></head><body>
<div class=wrap><p class=over>VIBE ON THE EDG3 · EVALS</p><p class=nav><a href="index.html">← all evals</a></p><h1>Melody from notes: it plays what it is given <span class=un title="No listening verdict yet">❗</span></h1>
<div class=ex><b>What this tests.</b> A full fine-tune of SA3 medium trained in August with a 128-note pianoroll from MuScriptor, added at each frame in DiT blocks 12-23. Until today the roll went into both CFG branches, so at cfg 7 the prompt was scaled and the notes were not. Here the uncond branch gets zeros, the null the inlet trained on. The question: does it play notes it was never trained on?
<br><b>Result (measured by MuScriptor, not yet heard).</b> <b>Invented melodies, none in the training set: the fed pitch sounds on 73% of frames, 2.5% with no stream, 3.2% for another melody. The top line sits on the fed pitch for 67%. 36 of 36 clips, 2 of 36 fail the gate, both on CE drift.</b> The same melody cut into shuffled 3 s blocks scores 40%, because it shares pitches; fed minus shuffled +0.33 [+0.29, +0.37]. <b>Transposed crops move with the transposition: F1 0.63 with the transposed roll, 0.05 with the roll as it was, 24 of 24.</b> On training crops, F1 with the fed roll is 0.65, where the source crop itself reads 0.61; 84% of played frames land on a fed note, against 52% with the roll in both branches and 8% with none.
<br><b>Checks on the same melodies.</b> It is the fix: with the notes in both CFG branches, the old way, the fed pitch sounds on 13%. It is not one seed: another render seed gives 65%, top line 62%, 36 of 36. It is not one checkpoint: the run's second training seed gives 73%, top line 67%, 36 of 36. EMA weights play no notes, 5.0% against 4.8% with no stream: 5,376 updates at beta 0.9999 is under one half-life and the inlet started at zero, so an evaluation of this model on its EMA weights would read as dead.
<br><b>Limits.</b> 24 steps, 24 s clips, 12 prompts. MuScriptor made the training rolls and also scores the renders, so the invented melodies were checked with Melodia as well, an f0 tracker that played no part in training: 74% of voiced frames within a semitone of the fed melody, octave folded, against 43% for its shuffled blocks, 17% for another melody and 18% with no stream, fed minus other +0.58 [+0.50, +0.65], 34 of 36. Neither meter says it sounds like music, and a thin lead on top of the track would also score well. Results vary by prompt: recall runs from 21% to 100%. Transposed clips drop in Audiobox (PQ 7.17, no-stream 7.68; CE 6.10 vs 6.42) and read duller. The EMA of this run has under one half-life, so these are online weights. These weights trained on commercial music and stay private; a publishable version means retraining on a legal set.</div>
<h2>Invented melodies</h2><div class=dim>Compare <b>melody alone</b> (a plain synth, for reference) with the generated clip. Numbers: fed pitch sounds anywhere / top line on it. The no-stream column is the same prompt and seed, scored against another melody.</div>
<table><tr><th>melody · prompt</th><th>the line</th><th>generated</th><th>no stream</th></tr>{T1}</table>
<h2>Transposed crops</h2><div class=dim>A real crop's roll moved up 5 or down 7 semitones. Numbers: F1 with the roll fed.</div>
<table><tr><th>prompt</th><th>source crop</th><th>roll as it was</th><th colspan=2>transposed</th></tr>{T2}</table>
<h2>Training crops, with and without CFG on the stream</h2><div class=dim>Numbers: F1 with the roll it was fed / with the same notes in shuffled blocks.</div>
<table><tr><th>crop</th><th>no stream</th><th>roll, both branches</th><th>shuffled, both branches</th><th>roll, CFG scales it</th><th>shuffled, CFG scales it</th></tr>{T3}</table>
<h2>Text CFG and note strength</h2><div class=dim>Invented melodies, 12 per cell, CFG on the stream. Fed pitch sounds / top line on it; gate against the no-stream clip of the same prompt and cfg; Audiobox CE. A different melody sounds on only 2 to 5% of frames in every cell. For the ear: raising either one plays the line more surely, and above x1 CE drops by about 0.8.</div>
<table>{T4}</table>{T5}
<h2>Is it the fix, the seed, or this checkpoint?</h2><div class=dim>The same invented melodies, cfg 7. Fed pitch sounds / top line on it.</div>{T6}<pre>{rep4}</pre>
<h2>Measurements</h2><pre>{rep}</pre><pre>{rep2}</pre><pre>{rep3}</pre></div><audio id=au></audio>
<script>const a=document.getElementById('au');let cur=null;document.addEventListener('click',e=>{{const b=e.target.closest('.cell');if(!b)return;const f='{SUB}/'+b.dataset.f;if(cur===b){{a.pause();b.classList.remove('playing');cur=null;return}}const t=a.currentTime;if(cur)cur.classList.remove('playing');a.src=f;a.addEventListener('loadedmetadata',()=>{{a.currentTime=Math.min(t,(a.duration||1e9)-.05);a.play()}},{{once:true}});cur=b;b.classList.add('playing')}});</script>
{notes_block("pianoroll_melody", levels=[("clip", "this clip"), ("page", "page")], hint="click a clip, then note what you hear")}
<footer style="margin:18px 12px 70px">evals · EXPERIMENTS D15</footer></body></html>"""
open(f"{ST}/pianoroll_melody.html", "w").write(inject(T))
base = {"paths": {"checkpoint": "UUID drive lumi_runs/pianoroll_fullft/proll_fullft_t256_bf16_s1/epoch=31-step=2688.ckpt", "page": "Misc/build_pianoroll_melody_page.py", "experiment": "EXPERIMENTS D15"},
        "training": {"recipe": "full fine-tune, AdamW + WSD, lr 1e-4, bf16, T=256, effective batch 64, 32 epochs, stream dropout 0.2, blocks 12-23, online weights rendered", "dataset": "goa latents_sa3, 5400 crops, MuScriptor roll, no augmentation"},
        "kim_feedback": None}
for run, purpose, hyp, script in ((NEW, "D15: does the pianoroll fine-tune play notes it was not trained on, with CFG on the stream?", "Training crops could be memory. Invented melodies and transposed crops cannot.", "eval/d15_new_melodies.py"),
                                  (CRP, "D15 re-read: the pianoroll fine-tune with zeros for the stream in CFG's uncond branch.", "E24 arm C went from +0.151 to +0.467 this way; D15 ran with the stream in both branches.", "eval/e24_eval2.py")):
    p = f"{run}/run_meta.json"
    m = json.load(open(p)) if os.path.exists(p) else {}
    for k, v in {**base, "purpose": purpose, "hypothesis": hyp, "script": script}.items():
        m.setdefault(k, v)
    json.dump(m, open(p, "w"), indent=1)
print("wrote", len(os.listdir(f"{ST}/{SUB}")), "clips")
