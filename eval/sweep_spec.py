"""The sweep grammar: axes in, cells out, with an id that survives a resume.

A GUI is the wrong shape for "sweep one axis with everything else pinned" -- that
is gap #4 in docs/INFERENCE-SURFACE.md. This module is the pure half of the fix:
it takes a render payload (a preset, see presets.py) plus a dict of axes and
produces the cross-product of cells. It performs no I/O beyond reading a spec file
and knows nothing about HTTP -- sweep_run.py is the client of :8056, so there is
never a second implementation of guidance (the server NORMALISES gains; a raw
weight computed anywhere else is a different scale).

Two decisions worth knowing before you extend it:

* **Seeds are an argument, not an axis.** They multiply every other axis, and a
  preset deliberately carries no seed, so making them an axis would invite exactly
  the bug presets.VOLATILE_KEYS exists to prevent.
* **cell_id is the resume key**, so it is a hash of the canonical coords, not a
  formatted string. Two cells differing only in a float that prints the same must
  still get different ids, and typing the axes in a different order next week must
  NOT invalidate a half-finished sweep.
"""
from __future__ import annotations

import copy
import hashlib
import itertools
import json
import re
from pathlib import Path

SCHEMA_VERSION = 1

# Ergonomics, not a whitelist: an axis name absent from this map is used as a raw
# dotted path, so the sweep does not need editing every time the server grows a knob.
AXIS_KINDS = {
    "strength": "dora.strength",
    "cfg": "cfg_scale",
    "steps": "steps",
    "duration": "duration",
    "prompt": "prompt",
    "apg": "apg_scale",
    "gamma": "gamma",
    "n_iter": "n_iter",
    "rho": "rho",
    "mu": "mu",
    "latch1_value": "latch.0.value",
    "latch1_gain": "latch.0.gain",
    "latch1_head": "latch.0.head",
    "latch2_value": "latch.1.value",
    "latch2_gain": "latch.1.gain",
    "film_value": "film.value",
    "film_gain": "film.gain",
    "model": "ckpt_path",
}


def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=repr)


def set_path(payload, dotted, value):
    """Deep copy of `payload` with `dotted` set. An integer segment indexes a list."""
    out = copy.deepcopy(payload)
    node = out
    parts = dotted.split(".")
    for i, key in enumerate(parts[:-1]):
        nxt = parts[i + 1]
        if key.isdigit():
            node = node[int(key)]
            continue
        if key not in node or not isinstance(node[key], (dict, list)):
            node[key] = [] if nxt.isdigit() else {}
        node = node[key]
    last = parts[-1]
    if last.isdigit():
        node[int(last)] = value
    else:
        node[last] = value
    return out


def _stem(coords) -> str:
    """Human-readable prefix. Lossy on purpose -- the hash carries correctness."""
    bits = []
    for k in sorted(coords):
        v = coords[k]
        s = re.sub(r"[^A-Za-z0-9.+-]+", "", str(v))[:16]
        bits.append(f"s{s}" if k == "seed" else f"{k}{s}")
    return "__".join(bits)[:80] or "cell"


def cell_id(coords) -> str:
    h = hashlib.sha1(_canon(coords).encode()).hexdigest()[:12]
    return f"{_stem(coords)}__{h}"


def expand(payload, axes, *, seeds=None) -> list[dict]:
    """Cross-product of `axes` (x seeds) over `payload`. Never mutates the input."""
    names = sorted(axes)                       # sorted => ids are order-independent
    for n in names:
        if not isinstance(axes[n], list) or not axes[n]:
            raise ValueError(f"axis {n!r} must be a non-empty list")
    combos = list(itertools.product(*(axes[n] for n in names))) or [()]
    seed_list = list(seeds) if seeds else [-1]     # -1 => the server picks and reports
    cells = []
    for combo in combos:
        for sd in seed_list:
            coords = dict(zip(names, combo))
            coords["seed"] = sd
            p = copy.deepcopy(payload)
            for n, v in zip(names, combo):
                p = set_path(p, AXIS_KINDS.get(n, n), v)
            p["seed"] = sd
            cells.append({"cell_id": cell_id(coords), "coords": coords, "payload": p})
    return cells


def validate_spec(spec) -> list[str]:
    """Problems with a sweep spec; empty list == ok."""
    problems = []
    if not spec.get("preset") and not spec.get("payload"):
        problems.append("spec needs either 'preset' (a name) or an inline 'payload'")
    axes = spec.get("axes") or {}
    if not isinstance(axes, dict):
        problems.append("'axes' must be an object")
        return problems
    for n, v in axes.items():
        if not isinstance(v, list):
            problems.append(f"axis {n!r} must be a list, got {type(v).__name__}")
        elif not v:
            problems.append(f"axis {n!r} is empty")
    if spec.get("seeds") is not None and not isinstance(spec["seeds"], list):
        problems.append("'seeds' must be a list of integers")
    return problems


def load_spec(path) -> dict:
    return json.loads(Path(path).read_text())
