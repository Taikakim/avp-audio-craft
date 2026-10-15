#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-16)
"""build_punch_grain_test_page.py -- blind listening test for the punch DoRA "grainy mode" prediction.

eval/punch_seed_latent_stats.py ranked the 64 punch seeds by how strongly the DoRA (k5 ep19 @ 0.45) smooths each seed's latent
(dora_smoothing_rank_20261015.json). Seed 764, the one that turned grainy, ranks 4/64. Prediction: the top-5 seeds (excluding 764) sound
grainy with the DoRA, the bottom-5 (excluding 3050) clean. 10 seeds in a fixed shuffled order, each as no-DoRA | DoRA (no LatCH); the prediction is hidden
until revealed. 764 and 3050 are labelled references. Writes ~/evals_aac/punch_grain_test.html (clips in punch_grain_test/).
"""
import json
import os
import random
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from comment_notes_block import notes_block
from float_player import inject

RUNS = "/run/media/kim/Mantu/sa3_control_runs"
RATING = f"{RUNS}/punch_rating_20261014"
NODORA = f"{RUNS}/punch_nodora_seeds_20261015"
STAGE = os.path.join(os.path.expanduser("~"), "evals_aac")
SUB = "punch_grain_test"
os.makedirs(f"{STAGE}/{SUB}", exist_ok=True)
rank = json.load(open(f"{RATING}/dora_smoothing_rank_20261015.json"))["ranking"]
order = [s for s, _ in rank]
pos = {s: i + 1 for i, s in enumerate(order)}
grainy = [s for s in order if s != 764][:5]
clean = [s for s in order if s != 3050][-5:]
test = grainy + clean
random.Random(20261016).shuffle(test)


def enc(src, name):
    dst = f"{STAGE}/{SUB}/{name}.m4a"
    if not os.path.exists(dst):
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", src, "-c:a", "aac", "-b:a", "128k", dst], check=True)
    return f"{SUB}/{name}.m4a"


def row(s, label, pred):
    return {"seed": s, "label": label, "pred": pred, "rank": pos[s],
            "nodora": enc(f"{NODORA}/nodora_s{s}.wav", f"nodora_s{s}"),
            "dora": enc(f"{RATING}/clips/base_s{s}_d0.45_n30.wav", f"dora_s{s}")}


rows = [row(s, f"#{i + 1}", "grainy" if s in grainy else "clean") for i, s in enumerate(test)]
refs = [row(764, "ref 764 (turned grainy)", "reference"), row(3050, "ref 3050 (stayed clean)", "reference")]
meta = {"purpose": __doc__.split("Writes")[0].strip(), "grainy_predicted": grainy, "clean_predicted": clean, "order": test,
        "sources": [RATING, NODORA], "kim_feedback": None}
json.dump(meta, open(f"{STAGE}/{SUB}/run_meta.json", "w"), indent=1)
DATA = json.dumps({"rows": rows, "refs": refs})
T = r"""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Punch Grain Test</title><style>
body{font:13px system-ui;margin:0;background:#0e0e10;color:#e0e0e0}#bar{position:sticky;top:0;background:#16181c;padding:7px 12px;border-bottom:1px solid #2a2a30;z-index:9}
#wrap{padding:14px;max-width:900px}h1{font-size:18px}h2{font-size:14px;color:#aaa;margin-top:18px}.muted{color:#888}.explain{background:#1a140c;border:1px solid #433;border-left:3px solid #d90;padding:10px 12px;font-size:12.5px;color:#dcd;margin:10px 0;line-height:1.45}.explain b{color:#fc6}
table{border-collapse:collapse;font-size:12px;margin:6px 0}td,th{border:1px solid #2a2a30;padding:5px 8px;text-align:center}th{background:#1c1c22;color:#aaa}td:first-child{text-align:left;color:#9ab}
.b{display:inline-block;cursor:pointer;border:1px solid #333;border-radius:3px;padding:2px 6px;background:#18181c}.b:hover{outline:1px solid #7cf}.play{outline:2px solid #5d5 !important}.un{color:#e44;font-weight:bold}
.pred{display:none}.show .pred{display:table-cell}button{background:#222;color:#ddd;border:1px solid #444;border-radius:3px;padding:4px 10px;cursor:pointer}
</style></head><body><div id=bar>&#9654; <b id=np>click a clip to play</b> <span id=pos class=muted></span> <span class=muted>· switching keeps the playhead · re-click stops</span></div>
<div id=wrap><h1>Punch DoRA: does it make these seeds grainy?</h1>
<div class=explain><b>Why this page exists.</b> The punch DoRA smooths every seed's latent in the same direction, but by different amounts. Seed 764, the one
that turned grainy, gets one of the largest shifts (4th of 64). The measurement predicts five of these ten seeds go grainy with the DoRA and five stay clean.
Each row: the seed without the DoRA, then with it (DoRA 0.45, no LatCH). <b>Listen first, note which ones sound grainy, then reveal.</b> __UN__</div>
<h2>References</h2><div id=refs></div><h2>Blind set</h2><div id=out></div><p><button onclick="document.getElementById('wrap').classList.add('show')">Reveal prediction</button></p></div><audio id=au_el></audio>
<script>const D=__DATA__;const au=document.getElementById('au_el'),npx=document.getElementById('np');let cur=null;
au.addEventListener('timeupdate',()=>{document.getElementById('pos').textContent=cur?('· '+au.currentTime.toFixed(1)+'s'):'';});au.addEventListener('ended',()=>{cur=null;mark();});
function mark(){document.querySelectorAll('.b.play').forEach(e=>e.classList.remove('play'));if(cur){const e=document.getElementById(cur);if(e)e.classList.add('play');}}
function play(id,f){if(cur===id){au.pause();cur=null;mark();npx.textContent='stopped';return;}if(window.noteSet)noteSet({model:'punch_grain_test',ckpt:'',clip:id});
 const pos=(cur!==null&&!au.paused)?au.currentTime:0;cur=id;mark();npx.textContent=id;au.src=f;const go=()=>{try{au.currentTime=Math.min(pos,(au.duration||1e9)-0.05);}catch(e){}au.play();};
 if(au.readyState>=1)go();else au.addEventListener('loadedmetadata',go,{once:true});}
const b=(id,f,l)=>`<span class=b id="${id}" onclick="play('${id}','${f}')">${l}</span>`;
function tab(rs,blind){let h='<table><tr><th>seed</th><th>no DoRA</th><th>with DoRA</th>'+(blind?'<th class=pred>prediction (smoothing rank /64)</th>':'')+'</tr>';
 rs.forEach(r=>{const id=blind?r.label.replace('#','t'):'s'+r.seed;h+=`<tr><td>${r.label}</td><td>${b(id+'_n',r.nodora,'&#9654; no DoRA')}</td><td>${b(id+'_d',r.dora,'&#9654; DoRA')}</td>`+(blind?`<td class=pred>${r.pred}, seed ${r.seed} (${r.rank})</td>`:'')+'</tr>';});return h+'</table>';}
document.getElementById('refs').innerHTML=tab(D.refs,false);document.getElementById('out').innerHTML=tab(D.rows,true);</script>
__NOTES__
<footer style="margin:18px 12px;color:#666;font-size:11px">evals &middot; punch DoRA grain test &middot; clips: internal</footer></body></html>"""
UN = '<span class=un>&#10071;</span> No listening verdict recorded yet.'
T = T.replace("__UN__", UN).replace("__NOTES__", notes_block("punch_grain_test", levels=[("clip", "this clip"), ("page", "page")], hint="click a clip, then note what you hear"))
open(f"{STAGE}/punch_grain_test.html", "w").write(inject(T.replace("__DATA__", DATA)))
print(f"wrote {STAGE}/punch_grain_test.html ({len(rows)} blind + {len(refs)} refs)")
