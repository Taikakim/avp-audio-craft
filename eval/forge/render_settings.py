"""RenderSettings / LaneChain (spec §6.1) -> request dicts for the server's resolvers (§5.5)."""
import json
import math

from .contract import ForgeError
from .schedule import RF_SAMPLERS, parse_spec

RENDER_DEFAULTS = {"prompt": "", "negative_prompt": "", "steps": 24, "cfg_scale": 6.0, "seed": -1,
                   "apg_scale": 1.0, "cfg_interval_progress": [0.0, 1.0], "schedule": {"shape": "model"},
                   "scale_phi": 0.0, "sampler_type": None}
SLOT_DEFAULT = {"head": "none", "kind": "constant", "value": 0.0, "weight": 1.0, "start_pct": 0.0, "end_pct": 0.6,
                "value_from": None}
# A ramp is built here, not by the model's own ramp_up/ramp_down. Those run 0 -> value in RAW feature units
# (stable_audio_3/inference/latch_targets.py), which is a sane sweep for a dB head near -30 and an
# impossible one for hardness (66.2 +/- 3.5): the target starts 19 sigma below the data and the guidance
# drives the render to noise. With `value_from` the ramp runs value_from -> value inside the head's own range.
RAMP_KINDS = ("ramp_up", "ramp_down")
RAMP_POINTS = 257
CHAIN_DEFAULTS = {"latch_on": False, "slots": [dict(SLOT_DEFAULT), dict(SLOT_DEFAULT)],
                  "hparams": {"rho": 1.0, "mu": 1.0, "gamma": 0.3, "n_iter": 4, "log_norms": False},
                  "film_on": False, "film": {"ckpt": None, "gain": 1.75, "value": 4.0},
                  "lora_on": False, "lora": {"ckpt_path": None, "slot": None, "strength": 1.0},
                  "bungee_on": False, "semitones": 0.0}
_SAMPLERS = sorted({s for v in RF_SAMPLERS.values() for s in v})


def _num(v, lo, hi, what, integer=False):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not lo <= v <= hi:
        raise ForgeError(400, f"{what}={v!r} outside {lo}..{hi}")
    if integer:
        if float(v) != int(v):
            raise ForgeError(400, f"{what} must be an integer")
        return int(v)
    return float(v)


def _merge(defaults, obj, what):
    if obj is None:
        obj = {}
    if not isinstance(obj, dict):
        raise ForgeError(400, f"{what} must be an object")
    unknown = sorted(set(obj) - set(defaults))
    if unknown:
        raise ForgeError(400, f"unknown {what} field(s): {', '.join(unknown)}")
    return {**defaults, **obj}


def parse_render(obj) -> dict:
    r = _merge(RENDER_DEFAULTS, obj, "render")
    for k in ("prompt", "negative_prompt"):
        r[k] = "" if r[k] is None else r[k]
        if not isinstance(r[k], str):
            raise ForgeError(400, f"render.{k} must be a string")
    r["steps"] = _num(r["steps"], 1, 150, "render.steps", integer=True)
    r["cfg_scale"] = _num(r["cfg_scale"], 0, 64, "render.cfg_scale")
    r["seed"] = _num(r["seed"], -1, 2**31 - 1, "render.seed", integer=True)
    r["apg_scale"] = _num(r["apg_scale"], 0, 1, "render.apg_scale")
    r["scale_phi"] = _num(r["scale_phi"], 0, 1, "render.scale_phi")
    cip = r["cfg_interval_progress"]
    if not isinstance(cip, (list, tuple)) or len(cip) != 2:
        raise ForgeError(400, "render.cfg_interval_progress must be [lo, hi]")
    lo, hi = _num(cip[0], 0, 1, "cfg_interval_progress[0]"), _num(cip[1], 0, 1, "cfg_interval_progress[1]")
    if lo > hi:
        raise ForgeError(400, "render.cfg_interval_progress lo must be <= hi")
    r["cfg_interval_progress"] = [lo, hi]
    r["schedule"] = parse_spec(r["schedule"])
    if r["sampler_type"] in ("", None):
        r["sampler_type"] = None
    elif r["sampler_type"] not in _SAMPLERS:
        raise ForgeError(400, f"render.sampler_type {r['sampler_type']!r} not in {', '.join(_SAMPLERS)}")
    return r


def canonical_key(render) -> str:
    return json.dumps(render, sort_keys=True)


def to_request(render, seed) -> dict:
    keys = ("prompt", "negative_prompt", "steps", "cfg_scale", "apg_scale", "cfg_interval_progress",
            "schedule", "scale_phi", "sampler_type")
    return {**{k: render[k] for k in keys}, "seed": int(seed)}


def parse_chain(obj):
    if obj is None:
        return None
    c = _merge(CHAIN_DEFAULTS, obj, "chain")
    for flag in ("latch_on", "film_on", "lora_on", "bungee_on"):
        if not isinstance(c[flag], bool):
            raise ForgeError(400, f"chain.{flag} must be true or false")
    slots = c["slots"]
    if not isinstance(slots, list) or len(slots) != 2:
        raise ForgeError(400, "chain.slots must have exactly 2 entries")
    parsed = []
    for i, s in enumerate(slots):
        s = _merge(SLOT_DEFAULT, s, f"chain.slots[{i}]")
        s["weight"] = _num(s["weight"], 0, 50, f"slots[{i}].weight")
        s["start_pct"] = _num(s["start_pct"], 0, 1, f"slots[{i}].start_pct")
        s["end_pct"] = _num(s["end_pct"], 0, 1, f"slots[{i}].end_pct")
        s["value"] = _num(s["value"], -1e6, 1e6, f"slots[{i}].value")
        if s["value_from"] is not None:
            s["value_from"] = _num(s["value_from"], -1e6, 1e6, f"slots[{i}].value_from")
        if s["start_pct"] > s["end_pct"]:
            raise ForgeError(400, f"slots[{i}] start_pct must be <= end_pct")
        parsed.append(s)
    c["slots"] = parsed
    hp = _merge(CHAIN_DEFAULTS["hparams"], c["hparams"], "chain.hparams")
    c["hparams"] = {"rho": _num(hp["rho"], 0, 30, "hparams.rho"), "mu": _num(hp["mu"], 0, 30, "hparams.mu"),
                    "gamma": _num(hp["gamma"], 0, 20, "hparams.gamma"),
                    "n_iter": _num(hp["n_iter"], 1, 80, "hparams.n_iter", integer=True),
                    "log_norms": bool(hp["log_norms"])}
    film = _merge(CHAIN_DEFAULTS["film"], c["film"], "chain.film")
    c["film"] = {"ckpt": film["ckpt"] or None, "gain": _num(film["gain"], 0, 2, "film.gain"),
                 "value": _num(film["value"], 0, 16, "film.value")}
    lora = _merge(CHAIN_DEFAULTS["lora"], c["lora"], "chain.lora")
    c["lora"] = {"ckpt_path": lora["ckpt_path"] or None,
                 "slot": None if lora["slot"] is None else _num(lora["slot"], 0, 63, "lora.slot", integer=True),
                 "strength": _num(lora["strength"], 0, 1, "lora.strength")}
    c["semitones"] = _num(c["semitones"], -24, 24, "chain.semitones")
    return c


def ramp_points(start, end, n=RAMP_POINTS):
    """`n` evenly spaced values from start to end, first and last included."""
    return [start + (end - start) * i / (n - 1) for i in range(n)]


def chain_to_request(chain, heads) -> dict:
    out = {"latch": None, "film": None, "dora": None}
    if chain is None:
        return out
    if chain["latch_on"]:
        latch = []
        for s in chain["slots"]:
            if s["head"] in (None, "", "none") or s["weight"] <= 0:
                continue
            entry = heads.get(s["head"])
            if entry is None:
                raise ForgeError(400, f"unknown LatCH head {s['head']!r}")
            item = {"head": s["head"], "kind": s["kind"], "value": s["value"],
                    "gain": float(entry["default_gain"]) * s["weight"],
                    "start_pct": s["start_pct"], "end_pct": s["end_pct"]}
            if s["kind"] in RAMP_KINDS and s["value_from"] is not None:
                # [C, T] in raw feature units, which resolve_latch hands on as target_raw (it drops kind/value)
                item["target_raw"] = [ramp_points(s["value_from"], s["value"])]
            latch.append(item)
        if latch:
            g0, hp = latch[0]["gain"], chain["hparams"]
            out.update(latch=latch, rho=hp["rho"] * g0, mu=hp["mu"] * g0, gamma=hp["gamma"],
                       n_iter=hp["n_iter"], log_norms=hp["log_norms"])
    if chain["film_on"]:
        out["film"] = dict(chain["film"])
    if chain["lora_on"]:
        lora = chain["lora"]
        if lora["slot"] is not None:
            out["dora"] = {"slot": lora["slot"], "strength": lora["strength"]}
        elif lora["ckpt_path"]:
            out["dora"] = {"ckpt_path": lora["ckpt_path"], "strength": lora["strength"]}
    return out
