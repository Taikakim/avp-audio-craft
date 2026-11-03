#!/usr/bin/env python3
"""Backfill local run_meta.json sidecars from the LUMI /scratch mirror.

Kim rsynced /scratch's small sidecars to <EVALUUID>/lumi_runs/_scratch_meta/ —
one run_meta.json per arm, mirroring /scratch/project_465003186/runs/<arm...>/.
Many of those arms have their CHECKPOINTS local but never got their sidecar, so
eval/model_db.find_run_meta() (which walks UP from the checkpoint to the root)
finds nothing and the eval pages show no recipe and, worse, no PURPOSE.

This copies each scratch sidecar into every local run directory for the same arm.
ADDITIVE ONLY: an existing local run_meta.json is NEVER overwritten — it is
reported as a conflict, with whether the JSON payload differs.

Roots come from eval/model_roots.json (no drive paths in code; the eval drive
mounts as Mantu or Mantu1).

    Misc/backfill_run_meta_sidecars.py                    # dry run (default)
    Misc/backfill_run_meta_sidecars.py --apply --jobs 10
    Misc/backfill_run_meta_sidecars.py --residue          # rebuild DB, list gaps
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import model_db  # noqa: E402
from disk_order import sort_by_disk_order  # noqa: E402

SCAN_SUFFIXES = model_db.SCAN_SUFFIXES
# leading path segments that sit between a root and the arm key (the doubled
# runs/runs is an rsync artifact on Mantu — see Misc/dedupe_model_copies.py)
PREFIXES = ("", "runs", "runs/runs", "lumi_runs", "lumi_runs/runs")


def scratch_arm_key(p: Path, meta_root: Path) -> str:
    parts = list(p.relative_to(meta_root).parts)[:-1]      # drop run_meta.json
    while parts and parts[0] == "runs":
        parts = parts[1:]
    return "/".join(parts) or "(root)"


def dir_has_ckpt(d: str) -> bool:
    for dirpath, dirnames, filenames in os.walk(d):
        dirnames[:] = [x for x in dirnames if not x.startswith(".")]
        for fn in filenames:
            if fn.endswith(SCAN_SUFFIXES):
                return True
    return False


def _probe(job: tuple) -> tuple:
    key, root_id, cand = job
    return key, root_id, cand, dir_has_ckpt(cand)


def collect(meta_root: Path, roots, jobs: int) -> tuple[list, list]:
    metas = sorted(meta_root.rglob("run_meta.json"))
    by_key = {scratch_arm_key(p, meta_root): p for p in metas}

    candidates = []
    for key, src in by_key.items():
        for r in roots:
            if not r.enabled or not r.available:
                continue
            base = Path(r.path)
            for pre in PREFIXES:
                cand = base / pre / key if pre else base / key
                if cand.is_dir():
                    candidates.append((key, r.id, str(cand)))

    hits = []
    if candidates:
        # same seek argument as do_residue(): walk the candidate dirs in on-disk
        # order and give each worker one contiguous slice.
        order = {p: i for i, p in enumerate(sort_by_disk_order([c[2] for c in candidates]))}
        candidates.sort(key=lambda c: order.get(c[2], 0))
        chunk = max(1, -(-len(candidates) // max(1, jobs)))
        with ProcessPoolExecutor(max_workers=jobs) as ex:
            for key, root_id, cand, ok in ex.map(_probe, candidates, chunksize=chunk):
                if ok:
                    hits.append((key, root_id, Path(cand), by_key[key]))
    return metas, hits


def ancestor_meta(d: Path, root: Path) -> Path | None:
    """run_meta.json at d or above it, up to (and including) the root."""
    cur = d
    root = root.resolve()
    while True:
        c = cur / "run_meta.json"
        if c.is_file():
            return c
        if cur.resolve() == root or cur.parent == cur:
            return None
        cur = cur.parent


def do_propagate(args, roots) -> dict:
    meta_root = Path(args.scratch_meta)
    metas, hits = collect(meta_root, roots, args.jobs)
    rootpath = {r.id: Path(r.path) for r in roots}

    copied, conflicts, covered = [], [], []
    for key, root_id, d, src in sorted(hits):
        own = d / "run_meta.json"
        if own.is_file():
            try:
                same = json.loads(own.read_text()) == json.loads(src.read_text())
            except Exception:
                same = None
            conflicts.append((key, root_id, str(own), same))
            continue
        anc = ancestor_meta(d, rootpath[root_id])
        if anc is not None:
            covered.append((key, root_id, str(anc)))
            continue
        if args.apply:
            shutil.copy2(src, own)
        copied.append((key, root_id, str(own)))

    print(f"scratch sidecars: {len(metas)} | arm dirs with local ckpts matched: {len(hits)}")
    print(f"{'COPIED' if args.apply else 'WOULD COPY'}: {len(copied)}")
    for k, rid, dst in copied:
        print(f"  + [{rid}] {k}")
    print(f"CONFLICT (local run_meta.json already present, left untouched): {len(conflicts)}")
    for k, rid, dst, same in conflicts:
        tag = "identical" if same is True else ("DIFFERS" if same is False else "unreadable")
        print(f"  ! [{rid}] {k}  ({tag})")
    print(f"covered by an ancestor run_meta.json already: {len(covered)}")
    for k, rid, anc in covered:
        print(f"  = [{rid}] {k}")
    return {"copied": copied, "conflicts": conflicts, "covered": covered}


# ---------------------------------------------------------------- residue ---
def _record(job):
    path, root_dict, overrides = job
    root = model_db.Root(**root_dict)
    return model_db.record_for(path, root, overrides)


def do_residue(args, roots) -> None:
    """Parallel equivalent of model_db.load_or_build(rescan=True) + gap report."""
    overrides = model_db._load_overrides(model_db.OVERRIDES_PATH)
    by_root = {}
    models = []
    for r in roots:
        if not r.enabled or not r.available:
            continue
        entries = model_db.scan_root(r)
        rd = r.__dict__ if hasattr(r, "__dict__") else r._asdict()
        # ON-DISK ORDER, not walk order. These roots are USB SPINNING disks; probing
        # a checkpoint reads its header, so the job is one seek per file and the
        # ORDER is what costs. Measured 2026-08-25 over the real file sets: walk
        # order 54.4 TB (sa3_lora_runs) / 97.9 TB (lumi_runs) of head travel vs
        # 4.5 / 3.4 TB sorted -- 12x and 29x. sort_by_disk_order() keys on the
        # FIEMAP first-extent offset (inode order as fallback), namespaced by st_dev.
        paths = sort_by_disk_order([e["path"] for e in entries])
        jobs = [(p, dict(rd), overrides) for p in paths]
        # ONE CONTIGUOUS SLICE PER WORKER: a small chunksize would round-robin the
        # sorted list back into an interleaved seek pattern, undoing the sort.
        chunk = max(1, -(-len(jobs) // max(1, args.jobs)))
        with ProcessPoolExecutor(max_workers=args.jobs) as ex:
            recs = list(ex.map(_record, jobs, chunksize=chunk))
        by_root[r.id] = {"scanned_at": time.time(), "path": r.path, "models": recs}
        models.extend(recs)
        print(f"[scan] {r.id}: {len(recs)} checkpoints", file=sys.stderr)
    # MERGE, never replace: shards run one per physical spindle, so a plain write
    # would drop the other shard's roots from the journal the census reads.
    j = model_db._read_journal() or {}
    cached = j.get("roots") or {}
    if j.get("schema") != model_db.SCHEMA_VERSION:
        cached = {}
    cached.update(by_root)
    model_db._write_journal({"schema": model_db.SCHEMA_VERSION, "roots": cached})

    arms = defaultdict(lambda: {"size": 0, "n": 0, "purpose": None, "corpus": None,
                                "roots": set()})
    for m in models:
        base = m.get("_root_path")
        try:
            parts = list(Path(m["path"]).relative_to(base).parts)
        except Exception:
            parts = list(Path(m["path"]).parts)
        while parts and parts[0] in ("runs", "lumi_runs"):
            parts = parts[1:]
        key = "/".join(parts[:-1]) or "(root)"
        a = arms[key]
        a["size"] += int(m.get("size") or 0)
        a["n"] += 1
        a["roots"].add(m.get("root_id") or "?")
        a["purpose"] = a["purpose"] or m.get("purpose")
        a["corpus"] = a["corpus"] or m.get("corpus")

    have_p = sum(1 for a in arms.values() if a["purpose"])
    have_c = sum(1 for a in arms.values() if a["corpus"])
    print(f"\nlocal arms: {len(arms)} | with purpose: {have_p} | with corpus: {have_c}")

    miss = [(k, a) for k, a in arms.items() if not a["purpose"]]
    byroot = defaultdict(list)
    for k, a in miss:
        byroot[",".join(sorted(a["roots"]))].append((k, a))
    print(f"\nARMS STILL MISSING PURPOSE: {len(miss)} (by root, largest first)")
    for rid in sorted(byroot, key=lambda r: -sum(a["size"] for _, a in byroot[r])):
        rows = sorted(byroot[rid], key=lambda x: -x[1]["size"])
        tot = sum(a["size"] for _, a in rows) / 1e9
        print(f"\n## {rid} — {len(rows)} arms, {tot:.1f} GB")
        for k, a in rows[:args.top]:
            print(f"  {a['size']/1e9:8.2f} GB  {a['n']:3d} ckpt  {k}")
        if len(rows) > args.top:
            print(f"  ... {len(rows)-args.top} more")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scratch-meta", default=None,
                    help="dir of mirrored run_meta.json (default: <EVALUUID>/lumi_runs/_scratch_meta)")
    ap.add_argument("--apply", action="store_true", help="actually copy (default: dry run)")
    ap.add_argument("--dry-run", action="store_true", default=True, help=argparse.SUPPRESS)
    ap.add_argument("--residue", action="store_true",
                    help="rebuild the model DB in parallel and list arms with no purpose")
    # 3, not 10: the model roots live on USB SPINNING disks (rotational=1, Seagate
    # BUP BK). Measured 2026-08-25 with --jobs 10 on one spindle: 98.5% busy for
    # 1.9 MB/s -- pure seek thrash, ~1% of the drive's sequential rate. A shallow queue
    # lets bfq order the seeks; a deep one just lengthens them. Shard by DRIVE
    # (--root-ids) and run one small pool per spindle rather than one big pool.
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--root-ids", default=None,
                    help="comma list of root ids to restrict to (shard by drive, so "
                         "each physical spindle gets its own small pool)")
    ap.add_argument("--top", type=int, default=25)
    args = ap.parse_args()

    roots = model_db.resolve_roots()
    if args.root_ids:
        want = {x.strip() for x in args.root_ids.split(",") if x.strip()}
        roots = [r for r in roots if r.id in want]
        if not roots:
            print(f"no roots match --root-ids {args.root_ids!r}", file=sys.stderr)
            return 2
        print(f"[shard] roots: {', '.join(r.id for r in roots)}")
    if args.scratch_meta is None:
        for r in roots:
            c = Path(r.path).parent / "lumi_runs" / "_scratch_meta"
            c2 = Path(r.path) / "_scratch_meta"
            if c2.is_dir():
                args.scratch_meta = str(c2)
                break
            if c.is_dir():
                args.scratch_meta = str(c)
                break
    if args.residue:
        do_residue(args, roots)
        return 0
    if args.scratch_meta is None or not Path(args.scratch_meta).is_dir():
        print("no scratch-meta dir found (drive unmounted?)", file=sys.stderr)
        return 2
    do_propagate(args, roots)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
