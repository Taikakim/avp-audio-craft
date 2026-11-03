#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-11-03)
"""build_mood_deconf_page.py -- listening page for eval/mood_deconf_render.py: de-confounded vs naive mood targets on every prompt.

Reads the run dir (cells.jsonl, report.json from eval/mood_deconf_report.py, run_meta.json). Page: summary tables, then one
listening table per chosen model + target group, rows = prompts, columns = baseline and gains, same-playhead buttons.
The FINDINGS text below is written by hand after reading the report; set it before building. It must state only what report.json supports.
Copies clips to ~/evals_aac/mood_deconf/ and writes ~/evals_aac/mood_deconf.html. No drive paths.
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "eval"))
from comment_notes_block import notes_block
from float_player import inject

SRC = os.path.expanduser("~/evals_aac/control_runs/mood_deconf_20261103")
STAGE = os.path.expanduser("~/evals_aac")
SUB = "mood_deconf"
FINDINGS_FILE = os.path.join(SRC, "findings.html")
MODEL_LABEL = {"base": "Medium base", "adamw": "AdamW epoch 9 file (AVP)", "goa": "Goa LoRA ep63", "combo_fusion_goa": "Fusion + Goa, 50/50"}
GROUPS = {"Melodic": ["Melodic", "Deconf_Melodic"], "Space": ["Space", "Deconf_Space"], "Dark": ["Dark", "Deconf_Dark"],
          "Uplifting (Deconf only)": ["Deconf_Uplifting"], "Anti-dark (Deconf only)": ["Deconf_AntiDark"]}
GAINS = [1024, 2048, 4096, 8192]

cells = [json.loads(l) for l in open(os.path.join(SRC, "cells.jsonl"))]
scores = {}
classes = json.load(open(os.path.join(SRC, "classes.json")))
for l in open(os.path.join(SRC, "mood_scores.jsonl")):
    d = json.loads(l)
    scores[d["id"]] = d["scores"]
rep = json.load(open(os.path.join(SRC, "report.json")))
meta = json.load(open(os.path.join(SRC, "run_meta.json")))
findings = open(FINDINGS_FILE).read()
sys.path.insert(0, os.path.join(HERE, "..", "eval"))
os.makedirs(os.path.join(STAGE, SUB), exist_ok=True)

KEEP = {"melodic", "space", "dark", "uplifting"}
ix = {k: classes.index(k) for k in KEEP}
clips, prompts = {}, {}
for c in cells:
    prompts[c["pid"]] = c["seed"]
    src, dst = os.path.join(SRC, c["id"] + ".m4a"), os.path.join(STAGE, SUB, c["id"] + ".m4a")
    if os.path.exists(src) and (not os.path.exists(dst) or os.path.getmtime(dst) < os.path.getmtime(src)):
        shutil.copy2(src, dst)
    s = scores.get(c["id"])
    clips[c["id"]] = {k: round(s[i], 3) for k, i in ix.items()} if s else {}
TEXT = json.load(open(os.path.join(SRC, "prompts.json")))
DATA = json.dumps({"clips": clips, "models": MODEL_LABEL, "groups": GROUPS, "gains": GAINS, "prompts": list(prompts), "text": TEXT,
                   "target_gain": rep["by_target_gain"], "paired": rep["paired"], "own": {"Melodic": "melodic", "Deconf_Melodic": "melodic", "Space": "space", "Deconf_Space": "space", "Dark": "dark", "Deconf_Dark": "dark", "Deconf_Uplifting": "uplifting", "Deconf_AntiDark": "melodic"}})

T = r"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Mood Deconfounded Targets</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet"><link rel="stylesheet" href="evals.css"><style>
.wrap{max-width:1400px}.muted{color:var(--dim)}
.explain{background:#fff;border:1px solid var(--rule);border-left:3px solid var(--edge);padding:10px 12px;font-size:12.5px;margin:10px 0;line-height:1.6}.explain b{color:var(--ink)}
table{border-collapse:collapse;font-size:12px;margin:4px 0;display:block;overflow-x:auto;max-width:100%}td,th{border:1px solid var(--rule);padding:4px 6px;text-align:center;white-space:nowrap}
th{background:var(--paper-dim);color:var(--dim);font-weight:500}td.l{text-align:left;white-space:normal;min-width:190px;max-width:320px}
.num{font-variant-numeric:tabular-nums}select{background:var(--paper-dim);color:var(--body);border:1px solid var(--rule);padding:4px;margin:0 10px 0 4px;font:inherit}
.b{display:inline-block;cursor:pointer;border:1px solid var(--rule);border-radius:2px;padding:2px 5px;margin:1px;font-size:11px;font-variant-numeric:tabular-nums;background:var(--paper-dim);min-width:30px}
.b:hover{border-color:var(--edge)}.play{background:var(--edge) !important;color:#fff;border-color:var(--edge)}.un{color:#e33;font-weight:bold;cursor:help}
</style></head><body>
<div class=wrap><p class=over>VIBE ON THE EDG3 · EVALS</p><p class=nav><a href="index.html">← all evals</a></p><h1>Mood steering: de-confounded targets vs naive ones</h1>
<div class=explain><b>Why this page exists.</b> A first run suggested that mood targets corrected for the classifier's stock-music common factor (de-confounded) steer better than
naive targets that name three tags. That run used one prompt and one seed. This one repeats it on 15 prompts, 4 models and 4 gains (1,980 clips).
<b>How to read it.</b> Each clip is compared with the same model, prompt and seed rendered through the guided sampler at gain 0. Scores are an Essentia mood classifier on the rendered audio, from 0 to 1.
A higher score means the classifier hears more of that tag, not that it sounds better. <b>Gate fails</b> = clips flagged by the disintegration screen.</div>
<div class=explain>__FINDINGS__ __UN__</div>
<div id=sum></div>
<h2>Listen</h2>
<div>Model<select id=sm></select>Target<select id=sg></select>Score shown<select id=ss></select></div>
<div class=muted>Rows are prompts, each with its own seed. The button shows the chosen score; the first column is the same render with no steering. Switching clips keeps the playhead; clicking the playing clip stops it.</div>
<div id=grid></div></div><audio id=au_el preload=none></audio>
<script>const D=__DATA__;
const au=document.getElementById('au_el'),np=document.createElement('span');let cur=null;
au.addEventListener('ended',()=>{cur=null;mark();});
function mark(){document.querySelectorAll('.b.play').forEach(e=>e.classList.remove('play'));if(cur){document.querySelectorAll('[data-id="'+cur+'"]').forEach(e=>e.classList.add('play'));}}
function play(id){if(cur===id){au.pause();cur=null;mark();np.textContent='stopped';return;}
 if(window.noteSet)noteSet({model:'mood_deconf',ckpt:'',clip:id});
 const pos=(cur!==null&&!au.paused)?au.currentTime:0;cur=id;mark();np.textContent=id.replace(/__/g,' · ');au.src='mood_deconf/'+id+'.m4a';
 const go=()=>{try{au.currentTime=Math.min(pos,(au.duration||1e9)-0.05);}catch(e){}au.play();};
 if(au.readyState>=1)go();else au.addEventListener('loadedmetadata',go,{once:true});au.load();}
const f=(v,d)=>v==null?'–':(v>=0?'+':'')+Number(v).toFixed(d);
let s='<h2>Requested mood: change in its score</h2><div class=muted>mean over all models and prompts (60 clips per cell) · change · fraction of clips that went up · gate fails</div><table><tr><th>target</th><th>tag</th>'+D.gains.map(g=>`<th>gain ${g}</th>`).join('')+'</tr>';
Object.keys(D.own).forEach(t=>{s+=`<tr><td class=l>${t.replace('_',' ')}</td><td>${D.own[t]}</td>`+D.gains.map(g=>{const r=D.target_gain[t+'|'+g];return `<td class=num><b>${f(r.own,3)}</b> · ${r.own_up.toFixed(2)} · ${r.fails}/${r.n}</td>`;}).join('')+'</tr>';});
s+='</table><h2>De-confounded minus naive, same model, prompt and gain</h2><div class=muted>95% interval resamples the 15 prompts. "Melodic kept" only tests something on Space and Dark, where melodic is not the request.</div><table><tr><th>target</th><th>requested mood</th><th>melodic kept</th><th>collateral change (lower is more selective)</th><th>Audiobox CE</th></tr>';
['Deconf_Melodic','Deconf_Space','Deconf_Dark'].forEach(t=>{s+=`<tr><td class=l>${t.replace('_',' ')}</td>`+['own','melodic','off','ce'].map(m=>{const r=D.paired[`${t}|${m}|all`];return r?`<td class=num><b>${f(r.diff,3)}</b> [${f(r.ci[0],3)}, ${f(r.ci[1],3)}]<br><span class=muted>higher in ${r.wins}/${r.n}</span></td>`:'<td>–</td>';}).join('')+'</tr>';});
document.getElementById('sum').innerHTML=s+'</table>';
const sm=document.getElementById('sm'),sg=document.getElementById('sg'),ss=document.getElementById('ss');
Object.entries(D.models).forEach(([k,v])=>sm.add(new Option(v,k)));Object.keys(D.groups).forEach(k=>sg.add(new Option(k,k)));['melodic','space','dark','uplifting'].forEach(k=>ss.add(new Option(k,k)));
function btn(id,sc){const c=D.clips[id];if(!c)return '<span class=muted>–</span>';const v=c[sc];return `<span class=b data-id="${id}" onclick="play('${id}')">${v==null?'▶':v.toFixed(2)}</span>`;}
function draw(){const m=sm.value,g=sg.value,sc=ss.value,ts=D.groups[g];
 let h='<table><tr><th>prompt</th><th>no steering</th>'+ts.flatMap(t=>D.gains.map(x=>`<th>${t.replace('_',' ')}<br>gain ${x}</th>`)).join('')+'</tr>';
 D.prompts.forEach(p=>{h+=`<tr><td class=l title="${(D.text[p]||'').replace(/"/g,'&quot;')}">${p}<br><span class=muted>${(D.text[p]||'').slice(0,70)}</span></td><td>${btn(`${m}__${p}__base0`,sc)}</td>`+ts.flatMap(t=>D.gains.map(x=>`<td>${btn(`${m}__${p}__${t}__g${x}`,sc)}</td>`)).join('')+'</tr>';});
 document.getElementById('grid').innerHTML=h+'</table>';mark();}
[sm,sg,ss].forEach(e=>e.addEventListener('change',draw));ss.value=D.own[D.groups[sg.value][0]];sg.addEventListener('change',()=>{ss.value=D.own[D.groups[sg.value][0]];draw();});draw();
</script>
__NOTES__
<footer style="margin:18px 12px 70px;color:#666;font-size:11px">evals &middot; mood de-confounded targets &middot; gate: control-head disintegration gate vs the guided gain-0 render</footer>
</body></html>"""
UN = "" if meta.get("kim_feedback") else '<span class=un title="No listening verdict recorded yet (unaudited).">&#10071;</span> No listening verdict recorded yet.'
T = T.replace("__FINDINGS__", findings).replace("__UN__", UN).replace(
    "__NOTES__", notes_block("mood_deconf", levels=[("clip", "this clip"), ("page", "page")], hint="click a clip, then note what you hear"))
out = os.path.join(STAGE, "mood_deconf.html")
open(out, "w").write(inject(T.replace("__DATA__", DATA)))
print(f"wrote {out}: {len(clips)} clips")
