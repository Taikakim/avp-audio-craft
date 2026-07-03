#!/usr/bin/env python3
"""Build the DoRA quality-audition page (same-playhead audio cells, up to MASTER spec).

The gap the audition pipeline had: build_manifest.py emits manifest.json but there was no
index.html template. This builds a self-contained page from the DoRA eval outputs:

  - reads <render-dir>/quality_eval.json  ({meta, checkpoints:[{tag, frechet_mid,
    cos_dist_mid, cos_dist_upper, CE, PQ, PC, CU, n_clips}]})  (eval_dora_quality.py)
  - finds the clips per tag:  <tag>__p<i>_seed<seed>.wav
  - encodes WAV -> AAC .m4a @128k (MASTER §UI: AAC for online; the onset builder used 96k,
    we use 128k per the spec line — quality clips are the point here)
  - emits index.html with the canonical same-playhead behaviour (switching cells keeps the
    playhead position; re-click stops) + a per-variant provenance/metrics box.

Variants are sorted by frechet_mid (lower = closer to the Goa corpus). Works for the
baseline soups (r16/r64/r128f) and the upcoming cautious variants alike — it just reads
whatever tags are in quality_eval.json.

Run (SA3 venv not required — stdlib + ffmpeg only):
    python Misc/build_dora_audition_page.py \
        --render-dirs stable-audio-3/renders_dora stable-audio-3/renders_soups \
        --out stable-audio-3/renders_dora_audition

Then serve over http (the page fetches nothing, but browsers still need http for audio on
some setups):  cd <out> && python -m http.server 8000  ->  http://localhost:8000/
"""
from __future__ import annotations
import argparse, glob, json, os, re, shutil, subprocess
from concurrent.futures import ThreadPoolExecutor

# The 3 eval prompts (eval_dora_cpu.py); index = p<i>. Fallback to "p{i}" if more appear.
PROMPTS = [
    "aggressive upbeat goa trance",
    "energetic acid techno, 130 BPM, analog bassline",
    "psytrance, 140 bpm",
]
CLIP_RE = re.compile(r"^(?P<tag>.+)__p(?P<pi>\d+)_seed(?P<seed>\d+)\.wav$")


def gather(render_dirs):
    """-> (variants list, clip-conversion jobs). Each variant: tag, metrics, clips[]."""
    variants, conv = [], []
    for rd in render_dirs:
        qpath = os.path.join(rd, "quality_eval.json")
        if not os.path.isfile(qpath):
            print(f"  skip {rd}: no quality_eval.json")
            continue
        q = json.load(open(qpath))
        for ck in q.get("checkpoints", []):
            tag = ck["tag"]
            clips = []
            for wav in sorted(glob.glob(os.path.join(rd, f"{tag}__p*_seed*.wav"))):
                m = CLIP_RE.match(os.path.basename(wav))
                if not m:
                    continue
                pi, seed = int(m["pi"]), int(m["seed"])
                clips.append({"wav": wav, "pi": pi, "seed": seed})
            variants.append({"tag": tag, "src_dir": os.path.basename(rd.rstrip("/")),
                             "metrics": {k: ck.get(k) for k in
                                         ("frechet_mid", "cos_dist_mid", "cos_dist_upper",
                                          "CE", "PQ", "PC", "CU", "n_clips")},
                             "clips": clips})
    return variants


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--render-dirs", nargs="+",
                    default=["stable-audio-3/renders_dora", "stable-audio-3/renders_soups"])
    ap.add_argument("--out", default="stable-audio-3/renders_dora_audition")
    ap.add_argument("--bitrate", default="128k")
    ap.add_argument("--title", default="DoRA quality audition — MERT-to-Goa + Audiobox")
    args = ap.parse_args()

    clipdir = os.path.join(args.out, "clips")
    os.makedirs(clipdir, exist_ok=True)
    variants = gather(args.render_dirs)
    if not variants:
        raise SystemExit("no variants found (no quality_eval.json with checkpoints)")

    # Encode clips -> m4a; rewrite each clip to its relative href.
    conv = []
    for v in variants:
        for c in v["clips"]:
            stem = f"{v['tag']}__p{c['pi']}_seed{c['seed']}.m4a"
            dst = os.path.join(clipdir, stem)
            c["f"] = f"clips/{stem}"
            if os.path.exists(c["wav"]) and not os.path.exists(dst):
                conv.append((c["wav"], dst))
            elif not os.path.exists(c["wav"]) and not os.path.exists(dst):
                c["f"] = None  # metrics-only (clips were cleaned)

    def cv(job):
        subprocess.run(["ffmpeg", "-y", "-i", job[0], "-c:a", "aac", "-b:a", args.bitrate, job[1]],
                       capture_output=True)
    print(f"variants {len(variants)} | clips to encode {len(conv)}")
    if conv:
        with ThreadPoolExecutor(max_workers=8) as ex:
            list(ex.map(cv, conv))
    print("encoding done")

    # Sort variants by closeness to Goa (frechet_mid asc; None last).
    variants.sort(key=lambda v: (v["metrics"]["frechet_mid"] is None,
                                 v["metrics"]["frechet_mid"] or 9e9))
    best = variants[0]["tag"] if variants else None
    DATA = json.dumps({"variants": variants, "prompts": PROMPTS, "best": best})

    T = r"""<!doctype html><html><head><meta charset=utf-8><title>__TITLE__</title><style>
body{font:12px system-ui;margin:0;background:#0e0e10;color:#e0e0e0}
#hdr{position:sticky;top:0;z-index:9;background:#16181c}
#bar{padding:8px 12px;border-bottom:1px solid #2a2a30}
#info{background:#0f1a14;border-top:1px solid #243;border-bottom:1px solid #243;border-left:3px solid #5d9;padding:8px 12px;color:#cde}#info b{color:#9ec}#info .p{color:#9aa;margin-top:3px}
#wrap{padding:12px;max-width:1100px}
h2{font-size:14px;color:#9cf;margin:16px 0 2px;border-top:1px solid #26262c;padding-top:10px}
.metrics{color:#9ab;font-size:11px;margin:2px 0 5px}.metrics b{color:#cde}.win{color:#5d9}
.clips{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:6px}
.c{cursor:pointer;border:1px solid #2a2a30;background:#1c1c22;padding:4px 9px;border-radius:4px}
.c:hover{outline:1px solid #7cf}.play{outline:2px solid #5d5 !important}.muted{color:#666}
input{background:#1c1c22;color:#ddd;border:1px solid #2a2a30;padding:3px 7px;margin-left:10px}a{color:#7cf}
</style></head><body>
<div id=hdr><div id=bar>&#9654; <b id=np>click a clip to play</b> <span id=pos class=muted></span>
&nbsp;·&nbsp; <span class=muted>switching clips keeps the playhead; re-click stops · sorted by MERT-to-Goa (lower=closer) · <span class=win>green = best</span></span>
<input id=flt placeholder="filter: r128f, goodearly, caut…" oninput="filt()"></div>
<div id=info>tap any clip or variant header for its metrics + provenance</div></div>
<div id=wrap></div>
<script>const D=__DATA__;
const au=new Audio();let cur=null;
au.addEventListener('timeupdate',()=>{document.getElementById('pos').textContent=cur?('· '+au.currentTime.toFixed(1)+'s'):'';});
au.addEventListener('ended',()=>{cur=null;mark();});
function mark(){document.querySelectorAll('.c.play').forEach(e=>e.classList.remove('play'));if(cur){const e=document.getElementById(cur);if(e)e.classList.add('play');}}
function fmt(x,n){return x==null?'·':(+x).toFixed(n);}
function showInfo(vi){const v=D.variants[vi],m=v.metrics,ib=document.getElementById('info');
 ib.style.display='block';ib.innerHTML=`<b>${v.tag}</b> <span class=muted>(${v.src_dir})</span> &nbsp; `+
 `frechet ${fmt(m.frechet_mid,4)} · cos_mid ${fmt(m.cos_dist_mid,4)} · cos_up ${fmt(m.cos_dist_upper,4)} &nbsp;|&nbsp; `+
 `CE ${fmt(m.CE,2)} · PQ ${fmt(m.PQ,2)} · PC ${fmt(m.PC,2)} · CU ${fmt(m.CU,2)}`+
 `<div class=p>lower frechet/cos = closer to the Goa corpus (MERT mid layers). Audiobox 1–10; PC is the genre-neutral axis. ${v.tag===D.best?'<span class=win>● best frechet</span>':''}</div>`;}
function play(id,f,lbl,vi){
  if(!f){return;}
  if(cur===id){au.pause();cur=null;mark();document.getElementById('np').textContent='stopped';return;}
  const pos=(cur!==null&&!au.paused)?au.currentTime:0;
  cur=id;mark();document.getElementById('np').textContent='▶ '+lbl;showInfo(vi);
  au.src=f;const go=()=>{try{au.currentTime=Math.min(pos,(au.duration||1e9)-0.05);}catch(e){}au.play();};
  if(au.readyState>=1)go();else au.addEventListener('loadedmetadata',go,{once:true});}
let h='';
D.variants.forEach((v,vi)=>{
 const m=v.metrics,win=v.tag===D.best;
 h+=`<div class=sec data-k="${v.tag.toLowerCase()}"><h2 onclick="showInfo(${vi})" style="cursor:pointer">${v.tag} ${win?'<span class=win>● best</span>':''}</h2>`;
 h+=`<div class=metrics>frechet <b>${fmt(m.frechet_mid,4)}</b> · cos_mid <b>${fmt(m.cos_dist_mid,4)}</b> · cos_up ${fmt(m.cos_dist_upper,4)} &nbsp;|&nbsp; CE <b>${fmt(m.CE,2)}</b> · PQ ${fmt(m.PQ,2)} · PC ${fmt(m.PC,2)} · CU ${fmt(m.CU,2)} <span class=muted>(${m.n_clips} clips)</span></div>`;
 h+='<div class=clips>';
 v.clips.forEach(c=>{
   const pr=D.prompts[c.pi]||('p'+c.pi);const lbl=`${v.tag} · ${pr} · seed${c.seed}`;
   const id=(v.tag+'_p'+c.pi+'_s'+c.seed).replace(/[^A-Za-z0-9_]/g,'');
   if(c.f)h+=`<span class=c id="${id}" onclick="play('${id}','${c.f}','${lbl.replace(/'/g,"")}',${vi})">p${c.pi}·seed${c.seed}</span>`;
   else h+=`<span class="c muted" title="clip not on disk">p${c.pi}·seed${c.seed}</span>`;
 });
 h+='</div></div>';
});
document.getElementById('wrap').innerHTML=h;
function filt(){const q=document.getElementById('flt').value.toLowerCase();document.querySelectorAll('.sec').forEach(s=>{s.style.display=s.dataset.k.includes(q)?'':'none';});}
</script></body></html>"""
    html = T.replace("__DATA__", DATA).replace("__TITLE__", args.title)
    out_html = os.path.join(args.out, "index.html")
    open(out_html, "w").write(html)
    print(f"wrote {out_html}  ({len(variants)} variants, best={best})")
    print(f"serve:  cd {args.out} && python -m http.server 8000  ->  http://localhost:8000/")


if __name__ == "__main__":
    main()
