#!/usr/bin/env python3
"""build_clip_scores_export.py -- per-clip metrics JSON for the model_matrix hybrid-score
feature (Kim direct 2026-07-30): a preload button, a 4-row metrics grid under the player
showing the playing clip's scores + its "equivalents" (same cfg/strength/prompt_id, which
fixes the seed) in the other selected checkpoints, a popup ranking ALL board-wide
equivalents by a chosen metric, and a hybrid score with user-adjustable importance weights.

Division (THE-FINN, task #84): W owns UI/render (build_model_matrix.py), this script owns
the data-export/index side. Source: eval/clap_full_table.csv (one row per rendered clip,
already joins CLAP + Audiobox + DSP metrics -- see build_clap_hyperparam_table.py). This
script does NOT re-measure anything; it reshapes the existing per-cell table into a compact
array-of-arrays JSON a browser can fetch once and index client-side.

Design (fleet-settled, 2026-07-30):
  - metric_meta classifies every metric column as score (has a quality direction) or
    descriptive (context, no inherent direction, hybrid-excluded by default) -- THE-FINN's
    table, cross-checked against clap_full_table.csv's real columns.
  - direction: "higher" or "lower" -- which way is better, so the frontend can invert
    (e.g. retrieval_rank, flatness) before percentile-ranking.
  - Percentile-rank (not z-score) is the recommended client-side normalization -- CONTINUITY:
    z-scores get wrecked by buzz-clip outlier tails, percentile rank is robust and IS a
    proper per-metric scale-normalization. This script does not compute percentiles itself
    (that's over the CURRENT comparison set, which the UI controls -- e.g. board-wide vs
    just-the-4-selected-columns), it ships raw values + direction, frontend computes ranks
    over whatever comparison set is active.
  - Gate-as-multiplier, not weighted-term (CONTINUITY): a disintegration-gate FAIL should
    floor/zero the hybrid score rather than being just another weighted input, so a
    confident-sounding buzz clip can't buy a high composite with enough PQ/CLAP weight.
    This export does not carry gate pass/fail itself (no gate data exists for the general
    model_matrix population, only for LatCH/control-head sweeps under
    eval/control_head_disintegration.json) -- frontend gates on it where available, all
    clips ungated otherwise (documented as a known gap, not silently pretended-clean).

Redaction: 'file' is a rendered clip filename (already public via every audio URL on the
page) -- not a checkpoint path. THE-FINN leak-patrols this export before W ships it, same
as any new public data surface.

Run: python3 eval/build_clip_scores_export.py -> ~/.cache/evals_aac/model_matrix/clip_scores.json
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "eval/clap_full_table.csv"
STAGING = Path.home() / ".cache/evals_aac"
OUT = STAGING / "model_matrix/clip_scores.json"

# equivalence key = cfg + strength + prompt_id (prompt_id fixes the seed; frame-length is a
# per-(model,ckpt) property already known from the page's own model meta, not per-clip)
ID_COLS = ["model", "ckpt", "prompt_id", "file", "cfg", "strength"]

METRIC_META = {
    # score metrics -- have a quality direction, eligible for the hybrid by default
    "clap_matched":    {"category": "score", "direction": "higher", "label": "CLAP adherence"},
    "clap_margin_far": {"category": "score", "direction": "higher", "label": "CLAP margin vs far-control"},
    "beats_all_far":   {"category": "score", "direction": "higher", "label": "CLAP beats-all-far (0/1)"},
    "retrieval_rank":  {"category": "score", "direction": "lower",  "label": "CLAP retrieval rank (1=best)"},
    "ce":              {"category": "score", "direction": "higher", "label": "Audiobox CE (enjoyment)"},
    "pq":              {"category": "score", "direction": "higher", "label": "Audiobox PQ (production quality)"},
    "cu":              {"category": "score", "direction": "higher", "label": "Audiobox CU (usefulness)"},
    "flatness":        {"category": "score", "direction": "lower",  "label": "spectral flatness (whitening/noise)"},
    # descriptive -- context, not quality; excluded from the hybrid unless the user opts in
    "pc":         {"category": "descriptive", "direction": None, "label": "Audiobox PC (complexity)"},
    "zcr":        {"category": "descriptive", "direction": None, "label": "zero-crossing rate"},
    "flux":       {"category": "descriptive", "direction": None, "label": "spectral flux"},
    "hf_ratio":   {"category": "descriptive", "direction": None, "label": "high-frequency ratio (brightness)"},
    "bpm":        {"category": "descriptive", "direction": None, "label": "tempo"},
    "onset_p95":  {"category": "descriptive", "direction": None, "label": "onset strength (95th pct)"},
    "centroid":   {"category": "descriptive", "direction": None, "label": "spectral centroid"},
    "crest":      {"category": "descriptive", "direction": "higher", "label": "crest factor (punch, weak signal)"},
    "rms":        {"category": "descriptive", "direction": None, "label": "RMS level"},
    "dur":        {"category": "descriptive", "direction": None, "label": "clip duration (s)"},
}
METRIC_COLS = list(METRIC_META)


def _num(s):
    if s is None or s == "":
        return None
    try:
        f = float(s)
        return None if f != f else round(f, 4)  # NaN -> None (valid JSON, no NaN literal)
    except ValueError:
        return None


def main():
    if not SRC.exists():
        raise SystemExit(f"missing {SRC} -- run eval/build_clap_hyperparam_table.py first")
    clips = []
    with open(SRC, newline="") as f:
        for row in csv.DictReader(f):
            if row.get("is_repr") == "True":
                continue  # _repr rows are epoch-history dupes of the same run, not distinct cells
            rec = [row["model"], row["ckpt"], row["prompt_id"], row["file"],
                   _num(row["cfg"]), _num(row["strength"])]
            rec += [_num(row.get(c)) for c in METRIC_COLS]
            clips.append(rec)

    out = {
        "columns": ID_COLS + METRIC_COLS,
        "metric_meta": METRIC_META,
        "n_clips": len(clips),
        "clips": clips,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(out, separators=(",", ":"))
    OUT.write_text(text)
    print(f"wrote {OUT}: {len(clips)} clips, {len(out['columns'])} cols, "
          f"{len(text) / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
