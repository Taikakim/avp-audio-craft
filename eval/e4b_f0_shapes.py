#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-11-03)
"""e4b_f0_shapes.py -- EXPERIMENTS E4b: E4 found rising and falling lead targets separate in measured pitch by 22 semitones at gain 8192, gate-clean. Is that a melody
following a line, or a side effect? A slope cannot tell, so: non-monotonic shapes (arch, valley) as well as up and down, higher gains, and a control measure.
  Follows: corr(measured semitones, target) minus corr(measured, the mirrored target), paired per prompt + seed. Chance is 0.
  Control: the same difference on the spectral centroid. If centroid follows as strongly as pitch, it may be a brightness sweep and not a melody.
  Octave check: the same pitch measure folded to pitch class cannot follow a line of 14.7 semitones over the whole range, so also report the share of frame-to-frame
  jumps of 11 to 13 semitones (Melodia octave errors) against the gain-0 baseline.
Grid: lead head, 6 prompts x 2 seeds x 4 shapes x gains 8192, 16384, 32768 = 144 clips. Baselines reused from E4 (same recipe, seeds).
Outputs: ~/evals_aac/control_runs/e4b_f0_shapes_20261103/. RUN: eval/run_e4b.sh
"""
import argparse
import json
import os
import sqlite3
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

for k, v in {"FLASH_ATTENTION_TRITON_AMD_ENABLE": "FALSE", "PYTORCH_TUNABLEOP_ENABLED": "0", "MIOPEN_FIND_MODE": "2"}.items():
    os.environ.setdefault(k, v)
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import numpy as np

OUT = Path("/home/kim/evals_aac/control_runs/e4b_f0_shapes_20261103")
E4 = Path("/home/kim/evals_aac/control_runs/e4_f0_gate_20261103")
HEAD = HERE.parent / "stable-audio-3/latch_weights_sa3_medium/val30_f0_other_ema0.999/latch_sa3_f0_other_best.pt"
PROMPTS = ("rb_common_0", "rb_common_1", "rb_mid_4", "rb_mid_5", "rb_rare_8", "kl_0")
GAINS = (8192, 16384, 32768)
LO, HI = 300.0, 700.0
FRAMES = 280
DUR = 20.0
SR = 44100
SHAPES = {"up": lambda x: x, "down": lambda x: 1 - x, "arch": lambda x: 1 - np.abs(2 * x - 1), "valley": lambda x: np.abs(2 * x - 1)}
MIRROR = {"up": "down", "down": "up", "arch": "valley", "valley": "arch"}


def hz(shape, n):
    return LO * (HI / LO) ** SHAPES[shape](np.linspace(0, 1, n))


def render():
    import torch
    sys.path.insert(0, str(HERE.parent / "control"))
    sys.path.insert(0, str(HERE.parent / "stable-audio-3"))
    import model_matrix_gen as M
    from sa3_control.audio_io import save_audio
    from stable_audio_3 import StableAudioModel

    OUT.mkdir(parents=True, exist_ok=True)
    pr = {p["id"]: p for p in M.build_prompts(n_per_band=3, n_kimlong=3)}
    log = OUT / "cells.jsonl"
    done = {json.loads(l)["id"] for l in log.read_text().splitlines()} if log.exists() else set()
    cells = [dict(id=f"{p}__s{int(pr[p]['seed']) + o}__{s}__g{g}", pid=p, seed=int(pr[p]["seed"]) + o, shape=s, gain=g) for p in PROMPTS for o in (0, 1) for s in SHAPES for g in GAINS]
    todo = [c for c in cells if c["id"] not in done]
    print(len(todo), "clips to render", flush=True)
    if not todo:
        return
    model = StableAudioModel.from_pretrained("medium-base", device="cuda:0")

    def gen(c):
        sink = []
        a = model.generate(prompt=pr[c["pid"]].get("text") or pr[c["pid"]].get("prompt"), duration=DUR, steps=24, cfg_scale=7.0, seed=c["seed"], batch_size=1, latents_sink=sink,
                           latch_configs=[{"model_path": str(HEAD), "target_raw": hz(c["shape"], FRAMES)[None, :].astype(np.float32), "weight": 1.0, "loss_type": "smooth_l1", "start_pct": 0.0, "end_pct": 1.0}],
                           latch_hparams={"n_iter": 4, "gamma": 0.3, "rho": float(c["gain"]), "mu": float(c["gain"])})
        return a.float().cpu(), sink[0].float().cpu()

    gen(todo[0])
    with log.open("a") as f:
        for c in todo:
            a, z = gen(c)
            if not bool(torch.isfinite(a).all()) or float(a.std()) < 1e-3 or not bool(torch.isfinite(z).all()):
                print("FAULT", c["id"], flush=True)
                continue
            tmp = OUT / "_t.wav"
            save_audio(str(tmp), a[0][:, : int(DUR * SR)], SR, normalize=True)
            subprocess.run(["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-i", str(tmp), "-c:a", "aac", "-b:a", "192k", str(OUT / f"{c['id']}.m4a")], check=True)
            tmp.unlink()
            f.write(json.dumps(dict(c, z_std=round(float(z.std()), 4))) + "\n")
            f.flush()


def features(path):
    import essentia.standard as es
    import librosa
    x = es.MonoLoader(filename=str(path), sampleRate=44100)()
    f0, _ = es.PredominantPitchMelodia(frameSize=2048, hopSize=441, sampleRate=44100, minFrequency=55, maxFrequency=1760)(es.EqualLoudness()(x))
    c = librosa.feature.spectral_centroid(y=x, sr=44100, n_fft=2048, hop_length=441)[0]
    return np.asarray(f0, dtype=np.float64), np.asarray(c, dtype=np.float64)


def scores(f0, cen, shape):
    v = f0 > 0
    st = 12 * np.log2(f0[v] / LO)
    tg = lambda s, n: SHAPES[s](np.linspace(0, 1, n))
    c = lambda a, b: float(np.corrcoef(a, b)[0, 1]) if a.std() > 0 and b.std() > 0 else 0.0
    follow = c(st, tg(shape, len(f0))[v]) - c(st, tg(MIRROR[shape], len(f0))[v])
    lc = np.log(np.maximum(cen, 1.0))
    bright = c(lc, tg(shape, len(lc))) - c(lc, tg(MIRROR[shape], len(lc)))
    j = np.abs(np.diff(st))
    return dict(follow=follow, bright=bright, octave_jumps=float(((j > 11) & (j < 13)).mean()), voiced=float(v.mean()), span=float(np.percentile(st, 95) - np.percentile(st, 5)))


def measure():
    from control_head_disintegration_eval import DB, gate
    cells = [json.loads(l) for l in (OUT / "cells.jsonl").read_text().splitlines()]
    db = sqlite3.connect(DB)
    cols = [r[1] for r in db.execute("PRAGMA table_info(metrics)").fetchall()]
    rows = {r[0]: dict(zip(cols, r)) for r in db.execute("select * from metrics where path like ? or path like ?", (f"{OUT}/%", f"{E4}/%__base0.m4a"))}
    base = {(json.loads(l)["pid"], json.loads(l)["seed"]): json.loads(l) for l in (E4 / "cells.jsonl").read_text().splitlines() if json.loads(l)["gain"] == 0}
    bf = {k: features(E4 / f"{b['id']}.m4a") for k, b in base.items()}
    per = []
    for c in cells:
        f0, cen = features(OUT / f"{c['id']}.m4a")
        k = (c["pid"], c["seed"])
        r = dict(c, **scores(f0, cen, c["shape"]))
        b = {f"base_{a}": v for a, v in scores(bf[k][0], bf[k][1], c["shape"]).items()}
        r.update(b)
        m, mb = rows.get(str(OUT / f"{c['id']}.m4a")), rows.get(str(E4 / f"{base[k]['id']}.m4a"))
        if m and mb:
            r["bad"], w, _ = gate({**m, "z_std": c["z_std"]}, {**mb, "z_std": base[k]["z_std"]}, rhythmic=True)
            r["why"] = [x.split("(")[0] for x in w]
            r["dce"] = (m["ce"] - mb["ce"]) if m.get("ce") is not None and mb.get("ce") is not None else None
        else:
            r["bad"], r["why"], r["dce"] = None, [], None
        per.append(r)
    (OUT / "per_clip.json").write_text(json.dumps(per, indent=0))
    L = ["follow = corr with the target minus corr with its mirror, in voiced semitones (mix, Melodia); chance 0, max 2. bright = the same on the log spectral centroid.", ""]
    rng = np.random.default_rng(1)
    table = []
    for g in GAINS:
        for sset, name in ((("up", "down"), "up/down"), (("arch", "valley"), "arch/valley")):
            sub = [r for r in per if r["gain"] == g and r["shape"] in sset]
            byp = defaultdict(list)
            for r in sub:
                byp[r["pid"]].append(r["follow"])
            pm = np.array([np.mean(v) for v in byp.values()])
            b = rng.choice(pm, size=(4000, len(pm))).mean(1)
            gated = [r for r in sub if r["bad"] is not None]
            row = dict(gain=g, shapes=name, n=len(sub), follow=round(float(np.mean([r["follow"] for r in sub])), 3), ci=[round(float(np.percentile(b, 2.5)), 3), round(float(np.percentile(b, 97.5)), 3)],
                       positive=int(sum(r["follow"] > 0 for r in sub)), base_follow=round(float(np.mean([r["base_follow"] for r in sub])), 3), bright=round(float(np.mean([r["bright"] for r in sub])), 3),
                       octave=round(float(np.mean([r["octave_jumps"] for r in sub])), 4), base_octave=round(float(np.mean([r["base_octave_jumps"] for r in sub])), 4), span=round(float(np.mean([r["span"] for r in sub])), 1),
                       fails=int(sum(bool(r["bad"]) for r in gated)), gated=len(gated), dce=round(float(np.mean([r["dce"] for r in gated if r["dce"] is not None] or [0])), 2), why=dict(Counter(x for r in gated for x in r["why"])))
            table.append(row)
            L.append(f"g{g:<6d}{name:12s} follow {row['follow']:+.3f} {row['ci']} positive {row['positive']}/{row['n']} (baseline {row['base_follow']:+.3f}); bright {row['bright']:+.3f}; octave jumps {row['octave']:.4f} (base {row['base_octave']:.4f}); span {row['span']} st; gate {row['fails']}/{row['gated']} dCE {row['dce']:+.2f} {row['why']}")
    (OUT / "report.json").write_text(json.dumps(table, indent=1))
    (OUT / "report.txt").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=("render", "measure"), required=True)
    a = ap.parse_args()
    render() if a.stage == "render" else measure()
