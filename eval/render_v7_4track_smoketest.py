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

def safe_slice(audio, start_idx, end_idx):
    """Slice audio and zero-pad if it goes out of bounds."""
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
    y = librosa.to_mono(audio)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=4096)
    return torch.tensor(chroma).unsqueeze(0)

def main():
    print("Starting V7 4-Track Smoke Test Pipeline (Fast Native Mode)...")
    
    order_path = Path("/run/media/kim/Mantu/sa3_lora_runs/mixtape_v7_phase0/order_used.json")
    clips = json.loads(order_path.read_text())[2:6]
    bounds = json.loads(Path("/tmp/bounds_structural.json").read_text())
    
    print("Loading pre-computed stems...")
    stems = {}
    NAMES = ["drums", "bass", "other", "vocals"]
    
    for c in clips:
        # Get the pre-computed stem index by matching the id
        # Wait, how do I know which index (00, 01, 02) matches this clip?
        # order_used.json is the exact order, so clip at index `clips` corresponds to transition stems!
        # Actually, let's just search through the stems directory to find the matching id in `run_meta.json`.
        pass
        
