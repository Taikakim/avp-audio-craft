#!/usr/bin/env python3
"""headb_bracket_rollup.py — roll the 48 per-cell results.json (from melody_pilot_eval.py
analyze) into ONE bracket_summary.tsv. One row per (ckpt, cfg, gain):

  adopt_act   mean conditioned-clip adoption of its OWN motif stream, active frames only
              (adopt_active = share of has-a-lead frames whose contour class matches the
              conditioning stream at the best shift).
  null_floor  empirical by-chance floor = mean over the null (all-rest) clips of their mean
              adoption across all four motif streams, active frames only. This is what
              "adoption" scores with NO conditioning — the number adopt_act must clear.
  margin      adopt_act - null_floor. The steering signal. >0 and clearly so = the head
              moves the melody toward the requested contour beyond chance.
  gates       conditioned clips passing the disintegration gate (clean) / total conditioned.
              A high margin with blown gates = buzz, not melody — discount it.
  z0_cos      mean cosine(cond z0, seed-matched null z0). <1 = conditioning changed the
              latent at all (causal check); ~1 = the adapter did nothing.
  lead_cov    mean fraction of frames with ANY rendered lead (low = "no lead to adopt").

Reads: <ROOT>/*/results.json . Prints TSV to stdout (the driver tees it to bracket_summary.tsv).
CPU/stdlib only.
"""
import glob
import json
import os
import re
import sys
from statistics import mean

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."


def num(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return mean(xs) if xs else None


def fmt(x):
    return f"{x:.3f}" if isinstance(x, (int, float)) else ""


rows = []
for res in glob.glob(os.path.join(ROOT, "*", "results.json")):
    cell = os.path.basename(os.path.dirname(res))
    m = re.match(r"(.+)_cfg([0-9.]+)_g([0-9.]+)$", cell)
    if not m:
        continue
    ck, cfg, gain = m.group(1), m.group(2), m.group(3)
    try:
        data = json.load(open(res))
    except Exception:
        continue
    cond = [r for r in data if r.get("conditioned")]
    null = [r for r in data if not r.get("conditioned")]

    adopt = num([r.get("adopt_active") for r in cond])
    # CONFUSION test (cfg-robust): per conditioned clip, own-target adoption (adopt_active) vs
    # the mean of the three NON-requested streams (xtarg_<t>_active). conf = own - wrong; >0 =
    # the render tracks the REQUESTED contour more than the others = real steering, no null needed.
    wvals = []
    for r in cond:
        ks = [k for k in r if k.startswith("xtarg_") and k.endswith("_active")]
        v = num([r.get(k) for k in ks])
        if v is not None:
            wvals.append(v)
    wrong = mean(wvals) if wvals else None
    conf = (adopt - wrong) if (adopt is not None and wrong is not None) else None
    # null floor: each null clip's mean over its four null_<stream>_active values (secondary now)
    nvals = []
    for r in null:
        ks = [k for k in r if k.startswith("null_") and k.endswith("_active")]
        v = num([r.get(k) for k in ks])
        if v is not None:
            nvals.append(v)
    nfloor = mean(nvals) if nvals else None
    margin = (adopt - nfloor) if (adopt is not None and nfloor is not None) else None

    gates = [r.get("gate") for r in cond]
    clean = sum(1 for g in gates if g == "clean")
    z0 = num([r.get("z0_cos_vs_null") for r in cond])
    lead = num([r.get("lead_coverage") for r in cond])
    rows.append([ck, cfg, gain, adopt, wrong, conf, z0, lead, f"{clean}/{len(cond)}", nfloor, margin])


def ckey(r):
    mm = re.search(r"(\d+)", r[0])
    return (int(mm.group(1)) if mm else 10**9, float(r[1]), float(r[2]))


rows.sort(key=ckey)
hdr = ["ckpt", "cfg", "gain", "adopt_act", "wrong_act", "conf", "z0_cos", "lead_cov",
       "gates_clean", "null_floor", "margin"]
print("\t".join(hdr))
for r in rows:
    print("\t".join([r[0], r[1], r[2], fmt(r[3]), fmt(r[4]), fmt(r[5]),
                     fmt(r[6]), fmt(r[7]), r[8], fmt(r[9]), fmt(r[10])]))

if not rows:
    print("# no results.json found under " + ROOT + " (did phase-2 analyze run?)", file=sys.stderr)
