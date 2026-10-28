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
              "C2_ep15_online": "retrained, lr 1e-2, epoch 15 (online)"}
COLS = [("base", 0), ("prod", 2048), ("prod", 8192), ("C3_ep10_ema1", 512), ("C3_ep10_ema1", 1024), ("C3_ep10_ema1", 2048),
        ("C3_ep10_ema1", 8192), ("C3_ep20_ema1", 2048), ("C2_ep15_online", 2048)]
SEEDS = (1234, 5678)

rows = [json.loads(l) for l in open(f"{SRC}/cells.jsonl") if l.strip()]
rep = json.load(open(f"{SRC}/report.json"))
meta = json.load(open(f"{SRC}/run_meta.json"))
base = {(c["prompt"], c["seed"]): c for c in rows if c["gain"] == 0 and c["clip"].startswith("base0__")}
os.makedirs(os.path.join(STAGE, SUB), exist_ok=True)
clips, groups = {}, []
for p in PROMPT_LABEL:
    for t in TARGET_LABEL:
        for s in SEEDS:
            b = base[(p, s)]
            groups.append([p, t, s])
            for h, g in COLS:
                c = b if h == "base" else next((r for r in rows if r["head"] == h and r["prompt"] == p and r["target"] == t
                                                and r["seed"] == s and r["gain"] == g), None)
                if c is None:
                    continue
                m, mb = c["m"][t], b["m"][t]
                cid = f"{p}__{t}__s{s}__{h}__g{g}"
                dst = os.path.join(STAGE, SUB, c["clip"])
                if not os.path.exists(dst):
                    shutil.copy2(os.path.join(SRC, c["clip"]), dst)
                clips[cid] = {"f": f"{SUB}/{c['clip']}", "head": h, "gain": g,
                              "dmid": round(m["mid"]["fcos"] - mb["mid"]["fcos"], 3) if h != "base" else None,
                              "dbass": round(m["bass"]["fcos"] - mb["bass"]["fcos"], 3) if h != "base" else None}
DATA = json.dumps({"prompt_label": PROMPT_LABEL, "target_label": TARGET_LABEL, "head_label": HEAD_LABEL, "cols": COLS,
                   "groups": groups, "clips": clips, "ladder": rep["ladder"], "paired": rep["paired"]})

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
 npx.textContent=id.split('__').slice(0,3).join(' · ')+' — '+(c.head==='base'?'no steering':D.head_label[c.head]+', gain '+c.gain);au.src=c.f;
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
h+='<h2>2 · Listen</h2><div class=muted>Each row is one prompt, target and seed; the first button is the same render with no steering. Button label = change in mid-band chroma match.</div>';
Object.keys(D.prompt_label).forEach(p=>{h+=`<h3>${D.prompt_label[p]}</h3><table><tr><th>target · seed</th>`+
 D.cols.map(([hd,g])=>`<th>${hd==='base'?'no steering':(D.head_label[hd]||hd)+'<br>gain '+g}</th>`).join('')+'</tr>';
 D.groups.filter(x=>x[0]===p).forEach(([pp,t,s])=>{h+=`<tr><td class=l>${D.target_label[t]} · s${s}</td>`+
  D.cols.map(([hd,g])=>{const id=`${pp}__${t}__s${s}__${hd}__g${g}`;return `<td>${btn(id,hd==='base'?'▶':f(D.clips[id]?.dmid,2))}</td>`;}).join('')+'</tr>';});
 h+='</table>';});
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
