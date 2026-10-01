"""Storage layout under OUT_DIR/_forge (spec §6.3)."""
from pathlib import Path

from .contract import check_level


class ForgePaths:
    def __init__(self, out_dir):
        self.root = Path(out_dir) / "_forge"
        self.uploads = self.root / "uploads"
        self.sessions = self.root / "sessions"
        self.presets = self.root / "presets"
        self.cache = self.root / "cache"

    def ensure(self) -> "ForgePaths":
        for d in (self.uploads, self.sessions, self.presets, self.cache):
            d.mkdir(parents=True, exist_ok=True)
        return self

    def cache_dir(self, kind: str) -> Path:
        d = self.cache / kind
        d.mkdir(parents=True, exist_ok=True)
        return d

    def preset_dir(self, level: str) -> Path:
        d = self.presets / check_level(level)
        d.mkdir(parents=True, exist_ok=True)
        return d
