"""Constants and validation shared by every /forge route (spec §2, §6)."""
import math
import re

SR = 44100
HOP = 4096
FPS = SR / HOP
CAP_SEC = 184.0
AUDIO_EXTS = {".wav", ".flac", ".mp3", ".m4a", ".ogg", ".aif", ".aiff"}
PRESET_LEVELS = ("prompt", "render", "latch", "film", "lora", "bungee", "master")
MAX_PENDING_JOBS = 4
PRESET_MAX_BYTES = 1 << 20
SESSION_MAX_BYTES = 16 << 20
UPLOAD_MAX_BYTES = 512 << 20
SPLICE_XFADE_FRAMES = 2

_NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


class ForgeError(Exception):
    """A client-facing error with an HTTP status. Routes turn it into {"ok": false, "error"}."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = int(status)
        self.message = str(message)


def check_cap(duration_sec, what="request") -> float:
    try:
        d = float(duration_sec)
    except (TypeError, ValueError):
        raise ForgeError(400, f"{what}: duration must be a number")
    if not math.isfinite(d) or d <= 0:
        raise ForgeError(400, f"{what}: duration must be a positive number")
    if d > CAP_SEC:
        raise ForgeError(400, "forge passes are capped at 184 s locally (T<2048)")
    return d


def check_name(name) -> str:
    if not isinstance(name, str) or name in (".", "..") or not _NAME_RE.match(name):
        raise ForgeError(400, f"invalid name {name!r} (allowed: A-Z a-z 0-9 . _ -, 1-80 chars)")
    return name


def check_level(level) -> str:
    if level not in PRESET_LEVELS:
        raise ForgeError(400, f"unknown preset level {level!r} (have {', '.join(PRESET_LEVELS)})")
    return level


def latent_frames(duration_sec) -> int:
    return int(math.ceil(float(duration_sec) * SR / HOP))
