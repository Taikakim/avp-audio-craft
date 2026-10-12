"""SA3 backbones the forge can switch between (spec §5.3 MODEL STAGE, §6.4)."""
import json
import os
from pathlib import Path

BACKBONES = {"medium": "rf_denoiser", "medium-base": "rectified_flow",
             "small-music": "rf_denoiser", "small-music-base": "rectified_flow"}


def hub_dir() -> Path:
    if os.environ.get("HF_HUB_CACHE"):
        return Path(os.environ["HF_HUB_CACHE"])
    if os.environ.get("HF_HOME"):
        return Path(os.environ["HF_HOME"]) / "hub"
    return Path.home() / ".cache" / "huggingface" / "hub"


def cached_config(model_id, hub=None):
    snaps = Path(hub or hub_dir()) / f"models--stabilityai--stable-audio-3-{model_id}" / "snapshots"
    hits = sorted(snaps.glob("*/model_config.json")) if snaps.is_dir() else []
    return hits[0] if hits else None


def _find(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            found = _find(v, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _find(v, key)
            if found is not None:
                return found
    return None


def objective_of(model_id, hub=None) -> str:
    cfg = cached_config(model_id, hub)
    if cfg is not None:
        try:
            found = _find(json.loads(cfg.read_text()), "diffusion_objective")
            if found:
                return str(found)
        except (OSError, ValueError):
            pass
    return BACKBONES[model_id]


def listing(hub=None):
    return [{"id": i, "objective": objective_of(i, hub), "cached": cached_config(i, hub) is not None}
            for i in BACKBONES]
