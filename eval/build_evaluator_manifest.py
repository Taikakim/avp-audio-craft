#!/usr/bin/env python3
"""build_evaluator_manifest.py -- pre-filter the shared manifest down to what evaluator.html
actually needs, at BUILD time instead of on every visitor's device (Kim 2026-08-16: "I can
perform periodic updates then, it does not have to be dynamic").

WHY THIS EXISTS: evaluator.html used to fetch manifest_live.jsonl directly -- the shared
index over the ENTIRE model_matrix corpus (every campaign, every model, every cfg x strength
x prompt x length combo), 24.5MB / ~71,700 lines at last measure -- then filter it down,
client-side, in every visitor's browser, to the tiny slice it actually uses: cfg7/w1 (or
cfg1/w1 for _ptm rows) clips from the ~68 avp-dataset scored models. On a slow mobile
connection that download alone was legitimately taking minutes, before a byte of the actual
~70k-line JSON-parse work even started. This script does that filtering ONCE, here, and
evaluator.html fetches the small result instead.

Run as part of score_and_publish.py's leg_tables() (the same table-rebuild step Kim already
runs periodically), right after build_clap_hyperparam_table.py -- which is what actually
determines the avp-scored model set (scored_models_avp.json) this script reads.

Not real-time: the output is a static file, refreshed only when this script re-runs. That is
the whole point -- it lets evaluator.html drop `cache:'no-store'` and let the browser's normal
HTTP cache do its job, since staleness between periodic rebuilds is an accepted tradeoff here
(unlike the live internal boards, which need every visit to reflect the latest scoring pass).
"""
import json
from pathlib import Path

STAGE_MATRIX = Path.home() / "evals_aac" / "model_matrix"
MANIFEST = STAGE_MATRIX / "manifest_live.jsonl"
SCORED_AVP = STAGE_MATRIX / "scored_models_avp.json"
OUT = STAGE_MATRIX / "manifest_avp_evaluator.json"

# Exactly the fields evaluator.html's loadManifest()/lengthBucket()/eligible() read off each
# entry -- dropping prompt_text, seed, and everything else the full manifest carries but this
# page never touches is most of the size win (prompt_text alone is often longer than every
# other field on the line combined).
FIELDS = ("model", "ckpt", "cfg", "strength", "file", "prompt_id", "duration_mode", "duration")


def is_op_point(e):
    """Same cut as everywhere else this session: cfg7/w1, or cfg1/w1 for the model's own
    _ptm rows (their only native, non-glitchy config)."""
    is_ptm = str(e.get("model", "")).endswith("_ptm")
    cfg, w = e.get("cfg"), e.get("strength")
    return (cfg == 1 and w == 1) if is_ptm else (cfg == 7 and w == 1)


def main():
    if not MANIFEST.exists():
        raise SystemExit(f"[evaluator-manifest] no manifest at {MANIFEST} -- is the eval drive mounted?")
    if not SCORED_AVP.exists():
        raise SystemExit(f"[evaluator-manifest] no {SCORED_AVP} -- run build_clap_hyperparam_table.py first")

    scored = set(json.loads(SCORED_AVP.read_text()))
    out = []
    for ln in MANIFEST.read_text().splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            e = json.loads(ln)
        except Exception:
            continue
        if e.get("model") not in scored:
            continue
        if not is_op_point(e):
            continue
        out.append({k: e.get(k) for k in FIELDS})

    OUT.write_text(json.dumps(out))
    size = OUT.stat().st_size
    print(f"[evaluator-manifest] wrote {OUT}  ({len(out)} entries from {len(scored)} avp "
          f"models, {size:,} bytes -- was {MANIFEST.stat().st_size:,} bytes unfiltered)")


if __name__ == "__main__":
    main()
