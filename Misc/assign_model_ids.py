#!/usr/bin/env python3
"""assign_model_ids.py — give every distinct trained model a STABLE, RANDOM, unique ID, and
record which labels are synonyms of it.

WHY (Kim direct, 2026-08-17): "We should keep using our model index when we pull stuff etc, and
everyone should check what's there for a model they're about to work with. Only for the synonym
issues, if nothing else. That's why models should have a unique random ID too."

The synonym problem is real and has already cost time. The same trained model reaches us under
several names:
  * `<label>_ptm`   — the SAME checkpoint re-rendered on medium-base (a render variant, not a
                      different model); already special-cased in model_matrix_gen.py and
                      build_model_index_page.py.
  * `<label>_repr`  — a re-render of the same checkpoint. On disk, `sa3_lora_runs/
                      bf16cmp_avp_t512_bs8_lr1e4` and `..._repr` are two symlinks to ONE
                      directory — two names, one model, discoverable only by readlink.
  * board label vs run-dir name vs the name in a sbatch `--name` flag, which drift apart.
A name is therefore NOT an identity. An ID is.

WHY RANDOM, not derived from the name or the weights:
  * Derived-from-name (a hash of the label) changes when the label changes — which is exactly
    the case we need to survive, so it would defeat the purpose.
  * Derived-from-weights (a content hash) is appealing but unstable in practice: the same model
    re-saved by a different torch version, or pruned fat->slim, changes bytes without becoming a
    different model. (Measured today: `bf16cmp_*` slims on the UUID drive differ in size from the
    LUMI originals for the same run/epoch/step.)
  * A random ID assigned ONCE and never recomputed is stable under both. The registry file is
    the authority; the ID means nothing except "this model".

ASSIGN-ONCE IS THE WHOLE CONTRACT: an existing ID is never changed, never reused, never
recycled after a model is retired. This script only ever ADDS. If an ID would collide it aborts
rather than reassign.

ID FORMAT: `M-XXXXXX` over a 30-char alphabet with I/L/O/U removed (transcription-safe, so an ID
read aloud or copied out of a log round-trips). ~7.3e8 possibilities; with a roster in the
hundreds a collision is vanishingly unlikely, and is checked for explicitly anyway.

USAGE
  python3 Misc/assign_model_ids.py --report        # show roster, synonyms, missing IDs; write nothing
  python3 Misc/assign_model_ids.py --assign        # assign IDs to models that lack one
  python3 Misc/assign_model_ids.py --self-test     # verify the contract (no repo files touched)

Registry: Misc/model_ids.json  — read by Misc/build_model_index_page.py, which prints the ID and
an "also known as" line for every model in model_index.md.
Only stdlib.
"""
import argparse
import json
import re
import secrets
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OVERRIDES = REPO / "Misc/models_index_overrides.json"
MANIFEST = Path.home() / ".cache/evals_aac/model_matrix/manifest_live.jsonl"
REGISTRY = REPO / "Misc/model_ids.json"
RUN_DIRS = [Path("/run/media/kim/Mantu/sa3_lora_runs"),
            Path("/run/media/kim/Mantu/sa3_control_runs")]

ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ".replace("I", "").replace("L", "") \
                                            .replace("O", "").replace("U", "")
ID_RE = re.compile(r"^M-[" + ALPHABET + r"]{6}$")

# Render-variant suffixes that do NOT make a different model. Mirrors the lookup order in
# build_model_index_page.py / model_matrix_gen.py so this tool and the index agree.
VARIANT_SUFFIXES = ("_ptm_repr", "_repr_ptm", "_ptm", "_repr")


def new_id(taken):
    """A fresh random ID not already in `taken`. Loops rather than trusting first draw."""
    for _ in range(10000):
        cand = "M-" + "".join(secrets.choice(ALPHABET) for _ in range(6))
        if cand not in taken:
            return cand
    raise RuntimeError("could not find a free ID in 10000 draws — alphabet/length too small?")


def strip_variant(label):
    """Collapse render-variant suffixes to the underlying model label."""
    changed = True
    while changed:
        changed = False
        for suf in VARIANT_SUFFIXES:
            if label.endswith(suf) and len(label) > len(suf):
                label = label[: -len(suf)]
                changed = True
    return label


def symlink_synonyms():
    """Labels that are separate names for ONE run directory, found via readlink.

    This is the class no naming convention catches: two symlinks with unrelated-looking names
    resolving to the same target are the same model, and nothing in the label says so.
    """
    by_target = defaultdict(set)
    for base in RUN_DIRS:
        if not base.is_dir():
            continue
        for p in base.iterdir():
            try:
                if p.is_symlink():
                    by_target[str(p.resolve())].add(p.name)
            except OSError:
                continue
    return {tgt: names for tgt, names in by_target.items() if len(names) > 1}


def load_roster():
    """Every model label we know about, from the overrides and (if present) the live manifest."""
    labels = set()
    if OVERRIDES.exists():
        labels |= {k for k in json.loads(OVERRIDES.read_text()) if not k.startswith("_")}
    if MANIFEST.exists():
        with MANIFEST.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    m = json.loads(line).get("model")
                except json.JSONDecodeError:
                    continue
                if m:
                    labels.add(m)
    return labels


def load_registry():
    if not REGISTRY.exists():
        return {"_doc": ("Assign-once random IDs for distinct trained models. NEVER change or "
                         "reuse an id. `ids` maps canonical label -> id; `aliases` maps a synonym "
                         "label -> its canonical label. Written by Misc/assign_model_ids.py."),
                "ids": {}, "aliases": {}}
    reg = json.loads(REGISTRY.read_text())
    reg.setdefault("ids", {})
    reg.setdefault("aliases", {})
    return reg


def canonicalize(labels, reg):
    """Group labels into canonical -> {synonyms}. Prefers an existing canonical from the registry
    so regeneration cannot silently re-pick a different representative."""
    groups = defaultdict(set)
    for lab in labels:
        canon = reg["aliases"].get(lab) or strip_variant(lab)
        groups[canon].add(lab)
    # fold in the on-disk symlink synonyms
    for _tgt, names in symlink_synonyms().items():
        canons = {reg["aliases"].get(n) or strip_variant(n) for n in names}
        known = [c for c in sorted(canons) if c in reg["ids"]]
        winner = known[0] if known else sorted(canons)[0]
        for c in canons:
            if c != winner:
                groups[winner] |= groups.pop(c, set())
        groups[winner] |= set(names)
    return groups


def audit(reg):
    """Contract checks on the registry itself. Returns a list of problems."""
    problems = []
    seen = {}
    for label, mid in reg["ids"].items():
        if not ID_RE.match(mid):
            problems.append(f"malformed id {mid!r} for {label}")
        if mid in seen:
            problems.append(f"DUPLICATE id {mid} used by both {seen[mid]!r} and {label!r}")
        seen[mid] = label
    for alias, canon in reg["aliases"].items():
        if canon not in reg["ids"]:
            problems.append(f"alias {alias!r} points at {canon!r} which has no id")
        if alias in reg["ids"]:
            problems.append(f"{alias!r} is BOTH an alias and a canonical id holder")
    return problems


def cmd_report(reg, groups):
    print(f"roster: {len(groups)} distinct model(s) from "
          f"{sum(len(v) for v in groups.values())} label(s)")
    syn = {c: s for c, s in groups.items() if len(s) > 1}
    print(f"\nSYNONYM GROUPS ({len(syn)}) — one model, several names:")
    for canon in sorted(syn):
        mid = reg["ids"].get(canon, "(no id yet)")
        others = sorted(n for n in syn[canon] if n != canon)
        print(f"  {mid}  {canon}\n        aka: {', '.join(others)}")
    missing = sorted(c for c in groups if c not in reg["ids"])
    print(f"\nMISSING AN ID ({len(missing)}):")
    for c in missing[:40]:
        print(f"  {c}")
    if len(missing) > 40:
        print(f"  ... and {len(missing) - 40} more")
    problems = audit(reg)
    print(f"\nREGISTRY AUDIT: {'OK' if not problems else str(len(problems)) + ' PROBLEM(S)'}")
    for p in problems:
        print(f"  ! {p}")
    return 1 if problems else 0


def cmd_assign(reg, groups):
    problems = audit(reg)
    if problems:
        print("refusing to assign — fix these registry problems first:")
        for p in problems:
            print(f"  ! {p}")
        return 1
    taken = set(reg["ids"].values())
    added = 0
    for canon in sorted(groups):
        if canon not in reg["ids"]:
            mid = new_id(taken)
            taken.add(mid)
            reg["ids"][canon] = mid
            added += 1
    # record synonyms so a renamed/aliased label still resolves to the same ID next run
    for canon, names in groups.items():
        for n in names:
            if n != canon:
                reg["aliases"][n] = canon
    problems = audit(reg)
    if problems:
        print("ABORT — the assignment would break the contract, nothing written:")
        for p in problems:
            print(f"  ! {p}")
        return 1
    REGISTRY.write_text(json.dumps(reg, indent=2, sort_keys=True) + "\n")
    print(f"assigned {added} new id(s); registry now holds {len(reg['ids'])} model(s) "
          f"and {len(reg['aliases'])} alias(es) -> {REGISTRY}")
    return 0


def cmd_self_test():
    """Verify the contract without touching any repo file."""
    ok = True

    def check(name, cond):
        nonlocal ok
        print(f"  {'PASS' if cond else 'FAIL'}  {name}")
        ok = ok and cond

    check("id format matches the regex", bool(ID_RE.match(new_id(set()))))
    check("alphabet excludes look-alikes I/L/O/U",
          not (set("ILOU") & set(ALPHABET)))
    check("new_id avoids a taken id", new_id({"M-AAAAAA"}) != "M-AAAAAA")

    # assign-once: a second pass must not change an existing id
    reg = {"ids": {"alpha": "M-AAAAAA"}, "aliases": {}}
    groups = {"alpha": {"alpha"}, "beta": {"beta"}}
    taken = set(reg["ids"].values())
    for canon in sorted(groups):
        if canon not in reg["ids"]:
            reg["ids"][canon] = new_id(taken)
            taken.add(reg["ids"][canon])
    check("existing id untouched by a later assign", reg["ids"]["alpha"] == "M-AAAAAA")
    check("new model got a distinct id", reg["ids"]["beta"] != "M-AAAAAA")

    # variant suffixes collapse
    check("_ptm collapses", strip_variant("foo_ptm") == "foo")
    check("_repr collapses", strip_variant("foo_repr") == "foo")
    check("_ptm_repr collapses", strip_variant("foo_ptm_repr") == "foo")
    check("a bare label is unchanged", strip_variant("foo") == "foo")
    check("a suffix-only label is not eaten", strip_variant("_ptm") == "_ptm")

    # audit catches a duplicate id and a dangling alias
    check("audit catches duplicate ids",
          any("DUPLICATE" in p for p in audit({"ids": {"a": "M-AAAAAA", "b": "M-AAAAAA"},
                                               "aliases": {}})))
    check("audit catches a dangling alias",
          any("no id" in p for p in audit({"ids": {}, "aliases": {"x": "ghost"}})))
    check("audit passes a clean registry",
          not audit({"ids": {"a": "M-AAAAAA"}, "aliases": {"a_ptm": "a"}}))
    print("self-test:", "OK" if ok else "FAILED")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="show roster/synonyms/missing, write nothing")
    ap.add_argument("--assign", action="store_true", help="assign ids to models lacking one")
    ap.add_argument("--self-test", action="store_true", help="verify the contract, touch nothing")
    a = ap.parse_args()
    if a.self_test:
        return cmd_self_test()
    reg = load_registry()
    groups = canonicalize(load_roster(), reg)
    if a.assign:
        return cmd_assign(reg, groups)
    return cmd_report(reg, groups)


if __name__ == "__main__":
    sys.exit(main())
