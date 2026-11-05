#!/usr/bin/env python3
"""mixtape_track_pool_v2.py -- re-render track pool with correct math and 100% AVP models.

Requirements:
- 80s total clips: 30s core generated first, extended 25s forward (55s) and 25s backward (80s).
- Full fine-tunes:
    * Static weight w = 1.0
    * SLERP w = 0.75
    * Magnitude-anchored task vector w = 1.25
- Adapters: static weight w = 1.0
- Base Medium (medium-base, 24 steps, CFG 6.0) AND Post-Trained Medium (medium, 8 steps, CFG 1.0, logSNR schedule).
- 10 prompts from the mixtape track pool.
- GUI presets saved and verified for reproducibility.
"""
import json, os, random, sys, time
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")

import numpy as np, soundfile as sf, torch
sys.path.insert(0, "/home/kim/Projects/SAO/eval")
sys.path.insert(0, "/home/kim/Projects/SAO/control")
sys.path.insert(0, "/home/kim/Projects/SAO/stable-audio-3")
from forge.fullft import load_fullft, _state_dict, ema_info
from sa3_control.audio_io import save_audio
from stable_audio_3 import StableAudioModel
import presets

RUNS = "/run/media/kim/Mantu/sa3_lora_runs"
OUT = f"{RUNS}/mixtape_trackpool_v2"
PRESET_DIR = "/home/kim/Projects/SAO/eval/presets/mixtape_v2_10prompts"
SR = 44100
CORE_SEC = 30.0
EXT_SEC = 25.0
TOTAL_SEC = 80.0

# 100% AVP Models
MODELS = [
    {
        "name": "soup_mean",
        "kind": "fullft",
        "ckpt": f"{RUNS}/__fullft/fullft/fullft_soup_fp32cmp_avp_t4096_bs1_no35/soup_mean.ckpt",
        "weights": [1.0, 0.75, 1.25]
    },
    {
        "name": "soup_ep7_ep14",
        "kind": "fullft",
        "ckpt": f"{RUNS}/__fullft/fullft/fullft_soup_fp32cmp_avp_t4096_bs1_no35/soup_ep7_ep14.ckpt",
        "weights": [1.0, 0.75, 1.25]
    },
    {
        "name": "fullft_avp_t256_ep80",
        "kind": "fullft",
        "ckpt": f"{RUNS}/__fullft/fullft_avp_t256/epoch=80-step=46944.weights.ckpt",
        "weights": [1.0, 0.75, 1.25]
    },
    {
        "name": "subloss_k24_avpaug_ep63",
        "kind": "adapter",
        "ckpt": "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/runs/subloss_k24/subloss_k24_avpaug_t512_bf16_s1/epoch=63-step=2368.ckpt",
        "weights": [1.0]
    },
    {
        "name": "fp32cmp_avp_bs4_lr1e4_ep28",
        "kind": "adapter",
        "ckpt": f"{RUNS}/__precision_compare/fp32cmp_avp_t4096_bs4_lr1e4/epoch=28-step=14953.weights.ckpt",
        "weights": [1.0]
    },
    {
        "name": "dora128adj_avp_8ep_final",
        "kind": "adapter",
        "ckpt": f"{RUNS}/__finetunes/dora128adj_avp_8ep_final/epoch=0-step=299.weights.ckpt",
        "weights": [1.0]
    },
]

PROMPTS = [
    {"pid": "p00", "seed": 1321560844, "prompt": "2020s goa trance, space retro mood, 143 bpm"},
    {"pid": "p01", "seed": 1382257276, "prompt": "psychedelic trance, 136 bpm, bubbling acid line, pulsating sub bass, tight kick and hi-hats, mystical"},
    {"pid": "p02", "seed": 729796532, "prompt": "This track is a high-energy Psytrance piece that fuses the driving force of classic Goa trance with modern, polished production techniques. It runs at 125 BPM in 4/4 time and is rooted in E♭ major, with occasional color from an E♭maj7 chord that adds a lush, slightly jazzy lift amid the relentless rhythm."},
    {"pid": "p03", "seed": 158725066, "prompt": "2020s tech trance, trance, space mood, 132 bpm"},
    {"pid": "p04", "seed": 782949196, "prompt": "mid 90s goa trance, melodic mood, 151 bpm"},
    {"pid": "p05", "seed": 1262357892, "prompt": "mid 90s goa trance, ambient, space soundscape mood, 110 bpm"},
    {"pid": "p06", "seed": 451991434, "prompt": "early 90s downtempo, ambient, meditative soundscape mood, 102 bpm"},
    {"pid": "p07", "seed": 1391676905, "prompt": "early 2000s goa trance, melodic dark mood, 145 bpm"},
    {"pid": "p08", "seed": 1126148435, "prompt": "hi-tech psytrance, 150 bpm, soaring synth lead, rolling bassline, intricate percussion patterns, dark and hypnotic"},
    {"pid": "p09", "seed": 1403519739, "prompt": "late 90s goa trance, 147 bpm"}
]

def slerp_tensor(v0: torch.Tensor, v1: torch.Tensor, t: float, eps: float = 1e-8) -> torch.Tensor:
    norm_v0 = torch.norm(v0)
    norm_v1 = torch.norm(v1)
    if norm_v0 < eps or norm_v1 < eps:
        return (1.0 - t) * v0 + t * v1
    
    u0 = v0 / norm_v0
    u1 = v1 / norm_v1
    dot = torch.sum(u0 * u1).clamp(-1.0, 1.0)
    
    if torch.abs(dot) > 0.9995:
        res = (1.0 - t) * u0 + t * u1
        res = res / (torch.norm(res) + eps)
    else:
        theta = torch.acos(dot)
        res = (torch.sin((1.0 - t) * theta) * u0 + torch.sin(t * theta) * u1) / torch.sin(theta)
        
    interp_norm = (1.0 - t) * norm_v0 + t * norm_v1
    return res * interp_norm

def blend_param(p_base: torch.Tensor, p_ft: torch.Tensor, w: float) -> torch.Tensor:
    if w == 1.0:
        return p_ft.clone()
    elif w < 1.0:
        return slerp_tensor(p_base, p_ft, w)
    else: # w > 1.0
        # Magnitude-anchored task vector scaling
        norm_ft = torch.norm(p_ft)
        v = p_base + w * (p_ft - p_base)
        norm_v = torch.norm(v)
        if norm_v < 1e-8:
            return v
        return (v / norm_v) * norm_ft

def generate_80s(model, prompt: str, seed: int, cfg_scale: float, steps: int):
    # Step 1: 30s core
    out_core = model.generate(prompt=prompt, duration=CORE_SEC, steps=steps, cfg_scale=cfg_scale, seed=seed, batch_size=1)
    core = out_core[0].float().cpu().numpy()
    n_core = core.shape[-1]
    
    # Step 2: Extend forward 25s (total 55s)
    W1 = CORE_SEC + EXT_SEC
    z1 = np.zeros((core.shape[0], int(W1 * SR)), dtype=np.float32)
    z1[:, :n_core] = core
    out_fwd = model.generate(prompt=prompt, duration=W1, steps=steps, cfg_scale=cfg_scale, seed=seed + 1,
                             inpaint_audio=(SR, torch.tensor(z1)),
                             inpaint_mask_start_seconds=CORE_SEC, inpaint_mask_end_seconds=W1,
                             batch_size=1)
    fwd = out_fwd[0].float().cpu().numpy()
    fwd = np.pad(fwd, ((0, 0), (0, max(0, int(W1 * SR) - fwd.shape[-1]))))[:, :int(W1 * SR)]
    
    # Step 3: Extend backward 25s (total 80s)
    W2 = W1 + EXT_SEC # 80.0s
    z2 = np.zeros((core.shape[0], int(W2 * SR)), dtype=np.float32)
    z2[:, int(EXT_SEC * SR):] = fwd
    out_full = model.generate(prompt=prompt, duration=W2, steps=steps, cfg_scale=cfg_scale, seed=seed + 2,
                              inpaint_audio=(SR, torch.tensor(z2)),
                              inpaint_mask_start_seconds=0.0, inpaint_mask_end_seconds=EXT_SEC,
                              batch_size=1)
    full = out_full[0].float().cpu().numpy()
    full = np.pad(full, ((0, 0), (0, max(0, int(W2 * SR) - full.shape[-1]))))[:, :int(W2 * SR)]
    return full

def save_preset(preset_name, prompt, seed, cfg_scale, steps, model_variant, ckpt_path, weight, kind):
    payload = {
        "prompt": prompt,
        "seed": seed,
        "cfg_scale": cfg_scale,
        "steps": steps,
        "duration": TOTAL_SEC,
        "model_variant": model_variant,
        "weight": weight,
        "checkpoint": ckpt_path,
        "kind": kind
    }
    if kind == "adapter":
        payload["dora"] = {
            "ckpt_path": ckpt_path,
            "strength": weight
        }
    p_path = f"{PRESET_DIR}/{preset_name}.json"
    os.makedirs(os.path.dirname(p_path), exist_ok=True)
    with open(p_path, "w") as f:
        json.dump({"schema": 1, "name": preset_name, "created": time.time(), "payload": payload}, f, indent=2)
    return p_path


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(PRESET_DIR, exist_ok=True)
    manifest_path = f"{OUT}/cells.jsonl"
    
    # Model assignment across 10 prompts:
    # 0, 1: soup_mean (fullft)
    # 2, 3: soup_ep7_ep14 (fullft)
    # 4, 5: fullft_avp_t256_ep80 (fullft)
    # 6, 7: subloss_k24_avpaug_ep63 (adapter)
    # 8: fp32cmp_avp_bs4_lr1e4_ep28 (adapter)
    # 9: dora128adj_avp_8ep_final (adapter)
    prompt_model_map = [
        (0, MODELS[0]), (1, MODELS[0]),
        (2, MODELS[1]), (3, MODELS[1]),
        (4, MODELS[2]), (5, MODELS[2]),
        (6, MODELS[3]), (7, MODELS[3]),
        (8, MODELS[4]),
        (9, MODELS[5])
    ]
    
    # Build list of jobs
    jobs = []
    for pid_idx, model_meta in prompt_model_map:
        p_info = PROMPTS[pid_idx]
        weights = model_meta["weights"]
        for backend in ["base", "ptm"]: # medium-base vs medium post-trained
            for w in weights:
                job_id = f"t{pid_idx:02d}_{model_meta['name']}_{backend}_w{int(w*100):03d}"
                jobs.append({
                    "id": job_id,
                    "pid_idx": pid_idx,
                    "pid": p_info["pid"],
                    "prompt": p_info["prompt"],
                    "seed": p_info["seed"],
                    "model_meta": model_meta,
                    "backend": backend,
                    "weight": w
                })

    done_ids = set()
    if os.path.exists(manifest_path):
        for line in open(manifest_path):
            try:
                done_ids.add(json.loads(line)["id"])
            except Exception:
                pass

    print(f"Total jobs to run: {len(jobs)}, already done: {len(done_ids)}", flush=True)

    # Group jobs by (backend, model) so we minimize model reloads
    from collections import defaultdict
    grouped = defaultdict(list)
    for j in jobs:
        if j["id"] not in done_ids:
            grouped[(j["backend"], j["model_meta"]["name"])].append(j)

    for (backend, model_name), job_list in grouped.items():
        m_meta = job_list[0]["model_meta"]
        print(f"\n==================================================", flush=True)
        print(f"Loading {backend.upper()} with {model_name} ({m_meta['kind']})", flush=True)
        print(f"==================================================", flush=True)
        
        pretrained_name = "medium-base" if backend == "base" else "medium"
        model = StableAudioModel.from_pretrained(pretrained_name, device="cuda")
        
        base_params = {}
        ft_params = {}
        
        if m_meta["kind"] == "fullft":
            tgt = model.model.model
            base_params = {k: v.detach().cpu().clone() for k, v in tgt.named_parameters()}
            sd = _state_dict(m_meta["ckpt"])
            ei = ema_info(sd)
            use_ema = bool(ei and ei["converged"])
            load_fullft(model, m_meta["ckpt"], weights="ema" if use_ema else "online", sd=sd)
            ft_params = {k: v.detach().cpu().clone() for k, v in tgt.named_parameters()}
            del sd
        else: # adapter
            model.load_lora([m_meta["ckpt"]])

        steps = 24 if backend == "base" else 8
        cfg = 6.0 if backend == "base" else 1.0

        for j in job_list:
            t0 = time.time()
            w = j["weight"]
            
            if m_meta["kind"] == "fullft":
                with torch.no_grad():
                    for k, p in model.model.model.named_parameters():
                        blended = blend_param(base_params[k], ft_params[k], w)
                        p.copy_(blended.to(device="cuda", dtype=p.dtype))
            else:
                model.set_lora_strength(w)
                
            print(f"[{j['id']}] Rendering prompt '{j['prompt'][:40]}...' (steps={steps}, cfg={cfg}, w={w})", flush=True)
            try:
                audio = generate_80s(model, j["prompt"], j["seed"], cfg, steps)
                out_wav = f"{OUT}/{j['id']}.wav"
                save_audio(out_wav, torch.tensor(audio), SR)
                
                # Save preset
                preset_name = f"mixtape_v2_10prompts/{j['id']}"
                preset_file = save_preset(preset_name, j["prompt"], j["seed"], cfg, steps,
                                          backend, m_meta["ckpt"], w, m_meta["kind"])
                
                # Compute RMS metrics
                rms_total = float(20 * np.log10(np.sqrt((audio ** 2).mean()) + 1e-12))
                peak = float(np.abs(audio).max())
                elapsed = time.time() - t0
                
                record = {
                    "id": j["id"],
                    "pid": j["pid"],
                    "prompt": j["prompt"],
                    "seed": j["seed"],
                    "backend": backend,
                    "model": m_meta["name"],
                    "kind": m_meta["kind"],
                    "ckpt": m_meta["ckpt"],
                    "weight": w,
                    "steps": steps,
                    "cfg": cfg,
                    "dur": round(audio.shape[-1] / SR, 2),
                    "rms_db": round(rms_total, 2),
                    "peak": round(peak, 3),
                    "preset": preset_file,
                    "render_sec": round(elapsed, 1)
                }
                with open(manifest_path, "a") as f:
                    f.write(json.dumps(record) + "\n")
                print(f"  -> Done in {elapsed:.1f}s | RMS: {rms_total:.1f} dB, Peak: {peak:.3f}", flush=True)
                
            except Exception as e:
                print(f"  -> ERROR on {j['id']}: {e}", flush=True)
                import traceback
                traceback.print_exc()

        del model, base_params, ft_params
        import gc
        gc.collect()
        torch.cuda.empty_cache()

    print("\nALL RENDER JOBS COMPLETED!", flush=True)

if __name__ == "__main__":
    main()
