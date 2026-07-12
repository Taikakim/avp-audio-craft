#!/usr/bin/env python3
"""Hardness steering: is the head's 'harder' direction genuine timbre or just added
distortion? (shortcut-feature hypothesis, from the two-stage scalar-guidance negative.)

Both flatness hypotheses were falsified (constant-target and pooled-mean both buzz at
every gain). Revised suspect #2: corpus hardness correlates with distortion, so the head's
ascent direction IS high-frequency harmonic garbage. Test: for each steered clip vs its
same-seed base, where does the magnitude-spectrum ENERGY CHANGE concentrate? If 'up'
(harder) piles energy into the high band (distortion signature) and it grows with gain,
that's the shortcut. CPU, mir venv, uses the existing bracket clips — no GPU, no new data.

Run: mir/bin/python control/sa3_control/hardness_spectral_diff.py
"""
import glob
import os
import re
import sys

import numpy as np

BRACKET = "/run/media/kim/Mantu/sa3_control_runs/hardness_bracket_2026-07-10"
SR = 22050
HI_HZ = 5000.0   # above this = candidate distortion/harmonic-garbage band


def load(path):
    import librosa
    y, _ = librosa.load(path, sr=SR, mono=True)
    return y


def band_split_change(base, steered):
    """Mean per-bin |STFT| change, split into low/high bands + zero-crossing delta."""
    import librosa
    n = min(len(base), len(steered))
    base, steered = base[:n], steered[:n]
    Sb = np.abs(librosa.stft(base, n_fft=2048))
    Ss = np.abs(librosa.stft(steered, n_fft=2048))
    freqs = librosa.fft_frequencies(sr=SR, n_fft=2048)
    diff = (Ss - Sb).mean(axis=1)                      # per-freq mean change over time
    hi = freqs >= HI_HZ
    lo = ~hi
    hi_gain = float(diff[hi].clip(min=0).sum())        # energy ADDED in high band
    lo_gain = float(diff[lo].clip(min=0).sum())
    total_add = hi_gain + lo_gain + 1e-9
    zcr_b = float((np.abs(np.diff(np.sign(base))) > 0).mean())
    zcr_s = float((np.abs(np.diff(np.sign(steered))) > 0).mean())
    return {"hi_frac_of_added_energy": round(hi_gain / total_add, 3),
            "zcr_base": round(zcr_b, 4), "zcr_steered": round(zcr_s, 4),
            "zcr_delta": round(zcr_s - zcr_b, 4)}


def main():
    bases = {}
    for f in glob.glob(f"{BRACKET}/base_s*.wav"):
        s = re.search(r"base_s(\d+)", os.path.basename(f)).group(1)
        bases[s] = load(f)
    print(f"loaded {len(bases)} base clips: seeds {list(bases)}")

    # up/down _g<G>[p]_s<seed>
    rows = []
    for f in sorted(glob.glob(f"{BRACKET}/*.wav")):
        b = os.path.basename(f)
        m = re.match(r"(up|down)_g(\d+)(p?)_s(\d+)\.wav", b)
        if not m:
            continue
        direction, gain, pooled, seed = m.group(1), int(m.group(2)), bool(m.group(3)), m.group(4)
        if seed not in bases:
            continue
        r = band_split_change(bases[seed], load(f))
        r.update({"direction": direction, "gain": gain, "pooled": pooled, "seed": seed})
        rows.append(r)

    print("\n=== high-band fraction of ADDED energy (distortion signature grows -> shortcut) ===")
    print(f"{'dir':5s} {'gain':>5s} {'pool':>5s} {'hi_frac':>8s} {'zcr_delta':>10s}")
    for r in sorted(rows, key=lambda x: (x["direction"], x["pooled"], x["gain"])):
        print(f"{r['direction']:5s} {r['gain']:5d} {str(r['pooled']):>5s} "
              f"{r['hi_frac_of_added_energy']:8.3f} {r['zcr_delta']:+10.4f}")

    # verdict: does hi_frac climb with gain for 'up'? does zcr blow up?
    ups = [r for r in rows if r["direction"] == "up" and not r["pooled"]]
    if ups:
        ups.sort(key=lambda x: x["gain"])
        hi_by_gain = [(r["gain"], r["hi_frac_of_added_energy"]) for r in ups]
        zcr_by_gain = [(r["gain"], r["zcr_delta"]) for r in ups]
        gains = [g for g, _ in hi_by_gain]
        hi = [h for _, h in hi_by_gain]
        trend = float(np.corrcoef(gains, hi)[0, 1]) if len(gains) > 2 and np.std(hi) > 0 else None
        print(f"\nUP: hi-band-fraction vs gain trend corr = {trend}")
        print(f"UP: zcr_delta by gain = {zcr_by_gain}")
        print("READ: hi_frac rising toward ~1.0 with gain + zcr_delta blowing up "
              "=> the 'harder' direction IS added high-freq distortion (shortcut CONFIRMED). "
              "hi_frac staying moderate/flat => genuine timbral change (shortcut weakened).")


if __name__ == "__main__":
    main()
