"""One honest description of a LatCH head, from its own checkpoint metadata.

Why this exists: explorer_render_server._head_entry derived its slider from
md["slider_min"] / md["feature_stats"], and scripts/latch/train_latch.py:467-490
writes NEITHER -- so every head fell through to a shared -80/20/-30 default that is
right for the dB-valued rms_* family and wrong for everything else (beat_activation
is 0.044 +/- 0.066; hardness is 66.2 +/- 3.5). The keys that ARE written are
std_mean / std_std, and the value the user types is in RAW feature units
(model.py:529-542 standardizes it after target construction), so the dataset range
is directly the right slider range.

Beyond the slider this answers the three questions the panel could not: can this
head take a scalar target at all (a 384-d chroma head cannot), is its loss a knob
or a fixed property of the objective, and is the head healthy enough to trust.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

SCHEMA_VERSION = 1
OVERRIDES_PATH = Path("/home/kim/Projects/SAO/Misc/latch_head_overrides.json")
_FALLBACK = (-80.0, 20.0, -30.0)       # explorer_render_server.py:277, kept for parity
UNDERTRAINED_EPOCHS = 10               # others reach 18-20; spectral_kurtosis stopped at 3
UNSTABLE_SIGMA = 100.0                 # next-largest real sigma is 35.4 (rms_energy_body)


def _num(v, default=None):
    try:
        f = float(v)
        return f if math.isfinite(f) else default
    except (TypeError, ValueError):
        return default


def slider_bounds(std_mean, std_std, sigma_k=2.0):
    """(lo, hi, default) covering the dataset's own +/- k-sigma range, in raw units."""
    m, s = _num(std_mean), _num(std_std)
    if m is None or s is None or s <= 0.0:
        return _FALLBACK
    return (round(m - sigma_k * s, 6), round(m + sigma_k * s, 6), round(m, 6))


def load_overrides(path=None):
    """Human-supplied facts the checkpoints don't carry. Absent file == no overrides."""
    p = Path(path) if path is not None else OVERRIDES_PATH
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return {}


def _health(epoch, std_std):
    e, s = _num(epoch), _num(std_std)
    bits = []
    if s is not None and s > UNSTABLE_SIGMA:
        bits.append(f"dataset sigma is {s:g}")
    if e is None:
        return ("unknown", "checkpoint records no epoch count")
    if e < UNDERTRAINED_EPOCHS:
        bits.insert(0, f"trained only {e:g} epochs (others reached 20)")
        return ("undertrained", " and ".join(bits) + " -- treat its output as unreliable")
    if bits:
        return ("unstable", " and ".join(bits) + " -- targets far from the mean will be violent")
    return ("ok", "")


def _units(name, kind_default):
    if name.startswith("rms_"):
        return "dB"
    if kind_default == "beat_grid":
        return "bpm"
    return ""


def describe(name, family, path, default_gain, *, metadata=None,
             overrides=None, sigma_k=2.0):
    """The server's existing /info head dict, every legacy key kept, plus the truth."""
    md = dict(metadata or {})
    ov = (overrides if overrides is not None else load_overrides()).get(name, {})
    out_ch = int(_num(md.get("out_channels"), 1) or 1)
    loss = md.get("loss_type")
    kind_default = md.get("target_kind_default", "constant")
    smin, smax, sval = slider_bounds(md.get("std_mean"), md.get("std_std"), sigma_k)
    health, reason = _health(md.get("epoch"), md.get("std_std"))
    scalar_ok = out_ch == 1
    if not scalar_ok:
        readout = ov.get("readout") or md.get("chroma_key") or md.get("target_source")
        src = ("overrides" if ov.get("readout") else
               "checkpoint" if readout else "not-recorded")
        readout = readout or "unknown"
    else:
        readout, src = "n/a", "n/a"
    return {
        # --- unchanged; controls.py:_autofill_defaults depends on these names ---
        "name": name, "family": family, "path": str(path),
        "default_gain": float(default_gain), "out_channels": out_ch,
        "loss_type": loss, "target_kind_default": kind_default,
        "slider_min": smin, "slider_max": smax, "value_default": sval,
        # --- new ---
        "std_mean": _num(md.get("std_mean")), "std_std": _num(md.get("std_std")),
        "standardized": bool(md.get("standardized", False)), "sigma_k": float(sigma_k),
        "units": _units(name, kind_default),
        "epoch": _num(md.get("epoch")), "avg_loss": _num(md.get("avg_loss")),
        "val_loss": _num(md.get("val_loss")), "selected_on": md.get("selected_on"),
        "health": health, "health_reason": reason,
        "supports_scalar_target": scalar_ok,
        "supports_loss_select": loss != "cosine",
        "supports_kinds": ["constant", "ramp_up", "ramp_down", "beat_grid"] if scalar_ok else [],
        "readout": readout, "readout_source": src,
        "gain_scale_note": (f"auto rho/mu = this slot's gain ({float(default_gain):g}); "
                            f"per-slot weight = slot_gain / slot-1 gain"),
        "schema": SCHEMA_VERSION,
    }
