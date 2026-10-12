"""sha256 of a file, memoised on (path, size, mtime_ns) — cache keys for chroma/stretch/encode."""
import hashlib
import threading
from pathlib import Path

_lock = threading.Lock()
_memo = {}


def file_sha256(path) -> str:
    p = Path(path)
    st = p.stat()
    key = (str(p.resolve()), st.st_size, st.st_mtime_ns)
    with _lock:
        if key in _memo:
            return _memo[key]
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    digest = h.hexdigest()
    with _lock:
        _memo[key] = digest
    return digest
