#!/usr/bin/env python3
"""Copy LUMI /scratch run_meta.json sidecars down onto the LOCAL checkpoint trees.

WHY (2026-08-25): eval/model_db.py joins each local checkpoint to the run_meta.json it
finds by walking UP from the ckpt to its root. Roughly two thirds of local training arms
had no sidecar -- the weights were rsynced but the small metadata file never was -- so the
eval pages showed no recipe and, worse, no PURPOSE. Kim then cannot tell why a run exists.
Kim rsynced scratch's sidecars to a flat mirror; this walks that mirror and drops each
run_meta.json into every LOCAL run directory that matches the same arm key.

ARM KEY: the path below the run root, minus the filename, with leading `runs`/`lumi_runs`
components stripped -- the same key eval/build_model_census.py joins on. Stripping is what
absorbs the doubled `runs/runs/` rsync artifact on the Mantu drive, and the same arm may
live under more than one root, so every match is written (see Misc/dedupe_model_copies.py).

ADDITIVE ONLY. An existing local run_meta.json is NEVER overwritten -- it is reported as a
conflict, with whether its contents differ from the scratch copy. DEFAULT IS A DRY RUN;
writing requires --apply.

Examples:
  Misc/propagate_run_meta.py --scratch-meta <mirror>                 # dry run
  Misc/propagate_run_meta.py --scratch-meta <mirror> --apply         # write
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))
import model_db                      # noqa: E402
from model_roots import resolve_roots  # noqa: E402

STRIP = ("runs", "lumi_runs")


def _key(parts: list[str]) -> str:
    while parts and parts[0] in STRIP:
        parts = parts[1:]
    return "/".join(parts)


def load_scratch(root: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for p in sorted(root.rglob("run_meta.json")):
        out[_key(list(p.relative_to(root).parts[:-1]))] = p
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scratch-meta", type=Path, required=True,
                    help="local mirror of /scratch/<proj>/runs sidecars")
    ap.add_argument("--apply", action="store_true", help="actually copy (default: dry run)")
    ap.add_argument("--roots", nargs="*", default=None, help="restrict to these root ids")
    args = ap.parse_args()

    scratch = load_scratch(args.scratch_meta)
    print(f"[scratch] {len(scratch)} sidecars in {args.scratch_meta}")

    copied: list[tuple[str, str]] = []
    conflicts: list[tuple[str, str, bool]] = []
    covered = 0
    unmatched: set[str] = set()

    for root in resolve_roots():
        if not root.enabled or not root.available:
            continue
        if args.roots and root.id not in args.roots:
            continue
        base = Path(root.path)
        targets: dict[Path, Path] = {}   # local dir -> scratch sidecar
        seen_dirs: set[Path] = set()
        for e in model_db.scan_root(root):
            d = Path(e["path"]).parent
            if d in seen_dirs:
                continue
            seen_dirs.add(d)
            # walk up from the ckpt dir to the root, first arm-key match wins
            cur, matched = d, None
            while True:
                k = _key(list(cur.relative_to(base).parts))
                if k and k in scratch:
                    matched = (cur, scratch[k])
                    break
                if cur == base:
                    break
                cur = cur.parent
            if matched is None:
                unmatched.add(str(d.relative_to(base)))
                continue
            tdir, src = matched
            if model_db.find_run_meta(Path(e["path"]), base) is not None:
                dst = tdir / "run_meta.json"
                if dst.is_file():
                    try:
                        differs = json.loads(dst.read_text()) != json.loads(src.read_text())
                    except Exception:
                        differs = True
                    conflicts.append((str(dst), str(src), differs))
                else:
                    globals()["_cov"] = None
                continue
            targets[tdir] = src

        for tdir, src in sorted(targets.items()):
            copied.append((str(tdir / "run_meta.json"), str(src)))
            if args.apply:
                shutil.copy2(src, tdir / "run_meta.json")

    conflicts = sorted(set(conflicts))
    print(f"\n[{'COPIED' if args.apply else 'WOULD COPY'}] {len(copied)}")
    for dst, src in copied:
        print(f"  + {dst}")
    print(f"\n[CONFLICT: local sidecar already present, left untouched] {len(conflicts)}")
    for dst, src, differs in conflicts:
        print(f"  ! {'DIFFERS' if differs else 'identical'}  {dst}")
    print(f"\n[no scratch sidecar for] {len(unmatched)} local ckpt dirs")
    if not args.apply:
        print("\n(dry run -- re-run with --apply to write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
