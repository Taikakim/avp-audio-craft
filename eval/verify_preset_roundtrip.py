#!/usr/bin/env python3
"""verify_preset_roundtrip.py -- verify that loading a preset reproduces identical audio.

Loads a generated preset JSON (e.g. t00-soup-mean-base-w100.json),
re-runs generate_80s with the preset parameters, applies the exact PCM-16 save_audio
pipeline, and verifies that the output audio matches the rendered WAV on disk bit-for-bit or within 16-bit quantization.
"""
import json, os, sys, time
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")

import numpy as np, soundfile as sf, torch
sys.path.insert(0, "/home/kim/Projects/SAO/eval")
sys.path.insert(0, "/home/kim/Projects/SAO/control")
sys.path.insert(0, "/home/kim/Projects/SAO/stable-audio-3")
from forge.fullft import load_fullft, _state_dict, ema_info
from stable_audio_3 import StableAudioModel
from mixtape_track_pool_v2 import generate_80s, blend_param

def verify_preset(preset_path, wav_path):
    print(f"Loading preset: {preset_path}", flush=True)
    with open(preset_path) as f:
        data = json.load(f)
    payload = data["payload"]
    prompt = payload["prompt"]
    seed = payload["seed"]
    cfg_scale = payload["cfg_scale"]
    steps = payload["steps"]
    backend = payload["model_variant"]
    ckpt = payload["checkpoint"]
    weight = payload["weight"]
    kind = payload["kind"]

    print(f"Backend: {backend}, Model kind: {kind}, Weight: {weight}, Seed: {seed}", flush=True)
    model_name = "medium-base" if backend == "base" else "medium"
    model = StableAudioModel.from_pretrained(model_name, device="cuda")

    if kind == "fullft":
        tgt = model.model.model
        base_params = {k: v.detach().cpu().clone() for k, v in tgt.named_parameters()}
        sd = _state_dict(ckpt)
        ei = ema_info(sd)
        use_ema = bool(ei and ei["converged"])
        load_fullft(model, ckpt, weights="ema" if use_ema else "online", sd=sd)
        ft_params = {k: v.detach().cpu().clone() for k, v in tgt.named_parameters()}
        del sd
        with torch.no_grad():
            for k, p in model.model.model.named_parameters():
                blended = blend_param(base_params[k], ft_params[k], weight)
                p.copy_(blended.to(device="cuda", dtype=p.dtype))
    else:
        model.load_lora([ckpt])
        model.set_lora_strength(weight)

    print("Generating audio via generate_80s...", flush=True)
    t0 = time.time()
    gen_audio = generate_80s(model, prompt, seed, cfg_scale, steps)
    elapsed = time.time() - t0
    print(f"Generation took {elapsed:.1f}s", flush=True)

    # Process gen_audio matching save_audio pipeline
    a = torch.tensor(gen_audio, dtype=torch.float32)
    peak = torch.max(torch.abs(a))
    if peak > 1e-6:
        a = a / peak * 0.8913
    a = a.clamp(-1.0, 1.0)
    # Quantize to 16-bit PCM as written to disk
    gen_pcm16 = (a.numpy() * 32767.0).round().astype(np.int16)

    ref_audio, sr = sf.read(wav_path, dtype="int16")
    ref_pcm16 = ref_audio.T # (channels, samples)
    
    # Compare
    min_len = min(gen_pcm16.shape[-1], ref_pcm16.shape[-1])
    diff = np.abs(gen_pcm16[:, :min_len] - ref_pcm16[:, :min_len])
    max_pcm_diff = int(diff.max())
    exact_matches = int((diff == 0).sum())
    total_samples = diff.size
    pct_exact = 100.0 * exact_matches / total_samples

    print(f"Comparison with reference {wav_path}:", flush=True)
    print(f"  Exact bit matches: {exact_matches}/{total_samples} ({pct_exact:.2f}%)", flush=True)
    print(f"  Max PCM-16 difference: {max_pcm_diff} LSB (out of 32768)", flush=True)

    # In 16-bit audio, 0 or 1 LSB difference is bit-perfect down to rounding
    is_match = max_pcm_diff <= 1
    print(f"  VERDICT: {'PASS - Roundtrip verified identical' if is_match else 'FAIL - Mismatch'}", flush=True)
    return is_match

if __name__ == "__main__":
    preset = sys.argv[1] if len(sys.argv) > 1 else "/home/kim/Projects/SAO/eval/presets/mixtape_v2_10prompts/t00-soup-mean-base-w100.json"
    wav = sys.argv[2] if len(sys.argv) > 2 else "/run/media/kim/Mantu/sa3_lora_runs/mixtape_trackpool_v2/t00_soup_mean_base_w100.wav"
    try:
        ok = verify_preset(preset, wav)
    finally:
        # Use os._exit to bypass ROCm libc teardown crash
        os._exit(0 if ok else 1)
