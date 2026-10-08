#!/usr/bin/env python
import json
import os
import torch
import soundfile as sf
import numpy as np
from pathlib import Path
from scipy.signal import butter, sosfilt
import sys

sys.path.insert(0, "/home/kim/Projects/SAO/eval")
sys.path.insert(0, "/home/kim/Projects/mir-same-chroma/src")
from stable_audio_3 import StableAudioModel
from mixtape_v7_generative_inference import dual_latch_guided_generate
from harmonic.same_chroma import compute_same_chroma

def lr4_sos(fc, kind):
    return butter(4, fc, btype=kind, fs=44100, output='sos')

def lr4_filter(audio, fc, kind):
    sos = lr4_sos(fc, kind)
    if audio.ndim == 1:
        return sosfilt(sos, audio)
    else:
        return np.vstack([sosfilt(sos, audio[0]), sosfilt(sos, audio[1])])

def safe_slice(audio, start_idx, end_idx):
    length = end_idx - start_idx
    channels = audio.shape[0]
    out = np.zeros((channels, length), dtype=audio.dtype)
    src_start = max(0, start_idx)
    src_end = min(audio.shape[1], end_idx)
    dst_start = max(0, -start_idx)
    dst_end = dst_start + (src_end - src_start)
    if src_start < src_end:
        out[:, dst_start:dst_end] = audio[:, src_start:src_end]
    return out

def get_chroma(audio, sr):
    c = compute_same_chroma(audio.T, sr).reshape(384, -1)
    return torch.tensor(c).unsqueeze(0)

def main():
    print("Starting V7 4-Track Smoke Test Pipeline (Full SAO Native Demucs Version)...")
    
    order_path = Path("/run/media/kim/Mantu/sa3_lora_runs/mixtape_v7_phase0/order_used.json")
    all_clips = json.loads(order_path.read_text())
    clips = all_clips[1:5]
    bounds = json.loads(Path("/tmp/bounds_structural.json").read_text())
    
    stems_out_dir = "/tmp/v7_smoke_stems_NATIVE"
    os.makedirs(stems_out_dir, exist_ok=True)
    
    print("Running Demucs natively in SAO venv...")
    stems = {}
    NAMES = ["drums", "bass", "other", "vocals"]
    
    from demucs.apply import apply_model
    from demucs.pretrained import get_model
    demucs_model = get_model("htdemucs_ft").cuda().eval()
    
    for c in clips:
        tmp_path = f"/run/media/kim/Mantu/sa3_lora_runs/mixtape_v7_phase0/tmp_{c['id']}.wav"
        x, sr = sf.read(tmp_path, dtype="float32")
        
        w = torch.from_numpy(x.T).cuda()
        ref = w.mean(0)
        wn = (w - ref.mean()) / (ref.std() + 1e-8)
        
        print(f"Demucsing {c['id']}...")
        with torch.no_grad():
            y = apply_model(demucs_model, wn[None], device="cuda", split=True, overlap=0.25)[0]
        y = (y * (ref.std() + 1e-8) + ref.mean()).cpu().numpy()
        
        c_stems = {n: y[demucs_model.sources.index(n)] for n in NAMES}
        stems[c['id']] = c_stems

    del demucs_model
    torch.cuda.empty_cache()

    print("Initializing SA3 Model...")
    sa3_model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    
    W_bars = 9
    SR = 44100
    
    for i in range(len(clips) - 1):
        cA = clips[i]
        cB = clips[i+1]
        print(f"Processing Transition {i+1}: {cA['id']} -> {cB['id']}")
        
        bA = bounds[cA['id']]
        bB = bounds[cB['id']]
        W_sec = W_bars * 4 * 60 / cA.get("bpm", 140)
        
        L = int(W_sec * SR)
        A_start_idx = int((bA["end_pre_zc"] - W_sec/2) * SR)
        A_end_idx = A_start_idx + L
        B_start_idx = int((bB["start"] - W_sec/2) * SR)
        B_end_idx = B_start_idx + L
        
        sA = stems[cA['id']]
        sB = stems[cB['id']]
        
        ramp_up = np.linspace(0, 1, L)
        ramp_down = np.linspace(1, 0, L)
        
        h_idx = L // 2
        fade_len = int(SR * 0.1)
        bass_out = np.zeros((2, L))
        
        bass_A_sliced = safe_slice(sA["bass"], A_start_idx, A_end_idx)
        bass_B_sliced = safe_slice(sB["bass"], B_start_idx, B_end_idx)
        
        bass_out[:, :h_idx - fade_len//2] = bass_A_sliced[:, :h_idx - fade_len//2]
        bass_out[:, h_idx - fade_len//2 : h_idx + fade_len//2] = bass_A_sliced[:, h_idx - fade_len//2 : h_idx + fade_len//2] * np.linspace(1, 0, fade_len)
        bass_out[:, h_idx:] += bass_B_sliced[:, h_idx:] * np.sin(np.linspace(0, np.pi/2, L - h_idx))
        
        drums_A_sliced = safe_slice(sA["drums"], A_start_idx, A_end_idx)
        drums_B_sliced = safe_slice(sB["drums"], B_start_idx, B_end_idx)
        
        drums_A_low = lr4_filter(drums_A_sliced, 800.0, "low")
        drums_B_low = lr4_filter(drums_B_sliced, 800.0, "low")
        drums_A_high = lr4_filter(drums_A_sliced, 800.0, "high")
        drums_B_high = lr4_filter(drums_B_sliced, 800.0, "high")
        
        drums_out_low = drums_A_low * ramp_down + drums_B_low * ramp_up
        drums_out_high = drums_A_high * ramp_down + drums_B_high * ramp_up
        drums_out = drums_out_low + drums_out_high
        
        other_A_sliced = safe_slice(sA["other"], A_start_idx, A_end_idx)
        other_B_sliced = safe_slice(sB["other"], B_start_idx, B_end_idx)
        
        print("Extracting Chroma Targets...")
        chroma_A = get_chroma(other_A_sliced, SR)
        chroma_B = get_chroma(other_B_sliced, SR)
        
        chroma_len = chroma_A.shape[-1]
        ramp_up_chroma = torch.linspace(0, 1, chroma_len)
        ramp_down_chroma = torch.linspace(1, 0, chroma_len)
        chroma_target = (chroma_A * ramp_down_chroma.unsqueeze(0).unsqueeze(0) + chroma_B * ramp_up_chroma.unsqueeze(0).unsqueeze(0)).float()
        
        ckpt_a = "/run/media/kim/Mantu/sa3_lora_runs/dora128adj_avp_8ep_final/epoch=0-step=299.weights.ckpt"
        ckpt_b = "/run/media/kim/Mantu/sa3_lora_runs/dora16_avp_familiarity_8ep/epoch=4-step=1495.weights.ckpt"
        
        print("Running LatCH + Dual-LoRA Inference...")
        try:
            other_out, _ = dual_latch_guided_generate(
                model=sa3_model,
                ckpt_a=ckpt_a,
                ckpt_b=ckpt_b,
                prompt_a="aggressive upbeat goa trance",
                prompt_b="driving pulsating psytrance",
                duration=W_sec,
                chroma_target_tensor=chroma_target,
                chroma_head_path="/run/media/kim/Mantu/sa3_lora_runs/cu_reward_renders/analysis/chroma_heads/latch_sa3_chroma_other_best.pt"
            )
            other_out = other_out.numpy()
            if other_out.shape[-1] < L:
                other_out = np.pad(other_out, ((0,0), (0, L - other_out.shape[-1])))
            else:
                other_out = other_out[:, :L]
        except Exception as e:
            print(f"Generative inference failed, falling back to crossfade: {e}")
            other_out = other_A_sliced * ramp_down + other_B_sliced * ramp_up
            
        trans_out = bass_out + drums_out + other_out
        
        sf.write(f"/home/kim/staging/kone-mixtape/smoke/v7_smoke_trans_FINAL_{i}.wav", trans_out.T, SR)
        
    print("Done! Transitions saved to /home/kim/staging/kone-mixtape/smoke/")

if __name__ == "__main__":
    main()
