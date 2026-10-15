#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-16)
"""build_dronesweep_rescale_page.py -- listening page for eval/dronesweep_rescale_decode.py.

The AVP drone sweep's force_scalar arms (fullft, EMA renders, ep7, cfg 7) run their final latent std to ~3 (healthy ~1.0-1.15).
Per latent: the original LUMI render, the same latent rescaled to std 1.1, and the same latent divided by 3, decoded again (no
re-render). Writes ~/evals_aac/dronesweep_rescale.html (clips in dronesweep_rescale/).
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from comment_notes_block import notes_block
from float_player import inject

SRC = "/run/media/kim/Mantu/sa3_control_runs/dronesweep_rescale_20261016"
PULL = "/home/kim/Projects/SAO/renders_pull/dronesweep"
STAGE = os.path.join(os.path.expanduser("~"), "evals_aac")
SUB = "dronesweep_rescale"
os.makedirs(f"{STAGE}/{SUB}", exist_ok=True)
meta = json.load(open(f"{SRC}/run_meta.json"))


def enc(src, name):
    dst = f"{STAGE}/{SUB}/{name}.m4a"
    if not os.path.exists(dst):
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", src, "-c:a", "aac", "-b:a", "128k", dst], check=True)
    return f"{SUB}/{name}.m4a"


groups = {}
for r in meta["rows"]:
    g = groups.setdefault(r["src"], {"src": r["src"], "z_std": r["z_std_in"]})
    g["orig"] = enc(f"{PULL}/{r['orig_wav']}", r["src"] + "__orig")
    g[r["variant"]] = enc(f"{SRC}/{r['file']}", r["file"][:-4])
rows = []
for k, g in groups.items():
    arm = "s1" if "_s1__" in k else "s2"
    pid = k.split("__w100__")[1].rsplit("__s", 1)[0]
    rows.append({**g, "arm": arm, "prompt": pid, "id": k})
DATA = json.dumps(sorted(rows, key=lambda r: (r["arm"], r["prompt"])))
T = r"""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Drone Sweep Rescale</title><style>
body{font:13px system-ui;margin:0;background:#0e0e10;color:#e0e0e0}#bar{position:sticky;top:0;background:#16181c;padding:7px 12px;border-bottom:1px solid #2a2a30;z-index:9}
#wrap{padding:14px;max-width:1100px}h1{font-size:18px}.muted{color:#888}.explain{background:#1a140c;border:1px solid #433;border-left:3px solid #d90;padding:10px 12px;font-size:12.5px;color:#dcd;margin:10px 0;line-height:1.45}.explain b{color:#fc6}
table{border-collapse:collapse;font-size:12px;margin:6px 0}td,th{border:1px solid #2a2a30;padding:5px 8px;text-align:center}th{background:#1c1c22;color:#aaa}td:first-child{text-align:left;color:#9ab}
.b{display:inline-block;cursor:pointer;border:1px solid #333;border-radius:3px;padding:2px 6px;background:#18181c}.b:hover{outline:1px solid #7cf}.play{outline:2px solid #5d5 !important}.un{color:#e44;font-weight:bold}
</style></head><body><div id=bar>&#9654; <b id=np>click a clip to play</b> <span id=pos class=muted></span> <span class=muted>· switching keeps the playhead · re-click stops</span></div>
<div id=wrap><h1>Drone sweep force_scalar: the runaway latents scaled back down</h1>
<div class=explain><b>Why this page exists.</b> The force_scalar full finetunes run their final latent's level to about 3 (a healthy render sits near 1.0-1.15),
at every cfg. Asked: would simply scaling the latents down help? Each row is one existing LUMI render (EMA weights, ep7, cfg 7): the original, the same latent
rescaled to a std of 1.1, and divided by 3, decoded again. Nothing was re-rendered. <b>What it cannot tell you.</b> Whether the content underneath is musical
only if it was: scaling fixes level, not content that ran off course. __UN__</div><div id=out></div></div><audio id=au_el></audio>
<script>const D=__DATA__;const au=document.getElementById('au_el'),npx=document.getElementById('np');let cur=null;
au.addEventListener('timeupdate',()=>{document.getElementById('pos').textContent=cur?('· '+au.currentTime.toFixed(1)+'s'):'';});au.addEventListener('ended',()=>{cur=null;mark();});
function mark(){document.querySelectorAll('.b.play').forEach(e=>e.classList.remove('play'));if(cur){const e=document.getElementById(cur);if(e)e.classList.add('play');}}
function play(id,f){if(cur===id){au.pause();cur=null;mark();npx.textContent='stopped';return;}if(window.noteSet)noteSet({model:'dronesweep_rescale',ckpt:'',clip:id});
 const pos=(cur!==null&&!au.paused)?au.currentTime:0;cur=id;mark();npx.textContent=id;au.src=f;const go=()=>{try{au.currentTime=Math.min(pos,(au.duration||1e9)-0.05);}catch(e){}au.play();};
 if(au.readyState>=1)go();else au.addEventListener('loadedmetadata',go,{once:true});}
const b=(id,f,l)=>f?`<span class=b id="${id}" onclick="play('${id}','${f}')">${l}</span>`:'–';
let h='<table><tr><th>arm · prompt</th><th>latent std</th><th>original</th><th>rescaled to 1.1</th><th>÷ 3</th></tr>';
D.forEach(r=>{h+=`<tr><td>force_scalar ${r.arm} · ${r.prompt}</td><td>${r.z_std.toFixed(2)}</td><td>${b(r.id+'_o',r.orig,'&#9654; original')}</td><td>${b(r.id+'_n',r['norm1.1'],'&#9654; 1.1')}</td><td>${b(r.id+'_d',r.div3,'&#9654; ÷3')}</td></tr>`;});
document.getElementById('out').innerHTML=h+'</table>';</script>
__NOTES__
<footer style="margin:18px 12px;color:#666;font-size:11px">evals &middot; AVP drone sweep, force_scalar rescale &middot; clips: internal</footer></body></html>"""
UN = "" if meta.get("kim_feedback") else '<span class=un>&#10071;</span> No listening verdict recorded yet.'
T = T.replace("__UN__", UN).replace("__NOTES__", notes_block("dronesweep_rescale", levels=[("clip", "this clip"), ("page", "page")], hint="click a clip, then note what you hear"))
open(f"{STAGE}/dronesweep_rescale.html", "w").write(inject(T.replace("__DATA__", DATA)))
print(f"wrote {STAGE}/dronesweep_rescale.html ({len(rows)} rows)")
