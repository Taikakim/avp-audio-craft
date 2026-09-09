#!/usr/bin/env python3
"""latent_channel_audit.py — per-CHANNEL latent-scale audit, and calibration for its threshold.

WHY (CONTINUITY 2026-09-09, with WINTERMUTE). The publish gate's latent-sanity check scores a
clip by its GLOBAL z0 std against a fixed Z0_STD_MAX = 2.0. That number is family-blind, and the
families genuinely differ: `medium` (ptm) is rf_denoiser/pingpong at 8 steps cfg 1, `medium-base`
is rectified_flow/euler at ~24 steps cfg 7, so their latent statistics differ by construction. A
single threshold across them is the same error as auditioning two checkpoints on the wrong
sampler -- a rule we already had on file for clips and never carried into the gate.

The fix is not a per-family threshold but a DIFFERENT STATISTIC. The 2026-08-10 runaway finding
was measured per channel (166 of 256 channels over 2.0 on the runaway vs 0 of 256 healthy), and
that is the half that carries the information:

  - a shifted FAMILY moves most channels a little  -> global std rises, channel count does not
  - a RUNAWAY blows up a subset hard               -> channel count rises sharply

Spot-checked on the corpus (W, n=6/group): ptm clips that TRIP the global gate and ptm clips that
PASS it show the SAME channel count (2 and 2), i.e. the global flag on ptm carries no information
about that clip at all; while a genuinely broken fullft ep7 sits at global std 3.87 -- under any
rail loose enough to spare ptm -- with 57 bad channels.

Two things this tool refuses to inherit:
  * the per-channel threshold. Reusing 2.0 because the clip-level constant says so is how the
    original mistake was made. --calibrate derives it from the corpus instead.
  * max-channel std as a discriminator. Measured non-discriminating (runaway 4.26-4.54 vs ptm
    2.21-2.54, under 2x). It is the COUNT that separates, not the worst channel.

  eval/latent_channel_audit.py --calibrate --per-arm 8
  eval/latent_channel_audit.py --chan-k 2.5 --per-arm 8 --out /tmp/chan_audit.json
"""
import argparse
import collections
import json
import os
import random
import re
import sys
from pathlib import Path

import numpy as np

Z0_ROOTS = [Path("/run/media/kim/Mantu/sa3_lora_runs/model_matrix"),
            Path("/run/media/kim/Mantu/sa3_control_runs/model_matrix")]


def arm_of(name: str) -> str:
    """Arm label = everything before the first render-axis field (cfg/w/seed/steps)."""
    stem = name.split(".z0.npy")[0]
    parts = stem.split("__")
    keep = []
    for p in parts:
        if re.fullmatch(r"(cfg[\d.]+|w\d+|s\d+|st\d+)", p):
            break
        keep.append(p)
    return "__".join(keep) or stem


def is_ptm(arm: str) -> bool:
    return "ptm" in arm.lower()


def sample_paths(per_arm: int, seed: int):
    by_arm = collections.defaultdict(list)
    for root in Z0_ROOTS:
        if not root.exists():
            continue
        with os.scandir(root) as it:
            for e in it:
                if e.name.endswith(".z0.npy"):
                    by_arm[arm_of(e.name)].append(os.path.join(root, e.name))
    rng = random.Random(seed)
    out = {}
    for arm, ps in by_arm.items():
        rng.shuffle(ps)
        out[arm] = ps[:per_arm]
    return out


def measure(path, chan_k):
    """Global std, per-channel stds, and the count of channels over chan_k."""
    a = np.load(path, mmap_mode="r")
    a = np.asarray(a, dtype=np.float64)
    if a.ndim == 3:
        a = a[0]
    if not np.isfinite(a).all():
        return {"finite": False}
    ch = a.std(axis=-1)                     # (256,) per-channel std over time
    return {"finite": True, "std": float(a.std()), "chan": ch,
            "n_over": int((ch > chan_k).sum()), "chan_max": float(ch.max())}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--per-arm", type=int, default=6, help="clips sampled per arm")
    ap.add_argument("--chan-k", type=float, default=2.0,
                    help="a channel counts as blown above this std (see --calibrate)")
    ap.add_argument("--calibrate", action="store_true",
                    help="derive chan-k from the corpus instead of taking it on faith, and "
                         "report how well each candidate separates arms")
    ap.add_argument("--standardize", action="store_true",
                    help="count channels exceeding k robust sigmas of THAT CHANNEL'S OWN "
                         "healthy baseline, per family, instead of a fixed absolute std. A "
                         "fixed threshold is not family-neutral -- measured, the unmodified "
                         "ptm base model blows 250/256 channels at k=2.0 while being by "
                         "definition healthy.")
    ap.add_argument("--std-k", type=float, default=6.0,
                    help="--standardize: robust sigmas (MAD-based) above the per-channel "
                         "family baseline before a channel counts as blown")
    ap.add_argument("--trajectory", action="store_true",
                    help="compare each arm against ITSELF across epochs instead of against a "
                         "threshold. Level-based rules cannot work here: healthy checkpoints "
                         "span the whole range (the unmodified ptm base model is among the "
                         "highest-variance arms in the corpus), so any global, per-family or "
                         "per-channel-standardised threshold flags the family rather than the "
                         "fault. A runaway is a SLOPE, and a slope needs no cross-arm calibration.")
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--out", default=None)
    ap.add_argument("--max-arms", type=int, default=0)
    a = ap.parse_args()

    sample = sample_paths(a.per_arm, a.seed)
    arms = sorted(sample)
    if a.max_arms:
        arms = arms[:a.max_arms]
    print(f"[audit] {len(arms)} arms, up to {a.per_arm} clips each", flush=True)

    rows, allchan = [], []
    for i, arm in enumerate(arms):
        for p in sample[arm]:
            m = measure(p, a.chan_k)
            if not m["finite"]:
                rows.append({"arm": arm, "ptm": is_ptm(arm), "finite": False,
                             "std": None, "n_over": 256, "chan_max": None})
                continue
            rows.append({"arm": arm, "ptm": is_ptm(arm), "finite": True,
                         "std": m["std"], "n_over": m["n_over"], "chan_max": m["chan_max"]})
            allchan.append(m["chan"])
        if (i + 1) % 25 == 0:
            print(f"  ..{i+1}/{len(arms)} arms", flush=True)

    fin = [r for r in rows if r["finite"]]
    print(f"[audit] {len(rows)} clips measured, {len(rows)-len(fin)} non-finite")

    if a.calibrate and allchan:
        C = np.concatenate(allchan)
        # A channel threshold should sit ABOVE what healthy channels do, not at a number
        # borrowed from a different statistic. Healthy = clips whose GLOBAL std is under 1.5,
        # which is well below the gate and comfortably non-runaway in every family.
        healthy = np.concatenate([c for c, r in zip(allchan, fin) if r["std"] < 1.5]) \
            if any(r["std"] < 1.5 for r in fin) else C
        print("\n[calibrate] per-channel std over ALL sampled clips:")
        for q in (50, 90, 99, 99.9):
            print(f"   p{q:<5} corpus {np.percentile(C, q):7.3f}   healthy-only "
                  f"{np.percentile(healthy, q):7.3f}")
        print("\n[calibrate] separation by candidate chan-k "
              "(ptm vs non-ptm medians, and the worst arm):")
        print(f"   {'k':>5} {'ptm med':>8} {'nonptm med':>11} {'p99 of arms':>12} {'worst arm':>10}")
        for k in (1.5, 2.0, 2.5, 3.0, 3.5, 4.0):
            over = [int((c > k).sum()) for c in allchan]
            pt = [o for o, r in zip(over, fin) if r["ptm"]]
            np_ = [o for o, r in zip(over, fin) if not r["ptm"]]
            print(f"   {k:5.1f} {np.median(pt) if pt else -1:8.1f} "
                  f"{np.median(np_) if np_ else -1:11.1f} "
                  f"{np.percentile(over, 99):12.1f} {max(over):10d}")

    if a.standardize and allchan:
        # Per-channel, per-family baseline from HEALTHY clips only (global std < 1.5, well
        # under the gate in every family). Median + MAD rather than mean + sd, because the
        # sample we are calibrating on contains the very runaways we want to detect.
        A = np.vstack(allchan)                       # (n_clips, 256)
        fam = np.array([r["ptm"] for r in fin])
        healthy = np.array([r["std"] < 1.5 for r in fin])
        base = {}
        for is_p in (True, False):
            sel = fam == is_p
            h = sel & healthy
            src = A[h] if h.sum() >= 30 else A[sel]
            med = np.median(src, axis=0)
            mad = np.median(np.abs(src - med), axis=0) * 1.4826      # -> sigma-equivalent
            base[is_p] = (med, np.maximum(mad, 1e-6))
            print(f"[standardize] {'ptm' if is_p else 'non-ptm'} baseline from "
                  f"{int(h.sum()) if h.sum()>=30 else int(sel.sum())} clips: "
                  f"per-channel median {med.mean():.3f} avg, robust sigma {mad.mean():.3f} avg")
        n_std = np.zeros(len(fin), dtype=int)
        for i, r in enumerate(fin):
            med, sig = base[r["ptm"]]
            n_std[i] = int((A[i] > med + a.std_k * sig).sum())
        for i, r in enumerate(fin):
            r["n_over_std"] = int(n_std[i])
        pt_i = [i for i, r in enumerate(fin) if r["ptm"]]
        np_i = [i for i, r in enumerate(fin) if not r["ptm"]]
        fl = lambda idx: 100.0 * sum(1 for i in idx if n_std[i] > 0) / max(1, len(idx))
        print(f"\n[standardize] channels over {a.std_k} robust sigma of their own family "
              f"baseline:")
        print(f"   ptm     p50/p90/p99 "
              f"{np.percentile(n_std[pt_i],50):.0f}/{np.percentile(n_std[pt_i],90):.0f}/"
              f"{np.percentile(n_std[pt_i],99):.0f}   flagged {fl(pt_i):5.2f}%")
        print(f"   non-ptm p50/p90/p99 "
              f"{np.percentile(n_std[np_i],50):.0f}/{np.percentile(n_std[np_i],90):.0f}/"
              f"{np.percentile(n_std[np_i],99):.0f}   flagged {fl(np_i):5.2f}%")
        print(f"   family bias {fl(pt_i)/max(fl(np_i),1e-9):.2f}x "
              "(global std>2.0 was 4.84x, fixed chan-k 2.0 was 5.92x)")
        for i, r in enumerate(fin):
            per_arm_key = r["arm"]
        # worst arms under the standardized count
        agg = collections.defaultdict(list)
        for i, r in enumerate(fin):
            agg[r["arm"]].append(n_std[i])
        worst = sorted(((np.median(v), max(v), k) for k, v in agg.items()), reverse=True)[:12]
        print(f"\n[standardize] worst 12 arms by standardized blown-channel count:")
        for med_, max_, k in worst:
            print(f"   {k[:52]:<52} med {med_:5.0f}  max {max_:4d}")

    # THE CONTRAST THAT IS THE WHOLE ARGUMENT: what each statistic does across families.
    # A good divergence statistic should be family-NEUTRAL (ptm and non-ptm alike when both
    # are healthy) and still separate broken from healthy. Global std fails the first half.
    pt = [r for r in fin if r["ptm"]]
    npm = [r for r in fin if not r["ptm"]]
    if pt and npm:
        print("\n[contrast] family neutrality of each statistic "
              f"(ptm n={len(pt)}, non-ptm n={len(npm)}):")
        gs_p = np.percentile([r["std"] for r in pt], [50, 90, 99])
        gs_n = np.percentile([r["std"] for r in npm], [50, 90, 99])
        ch_p = np.percentile([r["n_over"] for r in pt], [50, 90, 99])
        ch_n = np.percentile([r["n_over"] for r in npm], [50, 90, 99])
        print(f"   global z0 std      ptm p50/p90/p99 {gs_p[0]:.2f}/{gs_p[1]:.2f}/{gs_p[2]:.2f}"
              f"   non-ptm {gs_n[0]:.2f}/{gs_n[1]:.2f}/{gs_n[2]:.2f}")
        print(f"   blown-channel cnt  ptm p50/p90/p99 {ch_p[0]:.0f}/{ch_p[1]:.0f}/{ch_p[2]:.0f}"
              f"      non-ptm {ch_n[0]:.0f}/{ch_n[1]:.0f}/{ch_n[2]:.0f}")
        over_gate = lambda rs: 100.0 * sum(1 for r in rs if r["std"] > 2.0) / len(rs)
        over_chan = lambda rs: 100.0 * sum(1 for r in rs if r["n_over"] > 0) / len(rs)
        print(f"   %% flagged by std>2.0      ptm {over_gate(pt):5.2f}   non-ptm {over_gate(npm):5.2f}"
              "   <- family-dependent, the defect")
        print(f"   %% flagged by any channel  ptm {over_chan(pt):5.2f}   non-ptm {over_chan(npm):5.2f}")

    # per-arm rollup, worst first by channel count
    per_arm = collections.defaultdict(list)
    for r in rows:
        per_arm[r["arm"]].append(r)
    roll = []
    for arm, rs in per_arm.items():
        f = [r for r in rs if r["finite"]]
        roll.append({"arm": arm, "ptm": rs[0]["ptm"], "n": len(rs),
                     "nonfinite": len(rs) - len(f),
                     "median_std": float(np.median([r["std"] for r in f])) if f else None,
                     "median_chans": float(np.median([r["n_over"] for r in f])) if f else None,
                     "max_chans": max([r["n_over"] for r in rs])})
    roll.sort(key=lambda d: (-(d["median_chans"] if d["median_chans"] is not None else 1e9),
                             -(d["median_std"] if d["median_std"] is not None else 0.0)))
    print(f"\n[audit] worst 15 arms by blown-channel count (chan-k {a.chan_k}):")
    print(f"   {'arm':<44} {'ptm':>4} {'medstd':>7} {'medch':>6} {'maxch':>6}")
    for d in roll[:15]:
        ms = d["median_std"]
        mc = d["median_chans"]
        print(f"   {d['arm'][:44]:<44} {str(d['ptm']):>4} "
              f"{('n/a' if ms is None else f'{ms:.2f}'):>7} "
              f"{('n/a' if mc is None else f'{mc:.0f}'):>6} "
              f"{d['max_chans']:6d}")

    if a.trajectory:
        # split "<arm>__ep<N>" into (run, epoch) and look at the run's own std over epochs
        traj = collections.defaultdict(dict)
        for arm, rs in per_arm.items():
            m = re.match(r"^(.*)__ep(\d+)$", arm)
            if not m:
                continue
            f = [r for r in rs if r["finite"]]
            if not f:
                continue
            traj[m.group(1)][int(m.group(2))] = float(np.median([r["std"] for r in f]))
        multi = {k: v for k, v in traj.items() if len(v) >= 3}
        print(f"\n[trajectory] {len(multi)} runs with >=3 epochs sampled")
        rows_t = []
        for run, eps in multi.items():
            ks = sorted(eps)
            first, last = eps[ks[0]], eps[ks[-1]]
            peak = max(eps.values())
            rows_t.append((peak / max(first, 1e-9), last / max(first, 1e-9),
                           first, last, peak, ks[0], ks[-1], run))
        rows_t.sort(reverse=True)
        print(f"   {'run':<46} {'ep':>7} {'first':>6} {'last':>7} {'peak':>7} {'peak/1st':>9}")
        for pr, lr, first, last, peak, k0, k1, run in rows_t[:12]:
            print(f"   {run[:46]:<46} {k0:>3}->{k1:<3} {first:6.2f} {last:7.2f} "
                  f"{peak:7.2f} {pr:9.2f}x")
        ratios = np.array([r[0] for r in rows_t])
        print(f"\n   peak/first ratio across runs: p50 {np.percentile(ratios,50):.2f}x  "
              f"p90 {np.percentile(ratios,90):.2f}x  p99 {np.percentile(ratios,99):.2f}x  "
              f"max {ratios.max():.2f}x")
        for thr in (1.5, 2.0, 3.0, 5.0):
            n = int((ratios > thr).sum())
            print(f"   runs with peak/first > {thr}x: {n} of {len(ratios)} "
                  f"({100.0*n/len(ratios):.1f}%)")

    if a.out:
        json.dump({"chan_k": a.chan_k, "per_arm": a.per_arm, "seed": a.seed,
                   "arms": roll}, open(a.out, "w"), indent=1)
        print(f"\n[audit] wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
