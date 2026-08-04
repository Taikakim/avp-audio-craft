#!/usr/bin/env python3
"""interval_cfg_ab_analyze.py — melodic-movement readout for the interval-CFG A/B
(task #26; companion to eval/interval_cfg_ab.py; RUN WITH THE mir VENV).

Adapts W's mir/src/tools/melodic_movement_ladder.py metrics (chroma_flux,
pc_trans_rate, pc_entropy, pc_active — same code path, harmonic chroma-CQT) to the
95 s A/B clips (central 80 s), and computes the SAME metrics on matched 60-155 s
slices of the original unguided a2a_kaikkialla_newstack full-track ladder renders
(the long-form baseline, same ckpt/prompt/seed/steps/cfg). Verdict axis: does a
narrowed cfg_interval lift the nl .40-.55 chroma-flux dip vs the (0,1) default?

  mir/bin/python eval/interval_cfg_ab_analyze.py
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, "/home/kim/Projects/mir/src")
from core.file_utils import read_audio  # noqa: E402
import librosa  # noqa: E402

DIR = Path("/run/media/kim/Mantu/sa3_control_runs/interval_cfg_ab")
BASE_LADDER = Path("/run/media/kim/Mantu/sa3_lora_runs/a2a_kaikkialla_newstack")
SR = 22050


def metrics(y, sr, lo, hi):
    """W's ladder metrics on the [lo,hi] second slice (same math as
    melodic_movement_ladder.metrics, parameterized slice)."""
    if y.ndim > 1:
        y = y.mean(axis=1)
    if sr != SR:
        y = librosa.resample(y.astype(np.float32), orig_sr=sr, target_sr=SR)
        sr = SR
    y = y[int(lo * sr):int(hi * sr)]
    if len(y) < sr * 30:
        return None
    yh = librosa.effects.harmonic(y, margin=4.0)
    C = librosa.feature.chroma_cqt(y=yh, sr=sr, hop_length=2048)
    Cn = C / (C.sum(axis=0, keepdims=True) + 1e-9)
    fps = sr / 2048
    flux = float(np.linalg.norm(np.diff(Cn, axis=1), axis=0).mean())
    dom = Cn.argmax(axis=0)
    trans = float((np.diff(dom) != 0).sum() / (len(dom) / fps))
    avg = Cn.mean(axis=1)
    avg = avg / avg.sum()
    ent = float(-(avg * np.log2(avg + 1e-12)).sum())
    active = int((avg > 0.05).sum())
    return dict(chroma_flux=flux, pc_trans_rate=trans, pc_entropy=ent, pc_active=active)


def main():
    meta = json.loads((DIR / "run_meta.json").read_text())
    rows = []

    # A/B clips: central 80 s of the 95 s render
    for tag in meta["renders"]:
        wav = DIR / f"{tag}.wav"
        y, sr = read_audio(str(wav))
        m = metrics(y, sr, 7.5, 87.5)
        if m is None:
            print(f"[warn] {tag}: too short"); continue
        nl = int(tag.split("_")[0][2:]) / 1000
        iname = tag.split("_")[1]
        seed = int(tag.split("_s")[-1])
        rows.append(dict(kind="ab", label=tag, nl=nl, interval=iname, seed=seed, **m))
        print(f"[ab]   {tag}: flux={m['chroma_flux']:.4f} trans={m['pc_trans_rate']:.2f} "
              f"ent={m['pc_entropy']:.2f} act={m['pc_active']}", flush=True)

    # long-form baselines: SAME source window (60-155 s of the full render, central 80)
    for wav in sorted(BASE_LADDER.glob("a2a_nl*.wav")):
        nl = int(wav.stem[6:]) / 100
        y, sr = read_audio(str(wav))
        m = metrics(y, sr, 67.5, 147.5)
        if m is None:
            continue
        rows.append(dict(kind="ladder_baseline", label=wav.stem, nl=nl,
                         interval="full_longform", seed=1234, **m))
        print(f"[base] {wav.stem}: flux={m['chroma_flux']:.4f} trans={m['pc_trans_rate']:.2f}",
              flush=True)

    with open(DIR / "movement_metrics.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # verdict table: per (nl, interval) mean over seeds
    print("\n=== chroma_flux by nl x interval (mean over seeds; dip band = .40-.55) ===")
    inames = ["full", "hi07", "band0108"]
    print(f"{'nl':>6} " + " ".join(f"{i:>10}" for i in inames))
    ab = [r for r in rows if r["kind"] == "ab"]
    for nl in sorted(set(r["nl"] for r in ab)):
        vals = []
        for i in inames:
            xs = [r["chroma_flux"] for r in ab if r["nl"] == nl and r["interval"] == i]
            vals.append(f"{np.mean(xs):>10.4f}" if xs else f"{'—':>10}")
        print(f"{nl:>6.3f} " + " ".join(vals))
    print("(pc_trans_rate table)")
    for nl in sorted(set(r["nl"] for r in ab)):
        vals = []
        for i in inames:
            xs = [r["pc_trans_rate"] for r in ab if r["nl"] == nl and r["interval"] == i]
            vals.append(f"{np.mean(xs):>10.2f}" if xs else f"{'—':>10}")
        print(f"{nl:>6.3f} " + " ".join(vals))
    print(f"\n[analysis] -> {DIR}/movement_metrics.csv")


if __name__ == "__main__":
    main()
