"""FILES module listing (spec §6.3 GET /forge/files)."""
from pathlib import Path

from .contract import AUDIO_EXTS, ForgeError

ROOT_ORDER = ("crops", "renders", "uploads")
ROOT_LABELS = {"crops": "latent crops", "renders": "renders", "uploads": "uploads"}


def _row(root_id, rel, kind, p: Path, ref):
    st = p.stat()
    return {"root": root_id, "rel": rel, "kind": kind, "size": st.st_size, "mtime": st.st_mtime, "ref": ref}


def list_files(roots, root_id, q, limit):
    listing = [{"id": rid, "label": ROOT_LABELS[rid],
                "available": bool(roots.get(rid) and Path(roots[rid]).is_dir())} for rid in ROOT_ORDER]
    if root_id not in ROOT_ORDER:
        raise ForgeError(400, f"unknown root {root_id!r} (have {', '.join(ROOT_ORDER)})")
    base = roots.get(root_id)
    files = []
    ql = (q or "").lower()
    limit = max(1, min(int(limit), 5000))
    if base and Path(base).is_dir():
        base = Path(base)
        if root_id == "crops":
            for p in sorted(base.glob("*.npy")):
                if ql in p.stem.lower():
                    files.append(_row("crops", p.name, "latent", p, {"kind": "crop", "crop_id": p.stem}))
                if len(files) >= limit:
                    break
        elif root_id == "renders":
            wavs = [p for p in base.glob("*/out_*.wav") if not p.parent.name.startswith("_")]
            for p in sorted(wavs, key=lambda x: x.stat().st_mtime, reverse=True):
                rel = f"{p.parent.name}/{p.name}"
                if ql in rel.lower():
                    files.append(_row("renders", rel, "audio", p,
                                      {"kind": "render", "job_id": p.parent.name, "file": p.name}))
                if len(files) >= limit:
                    break
        else:
            for p in sorted(base.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
                if p.suffix.lower() in AUDIO_EXTS and ql in p.name.lower():
                    files.append(_row("uploads", p.name, "audio", p, {"kind": "upload", "sha256": p.stem}))
                if len(files) >= limit:
                    break
    return {"roots": listing, "files": files}
