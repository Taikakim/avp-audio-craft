#!/usr/bin/env python3
"""build_xft_distillation_page.py -- "does a full fine-tune distill to a small
adapter?" verdict page (task #77). Reframes task #71's 60-adapter SVD extraction
per CONTINUITY's DM (2026-07-24, sat unaddressed 5 days -- see WORKLOG 2026-07-29):
her SV-spectrum read of fullft_goa_t256 found the weight delta is NEAR-FULL-RANK, so
no small adapter captures it -- the 60-cell full grid would just be glitch. This page
presents the FINDING (energy-capture + per-class r90 tables, regenerated + verified
independently via eval/svd_energy_spectrum.py -- reproduces her numbers within
rounding) plus a small A/B: xft-extracted (glitch) vs a matched-rank TRAINED straight
DoRA (coherent) at r16 and r128, so the audible contrast makes the point instead of
just asserting it. The other ~55 xft-extracted cells stay rendered on disk (not
deleted -- other analyses may still want them) but are not presented here as if they
were 60 usable models.

Run: python3 Misc/build_xft_distillation_page.py -> ~/evals_aac/xft_distillation.html
"""
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comment_notes_block import notes_block  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RENDER_DIR = Path("/run/media/kim/Mantu/sa3_lora_runs/model_matrix")
STAGE = Path.home() / "evals_aac"
CLIPS = STAGE / "xft_distillation"
CLIPS.mkdir(parents=True, exist_ok=True)

SPECTRUM = json.loads((ROOT / "eval/svd_energy_spectrum.json").read_text())

# (pair label, glitch xft label+ckpt-tag, coherent trained-DoRA label+ckpt-tag, rank)
PAIRS = [
    ("goa · rank 16", "xftdora16_fullft_goa_t256", "adapter",
     "dora16_goa_newstack_8ep", "ep7", 16),
    ("avp · rank 16", "xftdora16_fullft_avp_t256", "adapter",
     "dora16_avp_8ep", "ep6", 16),
    ("avp · rank 128", "xftdora128_fullft_avp_t256", "adapter",
     "dora128adj_avp_8ep_final", "ep0", 128),
]
PROMPTS = [("housestyle", "s1234"), ("rb_common_0", "s786795416")]
CFG, W = 7, 100


def enc(src, dst):
    if not os.path.exists(dst) and os.path.exists(src):
        subprocess.run(["ffmpeg", "-y", "-i", src, "-c:a", "aac", "-b:a", "192k", dst],
                        capture_output=True)


def find_clip(label, ckpt_tag, pid, seed):
    wav = RENDER_DIR / f"{label}__{ckpt_tag}__cfg{CFG}__w{W}__{pid}__{seed}.wav"
    m4a = CLIPS / f"{label}__{ckpt_tag}__{pid}.m4a"
    return wav, m4a


jobs = []
pairs_out = []
for name, glitch_label, glitch_ckpt, coh_label, coh_ckpt, rank in PAIRS:
    clips = []
    for pid, seed in PROMPTS:
        gw, gm = find_clip(glitch_label, glitch_ckpt, pid, seed)
        cw, cm = find_clip(coh_label, coh_ckpt, pid, seed)
        jobs += [(gw, gm), (cw, cm)]
        clips.append({"prompt": pid,
                      "glitch": f"xft_distillation/{gm.name}" if gw.exists() else None,
                      "coherent": f"xft_distillation/{cm.name}" if cw.exists() else None})
    pairs_out.append({"name": name, "rank": rank, "clips": clips})

with ThreadPoolExecutor(max_workers=8) as ex:
    list(ex.map(lambda j: enc(*j), jobs))
print(f"encoded {sum(1 for _, m in jobs if m.exists())}/{len(jobs)} clips")

DATA = json.dumps({"pairs": pairs_out, "spectrum": SPECTRUM})

T = r"""<!doctype html><html><head><meta charset=utf-8><title>Does a full fine-tune distill to an adapter? -- NO (near-full-rank)</title><style>
body{font:13px system-ui;margin:0;background:#0e0e10;color:#e0e0e0;max-width:1100px}
#bar{position:sticky;top:0;background:#16181c;padding:7px 12px;border-bottom:1px solid #2a2a30;z-index:9}
#wrap{padding:14px}h1{font-size:18px}h2{font-size:15px;color:#9cf;margin:20px 0 3px}.muted{color:#888}
#explain{background:#1a140c;border:1px solid #433;border-left:3px solid #d90;padding:10px 12px;font-size:12.5px;color:#dcd;margin:10px 0}#explain b{color:#fc6}
#repro{background:#101418;border:1px solid #234;border-left:3px solid #38a;padding:8px 12px;font-size:11.5px;color:#9bd;margin:10px 0}#repro code{color:#bdf;background:#152030;padding:1px 4px;border-radius:3px}
table{border-collapse:collapse;font-size:12px;margin:4px 0}td,th{border:1px solid #2a2a30;padding:4px 8px;text-align:center}
th{background:#1c1c22;color:#aaa}td:first-child,th:first-child{text-align:left;color:#9ab}
.c{cursor:pointer;font-variant-numeric:tabular-nums}.c:hover{outline:2px solid #7cf}.play{outline:2px solid #5d5 !important}.loading{outline:2px solid #fa5 !important}
.sec{margin:14px 0;padding:10px 12px;border:1px solid #26262c;border-radius:6px;background:#131316}
.glitch{color:#e77}.coherent{color:#5d9}
</style></head><body>
<div id=bar>&#9654; <b id=np>click a cell to play</b> <span id=pos class=muted></span> <span id=ld class=muted style="color:#fa5"></span> <span class=muted>&middot; switching keeps the playhead &middot; loops until stopped</span></div>
<div id=wrap>
<h1>Does a full fine-tune distill to an adapter? -- <span style="color:#e77">NO (near-full-rank)</span></h1>
<div id=explain><b>What we tried:</b> compress a full-DiT fine-tune (every weight moved, not just a LoRA adapter's slice) back down into a small LoRA/DoRA adapter, via truncated SVD of the weight delta (deltaW = W_finetuned - W_base). If it worked, the small adapter would be a much cheaper way to ship the same result.
<br><b>Why it fails:</b> a full fine-tune changes weights in a <b>near-full-rank</b> way -- unlike a style LoRA (which lives in a genuinely low-rank subspace by construction), the fine-tune's weight movement spreads across most of the available directions. The <b>energy-capture table</b> below shows what fraction of the delta's total magnitude (Frobenius energy) survives at each truncation rank, averaged across all 229 trainable modules of one representative full fine-tune (fullft_goa_t256): even rank 512 -- a third of the model's own hidden dimension -- only recovers ~65%. The <b>per-module-class table</b> breaks this down further: the MLP/projection layers need the most rank (median 72% of their dimension for 90% of the energy), attention output layers the least (~49%), but none of them are anywhere close to "small."
<br><b>How to read the audition:</b> below are 3 matched-rank pairs -- an <b>xft-extracted</b> adapter (glitch, SVD-truncated from the fine-tune) next to a <b>trained</b> straight DoRA of the same rank (coherent, learned directly at that rank from scratch). Same prompts, same settings. The contrast is the finding: truncating a near-full-rank delta throws away most of what made the fine-tune work, while a DoRA trained AT that rank from the start learns something the rank can actually hold.</div>
<div id=repro>reproduce: <code>eval/extract_svd_adapters.py</code> (the 60-adapter extraction, task #71) &middot; <code>eval/svd_energy_spectrum.py --parent fullft_goa_t256</code> (this page's tables, regenerated independently -- reproduces CONTINUITY's original DM numbers within rounding). Redaction: rank/energy numbers are open science; checkpoint filenames/paths are kept off this page.</div>
<div id=summary></div>
<div id=out></div></div>
<audio id=au_el></audio>
<script>const D=__DATA__;
const au=document.getElementById('au_el'),npx=document.getElementById('np');let cur=null;
au.loop=true;
au.addEventListener('timeupdate',()=>{document.getElementById('pos').textContent=cur?('&middot; '+au.currentTime.toFixed(1)+'s'):'';});
au.addEventListener('waiting',()=>{document.getElementById('ld').textContent='loading...';markLoading(true);});
au.addEventListener('playing',()=>{document.getElementById('ld').textContent='';markLoading(false);});
function mark(){document.querySelectorAll('.c.play').forEach(e=>e.classList.remove('play'));if(cur){const e=document.getElementById(cur);if(e)e.classList.add('play');}}
function markLoading(on){document.querySelectorAll('.c.loading').forEach(e=>e.classList.remove('loading'));if(on&&cur){const e=document.getElementById(cur);if(e)e.classList.add('loading');}}
function startClip(id,f,l,pair,clip){
 if(window.noteSet)noteSet({model:'xft_distillation',ckpt:pair,clip:clip});
 const pos=(cur!==null&&!au.paused)?au.currentTime:0;cur=id;mark();npx.textContent='▶ '+l;
 document.getElementById('ld').textContent='loading...';markLoading(true);
 au.src=f;const go=()=>{try{au.currentTime=((au.duration&&pos>au.duration-1)?0:Math.min(pos,(au.duration||1e9)-0.05));}catch(e){}au.play();};
 if(au.readyState>=1)go();else au.addEventListener('loadedmetadata',go,{once:true});}
function play(id,f,l,pair,clip){
 if(cur===id){au.pause();cur=null;mark();npx.textContent='stopped';document.getElementById('ld').textContent='';return;}
 startClip(id,f,l,pair,clip);}
let h='';
h+='<div class=sec><h2>whole-model uniform-rank energy capture</h2><div class=muted>fraction of the delta\'s total Frobenius energy recovered if EVERY module is truncated to rank r (fullft_goa_t256, 229 modules)</div><table><tr><th>rank</th>';
const ladder=Object.keys(D.spectrum.whole_model_uniform_rank_energy);
ladder.forEach(r=>h+=`<th>${r}</th>`);
h+='</tr><tr><td>energy captured</td>';
ladder.forEach(r=>h+=`<td>${(D.spectrum.whole_model_uniform_rank_energy[r]*100).toFixed(1)}%</td>`);
h+='</tr></table></div>';
h+='<div class=sec><h2>per-module-class median r90 (rank needed for 90% energy)</h2><table><tr><th>class</th><th>n modules</th><th>dim</th><th>median r90</th><th>r90 / dim</th></tr>';
Object.entries(D.spectrum.class_summary).forEach(([cls,s])=>{
 h+=`<tr><td>${cls}</td><td>${s.n_modules}</td><td>${s.dim}</td><td>${s.median_r90}</td><td>${(s.median_r90_frac*100).toFixed(0)}%</td></tr>`;});
h+='</table></div>';
document.getElementById('summary').innerHTML=h;
h='';
D.pairs.forEach((p,pi)=>{
 h+=`<div class=sec><h2>${p.name}</h2>`;
 p.clips.forEach((c,ci)=>{
  h+=`<div style="margin:6px 0"><span class=muted>${c.prompt}:</span> `;
  if(c.glitch){const id=`g_${pi}_${ci}`;
   h+=`<span class="c glitch" id="${id}" onclick="play('${id}','${c.glitch}','${p.name} xft-extracted r${p.rank} ${c.prompt}','${p.name}','${c.glitch}')">&#9654; xft-extracted (glitch)</span> `;}
  if(c.coherent){const id=`c_${pi}_${ci}`;
   h+=`<span class="c coherent" id="${id}" onclick="play('${id}','${c.coherent}','${p.name} trained-DoRA r${p.rank} ${c.prompt}','${p.name}','${c.coherent}')">&#9654; trained DoRA (coherent)</span>`;}
  h+='</div>';});
 h+='</div>';});
document.getElementById('out').innerHTML=h;
</script>
__NOTES__
<footer style="margin:18px 12px;color:#666;font-size:11px">aavepyora.online &middot; evals &middot; xft distillation verdict &middot; source: eval/extract_svd_adapters.py, eval/svd_energy_spectrum.py</footer>
</body></html>"""

T = T.replace("__NOTES__", notes_block(
    "xft_distillation",
    levels=[("clip", "this clip"), ("ckpt", "this pair"), ("page", "whole page")],
    hint="click a cell then note the verdict here"))
out = STAGE / "xft_distillation.html"
out.write_text(T.replace("__DATA__", DATA))
print(f"wrote {out}: {len(pairs_out)} pairs, {sum(len(p['clips']) for p in pairs_out)} prompt-rows")
