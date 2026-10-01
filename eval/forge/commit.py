"""MIXDOWN commit: payload validation, pass planning and orchestration (spec §6.9, §8)."""
from .contract import CAP_SEC, ForgeError, check_cap
from .envelope import validate_envelope
from .render_settings import _num, canonical_key, chain_to_request, parse_chain, parse_render

STAGES = ["DECODE latent → audio", "BUNGEE stretch / pitch", "ENCODE audio → latent", "LANE CHAINS",
          "A2A RE-NOISE", "INPAINT OVERLAPS", "MIX", "MASTER CHAIN", "DECODE latent → audio"]


def _bool(v, what):
    if not isinstance(v, bool):
        raise ForgeError(400, f"{what} must be true or false")
    return v


def audible_lanes(lanes):
    soloed = any(l["solo"] for l in lanes)
    return {l["index"]: (l["solo"] if soloed else not l["muted"]) for l in lanes}


def validate_commit(payload, heads):
    if not isinstance(payload, dict):
        raise ForgeError(400, "commit payload must be an object")
    bpm = _num(payload.get("project_bpm"), 20, 300, "project_bpm")
    duration = check_cap(payload.get("duration_sec"), "commit")
    defaults = parse_render(payload.get("defaults"))
    lanes_in = payload.get("lanes")
    if (not isinstance(lanes_in, list) or not all(isinstance(l, dict) for l in lanes_in)
            or sorted(l.get("index", -1) for l in lanes_in) != [0, 1, 2, 3]):
        raise ForgeError(400, "lanes must list indexes 0, 1, 2, 3 exactly once")
    lanes = []
    for l in sorted(lanes_in, key=lambda x: x["index"]):
        chain = parse_chain(l.get("chain") or {})
        chain_to_request(chain, heads)
        lanes.append({"index": int(l["index"]), "muted": _bool(l.get("muted", False), "lane.muted"),
                      "solo": _bool(l.get("solo", False), "lane.solo"),
                      "gain": _num(l.get("gain", 1.0), 0, 2, "lane.gain"), "chain": chain})
    clips, by_id = [], {}
    for c in payload.get("clips") or []:
        cid = c.get("id") if isinstance(c, dict) else None
        if not isinstance(cid, str) or not cid or cid in by_id:
            raise ForgeError(400, "clip ids must be unique non-empty strings")
        native = c.get("native_bpm")
        native = None if native is None else _num(native, 20, 300, f"clip {cid} native_bpm")
        if native is not None and not 0.5 <= bpm / native <= 2.0:
            raise ForgeError(400, f"clip {cid}: stretch ratio {bpm / native:.3f} outside 0.5..2")
        if not isinstance(c.get("audio"), dict):
            raise ForgeError(400, f"clip {cid}: audio must be an AudioRef object")
        a2a = c.get("a2a")
        if a2a is not None:
            if not isinstance(a2a, dict):
                raise ForgeError(400, f"clip {cid}: a2a must be an object or null")
            a2a = {"render": parse_render(a2a.get("render")), "envelope": validate_envelope(a2a.get("envelope"))}
        clip = {"id": cid, "lane": _num(c.get("lane"), 0, 3, f"clip {cid} lane", integer=True),
                "start_sec": _num(c.get("start_sec"), 0, CAP_SEC, f"clip {cid} start_sec"),
                "offset_sec": _num(c.get("offset_sec", 0.0), 0, 1e5, f"clip {cid} offset_sec"),
                "dur_sec": _num(c.get("dur_sec"), 1e-3, CAP_SEC, f"clip {cid} dur_sec"),
                "loop": _bool(c.get("loop", False), f"clip {cid} loop"), "audio": c["audio"],
                "native_bpm": native, "detune_cents": _num(c.get("detune_cents", 0.0), -100, 100, f"clip {cid} detune"),
                "a2a": a2a}
        clips.append(clip)
        by_id[cid] = clip
    if not clips:
        raise ForgeError(400, "nothing to commit — the arrangement has no clips")
    overlaps = []
    for o in payload.get("overlaps") or []:
        key = o.get("key")
        lane = _num(o.get("lane"), 0, 3, f"overlap {key} lane", integer=True)
        a, b = by_id.get(o.get("a_id")), by_id.get(o.get("b_id"))
        if a is None or b is None or a["lane"] != lane or b["lane"] != lane:
            raise ForgeError(400, f"overlap {key}: clips must both be on lane {lane}")
        start, end = _num(o.get("start_sec"), 0, CAP_SEC, "overlap start"), _num(o.get("end_sec"), 0, CAP_SEC, "overlap end")
        if not start < end:
            raise ForgeError(400, f"overlap {key}: start_sec < end_sec required")
        overlaps.append({"key": str(key), "lane": lane, "start_sec": start, "end_sec": end, "a_id": a["id"],
                         "b_id": b["id"], "curve": validate_envelope(o.get("curve")),
                         "chroma_xfade": _bool(o.get("chroma_xfade", True), "overlap.chroma_xfade"),
                         "render": parse_render(o.get("render"))})
    mix = payload.get("mix") or {}
    if mix.get("order") not in ("tree", "cascade", "quad"):
        raise ForgeError(400, f"unknown mix order {mix.get('order')!r}")
    nodes = {}
    for name in ("M1", "M2", "MX"):
        node = (mix.get("nodes") or {}).get(name) or {}
        if node.get("interp") not in ("lerp", "slerp"):
            raise ForgeError(400, f"mix node {name}: interp must be lerp or slerp")
        nodes[name] = {"interp": node["interp"], "t": _num(node.get("t"), 0, 1, f"mix node {name} t")}
    weights = mix.get("quad_weights")
    if not isinstance(weights, list) or len(weights) != 4:
        raise ForgeError(400, "mix.quad_weights must have 4 numbers")
    master = payload.get("master") or {}
    latch_on = _bool(master.get("latch_on", False), "master.latch_on")
    if latch_on and master.get("head") not in heads:
        raise ForgeError(400, f"unknown master head {master.get('head')!r}")
    return {"project_bpm": bpm, "duration_sec": duration, "defaults": defaults, "lanes": lanes, "clips": clips,
            "overlaps": overlaps,
            "mix": {"order": mix["order"], "nodes": nodes,
                    "quad_weights": [_num(w, 0, 1e6, "quad weight") for w in weights]},
            "master": {"latch_on": latch_on, "head": master.get("head"),
                       "gain": _num(master.get("gain", 64), 0, 120, "master.gain"),
                       "norm_on": _bool(master.get("norm_on", True), "master.norm_on")},
            "decode_lanes": _bool(payload.get("decode_lanes", False), "decode_lanes")}


def plan_passes(v):
    audible = audible_lanes(v["lanes"])
    a2a, inpaint = [], []
    for lane in range(4):
        if not audible[lane]:
            continue
        groups = {}
        for c in sorted((c for c in v["clips"] if c["lane"] == lane), key=lambda c: c["start_sec"]):
            if c["a2a"] is not None:
                groups.setdefault(canonical_key(c["a2a"]["render"]), []).append(c)
        for n, members in enumerate(groups.values()):
            a2a.append({"lane": lane, "key": f"lane{lane}:a2a:{n}", "render": members[0]["a2a"]["render"],
                        "clip_ids": [c["id"] for c in members]})
        plain = {}
        for o in (o for o in v["overlaps"] if o["lane"] == lane):
            if o["chroma_xfade"]:
                inpaint.append({"lane": lane, "key": f"lane{lane}:ov:{o['key']}", "render": o["render"],
                                "overlap_keys": [o["key"]], "chroma": True})
            else:
                plain.setdefault(canonical_key(o["render"]), []).append(o)
        for n, members in enumerate(plain.values()):
            inpaint.append({"lane": lane, "key": f"lane{lane}:inpaint:{n}", "render": members[0]["render"],
                            "overlap_keys": [o["key"] for o in members], "chroma": False})
    return {"a2a": a2a, "inpaint": inpaint, "steps_total": sum(g["render"]["steps"] for g in a2a + inpaint)}
