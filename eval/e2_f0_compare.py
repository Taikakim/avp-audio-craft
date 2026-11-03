#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-11-03)
"""e2_f0_compare.py -- EXPERIMENTS E2: the lead f0 head retrained under the modular recipe against the current one, same grid, same prompts and seeds.
  shapes   up, down, arch, valley at gains 512, 2048, 8192: the same 'follow' score as E4b (corr with target minus corr with mirror; chance 0, max 2)
  periods  triangle waves at 10, 5, 2.5 s, in phase and antiphase, at gain 8192, the score from D16.
  gate     against the E4 gain-0 baselines.
Paired old vs new per prompt + seed + cell; 95% interval over prompts. Selected by steering, not by val loss: val has not predicted steering (E13).
Outputs: ~/evals_aac/control_runs/e2_f0_compare_20261103/. RUN: eval/run_e2_compare.sh
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
import d16_contour_ceiling as D
import e4b_f0_shapes as B

OUT = Path("/home/kim/evals_aac/control_runs/e2_f0_compare_20261103")
E4 = B.E4
ARMS = {"old": B.HEAD, "new": Path("/run/media/kim/Mantu/latch_sweep/f0_modular_2026-11-03/E2_c3_d512_L8/latch_sa3_f0_other_ep12.pt")}
GAINS = (512, 2048, 8192)
PERIODS = (10.0, 5.0, 2.5)
PGAIN = 8192
SHAPES = ("up", "down", "arch", "valley")


def target(c, n):
    if c["kind"] == "shape":
        return B.LO * (B.HI / B.LO) ** B.SHAPES[c["shape"]](np.linspace(0, 1, n))
    return B.LO * (B.HI / B.LO) ** D.tri(n, c["period"], c["anti"])


def all_cells(pr):
    out = []
    for arm in ARMS:
        for p in B.PROMPTS:
            for o in (0, 1):
                seed = int(pr[p]["seed"]) + o
                for s in SHAPES:
                    for g in GAINS:
                        out.append(dict(id=f"{arm}__{p}__s{seed}__{s}__g{g}", arm=arm, pid=p, seed=seed, kind="shape", shape=s, gain=g))
                for per in PERIODS:
                    for a in (False, True):
                        out.append(dict(id=f"{arm}__{p}__s{seed}__p{per}__{'anti' if a else 'in'}", arm=arm, pid=p, seed=seed, kind="period", period=per, anti=a, gain=PGAIN))
    return out


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
    todo = [c for c in all_cells(pr) if c["id"] not in done]
    print(len(todo), "clips to render", flush=True)
    if not todo:
        return
    model = StableAudioModel.from_pretrained("medium-base", device="cuda:0")

    def gen(c):
        sink = []
        a = model.generate(prompt=pr[c["pid"]].get("text") or pr[c["pid"]].get("prompt"), duration=B.DUR, steps=24, cfg_scale=7.0, seed=c["seed"], batch_size=1, latents_sink=sink,
                           latch_configs=[{"model_path": str(ARMS[c["arm"]]), "target_raw": target(c, B.FRAMES)[None, :].astype(np.float32), "weight": 1.0, "loss_type": "smooth_l1", "start_pct": 0.0, "end_pct": 1.0}],
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
            save_audio(str(tmp), a[0][:, : int(B.DUR * B.SR)], B.SR, normalize=True)
            subprocess.run(["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-i", str(tmp), "-c:a", "aac", "-b:a", "192k", str(OUT / f"{c['id']}.m4a")], check=True)
            tmp.unlink()
            f.write(json.dumps(dict(c, z_std=round(float(z.std()), 4))) + "\n")
            f.flush()


def measure():
    from control_head_disintegration_eval import DB, gate
    cells = [json.loads(l) for l in (OUT / "cells.jsonl").read_text().splitlines()]
    db = sqlite3.connect(DB)
    cols = [r[1] for r in db.execute("PRAGMA table_info(metrics)").fetchall()]
    rows = {r[0]: dict(zip(cols, r)) for r in db.execute("select * from metrics where path like ? or path like ?", (f"{OUT}/%", f"{E4}/%__base0.m4a"))}
    base = {(json.loads(l)["pid"], json.loads(l)["seed"]): json.loads(l) for l in (E4 / "cells.jsonl").read_text().splitlines() if json.loads(l)["gain"] == 0}
    per = []
    for c in cells:
        f0, cen = B.features(OUT / f"{c['id']}.m4a")
        if c["kind"] == "shape":
            s = B.scores(f0, cen, c["shape"])
            fo, br = s["follow"], s["bright"]
        else:
            fo, br = D.follow(f0, cen, c["period"], c["anti"])
        k = (c["pid"], c["seed"])
        m, mb = rows.get(str(OUT / f"{c['id']}.m4a")), rows.get(str(E4 / f"{base[k]['id']}.m4a"))
        bad, why, dce = None, [], None
        if m and mb:
            bad, w, _ = gate({**m, "z_std": c["z_std"]}, {**mb, "z_std": base[k]["z_std"]}, rhythmic=True)
            why = [x.split("(")[0] for x in w]
            dce = (m["ce"] - mb["ce"]) if m.get("ce") is not None and mb.get("ce") is not None else None
        per.append(dict(c, follow=fo, bright=br, bad=bool(bad) if bad is not None else None, why=why, dce=dce))
    (OUT / "per_clip.json").write_text(json.dumps(per, indent=0))
    rng = np.random.default_rng(1)
    keyf = lambda r: (r["pid"], r["seed"], r.get("shape"), r.get("period"), r.get("anti"), r["gain"])
    old = {keyf(r): r for r in per if r["arm"] == "old"}
    rows_out, L = [], ["follow: chance 0, max 2. new - old paired; interval over prompts.", ""]

    def line(label, sub_new):
        subo = [old[keyf(r)] for r in sub_new if keyf(r) in old]
        byp = defaultdict(list)
        for r in sub_new:
            if keyf(r) in old:
                byp[r["pid"]].append(r["follow"] - old[keyf(r)]["follow"])
        pm = np.array([np.mean(v) for v in byp.values()])
        b = rng.choice(pm, size=(4000, len(pm))).mean(1)
        row = dict(label=label, n=len(sub_new), old=round(float(np.mean([r["follow"] for r in subo])), 3), new=round(float(np.mean([r["follow"] for r in sub_new])), 3), diff=round(float(pm.mean()), 3), ci=[round(float(np.percentile(b, 2.5)), 3), round(float(np.percentile(b, 97.5)), 3)],
                   new_bright=round(float(np.mean([r["bright"] for r in sub_new])), 3), old_bright=round(float(np.mean([r["bright"] for r in subo])), 3),
                   old_fails=int(sum(bool(r["bad"]) for r in subo)), new_fails=int(sum(bool(r["bad"]) for r in sub_new)),
                   new_dce=round(float(np.mean([r["dce"] for r in sub_new if r["dce"] is not None] or [0])), 2), old_dce=round(float(np.mean([r["dce"] for r in subo if r["dce"] is not None] or [0])), 2), why=dict(Counter(x for r in sub_new for x in r["why"])))
        rows_out.append(row)
        L.append(f"{label:24s} old {row['old']:+.3f} new {row['new']:+.3f} diff {row['diff']:+.3f} {row['ci']}; bright {row['old_bright']:+.2f}->{row['new_bright']:+.2f}; gate {row['old_fails']}->{row['new_fails']}/{row['n']} {row['why']}; dCE {row['old_dce']:+.2f}->{row['new_dce']:+.2f}")

    new = [r for r in per if r["arm"] == "new"]
    for g in GAINS:
        line(f"up/down g{g}", [r for r in new if r["kind"] == "shape" and r["gain"] == g and r["shape"] in ("up", "down")])
        line(f"arch/valley g{g}", [r for r in new if r["kind"] == "shape" and r["gain"] == g and r["shape"] in ("arch", "valley")])
    for p in PERIODS:
        line(f"period {p} s g{PGAIN}", [r for r in new if r["kind"] == "period" and r["period"] == p])
    (OUT / "report.json").write_text(json.dumps(rows_out, indent=1))
    (OUT / "report.txt").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=("render", "measure"), required=True)
    a = ap.parse_args()
    render() if a.stage == "render" else measure()
