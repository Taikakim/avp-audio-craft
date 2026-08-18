#!/usr/bin/env python3
"""compare_trajectory_stats.py — put many runs' weight trajectories side by side and flag the ones
that do not converge.

WHY (C, 2026-08-18): checkpoint_trajectory_stats.py answers "what did THIS run do". The question
that actually comes up is comparative — "these four arms render broken, do their WEIGHTS look
different from the arms that render fine?" — and answering it meant hand-rolling the same pandas-less
table three times in one evening. Weight-space evidence is worth having because it is independent of
every audio metric: it cannot be confounded by a saturated measure, a mis-tokenised prompt, or a
caption problem, all three of which bit us the same day.

THE HEALTHY BAND, measured across 19 completed runs that Kim judged fine (2026-08-18):
    velocity ratio  vN/v0   0.49 - 0.55   (adapters)   0.21 - 0.54 (full-FT)
    path efficiency         0.65 - 0.75
    norm growth             1.57 - 2.37   (adapters)   ~1.00       (full-FT)
Those are empirical, not theoretical: the point is that healthy runs cluster tightly, so an arm
outside the cluster is worth looking at even without a threshold anyone can defend from first
principles.

WHAT THE FLAGS MEAN
    RISING-VEL   velocity is not decaying (vN/v0 >= 1.0). The run was still moving as fast at the
                 end as at the start — no convergence. With an orthogonalised (Muon/NS5) update this
                 is the expected signature of late-training drift with nothing damping it.
    LOW-EFF      path efficiency well below the band: the run wandered far to get nowhere, i.e. it
                 oscillated. Argues for averaging (EMA / checkpoint soup) rather than for a different
                 optimizer.
    HIGH-EFF     efficiency near 1.0 — a straight line. Healthy early, suspicious late: a run that
                 never curves is usually one that is marching in a single direction, which is what
                 runaway looks like before it diverges.
    NORM-BLOWUP  trainable-norm growth far above the band.

USAGE
  python3 eval/compare_trajectory_stats.py checkpoint-stats/ checkpoint-stats-lumi/
  python3 eval/compare_trajectory_stats.py <dirs...> --grep dronesweep --sort vel
Only stdlib.
"""
import argparse
import json
import os
from pathlib import Path

BAND_VEL = (0.15, 0.80)      # vN/v0
BAND_EFF = (0.60, 0.80)      # net displacement / path length


def load(dirs):
    """One row per run. Later dirs win on duplicate labels, but the collision is REPORTED — the same
    label computed from two different checkpoint copies is exactly the silent-overwrite shape that
    cost us a checkpoint this morning."""
    out, seen = {}, {}
    for d in dirs:
        for p in sorted(Path(d).glob("*_trajectory.json")):
            label = p.name.replace("_trajectory.json", "")
            try:
                j = json.load(open(p))
            except Exception as e:
                print(f"[warn] unreadable {p}: {e}")
                continue
            R = j.get("rows") or []
            if len(R) < 3:
                continue
            if label in out:
                seen.setdefault(label, []).append(str(p))
            g = [r["global_norm"] for r in R]
            v = [r["d_from_prev"] for r in R[1:]]
            s = j.get("summary") or {}
            out[label] = dict(
                label=label, src=str(d), n=len(R), g0=g[0], gN=g[-1],
                grow=g[-1] / g[0] if g[0] else 0.0,
                v0=v[0] if v else 0.0, vN=v[-1] if v else 0.0,
                vr=(v[-1] / v[0]) if v and v[0] else 0.0,
                eff=s.get("path_efficiency"), ckpt_dir=j.get("ckpt_dir", ""))
    for label, paths in seen.items():
        print(f"[warn] duplicate label {label!r} seen in multiple dirs; kept the last. "
              f"Others: {paths}")
    return list(out.values())


def flags(r):
    f = []
    if r["vr"] >= 1.0:
        f.append("RISING-VEL")
    if r["eff"] is not None and r["eff"] < BAND_EFF[0]:
        f.append("LOW-EFF")
    if r["eff"] is not None and r["eff"] > 0.90:
        f.append("HIGH-EFF")
    if r["grow"] > 3.0:
        f.append("NORM-BLOWUP")
    return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--grep", default=None, help="substring filter on the run label")
    ap.add_argument("--sort", default="vel", choices=("vel", "eff", "grow", "name"))
    a = ap.parse_args()

    rows = load(a.dirs)
    if a.grep:
        rows = [r for r in rows if a.grep.lower() in r["label"].lower()]
    if not rows:
        print("no trajectories matched")
        return 1
    key = {"vel": lambda r: -r["vr"], "eff": lambda r: (r["eff"] or 0),
           "grow": lambda r: -r["grow"], "name": lambda r: r["label"]}[a.sort]
    rows.sort(key=key)

    print(f"{'run':<44} {'n':>3} {'grow':>5} {'v_first':>8} {'v_last':>8} {'vN/v0':>6} {'eff':>5}  flags")
    print("-" * 108)
    n_flagged = 0
    for r in rows:
        f = flags(r)
        n_flagged += bool(f)
        eff = f"{r['eff']:.3f}" if r["eff"] is not None else "  -  "
        print(f"{r['label']:<44} {r['n']:>3} {r['grow']:>5.2f} {r['v0']:>8.1f} {r['vN']:>8.1f} "
              f"{r['vr']:>6.2f} {eff:>5}  {' '.join(f)}")
    print(f"\n{len(rows)} run(s), {n_flagged} flagged")
    print(f"healthy band (empirical, 19 runs Kim judged fine): vN/v0 {BAND_VEL[0]}-{BAND_VEL[1]}, "
          f"eff {BAND_EFF[0]}-{BAND_EFF[1]}")
    print("A run inside the band is NOT certified good — these are weight statistics and say nothing")
    print("about what it sounds like. They are only evidence about whether the OPTIMISER converged,")
    print("which is the specific question renders cannot answer.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
