#!/usr/bin/env python
# bench_encode.py — SAME-L encode-cost probe: T=512 vs T=4096, bs=1 vs bs=4, fp32 vs bf16.
# Answers "is live-encode-per-batch cheap enough to replace pre-encoding?" (Kim 2026-08-03).
# Run under the multitorch train venv on 1 GCD (see srun in the chat). Frozen encoder, no grad.
import os, time
os.environ["FLASH_ATTENTION_TRITON_AMD_ENABLE"] = "FALSE"
os.environ.setdefault("HF_HUB_OFFLINE", "1")
import torch

DEV = "cuda"
FPS_DS = 4096  # samples per latent frame

def load_encoder():
    # AutoencoderModel is a WRAPPER (no .to()/.eval()) — device/model_half go to from_pretrained.
    from stable_audio_3 import AutoencoderModel
    last = None
    for kw in ({"device": DEV, "model_half": False}, {"device": DEV}, {}):
        try:
            ae = AutoencoderModel.from_pretrained("same-l", **kw)
            print("[bench] loaded same-l with", kw)
            return ae
        except TypeError as e:
            last = e
        except Exception as e:
            print("[bench] same-l load failed:", repr(e)); last = e; break
    raise last

SR = 44100
def enc(ae, x):
    # AutoencoderModel.encode(audio[B,2,N], sr) -> latent[B,256,T]
    return ae.encode(x, SR)

def bench(ae, Tframes, bs=1, dtype=torch.float32, iters=4):
    n = Tframes * FPS_DS
    x = torch.randn(bs, 2, n, device=DEV, dtype=torch.float32)
    ts = []
    with torch.no_grad():
        for i in range(iters):
            torch.cuda.synchronize(); t0 = time.time()
            if dtype == torch.bfloat16:
                with torch.autocast("cuda", dtype=torch.bfloat16):
                    z = enc(ae, x)
            else:
                z = enc(ae, x)
            torch.cuda.synchronize(); ts.append(time.time() - t0)
    ts = sorted(ts)[1:]  # drop warmup (slowest)
    sh = tuple(z.shape) if hasattr(z, "shape") else type(z).__name__
    return sum(ts) / len(ts), sh

def main():
    ae = load_encoder()
    print(f"[bench] torch {torch.__version__} | {torch.cuda.get_device_name(0)}")
    for dt in (torch.float32, torch.bfloat16):
        tag = "bf16" if dt == torch.bfloat16 else "fp32"
        for T in (512, 4096):
            try:
                s, sh = bench(ae, T, 1, dt)
                print(f"[{tag}] T={T:<4} bs=1: {s*1000:7.1f} ms/encode  latent {sh}")
            except Exception as e:
                print(f"[{tag}] T={T} bs=1 FAILED: {repr(e)}")
        try:
            s, _ = bench(ae, 512, 4, dt)
            print(f"[{tag}] T=512  bs=4: {s*1000:7.1f} ms/batch ({s*1000/4:.1f} ms/clip)")
        except Exception as e:
            print(f"[{tag}] T=512 bs=4 FAILED: {repr(e)}")

if __name__ == "__main__":
    main()
