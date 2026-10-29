#!/usr/bin/env python3
# Owner: CONTINUITY (created 2026-10-28)
"""build_e21_transposition_page.py -- listening + results page for EXPERIMENTS E21 (second run): does chroma steering follow a
transposed target? 14 canonical matrix prompts x {hpcp, same_chroma} x {C, Eb, F#, A} x gains {512, 2048} + unguided.

Reads the run dir written by eval/e21b_transposition_server.py (cells.jsonl, e21b_results.json, run_meta.json), stages the clips as
256 kbps AAC under ~/evals_aac/e21_transposition/ and writes ~/evals_aac/e21_transposition.html. No drive paths on the page
(checkpoint filenames are fine since 2026-10-29, Kim). W publishes.
2026-10-29: also folds in E21c (SRC2, eval/run_e21c_20261029.sh): the production same_chroma head at 4096/8192 and the E13-retrained
same_chroma head (C3 lr 1e-3 ep10) at 512/2048, same prompts/seeds/settings, unguided shared with E21b.
"""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "eval"))
from comment_notes_block import notes_block
from float_player import inject

SRC = "/run/media/kim/Mantu/sa3_control_runs/e21b_transposition_canon_20261028"
SRC2 = "/run/media/kim/Mantu/sa3_control_runs/e21c_same_chroma_gain_20261029"
STAGE = os.path.join(os.path.expanduser("~"), "evals_aac")
SUB = "e21_transposition"
KEYS = {"0": "C", "3": "E♭", "6": "F♯", "9": "A"}

RUNS = [d for d in (SRC, SRC2) if os.path.exists(f"{d}/e21b_results.json")]
rows, seen, res, pcs = [], set(), {"summary": {}, "dead_clips_peak_1": []}, {}
for d in RUNS:
    tag = "E21c" if d == SRC2 else "E21b"
    for l in open(f"{d}/cells.jsonl"):
        if l.strip():
            r = json.loads(l)
            if r["id"] not in seen:                     # unguided renders are shared (E21c copied E21b's)
                seen.add(r["id"]); rows.append({**r, "src": d})
    rr = json.load(open(f"{d}/e21b_results.json"))
    for k, v in rr["summary"].items():
        res["summary"][k] = {**v, "run": tag}
    res["dead_clips_peak_1"] += rr["dead_clips_peak_1"]
    pcs[tag] = rr["positive_control_bungee"]
res["positive_control_bungee"] = pcs
meta = json.load(open(f"{SRC}/run_meta.json"))
meta2 = json.load(open(f"{SRC2}/run_meta.json")) if SRC2 in RUNS else {}
for v in (meta2.get("recipe", {}).get("heads") or {}).values():   # no drive paths on the page
    v["path"] = os.path.basename(v["path"])
if meta2.get("recipe", {}).get("unguided_from"):
    meta2["recipe"]["unguided_from"] = "the E21b run (same prompts, seeds and settings)"
import model_matrix_gen as M  # noqa: E402
PROMPTS = {p["id"]: {"text": p["text"], "seed": p["seed"]} for p in M.build_prompts(n_per_band=3, n_kimlong=3)}

os.makedirs(os.path.join(STAGE, SUB), exist_ok=True)
pos = [(d, f[:-4]) for d in RUNS for f in sorted(os.listdir(d)) if f.startswith("posctl__") and f.endswith(".wav")]
jobs = [(f"{r['src']}/{r['id']}.wav", os.path.join(STAGE, SUB, f"{r['id']}.m4a")) for r in rows] + \
       [(f"{d}/{i}.wav", os.path.join(STAGE, SUB, f"{i}.m4a")) for d, i in pos]
pos = [i for _, i in pos]
for src, dst in jobs:
    if not os.path.exists(dst):
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", src, "-c:a", "aac", "-b:a", "256k", dst], check=True)
br = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=bit_rate", "-of", "csv=p=0", jobs[0][1]],
                    capture_output=True, text=True).stdout.strip()
kbps = f"{int(br) // 1000} kbps" if br.isdigit() else "unknown"

clips = {r["id"]: {"f": f"{SUB}/{r['id']}.m4a", "pid": r["pid"], "head": r["head"], "k": r.get("k"), "g": r.get("gain")} for r in rows}
for i in pos:
    clips[i] = {"f": f"{SUB}/{i}.m4a", "pid": i.split("__")[1], "head": "posctl", "k": int(i.rsplit("__k", 1)[1]), "g": None,
                "src": i[len("posctl__"):].rsplit("__k", 1)[0]}
HEADS = {}
for r in rows:
    if r["head"]:
        HEADS.setdefault(r["head"], set()).add(int(r["gain"]))
LABEL = {"hpcp": "hpcp (production head, latch_sa3_hpcp_best.pt)",
         "same_chroma": "same_chroma (production head, latch_sa3_same_chroma_best.pt)",
         "same_chroma_e13": "same_chroma retrained in E13 (C3, lr 1e-3, epoch 10, latch_sa3_same_chroma_ep10.pt)"}
DATA = json.dumps({"prompts": PROMPTS, "keys": KEYS, "clips": clips,
                   "heads": [{"name": h, "gains": sorted(g), "label": LABEL.get(h, h)} for h, g in HEADS.items()],
                   "res": res, "recipe": meta.get("recipe", {}), "recipe2": meta2.get("recipe", {}), "kbps": kbps})

T = r"""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Chroma Transposition Probe</title><style>
:root{--bg:#0e0e10;--fg:#e0e0e0;--bar:#16181c;--line:#2a2a30;--th:#1c1c22;--muted:#888;--acc:#cde}
@media (prefers-color-scheme: light){:root:not([data-theme="dark"]){--bg:#fafafa;--fg:#222;--bar:#eef0f3;--line:#d4d4da;--th:#e8e8ee;--muted:#666;--acc:#245}}
body{font:13px system-ui;margin:0;background:var(--bg);color:var(--fg)}
#bar{position:sticky;top:0;background:var(--bar);padding:7px 12px;border-bottom:1px solid var(--line);z-index:9}
#wrap{padding:14px 16px;max-width:min(2200px,94vw);margin:0 auto}h1{font-size:18px}h2{font-size:15px;margin:26px 0 4px;color:var(--acc)}.muted{color:var(--muted)}
.explain{background:#1a140c;border:1px solid #433;border-left:3px solid #d90;padding:10px 12px;font-size:12.5px;color:#dcd;margin:10px 0;line-height:1.5;max-width:1100px}.explain b{color:#fc6}
@media (prefers-color-scheme: light){.explain{background:#fff6e6;color:#432;border-color:#e5c48a}.explain b{color:#a50}}
table{border-collapse:collapse;font-size:12px;margin:4px 0;display:block;overflow-x:auto}td,th{border:1px solid var(--line);padding:4px 6px;text-align:center;white-space:nowrap}
th{background:var(--th);color:var(--muted)}td.l{text-align:left;white-space:normal;min-width:220px;max-width:420px}
.num{font-variant-numeric:tabular-nums}.good{color:#4b4}.bad{color:#d55}
.b{display:inline-block;cursor:pointer;border:1px solid var(--line);border-radius:3px;padding:1px 5px;margin:1px;font-size:11px;background:var(--th)}
.b:hover{outline:1px solid #7cf}.play{outline:2px solid #5d5 !important}.un{color:#e44;font-weight:bold;cursor:help}
</style></head><body>
<div id=bar>&#9654; <b id=np>click a clip to play</b> <span id=pos class=muted></span> <span class=muted>· switching keeps the playhead · re-click stops</span></div>
<div id=wrap><h1>Does chroma steering follow a transposed target?</h1>
<div class=explain><b>What this tests.</b> A <i>chroma head</i> reads which pitch classes (C, C♯, D … B) are sounding from the model's latent while it
generates, and guidance nudges the generation toward a target chord. If the head really steers harmony, asking for the same chord a few semitones higher
should move the music by exactly that interval. That property is called <b>transposition equivariance</b>. A recent symbolic-music paper (Equivariant
Music Transformer, 2026) found standard models do not have it unless trained for it, so we tested ours.
<b>How it was made.</b> The 14 standard prompts of our model matrix, each with its fixed seed, rendered on the goa finetune with the settings that worked
best for the onset-density heads (50 steps, cfg 7, guidance over the whole run, gains 512 and 2048). Each prompt is steered toward a major triad on C,
E♭, F♯ and A (0, 3, 6, 9 semitones up) by two heads: <b>hpcp</b> (12 pitch-class bins) and <b>same_chroma</b> (three registers of pitch class).
<b>How to read it.</b> <b>Follows k</b>: for how many prompts the output's pitch-class profile, rotated, best matches the C version shifted by exactly
k semitones (chance is 1 in 12). <b>Specificity</b>: how much closer the output got to its own chord than to the other three, both measured against the
unguided render; above zero means the head steers toward the chord you asked for. The <b>bungee control</b> takes the C renders and pitch-shifts them
by 3, 6 and 9 semitones; if the meter misses those, nothing else on the page can be trusted.
<b>Follow-up (E21c, 2026-10-29).</b> same_chroma moved the right way but too little in the first pass. Two more arms on the same prompts and
seeds: the production same_chroma head at much higher gains (4096, 8192), and the same_chroma head <b>retrained in E13</b> with our modular optimiser,
at the usual 512 and 2048. The unguided column is shared.
<b>What it cannot tell you.</b> Whether it sounds good or musical; these are pitch-class statistics, measured on the whole clip. __UN__</div>
<div id=out></div>
<h2>Reproducibility</h2><div class=muted id=repro></div></div><audio id=au_el></audio>
<script>const D=__DATA__;
const au=document.getElementById('au_el'),npx=document.getElementById('np');let cur=null;
au.addEventListener('timeupdate',()=>{document.getElementById('pos').textContent=cur?('· '+au.currentTime.toFixed(1)+'s'):'';});
au.addEventListener('ended',()=>{cur=null;mark();});
function mark(){document.querySelectorAll('.b.play').forEach(e=>e.classList.remove('play'));if(cur){document.querySelectorAll('[data-id="'+cur+'"]').forEach(e=>e.classList.add('play'));}}
function play(id){const c=D.clips[id];if(cur===id){au.pause();cur=null;mark();npx.textContent='stopped';return;}
 if(window.noteSet)noteSet({model:'e21_transposition',ckpt:'',clip:id});
 const pos=(cur!==null&&!au.paused)?au.currentTime:0;cur=id;mark();npx.textContent=id+' — '+(D.prompts[c.pid]?.text||'').slice(0,90);au.src=c.f;
 const go=()=>{try{au.currentTime=Math.min(pos,(au.duration||1e9)-0.05);}catch(e){}au.play();};
 if(au.readyState>=1)go();else au.addEventListener('loadedmetadata',go,{once:true});}
const f=(v,d)=>v==null?'–':Number(v).toFixed(d);
const btn=(id,lbl)=>D.clips[id]?`<span class=b data-id="${id}" onclick="play('${id}')">${lbl}</span>`:'<span class=muted>–</span>';
const cid=(pid,h,k,g)=>h?`${pid}__${h}__k${k}__g${g}`:`${pid}__base`;
let h='<h2>1 · Results</h2><table><tr><th>run</th><th>head</th><th>gain</th><th>band</th><th>follows k</th><th>chance</th><th>toward own chord</th><th>toward the others</th><th>specificity</th></tr>';
Object.entries(D.res.summary).forEach(([key,v])=>{const [hd,g,b]=key.split('|');
 h+=`<tr><td>${v.run}</td><td>${hd}</td><td>${g.slice(1)}</td><td>${b}</td><td class=num><b>${v.equivariance_hits}/${v.n}</b></td><td class=num>${v.chance}</td><td class=num>${f(v.own_delta,3)}</td><td class=num>${f(v.other_delta,3)}</td><td class="num ${v.specificity>0?'good':'bad'}">${v.specificity>0?'+':''}${f(v.specificity,3)}</td></tr>`;});
const pc=D.res.positive_control_bungee;h+='</table><div class=muted>bungee control (C renders shifted by 3/6/9 semitones, detected at the right shift): '+
 Object.entries(pc).map(([run,p])=>run+': '+Object.entries(p).map(([b,v])=>`${b} ${v.hits}/${v.n}`).join(', ')).join(' · ')+(D.res.dead_clips_peak_1.length?` · ⚠ ${D.res.dead_clips_peak_1.length} dead clip(s) (peak 1.0): `+D.res.dead_clips_peak_1.join(', '):' · no dead clips')+'</div>';
D.heads.forEach(H=>{const hd=H.name;h+=`<h2>2 · Listen: ${H.label}</h2><div class=muted>Rows are the standard prompts (hover for the full text). Unguided first, then the four target chords at each gain.</div>`;
 h+='<table><tr><th>prompt</th><th>unguided</th>'+H.gains.map(g=>`<th colspan=4>gain ${g}: `+Object.values(D.keys).join(' · ')+'</th>').join('')+'</tr>';
 Object.entries(D.prompts).forEach(([pid,p])=>{h+=`<tr><td class=l title="${p.text.replace(/"/g,'&quot;')}"><b>${pid}</b> <span class=muted>${p.text.slice(0,70)}${p.text.length>70?'…':''}</span></td><td>${btn(cid(pid),'▶')}</td>`+
  H.gains.map(g=>Object.entries(D.keys).map(([k,n])=>`<td>${btn(cid(pid,hd,k,g),n)}</td>`).join('')).join('')+'</tr>';});
 h+='</table>';});
h+='<h2>3 · The bungee control</h2><div class=muted>The C render (gain 2048 in E21b, the production same_chroma at 8192 in E21c) and the same audio pitch-shifted up by 3, 6 and 9 semitones with bungee.</div><table><tr><th>source</th><th>C (original)</th><th>+3</th><th>+6</th><th>+9</th></tr>';
const srcs=[...new Set(Object.values(D.clips).filter(c=>c.head==='posctl').map(c=>c.src))];
srcs.forEach(s=>{h+=`<tr><td class=l>${s}</td><td>${btn(s,'▶')}</td>`+[3,6,9].map(k=>`<td>${btn('posctl__'+s+'__k'+k,'▶')}</td>`).join('')+'</tr>';});
h+='</table>';
document.getElementById('out').innerHTML=h;
const R=D.recipe;document.getElementById('repro').innerHTML=`Model: ${R.finetune||''} · sampler ${R.sampler} · ${R.steps} steps · cfg ${R.cfg} · ${R.duration} s · guidance window ${JSON.stringify(R.latch_window)} (${R.guide_schedule}) · loss ${R.loss} · heads and gains: ${JSON.stringify(R.heads||R.gains)}${D.recipe2.heads?' + E21c '+JSON.stringify(D.recipe2.heads):''} · prompts and seeds: model_matrix_gen.build_prompts · scripts: eval/e21b_transposition_server.py, eval/run_e21c_20261029.sh, eval/e21_bungee_posctl.py, Misc/build_e21_transposition_page.py · chroma meter: SAME octave-band chroma folded to 12 (harmonic.same_chroma) · audio ${D.kbps} AAC (measured).`;
</script>
__NOTES__
<footer style="margin:18px 12px;color:#666;font-size:11px">evals &middot; chroma transposition probe (EXPERIMENTS E21) &middot; equivariance idea: Guo &amp; Dixon, ISMIR 2026 (arXiv 2608.03920)</footer>
</body></html>"""
UN = "" if meta.get("kim_feedback") else '<span class=un title="No listening verdict recorded yet (unaudited).">&#10071;</span> No listening verdict recorded yet.'
T = T.replace("__UN__", UN).replace("__NOTES__", notes_block("e21_transposition", levels=[("clip", "this clip"), ("page", "page")],
                                                            hint="click a clip, then note what you hear"))
out = os.path.join(STAGE, "e21_transposition.html")
open(out, "w").write(inject(T.replace("__DATA__", DATA)))
print(f"wrote {out}: {len(clips)} clips, audio {kbps}")
