"""A preset is a /generate payload with a name. Nothing more.

Deliberately NOT a new parameter model: the payload is passed to the render
server untouched, so a preset stays valid as the server grows knobs. seed and
batch_size are stripped because a preset is a RECIPE -- a pinned seed would make
a sweep's seed axis a silent no-op, which is the kind of bug you only notice
after burning the renders.

ckpt_path and the whole dora block ARE kept: "the same preset on a different
model" works by overriding them, and you want to see what the preset was
authored against.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

SCHEMA_VERSION = 1
PRESET_DIR = Path("/home/kim/Projects/SAO/eval/presets")
VOLATILE_KEYS = frozenset({"seed", "batch_size", "job_id"})


def slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", str(name).strip().lower()).strip("-")
    return s or "preset"


def _dir(d) -> Path:
    p = Path(d) if d is not None else PRESET_DIR
    p.mkdir(parents=True, exist_ok=True)
    return p


def save(name, payload, *, notes="", form=None, dir=None) -> Path:
    """`payload` is what the render server consumes. `form` is the optional
    viewer-side snapshot {dash_id: value}.

    Both are stored because they answer different questions. The payload is what
    a CLI sweep POSTs; the form is what the GUI puts back in its boxes. Storing
    the form rather than inverting the payload is deliberate -- build_payload()
    merges (base prompt + variation), resolves dist-shift and collapses 35
    steering states into three blocks, so an inverse mapping would be a second
    source of truth that drifts. Reload the form, run it back through the SAME
    builder, get the same payload by construction.
    """
    if not str(payload.get("prompt", "")).strip():
        raise ValueError("a preset needs a non-empty prompt")
    body = {k: v for k, v in payload.items() if k not in VOLATILE_KEYS}
    rec = {"schema": SCHEMA_VERSION, "name": str(name), "notes": str(notes),
           "created": time.time(), "payload": body}
    if form:
        rec["form"] = dict(form)
    p = _dir(dir) / f"{slug(name)}.json"
    p.write_text(json.dumps(rec, indent=2, sort_keys=True))
    return p


def load(name, *, dir=None) -> dict:
    p = _dir(dir) / f"{slug(name)}.json"
    if not p.exists():
        raise FileNotFoundError(f"no preset {name!r} at {p}")
    return json.loads(p.read_text())


def list_presets(dir=None) -> list[dict]:
    """Newest first. A corrupt file is skipped, not fatal -- one bad hand-edit
    must not take the whole picker down."""
    out = []
    for p in _dir(dir).glob("*.json"):
        try:
            d = json.loads(p.read_text())
            out.append({"name": d["name"], "notes": d.get("notes", ""),
                        "created": d.get("created", 0.0),
                        "prompt": d.get("payload", {}).get("prompt", ""),
                        "path": str(p)})
        except (ValueError, KeyError, OSError):
            continue
    return sorted(out, key=lambda d: d["created"], reverse=True)
