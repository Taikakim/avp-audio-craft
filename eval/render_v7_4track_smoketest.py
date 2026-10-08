#!/usr/bin/env python
import json
import os
import torch
import soundfile as sf
import numpy as np
from pathlib import Path
from scipy.signal import butter, sosfilt
import librosa
import sys
import subprocess
import shutil

sys.path.insert(0, "/home/kim/Projects/SAO/eval")
from stable_audio_3 import StableAudioModel
from mixtape_v7_generative_inference import dual_latch_guided_generate

def lr4_sos(fc, kind):
    return butter(4, fc, btype=kind, fs=44100, output='sos')

def lr4_filter(audio, fc, kind):
    sos = lr4_sos(fc, kind)
    if audio.ndim == 1:
        return sosfilt(sos, audio)
    else:
        return np.vstack([sosfilt(sos, audio[0]), sosfilt(sos, audio[1])])

def get_chroma(audio, sr):
    y = librosa.to_mono(audio)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=4096)
    return torch.tensor(chroma).unsqueeze(0)

def demucs_clip(wav_path, out_dir):
    # Call demucs via mir venv
    cmd = [
        "/home/kim/Projects/mir/.venv/bin/python", "-m", "demucs.separate",
        "-n", "htdemucs_ft",
        "--out", out_dir,
        wav_path
    ]
    subprocess.run(cmd, check=True)

def main():
    print("Starting V7 4-Track Smoke Test Pipeline...")
    
    order_path = Path("/run/media/kim/Mantu/sa3_lora_runs/mixtape_v7_phase0/order_used.json")
    clips = json.loads(order_path.read_text())[2:6]
    bounds = json.loads(Path("/tmp/bounds_structural.json").read_text())
    
    stems_out_dir = "/tmp/v7_smoke_stems"
    os.makedirs(stems_out_dir, exist_ok=True)
    
    print("Running Demucs on 4 outpainted tracks via subprocess...")
    stems = {}
    NAMES = ["drums", "bass", "other", "vocals"]
    
    for c in clips:
        tmp_path = f"/run/media/kim/Mantu/sa3_lora_runs/mixtape_v7_phase0/tmp_{c['id']}.wav"
        
        # Check if already demucsed in tmp
        stem_dir = Path(stems_out_dir) / "htdemucs_ft" / Path(tmp_path).stem
        if not stem_dir.exists():
            print(f"Demucsing {c['id']}...")
            demucs_clip(tmp_path, stems_out_dir)
            
        # Load stems
        c_stems = {}
        for n in NAMES:
            x, sr = sf.read(str(stem_dir / f"{n}.wav"), dtype="float32")
            c_stems[n] = x.T
        stems[c['id']] = c_stems

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
        
        A_start_idx = int((bA["end_pre_zc"] - W_sec/2) * SR)
        A_end_idx = int((bA["end_pre_zc"] + W_sec/2) * SR)
        B_start_idx = int((bB["start"] - W_sec/2) * SR)
        B_end_idx = int((bB["start"] + W_sec/2) * SR)
        
        sA = stems[cA['id']]
        sB = stems[cB['id']]
        
        L = A_end_idx - A_start_idx
        
        ramp_up = np.linspace(0, 1, L)
        ramp_down = np.linspace(1, 0, L)
        
        h_idx = L // 2
        fade_len = int(SR * 0.1)
        bass_out = np.zeros((2, L))
        bass_out[:, :h_idx - fade_len//2] = sA["bass"][:, A_start_idx:A_start_idx + h_idx - fade_len//2]
        bass_out[:, h_idx - fade_len//2 : h_idx + fade_len//2] = sA["bass"][:, A_start_idx + h_idx - fade_len//2 : A_start_idx + h_idx + fade_len//2] * np.linspace(1, 0, fade_len)
        bass_out[:, h_idx:] += sB["bass"][:, B_start_idx + h_idx:B_end_idx] * np.sin(np.linspace(0, np.pi/2, L - h_idx))
        
        drums_A = sA["drums"][:, A_start_idx:A_end_idx]
        drums_B = sB["drums"][:, B_start_idx:B_end_idx]
        drums_A_low = lr4_filter(drums_A, 800.0, "low")
        drums_B_low = lr4_filter(drums_B, 800.0, "low")
        drums_A_high = lr4_filter(drums_A, 800.0, "high")
        drums_B_high = lr4_filter(drums_B, 800.0, "high")
        
        drums_out_low = drums_A_low * ramp_down + drums_B_low * ramp_up
        drums_out_high = drums_A_high * ramp_down + drums_B_high * ramp_up
        drums_out = drums_out_low + drums_out_high
        
        print("Extracting Chroma Targets...")
        chroma_A = get_chroma(sA["other"][:, A_start_idx:A_end_idx], SR)
        chroma_B = get_chroma(sB["other"][:, B_start_idx:B_end_idx], SR)
        chroma_target = (chroma_A * torch.tensor(ramp_down).unsqueeze(0).unsqueeze(0) + chroma_B * torch.tensor(ramp_up).unsqueeze(0).unsqueeze(0)).float()
        
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
        except Exception as e:
            print(f"Generative inference failed, falling back to crossfade: {e}")
            other_out = sA["other"][:, A_start_idx:A_end_idx] * ramp_down + sB["other"][:, B_start_idx:B_end_idx] * ramp_up
            
        trans_out = bass_out + drums_out + other_out
        
        sf.write(f"/home/kim/staging/kone-mixtape/smoke/v7_smoke_trans_FULL_{i}.wav", trans_out.T, SR)
        
    print("Done! Transitions saved to /home/kim/staging/kone-mixtape/smoke/")

if __name__ == "__main__":
    main()
