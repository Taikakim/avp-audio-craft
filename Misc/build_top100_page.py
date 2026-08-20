#!/usr/bin/env python3
"""build_top100_page.py — render eval/top100_work/top100.json (from eval/build_top100.py) into the
public "Top 100 by ear-proxy" page: our best clips per frame length, ranked by PQ ALONE, with
MERT near-duplicate disqualification. Kim direct 2026-08-21.

Stages to ~/evals_aac/top100.html (the served tree; URL /files/evals/top100.html once synced).
Three-audience standard (spec §14): explainer block above the tool; full recipe columns for
engineers parsed from the cell naming convention; same-playhead listening cells for Kim.
Redaction: run LABELS and hyperparameters are science (shown); no absolute paths, no infra.
"""
import html
import json
import os
import re
import time

WORK = "/home/kim/Projects/SAO/eval/top100_work/top100.json"
OUT = "/home/kim/evals_aac/top100.html"
ROOT = "/home/kim/evals_aac/"

CLASS_TITLES = {
    "T256_20s": ("T256 — 20–24 s", "the standard grid-cell length; by far the largest pool"),
    "T512_47s": ("T512 — ~47 s", "the production DoRA crop length"),
    "T1024_95s": ("T1024 — ~95 s", "long-form; small population so far — this class lists all it has"),
    "T2048_190s": ("T2048 — ~190 s", "native-length evals (LUMI renders)"),
    "T4096_380s": ("T4096 — ~380 s", "full-context native renders"),
}


def parse_cell(path):
    """model__epN__cfgX__wYYY__prompt__sSEED -> dict; graceful fallback for other naming."""
    b = re.sub(r"\.(m4a|wav|flac|mp3)$", "", os.path.basename(path))
    m = re.match(r"(?P<model>.+?)__ep(?P<ep>\d+)__cfg(?P<cfg>[\d.]+)__w(?P<w>\d+)__(?P<prompt>.+)__s(?P<seed>\d+)$", b)
    if m:
        d = m.groupdict()
        d["w"] = f"{int(d['w'])/100:g}"
        return d
    return {"model": b, "ep": "", "cfg": "", "w": "", "prompt": "", "seed": ""}


def main():
    D = json.load(open(WORK))
    gen = D.get("generated", time.strftime("%Y-%m-%d"))
    thr = D.get("threshold", 0)
    data = {"classes": [], "gen": gen, "thr": round(thr, 4)}
    for lbl, _t in CLASS_TITLES.items():
        cls = D["classes"].get(lbl)
        if not cls:
            continue
        clips = []
        for e in cls["clips"]:
            rel = e["path"][len(ROOT):] if e["path"].startswith(ROOT) else None
            if rel is None:
                continue
            c = parse_cell(e["path"])
            clips.append({"r": e["rank"], "u": rel, "pq": round(e["pq"], 3),
                          "dur": round(e["dur"]), **c})
        data["classes"].append({"id": lbl, "title": CLASS_TITLES[lbl][0],
                                "sub": CLASS_TITLES[lbl][1], "clips": clips,
                                "dropped": cls["near_dup_disqualified"]})

    doc = []
    A = doc.append
    A("<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>")
    A("<title>Top 100 by ear-proxy · evals</title><link rel='stylesheet' href='evals.css'>")
    A("<style>body{max-width:none;padding:0 18px}table{width:100%;border-collapse:collapse;font-size:13px}"
      "td,th{padding:3px 7px;border-bottom:1px solid #2a2a2a;text-align:left;white-space:nowrap}"
      ".c{cursor:pointer;user-select:none;padding:2px 9px;border:1px solid #444;border-radius:4px;display:inline-block}"
      ".c.play{background:#2b5d34;border-color:#4a8}.c.loading{background:#5d532b}"
      ".pq{font-weight:bold}.muted{color:#888;font-size:12px}.explain{background:#191d22;border:1px solid #333;"
      "border-radius:6px;padding:10px 14px;margin:10px 0;font-size:13px;line-height:1.5}"
      ".prompt{max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;display:inline-block;vertical-align:bottom}"
      "nav a{margin-right:14px}h2{margin-top:26px}#np{position:sticky;top:0;background:#111;padding:6px 0;z-index:5}</style></head><body>")
    A(f"<h1>Top 100 clips per frame length <span class='unaudited' title='unaudited — awaiting ear pass'>&#10071;</span></h1>")
    A("<div class=explain><b>What this is / why / how to read it.</b> Every generated clip we have "
      "ever scored (93k+), ranked <b>by Audiobox PQ alone</b> — chosen because on 668 of Kim's real "
      "A/B votes PQ alone predicted his preference better (77.6%) than any richer feature combination "
      "(adding CE or DSP features made the proxy <i>worse</i>). Near-duplicates are <b>disqualified</b>: "
      "walking each list from the top, a clip is dropped if its MERT embedding (rhythm layers 3–6 + "
      "melody layer 23, cosine) is closer than a calibrated threshold to any clip already kept — so "
      "the same take at three guidance weights appears once, at its best. <b>How to read:</b> click a "
      "cell to play; switching clips keeps the playhead (A/B at the same position); click again to stop. "
      "Columns carry the full recipe (model label, epoch, cfg, guidance weight, prompt, seed) for "
      "reproducibility. PQ is an ear <i>proxy</i> — this page is a listening shortlist, not a verdict.</div>")
    A(f"<div class=muted>generated {gen} · dedup threshold {data['thr']} (calibrated: guidance-weight "
      f"siblings vs cross-model pairs) · ranking source: clip_metrics.db · builder Misc/build_top100_page.py</div>")
    A("<div id=np>&#9654; nothing playing <span id=pos></span> <span id=ld></span></div><nav>")
    for c in data["classes"]:
        A(f"<a href='#{c['id']}'>{html.escape(c['title'])}</a>")
    A("</nav><audio id=au_el></audio><div id=body></div>")
    A("<script>const D=" + json.dumps(data) + ";</script>")
    A("""<script>
const au=document.getElementById('au_el'),npx=document.getElementById('np');let cur=null;
au.addEventListener('timeupdate',()=>{document.getElementById('pos').textContent=cur?('· '+au.currentTime.toFixed(1)+'s'):'';});
au.addEventListener('waiting',()=>{document.getElementById('ld').textContent='loading…';});
au.addEventListener('playing',()=>{document.getElementById('ld').textContent='';});
function mark(){document.querySelectorAll('.c.play').forEach(e=>e.classList.remove('play'));if(cur){const e=document.getElementById(cur);if(e)e.classList.add('play');}}
function play(id,f,l){
 if(cur===id){au.pause();cur=null;mark();npx.firstChild.textContent='▶ stopped ';return;}
 const pos=(cur!==null&&!au.paused)?au.currentTime:0;cur=id;mark();npx.firstChild.textContent='▶ '+l+' ';
 au.src=f;const go=()=>{try{au.currentTime=((au.duration&&pos>au.duration-1)?0:Math.min(pos,(au.duration||1e9)-0.05));}catch(e){}au.play();};
 if(au.readyState>=1)go();else au.addEventListener('loadedmetadata',go,{once:true});}
let h='';
D.classes.forEach(cl=>{
 h+=`<h2 id=${cl.id}>${cl.title}</h2><div class=muted>${cl.sub} · ${cl.clips.length} kept, ${cl.dropped} near-duplicates disqualified</div>`;
 h+='<table><tr><th>#</th><th></th><th>PQ</th><th>model</th><th>ep</th><th>cfg</th><th>w</th><th>prompt</th><th>seed</th><th>dur</th></tr>';
 cl.clips.forEach(c=>{
  const id=cl.id+'_'+c.r;
  h+=`<tr><td>${c.r}</td><td><span class=c id=${id} onclick='play("${id}","${c.u}","#${c.r} ${c.model}")'>▶</span></td>`+
     `<td class=pq>${c.pq.toFixed(3)}</td><td>${c.model}</td><td>${c.ep}</td><td>${c.cfg}</td><td>${c.w}</td>`+
     `<td><span class=prompt title="${c.prompt}">${c.prompt}</span></td><td>${c.seed}</td><td>${c.dur}s</td></tr>`;});
 h+='</table>';});
document.getElementById('body').innerHTML=h;
</script>""")
    A("<footer style='margin:18px 0;color:#666;font-size:11px'>aavepyora.online · evals · Top-100 by "
      "PQ with MERT dedup · PQ-alone rationale: W's preference fit 2026-08-21 · clips: existing eval "
      "renders (internal run labels; no new generation)</footer></body></html>")
    open(OUT, "w").write("\n".join(doc))
    n = sum(len(c["clips"]) for c in data["classes"])
    print(f"[top100] wrote {OUT}: {n} clips across {len(data['classes'])} classes")


if __name__ == "__main__":
    main()
