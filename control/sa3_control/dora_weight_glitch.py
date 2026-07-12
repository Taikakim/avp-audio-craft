#!/usr/bin/env python3
"""Do rank-128 DoRA adapters tolerate high DoRA weight (1.5) better than rank-16?

Kim's observation (2026-07-12): dora16_goa_newstack_8ep (and some other 16-rank runs) sound
spectrally glitchy at DoRA weight 1.5. Hypothesis: higher rank handles higher weight better.

Test with the model-matrix clips (already rendered at w1.0 and w1.5, same ckpt/cfg/prompt/seed):
for each model, measure the spectral GLITCH introduced going w1.0 -> w1.5 — high-band fraction
of added energy (>5 kHz) + zero-crossing-rate blowup (same meter as the hardness shortcut test).
Group by adapter rank. If rank-16 glitches harder at 1.5 than rank-128, the hypothesis holds.

Run: mir/bin/python control/sa3_control/dora_weight_glitch.py
"""
import glob
import os
import re
from collections import defaultdict

import numpy as np

MATRIX = "/home/kim/evals_aac/model_matrix"
SR = 22050
HI_HZ = 5000.0
# <model>__<ckpt>__cfg<C>__w<W>__<prompt>__s<seed>.m4a
FN = re.compile(r"^(?P<model>.+?)__(?P<ckpt>.+?)__cfg(?P<cfg>[\d.]+)__w(?P<w>\d+)__(?P<prompt>.+?)__s(?P<seed>\d+)$")


def load(path):
    import librosa
    y, _ = librosa.load(path, sr=SR, mono=True)
    return y


def glitch(a, b):
    """spectral change a->b: high-band fraction of ADDED energy + zcr delta."""
    import librosa
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    Sa = np.abs(librosa.stft(a, n_fft=2048)); Sb = np.abs(librosa.stft(b, n_fft=2048))
    freqs = librosa.fft_frequencies(sr=SR, n_fft=2048)
    diff = (Sb - Sa).mean(axis=1)
    hi = freqs >= HI_HZ
    hi_add = float(diff[hi].clip(min=0).sum()); lo_add = float(diff[~hi].clip(min=0).sum())
    zcr = lambda y: float((np.abs(np.diff(np.sign(y))) > 0).mean())
    return hi_add / (hi_add + lo_add + 1e-9), zcr(b) - zcr(a)


def rank_of(model):
    if "dora16" in model or "_r16" in model:
        return 16
    if "dora128" in model or "_r128" in model:
        return 128
    return None


def main():
    # index clips by (model, ckpt, cfg, prompt, seed) -> {w: path}
    idx = defaultdict(dict)
    for f in glob.glob(f"{MATRIX}/*.m4a"):
        m = FN.match(os.path.splitext(os.path.basename(f))[0])
        if not m:
            continue
        if rank_of(m["model"]) is None:
            continue
        key = (m["model"], m["ckpt"], m["cfg"], m["prompt"], m["seed"])
        idx[key][m["w"]] = f

    per_model = defaultdict(list)
    for key, ws in idx.items():
        if "100" in ws and "150" in ws:                 # need both w1.0 and w1.5
            try:
                hi_frac, zcr_d = glitch(load(ws["100"]), load(ws["150"]))
            except Exception:
                continue
            per_model[key[0]].append((hi_frac, zcr_d))

    print(f"{'model':38s} {'rank':>4s} {'n':>3s} {'hi_frac(1.0->1.5)':>17s} {'zcr_delta':>10s}")
    by_rank = defaultdict(list)
    rows = []
    for model, vals in sorted(per_model.items()):
        hf = np.mean([v[0] for v in vals]); zd = np.mean([v[1] for v in vals])
        rk = rank_of(model)
        by_rank[rk].append((hf, zd))
        rows.append((rk, model, len(vals), hf, zd))
    for rk, model, n, hf, zd in sorted(rows):
        print(f"{model:38s} {rk:4d} {n:3d} {hf:17.3f} {zd:+10.4f}")

    print("\n=== BY RANK (mean spectral glitch introduced by w1.0->w1.5) ===")
    for rk in (16, 128):
        if by_rank[rk]:
            hf = np.mean([v[0] for v in by_rank[rk]]); zd = np.mean([v[1] for v in by_rank[rk]])
            print(f"  rank-{rk:3d}: hi_frac {hf:.3f}  zcr_delta {zd:+.4f}  (n_models={len(by_rank[rk])})")
    if by_rank[16] and by_rank[128]:
        h16 = np.mean([v[0] for v in by_rank[16]]); h128 = np.mean([v[0] for v in by_rank[128]])
        z16 = np.mean([v[1] for v in by_rank[16]]); z128 = np.mean([v[1] for v in by_rank[128]])
        print(f"\nVERDICT: rank-16 hi_frac {h16:.3f} vs rank-128 {h128:.3f} "
              f"(zcr {z16:+.4f} vs {z128:+.4f}).")
        print("  Kim's hypothesis (higher rank tolerates w1.5 better) " +
              ("SUPPORTED" if h16 > h128 + 0.02 else "NOT supported / weak") +
              " on the spectral-glitch axis.")


if __name__ == "__main__":
    main()
