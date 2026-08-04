#!/usr/bin/env python3
"""steer_orthogonal_ab_analyze.py — meter pass for the Gram-Schmidt steering A/B
(task #58; companion to eval/steer_orthogonal_ab.py; RUN WITH THE mir VENV).

Per clip: mt_dark moodtheme sigmoid (mean over ~1 Hz patches, same effnet path that
labeled the training corpus), onset density (essentia OnsetRate), and the
disintegration-gate drift features vs the seed-matched base clip (flatness, hf_ratio,
zcr — the buzz signatures). Aggregates per arm across seeds and prints the verdict
table: does GS hold the protected axis at its solo value where naive addition drifts it?

  mir/bin/python eval/steer_orthogonal_ab_analyze.py \
      --dir /run/media/kim/Mantu/sa3_lora_runs/concept_steering/orthogonal_ab
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, "/home/kim/Projects/mir/src")
from spectral.whole_track_expanded import ExpandedExtractor  # noqa: E402

ARMS = ["base", "dark", "onset", "naive", "gs_kponset", "gs_kpdark"]


def gate_feats(y, sr, es):
    win = es.Windowing(type="hann")
    spec = es.Spectrum()
    flat = es.Flatness()
    frames = []
    for fr in es.FrameGenerator(y, frameSize=2048, hopSize=1024):
        frames.append(spec(win(fr)))
    S = np.array(frames)  # [n,1025]
    flatness = float(np.mean([flat(s) for s in S]))
    freqs = np.linspace(0, sr / 2, S.shape[1])
    hf = float(S[:, freqs > 10000].sum() / (S.sum() + 1e-9))
    zcr_f = es.ZeroCrossingRate()
    zcr = float(np.mean([zcr_f(fr) for fr in es.FrameGenerator(y, frameSize=2048, hopSize=1024)]))
    return {"flatness": flatness, "hf_ratio": hf, "zcr": zcr}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, required=True)
    args = ap.parse_args()

    import essentia.standard as es
    ext = ExpandedExtractor(enable_models=True, enable_dsp=False)
    labels = json.loads(Path("/home/kim/Projects/mir/models/essentia/mtg_jamendo_moodtheme-discogs-effnet-1.json").read_text())["classes"]
    i_dark = labels.index("dark")

    meta = json.loads((args.dir / "run_meta.json").read_text())
    seeds = meta["seeds"]

    rows = {}
    for wav in sorted(args.dir.glob("*.wav")):
        tag = wav.stem
        data, _rates, _meta = ext.extract(wav, wanted=["effnet_moodtheme_ts"])
        mood = np.asarray(data["effnet_moodtheme_ts"], dtype=np.float32)
        dark = float(mood[:, i_dark].mean())
        y = es.MonoLoader(filename=str(wav), sampleRate=44100)()
        _onset_times, onset_rate = es.OnsetRate()(y)
        g = gate_feats(y, 44100, es)
        rows[tag] = {"dark": round(dark, 4), "onsets_per_s": round(float(onset_rate), 3), **{k: round(v, 5) for k, v in g.items()}}
        print(f"[clip] {tag}: dark={dark:.4f} onsets/s={onset_rate:.2f} "
              f"flat={g['flatness']:.4f} hf={g['hf_ratio']:.4f}", flush=True)

    # per-arm aggregate (mean over seeds) + gate drift vs seed-matched base
    agg = {}
    for arm in ARMS:
        darks = [rows[f"{arm}_s{s}"]["dark"] for s in seeds]
        onss = [rows[f"{arm}_s{s}"]["onsets_per_s"] for s in seeds]
        drift = {}
        for feat in ("flatness", "hf_ratio", "zcr"):
            drift[feat] = round(float(np.mean(
                [rows[f"{arm}_s{s}"][feat] - rows[f"base_s{s}"][feat] for s in seeds])), 5)
        agg[arm] = {"dark_mean": round(float(np.mean(darks)), 4),
                    "dark_per_seed": darks,
                    "onsets_mean": round(float(np.mean(onss)), 3),
                    "onsets_per_seed": onss,
                    "gate_drift_vs_base": drift}

    print("\n=== ARM SUMMARY (mean over seeds) ===")
    print(f"{'arm':<12} {'dark':>7} {'onsets/s':>9}  gate-drift(flat/hf/zcr)")
    for arm in ARMS:
        a = agg[arm]
        d = a["gate_drift_vs_base"]
        print(f"{arm:<12} {a['dark_mean']:>7.4f} {a['onsets_mean']:>9.3f}  "
              f"{d['flatness']:+.4f}/{d['hf_ratio']:+.4f}/{d['zcr']:+.4f}")

    out = {"per_clip": rows, "per_arm": agg}
    (args.dir / "analysis.json").write_text(json.dumps(out, indent=2))
    print(f"\n[analysis] -> {args.dir}/analysis.json")


if __name__ == "__main__":
    main()
