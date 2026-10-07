import json
import soundfile as sf
import numpy as np
from pathlib import Path
import librosa

def load(path):
    y, sr = librosa.load(str(path), sr=44100, mono=False)
    if y.ndim == 1:
        y = np.vstack([y, y])
    return y, sr

phase0_dir = Path("/run/media/kim/Mantu/sa3_lora_runs/mixtape_v7_phase0")
order_path = phase0_dir / "order_used.json"
clips = json.loads(order_path.read_text())[:5]

bounds = json.loads(Path("/tmp/bounds_structural.json").read_text())

SR = 44100
W_bars = 9

# We overlap-add them.
# Clip 0 plays from 0 to its 'end_pre_zc'.
# Clip 1 overlaps. Its 'start' aligns exactly W_bars * 4 beats BEFORE Clip 0's 'end_pre_zc' (which is the handover peak).
# Actually, the bounds are already computed.
# Clip i ends at bounds[i]['end_pre_zc'].
# The overlap duration is exactly W_bars. 
# Wait, bounds['start'] is the start of the OVERLAP window for the incoming clip!
# And bounds['end_pre_zc'] is the end of the OVERLAP window for the outgoing clip!

out_audio = np.zeros((2, SR * 600))
current_time = 0.0

for i, c in enumerate(clips):
    y, sr = load(c["path"])
    b = bounds[c["id"]]
    
    # Calculate the crossfade window length in samples
    # The window is from 'start' to 'start' + W_bars in the incoming clip.
    # But wait, we don't have the exact duration of W_bars in seconds here.
    # Let's just use the exact samples.
    # For clip 0, it just starts at 0.
    if i == 0:
        end_idx = int(b["end_pre_zc"] * SR)
        out_audio[:, :end_idx] = y[:, :end_idx]
        current_time = b["end_pre_zc"]
    else:
        # Incoming clip starts its overlap at 'start'.
        # The handover point H is in the middle of the window, or at the end.
        # Actually, in bounds_structural.json, 'start' is the start of the overlapping window.
        # So we align 'start' of clip i with (current_time - Window) of the master!
        # What is the window length?
        bpm = c.get("bpm", 140)
        W_sec = W_bars * 4 * 60 / bpm
        
        start_idx = int(b["start"] * SR)
        # End index is the NEXT clip's overlap start. If it's the last clip, play to the end.
        if i < len(clips) - 1:
            end_idx = int(bounds[clips[i+1]["id"]]["end_pre_zc"] * SR)
        else:
            end_idx = y.shape[1]
            
        clip_chunk = y[:, start_idx:end_idx]
        
        # Place it in out_audio
        place_idx = int((current_time - W_sec) * SR)
        
        # Crossfade the overlapping region (W_sec)
        overlap_samps = int(W_sec * SR)
        ramp_up = np.linspace(0, 1, overlap_samps)
        ramp_down = np.linspace(1, 0, overlap_samps)
        
        # Fade out the existing audio in the overlap region
        out_audio[:, place_idx:place_idx+overlap_samps] *= ramp_down
        
        # Fade in the new audio
        fade_in_chunk = clip_chunk[:, :overlap_samps] * ramp_up
        
        out_audio[:, place_idx:place_idx+overlap_samps] += fade_in_chunk
        
        # Place the rest of the chunk
        out_audio[:, place_idx+overlap_samps : place_idx+clip_chunk.shape[1]] = clip_chunk[:, overlap_samps:]
        
        current_time = (place_idx + clip_chunk.shape[1]) / SR

# Trim trailing zeros
nonzero = np.where(out_audio[0] != 0)[0]
out_audio = out_audio[:, :nonzero[-1]]

out_path = "/home/kim/staging/kone-mixtape/smoke/mini_mix_structural_test.wav"
sf.write(out_path, out_audio.T, SR)
print(f"Mini-mix written to {out_path}")

