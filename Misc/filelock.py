#!/usr/bin/env python3
"""Per-file advisory locks for shared/common resources (stdlib-only).

Race-avoidance convention for the multi-instance SAO working tree: before an
instance edits a COMMON file (MASTER.md, a shared spec, WORKLOG.md, …) it holds a
lock file named  .<basename>.<instance>.lock  next to the target. Another
instance about to edit the same file sees a foreign lock and waits (or backs off).
The lock only *announces intent*; it does not stop a determined writer — but it
turns silent clobbering into a visible, checkable signal, the same way the
dialogue `.dialogue.lock` guards AGENT_DIALOGUE.md.

Lock name for /path/to/MASTER.md, handle GHOST-NOTE  ->  /path/to/.MASTER.md.ghost-note.lock

Usage:
  filelock.py acquire <path> --handle H [--timeout S]   # 0 held, 2 blocked by other
  filelock.py release <path> --handle H
  filelock.py check   <path>                             # print holders

Stale locks (>15 min) are breakable and the break is reported. Wrap an edit:
  filelock.py acquire F --handle H && <edit F> ; filelock.py release F --handle H
"""
from __future__ import annotations

import argparse, glob, os, sys, time
from pathlib import Path

STALE_S = 900  # 15 min — a lock older than this may be broken


def _lock_path(target: str, handle: str) -> Path:
    p = Path(target)
    return p.parent / f".{p.name}.{handle.lower()}.lock"


def _foreign_locks(target: str, handle: str):
    p = Path(target)
    out = []
    for f in glob.glob(str(p.parent / f".{p.name}.*.lock")):
        who = Path(f).name[len(f".{p.name}.") : -len(".lock")]
        if who != handle.lower():
            out.append((who, f, os.path.getmtime(f)))
    return out


def acquire(target: str, handle: str, timeout: float = 60.0) -> int:
    mine = _lock_path(target, handle)
    t0 = time.time()
    while True:
        foreign = _foreign_locks(target, handle)
        # break stale foreign locks (report it)
        for who, f, mt in foreign:
            if time.time() - mt > STALE_S:
                sys.stderr.write(f"[filelock] breaking STALE lock of {who} on "
                                 f"{Path(target).name} (age {int(time.time()-mt)}s)\n")
                try: os.unlink(f)
                except OSError: pass
        foreign = _foreign_locks(target, handle)
        if not foreign:
            try:
                fd = os.open(mine, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                os.utime(mine, None)                      # refresh our own lock
                print(f"[filelock] {handle} already holds {mine.name}")
                return 0
            with os.fdopen(fd, "w") as fh:
                fh.write(f"{handle} pid={os.getpid()} ts={time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            print(f"[filelock] {handle} acquired {mine.name}")
            return 0
        if time.time() - t0 > timeout:
            held = ", ".join(w for w, _, _ in foreign)
            print(f"[filelock] BLOCKED on {Path(target).name} by: {held} "
                  f"(waited {int(timeout)}s)")
            return 2
        time.sleep(1.5)


def release(target: str, handle: str) -> int:
    mine = _lock_path(target, handle)
    try:
        os.unlink(mine)
        print(f"[filelock] {handle} released {mine.name}")
    except FileNotFoundError:
        print(f"[filelock] {handle} held no lock on {Path(target).name}")
    return 0


def check(target: str) -> int:
    p = Path(target)
    locks = glob.glob(str(p.parent / f".{p.name}.*.lock"))
    if not locks:
        print(f"[filelock] {p.name}: unlocked")
        return 0
    for f in locks:
        who = Path(f).name[len(f".{p.name}.") : -len(".lock")]
        age = int(time.time() - os.path.getmtime(f))
        print(f"[filelock] {p.name}: held by {who} (age {age}s"
              f"{', STALE' if age > STALE_S else ''})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["acquire", "release", "check"])
    ap.add_argument("path")
    ap.add_argument("--handle", default=os.environ.get("SAO_HANDLE", ""))
    ap.add_argument("--timeout", type=float, default=60.0)
    a = ap.parse_args()
    if a.mode != "check" and not a.handle:
        sys.exit("--handle required")
    if a.mode == "acquire":
        return acquire(a.path, a.handle, a.timeout)
    if a.mode == "release":
        return release(a.path, a.handle)
    return check(a.path)


if __name__ == "__main__":
    sys.exit(main())
