"""Mount + checkpoint-root resolution for the SA3 inference surface.

Standing project rule: NO drive paths in code. Everything comes from
eval/model_roots.json. Mounts are resolved by probing a marker subdirectory --
the generalisation of explorer_render_server._mantu_root(), which exists because
the eval drive mounts as Mantu or Mantu1 depending on mount order (C bug
2026-07-13). A root whose mount is absent is still returned, with
available=False, so callers can serve a cached journal instead of 404ing.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path

DEFAULT_CONFIG_PATH = Path(__file__).with_name("model_roots.json")
_TOKEN = re.compile(r"\$\{([A-Z0-9_]+)\}")


@dataclass
class Root:
    id: str
    label: str
    path: str | None          # expanded; None when the mount is unresolved
    priority: int
    enabled: bool
    available: bool           # path is not None AND is an existing directory
    template: str
    note: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def load_config(path: str | Path | None = None) -> dict:
    """Read the roots config. Env SA3_MODEL_ROOTS overrides the default path."""
    p = Path(path or os.environ.get("SA3_MODEL_ROOTS") or DEFAULT_CONFIG_PATH)
    return json.loads(Path(p).read_text())


def resolve_mounts(cfg: dict) -> dict[str, str | None]:
    """Logical mount name -> the candidate that actually carries its marker."""
    out: dict[str, str | None] = {}
    for name, spec in (cfg.get("mounts") or {}).items():
        marker = spec.get("marker")
        chosen = None
        for cand in spec.get("candidates") or []:
            probe = Path(cand, marker) if marker else Path(cand)
            if probe.is_dir():
                chosen = cand
                break
        out[name] = chosen
    return out


def expand(template: str, mounts: dict[str, str | None]) -> str | None:
    """Substitute ${MOUNT} tokens. None if any token is unresolved."""
    missing = [m.group(1) for m in _TOKEN.finditer(template)
               if mounts.get(m.group(1)) is None]
    if missing:
        return None
    return _TOKEN.sub(lambda m: mounts[m.group(1)], template)


def resolve_roots(cfg: dict | None = None) -> list[Root]:
    """All configured roots, highest priority first, with availability filled in."""
    cfg = cfg if cfg is not None else load_config()
    mounts = resolve_mounts(cfg)
    roots: list[Root] = []
    for spec in cfg.get("roots") or []:
        template = spec["path"]
        path = expand(template, mounts)
        roots.append(Root(
            id=spec["id"],
            label=spec.get("label", spec["id"]),
            path=path,
            priority=int(spec.get("priority", 0)),
            enabled=bool(spec.get("enabled", True)),
            available=bool(path) and Path(path).is_dir(),
            template=template,
            note=spec.get("note", ""),
        ))
    roots.sort(key=lambda r: (-r.priority, r.id))
    return roots


def limits(cfg: dict | None = None) -> dict:
    cfg = cfg if cfg is not None else load_config()
    lim = dict(cfg.get("limits") or {})
    lim.setdefault("max_resident_adapters", 4)
    lim.setdefault("vram_floor_gb", 6.0)
    return lim
