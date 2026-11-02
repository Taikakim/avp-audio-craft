import json,sys,glob,os,librosa
sys.path.insert(0,'/home/kim/Projects/SAO/eval')
from mood_score_layeract_crops import EffnetMoodCPU
A='/home/kim/evals_aac/mood_finegrained/'; S=1102008041
SP=os.environ.get('SP','/run/media/kim/Kosmos/captions/review_20261103'); M=EffnetMoodCPU()
import inspect

fs=[f'fine_{m}__base__s{S}.m4a' for m in ['base','adamw','goa','combo_fusion_goa']]+[f'fine_{m}__{t}_g{g}__s{S}.m4a' for m in ['base','adamw','goa','combo_fusion_goa'] for t in ['Melodic','Space','Dark'] for g in [1024,2048,4096,8192]]
out={}
for f in fs:
    if not os.path.exists(A+f): print('missing',f); continue
    y,_=librosa.load(A+f,sr=16000,mono=True)
    out[f]=[float(x) for x in M(y)]
    print(f,flush=True)
    json.dump(out,open(SP+'/naive_scores.json','w'))
