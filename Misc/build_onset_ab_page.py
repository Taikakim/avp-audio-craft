#!/usr/bin/env python3
"""FiLM onset-density A/B audition page — cautious vs baseline, canonical 3-prompt sweep.

Reads onset_eval_<label>/onset_eval.json ({prompt_idx, prompt, gain, requested, measured})
+ run_meta.json, encodes clips to AAC .m4a, and emits one page: per head, a gain x density
authority grid PER PROMPT (cells coloured by measured onset density; click to play; switching
keeps the playhead, re-click stops) + per-gain correlation. Numbers are a noisy instrument —
the page is for listening. Effective gains only (<=3); above that the control over-steers.

    python Misc/build_onset_ab_page.py --labels Fusion_baseline FusionCaut soup_baseline soup_caut
"""
import argparse, json, os, subprocess
from concurrent.futures import ThreadPoolExecutor


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval-root", default="/run/media/kim/Mantu/sa3_control_runs")
    ap.add_argument("--labels", nargs="+",
                    default=["Fusion_baseline", "FusionCaut", "soup_baseline", "soup_caut"])
    ap.add_argument("--out", default="/run/media/kim/Mantu/sa3_control_runs/onset_ab_audition")
    ap.add_argument("--bitrate", default="128k")
    a = ap.parse_args()
    clipdir = os.path.join(a.out, "clips"); os.makedirs(clipdir, exist_ok=True)

    heads, conv = [], []
    for lab in a.labels:
        d = os.path.join(a.eval_root, f"onset_eval_{lab}")
        jp = os.path.join(d, "onset_eval.json")
        if not os.path.isfile(jp):
            print(f"skip {lab}: no {jp}"); continue
        rows = json.load(open(jp))
        meta = json.load(open(os.path.join(d, "run_meta.json"))) if os.path.isfile(os.path.join(d, "run_meta.json")) else {}
        prompts = meta.get("eval", {}).get("prompts") or sorted({r["prompt"] for r in rows})
        gains = sorted({r["gain"] for r in rows}); reqs = sorted({r["requested"] for r in rows})
        # cells[prompt_idx][gain|req] = {m, f}
        cells = {}
        for r in rows:
            pi = r.get("prompt_idx", 0); g, q, m = r["gain"], r["requested"], r["measured"]
            wav = os.path.join(d, f"onset_p{pi}_g{g:g}_d{q:g}.wav")
            f = None
            if os.path.exists(wav):
                stem = f"{lab}_p{pi}_g{g:g}_d{q:g}.m4a"; dst = os.path.join(clipdir, stem)
                f = f"clips/{stem}"
                if not os.path.exists(dst): conv.append((wav, dst))
            cells.setdefault(pi, {})[f"{g:g}|{q:g}"] = {"m": round(m, 1), "f": f}
        heads.append({"label": lab, "meta": meta, "corr": meta.get("corr_per_gain", {}),
                      "corr_pg": meta.get("corr_prompt_gain", {}), "prompts": prompts,
                      "gains": [f"{g:g}" for g in gains], "reqs": [f"{q:g}" for q in reqs], "cells": cells})

    def cv(j): subprocess.run(["ffmpeg", "-y", "-i", j[0], "-c:a", "aac", "-b:a", a.bitrate, j[1]], capture_output=True)
    print(f"heads {len(heads)} | clips to encode {len(conv)}")
    if conv:
        with ThreadPoolExecutor(max_workers=8) as ex: list(ex.map(cv, conv))
    DATA = json.dumps({"heads": heads})

    T = r"""<!doctype html><html><head><meta charset=utf-8><title>onset-density A/B — cautious vs baseline (3 prompts)</title><style>
body{font:12px system-ui;margin:0;background:#0e0e10;color:#e0e0e0}
#hdr{position:sticky;top:0;z-index:9;background:#16181c}#bar{padding:8px 12px;border-bottom:1px solid #2a2a30}
#info{background:#0f1a14;border-top:1px solid #243;border-bottom:1px solid #243;border-left:3px solid #5d9;padding:8px 12px;color:#cde}
#wrap{padding:12px;max-width:1200px}h2{font-size:14px;color:#9cf;margin:18px 0 2px;border-top:1px solid #26262c;padding-top:10px}
.pr{color:#caa;font-size:12px;margin:8px 0 1px}.corr{color:#8aa;font-size:11px;margin:1px 0 4px}.corr b{color:#cde}
table{border-collapse:collapse;font-size:11px;margin:2px 0 8px}td,th{border:1px solid #26262c;padding:3px 7px;text-align:center}
th{background:#1c1c22;color:#aaa}td:first-child,th:first-child{text-align:left;color:#9ab}
.c{cursor:pointer;font-variant-numeric:tabular-nums}.c:hover{outline:1px solid #7cf}.play{outline:2px solid #5d5 !important}
.muted{color:#666}</style></head><body>
<div id=hdr><div id=bar>&#9654; <b id=np>click a cell to play</b> <span id=pos class=muted></span>
&nbsp;·&nbsp; <span class=muted>switching keeps the playhead; re-click stops · cell = measured onsets/s (colour) · request across top, gain down side · effective gains only (&le;3)</span></div>
<div id=info>tap a cell or head title for provenance. Numbers are a noisy instrument — judge by ear. Onset-smear = high measured density that sounds like mush, not rhythm.</div></div>
<div id=wrap></div>
<script>const D=__DATA__;const au=new Audio();let cur=null;
au.addEventListener('timeupdate',()=>{document.getElementById('pos').textContent=cur?('· '+au.currentTime.toFixed(1)+'s'):'';});
au.addEventListener('ended',()=>{cur=null;mark();});
function mark(){document.querySelectorAll('.c.play').forEach(e=>e.classList.remove('play'));if(cur){const e=document.getElementById(cur);if(e)e.classList.add('play');}}
function info(hi){const h=D.heads[hi],m=h.meta;document.getElementById('info').innerHTML=
 `<b style=color:#9ec>${h.label}</b> ${m.optimizer?('· '+m.optimizer):''} ${m.lr&&m.lr!='-'?('· lr '+m.lr):''} · corr/gain `+
 h.gains.map(g=>`g${g}:<span style=color:#7cf>${h.corr[g]==null?'·':h.corr[g]}</span>`).join(' ');}
function col(m){const t=Math.max(0,Math.min(1,m/14));return`hsl(${Math.round(t*130)},45%,22%)`;}
function play(id,f,lbl,hi){if(!f)return;if(cur===id){au.pause();cur=null;mark();document.getElementById('np').textContent='stopped';return;}
 const pos=(cur!==null&&!au.paused)?au.currentTime:0;cur=id;mark();document.getElementById('np').textContent='▶ '+lbl;info(hi);
 au.src=f;const go=()=>{try{au.currentTime=Math.min(pos,(au.duration||1e9)-0.05);}catch(e){}au.play();};
 if(au.readyState>=1)go();else au.addEventListener('loadedmetadata',go,{once:true});}
let h='';D.heads.forEach((hd,hi)=>{
 h+=`<h2 onclick="info(${hi})" style=cursor:pointer>${hd.label} <span class=muted style=font-weight:400>— corr/gain `+hd.gains.map(g=>`g${g} <b style=color:#7cf>${hd.corr[g]==null?'·':hd.corr[g]}</b>`).join('  ')+`</span></h2>`;
 hd.prompts.forEach((pr,pi)=>{
   const cells=hd.cells[pi]||{};
   h+=`<div class=pr>“${pr}”</div>`;
   const pg=hd.gains.map(g=>{const c=hd.corr_pg['p'+pi+'_g'+g];return `g${g} <b>${c==null?'·':c}</b>`;}).join('  ');
   h+=`<div class=corr>corr/gain (this prompt): ${pg}</div>`;
   h+='<table><tr><th>g＼req</th>'+hd.reqs.map(q=>`<th>${q}</th>`).join('')+'</tr>';
   for(const g of hd.gains){h+=`<tr><td>g${g}</td>`+hd.reqs.map(q=>{const c=cells[g+'|'+q];if(!c)return'<td class=muted>·</td>';
     const id=(hd.label+'_p'+pi+'_'+g+'_'+q).replace(/[^A-Za-z0-9_]/g,'');
     if(!c.f)return`<td style=background:${col(c.m)}>${c.m}</td>`;
     return`<td class=c id="${id}" style=background:${col(c.m)} onclick="play('${id}','${c.f}','${hd.label} p${pi} g${g} d${q}→${c.m}',${hi})">${c.m}</td>`;}).join('')+'</tr>';}
   h+='</table>';});
});
document.getElementById('wrap').innerHTML=h;</script></body></html>"""
    out_html = os.path.join(a.out, "index.html")
    open(out_html, "w").write(T.replace("__DATA__", DATA))
    print(f"wrote {out_html} ({len(heads)} heads)")
    print(f"serve: cd {a.out} && python -m http.server 8000")


if __name__ == "__main__":
    main()
