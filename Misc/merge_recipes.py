#!/usr/bin/env python3
"""merge_recipes.py — non-clobbering merge of extracted recipes into overrides.

Reads eval/extracted_recipes.staging.json (from extract_recipes.py) and folds a
STRUCTURED `recipe` dict into Misc/models_index_overrides.json.

SAFETY RULES (this touches the PUBLIC model matrix — be conservative):
  - NEVER overwrite a `recipe` that is already a dict (G's hand-authored deep
    entries: adamw_* etc.). Those win; we skip them.
  - NEVER touch `one_liner` / `family` / `why` / `compare_against` / `note` /
    add_links / remove_links — those are human synthesis, not our lane here.
  - Fill `recipe` (as a structured dict) ONLY when it is absent OR a legacy
    string. When replacing a legacy string, preserve it as `recipe_legacy_str`
    so no hand-written context is lost.
  - Only labels with _status == "ok" in staging are eligible.
  - Labels not in staging are left entirely untouched.

Default is DRY-RUN (prints a plan, writes nothing). Pass --write to apply.
"""
import argparse, json
from pathlib import Path

OVERRIDES = Path("/home/kim/Projects/SAO/Misc/models_index_overrides.json")
STAGING = Path("/home/kim/Projects/SAO/eval/extracted_recipes.staging.json")

# Known-safe scalar/structured fields (numbers/enums/module-name patterns — no
# path or corpus leak risk); passed through verbatim.
_KEEP_SAFE = ("kind", "lora_config", "target_modules_count", "rank_from_shapes",
              "optimizer", "epoch", "global_step", "avg_loss")
# Free-form config dicts from control/latch/other checkpoints — UNKNOWN content,
# may embed dataset paths etc., so run through build_site.redact() as a safety net.
_KEEP_REDACT = ("args", "hparams", "hyper_parameters", "metadata", "config",
                "adapter_config", "state_dict_tensors")

# Import the shared redactor (same layer the public board renders through).
import sys as _sys
_sys.path.insert(0, "/home/kim/Projects/SAO/Misc")
try:
    from build_site import redact as _redact
except Exception:
    _redact = lambda s: s  # fail open to identity only if unavailable; merge stays dry-run-guarded


def _redact_deep(x):
    if isinstance(x, str): return _redact(x)
    if isinstance(x, dict): return {k: _redact_deep(v) for k, v in x.items()}
    if isinstance(x, list): return [_redact_deep(v) for v in x]
    return x


def _run_label_from_path(p):
    """/run/media/.../sa3_lora_runs/<run>/epoch=..ckpt -> '<run>' (drops the path)."""
    try:
        parts = str(p).replace("\\", "/").split("/")
        # the run label is the directory just above the checkpoint filename
        return parts[-2] if len(parts) >= 2 else str(p)
    except Exception:
        return None


def structured_recipe(rec, label):
    # source-clean by construction: NO absolute paths, NO checkpoint filenames.
    out = {k: rec[k] for k in _KEEP_SAFE if k in rec and rec[k] is not None}
    for k in _KEEP_REDACT:
        if k in rec and rec[k] is not None:
            out[k] = _redact_deep(rec[k])
    # SVD-extraction lineage: keep the SOURCE RUN LABEL (a matrix label), drop its path.
    ep = rec.get("extraction_provenance")
    if isinstance(ep, dict):
        clean = {}
        if "extracted_from" in ep:
            clean["extracted_from_run"] = _run_label_from_path(ep["extracted_from"])
        if "extraction_method" in ep:
            clean["extraction_method"] = ep["extraction_method"]
        if clean: out["extraction_provenance"] = clean
    if rec.get("safetensors_metadata"):
        out["safetensors_metadata"] = _redact_deep(rec["safetensors_metadata"])
    # provenance: symbolic manifest ref per the commentary spec (NOT a raw path/filename).
    out["provenance"] = {
        "checkpoint": f"manifest:{label}",
        "extracted": "2026-07-30 via Misc/extract_recipes.py (real checkpoint read)",
        "pruned_slim": rec.get("_pruned_slim"),
    }
    if rec.get("optimizer") and not isinstance(rec.get("optimizer"), dict):
        out["provenance"]["optimizer_note"] = rec["optimizer"]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="apply (default: dry-run)")
    args = ap.parse_args()

    ov = json.load(open(OVERRIDES))
    st = json.load(open(STAGING))

    plan = {"new_entry": [], "fill_missing": [], "replace_legacy_str": [],
            "skip_dict_recipe": [], "skip_not_ok": [], "skip_no_change": []}
    for label, rec in st.items():
        if rec.get("_status") != "ok":
            plan["skip_not_ok"].append(label); continue
        newrec = structured_recipe(rec, label)
        entry = ov.get(label)
        if entry is None:
            plan["new_entry"].append(label)
            if args.write:
                ov[label] = {"recipe": newrec,
                             "note": "auto: recipe extracted from checkpoint; evaluation sentence pending"}
        else:
            cur = entry.get("recipe")
            if isinstance(cur, dict):
                plan["skip_dict_recipe"].append(label)  # G's deep entry — leave it
            elif isinstance(cur, str) and cur.strip():
                plan["replace_legacy_str"].append(label)
                if args.write:
                    entry["recipe_legacy_str"] = cur
                    entry["recipe"] = newrec
            else:
                plan["fill_missing"].append(label)
                if args.write:
                    entry["recipe"] = newrec

    if args.write:
        OVERRIDES.write_text(json.dumps(ov, indent=2, ensure_ascii=False))

    print(("WROTE" if args.write else "DRY-RUN") + " — merge plan:")
    for k, v in plan.items():
        print(f"  {k}: {len(v)}")
    for k in ("new_entry", "replace_legacy_str", "fill_missing", "skip_dict_recipe"):
        if plan[k]:
            print(f"\n  {k} ({len(plan[k])}): " + ", ".join(plan[k][:20]) + (" ..." if len(plan[k]) > 20 else ""))
    if not args.write:
        print("\n(no file written — pass --write to apply)")


if __name__ == "__main__":
    main()
