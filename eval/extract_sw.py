import sys
sys.path.insert(0, "/home/kim/Projects/mir/src")
import json
import numpy as np
import soundfile as sf
import torch
from pathlib import Path
from preprocessing.bs_roformer_sep import load_audio, load_bs_roformer, separate_audio

NAMES = ["drums", "bass", "other", "vocals"]

def main():
    order_path = Path("/run/media/kim/Mantu/sa3_lora_runs/mixtape_v7_phase0/order_used.json")
    all_clips = json.loads(order_path.read_text())
    clips = all_clips[1:5]
    
    out_dir = Path("/tmp/v7_smoke_stems_SW")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    sep, mc, ac, ic = load_bs_roformer("jarredou-BS-ROFO-SW-Fixed-drums", "/home/kim/Projects/mir/models/bs-roformer", "cuda")
    inst = list(mc.instruments) if mc.instruments else ["bass", "drums", "other", "vocals", "guitar", "piano"]
    
    for c in clips:
        stem_dir = out_dir / c['id']
        if stem_dir.exists():
            continue
        stem_dir.mkdir(parents=True, exist_ok=True)
        
        p = f"/run/media/kim/Mantu/sa3_lora_runs/mixtape_v7_phase0/tmp_{c['id']}.wav"
        print(f"BS-Roformer extracting: {c['id']}")
        
        audio, sr = load_audio(p, ac.sample_rate)
        g = 0.9 / max(float(np.abs(audio).max()), 1e-8)
        y = separate_audio(sep, (audio * g).astype(np.float32), ac, mc, ic, torch.device("cuda")) / g
        
        st = {n: y[inst.index(n)] for n in NAMES}
        st["other"] = st["other"] + sum(y[inst.index(n)] for n in inst if n not in NAMES)
        
        for n in NAMES:
            sf.write(str(stem_dir / f"{n}.wav"), st[n], int(sr), subtype="FLOAT")
            
if __name__ == "__main__":
    main()
