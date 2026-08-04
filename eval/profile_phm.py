#!/usr/bin/env python
"""profile_phm.py — root-cause the PHM 26s/step (E2) vs dora 3s/step. GPU torch.profiler.

Uses the REAL LoRAParametrization from the repo, registered on real DiT module shapes via
torch.nn.utils.parametrize (the exact training code path), and times/profiles fwd+bwd of a
parametrized Linear for {dora-rows, phm} at bf16 — isolating the ONLY thing that differs
between the two training runs. Tests three hypotheses:
  H1 per-call cost: is phm_forward itself much slower on GPU (delta build)?
  H2 recompute: is the parametrization recomputed every .weight access (no caching)?
  H3 dtype fallback: does the materialized delta force fp32 matmuls?
The profiler op table (self CUDA time) localizes which.

Run (SA3 venv, GPU, hold SAO/.gpu.lock):
  FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE .venv/bin/python eval/profile_phm.py
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
import sys, time
from pathlib import Path
import torch
import torch.nn as nn
import torch.nn.utils.parametrize as P

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stable-audio-3"))
from stable_audio_3.models.lora.model import LoRAParametrization

DEV = "cuda"
DT = torch.bfloat16
# real DiT module shapes: attn out-proj (1536x1536) and fused qkv (7680x1536)
SHAPES = [("attn_out_1536x1536", 1536, 1536), ("fused_qkv_7680x1536", 7680, 1536)]
B, T = 4, 512          # batch, tokens (E2 config)
N_STEP, N_CALL = 12, 1


def make_param(fan_out, fan_in, kind):
    lin = nn.Linear(fan_in, fan_out, bias=False).to(DEV, DT)
    lin.weight.requires_grad_(False)
    at = "dora-rows" if kind == "dora-rows" else "phm"
    pm = LoRAParametrization(fan_in, fan_out, rank=128, lora_alpha=128,
                             adapter_type=at, phm_n=4).to(DEV, DT)
    P.register_parametrization(lin, "weight", pm)
    return lin


def bench(kind, fan_out, fan_in, cached):
    lin = make_param(fan_out, fan_in, kind)
    x = torch.randn(B, T, fan_in, device=DEV, dtype=DT, requires_grad=True)
    def step():
        ctx = P.cached() if cached else _null()
        with ctx:
            y = lin(x)
        y.sum().backward()
        for p in lin.parameters():
            p.grad = None
        x.grad = None
    step(); torch.cuda.synchronize()
    t = time.time()
    for _ in range(N_STEP):
        step()
    torch.cuda.synchronize()
    return (time.time() - t) / N_STEP * 1000


class _null:
    def __enter__(self): return self
    def __exit__(self, *a): return False


def main():
    print(f"device bf16; B={B} T={T}; per-step ms (fwd+bwd of parametrized linear)\n")
    print(f"{'shape':<22} {'dora':>9} {'phm':>9} {'phm/dora':>9} {'phm+cached':>11}")
    hot = None
    for name, fo, fi in SHAPES:
        d = bench("dora-rows", fo, fi, cached=False)
        p = bench("phm", fo, fi, cached=False)
        pc = bench("phm", fo, fi, cached=True)
        print(f"{name:<22} {d:>9.2f} {p:>9.2f} {p/d:>8.1f}x {pc:>11.2f}")
        if name == SHAPES[1][0]:
            hot = (fo, fi)

    # profiler on the worst case (fused qkv) — where does phm's CUDA time go?
    print("\n=== torch.profiler: phm fused_qkv fwd+bwd, top ops by self CUDA time ===")
    fo, fi = hot
    lin = make_param(fo, fi, "phm")
    x = torch.randn(B, T, fi, device=DEV, dtype=DT, requires_grad=True)
    from torch.profiler import profile, ProfilerActivity
    for _ in range(3):
        lin(x).sum().backward()
    torch.cuda.synchronize()
    with profile(activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA],
                 record_shapes=True) as prof:
        for _ in range(5):
            y = lin(x); y.sum().backward()
        torch.cuda.synchronize()
    print(prof.key_averages().table(sort_by="self_cuda_time_total", row_limit=15))

    # H3: what dtype is the materialized delta / weight?
    w = lin.weight
    print(f"\nmaterialized weight dtype: {w.dtype} (base DT={DT})")
    print("H-checks: p/dora ratio above = per-call cost; phm+cached vs phm = recompute share; "
          "profiler fp32 gemm rows = dtype fallback.")


if __name__ == "__main__":
    main()
