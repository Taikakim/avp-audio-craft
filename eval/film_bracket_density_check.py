#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-16)
# Last edited: WINTERMUTE 2026-10-16 — extension grid: per-arm FiLM gain ladders x requests 3/5/7/9/12 (listening verdict on the first check)
# Last edited: WINTERMUTE 2026-10-20 — arm fp32_lr3e-4 (test plan A4, fp32 optimizer state), kept out of the pick
"""film_bracket_density_check.py -- pick the full-run LR for EXPERIMENTS E12 by density response, not by loss.

WHY. The E12 bracket (FiLM onset-density adapter under the ModularOptimizer, lr 3e-4 / 1e-3 / 3e-3, 6000 steps each) trained
stably in all three arms with near-identical RF loss, and RF loss is blind to control (TRAINING.md D25), so the bracket alone
cannot choose. This renders each arm (and the shipped FiLM, the reference) as the FiLM adapter through the render server and
measures what the control actually does: spread = measured onsets/s at request 9 minus at request 3.

Context = E7 "base": medium-base, "psytrance, 140 bpm", euler 50, cfg 7, 20 s, seeds 1234 + 77, no DoRA. FiLM gain {1.0, 1.75}
x request {3, 9} onsets/s, plus one unguided render per seed. Pick rule (written before the data, used by the chain): the arm
with the largest mean spread at gain 1.0 among arms whose final latent std stays within 1.3x the unguided seed (the
latent-level screen, 2026-10-15); ties within 0.2 onsets/s -> the middle lr. Writes pick.json.
Output: Mantu/sa3_control_runs/film_bracket_density_check_20261016/. RUN: SAO/.venv/bin/python eval/film_bracket_density_check.py
"""
import json
import os
import shutil
import sys
import time

import numpy as np

MANTU = "/run/media/kim/Mantu"
OUT = f"{MANTU}/sa3_control_runs/film_bracket_density_check_20261016"
BR = f"{MANTU}/sa3_control_runs/film_modular_bracket_20261015"
ARMS = {"lr3e-4": f"{BR}/film_modular_lr3e-4_s6000/riffer_final.pt", "lr1e-3": f"{BR}/film_modular_lr1e-3_s6000/riffer_final.pt",
        "lr3e-3": f"{BR}/film_modular_lr3e-3_s6000/riffer_final.pt",
        "shipped": f"{MANTU}/sa3_control_runs/onset_Fusion_lr1e-4_randomcrop/riffer_final.pt",
        # the shipped run's own early checkpoints: does its density response appear only with training length?
        "shipped_s5400": f"{MANTU}/sa3_control_runs/onset_Fusion_lr1e-4_randomcrop/riffer_step5400.pt",
        "shipped_s10800": f"{MANTU}/sa3_control_runs/onset_Fusion_lr1e-4_randomcrop/riffer_step10800.pt",
        # the E12 full run (modular lr 1e-3, 54k steps, finished 2026-10-16 13:12): final + its midpoint
        "full_s54000": f"{MANTU}/sa3_control_runs/film_modular_full_20261016/film_modular_lr1e-3_s54000/riffer_final.pt",
        "full_s27000": f"{MANTU}/sa3_control_runs/film_modular_full_20261016/film_modular_lr1e-3_s54000/riffer_step27000.pt",
        # test plan A4 (2026-10-19): the lr3e-4 arm retrained with fp32 optimizer state; same seed and data order as lr3e-4
        "fp32_lr3e-4": f"{MANTU}/sa3_control_runs/film_precision_A_20261017/A4_fp32state_lr3e-4/riffer_final.pt"}
SERVER = "http://127.0.0.1:8056"
BASE = {"prompt": "psytrance, 140 bpm", "duration": 20.0, "steps": 50, "cfg_scale": 7.0, "sampler_type": "euler",
        "apg_scale": 1.0, "dora": {"name": "none", "strength": 1.0}}
SEEDS, GAINS, DENS = (1234, 77), (1.0, 1.75), (3, 9)
# Extension 2026-10-16 (listening: the weight, not the request, drives the change; extend the ladders): the pick summary still uses
# GAINS x DENS above; these grids add the rest. Shipped downward, lr3e-4 / lr1e-3 0.5-2.5, lr3e-3 0.1-1.0 in 0.1 steps.
EXT_DENS = (3, 5, 7, 9, 12)
EXT_GAINS = {"shipped": (0.1, 0.25, 0.5, 0.75, 1.0, 1.75), "lr3e-4": (0.5, 1.0, 1.5, 1.75, 2.0, 2.5),
             "lr1e-3": (0.5, 1.0, 1.5, 1.75, 2.0, 2.5), "lr3e-3": tuple(round(0.1 * i, 1) for i in range(1, 11)) + (1.75,),
             "shipped_s5400": (1.0, 1.75), "shipped_s10800": (1.0, 1.75),
             "full_s54000": tuple(round(0.25 * i, 2) for i in range(1, 21)), "full_s27000": (1.0, 1.75),
             "fp32_lr3e-4": (0.5, 1.0, 1.5, 1.75, 2.0, 2.5)}
# 2026-10-16 listening: the full run may take higher weights below the top request; its ladder is 0.25-5.0 in 0.25 steps and adds
# requests 1 and 2 onsets/s.
ARM_DENS = {"full_s54000": (1, 2, 3, 5, 7, 9, 12)}


def cells():
    out = [dict(arm=None, seed=s, gain=0, dens=None, id=f"base_s{s}") for s in SEEDS]
    for arm in ARMS:
        for s in SEEDS:
            for g in EXT_GAINS[arm]:
                for d in ARM_DENS.get(arm, EXT_DENS):
                    out.append(dict(arm=arm, seed=s, gain=g, dens=d, id=f"{arm}_s{s}_g{g:g}_d{d}"))
    return out


def main():
    import librosa
    import requests
    os.makedirs(OUT, exist_ok=True)
    jl = f"{OUT}/cells.jsonl"
    done = {json.loads(l)["id"] for l in open(jl) if l.strip()} if os.path.exists(jl) else set()
    if not os.path.exists(f"{OUT}/run_meta.json"):
        json.dump({"purpose": __doc__.split("Output:")[0].strip(), "arms": ARMS, "base": BASE, "seeds": SEEDS, "gains": GAINS,
                   "densities": DENS, "result": None, "kim_feedback": None}, open(f"{OUT}/run_meta.json", "w"), indent=1)
    for c in [c for c in cells() if c["id"] not in done]:
        p = {**BASE, "seed": c["seed"]}
        if c["arm"]:
            p["film"] = {"ckpt": ARMS[c["arm"]], "value": float(c["dens"]), "gain": float(c["gain"])}
        while True:
            try:
                r = requests.post(f"{SERVER}/generate", json=p, timeout=1800)
                break
            except requests.exceptions.ConnectionError:
                print(f"  {time.strftime('%H:%M')} server unreachable, retrying in 120 s", flush=True)
                time.sleep(120)
        res = r.json()
        if r.status_code != 200 or res.get("status") != "ok" or not res.get("files"):
            print(f"  FAIL {c['id']}: {r.status_code} {str(res)[:300]}", flush=True)
            continue
        dst = f"{OUT}/{c['id']}.wav"
        shutil.copyfile(res["files"][0], dst)
        y, sr = librosa.load(dst, sr=None, mono=True)
        c["onsets"] = round(len(librosa.onset.onset_detect(y=y, sr=sr, units="time")) / (len(y) / sr), 3)
        if res.get("latents") and os.path.exists(res["latents"][0]):
            c["z_std"] = round(float(np.load(res["latents"][0]).astype(np.float64).std()), 4)
        with open(jl, "a") as f:
            f.write(json.dumps(c) + "\n")
        print(f"  {c['id']}: {c['onsets']} on/s z {c.get('z_std')}", flush=True)
    rows = [json.loads(l) for l in open(jl) if l.strip()]
    base = {c["seed"]: c for c in rows if c["arm"] is None}
    summary = {}
    for arm in ARMS:
        cs = [c for c in rows if c["arm"] == arm]
        sp = {}
        for g in GAINS:
            hi = [c["onsets"] for c in cs if c["gain"] == g and c["dens"] == 9]
            lo = [c["onsets"] for c in cs if c["gain"] == g and c["dens"] == 3]
            sp[f"g{g:g}"] = round(float(np.mean(hi) - np.mean(lo)), 3) if hi and lo else None
        zr = [c["z_std"] / base[c["seed"]]["z_std"] for c in cs if c.get("z_std") and base.get(c["seed"], {}).get("z_std")]
        summary[arm] = {"spread": sp, "max_z_ratio": round(max(zr), 3) if zr else None}
    cand = {a: v for a, v in summary.items() if not a.startswith(("shipped", "fp32")) and (v["max_z_ratio"] or 0) <= 1.3 and v["spread"]["g1"] is not None}
    if not cand:   # every arm over the latent screen: fall back to all bracket arms
        cand = {a: v for a, v in summary.items() if not a.startswith(("shipped", "fp32")) and v["spread"]["g1"] is not None}
    best = max(cand, key=lambda a: cand[a]["spread"]["g1"])
    if "lr1e-3" in cand and cand[best]["spread"]["g1"] - cand["lr1e-3"]["spread"]["g1"] < 0.2:
        best = "lr1e-3"
    pick = {"pick": best, "lr": best.replace("lr", ""), "summary": summary, "rule": "largest gain-1.0 spread within the latent screen; ties < 0.2 -> lr1e-3"}
    json.dump(pick, open(f"{OUT}/pick.json", "w"), indent=1)
    m = json.load(open(f"{OUT}/run_meta.json"))
    m["result"] = pick
    json.dump(m, open(f"{OUT}/run_meta.json", "w"), indent=1)
    print(json.dumps(pick, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
