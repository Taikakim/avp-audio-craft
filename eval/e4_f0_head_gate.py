#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-11-03)
"""e4_f0_head_gate.py -- EXPERIMENTS E4: guided generation with the melody (f0) heads, with the disintegration gate. No "works" claim before this.

Heads: val30_f0_other_ema0.999 (lead, val 0.204) and val30_f0_bass_ema0.999 (bass, val 0.152), raw units Hz. Two opposite targets: a rising line and its mirror.
A real pitch effect must separate them: phase-locked in direction, unlike a density or brightness change, which would move both the same way.
  lead 300 -> 700 Hz, bass 60 -> 130 Hz, log-spaced over the clip.
Grid: 2 heads x 6 prompts x 2 seeds x 2 directions x gains 512, 2048, 8192, plus 12 guided gain-0 baselines = 156 clips. Base model, 20 s, 24 steps, cfg 7, no expandable_segments.
Measure (mir venv): PredominantPitchMelodia on the rendered mix, lead 55-1760 Hz, bass 30-350 Hz; voiced frames in semitones:
  slope  semitones per clip by least squares; corr  with the target line. Change vs baseline. Separation: slope(rising) - slope(falling), paired.
Melodia on a full mix is noisy: this is a screen, and a null here does not prove the head cannot steer a separated stem.
Then clip_metrics + Audiobox and the gate. Outputs: ~/evals_aac/control_runs/e4_f0_gate_20261103/. RUN: eval/run_e4.sh
"""
import argparse
import json
import os
import shutil
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

OUT = Path("/home/kim/evals_aac/control_runs/e4_f0_gate_20261103")
W = HERE.parent / "stable-audio-3" / "latch_weights_sa3_medium"
HEADS = {"lead": (W / "val30_f0_other_ema0.999" / "latch_sa3_f0_other_best.pt", 300.0, 700.0, 55, 1760),
         "bass": (W / "val30_f0_bass_ema0.999" / "latch_sa3_f0_bass_best.pt", 60.0, 130.0, 30, 350)}
PROMPTS = ("rb_common_0", "rb_common_1", "rb_mid_4", "rb_mid_5", "rb_rare_8", "kl_0")
SEEDS = (0, 1)                # offset added to each prompt's canonical seed
GAINS = (512, 2048, 8192)
DUR = 20.0
FRAMES = 280
SR = 44100


def line(lo, hi, rising):
    t = np.geomspace(lo, hi, FRAMES) if rising else np.geomspace(hi, lo, FRAMES)
    return t[None, :].astype(np.float32)


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
    cells = []
    for pid in PROMPTS:
        for so in SEEDS:
            seed = int(pr[pid]["seed"]) + so
            cells.append(dict(id=f"{pid}__s{seed}__base0", pid=pid, seed=seed, head=None, dir=None, gain=0))
            for h in HEADS:
                for d in ("up", "down"):
                    for g in GAINS:
                        cells.append(dict(id=f"{pid}__s{seed}__{h}__{d}__g{g}", pid=pid, seed=seed, head=h, dir=d, gain=g))
    todo = [c for c in cells if c["id"] not in done]
    print(len(todo), "clips to render", flush=True)
    if not todo:
        return
    model = StableAudioModel.from_pretrained("medium-base", device="cuda:0")
    t = pr[PROMPTS[0]]

    def gen(c):
        path, lo, hi, *_ = HEADS[c["head"] or "lead"]
        sink = []
        hp = {"n_iter": 4, "gamma": 0.3, "rho": float(c["gain"]), "mu": float(c["gain"])}
        a = model.generate(prompt=pr[c["pid"]].get("text") or pr[c["pid"]].get("prompt"), duration=DUR, steps=24, cfg_scale=7.0, seed=c["seed"], batch_size=1, latents_sink=sink,
                           latch_configs=[{"model_path": str(path), "target_raw": line(lo, hi, c["dir"] != "down"), "weight": 1.0, "loss_type": "smooth_l1", "start_pct": 0.0, "end_pct": 1.0}],
                           latch_hparams=hp)
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


def pitch(path, fmin, fmax):
    import essentia.standard as es
    x = es.MonoLoader(filename=str(path), sampleRate=44100)()
    f0, _ = es.PredominantPitchMelodia(frameSize=2048, hopSize=441, sampleRate=44100, minFrequency=fmin, maxFrequency=fmax)(es.EqualLoudness()(x))
    return np.asarray(f0, dtype=np.float64)


def track(f0, lo, hi, rising):
    v = f0 > 0
    if v.sum() < 50:
        return None
    t = np.arange(len(f0))[v] / len(f0)
    st = 12 * np.log2(f0[v] / lo)
    target = 12 * np.log2((np.geomspace(lo, hi, len(f0)) if rising else np.geomspace(hi, lo, len(f0)))[v] / lo)
    slope = float(np.polyfit(t, st, 1)[0])
    c = float(np.corrcoef(st, target)[0, 1]) if st.std() > 0 else 0.0
    return dict(slope=slope, corr=c, voiced=float(v.mean()), median_hz=float(np.median(f0[v])))


def measure():
    from control_head_disintegration_eval import DB, gate
    cells = [json.loads(l) for l in (OUT / "cells.jsonl").read_text().splitlines()]
    db = sqlite3.connect(DB)
    cols = [r[1] for r in db.execute("PRAGMA table_info(metrics)").fetchall()]
    rows = {r[0]: dict(zip(cols, r)) for r in db.execute("select * from metrics where path like ?", (f"{OUT}/%",))}
    base = {(c["pid"], c["seed"]): c for c in cells if c["gain"] == 0}
    for c in cells:
        c["metrics"] = rows.get(str(OUT / f"{c['id']}.m4a"))
        c["f0"] = {h: pitch(OUT / f"{c['id']}.m4a", HEADS[h][3], HEADS[h][4]) for h in (HEADS if c["gain"] == 0 else [c["head"]])}
    rep = {"table": [], "pairs": {}, "gate": {}}
    L = [f"{len(cells)} clips. Separation = slope(rising) - slope(falling), semitones per clip, paired over prompts and seeds; a real pitch effect makes it positive."]
    rng = np.random.default_rng(1)
    for h in HEADS:
        _, lo, hi, *_ = HEADS[h]
        for g in GAINS:
            ups = [c for c in cells if c["head"] == h and c["gain"] == g and c["dir"] == "up"]
            seps, corr_u, corr_d, base_u, fails, why, n = [], [], [], [], 0, Counter(), 0
            byp = defaultdict(list)
            for u in ups:
                d = next((c for c in cells if c["id"] == u["id"].replace("__up__", "__down__")), None)
                b = base[(u["pid"], u["seed"])]
                tu, td, tb = track(u["f0"][h], lo, hi, True), track(d["f0"][h], lo, hi, False) if d else None, track(b["f0"][h], lo, hi, True)
                for c in (u, d):
                    if c and c["metrics"] and b["metrics"]:
                        bad, w, _ = gate({**c["metrics"], "z_std": c["z_std"]}, {**b["metrics"], "z_std": b["z_std"]}, rhythmic=True)
                        n += 1
                        fails += bad
                        why.update(x.split("(")[0] for x in w)
                if tu and td and tb:
                    s = tu["slope"] - track(d["f0"][h], lo, hi, True)["slope"]
                    seps.append(s)
                    byp[u["pid"]].append(s)
                    corr_u.append(tu["corr"])
                    corr_d.append(td["corr"])
                    base_u.append(tb["corr"])
            pm = np.array([np.mean(v) for v in byp.values()])
            boot = rng.choice(pm, size=(4000, len(pm))).mean(1)
            r = dict(head=h, gain=g, n=len(seps), sep=round(float(np.mean(seps)), 2), ci=[round(float(np.percentile(boot, 2.5)), 2), round(float(np.percentile(boot, 97.5)), 2)],
                     positive=int(sum(x > 0 for x in seps)), corr_target=round(float(np.mean(corr_u + corr_d)), 3), corr_baseline=round(float(np.mean(base_u)), 3), fails=int(fails), gated=n, reasons=dict(why))
            rep["table"].append(r)
            L.append(f"{h:5s} g{g:<5d} separation {r['sep']:+6.2f} st {r['ci']} positive {r['positive']}/{r['n']}; corr with target {r['corr_target']:+.3f} (baseline vs rising {r['corr_baseline']:+.3f}); gate {r['fails']}/{r['gated']} {r['reasons']}")
    (OUT / "report.json").write_text(json.dumps(rep, indent=1))
    (OUT / "report.txt").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=("render", "measure"), required=True)
    a = ap.parse_args()
    render() if a.stage == "render" else measure()
