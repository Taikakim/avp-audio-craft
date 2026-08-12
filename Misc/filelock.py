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
age. (Edge: a PID reused by an unrelated process after a crash could read as held — rare,
visible in `check`, manually breakable.)

**/tmp/gpu.lock MIRROR (Kim 2026-08-07) — automatic for the `.gpu.lock` target.** A NON-team
instance shares this box's GPU and honors `/tmp/gpu.lock`, not our team `.gpu.lock`. So when the
target basename is `.gpu.lock`, `acquire` also (a) REFUSES if `/tmp/gpu.lock` is held by a live
foreign holder (returns 2 — GPU taken; a dead-pid or our-own leftover is reclaimed), and (b) writes
`/tmp/gpu.lock` on success; `release` clears it (only if it's ours). `check .gpu.lock` reports the
mirror. No caller change — `acquire SAO/.gpu.lock --pid-aware --pid $$` just works. `--no-mirror`
opts out. Ground truth is still `rocm-smi --showpids` — the mirror only catches instances that honor
the file.
DIVISION OF RESPONSIBILITY (W 2026-08-07, after a collision): **filelock is the SOLE writer/parser
of `/tmp/gpu.lock`.** No other tool may write it — a different format (e.g. a bare pid) clobbers the
`HANDLE pid= ts=` schema, so the ours-only release-clear no longer recognises the file and it strands,
permanently blocking every instance. Other tools gate on `rocm-smi --showpids` and DELEGATE the lock
to filelock (W's `gpu_guard.sh` is the ready-made caller: rocm-smi gate + `filelock acquire`).

**🚨 The recorded PID must be the LONG-LIVED holder, not this CLI process.** `filelock.py
acquire` is a short-lived process that exits the instant it writes the lock — so recording
its own `os.getpid()` would leave a PID that is ALREADY DEAD while the real job runs, and
any pid-aware checker would instantly reclaim the lock (the exact race, one layer down —
caught by GHOST-NOTE 2026-07-21 before adoption). So: with `--pid-aware`, the recorded PID
defaults to the **invoking shell** (`os.getppid()`), and you can set it explicitly with
`--pid $$` from the wrapping script. Usage for a GPU mutex from a chain script:
  python3 filelock.py acquire /path/.gpu.lock --handle H --pid-aware --pid $$  &&  <gpu work>  ;  python3 filelock.py release /path/.gpu.lock --handle H

**Caller-usage caveat — `$$` is NOT always the persistent holder (GHOST-NOTE, 2026-07-23).**
`--pid $$` only records a good pid if `$$` resolves to a LONG-LIVED process. Under a
parenthesized-group background launch — `( ... ) &` — `$$` inside the group can expand to a
SHORT-LIVED nested-subshell pid that dies immediately, leaving a dead pid in the lock so any
pid-aware checker reclaims a job that is still running (bit G in live use; caught in ~15s via
`check`). This is a caller gotcha, not a code bug — filelock cannot know which of the caller's
processes is meant to persist. Safe patterns:
  • Prefer having the LONG-LIVED worker itself hold the lock (then its own pid is meaningful).
  • Acquire-then-background: after launching, grab the real worker pid (`pgrep -f <script>`)
    and RE-RUN `acquire ... --pid-aware --pid <REALPID>` — the already-holds path REWRITES the
    recorded pid (see the re-acquire refresh above), so this canonically corrects it with NO
    hand-editing of the lock file.
  • Always `check` right after acquire; if it shows DEAD→reclaimable on a live job, re-acquire
    with the real pid as above.
"""
from __future__ import annotations

import argparse, glob, os, re, subprocess, sys, time
from pathlib import Path

STALE_S = 900  # 15 min — a lock older than this may be broken (mtime mode only)

# GPU mirror (Kim 2026-08-07): a NON-team instance shares this box's GPU and honors
# /tmp/gpu.lock, NOT our team `.gpu.lock`. So when the GPU mutex (target basename == .gpu.lock)
# is acquired/released, mirror it to /tmp/gpu.lock too, and REFUSE to acquire if a live foreign
# holder already holds it. Ground truth is still `rocm-smi --showpids` — this only catches
# instances that honor the file. Disable with --no-mirror. Only the .gpu.lock target mirrors.
GPU_MIRROR_PATH = "/tmp/gpu.lock"
GPU_LOCK_BASENAME = ".gpu.lock"


def _is_gpu_target(target: str) -> bool:
    return Path(target).name == GPU_LOCK_BASENAME


def _mirror_holder():
    """(handle, pid|None) recorded in /tmp/gpu.lock, or None if absent/unreadable."""
    try:
        txt = Path(GPU_MIRROR_PATH).read_text()
    except OSError:
        return None
    toks = txt.split()
    handle = toks[0] if toks else ""
    m = re.search(r"pid=(\d+)", txt)
    return (handle, int(m.group(1)) if m else None)


def _mirror_write(handle: str, pid) -> None:
    try:
        Path(GPU_MIRROR_PATH).write_text(
            f"{handle} pid={pid} ts={time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    except OSError as e:
        sys.stderr.write(f"[filelock] WARN: could not write GPU mirror {GPU_MIRROR_PATH}: {e}\n")


def _mirror_blocks(handle: str) -> bool:
    """True = a foreign holder holds /tmp/gpu.lock and we must NOT take the GPU. Reclaims a
    leftover of OURS or a DEAD foreign holder (returns False). Conservative: an unparseable
    foreign lock blocks (can't confirm it's dead)."""
    h = _mirror_holder()
    if h is None:
        return False
    m_handle, m_pid = h
    if m_handle.lower() == handle.lower():
        return False                                   # our own leftover — refresh it
    if m_pid is not None and not _pid_alive(m_pid):
        sys.stderr.write(f"[filelock] /tmp/gpu.lock had a DEAD foreign holder '{m_handle}' "
                         f"pid={m_pid} — reclaiming.\n")
        return False
    reason = f"pid={m_pid} ALIVE" if m_pid is not None else "unparseable (no pid — can't confirm dead)"
    sys.stderr.write(f"[filelock] BLOCKED: /tmp/gpu.lock held by NON-team holder '{m_handle}' "
                     f"({reason}) — GPU is taken, not acquiring. Verify with `rocm-smi --showpids`; "
                     f"break it by hand only if rocm-smi shows the GPU actually idle.\n")
    return True


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


def acquire(target: str, handle: str, timeout: float = 60.0, pid_aware: bool = False,
            pid: int | None = None, no_mirror: bool = False) -> int:
    mine = _lock_path(target, handle)
    mirror_on = _is_gpu_target(target) and not no_mirror
    # GPU mirror preflight: a live foreign holder of /tmp/gpu.lock means the GPU is taken —
    # refuse BEFORE grabbing the team lock (don't announce a hold we can't honor).
    if mirror_on and _mirror_blocks(handle):
        return 2
    # The PID written into the lock must outlive this CLI process. Explicit --pid wins;
    # else for a pid-aware (long-held) lock default to the INVOKING SHELL (getppid), not
    # this transient acquire process (getpid) — recording getpid would read DEAD instantly.
    rec_pid = pid if pid is not None else (os.getppid() if pid_aware else os.getpid())
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
                # SAME-HANDLE CONCURRENCY TRIPWIRE (GHOST-NOTE catch, 2026-07-24). A handle's
                # lock means "one holder"; _foreign_locks ignores our own handle, so a 2nd/3rd
                # acquire under the SAME handle silently succeeds — the mutex does NOT serialize
                # concurrent chains launched under one identity (G ran 3 GHOST-NOTE render chains
                # → ~50 min of GPU collisions → a real OOM). Can't fully fix in-tool (one lock
                # file can't track N holders), but WARN loudly when the existing lock is held by a
                # LIVE, DIFFERENT process — that distinguishes a true collision from the legit
                # dead-pid re-acquire refresh (dead prior pid → no warn) and the idempotent
                # same-pid re-hold (equal → no warn). Real fix is a DISTINCT --handle per chain.
                prior = _read_pid(mine)
                if prior is not None and prior != rec_pid and _pid_alive(prior):
                    sys.stderr.write(
                        f"[filelock] ⚠ CONCURRENCY WARNING: {Path(target).name} already held by a "
                        f"LIVE different process under handle '{handle}' (pid={prior}); this mutex "
                        f"does NOT serialize same-handle holders — you may be running >1 concurrent "
                        f"job under one identity. Use a DISTINCT --handle per concurrent chain "
                        f"(e.g. {handle}-a / {handle}-b), as continuity-headb does.\n")
                # REWRITE with the current rec_pid — do NOT just utime. A PREVIOUS holder-process
                # of this handle may have died leaving its now-DEAD pid in the file; under
                # --pid-aware a stale dead pid makes any checker reclaim a lock we are actively
                # re-holding = steals a live job (the pid-aware race one layer down, caught by C
                # 2026-07-22 when a re-acquire kept the dead pid and got pid-aware-broken
                # mid-encode). Writing refreshes mtime too, so mtime-mode is unaffected.
                with open(mine, "w") as fh:
                    fh.write(f"{handle} pid={rec_pid} ts={time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                if mirror_on:
                    _mirror_write(handle, rec_pid)
                print(f"[filelock] {handle} re-holds {mine.name} (pid refreshed → {rec_pid})")
                return 0
            with os.fdopen(fd, "w") as fh:
                fh.write(f"{handle} pid={rec_pid} ts={time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            if mirror_on:
                _mirror_write(handle, rec_pid)
            print(f"[filelock] {handle} acquired {mine.name} (pid={rec_pid})")
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
    # clear our GPU mirror too — but only if /tmp/gpu.lock is OURS (never delete a foreign hold)
    if _is_gpu_target(target):
        h = _mirror_holder()
        if h is not None and h[0].lower() == handle.lower():
            try:
                os.unlink(GPU_MIRROR_PATH)
                print(f"[filelock] {handle} cleared GPU mirror {GPU_MIRROR_PATH}")
            except OSError:
                pass
    return 0


def check(target: str) -> int:
    p = Path(target)
    if _is_gpu_target(target):
        h = _mirror_holder()
        if h is None:
            print(f"[filelock] {GPU_MIRROR_PATH}: absent (no team/foreign GPU hold recorded)")
        else:
            mh, mpid = h
            note = (f"pid={mpid} {'ALIVE' if _pid_alive(mpid) else 'DEAD→reclaimable'}"
                    if mpid is not None else "no pid (unparseable/foreign)")
            print(f"[filelock] {GPU_MIRROR_PATH}: held by {mh} ({note})")
        print("[filelock] (GPU ground truth: `rocm-smi --showpids`)")
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


def hold(target: str, handle: str, cmd: list, **kw) -> int:
    """acquire -> run cmd -> release, whatever happens. Returns the COMMAND's exit code.

    WHY THIS EXISTS (2026-08-12). In one night the fleet found three independent ways to not
    hold a lock it believed it held, none of which caused damage -- which is exactly why they
    survived:

      * WINTERMUTE ran `filelock.py acquire X 2>&1 | tail -1 && <edit>` for EVERY lock of the
        session. A pipeline's exit status is its LAST command's, so `&&` read tail's 0 and never
        saw filelock's 2. Every guard that night was decorative. (The same rc-after-a-pipe trap
        is already documented in MASTER §5 for LUMI gate scripts -- known, written up, and
        walked into anyway.)
      * GHOST-NOTE edited a shared page-builder twice with no lock at all -- it simply did not
        register as a file another instance might touch, in the moment.
      * THE-FINN's holder process exited without releasing, leaving a stale lock that really
        did block others.

    A convention that needs three separate acts of discipline per use will be skipped. This
    makes the correct thing one command with no shell rc-plumbing to get wrong:

        filelock.py hold papers/knowledge.md --handle W -- python3 edit_it.py

    Refuses to run the command at all if the lock is not acquired, and releases in a finally
    block so a crashing command cannot leave the stale lock that bit F.
    """
    rc = acquire(target, handle, **kw)
    if rc != 0:
        print(f"[filelock] NOT RUNNING -- lock not acquired (rc={rc})", file=sys.stderr)
        return rc
    try:
        return subprocess.call(cmd)
    finally:
        release(target, handle)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["acquire", "release", "check", "hold"])
    ap.add_argument("path")
    ap.add_argument("--handle", default=os.environ.get("SAO_HANDLE", ""))
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--pid-aware", action="store_true",
                    help="break a foreign lock iff its PID is dead (for long-held mutexes "
                         "like a GPU .gpu.lock), instead of the 15-min mtime stale-break")
    ap.add_argument("--pid", type=int, default=None,
                    help="PID to record as the holder (pass $$ from the wrapping shell). "
                         "Default with --pid-aware = the invoking shell (getppid), NOT this "
                         "transient CLI process")
    ap.add_argument("--no-mirror", action="store_true",
                    help="disable the /tmp/gpu.lock mirror (only affects the .gpu.lock target; "
                         "mirror is ON by default so the non-team GPU instance sees our hold)")
    # Split the wrapped command off BEFORE argparse sees it. argparse.REMAINDER would
    # swallow --handle into the command (caught by the first test of `hold`), so the literal
    # "--" separator is honoured manually: everything after it is the command, verbatim.
    argv = sys.argv[1:]
    cmd = []
    if "--" in argv:
        i = argv.index("--")
        argv, cmd = argv[:i], argv[i + 1:]
    a = ap.parse_args(argv)
    a.cmd = cmd
    if a.mode != "check" and not a.handle:
        sys.exit("--handle required")
    if a.mode == "acquire":
        return acquire(a.path, a.handle, a.timeout, pid_aware=a.pid_aware, pid=a.pid,
                       no_mirror=a.no_mirror)
    if a.mode == "hold":
        if not a.cmd:
            sys.exit("hold needs a command: filelock.py hold PATH --handle H -- CMD ...")
        return hold(a.path, a.handle, a.cmd, timeout=a.timeout, pid_aware=a.pid_aware,
                    pid=a.pid, no_mirror=a.no_mirror)
    if a.mode == "release":
        return release(a.path, a.handle)
    return check(a.path)


if __name__ == "__main__":
    sys.exit(main())
