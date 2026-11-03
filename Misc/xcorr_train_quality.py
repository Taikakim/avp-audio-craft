# Last edited: THE-FINN 2026-11-03 — root-variable paths updated for the __theme sorting
import collections, json, glob, re, os, numpy as np
from wandb.sdk.internal.datastore import DataStore
from wandb.proto import wandb_internal_pb2 as pb

def read_wandb(path, keys=None):
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
            if keys is not None and k not in keys: continue
            try: rows[step][k]=float(it.value_json)
            except Exception: pass
    return rows

def pear(x,y): return float(np.corrcoef(x,y)[0,1])
def spear(x,y):
    rx=np.argsort(np.argsort(x)); ry=np.argsort(np.argsort(y))
    return float(np.corrcoef(rx,ry)[0,1])

def control_authority(evdir):
    rows=json.load(open(f"{evdir}/onset_eval.json")); best=-2; slope_best=0
    for g in sorted({r['gain'] for r in rows}):
        gr=[r for r in rows if r['gain']==g]; xs=[r['requested'] for r in gr]; ys=[r['measured'] for r in gr]
        if len(set(xs))>1:
            c=np.corrcoef(xs,ys)[0,1]
            if c>best: best=c; slope_best=np.polyfit(xs,ys,1)[0]
    return best, slope_best

R="/run/media/kim/Mantu/sa3_control_runs"

# ============ lr2e5 : scalar telemetry x control authority (n=32) ============
print("="*70); print("lr2e5 (onset_FUSION_lr2e5_40epoch): scalar telemetry x control authority")
wb=glob.glob(f"{R}/__onsets/onset_FUSION_lr2e5_40epoch/wandb/run-*/run-*.wandb")[0]
th=read_wandb(wb)
qual={}
for ev in glob.glob(f"{R}/onset_eval_lr2e5_*"):
    m=re.search(r'lr2e5_(\d+)$', ev)
    if m and os.path.exists(f"{ev}/onset_eval.json"):
        try: qual[int(m.group(1))]=control_authority(ev)
        except Exception: pass
steps=sorted(set(th)&set(qual)); print(f"aligned steps: {len(steps)}  (range {steps[0]}-{steps[-1]})")
auth=[qual[s][0] for s in steps]; slope=[qual[s][1] for s in steps]
print(f"\n  control authority over training: {auth[0]:.2f} -> {auth[-1]:.2f} (slope-best {slope[0]:.1f}->{slope[-1]:.1f})")
for metric in ['loss','gnorm','it_s','epoch']:
    xs=[th[s].get(metric) for s in steps]
    if any(v is None for v in xs): continue
    print(f"  authority ~ {metric:6s}: Spearman {spear(xs,auth):+.2f}  Pearson {pear(xs,auth):+.2f}", end="")
    # lag-1 (does the metric lead authority?)
    if len(steps)>6:
        print(f"   | lag-1 Spearman {spear(xs[:-1],auth[1:]):+.2f}", end="")
    print()
print(f"  slope ~ gnorm: Spearman {spear([th[s]['gnorm'] for s in steps],slope):+.2f}")

# ============ opb : FULL telemetry x quality (n=4, EXPLORATORY) ============
print("\n"+"="*70); print("opb (onset_Fusion_opb_lr1.5e-4_30ep): full telemetry x quality  [n=4 EXPLORATORY]")
opb_wb=glob.glob("/home/kim/Projects/SAO/stable-audio-tools/avp_sa3/wandb/run-*-fqoxsw4o/run-*.wandb")
if not opb_wb: opb_wb=glob.glob("/home/kim/Projects/SAO/stable-audio-tools/avp_sa3/wandb/run-*/run-*.wandb")
oth=read_wandb(opb_wb[0])
oq={}
for ep,step in [(5,27000),(10,54000),(14,75600),(15,81000)]:
    ev=f"{R}/__onsets/onset_Fusion_opb_lr1.5e-4_30ep/onset_eval_opb_ep{ep}"
    if os.path.exists(f"{ev}/onset_eval.json"): oq[step]=control_authority(ev)[0]
osteps=sorted(oq)
# find the telemetry step nearest each eval step (layer_every=200 dense)
def near(s):
    cand=[k for k in oth if abs(k-s)<=200 and oth[k]]
    return min(cand, key=lambda k:abs(k-s)) if cand else None
rowsteps=[(s,near(s)) for s in osteps]; rowsteps=[(s,n) for s,n in rowsteps if n]
print(f"aligned: {[(s, oq[s]) for s,_ in rowsteps]}")
auth=[oq[s] for s,_ in rowsteps]
# layer subset: first/last/FiLM/every-2nd to_out dist_init + traj + fusion + global
keys=([f"dist_init/{b}.to_out.weight" for b in range(0,24,2)]+["dist_init/23.to_out.weight",
      "dist_init/24.film.0.weight","dist_init/24.tokens","g_over_w/0.to_out.weight","g_over_w/23.to_out.weight",
      "traj/velocity","traj/path_efficiency","traj/net_disp","fusion/gnorm_ema","fusion/gamma_step",
      "global/dist_init","global/gnorm","loss","gnorm"])
print(f"\n  authority (+0.{int((auth[-1]-auth[0])*100):d} over ep5->15): top |Spearman| predictors (n={len(auth)}):")
res=[]
for k in keys:
    xs=[oth[n].get(k) for _,n in rowsteps]
    if any(v is None for v in xs) or len(set(xs))<2: continue
    res.append((k, spear(xs,auth), pear(xs,auth)))
for k,sp,pe in sorted(res,key=lambda t:-abs(t[1]))[:12]:
    print(f"    authority ~ {k:32s}: Spearman {sp:+.2f}  Pearson {pe:+.2f}")
print(f"\n  (n=4 -> Spearman is rank-of-4; treat as DIRECTION/hypothesis, not significance)")
