import json
import os
import sys
from pathlib import Path
import numpy as np
import librosa
from scipy.signal import find_peaks

# Insert SAO paths
sys.path.insert(0, "/home/kim/Projects/SAO/eval")
sys.path.insert(0, "/home/kim/Projects/SAO/control")
from structure_ssm import ssm_from_chroma, _checkerboard, HZ, KERN
from chain_dj_overlay import outpaint_forward, BRIDGE_CKPT
from stable_audio_3 import StableAudioModel

def get_structural_peaks(audio_path, sr=22050):
    y, _ = librosa.load(str(audio_path), sr=sr, mono=True)
    hop = int(sr / HZ)
    C = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop).T
    S = ssm_from_chroma(C)
    n = S.shape[0]
    g = _checkerboard(KERN)
    nov = np.zeros(n)
    for i in range(KERN, n - KERN):
        nov[i] = float((S[i - KERN:i + KERN, i - KERN:i + KERN] * g).sum())
    nov = np.clip(nov, 0, None)
    if nov.max() > 0:
        nov /= nov.max()
    peaks, _ = find_peaks(nov, height=0.20, distance=int(HZ * 8))
    peak_times = peaks / HZ
    return peak_times, len(y)/sr

def main():
    print("Starting DJ mix v7 Phase 0 script...")
