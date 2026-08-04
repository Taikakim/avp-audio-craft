#!/usr/bin/env python3
"""Validate Foote section boundaries vs MuScriptor MIDI-derived sections (157 tracks).
MuScriptor: section_lens_bars -> cumulative bar indices -> downbeat times (our grid).
Metric: MIREX-style boundary F @ 3s and @ 1.7s (~1 bar). mir venv or any numpy python."""
import json
from pathlib import Path
import numpy as np

MUS = Path("/run/media/kim/Mantu/sa3_lora_runs/muscriptor_goa_midis/musicology")
import os
SEC = Path(os.environ.get("SEC_DIR", "/run/media/kim/Lehto/section_labels"))
GOA = Path("/run/media/kim/Mantu/ai-music/Goa_Separated")

def f_at(ref, hyp, tol):
    if not len(ref) or not len(hyp):
        return 0.0
    hit_r = sum(1 for r in ref if np.min(np.abs(np.array(hyp) - r)) <= tol)
    hit_h = sum(1 for h in hyp if np.min(np.abs(np.array(ref) - h)) <= tol)
    p, r = hit_h / len(hyp), hit_r / len(ref)
    return 2 * p * r / (p + r) if p + r else 0.0

rows = []
for mj in sorted(MUS.glob("*.musicology.json")):
    track = mj.name[: -len(".musicology.json")]
    sj = SEC / f"{track}.sections.json"
    db_f = GOA / track / f"{track}.DOWNBEATS"
    if not sj.exists() or not db_f.exists():
        continue
    m = json.load(open(mj)); s = json.load(open(sj))
    lens = m.get("structure", {}).get("section_lens_bars") or []
    if len(lens) < 2:
        continue
    db = np.array([float(x) for x in db_f.read_text().split()])
    cum = np.cumsum(lens)[:-1]
    cum = cum[cum < len(db)]
    ref = db[cum]                      # MIDI-derived boundaries on our bar grid
    hyp = np.array(s["boundaries_sec"])
    rows.append({"track": track, "n_ref": len(ref), "n_hyp": len(hyp),
                 "f3": round(f_at(ref, hyp, 3.0), 3),
                 "f1bar": round(f_at(ref, hyp, 1.7), 3)})

f3 = [r["f3"] for r in rows]; f1b = [r["f1bar"] for r in rows]
nref = [r["n_ref"] for r in rows]; nhyp = [r["n_hyp"] for r in rows]
print(f"n={len(rows)}  F@3s median={np.median(f3):.3f} mean={np.mean(f3):.3f}   "
      f"F@1bar median={np.median(f1b):.3f}   n_sections ref-med={np.median(nref):.0f} hyp-med={np.median(nhyp):.0f}")
out = Path(os.environ.get("VAL_OUT", "/home/kim/Projects/SAO/eval/section_boundary_validation.json"))
out.write_text(json.dumps({"summary": {"n": len(rows), "f3_median": float(np.median(f3)),
                                        "f3_mean": float(np.mean(f3)), "f1bar_median": float(np.median(f1b))},
                           "rows": rows}, indent=1))
print("wrote", out)
