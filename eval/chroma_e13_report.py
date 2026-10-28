#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-28)
"""chroma_e13_report.py -- EXPERIMENTS E13 numbers from the finished renders (CPU, no re-render).

Reads OUT/cells.jsonl (chroma measured by eval/chroma_e13_render.py) and clip_metrics.db (texture + Audiobox), applies the
disintegration gate (control_head_disintegration_eval.gate(), unchanged thresholds, plus the latent-level leg from z_std)
to every steered clip against its same-prompt, same-seed unguided render, and writes OUT/report.json + OUT/report.txt:
  screen   per weight set at gain 2048: change in frame-wise cos (bass, mid) and strongest-class hit vs the unguided render
  ladder   per head x gain: the same, with gate failures; usable ceiling = highest gain with at least 75% of cells clean
  paired   each retrained ladder head vs the production head at equal gain, same prompt/target/seed: mean difference and
           win fraction in d_fcos (bass+mid)/2, gate-clean pairs only
Also stores the summary in OUT/run_meta.json "result". RUN: mir/bin/python eval/chroma_e13_report.py
"""
import json
import sqlite3
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from control_head_disintegration_eval import DB, gate  # noqa: E402

OUT = Path("/home/kim/evals_aac/control_runs/chroma_e13_20261028")
CLEAN_FRAC = 0.75


def mean(xs):
    return round(st.mean(xs), 4) if xs else None


def main():
    cells = [json.loads(l) for l in (OUT / "cells.jsonl").read_text().splitlines() if l.strip()]
    db = sqlite3.connect(DB)
    cols = [r[1] for r in db.execute("PRAGMA table_info(metrics)").fetchall()]
    rows = {r[0]: dict(zip(cols, r)) for r in db.execute("select * from metrics where path like ?", (f"{OUT}/%",))}
    base = {}
    for c in cells:
        c["metrics"] = rows.get(str(OUT / c["clip"]))
        if c["gain"] == 0:
            base[(c["prompt"], c["seed"])] = c
    missing = sum(1 for c in cells if c["metrics"] is None)
    if missing:
        print(f"WARNING {missing} of {len(cells)} clips have no clip_metrics row; their gate uses the latent leg only")

    def delta(c):
        b = base[(c["prompt"], c["seed"])]
        m, mb = c["m"][c["target"]], b["m"][c["target"]]
        return {k: m[band][f] - mb[band][f] for band in ("bass", "mid") for f in ("fcos", "hit")
                for k in [f"{band}_{f}"]}

    def gate_of(c):
        b = base[(c["prompt"], c["seed"])]
        if c["metrics"] and b["metrics"]:
            bad, why, _ = gate({**c["metrics"], "z_std": c["z_std"]}, {**b["metrics"], "z_std": b["z_std"]},
                               rhythmic=c["prompt"] == "goa")
            return bad, why
        bad = c["z_std"] / b["z_std"] > 1.3
        return bad, ["latent-level"] if bad else []

    steered = [c for c in cells if c["gain"] > 0 and (c["prompt"], c["seed"]) in base]
    for c in steered:
        c["d"] = delta(c)
        c["bad"], c["why"] = gate_of(c)

    lines, report = [], {}
    # screen
    by = defaultdict(list)
    for c in steered:
        if c["stage"] == "screen":
            by[c["head"]].append(c)
    scr = []
    for h, cs in by.items():
        scr.append({"head": h, "n": len(cs), "fails": sum(c["bad"] for c in cs),
                    **{k: mean([c["d"][k] for c in cs]) for k in ("bass_fcos", "mid_fcos", "bass_hit", "mid_hit")}})
    scr.sort(key=lambda r: -((r["bass_fcos"] or 0) + (r["mid_fcos"] or 0)))
    report["screen"] = scr
    lines.append("SCREEN, gain 2048: change vs the unguided render (mean over prompts x targets x seeds)")
    lines.append(f"{'head':22s} {'n':>3s} {'fail':>4s} {'d_cos bass':>10s} {'d_cos mid':>9s} {'d_hit bass':>10s} {'d_hit mid':>9s}")
    for r in scr:
        lines.append(f"{r['head']:22s} {r['n']:3d} {r['fails']:4d} {r['bass_fcos']:+10.4f} {r['mid_fcos']:+9.4f} "
                     f"{r['bass_hit']:+10.4f} {r['mid_hit']:+9.4f}")
    # ladder
    lad = defaultdict(list)
    for c in steered:
        if c["stage"] == "ladder":
            lad[(c["head"], c["gain"])].append(c)
    heads = sorted({h for h, _ in lad}, key=lambda h: (h != "prod", h))
    gains = sorted({g for _, g in lad})
    report["ladder"], report["ceiling"] = [], {}
    lines.append("\nLADDER: per head x gain (mean over 3 prompts x 4 targets x 4 seeds); fail = disintegration gate")
    lines.append(f"{'head':22s} {'gain':>5s} {'n':>3s} {'fail':>4s} {'d_cos bass':>10s} {'d_cos mid':>9s} {'d_hit mid':>9s}  top reasons")
    for h in heads:
        ceiling = 0
        for g in gains:
            cs = lad.get((h, g), [])
            if not cs:
                continue
            fails = sum(c["bad"] for c in cs)
            reasons = defaultdict(int)
            for c in cs:
                for w in c["why"]:
                    reasons[w.split("(")[0]] += 1
            r = {"head": h, "gain": g, "n": len(cs), "fails": fails, "reasons": dict(reasons),
                 **{k: mean([c["d"][k] for c in cs]) for k in ("bass_fcos", "mid_fcos", "bass_hit", "mid_hit")},
                 "clean_mid_fcos": mean([c["d"]["mid_fcos"] for c in cs if not c["bad"]])}
            report["ladder"].append(r)
            if (len(cs) - fails) / len(cs) >= CLEAN_FRAC:
                ceiling = g
            top = ", ".join(f"{k} {v}" for k, v in sorted(reasons.items(), key=lambda kv: -kv[1])[:3])
            lines.append(f"{h:22s} {g:5d} {len(cs):3d} {fails:4d} {r['bass_fcos']:+10.4f} {r['mid_fcos']:+9.4f} {r['mid_hit']:+9.4f}  {top}")
        report["ceiling"][h] = ceiling
    lines.append("\nUSABLE CEILING (highest gain with >= 75% of cells gate-clean): "
                 + ", ".join(f"{h} {g}" for h, g in report["ceiling"].items()))
    # paired vs prod
    key = lambda c: (c["prompt"], c["target"], c["seed"], c["gain"])  # noqa: E731
    prod = {key(c): c for c in steered if c["stage"] == "ladder" and c["head"] == "prod"}
    report["paired"] = []
    lines.append("\nPAIRED vs the production head, same prompt/target/seed/gain, both gate-clean: mean diff of d_cos (bass+mid)/2, win share")
    for h in heads:
        if h == "prod":
            continue
        for g in gains:
            diffs = []
            for c in lad.get((h, g), []):
                p = prod.get(key(c))
                if p and not c["bad"] and not p["bad"]:
                    diffs.append(((c["d"]["bass_fcos"] + c["d"]["mid_fcos"]) - (p["d"]["bass_fcos"] + p["d"]["mid_fcos"])) / 2)
            if diffs:
                win = sum(d > 0 for d in diffs) / len(diffs)
                report["paired"].append({"head": h, "gain": g, "n": len(diffs), "mean_diff": mean(diffs), "win": round(win, 3)})
                lines.append(f"{h:22s} {g:5d} n={len(diffs):3d} diff {mean(diffs):+.4f} win {win:.2f}")
    txt = "\n".join(lines)
    (OUT / "report.txt").write_text(txt + "\n")
    (OUT / "report.json").write_text(json.dumps(report, indent=1))
    meta_p = OUT / "run_meta.json"
    meta = json.loads(meta_p.read_text()) if meta_p.exists() else {}
    meta["result"] = {"ceiling": report["ceiling"], "screen_top": scr[:5], "paired": report["paired"],
                      "report": str(OUT / "report.txt")}
    meta_p.write_text(json.dumps(meta, indent=1))
    print(txt)


if __name__ == "__main__":
    main()
