"""Beat-aligned bridge v3 (Kim): mid-sample two BEAT-rich same-BPM latents,
downbeat-phase-aligned, 8-bar & 16-bar crossfades in a ~1min arrangement,
audio2audio-refined seam pasted back. All arrangement math in numpy."""
import os
os.environ["FLASH_ATTENTION_TRITON_AMD_ENABLE"]="FALSE"; os.environ["PYTORCH_TUNABLEOP_ENABLED"]="0"; os.environ["MIOPEN_FIND_MODE"]="2"
import sys, json, traceback
sys.path[:0]=["/home/kim/Projects/SAO/stable-audio-3","/home/kim/Projects/SAO/control"]
import numpy as np, torch
from scipy.signal import find_peaks
from stable_audio_3 import StableAudioModel
from sa3_control.audio_io import save_audio
OUT="/home/kim/Projects/SAO/renders_beatbridge2"; os.makedirs(OUT, exist_ok=True)
CKPT="/run/media/kim/Mantu1/sa3_lora_runs/dora128_everything_8ep_lr1x/epoch=7-step=12216.ckpt"
LD="/home/kim/Projects/latents_sa3"; A_ID,B_ID="002859","002500"; BPM=143.0
sam=StableAudioModel.from_pretrained("medium-base", device="cuda"); sam.load_lora([CKPT])
sr=sam.model.sample_rate; ds=int(sam.model.pretransform.downsampling_ratio)
def save(p, a): save_audio(p, torch.from_numpy(np.ascontiguousarray(a.astype("float32"))), sr)

def load_mid(cid, secs=45):
    z_all=np.load(f"{LD}/{cid}.npy"); N=z_all.shape[1]
    lf=min(int(secs*sr/ds), N); c0=max(0, N//2 - lf//2)
    z=torch.from_numpy(z_all[:, c0:c0+lf]).unsqueeze(0).to("cuda", next(sam.model.pretransform.parameters()).dtype)
    with torch.inference_mode(): a=sam.model.pretransform.decode(z)[0].float().cpu().numpy()
    del z; torch.cuda.empty_cache()
    dba=np.load(f"{LD}/{cid}.TIMESERIES.npz")["downbeat_activation_ts"].astype(float)
    thr=max(dba.mean()+dba.std(), 0.4*dba.max())
    pk,_=find_peaks(dba, height=thr, distance=max(1,int(0.35*sr/ds)))
    pk=pk[(pk>=c0)&(pk<c0+lf)]; db=((pk-c0)*ds).astype(int); db=db[db<a.shape[1]]
    return a, db   # a: numpy [C, T]

print("[bb2] mid-sampling...", flush=True)
A,Adb=load_mid(A_ID); B,Bdb=load_mid(B_ID)
save(f"{OUT}/srcA_{A_ID}_mid.wav", A); save(f"{OUT}/srcB_{B_ID}_mid.wav", B)
print(f"[bb2] A {A.shape[1]/sr:.1f}s {len(Adb)}db  B {B.shape[1]/sr:.1f}s {len(Bdb)}db", flush=True)
bar=60.0/BPM*4
def a2a(win, nl):
    with torch.inference_mode():
        r=sam.generate(prompt="goa trance", duration=win.shape[1]/sr, steps=24, cfg_scale=6.0, seed=1234,
                       sampler_type="euler", init_audio=(sr, torch.from_numpy(np.ascontiguousarray(win)).cuda()),
                       init_noise_level=nl)[0].float().cpu().numpy()
    return r[:, :win.shape[1]]
for nbars in (8,16):
    xf=int(round(nbars*bar*sr)); tag=f"{nbars}bar"
    xstart=int(Adb[np.argmin(np.abs(Adb-16*sr))])
    bcand=Bdb[Bdb<=B.shape[1]-xf-int(14*sr)]
    bstart=int(bcand[np.argmin(np.abs(bcand-12*sr))]) if len(bcand) else int(Bdb[0])
    if xstart+xf>A.shape[1]: xstart=max(0, A.shape[1]-xf)
    w=np.linspace(0,1,xf,dtype=np.float32); fin=np.sqrt(w); fout=np.sqrt(1-w)
    seam=A[:, xstart:xstart+xf]*fout + B[:, bstart:bstart+xf]*fin
    arr=np.concatenate([A[:, :xstart], seam, B[:, bstart+xf:]], axis=1)
    save(f"{OUT}/arr_{tag}_raw.wav", arr)
    print(f"[bb2] {tag} raw {arr.shape[1]/sr:.1f}s seam@{xstart/sr:.1f}s xf={xf/sr:.1f}s", flush=True)
    pad=int(3*sr); e=int(0.5*sr); w0=max(0,xstart-pad); w1=min(arr.shape[1], xstart+xf+pad)
    try:
        ref=a2a(arr[:, w0:w1], 0.3).copy()
        ew=np.linspace(0,1,e,dtype=np.float32)
        ref[:, :e]=ref[:, :e]*ew + arr[:, w0:w0+e]*(1-ew)
        ref[:, -e:]=ref[:, -e:]*(1-ew) + arr[:, w1-e:w1]*ew
        out=arr.copy(); out[:, w0:w1]=ref
        save(f"{OUT}/arr_{tag}_refined_nl30.wav", out); print(f"[ok] {tag} refined", flush=True)
    except Exception: print(f"[FAIL] {tag}"); traceback.print_exc()
    torch.cuda.empty_cache()
print("[done]", flush=True)
