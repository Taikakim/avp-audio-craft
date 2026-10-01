"""Latent Forge HTTP routes (spec §6). Thin: parse, validate, dispatch into eval/forge/*.

The server imports this module and calls bind(sys.modules[__name__]) — NEVER
`import explorer_render_server` from here: run as a script the server is `__main__`,
and a second import would build a second, model-less copy of every global.
"""
import functools
import traceback

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from forge import analysis, contract, jobs as jobs_mod, logseq, progress, stretch, chroma
from forge.contract import ForgeError
from forge.paths import ForgePaths
from forge.services import Services
from forge.hashing import file_sha256
import json
from pathlib import Path
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool
from forge import library, uploads
from forge.store import JsonStore

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


# ------------------------------------------------------------------ library
_MEDIA = {".wav": "audio/wav", ".flac": "audio/flac", ".mp3": "audio/mpeg", ".m4a": "audio/mp4",
          ".ogg": "audio/ogg", ".aif": "audio/aiff", ".aiff": "audio/aiff"}


def parse_ref_param(raw):
    try:
        ref = json.loads(raw)
    except (TypeError, ValueError):
        raise ForgeError(400, "ref must be URL-encoded JSON")
    return ref


@router.put("/forge/upload")
@forge_route
async def upload(request: Request, filename: str = ""):
    w = uploads.UploadWriter(filename, paths().uploads, contract.UPLOAD_MAX_BYTES)
    try:
        async for chunk in request.stream():
            w.feed(chunk)
        dst, sha, n = w.finish()
    except BaseException:
        w.abort()
        raise
    try:
        info = await run_in_threadpool(uploads.probe_audio, dst)
    except ForgeError:
        dst.unlink(missing_ok=True)
        raise
    return ok(ref={"kind": "upload", "sha256": sha}, path=str(dst), bytes=n, **info)


@router.get("/forge/files")
@forge_route
async def files(root: str = "crops", q: str = "", limit: int = 500):
    ctx = services().ref_context()
    roots = {"crops": ctx.roots.get("crops"), "renders": ctx.roots.get("renders"), "uploads": ctx.roots.get("uploads")}
    return ok(**await run_in_threadpool(library.list_files, roots, root, q, limit))


@router.get("/forge/audio")
@forge_route
async def audio(ref: str):
    path = await run_in_threadpool(services().resolve_audio, parse_ref_param(ref))
    return FileResponse(path, media_type=_MEDIA.get(Path(path).suffix.lower(), "application/octet-stream"))


def _sessions():
    return JsonStore(paths().sessions, contract.SESSION_MAX_BYTES)


@router.get("/forge/sessions")
@forge_route
async def sessions_list():
    store = _sessions()
    rows = []
    for row in store.listing():
        try:
            n = len(store.get(row["name"]).get("clips") or [])
        except (ValueError, ForgeError):
            n = 0
        rows.append({**row, "n_clips": n})
    return ok(sessions=rows)


@router.get("/forge/sessions/{name}")
@forge_route
async def sessions_get(name: str):
    return _sessions().get(name)


@router.put("/forge/sessions/{name}")
@forge_route
async def sessions_put(name: str, request: Request):
    body = await request.json()
    if not isinstance(body, dict) or body.get("version") != 2:
        raise ForgeError(400, "session must be a JSON object with \"version\": 2")
    _sessions().put(name, body)
    return ok()


def _presets(level):
    return JsonStore(paths().preset_dir(level), contract.PRESET_MAX_BYTES)


@router.get("/forge/presets/{level}")
@forge_route
async def presets_list(level: str):
    return ok(names=_presets(level).names())


@router.get("/forge/presets/{level}/{name}")
@forge_route
async def presets_get(level: str, name: str):
    return _presets(level).get(name)


@router.put("/forge/presets/{level}/{name}")
@forge_route
async def presets_put(level: str, name: str, request: Request):
    _presets(level).put(name, await request.json())
    return ok()


@router.delete("/forge/presets/{level}/{name}")
@forge_route
async def presets_delete(level: str, name: str):
    _presets(level).delete(name)
    return ok()


# ------------------------------------------------------------------ analyze
def _crop_meta(crop_id):
    try:
        return SRV._player_meta(crop_id)
    except Exception:  # noqa: BLE001
        return None


def _analyze_ref(ref):
    svc = services()
    if isinstance(ref, dict) and ref.get("kind") == "crop":
        svc.resolve_audio(ref)                                  # validates + caches the decode
        meta = _crop_meta(ref["crop_id"]) or {}
        hint = meta.get("bpm_madmom") or meta.get("bpm_essentia")
        src = meta.get("source_path")
        if src and Path(src).is_file():
            import soundfile as sf
            a, sr = sf.read(src, dtype="float32", always_2d=True,
                            start=int(meta["start_sample"]), stop=int(meta["end_sample"]))
            return analysis.analyze_audio(a.T, sr, bpm_hint=hint)
        a = svc.load_audio(svc.decode_crop(ref["crop_id"]))
        return analysis.analyze_audio(a, SRV.SR, bpm_hint=hint)
    path = svc.resolve_audio(ref)
    return analysis.analyze_audio(svc.load_audio(path), SRV.SR)


@router.post("/forge/analyze")
@forge_route
async def analyze(request: Request):
    body = await request.json()
    return ok(**await run_in_threadpool(_analyze_ref, (body or {}).get("audio")))


def _stretch_ref(ref, speed, semitones):
    import soundfile as sf
    speed, semitones = stretch.validate(speed, semitones)
    svc = services()
    src = svc.resolve_audio(ref)
    if stretch.is_identity(speed, semitones):
        return {"ref": ref, "duration_sec": round(sf.info(str(src)).duration, 3)
                if src.suffix.lower() in (".wav", ".flac") else uploads.probe_audio(src)["duration_sec"]}
    sha = file_sha256(src)
    dst = paths().cache_dir("stretch") / f"{stretch.cache_key(sha, speed, semitones)}.wav"
    if not dst.exists():
        readable = src
        if src.suffix.lower() not in (".wav", ".flac"):
            readable = paths().cache_dir("decode") / f"{sha}.wav"
            if not readable.exists():
                sf.write(readable, svc.load_audio(src).T, SRV.SR, subtype="FLOAT")
        stretch.stretch_file(readable, dst, speed, semitones)
    return {"ref": {"kind": "path", "path": str(dst)}, "duration_sec": round(sf.info(str(dst)).duration, 3)}


@router.post("/forge/stretch")
@forge_route
async def stretch_route(request: Request):
    body = await request.json() or {}
    return ok(**await run_in_threadpool(_stretch_ref, body.get("audio"), body.get("speed", 1.0),
                                        body.get("semitones", 0.0)))


def _chroma_ref(ref):
    svc = services()
    src = svc.resolve_audio(ref)
    cache = paths().cache_dir("chroma") / f"{file_sha256(src)}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    payload = chroma.chroma_payload(svc.load_audio(src), SRV.SR)
    cache.write_text(json.dumps(payload))
    return payload


@router.post("/forge/chroma")
@forge_route
async def chroma_route(request: Request):
    body = await request.json() or {}
    return ok(**await run_in_threadpool(_chroma_ref, body.get("audio")))
