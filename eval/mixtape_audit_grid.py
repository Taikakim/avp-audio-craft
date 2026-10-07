#!/usr/bin/env python
"""mixtape_audit_grid.py — v7 phase 0 gate 2: do the beats keep their spacing across every transition?

WHY (GHOST-NOTE 2026-10-07, spec docs/superpowers/specs/2026-10-07-dj-mix-v7-transitions-spec.md gate 2).
mixtape_audit_continuity.py checks WHERE in its source each part of the mix comes from; it cannot see a beat
grid that slips or bends at a splice (clean audio, right clip, wrong phase). This audit runs madmom raw beats
(mir venv, via the repo's beat_grid CLI) on the FINISHED mix and, for each transition window plus a margin,
compares every inter-beat interval to the local reference tempo (the median interval of that region).

PASS: every interval within +-TOL ms (default 15) of the reference. NOTE the beat sidecar is on a 10 ms grid, so
a single interval can differ from the truth by up to ~10 ms through rounding alone; --tol 15 leaves 5 ms for a
real slip. A phase JUMP at a splice shows as one long/short interval; a tempo ramp as a run of drifting ones.

USAGE  .venv/bin/python eval/mixtape_audit_grid.py --mix MIX.wav --timeline timeline.json [--tol 15]
          [--margin 6] [--beats cache.npy] [--json OUT.json]
Exit code 1 if any transition has an interval outside tolerance. Run from a dir that is not the SAO root.
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dj_beatmatch import MIR_MADMOM_PY, MIR_REPO_ROOT  # noqa: E402


def mix_beats(mix_wav):
    with tempfile.TemporaryDirectory(prefix="grid_") as td:
        link = Path(td) / "mix.wav"
        link.symlink_to(Path(mix_wav).resolve())
        subprocess.run([MIR_MADMOM_PY, "-m", "src.rhythm.beat_grid", str(link), "--method", "madmom"],
                       cwd=MIR_REPO_ROOT, capture_output=True, text=True)
        p = Path(td) / f"{Path(td).name}.BEATS_GRID"
        if not p.exists():
            raise SystemExit("beat_grid produced no BEATS_GRID sidecar")
        return np.atleast_1d(np.loadtxt(str(p)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mix", required=True)
    ap.add_argument("--timeline", required=True)
    ap.add_argument("--tol", type=float, default=15.0, help="ms")
    ap.add_argument("--margin", type=float, default=6.0, help="seconds either side of the window")
    ap.add_argument("--beats", default=None, help="cache: a .npy of beat times to reuse")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    tl = json.loads(Path(a.timeline).read_text())
    if a.beats and Path(a.beats).exists():
        beats = np.load(a.beats)
    else:
        beats = mix_beats(a.mix)
        if a.beats:
            np.save(a.beats, beats)
    rows, bad = [], 0
    for k, (t0, t1) in enumerate(tl["trans"]):
        sel = beats[(beats >= t0 - a.margin) & (beats <= t1 + a.margin)]
        if len(sel) < 6:
            rows.append({"trans": k, "n_beats": int(len(sel)), "note": "too few beats detected"})
            bad += 1
            continue
        ibi = np.diff(sel)
        ref = float(np.median(ibi))
        dev = 1000 * (ibi - ref)
        worst = float(np.abs(dev).max())
        n_out = int((np.abs(dev) > a.tol).sum())
        bad += int(n_out > 0)
        rows.append({"trans": k, "t0": t0, "t1": t1, "n_beats": int(len(sel)), "ref_bpm": 60.0 / ref,
                     "worst_ms": worst, "n_out": n_out})
    worst_all = max((r.get("worst_ms", 0) for r in rows), default=0)
    print(f"{len(rows)} transitions, {bad} with an interval outside +-{a.tol:.0f} ms; worst {worst_all:.1f} ms")
    for r in rows:
        if r.get("n_out") or "note" in r:
            print("  ", r)
    if a.json:
        Path(a.json).write_text(json.dumps({"tol_ms": a.tol, "bad": bad, "rows": rows}, indent=1))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
