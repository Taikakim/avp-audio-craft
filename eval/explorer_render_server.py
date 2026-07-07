"""explorer_render_server.py — resident SA3 render server for the latent-explorer GUI.

FastAPI on :8056 (SAO/.venv). Holds medium-base resident on the GPU; endpoints
/info /status /audio /generate /a2a_track /a2a_mix /decode. All render logic is
lifted from the proven eval scripts (imported, not re-derived):
  - chroma_morph_transitions.py: load/tempo_of/bungee_stretch/downbeat_near/
    fine_align_shift/encode + the sinesweep release-callback, seam-inpaint,
    pure-basis splice, chroma-morph target machinery
  - a2a_fulltrack.py: sample_size budgeting, >378s two-window crossfade plan
  - density_control_eval.py: FiLM adapter install + ControlContext pattern

Launch:
  cd /home/kim/Projects/SAO && FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE \
    PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2 \
    .venv/bin/python eval/explorer_render_server.py --port 8056
"""
import os

os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import argparse
import contextlib
import gc
import json
import math
import random
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from collections import deque
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.concurrency import run_in_threadpool

sys.path.insert(0, "/home/kim/Projects/SAO/eval")
import chroma_morph_transitions as cmt  # noqa: E402  (inserts control + mir-same-chroma paths)
import a2a_fulltrack as a2a_mod  # noqa: E402

from sa3_control.audio_io import save_audio  # noqa: E402  (boot check: must resolve)
from sa3_control.adapters import ControlContext, use_control_context  # noqa: E402
from sa3_control.inject import install_adapters  # noqa: E402
from sa3_control.conditioner import ScalarAttributeEncoder  # noqa: E402
from sa3_control.generate import load_adapter_state  # noqa: E402
from harmonic.same_chroma import compute_same_chroma  # noqa: E402
from stable_audio_3 import StableAudioModel  # noqa: E402
from stable_audio_3.inference.longform import slerp  # noqa: E402
from stable_audio_3.models.latch import load_latch_from_checkpoint  # noqa: E402
from stable_audio_3.models import transformer as _sa3_tf  # noqa: E402

# ---------------------------------------------------------------- constants
FPS = cmt.FPS                      # 44100 / 4096 ≈ 10.7666 latent frames/sec
MAX_DURATION_SEC = 378.0
MEDIUM_HEAD_DIR = Path("/home/kim/Projects/SAO/stable-audio-3/latch_weights_sa3_medium")

DORA_REGISTRY = {
    "none": None,
    "hof": "/run/media/kim/Mantu1/sa3_lora_runs/sa3-goa-dora-47s-b4-cont/x20b3ygb/checkpoints/epoch=3-step=5400.ckpt",
    "newstack": "/run/media/kim/Mantu1/sa3_lora_runs/dora16_goa_newstack_8ep/epoch=3-step=5400.ckpt",
    "evr1x": "/run/media/kim/Mantu1/sa3_lora_runs/dora128_everything_8ep_lr1x/epoch=7-step=12216.ckpt",
}
FILM_DEFAULT_CKPT = ("/run/media/kim/Mantu1/sa3_control_runs/"
                     "onset_Fusion_lr1e-4_randomcrop/riffer_final.pt")
FILM_DEFAULT_GAIN = 1.75

# ---------------------------------------------------------------- globals
ARGS = None
OUT_DIR: Path = Path("/home/kim/Projects/sa3_render_out")
MODEL = None
SR = 44100
DS = 4096
HEADS: dict = {}                   # name -> registry entry (metadata only)

LOADED_DORA = "none"               # registry name or ckpt path currently merged
LOADED_STRENGTH = 1.0
FILM_LOADED = None                 # ckpt path of installed FiLM adapter, or None
FILM_STATE = None                  # {"mean","std","enc","dtype"}

GPU_LOCK = threading.Lock()
LOG_RING = deque(maxlen=400)
CURRENT_JOB = None
JOB_LOG_PATH = None

app = FastAPI()


# ---------------------------------------------------------------- utilities
def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    LOG_RING.append(line)
    print(line, flush=True)
    if JOB_LOG_PATH is not None:
        try:
            with open(JOB_LOG_PATH, "a") as f:
                f.write(line + "\n")
        except OSError:
            pass


def _f(req, key, default):
    v = req.get(key)
    return float(default) if v is None else float(v)


def _i(req, key, default):
    v = req.get(key)
    return int(default) if v is None else int(v)


def _b(req, key, default):
    v = req.get(key)
    return bool(default) if v is None else bool(v)


def require_path(p, what):
    if p is None:
        raise ValueError(f"{what}: no path given")
    pp = Path(p)
    if not pp.exists():
        hint = " — is Mantu1 mounted?" if str(pp).startswith("/run/media/") else ""
        raise FileNotFoundError(f"{what} not found: {pp}{hint}")
    return str(pp)


def resolve_seed(seed):
    seed = int(seed)
    if seed == -1:
        seed = random.randint(0, 2**31 - 1)
    return seed


def budget_for(dur_sec):
    # a2a_fulltrack.py:40-41 — generate()'s sample_size default silently clamps
    # long requests to 120s; always pass the real budget.
    return int(math.ceil((dur_sec + 8.0) * SR / DS)) * DS


def check_output_length(y, dur_sec, what):
    if y.shape[-1] < 0.98 * dur_sec * SR:      # fail LOUD, never truncate silently
        raise RuntimeError(f"{what} output {y.shape[-1]/SR:.1f}s << requested {dur_sec:.1f}s")


def make_log_cb(steps, extra=None, every=4):
    counter = {"i": 0}

    def cb(d):
        if extra is not None:
            extra(d)
        i = counter["i"]
        counter["i"] += 1
        if i % every == 0 or i == steps - 1:
            log(f"  step {i + 1}/{steps}  t={float(d['t'][0]):.3f}")

    return cb


def new_job(tag):
    global CURRENT_JOB, JOB_LOG_PATH
    base = time.strftime("%Y%m%d-%H%M%S") + "-" + tag
    job_id, i = base, 1
    while (OUT_DIR / job_id).exists():
        i += 1
        job_id = f"{base}-{i}"
    jd = OUT_DIR / job_id
    jd.mkdir(parents=True)
    CURRENT_JOB = job_id
    JOB_LOG_PATH = jd / "job.log"
    return job_id, jd


def load_audio(path):
    """cmt.load (soundfile, ffmpeg fallback) + force 44.1k stereo."""
    a, sr = cmt.load(path)
    if sr != SR:
        with tempfile.TemporaryDirectory() as td:
            wav = f"{td}/dec.wav"
            subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ar", str(SR),
                            "-ac", "2", wav], check=True)
            a, sr = sf.read(wav, dtype="float32", always_2d=True)
            a = a.T
    if a.shape[0] == 1:
        a = np.repeat(a, 2, axis=0)
    elif a.shape[0] > 2:
        a = a[:2]
    return np.ascontiguousarray(a, dtype=np.float32)


# ---------------------------------------------------------------- LatCH registry
def _num(v, default=None):
    try:
        if isinstance(v, torch.Tensor):
            v = v.item()
        return float(v)
    except (TypeError, ValueError):
        return default


def _head_entry(name, family, path, default_gain):
    info = {"name": name, "family": family, "path": str(path),
            "default_gain": default_gain, "out_channels": None, "loss_type": None,
            "target_kind_default": "constant",
            "slider_min": -80.0, "slider_max": 20.0, "value_default": -30.0}
    try:
        head = load_latch_from_checkpoint(str(path), device="cpu")  # never hardcode arch
        md = dict(getattr(head, "metadata", None) or {})
        info["out_channels"] = int(_num(md.get("out_channels"),
                                        head.out_proj.weight.shape[0]))
        info["loss_type"] = md.get("loss_type")
        info["target_kind_default"] = md.get("target_kind_default", "constant")
        # slider derivation = interface/diffusion_cond.py:690-707
        stats = md.get("feature_stats", {}) or {}
        if md.get("slider_min") is not None and md.get("slider_max") is not None:
            smin, smax = _num(md["slider_min"]), _num(md["slider_max"])
            sval = _num(stats.get("mean"), (smin + smax) / 2.0)
            sval = min(max(sval, smin), smax)
        elif stats and "min" in stats and "max" in stats:
            smin = _num(stats["min"])
            smax = _num(stats["max"]) * 2.0 if _num(stats["max"]) > 0 else 1.0
            sval = _num(stats.get("mean"), (smin + smax) / 2.0)
        else:
            smin, smax, sval = -80.0, 20.0, -30.0
        info.update(slider_min=smin, slider_max=smax, value_default=sval)
        del head
    except Exception as e:                      # unmounted Mantu etc: keep entry, note error
        info["scan_error"] = str(e)
    return info


def scan_latch_heads():
    for p in sorted(MEDIUM_HEAD_DIR.glob("latch_sa3_*_best.pt")):
        name = p.stem[len("latch_sa3_"):-len("_best")]
        HEADS[name] = _head_entry(name, "medium", p, 512.0)
    HEADS["chroma_other"] = _head_entry("chroma_other", "chroma",
                                        cmt.CHROMA_HEAD, cmt.CHROMA_GAIN)
    gc.collect()
    log(f"[boot] latch registry: {len(HEADS)} heads")


# ---------------------------------------------------------------- adapters (A.2)
def _resolve_dora(dora_req, default_name):
    if not dora_req:
        dora_req = {"name": default_name, "strength": 1.0}
    ckpt_path = dora_req.get("ckpt_path")
    name = dora_req.get("name") or default_name
    strength = _f(dora_req, "strength", 1.0)
    if ckpt_path:
        return str(ckpt_path), str(ckpt_path), strength
    if name == "none":
        return "none", None, strength
    if name not in DORA_REGISTRY:
        raise ValueError(f"unknown dora name {name!r} (have {sorted(DORA_REGISTRY)})")
    return name, DORA_REGISTRY[name], strength


def _install_film(ckpt):
    """FiLM adapter install — density_control_eval.py:77-124 lifted."""
    global FILM_STATE, FILM_LOADED
    log(f"[film] install {ckpt}")
    ck = torch.load(ckpt, map_location="cpu", weights_only=False)
    mean, std = ck.get("scalar_norm", [7.219, 1.424])
    n_tokens = min(int(ck["args"].get("n_tokens", 16)), 16)
    control_dim = int(ck["args"].get("control_dim", 768))
    md = next(MODEL.model.model.parameters()).dtype
    wrappers = install_adapters(MODEL, control_dim=control_dim)
    enc = ScalarAttributeEncoder(control_dim=control_dim, n_tokens=n_tokens)
    load_adapter_state(ck["state"], wrappers, enc)
    for w in wrappers:
        w.adapter.to(device=ARGS.device, dtype=md)
    enc.to(device=ARGS.device, dtype=md).eval()
    _sa3_tf.flex_attention_available = False    # density_control_eval.py:39-41
    _sa3_tf.flex_attention_compiled = None
    FILM_STATE = {"mean": float(mean), "std": float(std), "enc": enc, "dtype": md}
    FILM_LOADED = str(ckpt)


def prepare_model(dora_req, film_req, default_dora="none"):
    """DoRA/FiLM state machine. Returns True if the model was rebuilt."""
    global MODEL, LOADED_DORA, LOADED_STRENGTH, FILM_LOADED, FILM_STATE
    key, ckpt, strength = _resolve_dora(dora_req, default_dora)
    film_ckpt = None
    if film_req:
        film_ckpt = require_path(film_req.get("ckpt") or FILM_DEFAULT_CKPT, "FiLM checkpoint")
    # reload-per-change is the proven density_control_eval pattern; a FiLM ckpt
    # swap also forces a rebuild (install_adapters must not stack wrappers)
    rebuild = (MODEL is None or key != LOADED_DORA
               or (film_ckpt is not None and FILM_LOADED not in (None, film_ckpt)))
    if rebuild:
        if ckpt:
            require_path(ckpt, f"DoRA checkpoint {key!r}")
        log(f"[model] rebuild: dora={key}")
        MODEL = None
        FILM_STATE, FILM_LOADED = None, None
        gc.collect()
        torch.cuda.empty_cache()
        MODEL = StableAudioModel.from_pretrained(ARGS.model, device=ARGS.device)
        if ckpt:
            MODEL.load_lora([str(ckpt)])
        LOADED_DORA, LOADED_STRENGTH = key, 1.0
    if ckpt and strength != LOADED_STRENGTH:
        MODEL.set_lora_strength(strength)       # cheap; no reload for strength-only change
        LOADED_STRENGTH = strength
    if film_ckpt and FILM_LOADED != film_ckpt:
        _install_film(film_ckpt)
    return rebuild


def film_context(film_req):
    """Per-call FiLM context (density_control_eval.py:119-123). Null ctx when off."""
    if not film_req:
        return contextlib.nullcontext()
    st = FILM_STATE
    if st is None:
        raise RuntimeError("FiLM requested but adapter not installed")
    value = _f(film_req, "value", 4.0)
    gain = _f(film_req, "gain", FILM_DEFAULT_GAIN)
    s = torch.tensor([(value - st["mean"]) / st["std"]], device=ARGS.device, dtype=st["dtype"])
    ctrl = st["enc"](s)
    cc = torch.cat([ctrl, torch.zeros_like(ctrl)], 0)   # cond + trained-null uncond
    return use_control_context(ControlContext(cc, gain=gain))


# ---------------------------------------------------------------- LatCH configs (A.3.6)
def resolve_latch(latch_list, req, extra_first=None):
    """Build (latch_configs, latch_hparams). Server-side gain normalization:
    rho = mu = first slot's gain, per-slot weight = slot_gain / g0.
    extra_first: optional (config_dict, gain) prepended (a2a_mix chroma slot)."""
    slots = []
    if extra_first is not None:
        slots.append(extra_first)
    for s in latch_list or []:
        head = s.get("head")
        path = s.get("path")
        entry = None
        if path is None:
            if head in (None, "none", ""):
                continue
            entry = HEADS.get(head)
            if entry is None:
                raise ValueError(f"unknown latch head {head!r} (have {sorted(HEADS)})")
            path = entry["path"]
        else:
            for e in HEADS.values():
                if e["path"] == str(path):
                    entry = e
                    break
        require_path(path, f"LatCH head {head or path}")
        default_gain = entry["default_gain"] if entry else 512.0
        gain = _f(s, "gain", default_gain)
        cfg = {"model_path": str(path),
               "kind": s.get("kind") or (entry or {}).get("target_kind_default", "constant"),
               "value": _f(s, "value", (entry or {}).get("value_default", -30.0)),
               "start_pct": _f(s, "start_pct", 0.0),
               "end_pct": _f(s, "end_pct", 0.6)}
        slots.append((cfg, gain))
    if not slots:
        return None, None
    g0 = float(slots[0][1]) or 1.0
    configs = [{**cfg, "weight": float(gain) / g0} for cfg, gain in slots]
    hparams = {"rho": g0, "mu": g0,
               "gamma": _f(req, "gamma", 0.3), "n_iter": _i(req, "n_iter", 4)}
    return configs, hparams


def apply_latch(kw, latch_cfgs, latch_hp):
    if latch_cfgs:
        kw["latch_configs"] = latch_cfgs
        kw["latch_hparams"] = latch_hp
    return kw


# ---------------------------------------------------------------- responses
def build_response(job_id, jd, files, seed, t0, stages, warnings, meta, req, rebuilt):
    meta = dict(meta)
    meta.update({"dora_loaded": LOADED_DORA, "film_loaded": FILM_LOADED,
                 "model_rebuilt": bool(rebuilt), "params_echo": req})
    resp = {"status": "ok", "job_id": job_id,
            "files": [str(f) for f in files],
            "urls": [f"/audio/{job_id}/{Path(f).name}" for f in files],
            "seed": seed,
            "timings": {"total_sec": round(time.time() - t0, 1),
                        "per_stage": {k: round(v, 1) for k, v in stages.items()}},
            "warnings": warnings, "meta": meta}
    (jd / "result.json").write_text(json.dumps(resp, indent=2, default=str))
    return resp


# ================================================================ endpoints
@app.get("/info")
def info():
    return {"ok": True, "model": ARGS.model, "sample_rate": SR, "fps": FPS,
            "max_duration_sec": MAX_DURATION_SEC, "out_dir": str(OUT_DIR),
            "latch_heads": list(HEADS.values()),
            "dora": dict(DORA_REGISTRY),
            "film_default": {"ckpt": FILM_DEFAULT_CKPT, "gain": FILM_DEFAULT_GAIN}}


@app.get("/status")
def status():
    busy = GPU_LOCK.locked()
    return {"ok": True, "busy": busy, "job_id": CURRENT_JOB if busy else None,
            "log_tail": list(LOG_RING)[-20:]}


@app.get("/audio/{job_id}/{filename}")
def audio(job_id: str, filename: str):
    if any(("/" in s or ".." in s) for s in (job_id, filename)):
        return JSONResponse({"error": "bad path"}, status_code=404)
    p = OUT_DIR / job_id / filename
    if not p.is_file():
        return JSONResponse({"error": f"no such file {job_id}/{filename}"}, status_code=404)
    return FileResponse(p, media_type="audio/wav")


async def _run(impl, request: Request):
    try:
        body = await request.body()
        req = json.loads(body or b"{}")
    except Exception as e:
        return JSONResponse({"error": f"bad JSON body: {e}"}, status_code=400)
    try:
        return await run_in_threadpool(impl, req)
    except Exception as e:
        log(f"[error] {e}")
        return JSONResponse({"error": str(e), "traceback": traceback.format_exc()},
                            status_code=500)


@app.post("/generate")
async def generate_ep(request: Request):
    return await _run(_generate_impl, request)


@app.post("/a2a_track")
async def a2a_track_ep(request: Request):
    return await _run(_a2a_track_impl, request)


@app.post("/a2a_mix")
async def a2a_mix_ep(request: Request):
    return await _run(_a2a_mix_impl, request)


@app.post("/decode")
async def decode_ep(request: Request):
    return await _run(_decode_impl, request)


# ---------------------------------------------------------------- /generate
def _generate_impl(req):
    prompt = (req.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("prompt is required")
    duration = _f(req, "duration", 47.0)
    if not (1.0 <= duration <= MAX_DURATION_SEC):
        raise ValueError(f"duration {duration} outside 1..{MAX_DURATION_SEC}")
    steps = _i(req, "steps", 24)
    cfg = _f(req, "cfg_scale", 6.0)
    batch = max(1, _i(req, "batch_size", 1))
    seed = resolve_seed(_i(req, "seed", -1))
    with GPU_LOCK:
        t0 = time.time()
        stages = {}
        job_id, jd = new_job("gen")
        log(f"[gen {job_id}] '{prompt[:60]}' dur={duration:g}s steps={steps}")
        rebuilt = prepare_model(req.get("dora"), req.get("film"))
        stages["prepare"] = time.time() - t0
        latch_cfgs, latch_hp = resolve_latch(req.get("latch"), req)
        # kw-dict lifted from density_control_eval.py:141-155 + schedule extras
        kw = dict(prompt=prompt, duration=duration, steps=steps, cfg_scale=cfg,
                  seed=seed, batch_size=batch,
                  sample_size=budget_for(duration),
                  apg_scale=_f(req, "apg_scale", 1.0),
                  duration_padding_sec=_f(req, "duration_padding_sec", 6.0),
                  callback=make_log_cb(steps))
        if req.get("negative_prompt"):
            kw["negative_prompt"] = req["negative_prompt"]
        if req.get("sampler_type"):
            kw["sampler_type"] = req["sampler_type"]
        apply_latch(kw, latch_cfgs, latch_hp)
        tg = time.time()
        with film_context(req.get("film")):
            out = MODEL.generate(**kw)
        stages["generate"] = time.time() - tg
        check_output_length(out, duration, "generate")
        files = []
        for i in range(out.shape[0]):
            p = jd / f"out_{i:02d}.wav"
            save_audio(p, out[i].float().cpu(), SR, normalize=True)
            files.append(p)
        log(f"[gen {job_id}] done {time.time()-t0:.1f}s")
        return build_response(job_id, jd, files, seed, t0, stages, [],
                              {"op": "generate"}, req, rebuilt)


# ---------------------------------------------------------------- /a2a_track
def _a2a_pass(audio_np, nl, prompt, seed, steps, cfg, latch_cfgs, latch_hp, film_req):
    """a2a_fulltrack.py:34-49 inlined (its signature is too narrow for latch/film)."""
    a = torch.tensor(audio_np)
    dur = audio_np.shape[1] / SR
    kw = dict(prompt=prompt, duration=dur, steps=steps, cfg_scale=cfg, seed=seed,
              batch_size=1, sample_size=budget_for(dur),
              init_audio=(SR, a), init_noise_level=nl,
              callback=make_log_cb(steps))
    apply_latch(kw, latch_cfgs, latch_hp)
    with film_context(film_req):
        out = MODEL.generate(**kw)
    y = out[0].float().cpu().numpy()
    if y.shape[1] < audio_np.shape[1] * 0.98:    # fail LOUD, never pad silence
        raise RuntimeError(f"a2a output {y.shape[1]/SR:.1f}s << requested {dur:.1f}s")
    return y


def _a2a_track_impl(req):
    audio_path = require_path(req.get("audio_path"), "audio_path")
    prompt = (req.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("prompt is required")
    nls = req.get("noise_levels") or [_f(req, "noise_level", 0.4)]
    nls = [float(x) for x in nls]
    steps = _i(req, "steps", 24)
    cfg = _f(req, "cfg_scale", 6.0)
    seed = resolve_seed(_i(req, "seed", -1))
    with GPU_LOCK:
        t0 = time.time()
        stages = {}
        job_id, jd = new_job("a2atrack")
        log(f"[a2a_track {job_id}] {Path(audio_path).name} nls={nls}")
        rebuilt = prepare_model(req.get("dora"), req.get("film"))
        stages["prepare"] = time.time() - t0
        latch_cfgs, latch_hp = resolve_latch(req.get("latch"), req)
        audio = load_audio(audio_path)
        total_sec = audio.shape[1] / SR
        # window plan — a2a_fulltrack.py:72-75 / 106-114 semantics intact
        if total_sec <= a2a_mod.MAX_SEC:
            wins = [(0.0, total_sec)]
        else:
            wins = [(0.0, a2a_mod.MAX_SEC), (a2a_mod.MAX_SEC - a2a_mod.OVERLAP, total_sec)]
        files, warnings = [], []
        if len(wins) > 1:
            warnings.append(f"track {total_sec:.0f}s > {a2a_mod.MAX_SEC:.0f}s: "
                            f"two windows joined by {a2a_mod.OVERLAP:.0f}s crossfade")
        for nl in nls:
            tnl = time.time()
            pieces = []
            for lo, hi in wins:
                chunk = audio[:, int(lo * SR):int(hi * SR)]
                y = _a2a_pass(chunk, nl, prompt, seed, steps, cfg,
                              latch_cfgs, latch_hp, req.get("film"))[:, :chunk.shape[1]]
                pieces.append(y)
            if len(pieces) == 1:
                full = pieces[0]
            else:                               # equal-power cos/sin crossfade
                n = int(a2a_mod.OVERLAP * SR)
                tt = np.linspace(0, np.pi / 2, n, dtype=np.float32)
                fo, fi = np.cos(tt), np.sin(tt)
                head, tail = pieces[0], pieces[1]
                join = head[:, -n:] * fo + tail[:, :n] * fi
                full = np.concatenate([head[:, :-n], join, tail[:, n:]], axis=1)
            p = jd / f"out_nl{nl:.2f}.wav"
            save_audio(p, torch.tensor(full), SR, normalize=True)
            files.append(p)
            stages[f"nl{nl:.2f}"] = time.time() - tnl
            log(f"[a2a_track {job_id}] nl={nl:.2f} done {time.time()-tnl:.1f}s")
        meta = {"op": "a2a_track", "duration_sec": round(total_sec, 1),
                "windows": wins, "noise_levels": nls}
        return build_response(job_id, jd, files, seed, t0, stages, warnings,
                              meta, req, rebuilt)


# ---------------------------------------------------------------- /a2a_mix
def _pad_chroma(c, T):
    return c[:, :T] if c.shape[1] >= T else np.pad(c, ((0, 0), (0, T - c.shape[1])), mode="edge")


def _a2a_mix_impl(req):
    # normative reference: cmt.main() lines 173-479, window indexing generalized
    a_path = require_path(req.get("a_path"), "a_path")
    b_path = require_path(req.get("b_path"), "b_path")
    prompt = (req.get("prompt_region") or "").strip()
    if not prompt:
        raise ValueError("prompt_region is required")
    mode = req.get("mode") or "sinesweep"
    if mode not in ("sinesweep", "refine", "inpaint"):
        raise ValueError(f"unknown mode {mode!r}")
    seg = _f(req, "seg_sec", 75.0)
    snap = _b(req, "snap_to_downbeat", True)
    tempo_match = _b(req, "tempo_match", True)
    tempo_mode = req.get("tempo_mode") or "ramp"
    fine_align = _b(req, "fine_align", True)
    trans_lo = _f(req, "trans_start_sec", 26.0)
    trans_hi = _f(req, "trans_end_sec", 49.0)
    quantize_bars = _b(req, "quantize_bars", True)
    nl = _f(req, "noise_level", 0.42)
    seam_inpaint = _i(req, "seam_inpaint", 0)
    seam_nl = _f(req, "seam_nl", 0.35)
    pure_basis = _b(req, "pure_basis", True)
    chroma_on = _b(req, "chroma_morph", True)
    chroma_gain = _f(req, "chroma_gain", cmt.CHROMA_GAIN)
    guid_end = _f(req, "guidance_end_pct", 0.6)
    whole = req.get("whole_track")
    steps = _i(req, "steps", 24)
    cfg = _f(req, "cfg_scale", 6.0)
    seed = resolve_seed(_i(req, "seed", -1))
    warnings = []

    with GPU_LOCK:
        t0 = time.time()
        stages = {}
        job_id, jd = new_job("a2amix")
        log(f"[a2a_mix {job_id}] {Path(a_path).name} -> {Path(b_path).name} mode={mode}")
        rebuilt = prepare_model(req.get("dora"), req.get("film"),
                                default_dora="evr1x")    # op default per design
        stages["prepare"] = time.time() - t0

        # 1. load
        ts = time.time()
        A = load_audio(a_path)
        B = load_audio(b_path)
        lenA, lenB = A.shape[1] / SR, B.shape[1] / SR

        # 2. anchor defaults + downbeat snap (cmt.main lines 257-259)
        a_end = req.get("a_end_sec")
        b_start = req.get("b_start_sec")
        a_end = float(a_end) if a_end is not None else 0.62 * lenA
        b_start = float(b_start) if b_start is not None else 0.40 * lenB
        a_end = min(max(a_end, 0.0), lenA)
        b_start = min(max(b_start, 0.0), lenB)
        if snap:
            a_end = cmt.downbeat_near(A, SR, a_end)
            b_start = cmt.downbeat_near(B, SR, b_start)

        # 3. tempo (cmt.main 249-255)
        ta = cmt.tempo_of(A, SR, around_sec=a_end)
        if tempo_match:
            tb = cmt.tempo_of(B, SR, around_sec=b_start)
            speed = ta / tb                     # playback speed multiplies tempo
            if not (0.85 <= speed <= 1.18):
                warnings.append(f"tempo match ratio {speed:.3f} outside sane band "
                                f"0.85-1.18 — check tempo folds")
        else:
            tb, speed = None, 1.0
        bar_sec = 4 * 60.0 / ta
        log(f"  tempo A={ta:.1f} B={tb if tb else float('nan'):.1f} speed={speed:.4f}")
        stages["analysis"] = time.time() - ts

        # 4-6. window quantize (cmt.main 267-273) + seg floor (line 216)
        W_req_sec = max(trans_hi - trans_lo, 1.0 / FPS)
        if quantize_bars:
            bars = max(1, round(W_req_sec / bar_sec))
            W = int(round(bars * bar_sec * FPS))
            residual = W / FPS - bars * bar_sec  # seconds, |r| < 1 frame
        else:
            bars = None
            W = max(1, int(round(W_req_sec * FPS)))
            residual = 0.0
        seg = max(seg, 1.6 * W / FPS)
        ws_sec = max(0.0, trans_lo)
        if ws_sec + W / FPS > seg:
            ws_sec = max(0.0, seg - W / FPS)
            warnings.append(f"transition window shifted to start {ws_sec:.1f}s to fit seg")
        ws = int(round(ws_sec * FPS))
        we = ws + W
        ws_sec, we_sec = ws / FPS, we / FPS

        # cut A[a_end-seg : a_end] — fail loud if >10% padding needed
        ts = time.time()
        target_n = int(seg * SR)
        A_seg = A[:, max(0, int((a_end - seg) * SR)):int(a_end * SR)]
        if A_seg.shape[1] < 0.9 * target_n:
            raise RuntimeError(f"A segment only {A_seg.shape[1]/SR:.1f}s of {seg:.1f}s "
                               f"(a_end={a_end:.1f}s too early)")
        if A_seg.shape[1] < target_n:
            pad = np.zeros((A_seg.shape[0], target_n - A_seg.shape[1]), dtype=A_seg.dtype)
            A_seg = np.concatenate([pad, A_seg], axis=1)
            warnings.append(f"A front-padded {pad.shape[1]/SR:.1f}s")

        # cut + bungee-stretch B (cmt.main 272-282; cut on the RAW track, residual
        # shifts the cut so kicks align inside the blend; then stretch the cut)
        cut = b_start + residual
        src = B[:, int(cut * SR):int((cut + seg * 1.5) * SR)]
        if tempo_match and abs(speed - 1.0) > 0.0005:
            if tempo_mode == "ramp" and ws_sec > 0.05:
                # generalized DJ pitch-bend: B's audible entry is the WINDOW (not the
                # segment head as in the script) — matched speed until window start,
                # then the script's ramp (matched -> native over W/FPS) from there.
                # Two bungee calls; the seam at ws sits where slerp weight is 0 (pure A).
                head_src_n = int(ws_sec * speed * SR)
                head, tail = src[:, :head_src_n], src[:, head_src_n:]
                head_s = (cmt.bungee_stretch(head, SR, speed)
                          if head.shape[1] > 0 else head)
                tail_s = cmt.bungee_stretch(tail, SR, speed,
                                            ramp_to=1.0, ramp_out_sec=W / FPS)
                ws_n = int(round(ws_sec * SR))
                if head_s.shape[1] >= ws_n:     # keep the window-adjacent END intact
                    head_s = head_s[:, -ws_n:]
                else:
                    zpad = np.zeros((head_s.shape[0], ws_n - head_s.shape[1]),
                                    dtype=head_s.dtype)
                    head_s = np.concatenate([zpad, head_s], axis=1)
                Bs = np.concatenate([head_s, tail_s], axis=1)
            else:
                ramp_to = 1.0 if tempo_mode == "ramp" else None    # follow = matched
                Bs = cmt.bungee_stretch(src, SR, speed,
                                        ramp_to=ramp_to, ramp_out_sec=W / FPS)
        else:
            Bs = src
        B_seg = Bs[:, :target_n]

        # 5. fine-align (cmt.main 283-292); A tail / B head slices arranged so the
        # xcorr span IS the shared transition window on the composite timeline
        align_shift = 0.0
        if fine_align:
            we_n = int(we_sec * SR)
            ws_n = int(ws_sec * SR)
            align_shift = cmt.fine_align_shift(A_seg[:, :we_n], B_seg[:, ws_n:], SR,
                                               span_sec=W / FPS,
                                               max_shift_sec=bar_sec / 2)
            if abs(align_shift) > 0.004:
                log(f"  [align] B shifted {align_shift*1000:+.0f}ms (onset concurrence)")
                if align_shift < 0:
                    o = int(-align_shift * SR)
                    B_seg = Bs[:, o:o + target_n]
                else:
                    pad = np.zeros((B_seg.shape[0], int(align_shift * SR)), dtype=B_seg.dtype)
                    B_seg = np.concatenate([pad, B_seg], axis=1)[:, :target_n]
            if abs(align_shift) > bar_sec / 4:
                warnings.append(f"large align shift {align_shift*1000:+.0f}ms (> quarter bar)")
        if B_seg.shape[1] < 0.9 * target_n:
            raise RuntimeError(f"B segment only {B_seg.shape[1]/SR:.1f}s of {seg:.1f}s "
                               f"(b_start={b_start:.1f}s too late)")
        if B_seg.shape[1] < target_n:
            pad = np.zeros((B_seg.shape[0], target_n - B_seg.shape[1]), dtype=B_seg.dtype)
            B_seg = np.concatenate([B_seg, pad], axis=1)
            warnings.append(f"B end-padded {pad.shape[1]/SR:.1f}s")
        if abs(residual) > 0.02:
            warnings.append(f"bar-quantize residual {residual*1000:+.0f}ms folded into B cut")
        stages["beatmatch"] = time.time() - ts

        # 7. encode + composite: both sides share the composite timeline; slerp
        # over [ws,we] (generalization of cmt.main 297-299)
        ts = time.time()
        zA = cmt.encode(MODEL, A_seg, SR)
        zB = cmt.encode(MODEL, B_seg, SR)
        Tz = min(zA.shape[-1], zB.shape[-1])
        if we > Tz:
            shift = we - Tz
            ws, we = ws - shift, Tz
            ws_sec, we_sec = ws / FPS, we / FPS
            warnings.append(f"window nudged {shift} frames left to fit latent grid")
        t = torch.linspace(0, 1, W, device=zA.device, dtype=torch.float32).view(1, 1, -1)
        mid = slerp(zA[..., ws:we].float(), zB[..., ws:we].float(), t).to(zA.dtype)
        z = torch.cat([zA[..., :ws], mid, zB[..., we:Tz]], dim=-1)
        dur = Tz / FPS

        # 8. chroma-morph target (cmt.main 302-307) — appended to EVERY pass
        target = None
        if chroma_on:
            require_path(cmt.CHROMA_HEAD, "chroma head")
            cA = compute_same_chroma(A_seg.T, SR).reshape(384, -1)
            cB = compute_same_chroma(B_seg.T, SR).reshape(384, -1)
            cA_r, cB_r = _pad_chroma(cA, Tz), _pad_chroma(cB, Tz)
            ramp = np.linspace(0, 1, W, dtype=np.float32)[None, :]
            morph = cA_r[:, ws:we] * (1 - ramp) + cB_r[:, ws:we] * ramp
            target = np.concatenate([cA_r[:, :ws], morph, cB_r[:, we:Tz]], axis=1)
        extra = (({"model_path": cmt.CHROMA_HEAD, "target_raw": target,
                   "end_pct": guid_end}, chroma_gain)
                 if chroma_on else None)
        latch_cfgs, latch_hp = resolve_latch(req.get("latch"), req, extra_first=extra)

        # decode composite reference once
        pre = MODEL.model.pretransform
        with torch.inference_mode():
            audio_ref = pre.decode(z.to(next(pre.parameters()).dtype))[0]
        stages["encode_composite"] = time.time() - ts

        # 9. mode pass
        ts = time.time()
        film_req = req.get("film")
        kw = dict(prompt=prompt, duration=dur, steps=steps, cfg_scale=cfg,
                  seed=seed, batch_size=1, sample_size=budget_for(dur))
        apply_latch(kw, latch_cfgs, latch_hp)
        if mode == "inpaint":                    # cmt.main 342-345
            kw["inpaint_audio"] = (SR, audio_ref.float())
            kw["inpaint_mask_start_seconds"] = ws_sec
            kw["inpaint_mask_end_seconds"] = we_sec
            kw["callback"] = make_log_cb(steps)
        elif mode == "sinesweep":                # cmt.main 311-315 + 349-364, EXACT
            kw["init_audio"] = (SR, audio_ref.float())
            kw["init_noise_level"] = nl
            depth_shape = torch.zeros(Tz)
            depth_shape[ws:we] = torch.sin(torch.linspace(0, torch.pi, W))
            z_ref = z.float().cpu()
            torch.manual_seed(4242)
            eps_ref = torch.randn_like(z_ref)
            depth = (depth_shape * nl).view(1, 1, -1)

            def cb(d, _z=z_ref, _e=eps_ref, _d=depth):
                x, tt = d["x"], float(d["t"][0])
                n = min(x.shape[-1], _z.shape[-1])
                hold = (_d[..., :n] < tt)        # not yet released
                ref_t = ((1 - tt) * _z[..., :n] + tt * _e[..., :n]).to(x.device, x.dtype)
                xs = x[..., :n]
                x[..., :n].copy_(torch.where(hold.to(x.device), ref_t, xs))

            kw["callback"] = make_log_cb(steps, extra=cb)
        else:                                    # refine: whole composite a2a
            kw["init_audio"] = (SR, audio_ref.float())
            kw["init_noise_level"] = nl
            kw["callback"] = make_log_cb(steps)
        log(f"  [pass] {mode} dur={dur:.1f}s window {ws_sec:.1f}-{we_sec:.1f}s "
            f"({W}f{f' = {bars} bars' if bars else ''})")
        with film_context(film_req):
            y = MODEL.generate(**kw)[0].float().cpu().numpy()
        check_output_length(y, dur, mode)
        stages["main_pass"] = time.time() - ts

        # 10. seam-inpaint strips (sinesweep only; cmt.main 375-393)
        if mode == "sinesweep" and seam_inpaint > 0:
            ts = time.time()
            S = seam_inpaint / FPS
            starts = [max(ws_sec - S / 2, 0), we_sec - S / 2]
            ends = [ws_sec + S / 2, min(we_sec + S / 2, y.shape[1] / SR)]
            log(f"  [pass] seam-inpaint {seam_inpaint}f strips")
            kw3 = dict(prompt=prompt, duration=y.shape[1] / SR, steps=steps,
                       cfg_scale=cfg, seed=seed, batch_size=1,
                       sample_size=budget_for(y.shape[1] / SR),
                       inpaint_audio=(SR, torch.tensor(y)),
                       inpaint_mask_start_seconds=starts,
                       inpaint_mask_end_seconds=ends,
                       callback=make_log_cb(steps))
            apply_latch(kw3, latch_cfgs, latch_hp)
            with film_context(film_req):
                y = MODEL.generate(**kw3)[0].float().cpu().numpy()
            stages["seam_inpaint"] = time.time() - ts

        # out_bridge.wav = pre-splice render, always saved (exploration tool)
        bridge_path = jd / "out_bridge.wav"
        save_audio(bridge_path, torch.tensor(y), SR, normalize=True)

        # 11. pure-basis splice (cmt.main 394-419; offB generalizes to 0 because
        # B_seg shares the composite timeline here)
        if mode == "sinesweep" and pure_basis:
            S = seam_inpaint / FPS if seam_inpaint > 0 else 0.0
            lo_n = int(max(ws_sec - S / 2, 0) * SR)
            hi_n = int(min((we_sec + S / 2) * SR, y.shape[1]))
            f2 = int(0.5 * SR)
            rmp = np.linspace(0, 1, f2, dtype=np.float32)
            out_full = y.copy()
            n0 = min(lo_n, A_seg.shape[1], y.shape[1])
            if n0 > f2:
                out_full[:, :n0 - f2] = A_seg[:, :n0 - f2]
                out_full[:, n0 - f2:n0] = (A_seg[:, n0 - f2:n0] * (1 - rmp)
                                           + y[:, n0 - f2:n0] * rmp)
            m2 = min(y.shape[1], B_seg.shape[1])
            if hi_n + f2 <= m2:
                out_full[:, hi_n:hi_n + f2] = (y[:, hi_n:hi_n + f2] * (1 - rmp)
                                               + B_seg[:, hi_n:hi_n + f2] * rmp)
                out_full[:, hi_n + f2:m2] = B_seg[:, hi_n + f2:m2]
            y = out_full

        # inpaint mode: original-audio splice-back with 1s fades (cmt.main 420-434)
        if mode == "inpaint":
            ref = audio_ref.float().cpu().numpy()
            n = min(y.shape[1], ref.shape[1])
            y, ref = y[:, :n], ref[:, :n]
            lo_n, hi_n = int(ws_sec * SR), min(int(we_sec * SR), n)
            f = int(1.0 * SR)
            outy = ref.copy()
            outy[:, lo_n:hi_n] = y[:, lo_n:hi_n]
            r = np.linspace(0, 1, f, dtype=np.float32)
            if lo_n - f >= 0:
                outy[:, lo_n - f:lo_n] = ref[:, lo_n - f:lo_n] * (1 - r) + y[:, lo_n - f:lo_n] * r
            if hi_n + f <= n:
                outy[:, hi_n:hi_n + f] = y[:, hi_n:hi_n + f] * (1 - r) + ref[:, hi_n:hi_n + f] * r
            y = outy
            # optional seam-smoothing double pass (cmt.main 435-473, eps seed 2424)
            if seam_nl > 0:
                ts = time.time()
                log(f"  [pass] seam-nl {seam_nl:.2f} sine masks")
                seam_w = 512
                Tz2 = int(np.ceil(y.shape[1] / SR * FPS))
                dshape = torch.zeros(Tz2)
                for centre in (int(ws_sec * FPS), int(we_sec * FPS)):
                    lo2 = max(centre - seam_w // 2, 0)
                    hi2 = min(centre + seam_w // 2, Tz2)
                    bump = torch.sin(torch.linspace(0, torch.pi, hi2 - lo2))
                    dshape[lo2:hi2] = torch.maximum(dshape[lo2:hi2], bump)
                pp = next(pre.parameters())
                with torch.inference_mode():
                    z_ref2 = pre.encode(torch.tensor(y, device=pp.device,
                                                     dtype=pp.dtype).unsqueeze(0)).float().cpu()
                torch.manual_seed(2424)
                eps2 = torch.randn_like(z_ref2)
                depth2 = (dshape * seam_nl).view(1, 1, -1)

                def cb2(d, _z=z_ref2, _e=eps2, _d=depth2):
                    x, tt = d["x"], float(d["t"][0])
                    nn = min(x.shape[-1], _z.shape[-1], _d.shape[-1])
                    hold = (_d[..., :nn] < tt)
                    ref_t = ((1 - tt) * _z[..., :nn] + tt * _e[..., :nn]).to(x.device, x.dtype)
                    x[..., :nn].copy_(torch.where(hold.to(x.device), ref_t, x[..., :nn]))

                kw2 = dict(prompt=prompt, duration=y.shape[1] / SR, steps=steps,
                           cfg_scale=cfg, seed=seed, batch_size=1,
                           sample_size=budget_for(y.shape[1] / SR),
                           init_audio=(SR, torch.tensor(y)),
                           init_noise_level=seam_nl,
                           callback=make_log_cb(steps, extra=cb2))
                apply_latch(kw2, latch_cfgs, latch_hp)
                with film_context(film_req):
                    y = MODEL.generate(**kw2)[0].float().cpu().numpy()
                stages["seam_nl"] = time.time() - ts

        # 12. optional whole-track a2a pass over the composite
        if whole:
            ts = time.time()
            wt_nl = _f(whole, "noise_level", 0.4)
            wt_prompt = (whole.get("prompt") or prompt).strip()
            log(f"  [pass] whole-track a2a nl={wt_nl:.2f}")
            dur2 = y.shape[1] / SR
            kw4 = dict(prompt=wt_prompt, duration=dur2, steps=steps, cfg_scale=cfg,
                       seed=seed, batch_size=1, sample_size=budget_for(dur2),
                       init_audio=(SR, torch.tensor(y)), init_noise_level=wt_nl,
                       callback=make_log_cb(steps))
            apply_latch(kw4, latch_cfgs, latch_hp)
            with film_context(film_req):
                y = MODEL.generate(**kw4)[0].float().cpu().numpy()
            check_output_length(y, dur2, "whole_track")
            stages["whole_track"] = time.time() - ts

        mix_path = jd / "out_mix.wav"
        save_audio(mix_path, torch.tensor(y), SR, normalize=True)
        log(f"[a2a_mix {job_id}] done {time.time()-t0:.1f}s")

        meta = {"op": "a2a_mix", "mode": mode,
                "tempo_a": round(ta, 2), "tempo_b": round(tb, 2) if tb else None,
                "speed": round(speed, 4),
                "align_shift_ms": round(align_shift * 1000, 1),
                "window": {"start_sec": round(ws_sec, 2), "end_sec": round(we_sec, 2),
                           "frames": W, "bars": bars},
                "anchors_used": {"a_end_sec": round(a_end, 2),
                                 "b_start_sec": round(b_start, 2)},
                "quantize_residual_sec": round(residual, 4),
                "seg_sec": round(seg, 2), "chroma_morph": chroma_on}
        return build_response(job_id, jd, [mix_path, bridge_path], seed, t0, stages,
                              warnings, meta, req, rebuilt)


# ---------------------------------------------------------------- /decode (P2)
def _decode_impl(req):
    # handler logic per mir/scripts/latent_server_sa3.py::_decode_latent
    latent_dir = Path(req.get("latent_dir") or "/home/kim/Projects/latents_sa3")
    crop_id = req.get("crop_id")
    latent_path = req.get("latent_path")
    sidecar = None
    if latent_path:
        path = require_path(latent_path, "latent_path")
    elif crop_id:
        path = require_path(latent_dir / f"{crop_id}.npy", f"crop {crop_id}")
        sj = latent_dir / f"{crop_id}.json"
        if sj.exists():
            sidecar = json.loads(sj.read_text())
    else:
        raise ValueError("need latent_path or crop_id")
    arr = np.load(path).astype(np.float32)
    if arr.ndim == 3:
        arr = arr[0]
    with GPU_LOCK:
        t0 = time.time()
        job_id, jd = new_job("dec")
        log(f"[decode {job_id}] {Path(path).name} shape={arr.shape}")
        pre = MODEL.model.pretransform
        p = next(pre.parameters())
        z = torch.from_numpy(arr).unsqueeze(0).to(device=p.device, dtype=p.dtype)
        with torch.inference_mode():
            audio = pre.decode(z, chunked=True, chunk_size=128, overlap=32)
        a = audio.squeeze(0).float().cpu()
        if sidecar is not None:
            n_content = int(sum(sidecar.get("padding_mask") or [])) or arr.shape[1]
            samples = n_content * DS
            if 0 < samples < a.shape[1]:
                a = a[:, :samples]
        out = jd / "out_00.wav"
        save_audio(out, a, SR, normalize=True)
        meta = {"op": "decode", "latent_shape": list(arr.shape),
                "duration_sec": round(a.shape[1] / SR, 2)}
        return build_response(job_id, jd, [out], None, t0, {}, [], meta, req, False)


# ---------------------------------------------------------------- boot
def main():
    global ARGS, OUT_DIR, MODEL, SR, DS, LOADED_DORA
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8056)
    ap.add_argument("--out-dir", type=Path, default=Path("/home/kim/Projects/sa3_render_out"))
    ap.add_argument("--model", default="medium-base")
    ap.add_argument("--device", default="cuda")
    ARGS = ap.parse_args()
    OUT_DIR = ARGS.out_dir
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    scan_latch_heads()
    log(f"[boot] loading {ARGS.model} on {ARGS.device} ...")
    MODEL = StableAudioModel.from_pretrained(ARGS.model, device=ARGS.device)
    LOADED_DORA = "none"
    SR = MODEL.model.sample_rate
    DS = MODEL.model.pretransform.downsampling_ratio
    assert abs(SR / DS - FPS) < 1e-6, f"FPS mismatch: {SR}/{DS} != {FPS}"
    log(f"[boot] ready — sr={SR} ds={DS} fps={FPS:.4f} out={OUT_DIR}")
    uvicorn.run(app, host="127.0.0.1", port=ARGS.port)


if __name__ == "__main__":
    main()
