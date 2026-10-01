import threading
import time

import pytest

import forge_testutil  # noqa: F401
from forge.jobs import CannotCancel, JobQueue, QueueFull, UnknownOp


def wait_state(q, jid, states, timeout=5.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        rec = q.get(jid)
        if rec and rec["state"] in states:
            return rec
        time.sleep(0.01)
    raise AssertionError(f"{jid} never reached {states}: {q.get(jid)}")


def test_runs_and_returns_result():
    q = JobQueue({"echo": lambda jid, p: {"job_id": jid, "x": p["x"]}})
    jid, ahead = q.submit("echo", {"x": 3})
    assert jid.startswith("forge-") and ahead == 0
    rec = wait_state(q, jid, {"done"})
    assert rec["result"] == {"job_id": jid, "x": 3}
    assert rec["error"] is None and rec["started"] and rec["finished"] and rec["position"] is None
    assert rec["payload"] == {"x": 3}
    q.stop()


def test_error_state():
    def boom(jid, p):
        raise ValueError("nope")
    logged = []
    q = JobQueue({"boom": boom}, log=logged.append)
    jid, _ = q.submit("boom", {})
    rec = wait_state(q, jid, {"error"})
    assert rec["error"] == "nope" and rec["result"] is None
    assert any("nope" in line for line in logged)
    q.stop()


def test_unknown_op():
    q = JobQueue({})
    with pytest.raises(UnknownOp):
        q.submit("x", {})
    q.stop()


def test_queue_full_positions_and_cancel():
    gate = threading.Event()
    q = JobQueue({"slow": lambda jid, p: (gate.wait(5), {"ok": True})[1]}, max_pending=4)
    first, _ = q.submit("slow", {})
    wait_state(q, first, {"running"})
    queued = [q.submit("slow", {"n": i}) for i in range(3)]
    assert [ahead for _, ahead in queued] == [1, 2, 3]
    assert q.get(queued[2][0])["position"] == 3
    with pytest.raises(QueueFull):
        q.submit("slow", {})
    with pytest.raises(CannotCancel):
        q.cancel(first)
    rec = q.cancel(queued[0][0])
    assert rec["state"] == "cancelled"
    assert q.get(queued[2][0])["position"] == 2
    gate.set()
    wait_state(q, queued[2][0], {"done"})
    assert q.get(queued[0][0])["state"] == "cancelled"
    listed = q.list(10)
    assert listed[0]["job_id"] == queued[2][0]            # newest first
    assert "payload" not in listed[0] and "result" not in listed[0]
    q.stop()
