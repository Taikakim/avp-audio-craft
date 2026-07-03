import os, re, glob, json, subprocess
from concurrent.futures import ThreadPoolExecutor
import numpy as np

R="/run/media/kim/Mantu/sa3_control_runs"; REPO=os.path.expanduser("~/riffer-evals")
CD=f"{REPO}/clips_onset_eval"; AAC=f"{REPO}/clips_online_aac"
os.makedirs(CD, exist_ok=True); os.makedirs(AAC, exist_ok=True)
PURP=json.load(open(f"{REPO}/run_purposes.json"))

jsons=sorted(set(glob.glob(f"{R}/onset_eval_*/onset_eval.json")
                 +glob.glob(f"{R}/onset_eval_*/**/onset_eval.json", recursive=True)))

def label_of(d):
    s=os.path.basename(d).replace("onset_eval_","")
    m=re.match(r'(lr\w+?)_(\d+)$', s)
    if m: return (m.group(1), int(m.group(2)), f"{m.group(1)} · step {m.group(2)} (ep{int(m.group(2))//5400})")
    return ("targeted", 0, s)

# gather
raw=[]
for j in jsons:
    d=os.path.dirname(j); name=os.path.basename(d)
    try: rows=json.load(open(j))
    except Exception: continue
    if not isinstance(rows,list) or not rows: continue
    grp,step,lab=label_of(d)
    raw.append((d,name,grp,step,lab,rows))

# --- representative selection for the online (AAC) build ---
online=set()
for grp in ("lr2e5","lr8e5"):                       # per-step sweeps: ~5 evenly-spaced
    g=sorted([r for r in raw if r[2]==grp], key=lambda r:r[3])
    if g:
        idx=sorted(set(int(round(i*(len(g)-1)/4)) for i in range(5)))
        for i in idx: online.add(g[i][1])
for r in raw:                                        # targeted: the recognizable one-offs
    if r[2]=="targeted" and any(k in r[1] for k in ("lowgain","inrange","g11to20","FULL_s3000c","soups_multiprompt","clean_ep15")):
        online.add(r[1])
print(f"online selection: {len(online)} dirs")

conv_mp3=[]; conv_aac=[]; dirs=[]
for d,name,grp,step,lab,rows in raw:
    is_on = name in online
    odir=f"{CD}/{name}"; aacdir=f"{AAC}/{name}"; os.makedirs(odir,exist_ok=True)
    if is_on: os.makedirs(aacdir,exist_ok=True)
    gains=sorted({r['gain'] for r in rows}); reqs=sorted({r['requested'] for r in rows})
    cells={}
    for r in rows:
        g,q,m=r['gain'],r['requested'],r['measured']
        wav=f"{d}/onset_g{g:g}_d{q:g}.wav"
        mp3=f"{odir}/onset_g{g:g}_d{q:g}.mp3"; m4a=f"{aacdir}/onset_g{g:g}_d{q:g}.m4a"
        frel=None
        if os.path.exists(wav):
            if not os.path.exists(mp3): conv_mp3.append((wav,mp3))
            if is_on and not os.path.exists(m4a): conv_aac.append((wav,m4a))
            frel = f"clips_online_aac/{name}/onset_g{g:g}_d{q:g}.m4a" if is_on else f"clips_onset_eval/{name}/onset_g{g:g}_d{q:g}.mp3"
        cells[f"{g:g}|{q:g}"]={"m":round(m,2),"f":frel}
    corr={}
    for g in gains:
        gr=[r for r in rows if r['gain']==g]; xs=[r['requested'] for r in gr]; ys=[r['measured'] for r in gr]
        corr[f"{g:g}"]=round(float(np.corrcoef(xs,ys)[0,1]),2) if len(set(xs))>1 else None
    # run_meta backfill (legacy dirs) — provenance the GUI + inference UIs read
    p=PURP.get(grp, PURP.get("targeted",{}))
    run_meta={"dir":name,"group":grp,"step":step,"label":lab,"online":is_on,
              "run":p.get("run",grp),"optimizer":p.get("optimizer"),"lr":p.get("lr"),
              "scalar_field":p.get("scalar_field"),"epochs":p.get("epochs"),"purpose":p.get("purpose","")}
    if not os.path.exists(f"{d}/run_meta.json"):
        json.dump(run_meta, open(f"{d}/run_meta.json","w"), indent=2)
    dirs.append({"name":name,"group":grp,"step":step,"label":lab,"online":is_on,
                 "gains":[f"{g:g}" for g in gains],"reqs":[f"{q:g}" for q in reqs],
                 "cells":cells,"corr":corr,"meta":run_meta})

print(f"{len(dirs)} dirs | mp3 to convert {len(conv_mp3)} | AAC (online) {len(conv_aac)}")
def cv_mp3(p): subprocess.run(["ffmpeg","-y","-i",p[0],"-b:a","128k",p[1]],capture_output=True)
def cv_aac(p): subprocess.run(["ffmpeg","-y","-i",p[0],"-c:a","aac","-b:a","96k",p[1]],capture_output=True)
with ThreadPoolExecutor(max_workers=8) as ex: list(ex.map(cv_mp3, conv_mp3))   # local full cache (gitignored)
with ThreadPoolExecutor(max_workers=8) as ex: list(ex.map(cv_aac, conv_aac))   # online selection
print("encoding done (8 cores)")

dirs.sort(key=lambda d:(d['group'],d['step'],d['name']))
flat=[]
for di,d in enumerate(dirs):
    if not d.get('online'): continue
    for k,c in d['cells'].items():
        if c.get('f'):
            g,q=k.split('|'); flat.append({"lab":d['label'],"g":g,"q":q,"m":c['m'],"f":c['f'],"di":di})
flat.sort(key=lambda x:-x['m'])
DATA=json.dumps({"dirs":dirs,"flat":flat})
T=r"""<!doctype html><html><head><meta charset=utf-8><title>onset_eval — control-response sweeps</title><style>
body{font:12px system-ui;margin:0;background:#0e0e10;color:#e0e0e0}
#hdr{position:sticky;top:0;z-index:9;background:#16181c}
#bar{padding:8px 12px;border-bottom:1px solid #2a2a30}
#info{background:#0f1a14;border-top:1px solid #243;border-bottom:1px solid #243;border-left:3px solid #5d9;padding:8px 12px;font-size:12px;color:#cde}#info b{color:#9ec}#info .p{color:#9aa;margin-top:3px}
#info b{color:#9ec} #info .p{color:#9aa;margin-top:3px}
#wrap{padding:12px;max-width:1320px}h2{font-size:14px;color:#9cf;margin:18px 0 2px;border-top:1px solid #26262c;padding-top:10px}
.glabel{color:#8aa;font-size:11px;margin:6px 0 1px}.on{color:#5d9}.off{color:#666}
table{border-collapse:collapse;font-size:11px;margin:2px 0}td,th{border:1px solid #26262c;padding:3px 7px;text-align:center}
th{background:#1c1c22;color:#aaa}td:first-child,th:first-child{text-align:left;color:#9ab}.c{cursor:pointer;font-variant-numeric:tabular-nums}
.c:hover{outline:1px solid #7cf}.play{outline:2px solid #5d5 !important}.corr{color:#7cf}.no{color:#555;cursor:default}
input{background:#1c1c22;color:#ddd;border:1px solid #2a2a30;padding:3px 7px;margin-left:10px}a{color:#7cf}.muted{color:#666}
</style></head><body>
<div id=hdr><div id=bar>&#9654; <b id=np>click a cell to play</b> <span id=pos class=muted></span> &nbsp;·&nbsp; <span class=muted>switching cells keeps the playhead; re-click stops · <span class=on>green = in online selection</span></span>
<input id=flt placeholder="filter: lr2e5, lowgain, FULL…" oninput="filt()"> <button id=tgl onclick="toggleView()" style="background:#1c2c1c;color:#9ec;border:1px solid #2a3a2a;padding:3px 8px;cursor:pointer;margin-left:6px">↕ sort all clips by output density</button></div>
<div id=info>tap any cell or run header for its provenance (run · optimizer · lr · scalar · epochs · purpose)</div></div>
<div id=wrap></div><div id=sorted style="display:none;padding:12px"></div>
<script>const D=__DATA__;let sortedView=false;
const au=new Audio(); let cur=null;
au.addEventListener('timeupdate',()=>{document.getElementById('pos').textContent=cur?('· '+au.currentTime.toFixed(1)+'s'):'';});
au.addEventListener('ended',()=>{cur=null;mark();});
function mark(){document.querySelectorAll('.c.play').forEach(e=>e.classList.remove('play'));if(cur){const e=document.getElementById(cur);if(e)e.classList.add('play');}}
function showInfo(di){const m=D.dirs[di].meta;const ib=document.getElementById('info');
 ib.style.display='block';ib.innerHTML=`<b>${m.run||m.group}</b> &nbsp; ${m.optimizer||''} ${m.lr?('· lr '+m.lr):''} ${m.scalar_field?('· '+m.scalar_field):''} ${m.epochs?('· '+m.epochs+'ep'):''} ${m.step?('· step '+m.step):''} ${m.online?'<span class=on>· ONLINE</span>':''}<div class=p>${m.purpose||''}</div>`;}
function cell(id,f,lbl,di){
  if(!f){return;}
  if(cur===id){au.pause();cur=null;mark();document.getElementById('np').textContent='stopped';return;}
  const pos=(cur!==null&&!au.paused)?au.currentTime:0;
  cur=id;mark();document.getElementById('np').textContent='▶ '+lbl;showInfo(di);
  au.src=f;const go=()=>{try{au.currentTime=Math.min(pos,(au.duration||1e9)-0.05);}catch(e){}au.play();};
  if(au.readyState>=1)go(); else au.addEventListener('loadedmetadata',go,{once:true});
}
function col(m){const t=Math.max(0,Math.min(1,m/14));return`hsl(${Math.round(t*130)},45%,22%)`;}
let h='',lastg=null;
D.dirs.forEach((d,di)=>{
 if(d.group!==lastg){h+=`<h2>${d.group}</h2>`;lastg=d.group;}
 h+=`<div class=sec data-k="${(d.name+' '+d.label).toLowerCase()}"><div class=glabel onclick="showInfo(${di})" style="cursor:pointer">${d.label} <span class="${d.online?'on':'off'}">${d.online?'●online':'○local'}</span> &nbsp; corr/gain: `+d.gains.map(g=>`g${g}:<span class=corr>${d.corr[g]==null?'·':d.corr[g]}</span>`).join('  ')+` &nbsp;<span class=muted>(click for run info)</span></div>`;
 h+='<table><tr><th>g＼d</th>'+d.reqs.map(q=>`<th>${q}</th>`).join('')+'</tr>';
 for(const g of d.gains){h+=`<tr><td>g${g}</td>`+d.reqs.map(q=>{const c=d.cells[g+'|'+q];if(!c)return'<td class=muted>·</td>';if(!c.f)return`<td class=no style="background:${col(c.m)}">${c.m}</td>`;const id=(d.name+'_'+g+'_'+q).replace(/[^A-Za-z0-9_]/g,'');return`<td class=c id="${id}" style="background:${col(c.m)}" onclick="cell('${id}','${c.f}','${d.label} · g${g} d${q} → ${c.m}',${di})">${c.m}</td>`;}).join('')+'</tr>';}
 h+='</table></div>';
});
document.getElementById('wrap').innerHTML=h;
function toggleView(){sortedView=!sortedView;document.getElementById('wrap').style.display=sortedView?'none':'';const s=document.getElementById('sorted');s.style.display=sortedView?'block':'none';document.getElementById('tgl').textContent=sortedView?'↕ show grids':'↕ sort all clips by output density';if(sortedView&&!s.dataset.built){let h='<div class=glabel>all '+D.flat.length+' online clips, highest output density first &mdash; click ▶ to play (same-playhead switching works here too)</div><table><tr><th>#</th><th>out</th><th>run</th><th>gain</th><th>req</th><th>▶</th></tr>';D.flat.forEach((c,i)=>{const id="s"+i;h+=`<tr><td class=muted>${i+1}</td><td style="background:${col(c.m)};font-variant-numeric:tabular-nums">${c.m}</td><td>${c.lab}</td><td>g${c.g}</td><td>${c.q}</td><td class=c id="${id}" onclick="cell('${id}','${c.f}','${c.lab} g${c.g} d${c.q} → ${c.m}',${c.di})">▶</td></tr>`;});s.innerHTML=h+'</table>';s.dataset.built='1';}}
function filt(){const v=document.getElementById('flt').value.toLowerCase();document.querySelectorAll('.sec').forEach(s=>{s.style.display=s.dataset.k.includes(v)?'':'none';});}
</script></body></html>"""
open(f"{REPO}/onset_eval.html","w").write(T.replace("__DATA__",DATA))
gc={}; oc=0
for d in dirs: gc[d['group']]=gc.get(d['group'],0)+1; oc+=1 if d['online'] else 0
print(f"onset_eval.html built; groups {gc}; online {oc}; run_meta backfilled")
