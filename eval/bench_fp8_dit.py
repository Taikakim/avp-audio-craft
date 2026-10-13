#!/usr/bin/env python
# Owner: GHOST-NOTE (created 2026-10-13)
"""bench_fp8_dit.py -- does FP8 on the FROZEN linears speed up an SA3 DiT training step, and what does it do to the gradient?

Same proxy as eval/bench_attention_256.py (ANTIGRAVITY): medium-base, T frames, B=1, bf16 autocast, the 48 `to_out` weights are the
trainable stand-in for an adapter, everything else frozen. Two arms in ONE process, alternating, so card state and clocks are shared:
  bf16 : the stock model
  fp8  : every frozen nn.Linear -> eval/fp8_linear.Fp8Linear (E4M3 forward, E5M2 input-gradient, dynamic per-tensor scale)
First an INSTRUMENT check (audit-the-instrument rule): on identical inputs, cosine / relative error of the output velocity and of the
gradient of every trainable weight, fp8 against bf16; and the same between two bf16 runs (the noise floor of the comparison).
Then 256 timed steps per arm. Writes a JSON.

RUN: FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE ROCR_VISIBLE_DEVICES=0 <venv>/bin/python eval/bench_fp8_dit.py --attn native --out X.json
     (--attn ck needs flash_attn in the venv). Run from a scratch cwd, not the SAO root.
"""
import argparse
import json
import os
import statistics
import sys
import time

os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
import torch
import torch.nn.functional as F

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fp8_linear as f8  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--t", type=int, default=512)
    ap.add_argument("--steps", type=int, default=256)
    ap.add_argument("--warmup", type=int, default=10)
    ap.add_argument("--attn", choices=("native", "ck"), default="native")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    from stable_audio_3 import StableAudioModel
    import stable_audio_3.models.transformer as tr
    dev, T, B, C = "cuda", a.t, 1, 256
    if a.attn == "ck":
        assert getattr(tr, "flash_attn_func", None) is not None, "flash_attn is not importable in this venv"
    else:
        tr.flash_attn_func = tr.flash_attn_varlen_func = None
    m = StableAudioModel.from_pretrained("medium-base")
    diff = m.model
    diff.requires_grad_(False)
    train = [p for n, p in diff.model.named_parameters() if "to_out" in n][:48]
    for p in train:
        p.requires_grad_(True)
    cond = diff.conditioner([{"prompt": "mid 90s goa trance, 145 bpm", "seconds_total": T / 10.7666}], dev)
    for _id, _c in (("inpaint_mask", 1), ("inpaint_masked_input", C)):
        if _id in getattr(diff, "local_add_cond_ids", []) and _id not in cond:
            cond[_id] = [torch.zeros(B, _c, T, device=dev)]
    g = torch.Generator(device="cpu").manual_seed(0)
    z0, noise = torch.randn(B, C, T, generator=g).to(dev), torch.randn(B, C, T, generator=g).to(dev)
    t = torch.tensor([0.5], device=dev)
    x = z0 * (1 - t)[:, None, None] + noise * t[:, None, None]

    def step():
        with torch.autocast("cuda", dtype=torch.bfloat16):
            v = diff(x, t, cond=cond, cfg_dropout_prob=0.0)
        loss = F.mse_loss(v.float(), noise - z0)
        loss.backward()
        return v.detach().float(), loss.item()

    def grads():
        gr = torch.cat([p.grad.detach().float().flatten() for p in train])
        for p in train:
            p.grad = None
        return gr

    res = {"torch": torch.__version__, "hip": torch.version.hip, "attn": a.attn, "T": T, "steps": a.steps}
    # --- the instrument check
    v_ref, l_ref = step(); g_ref = grads()
    v_ref2, l_ref2 = step(); g_ref2 = grads()                                     # bf16 against bf16: the noise floor
    n, cov, tot = f8.swap_fp8(diff.model)
    res["fp8_layers"], res["fp8_param_fraction_of_linears"] = n, cov / max(tot, 1)
    v_8, l_8 = step(); g_8 = grads()
    cos = lambda p, q: float(F.cosine_similarity(p.flatten(), q.flatten(), dim=0))   # noqa: E731
    rel = lambda p, q: float((p - q).norm() / q.norm())                              # noqa: E731
    res["check"] = {"velocity_cos_fp8_vs_bf16": cos(v_8, v_ref), "velocity_rel_fp8_vs_bf16": rel(v_8, v_ref),
                    "velocity_rel_bf16_vs_bf16": rel(v_ref2, v_ref), "grad_cos_fp8_vs_bf16": cos(g_8, g_ref),
                    "grad_rel_fp8_vs_bf16": rel(g_8, g_ref), "grad_cos_bf16_vs_bf16": cos(g_ref2, g_ref),
                    "loss_bf16": l_ref, "loss_fp8": l_8}
    print("INSTRUMENT CHECK", json.dumps(res["check"], indent=1), f"\n  fp8 layers {n}, {cov / max(tot, 1):.1%} of linear params", flush=True)

    # --- timing: alternate the arms in rounds of 64 steps so drift hits both
    f8.restore_fp8(diff.model)
    arms = {"bf16": [], "fp8": []}
    swapped = {"fp8": None}
    mem = {}
    for _ in range(a.warmup):
        step(); grads()
    f8.swap_fp8(diff.model)
    for _ in range(a.warmup):
        step(); grads()
    f8.restore_fp8(diff.model)
    rounds = max(1, a.steps // 64)
    for r in range(rounds):
        for arm in ("bf16", "fp8"):
            if arm == "fp8":
                f8.swap_fp8(diff.model)
            torch.cuda.reset_peak_memory_stats()
            for _ in range(64):
                torch.cuda.synchronize(); t0 = time.perf_counter()
                step(); grads()
                torch.cuda.synchronize(); arms[arm].append((time.perf_counter() - t0) * 1000)
            mem[arm] = max(mem.get(arm, 0), torch.cuda.max_memory_allocated() / 2 ** 30)
            if arm == "fp8":
                f8.restore_fp8(diff.model)
    for arm, ts in arms.items():
        res[arm] = {"mean_ms": statistics.mean(ts), "median_ms": statistics.median(ts), "stdev_ms": statistics.stdev(ts),
                    "n": len(ts), "peak_vram_gib": mem[arm]}
        print(f"{arm}: median {statistics.median(ts):.1f} ms  mean {statistics.mean(ts):.1f}  (n={len(ts)})  peak {mem[arm]:.2f} GiB")
    res["speedup_median"] = res["bf16"]["median_ms"] / res["fp8"]["median_ms"]
    print(f"fp8 speedup (median) x{res['speedup_median']:.3f}")
    if a.out:
        json.dump(res, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
