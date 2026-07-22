#!/usr/bin/env python3
"""
build_dora_table_page.py -- interactive web page over the DoRA hyperparameter x metric table
(Kim 2026-07-22: "prepare a web page with the same content but interactive ordering by different
columns, colour coding per column"). Reads eval/clap_dora_aggregate.csv (234 model x checkpoint
rows: hyperparams + CLAP degeneration + Audiobox + DSP) + eval/corpus_reference.json (goa/avp
training baselines). Emits a single self-contained HTML (no external deps): click a header to
sort, every numeric column is a direction-aware heatmap, filter by dataset/rank, and a pinned
DATASET-BASELINE strip so drift-from-source is readable (the stereo-narrowing answer).

OUT: eval/dora_table.html
"""
import csv
import json
from pathlib import Path

ROOT = Path("/home/kim/Projects/SAO/eval")
AGG = ROOT / "clap_dora_aggregate.csv"
REF = ROOT / "corpus_reference.json"
OUT = ROOT / "dora_table.html"

# column groups + per-metric direction (+1 = higher is better/green, -1 = lower is better)
HP = ["model", "ckpt", "arch", "rank", "alpha", "alpha_over_rank", "precision", "frames_T",
      "batch", "lr", "optimizer", "dataset", "aug", "epoch", "steps", "train_N", "n_cells"]
METRICS = {"clap_matched": +1, "clap_margin_far": +1, "ce": +1, "pq": +1, "cu": +1, "pc": +1,
           "zcr": -1, "flatness": -1, "flux": +1, "hf_ratio": -1, "bpm": 0,
           "onset_p95": +1, "centroid": 0, "crest": -1, "rms": +1}
NICE = {"clap_matched": "CLAP", "clap_margin_far": "CLAP·mgn", "alpha_over_rank": "α/rank",
        "frames_T": "T", "onset_p95": "onset", "hf_ratio": "hf", "flatness": "flat",
        "precision": "prec", "optimizer": "opt"}

# hover tooltips per column (native title=). ↑ = higher is better, ↓ = lower is better.
DESC = {
    "model": "Training run label (the recipe). Each row aggregates that run's cfg×strength×prompt cells.",
    "ckpt": "Checkpoint = the training epoch snapshot rendered (ep<N>).",
    "arch": "Adapter type: dora (DoRA rows) · fullft (whole DiT fine-tuned) · base (no adapter).",
    "rank": "DoRA/LoRA rank = adapter capacity. r16 harsh/worst; ≥64 plateaus; 128 = safe default.",
    "alpha": "DoRA alpha = adapter scaling. With α<rank the adapter is applied more gently.",
    "alpha_over_rank": "alpha ÷ rank (effective scale). <1 = 'adjusted' (adj) — beats the standard α=rank.",
    "precision": "Training precision: fp32 or bf16. ≈equal for genre-adherence & buzz; fp32's edge is fidelity (ear-only).",
    "frames_T": "Latent context length in frames (T). ×0.0928 s = seconds. Optimum ~1024; T4096 (long) is worse.",
    "batch": "Training batch size. Marginal 'bigger better' is a confound; at matched context small batch is cleaner.",
    "lr": "Learning rate. Flat 1e-4↔2e-4; cliffs (collapses) at 6e-4.",
    "optimizer": "Optimizer: FusionOpt or AdamW.",
    "dataset": "Training corpus: goa (psytrance) · avp (Kim's own music) · mixed.",
    "aug": "Augmentation multiplier (pitch/stretch). 0 = none. aug10 is the cleanest single win (helps every axis).",
    "epoch": "This checkpoint's training epoch. Overtraining collapses UN-augmented runs by ~ep15; aug10 climbs to ep74 (corpus best).",
    "steps": "Total training optimizer steps at this checkpoint (steps/epoch × epoch, from the recipe's recorded step count). Blank where not recorded.",
    "train_N": "Training-set size = # latent crops. Anchored to the known encoded_dir (aug10=320, originals=288, everything=6111, goa=5401, avp=2393); variant runs estimated from steps/epoch×batch. LOW N = overfit-risk (a small set drilled hard can top CLAP by memorizing the prompt space).",
    "n_cells": "Number of rendered cells averaged into this row.",
    "clap_matched": "↑ CLAP cosine(audio, its OWN prompt) = genre/prompt ADHERENCE. Low = output drifted off-genre (degeneration).",
    "clap_margin_far": "↑ CLAP gap between the true prompt and out-of-genre control prompts. Higher = more decisively on-genre.",
    "ce": "↑ Audiobox Content Enjoyment (learned subjective 'is it enjoyable'). ~scale 1–10.",
    "pq": "↑ Audiobox Production Quality (learned 'how well produced'). Nearly collinear with CU.",
    "cu": "↑ Audiobox Content Usefulness (learned). Nearly collinear with PQ.",
    "pc": "Audiobox Production Complexity (learned). Neutral — more/less complex, not better/worse.",
    "zcr": "↓ Zero-crossing rate = noise/brightness proxy. High = noisier/buzzier.",
    "flatness": "↓ Spectral flatness (Wiener entropy) = noise-like vs tonal. High = whitened/noisy (buzz).",
    "flux": "↑ Spectral flux = frame-to-frame spectral change (dynamism). Low = static/drone-like.",
    "hf_ratio": "↓ Fraction of spectral energy above 6 kHz = HF-blowout / static-buzz signature. High = harsh.",
    "bpm": "Estimated tempo (BPM). Informational — uncorrelated with quality.",
    "onset_p95": "↑ 95th-pct onset strength = rhythmic density / attack presence. Higher = busier/punchier.",
    "centroid": "Spectral centroid = brightness (Hz). Neutral.",
    "crest": "↓ Crest factor (peak÷RMS). High = peaky/transient; low = more sustained/filled. Genre-adherent output trends lower.",
    "rms": "↑ RMS energy = overall loudness/fullness.",
}


def main():
    rows = list(csv.DictReader(AGG.open()))
    ref = json.loads(REF.read_text())
    cols = HP + [c for c in METRICS if c in rows[0]]

    # numeric coercion + per-column min/max for the heatmap
    def num(v):
        try:
            return float(v)
        except Exception:
            return None
    data = []
    for r in rows:
        data.append({c: (num(r[c]) if c in METRICS or c in
                         ("rank", "alpha", "alpha_over_rank", "frames_T", "batch", "lr", "aug", "epoch", "n_cells")
                         else r.get(c, "")) for c in cols})

    # dataset-baseline strip (only the cleanly-comparable axes -- same algorithm as eval extractors)
    base = {}
    for c in ("goa", "avp"):
        b = ref.get(c, {})
        base[c] = {"stereo_corr": b.get("stereo_corr", {}).get("mean"),
                   "stereo_width": b.get("stereo_width", {}).get("mean"),
                   "dissonance": b.get("dissonance", {}).get("mean"),
                   "inharmonicity": b.get("inharmonicity", {}).get("mean"),
                   "mood_top": (b.get("mood_top10") or [])[:6]}

    payload = {"cols": cols, "rows": data, "metrics": METRICS, "hp": HP,
               "nice": NICE, "base": base, "desc": DESC}
    html = _PAGE.replace("__DATA__", json.dumps(payload))
    OUT.write_text(html)
    print(f"wrote {OUT}  ({len(rows)} rows, {len(cols)} cols)")


_PAGE = r"""<!doctype html><html><head><meta charset=utf-8><title>DoRA hyperparameter × metric table</title>
<style>
body{font:12px system-ui;margin:0;background:#0f0f12;color:#e2e2e6}
h1{font-size:16px;margin:12px 14px 2px}.sub{color:#9a9;margin:0 14px 8px;font-size:12px;max-width:1100px;line-height:1.5}
.base{margin:8px 14px;padding:8px 12px;background:#15161b;border:1px solid #2a2c34;border-radius:7px;font-size:12px}
.base b{color:#8cf}.hi{color:#f97;font-weight:bold}
.ctl{margin:8px 14px;display:flex;gap:14px;flex-wrap:wrap;align-items:center}
.ctl label{color:#9a9}select,input{background:#1b1c22;color:#dde;border:1px solid #333;border-radius:4px;padding:3px 5px;font-size:12px}
.wrap{overflow:auto;max-height:78vh;margin:0 8px;border:1px solid #23242c;border-radius:6px}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
th,td{padding:3px 7px;text-align:right;white-space:nowrap;border-bottom:1px solid #1c1d24}
th{position:sticky;top:0;background:#181920;cursor:pointer;user-select:none;border-bottom:2px solid #2a2c34;z-index:2}
th:hover{background:#20222b}th.sorted{color:#8cf}
td.txt,th.txt{text-align:left}td.model{text-align:left;color:#cde;position:sticky;left:0;background:#12131a;z-index:1}
tr:hover td{background:#191a22 !important}tr:hover td.model{background:#1c1e28 !important}
.arrow{font-size:9px;color:#8cf}
</style></head><body>
<h1>DoRA hyperparameter × metric table</h1>
<p class=sub>Every trained model × checkpoint (each row aggregates its cfg×strength×prompt cells).
<b>Hover any column header for its definition</b>; click to sort. Each metric column is a
heat-map (green = better direction, red = worse). Filter below. Hyperparameters parsed from the
checkpoint recipes.</p>
<div class=base id=base></div>
<div class=ctl>
 <label>dataset <select id=fds><option value="">all</option><option>goa</option><option>avp</option><option>mixed</option></select></label>
 <label>rank <select id=frank><option value="">all</option></select></label>
 <label>arch <select id=farch><option value="">all</option></select></label>
 <label>find <input id=ftext placeholder="model substring" size=18></label>
 <span id=count style=color:#9a9></span>
</div>
<div class=wrap><table id=t><thead><tr id=hrow></tr></thead><tbody id=body></tbody></table></div>
<script>
const D=__DATA__;
const {cols,rows,metrics,nice,base,desc}=D;
const nfmt=(c,v)=>{if(v==null||v==='')return '';if(typeof v!=='number')return v;
 if(['lr'].includes(c))return v.toExponential(1);
 if(['rank','alpha','frames_T','batch','aug','epoch','n_cells','bpm'].includes(c))return v%1?v.toFixed(1):v.toFixed(0);
 return v.toFixed(3);};
// per-column min/max for heatmap
const ext={};
for(const c in metrics){const vs=rows.map(r=>r[c]).filter(v=>typeof v==='number');ext[c]=[Math.min(...vs),Math.max(...vs)];}
function heat(c,v){if(typeof v!=='number'||!(c in metrics)||metrics[c]===0)return '';
 const [lo,hi]=ext[c];let t=(v-lo)/(hi-lo+1e-9);if(metrics[c]<0)t=1-t;   // direction-aware
 const r=Math.round(200*(1-t)+30*t),g=Math.round(60*(1-t)+180*t);return `background:rgba(${r},${g},70,0.30)`;}
let sortCol='clap_matched',sortDir=-1;
function hdr(){const tr=document.getElementById('hrow');tr.innerHTML='';
 for(const c of cols){const th=document.createElement('th');const isTxt=typeof rows[0][c]!=='number';
  th.className=(isTxt?'txt ':'')+(c===sortCol?'sorted':'');th.textContent=nice[c]||c;
  th.title=(desc[c]||c)+'  ·  click to sort';
  if(c===sortCol)th.innerHTML+=' <span class=arrow>'+(sortDir<0?'▼':'▲')+'</span>';
  th.onclick=()=>{if(sortCol===c)sortDir*=-1;else{sortCol=c;sortDir=(c in metrics&&metrics[c]>=0)||typeof rows[0][c]!=='number'?-1:-1;}render();};
  tr.appendChild(th);}}
function render(){
 const ds=fds.value,rk=frank.value,ar=farch.value,tx=ftext.value.toLowerCase();
 let rs=rows.filter(r=>(!ds||r.dataset===ds)&&(!rk||String(r.rank)===rk)&&(!ar||r.arch===ar)&&(!tx||String(r.model).toLowerCase().includes(tx)));
 rs.sort((a,b)=>{let x=a[sortCol],y=b[sortCol];if(x==null)return 1;if(y==null)return -1;
  if(typeof x==='number')return (x-y)*sortDir;return String(x).localeCompare(String(y))*sortDir;});
 const body=document.getElementById('body');body.innerHTML='';
 for(const r of rs){const tr=document.createElement('tr');
  for(const c of cols){const td=document.createElement('td');const v=r[c];
   if(c==='model')td.className='model';else if(typeof v!=='number')td.className='txt';
   td.textContent=nfmt(c,v);const h=heat(c,v);if(h)td.style.cssText=h;tr.appendChild(td);}
  body.appendChild(tr);}
 hdr();count.textContent=rs.length+' / '+rows.length+' rows';}
// filters
for(const id of ['fds','frank','farch'])document.getElementById(id);
[...new Set(rows.map(r=>r.rank).filter(v=>v!=null))].sort((a,b)=>a-b).forEach(v=>frank.add(new Option(v,v)));
[...new Set(rows.map(r=>r.arch).filter(Boolean))].forEach(v=>farch.add(new Option(v,v)));
['fds','frank','farch'].forEach(id=>document.getElementById(id).onchange=render);
ftext.oninput=render;
// dataset baseline strip
let bh='<b>Dataset training baselines</b> (same algorithm as the eval extractors → drift-readable). ';
bh+='<span class=hi>Stereo narrowing is a MODEL artifact:</span> goa training stereo_corr '+base.goa.stereo_corr+' / avp '+base.avp.stereo_corr+' (wide) vs renders ≈0.88 (narrow). ';
bh+='<br><b>goa</b>: stereo_corr '+base.goa.stereo_corr+' · dissonance '+base.goa.dissonance+' · inharm '+base.goa.inharmonicity+' · moods '+(base.goa.mood_top||[]).slice(0,5).join(', ');
bh+='<br><b>avp</b>: stereo_corr '+base.avp.stereo_corr+' · dissonance '+base.avp.dissonance+' · inharm '+base.avp.inharmonicity+' · moods '+(base.avp.mood_top||[]).slice(0,5).join(', ');
document.getElementById('base').innerHTML=bh;
render();
</script></body></html>"""


if __name__ == "__main__":
    main()
