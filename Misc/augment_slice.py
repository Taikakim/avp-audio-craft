import os, json, glob, random, numpy as np, soundfile as sf
from bungee_python import bungee as bungee_lib
random.seed(7); CROP=16777216
fs=sorted(glob.glob("/run/media/kim/Kosmos/latents/latents_sa3/*.json")); random.shuffle(fs); fs=fs[:150]
OUT="/run/media/kim/Mantu/aug_validation"; os.makedirs(OUT,exist_ok=True); man=[]
for i,f in enumerate(fs):
    d=json.load(open(f)); sp=d.get('source_path'); s0=d.get('start_sample'); s1=d.get('end_sample'); ST=d.get('source_total_samples'); bpm=d.get('bpm_madmom')
    if not (sp and os.path.exists(sp) and bpm): continue
    typ=random.choice(['bpm','pitch','both'])
    bd=random.uniform(-8,16) if typ in ('bpm','both') else 0.0
    semi=random.uniform(-2,2) if typ in ('pitch','both') else 0.0
    speed=(bpm+bd)/bpm if bd else 1.0
    src_len=int(np.ceil(CROP*speed)); ns0=max(0,min(s0-(src_len-CROP)//2, ST-src_len)) if ST>src_len else 0
    try: audio,sr=sf.read(sp,start=ns0,stop=min(ns0+src_len,ST),dtype='float32')
    except Exception as e: print("read err",e); continue
    ch=audio.shape[1] if audio.ndim>1 else 1; ai=audio if audio.ndim>1 else audio.reshape(-1,1)
    st=bungee_lib.Bungee(sample_rate=sr,channels=ch)
    if speed!=1.0: st.set_speed(speed)
    if semi!=0: st.set_pitch(2.0**(semi/12.0))
    out=np.asarray(st.process(ai),dtype=np.float32)
    out=out[:CROP] if len(out)>=CROP else np.pad(out,((0,CROP-len(out)),(0,0)))
    name=os.path.basename(f)[:-5]; wp=f"{OUT}/{name}_aug.wav"; sf.write(wp,out,sr)
    man.append({"src":f,"wav":wp,"type":typ,"bpm_delta":round(bd,1),"semitones":round(semi,2),"orig_bpm":round(bpm,1),"new_bpm":round(bpm+bd,1),"onset_per_beat":d.get('onset_per_beat'),"prompt":d.get('prompt')})
    if i%25==0: print(f"{i+1}/150 ({len(man)} ok)",flush=True)
json.dump(man,open(f"{OUT}/aug_manifest.json","w")); print(f"AUGMENT_DONE {len(man)} clips",flush=True)
