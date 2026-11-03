#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-11-03)
"""d16_contour_ceiling.py -- EXPERIMENTS D16: where is the temporal ceiling of trajectory guidance? E4b showed the lead f0 head follows slow pitch shapes.
Triangle waves in pitch at periods 10, 5, 2.5, 1.25, 0.625 s, in phase and in antiphase, at gain 16384 (lead head, 300-700 Hz). An arrangement-level gesture sits at the
long end; a phrase at a few seconds; a note at the short end.
  follow = corr(measured semitones, target) - corr(measured, antiphase target), over voiced frames (Melodia on the mix), chance 0, max 2.
  Pitch is read raw, not smoothed; Melodia hop is 10 ms.
Grid: 6 prompts x 2 seeds x 5 periods x 2 phases = 120 clips; base model, 20 s, 24 steps, cfg 7. Baselines from E4 give the null at each period.
Outputs: ~/evals_aac/control_runs/d16_contour_ceiling_20261103/. RUN: eval/run_d16.sh
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
import e4b_f0_shapes as B

OUT = Path("/home/kim/evals_aac/control_runs/d16_contour_ceiling_20261103")
E4 = B.E4
PERIODS = (10.0, 5.0, 2.5, 1.25, 0.625)
GAIN = 16384


def tri(n, period, anti):
    t = np.linspace(0, B.DUR, n, endpoint=False) / period
    x = 1 - np.abs(2 * (t % 1) - 1)
    return 1 - x if anti else x


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
    cells = [dict(id=f"{p}__s{int(pr[p]['seed']) + o}__p{per}__{'anti' if a else 'in'}", pid=p, seed=int(pr[p]["seed"]) + o, period=per, anti=a) for p in B.PROMPTS for o in (0, 1) for per in PERIODS for a in (False, True)]
    todo = [c for c in cells if c["id"] not in done]
    print(len(todo), "clips to render", flush=True)
    if not todo:
        return
    model = StableAudioModel.from_pretrained("medium-base", device="cuda:0")

    def gen(c):
        sink = []
        tg = (B.LO * (B.HI / B.LO) ** tri(B.FRAMES, c["period"], c["anti"]))[None, :].astype(np.float32)
        a = model.generate(prompt=pr[c["pid"]].get("text") or pr[c["pid"]].get("prompt"), duration=B.DUR, steps=24, cfg_scale=7.0, seed=c["seed"], batch_size=1, latents_sink=sink,
                           latch_configs=[{"model_path": str(B.HEAD), "target_raw": tg, "weight": 1.0, "loss_type": "smooth_l1", "start_pct": 0.0, "end_pct": 1.0}],
                           latch_hparams={"n_iter": 4, "gamma": 0.3, "rho": float(GAIN), "mu": float(GAIN)})
        return a.float().cpu(), sink[0].float().cpu()

    gen(todo[0])
    with log.open("a") as f:
        for c in todo:
            a, z = gen(c)
            if not bool(torch.isfinite(a).all()) or float(a.std()) < 1e-3 or not bool(torch.isfinite(z).all()):
                print("FAULT", c["id"], flush=True)
                continue
            tmp = OUT / "_t.wav"
            save_audio(str(tmp), a[0][:, : int(B.DUR * B.SR)], B.SR, normalize=True)
            subprocess.run(["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-i", str(tmp), "-c:a", "aac", "-b:a", "192k", str(OUT / f"{c['id']}.m4a")], check=True)
            tmp.unlink()
            f.write(json.dumps(dict(c, z_std=round(float(z.std()), 4))) + "\n")
            f.flush()


def follow(f0, cen, period, anti):
    v = f0 > 0
    st = 12 * np.log2(f0[v] / B.LO)
    c = lambda a, b: float(np.corrcoef(a, b)[0, 1]) if a.std() > 0 and b.std() > 0 else 0.0
    n = len(f0)
    lc = np.log(np.maximum(cen, 1.0))
    return (c(st, tri(n, period, anti)[v]) - c(st, tri(n, period, not anti)[v]),
            c(lc, tri(len(lc), period, anti)) - c(lc, tri(len(lc), period, not anti)))


def measure():
    from control_head_disintegration_eval import DB, gate
    cells = [json.loads(l) for l in (OUT / "cells.jsonl").read_text().splitlines()]
    db = sqlite3.connect(DB)
    cols = [r[1] for r in db.execute("PRAGMA table_info(metrics)").fetchall()]
    rows = {r[0]: dict(zip(cols, r)) for r in db.execute("select * from metrics where path like ? or path like ?", (f"{OUT}/%", f"{E4}/%__base0.m4a"))}
    base = {(json.loads(l)["pid"], json.loads(l)["seed"]): json.loads(l) for l in (E4 / "cells.jsonl").read_text().splitlines() if json.loads(l)["gain"] == 0}
    bf = {k: B.features(E4 / f"{b['id']}.m4a") for k, b in base.items()}
    per = []
    for c in cells:
        f0, cen = B.features(OUT / f"{c['id']}.m4a")
        k = (c["pid"], c["seed"])
        fo, br = follow(f0, cen, c["period"], c["anti"])
        r = dict(c, follow=fo, bright=br, base_follow=follow(bf[k][0], bf[k][1], c["period"], c["anti"])[0])
        m, mb = rows.get(str(OUT / f"{c['id']}.m4a")), rows.get(str(E4 / f"{base[k]['id']}.m4a"))
        r["bad"], r["why"] = (None, [])
        if m and mb:
            bad, w, _ = gate({**m, "z_std": c["z_std"]}, {**mb, "z_std": base[k]["z_std"]}, rhythmic=True)
            r["bad"], r["why"] = bool(bad), [x.split("(")[0] for x in w]
        per.append(r)
    (OUT / "per_clip.json").write_text(json.dumps(per, indent=0))
    rng = np.random.default_rng(1)
    L, table = [f"gain {GAIN}. follow: corr with target minus corr with antiphase, chance 0, max 2. Null: the unsteered baselines against the same targets (mean of absolute values, since the sign is arbitrary)."], []
    for p in PERIODS:
        sub = [r for r in per if r["period"] == p]
        byp = defaultdict(list)
        for r in sub:
            byp[r["pid"]].append(r["follow"])
        pm = np.array([np.mean(v) for v in byp.values()])
        b = rng.choice(pm, size=(4000, len(pm))).mean(1)
        row = dict(period=p, n=len(sub), follow=round(float(np.mean([r["follow"] for r in sub])), 3), ci=[round(float(np.percentile(b, 2.5)), 3), round(float(np.percentile(b, 97.5)), 3)], positive=int(sum(r["follow"] > 0 for r in sub)),
                   null_abs=round(float(np.mean([abs(r["base_follow"]) for r in sub])), 3), bright=round(float(np.mean([r["bright"] for r in sub])), 3), fails=int(sum(bool(r["bad"]) for r in sub)), why=dict(Counter(x for r in sub for x in r["why"])))
        table.append(row)
        L.append(f"period {p:5.3f} s  follow {row['follow']:+.3f} {row['ci']} positive {row['positive']}/{row['n']}; null {row['null_abs']:.3f}; bright {row['bright']:+.3f}; gate {row['fails']}/{row['n']} {row['why']}")
    (OUT / "report.json").write_text(json.dumps(table, indent=1))
    (OUT / "report.txt").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=("render", "measure"), required=True)
    a = ap.parse_args()
    render() if a.stage == "render" else measure()
