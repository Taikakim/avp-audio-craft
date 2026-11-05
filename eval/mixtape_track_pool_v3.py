#!/usr/bin/env python3
"""mixtape_track_pool_v3.py -- beat-aware steady crop + two-pass outpainting with dual prompt modes.

Key Improvements:
1. Beat-aware steady cropper: identifies fadeout via rolling RMS, extracts div4-bar steady core
   using madmom_downbeats and find_zero_crossing_backwards, eliminating 30s tail fadeouts.
2. Two-pass outpainting:
   - Pass 1: Latter outpaint (forward continuation from steady core)
   - Pass 2: Preceding outpaint (backward lead-in)
3. Dual prompt modes per track:
   - Mode A: Exact original prompt.
   - Mode B: LMM Hardware & Timbre Enriched prompt (SH-101 portamento, 303 acid, Polivoks, FM lead, etc.).
4. Asymmetric allocation (20% of clips):
   - Extracts onsets with detect_onsets.
   - Preceding outpaint reduced by 20%, latter outpaint increased by 15%, snapped to onsets.
5. Model configurations & Adapter Stacking:
   - Base Medium 24-step engine (NO PTM 8-step on flow-matching checkpoints).
   - Full-FT backbone (fullft_avp_t256_ep80) at w in [1.0, 1.25] (CFG 10.0).
   - Adapters stacked directly on Full-FT backbone (dora128adj, subloss_k24, fp32cmp) at w in [1.0, 1.25] (CFG 8.0).
   - Soups (soup_mean, soup_ep7_ep14) at w in [0.75, 1.0] (CFG 7.0).
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
from dj_beatmatch import madmom_downbeats
sys.path.insert(0, "/home/kim/Projects/mir/src")
from tools.create_training_crops import find_zero_crossing_backwards
from rhythm.onsets import detect_onsets

RUNS = "/run/media/kim/Mantu/sa3_lora_runs"
OUT = f"{RUNS}/mixtape_trackpool_v3"
PRESET_DIR = "/home/kim/Projects/SAO/eval/presets/mixtape_v3_prompts"
SR = 44100
CORE_TARGET_SEC = 30.0
TOTAL_TARGET_SEC = 80.0

PROMPTS_V3 = [
    {
        "pid": "p00",
        "seed": 1321560844,
        "prompt": "2020s goa trance, space retro mood, 143 bpm",
        "prompt_enriched": "2020s goa trance, space retro mood, 143 bpm, Roland SH-101 portamento lead, legato bittersweet synth melody a fifth above the fundamental, lush vintage analog chorus, punchy 909 kick, cosmic resonant filter sweeps"
    },
    {
        "pid": "p01",
        "seed": 1382257276,
        "prompt": "psychedelic trance, 136 bpm, bubbling acid line, pulsating sub bass, tight kick and hi-hats, mystical",
        "prompt_enriched": "psychedelic trance, 136 bpm, distorted bubbly 303 acid riff, Roland TB-303 square wave resonance, squelchy envelope filter modulation, pulsating Moog sub bass, tight kick and hi-hats, mystical Tibetan bell harmonics"
    },
    {
        "pid": "p02",
        "seed": 729796532,
        "prompt": "This track is a high-energy Psytrance piece that fuses the driving force of classic Goa trance with modern, polished production techniques. It runs at 125 BPM in 4/4 time and is rooted in E♭ major, with occasional color from an E♭maj7 chord that adds a lush, slightly jazzy lift amid the relentless rhythm.",
        "prompt_enriched": "high-energy psytrance, classic Goa trance, 125 bpm, Eb major, Nord Lead 2 screaming resonant poly-arp, Oberheim SEM warm brass stabs voicing an Ebmaj7 chord, crisp ping-pong stereo delays, relentless driving rolling bassline",
        "asymmetric": True
    },
    {
        "pid": "p03",
        "seed": 158725066,
        "prompt": "2020s tech trance, trance, space mood, 132 bpm",
        "prompt_enriched": "2020s tech trance, trance, space mood, 132 bpm, growly FM lead synth, Yamaha DX7 metallic pluck texture, aggressive saw wave stabs, tight industrial percussion, wide stereophonic reverb space"
    },
    {
        "pid": "p04",
        "seed": 782949196,
        "prompt": "mid 90s goa trance, melodic mood, 151 bpm",
        "prompt_enriched": "mid 90s goa trance, melodic mood, 151 bpm, Roland JD-800 sparkling crystal lead, Korg Prophecy eastern microtonal lead riff, acid squelch, soaring euphoric dual-lead harmony, frantic 16th-note arpeggios"
    },
    {
        "pid": "p05",
        "seed": 1262357892,
        "prompt": "mid 90s goa trance, ambient, space soundscape mood, 110 bpm",
        "prompt_enriched": "mid 90s goa trance, ambient, space soundscape mood, 110 bpm, Polivoks psychedelic sfx, dirty analog tape delay, atmospheric EMS VCS3 modular bleeps, deep floating drone pad, organic slow resonance sweep"
    },
    {
        "pid": "p06",
        "seed": 451991434,
        "prompt": "early 90s downtempo, ambient, meditative soundscape mood, 102 bpm",
        "prompt_enriched": "early 90s downtempo, ambient, meditative soundscape mood, 102 bpm, experimental modular synth sounds, Buchla bongos and random voltage generative blips, warm Rhodes chords, deep warm sub bass, organic vinyl dust"
    },
    {
        "pid": "p07",
        "seed": 1391676905,
        "prompt": "early 2000s goa trance, melodic dark mood, 145 bpm",
        "prompt_enriched": "early 2000s goa trance, melodic dark mood, 145 bpm, Access Virus B razor-sharp hypersaw lead, dark minor 9th bittersweet synth arpeggios, screaming resonance, driving psy bassline, sinister space drones",
        "asymmetric": True
    },
    {
        "pid": "p08",
        "seed": 1126148435,
        "prompt": "hi-tech psytrance, 150 bpm, soaring synth lead, rolling bassline, intricate percussion patterns, dark and hypnotic",
        "prompt_enriched": "hi-tech psytrance, 150 bpm, soaring Roland SH-101 portamento lead, glitchy modular granular glitch sfx, razor-fast FM zaps, rolling bassline, intricate percussion patterns, dark and hypnotic"
    },
    {
        "pid": "p09",
        "seed": 1403519739,
        "prompt": "late 90s goa trance, 147 bpm",
        "prompt_enriched": "late 90s goa trance, 147 bpm, dual Roland TB-303 acid battle, resonant bandpass filter sweeps, bittersweet eastern modal melody, punchy 909 snare rolls, shimmering psychedelic flange"
    }
]

TRACK_CONFIGS = [
    {
        "idx": 0, "name": "fullft_ep80_w100",
        "base_model": "medium-base",
        "fullft_ckpt": f"{RUNS}/__fullft/fullft_avp_t256/epoch=80-step=46944.weights.ckpt",
        "fullft_w": 1.0,
        "adapter_ckpt": None, "adapter_w": 0.0,
        "cfg": 10.0, "steps": 24
    },
    {
        "idx": 1, "name": "fullft_ep80_w125",
        "base_model": "medium-base",
        "fullft_ckpt": f"{RUNS}/__fullft/fullft_avp_t256/epoch=80-step=46944.weights.ckpt",
        "fullft_w": 1.25,
        "adapter_ckpt": None, "adapter_w": 0.0,
        "cfg": 10.0, "steps": 24
    },
    {
        "idx": 2, "name": "fullft_ep80_dora128adj_w100",
        "base_model": "medium-base",
        "fullft_ckpt": f"{RUNS}/__fullft/fullft_avp_t256/epoch=80-step=46944.weights.ckpt",
        "fullft_w": 1.0,
        "adapter_ckpt": f"{RUNS}/__finetunes/dora128adj_avp_8ep_final/epoch=0-step=299.weights.ckpt",
        "adapter_w": 1.0,
        "cfg": 8.0, "steps": 24
    },
    {
        "idx": 3, "name": "fullft_ep80_dora128adj_w125",
        "base_model": "medium-base",
        "fullft_ckpt": f"{RUNS}/__fullft/fullft_avp_t256/epoch=80-step=46944.weights.ckpt",
        "fullft_w": 1.0,
        "adapter_ckpt": f"{RUNS}/__finetunes/dora128adj_avp_8ep_final/epoch=0-step=299.weights.ckpt",
        "adapter_w": 1.25,
        "cfg": 8.0, "steps": 24
    },
    {
        "idx": 4, "name": "fullft_ep80_subloss_k24_w100",
        "base_model": "medium-base",
        "fullft_ckpt": f"{RUNS}/__fullft/fullft_avp_t256/epoch=80-step=46944.weights.ckpt",
        "fullft_w": 1.0,
        "adapter_ckpt": "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/runs/subloss_k24/subloss_k24_avpaug_t512_bf16_s1/epoch=63-step=2368.ckpt",
        "adapter_w": 1.0,
        "cfg": 8.0, "steps": 24
    },
    {
        "idx": 5, "name": "fullft_ep80_subloss_k24_w125",
        "base_model": "medium-base",
        "fullft_ckpt": f"{RUNS}/__fullft/fullft_avp_t256/epoch=80-step=46944.weights.ckpt",
        "fullft_w": 1.0,
        "adapter_ckpt": "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/runs/subloss_k24/subloss_k24_avpaug_t512_bf16_s1/epoch=63-step=2368.ckpt",
        "adapter_w": 1.25,
        "cfg": 8.0, "steps": 24
    },
    {
        "idx": 6, "name": "soup_mean_base_w100",
        "base_model": "medium-base",
        "fullft_ckpt": f"{RUNS}/__fullft/fullft/fullft_soup_fp32cmp_avp_t4096_bs1_no35/soup_mean.ckpt",
        "fullft_w": 1.0,
        "adapter_ckpt": None, "adapter_w": 0.0,
        "cfg": 7.0, "steps": 24
    },
    {
        "idx": 7, "name": "soup_mean_base_w075",
        "base_model": "medium-base",
        "fullft_ckpt": f"{RUNS}/__fullft/fullft/fullft_soup_fp32cmp_avp_t4096_bs1_no35/soup_mean.ckpt",
        "fullft_w": 0.75,
        "adapter_ckpt": None, "adapter_w": 0.0,
        "cfg": 7.0, "steps": 24
    },
    {
        "idx": 8, "name": "soup_ep7_ep14_base_w100",
        "base_model": "medium-base",
        "fullft_ckpt": f"{RUNS}/__fullft/fullft/fullft_soup_fp32cmp_avp_t4096_bs1_no35/soup_ep7_ep14.ckpt",
        "fullft_w": 1.0,
        "adapter_ckpt": None, "adapter_w": 0.0,
        "cfg": 7.0, "steps": 24
    },
    {
        "idx": 9, "name": "fullft_ep80_fp32cmp_w100",
        "base_model": "medium-base",
        "fullft_ckpt": f"{RUNS}/__fullft/fullft_avp_t256/epoch=80-step=46944.weights.ckpt",
        "fullft_w": 1.0,
        "adapter_ckpt": f"{RUNS}/__precision_compare/fp32cmp_avp_t4096_bs4_lr1e4/epoch=28-step=14953.weights.ckpt",
        "adapter_w": 1.0,
        "cfg": 8.0, "steps": 24
    },
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
    return res * ((1.0 - t) * norm_v0 + t * norm_v1)

def blend_param(p_base: torch.Tensor, p_ft: torch.Tensor, w: float) -> torch.Tensor:
    if w == 1.0:
        return p_ft.clone()
    elif w < 1.0:
        return slerp_tensor(p_base, p_ft, w)
    else:
        norm_ft = torch.norm(p_ft)
        v = p_base + w * (p_ft - p_base)
        norm_v = torch.norm(v)
        if norm_v < 1e-8:
            return v
        return (v / norm_v) * norm_ft

def extract_steady_crop(audio, sr):
    mono = audio.mean(axis=0)
    hop = int(0.25 * sr)
    rms = [np.sqrt(np.mean(mono[i:i+hop]**2)) for i in range(0, len(mono)-hop, hop)]
    times = [i / sr for i in range(0, len(mono)-hop, hop)]
    mid_rms = np.median([r for t, r in zip(times, rms) if 4.0 <= t <= 20.0])
    
    fadeout_time = audio.shape[-1] / sr
    for t, r in zip(times, rms):
        if t > 18.0 and r < 0.65 * mid_rms:
            fadeout_time = t
            break
            
    db = np.array(madmom_downbeats(audio, sr))
    valid_starts = [t for t in db if t >= 1.5]
    start_t = valid_starts[0] if valid_starts else db[0]
    start_idx = np.where(db == start_t)[0][0]
    
    valid_ends = [db[i] for i in range(start_idx + 4, len(db), 4) if db[i] < (fadeout_time - 0.2)]
    if valid_ends:
        end_t = valid_ends[-1]
    else:
        earlier = [t for t in db if start_t + 5.0 <= t < (fadeout_time - 0.2)]
        end_t = earlier[-1] if earlier else (fadeout_time - 0.5)
        
    s_samp = find_zero_crossing_backwards(mono, int(start_t * sr), search_window=int(0.05 * sr))
    e_samp = find_zero_crossing_backwards(mono, int(end_t * sr), search_window=int(0.05 * sr))
    
    crop = audio[:, s_samp:e_samp]
    dur = crop.shape[-1] / sr
    print(f"  [steady_crop] Extracted {dur:.2f}s ({s_samp/sr:.2f}s -> {e_samp/sr:.2f}s, div4 bars), fadeout was at {fadeout_time:.2f}s")
    return crop, dur

def save_preset(preset_name, payload):
    p_path = f"{PRESET_DIR}/{preset_name}.json"
    os.makedirs(os.path.dirname(p_path), exist_ok=True)
    with open(p_path, "w") as f:
        json.dump({"schema": 1, "name": preset_name, "created": time.time(), "payload": payload}, f, indent=2)
    return p_path

def render_v3_track(model, p_info, cfg_meta):
    prompt_orig = p_info["prompt"]
    prompt_hw = p_info["prompt_enriched"]
    seed = p_info["seed"]
    cfg = cfg_meta["cfg"]
    steps = cfg_meta["steps"]
    is_asym = p_info.get("asymmetric", False)
    
    # Step 1: Generate initial 30s core
    print(f"  -> Rendering initial 30s core (seed={seed})...", flush=True)
    t0 = time.time()
    out = model.generate(prompt=prompt_orig, duration=CORE_TARGET_SEC, steps=steps, cfg_scale=cfg, seed=seed, batch_size=1)
    core_raw = out[0].float().cpu().numpy()
    core_time = time.time() - t0
    
    # Step 2: Extract steady beat crop (discard tail fadeout)
    crop, crop_dur = extract_steady_crop(core_raw, SR)
    
    # Step 3: Determine extension lengths
    rem_dur = max(20.0, TOTAL_TARGET_SEC - crop_dur)
    nom_pre = rem_dur / 2.0
    nom_post = rem_dur - nom_pre
    
    if is_asym:
        # 20% less preceding, 15% more latter
        d_pre = nom_pre * 0.80
        d_post = nom_post * 1.15
        print(f"  [asymmetric_split] 20% onset rule applied: pre={d_pre:.2f}s (-20%), post={d_post:.2f}s (+15%)")
    else:
        d_pre = nom_pre
        d_post = nom_post
        
    versions = [
        {"mode": "same", "ext_prompt": prompt_orig, "suffix": "ext_same"},
        {"mode": "hw", "ext_prompt": prompt_hw, "suffix": "ext_hw"}
    ]
    
    results = {"crop": crop, "crop_dur": crop_dur, "core_time": core_time, "extensions": []}
    
    for ver in versions:
        mode = ver["mode"]
        ext_prompt = ver["ext_prompt"]
        suffix = ver["suffix"]
        track_id = f"t{p_info['pid'][1:]}_{cfg_meta['name']}_{suffix}"
        
        print(f"  -> Outpainting [{suffix}] (mode: {mode}): Pass 1 (forward {d_post:.1f}s)...", flush=True)
        t_start = time.time()
        
        # Pass 1: Latter outpaint (forward continuation)
        W1 = crop_dur + d_post
        z1 = np.zeros((crop.shape[0], int(W1 * SR)), dtype=np.float32)
        z1[:, :crop.shape[-1]] = crop
        
        out_fwd = model.generate(prompt=ext_prompt, duration=W1, steps=steps, cfg_scale=cfg, seed=seed + 1,
                                 inpaint_audio=(SR, torch.tensor(z1)),
                                 inpaint_mask_start_seconds=crop_dur, inpaint_mask_end_seconds=W1,
                                 batch_size=1)
        fwd = out_fwd[0].float().cpu().numpy()
        fwd = np.pad(fwd, ((0, 0), (0, max(0, int(W1 * SR) - fwd.shape[-1]))))[:, :int(W1 * SR)]
        
        # Pass 2: Preceding outpaint (backward lead-in)
        print(f"  -> Outpainting [{suffix}]: Pass 2 (backward {d_pre:.1f}s)...", flush=True)
        offset = int(d_pre * SR)
        total_samples = offset + fwd.shape[-1]
        W2 = total_samples / SR
        z2 = np.zeros((crop.shape[0], total_samples), dtype=np.float32)
        z2[:, offset:offset + fwd.shape[-1]] = fwd
        
        out_full = model.generate(prompt=ext_prompt, duration=W2, steps=steps, cfg_scale=cfg, seed=seed + 2,
                                  inpaint_audio=(SR, torch.tensor(z2)),
                                  inpaint_mask_start_seconds=0.0, inpaint_mask_end_seconds=d_pre,
                                  batch_size=1)
        full = out_full[0].float().cpu().numpy()
        full = np.pad(full, ((0, 0), (0, max(0, total_samples - full.shape[-1]))))[:, :total_samples]
        ext_time = time.time() - t_start
        
        # Save output wav
        out_wav = f"{OUT}/{track_id}.wav"
        save_audio(out_wav, torch.tensor(full), SR)
        
        # Save preset
        preset_payload = {
            "prompt_core": prompt_orig,
            "prompt_ext": ext_prompt,
            "seed": seed,
            "cfg_scale": cfg,
            "steps": steps,
            "duration": round(full.shape[-1] / SR, 2),
            "model_config": cfg_meta["name"],
            "fullft_ckpt": cfg_meta["fullft_ckpt"],
            "fullft_w": cfg_meta["fullft_w"],
            "adapter_ckpt": cfg_meta["adapter_ckpt"],
            "adapter_w": cfg_meta["adapter_w"],
            "mode": mode,
            "asymmetric": is_asym,
            "d_pre": round(d_pre, 2),
            "d_post": round(d_post, 2),
            "crop_dur": round(crop_dur, 2)
        }
        preset_path = save_preset(f"mixtape_v3/{track_id}", preset_payload)
        
        rms_total = float(20 * np.log10(np.sqrt((full ** 2).mean()) + 1e-12))
        peak = float(np.abs(full).max())
        
        rec = {
            "id": track_id,
            "pid": p_info["pid"],
            "prompt_core": prompt_orig,
            "prompt_ext": ext_prompt,
            "mode": mode,
            "seed": seed,
            "model_name": cfg_meta["name"],
            "fullft_w": cfg_meta["fullft_w"],
            "adapter_w": cfg_meta["adapter_w"],
            "cfg": cfg,
            "steps": steps,
            "dur": round(full.shape[-1] / SR, 2),
            "crop_dur": round(crop_dur, 2),
            "d_pre": round(d_pre, 2),
            "d_post": round(d_post, 2),
            "asymmetric": is_asym,
            "rms_db": round(rms_total, 2),
            "peak": round(peak, 3),
            "preset": preset_path,
            "render_sec": round(ext_time, 1)
        }
        results["extensions"].append(rec)
        print(f"  [SAVED] {track_id}.wav ({rec['dur']}s) | RMS: {rms_total:.1f} dB, Peak: {peak:.3f} in {ext_time:.1f}s", flush=True)
        
    return results

def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(PRESET_DIR, exist_ok=True)
    manifest_path = f"{OUT}/cells.jsonl"
    
    done_ids = set()
    if os.path.exists(manifest_path):
        for line in open(manifest_path):
            try:
                done_ids.add(json.loads(line)["id"])
            except Exception:
                pass
                
    print(f"=== Starting Mixtape Track Pool V3 ===")
    print(f"Manifest: {manifest_path}, existing records: {len(done_ids)}")
    
    # Iterate through the 10 prompt/model configurations
    for i in range(10):
        p_info = PROMPTS_V3[i]
        cfg_meta = TRACK_CONFIGS[i]
        
        id_same = f"t{p_info['pid'][1:]}_{cfg_meta['name']}_ext_same"
        id_hw = f"t{p_info['pid'][1:]}_{cfg_meta['name']}_ext_hw"
        
        if id_same in done_ids and id_hw in done_ids:
            print(f"\n[SKIP] Prompt {p_info['pid']} ({cfg_meta['name']}) already fully rendered.")
            continue
            
        print(f"\n=======================================================", flush=True)
        print(f"Rendering Prompt {p_info['pid']}: {cfg_meta['name']}", flush=True)
        print(f"Prompt: {p_info['prompt']}", flush=True)
        print(f"Enriched: {p_info['prompt_enriched']}", flush=True)
        print(f"=======================================================", flush=True)
        
        # Load model and configure weights
        model = StableAudioModel.from_pretrained(cfg_meta["base_model"], device="cuda")
        
        # 1. Full-FT load & blend if needed
        base_params = {}
        ft_params = {}
        if cfg_meta["fullft_ckpt"]:
            tgt = model.model.model
            base_params = {k: v.detach().cpu().clone() for k, v in tgt.named_parameters()}
            sd = _state_dict(cfg_meta["fullft_ckpt"])
            ei = ema_info(sd)
            use_ema = bool(ei and ei["converged"])
            load_fullft(model, cfg_meta["fullft_ckpt"], weights="ema" if use_ema else "online", sd=sd)
            ft_params = {k: v.detach().cpu().clone() for k, v in tgt.named_parameters()}
            del sd
            
            # Blend if fullft_w != 1.0
            w = cfg_meta["fullft_w"]
            if w != 1.0:
                with torch.no_grad():
                    for k, p in model.model.model.named_parameters():
                        blended = blend_param(base_params[k], ft_params[k], w)
                        p.copy_(blended.to(device="cuda", dtype=p.dtype))
                        
        # 2. Adapter stack if present
        if cfg_meta["adapter_ckpt"]:
            model.load_lora([cfg_meta["adapter_ckpt"]])
            model.set_lora_strength(cfg_meta["adapter_w"])
            print(f"  [adapter] Stacked {cfg_meta['adapter_ckpt']} at strength {cfg_meta['adapter_w']}", flush=True)
            
        res = render_v3_track(model, p_info, cfg_meta)
        
        # Also save the steady core loop for reference
        core_id = f"t{p_info['pid'][1:]}_{cfg_meta['name']}_core"
        save_audio(f"{OUT}/{core_id}.wav", torch.tensor(res["crop"]), SR)
        
        with open(manifest_path, "a") as f:
            for rec in res["extensions"]:
                f.write(json.dumps(rec) + "\n")
                
        # Clean up model
        del model, base_params, ft_params
        import gc
        gc.collect()
        torch.cuda.empty_cache()
        
    print("\nALL V3 JOBS FINISHED SUCCESSFULLY!", flush=True)
    os._exit(0)

if __name__ == "__main__":
    main()
