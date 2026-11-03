import librosa, json, numpy as np, glob, os, warnings; warnings.filterwarnings("ignore")
def beat_strength(y,sr,hop=512):
    oe=librosa.onset.onset_strength(y=y,sr=sr,hop_length=hop); oe=(oe-oe.mean())/(oe.std()+1e-9)
    ac=librosa.autocorrelate(oe); fps=sr/hop; lo,hi=int(0.3*fps),int(1.0*fps)
    return float(ac[lo:hi].max()/(ac[0]+1e-9)) if hi<len(ac) and ac[0]>0 else 0.0
R="/run/media/kim/Mantu/sa3_control_runs"; out={}
for d in sorted(glob.glob(f"{R}/*/eval_mp/*/pq_scores.json")):
    rundir=d.split('/')[-4]; name=d.split('/')[-2]
    if name.endswith('_hi'): continue
    base=os.path.dirname(d); bs=[]
    for r in json.load(open(d)):
        if str(r['seed'])!="777": continue
        g=f"{r['gain']:g}"; dd=f"{r['density']:g}"
        if g not in ("0.5","1","2","3") or dd not in ("3","7","9","12"): continue
        try: y,sr=librosa.load(f"{base}/{r['file']}",sr=22050,mono=True); bs.append(beat_strength(y,sr))
        except: pass
    if bs: out[f"{rundir}__{name}"]=round(float(np.mean(bs)),3)
json.dump(out,open("/tmp/beat_presence.json","w")); print(f"BEAT_PRESENCE_DONE n={len(out)}",flush=True)
