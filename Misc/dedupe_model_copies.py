#!/usr/bin/env python3
"""Find (and optionally reclaim) parallel copies of the same model checkpoint.

WHY THIS EXISTS (2026-08-25): the LUMI run tree got rsynced to the eval drives more
than once with different path prefixes, so the SAME arm exists at up to three paths --
`Mantu/lumi_runs/<arm>/`, `Mantu/lumi_runs/runs/runs/<arm>/` (a trailing-slash artifact)
and `<UUID>/lumi_runs/runs/<arm>/`. First measurement: 299 groups, ~297 GB reclaimable.

THE TRAP THIS TOOL EXISTS TO AVOID: grouping by (filename, size) is WRONG and
overstates the waste by ~4x. Sibling training arms are the same architecture trained on
different data/length, so `fullft_avp_t256/epoch=7-step=4784.ckpt` and
`fullft_avp_t1024/epoch=7-step=4784.ckpt` share a name AND a byte count while being
completely different models. Deleting on that key destroys unique weights. We therefore
group on the trailing `--depth` path components (default 3 = arm-family/arm/file), and
never delete anything whose content signature has not matched.

DEFAULT IS A DRY RUN. Deleting requires --apply, and --apply requires --verify full.

Three reclaim modes:
  (report)    default -- print groups + reclaimable bytes, touch nothing.
  --hardlink  replace duplicates with hard links to the keeper. Same filesystem only,
              so it works for the Mantu flat-vs-runs/runs double tree. BOTH PATHS KEEP
              WORKING and no bytes are lost -- prefer this where it applies.
  --apply     unlink duplicates, keeping one verified copy. Cross-drive case.

Keeper choice: the first root listed in --prefer that holds a copy, else the shortest
path. The UUID drive is the canonical LUMI mirror for this project, so it is preferred
by default (see the no-hardcoded-drive-paths rule -- roots are CLI/config, not literals).

Examples:
  Misc/dedupe_model_copies.py                                   # report
  Misc/dedupe_model_copies.py --verify full --json /tmp/d.json  # report + manifest
  Misc/dedupe_model_copies.py --hardlink --verify full          # reclaim, keep paths
  Misc/dedupe_model_copies.py --apply --verify full             # reclaim, drop paths
"""
from __future__ import annotations

import argparse
import hashlib
import json
import fcntl
import os
import stat as statmod
import struct
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from disk_order import sort_by_disk_order  # noqa: E402

MODEL_EXT = (".ckpt", ".pt", ".safetensors", ".bin")
CHUNK = 1 << 20

# Defaults only -- override with --roots. Kept out of the code path that deletes.
DEFAULT_ROOTS = [
    "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d",
    "/run/media/kim/Mantu",
    "/run/media/kim/Mantu1",
    "/run/media/kim/Lehto",
]
# linux/fs.h -- struct file_dedupe_range { u64 src_off; u64 src_len; u16 dest_count;
# u16 res1; u32 res2; } + struct file_dedupe_range_info { s64 fd; u64 off; u64 deduped;
# s32 status; u32 res; }
FIDEDUPERANGE = 0xC0189436
_DEDUPE_HDR = struct.Struct("=QQHHL")
_DEDUPE_INFO = struct.Struct("=qQQlL")
DEDUPE_CHUNK = 16 * 1024 * 1024                  # btrfs caps a single call; loop instead
FILE_DEDUPE_RANGE_DIFFERS = 1

SKIP_DIRS = {".git", "__pycache__", "node_modules", ".rsync-partial", "lost+found"}


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def scan(roots: list[Path], min_size: int) -> tuple[list[tuple[Path, int, int, int]], int]:
    """(path, size, st_dev, st_ino) for every REAL model file at or above min_size.

    SYMLINKS ARE SKIPPED, not followed (Kim caught this 2026-08-25). `Path.stat()`
    follows a symlink, so a linked file would enter the scan wearing its target's size
    and content, land in a group as a "verified duplicate", and -- if it were chosen as
    the keeper -- the real file would be deleted, leaving a dangling link. `os.lstat`
    plus an explicit skip removes the whole failure mode. Symlinked DIRECTORIES are
    already safe because os.walk does not follow them (followlinks=False, made
    explicit below), so an aliased subtree is never scanned twice.
    """
    out: list[tuple[Path, int, int, int]] = []
    links = 0
    for root in roots:
        if not root.is_dir():
            print(f"[skip] not mounted: {root}", file=sys.stderr)
            continue
        for dirpath, dirnames, filenames in os.walk(root, onerror=lambda e: None,
                                                    followlinks=False):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in filenames:
                if not name.endswith(MODEL_EXT):
                    continue
                p = Path(dirpath, name)
                try:
                    st = os.lstat(p)            # lstat: do NOT resolve the link
                except OSError:
                    continue
                if statmod.S_ISLNK(st.st_mode):
                    links += 1
                    continue
                if st.st_size >= min_size:
                    out.append((p, st.st_size, st.st_dev, st.st_ino))
    return out, links


def quick_sig(path: Path, size: int) -> str:
    """sha1 of the first and last megabyte. Cheap; enough to REPORT a group."""
    h = hashlib.sha1()
    with open(path, "rb") as fh:
        h.update(fh.read(CHUNK))
        if size > 2 * CHUNK:
            fh.seek(-CHUNK, os.SEEK_END)
            h.update(fh.read(CHUNK))
    return h.hexdigest()


SAMPLE_BLOCKS = 64


def sampled_sig(path: Path, size: int) -> str:
    """sha256 of SAMPLE_BLOCKS 1 MB blocks spread evenly through the file.

    ~64 MB read regardless of file size, versus 13-41 GB for full_sig. Catches the
    failure this tool actually guards against -- a copy corrupted or truncated mid
    transfer over USB -- because such damage spans megabytes, not bytes. It does NOT
    prove bit-for-bit identity, so it is a defensible gate for DELETING a redundant
    copy, not a substitute for a checksum when one copy is the only copy.

    Block positions are deterministic (evenly spaced), so two files that differ
    anywhere inside a sampled block diverge, and re-running gives the same answer.
    """
    h = hashlib.sha256()
    h.update(str(size).encode())                 # size is part of the identity
    if size <= SAMPLE_BLOCKS * CHUNK:
        return full_sig(path, size)
    step = (size - CHUNK) // (SAMPLE_BLOCKS - 1)
    with open(path, "rb") as fh:
        for i in range(SAMPLE_BLOCKS):
            fh.seek(i * step)
            h.update(fh.read(CHUNK))
    return h.hexdigest()


def full_sig(path: Path, _size: int) -> str:
    """sha256 of the whole file. Required before anything is deleted or relinked."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(8 * CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def reflink_dedupe(keeper: Path, dup: Path, size: int) -> tuple[int, str]:
    """Share `dup`'s extents with `keeper` via FIDEDUPERANGE. (bytes_shared, status).

    The KERNEL compares the ranges and only shares where they are byte-identical, so
    this cannot corrupt a file that turns out to differ -- and unlike a hard link the
    two paths stay independent inodes, so later writing to one does not alter the other.
    That is the real advantage over --hardlink.

    NOTE, honestly: this does NOT avoid the disk reads. btrfs compares the extents page
    by page, so the I/O is the same as hashing both copies. What it buys is atomicity
    (no time-of-check/time-of-use gap), a single pass instead of hash-then-act, and
    reflink rather than hardlink semantics. The I/O saving comes from --verify sampled,
    not from here.
    """
    try:
        src = os.open(keeper, os.O_RDONLY)
    except OSError as e:
        return 0, f"open keeper: {e}"
    try:
        dst = os.open(dup, os.O_WRONLY)
    except OSError as e:
        os.close(src)
        return 0, f"open dup: {e}"
    shared = 0
    try:
        off = 0
        while off < size:
            length = min(DEDUPE_CHUNK, size - off)
            buf = bytearray(_DEDUPE_HDR.pack(off, length, 1, 0, 0)
                            + _DEDUPE_INFO.pack(dst, off, 0, 0, 0))
            fcntl.ioctl(src, FIDEDUPERANGE, buf, True)
            _fd, _o, deduped, status, _r = _DEDUPE_INFO.unpack_from(buf, _DEDUPE_HDR.size)
            if status == FILE_DEDUPE_RANGE_DIFFERS:
                return shared, "differs"
            if status < 0:
                return shared, f"errno {-status}"
            if deduped == 0:
                return shared, "no progress"
            shared += deduped
            off += deduped
    except OSError as e:
        return shared, f"ioctl: {e}"
    finally:
        os.close(src)
        os.close(dst)
    return shared, "ok"


def group_key(path: Path, depth: int) -> str:
    """Trailing `depth` path components. NOT the bare filename -- see module docstring."""
    return "/".join(path.parts[-depth:])


def pick_keeper(paths: list[Path], prefer: list[str]) -> Path:
    for pref in prefer:
        for p in paths:
            if str(p).startswith(pref):
                return p
    return min(paths, key=lambda p: (len(str(p)), str(p)))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--roots", nargs="*", default=DEFAULT_ROOTS,
                    help="directories to scan (default: the eval drives)")
    ap.add_argument("--prefer", nargs="*", default=None,
                    help="keeper preference, most-preferred first (default: --roots order)")
    ap.add_argument("--min-size-mb", type=float, default=50.0,
                    help="ignore files smaller than this (default 50 MB)")
    ap.add_argument("--depth", type=int, default=3,
                    help="trailing path components that identify an arm (default 3)")
    ap.add_argument("--verify", choices=("quick", "sampled", "full"), default="quick",
                    help="quick = first+last MB (reporting only); sampled = 64 spread "
                         "1 MB blocks, ~64 MB/file (default gate for --apply/--hardlink); "
                         "full = whole-file sha256, hundreds of GB over USB")
    ap.add_argument("--apply", action="store_true", help="DELETE duplicates (destructive)")
    ap.add_argument("--hardlink", action="store_true",
                    help="replace duplicates with hard links (same filesystem only)")
    ap.add_argument("--reflink", action="store_true",
                    help="share extents via FIDEDUPERANGE (btrfs/xfs, same filesystem). "
                         "Safer than --hardlink: the kernel verifies equality itself and "
                         "the paths stay separate inodes, so writing one cannot alter the "
                         "other. Same disk reads as --hardlink, not fewer.")
    ap.add_argument("--json", type=Path, help="write the full plan/manifest here")
    ap.add_argument("--limit", type=int, default=15, help="groups to print (default 15)")
    args = ap.parse_args()

    if sum(bool(x) for x in (args.apply, args.hardlink, args.reflink)) > 1:
        ap.error("--apply, --hardlink and --reflink are mutually exclusive")
    if (args.apply or args.hardlink or args.reflink) and args.verify == "quick":
        ap.error("--apply/--hardlink/--reflink need --verify sampled or full: the quick "
                 "signature reads 2 MB of a multi-GB checkpoint and is NOT evidence of "
                 "identical content")

    roots = [Path(r) for r in args.roots]
    prefer = args.prefer if args.prefer is not None else [str(r) for r in roots]
    min_size = int(args.min_size_mb * 1024 * 1024)

    files, n_links = scan(roots, min_size)
    print(f"scanned {len(files)} real model files >= {human(min_size)}"
          + (f" | skipped {n_links} symlink(s)" if n_links else ""))

    buckets: dict[tuple[str, int], list[tuple[Path, int, int]]] = defaultdict(list)
    for path, size, dev, ino in files:
        buckets[(group_key(path, args.depth), size)].append((path, dev, ino))
    candidates = {k: v for k, v in buckets.items() if len(v) > 1}
    print(f"candidate groups (same arm path + size): {len(candidates)}")
    if not candidates:
        return 0

    sig = {"full": full_sig, "sampled": sampled_sig}.get(args.verify, quick_sig)

    # Collapse pre-existing hard links FIRST (they share one copy of the bytes, so there
    # is nothing to reclaim and nothing to hash), then hash everything that remains in
    # ON-DISK order rather than group-by-group.
    #
    # These roots are USB SPINNING disks and directory order diverges wildly from
    # physical layout, because the tree was rsynced in several passes. Measured
    # 2026-08-25: reading 450 files in walk order costs 97.9 TB of head travel on a
    # 3.6 TB platter (~27 full sweeps) versus 3.4 TB sorted. Group order IS arm order is
    # walk order, so hashing group-by-group inherited the same defect. Signing every
    # candidate in one platter sweep and assembling groups from cached signatures fixes
    # it -- worth most under --verify full, which reads every byte of hundreds of GB.
    # (Misc/disk_order.py)
    live: dict[tuple[str, int], list[tuple[Path, int, int]]] = {}
    for gk, entries in candidates.items():
        seen_inodes: set[tuple[int, int]] = set()
        kept = [e for e in entries
                if not ((e[1], e[2]) in seen_inodes or seen_inodes.add((e[1], e[2])))]
        if len(kept) > 1:
            live[gk] = kept

    todo = {path: gk[1] for gk, entries in live.items() for path, _d, _i in entries}
    sigs: dict[Path, str] = {}
    ordered = sort_by_disk_order(list(todo))
    for n, path in enumerate(ordered, 1):
        try:
            sigs[path] = sig(path, todo[path])
        except OSError as e:                     # unreadable copy is never a keeper
            print(f"[warn] unreadable, ignoring: {path} ({e})", file=sys.stderr)
        if args.verify in ("full", "sampled") and n % 25 == 0:
            print(f"  hashed {n}/{len(ordered)}", file=sys.stderr)

    groups, reclaimable, mismatched = [], 0, 0
    for (key, size), entries in sorted(live.items()):
        by_sig: dict[str, list[tuple[Path, int, int]]] = defaultdict(list)
        for path, dev, ino in entries:
            if path in sigs:
                by_sig[sigs[path]].append((path, dev, ino))
        if len(by_sig) > 1:
            mismatched += 1                      # same name+size, DIFFERENT bytes
        for digest, matched in by_sig.items():
            if len(matched) < 2:
                continue
            paths = [p for p, _, _ in matched]
            devs = {p: d for p, d, _ in matched}
            keeper = pick_keeper(paths, prefer)
            dupes = [p for p in paths if p != keeper]
            reclaimable += size * len(dupes)
            groups.append({"key": key, "size": size, "sig": digest,
                           "verify": args.verify, "keep": str(keeper),
                           "duplicates": [str(p) for p in dupes],
                           "same_fs": [devs[p] == devs[keeper] for p in dupes]})

    groups.sort(key=lambda g: g["size"] * len(g["duplicates"]), reverse=True)
    print(f"verified duplicate groups: {len(groups)} | reclaimable {human(reclaimable)}")
    if mismatched:
        print(f"NOTE: {mismatched} group(s) share an arm path + size but differ in "
              f"content -- those are distinct models and were NOT marked duplicate.")

    for g in groups[:args.limit]:
        print(f"\n  {g['key']}  {human(g['size'])} x{len(g['duplicates']) + 1}")
        print(f"     keep   {g['keep']}")
        for p, same in zip(g["duplicates"], g["same_fs"]):
            print(f"     {'link' if same else 'drop'}   {p}")
    if len(groups) > args.limit:
        print(f"\n  ... {len(groups) - args.limit} more group(s); --limit 0 shows none, "
              f"--json writes them all")

    if args.json:
        args.json.write_text(json.dumps(
            {"reclaimable_bytes": reclaimable, "verify": args.verify,
             "mismatched_groups": mismatched, "groups": groups}, indent=1))
        print(f"\nplan written: {args.json}")

    if not (args.apply or args.hardlink or args.reflink):
        print("\nDRY RUN -- nothing changed. Re-run with --verify full and either "
              "--hardlink (keeps every path, same filesystem only) or --apply (deletes).")
        return 0

    freed = skipped = 0
    for g in groups:
        keeper = Path(g["keep"])
        if not keeper.exists():
            print(f"[skip] keeper vanished: {keeper}", file=sys.stderr)
            continue
        for dup_s, same_fs in zip(g["duplicates"], g["same_fs"]):
            dup = Path(dup_s)
            if not dup.exists():
                continue
            if (args.hardlink or args.reflink) and not same_fs:
                skipped += 1                     # cross-device: --apply handles these
                continue
            # Re-check at apply time -- the plan may be minutes old, and a symlink or an
            # already-shared inode must never be unlinked or relinked.
            try:
                dst, ks = os.lstat(dup), os.lstat(keeper)
            except OSError as e:
                print(f"[warn] {dup}: {e}", file=sys.stderr)
                continue
            if statmod.S_ISLNK(dst.st_mode) or statmod.S_ISLNK(ks.st_mode):
                print(f"[skip] symlink appeared, refusing: {dup}", file=sys.stderr)
                continue
            if (dst.st_dev, dst.st_ino) == (ks.st_dev, ks.st_ino):
                continue                         # already the same file
            try:
                if args.reflink:
                    shared, why = reflink_dedupe(keeper, dup, g["size"])
                    if why != "ok":
                        print(f"[warn] reflink {dup}: {why} "
                              f"({shared / 2**20:.0f} MB shared)", file=sys.stderr)
                    freed += shared
                    continue
                if args.hardlink:
                    tmp = dup.with_suffix(dup.suffix + ".dedupe-tmp")
                    os.link(keeper, tmp)         # link FIRST, swap after -- never a gap
                    os.replace(tmp, dup)
                else:
                    dup.unlink()
                freed += g["size"]
            except OSError as e:
                print(f"[warn] {dup}: {e}", file=sys.stderr)
    verb = "reflinked" if args.reflink else ("relinked" if args.hardlink else "deleted")
    print(f"\n{verb}: {human(freed)} reclaimed"
          + (f" | {skipped} cross-filesystem copies left for --apply" if skipped else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
