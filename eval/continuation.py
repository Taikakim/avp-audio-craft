"""Recover a render's provenance from the sidecars written next to its latent.

WHY: `/longform init_latent_path` continues an existing render's LATENT, but the
adapter and its strength are re-specified by the caller. Say nothing and the tail
is rendered by whatever the server happens to have resident; say something
different and nothing objects. Either way the second half of a track can be a
different model from the first half, with no record anywhere (flagged as the
remaining increment in commit 632c417, deferred at the time as a one-off).

The information IS on disk, in one of two shapes depending on which renderer made
the prefix:
  * `<jobdir>/result.json`      -- what :8056 writes (meta.params_echo holds the
                                   whole request, including ckpt_path and dora)
  * `<stem>.mmline.json`        -- what the matrix-cell renderers write next to
                                   each clip (label/tag/ckpt/strength)

`recover()` reads whichever exists; `apply()` decides what to do with it. The
policy is deliberately NOT "force the prefix's model": rendering a tail with a
different adapter is a legitimate experiment. The policy is that a silent
divergence becomes a named warning, and a request that says nothing inherits the
prefix instead of inheriting the server's current state.
"""
from __future__ import annotations

import json
from pathlib import Path


def _read(p: Path):
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def recover(init_latent_path: str) -> dict:
    """{"ckpt_path", "dora", "label", "source"} — {} when nothing records it."""
    p = Path(init_latent_path)

    # <clip>.z0.npy -> <clip>.mmline.json  (strip BOTH suffixes)
    stem = p.name
    for suffix in (".z0.npy", ".npy"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    mm = p.with_name(stem + ".mmline.json")
    if mm.exists():
        d = _read(mm) or {}
        out = {"source": str(mm)}
        if d.get("ckpt"):
            out["ckpt_path"] = d["ckpt"]
        if d.get("strength") is not None or d.get("label"):
            out["dora"] = {"name": d.get("label"), "strength": d.get("strength")}
        if d.get("label"):
            out["label"] = d["label"]
        return out if len(out) > 1 else {}

    rj = p.with_name("result.json")
    if rj.exists():
        d = _read(rj) or {}
        echo = ((d.get("meta") or {}).get("params_echo")) or {}
        out = {"source": str(rj)}
        if echo.get("ckpt_path"):
            out["ckpt_path"] = echo["ckpt_path"]
        if echo.get("dora"):
            out["dora"] = echo["dora"]
        loaded = (d.get("meta") or {}).get("dora_loaded")
        if loaded and "label" not in out:
            out["label"] = loaded
        return out if len(out) > 1 else {}

    return {}


def _same(a, b) -> bool:
    if a is None or b is None:
        return a is b
    try:
        return abs(float(a) - float(b)) < 1e-9
    except (TypeError, ValueError):
        return a == b


def apply(req: dict, prior: dict) -> list[str]:
    """Mutate `req` in place; return warnings. The CALLER always wins on conflict."""
    if not prior:
        return []
    warnings: list[str] = []
    src = prior.get("source", "the prefix's sidecar")

    p_ckpt = prior.get("ckpt_path")
    ckpt_conflict = False
    if p_ckpt:
        r_ckpt = (req.get("ckpt_path") or "").strip() or None
        if r_ckpt is None:
            req["ckpt_path"] = p_ckpt
            warnings.append(f"continuation: recovered ckpt_path {p_ckpt} from {src} "
                            f"— the prefix and the tail now use the same model")
        elif r_ckpt != p_ckpt:
            ckpt_conflict = True
            warnings.append(f"continuation: THE TAIL USES A DIFFERENT MODEL THAN ITS "
                            f"PREFIX — prefix was {p_ckpt} (per {src}), this request "
                            f"asks for {r_ckpt}. Rendering as asked.")

    # A recovered DoRA belongs to the PREFIX's base model. If the caller has
    # deliberately pointed the tail at a different checkpoint, inheriting that
    # adapter would be a second silent substitution, not a fix for the first.
    p_dora = prior.get("dora") or {}
    if p_dora and not ckpt_conflict:
        r_dora = req.get("dora")
        if not r_dora:
            req["dora"] = dict(p_dora)
            warnings.append(f"continuation: recovered dora {p_dora} from {src}")
        else:
            for key in ("name", "strength"):
                pv, rv = p_dora.get(key), r_dora.get(key)
                if pv is not None and rv is not None and not _same(pv, rv):
                    warnings.append(
                        f"continuation: dora {key} differs from the prefix — "
                        f"prefix {pv}, this request {rv} (per {src}). Rendering as asked.")
    return warnings
