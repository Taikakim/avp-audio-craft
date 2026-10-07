"""mixtape_replaycheck_v7.py — gate 1 for DJ mix v7: does every incoming clip CONTINUE from the exact source position
after its entry window (the v6 replay put it ~10 s back)? Direct, no tracking ambiguity: for each clip, take 3 s of the
mix just after its entry window, find the best-matching position in the clip's own low band, compare with where the
placement says it must be. v6 would show errors near -10 s; v7 shows milliseconds. USAGE (eval dir, SAO venv):
  python mixtape_replaycheck_v7.py [--dir <mixtape_v7_phase0>] [--bounds <work48b/bounds.json>]
Exit 1 if any clip is more than 0.1 s off.
"""
import json,subprocess,numpy as np,sys,argparse
from scipy.signal import butter,sosfiltfilt,resample_poly,fftconvolve
ap=argparse.ArgumentParser();ap.add_argument('--dir',default='/run/media/kim/Mantu/sa3_lora_runs/mixtape_v7_phase0');ap.add_argument('--bounds',default='/run/media/kim/Mantu/sa3_lora_runs/mixtape_v6_rerender/work48b/bounds.json');A=ap.parse_args()
D=A.dir.rstrip('/')+'/'
def low(path):
    y=np.frombuffer(subprocess.run(["ffmpeg","-v","error","-i",path,"-f","f32le","-ac","1","-ar","44100","-"],capture_output=True).stdout,dtype=np.float32)
    return resample_poly(sosfiltfilt(butter(4,150,"low",fs=44100,output="sos"),y),1,44),44100/44
mix,fs=low(D+'mixtape_full_plain.wav')
tl=json.load(open(D+'timeline.json'));m=json.load(open(D+'run_meta.json'));order=json.load(open(D+'order_used.json'))
bounds=json.load(open(A.bounds));dbc=json.load(open(D+'downbeats_native.json'))
T=[0.0]
for t,tr in zip(tl['trans'],m['transitions']): T.append(t[0]+tr['shift_samples']/44100)
res=[]
for i in range(1,len(order)):
    c=order[i];db=np.array(dbc[c['id']]);key=c['id'];bk=bounds.get(key) or bounds[next(k for k in bounds if key.startswith(k) or k.startswith(key[:60]))]
    in_s=db[np.argmin(abs(db-bk['start']))]
    Lprev=tl['trans'][i-1][1]-tl['trans'][i-1][0]
    src,_=low(c['path'])
    t0=T[i]+Lprev+0.3;dur=3.0               # just after the entry window, before any stretch ramp
    seg=mix[int(t0*fs):int((t0+dur)*fs)]
    exp=in_s+(t0-T[i])                      # where in the source this MUST be if the clip continues
    cc=fftconvolve(src,seg[::-1],mode='valid');e=np.sqrt(fftconvolve(src**2,np.ones(len(seg)),mode='valid')+1e-9)*np.linalg.norm(seg)
    ncc=cc/e;k=int(np.argmax(ncc));best=k/fs
    res.append((i,round(best-exp,3),round(float(ncc[k]),2)))
dev=np.array([r[1] for r in res]);print('clips checked',len(res),'| source-position error after entry window (s): med %.3f max|.| %.3f; within 0.1 s: %d/%d'%(np.median(dev),abs(dev).max(),int((abs(dev)<0.1).sum()),len(res)))
print('far off (>0.1 s):',[r for r in res if abs(r[1])>=0.1])

sys.exit(1 if any(abs(r[1])>=0.1 for r in res) else 0)
