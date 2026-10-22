#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-15)
# Last edited: WINTERMUTE 2026-10-22 -- --prefix/--sub/--page/--title/--intro/--order (any set of onset grids; defaults = the Phase E page), optimizer column from run_meta["summary"]
"""build_latch_onset_grid_page.py -- the old onset_eval-style gain x density matrix for the six Phase E
LatCH density heads (onset_per_beat_ts), with the disintegration gate applied to every steered cell.

Source: sa3_control_runs/onset_eval_latchE_<arm>/ (onset_eval.json + run_meta.json + onset_g<gain>_d<req>.wav),
rendered 2026-10-14 by control/sa3_control/onset_eval.py-style grids: prompt "psytrance, 140 bpm", seed 1234,
20 s, 50 steps, cfg 7; gains 0/128/512/2048/8192 x requested 2/4/6/8/10 onsets/s.

Gate: eval/control_head_disintegration_eval.gate() (whitening, hf-blowout, noise-zcr, beat-loss) against the
arm's own gain-0 clip, with ONE deliberate change: the quality leg reads Audiobox PQ, not CE
(project call 2026-10-15), |dPQ| > PQ_DRIFT = disintegrated. Authority (per-gain correlation of requested
vs measured) is computed on gate-passing cells only, as the gate spec requires.

Inputs it expects already scored in eval/clip_metrics.db (paths under ~/evals_aac/latch_onset_grid/):
  ffmpeg -> m4a 128k into ~/evals_aac/latch_onset_grid/<arm>/
  mir/bin/python control/sa3_control/clip_metrics.py --roots latch_onset_grid
  mir/bin/python control/sa3_control/clip_metrics_audiobox.py --roots latch_onset_grid
Writes ~/evals_aac/latch_onset_grid.html and a LOCAL disintegration_gate.json beside each source grid.
No checkpoint filenames or drive paths reach the page (public redaction seam).
"""
import glob
import json
import os
import re
import sqlite3
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "eval"))
from comment_notes_block import notes_block
from control_head_disintegration_eval import THR, gate
from float_player import inject

import argparse
_ap = argparse.ArgumentParser()
_ap.add_argument("--prefix", default="onset_eval_latchE_", help="grid dirs under sa3_control_runs/ to collect")
_ap.add_argument("--sub", default="latch_onset_grid", help="clip folder under ~/evals_aac (and the page's model key)")
_ap.add_argument("--page", default="latch_onset_grid.html")
_ap.add_argument("--title", default="LatCH onset-density heads: gain &times; requested density")
_ap.add_argument("--intro", default=None, help="HTML replacing the 'Six small LatCH guidance heads (Phase E)...' sentence")
_ap.add_argument("--order", default="", help="comma list of head names in display order (others follow, sorted)")
ARGS = _ap.parse_args()

SRC = "/run/media/kim/Mantu/sa3_control_runs"
BR = "/run/media/kim/Mantu/latch_sweep/modular_2026-09-30"
STAGE = os.path.join(os.path.expanduser("~"), "evals_aac")
SUB = ARGS.sub
DB = os.path.join(HERE, "..", "eval", "clip_metrics.db")
PQ_DRIFT = 1.5
FN = re.compile(r"onset_g(\d+)_d(\d+)\.m4a$")


def arm_flags(cmd):
    d = {}
    for k, pat, dflt in (("dim", r"--dim (\d+)", "256"), ("depth", r"--depth (\d+)", "4"), ("batch", r"--batch-size (\d+)", "16"),
                         ("lr", r"--lr ([\d.e+-]+)", "1e-2"), ("seed", r"--seed (\d+)", "0")):
        m = re.search(pat, cmd)
        d[k] = m.group(1) if m else dflt
    return d


summ = {}
for l in open(f"{BR}/phaseE/SUMMARY.tsv").read().splitlines():
    s = l.split("\t")
    if len(s) >= 6:
        summ[s[0]] = {"best_val": s[2], "last_val": s[3], **arm_flags(s[5])}

con = sqlite3.connect(DB)
cols = [r[1] for r in con.execute("PRAGMA table_info(metrics)")]
rows = {r[0]: dict(zip(cols, r)) for r in con.execute("SELECT * FROM metrics WHERE path LIKE ?", (f"%/{SUB}/%",))}

arms = []
_dirs = sorted(glob.glob(f"{SRC}/{ARGS.prefix}*"))
_ord = [x for x in ARGS.order.split(",") if x]
_dirs.sort(key=lambda d: (_ord.index(os.path.basename(d)[len(ARGS.prefix):]) if os.path.basename(d)[len(ARGS.prefix):] in _ord else len(_ord), d))
for d in _dirs:
    name = os.path.basename(d)[len(ARGS.prefix):]
    meta = json.load(open(f"{d}/run_meta.json"))
    if name not in summ and meta.get("summary"):     # heads outside Phase E carry their own row in run_meta["summary"]
        summ[name] = meta["summary"]
    meas = {(int(x["gain"]), int(x["requested"])): x["measured"] for x in json.load(open(f"{d}/onset_eval.json"))}
    cells = {}
    for p, r in rows.items():
        m = FN.search(p)
        if m and f"/{SUB}/{name}/" in p:
            cells[(int(m.group(1)), int(m.group(2)))] = r
    gains = sorted({g for g, _ in cells})
    reqs = sorted({q for _, q in cells})
    out = []
    for (g, q), r in sorted(cells.items()):
        base = cells.get((0, q)) or cells[(0, reqs[0])]
        c = {"gain": g, "req": q, "meas": meas.get((g, q)), "pq": r["pq"], "ce": r["ce"],
             "f": f"{SUB}/{name}/onset_g{g}_d{q}.m4a", "fail": False, "why": [], "corr": []}
        if g > 0:
            # quality leg = PQ, not CE: blank ce on both so gate() skips its CE check
            bad, why, corr = gate({**r, "ce": None}, {**base, "ce": None}, rhythmic=True)
            if r["pq"] is not None and base["pq"] is not None and abs(r["pq"] - base["pq"]) > PQ_DRIFT:
                why.append(f"pq-drift({base['pq']:.2f}->{r['pq']:.2f}, Δ{r['pq'] - base['pq']:+.2f})")
                bad = True
            c.update(fail=bad, why=why, corr=corr)
            c["dpq"] = r["pq"] - base["pq"] if r["pq"] is not None and base["pq"] is not None else None
        out.append(c)
    stats = []
    for g in gains:
        if g == 0:
            continue
        gc = [c for c in out if c["gain"] == g]
        ok = [c for c in gc if not c["fail"] and c["meas"] is not None]
        r = float(np.corrcoef([c["req"] for c in ok], [c["meas"] for c in ok])[0, 1]) if len(ok) >= 3 else None
        span = (max(c["meas"] for c in ok) - min(c["meas"] for c in ok)) if len(ok) >= 2 else None
        stats.append({"gain": g, "n_ok": len(ok), "n": len(gc), "r": r, "span": span})
    clean_gains = [s["gain"] for s in stats if s["n_ok"] == s["n"]]
    ceiling = 0
    for s in stats:                       # highest gain with every lower gain also fully clean
        if s["n_ok"] != s["n"]:
            break
        ceiling = s["gain"]
    sm = summ.get(name, {})
    fb = meta.get("kim_feedback") or []
    fb = [fb] if isinstance(fb, str) else fb
    arm = {"name": name, "epoch": meta.get("epoch"), "val_loss": meta.get("val_loss"), "audited": bool(fb),
           "verdicts": [{"date": v.get("date", ""), "text": v.get("verdict", "")} for v in fb if isinstance(v, dict)],
           "cells": out, "stats": stats, "ceiling": ceiling, "gains": gains, "reqs": reqs, **{k: sm.get(k) for k in ("dim", "depth", "batch", "lr", "seed", "best_val", "opt")}}
    arms.append(arm)
    json.dump({"gate": "control_head_disintegration_eval.gate + pq-drift (|dPQ|>%s, replaces ce-drift)" % PQ_DRIFT, "thresholds": THR,
               "usable_ceiling_gain": ceiling, "fully_clean_gains": clean_gains, "authority": stats,
               "cells": [{k: c[k] for k in ("gain", "req", "meas", "pq", "fail", "why", "corr")} for c in out]},
              open(f"{d}/disintegration_gate.json", "w"), indent=1)
    print(f"{name}: ceiling g{ceiling}  " + "  ".join(f"g{s['gain']} {s['n_ok']}/{s['n']} r={s['r'] if s['r'] is None else round(s['r'], 2)}" for s in stats))

# the FiLM adapter on the same requested densities, for scale: measured span at strength >= 1.3
film = [x for x in json.load(open(f"{SRC}/onset_eval_54000_g11to20/onset_eval.json")) if x["gain"] >= 1.3]
film_span = [min(x["measured"] for x in film), max(x["measured"] for x in film)]
DATA = json.dumps({"arms": arms, "pq_drift": PQ_DRIFT, "film_span": film_span})
T = r"""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>LatCH Onset Density Matrix</title><style>
body{font:13px system-ui;margin:0;background:#0e0e10;color:#e0e0e0}
#bar{position:sticky;top:0;background:#16181c;padding:7px 12px;border-bottom:1px solid #2a2a30;z-index:9}
#wrap{padding:14px;max-width:1300px}h1{font-size:18px}h2{font-size:15px;margin:22px 0 4px;color:#cde}.muted{color:#888}
.explain{background:#1a140c;border:1px solid #433;border-left:3px solid #d90;padding:10px 12px;font-size:12.5px;color:#dcd;margin:10px 0;line-height:1.45}.explain b{color:#fc6}
table{border-collapse:collapse;font-size:12px;margin:4px 0;display:block;overflow-x:auto}td,th{border:1px solid #2a2a30;padding:4px 8px;text-align:center;white-space:nowrap}
th{background:#1c1c22;color:#aaa}td:first-child,th:first-child{text-align:left;color:#9ab}
.c{cursor:pointer;font-variant-numeric:tabular-nums}.c:hover{outline:2px solid #7cf}.play{outline:2px solid #5d5 !important}
.num{font-size:10.5px;color:#9a9;display:block}.bad{background:#2a1214}.bad .num{color:#d88}.x{color:#f66;font-weight:bold}
.un{color:#e44;font-weight:bold;cursor:help}.ceil{color:#7d7;font-weight:bold}
</style></head><body>
<div id=bar>&#9654; <b id=np>click a cell to play</b> <span id=pos class=muted></span> <span class=muted>· switching keeps the playhead · re-click stops</span></div>
<div id=wrap><h1>LatCH onset-density heads: gain &times; requested density</h1>
<div class=explain><b>What this tests.</b> Six small LatCH guidance heads (Phase E), all trained to read <i>onsets per beat</i> from the SA3 latent and differing only in width, depth, batch size, learning rate or seed.
At generation time each head nudges the sampler toward a requested rhythmic density. This is the same grid the old <i>onset_eval</i> board used for the FiLM adapter:
one prompt (&ldquo;psytrance, 140&nbsp;bpm&rdquo;), one seed, 20&nbsp;s clips, guidance gains 0 / 128 / 512 / 2048 / 8192 &times; requested 2&ndash;10 onsets per second
(converted to onsets per beat at 140&nbsp;bpm). Gain 0 is the unsteered clip, identical across its row.
<b>How to read a cell.</b> Big number = measured onsets per second (librosa); below it, Audiobox production quality (PQ, 1&ndash;10) and its change against the unsteered clip.
<b>Red cells failed the disintegration gate</b>: compared with the unsteered clip they whitened, gained high-frequency buzz, got noisy, lost the beat, or PQ moved by more than __PQ__.
Hover a red cell for the reason. A head can move the meter by turning into noise, so the correlation in each summary counts <b>only the cells that passed</b>.
<b>Usable ceiling</b> = the highest gain at which every cell (and every lower gain) passed.
<b>What it cannot tell you.</b> The gate is a DSP screen, not the ear: a passing cell can still sound bad. One prompt and one seed per cell, so single numbers are noisy.
<span class=un title="No listening verdict recorded yet (unaudited).">&#10071;</span> = no listening verdict recorded yet.</div>
<div id=verdict></div><h2>Summary</h2><div id=sum></div><div id=out></div></div><audio id=au_el></audio>
<script>const D=__DATA__;
const au=document.getElementById('au_el'),npx=document.getElementById('np');let cur=null;
au.addEventListener('timeupdate',()=>{document.getElementById('pos').textContent=cur?('· '+au.currentTime.toFixed(1)+'s'):'';});
au.addEventListener('ended',()=>{cur=null;mark();});
function mark(){document.querySelectorAll('.c.play').forEach(e=>e.classList.remove('play'));if(cur){const e=document.getElementById(cur);if(e)e.classList.add('play');}}
function play(id,f,l,arm,clip){
 if(cur===id){au.pause();cur=null;mark();npx.textContent='stopped';return;}
 if(window.noteSet)noteSet({model:'latch_onset_grid',ckpt:arm,clip:clip});
 const pos=(cur!==null&&!au.paused)?au.currentTime:0;cur=id;mark();npx.textContent=l;au.src=f;
 const go=()=>{try{au.currentTime=Math.min(pos,(au.duration||1e9)-0.05);}catch(e){}au.play();};
 if(au.readyState>=1)go();else au.addEventListener('loadedmetadata',go,{once:true});}
const f2=(v,d)=>v==null?'–':v.toFixed(d),sg=(v,d)=>v==null?'':(v>=0?'+':'')+v.toFixed(d);
{const vs=[...new Map(D.arms.flatMap(a=>a.verdicts).map(v=>[v.date+v.text,v])).values()];
 if(vs.length){const sp=a=>{const c=a.cells.filter(x=>x.gain>0&&x.gain<=512).map(x=>x.meas);return (Math.max(...c)-Math.min(...c)).toFixed(1);};
  document.getElementById('verdict').innerHTML='<div class=explain style="border-left-color:#5c5;background:#0f1a10"><b style="color:#8e8">Listening verdict</b> '+vs.map(v=>`(${v.date}): &ldquo;${v.text}&rdquo;`).join(' ')+
  `<br><b style="color:#8e8">What the numbers say alongside it.</b> On the same requested densities the FiLM control adapter (strength 1.3&ndash;2) measures ${D.film_span[0].toFixed(1)}&ndash;${D.film_span[1].toFixed(1)} onsets/s.
  These heads, at the gains that pass the gate cleanly (128&ndash;512), spread only ${Math.min(...D.arms.map(a=>+sp(a)))}&ndash;${Math.max(...D.arms.map(a=>+sp(a)))} onsets/s around the unsteered 7.3, and reach a FiLM-like range only at 2048&ndash;8192, where cells start to fail.
  So &ldquo;passes the gate&rdquo; here mostly means &ldquo;barely changed&rdquo;, and the high correlations describe a small, sub-audible shift. Read the usable-ceiling column as an upper bound on safety, not as evidence of control.</div>`;}}
const UN='<span class=un title="No listening verdict recorded yet (unaudited).">&#10071;</span>';
const OPT=D.arms.some(a=>a.opt);
let s='<table><tr><th></th><th>head</th>'+(OPT?'<th>optimizer / schedule</th>':'')+'<th>width</th><th>depth</th><th>batch</th><th>lr</th><th>seed</th><th>best val</th>';
const G=D.arms[0].stats.map(x=>x.gain);G.forEach(g=>s+=`<th>gain ${g}<br><span class=muted>clean · r · span</span></th>`);s+='<th>usable ceiling</th></tr>';
D.arms.forEach(a=>{s+=`<tr><td>${a.audited?'':UN}</td><td><a href="#${a.name}" style="color:#9cf">${a.name}</a></td>${OPT?`<td style="text-align:left">${a.opt||''}</td>`:''}<td>${a.dim}</td><td>${a.depth}</td><td>${a.batch}</td><td>${a.lr}</td><td>${a.seed}</td><td>${a.best_val||''}</td>`;
 a.stats.forEach(x=>{s+=`<td class="${x.n_ok<x.n?'bad':''}">${x.n_ok}/${x.n} · ${f2(x.r,2)} · ${f2(x.span,1)}</td>`;});
 s+=`<td class=ceil>${a.ceiling?('gain '+a.ceiling):'none'}</td></tr>`;});
document.getElementById('sum').innerHTML=s+'</table><div class=muted style="font-size:11.5px">clean = cells passing the gate · r = correlation of requested vs measured over the clean cells · span = measured range (onsets/s) over the clean cells</div>';
let h='';
D.arms.forEach(a=>{
 h+=`<h2 id="${a.name}">${a.audited?'':UN} ${a.name} <span class=muted style="font-weight:normal">width ${a.dim}, depth ${a.depth}, batch ${a.batch}, lr ${a.lr}, seed ${a.seed}; checkpoint epoch ${a.epoch}</span></h2>`;
 h+='<table><tr><th>gain \\ requested</th>'+a.reqs.map(q=>`<th>${q} /s</th>`).join('')+'</tr>';
 a.gains.forEach(g=>{h+=`<tr><td>${g===0?'0 (unsteered)':g}</td>`;
  a.reqs.forEach(q=>{const c=a.cells.find(x=>x.gain===g&&x.req===q);if(!c){h+='<td>·</td>';return;}
   const id=`${a.name}_${g}_${q}`,tip=c.fail?c.why.join('; '):(c.corr.length?c.corr.join('; '):'');
   h+=`<td class="c ${c.fail?'bad':''}" id="${id}" title="${tip}" onclick="play('${id}','${c.f}','${a.name} gain ${g} req ${q}/s','${a.name}','g${g}_d${q}')">${c.fail?'<span class=x>&#10007;</span> ':''}&#9654; ${f2(c.meas,2)}<span class=num>PQ ${f2(c.pq,2)}${g?' ('+sg(c.dpq,2)+')':''}</span></td>`;});
  h+='</tr>';});
 h+='</table>';});
document.getElementById('out').innerHTML=h;
</script>
__NOTES__
<footer style="margin:18px 12px;color:#666;font-size:11px">evals &middot; LatCH onset-density matrix &middot; grids: sa3_control_runs onset_eval (internal) &middot; gate: control-head disintegration gate, quality leg = Audiobox PQ</footer>
</body></html>"""
_INTRO = ("Six small LatCH guidance heads (Phase E), all trained to read <i>onsets per beat</i> from the SA3 latent and differing only in width, "
          "depth, batch size, learning rate or seed.")
assert _INTRO in T
if ARGS.intro:
    T = T.replace(_INTRO, ARGS.intro)
T = T.replace("<h1>LatCH onset-density heads: gain &times; requested density</h1>", f"<h1>{ARGS.title}</h1>")
T = T.replace("model:'latch_onset_grid'", f"model:'{SUB}'")
T = T.replace("__PQ__", str(PQ_DRIFT)).replace("__NOTES__", notes_block(SUB, levels=[("clip", "this clip"), ("page", "page")], hint="click a cell, then note what you hear"))
out = os.path.join(STAGE, ARGS.page)
open(out, "w").write(inject(T.replace("__DATA__", DATA)))
print(f"wrote {out}: {len(arms)} heads, {sum(len(a['cells']) for a in arms)} cells")
