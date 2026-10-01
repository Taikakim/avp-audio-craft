"""Streaming, content-addressed uploads (spec §6.3 PUT /forge/upload)."""
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from .contract import AUDIO_EXTS, ForgeError


class UploadWriter:
    def __init__(self, filename, uploads_dir, max_bytes):
        self.ext = Path(filename or "").suffix.lower()
        if self.ext not in AUDIO_EXTS:
            raise ForgeError(400, f"unsupported extension {self.ext or '(none)'} "
                                  f"(allowed: {' '.join(sorted(e[1:] for e in AUDIO_EXTS))})")
        self.dir = Path(uploads_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.max_bytes = int(max_bytes)
        self._hash = hashlib.sha256()
        self._n = 0
        fd, self._tmp = tempfile.mkstemp(dir=self.dir, suffix=".part")
        self._f = os.fdopen(fd, "wb")

    def feed(self, chunk: bytes) -> None:
        self._n += len(chunk)
        if self._n > self.max_bytes:
            self.abort()
            raise ForgeError(400, f"upload exceeds {self.max_bytes // (1 << 20)} MiB")
        self._hash.update(chunk)
        self._f.write(chunk)

    def finish(self):
        self._f.close()
        if self._n == 0:
            self.abort()
            raise ForgeError(400, "empty upload")
        sha = self._hash.hexdigest()
        dst = self.dir / f"{sha}{self.ext}"
        if dst.exists():
            os.unlink(self._tmp)
        else:
            os.replace(self._tmp, dst)
        return dst, sha, self._n

    def abort(self) -> None:
        try:
            self._f.close()
        except Exception:  # noqa: BLE001
            pass
        if os.path.exists(self._tmp):
            os.unlink(self._tmp)


def probe_audio(path) -> dict:
    cmd = ["ffprobe", "-v", "error", "-select_streams", "a:0",
           "-show_entries", "stream=sample_rate,channels:format=duration", "-of", "json", str(path)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise ForgeError(400, f"not a readable audio file: {r.stderr.strip()[:200]}")
    d = json.loads(r.stdout or "{}")
    streams = d.get("streams") or []
    if not streams or "duration" not in (d.get("format") or {}):
        raise ForgeError(400, "no audio stream found")
    return {"duration_sec": round(float(d["format"]["duration"]), 3),
            "sample_rate": int(streams[0]["sample_rate"]), "channels": int(streams[0]["channels"])}
