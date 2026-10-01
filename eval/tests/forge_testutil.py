"""Put THIS worktree's eval/ first on sys.path (tests must never import the shared tree)."""
import sys
from pathlib import Path

EVAL = Path(__file__).resolve().parents[1]
if str(EVAL) in sys.path:
    sys.path.remove(str(EVAL))
sys.path.insert(0, str(EVAL))


def make_stub_server(out_dir):
    """A minimal stand-in for explorer_render_server, for boxes with no torch / GPU.

    It reproduces ONLY the surface forge_api uses and the three hooks the real server gains in M2 T8
    (log -> forge.logseq, make_log_cb -> forge.progress.on_step, /status carrying progress), so the
    /forge routes can be exercised end to end. It is not a substitute for the real-server tests:
    test_forge_api_jobs.py prefers the real module and falls back to this one.
    """
    import threading
    import types

    from fastapi import FastAPI

    from forge import logseq, progress

    srv = types.ModuleType("stub_render_server")
    srv.app = FastAPI()
    srv.OUT_DIR = out_dir
    srv.GPU_LOCK = threading.Lock()
    srv.PLAYER_CFG = {}

    def log(msg):
        logseq.append(f"00:00:00 {msg}")

    def make_log_cb(steps):
        counter = {"i": 0}

        def cb(d):
            counter["i"] += 1
            progress.on_step(counter["i"], steps)
        return cb

    def _unimplemented(name):
        def impl(req):
            raise RuntimeError(f"{name} is not available on the stub server")
        return impl

    srv.log = log
    srv.make_log_cb = make_log_cb
    for n in ("_generate_impl", "_a2a_track_impl", "_a2a_mix_impl", "_longform_impl", "_decode_impl", "_bend_impl"):
        setattr(srv, n, _unimplemented(n))

    @srv.app.get("/status")
    def status():
        return {"ok": True, "busy": srv.GPU_LOCK.locked(), "job_id": None, "log_tail": [],
                "progress": progress.snapshot()}

    import forge_api
    forge_api.bind(srv)
    srv.app.include_router(forge_api.router)
    return srv
