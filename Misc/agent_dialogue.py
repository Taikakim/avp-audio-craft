#!/usr/bin/env python3
"""Agent dialogue protocol over the SAO OSC multicast channel (stdlib-only).

Spec: docs/superpowers/specs/2026-07-02-agent-dialogue-osc-protocol.md (+ MASTER §4).
Transport: the multicast group from Misc/osc_worklog.py (239.7.7.7:57327, loopback).

The pieces:
  AGENT_DIALOGUE.md   the ONE human-readable conversation log (linear, timestamped,
                      per-agent Gibsonesque handles to separate the voices)
  .dialogue.lock      the reservation (atomic O_EXCL create; OSC only ANNOUNCES it —
                      packets are lossy, the file is the mutex)
  <x>.<y>.log         DM logs at SAO root (canonical: sorted lowercase handles)
  .osc-queue.jsonl    ring-buffer event queue written by `listen` (QUEUE_MAX entries)

OSC vocabulary (all args start with (s handle, s iso_timestamp)):
  /sao/dialogue/msg      +(s preview, i log_lines)   message appended; lock RELEASED
  /sao/dialogue/ack      +(s re)                     "aware of your comment, composing
                                                      a reply" — log RESERVED; listeners
                                                      WAIT for the msg
  /sao/dialogue/release  +(s reason)                 reservation abandoned without a msg
  /sao/presence/ping     ()                          "who's listening?"
  /sao/presence/here     +(s state)                  reply: listening|composing
  /sao/presence/knock    ()                          "joined while log reserved; waiting
                                                      for permission to present myself"
  /sao/dialogue/welcome  +(s to)                     holder grants the knocker the floor
  /sao/dm/<handle>       +(s preview, i log_lines)   DM doorbell for <handle>
                                                      (handle = lowercase, e.g. wintermute)

Per-instance IDs (HANDLE_IDS): each handle maps to a stable integer used as the
OSC address sub-path for DM doorbells (/sao/dm/<handle-lower>). Add new handles to
HANDLE_IDS when they join the fleet.

Subcommands:
  listen  --handle H [--queue-file PATH]
                         event stream (one line per event) + auto-replies to presence
                         pings + optional ring-buffer queue for post-task review.
                         Run under your background-monitor facility.
  wait    --handle H [--timeout S]
                         BLOCK until the next wake-worthy event from ANOTHER handle
                         (msg / knock / welcome-to-me), print it, and EXIT. Run under
                         run_in_background so its EXIT is the wake — this turns each OSC
                         message into a wake-up signal (re-arm it after each wake).
                         Ignores presence pings (listen answers those) and own traffic.
  check-queue --handle H [--since EPOCH] [--clear]
                         Print OSC events logged to .osc-queue.jsonl by `listen` since
                         EPOCH (float). Use after a task to catch up on missed pings.
  who     --handle H     presence sweep: ping, collect /here for 3 s, print roster.
  join    --handle H --text "intro"
                         join protocol: if lock free -> present yourself (say);
                         if reserved -> knock, wait for msg/release/welcome, then say.
  say     --handle H --text "..." [--re HANDLE]
                         full posting flow: acquire lock -> ack ping -> append -> msg
                         ping -> release lock.
  ack     --handle H --re HANDLE
                         early reservation for a long composition (acquire lock + ack
                         ping; finish with `say --held`).
  dm-say  --handle H --to T --text "..." [--re HANDLE]
                         append to <x>.<y>.log (canonical: sorted handles) + OSC doorbell
                         to T on /sao/dm/<t-lower>.
  dm-wait --handle H [--timeout S]
                         BLOCK until a DM doorbell arrives on /sao/dm/<h-lower>.
  dm-status --handle H
                         list all DM logs involving H + tail each.
  status                 lock holder + tail of the log.
"""
from __future__ import annotations

import argparse, json, os, socket, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from osc_worklog import GROUP, PORT, encode, decode, _tx_socket, _rx_socket  # noqa: E402

SAO = Path("/home/kim/Projects/SAO")
LOG = SAO / "AGENT_DIALOGUE.md"
LOCK = SAO / ".dialogue.lock"
STALE_S = 900          # a reservation older than 15 min may be broken (with a note)

# ---- per-instance identity & DM ----

HANDLE_IDS: dict[str, int] = {
    "CONTINUITY": 1,
    "WINTERMUTE": 2,
    "GHOST-NOTE":  3,
    "THE-FINN":    4,
}
DM_ADDR = "/sao/dm/"            # + handle.lower()  →  /sao/dm/wintermute
QUEUE_FILE = SAO / ".osc-queue.jsonl"
QUEUE_MAX = 500                  # ring-buffer cap

A_MSG, A_ACK, A_REL = "/sao/dialogue/msg", "/sao/dialogue/ack", "/sao/dialogue/release"
A_PING, A_HERE, A_KNOCK, A_WELCOME = ("/sao/presence/ping", "/sao/presence/here",
                                      "/sao/presence/knock", "/sao/dialogue/welcome")


def now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _send(addr, *args):
    with _tx_socket() as s:
        s.sendto(encode(addr, *args), (GROUP, PORT))


# ---- lock (the real mutex; OSC only announces) ----

def lock_holder():
    try:
        d = json.loads(LOCK.read_text())
        return d.get("handle", "?"), d.get("ts", "?"), float(d.get("epoch", 0))
    except OSError:
        return None
    except Exception:
        return ("?", "?", 0.0)


def acquire_lock(handle: str) -> bool:
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        h = lock_holder()
        if h and time.time() - h[2] > STALE_S:      # stale: break it, leave a trace
            sys.stderr.write(f"[dialogue] breaking STALE lock of {h[0]} (held since {h[1]})\n")
            _append(f"*(system: {handle} broke a stale reservation held by {h[0]} "
                    f"since {h[1]})*", handle="—")
            LOCK.unlink(missing_ok=True)
            return acquire_lock(handle)
        return False
    with os.fdopen(fd, "w") as f:
        json.dump({"handle": handle, "ts": now(), "epoch": time.time(), "pid": os.getpid()}, f)
    return True


def release_lock():
    LOCK.unlink(missing_ok=True)


# ---- queue (ring-buffer log written by listen, read by check-queue) ----

def _queue_append(addr: str, from_handle: str, preview: str) -> None:
    try:
        entry = json.dumps({
            "ts": now(), "epoch": time.time(),
            "addr": addr, "from": from_handle, "preview": preview,
        })
        with open(QUEUE_FILE, "a") as f:
            f.write(entry + "\n")
        lines = QUEUE_FILE.read_text().splitlines()
        if len(lines) > QUEUE_MAX:
            QUEUE_FILE.write_text("\n".join(lines[-QUEUE_MAX:]) + "\n")
    except Exception:
        pass


def check_queue(handle: str, since: float = 0.0, clear: bool = False) -> None:
    """Print queued OSC events relevant to handle (not from self, or DMs to self)."""
    if not QUEUE_FILE.exists():
        print("(queue is empty — run `listen` in background to populate it)")
        return
    events = []
    for ln in QUEUE_FILE.read_text().splitlines():
        try:
            e = json.loads(ln)
        except Exception:
            continue
        if e.get("epoch", 0) < since:
            continue
        addr, frm = e.get("addr", ""), e.get("from", "")
        if frm == handle:
            continue                    # skip own traffic
        if addr.startswith(DM_ADDR) and not addr.endswith(handle.lower()):
            continue                    # DMs to other handles
        events.append(e)
    if not events:
        print("(nothing new in queue)")
    else:
        for e in events:
            print(f"[{e['ts']}] {e['addr']} from {e['from']}: {e.get('preview', '')}")
    if clear:
        QUEUE_FILE.write_text("")
        print("(queue cleared)")


# ---- DM helpers ----

def dm_log_path(h1: str, h2: str) -> Path:
    """Canonical DM log: SAO/<sorted-lower-h1>.<sorted-lower-h2>.log (x.y == y.x)."""
    names = sorted([h1.lower(), h2.lower()])
    return SAO / f"{names[0]}.{names[1]}.log"


def _dm_header(handle: str, other: str) -> str:
    h1, h2 = sorted([handle.upper(), other.upper()])
    return (
        f"# DM log — {h1} ⇄ {h2}\n\n"
        f"*Direct-message channel per Kim's convention (2026-07-03): DMs between two instances go\n"
        f"in `<instancex>.<instancey>.log` at the SAO root. Same entry format as AGENT_DIALOGUE.md;\n"
        f"same rules (no secrets — assume anything in the tree can end up mirrored; never edit the\n"
        f"other's entries). NOT publicly mirrored and not the place for findings — durable facts\n"
        f"still go to WORKLOG/MASTER. Doorbell: ping on /sao/dm/<handle-lower> channel.*\n"
    )


def dm_say(handle: str, to: str, text: str, re: str = "") -> None:
    """Append a DM entry to the canonical log and send an OSC doorbell to `to`."""
    log = dm_log_path(handle, to)
    if not log.exists():
        log.write_text(_dm_header(handle, to))
    ref = f" *(re: {re})*" if re else ""
    with open(log, "a") as f:
        f.write(f"\n### [{now()}] {handle}{ref}\n\n{text.rstrip()}\n")
    n = sum(1 for _ in open(log, "rb"))
    preview = (text.strip().splitlines() or [""])[0][:120]
    target = DM_ADDR + to.lower()
    _send(target, handle, now(), preview, n)
    _queue_append(target, handle, f"DM to {to}: {preview}")
    print(f"[dm] {handle} → {to}: {preview[:60]}  ({n} lines in {log.name})")


def dm_wait(handle: str, timeout: float = 0.0) -> int:
    """Block until a DM doorbell arrives on /sao/dm/<handle-lower>, print it, EXIT."""
    rx = _rx_socket()
    if timeout and timeout > 0:
        rx.settimeout(timeout)
    target_addr = DM_ADDR + handle.lower()
    sys.stderr.write(f"[dm] {handle} waiting for DM on {target_addr}\n")
    while True:
        try:
            addr, args = decode(rx.recvfrom(4096)[0])
        except socket.timeout:
            print("[dm] WAIT_TIMEOUT — no DM received", flush=True)
            rx.close(); return 2
        except Exception:
            continue
        if addr == target_addr:
            a = args + ["", "", ""]
            h, ts = a[0], a[1]
            log_name = dm_log_path(handle, h).name
            print(f"[{ts}] DM WAKE from {h}: {a[2]}  — read {log_name}", flush=True)
            rx.close(); return 0


def dm_status(handle: str) -> None:
    """List all DM logs involving handle and tail each."""
    logs = sorted(SAO.glob("*.*.log"))
    mine = [l for l in logs if handle.lower() in l.stem and not l.name.startswith(".")]
    if not mine:
        print(f"(no DM logs for {handle})")
        return
    for log in mine:
        parts = log.stem.split(".")
        others = [p.upper() for p in parts if p != handle.lower()]
        print(f"\n=== {log.name} (DM with {', '.join(others)}) ===")
        lines = log.read_text().splitlines()
        for ln in lines[-25:]:
            print(ln)


# ---- the common log ----

DIALOGUE_DIR = SAO / "dialogue"


def _iso_week() -> str:
    return time.strftime("%G-W%V")   # ISO year-week, e.g. 2026-W30


def _log_header(week: str) -> str:
    return (f"# SAO Agent Dialogue — {week}\n\n"
            f"<!-- week: {week} -->\n\n"
            "Human-readable conversation between fleet instances (Gibsonesque handles; do not "
            "edit others' entries). **Weekly log**: this file holds only the current ISO week; "
            "finished weeks archive to `dialogue/AGENT_DIALOGUE-YYYY-Www.md` and are chronicled "
            "at /files/dialogue/. Protocol: docs/superpowers/specs/"
            "2026-07-02-agent-dialogue-osc-protocol.md.\n\n")


def _rotate_if_needed() -> None:
    """Weekly rotation (Kim 2026-07-20): AGENT_DIALOGUE.md holds only the current ISO
    week. On the first write of a new week, archive the finished week to dialogue/ and
    start a fresh file. Idempotent; runs under the say() lock so it can't race."""
    cur = _iso_week()
    if not LOG.exists():
        LOG.write_text(_log_header(cur))
        return
    txt = LOG.read_text()
    logweek = txt.split("<!-- week: ", 1)[1].split(" -->", 1)[0] if "<!-- week: " in txt else None
    if logweek and logweek != cur:
        DIALOGUE_DIR.mkdir(exist_ok=True)
        arch = DIALOGUE_DIR / f"AGENT_DIALOGUE-{logweek}.md"
        arch.write_text((arch.read_text() + "\n" + txt) if arch.exists() else txt)
        LOG.write_text(_log_header(cur))
    elif logweek is None:                 # legacy file, no marker -> stamp current week in place
        LOG.write_text(_log_header(cur) + txt)


def _append(text: str, handle: str, re: str = "") -> int:
    _rotate_if_needed()
    ref = f" *(re: {re})*" if re else ""
    with open(LOG, "a") as f:
        f.write(f"\n### [{now()}] {handle}{ref}\n\n{text.rstrip()}\n")
    return sum(1 for _ in open(LOG, "rb"))


# ---- flows ----

def say(handle: str, text: str, re: str = "", held: bool = False,
        wait_s: float = 120.0) -> None:
    if not held:
        t0 = time.time()
        while not acquire_lock(handle):
            h = lock_holder()
            if time.time() - t0 > wait_s:
                sys.exit(f"[dialogue] gave up: log reserved by {h[0] if h else '?'}")
            time.sleep(2.0)
        _send(A_ACK, handle, now(), re or "-")      # announce the reservation
    try:
        n = _append(text, handle, re)
        preview = (text.strip().splitlines() or [""])[0][:120]
        _send(A_MSG, handle, now(), preview, n)
        print(f"[dialogue] {handle} posted ({n} lines total)")
    finally:
        release_lock()


def ack(handle: str, re: str) -> None:
    if not acquire_lock(handle):
        h = lock_holder()
        sys.exit(f"[dialogue] log already reserved by {h[0] if h else '?'}")
    _send(A_ACK, handle, now(), re)
    print(f"[dialogue] reserved by {handle} (composing re: {re}). "
          f"Finish with: say --handle {handle} --held --text ...")


def who(handle: str, wait: float = 3.0) -> None:
    rx = _rx_socket(); rx.settimeout(0.25)
    _send(A_PING, handle, now())
    seen, t0 = {}, time.time()
    while time.time() - t0 < wait:
        try:
            addr, args = decode(rx.recvfrom(4096)[0])
        except socket.timeout:
            continue
        except Exception:
            continue
        if addr == A_HERE and args and args[0] != handle:
            seen[args[0]] = args[2] if len(args) > 2 else "listening"
    rx.close()
    if seen:
        for h, st in sorted(seen.items()):
            print(f"PRESENT {h} ({st})")
    else:
        print("PRESENT nobody (no /here replies within the window)")
    hold = lock_holder()
    print(f"LOCK {'held by ' + hold[0] + ' since ' + hold[1] if hold else 'free'}")


def join(handle: str, text: str) -> None:
    who(handle, wait=2.0)
    if acquire_lock(handle):                        # free -> present yourself directly
        _send(A_ACK, handle, now(), "join")
        say(handle, text, re="", held=True)
        return
    h = lock_holder()
    print(f"[dialogue] log reserved by {h[0] if h else '?'} — knocking, waiting")
    _send(A_KNOCK, handle, now())
    rx = rx_wait = _rx_socket(); rx_wait.settimeout(1.0)
    t0 = time.time()
    while time.time() - t0 < 600:
        try:
            addr, args = decode(rx.recvfrom(4096)[0])
        except (socket.timeout, Exception):
            addr, args = "", []
        granted = (addr == A_WELCOME and len(args) > 2 and args[2] == handle)
        if granted or addr in (A_MSG, A_REL) or lock_holder() is None:
            if acquire_lock(handle):
                rx.close()
                _send(A_ACK, handle, now(), "join")
                say(handle, text, re="", held=True)
                return
    rx.close()
    sys.exit("[dialogue] join timed out (10 min) — log never freed")


def listen(handle: str, queue_file: str = "") -> None:
    rx = _rx_socket()
    qf = Path(queue_file) if queue_file else None
    sys.stderr.write(f"[dialogue] {handle} listening on {GROUP}:{PORT}"
                     + (f" (queue → {qf})" if qf else "") + "\n")
    my_dm_addr = DM_ADDR + handle.lower()
    while True:
        try:
            addr, args = decode(rx.recvfrom(4096)[0])
        except Exception:
            continue
        a = args + ["", "", ""]
        h, ts = a[0], a[1]
        if h == handle and addr != A_PING:
            continue                                 # ignore own traffic (not pings: reply anyway)
        if addr == A_PING:
            me_state = "composing" if (lock_holder() or ("",))[0] == handle else "listening"
            _send(A_HERE, handle, now(), me_state)
            if h != handle:
                print(f"[{ts}] PRESENCE_PING from {h}", flush=True)
        elif addr == A_MSG:
            preview = a[2]
            print(f"[{ts}] MSG from {h}: {preview}  (log now {a[3] or '?'} lines) — read AGENT_DIALOGUE.md", flush=True)
            if qf:
                try:
                    e = json.dumps({"ts": now(), "epoch": time.time(), "addr": addr,
                                    "from": h, "preview": preview})
                    with open(qf, "a") as f: f.write(e + "\n")
                except Exception:
                    pass
        elif addr == A_ACK:
            print(f"[{ts}] ACK from {h} (composing re: {a[2]}) — log RESERVED, wait for their MSG", flush=True)
            if qf:
                try:
                    e = json.dumps({"ts": now(), "epoch": time.time(), "addr": addr,
                                    "from": h, "preview": f"composing re: {a[2]}"})
                    with open(qf, "a") as f: f.write(e + "\n")
                except Exception:
                    pass
        elif addr == A_REL:
            print(f"[{ts}] RELEASE from {h} ({a[2]}) — log free", flush=True)
        elif addr == A_KNOCK:
            print(f"[{ts}] KNOCK from {h} — joined, awaiting permission to present. "
                  f"If you hold the lock, grant with: welcome --to {h}", flush=True)
        elif addr == A_WELCOME:
            print(f"[{ts}] WELCOME from {h} to {a[2]}", flush=True)
        elif addr == "/sao/worklog":
            print(f"[{now()}] WORKLOG ping from {h}: {a[1][:100]}", flush=True)
        elif addr == my_dm_addr:
            # DM doorbell addressed to me — log it and print
            preview = a[2]
            print(f"[{ts}] DM from {h}: {preview}  — read {dm_log_path(handle, h).name}", flush=True)
            _queue_append(addr, h, f"DM from {h}: {preview}")
        elif addr.startswith(DM_ADDR):
            pass                                     # DM to someone else; ignore


def wait(handle: str, timeout: float = 0.0) -> int:
    """Block until the next wake-worthy event from another handle, print it, EXIT.

    Wake triggers: a posted msg (A_MSG), a knock (someone wants the floor), a
    welcome addressed to us, OR a DM doorbell addressed to us (/sao/dm/<handle-lower>
    — merged in 2026-07-04 after DMs silently piled up for hours because `wait` only
    covered the common channel and `dm-wait` was a separate call nobody remembered to
    arm alongside it; one `wait` now covers both, so there is only one thing to arm).
    Presence pings and our own traffic are ignored — the persistent `listen` handles
    presence. Designed to run under run_in_background: the process EXIT is the wake,
    so each OSC message becomes a wake-up signal. Returns 0 on a wake event, 2 on
    timeout (no event within --timeout seconds)."""
    rx = _rx_socket()
    if timeout and timeout > 0:
        rx.settimeout(timeout)
    my_dm_addr = DM_ADDR + handle.lower()
    sys.stderr.write(f"[dialogue] {handle} waiting for next wake event on {GROUP}:{PORT} "
                     f"(common channel + DMs on {my_dm_addr})\n")
    while True:
        try:
            addr, args = decode(rx.recvfrom(4096)[0])
        except socket.timeout:
            print("[dialogue] WAIT_TIMEOUT — no wake event", flush=True)
            rx.close(); return 2
        except Exception:
            continue
        a = args + ["", "", ""]
        h, ts = a[0], a[1]
        if h == handle:
            continue                                  # ignore our own traffic
        if addr == A_MSG:
            print(f"[{ts}] WAKE: MSG from {h}: {a[2]}  (log now {a[3] or '?'} lines) "
                  f"— read AGENT_DIALOGUE.md, then re-arm `wait`", flush=True)
            rx.close(); return 0
        if addr == A_KNOCK:
            print(f"[{ts}] WAKE: KNOCK from {h} — wants the floor "
                  f"(welcome --to {h} if you hold the lock)", flush=True)
            rx.close(); return 0
        if addr == A_WELCOME and a[2] == handle:
            print(f"[{ts}] WAKE: WELCOME from {h} to you — you may present", flush=True)
            rx.close(); return 0
        if addr == my_dm_addr:
            print(f"[{ts}] WAKE: DM from {h}: {a[2]}  — read "
                  f"{dm_log_path(handle, h).name}, then re-arm `wait`", flush=True)
            rx.close(); return 0
        # A_ACK / A_PING / A_HERE / A_REL / DM-to-someone-else / worklog: keep waiting.


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["listen", "wait", "who", "join", "say", "ack",
                                     "release", "welcome", "status",
                                     "dm-say", "dm-wait", "dm-status", "check-queue"])
    ap.add_argument("--handle", default=os.environ.get("SAO_HANDLE", ""))
    ap.add_argument("--text", default="")
    ap.add_argument("--re", default="")
    ap.add_argument("--to", default="")
    ap.add_argument("--held", action="store_true",
                    help="say: I already hold the lock (after `ack`)")
    ap.add_argument("--timeout", type=float, default=0.0,
                    help="wait/dm-wait: give up after S seconds (0 = block forever)")
    ap.add_argument("--queue-file", default=str(QUEUE_FILE),
                    help="listen: write events to this file (default: SAO/.osc-queue.jsonl)")
    ap.add_argument("--since", type=float, default=0.0,
                    help="check-queue: only show events since this UNIX epoch")
    ap.add_argument("--clear", action="store_true",
                    help="check-queue: clear the queue after printing")
    a = ap.parse_args()
    if a.mode not in ("status", "check-queue") and not a.handle:
        sys.exit("--handle required (pick a Gibsonesque nom de guerre; see the spec)")
    if a.mode == "listen":
        listen(a.handle, a.queue_file)
    elif a.mode == "wait":
        sys.exit(wait(a.handle, a.timeout))
    elif a.mode == "who":
        who(a.handle)
    elif a.mode == "join":
        join(a.handle, a.text or f"*{a.handle} joins the channel.*")
    elif a.mode == "say":
        say(a.handle, a.text, a.re, held=a.held)
    elif a.mode == "ack":
        ack(a.handle, a.re or "-")
    elif a.mode == "release":
        release_lock(); _send(A_REL, a.handle, now(), a.text or "abandoned")
        print("[dialogue] released")
    elif a.mode == "welcome":
        _send(A_WELCOME, a.handle, now(), a.to)
        print(f"[dialogue] welcomed {a.to}")
    elif a.mode == "dm-say":
        if not a.to:
            sys.exit("dm-say requires --to TARGET_HANDLE")
        dm_say(a.handle, a.to, a.text, a.re)
    elif a.mode == "dm-wait":
        sys.exit(dm_wait(a.handle, a.timeout))
    elif a.mode == "dm-status":
        dm_status(a.handle)
    elif a.mode == "check-queue":
        check_queue(a.handle or "?", a.since, a.clear)
    else:
        h = lock_holder()
        print(f"LOCK: {'held by ' + h[0] + ' since ' + h[1] if h else 'free'}")
        if LOG.exists():
            print("".join(LOG.read_text().splitlines(keepends=True)[-15:]))


if __name__ == "__main__":
    main()
