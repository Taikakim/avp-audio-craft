"""A sequence-numbered copy of the server log ring, so the TERMINAL tab can fetch only new lines."""
import threading
from collections import deque

_lock = threading.Lock()
_ring = deque(maxlen=400)
_seq = 0


def append(text) -> None:
    global _seq
    with _lock:
        _seq += 1
        _ring.append((_seq, str(text)))


def since(seq):
    seq = int(seq)
    with _lock:
        return _seq, [{"seq": s, "text": t} for s, t in _ring if s > seq]


def reset() -> None:
    global _seq
    with _lock:
        _ring.clear()
        _seq = 0
