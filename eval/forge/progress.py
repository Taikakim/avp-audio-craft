"""Progress of the running forge job (spec §6.1 Progress). One job runs at a time."""
import threading

_lock = threading.Lock()
_state = None


def begin(job_id, op, steps_total, stage_labels=()) -> None:
    global _state
    with _lock:
        _state = {"job_id": str(job_id), "op": str(op), "stage": "", "stage_index": 0,
                  "stage_count": len(stage_labels), "step": 0, "steps": 0,
                  "steps_left_total": max(0, int(steps_total)), "steps_total": max(0, int(steps_total)),
                  "_done": 0}


def stage(index, label) -> None:
    with _lock:
        if _state is not None:
            _state.update(stage=str(label), stage_index=int(index), step=0, steps=0)


def on_step(i, steps) -> None:
    with _lock:
        if _state is None:
            return
        _state["_done"] += 1
        _state["step"] = int(i)
        _state["steps"] = int(steps)
        _state["steps_left_total"] = max(0, _state["steps_total"] - _state["_done"])


def end() -> None:
    global _state
    with _lock:
        _state = None


def snapshot():
    with _lock:
        if _state is None:
            return None
        return {k: v for k, v in _state.items() if not k.startswith("_")}
