"""Named JSON documents on disk: sessions and presets (spec §6.3)."""
import json
import os
import tempfile
from pathlib import Path

from .contract import ForgeError, check_name


class JsonStore:
    def __init__(self, root, max_bytes):
        self.root = Path(root)
        self.max_bytes = int(max_bytes)

    def _path(self, name) -> Path:
        return self.root / f"{check_name(name)}.json"

    def names(self):
        if not self.root.is_dir():
            return []
        return sorted(p.stem for p in self.root.glob("*.json"))

    def listing(self):
        return [{"name": n, "updated": self._path(n).stat().st_mtime} for n in self.names()]

    def get(self, name) -> dict:
        p = self._path(name)
        if not p.is_file():
            raise ForgeError(404, f"no such entry {name!r}")
        return json.loads(p.read_text())

    def put(self, name, obj) -> None:
        p = self._path(name)
        if not isinstance(obj, dict):
            raise ForgeError(400, "payload must be a JSON object")
        data = json.dumps(obj, indent=2).encode()
        if len(data) > self.max_bytes:
            raise ForgeError(400, f"payload too large ({len(data)} > {self.max_bytes} bytes)")
        self.root.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.root, suffix=".part")
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, p)

    def delete(self, name) -> None:
        p = self._path(name)
        if not p.is_file():
            raise ForgeError(404, f"no such entry {name!r}")
        p.unlink()
