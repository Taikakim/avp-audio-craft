#!/usr/bin/env python
# Owner: GHOST-NOTE (created 2026-10-13)
"""trace_dit_step.py -- the workload for `rocprofv3 --kernel-trace --stats`: a few SA3 DiT training steps (same proxy as
eval/bench_attention_256.py: medium-base, T=512, B=1, bf16 autocast, 48 trainable to_out) with CK flash-attn or native SDPA, or a raw
CK fwd+bwd loop (--mode ckraw) to reproduce the GPU memory fault seen in the 10.1 CK kernel benchmark at T=512.
WHY: CK is ~1.45x slower than SDPA per step on every stack tried; the trace says which kernels the time goes to.
RUN: rocprofv3 --kernel-trace --stats -d OUT -- <venv>/bin/python eval/trace_dit_step.py --attn ck|native  (from a scratch cwd)"""
import argparse, os, platform, sys, time
# platform.architecture() forks `file`; a fork inside a process rocprofv3 is tracing deadlocks (seen 2026-10-13: main thread in wait4 on a
# child that never exec'd, both CK and SDPA runs). Nothing here needs it.
platform.architecture = lambda *a, **k: ("64bit", "ELF")
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
import torch
import torch.nn.functional as F

ap = argparse.ArgumentParser()
ap.add_argument("--attn", choices=("native", "ck"), default="native")
ap.add_argument("--mode", choices=("dit", "ckraw"), default="dit")
ap.add_argument("--steps", type=int, default=6)
ap.add_argument("--t", type=int, default=512)
a = ap.parse_args()
dev, T = "cuda", a.t
if a.mode == "ckraw":
    from flash_attn import flash_attn_func
    ok = 0
    for i in range(400):
        q = torch.randn(1, T, 24, 64, device=dev, dtype=torch.bfloat16, requires_grad=True)
        k, v = torch.randn_like(q), torch.randn_like(q)
        o = flash_attn_func(q, k, v)
        o.sum().backward()
        torch.cuda.synchronize()
        ok += 1
    print(f"ckraw: {ok} fwd+bwd OK at T={T}")
    sys.exit(0)
from stable_audio_3 import StableAudioModel
import stable_audio_3.models.transformer as tr
if a.attn == "native":
    tr.flash_attn_func = tr.flash_attn_varlen_func = None
else:
    assert tr.flash_attn_func is not None
m = StableAudioModel.from_pretrained("medium-base")
diff = m.model
diff.requires_grad_(False)
for p in [p for n, p in diff.model.named_parameters() if "to_out" in n][:48]:
    p.requires_grad_(True)
cond = diff.conditioner([{"prompt": "mid 90s goa trance, 145 bpm", "seconds_total": T / 10.7666}], dev)
for _id, _c in (("inpaint_mask", 1), ("inpaint_masked_input", 256)):
    if _id in getattr(diff, "local_add_cond_ids", []) and _id not in cond:
        cond[_id] = [torch.zeros(1, _c, T, device=dev)]
g = torch.Generator(device="cpu").manual_seed(0)
z0, noise = torch.randn(1, 256, T, generator=g).to(dev), torch.randn(1, 256, T, generator=g).to(dev)
t = torch.tensor([0.5], device=dev)
x = z0 * (1 - t)[:, None, None] + noise * t[:, None, None]
for i in range(a.steps):
    t0 = time.perf_counter()
    with torch.autocast("cuda", dtype=torch.bfloat16):
        v = diff(x, t, cond=cond, cfg_dropout_prob=0.0)
    F.mse_loss(v.float(), noise - z0).backward()
    for p in diff.parameters():
        p.grad = None
    torch.cuda.synchronize()
    print(f"step {i}: {(time.perf_counter() - t0) * 1000:.1f} ms", flush=True)
