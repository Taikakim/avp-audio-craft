"""AudioRef -> server file path (spec §6.1). Every path a client names is validated here."""
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Callable, Optional

from .contract import AUDIO_EXTS, ForgeError

_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,120}$")


@dataclass
class RefContext:
    out_dir: Path
    uploads: Path
    latent_dir: Optional[Path]
    decode_crop: Callable[[str], Path]
    roots: dict = field(default_factory=dict)


def _hint(p: Path) -> str:
    return " — is the drive mounted?" if str(p).startswith("/run/media/") else ""


def _audio_file(p: Path) -> Path:
    if p.suffix.lower() not in AUDIO_EXTS:
        raise ForgeError(400, f"not an audio file: {p.name}")
    if not p.is_file():
        raise ForgeError(404, f"no such file: {p}{_hint(p)}")
    return p


def _segment(value, what) -> str:
    if not isinstance(value, str) or value in (".", "..") or not _ID_RE.match(value):
        raise ForgeError(400, f"invalid {what}: {value!r}")
    return value


def check_crop_id(crop_id) -> str:
    return _segment(crop_id, "crop_id")


def resolve_audio(ref, ctx: RefContext) -> Path:
    if not isinstance(ref, dict):
        raise ForgeError(400, "audio ref must be an object with a 'kind'")
    kind = ref.get("kind")
    if kind == "upload":
        sha = ref.get("sha256")
        if not isinstance(sha, str) or not _SHA_RE.match(sha):
            raise ForgeError(400, "upload ref needs a 64-hex sha256")
        hits = [p for p in sorted(Path(ctx.uploads).glob(f"{sha}.*")) if p.suffix.lower() in AUDIO_EXTS]
        if not hits:
            raise ForgeError(404, f"no upload {sha}")
        return hits[0]
    if kind == "render":
        job = _segment(ref.get("job_id"), "job_id")
        name = _segment(ref.get("file"), "file")
        return _audio_file(Path(ctx.out_dir) / job / name)
    if kind == "crop":
        cid = check_crop_id(ref.get("crop_id"))
        if ctx.latent_dir is None:
            raise ForgeError(404, "latent_dir not configured on the server")
        npy = Path(ctx.latent_dir) / f"{cid}.npy"
        if not npy.is_file():
            raise ForgeError(404, f"no crop {cid}{_hint(npy)}")
        return ctx.decode_crop(cid)
    if kind == "file":
        root_id = ref.get("root")
        if root_id not in ctx.roots:
            raise ForgeError(400, f"unknown root {root_id!r}")
        rel = ref.get("rel")
        parts = PurePosixPath(rel).parts if isinstance(rel, str) else ()
        if not rel or PurePosixPath(rel).is_absolute() or ".." in parts:
            raise ForgeError(400, f"invalid rel path {rel!r}")
        base = Path(ctx.roots[root_id]).resolve()
        p = (base / rel).resolve()
        if not p.is_relative_to(base):
            raise ForgeError(400, f"invalid rel path {rel!r}")
        return _audio_file(p)
    if kind == "path":
        raw = ref.get("path")
        if not isinstance(raw, str) or not raw.startswith("/"):
            raise ForgeError(400, "path ref needs an absolute server path")
        return _audio_file(Path(raw))
    raise ForgeError(400, f"unknown audio ref kind {kind!r}")
