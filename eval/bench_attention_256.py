#!/usr/bin/env python3
# Owner: ANTIGRAVITY (created 2026-10-13)
# Last edited: GHOST-NOTE 2026-10-13 -- copied from the Antigravity scratch dir into eval/ so the CK-vs-SDPA runs can be repeated
"""
Benchmark CK Flash-Attention vs Native PyTorch SDPA on gfx1201 across 256 steps.
Supports:
  1. kernel: Raw attention kernel fwd+bwd over 256 steps (CK vs PyTorch SDPA backends)
  2. model: End-to-end SA3 DiT model fwd+bwd over 256 steps (CK vs native PyTorch SDPA)
"""

import os
import sys
import time
import argparse
import statistics
import json

os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import torch
import torch.nn.functional as F

def get_env_info():
    info = {
        "python": sys.executable,
        "torch_version": torch.__version__,
        "hip_version": getattr(torch.version, "hip", None),
        "cuda_is_available": torch.cuda.is_available(),
        "device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "None",
    }
    try:
        import flash_attn
        info["flash_attn_version"] = getattr(flash_attn, "__version__", "unknown")
        import flash_attn_2_cuda
        info["flash_attn_2_cuda"] = flash_attn_2_cuda.__file__
    except ImportError:
        info["flash_attn_version"] = None
        info["flash_attn_2_cuda"] = None
    return info

def bench_raw_kernel(T=512, B=1, H=24, D=64, steps=256, warmup=10, dtype=torch.bfloat16):
    print(f"\n=======================================================")
    print(f"RAW ATTENTION KERNEL BENCHMARK (B={B}, H={H}, T={T}, D={D}, steps={steps}, dtype={dtype})")
    print(f"=======================================================")
    
    results = {}
    
    # Try CK Flash-Attention if available
    try:
        from flash_attn import flash_attn_func
        has_ck = True
    except ImportError:
        has_ck = False
        
    candidates = []
    if has_ck:
        candidates.append(("CK_FlashAttention", "ck"))
        
    from torch.nn.attention import SDPBackend, sdpa_kernel
    candidates.append(("PyTorch_SDPA_Default", "sdpa_default"))
    candidates.append(("PyTorch_SDPA_Flash", SDPBackend.FLASH_ATTENTION))
    candidates.append(("PyTorch_SDPA_MemEfficient", SDPBackend.EFFICIENT_ATTENTION))
    candidates.append(("PyTorch_SDPA_Math", SDPBackend.MATH))
    
    for label, mode in candidates:
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        
        # Q, K, V setup
        # For CK flash_attn_func: shape is [B, T, H, D]
        # For PyTorch SDPA: shape is [B, H, T, D]
        g = torch.Generator(device="cuda").manual_seed(42)
        
        try:
            if mode == "ck":
                q = torch.randn(B, T, H, D, device="cuda", dtype=dtype, generator=g, requires_grad=True)
                k = torch.randn(B, T, H, D, device="cuda", dtype=dtype, generator=g, requires_grad=True)
                v = torch.randn(B, T, H, D, device="cuda", dtype=dtype, generator=g, requires_grad=True)
                grad_out = torch.randn(B, T, H, D, device="cuda", dtype=dtype, generator=g)
                
                def run_op():
                    out = flash_attn_func(q, k, v, causal=False)
                    out.backward(grad_out)
                    q.grad = None; k.grad = None; v.grad = None
            elif mode == "sdpa_default":
                q = torch.randn(B, H, T, D, device="cuda", dtype=dtype, generator=g, requires_grad=True)
                k = torch.randn(B, H, T, D, device="cuda", dtype=dtype, generator=g, requires_grad=True)
                v = torch.randn(B, H, T, D, device="cuda", dtype=dtype, generator=g, requires_grad=True)
                grad_out = torch.randn(B, H, T, D, device="cuda", dtype=dtype, generator=g)
                
                def run_op():
                    out = F.scaled_dot_product_attention(q, k, v, is_causal=False)
                    out.backward(grad_out)
                    q.grad = None; k.grad = None; v.grad = None
            else:
                q = torch.randn(B, H, T, D, device="cuda", dtype=dtype, generator=g, requires_grad=True)
                k = torch.randn(B, H, T, D, device="cuda", dtype=dtype, generator=g, requires_grad=True)
                v = torch.randn(B, H, T, D, device="cuda", dtype=dtype, generator=g, requires_grad=True)
                grad_out = torch.randn(B, H, T, D, device="cuda", dtype=dtype, generator=g)
                
                def run_op():
                    with sdpa_kernel(mode):
                        out = F.scaled_dot_product_attention(q, k, v, is_causal=False)
                        out.backward(grad_out)
                        q.grad = None; k.grad = None; v.grad = None

            # Warmup
            for _ in range(warmup):
                run_op()
            torch.cuda.synchronize()
            
            # Timed steps
            times = []
            start_total = time.perf_counter()
            for s in range(steps):
                t0 = time.perf_counter()
                run_op()
                torch.cuda.synchronize()
                t1 = time.perf_counter()
                times.append((t1 - t0) * 1000.0) # in ms
            end_total = time.perf_counter()
            total_sec = end_total - start_total
            
            mean_ms = statistics.mean(times)
            median_ms = statistics.median(times)
            min_ms = min(times)
            max_ms = max(times)
            stdev_ms = statistics.stdev(times)
            peak_vram_mb = torch.cuda.max_memory_allocated() / (1024 * 1024)
            
            # Theoretical FLOPs for attention fwd + bwd:
            # fwd: 2 * 2 * B * H * T * T * D = 4 * B * H * T^2 * D
            # bwd: ~2.5x fwd FLOPs -> total ~ 3.5 * (4 * B * H * T^2 * D)
            # We report per-step time and throughput
            tflops = (3.5 * 4 * B * H * (T ** 2) * D) / (mean_ms * 1e-3) / 1e12
            
            print(f"[{label:28s}] {steps} steps in {total_sec:.3f}s | "
                  f"mean: {mean_ms:6.3f} ms | median: {median_ms:6.3f} ms | "
                  f"min: {min_ms:6.3f} ms | max: {max_ms:6.3f} ms | "
                  f"peak VRAM: {peak_vram_mb:6.1f} MB | {tflops:5.1f} TFLOPS")
            
            results[label] = {
                "total_sec": total_sec,
                "mean_ms": mean_ms,
                "median_ms": median_ms,
                "min_ms": min_ms,
                "max_ms": max_ms,
                "stdev_ms": stdev_ms,
                "peak_vram_mb": peak_vram_mb,
                "tflops": tflops
            }
        except Exception as e:
            print(f"[{label:28s}] FAILED: {e}")
            results[label] = {"error": str(e)}
            
    return results

def bench_model_dit(T=512, steps=256, warmup=5, opt_choice="all"):
    print(f"\n=======================================================")
    print(f"SA3 DiT MODEL TRAINING BENCHMARK (T={T}, steps={steps}, warmup={warmup})")
    print(f"=======================================================")
    
    from stable_audio_3 import StableAudioModel
    import stable_audio_3.models.transformer as tr
    
    dev = "cuda"
    print("Loading medium-base model onto CUDA...", flush=True)
    t_load0 = time.time()
    m = StableAudioModel.from_pretrained("medium-base")
    diff = m.model
    diff.requires_grad_(False)
    
    # Train to_out projections across blocks to trigger full forward & backward
    train_params = [p for n, p in diff.model.named_parameters() if "to_out" in n][:48]
    for p in train_params:
        p.requires_grad_(True)
        
    print(f"Model loaded in {time.time() - t_load0:.2f}s. Parameters trained: {len(train_params)} to_out layers.", flush=True)
    
    # Setup inputs
    cond = diff.conditioner([{"prompt": "mid 90s goa trance, 145 bpm", "seconds_total": T / 10.7666}], dev)
    B, C = 1, 256
    for _id, _c in (("inpaint_mask", 1), ("inpaint_masked_input", C)):
        if _id in getattr(diff, "local_add_cond_ids", []) and _id not in cond:
            cond[_id] = [torch.zeros(B, _c, T, device=dev)]
            
    g = torch.Generator(device="cpu").manual_seed(0)
    z0 = torch.randn(B, C, T, generator=g).to(dev)
    noise = torch.randn(B, C, T, generator=g).to(dev)
    t = torch.tensor([0.5], device=dev)
    x = z0 * (1 - t)[:, None, None] + noise * t[:, None, None]
    
    # Determine CK availability
    has_ck = getattr(tr, "flash_attn_func", None) is not None
    CK_funcs = (tr.flash_attn_func, tr.flash_attn_varlen_func) if has_ck else (None, None)
    
    options = {}
    if has_ck and opt_choice in ("all", "ck"):
        options["CK_FlashAttention"] = CK_funcs
    if opt_choice in ("all", "native", "no_fa"):
        options["Native_PyTorch_SDPA"] = (None, None)
        
    results = {}
    
    for opt_name, (fa_func, fa_varlen) in options.items():
        tr.flash_attn_func = fa_func
        tr.flash_attn_varlen_func = fa_varlen
        
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        
        print(f"\nRunning condition: {opt_name} (flash_attn_func={tr.flash_attn_func is not None}) ...", flush=True)
        
        # Warmup
        for w in range(warmup):
            with torch.autocast("cuda", dtype=torch.bfloat16):
                v = diff(x, t, cond=cond, cfg_dropout_prob=0.0)
            loss = F.mse_loss(v.float(), noise - z0)
            loss.backward()
            for p in train_params:
                p.grad = None
        torch.cuda.synchronize()
        
        # 256 Steps Benchmark
        step_times = []
        losses = []
        start_bench = time.perf_counter()
        
        for step in range(steps):
            t_s0 = time.perf_counter()
            with torch.autocast("cuda", dtype=torch.bfloat16):
                v = diff(x, t, cond=cond, cfg_dropout_prob=0.0)
            loss = F.mse_loss(v.float(), noise - z0)
            loss.backward()
            for p in train_params:
                p.grad = None
            torch.cuda.synchronize()
            t_s1 = time.perf_counter()
            dt_ms = (t_s1 - t_s0) * 1000.0
            step_times.append(dt_ms)
            losses.append(loss.item())
            
            if (step + 1) % 64 == 0 or step == steps - 1:
                print(f"  Step {step+1:3d}/{steps}: recent 64 mean = {statistics.mean(step_times[-64:]):.2f} ms | loss = {loss.item():.4f}", flush=True)
                
        end_bench = time.perf_counter()
        total_time_s = end_bench - start_bench
        
        mean_ms = statistics.mean(step_times)
        median_ms = statistics.median(step_times)
        min_ms = min(step_times)
        max_ms = max(step_times)
        stdev_ms = statistics.stdev(step_times)
        peak_vram_gib = torch.cuda.max_memory_allocated() / (1024 ** 3)
        throughput = steps / total_time_s
        
        print(f"RESULT [{opt_name}] across {steps} steps:")
        print(f"  Total time:       {total_time_s:.2f} s")
        print(f"  Throughput:       {throughput:.2f} steps/s")
        print(f"  Mean step time:   {mean_ms:.2f} ms")
        print(f"  Median step time: {median_ms:.2f} ms")
        print(f"  Min / Max step:   {min_ms:.2f} ms / {max_ms:.2f} ms (stdev: {stdev_ms:.2f} ms)")
        print(f"  Peak VRAM:        {peak_vram_gib:.2f} GiB")
        print(f"  Loss @ step {steps}: {losses[-1]:.4f} (all finite: {all(torch.isfinite(torch.tensor(losses)).tolist())})")
        
        results[opt_name] = {
            "total_time_s": total_time_s,
            "throughput_steps_per_s": throughput,
            "mean_ms": mean_ms,
            "median_ms": median_ms,
            "min_ms": min_ms,
            "max_ms": max_ms,
            "stdev_ms": stdev_ms,
            "peak_vram_gib": peak_vram_gib,
            "final_loss": losses[-1],
        }
        
    return results

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["all", "kernel", "model"], default="all")
    parser.add_argument("--steps", type=int, default=256)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--t", type=int, default=512)
    parser.add_argument("--opt", choices=["all", "ck", "native"], default="all")
    parser.add_argument("--out", type=str, default=None)
    args = parser.parse_args()
    
    env_info = get_env_info()
    print("Environment:")
    for k, v in env_info.items():
        print(f"  {k}: {v}")
        
    out_data = {"env": env_info}
    
    if args.mode in ("all", "kernel"):
        kernel_res_512 = bench_raw_kernel(T=512, steps=args.steps, warmup=args.warmup)
        kernel_res_2048 = bench_raw_kernel(T=2048, steps=args.steps, warmup=args.warmup)
        out_data["kernel_t512"] = kernel_res_512
        out_data["kernel_t2048"] = kernel_res_2048
        
    if args.mode in ("all", "model"):
        model_res = bench_model_dit(T=args.t, steps=args.steps, warmup=args.warmup, opt_choice=args.opt)
        out_data["model"] = model_res
        
    if args.out:
        with open(args.out, "w") as f:
            json.dump(out_data, f, indent=2)
        print(f"\nSaved benchmark results to {args.out}")

if __name__ == "__main__":
    main()
