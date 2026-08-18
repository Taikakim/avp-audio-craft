#!/usr/bin/env python3
"""make_caption_shards.py — pre-distribute per-GPU work lists for the caption pipeline.

TWO MODES, because both stages of the pipeline have the same shape (a big pile of independent
per-track work, resumable, wanting to run as wide as the scheduler allows):
  --mode caption  items = audio files under --archive; done = out/json/<sha1(relpath)>.json
  --mode granite  items = MF caption jsons under --captions-json; done = out/<same basename>.json
Kept as ONE tool on purpose: a second near-identical shard maker is exactly the duplication that
has bitten this repo twice in 24h (two sidecar re-keyers, two caption auditors).


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

AUDIO_EXT = (".mp3", ".flac", ".m4a", ".wav", ".ogg", ".opus", ".aiff", ".aif")


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
    ap.add_argument("--mode", choices=("caption", "granite"), default="caption",
                    help="caption: shard AUDIO for Music Flamingo. granite: shard MF CAPTION JSONS "
                         "for the Granite revision pass.")
    ap.add_argument("--archive", type=Path, help="[caption] corpus root to scan for audio")
    ap.add_argument("--captions-json", type=Path,
                    help="[granite] dir of MF caption jsons to revise (…/json)")
    ap.add_argument("--out", required=True, type=Path,
                    help="[caption] captions dir (uses out/json, writes out/shards). "
                         "[granite] the GRANITE output dir (writes out/shards)")
    ap.add_argument("--shards", type=int, required=True,
                    help="TOTAL number of shards = total GPUs across every job you will submit")
    ap.add_argument("--rate", type=float, default=115.0,
                    help="measured tracks/hour/GCD, for the wall-time estimate (default 115, "
                         "measured on the 2026-08-18 hinted re-caption)")
    ap.add_argument("--name", default=None,
                    help="only shard files with this exact basename, e.g. full_mix.flac. REQUIRED "
                         "for stem-separated corpora: Goa_Separated has drums/bass/other/vocals "
                         "beside each full_mix, and an extension glob captions the stems as if they "
                         "were tracks (caught 2026-08-18 when a shard run found 2707 'tracks' in a "
                         "2676-track corpus -- the extra 31 were stems from an in-flight upload).")
    ap.add_argument("--stem", default=None,
                    help="only shard files whose basename WITHOUT extension is this, e.g. full_mix. "
                         "Prefer this over --name for stem-separated corpora: --name pins ONE "
                         "container format, and Goa_Separated is not uniform -- 3150 full_mix.flac "
                         "but also 722 .mp3, 474 .ogg, 96 .m4a, 10 .wav, 9 .aiff. `--name "
                         "full_mix.flac` therefore drops 29%% of the corpus and reports a clean "
                         "count while doing it (caught 2026-08-18, after --name itself was added "
                         "that morning to fix the opposite problem of shells sweeping in stems).")
    ap.add_argument("--all", action="store_true",
                    help="shard EVERY track, not just uncaptioned ones (default is resume-aware)")
    a = ap.parse_args()

    sdir = a.out / "shards"
    sdir.mkdir(parents=True, exist_ok=True)

    if a.mode == "granite":
        if not a.captions_json or not a.captions_json.is_dir():
            raise SystemExit("[shards] FATAL: --mode granite needs --captions-json <dir of MF jsons>")
        # Granite's own skip test is basename-based (goa_granite_task.py:114:
        #   todo = [p for p in paths if not exists(join(out, basename(p)))]), so match it exactly.
        items = sorted(Path(e.path) for e in os.scandir(a.captions_json)
                       if e.name.endswith(".json"))
        done = {e.name for e in os.scandir(a.out) if e.name.endswith(".json")} \
            if a.out.is_dir() else set()
        todo = items if a.all else [p for p in items if p.name not in done]
        print(f"[shards] mode=granite: {len(items)} MF caption jsons under {a.captions_json}")
        print(f"[shards] {len(done)} already revised in {a.out}")
        _emit(todo, sdir, a.shards, a.rate)
        # Granite can only revise captions that EXIST. If the MF pass is still running, this shards
        # a moving target — say so rather than let someone shard 8k and wonder where the rest went.
        print(f"[shards] NOTE granite can only cover captions that exist NOW. If the MF pass is "
              f"still running, re-run this and resubmit when it finishes to pick up the rest.")
        return 0

    jdir = a.out / "json"

    # os.scandir over the tree, not glob — a 23k-file dir defeats shell globbing (ARG_MAX) and
    # `find` has been unreliable on Lustre here; scandir is neither.
    tracks = []
    for root, _dirs, files in os.walk(a.archive):
        for f in files:
            if a.stem:
                base, ext = os.path.splitext(f)
                if base == a.stem and ext.lower() in AUDIO_EXT:
                    tracks.append(Path(root) / f)
            elif a.name:
                if f == a.name:
                    tracks.append(Path(root) / f)
            elif f.lower().endswith(AUDIO_EXT):
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
    if a.stem:
        # Report the format mix. A stem-matched corpus that is 100% one extension is fine; one that
        # is not tells you immediately what a --name run would have silently excluded.
        import collections
        mix = collections.Counter(t.suffix.lower() for t in tracks)
        print(f"[shards] formats: {dict(mix.most_common())}")
    print(f"[shards] {len(tracks)} tracks under {a.archive}")
    print(f"[shards] {len(done)} already captioned in {jdir}")
    _emit(todo, sdir, a.shards, a.rate)
    return 0


def _emit(todo, sdir, shards, rate):
    """Round-robin the work into `shards` files and report the cost. Round-robin (not contiguous
    blocks) so a shard is never one long album — otherwise per-shard runtime tracks album length
    instead of averaging out, and the campaign waits on its unluckiest shard."""
    if not todo:
        print("[shards] nothing to do — every item already has an output")
        return
    written = 0
    for s in range(shards):
        part = todo[s::shards]
        (sdir / f"shard_{s:03d}.txt").write_text("".join(f"{p}\n" for p in part))
        written += len(part)
    assert written == len(todo), f"shard round-trip lost items: {written} != {len(todo)}"
    print(f"[shards] {len(todo)} TO DO -> {shards} shards ({len(todo)/max(1,shards):.0f} each)")
    print(f"[shards] wrote {shards} files to {sdir} (shard_000.txt .. shard_{shards-1:03d}.txt)")
    print(f"[shards] every item assigned exactly once ({written} total, verified)")
    print(f"[shards] at {rate:.0f} items/h/GCD this is ~{len(todo)/rate:.0f} GCD-hours of work")
    print(f"[shards]   -> ~{len(todo)/rate/shards:.1f} h wall if all {shards} run concurrently")
    print(f"[shards] submit: for O in {' '.join(str(o) for o in range(0, shards, 8))}; "
          f"do SHARD_OFFSET=$O sbatch --nodes=1 --time=03:00:00 <the sbatch>; done")


if __name__ == "__main__":
    raise SystemExit(main())
