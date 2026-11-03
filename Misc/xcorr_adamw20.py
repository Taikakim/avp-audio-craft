import collections, json, glob, re, os, numpy as np
from wandb.sdk.internal.datastore import DataStore
from wandb.proto import wandb_internal_pb2 as pb

def read_wandb(path):
    ds=DataStore(); ds.open_for_scan(path); rows=collections.defaultdict(dict)
    while True:
        try: rec=ds.scan_data()
        except Exception: break
        if rec is None: break
        m=pb.Record(); m.ParseFromString(rec)
        if m.WhichOneof("record_type")!="history": continue
        h=m.history; step=h.step.num
        for it in h.item:
            k=it.key or ".".join(it.nested_key)
            if k.endswith("._type") or "._" in k: continue
            try: rows[step][k]=float(it.value_json)
            except Exception: pass
    return rows

def spear(x,y):
    rx=np.argsort(np.argsort(x)); ry=np.argsort(np.argsort(y)); return float(np.corrcoef(rx,ry)[0,1])
def pear(x,y): return float(np.corrcoef(x,y)[0,1])
def control_authority(evdir):
    rows=json.load(open(f"{evdir}/onset_eval.json")); best=-2
    for g in sorted({r['gain'] for r in rows}):
        gr=[r for r in rows if r['gain']==g]; xs=[r['requested'] for r in gr]; ys=[r['measured'] for r in gr]
        if len(set(xs))>1: best=max(best, np.corrcoef(xs,ys)[0,1])
    return best

R="/run/media/kim/Mantu/sa3_control_runs"; A=f"{R}/onset_AdamW_lr7.5e-5_randomcrop_20ep"
wbs=glob.glob("/home/kim/Projects/SAO/stable-audio-tools/avp_sa3/wandb/run-20260625_071023-8dahxh28/run-*.wandb")
print("wandb candidates:", [os.path.relpath(w,R) if w.startswith(R) else w for w in wbs[:4]])
assert wbs, "no wandb found for AdamW-20ep"
th=read_wandb(sorted(wbs)[-1])
allk=sorted({k for s in th for k in th[s]})
print(f"telemetry: {len(th)} steps, {len(allk)} keys; per-layer present: dist_init/*={sum(k.startswith('dist_init/') for k in allk)} traj/*={sum(k.startswith('traj/') for k in allk)} g_over_w/*={sum(k.startswith('g_over_w/') for k in allk)}")

# authority series (20 epochs)
oq={}
for ep in range(1,21):
    ev=f"{A}/onset_eval_adamw20_ep{ep}"
    if os.path.exists(f"{ev}/onset_eval.json"): oq[ep*5400]=control_authority(ev)
osteps=sorted(oq)
def near(s,tol=400):
    cand=[k for k in th if abs(k-s)<=tol and th[k]]
    return min(cand,key=lambda k:abs(k-s)) if cand else None
rows=[(s,near(s)) for s in osteps]; rows=[(s,n) for s,n in rows if n]
auth=[oq[s] for s,_ in rows]
print(f"\naligned {len(rows)}/20 epochs; authority {min(auth):+.2f}..{max(auth):+.2f}; ep9 collapse value = {oq.get(9*5400)}")

# layer subset: first/last/input-FiLM/every-2nd  (+ trajectory + global + scalar)
layers=list(range(0,24,2))+[23]
keys=[f"dist_init/{b}.to_out.weight" for b in layers]+[f"g_over_w/{b}.to_out.weight" for b in (0,11,23)]
keys+=["dist_init/24.film.0.weight","dist_init/24.tokens","traj/velocity","traj/path_efficiency",
       "traj/net_disp","global/dist_init","global/gnorm","gnorm","loss"]
keys=[k for k in keys if k in allk]
res=[]
for k in keys:
    xs=[th[n].get(k) for _,n in rows]
    if any(v is None for v in xs) or len(set(xs))<2: continue
    res.append((k, spear(xs,auth), pear(xs,auth)))
print(f"\n=== RICH MATRIX: authority ~ telemetry  (n={len(auth)}, real statistics) ===")
for k,sp,pe in sorted(res,key=lambda t:-abs(t[1])):
    flag=" <<<" if abs(sp)>=0.5 else ""
    print(f"  {k:34s}: Spearman {sp:+.2f}  Pearson {pe:+.2f}{flag}")
print(f"\n  (|Spearman|>=0.45 ~ p<0.05 at n=20; '<<<' = candidate predictor of control authority)")
