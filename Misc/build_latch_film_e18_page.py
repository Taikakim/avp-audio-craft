#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-25)
"""build_latch_film_e18_page.py -- listening card for EXPERIMENTS E18 (smooth FiLM -> LatCH hand-off, tapered LatCH end).

Reads the E18 run dir (cells.jsonl, report.json from eval/latch_film_e18_report.py, run_meta.json). Page:
  1 summary per arm: onsets/s at 3/6/9, range (9 minus 3), CLAP drift to the unguided render, dCE, gate fails
  2 the hand-off card: per context x seed, A1 / A2 / A3 next to each other per density (hard end vs exp tail vs full window)
  3 every arm per context x seed (rows) x density (columns), unguided first
  4 arm 6: a real onsets-per-beat curve vs a constant at its mean, with corr(local onset rate, target curve)
Writes ~/evals_aac/latch_film_e18.html (clips under ~/evals_aac/latch_film_e18/). No checkpoint filenames or drive paths.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from comment_notes_block import notes_block
from float_player import inject

SRC = "/run/media/kim/Mantu/sa3_control_runs/latch_film_e18_20261025"
STAGE = os.path.join(os.path.expanduser("~"), "evals_aac")
SUB = "latch_film_e18"
CTX_LABEL = {"base": "psytrance, 140 bpm", "house": "deep house, 122 bpm (far from the training style)"}
ARM_LABEL = {
    "film": "FiLM only, constant",
    "A1": "LatCH, whole run (the clean reference)",
    "A2": "LatCH, stops hard at 80%",
    "A3": "LatCH, exp fade-out over the last 20%",
    "A4a": "FiLM to 20% → linear crossfade 20–40% → LatCH → exp fade 80–100%",
    "A4b": "same as A4a, raised-cosine crossfade",
    "A4c": "FiLM to 20% → raised-cosine crossfade 20–80% → exp fade 80–100%",
    "A5": "FiLM + LatCH together, constant (earlier best)",
}

rows = [json.loads(l) for l in open(f"{SRC}/cells.jsonl") if l.strip()]
rep = json.load(open(f"{SRC}/report.json"))
meta = json.load(open(f"{SRC}/run_meta.json"))
drift = json.load(open(f"{SRC}/clap.json"))["drift"]
for c in rows:
    c["f"] = f"{SUB}/{c['ctx']}/{c['id']}.m4a"
    c["drift"] = drift.get(c["id"])
clips = {c["id"]: {k: c.get(k) for k in ("id", "f", "ctx", "seed", "arm", "dens", "onsets", "drift")} for c in rows}
groups = sorted({(c["ctx"], c["seed"]) for c in rows})
DATA = json.dumps({"ctx_label": CTX_LABEL, "arm_label": ARM_LABEL, "arms": list(ARM_LABEL), "groups": groups,
                   "clips": clips, "rep": rep})

T = r"""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>FiLM LatCH Hand-off</title><style>
body{font:13px system-ui;margin:0;background:#0e0e10;color:#e0e0e0}
#bar{position:sticky;top:0;background:#16181c;padding:7px 12px;border-bottom:1px solid #2a2a30;z-index:9}
#wrap{padding:14px 16px;max-width:1400px}h1{font-size:18px}h2{font-size:15px;margin:26px 0 4px;color:#cde}h3{font-size:13px;margin:14px 0 4px;color:#abc}.muted{color:#888}
.explain{background:#1a140c;border:1px solid #433;border-left:3px solid #d90;padding:10px 12px;font-size:12.5px;color:#dcd;margin:10px 0;line-height:1.45}.explain b{color:#fc6}
table{border-collapse:collapse;font-size:12px;margin:4px 0;display:block;overflow-x:auto}td,th{border:1px solid #2a2a30;padding:4px 6px;text-align:center;white-space:nowrap}
th{background:#1c1c22;color:#aaa}td.l{text-align:left;color:#9ab;white-space:normal;min-width:180px}
.num{font-variant-numeric:tabular-nums}.good{color:#7d7}
.b{display:inline-block;cursor:pointer;border:1px solid #333;border-radius:3px;padding:1px 4px;margin:1px;font-size:11px;font-variant-numeric:tabular-nums;background:#18181c}
.b:hover{outline:1px solid #7cf}.play{outline:2px solid #5d5 !important}.un{color:#e44;font-weight:bold;cursor:help}
</style></head><body>
<div id=bar>&#9654; <b id=np>click a clip to play</b> <span id=pos class=muted></span> <span class=muted>· switching keeps the playhead · re-click stops</span></div>
<div id=wrap><h1>Handing density control from FiLM to LatCH, and fading LatCH out</h1>
<div class=explain><b>Why this page exists.</b> LatCH guidance that switches off abruptly sounded bad in the GUI. Under the default weighting a LatCH
window's per-step weight grows toward its end, so a hard stop cuts it at its strongest step. E18 tests two fixes: an exponential fade-out at the end
of the LatCH window (A3 against the hard stop A2), and a full hand-off that starts with the FiLM adapter (wide range), crossfades into LatCH (transparent)
and fades LatCH out (A4a/b/c, against FiLM and LatCH together at full strength, A5).
<b>How to read it.</b> Every arm asks for 3, 6 and 9 onsets per second; buttons read request → measured. <b>Range</b> = measured at 9 minus measured at 3.
<b>Drift</b> = CLAP embedding distance from the same seed rendered with no guidance (how far the character moved); the two unguided seeds of a context
differ by the "seed reference". The fades act on the <i>sampling steps</i>, not on time in the clip, so there is no seam at a point in the audio:
listen for a clip-wide change in texture (grit, brightness, a smeared or brittle top end). All renders use the goa finetune, 50 steps, LatCH gain 512, FiLM gain 1.
<b>What it cannot tell you.</b> Whether it sounds good; onset counts and CLAP are screens. __UN__</div>
<div id=out></div></div><audio id=au_el></audio>
<script>const D=__DATA__;
const au=document.getElementById('au_el'),npx=document.getElementById('np');let cur=null;
au.addEventListener('timeupdate',()=>{document.getElementById('pos').textContent=cur?('· '+au.currentTime.toFixed(1)+'s'):'';});
au.addEventListener('ended',()=>{cur=null;mark();});
function mark(){document.querySelectorAll('.b.play').forEach(e=>e.classList.remove('play'));if(cur){document.querySelectorAll('[data-id="'+cur+'"]').forEach(e=>e.classList.add('play'));}}
function play(id){const c=D.clips[id];if(cur===id){au.pause();cur=null;mark();npx.textContent='stopped';return;}
 if(window.noteSet)noteSet({model:'latch_film_e18',ckpt:'',clip:id});
 const pos=(cur!==null&&!au.paused)?au.currentTime:0;cur=id;mark();npx.textContent=id+(c.arm in D.arm_label?' — '+D.arm_label[c.arm]:'');au.src=c.f;
 const go=()=>{try{au.currentTime=Math.min(pos,(au.duration||1e9)-0.05);}catch(e){}au.play();};
 if(au.readyState>=1)go();else au.addEventListener('loadedmetadata',go,{once:true});}
const f=(v,d)=>v==null?'–':Number(v).toFixed(d);
const btn=(id,lbl)=>D.clips[id]?`<span class=b data-id="${id}" title="drift ${f(D.clips[id].drift,3)}" onclick="play('${id}')">${lbl}</span>`:'<span class=muted>–</span>';
const cid=(ctx,s,arm,d)=>`${ctx}_s${s}__${arm}`+(d?`_d${d}`:'');
let h='<h2>1 · Summary per arm</h2><div class=muted>mean over 2 contexts × 2 seeds; unguided onsets/s: '+
 Object.entries(D.rep.unguided_onsets).map(([k,v])=>`${k} ${v}`).join(', ')+' · seed reference drift: '+
 Object.entries(D.rep.clap_seed_reference).map(([k,v])=>`${k} ${v}`).join(', ')+'</div>';
h+='<table><tr><th>arm</th><th>3/s →</th><th>6/s →</th><th>9/s →</th><th>range</th><th>drift</th><th>range per drift</th><th>ΔCE</th><th>gate fails</th></tr>';
D.arms.forEach(a=>{const r=D.rep.arms[a];h+=`<tr><td class=l><b>${a}</b> ${D.arm_label[a]}</td><td class=num>${f(r.onsets[3],2)}</td><td class=num>${f(r.onsets[6],2)}</td><td class=num>${f(r.onsets[9],2)}</td>`+
 `<td class=num><b>${f(r.range,2)}</b></td><td class=num>${f(r.clap_drift,3)}</td><td class=num>${f(r.range/r.clap_drift,1)}</td><td class=num>${r.dce>=0?'+':''}${f(r.dce,2)}</td><td class=num>${r.gate_fail}/${r.gate_n}</td></tr>`;});
h+='</table>';
h+='<h2>2 · The hand-off card: full window vs hard stop vs exp tail</h2><div class=muted>Same seed and request in each column group. A2 and A3 have identical guidance up to 80% of the steps; only the last 20% differ. Listen for whether A2 (hard stop) leaves a texture A3 does not.</div>';
h+='<table><tr><th>context · seed</th>'+[3,6,9].map(d=>`<th>${d}/s: A1 · A2 · A3</th>`).join('')+'<th>unguided</th></tr>';
D.groups.forEach(([ctx,s])=>{h+=`<tr><td class=l>${D.ctx_label[ctx]} · s${s}</td>`+[3,6,9].map(d=>'<td>'+['A1','A2','A3'].map(a=>btn(cid(ctx,s,a,d),`${a} ${f(D.clips[cid(ctx,s,a,d)]?.onsets,1)}`)).join(' ')+'</td>').join('')+
 `<td>${btn(cid(ctx,s,'unguided'),'▶ '+f(D.clips[cid(ctx,s,'unguided')]?.onsets,1))}</td></tr>`;});
h+='</table>';
h+='<h2>3 · Every arm</h2>';
D.groups.forEach(([ctx,s])=>{h+=`<h3>${D.ctx_label[ctx]} · seed ${s} <span class=muted style="font-weight:normal">· unguided ${btn(cid(ctx,s,'unguided'),'▶ '+f(D.clips[cid(ctx,s,'unguided')]?.onsets,1)+'/s')}</span></h3>`;
 h+='<table><tr><th>arm</th><th>3/s</th><th>6/s</th><th>9/s</th></tr>'+D.arms.map(a=>`<tr><td class=l><b>${a}</b> ${D.arm_label[a]}</td>`+
  [3,6,9].map(d=>{const c=D.clips[cid(ctx,s,a,d)];return `<td>${btn(cid(ctx,s,a,d),`${d}→${f(c?.onsets,1)} · ${f(c?.drift,2)}`)}</td>`;}).join('')+'</tr>').join('')+'</table>';});
h+='<h2>4 · A real density curve as the LatCH target</h2><div class=muted>Target: a goa passage going from a breakdown (0.7 onsets per beat) into a 16th-note build (3.9 per beat), 20 s. Constant = LatCH asked for that curve\'s mean the whole time. corr = correlation of the render\'s onset rate over time (2 s window) with the target curve; unguided shows how much the music follows it by chance.</div>';
h+='<table><tr><th>context · seed</th><th>curve target</th><th>constant at its mean</th><th>unguided</th></tr>';
Object.entries(D.rep.arm6).forEach(([k,v])=>{const [ctx,ss]=k.split('_s');h+=`<tr><td class=l>${D.ctx_label[ctx]} · s${ss}</td>`+
 `<td>${btn(cid(ctx,ss,'A6curve'),'▶')} corr <b class=${v.corr_curve>0.5?'good':''}>${f(v.corr_curve,2)}</b></td><td>${btn(cid(ctx,ss,'A6const'),'▶')} corr ${f(v.corr_const,2)}</td><td>${btn(cid(ctx,ss,'unguided'),'▶')} corr ${f(v.corr_unguided,2)}</td></tr>`;});
h+='</table>';
document.getElementById('out').innerHTML=h;
</script>
__NOTES__
<footer style="margin:18px 12px;color:#666;font-size:11px">evals &middot; FiLM → LatCH hand-off (EXPERIMENTS E18) &middot; clips: sa3_control_runs (internal) &middot; gate: control-head disintegration gate vs the unguided render</footer>
</body></html>"""
UN = "" if meta.get("kim_feedback") else '<span class=un title="No listening verdict recorded yet (unaudited).">&#10071;</span> No listening verdict recorded yet.'
T = T.replace("__UN__", UN).replace(
    "__NOTES__", notes_block("latch_film_e18", levels=[("clip", "this clip"), ("page", "page")], hint="click a clip, then note what you hear"))
out = os.path.join(STAGE, "latch_film_e18.html")
open(out, "w").write(inject(T.replace("__DATA__", DATA)))
print(f"wrote {out}: {len(rows)} clips")
