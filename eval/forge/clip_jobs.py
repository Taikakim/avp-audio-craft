"""Per-clip A2A and single-overlap inpaint preview jobs (spec §6.7, §6.8), and clip outpaint."""
# Last edited: WINTERMUTE 2026-10-14 -- outpaint job (extend a clip before/after, windowed inpaint)
import time

import numpy as np
import torch

from . import passes, progress
from .chroma import chroma_384
from .contract import FPS, HOP, SR, ForgeError, check_cap, latent_frames
from .envelope import sample_envelope, validate_envelope
from .lanes import place_lanes, place_single
from .overlap import chroma_target, region_frames
from .render_settings import _num, chain_to_request, parse_chain, parse_render, to_request

_LANES = [{"index": i, "muted": False, "solo": False, "gain": 1.0} for i in range(4)]


def _seed(srv, render):
    return int(render["seed"]) if render["seed"] >= 0 else int(srv.resolve_seed(-1))


def _save(srv, jd, z, n_samples):
    wav, zp = jd / "out_00.wav", jd / "out_00.z0.npy"
    srv.save_audio(wav, passes.decode_latent(srv, z, n_samples), SR, normalize=True)
    np.save(zp, z.squeeze(0).to(torch.float16).numpy())
    return wav, zp


def latent_similarity(a, b):
    """Mean over frames of the cosine between two (1, C, T) latents: 1.0 is the same latent, about 0 is
    unrelated. Logged for every a2a_clip so "did the render pick the file up" has a number: with LatCH on,
    strong guidance can overpower a lightly noised source and the result then no longer resembles it."""
    n = min(a.shape[-1], b.shape[-1])
    c = torch.nn.functional.cosine_similarity(a[..., :n].float(), b[..., :n].float(), dim=1)
    import math; m = float(c.mean()); return 0.0 if math.isnan(m) else m


def validate_a2a_clip(payload, heads):
    if not isinstance(payload, dict) or not isinstance(payload.get("audio"), dict):
        raise ForgeError(400, "a2a_clip needs an audio AudioRef object")
    env = payload.get("envelope")
    chain = parse_chain(payload.get("chain"))
    chain_to_request(chain, heads)
    ckpt = payload.get("ckpt_path")
    if ckpt is not None and not isinstance(ckpt, str):
        raise ForgeError(400, "ckpt_path must be a string or null")
    return {"audio": payload["audio"], "render": parse_render(payload.get("render")),
            "envelope": None if env is None else validate_envelope(env),
            "noise_level": _num(payload.get("noise_level", 0.4), 0, 1, "noise_level"),
            "chain": chain, "ckpt_path": ckpt or None}


def run_a2a_clip(srv, svc, job_id, payload):
    v = validate_a2a_clip(payload, srv.HEADS)
    seed = _seed(srv, v["render"])
    progress.begin(job_id, "a2a_clip", v["render"]["steps"])
    try:
        t0, warnings = time.time(), []
        audio = svc.load_audio(svc.resolve_audio(v["audio"]))
        duration = check_cap(audio.shape[1] / SR, "a2a_clip")
        T = latent_frames(duration)
        buf = np.zeros((2, T * HOP), dtype=np.float32)
        buf[:, :audio.shape[1]] = audio
        z = svc.encode_cached(buf)[..., :T].float()
        depth = (sample_envelope(v["envelope"], T) if v["envelope"] is not None
                 else np.full(T, v["noise_level"], dtype=np.float32))
        req = {**to_request(v["render"], seed), **chain_to_request(v["chain"], srv.HEADS)}
        if v["ckpt_path"] and not req.get("dora"):
            req["ckpt_path"] = v["ckpt_path"]
        out_id, jd = srv.new_job("forgea2a")
        z_new = passes.run_hold_pass(srv, z, depth, req, warnings, label="a2a_clip")
        wav, zp = _save(srv, jd, z_new, audio.shape[1])
        sim = latent_similarity(z, z_new)
        latch = req.get("latch") or []
        srv.log(f"[forge] a2a_clip: result vs source latent cosine {sim:.3f} "
                f"(noise {float(depth.max()) if depth.size else 0.0:.2f}, {len(latch)} LatCH slot(s)"
                + (f", rho {req.get('rho'):g} mu {req.get('mu'):g}" if latch else "") + ")")
        meta = {"op": "a2a_clip", "latents": [str(zp)], "depth_max": float(depth.max()) if depth.size else 0.0,
                "duration_sec": round(duration, 3), "source_similarity": round(sim, 4)}
        return srv.build_response(out_id, jd, [wav], seed, t0, {}, warnings, meta, payload, False)
    finally:
        progress.end()


def _side(obj, what):
    if not isinstance(obj, dict) or not isinstance(obj.get("audio"), dict):
        raise ForgeError(400, f"inpaint.{what} needs an audio AudioRef object")
    return {"audio": obj["audio"], "start_sec": _num(obj.get("start_sec"), 0, 1e5, f"{what}.start_sec"),
            "offset_sec": _num(obj.get("offset_sec", 0.0), 0, 1e5, f"{what}.offset_sec"),
            "dur_sec": _num(obj.get("dur_sec"), 1e-3, 1e5, f"{what}.dur_sec")}


def validate_inpaint(payload):
    if not isinstance(payload, dict):
        raise ForgeError(400, "inpaint payload must be an object")
    region = payload.get("region") or {}
    rs = _num(region.get("start_sec"), 0, 1e5, "region.start_sec")
    re_ = _num(region.get("end_sec"), 0, 1e5, "region.end_sec")
    if not rs < re_:
        raise ForgeError(400, "region start_sec < end_sec required")
    pad = _num(payload.get("pad_sec", 8.0), 0, 60, "pad_sec")
    span_start, span_end = max(0.0, rs - pad), re_ + pad
    check_cap(span_end - span_start, "inpaint")
    chroma = payload.get("chroma_xfade", True)
    if not isinstance(chroma, bool):
        raise ForgeError(400, "chroma_xfade must be true or false")
    return {"a": _side(payload.get("a"), "a"), "b": _side(payload.get("b"), "b"),
            "region": (rs, re_), "curve": validate_envelope(payload.get("curve")), "chroma_xfade": chroma,
            "render": parse_render(payload.get("render")), "span_start": span_start, "span_end": span_end}


def _shifted(side, cid, s0):
    start, offset, dur = side["start_sec"] - s0, side["offset_sec"], side["dur_sec"]
    if start < 0:
        offset, dur, start = offset - start, dur + start, 0.0
    return {"id": cid, "lane": 0, "start_sec": start, "offset_sec": offset, "dur_sec": max(dur, 1e-3), "loop": False}


def run_inpaint_preview(srv, svc, job_id, payload):
    v = validate_inpaint(payload)
    seed = _seed(srv, v["render"])
    progress.begin(job_id, "inpaint", v["render"]["steps"])
    try:
        t0, warnings = time.time(), []
        s0 = v["span_start"]
        duration = v["span_end"] - s0
        T = latent_frames(duration)
        n = T * HOP
        clips = [_shifted(v["a"], "a", s0), _shifted(v["b"], "b", s0)]
        audio = {"a": svc.load_audio(svc.resolve_audio(v["a"]["audio"])),
                 "b": svc.load_audio(svc.resolve_audio(v["b"]["audio"]))}
        rs, re_ = v["region"][0] - s0, v["region"][1] - s0
        ov = {"lane": 0, "start_sec": rs, "end_sec": re_, "a_id": "a", "b_id": "b", "curve": v["curve"]}
        buf = place_lanes(clips, _LANES, [ov], n, SR, lambda c: audio[c["id"]])[0]
        if buf is None:
            raise ForgeError(400, "both clips fall outside the inpaint span")
        z = svc.encode_cached(buf)[..., :T].float()
        target = None
        if v["chroma_xfade"]:
            c_a = chroma_384(place_single(clips[0], n, SR, audio["a"]), SR, T)
            c_b = chroma_384(place_single(clips[1], n, SR, audio["b"]), SR, T)
            f0, f1 = region_frames(rs, re_, FPS, T)
            target = chroma_target(c_a, c_b, f0, f1, v["curve"])
        out_id, jd = srv.new_job("forgeinpaint")
        z_new = passes.run_inpaint_pass(srv, z, [(rs, re_)], to_request(v["render"], seed), warnings,
                                        chroma_target=target, label="inpaint")
        wav, zp = _save(srv, jd, z_new, int(round(duration * SR)))
        meta = {"op": "inpaint", "latents": [str(zp)], "span_start_sec": round(s0, 4),
                "span_end_sec": round(v["span_end"], 4),
                # The client's history/preview player needs a length; without it the entry is 0 s
                # and the preview never plays (review 2026-10-01).
                "duration_sec": round(duration, 3)}
        return srv.build_response(out_id, jd, [wav], seed, t0, {}, warnings, meta, payload, False)
    finally:
        progress.end()


# ---------------------------------------------------------------------------------------- outpaint
# Extend a clip before its start and/or after its end. Each pass is an ordinary inpaint render
# (passes.run_inpaint_pass, so the clip's prompt, schedule, sampler, adapter and its lane's LatCH
# chain all apply): CONTEXT seconds of the clip's own audio next to an empty region, the region
# masked. One render may not exceed the CAP, so a long extension is a chain of windows, each using
# the audio the previous one produced as its context.
OUTPAINT_MAX_SEC = 600.0
OUTPAINT_XFADE_SEC = 0.1


def validate_outpaint(payload, heads):
    if not isinstance(payload, dict) or not isinstance(payload.get("audio"), dict):
        raise ForgeError(400, "outpaint needs an audio AudioRef object")
    pre = _num(payload.get("pre_sec", 0.0), 0, OUTPAINT_MAX_SEC, "pre_sec")
    post = _num(payload.get("post_sec", 0.0), 0, OUTPAINT_MAX_SEC, "post_sec")
    if pre <= 0 and post <= 0:
        raise ForgeError(400, "outpaint needs pre_sec or post_sec above 0")
    ctx = _num(payload.get("context_sec", 30.0), 2.0, 90.0, "context_sec")
    chain = parse_chain(payload.get("chain"))
    chain_to_request(chain, heads)
    ckpt = payload.get("ckpt_path")
    if ckpt is not None and not isinstance(ckpt, str):
        raise ForgeError(400, "ckpt_path must be a string or null")
    return {"audio": payload["audio"],
            "offset_sec": _num(payload.get("offset_sec", 0.0), 0, 1e5, "offset_sec"),
            "dur_sec": None if payload.get("dur_sec") is None else _num(payload.get("dur_sec"), 1e-3, 1e5, "dur_sec"),
            "pre_sec": pre, "post_sec": post, "context_sec": ctx,
            "render": parse_render(payload.get("render")), "chain": chain, "ckpt_path": ckpt or None}


def outpaint_windows(clip_sec, pre, post, context, cap):
    """[(side, context_sec, new_sec)] in render order: the end first, then the start. Each window is
    context + new <= cap, and the context never exceeds the audio that exists by then."""
    out, have = [], clip_sec
    for side, total in (("post", post), ("pre", pre)):
        left = total
        while left > 1e-6:
            ctx = min(context, have)
            new = min(left, cap - ctx)
            out.append((side, ctx, new))
            have += new
            left -= new
    return out


def run_outpaint(srv, svc, job_id, payload):
    v = validate_outpaint(payload, srv.HEADS)
    seed = _seed(srv, v["render"])
    from .contract import CAP_SEC
    audio = svc.load_audio(svc.resolve_audio(v["audio"]))
    a0 = int(round(v["offset_sec"] * SR))
    a1 = audio.shape[1] if v["dur_sec"] is None else min(audio.shape[1], a0 + int(round(v["dur_sec"] * SR)))
    cur = np.ascontiguousarray(audio[:, a0:a1], dtype=np.float32)
    if cur.shape[1] < SR:
        raise ForgeError(400, "outpaint needs at least 1 s of clip audio")
    wins = outpaint_windows(cur.shape[1] / SR, v["pre_sec"], v["post_sec"], v["context_sec"], CAP_SEC)
    steps = int(v["render"]["steps"])
    progress.begin(job_id, "outpaint", steps * len(wins),
                   stage_labels=[f"{s} {n:.0f}s" for s, _, n in wins])
    try:
        t0, warnings = time.time(), []
        req0 = {**to_request(v["render"], seed), **chain_to_request(v["chain"], srv.HEADS)}
        if v["ckpt_path"] and not req0.get("dora"):
            req0["ckpt_path"] = v["ckpt_path"]
        out_id, jd = srv.new_job("forgeoutpaint")
        xf = int(OUTPAINT_XFADE_SEC * SR)
        latents = []
        for k, (side, ctx_sec, new_sec) in enumerate(wins):
            progress.stage(k, f"{side} {new_sec:.0f}s")
            nc, nn = int(round(ctx_sec * SR)), int(round(new_sec * SR))
            win = np.zeros((2, nc + nn), np.float32)
            if side == "post":
                win[:, :nc] = cur[:, cur.shape[1] - nc:]
                region = (ctx_sec, ctx_sec + new_sec)
            else:
                win[:, nn:] = cur[:, :nc]
                region = (0.0, new_sec)
            T = latent_frames((nc + nn) / SR)
            buf = np.zeros((2, T * HOP), np.float32)
            buf[:, :win.shape[1]] = win
            z = svc.encode_cached(buf)[..., :T].float()
            req = {**req0, "seed": seed + k}
            z_new = passes.run_inpaint_pass(srv, z, [region], req, warnings, label=f"outpaint {k + 1}/{len(wins)}")
            zp = jd / f"win_{k:02d}.z0.npy"
            np.save(zp, z_new.squeeze(0).to(torch.float16).numpy())
            latents.append(str(zp))
            dec = passes.decode_latent(srv, z_new, nc + nn).numpy()
            # The clip's own samples stay exact; only a short crossfade at the join hands over to the
            # decoded window, which is continuous from its context into the new audio.
            r = np.linspace(0.0, 1.0, min(xf, nc), dtype=np.float32)
            if side == "post":
                if r.size:
                    cur[:, cur.shape[1] - r.size:] = (cur[:, cur.shape[1] - r.size:] * (1 - r)
                                                      + dec[:, nc - r.size:nc] * r)
                cur = np.concatenate([cur, dec[:, nc:]], axis=1)
            else:
                if r.size:
                    cur[:, :r.size] = cur[:, :r.size] * r + dec[:, nn:nn + r.size] * (1 - r)
                cur = np.concatenate([dec[:, :nn], cur], axis=1)
        if not np.isfinite(cur).all():
            raise ForgeError(500, "outpaint produced non-finite audio")
        wav = jd / "out_00.wav"
        srv.save_audio(wav, torch.from_numpy(np.clip(cur, -1.0, 1.0)), SR, normalize=False)
        meta = {"op": "outpaint", "latents": latents, "pre_sec": round(v["pre_sec"], 4),
                "post_sec": round(v["post_sec"], 4), "windows": len(wins),
                "duration_sec": round(cur.shape[1] / SR, 3)}
        return srv.build_response(out_id, jd, [wav], seed, t0, {}, warnings, meta, payload, False)
    finally:
        progress.end()
