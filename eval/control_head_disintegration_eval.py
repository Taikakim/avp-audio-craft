#!/usr/bin/env python3
"""control_head_disintegration_eval.py — the MANDATORY disintegration gate for ANY control-head
evaluation (Kim directive 2026-07-20). See docs/superpowers/specs/2026-07-20-control-head-
disintegration-gate.md.

WHY THIS IS MANDATORY: a control head that renders static buzz still MOVES the feature meter
(noise = high flatness/ZCR/flux/HF), so a feature-authority metric alone scores buzz as "working."
Kim reviewed heads tagged working and heard buzz in both shift directions. So NO control-head
result (authority, steer-Δ, usable range, "this head works") may be reported without first passing
every steered clip through this gate against its unsteered baseline. Feature-moved ≠ musical.

WHAT IT CHECKS — per steered clip vs its SAME-PROMPT gain-0 (unsteered) baseline, all from
clip_metrics.db (no re-render):
  HARD flags (any one => disintegrated, clip excluded from authority):
    * whitening   — spectral flatness spikes (droning/noise bed)
    * hf-blowout  — hf_ratio spikes (the static-buzz signature the old bracket gate MISSED)
    * noise-zcr   — zero-crossing rate spikes (ringing/fizz)
    * beat-loss   — (rhythmic prompt only) onset density collapses AND bpm breaks
    * ce-drift    — Audiobox CE drifts too far from baseline (quality collapse), |ΔCE| > CE_DRIFT
  CORROBORATING (recorded, not fatal alone): centroid shift, crest change.

This is a TIGHTENED DSP screen, still not the ear. Thresholds are calibrated on the goa/ambient
sweep baselines but MUST be validated against Kim's one-by-one GUI verdicts; treat "clean" here as
"not obviously disintegrated by DSP," not "musically good." (memory: the ear is the verdict.)

Reusable: point --pattern at any control-head clip family already scored into clip_metrics.db whose
names follow {head}__{base|gN}__{pid}. Default runs the LatCH weight sweep and diffs the result
against the older, too-lenient latch_bracket_quality.json to show which heads FLIP to disintegrating.
"""
import argparse
import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

DB = Path(__file__).resolve().parent / "clip_metrics.db"

# baseline-drift thresholds. ratio = clip/baseline; absolute floors stop tiny-baseline ratios from
# firing on near-silence. Tuned on the sweep's goa(p0)/ambient(p1) gain-0 baselines 2026-07-20.
THR = {
    "flatness_ratio": 2.5, "flatness_abs": 0.05,     # whitening
    "hf_ratio_ratio": 2.0, "hf_ratio_abs": 0.05,     # HF-blowout / static buzz  (NEW vs old gate)
    "zcr_ratio": 1.6, "zcr_abs": 0.15,               # noise / ringing
    "onset_collapse": 0.4, "bpm_break": 20.0,        # beat-loss (rhythmic only)
    "ce_drift": 1.5,                                 # |ΔCE| quality collapse   (NEW — Kim's ask)
    "centroid_ratio_hi": 1.5, "centroid_ratio_lo": 0.6,  # corroborating spectral shift
}
NAME = re.compile(r"([a-z0-9_]+)__(base|g\d+)__(p\d+)\.\w+$")
RHYTHMIC = {"p0"}


def load(pattern):
    db = sqlite3.connect(DB)
    cols = [r[1] for r in db.execute("PRAGMA table_info(metrics)").fetchall()]
    rows = db.execute(f"select {','.join(cols)} from metrics where path like ?",
                      (f"%{pattern}%",)).fetchall()
    base, by, gains = {}, defaultdict(dict), set()
    for r in rows:
        d = dict(zip(cols, r))
        m = NAME.search(d["path"])
        if not m:
            continue
        head, g, pid = m.groups()
        if head == "baseline":
            base[pid] = d
        else:
            gv = int(g[1:])
            by[(head, pid)][gv] = d
            gains.add(gv)
    return base, by, sorted(gains)


def gate(clip, base, rhythmic, thr=THR):
    """(disintegrated: bool, hard_reasons: list, corroborating: list) vs same-prompt baseline."""
    r, corr = [], []

    def ratio(k):
        return clip[k] / max(base[k], 1e-5) if clip.get(k) is not None and base.get(k) else 0.0

    if clip["flatness"] > thr["flatness_abs"] and ratio("flatness") > thr["flatness_ratio"]:
        r.append(f"whitening(flat {base['flatness']:.3f}->{clip['flatness']:.3f})")
    if clip.get("hf_ratio") and clip["hf_ratio"] > thr["hf_ratio_abs"] and ratio("hf_ratio") > thr["hf_ratio_ratio"]:
        r.append(f"hf-blowout(hf {base['hf_ratio']:.3f}->{clip['hf_ratio']:.3f})")
    if clip["zcr"] > thr["zcr_abs"] and ratio("zcr") > thr["zcr_ratio"]:
        r.append(f"noise-zcr({base['zcr']:.3f}->{clip['zcr']:.3f})")
    if rhythmic:
        op, opb = clip.get("onset_p95") or 0, base.get("onset_p95") or 0
        bp, bpb = clip.get("bpm") or 0, base.get("bpm") or 0
        if opb > 0.5 and op < thr["onset_collapse"] * opb and (bp == 0 or abs(bp - bpb) > thr["bpm_break"]):
            r.append(f"beat-loss(onset {opb:.1f}->{op:.1f}, bpm {bpb:.0f}->{bp:.0f})")
    ce, ceb = clip.get("ce"), base.get("ce")
    if ce is not None and ceb is not None and abs(ce - ceb) > thr["ce_drift"]:
        r.append(f"ce-drift({ceb:.2f}->{ce:.2f}, Δ{ce-ceb:+.2f})")
    # corroborating (non-fatal)
    cr = ratio("centroid")
    if cr and (cr > thr["centroid_ratio_hi"] or cr < thr["centroid_ratio_lo"]):
        corr.append(f"centroid×{cr:.2f}")
    return bool(r), r, corr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pattern", default="latch_sa3_sweep",
                    help="substring of clip paths in clip_metrics.db (a control-head clip family)")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "control_head_disintegration.json"))
    ap.add_argument("--diff-old", default=str(Path(__file__).resolve().parent / "latch_bracket_quality.json"),
                    help="older gate json to diff against (show heads that FLIP to disintegrating)")
    a = ap.parse_args()

    base, by, gains = load(a.pattern)
    if not base:
        print(f"no baseline clips for pattern '{a.pattern}' — need {{head}}__base__{{pid}} rows"); return

    result = {}
    cells = {}   # per-cell verdict for the page generators: "{head}__g{gain}__{pid}" -> {...}
    heads = sorted({h for (h, _) in by})
    print(f"{'head':22s} {'prompt':6s} {'usable≤':>7s}  first-disintegration (vs unsteered baseline)")
    for head in heads:
        result[head] = {}
        for pid in sorted(base):
            clips = by.get((head, pid), {})
            if not clips:
                continue
            rhythmic = pid in RHYTHMIC
            usable, failure = 0, None
            for g in sorted(clips):
                bad, reasons, corr = gate(clips[g], base[pid], rhythmic)
                # per-cell verdict — EVERY gain evaluated independently (no break), so a page
                # can flag each cell directly instead of deriving it from the ceiling.
                cells[f"{head}__g{g}__{pid}"] = {
                    "head": head, "gain": g, "prompt": pid,
                    "disintegrated": bad, "hard_reasons": reasons, "corroborating": corr}
                if bad and failure is None:
                    failure = {"gain": g, "reasons": reasons, "corroborating": corr}
                if not bad and failure is None:
                    usable = g   # highest clean gain before the first disintegration (the badge)
            result[head][pid] = {"usable_max_gain": usable, "failure": failure}
            ftxt = "clean through max" if not failure else f"g{failure['gain']}: {', '.join(failure['reasons'])}"
            print(f"{head:22s} {pid:6s} {usable:>7d}  {ftxt}")

    # diff vs the older lenient gate: which (head,prompt) had a WIDER usable range before?
    flips = []
    old_path = Path(a.diff_old)
    if old_path.exists():
        old = json.loads(old_path.read_text()).get("result", {})
        for head in heads:
            for pid in result[head]:
                new_u = result[head][pid]["usable_max_gain"]
                old_u = old.get(head, {}).get(pid, {}).get("usable_max_gain")
                if old_u is not None and new_u < old_u:
                    flips.append({"head": head, "prompt": pid, "old_usable": old_u, "new_usable": new_u,
                                  "now_fails": result[head][pid]["failure"]["reasons"]})
    if flips:
        print("\n=== TIGHTENED gate catches disintegration the old gate passed ===")
        for f in flips:
            print(f"  {f['head']:22s} {f['prompt']}  old≤{f['old_usable']} -> now≤{f['new_usable']}  ({', '.join(f['now_fails'])})")

    Path(a.out).write_text(json.dumps({
        "purpose": "MANDATORY disintegration gate for control-head evals (Kim directive 2026-07-20)",
        "spec": "docs/superpowers/specs/2026-07-20-control-head-disintegration-gate.md",
        "pattern": a.pattern, "gains": gains, "thresholds": THR,
        "baseline": "same-prompt gain-0 unsteered clip",
        "hard_flags": ["whitening", "hf-blowout", "noise-zcr", "beat-loss(rhythmic)", "ce-drift"],
        "caveat": "tightened DSP screen, NOT ear-verified — 'clean' = not-obviously-disintegrated, "
                  "not musically good. Recalibrate thresholds against Kim's GUI verdicts.",
        "result": result,          # per-head/prompt: usable_max_gain (badge) + first failure
        "cells": cells,            # per-cell: "{head}__g{gain}__{pid}" -> disintegrated flag + reasons
        "flips_vs_old_gate": flips,
    }, indent=1))
    print(f"\n-> {a.out}")


if __name__ == "__main__":
    main()
