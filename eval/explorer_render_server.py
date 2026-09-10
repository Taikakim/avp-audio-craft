"""explorer_render_server.py — resident SA3 render server for the latent-explorer GUI.

FastAPI on :8056 (SAO/.venv). Holds medium-base resident on the GPU; endpoints
/info /status /audio /generate /a2a_track /a2a_mix /longform /decode /bend. All render logic is
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
import configparser
import contextlib
import gc
import io
import json
import math
import random
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import wave
from collections import deque
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.concurrency import run_in_threadpool

sys.path.insert(0, "/home/kim/Projects/SAO/eval")
import chroma_morph_transitions as cmt  # noqa: E402  (inserts control + mir-same-chroma paths)
import a2a_fulltrack as a2a_mod  # noqa: E402

from sa3_control.audio_io import save_audio  # noqa: E402  (boot check: must resolve)
from sa3_control.adapters import ControlContext, use_control_context  # noqa: E402
from sa3_control.inject import install_adapters  # noqa: E402
from sa3_control.conditioner import ScalarAttributeEncoder  # noqa: E402
from sa3_control.generate import load_adapter_state  # noqa: E402
from sa3_control.steered_longform import _parse_prompt_arc  # noqa: E402  (arc grammar '0:A|45:B')
from harmonic.same_chroma import compute_same_chroma  # noqa: E402
sys.path.insert(0, "/home/kim/Projects/SAO/stable-audio-3/scripts")
from weight_mutations import Condition, apply_condition  # noqa: E402
from stable_audio_3 import StableAudioModel  # noqa: E402
from stable_audio_3.models.latch import load_latch_from_checkpoint  # noqa: E402
from stable_audio_3.inference.longform import (  # noqa: E402
    InpaintContinuationGenerator, LongFormRenderer, PromptSchedule, slerp)
from stable_audio_3.inference.sampling import build_schedule  # noqa: E402
from stable_audio_3.inference.distribution_shift import FluxDistributionShift  # noqa: E402
from stable_audio_3.models import transformer as _sa3_tf  # noqa: E402

# ---------------------------------------------------------------- constants
FPS = cmt.FPS                      # 44100 / 4096 ≈ 10.7666 latent frames/sec
MAX_DURATION_SEC = 378.0
MEDIUM_HEAD_DIR = Path("/home/kim/Projects/SAO/stable-audio-3/latch_weights_sa3_medium")
import head_meta  # noqa: E402  (eval/ is already on sys.path)
import presets  # noqa: E402
import continuation  # noqa: E402
_HEAD_OVERRIDES = head_meta.load_overrides()

# ---------------------------------------------------------------- latent player (ported from :7892)
# The standalone torch player (mir/scripts/latent_server_sa3.py) called
# AutoencoderModel.from_pretrained("same-l") -- a SECOND resident copy (7.12 GB)
# of the very weights this server already holds as MODEL.model.pretransform.
# Its GET endpoints live here now and reuse that instance. Config, never a
# hardcoded drive path: SA3_PLAYER_INI overrides the co-located ini.
PLAYER_INI_PATH = Path(os.environ.get("SA3_PLAYER_INI")
                       or Path(__file__).with_name("latent_player.ini"))


def load_player_cfg(path=None) -> dict:
    """Read [player] from the ini. Missing file -> in-code defaults (no crash at boot)."""
    cfg = {"latent_dir": "", "chunk_size": 128, "overlap": 32}
    parser = configparser.ConfigParser()
    try:
        if parser.read(str(path or PLAYER_INI_PATH)) and parser.has_section("player"):
            sec = parser["player"]
            cfg["latent_dir"] = sec.get("latent_dir", cfg["latent_dir"])
            cfg["chunk_size"] = sec.getint("chunk_size", cfg["chunk_size"])
            cfg["overlap"] = sec.getint("overlap", cfg["overlap"])
    except (OSError, configparser.Error, ValueError):
        pass
    return cfg


PLAYER_CFG = load_player_cfg()
STEER_HEADS: dict = {}             # feature -> loaded LatCH head (lazy, GPU-resident)

# The eval drive is removable; udisks mounts it as Mantu OR Mantu1 depending on
# mount order. Hardcoding either breaks DoRA loading when it flips (C bug 2026-07-13).
# Resolve to whichever mount actually holds sa3_lora_runs.
def _mantu_root():
    for d in ("/run/media/kim/Mantu", "/run/media/kim/Mantu1"):
        if Path(d, "sa3_lora_runs").is_dir():
            return d
    return "/run/media/kim/Mantu"
_MANTU = _mantu_root()

import model_db                                   # noqa: E402
import model_roots                                # noqa: E402

_ROOTS_CFG = model_roots.load_config()
_LIMITS = model_roots.limits(_ROOTS_CFG)
import adapter_slots  # noqa: E402
SLOTS = adapter_slots.SlotTable(
    max_slots=int(_LIMITS.get('max_resident_adapters', 4)),
    vram_floor_gb=float(_LIMITS.get('vram_floor_gb', 6.0)))
ACTIVE_SLOT = None          # index into SLOTS.slots, or None = base model


def _root_by_id(rid):
    for r in model_roots.resolve_roots(_ROOTS_CFG):
        if r.id == rid:
            return r
    return None


def _default_scan_root():
    """Backwards compat: the pinned root the picker used before multi-root."""
    r = _root_by_id("local_dora")
    return Path(r.path) if r and r.path else Path(f"{_MANTU}/sa3_lora_runs")

DORA_REGISTRY = {
    "none": None,
    "hof": f"{_MANTU}/sa3_lora_runs/sa3-goa-dora-47s-b4-cont/x20b3ygb/checkpoints/epoch=3-step=5400.ckpt",
    "newstack": f"{_MANTU}/sa3_lora_runs/dora16_goa_newstack_8ep/epoch=3-step=5400.ckpt",
    "evr1x": f"{_MANTU}/sa3_lora_runs/dora128_everything_8ep_lr1x/epoch=7-step=12216.ckpt",
}
FILM_DEFAULT_CKPT = (f"{_MANTU}/sa3_control_runs/"
                     "onset_Fusion_lr1e-4_randomcrop/riffer_final.pt")
FILM_DEFAULT_GAIN = 1.75

CKPT_SCAN_ROOT = _default_scan_root()      # legacy single-root default (compat)
# Persistent, not /tmp: a reboot used to wipe this and force a full rescan of the
# checkpoint tree off USB spinning disks. Override with SA3_CKPT_JOURNAL.
CKPT_JOURNAL_PATH = Path(os.environ.get(
    "SA3_CKPT_JOURNAL",
    Path(os.environ.get("XDG_CACHE_HOME") or (Path.home() / ".cache"))
    / "sa3-explorer" / "ckpt_journal.json"))
CKPT_JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
CKPT_JOURNAL_LOCK = threading.Lock()

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


def resolve_cfg_interval(req):
    """(lo, hi) tuple in native SIGMA semantics — the DiT gates CFG on
    cfg_interval[0] <= sigma <= cfg_interval[1] (dit.py), NOT on step index.
    Accepts cfg_interval=[lo,hi] or cfg_interval_min/cfg_interval_max."""
    ci = req.get("cfg_interval")
    if ci is not None:
        lo, hi = float(ci[0]), float(ci[1])
    else:
        lo = _f(req, "cfg_interval_min", 0.0)
        hi = _f(req, "cfg_interval_max", 1.0)
    if not (0.0 <= lo <= hi <= 1.0):
        raise ValueError(f"cfg_interval ({lo}, {hi}) must satisfy 0 <= lo <= hi <= 1")
    return (lo, hi)


def resolve_dist_shift(req):
    """GUI `dist_shift: float|"default"|"flux"|null` -> schedule-warp override
    for generate(). A float builds a constant-alpha FluxDistributionShift
    (Self-Flow convention, t_shifted = a*t / (1 + (a-1)*t); a=1 -> linear).
    "flux" -> the stock length-dependent FluxDistributionShift(), exactly as
    breathing_v2_blockbuild.py:88-91 passes it. None/absent/""/"default" ->
    None, which lets generate()/build_schedule fall back to the model's
    sampling_dist_shift (the GUI's 'model default')."""
    v = req.get("dist_shift")
    if v is None or v in ("", "default"):
        return None
    if v == "flux":
        return FluxDistributionShift()
    a = float(v)
    if a <= 0:
        raise ValueError(f"dist_shift must be > 0 (got {a})")
    return FluxDistributionShift(alpha_min=a, alpha_max=a)


def resolve_dora_req(req):
    """Fold the GUI ckpt picker's TOP-LEVEL `ckpt_path` into the dora request
    dict consumed by _resolve_dora (an explicit dora.ckpt_path still wins)."""
    if not req.get("dora") and not req.get("ckpt_path"):
        return None                       # unchanged: no dora block at all
    dora_req = dict(req.get("dora") or {})
    top = req.get("ckpt_path")
    if top:
        dora_req.setdefault("ckpt_path", str(top))
    # `slot` selects one of the RESIDENT adapters instead of naming a checkpoint to
    # load. Absent (the default) => today's path, byte for byte.
    dora_req.setdefault("slot", None)
    return dora_req


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
    """Enriched head description. The slider derivation moved to head_meta.py:
    the old md["slider_min"] / md["feature_stats"] lookup read keys that
    scripts/latch/train_latch.py never writes, so every head silently got the
    same -80/20/-30 range -- right for the dB-valued rms_* family and wrong for
    beat_activation (0.044 +/- 0.066), hpcp, hardness (Kim, 2026-08-24)."""
    try:
        head = load_latch_from_checkpoint(str(path), device="cpu")  # never hardcode arch
        md = dict(getattr(head, "metadata", None) or {})
        md.setdefault("out_channels", int(head.out_proj.weight.shape[0]))
        del head
        info = head_meta.describe(name, family, path, default_gain,
                                  metadata=md, overrides=_HEAD_OVERRIDES)
    except Exception as e:                  # unmounted drive etc: keep the entry
        info = head_meta.describe(name, family, path, default_gain,
                                  metadata={}, overrides=_HEAD_OVERRIDES)
        info["scan_error"] = str(e)
        info["health"] = "unknown"
        info["health_reason"] = f"checkpoint could not be read: {e}"
    return info


def _chroma_head_path():
    """cmt.CHROMA_HEAD is a literal under /run/media/kim/Mantu1
    (chroma_morph_transitions.py:46). The eval drive mounts as Mantu OR Mantu1
    depending on label collision at mount time, so re-root it onto whichever is
    live rather than hardcoding either (no-hardcoded-drive-paths rule)."""
    raw = str(cmt.CHROMA_HEAD)
    if os.path.exists(raw):
        return raw
    for stale in ("/run/media/kim/Mantu1", "/run/media/kim/Mantu"):
        if raw.startswith(stale):
            cand = _MANTU + raw[len(stale):]
            if os.path.exists(cand):
                return cand
    return None


def scan_latch_heads():
    for p in sorted(MEDIUM_HEAD_DIR.glob("latch_sa3_*_best.pt")):
        name = p.stem[len("latch_sa3_"):-len("_best")]
        HEADS[name] = _head_entry(name, "medium", p, 512.0)
    n_medium = len(HEADS)
    # The 17th head. NOT from MEDIUM_HEAD_DIR -- a different family, a different
    # default gain (2048 vs 512), and its own readout. Kept explicit so the UI can
    # say so instead of showing it as a peer of the 16 medium heads.
    cp = _chroma_head_path()
    if cp:
        HEADS["chroma_other"] = _head_entry("chroma_other", "chroma", cp, cmt.CHROMA_GAIN)
    else:
        log(f"[boot] chroma_other SKIPPED: {cmt.CHROMA_HEAD} not found under {_MANTU}")
    gc.collect()
    log(f"[boot] latch registry: {len(HEADS)} heads ({n_medium} medium + "
        f"{len(HEADS) - n_medium} chroma)")


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


LOADED_MUT = None


MUTATE_OPS = ("drift", "shuffle", "blur", "contrast", "tilt", "life")


def resolve_mutate(req):
    """req["mutate"] -> normalized mutation dict or None. Weight-garden ops
    (weight_mutations.py): shuffle is the value-preserving op that proved
    musical (WORKLOG 07-04); the other five (drift/blur/contrast/tilt/life)
    pass through since 07-13 (parity-audit item 4). 'life' also takes an
    optional quantile (alive threshold, default 0.75)."""
    m = req.get("mutate") or {}
    if not m.get("enabled"):
        return None
    op = str(m.get("op", "shuffle"))
    if op not in MUTATE_OPS:
        raise ValueError(f"unknown mutate op {op!r} (have {MUTATE_OPS})")
    out = {"op": op,
           "amount": float(m.get("amount", 0.25)),
           "target": str(m.get("target", "attn")),
           "seed": int(m.get("seed", 1234)),
           "decay_rate": float(m.get("decay_rate", 0.5)),
           "decay_direction": str(m.get("decay_direction", "late"))}
    if op == "life":
        out["quantile"] = float(m.get("quantile", 0.75))
    return out


CURRENT_LORA_INTERVAL = (0.0, 1.0)


def with_lora_interval(kw):
    """Attach per-request LoRA sigma-interval gating (Kim 2026-07-12; native
    sigma semantics, dit.py:466 — e.g. (0.25, 1.0) = adapter OFF for the final
    low-noise detail steps). No-op at the (0,1) default or with no adapter."""
    if SLOTS.slots:
        # TRAP (adapter_slots docstring): dit.py only touches indices PRESENT in
        # lora_configs; an omitted index keeps its last enable state, so "A vs B"
        # silently becomes "A+B". Always emit every resident index.
        kw.setdefault("lora_configs",
                      SLOTS.lora_configs(ACTIVE_SLOT, interval=CURRENT_LORA_INTERVAL))
        return kw
    if LOADED_DORA not in (None, "none") and CURRENT_LORA_INTERVAL != (0.0, 1.0):
        kw.setdefault("lora_configs", [{"lora_index": 0,
                                        "interval": CURRENT_LORA_INTERVAL}])
    return kw


def prepare_model(dora_req, film_req, default_dora="none", mutate_req=None):
    """DoRA/FiLM/mutation state machine. Returns True if the model was rebuilt."""
    global MODEL, LOADED_DORA, LOADED_STRENGTH, FILM_LOADED, FILM_STATE, LOADED_MUT
    global CURRENT_LORA_INTERVAL, ACTIVE_SLOT
    CURRENT_LORA_INTERVAL = (
        _f(dora_req or {}, "interval_min", 0.0),
        _f(dora_req or {}, "interval_max", 1.0))
    mut_key = json.dumps(mutate_req, sort_keys=True) if mutate_req else None
    # SLOT MODE: the resident slot table owns adapter residency, so a "which model"
    # change costs nothing -- no rebuild, no disk read. The single-adapter path
    # below is untouched when `slot` is absent.
    slot = (dora_req or {}).get("slot")
    if SLOTS.slots and slot is not None:
        ACTIVE_SLOT = int(slot)
        key, ckpt, strength = "none", None, _f(dora_req or {}, "strength", 1.0)
    else:
        # NOT slot mode. Every resident slot must be silenced explicitly -- leaving
        # ACTIVE_SLOT at its previous value made a `slot: null` render come back
        # BYTE-IDENTICAL to the last slot render (caught 2026-08-26), i.e. "base
        # model" was quietly still the last adapter. Same failure class as trap 1.
        ACTIVE_SLOT = None
        key, ckpt, strength = _resolve_dora(dora_req, default_dora)
    film_ckpt = None
    if film_req:
        film_ckpt = require_path(film_req.get("ckpt") or FILM_DEFAULT_CKPT, "FiLM checkpoint")
    # reload-per-change is the proven density_control_eval pattern; a FiLM ckpt
    # swap also forces a rebuild (install_adapters must not stack wrappers)
    rebuild = (MODEL is None or key != LOADED_DORA or mut_key != LOADED_MUT
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
        if mutate_req:
            # weight-garden mutation on the frozen base DiT, BEFORE adapter attach
            # (train_lora --glitch order). Reset = rebuild without mutate.
            mop = mutate_req.get("op", "shuffle")
            op_spec = {"op": mop, "amount": mutate_req["amount"]}
            if mop == "life":
                op_spec["quantile"] = mutate_req.get("quantile", 0.75)
            cond = Condition(name=f"ui_{mop}",
                             ops=[op_spec],
                             target=mutate_req["target"],
                             decay_rate=mutate_req["decay_rate"],
                             decay_direction=mutate_req["decay_direction"],
                             mutation_seed=mutate_req["seed"])
            summary = apply_condition(MODEL.dit, cond)
            log(f"[mutate] {mop} amount={mutate_req['amount']} target={mutate_req['target']} "
                f"seed={mutate_req['seed']} -> {summary}")
        if ckpt:
            MODEL.load_lora([str(ckpt)])
        LOADED_DORA, LOADED_STRENGTH = key, 1.0
        LOADED_MUT = mut_key
        if SLOTS.slots:
            # The rebuild threw the resident adapters away with the old MODEL. The
            # table still believes they are loaded, so clear its belief first or
            # apply() sees an unchanged set and skips the reload.
            want = [sl.as_dict() for sl in SLOTS.slots]
            SLOTS.slots = []
            SLOTS.apply(MODEL, want)
            log(f"[slots] re-applied {len(want)} after model rebuild")
    if SLOTS.slots:
        # ACTIVE_SLOT is None outside slot mode, so this zeroes every slot.
        SLOTS.push_strengths(MODEL, ACTIVE_SLOT,
                             strength if slot is not None else 0.0)
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
        if s.get("builtin"):
            # Parameterless builtin guides (E1 recurrence potential, 2026-07-16):
            # no checkpoint — resolved inside model.py's _latch_guided_generate.
            gain = _f(s, "gain", 1e6)
            cfg = {"builtin": str(s["builtin"]), "value": _f(s, "value", 0.34),
                   "start_pct": _f(s, "start_pct", 0.3), "end_pct": _f(s, "end_pct", 0.8),
                   "huber_beta": _f(s, "huber_beta", 0.05)}
            slots.append((cfg, gain))
            continue
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
        # full hyperparam pass-through (Kim 2026-07-12; parity-audit item 1 —
        # these were silently dropped before): per-slot loss shaping.
        if s.get("loss_type"):
            cfg["loss_type"] = str(s["loss_type"])   # mse/smooth_l1/cosine/scalar_pooled/chroma_rung1/2
        if s.get("w_sec") is not None:
            cfg["w_sec"] = _f(s, "w_sec", 1.0)
        # MEASURED CURVE as the target, instead of a kind+value shape (C, 2026-08-28).
        # model.py:539 has always honoured cfg["target_raw"] -- [C, T_any], linearly
        # resampled to the latent grid and then standardised exactly like a built
        # target, so it is supplied in RAW feature units like `value`. resolve_latch
        # simply never passed it through, so /generate could only ever request
        # constant / ramp / beat_grid shapes. That made the one question worth asking
        # of a trajectory-conditioned generator -- "does a REAL curve transfer?" --
        # unaskable through the server. `kind` is dropped when raw is present so the
        # two cannot silently disagree.
        if s.get("target_raw") is not None:
            raw = s["target_raw"]
            n = len(raw[0]) if raw and isinstance(raw[0], (list, tuple)) else len(raw)
            if n < 2:
                raise ValueError("target_raw needs at least 2 frames")
            cfg["target_raw"] = raw
            cfg.pop("kind", None)
            cfg.pop("value", None)
        slots.append((cfg, gain))
    if not slots:
        return None, None
    g0 = float(slots[0][1]) or 1.0
    configs = [{**cfg, "weight": float(gain) / g0} for cfg, gain in slots]
    # rho/mu accept explicit overrides; default stays tied to slot-1 gain
    hparams = {"rho": _f(req, "rho", g0), "mu": _f(req, "mu", g0),
               "gamma": _f(req, "gamma", 0.3), "n_iter": _i(req, "n_iter", 4)}
    return configs, hparams


def apply_latch(kw, latch_cfgs, latch_hp):
    if latch_cfgs:
        kw["latch_configs"] = latch_cfgs
        kw["latch_hparams"] = latch_hp
    return kw


# ---------------------------------------------------------------- latents (z0)
def save_z0(jd, stem, latents, index=None):
    """Write <stem>.z0.npy next to the audio. Standing directive: save z0 next to
    every render (Kim). fp16 to match what every batch renderer writes, so the
    sidecars are interchangeable and eval/continuation.py can read either.

    `latents` is the (B, C, T) tensor handed back by MODEL.generate's latents_sink;
    pass `index` to slice one batch item. Never raises: a good render must not be
    lost because a sidecar could not be written."""
    try:
        t = latents if index is None else latents[index]
        arr = t.detach().squeeze(0).to(torch.float16).cpu().numpy() \
            if t.dim() == 3 else t.detach().to(torch.float16).cpu().numpy()
        p = Path(jd) / f"{stem}.z0.npy"
        np.save(p, arr)
        return str(p)
    except Exception as e:
        log(f"[z0] not saved for {stem}: {e}")
        return None


# ---------------------------------------------------------------- responses
def build_response(job_id, jd, files, seed, t0, stages, warnings, meta, req, rebuilt):
    meta = dict(meta)
    meta.update({"dora_loaded": LOADED_DORA, "film_loaded": FILM_LOADED,
                 "model_rebuilt": bool(rebuilt), "params_echo": req})
    resp = {"status": "ok", "job_id": job_id,
            "files": [str(f) for f in files],
            # top-level so clients (eval/sweep_run.py, the viewer) do not have to
            # know which endpoint produced them
            "latents": list(meta.get("latents") or []),
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


def _scan_ckpts(root: Path):
    """Recursive *.ckpt / *.safetensors scan. Entries carry mtime+size so the
    GUI (and a future incremental pass) can detect staleness cheaply."""
    entries = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for fn in filenames:
            if not (fn.endswith(".ckpt") or fn.endswith(".safetensors")):
                continue
            p = Path(dirpath) / fn
            try:
                st = p.stat()
            except OSError:
                continue                        # racing deletion / unreadable
            entries.append({"path": str(p),
                            "name": str(p.relative_to(root)),
                            "mtime": st.st_mtime,
                            "size": st.st_size,
                            "kind": "safetensors" if fn.endswith(".safetensors") else "ckpt"})
    entries.sort(key=lambda e: e["mtime"], reverse=True)
    return entries


@app.get("/ckpts")
def ckpts(rescan: int = 0, root: str = None, root_ids: str = None):
    """Checkpoint journal for the GUI picker.

    LEGACY (no params / root=): unchanged -- single root, the /tmp journal keyed
    by root path, rescan=1 re-walks. Callers written before multi-root see the
    exact same response shape.

    NEW (root_ids=a,b): merged multi-root listing from the model DB. Entries keep
    the legacy keys and gain root_id + family + label so the picker can render a
    useful option label without a second request.
    """
    if root_ids:
        ids = [s for s in root_ids.split(",") if s]
        out = model_db.load_or_build(ids, rescan=bool(rescan))
        entries = []
        for m in out["models"]:
            rp = m.get("_root_path")
            try:
                name = str(Path(m["path"]).relative_to(rp)) if rp else Path(m["path"]).name
            except ValueError:
                name = Path(m["path"]).name
            entries.append({"path": m["path"], "name": name,
                            "mtime": m["mtime"], "size": m["size"], "kind": m["kind"],
                            "root_id": m["root_id"], "family": m["family"],
                            "label": m["label"], "epoch": m["epoch"], "step": m["step"],
                            "rank": m["rank"], "corpus": m.get("corpus"),
                            "verdict": m.get("verdict")})
        entries.sort(key=lambda e: e["mtime"], reverse=True)
        return {"ok": True, "roots": out["roots"], "cached": not rescan,
                "scanned_at": time.time(), "count": len(entries),
                "ckpts": entries, "stale_root_ids": out["stale_root_ids"]}
    rootp = Path(root) if root else CKPT_SCAN_ROOT
    key = str(rootp)
    with CKPT_JOURNAL_LOCK:
        journal = {}
        if CKPT_JOURNAL_PATH.exists():
            try:
                journal = json.loads(CKPT_JOURNAL_PATH.read_text())
            except (OSError, json.JSONDecodeError):
                journal = {}
        cached = journal.get("roots", {}).get(key)
        if cached is not None and not rescan:
            return {"ok": True, "root": key, "cached": True,
                    "scanned_at": cached["scanned_at"],
                    "count": len(cached["entries"]), "ckpts": cached["entries"]}
        if not rootp.is_dir():
            hint = " — is Mantu1 mounted?" if key.startswith("/run/media/") else ""
            resp = {"ok": False, "root": key, "error": f"scan root not found: {key}{hint}"}
            if cached is not None:              # unmounted drive: serve stale journal
                resp.update(ok=True, cached=True, stale=True,
                            scanned_at=cached["scanned_at"],
                            count=len(cached["entries"]), ckpts=cached["entries"])
                return resp
            return JSONResponse(resp, status_code=404)
        t0 = time.time()
        entries = _scan_ckpts(rootp)
        scanned_at = time.time()
        journal.setdefault("roots", {})[key] = {"scanned_at": scanned_at, "entries": entries}
        tmp = CKPT_JOURNAL_PATH.with_suffix(".json.tmp")
        try:
            tmp.write_text(json.dumps(journal))
            tmp.replace(CKPT_JOURNAL_PATH)      # atomic — concurrent readers see old or new
        except OSError as e:
            log(f"[ckpts] journal write failed: {e}")
        log(f"[ckpts] scanned {key}: {len(entries)} ckpts in {scanned_at - t0:.1f}s")
        return {"ok": True, "root": key, "cached": False, "scanned_at": scanned_at,
                "count": len(entries), "ckpts": entries}


@app.get("/presets")
def presets_list():
    """Named /generate payloads. A preset is a RECIPE: seed and batch_size are
    stripped on save so a sweep's seed axis is never silently pinned."""
    return {"ok": True, "presets": presets.list_presets()}


@app.get("/presets/{name}")
def presets_get(name: str):
    try:
        return presets.load(name)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/presets")
async def presets_post(request: Request):
    body = await request.json()
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    try:
        p = presets.save(name, body.get("payload") or {},
                         notes=body.get("notes", ""), form=body.get("form"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "name": name, "path": str(p)}


def _slot_state(extra=None):
    d = SLOTS.as_dict()
    # ARGS is None until main() parses; /slots must still answer under a
    # TestClient, which imports the module without running main().
    d.update(ok=True, active=ACTIVE_SLOT, backbone=getattr(ARGS, "model", None))
    if extra:
        d.update(extra)
    return d


@app.post("/ab")
async def ab_post(request: Request):
    """One payload, rendered across several resident slots. Body = any /generate
    payload plus {"ab": {"slots": [int|null, ...], "strengths": [float]?}}.

    `null` is the bare base -- the control arm, and the one you actually need: an
    adapter that "sounds better" against nothing is not a finding.

    ONE seed is resolved up front and reused for every arm, so the arms differ only
    by the model. This is the interactive counterpart to eval/sweep_run.py: /ab
    needs every arm resident at once (bounded by VRAM), a sweep does not.
    """
    body = await request.json()
    ab = body.get("ab") or {}
    want = list(ab.get("slots") or [])
    if len(want) < 2:
        return JSONResponse(status_code=400,
                            content={"ok": False, "error": "ab.slots needs at least two "
                                                           "arms (use null for the base)"})
    bad = [x for x in want if x is not None and not (0 <= int(x) < len(SLOTS.slots))]
    if bad:
        return JSONResponse(
            status_code=400,
            content={"ok": False,
                     "error": f"slot(s) {bad} not resident — POST /slots first "
                              f"({len(SLOTS.slots)} resident)"})
    strengths = list(ab.get("strengths") or [])
    seed = resolve_seed(_i(body, "seed", -1))          # ONE seed, reused per arm
    t0 = time.time()
    arms, warnings = [], []
    for i, sl in enumerate(want):
        one = {k: v for k, v in body.items() if k != "ab"}
        one["seed"] = seed
        st = float(strengths[i]) if i < len(strengths) else 1.0
        one["dora"] = {**(body.get("dora") or {}), "slot": sl, "strength": st}
        one.pop("ckpt_path", None)                      # the slot IS the model
        try:
            resp = await run_in_threadpool(_generate_impl, one)
            label = ("base (no adapter)" if sl is None
                     else SLOTS.slots[int(sl)].label)
            arms.append({"slot": sl, "label": label, "strength": st,
                         "files": resp.get("files", []), "urls": resp.get("urls", []),
                         "z0": resp.get("latents", []), "job_id": resp.get("job_id"),
                         "rebuilt": (resp.get("meta") or {}).get("model_rebuilt")})
        except Exception as e:
            warnings.append(f"arm {i} (slot {sl}) failed: {e}")
            arms.append({"slot": sl, "label": f"slot {sl}", "strength": st,
                         "files": [], "urls": [], "z0": [], "error": str(e)})
    return {"ok": True, "arms": arms, "seed": seed, "warnings": warnings,
            "timings": {"total_sec": round(time.time() - t0, 1)}}


@app.get("/slots")
def slots_get():
    """Resident adapter slots. A/B between them costs milliseconds; the alternative
    (rebuild per switch) re-reads GBs from disk and transiently double-allocates."""
    return _slot_state()


@app.post("/slots")
async def slots_post(request: Request):
    """Body: {"slots": [{"ckpt_path", "label"?}, ...], "activate": int|None}.

    Every entry is resolved against the model DB so family and residency cost are
    ground truth, not caller-supplied. A non-adapter family or a set that would
    cross the VRAM floor is REFUSED with a reason rather than OOMing mid-render.
    """
    global ACTIVE_SLOT
    body = await request.json()
    specs = []
    db = {m["path"]: m for m in model_db.load_or_build(rescan=False)["models"]}
    for ent in (body.get("slots") or []):
        path = str(ent.get("ckpt_path") or "").strip()
        if not path:
            raise HTTPException(status_code=400, detail="each slot needs a ckpt_path")
        rec = db.get(path)
        if rec is None:
            raise HTTPException(
                status_code=404,
                detail=f"{path} is not in the model DB — check /models, or rescan")
        if not os.path.exists(path):
            raise HTTPException(
                status_code=404,
                detail=f"{path} is in the DB but not on disk (drive unmounted?)")
        specs.append({"path": path,
                      "label": ent.get("label") or rec.get("label") or path,
                      "family": rec.get("family", "adapter"),
                      # recomputed, not read from the record: a journal written
                      # before the 2026-08-26 measured correction carries the old
                      # 0.33 GB/r128 estimate, and understating cost is how the
                      # floor check lets through a set that then OOMs.
                      "cost_gb": model_db._load_cost_gb(
                          rec.get("family", "adapter"), rec.get("rank"))})
    if MODEL is None:
        raise HTTPException(status_code=409, detail="model not loaded yet")
    plan = SLOTS.apply(MODEL, specs)
    if not plan["ok"]:
        return JSONResponse(status_code=400,
                            content={"ok": False, "reason": plan["reason"],
                                     "projected_free_gb": plan["projected_free_gb"]})
    act = body.get("activate", None)
    ACTIVE_SLOT = None if act is None else int(act)
    if ACTIVE_SLOT is not None and not (0 <= ACTIVE_SLOT < len(SLOTS.slots)):
        ACTIVE_SLOT = None
    SLOTS.push_strengths(MODEL, ACTIVE_SLOT, 1.0)
    log(f"[slots] {len(SLOTS.slots)} resident, active={ACTIVE_SLOT}, "
        f"free={plan['projected_free_gb']} GB")
    return _slot_state({"rebuild": plan["rebuild"]})


@app.get("/roots")
def roots():
    """Configured checkpoint roots + live availability. The GUI's root selector
    is fed from here; an unmounted removable drive comes back available=false
    rather than as an error."""
    out = model_db.load_or_build(rescan=False)
    counts = {}
    for m in out["models"]:
        counts[m["root_id"]] = counts.get(m["root_id"], 0) + 1
    rows = []
    for r in model_roots.resolve_roots(_ROOTS_CFG):
        d = r.as_dict()
        d["count"] = counts.get(r.id, 0)
        rows.append(d)
    return {"ok": True, "roots": rows, "stale_root_ids": out["stale_root_ids"],
            "limits": _LIMITS}


@app.get("/models")
def models(root_ids: str = None, family: str = None, corpus: str = None,
           q: str = None, loadable: int = None, rescan: int = 0):
    """The model database. Every field is either detected from the checkpoint,
    read from the run's run_meta.json, or a human verdict from
    Misc/models_index_overrides.json -- record["provenance"] says which."""
    ids = [s for s in (root_ids or "").split(",") if s] or None
    out = model_db.load_or_build(ids, rescan=bool(rescan))
    ms = out["models"]
    if family:
        ms = [m for m in ms if m["family"] == family]
    if corpus:
        ms = [m for m in ms if (m.get("corpus") or "") == corpus]
    if loadable is not None:
        ms = [m for m in ms if bool(m["loadable"]) == bool(loadable)]
    if q:
        ql = q.lower()
        ms = [m for m in ms
              if ql in m["path"].lower() or ql in (m.get("label") or "").lower()]
    return {"ok": True, "count": len(ms), "models": ms,
            "stale_root_ids": out["stale_root_ids"]}


@app.get("/models/{model_id}")
def model_one(model_id: str):
    for m in model_db.load_or_build(rescan=False)["models"]:
        if m["id"] == model_id:
            return {"ok": True, "model": m}
    return JSONResponse({"ok": False, "error": f"no model {model_id!r}"},
                        status_code=404)


@app.api_route("/schedule", methods=["GET", "POST"])
async def schedule(request: Request):
    """Real sigma schedule for the GUI chart — same build_schedule call the run
    makes: dist_shift is length-dependent, seq_len = ceil(duration*SR/DS) exactly
    as compute_effective_seq_len_from_conditioning derives it from seconds_total
    (generate() sets use_effective_length_for_schedule=True).

    POST JSON (the render_client contract): {"steps": int, "duration": float,
    "dist_shift": float|null (null/absent = model default; float = constant-alpha
    Flux shift, matching resolve_dist_shift on /generate), "sigma_max": float}.
    GET keeps the same keys as query params, plus the legacy shift=0 flag
    (-> linear, no warp). For a2a previews pass sigma_max=init_noise_level
    (schedule truncates there)."""
    if request.method == "POST":
        try:
            req = json.loads((await request.body()) or b"{}")
        except Exception as e:
            return JSONResponse({"error": f"bad JSON body: {e}"}, status_code=400)
    else:
        req = dict(request.query_params)
    m = MODEL
    if m is None:
        return JSONResponse({"error": "model not loaded (rebuild in progress?)"},
                            status_code=503)
    try:
        steps = max(1, _i(req, "steps", 24))
        duration = _f(req, "duration", 47.0)
        sigma_max = _f(req, "sigma_max", 1.0)
        if str(req.get("shift", "1")) in ("0", "false", "False"):  # legacy GET flag
            ds_obj, ds_echo = None, "linear"
        else:
            ds_obj = resolve_dist_shift(req)
            if ds_obj is None:
                ds_echo = "model"
                ds_obj = m.model.sampling_dist_shift
            elif req.get("dist_shift") == "flux":
                ds_echo = "flux"
            else:
                ds_echo = float(req["dist_shift"])
    except (TypeError, ValueError) as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    latent_len = max(1, math.ceil(duration * SR / DS))
    sched = build_schedule(steps=steps, sigma_max=sigma_max,
                           dist_shift=ds_obj,
                           fallback_seq_len=latent_len,
                           include_endpoint=True, device="cpu")
    if sched.dim() == 2:
        sched = sched[0]
    sigmas = [float(s) for s in sched]
    return {"ok": True, "steps": steps, "duration": duration,
            "sigma_max": sigma_max, "dist_shift": ds_echo,
            "latent_len": latent_len, "sigmas": sigmas}


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


@app.post("/longform")
async def longform_ep(request: Request):
    return await _run(_longform_impl, request)


@app.post("/decode")
async def decode_ep(request: Request):
    return await _run(_decode_impl, request)


@app.post("/bend")
async def bend_ep(request: Request):
    return await _run(_bend_impl, request)


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
        rebuilt = prepare_model(resolve_dora_req(req), req.get("film"),
                                mutate_req=resolve_mutate(req))
        stages["prepare"] = time.time() - t0
        latch_cfgs, latch_hp = resolve_latch(req.get("latch"), req)
        # kw-dict lifted from density_control_eval.py:141-155 + schedule extras
        kw = dict(prompt=prompt, duration=duration, steps=steps, cfg_scale=cfg,
                  seed=seed, batch_size=batch,
                  sample_size=budget_for(duration),
                  apg_scale=_f(req, "apg_scale", 1.0),
                  # tuple rides **sampler_kwargs -> sampler extra_args -> DiT forward
                  # (latch path: explicit passthrough in model.py _latch_guided_generate)
                  cfg_interval=resolve_cfg_interval(req),
                  # None -> generate() falls back to model.sampling_dist_shift
                  dist_shift=resolve_dist_shift(req),
                  duration_padding_sec=_f(req, "duration_padding_sec", 6.0),
                  callback=make_log_cb(steps))
        if req.get("negative_prompt"):
            kw["negative_prompt"] = req["negative_prompt"]
        if req.get("sampler_type"):
            kw["sampler_type"] = req["sampler_type"]
        apply_latch(kw, latch_cfgs, latch_hp)
        tg = time.time()
        # latents_sink is a NON-INVASIVE capture added to the fork 2026-08-26: the
        # audio returned is byte-identical to a call without it (proved on both the
        # sample_diffusion and latch-guided branches with a same-seed A/B), and we
        # additionally get the z0 that produced it. The alternative -- a second
        # return_latents=True call -- would double the compute; decoding it here
        # instead would mean reimplementing two different decode paths.
        z0_sink = []
        with film_context(req.get("film")):
            out = MODEL.generate(**with_lora_interval(kw), latents_sink=z0_sink)
        stages["generate"] = time.time() - tg
        check_output_length(out, duration, "generate")
        files, latents = [], []
        z0 = z0_sink[0] if z0_sink else None
        for i in range(out.shape[0]):
            p = jd / f"out_{i:02d}.wav"
            save_audio(p, out[i].float().cpu(), SR, normalize=True)
            files.append(p)
            if z0 is not None and i < z0.shape[0]:
                zp = save_z0(jd, f"out_{i:02d}", z0, index=i)
                if zp:
                    latents.append(zp)
        log(f"[gen {job_id}] done {time.time()-t0:.1f}s")
        return build_response(job_id, jd, files, seed, t0, stages, [],
                              {"op": "generate", "latents": latents}, req, rebuilt)


# ---------------------------------------------------------------- /a2a_track
_PRESERVE_HEAD_CACHE = {}


def make_preserve_hook(req, chunk_np, steps):
    """Kim's inference-time selection steering: at each ping-pong renoise, draw K
    candidates and keep the one whose LatCH-head prediction best matches the
    SOURCE's envelope — training-free rhythm preservation (selection, no grads).
    Active for the first `until` fraction of steps (structure locks early)."""
    p = req.get("preserve") or {}
    if not p.get("enabled"):
        return None
    import librosa
    head_name = p.get("head", "onset_envelope")
    entry = HEADS.get(head_name)
    if entry is None:
        raise ValueError(f"unknown preserve head {head_name!r}")
    if head_name not in _PRESERVE_HEAD_CACHE:
        _PRESERVE_HEAD_CACHE[head_name] = load_latch_from_checkpoint(
            entry["path"], device=ARGS.device)
    head = _PRESERVE_HEAD_CACHE[head_name]
    meta = getattr(head, "metadata", {}) or {}
    fps_lat = SR / 4096.0
    T = int(np.ceil(chunk_np.shape[1] / SR * fps_lat))
    env = librosa.onset.onset_strength(y=chunk_np.mean(0), sr=SR, hop_length=512)
    env_t = np.interp(np.linspace(0, len(env) - 1, T), np.arange(len(env)), env)
    if meta.get("standardized"):
        env_t = (env_t - float(meta.get("std_mean", 0.0))) / (float(meta.get("std_std", 1.0)) or 1.0)
    target = torch.tensor(env_t, dtype=torch.float32, device=ARGS.device)
    target = target.view(1, 1, -1).expand(1, head.out_channels, -1).contiguous()
    K = max(2, int(p.get("k", 4)))
    until = float(p.get("until", 0.5))

    def hook(denoised, t_next, x, i):
        if i >= until * steps:
            return None                        # free-running tail
        tn = float(t_next if t_next.dim() == 0 else t_next.reshape(-1)[0])
        if tn <= 0:
            return None
        t_vec = torch.full((x.shape[0],), tn, device=x.device, dtype=torch.float32)
        best, best_score = None, None
        for _ in range(K):
            cand = (1 - t_next) * denoised + t_next * torch.randn_like(x)
            pred = head(cand.float(), t_vec)
            n = min(pred.shape[-1], target.shape[-1])
            score = -torch.mean((pred[..., :n] - target[..., :n]) ** 2).item()
            if best_score is None or score > best_score:
                best, best_score = cand, score
        return best

    return hook


def _a2a_pass(audio_np, nl, prompt, seed, steps, cfg, latch_cfgs, latch_hp, film_req,
              apg_scale=1.0, cfg_interval=(0.0, 1.0), dist_shift=None,
              renoise_hook=None, sampler_type=None):
    """a2a_fulltrack.py:34-49 inlined (its signature is too narrow for latch/film).
    apg_scale/cfg_interval/dist_shift mirror the /generate kwargs (same
    generate() plumbing: cfg_interval rides **sampler_kwargs to the DiT gate)."""
    a = torch.tensor(audio_np)
    dur = audio_np.shape[1] / SR
    kw = dict(prompt=prompt, duration=dur, steps=steps, cfg_scale=cfg, seed=seed,
              batch_size=1, sample_size=budget_for(dur),
              init_audio=(SR, a), init_noise_level=nl,
              apg_scale=apg_scale, cfg_interval=cfg_interval, dist_shift=dist_shift,
              callback=make_log_cb(steps))
    if renoise_hook is not None:
        kw["renoise_hook"] = renoise_hook
        kw["sampler_type"] = sampler_type or "pingpong"   # selection needs stochasticity
    elif sampler_type:
        kw["sampler_type"] = sampler_type
    apply_latch(kw, latch_cfgs, latch_hp)
    with film_context(film_req):
        out = MODEL.generate(**with_lora_interval(kw))
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
    apg = _f(req, "apg_scale", 1.0)
    cfg_interval = resolve_cfg_interval(req)
    dist_shift = resolve_dist_shift(req)
    seed = resolve_seed(_i(req, "seed", -1))
    with GPU_LOCK:
        t0 = time.time()
        stages = {}
        job_id, jd = new_job("a2atrack")
        log(f"[a2a_track {job_id}] {Path(audio_path).name} nls={nls}")
        rebuilt = prepare_model(resolve_dora_req(req), req.get("film"),
                                mutate_req=resolve_mutate(req))
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
                hook = make_preserve_hook(req, chunk, steps)
                y = _a2a_pass(chunk, nl, prompt, seed, steps, cfg,
                              latch_cfgs, latch_hp, req.get("film"),
                              apg_scale=apg, cfg_interval=cfg_interval,
                              dist_shift=dist_shift,
                              renoise_hook=hook)[:, :chunk.shape[1]]
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
                # No z0 for the a2a paths, deliberately: the output is a crossfade of
                # SEPARATELY sampled windows, so there is no single latent that produced
                # it. Re-encoding the finished audio would give a latent OF the render,
                # not the z0 THAT MADE it -- calling that z0 would break continuation in
                # a way nobody could see. (C, 2026-08-26)
                "latents": [],
                "z0_reason": "a2a output is a crossfade of separately sampled windows — no single z0 exists for it",
                "windows": wins, "noise_levels": nls}
        return build_response(job_id, jd, files, seed, t0, stages, warnings,
                              meta, req, rebuilt)


# ---------------------------------------------------------------- /longform (parity audit 3b)
def _arc_prompt_at(arc, t_sec):
    """Last arc entry with start <= t_sec. arc = _parse_prompt_arc output:
    a bare string (single prompt) or [(t_sec, prompt), ...] sorted-by-construction."""
    if isinstance(arc, str):
        return arc
    prompt = arc[0][1]
    for start, p in arc:
        if t_sec >= float(start):
            prompt = p
    return prompt


def _longform_impl(req):
    """Prompt-ARC rendering. schedule = '0:promptA|45:promptB|...' — the
    steered_longform.py arc grammar (its _parse_prompt_arc, imported; colon-safe,
    a single prompt stays a bare string). Two paths:
      - audio_path given: /a2a_track-style window loop over the source, prompt
        selected per window from the arc (breathing_v2_blockbuild.py pattern);
        full dora/film/latch/preserve/dist_shift support rides _a2a_pass.
      - no audio_path: text-to-audio longform via the proven LongFormRenderer +
        InpaintContinuationGenerator (inference/longform.py — the machinery a
        night was once lost re-inventing); FiLM applies via context. LatCH is
        NOT reachable on this path (sample_diffusion seam) — warned, not dropped
        silently. Pass init_latent_path (a prior render's own .z0.npy) to CONTINUE
        that render instead of starting from nothing — duration is then the FINAL
        total (existing + new); see LongFormRenderer.render_latents' init_latents
        (2026-08-23, GHOST-NOTE/CONTINUITY: parameter plumbing onto the existing
        InpaintContinuationGenerator.generate(prefix_latents=...) primitive, not
        new machinery)."""
    schedule_arg = (req.get("schedule") or req.get("prompt") or "").strip()
    if not schedule_arg:
        raise ValueError("schedule is required ('0:promptA|45:promptB|...' arc grammar)")
    arc = _parse_prompt_arc(schedule_arg)
    arc_echo = arc if isinstance(arc, list) else [(0.0, arc)]
    steps = _i(req, "steps", 24)
    cfg = _f(req, "cfg_scale", 6.0)
    seed = resolve_seed(_i(req, "seed", -1))
    audio_path = req.get("audio_path")
    window_sec = _f(req, "window_sec", 30.0)
    overlap_sec = _f(req, "overlap_sec", 5.0)
    xfade_sec = _f(req, "xfade_sec", 4.0)
    if not (0.0 < overlap_sec < window_sec):
        raise ValueError(f"need 0 < overlap_sec ({overlap_sec}) < window_sec ({window_sec})")
    with GPU_LOCK:
        t0 = time.time()
        stages = {}
        warnings = []
        job_id, jd = new_job("longform")
        log(f"[longform {job_id}] {len(arc_echo)} arc entries, "
            f"{'a2a ' + Path(audio_path).name if audio_path else 't2a'}")
        rebuilt = prepare_model(resolve_dora_req(req), req.get("film"),
                                mutate_req=resolve_mutate(req))
        stages["prepare"] = time.time() - t0
        latch_cfgs, latch_hp = resolve_latch(req.get("latch"), req)
        lat = None            # set only on the t2a branch, which decodes latents itself
        if audio_path:
            # a2a arc: window loop like /a2a_track, prompt per window from the arc
            audio_path = require_path(audio_path, "audio_path")
            nl = _f(req, "noise_level", 0.4)
            apg = _f(req, "apg_scale", 1.0)
            cfg_interval = resolve_cfg_interval(req)
            dist_shift = resolve_dist_shift(req)
            audio = load_audio(audio_path)
            total_sec = audio.shape[1] / SR
            win = min(window_sec, a2a_mod.MAX_SEC)
            hop = win - overlap_sec
            wins, lo = [], 0.0
            while True:
                hi = lo + win
                if hi >= total_sec:
                    wins.append((lo, total_sec))
                    break
                wins.append((lo, hi))
                lo += hop
            n_ov = int(overlap_sec * SR)
            full = None
            prompts_used = []
            for k, (lo, hi) in enumerate(wins):
                tw = time.time()
                pr = _arc_prompt_at(arc, lo)
                prompts_used.append({"t_sec": round(lo, 2), "prompt": pr})
                chunk = audio[:, int(lo * SR):int(hi * SR)]
                hook = make_preserve_hook(req, chunk, steps)
                log(f"  [w{k:02d}] {lo:.1f}-{hi:.1f}s '{pr[:50]}'")
                y = _a2a_pass(chunk, nl, pr, seed + k, steps, cfg,
                              latch_cfgs, latch_hp, req.get("film"),
                              apg_scale=apg, cfg_interval=cfg_interval,
                              dist_shift=dist_shift,
                              renoise_hook=hook)[:, :chunk.shape[1]]
                if full is None:
                    full = y
                else:                            # equal-power cos/sin join (a2a_track)
                    n = min(n_ov, full.shape[1], y.shape[1])
                    tt = np.linspace(0, np.pi / 2, n, dtype=np.float32)
                    join = full[:, -n:] * np.cos(tt) + y[:, :n] * np.sin(tt)
                    full = np.concatenate([full[:, :-n], join, y[:, n:]], axis=1)
                stages[f"w{k:02d}"] = time.time() - tw
            out = torch.tensor(full)
            meta = {"op": "longform", "mode": "a2a",
                    "duration_sec": round(total_sec, 1),
                    "windows": [[round(a, 2), round(b, 2)] for a, b in wins],
                    "noise_level": nl, "arc": prompts_used}
        else:
            duration = _f(req, "duration", 120.0)
            if latch_cfgs:
                warnings.append("latch ignored on the t2a longform path "
                                "(sample_diffusion seam has no latch hook)")
            # CONTINUE FROM AN EXISTING RENDER: init_latent_path points at a prior
            # render's own saved .z0.npy (every renderer writes one — the standing
            # z0-with-audio directive). duration here is the FINAL total (existing +
            # new), matching LongFormRenderer.render_latents' total_frames contract.
            # Saved z0 sidecars are fp16; cast to the model's own dtype before use or
            # this surfaces as garbage output, not an exception (CONTINUITY, 2026-08-23).
            init_latents = None
            init_latent_path = req.get("init_latent_path")
            if init_latent_path:
                init_latent_path = require_path(init_latent_path, "init_latent_path")
                # Recover the prefix's OWN adapter before rendering the tail with
                # whatever happens to be resident. Silence here is how a track ends
                # up with two different models in it and no record (632c417).
                warnings.extend(continuation.apply(
                    req, continuation.recover(init_latent_path)))
                dit_param = next(MODEL.model.model.parameters())
                init_latents = torch.from_numpy(np.load(init_latent_path)).to(
                    dtype=dit_param.dtype, device=dit_param.device)
                if init_latents.dim() == 2:
                    init_latents = init_latents.unsqueeze(0)
            sched = PromptSchedule(arc, crossfade_sec=xfade_sec)
            fr = lambda s: max(1, int(round(s * FPS)))  # noqa: E731  (steered_longform)
            gen = InpaintContinuationGenerator(MODEL, steps=steps, cfg_scale=cfg)
            renderer = LongFormRenderer(gen, channels=MODEL.model.io_channels, fps=FPS,
                                        window_frames=fr(window_sec),
                                        overlap_frames=fr(overlap_sec))
            ts = time.time()
            with film_context(req.get("film")):
                lat = renderer.render_latents(sched, total_frames=fr(duration),
                                              base_seed=seed, init_latents=init_latents)
            stages["render"] = time.time() - ts
            ts = time.time()
            pre = MODEL.model.pretransform
            with torch.inference_mode():
                audio_t = pre.decode(lat.to(next(pre.parameters()).dtype),
                                     chunked=True, chunk_size=128, overlap=32)
            out = audio_t.squeeze(0).float().cpu()
            stages["decode"] = time.time() - ts
            check_output_length(out, duration, "longform")
            meta = {"op": "longform", "mode": "t2a", "duration_sec": duration,
                    "init_latent_path": init_latent_path,
                    "window_sec": window_sec, "overlap_sec": overlap_sec,
                    "xfade_sec": xfade_sec, "arc": arc_echo,
                    "drift_log": renderer.drift_log}
        p = jd / "out_00.wav"
        save_audio(p, out, SR, normalize=True)
        # Standing directive: save z0 next to every render. On this path we already
        # hold the latents (we decode them ourselves), so it is a free np.save --
        # and it is what makes THIS render continuable in turn.
        if lat is not None:
            try:
                np.save(jd / "out_00.z0.npy",
                        lat.detach().squeeze(0).to(torch.float16).cpu().numpy())
                meta["z0_path"] = str(jd / "out_00.z0.npy")
                meta["latents"] = [meta["z0_path"]]
            except Exception as e:                  # never fail a good render over this
                warnings.append(f"z0 not saved: {e}")
        log(f"[longform {job_id}] done {time.time()-t0:.1f}s")
        return build_response(job_id, jd, [p], seed, t0, stages, warnings,
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
    apg = _f(req, "apg_scale", 1.0)
    cfg_interval = resolve_cfg_interval(req)
    dist_shift = resolve_dist_shift(req)
    seed = resolve_seed(_i(req, "seed", -1))
    film_req = req.get("film")
    # crossfade-lab knobs (parity-audit 3c / item 6, Kim 2026-07-12)
    interp = (req.get("interp") or "slerp").lower()
    if interp not in ("slerp", "lerp"):
        raise ValueError(f"unknown interp {interp!r} (slerp|lerp)")
    construction = (req.get("construction") or "model").lower()
    if construction not in ("model", "latent_xfade", "audio_xfade"):
        raise ValueError(f"unknown construction {construction!r} "
                         "(model | latent_xfade = decoded composite, no model pass | "
                         "audio_xfade = transition_lab v2 equal-power audio baseline)")
    if construction != "model":
        chroma_on = False                        # guidance target feeds model passes only
    eps_seed = _i(req, "eps_seed", 4242)         # sinesweep graded-clamp eps
    seam_eps_seed = _i(req, "seam_eps_seed", 2424)  # inpaint seam-nl eps
    warnings = []

    with GPU_LOCK:
        t0 = time.time()
        stages = {}
        job_id, jd = new_job("a2amix")
        log(f"[a2a_mix {job_id}] {Path(a_path).name} -> {Path(b_path).name} mode={mode}")
        rebuilt = prepare_model(resolve_dora_req(req), req.get("film"),
                                default_dora="evr1x",    # op default per design
                                mutate_req=resolve_mutate(req))
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
        if quantize_bars:
            # bar-grid coincidence (cmt.main 257-272 guarantee, generalized): B's
            # downbeat anchor sits at composite 0 and A's at composite `seg`. The
            # script got A/B grid coincidence for free (window = last W frames of
            # A_seg, both anchors ON the window edges); here the window is
            # user-placed, so BOTH the window start and seg must be whole bars or
            # the grids sit `seg mod bar` + `ws mod bar` apart inside the blend.
            ws_q = max(0.0, round(ws_sec / bar_sec) * bar_sec)
            if abs(ws_q - ws_sec) > 0.02:
                warnings.append(f"window start snapped {ws_sec:.2f}s -> {ws_q:.2f}s "
                                f"(A/B bar-grid coincidence)")
            ws_sec = ws_q
            seg_q = math.ceil(seg / bar_sec - 1e-9) * bar_sec
            if abs(seg_q - seg) > 0.02:
                warnings.append(f"seg grown {seg:.2f}s -> {seg_q:.2f}s (whole bars, "
                                f"A anchor on the composite bar grid)")
            seg = seg_q
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

        # cut + bungee-stretch B (cmt.main 272-282; cut on the RAW track, shifted
        # so kicks align inside the blend; then stretch the cut). The script folds
        # the WINDOW residual because its anchors sit on the two window edges (W
        # frames apart); here A's anchor is at composite `seg` and B's at 0, so the
        # grid-coincidence fold is seg's off-grid remainder (0 when quantized above).
        seg_resid = seg - round(seg / bar_sec) * bar_sec
        cut = b_start + seg_resid
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
        if abs(seg_resid) > 0.02:
            warnings.append(f"bar-grid remainder {seg_resid*1000:+.0f}ms folded into B cut")
        stages["beatmatch"] = time.time() - ts

        # 7. encode + composite: both sides share the composite timeline;
        # slerp/lerp over [ws,we] (generalization of cmt.main 297-299).
        # construction=audio_xfade never enters the latent domain (transition_lab
        # v2 no-model baseline: equal-power cos/sin crossfade in audio).
        ts = time.time()
        if construction == "audio_xfade":
            n0, n1 = int(ws_sec * SR), min(int(we_sec * SR), target_n)
            tt = np.linspace(0, np.pi / 2, max(n1 - n0, 1), dtype=np.float32)
            y = A_seg.copy()
            y[:, n0:n1] = A_seg[:, n0:n1] * np.cos(tt) + B_seg[:, n0:n1] * np.sin(tt)
            y[:, n1:] = B_seg[:, n1:]
            dur = y.shape[1] / SR
        else:
            zA = cmt.encode(MODEL, A_seg, SR)
            zB = cmt.encode(MODEL, B_seg, SR)
            Tz = min(zA.shape[-1], zB.shape[-1])
            if we > Tz:
                shift = we - Tz
                ws, we = ws - shift, Tz
                ws_sec, we_sec = ws / FPS, we / FPS
                warnings.append(f"window nudged {shift} frames left to fit latent grid")
            t = torch.linspace(0, 1, W, device=zA.device, dtype=torch.float32).view(1, 1, -1)
            if interp == "lerp":
                mid = ((1 - t) * zA[..., ws:we].float()
                       + t * zB[..., ws:we].float()).to(zA.dtype)
            else:
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

        # decode composite reference once (model + latent_xfade; audio_xfade
        # already holds y in the audio domain)
        pre = MODEL.model.pretransform
        if construction != "audio_xfade":
            with torch.inference_mode():
                audio_ref = pre.decode(z.to(next(pre.parameters()).dtype))[0]
        stages["encode_composite"] = time.time() - ts

        # 9. mode pass (construction 'model' only; latent_xfade = the decoded
        # composite verbatim — the pure latent-crossfade arm, no model pass)
        ts = time.time()
        if construction == "latent_xfade":
            y = audio_ref.float().cpu().numpy()
            log(f"  [pass] latent_xfade ({interp}) — no model pass")
        elif construction == "audio_xfade":
            log("  [pass] audio_xfade — no model pass")
        else:
            kw = dict(prompt=prompt, duration=dur, steps=steps, cfg_scale=cfg,
                      apg_scale=apg, cfg_interval=cfg_interval, dist_shift=dist_shift,
                      seed=seed, batch_size=1, sample_size=budget_for(dur))
            apply_latch(kw, latch_cfgs, latch_hp)
            if mode == "inpaint":                # cmt.main 342-345
                kw["inpaint_audio"] = (SR, audio_ref.float())
                kw["inpaint_mask_start_seconds"] = ws_sec
                kw["inpaint_mask_end_seconds"] = we_sec
                kw["callback"] = make_log_cb(steps)
            elif mode == "sinesweep":            # cmt.main 311-315 + 349-364, EXACT
                kw["init_audio"] = (SR, audio_ref.float())
                kw["init_noise_level"] = nl
                depth_shape = torch.zeros(Tz)
                depth_shape[ws:we] = torch.sin(torch.linspace(0, torch.pi, W))
                z_ref = z.float().cpu()
                torch.manual_seed(eps_seed)      # graded-clamp eps (was fixed 4242)
                eps_ref = torch.randn_like(z_ref)
                depth = (depth_shape * nl).view(1, 1, -1)

                def cb(d, _z=z_ref, _e=eps_ref, _d=depth):
                    x, tt = d["x"], float(d["t"][0])
                    n = min(x.shape[-1], _z.shape[-1])
                    hold = (_d[..., :n] < tt)    # not yet released
                    ref_t = ((1 - tt) * _z[..., :n] + tt * _e[..., :n]).to(x.device, x.dtype)
                    xs = x[..., :n]
                    x[..., :n].copy_(torch.where(hold.to(x.device), ref_t, xs))

                kw["callback"] = make_log_cb(steps, extra=cb)
            else:                                # refine: whole composite a2a
                kw["init_audio"] = (SR, audio_ref.float())
                kw["init_noise_level"] = nl
                kw["callback"] = make_log_cb(steps)
            log(f"  [pass] {mode} dur={dur:.1f}s window {ws_sec:.1f}-{we_sec:.1f}s "
                f"({W}f{f' = {bars} bars' if bars else ''})")
            with film_context(film_req):
                y = MODEL.generate(**with_lora_interval(kw))[0].float().cpu().numpy()
            check_output_length(y, dur, mode)
        stages["main_pass"] = time.time() - ts

        # 10. seam-inpaint strips (model-construction sinesweep only; cmt.main 375-393)
        if construction == "model" and mode == "sinesweep" and seam_inpaint > 0:
            ts = time.time()
            S = seam_inpaint / FPS
            starts = [max(ws_sec - S / 2, 0), we_sec - S / 2]
            ends = [ws_sec + S / 2, min(we_sec + S / 2, y.shape[1] / SR)]
            log(f"  [pass] seam-inpaint {seam_inpaint}f strips")
            kw3 = dict(prompt=prompt, duration=y.shape[1] / SR, steps=steps,
                       cfg_scale=cfg, apg_scale=apg, cfg_interval=cfg_interval,
                       dist_shift=dist_shift, seed=seed, batch_size=1,
                       sample_size=budget_for(y.shape[1] / SR),
                       inpaint_audio=(SR, torch.tensor(y)),
                       inpaint_mask_start_seconds=starts,
                       inpaint_mask_end_seconds=ends,
                       callback=make_log_cb(steps))
            apply_latch(kw3, latch_cfgs, latch_hp)
            with film_context(film_req):
                y = MODEL.generate(**with_lora_interval(kw3))[0].float().cpu().numpy()
            stages["seam_inpaint"] = time.time() - ts

        # out_bridge.wav = pre-splice render, always saved (exploration tool)
        bridge_path = jd / "out_bridge.wav"
        save_audio(bridge_path, torch.tensor(y), SR, normalize=True)

        # 11. pure-basis splice (cmt.main 394-419; offB generalizes to 0 because
        # B_seg shares the composite timeline here). FAITHFUL to the script incl.
        # its f2 (0.5 s) B-side shift: origB = B_seg[hi_n - offB - f2:] means the
        # fade and everything after the window play original-B 0.5 s late relative
        # to the composite grid — the ear-ranked proven renders include that shift,
        # so we reproduce it rather than the grid-aligned variant.
        if construction == "model" and mode == "sinesweep" and pure_basis:
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
            if f2 <= hi_n and hi_n + f2 <= m2:
                out_full[:, hi_n:hi_n + f2] = (y[:, hi_n:hi_n + f2] * (1 - rmp)
                                               + B_seg[:, hi_n - f2:hi_n] * rmp)
                out_full[:, hi_n + f2:m2] = B_seg[:, hi_n:m2 - f2]
            else:
                warnings.append("pure-basis B splice skipped (window too close to "
                                "composite start/end)")
            y = out_full

        # inpaint mode: original-audio splice-back with 1s fades (cmt.main 420-434)
        if construction == "model" and mode == "inpaint":
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
                torch.manual_seed(seam_eps_seed)  # seam-nl eps (was fixed 2424)
                eps2 = torch.randn_like(z_ref2)
                depth2 = (dshape * seam_nl).view(1, 1, -1)

                def cb2(d, _z=z_ref2, _e=eps2, _d=depth2):
                    x, tt = d["x"], float(d["t"][0])
                    nn = min(x.shape[-1], _z.shape[-1], _d.shape[-1])
                    hold = (_d[..., :nn] < tt)
                    ref_t = ((1 - tt) * _z[..., :nn] + tt * _e[..., :nn]).to(x.device, x.dtype)
                    x[..., :nn].copy_(torch.where(hold.to(x.device), ref_t, x[..., :nn]))

                kw2 = dict(prompt=prompt, duration=y.shape[1] / SR, steps=steps,
                           cfg_scale=cfg, apg_scale=apg, cfg_interval=cfg_interval,
                           dist_shift=dist_shift, seed=seed, batch_size=1,
                           sample_size=budget_for(y.shape[1] / SR),
                           init_audio=(SR, torch.tensor(y)),
                           init_noise_level=seam_nl,
                           callback=make_log_cb(steps, extra=cb2))
                apply_latch(kw2, latch_cfgs, latch_hp)
                with film_context(film_req):
                    y = MODEL.generate(**with_lora_interval(kw2))[0].float().cpu().numpy()
                stages["seam_nl"] = time.time() - ts

        # 12. optional whole-track a2a pass over the composite
        if whole:
            ts = time.time()
            wt_nl = _f(whole, "noise_level", 0.4)
            wt_prompt = (whole.get("prompt") or prompt).strip()
            log(f"  [pass] whole-track a2a nl={wt_nl:.2f}")
            dur2 = y.shape[1] / SR
            kw4 = dict(prompt=wt_prompt, duration=dur2, steps=steps, cfg_scale=cfg,
                       apg_scale=apg, cfg_interval=cfg_interval, dist_shift=dist_shift,
                       seed=seed, batch_size=1, sample_size=budget_for(dur2),
                       init_audio=(SR, torch.tensor(y)), init_noise_level=wt_nl,
                       callback=make_log_cb(steps))
            apply_latch(kw4, latch_cfgs, latch_hp)
            with film_context(film_req):
                y = MODEL.generate(**with_lora_interval(kw4))[0].float().cpu().numpy()
            check_output_length(y, dur2, "whole_track")
            stages["whole_track"] = time.time() - ts

        mix_path = jd / "out_mix.wav"
        save_audio(mix_path, torch.tensor(y), SR, normalize=True)
        log(f"[a2a_mix {job_id}] done {time.time()-t0:.1f}s")

        meta = {"op": "a2a_mix", "mode": mode,
                # No z0 for the a2a paths, deliberately: the output is a crossfade of
                # SEPARATELY sampled windows, so there is no single latent that produced
                # it. Re-encoding the finished audio would give a latent OF the render,
                # not the z0 THAT MADE it -- calling that z0 would break continuation in
                # a way nobody could see. (C, 2026-08-26)
                "latents": [],
                "z0_reason": "a2a output is a crossfade of separately sampled windows — no single z0 exists for it",
                "construction": construction, "interp": interp,
                "eps_seed": eps_seed, "seam_eps_seed": seam_eps_seed,
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
    latent_dir = Path(req.get("latent_dir") or PLAYER_CFG["latent_dir"])
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


# ---------------------------------------------------------------- /bend (parity audit 3d)
def _bend_impl(req):
    """Latent data-bending: resolve the source latent exactly like /decode
    (latent_path | crop_id under latent_dir), apply eval/latent_bend.py ops
    (module written in parallel — imported lazily and guarded; contract:
    apply_bends(latent, ops, seed) on a (1,C,T) float32 CPU tensor), then the
    same chunked decode + sidecar trim + normalized save as _decode_impl."""
    try:
        import latent_bend  # noqa: PLC0415  (eval/ already on sys.path; lazy so boot never depends on it)
    except ImportError as e:
        raise RuntimeError(f"latent_bend module not available yet ({e}) — "
                           "being written in parallel; retry once it lands")
    ops = req.get("ops")
    if not isinstance(ops, list) or not ops:
        raise ValueError("ops must be a non-empty list of bend-op dicts "
                         "(weight_mutations-style: [{'op': ..., 'amount': ...}, ...])")
    seed = resolve_seed(_i(req, "seed", -1))
    latent_dir = Path(req.get("latent_dir") or PLAYER_CFG["latent_dir"])
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
    if arr.ndim == 2:
        arr = arr[None]
    with GPU_LOCK:
        t0 = time.time()
        stages = {}
        job_id, jd = new_job("bend")
        log(f"[bend {job_id}] {Path(path).name} shape={tuple(arr.shape)} "
            f"ops={[o.get('op') for o in ops]} seed={seed}")
        ts = time.time()
        z = torch.from_numpy(arr)                # (1,C,T) float32, CPU
        z = latent_bend.apply_bends(z, ops, seed)
        if not torch.isfinite(z).all():
            raise RuntimeError("bend produced non-finite latents — refusing to decode")
        stages["bend"] = time.time() - ts
        ts = time.time()
        pre = MODEL.model.pretransform
        p = next(pre.parameters())
        with torch.inference_mode():
            audio = pre.decode(z.to(device=p.device, dtype=p.dtype),
                               chunked=True, chunk_size=128, overlap=32)
        a = audio.squeeze(0).float().cpu()
        if sidecar is not None:
            n_content = int(sum(sidecar.get("padding_mask") or [])) or arr.shape[-1]
            samples = n_content * DS
            if 0 < samples < a.shape[1]:
                a = a[:, :samples]
        stages["decode"] = time.time() - ts
        out = jd / "out_00.wav"
        save_audio(out, a, SR, normalize=True)
        meta = {"op": "bend", "ops": ops, "latent_shape": list(arr.shape),
                "duration_sec": round(a.shape[1] / SR, 2)}
        return build_response(job_id, jd, [out], seed, t0, stages, [], meta, req, False)


# ---------------------------------------------------------------- latent player GET endpoints
# Ported 1:1 from mir/scripts/latent_server_sa3.py (:7892) so the second resident
# SAME-L copy can be retired. The query-parameter contract is UNCHANGED
# (?crop= / ?crop_a=&crop_b=&t=&interp= / ?crop=&head=&gain=) so the viewer
# client needs only a base-URL change. Every decode goes through the already
# loaded MODEL.model.pretransform -- never a second from_pretrained().
def _player_latent_dir() -> Path:
    d = PLAYER_CFG.get("latent_dir")
    if not d:
        raise RuntimeError(f"latent_dir not configured -- set it in {PLAYER_INI_PATH}")
    return Path(d)


def wav_bytes(audio: np.ndarray, sr: int) -> bytes:
    """audio [2, samples] float32 -> stereo int16 WAV bytes (verbatim from :7892)."""
    a = np.clip(audio, -1.0, 1.0)
    i16 = (a * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(i16.T.flatten().tobytes())
    return buf.getvalue()


def _player_meta(crop_id: str) -> dict:
    return json.loads((_player_latent_dir() / f"{crop_id}.json").read_text())


def _player_latent(crop_id: str) -> np.ndarray:
    path = _player_latent_dir() / f"{crop_id}.npy"
    if not path.exists():
        raise FileNotFoundError(f"crop {crop_id}")
    arr = np.load(path).astype(np.float32)
    return arr[0] if arr.ndim == 3 else arr


def _player_decode(z_np: np.ndarray) -> np.ndarray:
    """[C, T] latent -> [2, samples] float32, on the RESIDENT pretransform."""
    pre = MODEL.model.pretransform
    par = next(pre.parameters())
    z = torch.from_numpy(np.ascontiguousarray(z_np)).unsqueeze(0).to(
        device=par.device, dtype=par.dtype)
    with torch.inference_mode():
        audio = pre.decode(z, chunked=True,
                           chunk_size=int(PLAYER_CFG["chunk_size"]),
                           overlap=int(PLAYER_CFG["overlap"]))
    return audio.squeeze(0).float().cpu().numpy()


def _player_trim(audio_np: np.ndarray, meta: dict | None, n_frames: int) -> np.ndarray:
    if not meta:
        return audio_np
    n_content = int(sum(meta.get("padding_mask") or [])) or n_frames
    samples = n_content * DS
    return audio_np[:, :samples] if 0 < samples < audio_np.shape[1] else audio_np


def _player_steer_head(feature: str):
    """Load a LatCH head from the SHARED HEADS registry (no second scanner)."""
    if feature in STEER_HEADS:
        return STEER_HEADS[feature]
    entry = HEADS.get(feature)
    if entry is None:
        raise FileNotFoundError(f"head {feature}")
    dev = next(MODEL.model.pretransform.parameters()).device
    head = load_latch_from_checkpoint(str(entry["path"]), device=str(dev))
    head.eval().requires_grad_(False)
    STEER_HEADS[feature] = head
    return head


def _player_run(fn):
    """Shared error contract of the old player: 404 for unknown crop/head."""
    try:
        return Response(content=fn(), media_type="audio/wav")
    except FileNotFoundError as e:
        log(f"[player] 404 {e}")
        return JSONResponse({"error": "unknown crop or head",
                             "heads": sorted(HEADS)}, status_code=404)
    except Exception as e:
        log(f"[player] error {e}")
        return JSONResponse({"error": str(e),
                             "traceback": traceback.format_exc()}, status_code=500)


@app.get("/crops")
def player_crops():
    try:
        return sorted(p.stem for p in _player_latent_dir().glob("*.npy"))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/meta")
def player_meta(crop: str = None, crop_id: str = None):
    try:
        return _player_meta(crop or crop_id)
    except (FileNotFoundError, TypeError):
        return JSONResponse({"error": "unknown crop"}, status_code=404)


@app.get("/player_status")
def player_status():
    """The old :7892 /status. Not mounted at /status -- this server already has one."""
    try:
        latent_dir = str(_player_latent_dir())
    except Exception as e:
        latent_dir = f"<{e}>"
    return {"ok": True, "model": ARGS.model if ARGS else None, "sample_rate": SR,
            "latent_dir": latent_dir, "heads": sorted(HEADS)}


@app.get("/decode")
def player_decode(crop: str = None, crop_id: str = None):
    cid = crop or crop_id

    def run():
        arr = _player_latent(cid)
        meta = None
        if (_player_latent_dir() / f"{cid}.json").exists():
            meta = _player_meta(cid)
        with GPU_LOCK:
            audio = _player_decode(arr)
        return wav_bytes(_player_trim(audio, meta, arr.shape[1]), SR)
    return _player_run(run)


@app.get("/source")
def player_source(crop: str = None, crop_id: str = None):
    cid = crop or crop_id

    def run():
        meta = _player_meta(cid)
        audio, sr = sf.read(meta["source_path"], dtype="float32", always_2d=True,
                            start=int(meta["start_sample"]),
                            stop=int(meta["end_sample"]))
        audio = audio.T
        if audio.shape[0] == 1:
            audio = np.repeat(audio, 2, axis=0)
        elif audio.shape[0] > 2:
            audio = audio[:2]
        return wav_bytes(audio, sr)
    return _player_run(run)


@app.get("/mix")
def player_mix(crop_a: str, crop_b: str, t: float = 0.5, interp: str = "slerp"):
    def run():
        a, b = _player_latent(crop_a), _player_latent(crop_b)
        n = min(a.shape[1], b.shape[1])
        za = torch.from_numpy(a[:, :n]).unsqueeze(0).float()
        zb = torch.from_numpy(b[:, :n]).unsqueeze(0).float()
        # SA3's own slerp (already imported) -- per-frame over the channel dim.
        z = (slerp(za, zb, float(t)) if interp == "slerp"
             else (1.0 - float(t)) * za + float(t) * zb)
        with GPU_LOCK:
            audio = _player_decode(z.squeeze(0).numpy())
        return wav_bytes(audio, SR)
    return _player_run(run)


@app.get("/steer")
def player_steer(crop: str = None, head: str = None, gain: float = 48.0,
                 crop_id: str = None, feature: str = None):
    cid, feat = crop or crop_id, head or feature

    def run():
        arr = _player_latent(cid)
        h = _player_steer_head(feat)
        dev = next(MODEL.model.pretransform.parameters()).device
        z = torch.from_numpy(arr).unsqueeze(0).float().to(dev)
        z.requires_grad_(True)
        ts = torch.tensor([0.001], dtype=torch.float32, device=z.device)
        h(z, ts).mean().backward()
        z_edit = (z.detach() + float(gain) * z.grad).cpu().numpy()[0]
        with GPU_LOCK:
            audio = _player_decode(z_edit)
        return wav_bytes(audio, SR)
    return _player_run(run)


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

    # Warm the model database in the background while the DiT loads. The first
    # /models call otherwise walks ~2100 files across two USB drives, which blows
    # past the viewer client's timeout -- the picker then silently falls back to
    # its four legacy registry names, which is exactly how the UI looked empty
    # for a whole day (2026-08-24/25).
    def _warm_model_db():
        try:
            t0 = time.time()
            n = len(model_db.load_or_build(rescan=False)["models"])
            log(f"[boot] model db warm: {n} models in {time.time() - t0:.1f}s")
        except Exception as e:                       # never block boot on a scan
            log(f"[boot] model db warm failed: {e}")
    threading.Thread(target=_warm_model_db, daemon=True).start()

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
