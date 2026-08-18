#!/usr/bin/env python3
"""make_caption_shards.py — pre-distribute the captioning work as one file list per GPU.

WHY (Kim direct, 2026-08-18): the binding constraint is WALL CLOCK — 4 days of compute left, with
~500-600 GPU-hours/day available against the 192 that a single 8-GCD node actually spends. The
captioning work is a FIXED pile of GCD-hours (measured 115 tracks/h/GCD), so spreading it wider
costs the same and finishes sooner. But asking for one huge allocation schedules badly, so the plan
is MANY SMALL JOBS — and small jobs cannot each compute their own sharding, or they would all
compute the SAME shards and caption the same tracks in parallel.

So the assignment is made ONCE, here, before any job is submitted: one text file per GPU, each
listing exactly the tracks that GPU should caption. Jobs then just read their slice. Race-free by
construction, and inspectable — you can read shard_007.txt and know precisely what rank 7 will do.

RESUME IS BUILT IN: only tracks with no existing caption json are listed, so re-running this after a
partial pass re-balances the REMAINING work evenly across all shards. That matters — sharding over
the full track list instead would hand some GPUs mostly-finished shards and others mostly-fresh
ones, and the job would take as long as its unluckiest shard.

USAGE (login node — pure stdlib, no GPU, no container):
  python3 lumi/make_caption_shards.py \
      --archive /scratch/project_465003186/goa_archive \
      --out /scratch/project_465003186/goa_archive_captions_hinted \
      --shards 64

Then submit N jobs, each covering 8 of those shards:
  for O in 0 8 16 24 32 40 48 56; do SHARD_OFFSET=$O sbatch --nodes=1 --time=03:00:00 ...; done
"""
import argparse
import os
from pathlib import Path

AUDIO_EXT = (".mp3", ".flac", ".m4a", ".wav", ".ogg", ".opus")


def key_for(path: Path, archive: Path) -> str:
    """Caption-json stem for a track. MUST match goa_caption_task.py:65 EXACTLY:

        hashlib.sha1(str(p.relative_to(archive)).encode()).hexdigest()

    Note RELATIVE to the archive root, not the absolute path — I wrote the absolute-path version
    first and it matched nothing, which would have silently re-sharded all 23k tracks instead of the
    15.7k remaining. Same keying-mismatch class as the sidecar bug that started this whole episode:
    the two sides agree on the CONCEPT of a key and disagree on its exact form, and nothing errors.
    """
    import hashlib
    return hashlib.sha1(str(path.relative_to(archive)).encode()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", required=True, type=Path, help="corpus root to scan for audio")
    ap.add_argument("--out", required=True, type=Path,
                    help="captions dir (expects/creates out/json and out/shards)")
    ap.add_argument("--shards", type=int, required=True,
                    help="TOTAL number of shards = total GPUs across every job you will submit")
    ap.add_argument("--rate", type=float, default=115.0,
                    help="measured tracks/hour/GCD, for the wall-time estimate (default 115, "
                         "measured on the 2026-08-18 hinted re-caption)")
    ap.add_argument("--all", action="store_true",
                    help="shard EVERY track, not just uncaptioned ones (default is resume-aware)")
    a = ap.parse_args()

    jdir = a.out / "json"
    sdir = a.out / "shards"
    sdir.mkdir(parents=True, exist_ok=True)

    # os.scandir over the tree, not glob — a 23k-file dir defeats shell globbing (ARG_MAX) and
    # `find` has been unreliable on Lustre here; scandir is neither.
    tracks = []
    for root, _dirs, files in os.walk(a.archive):
        for f in files:
            if f.lower().endswith(AUDIO_EXT):
                tracks.append(Path(root) / f)
    tracks.sort()
    if not tracks:
        raise SystemExit(f"[shards] FATAL: no audio found under {a.archive}")

    done = set()
    if jdir.is_dir():
        done = {os.path.splitext(e.name)[0] for e in os.scandir(jdir)
                if e.name.endswith(".json")}

    todo = tracks if a.all else [t for t in tracks if key_for(t, a.archive) not in done]
    # A resume filter that matches NOTHING looks identical to "nothing is done yet". If the caption
    # dir has files but none of our keys hit, the key functions have drifted — say so loudly rather
    # than quietly re-doing thousands of tracks.
    if done and not a.all and len(todo) == len(tracks):
        raise SystemExit(
            f"[shards] FATAL: {len(done)} caption json(s) exist in {jdir} but NONE matched a "
            f"computed key — key_for() has drifted from goa_caption_task.py:65. Refusing to shard, "
            f"because this would silently re-caption every track.")
    print(f"[shards] {len(tracks)} tracks under {a.archive}")
    print(f"[shards] {len(done)} already captioned in {jdir}")
    print(f"[shards] {len(todo)} TO DO -> {a.shards} shards "
          f"({len(todo) / max(1, a.shards):.0f} tracks each)")
    if not todo:
        print("[shards] nothing to do — every track already has a caption json")
        return 0

    # round-robin, so a shard is never a contiguous run of one album (which would make per-shard
    # runtime depend on album length rather than averaging out)
    written = 0
    for s in range(a.shards):
        part = todo[s::a.shards]
        (sdir / f"shard_{s:03d}.txt").write_text("".join(f"{p}\n" for p in part))
        written += len(part)
    assert written == len(todo), f"shard round-trip lost tracks: {written} != {len(todo)}"

    hours = len(todo) / a.rate / a.shards
    print(f"[shards] wrote {a.shards} files to {sdir} (shard_000.txt .. shard_{a.shards-1:03d}.txt)")
    print(f"[shards] every track assigned exactly once ({written} total, verified)")
    print(f"[shards] at {a.rate:.0f} tracks/h/GCD this is ~{len(todo)/a.rate:.0f} GCD-hours of work")
    print(f"[shards]   -> ~{hours:.1f} h wall if all {a.shards} run concurrently")
    print(f"[shards] submit e.g.: for O in {' '.join(str(o) for o in range(0, a.shards, 8))}; "
          f"do SHARD_OFFSET=$O sbatch --nodes=1 --time=03:00:00 lumi/sbatch/goa_caption.sbatch; done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
