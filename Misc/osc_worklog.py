#!/usr/bin/env python3
"""OSC coordination channel for SAO Claude instances (stdlib-only, loopback MULTICAST).

v2 (2026-07-02): switched from unicast to MULTICAST after a correct objection from a
sibling instance — unicast UDP is point-to-point (a second listener either fails to
bind or, with SO_REUSEPORT, LOAD-BALANCES packets: each ping reaches only ONE
listener). Multicast is UDP's actual pub-sub: every process that joins the group gets
its own copy, so any number of instances can co-listen.

Convention (pre-arranged; see MASTER.md "Cross-instance signaling"):
  address  /sao/worklog          — "WORKLOG.md was appended; go read it"
  args     (s session_tag, s note, i worklog_line_count)
  endpoint multicast 239.7.7.7:57327 on the loopback interface (never leaves the host)

Pings are fire-and-forget with NO replay: anything sent while you weren't listening is
gone. Therefore: read WORKLOG on session start regardless; the ping only covers the
"while alive" case.

Send (after appending to WORKLOG — or just use Misc/worklog_note.sh):
    python3 Misc/osc_worklog.py send --session fusion-night --note "ES pilot done"

Listen (run under your Monitor/background facility; one stdout line per ping):
    python3 Misc/osc_worklog.py listen

Self-test (proves FAN-OUT: two listeners in one process must BOTH receive one ping):
    python3 Misc/osc_worklog.py selftest
"""
from __future__ import annotations

import argparse, os, socket, struct, sys, time

GROUP, PORT = "239.7.7.7", 57327          # administratively-scoped multicast, loopback only
LOOP_IF = "127.0.0.1"
ADDRESS = "/sao/worklog"
WORKLOG = "/home/kim/Projects/SAO/WORKLOG.md"


# ---- minimal OSC 1.0 encoding/decoding (strings + int32) ----

def _pad(b: bytes) -> bytes:
    return b + b"\x00" * (4 - len(b) % 4 if len(b) % 4 else 4)  # OSC strings: NUL + pad to 4


def _osc_str(s: str) -> bytes:
    return _pad(s.encode("utf-8"))


def encode(address: str, *args) -> bytes:
    tags = ","
    payload = b""
    for a in args:
        if isinstance(a, int):
            tags += "i"; payload += struct.pack(">i", a)
        else:
            tags += "s"; payload += _osc_str(str(a))
    return _osc_str(address) + _osc_str(tags) + payload


def _read_str(buf: bytes, i: int):
    end = buf.index(b"\x00", i)
    s = buf[i:end].decode("utf-8", "replace")
    return s, (end + 4) & ~3


def decode(buf: bytes):
    addr, i = _read_str(buf, 0)
    tags, i = _read_str(buf, i)
    args = []
    for t in tags.lstrip(","):
        if t == "i":
            args.append(struct.unpack(">i", buf[i:i + 4])[0]); i += 4
        elif t == "s":
            s, i = _read_str(buf, i); args.append(s)
        else:
            break
    return addr, args


# ---- sockets ----

def _tx_socket() -> socket.socket:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
    s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(LOOP_IF))
    s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)  # local members receive
    return s


def _rx_socket() -> socket.socket:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)   # co-listeners on Linux
    except (AttributeError, OSError):
        pass
    s.bind(("", PORT))
    mreq = socket.inet_aton(GROUP) + socket.inet_aton(LOOP_IF)    # join group on loopback
    s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    return s


# ---- modes ----

def send(session: str, note: str) -> None:
    lines = 0
    try:
        lines = sum(1 for _ in open(WORKLOG, "rb"))
    except OSError:
        pass
    pkt = encode(ADDRESS, session, note, lines)
    with _tx_socket() as s:
        s.sendto(pkt, (GROUP, PORT))
    print(f"[osc] sent {ADDRESS} (multicast {GROUP}:{PORT}) session={session!r} "
          f"note={note!r} lines={lines}")


def listen() -> None:
    with _rx_socket() as s:
        sys.stderr.write(f"[osc] joined multicast {GROUP}:{PORT} for {ADDRESS} "
                         f"(co-listening safe)\n")
        while True:
            buf, _ = s.recvfrom(4096)
            try:
                addr, args = decode(buf)
            except Exception:
                continue
            if addr == ADDRESS:
                sess = args[0] if len(args) > 0 else "?"
                note = args[1] if len(args) > 1 else ""
                n = args[2] if len(args) > 2 else -1
                print(f"WORKLOG_UPDATED session={sess} lines={n} note={note}", flush=True)


def selftest() -> int:
    """Fan-out proof: TWO listeners must EACH receive the same single ping."""
    rx1, rx2 = _rx_socket(), _rx_socket()
    rx1.settimeout(3.0); rx2.settimeout(3.0)
    with _tx_socket() as tx:
        tx.sendto(encode(ADDRESS, "selftest", "ping", 123), (GROUP, PORT))
    ok = True
    for i, rx in enumerate((rx1, rx2), 1):
        try:
            addr, args = decode(rx.recvfrom(4096)[0])
            got = addr == ADDRESS and args == ["selftest", "ping", 123]
        except socket.timeout:
            got = False
        print(f"[osc] listener {i}: {'received' if got else 'MISSED'}")
        ok &= got
    rx1.close(); rx2.close()
    print(f"[osc] selftest {'OK — true fan-out (both listeners got the ping)' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["send", "listen", "selftest"])
    ap.add_argument("--session", default=os.environ.get("SAO_SESSION", "unnamed"))
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    if a.mode == "send":
        send(a.session, a.note)
    elif a.mode == "listen":
        listen()
    else:
        sys.exit(selftest())
