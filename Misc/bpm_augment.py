import os, json, glob, warnings; warnings.filterwarnings("ignore")
os.environ["TF_CPP_MIN_LOG_LEVEL"]="3"
import essentia; essentia.log.warningActive=False; essentia.log.infoActive=False
import essentia.standard as es
rex=es.RhythmExtractor2013(method="multifeature")
dirs=sorted(glob.glob("/run/media/kim/Mantu/sa3_control_runs/*/eval_mp/*/pq_scores.json"))
n=0
for d in dirs:
    rows=json.load(open(d))
    if rows and all('bpm' in r for r in rows): continue
    base=os.path.dirname(d); ch=False
    for r in rows:
        w=f"{base}/{r['file']}"
        if 'bpm' not in r and os.path.exists(w):
            try:
                a=es.MonoLoader(filename=w,sampleRate=44100)()
                bpm,_,conf,_,_=rex(a); r['bpm']=round(float(bpm),1); r['bpm_conf']=round(float(conf),2); ch=True; n+=1
            except Exception: r['bpm']=None
    if ch: json.dump(rows, open(d,'w'))
    print(f"done {base.split('/')[-3]}/{os.path.basename(base)} ({n} total)",flush=True)
print("BPM_AUGMENT_DONE",flush=True)
