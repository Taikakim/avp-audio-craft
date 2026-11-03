"""Consolidate ALL onset_eval control-response stats across the big sweep into a single
committed CSV + JSON. One row per eval dir: control authority, slope, per-gain corr,
output range, and run provenance (from run_meta.json where present)."""
import glob, json, os, csv, numpy as np

R = "/run/media/kim/Mantu/sa3_control_runs"
OUT = "/home/kim/riffer-evals/stats"
os.makedirs(OUT, exist_ok=True)

def group_of(name):
    for g in ("lr2e5", "lr8e5", "adamw20", "opb"):
        if g in name: return g
    return "targeted"

def stats(evdir):
    rows = json.load(open(f"{evdir}/onset_eval.json"))
    gains = sorted({r["gain"] for r in rows})
    best, bg, bslope = -2.0, None, 0.0
    per_gain = {}
    meas = [r["measured"] for r in rows]
    for g in gains:
        gr = [r for r in rows if r["gain"] == g]
        xs = [r["requested"] for r in gr]; ys = [r["measured"] for r in gr]
        if len(set(xs)) > 1:
            c = float(np.corrcoef(xs, ys)[0, 1]); per_gain[f"g{g:g}"] = round(c, 3)
            if c > best: best, bg, bslope = c, g, float(np.polyfit(xs, ys, 1)[0])
    rec = {"authority": round(best, 3), "best_gain": bg, "slope": round(bslope, 2),
           "n_pts": len(rows), "meas_min": round(min(meas), 1), "meas_max": round(max(meas), 1)}
    mp = f"{evdir}/run_meta.json"
    if os.path.exists(mp):
        m = json.load(open(mp)); tr = m.get("train", {}) or {}
        rec.update({"scalar_field": m.get("scalar_field"), "lr": tr.get("lr"),
                    "optimizer": tr.get("optimizer"), "notes": (m.get("notes") or "")[:90]})
    rec["per_gain"] = per_gain
    return rec

recs = []
for j in sorted(glob.glob(f"{R}/**/onset_eval.json", recursive=True)):
    d = os.path.dirname(j); name = os.path.relpath(d, R)
    try:
        s = stats(d); s["dir"] = name; s["group"] = group_of(name); recs.append(s)
    except Exception as e:
        print(f"skip {name}: {e}")

recs.sort(key=lambda r: (r["group"], r["dir"]))
cols = ["group", "dir", "authority", "best_gain", "slope", "meas_min", "meas_max", "n_pts",
        "scalar_field", "lr", "optimizer", "notes"]
with open(f"{OUT}/big_sweep_stats.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader()
    for r in recs: w.writerow(r)
json.dump(recs, open(f"{OUT}/big_sweep_stats.json", "w"), indent=1)

by_group = {}
for r in recs: by_group.setdefault(r["group"], []).append(r["authority"])
print(f"{len(recs)} eval dirs consolidated -> stats/big_sweep_stats.{{csv,json}}")
for g, a in sorted(by_group.items()):
    print(f"  {g:9s}: {len(a):2d} dirs  authority {min(a):+.2f}..{max(a):+.2f}  median {np.median(a):+.2f}")
