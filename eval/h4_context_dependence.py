"""H4: does a knob's effect depend on the OTHER knobs' settings (decay vs sustain, FEG amount vs cutoff, ...)?

Per ladder (one knob swept, everything else fixed at the ladder's context): effect size of the full sweep,
  audio  log-mel L1 distance between the first and last rung's render (what you would hear; no SAME involved)
  latent mean over frames of ||z_last - z_first|| (SAME-S, frame-aligned: same phrase on every rung)
then Spearman of effect size against each context parameter (the ladder's rung-0 value), per knob, and
the effect's median in context terciles. Filter knobs are also split by Surge filter TYPE (pole count and
topology), since the same knob can do different things on different filters. Also: direction consistency (signed pair cosine of time-mean
displacements) within each context tercile -- whether the DIRECTION, not just the size, depends on context.
Input: ladders_v2t.npz (train-split prior, 105 presets, contexts vary widely) + its latents.
Out: <dir>/context_dependence_<name>.json + effect_size_<name>.npz (per-ladder audio/latent effect). Run: SAO/.venv/bin/python eval/h4_context_dependence.py [--name ladders_v2t]
"""
import argparse
import json
import os

os.environ.setdefault("OMP_NUM_THREADS", "8")
import numpy as np
import torch
import re

import torchaudio
from scipy.stats import spearmanr

_SPEC = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "stable-audio-tools", "scripts",
                          "synth_inversion", "surge_spec.py")).read()
LP_FILTERS = re.findall(r'\("(LP [^"]+)", [0-9.]+\)', _SPEC.split("LP_FILTERS = [", 1)[1].split("]", 1)[0])
FILTER_KNOBS = ("cutoff", "resonance", "feg_amount", "feg_decay")

DIR = "/run/media/kim/Mantu/surge_200k_models/h4_gate_v2"
NAMES = ["midi_note", "filter_type", "shape", "width", "sub_mix", "sync", "fm_depth", "unison", "unison_detune",
         "cutoff", "resonance", "keytrack", "feg_amount", "feg_decay", "feg_sustain", "aeg_decay", "aeg_sustain",
         "aeg_release", "waveshaper_type", "drive", "chorus_mix", "delay_mix", "delay_fb"]
I = {n: i for i, n in enumerate(NAMES)}
# Context parameters that should gate each knob's effect (musically).
CONTEXT = {"cutoff": ["feg_amount", "resonance", "midi_note"], "resonance": ["cutoff", "feg_amount"],
           "feg_amount": ["cutoff", "feg_decay", "resonance"], "feg_decay": ["feg_amount", "cutoff"],
           "aeg_decay": ["aeg_sustain"], "aeg_sustain": ["aeg_decay"], "aeg_release": ["aeg_sustain"],
           "shape": ["cutoff", "sub_mix"], "sub_mix": ["cutoff", "shape"], "fm_depth": ["cutoff", "shape"]}


def unit(v):
    return v / (np.linalg.norm(v, axis=-1, keepdims=True) + 1e-12)


def pair_cos(D):
    if len(D) < 3:
        return float("nan")
    U = unit(D)
    C = U @ U.T
    n = len(U)
    return float((C.sum() - n) / (n * (n - 1)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=DIR)
    ap.add_argument("--name", default="ladders_v2t")
    a = ap.parse_args()
    d = np.load(f"{a.dir}/{a.name}.npz", mmap_mode="r")
    Z = np.load(f"{a.dir}/{a.name}.latents_same_s.npz")["z"]
    knobs, rhythms = [str(x) for x in d["knobs"]], [str(x) for x in d["rhythms"]]
    kid, lid, rung, nr, rh = (d[c][:] for c in ("knob_id", "ladder_id", "rung", "n_rungs", "rhythm_id"))
    vecs, sr = d["vecs"][:], int(d["sample_rate"])
    audio = d["audio"]             # ONE read: np.load ignores mmap_mode for .npz, so d["audio"][i] re-reads it all
    mel = torchaudio.transforms.MelSpectrogram(sr, n_fft=2048, hop_length=512, n_mels=96)

    def logmel(i):
        return torch.log(mel(torch.from_numpy(audio[i].astype(np.float32))) + 1e-5)

    rows = []
    for l in np.unique(lid):
        idx = np.where(lid == l)[0]
        f, t = idx[rung[idx] == 0][0], idx[rung[idx] == nr[idx][0] - 1][0]
        za, zb = Z[f].astype(np.float32), Z[t].astype(np.float32)
        rows.append({"ladder_id": int(l), "knob": int(kid[f]), "rhythm": int(rh[f]), "ctx": vecs[f],
                     "audio": float((logmel(t) - logmel(f)).abs().mean()),
                     "latent": float(np.linalg.norm(zb - za, axis=0).mean()), "D": (zb - za).mean(-1)})
    # Per-ladder effect sizes, for downstream splits (e.g. fit only on ladders where the knob is audible).
    np.savez(f"{a.dir}/effect_size_{a.name}.npz", ladder_id=np.array([r["ladder_id"] for r in rows]),
             knob_id=np.array([r["knob"] for r in rows]), audio_effect=np.array([r["audio"] for r in rows]),
             latent_effect=np.array([r["latent"] for r in rows]))
    res = {"file": a.name, "n_ladders": len(rows), "per_knob": {}}
    for k, name in enumerate(knobs):
        R = [r for r in rows if r["knob"] == k]
        if not R:
            continue
        aud, lat = np.array([r["audio"] for r in R]), np.array([r["latent"] for r in R])
        D = np.stack([r["D"] for r in R])
        out = {"n": len(R), "audio_effect_median": round(float(np.median(aud)), 4),
               "latent_effect_median": round(float(np.median(lat)), 4),
               "by_rhythm_audio": {rhythms[q]: round(float(np.median(aud[[r["rhythm"] == q for r in R]])), 4)
                                   for q in range(len(rhythms))}, "context": {}}
        for c in CONTEXT.get(name, []):
            x = np.array([r["ctx"][I[c]] for r in R])
            if np.ptp(x) < 1e-6:
                out["context"][c] = "constant in this set"
                continue
            q = np.quantile(x, [1 / 3, 2 / 3])
            bins = [x <= q[0], (x > q[0]) & (x <= q[1]), x > q[1]]
            out["context"][c] = {
                "range": [round(float(x.min()), 3), round(float(x.max()), 3)],
                "spearman_audio": round(float(spearmanr(x, aud).statistic), 3),
                "spearman_latent": round(float(spearmanr(x, lat).statistic), 3),
                "audio_effect_by_tercile": [round(float(np.median(aud[b])), 4) for b in bins],
                "direction_consistency_by_tercile": [round(pair_cos(D[b]), 3) for b in bins],
                "cross_tercile_direction_cos_low_vs_high": round(float(unit(unit(D[bins[0]]).mean(0)) @
                                                                       unit(unit(D[bins[2]]).mean(0))), 3)}
        if name in FILTER_KNOBS:
            # Categorical context (Surge filter type: pole count / topology). Per type with >= 12 ladders:
            # audible effect, direction consistency within the type, and cosine of the type's mean direction
            # with the pooled mean direction (low = this filter type moves the latent somewhere else).
            ft = np.array([int(round(r["ctx"][I["filter_type"]] * (len(LP_FILTERS) - 1))) for r in R])
            pooled = unit(unit(D).mean(0))
            out["by_filter_type"] = {}
            for f in np.unique(ft):
                b = ft == f
                if b.sum() < 12:
                    continue
                out["by_filter_type"][LP_FILTERS[f]] = {
                    "n": int(b.sum()), "audio_effect_median": round(float(np.median(aud[b])), 4),
                    "direction_consistency": round(pair_cos(D[b]), 3),
                    "mean_direction_cos_vs_pooled": round(float(unit(unit(D[b]).mean(0)) @ pooled), 3)}
        res["per_knob"][name] = out
    print(json.dumps(res, indent=1))
    json.dump(res, open(f"{a.dir}/context_dependence_{a.name}.json", "w"), indent=1)


if __name__ == "__main__":
    main()
