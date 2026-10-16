#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-16)
# Last edited: WINTERMUTE 2026-10-16 — per-arm gain x request grids for the extension
"""build_film_bracket_check_page.py -- listening page for eval/film_bracket_density_check.py (EXPERIMENTS E12).

The three modular-optimizer FiLM bracket arms (lr 3e-4 / 1e-3 / 3e-3, 6000 steps) and the shipped FiLM, each as the FiLM adapter
on "psytrance, 140 bpm" (base model, 20 s, 2 seeds), at FiLM gain 1.0 and 1.75 and requests of 3 and 9 onsets/s. Per arm and gain:
the spread (measured at 9 minus at 3) and the highest final-latent level relative to the unguided seed (the saturation screen).
Shows which arm the chain picked for the 54k full run. Writes ~/evals_aac/film_bracket_check.html (clips in film_bracket_check/).
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from comment_notes_block import notes_block
from float_player import inject

SRC = "/run/media/kim/Mantu/sa3_control_runs/film_bracket_density_check_20261016"
STAGE = os.path.join(os.path.expanduser("~"), "evals_aac")
SUB = "film_bracket_check"
os.makedirs(f"{STAGE}/{SUB}", exist_ok=True)
rows = [json.loads(l) for l in open(f"{SRC}/cells.jsonl") if l.strip()]
for c in rows:
    dst = f"{STAGE}/{SUB}/{c['id']}.m4a"
    if not os.path.exists(dst):
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", f"{SRC}/{c['id']}.wav", "-c:a", "aac", "-b:a", "128k", dst], check=True)
    c["f"] = f"{SUB}/{c['id']}.m4a"
pick = json.load(open(f"{SRC}/pick.json")) if os.path.exists(f"{SRC}/pick.json") else {}
meta = json.load(open(f"{SRC}/run_meta.json"))
LABEL = {"lr3e-4": "modular lr 3e-4", "lr1e-3": "modular lr 1e-3", "lr3e-3": "modular lr 3e-3", "shipped": "shipped FiLM (FusionOpt, 54k steps)"}
DATA = json.dumps({"rows": rows, "pick": pick, "label": LABEL})
T = r"""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>FiLM Bracket Check</title><style>
body{font:13px system-ui;margin:0;background:#0e0e10;color:#e0e0e0}#bar{position:sticky;top:0;background:#16181c;padding:7px 12px;border-bottom:1px solid #2a2a30;z-index:9}
#wrap{padding:14px;max-width:1200px}h1{font-size:18px}.muted{color:#888}
.explain{background:#1a140c;border:1px solid #433;border-left:3px solid #d90;padding:10px 12px;font-size:12.5px;color:#dcd;margin:10px 0;line-height:1.45}.explain b{color:#fc6}
table{border-collapse:collapse;font-size:12px;margin:6px 0;display:block;overflow-x:auto}td,th{border:1px solid #2a2a30;padding:4px 6px;text-align:center;white-space:nowrap;vertical-align:top}
th{background:#1c1c22;color:#aaa}td:first-child{text-align:left;color:#9ab}.pk{color:#7d7;font-weight:bold}
.b{display:inline-block;cursor:pointer;border:1px solid #333;border-radius:3px;padding:0 3px;margin:1px;font-size:10.5px;background:#18181c}.b:hover{outline:1px solid #7cf}.play{outline:2px solid #5d5 !important}.un{color:#e44;font-weight:bold}
</style></head><body><div id=bar>&#9654; <b id=np>click a clip to play</b> <span id=pos class=muted></span> <span class=muted>· switching keeps the playhead · re-click stops</span></div>
<div id=wrap><h1>FiLM density adapter: modular-optimizer bracket vs the shipped FiLM</h1>
<div class=explain><b>Why this page exists.</b> The FiLM density adapter was retrained under the modular optimizer at three learning rates (6000 steps each);
the training loss is the same for all three and cannot see control, so this checks what each actually does to onset density. The arm with the largest clean
spread at FiLM gain 1.0 was picked for the overnight 54 000-step run. <b>How to read it.</b> Per arm and FiLM gain: spread = measured onsets/s for the 9/s request
minus the 3/s request (2 seeds). Below it, one grid per arm: FiLM gain down, request across; each button = seed · measured onsets/s · final-latent level
vs the unguided seed (red above 1.3 = saturation risk). The grids were extended after the first listen (the weight, not the request, drives the change).
<b>What it cannot tell you.</b> Whether the style pull is smaller than the shipped FiLM's: that needs the E7 contexts, after the full run. __UN__</div>
<div id=out></div></div><audio id=au_el></audio>
<script>const D=__DATA__;const au=document.getElementById('au_el'),npx=document.getElementById('np');let cur=null;
au.addEventListener('timeupdate',()=>{document.getElementById('pos').textContent=cur?('· '+au.currentTime.toFixed(1)+'s'):'';});au.addEventListener('ended',()=>{cur=null;mark();});
function mark(){document.querySelectorAll('.b.play').forEach(e=>e.classList.remove('play'));if(cur){const e=document.getElementById(cur);if(e)e.classList.add('play');}}
function play(id,f){if(cur===id){au.pause();cur=null;mark();npx.textContent='stopped';return;}if(window.noteSet)noteSet({model:'film_bracket_check',ckpt:'',clip:id});
 const pos=(cur!==null&&!au.paused)?au.currentTime:0;cur=id;mark();npx.textContent=id;au.src=f;const go=()=>{try{au.currentTime=Math.min(pos,(au.duration||1e9)-0.05);}catch(e){}au.play();};
 if(au.readyState>=1)go();else au.addEventListener('loadedmetadata',go,{once:true});}
const btn=(c,l)=>`<span class=b id="${c.id}" onclick="play('${c.id}','${c.f}')">${l}</span>`;
const S=(D.pick&&D.pick.summary)||{};let h='<div class=muted>unguided: '+D.rows.filter(r=>!r.arm).map(r=>btn(r,`&#9654; s${r.seed} → ${r.onsets}/s`)).join(' ')+'</div>';
if(D.pick&&D.pick.pick)h+=`<p>Picked for the full run: <span class=pk>${D.label[D.pick.pick]}</span> (${D.pick.rule})</p>`;
h+='<h2 style="font-size:14px">Summary: spread (9/s request minus 3/s)</h2><table><tr><th>arm</th><th>FiLM gain 1.0</th><th>FiLM gain 1.75</th></tr>';
Object.keys(D.label).forEach(a=>{const s=S[a]||{spread:{}};h+=`<tr><td class="${D.pick.pick===a?'pk':''}">${D.label[a]}</td><td>${(s.spread||{}).g1??'–'}/s</td><td>${(s.spread||{})['g1.75']??'–'}/s</td></tr>`;});
h+='</table>';
const base={};D.rows.filter(r=>!r.arm).forEach(r=>base[r.seed]=r.z_std);
Object.keys(D.label).forEach(a=>{const rs=D.rows.filter(r=>r.arm===a);if(!rs.length)return;
 const gs=[...new Set(rs.map(r=>r.gain))].sort((x,y)=>x-y),ds=[...new Set(rs.map(r=>r.dens))].sort((x,y)=>x-y);
 h+=`<h2 style="font-size:14px" class="${D.pick.pick===a?'pk':''}">${D.label[a]}</h2><table><tr><th>FiLM gain</th>`+ds.map(d=>`<th>request ${d}/s</th>`).join('')+'</tr>';
 gs.forEach(g=>{h+=`<tr><td>${g}</td>`+ds.map(d=>'<td>'+rs.filter(r=>r.gain===g&&r.dens===d).sort((x,y)=>x.seed-y.seed).map(c=>{const z=c.z_std&&base[c.seed]?c.z_std/base[c.seed]:null;
  return btn(c,`s${c.seed} ${c.onsets}/s`+(z?` ·<span style="color:${z>1.3?'#e66':'#888'}">×${z.toFixed(2)}</span>`:''));}).join('<br>')+'</td>').join('')+'</tr>';});
 h+='</table>';});
document.getElementById('out').innerHTML=h;</script>
__NOTES__
<footer style="margin:18px 12px;color:#666;font-size:11px">evals &middot; FiLM modular-optimizer bracket (EXPERIMENTS E12) &middot; clips: sa3_control_runs (internal)</footer></body></html>"""
UN = "" if meta.get("kim_feedback") else '<span class=un>&#10071;</span> No listening verdict recorded yet.'
T = T.replace("__UN__", UN).replace("__NOTES__", notes_block("film_bracket_check", levels=[("clip", "this clip"), ("page", "page")], hint="click a clip, then note what you hear"))
open(f"{STAGE}/film_bracket_check.html", "w").write(inject(T.replace("__DATA__", DATA)))
print(f"wrote {STAGE}/film_bracket_check.html ({len(rows)} clips)")
