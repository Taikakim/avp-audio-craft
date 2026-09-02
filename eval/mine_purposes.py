#!/usr/bin/env python3
"""Tier-1 purpose miner — join census arms to the sbatch that launched them, and pull that
script's header comment.

WHY (Kim 2026-09-02): 273 of 363 census arms have no `purpose`; Kim on his own runs: "I don't
remember what all of these were about anymore." THE-FINN's pilot established a two-tier method
(DM 2026-09-02): Tier 1 = the sbatch HEADER COMMENT, which is ~free and gave STRONG purpose on
2 of 3 pilot arms; Tier 2 = transcript archaeology in ~/.claude/projects, which is bounded but
costly and only needed where no sbatch exists or the WHY/citations matter.

THE POINT OF THIS SCRIPT: Tier 1 is a JOIN, not a reading task. Many arms share one sbatch, so
the human/agent judgement needed is ONE purpose line per HEADER, not per arm -- that collapses
the job by roughly an order of magnitude. This does the join deterministically and hands back
the distinct headers to write against.

Writes NOTHING. Output is a review bundle; purposes land in Misc/models_index_overrides.json
(keys `purpose`/`purpose_evidence`/`purpose_confidence`) -- never in the generated census.

  eval/mine_purposes.py --out eval/purpose_candidates.json
"""
import argparse, csv, json, re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SBATCH_DIR = ROOT / "lumi" / "sbatch"


def header_of(text: str) -> str:
    """Leading comment block, minus the shebang and the #SBATCH directives (those are
    resources, not intent)."""
    out = []
    for line in text.splitlines():
        if line.startswith("#!"):
            continue
        if not line.startswith("#"):
            if out:
                break
            continue
        if re.match(r"#\s*SBATCH\b", line):
            continue
        out.append(line.lstrip("#").rstrip())
    return "\n".join(out).strip()


def arm_tokens(arm: str) -> list[str]:
    """Names worth searching a script for: the full arm, its leaf, and its run dir."""
    parts = [p for p in arm.split("/") if p and p != "(root)"]
    toks = [arm] + parts
    # strip a trailing -vN duplicate marker; those are DDP rank collisions, same run
    toks += [re.sub(r"-v\d+$", "", t) for t in toks]
    return [t for t in dict.fromkeys(toks) if len(t) >= 6]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--census", type=Path, default=ROOT / "eval" / "model_census.csv")
    ap.add_argument("--out", type=Path, default=ROOT / "eval" / "purpose_candidates.json")
    ap.add_argument("--all", action="store_true",
                    help="include arms that already have a purpose (default: only the gaps)")
    args = ap.parse_args()

    rows = list(csv.DictReader(args.census.open()))
    arms = [r for r in rows if args.all or not (r.get("purpose") or "").strip()]

    scripts = {}
    for p in sorted(SBATCH_DIR.glob("*.sbatch")):
        t = p.read_text(errors="ignore")
        # ROLE MATTERS, and content-matching alone cannot see it: a RENDER script NAMES the
        # training runs it renders, so it matches their arms just as strongly as the script
        # that actually trained them. First version of this miner handed 44 dorlor_ab arms to
        # a11_full_render.sbatch (a renderer) instead of dorlor_ab.sbatch (their trainer).
        # A trainer is a script that actually invokes the trainer entry point.
        role = "trainer" if re.search(r"train_lora|train\.py", t) else "other"
        scripts[p.name] = {"text": t, "header": header_of(t), "role": role}

    matched: dict[str, list] = defaultdict(list)
    unmatched = []
    for r in arms:
        arm = r["arm"]
        hits = []
        for name, s in scripts.items():
            for tok in arm_tokens(arm):
                if tok in s["text"]:
                    # rank: trainers before non-trainers, then leaf/full-name before run-dir
                    role_rank = 0 if s["role"] == "trainer" else 1
                    name_rank = 0 if tok in (arm, arm.split("/")[-1]) else 1
                    hits.append((role_rank, name_rank, name, tok))
                    break
        if not hits:
            unmatched.append(arm)
            continue
        hits.sort()
        role_rank, name_rank, name, tok = hits[0]
        matched[name].append({
            "arm": arm, "matched_on": tok,
            "via": "trainer" if role_rank == 0 else "NON-TRAINER (no training script matched)",
            "strength": "strong" if (role_rank == 0 and name_rank == 0) else "weak",
            "other_candidates": sorted({h[2] for h in hits[1:]})})

    bundle = {
        "_doc": ("Tier-1 purpose-mining bundle, produced by eval/mine_purposes.py. One entry per "
                 "SBATCH: write ONE purpose line against its `header`, then apply it to every arm "
                 "in `arms`. Land results in Misc/models_index_overrides.json under `purpose` / "
                 "`purpose_evidence` / `purpose_confidence` -- NEVER in the generated census. "
                 "Arms in `_unmatched` have no sbatch and are the Tier-2 (transcript) queue."),
        "_stats": {"arms_considered": len(arms), "arms_matched": sum(len(v) for v in matched.values()),
                   "distinct_headers": len(matched), "arms_unmatched": len(unmatched)},
        "by_sbatch": {k: {"role": scripts[k]["role"], "header": scripts[k]["header"], "arms": v}
                      for k, v in sorted(matched.items(), key=lambda kv: -len(kv[1]))},
        "_unmatched": sorted(unmatched),
    }
    args.out.write_text(json.dumps(bundle, indent=1, ensure_ascii=False) + "\n")
    st = bundle["_stats"]
    print(f"arms considered : {st['arms_considered']}")
    print(f"  matched       : {st['arms_matched']}  across {st['distinct_headers']} distinct sbatch headers")
    print(f"  unmatched     : {st['arms_unmatched']}  -> Tier-2 queue")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
