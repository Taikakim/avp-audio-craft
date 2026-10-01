"""Latent Forge HTTP routes (spec §6). Thin: parse, validate, dispatch into eval/forge/*.

The server imports this module and calls bind(sys.modules[__name__]) — NEVER
`import explorer_render_server` from here: run as a script the server is `__main__`,
and a second import would build a second, model-less copy of every global.
"""
import functools
import traceback

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from forge import contract, jobs as jobs_mod, logseq, progress
from forge.contract import ForgeError
from forge.paths import ForgePaths
from forge.services import Services

router = APIRouter()
SRV = None
QUEUE = None
_RUNNERS = {}
_VALIDATORS = {}
_SERVICES = None

EXISTING_OPS = {"generate": "_generate_impl", "a2a_track": "_a2a_track_impl", "a2a_mix": "_a2a_mix_impl",
                "longform": "_longform_impl", "decode": "_decode_impl", "bend": "_bend_impl"}


def ok(**kw):
    return {"ok": True, **kw}


def err(status, message, **extra):
    return JSONResponse({"ok": False, "error": message, **extra}, status_code=status)


def forge_route(fn):
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except ForgeError as e:
            return err(e.status, e.message)
        except Exception as e:  # noqa: BLE001
            SRV.log(f"[forge] error {e}")
            return err(500, str(e), traceback=traceback.format_exc())
    return wrapper


def paths() -> ForgePaths:
    return ForgePaths(SRV.OUT_DIR).ensure()


def services() -> Services:
    global _SERVICES
    if _SERVICES is None or _SERVICES.srv is not SRV:
        _SERVICES = Services(SRV, paths)
    return _SERVICES


def _existing_runner(op, impl_name):
    def run(job_id, payload):
        steps = 0 if op in ("decode", "bend") else int(payload.get("steps", 24))
        passes = len(payload.get("noise_levels") or [1]) if op == "a2a_track" else 1
        progress.begin(job_id, op, steps * passes)
        try:
            return getattr(SRV, impl_name)(payload)          # looked up per call: monkeypatchable
        finally:
            progress.end()
    return run


def _validate_existing(op, payload):
    if op == "generate":
        contract.check_cap(payload.get("duration", 47.0), "generate")
    if op == "longform" and not payload.get("audio_path"):
        contract.check_cap(payload.get("duration", 120.0), "longform")


def register_runner(op, fn, validator=None):
    _RUNNERS[op] = fn
    if validator is not None:
        _VALIDATORS[op] = validator
    if QUEUE is not None:
        QUEUE.set_runner(op, fn)


def reset_queue():
    global QUEUE
    if QUEUE is not None:
        QUEUE.stop()
    QUEUE = jobs_mod.JobQueue(_RUNNERS, max_pending=contract.MAX_PENDING_JOBS,
                              log=lambda m: SRV.log(m))
    return QUEUE


def bind(srv):
    global SRV
    SRV = srv
    for op, impl in EXISTING_OPS.items():
        register_runner(op, _existing_runner(op, impl),
                        validator=lambda p, _op=op: _validate_existing(_op, p))
    reset_queue()


# ------------------------------------------------------------------ jobs
@router.post("/forge/jobs")
@forge_route
async def jobs_submit(request: Request):
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        raise ForgeError(400, "body must be JSON {op, payload}")
    if not isinstance(body, dict) or not isinstance(body.get("op"), str):
        raise ForgeError(400, "body needs an 'op' string")
    op, payload = body["op"], body.get("payload")
    if op not in _RUNNERS:
        raise ForgeError(400, f"unknown op {op!r} (have {', '.join(sorted(_RUNNERS))})")
    if not isinstance(payload, dict):
        raise ForgeError(400, "payload must be a JSON object")
    if op in _VALIDATORS:
        _VALIDATORS[op](payload)
    try:
        jid, ahead = QUEUE.submit(op, payload)
    except jobs_mod.QueueFull:
        raise ForgeError(409, "job queue full")
    return JSONResponse({"ok": True, "job_id": jid, "position": ahead}, status_code=202)


@router.get("/forge/jobs")
@forge_route
async def jobs_list(limit: int = 50):
    return ok(jobs=QUEUE.list(limit))


@router.get("/forge/jobs/{job_id}")
@forge_route
async def jobs_get(job_id: str):
    rec = QUEUE.get(job_id)
    if rec is None:
        raise ForgeError(404, f"no job {job_id}")
    snap = progress.snapshot()
    prog = snap if (snap and snap["job_id"] == job_id and rec["state"] == "running") else None
    return ok(**rec, progress=prog)


@router.delete("/forge/jobs/{job_id}")
@forge_route
async def jobs_cancel(job_id: str):
    try:
        rec = QUEUE.cancel(job_id)
    except KeyError:
        raise ForgeError(404, f"no job {job_id}")
    except jobs_mod.CannotCancel:
        raise ForgeError(409, "cannot cancel a running pass")
    return ok(**rec, progress=None)


# ------------------------------------------------------------------ log
@router.get("/forge/log")
@forge_route
async def log_since(since: int = 0):
    last, lines = logseq.since(since)
    return ok(seq=last, lines=lines)
