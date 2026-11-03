import os
os.environ["HIP_VISIBLE_DEVICES"]=""; os.environ["CUDA_VISIBLE_DEVICES"]=""  # force CPU, no GPU contention
import glob, random, json, subprocess, tempfile, sys
sys.path.insert(0,"/home/kim/Projects/mir/src")
from timbral.audiobox_aesthetics import analyze_audiobox_aesthetics
tracks=sorted(glob.glob("/run/media/kim/Mantu/ai-music/Goa_Separated/*/full_mix.*"))
random.seed(42); random.shuffle(tracks); tracks=tracks[:40]
scores=[]
for i,t in enumerate(tracks):
    tmp=tempfile.mktemp(suffix=".wav")
    subprocess.run(["ffmpeg","-y","-loglevel","error","-ss","30","-t","20","-i",t,tmp])
    if os.path.exists(tmp) and os.path.getsize(tmp)>1000:
        try: scores.append(analyze_audiobox_aesthetics(tmp))
        except Exception as e: print("err",str(e)[:60],flush=True)
        os.remove(tmp)
    if i%10==0: print(f"{len(scores)} scored",flush=True)
if scores: print("KEYS:",list(scores[0].keys()),flush=True)
json.dump(scores,open("/tmp/goa_audiobox.json","w"))
print(f"GOA_BASELINE_DONE n={len(scores)}",flush=True)
