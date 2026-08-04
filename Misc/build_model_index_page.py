#!/usr/bin/env python3
"""
build_model_index_page.py -- regenerate the repo-root `model_index.md` from the
LIVE eval-board manifest, so the model roster stays current instead of drifting
into a hand-maintained snapshot (the old model_index.md was a 2026-07-04 compile
of ~24 checkpoints; the board now carries 227 labels).

WHY A SECOND "build_model_index" SCRIPT?
  `Misc/build_model_index.py` is a DIFFERENT tool: it scans the filesystem
  (Mantu/sa3_lora_runs, sa3_control_runs, LatCH weights) for checkpoint files and
  cross-references eval-page dirs, emitting an HTML awareness page
  (~/.cache/evals_aac/models.html) that feeds docs/checkpoint-hall-of-fame.md.
  This script instead reads the eval-board MANIFEST (the models actually rendered
  onto the board) and emits the repo-root markdown `model_index.md`. Different
  input, different output, different audience -- they only share the overrides JSON.

SOURCES
  * ~/.cache/evals_aac/model_matrix/manifest_live.jsonl  -- one record per clip;
    the distinct `model` labels ARE the live roster. `ckpt` gives the epoch/ckpt
    tags rendered; `prompt_text` is not used here.
  * Misc/models_index_overrides.json  -- the rich, maintained per-model source:
    `recipe` (real hyperparameters extracted from each checkpoint, NOT hand-typed),
    `why` + `one_liner` (plain-language account of why the model was made),
    `compare_against` (which models it is best A/B'd against), and the HAND-ADDED
    `note` / `verdict` (the by-ear + board-metered judgments). These verdicts are
    the valuable, human-authored layer -- they live in the JSON precisely so they
    SURVIVE regeneration: this generator only READS them, never invents them.
  * Misc/model_index_legacy.md  -- a static snapshot of the 2026-07-04 hand-authored
    body (July DoRA by-ear verdicts + off-board control-head notes for onset/style/
    LatCH/ES/mutated bases that are NOT on the live board). Appended verbatim so
    nothing from the old page is lost.

`_ptm` labels are the SAME checkpoint re-rendered on medium-base (a base-mismatch
render variant, per eval/model_matrix_gen.py) -- collapsed onto their parent model.
Override lookup mirrors model_matrix_gen.py: try the label, then strip `_ptm`,
then `_ptm`+`_repr`.

Run:  python3 Misc/build_model_index_page.py     (writes model_index.md at repo root)
Only stdlib -- no venv needed. To change a verdict/recipe, edit the overrides JSON
(or Misc/model_index_legacy.md for the off-board notes) and re-run.
"""
import datetime
import json
import re
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MANIFEST = Path.home() / ".cache/evals_aac/model_matrix/manifest_live.jsonl"
OVERRIDES = REPO / "Misc/models_index_overrides.json"
LEGACY = REPO / "Misc/model_index_legacy.md"
OUT = REPO / "model_index.md"

# label tokens that mark the start of the parameter tail (used to derive a family
# name for the handful of live models with no override `family`).
PARAM_TOK = re.compile(r"^(?:lr|t|bs|ep|r|a|k|s|f|aug|w|cfg|sub|v)\d|^\d")


def load_roster():
    """Distinct model labels from the live manifest, with the ckpt tags and clip
    counts seen for each. Missing/empty manifest -> empty roster (caller warns)."""
    roster = defaultdict(lambda: {"ckpts": set(), "clips": 0})
    if not MANIFEST.exists():
        return {}
    for line in MANIFEST.open():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        m = r.get("model")
        if not m:
            continue
        roster[m]["clips"] += 1
        if r.get("ckpt"):
            roster[m]["ckpts"].add(r["ckpt"])
    return roster


def load_overrides():
    if not OVERRIDES.exists():
        return {}
    try:
        raw = json.load(OVERRIDES.open())
    except (json.JSONDecodeError, OSError):
        return {}
    return {k: v for k, v in raw.items() if isinstance(v, dict)}


def lookup(label, overrides):
    """Resolve a manifest label to its override entry, mirroring
    model_matrix_gen.py's suffix-stripping (label, -_ptm, -_ptm-_repr)."""
    for cand in (label, re.sub(r"_ptm$", "", label),
                 re.sub(r"_repr$", "", re.sub(r"_ptm$", "", label))):
        if cand in overrides:
            return overrides[cand]
    return None


def derive_family(label, ov):
    """Family for grouping: the override's `family` if set, else a heuristic from
    the label prefix (leading non-parametric tokens)."""
    if ov and ov.get("family"):
        return ov["family"]
    base = re.sub(r"_ptm$", "", label)
    if base == "base":
        return "base"
    if base.startswith("sa3-goa-dora-47s"):
        return "sa3_goa_dora_47s (original July DoRA)"
    toks = re.split(r"[_\-]", base)
    keep = []
    for t in toks:
        if PARAM_TOK.match(t):
            break
        keep.append(t)
    return "_".join(keep) if keep else base


def fmt(v):
    """Compact one-line string for a recipe scalar/dict value."""
    if isinstance(v, dict):
        return ", ".join(f"{k} {fmt(x)}" for k, x in v.items()
                         if k not in ("include", "exclude", "dropout") and x not in (None, ""))
    return str(v)


def recipe_lines(recipe):
    """Turn a recipe (structured dict OR legacy string) into readable markdown
    bullet lines. Handles the several dict shapes present in the overrides:
    dora/lora (lora_config+optimizer), svd-extracted adapter, whole-DiT fullft
    (`training` sub-dict), and the deep hand-authored flat shape (method/rank_alpha/
    optimizer/precision/context_len keys)."""
    if not recipe:
        return []
    if isinstance(recipe, str):
        return [f"- **Recipe:** {recipe.strip()}"]
    r = recipe
    training = r.get("training") if isinstance(r.get("training"), dict) else {}
    lc = r.get("lora_config") if isinstance(r.get("lora_config"), dict) else {}

    def pick(*keys):
        for src in (r, training):
            for k in keys:
                if src.get(k) not in (None, ""):
                    return src[k]
        return None

    bits = []
    kind = r.get("kind")
    if kind:
        bits.append(("kind", kind))
    method = pick("method")
    if method:
        bits.append(("method", method))
    elif lc.get("adapter_type"):
        bits.append(("method", lc["adapter_type"]))
    if lc:
        ra = f"rank {lc.get('rank')}, alpha {lc.get('alpha')}"
        bits.append(("rank/alpha", ra))
    elif pick("rank_alpha"):
        bits.append(("rank/alpha", pick("rank_alpha")))
    for key, names in (("base_model", ("base_model",)),
                       ("optimizer", ("optimizer",)),
                       ("lr_schedule", ("lr_schedule",)),
                       ("precision", ("precision",)),
                       ("context_len", ("context_len", "context_len")),
                       ("corpus", ("corpus",)),
                       ("objective", ("objective",))):
        val = pick(*names)
        if val is not None:
            bits.append((key, fmt(val)))
    # epochs / steps
    if pick("epochs"):
        bits.append(("epochs", fmt(pick("epochs"))))
    elif r.get("epoch") is not None:
        step = f", step {r['global_step']}" if r.get("global_step") is not None else ""
        bits.append(("epochs", f"epoch {r['epoch']} (0-indexed){step}"))
    if pick("steps"):
        bits.append(("steps", fmt(pick("steps"))))
    ep = r.get("extraction_provenance")
    if isinstance(ep, dict) and ep.get("extracted_from_run"):
        bits.append(("extracted from", f"{ep['extracted_from_run']} "
                                       f"({ep.get('extraction_method', 'svd')})"))
    # de-dup keys, keep first
    seen, out = set(), []
    for k, v in bits:
        if k in seen:
            continue
        seen.add(k)
        out.append(f"  - {k}: {fmt(v)}")
    if not out:
        return []
    return ["- **Recipe:**"] + out


def is_placeholder_note(note):
    return not note or str(note).strip().startswith("auto:")


def model_block(label, info, ov, dedup=None):
    """Markdown for one live model. `ov` may be None (recipe/verdict unknown).
    `dedup` maps a field name ('why'/'verdict') to {text: first_label}; when the
    same long text recurs within a family it is printed once and back-referenced,
    so families like xft_distillation (60 members sharing one finding) stay readable."""
    dedup = {} if dedup is None else dedup  # NB: empty dict is falsy; must not replace it
    L = [f"#### `{label}`"]
    ckpts = sorted(info["ckpts"])
    meta = f"{len(ckpts)} ckpt tag(s) on board ({', '.join(ckpts)}) · {info['clips']} clips"
    if ov is None:
        L.append(f"- {meta}")
        L.append("- *No override entry — recipe/verdict not yet recorded. "
                 "Add one to `Misc/models_index_overrides.json` (or see the Legacy "
                 "snapshot below for July by-ear notes) and re-run.*")
        return "\n".join(L)

    if ov.get("one_liner"):
        L.append(f"- **{ov['one_liner'].strip()}**")
    L.append(f"- {meta}")
    if ov.get("training_data"):
        L.append(f"- **Training data:** {ov['training_data'].strip()}")
    L += recipe_lines(ov.get("recipe"))

    def with_dedup(field, text):
        text = text.strip()
        seen = dedup.setdefault(field, {})
        first = seen.get(text)
        if first is not None and first != label:
            return f"(same as `{first}`)"
        seen[text] = label
        return text

    if ov.get("why"):
        L.append(f"- **Why it was made:** {with_dedup('why', ov['why'])}")
    comps = ov.get("compare_against") or []
    if comps:
        L.append("- **Compare against:**")
        for c in comps:
            if isinstance(c, dict):
                tgt = c.get("target", "")
                axis = f" — {c['axis']}" if c.get("axis") else ""
                L.append(f"  - `{tgt}`{axis}" if not tgt.startswith("the ") else f"  - {tgt}{axis}")
            else:
                L.append(f"  - {c}")
    # THE HAND-ADDED JUDGMENTS -- preserved verbatim (long shared ones de-duped).
    if ov.get("verdict"):
        L.append(f"- **Verdict:** {with_dedup('verdict', ov['verdict'])}")
    if not is_placeholder_note(ov.get("note")) and ov.get("note") != ov.get("verdict"):
        L.append(f"- **Note (by-ear):** {ov['note'].strip()}")
    status = ov.get("status")
    if status:
        L.append(f"- *status: {status}*")
    return "\n".join(L)


def main():
    roster = load_roster()
    overrides = load_overrides()
    today = datetime.date.today().isoformat()

    # collapse `_ptm` render-variants onto their parent trained model
    families = defaultdict(dict)  # family -> {canonical_label: {info, variants, ov}}
    variant_count = len(roster)
    for label in sorted(roster):
        ov = lookup(label, overrides)
        canon = re.sub(r"_ptm$", "", label)
        fam = derive_family(canon, ov)
        slot = families[fam].setdefault(canon, {
            "info": {"ckpts": set(), "clips": 0}, "variants": [], "ov": ov})
        slot["info"]["ckpts"] |= roster[label]["ckpts"]
        slot["info"]["clips"] += roster[label]["clips"]
        slot["variants"].append(label)
        if slot["ov"] is None and ov is not None:
            slot["ov"] = ov

    n_models = sum(len(v) for v in families.values())
    n_fam = len(families)
    n_with = sum(1 for fam in families.values() for s in fam.values() if s["ov"])
    n_without = n_models - n_with
    def has_verdict(ov):
        return bool(ov and (ov.get("verdict") or not is_placeholder_note(ov.get("note"))))

    n_verdict = sum(1 for fam in families.values() for s in fam.values()
                    if has_verdict(s["ov"]))

    # family order: largest first, then alphabetical (base pinned first)
    def fam_key(f):
        return (f != "base", -len(families[f]), f)
    fam_order = sorted(families, key=fam_key)

    doc = []
    doc.append("# SA3 Model Index")
    doc.append("")
    doc.append(f"> [!NOTE]")
    doc.append(f"> **Generated {today} — re-run `python3 Misc/build_model_index_page.py`.**")
    doc.append(f"> Auto-built from the live eval-board manifest "
               f"(`~/.cache/evals_aac/model_matrix/manifest_live.jsonl`) joined to the maintained "
               f"per-model source `Misc/models_index_overrides.json` (real recipes extracted from "
               f"each checkpoint + plain-language why + comparison targets + hand-added by-ear "
               f"verdicts). This replaces the old hand-compiled snapshot; the July-4 body is kept "
               f"verbatim as a **Legacy snapshot** at the foot of this file.")
    doc.append(">")
    doc.append(f"> **Roster:** {variant_count} board labels → **{n_models} distinct trained models** "
               f"across **{n_fam} families** (`_ptm` = same checkpoint re-rendered on medium-base, "
               f"collapsed onto its parent). {n_with} carry a recipe/verdict override; "
               f"{n_without} are on the board but not yet annotated; {n_verdict} carry a hand-added "
               f"by-ear or board-metered verdict.")
    doc.append(">")
    doc.append(f"> **To change a verdict or recipe:** edit `Misc/models_index_overrides.json` "
               f"(verdicts live there so they survive regeneration — this generator only reads them) "
               f"and re-run the script. Off-board control-head notes live in "
               f"`Misc/model_index_legacy.md`.")
    doc.append("")
    doc.append("---")
    doc.append("")

    for fam in fam_order:
        slots = families[fam]
        # oldest-appearing / alphabetical within family
        labels = sorted(slots)
        n_fam_verdict = sum(1 for s in slots.values() if has_verdict(s["ov"]))
        doc.append(f"## {fam} — {len(slots)} model(s)"
                   + (f", {n_fam_verdict} with a verdict" if n_fam_verdict else ""))
        doc.append("")
        fam_dedup = {}  # de-dup shared why/verdict within this family
        for canon in labels:
            slot = slots[canon]
            variants = [v for v in slot["variants"] if v != canon]
            block = model_block(canon, slot["info"], slot["ov"], fam_dedup)
            doc.append(block)
            if variants:
                doc.append(f"- *(also on board as base-render variant: "
                           f"{', '.join('`'+v+'`' for v in variants)})*")
            doc.append("")
        doc.append("")

    # ---- legacy appendix (verbatim, nothing lost) ----
    if LEGACY.exists():
        legacy = LEGACY.read_text()
        legacy = re.sub(r"^<!--.*?-->\s*", "", legacy, flags=re.DOTALL)
        doc.append("---")
        doc.append("")
        doc.append("# Legacy hand-compiled snapshot (2026-07-04)")
        doc.append("")
        doc.append("> [!NOTE]")
        doc.append("> Below is the original hand-authored index, kept verbatim for its by-ear "
                   "verdicts. It covers the July DoRA runs **and** the control-head families "
                   "(onset FiLM / style fingerprint / LatCH guidance / ES conditioners / mutated "
                   "bases / adapter soups) that are **not on the live text-to-audio board above**, "
                   "so the generator cannot reach them. Source: `Misc/model_index_legacy.md`.")
        doc.append("")
        doc.append(legacy.strip())
        doc.append("")

    OUT.write_text("\n".join(doc))
    print(f"wrote {OUT}")
    print(f"  {variant_count} board labels -> {n_models} models, {n_fam} families")
    print(f"  {n_with} annotated, {n_without} un-annotated, {n_verdict} with a by-ear/metered verdict")
    if not roster:
        print("  WARNING: manifest empty or missing -- roster is empty!")


if __name__ == "__main__":
    main()
