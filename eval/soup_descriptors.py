#!/usr/bin/env python3
"""Descriptor readout for the PT->base soup ladder — CONTINUITY 2026-09-07.

Answers ONE falsifiable question: does an intermediate alpha land BETWEEN the two
endpoints in audio-descriptor space (interpolation), or outside them (off-manifold)?

It does NOT score quality. "Punchy but varied" is Kim's ear, not a number here.

⚠ SELF-GATE (audit-the-instrument-first). A descriptor is only reported if it separates
the base and PT endpoints by more than the prompt-to-prompt spread WITHIN an endpoint.
A descriptor that cannot tell the two ends apart cannot say anything about a midpoint,
and printing its blend values anyway is how a ceiling gets reported as a finding.

⚠ Compare only WITHIN one sampler. PT is diffusion_objective 'rf_denoiser' (native
pingpong), base is 'rectified_flow' (euler), and every blend loads medium-base's config
-- so a cross-sampler delta is a sampler delta, not a weight delta.

  eval/soup_descriptors.py --dir ~/evals_aac/soup_rewind
"""
import argparse, json, re, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from disintegration_metrics import measure

PAT = re.compile(r"^(?P<arm>.+?)__(?P<prompt>goa|psy|break)__st(?P<steps>\d+)__cfg(?P<cfg>[\d.]+)\.wav$")


def sampler_of(arm, meta):
    if meta.get("sampler"):
        return meta["sampler"]
    return "pingpong" if arm.endswith("_pingpong") else "euler"


def base_arm(arm):
    a = re.sub(r"_(pingpong|euler)$", "", arm)
    return re.sub(r"^endpoint_(base|pt)$", r"endpoint_\1", a)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, required=True)
    ap.add_argument("--json", type=Path)
    a = ap.parse_args()

    rows = []
    for w in sorted(a.dir.glob("*.wav")):
        m = PAT.match(w.name)
        if not m:
            print(f"  ! unparsed filename, skipped: {w.name}")
            continue
        j = w.with_suffix(".json")
        meta = json.loads(j.read_text()) if j.exists() else {}
        arm = m["arm"]
        rows.append(dict(arm=base_arm(arm), sampler=sampler_of(arm, meta),
                         prompt=m["prompt"], steps=int(m["steps"]), **measure(w)))
    if not rows:
        sys.exit("no wavs parsed")

    KEYS = ["onsets", "flatness", "zcr", "hf"]
    out = {}
    for sampler in sorted({r["sampler"] for r in rows}):
        for steps in sorted({r["steps"] for r in rows}):
            sel = [r for r in rows if r["sampler"] == sampler and r["steps"] == steps]
            arms = sorted({r["arm"] for r in sel})
            ends = [e for e in ("endpoint_base", "endpoint_pt") if e in arms]
            print(f"\n=== sampler={sampler} steps={steps}  ({len(sel)} clips, arms: {', '.join(arms)})")
            if len(ends) < 2:
                print("  SKIP: both endpoints required to judge betweenness "
                      f"(have {ends or 'none'})")
                continue

            def vals(arm, k):
                return np.array([r[k] for r in sel if r["arm"] == arm])

            for k in KEYS:
                b, p = vals("endpoint_base", k), vals("endpoint_pt", k)
                spread = max(b.std(), p.std())          # within-endpoint, across prompts
                sep = abs(b.mean() - p.mean())
                if sep <= spread:
                    print(f"  {k:9s} MUTE: base {b.mean():.4f} vs pt {p.mean():.4f} "
                          f"(sep {sep:.4f} <= within-endpoint spread {spread:.4f}) "
                          f"-- cannot resolve a midpoint, not reported")
                    continue
                print(f"  {k:9s} base {b.mean():.4f} -> pt {p.mean():.4f}  (sep {sep:.4f}, spread {spread:.4f})")
                for arm in arms:
                    if arm.startswith("endpoint_"):
                        continue
                    v = vals(arm, k).mean()
                    lo, hi = sorted((b.mean(), p.mean()))
                    frac = (v - b.mean()) / (p.mean() - b.mean())
                    where = "between" if lo <= v <= hi else "OUTSIDE"
                    print(f"      {arm:14s} {v:.4f}  {where:8s} frac_toward_pt={frac:+.2f}")
                    out.setdefault(f"{sampler}/st{steps}/{k}", {})[arm] = dict(
                        value=float(v), frac_toward_pt=float(frac), between=(where == "between"))
    if a.json:
        a.json.write_text(json.dumps(out, indent=1))
        print(f"\nwrote {a.json}")


if __name__ == "__main__":
    main()
