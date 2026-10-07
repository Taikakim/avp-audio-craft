#!/usr/bin/env python
"""build_dj_mixes_section.py — add the DJ-style continuous mixes (+ four phone rating buttons) to the
"The Mixtape" page staged at ~/staging/kone-mixtape/ (live: aavepyora.online/files/kone-mixtape/).

Kim 2026-10-07: "add the latest mixes to the webpage we have for them [the Kone mixtape page, on our own
site] ... four large-ish buttons with a phone user in mind, like our clip eval app: A this clip is too
bright, B this clip lacks punch, C the transition that last played felt out of sync, D the transition had
sound elements unfitting to a good transition, so I can rate these on the go. Then ask W to publish it."

WHAT IT DOES
  1. transcodes each mix wav to AAC 256k m4a in the staging dir (skips files that exist);
  2. computes a TIMELINE per mix from the pair renders' run_meta sidecars (clip i is current until the
     midpoint of transition i, transition i = [segment start + a_head, segment end]), so a tap on the
     page can say WHICH clip / transition was under the playhead, and writes only clip/transition
     indices, names and seconds to timelines.json (no local paths: W's publish leak-scan refuses them);
  3. rewrites the block between <!-- DJMIX:BEGIN --> and <!-- DJMIX:END --> in index.html (the block is
     inserted after the lede on first run) with the players and a fixed bottom bar of four buttons.
Buttons POST {type:'mixflag', mix, variant, flag, t, clip, clip_idx, trans_idx, source} to /files/ratings.php
(web/ratings.php 'mixflag' branch), queue in localStorage when offline and retry. Players of the older
versions on the page carry no timeline: a tap there records mix + seconds only.

USAGE  .venv/bin/python eval/build_dj_mixes_section.py --stage ~/staging/kone-mixtape \\
          --mix v6:"v6":RENDER_DIR:MIX_DIR:pairs.json  [--mix v5:...]   (see MIXES below for the real call)
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

SR = 44100
XF = 0.04            # mixtape_assemble_continuous.JOIN_XFADE_SEC (does not move the cumulative position)
BEGIN, END = "<!-- DJMIX:BEGIN -->", "<!-- DJMIX:END -->"
FLAGS = [("A", "bright", "too bright", "this clip is too bright"),
         ("B", "punch", "lacks punch", "this clip lacks punch"),
         ("C", "sync", "out of sync", "the transition that last played felt out of sync"),
         ("D", "unfit", "unfitting sounds", "the transition had sound elements unfitting to a good transition")]


def short(name):
    m = re.match(r"^(.*?)__(ep\d+)", name)
    return f"{m.group(1)} {m.group(2)}" if m else name[:40]


def probe_dur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "csv=p=0", str(p)]).decode().strip())


def timeline(render_dir, pairs_json, mix_wav):
    """clips/transitions in seconds of the assembled mix. render_dir holds NN_<A>_TO_<B>_run_meta.json."""
    metas = sorted(Path(render_dir).glob("*_run_meta.json"))
    pairs = json.loads(Path(pairs_json).read_text()) if pairs_json and Path(pairs_json).exists() else None
    names, segs = [], []
    for k, mp in enumerate(metas):
        m = json.loads(mp.read_text())["measured"]
        cut = round((m["a_head_sec"] + m["overlap_sec"]) * SR) / SR
        segs.append((m["a_head_sec"], cut))
        mm = re.match(r"^\d+_(.*)_TO_(.*)_run_meta\.json$", mp.name)
        if pairs:
            names.append(Path(pairs[k]["a_path"]).stem)
            if k == len(metas) - 1:
                names.append(Path(pairs[k]["b_path"]).stem)
        else:
            names.append(mm.group(1))
            if k == len(metas) - 1:
                names.append(mm.group(2))
    dur = probe_dur(mix_wav)
    s, trans, bounds = 0.0, [], [0.0]
    for k, (a_head, cut) in enumerate(segs):
        t0, t1 = s + a_head, s + cut
        trans.append([round(t0, 2), round(t1, 2)])
        bounds.append(round((t0 + t1) / 2, 2))
        s += cut
    bounds.append(round(dur, 2))
    return {"dur": round(dur, 2), "clips": [short(n) for n in names], "clip_bounds": bounds, "trans": trans}


def player(mix_id, label, desc, fname, tl, kbps):
    n = len(tl["clips"])
    return f"""  <div class="version">
    <h3>{label}</h3>
    <p class="desc">{desc}</p>
    <div class="player">
      <audio controls preload="none" data-mix="{mix_id}" src="{fname}"></audio>
      <div class="stat">{tl['dur'] / 60:.1f} min &middot; {n} clips &middot; {len(tl['trans'])} transitions &middot; AAC {kbps} kbps</div>
    </div>
  </div>"""


CSS = """<style>
#djbar{position:fixed;left:0;right:0;bottom:0;z-index:50;background:var(--surface);border-top:1px solid var(--border);
 padding:8px 10px calc(8px + env(safe-area-inset-bottom));box-shadow:0 -6px 18px #0004}
#djnow{font-family:var(--mono);font-size:11.5px;color:var(--muted);text-align:center;margin:0 0 6px;min-height:15px;
 white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#djgrid{display:grid;grid-template-columns:1fr 1fr;gap:8px;max-width:680px;margin:0 auto}
.djb{min-height:74px;border-radius:14px;border:2px solid var(--border);background:var(--bg);color:var(--text);
 font:inherit;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;padding:6px 8px;
 touch-action:manipulation;user-select:none;-webkit-tap-highlight-color:transparent}
.djb b{font-family:var(--mono);font-size:22px;line-height:1}
.djb span{font-size:13px;line-height:1.15;text-align:center}
.djb.hit{background:var(--accent);color:#fff;border-color:var(--accent)}
#djtoast{position:fixed;left:50%;transform:translateX(-50%);bottom:calc(190px + env(safe-area-inset-bottom));max-width:92vw;
 background:#000c;color:#fff;border-radius:10px;padding:8px 14px;font-size:13px;opacity:0;pointer-events:none;transition:opacity .2s;z-index:60;text-align:center}
#djtoast.on{opacity:1}
body{padding-bottom:210px}
#djmixes h2{font-family:var(--serif);font-weight:560;font-size:1.5rem;margin:0 0 8px}
#djmixes h3{font-family:var(--serif);font-weight:560;font-size:1.2rem;margin:0 0 6px}
</style>"""

JS = """<script>
(function(){
const TL={}, QK='djmix_flag_queue', EP='/files/ratings.php';
let cur=null;
fetch('timelines.json',{cache:'no-store'}).then(r=>r.json()).then(j=>{Object.assign(TL,j);}).catch(()=>{});
const nowEl=document.getElementById('djnow'), toast=document.getElementById('djtoast');
function fmt(t){t=Math.max(0,Math.floor(t));return Math.floor(t/60)+':'+String(t%60).padStart(2,'0');}
function where(a){
 const id=a.dataset.mix, t=a.currentTime, tl=TL[id], out={mix:id,t:t,clip:'',clip_idx:-1,trans_idx:-1};
 if(!tl)return out;
 let i=0; while(i+1<tl.clip_bounds.length-1 && t>=tl.clip_bounds[i+1]) i++;
 out.clip_idx=i; out.clip=tl.clips[Math.min(i,tl.clips.length-1)];
 let k=-1; for(let j=0;j<tl.trans.length;j++){ if(t>=tl.trans[j][0]) k=j; else break; }
 out.trans_idx=k; return out;
}
function label(w){
 const tl=TL[w.mix], n=tl?tl.clips.length:0;
 return w.mix+' '+fmt(w.t)+(w.clip_idx>=0?' \\u00b7 clip '+(w.clip_idx+1)+'/'+n:'')+(w.trans_idx>=0?' \\u00b7 transition '+(w.trans_idx+1):'');
}
function tick(){ if(cur){nowEl.textContent=label(where(cur));} }
document.querySelectorAll('audio[data-mix]').forEach(a=>{
 a.addEventListener('play',()=>{document.querySelectorAll('audio[data-mix]').forEach(b=>{if(b!==a)b.pause();});cur=a;
   if('mediaSession' in navigator){navigator.mediaSession.metadata=new MediaMetadata({title:'Kone mixtape '+a.dataset.mix,artist:'Stable Audio 3 DJ mix'});
     navigator.mediaSession.setActionHandler('previoustrack',()=>{a.currentTime=Math.max(0,a.currentTime-30);});
     navigator.mediaSession.setActionHandler('nexttrack',()=>{a.currentTime=a.currentTime+30;});}});
 a.addEventListener('timeupdate',tick); a.addEventListener('seeked',tick);
});
function say(m){toast.textContent=m;toast.classList.add('on');clearTimeout(say._t);say._t=setTimeout(()=>toast.classList.remove('on'),2600);}
function queue(){try{return JSON.parse(localStorage.getItem(QK)||'[]')}catch(e){return []}}
function save(q){try{localStorage.setItem(QK,JSON.stringify(q))}catch(e){}}
async function flush(){
 let q=queue(); if(!q.length)return; const rest=[];
 for(const rec of q){
  try{const r=await fetch(EP,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(rec)});
      if(!(r.ok||(r.status>=400&&r.status<500&&r.status!==429)))rest.push(rec);}catch(e){rest.push(rec);}
  await new Promise(r=>setTimeout(r,200));
 }
 save(rest); badge();
}
function badge(){const n=queue().length,e=document.getElementById('djunsent');if(e)e.textContent=n?(n+' unsent'):'';}
let last={k:'',ms:0};
document.querySelectorAll('.djb').forEach(b=>b.addEventListener('click',()=>{
 if(!cur){say('press play on a mix first');return;}
 const w=where(cur), flag=b.dataset.flag, needTrans=(flag==='sync'||flag==='unfit');
 if(needTrans && TL[w.mix] && w.trans_idx<0){say('no transition has played yet');return;}
 const key=flag+'|'+w.clip_idx+'|'+w.trans_idx;
 if(key===last.k && Date.now()-last.ms<3000){say('already flagged');return;}
 last={k:key,ms:Date.now()};
 const rec={type:'mixflag',mix:w.mix.split('_')[0].replace(/[^A-Za-z0-9._-]/g,'_'),variant:(w.mix.split('_').slice(1).join('_')||'full').replace(/[^A-Za-z0-9._-]/g,'_'),flag:flag,
   t:Math.round(w.t*10)/10,clip:(w.clip||'').replace(/[^A-Za-z0-9._-]/g,'_').slice(0,120),clip_idx:w.clip_idx,trans_idx:w.trans_idx,source:'kone-mixtape'};
 const q=queue(); q.push(rec); save(q);
 if(navigator.vibrate)navigator.vibrate(40);
 b.classList.add('hit'); setTimeout(()=>b.classList.remove('hit'),350);
 say(b.dataset.say+' \\u2014 '+label(w)); flush(); badge();
}));
window.addEventListener('online',flush); badge(); flush();
})();
</script>"""


def bar():
    btns = "\n".join(f'    <button class="djb" data-flag="{f}" data-say="{short_}"><b>{L}</b><span>{t}</span></button>'
                     for L, f, short_, t in FLAGS)
    return (f'<div id="djtoast"></div>\n<div id="djbar">\n  <p id="djnow">press play on a mix, then tap while it plays</p>'
            f'<span id="djunsent"></span>\n  <div id="djgrid">\n{btns}\n  </div>\n</div>')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", type=Path, required=True)
    ap.add_argument("--mix", action="append", required=True,
                    help="id|label|desc|wav|render_dir|pairs_json   (pairs_json may be empty)")
    ap.add_argument("--heading", default="DJ mixes: beat-aware, built from the retrained models")
    ap.add_argument("--intro", default="")
    ap.add_argument("--bitrate", default="256k", help="AAC bitrate (review-audio standard 256k; the page prints the MEASURED rate)")
    ap.add_argument("--private-out", type=Path, default=None,
                    help="write the full timelines (WITH clip names) here; the public timelines.json carries no "
                         "model/checkpoint names, only 'clip N' (W's leak-scan refuses checkpoint filenames)")
    a = ap.parse_args()
    a.stage.mkdir(parents=True, exist_ok=True)
    tls, cards = {}, []
    for spec in a.mix:
        mid, label, desc, wav, rdir, pj = spec.split("|")
        fname = f"dj_{mid}.m4a"
        out = a.stage / fname
        if not out.exists():
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-c:a", "aac", "-b:a", a.bitrate, str(out)], check=True)
        tls[mid] = timeline(rdir, pj or None, wav)
        kbps = round(float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=bit_rate', '-of', 'csv=p=0', str(out)]).decode().strip()) / 1000)
        cards.append(player(mid, label, desc, fname, tls[mid], kbps))
        print(f"[mix] {mid}: {tls[mid]['dur'] / 60:.1f} min, {len(tls[mid]['clips'])} clips, {out.stat().st_size / 1e6:.0f} MB", flush=True)
    if a.private_out:
        a.private_out.write_text(json.dumps(tls, indent=1))
    pub = {k: {**v, "clips": [f"clip {i + 1}" for i in range(len(v["clips"]))]} for k, v in tls.items()}
    (a.stage / "timelines.json").write_text(json.dumps(pub, separators=(",", ":")))
    block = (f"{BEGIN}\n{CSS}\n<section id=\"djmixes\" style=\"margin-bottom:40px\">\n  <h2>{a.heading}</h2>\n"
             f"  <p class=\"note\">{a.intro}</p>\n" + "\n".join(cards) + f"\n</section>\n{bar()}\n{JS}\n{END}")
    idx = a.stage / "index.html"
    html = idx.read_text()
    if BEGIN in html:
        html = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), lambda m: block, html, flags=re.S)
    else:
        m = re.search(r'<p class="lede">.*?</p>', html, flags=re.S)
        pos = m.end() if m else html.index("<body>") + 6 if "<body>" in html else len(html)
        html = html[:pos] + "\n\n" + block + "\n" + html[pos:]
    idx.write_text(html)
    print("[page] wrote", idx, flush=True)


if __name__ == "__main__":
    main()
