# Owner: THE-FINN (created 2026-11-03) -- torch-free LatCH-steered render: upstream's LiteRT DiT + an exported head gradient (ONNX Runtime) + numpy ping-pong.
# Mirrors stable_audio_3/inference/latch_guided.py::sample_flow_pingpong_multi_latch_guided (alpha schedule, gamma 0.3, n_iter 4). CPU only.
import sys, os, json, time, numpy as np
TF='/home/kim/sao_runs/tflite_cpu_test/optimized/tflite'; sys.path[:0]=[TF,TF+'/scripts']; os.chdir(TF)
import sa3_tflite as A
from models.defs import tflite_pipeline as P
from weights import ensure_local, dit_rel, dec_rel
from rung_decoder import RungDecoder
import onnxruntime as ort
OUT='/home/kim/sao_runs/head_export/renders'; TH=12
PROMPT='driving psychedelic trance, rolling bassline, acid lead, 145 BPM'; SEC=24.0; STEPS=8
T_lat=int(np.ceil(SEC*44100/4096)); assert T_lat==259
MEAN,STD=-21.92660903930664,14.534050941467285
so=ort.SessionOptions(); so.intra_op_num_threads=TH
G=ort.InferenceSession('/home/kim/sao_runs/head_export/bass_grad_T259.onnx',so,providers=['CPUExecutionProvider'])
tok=P.Tokenizer(); ids,mask=tok(PROMPT); t5=P.T5GemmaTFLite(ensure_local(A.T5_REL),TH); h=t5(ids,mask)
def backend(path): return A.make_dit_backend(path,T_lat,h,mask.astype(np.float32),SEC,TH,cfg=1.0,apg=1.0,null_hidden=None,null_mask=None,local_add_cond=None,batched=True)
dec=RungDecoder(ensure_local(dec_rel('same-l','w8a8')),threads=TH,trim=A.RUNG_TRIM['same-l'],max_rung=None)
sig=P.build_pingpong_schedule(STEPS,1.0); alpha=np.clip(1-np.asarray(sig[:-1],np.float32),0,None); sched=alpha/alpha.sum()
Q=[]
def grad(x,t,tg,keep=False):
    g,l=G.run(None,{'x':x.astype(np.float32),'t':np.array([t],np.float32),'target':tg})
    if keep: Q.append(dict(x=x.copy(),t=t,tg=tg.copy(),g=g.copy()))
    return g
def render(name,dit,seed,gain,value,keep=False):
    x0,sn=P.make_noise(T_lat,STEPS,seed); x=x0.copy(); rng=np.random.default_rng(seed+1000)
    tg=None if value is None else np.full((1,1,T_lat),(value-MEAN)/STD,np.float32)
    tg_ms=0.;n=0;t0=time.perf_counter()
    for i in range(STEPS):
        tc,tn=float(sig[i]),float(sig[i+1]); s=float(sched[i])
        if tg is not None and s>0:
            a=time.perf_counter(); x=x-gain*s*grad(x,tc,tg,keep and i in(3,6)); tg_ms+=time.perf_counter()-a;n+=1
        v=dit(x,tc,None,None); z=x-tc*v
        if tg is not None and s>0:
            a=time.perf_counter()
            for _ in range(4):
                z=z-gain*s*grad(z+0.3*rng.standard_normal(z.shape).astype(np.float32),0.0,tg,keep and i==6 and _==0); n+=1
            tg_ms+=time.perf_counter()-a
        x=(1-tn)*z+tn*sn[i] if (i<STEPS-1 and tn>0) else z
    wall=time.perf_counter()-t0
    a=dec.decode(x)[:,:,:T_lat*4096][0]; a=a[:,:int(SEC*44100)]
    P.save_wav(f'{OUT}/{name}.wav',a); np.save(f'{OUT}/{name}.z0.npy',x)
    f=np.fft.rfftfreq(a.shape[1],1/44100); S=np.abs(np.fft.rfft(a,axis=1))**2; band=lambda lo,hi:S[:,(f>=lo)&(f<hi)].sum()
    tot=band(20,20000); db=lambda p:10*np.log10(p+1e-20)
    r=dict(name=name,seed=seed,gain=gain,target_db=value,z_std=float(x.std()),finite=bool(np.isfinite(a).all()),peak=float(abs(a).max()),rms_db=float(20*np.log10(np.sqrt((a**2).mean())+1e-9)),bass_share_db=float(db(band(20,150))-db(tot)),sample_s=round(wall,2),guide_s=round(tg_ms,2),grad_calls=n)
    print(json.dumps(r),flush=True); return r
R=[]; rung=ensure_local(dit_rel('medium','w8a8')); D=backend(rung)
for seed in (1234,77):
    R.append(render(f'off_s{seed}',D,seed,0,None))
    for gain in (512,2048):
        for v,nm in ((-36.0,'lo'),(-8.0,'hi')):
            R.append(render(f'{nm}_g{gain}_s{seed}',D,seed,gain,v,keep=(seed==1234 and gain==512)))
print('LORA',flush=True)
from lora_patch import get_patched_dit; from lora_core import parse_lora_spec
pth=get_patched_dit(ensure_local(dit_rel('medium','fp32')),[parse_lora_spec(['/home/kim/sao_runs/tflite_cpu_test/adapters/avp_armG_ep74_noconv.safetensors','strength=1.0'])],family='medium',precision='fp32',log=print)
D2=backend(pth); seed=1234
R.append(render(f'dora_off_s{seed}',D2,seed,0,None))
for v,nm in ((-36.0,'lo'),(-8.0,'hi')): R.append(render(f'dora_{nm}_g512_s{seed}',D2,seed,512,v))
json.dump(R,open(f'{OUT}/results.json','w'),indent=1)
np.savez(f'{OUT}/grad_queries.npz',**{f'{k}{i}':q[k] for i,q in enumerate(Q) for k in q})
print('ALLDONE',len(R),flush=True)
