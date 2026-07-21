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

**--pid-aware (for long-lived resource mutexes, e.g. a GPU `.gpu.lock`).** The default
15-min mtime stale-break is tuned for quick file edits; it is WRONG for a lock held for
hours (a multi-hour train/render would have its lock stolen at 15 min → two jobs on the
GPU at once, which hard-crashed the box twice on 2026-07-21). With `--pid-aware`, a foreign
lock is broken **iff its recorded PID is not alive** — so a crashed/rebooted holder is
reclaimed instantly (dead PID), while a live long-running job is NEVER stolen no matter its
age. Every lock already records `pid=`; this just consults it. (Edge: a PID reused by an
unrelated process after a crash could read as held — rare, visible in `check`, manually
breakable.) Usage for a GPU mutex:
  filelock.py acquire /path/.gpu.lock --handle H --pid-aware && <gpu work> ; filelock.py release /path/.gpu.lock --handle H
"""
from __future__ import annotations

import argparse, glob, os, re, sys, time
from pathlib import Path

STALE_S = 900  # 15 min — a lock older than this may be broken (mtime mode only)


def _pid_alive(pid) -> bool:
    """True iff a process with this PID currently exists. Unparseable/None → dead."""
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True                 # exists, just not ours to signal
    except (OSError, ValueError):
        return False
    return True


def _read_pid(lockfile: str):
    try:
        m = re.search(r"pid=(\d+)", Path(lockfile).read_text())
        return int(m.group(1)) if m else None
    except OSError:
        return None


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


def acquire(target: str, handle: str, timeout: float = 60.0, pid_aware: bool = False) -> int:
    mine = _lock_path(target, handle)
    t0 = time.time()
    while True:
        foreign = _foreign_locks(target, handle)
        # break dead/stale foreign locks (report it). pid-aware: break iff the holder's
        # PID is gone (so a live long job is never stolen); else: break on mtime>STALE_S.
        for who, f, mt in foreign:
            if pid_aware:
                if not _pid_alive(_read_pid(f)):
                    sys.stderr.write(f"[filelock] breaking ORPHANED lock of {who} on "
                                     f"{Path(target).name} (pid gone; age {int(time.time()-mt)}s)\n")
                    try: os.unlink(f)
                    except OSError: pass
            elif time.time() - mt > STALE_S:
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
        pid = _read_pid(f)
        pidnote = ""
        if pid is not None:
            pidnote = f", pid={pid} {'ALIVE' if _pid_alive(pid) else 'DEAD→reclaimable'}"
        print(f"[filelock] {p.name}: held by {who} (age {age}s"
              f"{', STALE' if age > STALE_S else ''}{pidnote})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["acquire", "release", "check"])
    ap.add_argument("path")
    ap.add_argument("--handle", default=os.environ.get("SAO_HANDLE", ""))
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--pid-aware", action="store_true",
                    help="break a foreign lock iff its PID is dead (for long-held mutexes "
                         "like a GPU .gpu.lock), instead of the 15-min mtime stale-break")
    a = ap.parse_args()
    if a.mode != "check" and not a.handle:
        sys.exit("--handle required")
    if a.mode == "acquire":
        return acquire(a.path, a.handle, a.timeout, pid_aware=a.pid_aware)
    if a.mode == "release":
        return release(a.path, a.handle)
    return check(a.path)


if __name__ == "__main__":
    sys.exit(main())
