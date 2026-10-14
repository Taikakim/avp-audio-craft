# Owner: WINTERMUTE (created 2026-10-13)
# Last edited: WINTERMUTE 2026-10-13 -- priors + on-disk history so a first load has an ETA too
"""Progress of a model (re)load, for the Forge top-bar bar. GET /status carries snapshot().

A load is a few opaque calls (from_pretrained, a checkpoint read), so the only honest
fraction is time-based: each stage's expected duration is the last measured duration of
that same stage for that same target (the backbone id). Measured times persist in
HISTORY_PATH across server restarts; a stage never measured falls back to PRIORS, which
are this box's own timings (2026-10-13: medium-base boot 12 s, a full-FT online load 60 s
from the UUID drive). Only a load that FINISHED updates the history, so a load that died
on an OOM does not teach the bar that a stage is quick.
"""
import json
import os
import threading
import time
from pathlib import Path

HISTORY_PATH = Path(os.environ.get("FORGE_MODELLOAD_HISTORY",
                                   Path.home() / ".cache/latent-forge/model_load_times.json"))
PRIORS = {"free": 1.0, "base model": 15.0, "adapter": 5.0, "full finetune": 60.0,
          "adapter slots": 5.0}

_lock = threading.Lock()
_state = None
_history: dict[tuple[str, str], float] = {}   # (target, stage) -> seconds, last measured
_loaded = False


def _load_history() -> None:
    global _loaded
    if _loaded:
        return
    _loaded = True
    try:
        for k, v in json.loads(HISTORY_PATH.read_text()).items():
            tgt, _, st = k.partition("|")
            _history.setdefault((tgt, st), float(v))
    except (OSError, ValueError):
        pass


def _save_history() -> None:
    try:
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        HISTORY_PATH.write_text(json.dumps({f"{t}|{s}": round(v, 2) for (t, s), v in _history.items()},
                                           indent=1, sort_keys=True))
    except OSError:
        pass   # a read-only cache dir costs the ETA after a restart, never the load


def _expected(target: str, stage: str):
    return _history.get((target, stage), PRIORS.get(stage))


def begin(target: str, stages: list[str]) -> None:
    global _state
    with _lock:
        _load_history()
        # Expectations are frozen here: the bar must not change its total halfway through.
        _state = {"target": str(target), "stages": list(stages), "index": -1, "t0": time.time(),
                  "stage_t0": time.time(), "measured": {},
                  "expected": [_expected(str(target), s) for s in stages]}
    stage(stages[0])


def stage(label: str) -> None:
    with _lock:
        if _state is None:
            return
        now = time.time()
        _close_stage(now)
        st = _state["stages"]
        _state["index"] = st.index(label) if label in st else _state["index"] + 1
        _state["stage_t0"] = now


def _close_stage(now: float) -> None:
    i = _state["index"]
    if 0 <= i < len(_state["stages"]):
        _state["measured"][_state["stages"][i]] = now - _state["stage_t0"]


def end(ok: bool = True) -> None:
    global _state
    with _lock:
        if _state is not None and ok:
            _close_stage(time.time())
            for s, v in _state["measured"].items():
                _history[(_state["target"], s)] = v
            _save_history()
        _state = None


def snapshot(now: float | None = None):
    with _lock:
        if _state is None:
            return None
        now = time.time() if now is None else now
        st, i, tgt = _state["stages"], _state["index"], _state["target"]
        label = st[i] if 0 <= i < len(st) else ""
        expected = _state["expected"]
        stage_elapsed = now - _state["stage_t0"]
        elapsed = now - _state["t0"]
        fraction = eta = None
        if all(e is not None for e in expected) and sum(expected) > 0:
            # Finished stages count in full; the running one is capped just below its end, so
            # a slower-than-expected load stalls at the stage boundary instead of reading done.
            done = sum(expected[:i]) + min(stage_elapsed, 0.95 * expected[i])
            fraction = round(min(0.99, done / sum(expected)), 3)
            # Remaining = the rest of this stage (0 once over time) plus the stages after it.
            eta = round(max(0.0, expected[i] - stage_elapsed) + sum(expected[i + 1:]), 1)
        return {"target": tgt, "stage": label, "stage_index": i + 1, "stage_count": len(st),
                "elapsed_sec": round(elapsed, 1),
                "expected_sec": round(sum(expected), 1) if fraction is not None else None,
                "eta_sec": eta, "fraction": fraction}
