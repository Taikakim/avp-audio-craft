#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-15)
"""punch_nodora_seeds.py -- the punch rating set's 64 seeds rendered WITHOUT the DoRA (and without LatCH).

WHY (project direction 2026-10-15): seed 764 of the punch DoRA render is grainy and saturates under FiLM, 3050 does not.
Hypothesis: like the post-trained model, the DoRA narrows the output range and pulls renders toward a few modes, one of
them grainy. eval/punch_seed_latent_stats.py found 764 smoother in time with larger per-channel offsets, but no direction
that predicts quality on the other seeds (1 labelled seed, PQ as proxy). This adds the missing reference: the same seeds,
prompt and sampler on the plain base model, so the DoRA's own shift of the latent statistics can be measured per seed.

Client of :8056 /generate. Base payload = the rating server's "cleanest" preset minus its LatCH slots and DoRA
(dora "none"): the punch prompt, euler 30 steps, cfg 9, 48 s, same schedule fields. Seeds = the 64 of
punch_rating_20261014/manifest.json. The latent is copied beside each wav (<id>.z0.npy).
Output: Mantu2/sa3_control_runs/punch_nodora_seeds_20261015/. RUN: SAO/.venv/bin/python eval/punch_nodora_seeds.py [--dry]
"""
import argparse
import copy
import json
import os
import shutil
import sys
import time

_MANTU = next((p for p in ("/run/media/kim/Mantu", "/run/media/kim/Mantu2", "/run/media/kim/Mantu1")
               if os.path.isdir(f"{p}/sa3_control_runs")), "/run/media/kim/Mantu")   # removable drive: name varies
OUT = f"{_MANTU}/sa3_control_runs/punch_nodora_seeds_20261015"
RATING = f"{_MANTU}/sa3_control_runs/punch_rating_20261014"
SERVER = "http://127.0.0.1:8056"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    seeds = sorted({e["seed"] for e in json.load(open(f"{RATING}/manifest.json"))["entries"]})
    jl = f"{OUT}/cells.jsonl"
    done = {json.loads(l)["seed"] for l in open(jl) if l.strip()} if os.path.exists(jl) else set()
    todo = [s for s in seeds if s not in done]
    print(f"[nodora] {len(todo)} of {len(seeds)} seeds to render", flush=True)
    if a.dry:
        return 0
    import requests
    presets = json.load(open(f"{RATING}/presets.json"))
    base = copy.deepcopy(presets.get("presets", presets)["cleanest"])
    for k in ("latch", "rho", "mu", "gamma", "n_iter", "ckpt_path"):
        base.pop(k, None)
    base["dora"] = {"name": "none", "strength": 1.0}
    os.makedirs(OUT, exist_ok=True)
    if not os.path.exists(f"{OUT}/run_meta.json"):
        json.dump({"purpose": __doc__.split("Client of")[0].strip(),
                   "hypothesis": "The DoRA shifts per-seed latent statistics toward smoother, larger-offset latents, and the grainy seeds furthest.",
                   "payload_minus_prompt": {k: v for k, v in base.items() if k != "prompt"}, "seeds": seeds,
                   "related": ["eval/punch_seed_latent_stats.py", f"{RATING}/seed_latent_stats_20261015.json"],
                   "result": None, "kim_feedback": None}, open(f"{OUT}/run_meta.json", "w"), indent=1)
    for s in todo:
        t0 = time.time()
        while True:
            try:
                r = requests.post(f"{SERVER}/generate", json={**base, "seed": s}, timeout=1800)
                break
            except requests.exceptions.ConnectionError:
                print(f"  {time.strftime('%H:%M')} server unreachable, retrying in 120 s", flush=True)
                time.sleep(120)
        res = r.json()
        if r.status_code != 200 or res.get("status") != "ok" or not res.get("files"):
            print(f"  FAIL s{s}: {r.status_code} {str(res)[:300]}", flush=True)
            continue
        cid = f"nodora_s{s}"
        shutil.copyfile(res["files"][0], f"{OUT}/{cid}.wav")
        if res.get("latents"):
            shutil.copyfile(res["latents"][0], f"{OUT}/{cid}.z0.npy")
        with open(jl, "a") as fh:
            fh.write(json.dumps({"id": cid, "seed": s, "secs": round(time.time() - t0, 1)}) + "\n")
        print(f"  {cid} ({time.time() - t0:.1f}s)", flush=True)
    print("DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
