"""FIFO job queue with one worker thread (spec §6.2). Runners take the GPU lock themselves."""
import itertools
import json
import os
import re
import threading
import time
import traceback
from collections import deque


class QueueFull(Exception):
    pass


class UnknownOp(Exception):
    pass


class CannotCancel(Exception):
    pass


_TERMINAL = ("done", "error", "cancelled")
_JID_RE = re.compile(r"^forge-[0-9]{8}-[0-9]{6}-[0-9]+$")


class JobQueue:
    def __init__(self, runners, max_pending=4, history=200, log=None, archive_dir=None):
        # archive_dir: a callable returning a Path (or None). Finished records are written there so
        # GET /forge/jobs/{id} -- USE SETTINGS reads the payload through it -- still answers after a
        # server restart or the 200-record trim; history entries outlive both (review 2026-10-01).
        self._archive_dir = archive_dir
        self._runners = dict(runners)
        self._max = int(max_pending)
        self._history = int(history)
        self._log = log or (lambda msg: None)
        self._jobs = {}
        self._order = []
        self._queue = deque()
        self._running = None
        self._cv = threading.Condition()
        self._counter = itertools.count(1)
        self._stop = False
        self._thread = threading.Thread(target=self._loop, name="forge-jobs", daemon=True)
        self._thread.start()

    def set_runner(self, op, fn):
        with self._cv:
            self._runners[op] = fn

    def ops(self):
        with self._cv:
            return sorted(self._runners)

    def submit(self, op, payload):
        with self._cv:
            if op not in self._runners:
                raise UnknownOp(op)
            ahead = len(self._queue) + (1 if self._running else 0)
            if ahead >= self._max:
                raise QueueFull()
            jid = f"forge-{time.strftime('%Y%m%d-%H%M%S')}-{next(self._counter)}"
            self._jobs[jid] = {"job_id": jid, "op": op, "payload": payload, "state": "queued",
                               "result": None, "error": None, "created": time.time(),
                               "started": None, "finished": None}
            self._order.append(jid)
            self._queue.append(jid)
            self._trim()
            self._cv.notify_all()
            return jid, ahead

    def _position(self, jid):
        if jid in self._queue:
            return list(self._queue).index(jid) + (1 if self._running else 0)
        return None

    def get(self, jid):
        with self._cv:
            rec = self._jobs.get(jid)
            if rec is None:
                return self._read_archive(jid)
            return {**rec, "position": self._position(jid)}

    def _archive_path(self, jid):
        d = self._archive_dir() if self._archive_dir else None
        if d is None or not _JID_RE.match(str(jid)):
            return None
        return d / f"{jid}.json"

    def _write_archive(self, rec):
        try:
            p = self._archive_path(rec["job_id"])
            if p is None:
                return
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_name(p.name + ".part")
            tmp.write_text(json.dumps(rec, default=str))
            os.replace(tmp, p)
        except Exception as e:  # noqa: BLE001 -- archiving is best-effort, never fails a job
            self._log(f"[forge] could not archive job {rec.get('job_id')}: {e}")

    def _read_archive(self, jid):
        try:
            p = self._archive_path(jid)
            if p is None or not p.is_file():
                return None
            return {**json.loads(p.read_text()), "position": None}
        except Exception:  # noqa: BLE001 -- a corrupt archive file is "no such job", not a 500
            return None

    def cancel(self, jid):
        with self._cv:
            rec = self._jobs.get(jid)
            if rec is None:
                raise KeyError(jid)
            if rec["state"] == "running":
                raise CannotCancel(jid)
            if rec["state"] == "queued":
                self._queue.remove(jid)
                rec.update(state="cancelled", finished=time.time())
            return {**rec, "position": None}

    def list(self, limit=50):
        with self._cv:
            ids = list(reversed(self._order))[: int(limit)]
            return [{k: self._jobs[j][k] for k in ("job_id", "op", "state", "created", "started", "finished")}
                    for j in ids]

    def stop(self):
        with self._cv:
            self._stop = True
            self._cv.notify_all()
        self._thread.join(timeout=5)

    def _trim(self):
        done = [j for j in self._order if self._jobs[j]["state"] in _TERMINAL]
        for j in done[: max(0, len(self._order) - self._history)]:
            self._order.remove(j)
            del self._jobs[j]

    def _loop(self):
        while True:
            with self._cv:
                while not self._queue and not self._stop:
                    self._cv.wait()
                if self._stop:
                    return
                jid = self._queue.popleft()
                rec = self._jobs[jid]
                rec.update(state="running", started=time.time())
                self._running = jid
                fn = self._runners[rec["op"]]
                payload = rec["payload"]
            try:
                result = fn(jid, payload)
                with self._cv:
                    rec.update(state="done", result=result, finished=time.time())
                self._write_archive(dict(rec))
            except Exception as e:  # noqa: BLE001 — a job failure must never kill the worker
                self._log(f"[forge] job {jid} ({rec['op']}) failed: {e}\n{traceback.format_exc()}")
                with self._cv:
                    rec.update(state="error", error=str(e), finished=time.time())
                self._write_archive(dict(rec))
            finally:
                with self._cv:
                    self._running = None
                    self._cv.notify_all()
