#!/usr/bin/env python3
"""
build_training_curves_page.py -- recover the LUMI training loss curves from the locally-grabbed
Lightning metrics.csv files (Kim ran --logger csv on LUMI, so no wandb, but the scalar curves
ARE saved). One self-contained HTML page, canvas-plotted, no external deps.

Plots per run: train/loss (log-y) + train/std_data & train/std_targets on a twin axis -- the
latter two are the "latent amplitude vs original training data" statistic Zach (StabilityAI)
flagged as what the model adapts to in the benign early drop.

RUN (any python3): python3 eval/build_training_curves_page.py
OUT: ~/evals_aac/training_curves.html  (local view; NOT auto-pushed to the live site)
"""
import csv
import glob
import json
import os
import re
from pathlib import Path

RUNS_ROOT = Path("/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/runs")
OUT = Path.home() / "evals_aac" / "training_curves.html"


def label_from(csv_path: str) -> str:
    """Recipe-style label from the path (redact absolute path; keep the science)."""
    p = Path(csv_path)
    # .../runs/<run>/[<arm>/]lightning_logs/version_N/metrics.csv
    parts = p.parts
    i = parts.index("runs")
    seg = [s for s in parts[i + 1:] if s not in ("lightning_logs",) and not s.startswith("version_")]
    seg = [s for s in seg if s != "metrics.csv"]
    return " / ".join(seg)


def read_csv(path: str):
    rows = list(csv.DictReader(open(path)))
    cols = rows[0].keys() if rows else []

    def series(col):
        out = []
        for r in rows:
            v = r.get(col, "")
            if v not in ("", None):
                try:
                    out.append([float(r["step"]), float(v)])
                except (ValueError, KeyError):
                    pass
        return out
    return {
        "loss": series("train/loss"),
        "std_data": series("train/std_data"),
        "std_targets": series("train/std_targets"),
        "lr": series("train/lr"),
        "n": len(rows),
    }


def main():
    csvs = sorted(glob.glob(str(RUNS_ROOT / "**" / "metrics.csv"), recursive=True))
    runs = []
    for c in csvs:
        d = read_csv(c)
        if not d["loss"]:
            continue
        runs.append({"label": label_from(c), "data": d})
    payload = json.dumps(runs)

    html = """<!doctype html><meta charset=utf-8><title>LUMI training curves (recovered)</title>
<style>
:root{color-scheme:dark}body{background:#0d0f12;color:#cdd3da;font:13px/1.5 'IBM Plex Mono',monospace;margin:0;padding:24px}
h1{font-size:17px;font-weight:600;margin:0 0 4px}.dim{color:#8892a0;max-width:820px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(400px,1fr));gap:20px;margin-top:20px}
.card{background:#14181d;border:1px solid #232a32;border-radius:8px;padding:14px}
.card h2{font-size:13px;margin:0 0 8px;color:#9ecbff;font-weight:500;word-break:break-all}
canvas{width:100%;height:200px;display:block}
.leg{display:flex;gap:14px;margin-top:6px;font-size:11px;color:#8892a0;flex-wrap:wrap}
.sw{display:inline-block;width:10px;height:3px;vertical-align:middle;margin-right:4px}
.meta{color:#6b7480;font-size:11px;margin-top:4px}
</style>
<h1>LUMI training curves &mdash; recovered from local <code>metrics.csv</code></h1>
<p class=dim>Kim ran <code>--logger csv</code> on LUMI (no wandb), but the scalar curves were saved and
pulled with the checkpoints. <b>loss</b> is log-y. <b>std_data</b> / <b>std_targets</b> (right axis) are the
latent-amplitude statistic Zach flagged &mdash; the benign early drop is the adapter matching the dataset's
latent statistics, not overfitting. Local view only.</p>
<div class=grid id=g></div>
<script>
const RUNS=__PAYLOAD__;
const g=document.getElementById('g');
function draw(cv,d){
 const dpr=devicePixelRatio||1,W=cv.clientWidth,H=cv.clientHeight;
 cv.width=W*dpr;cv.height=H*dpr;const x=cv.getContext('2d');x.scale(dpr,dpr);
 const pad={l:44,r:40,t:10,b:20};
 const loss=d.loss;if(!loss.length)return;
 const xs=loss.map(p=>p[0]),xmin=Math.min(...xs),xmax=Math.max(...xs);
 const lv=loss.map(p=>p[1]).filter(v=>v>0);
 const lmin=Math.log(Math.min(...lv)),lmax=Math.log(Math.max(...lv));
 const px=s=>pad.l+(s-xmin)/(xmax-xmin||1)*(W-pad.l-pad.r);
 const pyL=v=>pad.t+(1-(Math.log(v)-lmin)/((lmax-lmin)||1))*(H-pad.t-pad.b);
 // right axis range from std series
 const stds=[...d.std_data,...d.std_targets].map(p=>p[1]);
 const smin=stds.length?Math.min(...stds):0,smax=stds.length?Math.max(...stds):1;
 const pyR=v=>pad.t+(1-(v-smin)/((smax-smin)||1))*(H-pad.t-pad.b);
 // grid
 x.strokeStyle='#232a32';x.lineWidth=1;x.beginPath();
 x.moveTo(pad.l,pad.t);x.lineTo(pad.l,H-pad.b);x.lineTo(W-pad.r,H-pad.b);x.stroke();
 function line(series,py,color){if(!series.length)return;x.strokeStyle=color;x.lineWidth=1.6;x.beginPath();
  series.forEach((p,i)=>{const X=px(p[0]),Y=py(p[1]);i?x.lineTo(X,Y):x.moveTo(X,Y)});x.stroke();}
 line(d.std_data,pyR,'#c98b3a');line(d.std_targets,pyR,'#7a9e5a');
 line(loss,pyL,'#9ecbff');
 // y labels (loss)
 x.fillStyle='#6b7480';x.font='10px monospace';
 x.fillText(Math.exp(lmax).toFixed(3),2,pad.t+8);x.fillText(Math.exp(lmin).toFixed(3),2,H-pad.b);
 x.fillText('step '+xmax,W-pad.r-46,H-4);
}
RUNS.forEach(r=>{
 const c=document.createElement('div');c.className='card';
 c.innerHTML='<h2>'+r.label+'</h2><canvas></canvas>'+
  '<div class=leg><span><span class="sw" style="background:#9ecbff"></span>loss (log)</span>'+
  '<span><span class="sw" style="background:#c98b3a"></span>std_data</span>'+
  '<span><span class="sw" style="background:#7a9e5a"></span>std_targets</span></div>'+
  '<div class=meta>'+r.data.n+' logged points</div>';
 g.appendChild(c);
 const cv=c.querySelector('canvas');requestAnimationFrame(()=>draw(cv,r.data));
});
addEventListener('resize',()=>{g.innerHTML='';location.reload();});
</script>
"""
    html = html.replace("__PAYLOAD__", payload)
    OUT.write_text(html)
    print(f"wrote {OUT}  ({len(runs)} runs)")
    for r in runs:
        print(f"  {r['data']['n']:4d} pts  {r['label']}")


if __name__ == "__main__":
    main()
