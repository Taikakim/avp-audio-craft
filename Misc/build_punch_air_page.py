#!/usr/bin/env python3
# Owner: GHOST-NOTE (created 2026-10-14)
"""build_punch_air_page.py -- static listening page for the punch DoRA steering set: 64 seeds x {original, bass+body RMS heads, + air-band head at 4 targets}.

Kim 2026-10-14: "add renders from all batches to the eval page and tell W to put it online". Built from the rating server's data dir (manifest.json, metrics.json,
air_escalate.json). Three-audience standard (eval-tables spec s14): same-playhead cells (switching keeps the position), a per-cell DSP delta line, and a plain-language
explainer. Steered clips are the LEVEL-MATCHED versions (steered scaled to the original's RMS, peak guard 0.97) so loudness is not what you hear. Rating (1-5) lives on the
local rating server; this page is for listening and comparing. No checkpoint filenames or drive paths are written (public-page redaction seam).
Run: python3 Misc/build_punch_air_page.py -> ~/evals_aac/punch_air.html (+ ~/evals_aac/punch_air/*.m4a, AAC 256k)
"""
import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comment_notes_block import notes_block

DATA_DIR = "/run/media/kim/Mantu2/sa3_control_runs/punch_rating_20261014"
STAGE = os.path.join(os.path.expanduser("~"), "evals_aac")
OUT = os.path.join(STAGE, "punch_air")
os.makedirs(OUT, exist_ok=True)
man = json.load(open(f"{DATA_DIR}/manifest.json"))["entries"]
met = json.load(open(f"{DATA_DIR}/metrics.json"))
esc = json.load(open(f"{DATA_DIR}/air_escalate.json"))
ARMS = [("cleanest", "bass+body"), ("cleanest_air", "+air −30 dB (median)"), ("cleanest_air2", "+air −10 dB"), ("cleanest_air3", "+air 0 dB"), ("cleanest_air4", "+air +10 dB")]
jobs, seeds = [], {}
for e in man:
    if e.get("latch_scale") != 1 or e.get("dora_strength") != 0.45 or e.get("steps") != 30 or e["preset"] not in dict(ARMS):
        continue
    s = seeds.setdefault(e["seed"], {})
    s["orig"] = {"f": f"punch_air/{e['base'][:-4]}.m4a", "src": f"{DATA_DIR}/clips/{e['base']}"}
    d = (met.get(e["id"]) or {}).get("delta") or {}
    s[e["preset"]] = {"f": f"punch_air/{e['id']}.m4a", "src": f"{DATA_DIR}/clips/{e['matched']}", "centroid": d.get("centroid"), "flat": d.get("flatness"), "crest": d.get("crest"),
                      "zcr": d.get("zcr")}
for sd in seeds.values():
    for c in sd.values():
        jobs.append((c["src"], f"{STAGE}/{c['f']}"))


def enc(j):
    src, dst = j
    if not os.path.exists(dst):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-c:a", "aac", "-b:a", "256k", dst], check=True)


with ThreadPoolExecutor(8) as ex:
    list(ex.map(enc, jobs))
final = {int(k): v[-1]["preset"] for k, v in esc.items()}
rows = []
for sd in sorted(seeds):
    r = {"seed": sd, "final": final.get(sd)}
    for k, c in seeds[sd].items():
        r[k] = {x: c[x] for x in c if x != "src"}
    rows.append(r)
DATA = json.dumps({"rows": rows, "arms": ARMS})
T = r"""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Punch Steering Air Head</title><style>
body{font:13px system-ui;margin:0;background:#0e0e10;color:#e0e0e0;max-width:1300px}
#bar{position:sticky;top:0;background:#16181c;padding:7px 12px;border-bottom:1px solid #2a2a30;z-index:9}
#wrap{padding:14px}h1{font-size:18px}.muted{color:#888}
.explain{background:#1a140c;border:1px solid #433;border-left:3px solid #d90;padding:10px 12px;font-size:12.5px;color:#dcd;margin:10px 0}.explain b{color:#fc6}
table{border-collapse:collapse;font-size:12px;margin:4px 0;display:block;overflow-x:auto}td,th{border:1px solid #2a2a30;padding:4px 8px;text-align:center;white-space:nowrap}
th{background:#1c1c22;color:#aaa}td:first-child,th:first-child{text-align:left;color:#9ab}
.c{cursor:pointer;font-variant-numeric:tabular-nums}.c:hover{outline:2px solid #7cf}.play{outline:2px solid #5d5 !important}.loading{outline:2px solid #fa5 !important}
.num{font-size:10.5px;color:#9a9;display:block}.fin{background:#142414}.un{color:#e44;font-weight:bold;cursor:help}
</style></head><body>
<div id=bar>&#9654; <b id=np>click a cell to play</b> <span id=pos class=muted></span> <span id=ld style="color:#fa5"></span> <span class=muted>· switching keeps the playhead · loops until stopped</span></div>
<div id=wrap><h1>Punch steering: adding a high-frequency head</h1>
<div class=explain><b>What this tests.</b> One DoRA-finetuned model, 64 seeds. Two LatCH guidance heads (bass and body band RMS) make the output rounder and fuller but also darker.
A third head steers the <i>air band</i> (2.5&nbsp;kHz and up, RMS in dB) toward a target level; the columns raise that target from the training-set median (&minus;30&nbsp;dB) to +10&nbsp;dB.
<b>How to read it.</b> Each row is one seed; every cell is the same seed and DoRA strength, steered clips are level-matched to the original so loudness is not what you hear. Under each cell:
&Delta; spectral centroid (Hz), &Delta; flatness, &Delta; crest factor versus the original. <b>The green column is the target the automatic loop settled on</b> for that seed (first target whose
high-band share is within 1&nbsp;dB of the original). <b>What the numbers cannot tell you:</b> whether it sounds better. Crest and flatness are screens; the judgement is by ear. Rated locally 1&ndash;5 by the project owner; <span class=un title="No listening verdict recorded yet (unaudited).">&#10071;</span> = no verdict recorded yet.</div>
<div id=out></div></div><audio id=au_el></audio>
<script>const D=__DATA__;
const au=document.getElementById('au_el'),npx=document.getElementById('np');let cur=null;au.loop=true;
au.addEventListener('timeupdate',()=>{document.getElementById('pos').textContent=cur?('· '+au.currentTime.toFixed(1)+'s'):'';});
au.addEventListener('waiting',()=>{document.getElementById('ld').textContent='loading…';markLoading(true);});
au.addEventListener('playing',()=>{document.getElementById('ld').textContent='';markLoading(false);});
function mark(){document.querySelectorAll('.c.play').forEach(e=>e.classList.remove('play'));if(cur){const e=document.getElementById(cur);if(e)e.classList.add('play');}}
function markLoading(on){document.querySelectorAll('.c.loading').forEach(e=>e.classList.remove('loading'));if(on&&cur){const e=document.getElementById(cur);if(e)e.classList.add('loading');}}
function startClip(id,f,l,clip){
 if(window.noteSet)noteSet({model:'punch_air',ckpt:'',clip:clip});
 const pos=(cur!==null&&!au.paused)?au.currentTime:0;cur=id;mark();npx.textContent='▶ '+l;
 document.getElementById('ld').textContent='loading…';markLoading(true);
 au.src=f;const go=()=>{try{au.currentTime=((au.duration&&pos>au.duration-1)?0:Math.min(pos,(au.duration||1e9)-0.05));}catch(e){}au.play();};
 if(au.readyState>=1)go();else au.addEventListener('loadedmetadata',go,{once:true});}
function play(id,f,l,clip){if(cur===id){au.pause();cur=null;mark();npx.textContent='stopped';document.getElementById('ld').textContent='';return;}startClip(id,f,l,clip);}
const sg=(v,d)=>v==null?'':(v>=0?'+':'')+v.toFixed(d);
let h='<table><tr><th>seed</th><th>original</th>'+D.arms.map(a=>`<th>${a[1]}</th>`).join('')+'</tr>';
D.rows.forEach(r=>{
 h+=`<tr><td>${r.seed}</td><td class=c id="o${r.seed}" onclick="play('o${r.seed}','${r.orig.f}','${r.seed} original','${r.seed}_orig')">&#9654; original</td>`;
 D.arms.forEach(([k,l])=>{const c=r[k];if(!c){h+='<td>·</td>';return;}
  const id=`${k}_${r.seed}`;
  h+=`<td class="c ${r.final===k?'fin':''}" id="${id}" onclick="play('${id}','${c.f}','${r.seed} ${l}','${r.seed}_${k}')">&#9654; ${l}<span class=num>${sg(c.centroid,0)} Hz · flat ${sg(c.flat,3)} · crest ${sg(c.crest,2)}</span></td>`;});
 h+='</tr>';});
document.getElementById('out').innerHTML=h+'</table>';
</script>
__NOTES__
<footer style="margin:18px 12px;color:#666;font-size:11px">evals &middot; punch steering air head &middot; clips and metrics: sa3_control_runs/punch_rating (internal)</footer>
</body></html>"""
T = T.replace("__NOTES__", notes_block("punch_air", levels=[("clip", "this clip"), ("page", "page")], hint="click a cell, then note what you hear"))
open(os.path.join(STAGE, "punch_air.html"), "w").write(T.replace("__DATA__", DATA))
sz = sum(os.path.getsize(f"{OUT}/{f}") for f in os.listdir(OUT)) / 1e6
print(f"wrote punch_air.html: {len(rows)} seeds, {len(jobs)} clips, {sz:.0f} MB")
