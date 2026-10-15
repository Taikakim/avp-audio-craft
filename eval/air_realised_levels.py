# Owner: GHOST-NOTE (created 2026-10-15) -- band RMS (dB) of raw renders in a dir (argv[1], default compare/), mir venv; writes realised.json there
import sys, json, glob, os
sys.path.insert(0,"/home/kim/Projects/mir")
import numpy as np, soundfile as sf
from src.spectral.multiband_rms import calculate_band_rms
CMP=sys.argv[1] if len(sys.argv)>1 else "/run/media/kim/Mantu/latch_sweep/air_head_2026-10-14/compare"
B={"bass":(20,120),"body":(120,600),"mid":(600,2500),"air":(2500,22000)}
out={}
for p in sorted(glob.glob(CMP+"/s*_*.wav")):
    if p.endswith("_matched.wav"): continue
    k=os.path.basename(p)[:-4]
    x,sr=sf.read(p,dtype="float32"); m=x.mean(1) if x.ndim>1 else x
    out[k]={n:calculate_band_rms(m,sr,lo,min(hi,sr/2-100)) for n,(lo,hi) in B.items()}
json.dump(out,open(CMP+"/realised.json","w"),indent=1)
for a in ["base","bass_body","old_adamw_g8448","old_adamw_g24000","A2_g8448","A2_g24000","A5_g8448","A5_g24000","A6_soap_g24000"]:
    v=[out[f"s{s}_{a}"] for s in (764,1337,3017,3050)]
    print(f"{a:18s} "+"  ".join(f"{n} {np.mean([x[n] for x in v]):6.1f}" for n in B))
