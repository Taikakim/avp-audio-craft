"""MIXDOWN commit: payload validation, pass planning and orchestration (spec §6.9, §8)."""
import time

import numpy as np

try:  # torch is only needed by run_commit; validation/planning stay importable on a CPU-only box
    import torch
except ImportError:  # pragma: no cover
    torch = None

from . import passes, progress
from .chroma import chroma_384
from .contract import CAP_SEC, FPS, HOP, SR, ForgeError, check_cap, latent_frames
from .envelope import validate_envelope
from .holdpass import clip_frame_span, depth_for_spans
from .lanes import place_lanes, place_single
from .mixing import mix_latents, normalise
from .overlap import chroma_target, region_frames
from .render_settings import _num, canonical_key, chain_to_request, parse_chain, parse_render, to_request

STAGES = ["DECODE latent → audio", "BUNGEE stretch / pitch", "ENCODE audio → latent", "LANE CHAINS",
          "A2A RE-NOISE", "INPAINT OVERLAPS", "MIX", "MASTER CHAIN", "DECODE latent → audio"]


# How much of the mix the MASTER CHAIN's LatCH pass re-noises when the request does not say.
MASTER_NOISE_DEFAULT = 0.25


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
    # Two shapes. With `slots` / `hparams` the master LatCH is the SAME chain a lane has -- up to two
    # heads with kind, target, weight and window, plus rho / mu / gamma / iterations -- and runs as a
    # guided re-noise of the mix (`noise` deep), because a target, a weight and a window only mean
    # something inside a sampler. Without them it is the older single-head gradient step
    # (head + gain), kept so a session or client written before this still commits.
    mchain, guided = None, False
    if "slots" in master or "hparams" in master:
        mchain = parse_chain({"latch_on": latch_on, **{k: master[k] for k in ("slots", "hparams") if k in master}})
        guided = bool(chain_to_request(mchain, heads)["latch"])
    elif latch_on and master.get("head") not in heads:
        raise ForgeError(400, f"unknown master head {master.get('head')!r}")
    return {"project_bpm": bpm, "duration_sec": duration, "defaults": defaults, "lanes": lanes, "clips": clips,
            "overlaps": overlaps,
            "mix": {"order": mix["order"], "nodes": nodes,
                    "quad_weights": [_num(w, 0, 1e6, "quad weight") for w in weights]},
            "master": {"latch_on": latch_on, "head": master.get("head"),
                       "gain": _num(master.get("gain", 64), 0, 120, "master.gain"),
                       "norm_on": _bool(master.get("norm_on", True), "master.norm_on"),
                       "chain": mchain, "guided": guided,
                       "noise": _num(master.get("noise", MASTER_NOISE_DEFAULT), 0, 1, "master.noise")},
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
    # The master LatCH pass samples too, with the session defaults' render settings.
    m = v["master"]
    master = ({"key": "master", "render": v["defaults"]}
              if m["latch_on"] and m["guided"] and m["noise"] > 0 else None)
    steps = sum(g["render"]["steps"] for g in a2a + inpaint) + (master["render"]["steps"] if master else 0)
    return {"a2a": a2a, "inpaint": inpaint, "master": master, "steps_total": steps}


def _seed(srv, render):
    return int(render["seed"]) if render["seed"] >= 0 else int(srv.resolve_seed(-1))


def run_commit(srv, svc, job_id, payload):
    v = validate_commit(payload, srv.HEADS)
    plan = plan_passes(v)
    seeds = {g["key"]: _seed(srv, g["render"]) for g in plan["a2a"] + plan["inpaint"] + ([plan["master"]] if plan["master"] else [])}
    flags = [{"label": s, "on": False, "note": "", "seconds": 0.0} for s in STAGES]
    timings, warnings, passes_meta = {}, [], []
    t0 = time.time()
    progress.begin(job_id, "commit", plan["steps_total"], STAGES)

    def enter(i):
        progress.stage(i + 1, STAGES[i])
        return time.time()

    def leave(i, ts, on, note):
        flags[i].update(on=bool(on), note=note, seconds=round(time.time() - ts, 2))
        timings[f"S{i + 1}"] = flags[i]["seconds"]

    try:
        out_id, jd = srv.new_job("forgecommit")
        T = latent_frames(v["duration_sec"])
        n_samples = T * HOP
        clips = {c["id"]: c for c in v["clips"]}
        lanes = v["lanes"]

        ts = enter(0)
        paths = {cid: svc.resolve_audio(c["audio"]) for cid, c in clips.items()}
        crops = [cid for cid, c in clips.items() if c["audio"].get("kind") == "crop"]
        leave(0, ts, crops, f"{len(crops)} crop(s)" if crops else "no latents")

        ts = enter(1)
        audio, stretched = {}, []
        for cid, c in clips.items():
            chain = lanes[c["lane"]]["chain"]
            speed = v["project_bpm"] / c["native_bpm"] if c["native_bpm"] else 1.0
            semis = (chain["semitones"] if chain["bungee_on"] else 0.0) + c["detune_cents"] / 100.0
            path = svc.stretched_path(paths[cid], speed, semis)
            if path != paths[cid]:
                stretched.append(cid)
            audio[cid] = svc.load_audio(path)
        leave(1, ts, stretched, f"{len(stretched)} clip(s)" if stretched else "at tempo")

        ts = enter(2)
        bufs = place_lanes(v["clips"], lanes, v["overlaps"], n_samples, SR, lambda c: audio[c["id"]])
        z = [None if b is None else svc.encode_cached(b)[..., :T].float() for b in bufs]
        used = [i for i in range(4) if z[i] is not None]
        leave(2, ts, used, ", ".join(f"L{i + 1}" for i in used) or "idle")
        if not used:
            raise ForgeError(400, "nothing to commit — every lane is empty or muted")

        ts = enter(3)
        a2a_lanes = sorted({g["lane"] for g in plan["a2a"] if z[g["lane"]] is not None})
        chain_lanes = [i for i in used
                       if any(chain_to_request(lanes[i]["chain"], srv.HEADS)[k] for k in ("latch", "film", "dora"))]
        notes = [f"L{i + 1}" + ("" if i in a2a_lanes else " (idle — no A2A clip)") for i in chain_lanes]
        leave(3, ts, set(chain_lanes) & set(a2a_lanes), ", ".join(notes) or "all bypassed")

        ts = enter(4)
        for g in plan["a2a"]:
            lane = g["lane"]
            if z[lane] is None:
                continue
            spans = []
            for cid in g["clip_ids"]:
                f0, n = clip_frame_span(clips[cid]["start_sec"], clips[cid]["dur_sec"], FPS)
                spans.append((f0, clips[cid]["a2a"]["envelope"], n))
            req = {**to_request(g["render"], seeds[g["key"]]), **chain_to_request(lanes[lane]["chain"], srv.HEADS)}
            tp = time.time()
            z[lane] = passes.run_hold_pass(srv, z[lane], depth_for_spans(spans, T), req, warnings, label=g["key"])
            passes_meta.append({"lane": lane, "kind": "a2a", "key": g["key"], "seed": seeds[g["key"]],
                                "steps": g["render"]["steps"], "seconds": round(time.time() - tp, 2)})
        leave(4, ts, a2a_lanes, " ".join(f"L{i + 1}" for i in a2a_lanes) or "none")

        ts = enter(5)
        ovs = {o["key"]: o for o in v["overlaps"]}
        for g in plan["inpaint"]:
            lane = g["lane"]
            if z[lane] is None:
                continue
            group = [ovs[k] for k in g["overlap_keys"]]
            target = None
            if g["chroma"]:
                o = group[0]
                c_a = chroma_384(place_single(clips[o["a_id"]], n_samples, SR, audio[o["a_id"]]), SR, T)
                c_b = chroma_384(place_single(clips[o["b_id"]], n_samples, SR, audio[o["b_id"]]), SR, T)
                f0, f1 = region_frames(o["start_sec"], o["end_sec"], FPS, T)
                target = chroma_target(c_a, c_b, f0, f1, o["curve"])
            tp = time.time()
            z[lane] = passes.run_inpaint_pass(srv, z[lane], [(o["start_sec"], o["end_sec"]) for o in group],
                                              to_request(g["render"], seeds[g["key"]]), warnings,
                                              chroma_target=target, label=g["key"])
            passes_meta.append({"lane": lane, "kind": "inpaint", "key": g["key"], "seed": seeds[g["key"]],
                                "steps": g["render"]["steps"], "seconds": round(time.time() - tp, 2)})
        n_ov = len(v["overlaps"])
        leave(5, ts, plan["inpaint"], f"{n_ov} region{'s' if n_ov != 1 else ''}" if n_ov else "none")

        ts = enter(6)
        mixed, weff = mix_latents(z, v["mix"])
        note = "lerp" if v["mix"]["order"] == "quad" else "·".join(v["mix"]["nodes"][k]["interp"][0] for k in ("M1", "M2", "MX"))
        leave(6, ts, len(used) > 1, note)

        ts = enter(7)
        m = v["master"]
        if m["norm_on"]:
            mixed = normalise(mixed, z, weff)
        latched = False
        if m["latch_on"] and m["chain"] is None:                       # the older single-head gradient step
            mixed = passes.steer_master(srv, mixed, m["head"], m["gain"])
            latched = True
        elif plan["master"] is not None:                               # the lane's own chain, on the mix
            req = {**to_request(plan["master"]["render"], seeds["master"]), **chain_to_request(m["chain"], srv.HEADS)}
            tp = time.time()
            mixed = passes.run_hold_pass(srv, mixed, np.full(T, m["noise"], dtype=np.float32), req, warnings,
                                         label="master")
            passes_meta.append({"lane": None, "kind": "master", "key": "master", "seed": seeds["master"],
                                "steps": plan["master"]["render"]["steps"], "seconds": round(time.time() - tp, 2)})
            latched = True
        leave(7, ts, latched or m["norm_on"],
              " + ".join(x for x in ("latch" if latched else "", "norm" if m["norm_on"] else "") if x) or "bypassed")

        ts = enter(8)
        n_out = int(round(v["duration_sec"] * SR))
        mix_wav, mix_z = jd / "mix.wav", jd / "mix.z0.npy"
        srv.save_audio(mix_wav, passes.decode_latent(srv, mixed, n_out), SR, normalize=True)
        np.save(mix_z, mixed.squeeze(0).to(torch.float16).numpy())
        files, lanes_meta = [mix_wav], []
        for i in range(4):
            if z[i] is None:
                lanes_meta.append({"index": i, "used": False, "z0_path": None, "wav_path": None})
                continue
            zp = jd / f"lane{i}.z0.npy"
            np.save(zp, z[i].squeeze(0).to(torch.float16).numpy())
            wp = None
            if v["decode_lanes"]:
                wp = jd / f"lane{i}.wav"
                srv.save_audio(wp, passes.decode_latent(srv, z[i], n_out), SR, normalize=True)
                files.append(wp)
            lanes_meta.append({"index": i, "used": True, "z0_path": str(zp), "wav_path": str(wp) if wp else None})
        leave(8, ts, True, f"{v['duration_sec']:g}s")

        meta = {"op": "commit", "latents": [str(mix_z)], "stages": flags, "lanes": lanes_meta,
                "passes": passes_meta, "resolved_seeds": seeds, "mix_weights": weff}
        return srv.build_response(out_id, jd, files, None, t0, timings, warnings, meta, payload, False)
    finally:
        progress.end()
