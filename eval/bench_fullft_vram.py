#!/usr/bin/env python
# Owner: GHOST-NOTE (created 2026-10-13)
"""bench_fullft_vram.py -- peak VRAM of ONE full-finetune step of the SA3 medium-base DiT on this 16 GB card, per optimizer / dtype arm.

WHY (GHOST-NOTE 2026-10-13, owner's question: would FP8/BF8 allow full FT with optimisers heavier than Lion?). Answer by measuring the
real thing: every DiT parameter trainable, T frames, B=1, bf16 autocast, the model's own activation checkpointing, then 2 optimizer steps.
Arms (--arm): weights dtype (bf16 | fp32 master) x optimizer (lion | adamw) x state dtype (bf16 | fp32). Lion is the plain sign(b1*m+(1-b1)*g)
rule with decoupled decay, written inline (no lion_pytorch in the venv). Prints one JSON line: peak allocated GiB after forward/backward and
after the optimizer step, or OOM. Run one arm per process (an OOM can leave the allocator unusable).
RUN: ROCR_VISIBLE_DEVICES=0 FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE .venv/bin/python eval/bench_fullft_vram.py --arm bf16-lion-bf16 [--t 512]  (scratch cwd, GPU lock first)
"""
import argparse, json, os, platform, sys, time
platform.architecture = lambda *a, **k: ("64bit", "ELF")
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
import torch
import torch.nn.functional as F

ap = argparse.ArgumentParser()
ap.add_argument("--arm", required=True, help="<weights bf16|fp32>-<lion|adamw>-<state bf16|fp32>")
ap.add_argument("--t", type=int, default=512)
a = ap.parse_args()
wd, opt, sd = a.arm.split("-")
WD = torch.bfloat16 if wd == "bf16" else torch.float32
SD = torch.bfloat16 if sd == "bf16" else torch.float32
dev, T, C = "cuda", a.t, 256
GiB = 2 ** 30

from stable_audio_3 import StableAudioModel
m = StableAudioModel.from_pretrained("medium-base")
diff = m.model
cond = diff.conditioner([{"prompt": "mid 90s goa trance, 145 bpm", "seconds_total": T / 10.7666}], dev)
for _id, _c in (("inpaint_mask", 1), ("inpaint_masked_input", C)):
    if _id in getattr(diff, "local_add_cond_ids", []) and _id not in cond:
        cond[_id] = [torch.zeros(1, _c, T, device=dev)]
inner = diff.model
inner.to(device=dev, dtype=WD).train()
torch.cuda.empty_cache()
params = [p for p in inner.parameters()]
for p in params:
    p.requires_grad_(True)
n = sum(p.numel() for p in params)
state = {}


def opt_step(lr=1e-6, b1=0.9, b2=0.99, wdec=0.01):
    with torch.no_grad():
        for p in params:
            g = p.grad
            if g is None:
                continue
            st = state.setdefault(p, {})
            if opt == "adamw":
                if not st:
                    st["m"] = torch.zeros_like(p, dtype=SD); st["v"] = torch.zeros_like(p, dtype=SD); st["t"] = 0
                st["t"] += 1
                st["m"].mul_(b1).add_(g.to(SD), alpha=1 - b1)
                st["v"].mul_(b2).addcmul_(g.to(SD), g.to(SD), value=1 - b2)
                den = (st["v"].float() / (1 - b2 ** st["t"])).sqrt_().add_(1e-8)
                p.mul_(1 - lr * wdec).addcdiv_((st["m"].float() / (1 - b1 ** st["t"])).to(p.dtype), den.to(p.dtype), value=-lr)
            else:
                if not st:
                    st["m"] = torch.zeros_like(p, dtype=SD)
                u = (st["m"].float() * b1 + g.float() * (1 - b1)).sign_()
                p.mul_(1 - lr * wdec).add_(u.to(p.dtype), alpha=-lr)
                st["m"].mul_(0.99).add_(g.to(SD), alpha=0.01)
            p.grad = None


g = torch.Generator(device="cpu").manual_seed(0)
z0, noise = torch.randn(1, C, T, generator=g).to(dev), torch.randn(1, C, T, generator=g).to(dev)
t = torch.tensor([0.5], device=dev)
x = z0 * (1 - t)[:, None, None] + noise * t[:, None, None]
res = {"arm": a.arm, "T": T, "params_M": round(n / 1e6), "weights_gib": round(torch.cuda.memory_allocated() / GiB, 2)}
try:
    for i in range(2):
        torch.cuda.reset_peak_memory_stats()
        with torch.autocast("cuda", dtype=torch.bfloat16):
            v = diff(x.to(WD) if WD != torch.float32 else x, t, cond=cond, cfg_dropout_prob=0.0)
        F.mse_loss(v.float(), noise - z0).backward()
        res[f"peak_fwdbwd_gib_step{i}"] = round(torch.cuda.max_memory_allocated() / GiB, 2)
        torch.cuda.reset_peak_memory_stats()
        opt_step()
        torch.cuda.synchronize()
        res[f"peak_optstep_gib_step{i}"] = round(torch.cuda.max_memory_allocated() / GiB, 2)
        res[f"resident_after_step{i}_gib"] = round(torch.cuda.memory_allocated() / GiB, 2)
    res["status"] = "ok"
except torch.OutOfMemoryError as e:
    res["status"] = "OOM"
    res["at"] = f"step{i}"
    res["peak_gib"] = round(torch.cuda.max_memory_allocated() / GiB, 2)
print("RESULT", json.dumps(res), flush=True)
