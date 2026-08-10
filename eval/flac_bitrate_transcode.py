#!/usr/bin/env python3
"""
flac_bitrate_transcode.py -- build the 5 parallel corpus versions for the
MP3-bitrate training A/B (SA3 full-FT).

Takes a filelist of VERIFIED-lossless full_mix.flac paths (produced by the Goa
provenance scan, `goa_flac_verified_lossless.txt`) and materialises FIVE parallel
corpus dirs under an output root, preserving relative structure:

    <out>/flac/     <rel>.flac        (verbatim copy of the source FLAC)
    <out>/mp3_320/  <rel>.mp3         (libmp3lame CBR 320k)
    <out>/mp3_256/  <rel>.mp3         (libmp3lame CBR 256k)
    <out>/mp3_192/  <rel>.mp3         (libmp3lame CBR 192k)
    <out>/mp3_128/  <rel>.mp3         (libmp3lame CBR 128k)

The MP3 arms are the SOURCE-BITRATE variable of the experiment; every downstream
step (pre-encode, captions, seed, training config) is held identical across the
five arms so that source bitrate is the only thing that differs.

Relative path derivation
------------------------
Each source is <corpus_root>/<ARTIST - TITLE>/full_mix.flac. We key each track by
its parent dir name (the "ARTIST - TITLE" folder), so the materialised file is
<out>/<arm>/<ARTIST - TITLE>.<ext>. Pass --corpus-root to strip a common prefix
instead if you prefer deeper nesting.

Idempotent: skips any target that already exists with non-zero size (unless
--force). Safe to re-run / resume after interruption.

NOTE: This script only STAGES corpora. It launches NO training. The training
sbatch is intentionally not written yet (depends on LUMI-vs-local encode host --
Kim's call). See DESIGN.md.
"""
import argparse
import os
import shutil
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

FFMPEG = "/usr/bin/ffmpeg"

# arm name -> ffmpeg libmp3lame args (None = verbatim FLAC copy)
ARMS = {
    "flac": None,
    "mp3_320": ["-c:a", "libmp3lame", "-b:a", "320k"],
    "mp3_256": ["-c:a", "libmp3lame", "-b:a", "256k"],
    "mp3_192": ["-c:a", "libmp3lame", "-b:a", "192k"],
    "mp3_128": ["-c:a", "libmp3lame", "-b:a", "128k"],
}


def rel_key(src, corpus_root):
    """Derive the relative stem (without extension) for a source flac."""
    if corpus_root:
        rel = os.path.relpath(src, corpus_root)
        stem = os.path.splitext(rel)[0]
        # collapse the trailing '/full_mix' so the track name carries identity
        if os.path.basename(stem) == "full_mix":
            stem = os.path.dirname(stem)
        return stem
    # default: use the parent-dir name ("ARTIST - TITLE")
    return os.path.basename(os.path.dirname(src))


def target_path(out_root, arm, stem):
    ext = "flac" if arm == "flac" else "mp3"
    return os.path.join(out_root, arm, f"{stem}.{ext}")


def transcode_one(args_tuple):
    src, out_root, corpus_root, force, caption = args_tuple
    stem = rel_key(src, corpus_root)
    results = []
    for arm, aargs in ARMS.items():
        dst = target_path(out_root, arm, stem)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        # write the generic caption .txt sibling that train_lora's --data_dir
        # caption_metadata_fn reads (identical caption in every arm -> bitrate is
        # the only variable). Cheap; (re)write always so it can never go missing.
        if caption:
            with open(os.path.splitext(dst)[0] + ".txt", "w") as cf:
                cf.write(caption + "\n")
        if (not force) and os.path.exists(dst) and os.path.getsize(dst) > 0:
            results.append((arm, "skip"))
            continue
        tmp = dst + ".tmp"
        try:
            if aargs is None:
                shutil.copyfile(src, tmp)
            else:
                # -f mp3 is required because the .tmp suffix hides the extension
                cmd = [FFMPEG, "-v", "error", "-y", "-i", src,
                       *aargs, "-map_metadata", "-1", "-f", "mp3", tmp]
                p = subprocess.run(cmd, capture_output=True, timeout=600)
                if p.returncode != 0:
                    results.append((arm, "FAIL:" + p.stderr.decode()[:120]))
                    if os.path.exists(tmp):
                        os.remove(tmp)
                    continue
            os.replace(tmp, dst)
            results.append((arm, "ok"))
        except Exception as e:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
            results.append((arm, "FAIL:" + str(e)[:120]))
    return src, results


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--filelist", required=True,
                    help="text file, one verified-lossless full_mix.flac path per line")
    ap.add_argument("--out-root", required=True,
                    help="output root; arm subdirs (flac/, mp3_320/, ...) created under it")
    ap.add_argument("--corpus-root", default="",
                    help="optional common prefix to strip for nested rel paths; "
                         "default keys each track by its parent-dir name")
    ap.add_argument("--workers", type=int, default=min(12, os.cpu_count() or 4))
    ap.add_argument("--force", action="store_true",
                    help="re-encode even if target exists")
    ap.add_argument("--caption", default="goa trance, psychedelic",
                    help="generic caption written to a .txt sibling of every clip "
                         "(identical across arms so bitrate is the only variable). "
                         "Empty string disables caption sidecars.")
    ap.add_argument("--limit", type=int, default=0,
                    help="process only first N tracks (controlled A/B subset; "
                         "DESIGN caps ~1200 for a manageable 5x transcode + transfer)")
    args = ap.parse_args()

    with open(args.filelist) as f:
        srcs = [ln.strip() for ln in f if ln.strip()]
    if args.limit:
        srcs = srcs[:args.limit]
    missing = [s for s in srcs if not os.path.exists(s)]
    if missing:
        print(f"WARNING: {len(missing)} listed paths do not exist; skipping them",
              file=sys.stderr)
        srcs = [s for s in srcs if os.path.exists(s)]

    print(f"transcoding {len(srcs)} tracks x {len(ARMS)} arms -> {args.out_root}")
    for arm in ARMS:
        os.makedirs(os.path.join(args.out_root, arm), exist_ok=True)

    n_ok = n_skip = n_fail = 0
    done = 0
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(transcode_one,
                          (s, args.out_root, args.corpus_root, args.force, args.caption))
                for s in srcs]
        for fut in as_completed(futs):
            src, res = fut.result()
            for arm, status in res:
                if status == "ok":
                    n_ok += 1
                elif status == "skip":
                    n_skip += 1
                else:
                    n_fail += 1
                    print(f"  FAIL {arm} {os.path.basename(os.path.dirname(src))}: {status}",
                          file=sys.stderr)
            done += 1
            if done % 100 == 0:
                print(f"  {done}/{len(srcs)} tracks", flush=True)

    print(f"DONE: {n_ok} encoded, {n_skip} skipped (idempotent), {n_fail} failed")
    if n_fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
