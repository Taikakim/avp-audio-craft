"""Record real /forge responses into docs/latent-forge/contract/fixtures/<name>.json (M2 T15).

The client's recordedContract.test.ts runs against these and SKIPS while a name is missing, because a
hand-made mock that agrees with its client proves nothing. Each file is {"status": int, "body": ...}.

Run against a live server (stdlib only, any python):
    python eval/forge/record_fixtures.py [--base http://127.0.0.1:8056] [--only info,slots]

It submits four short GPU jobs (generate, a2a_clip, inpaint, commit; 8 s, few steps) and writes a
`_fixture_probe` session and LatCH preset, which the contract test expects to find listed. A job record
already on the server for the same op (e.g. one a person submitted from the GUI) is preferred over a
synthetic one: it carries the payload the real client built.
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "docs" / "latent-forge" / "contract" / "fixtures"
PROBE = "_fixture_probe"


class Client:
    def __init__(self, base):
        self.base = base.rstrip("/")

    def call(self, method, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"content-type": "application/json"} if data else {})
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                return {"status": r.status, "body": json.loads(r.read() or b"null")}
        except urllib.error.HTTPError as e:
            return {"status": e.code, "body": json.loads(e.read() or b"null")}


def save(name, fx):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(fx, indent=1) + "\n")
    print(f"  {name}.json  status {fx['status']}")


def wait_done(c, jid, timeout=900):
    t0 = time.time()
    while time.time() - t0 < timeout:
        fx = c.call("GET", f"/forge/jobs/{jid}")
        if fx["body"].get("state") in ("done", "error", "cancelled"):
            return fx
        time.sleep(0.5)
    raise RuntimeError(f"job {jid} did not finish in {timeout}s")


def existing_done(c, op):
    for j in c.call("GET", "/forge/jobs?limit=50")["body"].get("jobs", []):
        if j.get("op") == op and j.get("state") == "done":
            return c.call("GET", f"/forge/jobs/{j['job_id']}")
    return None


def run_job(c, op, payload, record_submit=False, record_busy=False):
    sub = c.call("POST", "/forge/jobs", {"op": op, "payload": payload})
    if sub["status"] != 202:
        raise RuntimeError(f"{op} submit refused: {sub}")
    if record_submit:
        save("forge_job_submit", sub)
    if record_busy:
        # /status reports busy only while the model is sampling; poll until we catch it.
        t0 = time.time()
        while time.time() - t0 < 120:
            st = c.call("GET", "/status")
            if st["body"].get("busy"):
                save("status_busy", st)
                break
            time.sleep(0.1)
        else:
            print("  status_busy: never caught the server busy (job too short?)")
    done = wait_done(c, sub["body"]["job_id"])
    if done["body"]["state"] != "done":
        raise RuntimeError(f"{op} failed: {done['body'].get('error')}")
    return done


def render_ref(done):
    r = done["body"]["result"]
    return {"kind": "render", "job_id": r["job_id"], "file": r["urls"][0].split("/")[-1]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8056")
    ap.add_argument("--only", default="", help="comma-separated fixture groups: get,store,jobs")
    a = ap.parse_args()
    groups = set(a.only.split(",")) if a.only else {"get", "store", "jobs"}
    c = Client(a.base)

    if "get" in groups:
        print("GET routes")
        for name, path in [("info", "/info"), ("slots", "/slots"),
                           ("models_adapters", "/models?family=adapter&loadable=1"),
                           ("models_control_adapters", "/models?family=control_adapter"),
                           ("forge_files_crops", "/forge/files?root=crops&limit=5"),
                           ("forge_files_renders", "/forge/files?root=renders&limit=5")]:
            save(name, c.call("GET", path))

    if "store" in groups:
        print("sessions and presets (writes the _fixture_probe entries)")
        sessions = c.call("GET", "/forge/sessions")["body"].get("sessions", [])
        real = next((s["name"] for s in sessions if s["name"] != PROBE), None)
        project = c.call("GET", f"/forge/sessions/{real}")["body"] if real else {"version": 2, "clips": []}
        put = c.call("PUT", f"/forge/sessions/{PROBE}", project)
        if put["status"] != 200:
            raise RuntimeError(f"session PUT refused: {put}")
        save("forge_sessions_list", c.call("GET", "/forge/sessions"))
        save("forge_session_get", c.call("GET", f"/forge/sessions/{PROBE}"))
        put = c.call("PUT", f"/forge/presets/latch/{PROBE}", {"latch_on": False})
        if put["status"] != 200:
            raise RuntimeError(f"preset PUT refused: {put}")
        save("forge_presets_latch_list", c.call("GET", "/forge/presets/latch"))
        save("forge_preset_latch_get", c.call("GET", f"/forge/presets/latch/{PROBE}"))

    if "jobs" in groups:
        print("jobs (short GPU renders)")
        defaults = c.call("GET", "/forge/backbone")["body"].get("defaults") or {"steps": 8, "cfg_scale": 6.0}
        render = {"prompt": "driving psytrance, rolling bassline, acid lead", "negative_prompt": "",
                  "steps": min(int(defaults["steps"]), 8), "cfg_scale": float(defaults["cfg_scale"]),
                  "seed": 7, "apg_scale": 1, "cfg_interval_progress": [0, 1],
                  "scale_phi": 0}
        save("forge_error_cap", c.call("POST", "/forge/jobs",
                                       {"op": "generate", "payload": {**render, "duration": 300}}))
        gen = run_job(c, "generate", {**render, "duration": 8}, record_submit=True, record_busy=True)
        save("forge_job_generate_done", existing_done(c, "generate") or gen)
        ref = render_ref(gen)
        save("forge_job_a2a_clip_done", existing_done(c, "a2a_clip") or run_job(
            c, "a2a_clip", {"audio": ref, "render": render, "noise_level": 0.5, "chain": None}))
        side = {"audio": ref, "offset_sec": 0.0, "dur_sec": 8.0}
        save("forge_job_inpaint_done", existing_done(c, "inpaint") or run_job(
            c, "inpaint", {"a": {**side, "start_sec": 0.0}, "b": {**side, "start_sec": 6.0},
                           "region": {"start_sec": 6.0, "end_sec": 8.0}, "pad_sec": 2.0,
                           "curve": {"points": [0, 0.35, 0.7, 1], "curves": [0, 0, 0]}, "chroma_xfade": False, "render": render}))
        commit = existing_done(c, "commit")
        if commit is None:
            print("  forge_job_commit_done: no commit on the server; press MIXDOWN in the GUI, then rerun "
                  "with --only jobs (a commit payload is the whole project, which only the client builds)")
        else:
            save("forge_job_commit_done", commit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
