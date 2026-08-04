"""On-manifold crossfade (Kim): inpaint 20s/40s bridge + audio-crossfade then
audio2audio-refine the seam at init_noise 0.2/0.3/0.4. Memory-defensive (shares
VRAM with W's pipeline): crop latents before decode, empty_cache, per-render try."""
import os
os.environ["FLASH_ATTENTION_TRITON_AMD_ENABLE"]="FALSE"; os.environ["PYTORCH_TUNABLEOP_ENABLED"]="0"; os.environ["MIOPEN_FIND_MODE"]="2"
import sys, traceback
sys.path[:0]=["/home/kim/Projects/SAO/stable-audio-3","/home/kim/Projects/SAO/control"]
import numpy as np, torch
from stable_audio_3 import StableAudioModel
from sa3_control.audio_io import save_audio
OUT="/home/kim/Projects/SAO/renders_bridge"; os.makedirs(OUT, exist_ok=True)
CKPT="/run/media/kim/Mantu1/sa3_lora_runs/dora128_everything_8ep_lr1x/epoch=7-step=12216.ckpt"
LAT_A="/home/kim/Projects/latents_sa3/000100.npy"; LAT_B="/home/kim/Projects/latents_sa3/001200.npy"
PROMPT="goa trance"
sam=StableAudioModel.from_pretrained("medium-base", device="cuda"); sam.load_lora([CKPT])
sr=sam.model.sample_rate; ds=sam.model.pretransform.downsampling_ratio
lf12=int(12*sr/ds)                                  # latent frames for ~12s
def decode_seg(npy, secs=10):
    z=torch.from_numpy(np.load(npy))[:, :lf12].unsqueeze(0).to("cuda", next(sam.model.pretransform.parameters()).dtype)
    with torch.inference_mode(): a=sam.model.pretransform.decode(z)[0].float().cpu()
    del z; torch.cuda.empty_cache()
    return a[:, :int(secs*sr)]
print("[bridge] decoding source segments...", flush=True)
A=decode_seg(LAT_A); B=decode_seg(LAT_B)
save_audio(f"{OUT}/srcA.wav", A, sr); save_audio(f"{OUT}/srcB.wav", B, sr)
def gen(tag, **kw):
    try:
        with torch.inference_mode():
            o=sam.generate(prompt=PROMPT, cfg_scale=6.0, steps=24, sampler_type="euler", seed=1234, **kw)[0].float().cpu()
        save_audio(f"{OUT}/{tag}.wav", o, sr); print(f"[ok] {tag}", flush=True)
    except Exception:
        print(f"[FAIL] {tag}:", flush=True); traceback.print_exc()
    torch.cuda.empty_cache()
# Exp2 first (shorter ~16s), then Exp1 20s, then 40s (biggest last)
xf=int(4*sr); w=np.linspace(0,1,xf,dtype=np.float32); fd=torch.from_numpy(np.sqrt(w)); ifd=torch.from_numpy(np.sqrt(1-w))
seam=A[:, -xf:]*ifd + B[:, :xf]*fd
xfbuf=torch.cat([A[:, :-xf], seam, B[:, xf:]], dim=1)
save_audio(f"{OUT}/exp2_raw_audiocrossfade.wav", xfbuf, sr)
for nl in (0.2,0.3,0.4):
    gen(f"exp2_refine_nl{int(nl*100):02d}", duration=xfbuf.shape[1]/sr, init_audio=(sr, xfbuf.cuda()), init_noise_level=nl)
for gap in (20,40):
    g=int(gap*sr); buf=torch.cat([A, torch.zeros(A.shape[0], g), B], dim=1)
    gen(f"exp1_inpaint_bridge_{gap}s", duration=(2*A.shape[1]+g)/sr, inpaint_audio=(sr, buf.cuda()),
        inpaint_mask_start_seconds=10.0, inpaint_mask_end_seconds=10.0+gap)
print("[done]", flush=True)
