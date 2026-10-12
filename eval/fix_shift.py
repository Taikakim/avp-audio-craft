# Owner: unconfirmed (found untracked 2026-10-12; written 2026-10-08, kone-mixtape v7 debugging)
# One-off: cross-correlate two adjacent mixtape_v7_phase0 clips to find their beat offset.
import json
import numpy as np
import soundfile as sf
from scipy.signal import correlate, find_peaks

with open('/run/media/kim/Mantu/sa3_lora_runs/mixtape_v7_phase0/order_used.json') as f:
    order = json.load(f)
with open('/run/media/kim/Mantu/sa3_lora_runs/mixtape_v7_phase0/run_meta.json') as f:
    meta = json.load(f)

k = 10
path1 = order[k]['path']
path2 = order[k+1]['path']

def load_and_onset(path):
    wav, sr = sf.read(path)
    wav = wav.mean(axis=1)
    wav = np.abs(wav)
    rem = len(wav) % 100
    if rem > 0:
        wav = wav[:-rem]
    wav = wav.reshape(-1, 100).mean(axis=1)
    return wav

env1 = load_and_onset(path1)
env2 = load_and_onset(path2)

env1_end = env1[-441*15:]
env2_start = env2[:441*15]

corr = correlate(env1_end, env2_start, mode='full')
peaks, _ = find_peaks(corr, distance=441*0.3) # peaks separated by at least 0.3s
# Sort peaks by correlation value
peaks = sorted(peaks, key=lambda p: corr[p], reverse=True)

print("Top 5 shifts:")
for p in peaks[:5]:
    lag = p - len(env2_start) + 1
    shift = lag * 100
    print(f"Shift: {shift:8d} | value: {corr[p]:.2f}")
