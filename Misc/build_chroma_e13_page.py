#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-28)
"""build_chroma_e13_page.py -- listening card for EXPERIMENTS E13 (same_chroma LatCH head retrained under the ModularOptimizer vs
the production head, gain ladder 512-8192).

Reads the E13 run dir (cells.jsonl, report.json from eval/chroma_e13_report.py, run_meta.json). Page:
  1 summary per head x gain: change in chroma toward the target vs the unguided render (bass, mid), strongest-class hit, gate fails
  2 listening rows: per prompt x target x seed, the unguided render, the production head at 2048 / 8192 and the retrained heads
Copies the clips it uses to ~/evals_aac/chroma_e13/ and writes ~/evals_aac/chroma_e13.html. No checkpoint filenames or drive paths.
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from comment_notes_block import notes_block
from float_player import inject

SRC = os.path.expanduser("~/evals_aac/control_runs/chroma_e13_20261028")
STAGE = os.path.expanduser("~/evals_aac")
SUB = "chroma_e13"
PROMPT_LABEL = {"goa": "goa trance (full mix)", "guitar": "solo acoustic guitar", "piano": "solo grand piano"}
TARGET_LABEL = {"C": "hold C major", "Am": "hold A minor", "keylift": "key-lift C → E♭ → F♯ (7 s each)",
                "i-VI-III-VII": "Am → F → C → G (5 s each)"}
HEAD_LABEL = {"prod": "production head (AdamW, depth 4)",
              "C3_ep10_ema1": "retrained, lr 1e-3, epoch 10 (EMA)",
              "C3_ep10_ema025": "retrained, lr 1e-3, epoch 10 (short EMA)",
              "C3_ep10_online": "retrained, lr 1e-3, epoch 10 (online)",
              "C3_ep20_ema1": "retrained, lr 1e-3, epoch 20 (EMA)",
              "C2_ep15_online": "retrained, lr 1e-2, epoch 15 (online)",
              "S0_ep12": "onset-head recipe (d256 depth 8, lr 1e-2, batch 16), epoch 12",
              "S1_ep12": "deeper: d512 depth 12, lr 1e-3, epoch 12",
              "S2_ep12": "wider: d768 depth 8, lr 1e-3, epoch 12"}
MODE_LABEL = {"": "", "~contrast": " · contrast target", "~sharp": " · sharp target", "~normal": ""}
SEEDS = (1234, 5678)
# Each section: listening rows (prompt x target x seed) x columns (head, gain, target mode); the first column is the unsteered render.
SECTIONS = [
    {"title": "2 · Listen: retrained vs production", "targets": list(TARGET_LABEL),
     "note": "Each row is one prompt, target and seed; the first button is the same render with no steering. Button label = change in mid-band chroma match.",
     "cols": [("base", 0, ""), ("prod", 2048, ""), ("prod", 8192, ""), ("C3_ep10_ema1", 512, ""), ("C3_ep10_ema1", 1024, ""),
              ("C3_ep10_ema1", 2048, ""), ("C3_ep10_ema1", 8192, ""), ("C3_ep20_ema1", 2048, ""), ("C2_ep15_online", 2048, "")]},
    {"title": "3 · Listen: other recipes and sizes (E13b)", "targets": ["C", "keylift"],
     "note": "Same comparison for the heads trained afterwards: the onset-head recipe, a deeper head (12 blocks) and a wider one (768). None steered further than the retrained head of section 2.",
     "cols": [("base", 0, ""), ("C3_ep10_ema1", 512, ""), ("C3_ep10_ema1", 2048, ""), ("S0_ep12", 512, ""), ("S0_ep12", 2048, ""),
              ("S1_ep12", 512, ""), ("S1_ep12", 2048, ""), ("S2_ep12", 512, ""), ("S2_ep12", 2048, "")]},
    {"title": "4 · Listen: exaggerated targets and higher gain (E13x)", "targets": ["C", "keylift"],
     "note": "The retrained head pushed harder. The loss is cosine, so a target can only push harder by changing shape: 'contrast' removes each frame's mean (the guide also pushes the other notes down), 'sharp' squares it first (concentrated on the strongest notes). Gains up to 32768. Every clip is still scored against the plain chord.",
     "cols": [("base", 0, ""), ("C3_ep10_ema1", 8192, ""), ("C3_ep10_ema1", 16384, "~normal"), ("C3_ep10_ema1", 32768, "~normal"),
              ("C3_ep10_ema1", 2048, "~contrast"), ("C3_ep10_ema1", 8192, "~contrast"), ("C3_ep10_ema1", 32768, "~contrast"),
              ("C3_ep10_ema1", 2048, "~sharp"), ("C3_ep10_ema1", 8192, "~sharp"), ("C3_ep10_ema1", 32768, "~sharp"),
              ("prod", 32768, "~sharp")]},
]

rows = [json.loads(l) for l in open(f"{SRC}/cells.jsonl") if l.strip()]
rep = json.load(open(f"{SRC}/report.json"))
meta = json.load(open(f"{SRC}/run_meta.json"))
base = {(c["prompt"], c["seed"]): c for c in rows if c["gain"] == 0 and c["clip"].startswith("base0__")}
by = {(r["head"], r["prompt"], r["target"], r["seed"], r["gain"]): r for r in rows if r["gain"] > 0}
os.makedirs(os.path.join(STAGE, SUB), exist_ok=True)
clips, sections = {}, []
for sec in SECTIONS:
    groups, cols = [], []
    for h, g, mode in sec["cols"]:
        if h == "base" or any((h, p, t + mode, s, g) in by for p in PROMPT_LABEL for t in sec["targets"] for s in SEEDS):
            cols.append([h, g, mode, "no steering" if h == "base" else HEAD_LABEL.get(h, h) + "<br>gain " + str(g) + MODE_LABEL[mode]])
    for p in PROMPT_LABEL:
        for t in sec["targets"]:
            for s in SEEDS:
                b = base[(p, s)]
                groups.append([p, t, s])
                for h, g, mode, _ in cols:
                    c = b if h == "base" else by.get((h, p, t + mode, s, g))
                    if c is None:
                        continue
                    cid = f"{p}__{t}{mode}__s{s}__{h}__g{g}"
                    dst = os.path.join(STAGE, SUB, c["clip"])
                    if not os.path.exists(dst):
                        shutil.copy2(os.path.join(SRC, c["clip"]), dst)
                    m, mb = c["m"][t + mode] if h != "base" else None, b["m"][t]
                    clips[cid] = {"f": f"{SUB}/{c['clip']}", "head": h, "gain": g, "mode": mode,
                                  "dmid": round(m["mid"]["fcos"] - mb["mid"]["fcos"], 3) if m else None,
                                  "dbass": round(m["bass"]["fcos"] - mb["bass"]["fcos"], 3) if m else None}
    if len(cols) > 1:
        sections.append({"title": sec["title"], "note": sec["note"], "cols": cols, "groups": groups})
DATA = json.dumps({"prompt_label": PROMPT_LABEL, "target_label": TARGET_LABEL, "head_label": HEAD_LABEL, "sections": sections,
                   "clips": clips, "ladder": rep["ladder"], "paired": rep["paired"], "size": rep.get("size", []),
                   "exag": rep.get("exag", [])})

T = r"""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Chroma Head Retrain</title><style>
body{font:13px system-ui;margin:0;background:#0e0e10;color:#e0e0e0}
#bar{position:sticky;top:0;background:#16181c;padding:7px 12px;border-bottom:1px solid #2a2a30;z-index:9}
#wrap{padding:14px 16px;max-width:1400px}h1{font-size:18px}h2{font-size:15px;margin:26px 0 4px;color:#cde}h3{font-size:13px;margin:14px 0 4px;color:#abc}.muted{color:#888}
.explain{background:#1a140c;border:1px solid #433;border-left:3px solid #d90;padding:10px 12px;font-size:12.5px;color:#dcd;margin:10px 0;line-height:1.45}.explain b{color:#fc6}
table{border-collapse:collapse;font-size:12px;margin:4px 0;display:block;overflow-x:auto}td,th{border:1px solid #2a2a30;padding:4px 6px;text-align:center;white-space:nowrap}
th{background:#1c1c22;color:#aaa}td.l{text-align:left;color:#9ab;white-space:normal;min-width:160px}
.num{font-variant-numeric:tabular-nums}
.b{display:inline-block;cursor:pointer;border:1px solid #333;border-radius:3px;padding:1px 4px;margin:1px;font-size:11px;font-variant-numeric:tabular-nums;background:#18181c}
.b:hover{outline:1px solid #7cf}.play{outline:2px solid #5d5 !important}.un{color:#e44;font-weight:bold;cursor:help}
</style></head><body>
<div id=bar>&#9654; <b id=np>click a clip to play</b> <span id=pos class=muted></span> <span class=muted>· switching keeps the playhead · re-click stops</span></div>
<div id=wrap><h1>Chroma steering: the retrained head vs the production head</h1>
<div class=explain><b>Why this page exists.</b> The chroma head steers harmony (which notes and chords sound) toward a target, and an earlier listen found
the production head transparent but subtle, most audible at gain 2048. It was retrained with the modular optimiser (larger, depth 8, held-out validation).
This page asks whether the retrained head moves the harmony further at the same gain, and whether that still sounds clean.
<b>How to read it.</b> Each clip is compared with the same prompt and seed rendered with no steering. Numbers on the buttons are the change in chroma
match to the target (mid band; higher = closer to the target). <b>Gate fails</b> = clips flagged by the disintegration screen (whitening, high-frequency
buzz, noise, beat loss, Audiobox quality drop, latent level). All clips: SA3 medium base, 20 s, 24 steps, cfg 7.
<b>What it cannot tell you.</b> Whether the chord change sounds musical, or whether the instrument's character survived: listen for that. __UN__</div>
<div id=out></div></div><audio id=au_el></audio>
<script>const D=__DATA__;
const au=document.getElementById('au_el'),npx=document.getElementById('np');let cur=null;
au.addEventListener('timeupdate',()=>{document.getElementById('pos').textContent=cur?('· '+au.currentTime.toFixed(1)+'s'):'';});
au.addEventListener('ended',()=>{cur=null;mark();});
function mark(){document.querySelectorAll('.b.play').forEach(e=>e.classList.remove('play'));if(cur){document.querySelectorAll('[data-id="'+cur+'"]').forEach(e=>e.classList.add('play'));}}
function play(id){const c=D.clips[id];if(cur===id){au.pause();cur=null;mark();npx.textContent='stopped';return;}
 if(window.noteSet)noteSet({model:'chroma_e13',ckpt:'',clip:id});
 const pos=(cur!==null&&!au.paused)?au.currentTime:0;cur=id;mark();
 npx.textContent=id.split('__').slice(0,3).join(' · ')+' — '+(c.head==='base'?'no steering':(D.head_label[c.head]||c.head)+', gain '+c.gain+(c.mode?' '+c.mode.slice(1)+' target':''));au.src=c.f;
 const go=()=>{try{au.currentTime=Math.min(pos,(au.duration||1e9)-0.05);}catch(e){}au.play();};
 if(au.readyState>=1)go();else au.addEventListener('loadedmetadata',go,{once:true});}
const f=(v,d)=>v==null?'–':(v>=0?'+':'')+Number(v).toFixed(d);
const btn=(id,lbl)=>D.clips[id]?`<span class=b data-id="${id}" title="bass ${f(D.clips[id].dbass,3)}" onclick="play('${id}')">${lbl}</span>`:'<span class=muted>–</span>';
let h='<h2>1 · Summary per head and gain</h2><div class=muted>mean over 3 prompts × 4 targets × 4 seeds (48 clips per row); change vs the unguided render</div>';
const heads=[...new Set(D.ladder.map(r=>r.head))];const gains=[...new Set(D.ladder.map(r=>r.gain))];
h+='<table><tr><th>head</th>'+gains.map(g=>`<th>gain ${g}<br>mid · bass · fails</th>`).join('')+'</tr>';
heads.forEach(hd=>{h+=`<tr><td class=l>${D.head_label[hd]||hd}</td>`+gains.map(g=>{const r=D.ladder.find(x=>x.head===hd&&x.gain===g);
 return r?`<td class=num><b>${f(r.mid_fcos,3)}</b> · ${f(r.bass_fcos,3)} · ${r.fails}/${r.n}</td>`:'<td>–</td>';}).join('')+'</tr>';});
h+='</table>';
if(D.size.length){
 h+='<h2>1b · Other recipes and sizes (E13b)</h2><div class=muted>3 prompts × hold C / key-lift × 2 seeds (12 clips per cell); change vs the unguided render, mid · bass · fails</div>';
 const sh=[...new Set(D.size.map(r=>r.head))].sort();
 h+='<table><tr><th>head</th><th>gain 512</th><th>gain 2048</th></tr>'+sh.map(hd=>`<tr><td class=l>${D.head_label[hd]||hd}</td>`+[512,2048].map(g=>{const r=D.size.find(x=>x.head===hd&&x.gain===g);
  return r?`<td class=num><b>${f(r.mid_fcos,3)}</b> · ${f(r.bass_fcos,3)} · ${r.fails}/${r.n}</td>`:'<td>–</td>';}).join('')+'</tr>').join('')+'</table>';}
if(D.exag.length){
 h+='<h2>1c · Exaggerated targets and higher gain (E13x)</h2><div class=muted>same 12 clips per cell; every clip scored against the plain chord. mid · bass · fails (top gate reason)</div>';
 const eg=[...new Set(D.exag.map(r=>r.gain))].sort((a,b)=>a-b);const keys=[...new Set(D.exag.map(r=>r.head+'|'+r.mode))];
 h+='<table><tr><th>head · target shape</th>'+eg.map(g=>`<th>gain ${g}</th>`).join('')+'</tr>'+keys.map(k=>{const [hd,md]=k.split('|');
  return `<tr><td class=l>${D.head_label[hd]||hd} · <b>${md}</b></td>`+eg.map(g=>{const r=D.exag.find(x=>x.head===hd&&x.mode===md&&x.gain===g);
   const why=r&&r.fails?Object.entries(r.reasons).sort((a,b)=>b[1]-a[1])[0][0]:'';
   return r?`<td class=num><b>${f(r.mid_fcos,3)}</b> · ${f(r.bass_fcos,3)} · ${r.fails}/${r.n}${why?' <span class=muted>'+why+'</span>':''}</td>`:'<td>–</td>';}).join('')+'</tr>';}).join('')+'</table>';}
D.sections.forEach(S=>{h+=`<h2>${S.title}</h2><div class=muted>${S.note}</div>`;
 Object.keys(D.prompt_label).forEach(p=>{h+=`<h3>${D.prompt_label[p]}</h3><table><tr><th>target · seed</th>`+
  S.cols.map(c=>`<th>${c[3]}</th>`).join('')+'</tr>';
  S.groups.filter(x=>x[0]===p).forEach(([pp,t,s])=>{h+=`<tr><td class=l>${D.target_label[t]} · s${s}</td>`+
   S.cols.map(([hd,g,md])=>{const id=`${pp}__${t}${md}__s${s}__${hd}__g${g}`;return `<td>${btn(id,hd==='base'?'▶':f(D.clips[id]?.dmid,2))}</td>`;}).join('')+'</tr>';});
  h+='</table>';});});
document.getElementById('out').innerHTML=h;
</script>
__NOTES__
<footer style="margin:18px 12px;color:#666;font-size:11px">evals &middot; chroma head retrain (EXPERIMENTS E13) &middot; gate: control-head disintegration gate vs the unguided render</footer>
</body></html>"""
UN = "" if meta.get("kim_feedback") else '<span class=un title="No listening verdict recorded yet (unaudited).">&#10071;</span> No listening verdict recorded yet.'
T = T.replace("__UN__", UN).replace(
    "__NOTES__", notes_block("chroma_e13", levels=[("clip", "this clip"), ("page", "page")], hint="click a clip, then note what you hear"))
out = os.path.join(STAGE, "chroma_e13.html")
open(out, "w").write(inject(T.replace("__DATA__", DATA)))
print(f"wrote {out}: {len(clips)} clips")
