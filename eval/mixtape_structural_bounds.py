import json
import sys
from pathlib import Path
import numpy as np
from scipy.signal import find_peaks

sys.path.insert(0, "/home/kim/Projects/SAO/eval")
sys.path.insert(0, "/home/kim/Projects/SAO/control")
import librosa
from structure_ssm import ssm_from_chroma, _checkerboard, HZ, KERN

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
    
    peaks, _ = find_peaks(nov, height=0.20, distance=int(HZ * 8)) # >=8 s apart
    peak_times = peaks / HZ
    return peak_times, len(y)/sr

def main():
    phase0_dir = Path("/run/media/kim/Mantu/sa3_lora_runs/mixtape_v7_phase0")
    order_path = phase0_dir / "order_used.json"
    db_path = phase0_dir / "downbeats_native.json"
    
    clips = json.loads(order_path.read_text())
    downbeats = json.loads(db_path.read_text())
    
    out_path = Path("/tmp/bounds_structural.json")
    
    W = 9 # Window size in bars
    W_half = W // 2 # 4 bars before, 5 bars after (or vice versa)
    
    results = {}
    
    for i, c in enumerate(clips):
        key = c["id"]
        wav_path = Path(c["path"])
        if not wav_path.exists():
            continue
            
        print(f"Processing {i+1}/{len(clips)}: {key}")
        peaks, duration = get_structural_peaks(wav_path)
        db = np.array(downbeats[key])
        
        # INCOMING (Track B): Start W_half bars before an early peak
        in_start = None
        for p in peaks:
            db_idx = np.argmin(np.abs(db - p))
            if db_idx >= W_half and (db_idx + W - W_half) < len(db):
                in_start = float(db[db_idx - W_half])
                break
        if in_start is None:
            in_start = float(db[0])
            
        # OUTGOING (Track A): End W - W_half bars after a late peak
        lo_t = duration * 0.70
        hi_t = duration * 0.95
        out_end = None
        valid_peaks = [p for p in peaks if lo_t <= p <= hi_t]
        if valid_peaks:
            p = valid_peaks[-1]
            db_idx = np.argmin(np.abs(db - p))
            if (db_idx + (W - W_half)) < len(db) and db_idx >= W_half:
                out_end = float(db[db_idx + (W - W_half)])
                
        if out_end is None:
            t_fb = duration * 0.85
            db_idx = np.argmin(np.abs(db - t_fb))
            if db_idx + (W - W_half) < len(db):
                out_end = float(db[db_idx + (W - W_half)])
            else:
                out_end = float(db[-1])
            
        results[key] = {
            "start": in_start,
            "end": out_end,
            "end_pre_zc": out_end,
            "duration": duration,
        }
        
    out_path.write_text(json.dumps(results, indent=2))
    print(f"Wrote {len(results)} bounds to {out_path}")

if __name__ == "__main__":
    main()
