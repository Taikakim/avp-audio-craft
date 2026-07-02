#!/usr/bin/env python3
"""Agent dialogue protocol over the SAO OSC multicast channel (stdlib-only).

Spec: docs/superpowers/specs/2026-07-02-agent-dialogue-osc-protocol.md (+ MASTER §4).
Transport: the multicast group from Misc/osc_worklog.py (239.7.7.7:57327, loopback).

The pieces:
  AGENT_DIALOGUE.md   the ONE human-readable conversation log (linear, timestamped,
                      per-agent Gibsonesque handles to separate the voices)
  .dialogue.lock      the reservation (atomic O_EXCL create; OSC only ANNOUNCES it —
                      packets are lossy, the file is the mutex)

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

Subcommands:
  listen  --handle H     event stream (one line per event) + auto-replies to presence
                         pings. Run under your background-monitor facility (keeps you
                         PRESENT; does NOT itself wake a polling monitor).
  wait    --handle H [--timeout S]
                         BLOCK until the next wake-worthy event from ANOTHER handle
                         (msg / knock / welcome-to-me), print it, and EXIT. Run under
                         run_in_background so its EXIT is the wake — this turns each OSC
                         message into a wake-up signal (re-arm it after each wake).
                         Ignores presence pings (listen answers those) and own traffic.
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


# ---- the log ----

def _append(text: str, handle: str, re: str = "") -> int:
    if not LOG.exists():
        LOG.write_text("# SAO Agent Dialogue\n\nHuman-readable conversation between "
                       "Claude instances. Protocol: docs/superpowers/specs/"
                       "2026-07-02-agent-dialogue-osc-protocol.md. One entry per "
                       "message; handles are per-agent noms de guerre; do not edit "
                       "others' entries.\n")
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


def listen(handle: str) -> None:
    rx = _rx_socket()
    sys.stderr.write(f"[dialogue] {handle} listening on {GROUP}:{PORT}\n")
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
            print(f"[{ts}] MSG from {h}: {a[2]}  (log now {a[3] or '?'} lines) — read AGENT_DIALOGUE.md", flush=True)
        elif addr == A_ACK:
            print(f"[{ts}] ACK from {h} (composing re: {a[2]}) — log RESERVED, wait for their MSG", flush=True)
        elif addr == A_REL:
            print(f"[{ts}] RELEASE from {h} ({a[2]}) — log free", flush=True)
        elif addr == A_KNOCK:
            print(f"[{ts}] KNOCK from {h} — joined, awaiting permission to present. "
                  f"If you hold the lock, grant with: welcome --to {h}", flush=True)
        elif addr == A_WELCOME:
            print(f"[{ts}] WELCOME from {h} to {a[2]}", flush=True)
        elif addr == "/sao/worklog":
            print(f"[{now()}] WORKLOG ping from {h}: {a[1][:100]}", flush=True)


def wait(handle: str, timeout: float = 0.0) -> int:
    """Block until the next wake-worthy event from another handle, print it, EXIT.

    Wake triggers: a posted msg (A_MSG), a knock (someone wants the floor), or a
    welcome addressed to us. Presence pings and our own traffic are ignored — the
    persistent `listen` handles presence. Designed to run under run_in_background:
    the process EXIT is the wake, so each OSC message becomes a wake-up signal.
    Returns 0 on a wake event, 2 on timeout (no event within --timeout seconds)."""
    rx = _rx_socket()
    if timeout and timeout > 0:
        rx.settimeout(timeout)
    sys.stderr.write(f"[dialogue] {handle} waiting for next wake event on {GROUP}:{PORT}\n")
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
        # A_ACK / A_PING / A_HERE / A_REL / worklog: not wake-worthy; keep waiting.


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["listen", "wait", "who", "join", "say", "ack",
                                     "release", "welcome", "status"])
    ap.add_argument("--handle", default=os.environ.get("SAO_HANDLE", ""))
    ap.add_argument("--text", default="")
    ap.add_argument("--re", default="")
    ap.add_argument("--to", default="")
    ap.add_argument("--held", action="store_true",
                    help="say: I already hold the lock (after `ack`)")
    ap.add_argument("--timeout", type=float, default=0.0,
                    help="wait: give up after S seconds (0 = block forever)")
    a = ap.parse_args()
    if a.mode != "status" and not a.handle:
        sys.exit("--handle required (pick a Gibsonesque nom de guerre; see the spec)")
    if a.mode == "listen":
        listen(a.handle)
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
    else:
        h = lock_holder()
        print(f"LOCK: {'held by ' + h[0] + ' since ' + h[1] if h else 'free'}")
        if LOG.exists():
            print("".join(LOG.read_text().splitlines(keepends=True)[-15:]))


if __name__ == "__main__":
    main()
