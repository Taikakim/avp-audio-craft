#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-11-03)
"""d1_sdedit_survival.py -- EXPERIMENTS D1: as SDEdit's start noise t_s rises, what of the source survives, and in what order?

Decides where a "keep vs regenerate" split belongs for audio-to-audio: if rhythm's timing outlives harmony (or the reverse) at some t_s, that band
of t_s keeps one and regenerates the other. Also a trajectory-level check of the earlier finding that rhythm is noise-invariant (beat R2 .80 at L14).

Render: 12 goa tracks (fixed random pick from Goa_Separated), a 20 s window from 60 s in, through a2a on the base model at
t_s = 0.1 ... 0.9 and 1.0, 2 seeds, cfg 7, 24 steps, one fixed prompt = 240 clips.
Measure each output against its source, per band where it applies:
  phase_{bass,mid,air}  corr at zero lag of the onset envelopes: timing kept IN PLACE (the "temporal phase")
  rhythm_lag_{mid}      best corr within +-1 beat-ish lag (0.25 s): the same rhythm, perhaps shifted
  tiv                   mean per-frame cosine of the Tonal Interval Vector (weighted DFT of chroma, Harte/Bernardes)
  chroma                mean per-frame cosine of chroma
  mel                   mean per-frame cosine of the log-mel spectrum (overall timbre/texture)
Floor: the same measures between each output and a DIFFERENT track's source, so "survives" means above what unrelated goa scores.
Survival point of a measure: the t_s where it falls halfway from its value at t_s 0.1 to the floor.

Outputs: clips and cells in ~/evals_aac/control_runs/d1_sdedit_survival_20261103/, measures.jsonl, report.txt, report.json, run_meta.json.
RUN: eval/run_d1.sh   (render on SAO/.venv under the GPU lock, then --stage measure on mir/bin/python)
"""
import argparse
import json
import os
import random
import subprocess
import sys
from pathlib import Path

for k, v in {"FLASH_ATTENTION_TRITON_AMD_ENABLE": "FALSE", "PYTORCH_TUNABLEOP_ENABLED": "0", "MIOPEN_FIND_MODE": "2"}.items():
    os.environ.setdefault(k, v)

import numpy as np

OUT = Path("/home/kim/evals_aac/control_runs/d1_sdedit_survival_20261103")
SRC_ROOT = Path("/run/media/kim/Mantu/ai-music/Goa_Separated")
PROMPT = "goa trance, melodic mood, 145 bpm"
LEVELS = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
SEEDS = (1234, 5678)
N_TRACKS = 12
START = 60.0
DUR = 20.0
SR = 44100
STEPS = 24
CFG = 7.0
MEASURES = ("phase_bass", "phase_mid", "phase_air", "rhythm_lag_mid", "tiv", "chroma", "mel")


def pick_tracks():
    dirs = sorted(d for d in SRC_ROOT.iterdir() if d.is_dir() and any((d / f"full_mix.{e}").exists() for e in ("flac", "wav", "mp3", "m4a")))
    random.Random(764).shuffle(dirs)
    return dirs[:N_TRACKS]


def full_mix(d):
    return next(d / f"full_mix.{e}" for e in ("flac", "wav", "mp3", "m4a") if (d / f"full_mix.{e}").exists())


def load_window(path):
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(START), "-t", str(DUR), "-i", str(path), "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True)
    return np.frombuffer(r.stdout, dtype=np.float32).reshape(-1, 2).T.copy()


def render():
    import torch
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "control"))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stable-audio-3"))
    from sa3_control.audio_io import save_audio
    from stable_audio_3 import StableAudioModel

    OUT.mkdir(parents=True, exist_ok=True)
    tracks = pick_tracks()
    log = OUT / "cells.jsonl"
    done = {json.loads(l)["id"] for l in log.read_text().splitlines()} if log.exists() else set()
    todo = [(i, ts, s) for i in range(len(tracks)) for ts in LEVELS for s in SEEDS if f"t{i:02d}__ts{ts:.1f}__s{s}" not in done]
    print(len(todo), "clips to render", flush=True)
    if not todo:
        return
    model = StableAudioModel.from_pretrained("medium-base", device="cuda:0")
    ds = model.model.pretransform.downsampling_ratio
    size = int(DUR * SR)
    size = (size // ds + (1 if size % ds else 0)) * ds
    src = {}
    with log.open("a") as f:
        for i, ts, s in todo:
            if i not in src:
                x = load_window(full_mix(tracks[i]))
                src[i] = x
                sp = OUT / f"t{i:02d}__source.m4a"
                if not sp.exists():
                    tmp = OUT / "_tmp.wav"
                    save_audio(str(tmp), torch.tensor(x), SR, normalize=True)
                    subprocess.run(["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-i", str(tmp), "-c:a", "aac", "-b:a", "192k", str(sp)], check=True)
                    tmp.unlink()
            cid = f"t{i:02d}__ts{ts:.1f}__s{s}"
            a = model.generate(prompt=PROMPT, duration=DUR, steps=STEPS, cfg_scale=CFG, seed=s, batch_size=1, sample_size=size,
                               init_audio=(SR, torch.tensor(src[i])), init_noise_level=ts)
            a = a.float().cpu()
            if not bool(torch.isfinite(a).all()) or float(a.std()) < 1e-3:
                print("FAULT", cid, flush=True)
                continue
            tmp = OUT / "_tmp.wav"
            save_audio(str(tmp), a[0][:, : int(DUR * SR)], SR, normalize=True)
            subprocess.run(["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-i", str(tmp), "-c:a", "aac", "-b:a", "192k", str(OUT / f"{cid}.m4a")], check=True)
            tmp.unlink()
            f.write(json.dumps(dict(id=cid, track=i, ts=ts, seed=s)) + "\n")
            f.flush()
    (OUT / "tracks.json").write_text(json.dumps({f"t{i:02d}": d.name for i, d in enumerate(tracks)}, indent=1, ensure_ascii=False))


def features(path):
    import librosa
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", "22050", "-f", "f32le", "-"], capture_output=True, check=True)
    y = np.frombuffer(r.stdout, dtype=np.float32).copy()
    hop = 512
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=hop)) ** 2
    fr = librosa.fft_frequencies(sr=22050, n_fft=2048)
    bands = {"bass": fr < 150, "mid": (fr >= 150) & (fr < 4000), "air": fr >= 4000}
    out = {}
    for b, m in bands.items():
        e = np.log1p(S[m].sum(0) * 1e3)
        out[f"on_{b}"] = np.maximum(np.diff(e, prepend=e[0]), 0)
    c = librosa.feature.chroma_stft(S=S, sr=22050, hop_length=hop)
    out["chroma"] = c
    weights = np.array([0.5, 0.5, 1 / 3, 0.25, 0.2, 0.2])[:, None]             # Harte / Bernardes-style interval weights
    F = np.fft.fft(c / (c.sum(0, keepdims=True) + 1e-9), axis=0)[1:7]
    out["tiv"] = np.concatenate([(F * weights).real, (F * weights).imag], axis=0)
    out["mel"] = librosa.power_to_db(librosa.feature.melspectrogram(S=S, sr=22050, n_mels=64))
    return out


def cos_frames(a, b):
    n = min(a.shape[1], b.shape[1])
    a, b = a[:, :n], b[:, :n]
    return float(np.mean((a * b).sum(0) / (np.linalg.norm(a, axis=0) * np.linalg.norm(b, axis=0) + 1e-9)))


def corr(a, b):
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    return float(np.corrcoef(a, b)[0, 1]) if a.std() > 0 and b.std() > 0 else 0.0


def compare(x, s):
    d = {f"phase_{b}": corr(x[f"on_{b}"], s[f"on_{b}"]) for b in ("bass", "mid", "air")}
    lag = int(0.25 * 22050 / 512)
    a, b = x["on_mid"], s["on_mid"]
    d["rhythm_lag_mid"] = max(corr(a[max(0, l):], b[max(0, -l):]) for l in range(-lag, lag + 1))
    d["tiv"] = cos_frames(x["tiv"], s["tiv"])
    d["chroma"] = cos_frames(x["chroma"], s["chroma"])
    m0 = x["mel"] - x["mel"].mean(1, keepdims=True)
    m1 = s["mel"] - s["mel"].mean(1, keepdims=True)
    d["mel"] = cos_frames(m0, m1)
    return d


def measure():
    cells = [json.loads(l) for l in (OUT / "cells.jsonl").read_text().splitlines()]
    srcf = {i: features(OUT / f"t{i:02d}__source.m4a") for i in sorted({c["track"] for c in cells})}
    tracks = sorted(srcf)
    rows = []
    with (OUT / "measures.jsonl").open("w") as f:
        for c in cells:
            x = features(OUT / f"{c['id']}.m4a")
            r = dict(c, **compare(x, srcf[c["track"]]))
            other = tracks[(tracks.index(c["track"]) + 1) % len(tracks)]
            r.update({f"floor_{k}": v for k, v in compare(x, srcf[other]).items()})
            rows.append(r)
            f.write(json.dumps(r) + "\n")
    report(rows)


def report(rows):
    rep = {"curve": {}, "floor": {}, "half_point": {}, "n": len(rows)}
    L = [f"{len(rows)} clips; mean over {N_TRACKS} tracks x {len(SEEDS)} seeds", "", "t_s     " + "".join(f"{m:>16s}" for m in MEASURES)]
    for ts in LEVELS:
        v = [r for r in rows if abs(r["ts"] - ts) < 1e-6]
        rep["curve"][f"{ts:.1f}"] = {m: round(float(np.mean([r[m] for r in v])), 4) for m in MEASURES}
        L.append(f"{ts:.1f}     " + "".join(f"{rep['curve'][f'{ts:.1f}'][m]:16.3f}" for m in MEASURES))
    rep["floor"] = {m: round(float(np.mean([r[f"floor_{m}"] for r in rows])), 4) for m in MEASURES}
    L.append("floor   " + "".join(f"{rep['floor'][m]:16.3f}" for m in MEASURES))
    L += ["", "half point: t_s where the measure falls halfway from t_s 0.1 to the floor (interval: bootstrap over tracks)"]
    rng = np.random.default_rng(1)

    def half(sub, m):
        c = [float(np.mean([r[m] for r in sub if abs(r["ts"] - ts) < 1e-6])) for ts in LEVELS]
        fl = float(np.mean([r[f"floor_{m}"] for r in sub]))
        goal = (c[0] + fl) / 2
        for a in range(1, len(c)):
            if c[a] <= goal:
                return LEVELS[a - 1] + (LEVELS[a] - LEVELS[a - 1]) * (c[a - 1] - goal) / max(c[a - 1] - c[a], 1e-9)
        return 1.0

    for m in MEASURES:
        ts = sorted({r["track"] for r in rows})
        pts = []
        for _ in range(1000):
            pick = rng.choice(ts, size=len(ts))
            sub = [r for t in pick for r in rows if r["track"] == t]
            pts.append(half(sub, m))
        h = half(rows, m)
        rep["half_point"][m] = {"t_s": round(h, 3), "ci": [round(float(np.percentile(pts, 2.5)), 3), round(float(np.percentile(pts, 97.5)), 3)]}
        L.append(f"  {m:16s} {h:.3f}  [{rep['half_point'][m]['ci'][0]}, {rep['half_point'][m]['ci'][1]}]")
    (OUT / "report.json").write_text(json.dumps(rep, indent=1))
    (OUT / "report.txt").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=("render", "measure"), required=True)
    a = ap.parse_args()
    render() if a.stage == "render" else measure()
