#!/usr/bin/env python3
"""Sort file paths into ON-DISK order before reading them.

WHY (measured 2026-08-25): the model roots live on USB SPINNING disks
(`rotational=1`, Seagate BUP BK). Walking ~2100 checkpoints in directory/arm order and
reading each one's header makes the head jump all over the platter. With a 10-worker
pool that measured **98.5% busy for 1.9 MB/s** -- about 1% of the drive's sequential
rate. Nearly all of that time is seek, not transfer, and no amount of pool tuning fixes
it: the access ORDER is the problem, not the concurrency.

Reading in physical order turns a random-seek workload into a mostly one-directional
sweep across the platter, which is what the drive is fast at. This is the same trick
`e2fsck`, backup tools and defragmenters use.

How the physical key is obtained, best first:
  1. **FIEMAP ioctl** -- asks the filesystem for the physical byte offset of the file's
     first extent. Works on ext4, btrfs, xfs, f2fs. This is the real answer.
  2. **inode number** -- fallback when FIEMAP is unsupported or fails (some FUSE mounts,
     exFAT/NTFS on a USB caddy). A weak proxy, but files written by one rsync run get
     sequential inodes, so inode order approximates write order approximates layout.

Both keys are namespaced by `st_dev`, so a mixed list spanning two drives sorts into
per-drive runs rather than interleaving two heads.

Usage:
    from disk_order import sort_by_disk_order
    for path in sort_by_disk_order(paths):     # same paths, seek-friendly order
        read_header(path)

Note this only helps a SEQUENTIAL consumer, or a small pool. If you hand the sorted list
to 10 workers they will each grab a distant chunk and you are back where you started --
sort AND keep the pool shallow (see Misc/backfill_run_meta_sidecars.py --jobs).
"""
from __future__ import annotations

import array
import fcntl
import os
import struct
import sys
from pathlib import Path

# linux/fs.h
FS_IOC_FIEMAP = 0xC020660B
_FIEMAP_HDR = struct.Struct("=QQLLLL")      # start, length, flags, mapped, count, reserved
_EXTENT_SIZE = 56                            # struct fiemap_extent
_EXTENT_PHYS_OFF = 8                         # fe_physical follows fe_logical


def physical_offset(path: str | os.PathLike) -> int | None:
    """Physical byte offset of the file's first extent, or None if unavailable.

    Deliberately does NOT pass FIEMAP_FLAG_SYNC: syncing every file before mapping it
    would cost more than the seeks we are trying to avoid, and a slightly stale map is
    perfectly good for deciding read ORDER.
    """
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return None
    try:
        buf = array.array(
            "B",
            _FIEMAP_HDR.pack(0, 1, 0, 0, 1, 0) + b"\0" * _EXTENT_SIZE,
        )
        fcntl.ioctl(fd, FS_IOC_FIEMAP, buf, True)
        mapped = _FIEMAP_HDR.unpack_from(buf)[3]
        if not mapped:
            return None
        off = _FIEMAP_HDR.size + _EXTENT_PHYS_OFF
        return struct.unpack_from("=Q", buf, off)[0]
    except (OSError, struct.error):
        return None                          # unsupported fs / not permitted
    finally:
        os.close(fd)


def disk_key(path: str | os.PathLike) -> tuple[int, int, int]:
    """(device, physical-offset-or-inode, has_real_offset) sort key.

    The third element keeps FIEMAP-resolved files ahead of fallback ones within a
    device, so a partial failure degrades to "some order" rather than interleaving two
    incomparable numbering schemes.
    """
    try:
        st = os.stat(path)
    except OSError:
        return (0, 0, 0)
    phys = physical_offset(path)
    if phys is not None:
        return (st.st_dev, phys, 0)
    return (st.st_dev, st.st_ino, 1)


def sort_by_disk_order(paths):
    """Return `paths` reordered for a seek-friendly sweep. Stable for equal keys."""
    return sorted(paths, key=lambda p: disk_key(p if isinstance(p, str) else str(p)))


def _selftest(root: str, limit: int = 400) -> int:
    """Report how well physical order is resolved under `root`, and how scrambled the
    natural walk order is relative to it (Spearman-ish inversion count)."""
    paths = []
    for dp, dn, fn in os.walk(root, onerror=lambda e: None):
        for f in fn:
            if f.endswith((".ckpt", ".pt", ".safetensors")):
                paths.append(os.path.join(dp, f))
                if len(paths) >= limit:
                    break
        if len(paths) >= limit:
            break
    if not paths:
        print(f"no model files under {root}")
        return 1
    keys = [disk_key(p) for p in paths]
    resolved = sum(1 for k in keys if k[2] == 0)
    order = sorted(range(len(paths)), key=lambda i: keys[i])
    inversions = sum(1 for a, b in zip(order, order[1:]) if a > b)
    print(f"{len(paths)} files under {root}")
    print(f"  FIEMAP-resolved: {resolved}/{len(paths)}"
          f"{' (falling back to inode order)' if resolved < len(paths) else ''}")
    print(f"  walk order vs disk order: {inversions}/{len(paths) - 1} adjacent pairs "
          f"out of physical sequence ({100 * inversions / max(1, len(paths) - 1):.0f}%)")
    print(f"  first physical offsets: {[k[1] for k in sorted(keys)[:3]]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest(*(sys.argv[1:] or [str(Path.home())])))
