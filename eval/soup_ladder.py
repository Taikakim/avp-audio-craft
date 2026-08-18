#!/usr/bin/env python3
"""soup_ladder.py — weighted model soups over ONE run's checkpoint ladder, with the temporal
weighting profiles Kim found work (bell peak at late epochs, exponential-ascending), for any
Lightning DoRA/LoRA run. Generic replacement for the run-hardcoded soup_dora.py /
riffer-only make_soup_profiles.py.

WHY A TEMPORAL SOUP IS THE REPAIR FOR A DIFFUSING RUN (C, 2026-08-18). A constant-LR AdamW run
whose successive epoch displacements are uncorrelated (path efficiency at the 1/sqrt(n) random-walk
floor — the AdamW-sweep signature) has a terminal checkpoint = small drift + large random
excursion. No single direction to project out; averaging N checkpoints shrinks the excursion by
~sqrt(N) and keeps the drift. That is what these profiles do. For a run that oscillates instead,
the same average cancels the oscillation. Either way it needs the LADDER, not the terminal.

WHAT IS AVERAGED. The adapter tensors (lora_A, lora_B, magnitude) directly, factor-wise, exactly as
soup_dora.py did for the soups Kim has already judged. Factor-wise averaging is sound WITHIN one
run (consecutive checkpoints are one continuous trajectory in one factorization gauge). It is NOT
sound ACROSS runs — the B·A factorization has a gauge freedom (B->BR, A->R^-1 A) and different
seeds start A from different random bases, so mean(B)·mean(A) != mean(B·A). Cross-run soups must
average ΔW_eff (see task_vector_gram.py) and re-factor; this tool refuses mixed-run input.

PROFILES (over N checkpoints, i = 0..N-1)
  uniform    every checkpoint equal
  asc        linear ramp, high at the end
  expasc     exp(4 i/(N-1)) — ~55x last-to-first, smooth ascending  (Kim: "worked great")
  bell_late  Laplacian peak at --peak-frac of the ladder (default 0.75), width --tau epochs
  bell_end   Laplacian peak on the last checkpoint

USAGE
  .venv/bin/python eval/soup_ladder.py --ladder "<run>/epoch=*.weights.ckpt" \
      --profiles uniform,expasc,bell_late --out-dir <dir> [--start-ep 2]
Writes <dir>/soup_<run>_<profile>.ckpt = {state_dict, lora_config, epoch:-1, global_step:-1,
soup:{profile, sources, weights}} — loads via load_lora_checkpoint like any epoch. CPU-only.
"""
import argparse
import glob
import json
import math
import os
import re
import sys

import torch


def profile_weights(N, profile, peak_frac=0.75, tau=1.5):
    if N < 1:
        raise ValueError("empty ladder")
    if profile == "uniform":
        w = [1.0] * N
    elif profile == "asc":
        w = [i + 1.0 for i in range(N)]
    elif profile == "expasc":
        w = [math.exp(4.0 * i / max(N - 1, 1)) for i in range(N)]
    elif profile == "bell_late":
        c = peak_frac * (N - 1)
        w = [math.exp(-abs(i - c) / tau) for i in range(N)]
    elif profile == "bell_end":
        c = N - 1
        w = [math.exp(-abs(i - c) / tau) for i in range(N)]
    else:
        raise ValueError(f"unknown profile {profile!r}")
    s = sum(w)
    return [x / s for x in w]


def soup_state_dicts(sds, weights):
    """Weighted average, fp64 accumulate, cast back to the first dict's dtype per key.
    Every dict must have identical keys and shapes (checked)."""
    if len(sds) != len(weights):
        raise ValueError("one weight per state dict")
    if abs(sum(weights) - 1.0) > 1e-9:
        raise ValueError(f"weights must sum to 1, got {sum(weights)}")
    keys = list(sds[0].keys())
    for i, sd in enumerate(sds[1:], 1):
        if set(sd.keys()) != set(keys):
            raise ValueError(f"state dict {i} has different keys")
    out = {}
    for k in keys:
        ref = sds[0][k]
        acc = torch.zeros(ref.shape, dtype=torch.float64)
        for sd, w in zip(sds, weights):
            if sd[k].shape != ref.shape:
                raise ValueError(f"shape mismatch on {k}")
            if w != 0.0:
                acc += sd[k].to(torch.float64) * w
        out[k] = acc.to(ref.dtype)
    return out


def _run_of(path):
    """Directory name of the run — used to refuse mixed-run ladders."""
    return os.path.basename(os.path.dirname(os.path.abspath(path)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ladder", required=True, help="glob over ONE run's epoch=*.ckpt")
    ap.add_argument("--profiles", default="uniform,expasc,bell_late")
    ap.add_argument("--start-ep", type=int, default=0, help="drop epochs before this")
    ap.add_argument("--peak-frac", type=float, default=0.75)
    ap.add_argument("--tau", type=float, default=1.5)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--tag", default=None, help="name for the run in output filenames")
    a = ap.parse_args()

    paths = sorted(glob.glob(a.ladder), key=lambda p: int(re.search(r"epoch=(\d+)", p).group(1)))
    paths = [p for p in paths if int(re.search(r"epoch=(\d+)", p).group(1)) >= a.start_ep]
    if len(paths) < 2:
        sys.exit(f"[soup] need >=2 checkpoints, got {len(paths)} for {a.ladder}")
    runs = {_run_of(p) for p in paths}
    if len(runs) != 1:
        sys.exit(f"[soup] REFUSING: ladder spans {len(runs)} runs {sorted(runs)}. Factor-wise "
                 f"averaging is only sound within one run (B·A gauge). Cross-run: average ΔW_eff.")
    run = a.tag or runs.pop()
    eps = [int(re.search(r"epoch=(\d+)", p).group(1)) for p in paths]
    print(f"[soup] {run}: {len(paths)} checkpoints, epochs {eps}", flush=True)

    sds, cfg = [], None
    for p in paths:
        ck = torch.load(p, map_location="cpu", weights_only=False, mmap=True)
        sd = ck.get("state_dict", ck)
        sds.append({k: v.clone() for k, v in sd.items()
                    if re.search(r"\.(lora_A|lora_B|magnitude)$", k)})
        cfg = cfg or ck.get("lora_config", {})
    os.makedirs(a.out_dir, exist_ok=True)
    for prof in [p.strip() for p in a.profiles.split(",") if p.strip()]:
        w = profile_weights(len(sds), prof, a.peak_frac, a.tau)
        out = soup_state_dicts(sds, w)
        dst = os.path.join(a.out_dir, f"soup_{run}_{prof}.ckpt")
        torch.save({"state_dict": out, "lora_config": cfg, "epoch": -1, "global_step": -1,
                    "soup": {"profile": prof, "sources": paths, "epochs": eps,
                             "weights": w, "tool": "eval/soup_ladder.py"}}, dst)
        print(f"  {prof:<10} weights " + " ".join(f"{x:.2f}" for x in w) + f"  -> {dst}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
