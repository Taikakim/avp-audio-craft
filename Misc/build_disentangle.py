import os, re, glob, json, subprocess, sys, warnings
warnings.filterwarnings("ignore"); os.environ["TF_CPP_MIN_LOG_LEVEL"]="3"
from concurrent.futures import ThreadPoolExecutor
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comment_notes_block import notes_block
import essentia; essentia.log.warningActive=False; essentia.log.infoActive=False
import essentia.standard as es
import librosa

R="/run/media/kim/Mantu/sa3_control_runs"; REPO=os.path.expanduser("~/riffer-evals")
AAC=f"{REPO}/clips_online_aac"; os.makedirs(AAC, exist_ok=True)
PURP=json.load(open(f"{REPO}/run_purposes.json"))
OPB=f"{R}/onset_Fusion_opb_lr1.5e-4_30ep"

def groove(path):
    y,sr=librosa.load(path,sr=22050,mono=True); oe=librosa.onset.onset_strength(y=y,sr=sr)
    if oe.std()<1e-9: return 0.0
    oe=(oe-oe.mean())/oe.std(); ac=librosa.autocorrelate(oe); fps=sr/512; lo,hi=int(0.3*fps),int(1.0*fps)
    return float(ac[lo:hi].max()/(ac[0]+1e-9)) if hi<len(ac) and ac[0]>0 else 0.0
def measure(c):
    try:
        a=es.MonoLoader(filename=c,sampleRate=44100)()
        bpm=float(es.RhythmExtractor2013(method="multifeature")(a)[0]); gr=groove(c)
        return bpm,gr
    except Exception: return 0.0,0.0

eps=[(5,27000),(10,54000),(14,75600),(15,81000),(25,135000)]
# gather + measure (parallel 8) + AAC encode (parallel 8)
clips=[]
for ep,step in eps:
    d=f"{OPB}/onset_eval_opb_ep{ep}"; j=f"{d}/onset_eval.json"
    if not os.path.exists(j): continue
    rows=json.load(open(j))
    for r in rows:
        g,q,m=r['gain'],r['requested'],r['measured']
        wav=f"{d}/onset_g{g:g}_d{q:g}.wav"
        if os.path.exists(wav): clips.append({"ep":ep,"gain":g,"req":q,"meas":m,"wav":wav})
print(f"{len(clips)} opb clips to measure")
def do(c): c["bpm"],c["groove"]=measure(c["wav"]); return c
with ThreadPoolExecutor(max_workers=8) as ex: clips=list(ex.map(do, clips))
# AAC encode
aacdir=f"{AAC}/opb"; os.makedirs(aacdir,exist_ok=True); enc=[]
for c in clips:
    m4a=f"{aacdir}/ep{c['ep']}_g{c['gain']:g}_d{c['req']:g}.m4a"
    c["f"]=f"clips_online_aac/opb/ep{c['ep']}_g{c['gain']:g}_d{c['req']:g}.m4a"
    if not os.path.exists(m4a): enc.append((c["wav"],m4a))
def cv(p): subprocess.run(["ffmpeg","-y","-i",p[0],"-c:a","aac","-b:a","96k",p[1]],capture_output=True)
with ThreadPoolExecutor(max_workers=8) as ex: list(ex.map(cv, enc))
print(f"measured + AAC-encoded ({len(enc)} new)")

def corr(xs,ys): return round(float(np.corrcoef(xs,ys)[0,1]),2) if len(set(xs))>1 else None
srcs=[]
for ep,step in eps:
    cs=[c for c in clips if c['ep']==ep]
    if not cs: continue
    gains=sorted({c['gain'] for c in cs}); reqs=sorted({c['req'] for c in cs})
    agg={}
    for g in gains:
        gc=[c for c in cs if c['gain']==g]
        agg[f"{g:g}"]={"ctrl":corr([c['req'] for c in gc],[c['meas'] for c in gc]),
                       "tempo":corr([c['req'] for c in gc],[c['bpm'] for c in gc]),
                       "groove":round(float(np.mean([c['groove'] for c in gc])),2),
                       "omin":round(min(c['meas'] for c in gc),1),"omax":round(max(c['meas'] for c in gc),1)}
    cells={f"{c['gain']:g}|{c['req']:g}":{"m":round(c['meas'],1),"g":round(c['groove'],2),"b":round(c['bpm'],0),"f":c['f']} for c in cs}
    srcs.append({"ep":ep,"step":step,"gains":[f"{g:g}" for g in gains],"reqs":[f"{q:g}" for q in reqs],
                 "agg":agg,"cells":cells,
                 "overall_tempo":corr([c['req'] for c in cs],[c['bpm'] for c in cs]),
                 "overall_ctrl":corr([c['req'] for c in cs],[c['meas'] for c in cs])})
P=PURP["opb"]
DATA=json.dumps({"srcs":srcs,"meta":P})
T=r"""<!doctype html><html><head><meta charset=utf-8><title>onset_per_beat disentanglement</title><style>
body{font:13px system-ui;margin:0;background:#0e0e10;color:#e0e0e0;max-width:1150px}
#bar{position:sticky;top:0;background:#16181c;padding:7px 12px;border-bottom:1px solid #2a2a30;z-index:9}
#wrap{padding:14px}h1{font-size:18px}h2{font-size:15px;color:#9cf;margin:20px 0 3px}a{color:#7cf}.muted{color:#888}
#info{background:#11161c;border:1px solid #243;border-left:3px solid #5d9;padding:8px 12px;font-size:12px;margin:8px 0}#info b{color:#9ec}#info .p{color:#9aa;margin-top:3px}
.head{background:#16181c;border:1px solid #2a2a30;border-radius:8px;padding:11px 15px;margin:8px 0}.big{font-size:26px;font-weight:600}.kill{color:#5d5}.bad{color:#e66}
table{border-collapse:collapse;font-size:12px;margin:5px 0}td,th{border:1px solid #2a2a30;padding:4px 9px;text-align:center}
th{background:#1c1c22}td:first-child,th:first-child{text-align:left;color:#bbb}.c{cursor:pointer;font-variant-numeric:tabular-nums}.c:hover{outline:2px solid #7cf}.play{outline:2px solid #5d5 !important}.loading{outline:2px solid #fa5 !important}.sub{color:#888;font-size:11px}
</style></head><body>
<div id=bar>&#9654; <b id=np>click a cell to play</b> <span id=pos class=muted></span> <span id=ld class=muted style="color:#fa5"></span> <span class=muted>· switching keeps the playhead · loops until stopped · amber outline = loading</span></div>
<div id=wrap>
<h1>onset_per_beat &mdash; tempo-shortcut disentanglement</h1>
<div id=info></div>
<div class=head>opb tempo-shortcut <span class=big id=hl>&mdash;</span> &nbsp; vs onset_density baseline <b>+0.7&hellip;+0.9</b>
<div class=sub>corr(requested opb, output BPM) — near zero = the model no longer fakes density via tempo. Control authority climbs ep5→15 while this stays dead = the disentanglement is learned.</div></div>
<div id=out></div></div>
<audio id=au_el></audio>
<script>const D=__DATA__;
const au=document.getElementById('au_el'),npx=document.getElementById('np');let cur=null;
au.loop=true;
au.addEventListener('timeupdate',()=>{document.getElementById('pos').textContent=cur?('· '+au.currentTime.toFixed(1)+'s'):'';});
au.addEventListener('waiting',()=>{document.getElementById('ld').textContent='loading…';markLoading(true);});
au.addEventListener('playing',()=>{document.getElementById('ld').textContent='';markLoading(false);});
function mark(){document.querySelectorAll('.c.play').forEach(e=>e.classList.remove('play'));if(cur){const e=document.getElementById(cur);if(e)e.classList.add('play');}}
function markLoading(on){document.querySelectorAll('.c.loading').forEach(e=>e.classList.remove('loading'));if(on&&cur){const e=document.getElementById(cur);if(e)e.classList.add('loading');}}
function startClip(id,f,l){const pos=(cur!==null&&!au.paused)?au.currentTime:0;cur=id;mark();npx.textContent='▶ '+l;document.getElementById('ld').textContent='loading…';markLoading(true);au.src=f;const go=()=>{try{au.currentTime=((au.duration&&pos>au.duration-1)?0:Math.min(pos,(au.duration||1e9)-0.05));}catch(e){}au.play();};if(au.readyState>=1)go();else au.addEventListener('loadedmetadata',go,{once:true});}
function play(id,f,l){if(cur===id){au.pause();cur=null;mark();npx.textContent='stopped';document.getElementById('ld').textContent='';return;}startClip(id,f,l);}
function noteCk(ep,f){if(window.noteSet)noteSet({model:'__RUN__',ckpt:'ep'+ep,clip:f.split('/').pop()});}
const M=D.meta;document.getElementById('info').innerHTML=`<b>${M.run}</b> · ${M.optimizer} · lr ${M.lr} · ${M.scalar_field} · ${M.epochs}ep<div class=p>${M.purpose}</div>`;
function gcol(g){let t=Math.max(0,Math.min(1,(g-0.5)/0.45));return`hsl(${Math.round(t*120)},45%,23%)`;}
function tcol(c){if(c==null)return'#1a1a1f';return`hsl(${Math.round((1-Math.abs(c))*120)},45%,23%)`;}
function ccol(c){if(c==null)return'#1a1a1f';return`hsl(${Math.round(Math.max(0,c)*120)},45%,23%)`;}
let h='';
for(const s of D.srcs){
 h+=`<h2>ep${s.ep} <span class=sub>(step ${s.step})</span></h2><div class=sub>overall: control ${s.overall_ctrl} · tempo-shortcut ${s.overall_tempo}</div>`;
 h+='<table><tr><th>gain</th><th>control&nbsp;corr</th><th>tempo-shortcut</th><th>groove</th><th>out range</th></tr>';
 for(const g of s.gains){const a=s.agg[g];h+=`<tr><td>${g}</td><td style="background:${ccol(a.ctrl)}">${a.ctrl}</td><td style="background:${tcol(a.tempo)}">${a.tempo}</td><td style="background:${gcol(a.groove)}">${a.groove}</td><td>${a.omin}–${a.omax}</td></tr>`;}
 h+='</table><table><tr><th>g＼req</th>'+s.reqs.map(q=>`<th>${q}</th>`).join('')+'</tr>';
 for(const g of s.gains){h+=`<tr><td>g${g}</td>`+s.reqs.map(q=>{const c=s.cells[g+'|'+q];if(!c)return'<td>·</td>';const id=`e${s.ep}_${g}_${q}`.replace(/[^A-Za-z0-9_]/g,'');const lbl=`ep${s.ep} g${g} req${q} → ${c.m}, ${c.b}bpm, groove ${c.g}`;return`<td class=c id="${id}" style="background:${gcol(c.g)}" onclick="noteCk('${s.ep}','${c.f}');play('${id}','${c.f}','${lbl}')">${c.m}</td>`;}).join('')+'</tr>';}
 h+='</table>';
}
document.getElementById('out').innerHTML=h;
const last=D.srcs[D.srcs.length-1];if(last&&last.overall_tempo!=null){const m=last.overall_tempo;const e=document.getElementById('hl');e.textContent=(m>=0?'+':'')+m.toFixed(2);e.className='big '+(Math.abs(m)<0.3?'kill':'bad');}
</script>
__NOTES__
</body></html>"""
# comment widget (Kim: build once, drop everywhere) — model = the opb run dir,
# ckpt = epN (per-ckpt fields in the run's run_meta), clip = cell file
T = T.replace("__RUN__", os.path.basename(OPB))
T = T.replace("__NOTES__", notes_block(
    "disentangle",
    levels=[("clip", "this clip"), ("ckpt", "this epoch"),
            ("model", "whole run"), ("page", "whole page")]))
open(f"{REPO}/disentangle.html","w").write(T.replace("__DATA__",DATA))
print(f"disentangle.html built: {len(srcs)} epochs")
for s in srcs: print(f"  ep{s['ep']}: ctrl {s['overall_ctrl']}, tempo {s['overall_tempo']}")
