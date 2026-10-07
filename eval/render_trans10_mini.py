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

# Transition 10 from mixtape_v7_phase0
# clip_A: fp32cmp_avp_t512_bs8_lr1e4_repr_ptm__ep7__cfg1__w100__rb_common_1__s225176290__st8
# clip_B: dora128adj_avp_8ep_final_ptm__ep0__cfg1__w100__rb_common_1__s225176290__st8
# Wait, let's look at order_used.json for the 10th transition
order_path = Path("/run/media/kim/Mantu/sa3_lora_runs/mixtape_v7_phase0/order_used.json")
clips = json.loads(order_path.read_text())
clip_A = clips[9]
clip_B = clips[10]

bounds = json.loads(Path("/tmp/bounds_structural.json").read_text())

SR = 44100
W_bars = 9

yA, srA = load(clip_A["path"])
yB, srB = load(clip_B["path"])

bA = bounds[clip_A["id"]]
bB = bounds[clip_B["id"]]

# A ends at bA['end_pre_zc']
# B starts at bB['start']
# Overlap is W_bars
W_sec = W_bars * 4 * 60 / clip_A.get("bpm", 140)

out_samps = int((bA["end_pre_zc"] + (yB.shape[1]/SR - bB["start"])) * SR)
out_audio = np.zeros((2, out_samps))

# Place A
a_end_idx = int(bA["end_pre_zc"] * SR)
out_audio[:, :a_end_idx] = yA[:, :a_end_idx]

# Place B
b_start_idx = int(bB["start"] * SR)
place_idx = int((bA["end_pre_zc"] - W_sec) * SR)

overlap_samps = int(W_sec * SR)
ramp_up = np.linspace(0, 1, overlap_samps)
ramp_down = np.linspace(1, 0, overlap_samps)

# Fade out A
out_audio[:, place_idx:place_idx+overlap_samps] *= ramp_down

# Fade in B
fade_in_chunk = yB[:, b_start_idx:b_start_idx+overlap_samps] * ramp_up
out_audio[:, place_idx:place_idx+overlap_samps] += fade_in_chunk

# Rest of B
out_audio[:, place_idx+overlap_samps : place_idx+yB.shape[1]-b_start_idx] = yB[:, b_start_idx+overlap_samps:]

# Trim
nonzero = np.where(out_audio[0] != 0)[0]
out_audio = out_audio[:, :nonzero[-1]]

out_path = "/home/kim/staging/kone-mixtape/smoke/trans10_structural_test.wav"
sf.write(out_path, out_audio.T, SR)
print(f"Trans 10 written to {out_path}")

