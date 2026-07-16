#!/usr/bin/env python3
"""build_e1_pilot_page.py — eval page for the E1 anti-loop steering pilot.

Kim's ask 2026-07-16 ("UI page for the loopy experiments"). Surfaces
sa3_control_runs/e1_pilot_20260716 (band-hinge recurrence guide, W's pilot on
the longform validation plan) as a same-playhead listening page: unguided
baselines vs the λ ladder at nl50/nl60, per-clip loop metrics + Δ-vs-baseline,
the lam1e7 ear-verdict clip highlighted. Glob-driven — rerun after new arms
land and they appear.

Redaction (MASTER §4): params/metrics/prompt = science, shown; checkpoint
FILENAMES + absolute paths = plumbing, described not named.

Run: python3 Misc/build_e1_pilot_page.py   (ffmpeg for m4a encode)
Output: ~/evals_aac/e1_pilot.html + ~/evals_aac/e1_pilot/*.m4a (W rsyncs).
"""
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comment_notes_block import notes_block

RUN = Path("/run/media/kim/Mantu/sa3_control_runs/e1_pilot_20260716")
BASE = Path("/run/media/kim/Mantu/sa3_lora_runs/a2a_kaikkialla_newstack")
STAGE = Path.home() / "evals_aac"
CLIPS = STAGE / "e1_pilot"
CLIPS.mkdir(parents=True, exist_ok=True)

meta = json.loads((RUN / "run_meta.json").read_text())
scores = json.loads((RUN / "pilot_scores.json").read_text())
rows = {r["clip"]: r for r in scores["rows"]}
baselines = scores["baselines"]

def enc(src: Path, dst: Path):
    if not dst.exists():
        subprocess.run(["ffmpeg", "-y", "-i", str(src), "-c:a", "aac",
                        "-b:a", "192k", str(dst)], capture_output=True)

jobs = []
cells = []
for wav in sorted(RUN.glob("e1_*.wav")):
    m = re.match(r"e1_nl(\d+)_lam([0-9e.]+?)(_edge34)?\.wav", wav.name)
    if not m:
        continue
    nl, lam, edge34 = int(m.group(1)), m.group(2), bool(m.group(3))
    m4a = CLIPS / (wav.stem + ".m4a")
    jobs.append((wav, m4a))
    s = rows.get(wav.name, {})
    cells.append({"nl": nl, "lam": lam, "lamv": float(lam.replace("e", "E")),
                  "edge34": edge34, "f": f"e1_pilot/{m4a.name}",
                  "clip": wav.name, **{k: s.get(k) for k in
                  ("r_max", "line_frac_16s", "l_max_sec", "det_soft",
                   "d_line_frac_16s", "d_l_max_sec")}})
for nl in (50, 60):
    src = BASE / f"a2a_nl{nl}.wav"
    if src.exists():
        m4a = CLIPS / f"baseline_nl{nl}.m4a"
        jobs.append((src, m4a))
        b = baselines[str(nl)]
        cells.append({"nl": nl, "lam": "0 (baseline)", "lamv": 0.0,
                      "edge34": None, "f": f"e1_pilot/{m4a.name}",
                      "clip": f"a2a_nl{nl}.wav (unguided)",
                      "r_max": round(b["r_max"], 3),
                      "line_frac_16s": round(b["line_frac_16s"], 3),
                      "l_max_sec": b["l_max_sec"],
                      "det_soft": round(b["det_soft"], 3),
                      "d_line_frac_16s": 0.0, "d_l_max_sec": 0.0})

with ThreadPoolExecutor(max_workers=8) as ex:
    list(ex.map(lambda j: enc(*j), jobs))
print(f"encoded {len(jobs)} clips -> {CLIPS}")

cells.sort(key=lambda c: (c["nl"], c["lamv"], c["edge34"] is False))
DATA = json.dumps(cells)
G = meta.get("guide", {})
recipe = (f"a2a re-render of one full goa track (source: {meta['track'].rsplit('.',1)[0]}), "
          f"prompt “{meta['prompt']}”, seed {meta['seed']}, steps {meta['steps']}, "
          f"cfg {meta['cfg']}, goa DoRA r16 (newstack) epoch 3 (internal checkpoint), "
          f"guide: built-in recurrence band-hinge, working edge {G.get('edge_q90', 0.34)}")

T = r"""<!doctype html><html><head><meta charset=utf-8><title>E1 pilot — anti-loop steering</title><style>
body{font:13px system-ui;margin:0;background:#0e0e10;color:#e0e0e0;max-width:1150px}
#bar{position:sticky;top:0;background:#16181c;padding:7px 12px;border-bottom:1px solid #2a2a30;z-index:9}
#wrap{padding:14px}h1{font-size:18px}h2{font-size:15px;color:#9cf;margin:20px 0 4px}.muted{color:#888}
#explain{background:#1a140c;border:1px solid #433;border-left:3px solid #d90;padding:10px 12px;font-size:12.5px;color:#dcd;margin:10px 0}#explain b{color:#fc6}
#recipe{background:#11161c;border:1px solid #243;border-left:3px solid #5d9;padding:8px 12px;font-size:12px;color:#cde;margin:8px 0}
table{border-collapse:collapse;font-size:12px;margin:6px 0;width:100%}td,th{border:1px solid #2a2a30;padding:4px 8px;text-align:center}
th{background:#1c1c22;color:#aaa}td:first-child{text-align:left}
.c{cursor:pointer}.c:hover{outline:2px solid #7cf}.play{outline:2px solid #5d5 !important}
.hero{outline:2px solid #d90}.dorm{color:#667}
</style></head><body>
<div id=bar>&#9654; <b id=np>click a row's ▶ to play</b> <span id=pos class=muted></span> <span class=muted>· switching keeps the playhead · re-click stops</span></div>
<div id=wrap>
<h1>E1 pilot — anti-loop steering (recurrence band-hinge guide)</h1>
<div id=explain><b>What this tests:</b> long a2a re-renders of a full track tend to fall into a <b>loop attractor</b> — the model finds a phrase and repeats it. This pilot steers sampling away from self-repetition with a gradient guide on a recurrence statistic (penalized only above a "too repetitive" edge), at increasing guide strength λ.
<br><b>How to listen:</b> start with the <b>baseline</b> row of each section, then walk up the λ ladder <i>at the same playhead</i>. The metrics: <b>line_frac 16s</b> = fraction of the render that is part of a ≥16 s repeat (lower = less looping); <b>l_max</b> = longest repeated stretch in seconds. The λ=1e7 row (marked ⭐) halved line_frac and cut l_max 123s→34s at a mild quality cost — <b>the open question is your ears: does it sound alive, or damaged?</b>
<br><b>Fine print:</b> rows marked "guide dormant" are early rounds where the repetition edge was set from corpus statistics that model loops never reach (a real finding — crisp corpus repeats out-score approximate model loops); they play as near-baselines. Δ columns are against the same-seed unguided baseline.</div>
<div id=recipe><b>Recipe:</b> __RECIPE__</div>
<div id=out></div></div>
<audio id=au_el></audio>
<script>const C=__DATA__;
const au=document.getElementById('au_el'),npx=document.getElementById('np');let cur=null;
au.addEventListener('timeupdate',()=>{document.getElementById('pos').textContent=cur?('· '+au.currentTime.toFixed(1)+'s'):'';});
au.addEventListener('ended',()=>{cur=null;mark();});
function mark(){document.querySelectorAll('.c.play').forEach(e=>e.classList.remove('play'));if(cur){const e=document.getElementById(cur);if(e)e.classList.add('play');}}
function play(id,f,l,clip){
 if(window.noteSet)noteSet({model:'e1_pilot_20260716',ckpt:'',clip:clip});
 if(cur===id){au.pause();cur=null;mark();npx.textContent='stopped';return;}
 const pos=(cur!==null&&!au.paused)?au.currentTime:0;cur=id;mark();npx.textContent='▶ '+l;
 au.src=f;const go=()=>{try{au.currentTime=((au.duration&&pos>au.duration-1)?0:Math.min(pos,(au.duration||1e9)-0.05));}catch(e){}au.play();};
 if(au.readyState>=1)go();else au.addEventListener('loadedmetadata',go,{once:true});}
function col(v){if(v==null)return'#1a1a1f';const t=Math.max(0,Math.min(1,v/0.75));return`hsl(${Math.round((1-t)*120)},45%,22%)`;}
let h='';
for(const nl of [60,50]){
 const rows=C.filter(c=>c.nl===nl);if(!rows.length)continue;
 h+=`<h2>nl 0.${nl} ${nl===60?'— the loopy regime (baseline l_max 123 s)':'— milder regime'}</h2>`;
 h+='<table><tr><th>arm</th><th>λ</th><th>line_frac 16s</th><th>Δ</th><th>l_max (s)</th><th>Δ</th><th>r_max</th><th>▶</th></tr>';
 rows.forEach((c,i)=>{const id=`p${nl}_${i}`;const hero=(c.lam==='1e7');
  const dorm=(c.edge34===false);
  const name=(c.lamv===0)?'<b>unguided baseline</b>':(dorm?`λ=${c.lam} <span class=dorm>(guide dormant — corpus edge)</span>`:`λ=${c.lam}`);
  h+=`<tr${hero?' class=hero':''}><td>${hero?'⭐ ':''}${name}</td><td>${c.lamv===0?'—':c.lam}</td>`+
   `<td style="background:${col(c.line_frac_16s)}">${c.line_frac_16s??'·'}</td><td>${c.d_line_frac_16s??'·'}</td>`+
   `<td>${c.l_max_sec??'·'}</td><td>${c.d_l_max_sec??'·'}</td><td>${c.r_max??'·'}</td>`+
   `<td class=c id="${id}" onclick="play('${id}','${c.f}','nl${nl} ${c.lamv===0?'baseline':'λ'+c.lam}','${c.clip}')">▶</td></tr>`;});
 h+='</table>';
}
document.getElementById('out').innerHTML=h;
</script>
__NOTES__
<footer style="margin:18px 12px;color:#666;font-size:11px">aavepyora.online · evals · E1 anti-loop pilot · clips + metrics: sa3_control_runs/e1_pilot_20260716 (internal)</footer>
</body></html>"""

T = T.replace("__RECIPE__", recipe)
T = T.replace("__NOTES__", notes_block(
    "e1_pilot",
    levels=[("clip", "this clip"), ("model", "whole pilot"), ("page", "page")],
    hint="click a row's ▶ then write the ear-verdict here"))
out = STAGE / "e1_pilot.html"
out.write_text(T.replace("__DATA__", DATA))
print(f"wrote {out}: {len(cells)} rows")
