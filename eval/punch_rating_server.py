#!/usr/bin/env python3
# Owner: GHOST-NOTE (created 2026-10-14)
"""punch_rating_server.py -- rate "did the steering improve the overall sound?" 1-5 on many seeds, and request new clips with other control weights.

WHY (Kim 2026-10-14): outcomes differ so much between seeds that two seeds prove nothing; he wants a set of ~64 seeds and his own rating per clip
(1 = worsening, 3 = neutral, 5 = marked improvement of the overall sound quality), and the page connected to the render server so he can request new clips
with different adapter weights that join the rateable list. His criteria (memory steering-improvement-criteria): improvement = less coarseness + the missing
bass, "a rounding of the sound to a more balanced whole"; a louder / more compressed result is NOT an improvement -> the steered clip is played LEVEL-MATCHED
to the original by default (raw is one click away), and loudness / crest / centroid deltas are shown beside it.

One process, three jobs:  (1) serves the page and the wav clips  (2) stores ratings (ratings.jsonl, append-only, latest per id wins)
(3) forwards "new clip" requests to the render server :8056 /generate (replaying a punch preset with a new seed, latch-gain scale and/or DoRA strength).
The render server must be running for (3): eval/forge/dev_server.sh start <HANDLE>  (it holds the GPU lock as kind=server). Ratings work without it.

    SAO/.venv/bin/python eval/punch_rating_server.py --batch 64       # render the initial set (needs the render server up), then
    SAO/.venv/bin/python eval/punch_rating_server.py                  # serve http://localhost:8058
Data: /run/media/kim/Mantu2/sa3_control_runs/punch_rating_20261014/  (clips/*.wav, manifest.json, ratings.jsonl, presets.json)
Latch weights: rho = 0.7 x gain of slot 0, mu = 0.6 x gain of slot 0 (read off every punch job); a latch-scale s multiplies all slot gains AND rho, mu.
"""
import argparse
import json
import os
import shutil
import threading
import time
import urllib.request

import numpy as np
import soundfile as sf

DATA = "/run/media/kim/Mantu2/sa3_control_runs/punch_rating_20261014"
CLIPS = f"{DATA}/clips"
RENDER = "http://localhost:8056"
PUNCH = "/home/kim/Music/latch/combo/punch/"
PRESET_JOBS = {"cleanest": "cleanest-20261009-143711-gen", "beefier2": "beefier2-20261009-142214-gen", "beefiest": "beefiest-20261009-142440-gen",
               "beefiest2": "beefiest2-20261009-142514-gen"}
BASE_JOB = "base-for-beefiest2-20261009-142544-gen"
LOCK = threading.Lock()


def load_presets():
    p = f"{DATA}/presets.json"
    if not os.path.exists(p):
        os.makedirs(DATA, exist_ok=True)
        out = {}
        for k, j in PRESET_JOBS.items():
            out[k] = json.load(open(f"{PUNCH}{j}/result.json"))["meta"]["params_echo"]
        out["_base"] = json.load(open(f"{PUNCH}{BASE_JOB}/result.json"))["meta"]["params_echo"]
        json.dump(out, open(p, "w"), indent=1)
    return json.load(open(p))


def post(body, timeout=1800):
    rq = urllib.request.Request(f"{RENDER}/generate", json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(rq, timeout=timeout))


def render_up():
    try:
        return bool(json.load(urllib.request.urlopen(f"{RENDER}/status", timeout=3)).get("ok"))
    except Exception:
        return False


def stats(x, sr):
    m = x.mean(1) if x.ndim > 1 else x
    rms = float(np.sqrt((m ** 2).mean()) + 1e-12)
    S = np.abs(np.fft.rfft(m[: len(m) // 4096 * 4096].reshape(-1, 4096) * np.hanning(4096), axis=1))
    f = np.fft.rfftfreq(4096, 1 / sr)
    cen = float(((f * S).sum(1) / (S.sum(1) + 1e-9)).mean())
    flat = float(np.exp(np.log(S + 1e-9).mean(1)).mean() / (S.mean(1) + 1e-9).mean())
    return {"rms_db": 20 * np.log10(rms), "crest": float(np.abs(m).max() / rms), "centroid": cen, "flat": flat}


def body(presets, preset, seed, latch_scale, dora_strength, steps, steered):
    b = json.loads(json.dumps(presets[preset] if steered else presets["_base"]))
    b["seed"] = int(seed)
    if steps:
        b["steps"] = int(steps)
    if dora_strength is not None and b.get("dora"):
        b["dora"]["strength"] = float(dora_strength)
    if steered and latch_scale != 1.0:
        for s in b.get("latch") or []:
            s["gain"] = s["gain"] * latch_scale
        for k in ("rho", "mu"):
            if b.get(k) is not None:
                b[k] = b[k] * latch_scale
    return b


def make_pair(seed, preset="cleanest", latch_scale=1.0, dora_strength=None, steps=None, source="batch"):
    presets = load_presets()
    os.makedirs(CLIPS, exist_ok=True)
    ds = dora_strength if dora_strength is not None else (presets["_base"].get("dora") or {}).get("strength")
    st = steps or presets[preset]["steps"]
    eid = f"s{int(seed)}_{preset}_x{latch_scale:g}_d{ds:g}_n{st}"
    with LOCK:
        man = json.load(open(f"{DATA}/manifest.json")) if os.path.exists(f"{DATA}/manifest.json") else {"entries": []}
        if any(e["id"] == eid for e in man["entries"]):
            return next(e for e in man["entries"] if e["id"] == eid)
    bid = f"base_s{int(seed)}_d{ds:g}_n{st}"
    bpath = f"{CLIPS}/{bid}.wav"
    if not os.path.exists(bpath):
        r = post(body(presets, preset, seed, 1.0, ds, st, False))
        shutil.copy(r["files"][0], bpath)
    sp = f"{CLIPS}/{eid}__steered.wav"
    r = post(body(presets, preset, seed, latch_scale, ds, st, True))
    shutil.copy(r["files"][0], sp)
    xb, sr = sf.read(bpath, dtype="float32")
    xs, _ = sf.read(sp, dtype="float32")
    sb, ss = stats(xb, sr), stats(xs, sr)
    g = 10 ** ((sb["rms_db"] - ss["rms_db"]) / 20)
    pk = float(np.abs(xs).max()) * g
    if pk > 0.97:
        g *= 0.97 / pk
    mp = f"{CLIPS}/{eid}__steered_matched.wav"
    sf.write(mp, xs * g, sr, subtype="PCM_16")
    e = {"id": eid, "seed": int(seed), "preset": preset, "latch_scale": latch_scale, "dora_strength": ds, "steps": st, "source": source, "created": time.strftime("%Y-%m-%d %H:%M:%S"),
         "base": f"{bid}.wav", "steered": os.path.basename(sp), "matched": os.path.basename(mp), "match_gain_db": float(20 * np.log10(g)),
         "d_rms_db": ss["rms_db"] - sb["rms_db"], "d_crest": ss["crest"] - sb["crest"], "d_centroid": ss["centroid"] - sb["centroid"], "d_flat": ss["flat"] - sb["flat"],
         "latch": [{"head": s["head"], "gain": s["gain"] * latch_scale, "value": s["value"]} for s in (presets[preset].get("latch") or [])]}
    with LOCK:
        man = json.load(open(f"{DATA}/manifest.json")) if os.path.exists(f"{DATA}/manifest.json") else {"entries": []}
        man["entries"].append(e)
        json.dump(man, open(f"{DATA}/manifest.json", "w"), indent=1)
    return e


def ratings():
    out = {}
    p = f"{DATA}/ratings.jsonl"
    if os.path.exists(p):
        for l in open(p):
            if l.strip():
                r = json.loads(l)
                out[r["id"]] = r
    return out


def serve(port):
    import uvicorn
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import FileResponse, HTMLResponse
    app = FastAPI()
    page = os.path.join(os.path.dirname(os.path.abspath(__file__)), "punch_rating_page.html")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return open(page).read()

    @app.get("/api/state")
    def state():
        man = json.load(open(f"{DATA}/manifest.json")) if os.path.exists(f"{DATA}/manifest.json") else {"entries": []}
        mp = f"{DATA}/metrics.json"
        met = json.load(open(mp)) if os.path.exists(mp) else {}
        for e in man["entries"]:
            if e["id"] in met:
                e["m"] = met[e["id"]]["delta"]
        return {"entries": man["entries"], "ratings": ratings(), "render_up": render_up(), "presets": [k for k in load_presets() if not k.startswith("_")]}

    @app.get("/clips/{name}")
    def clip(name: str):
        p = os.path.join(CLIPS, os.path.basename(name))
        if not os.path.exists(p):
            raise HTTPException(404)
        return FileResponse(p, media_type="audio/wav")

    @app.post("/api/rate")
    async def rate(request: Request):
        r = await request.json()
        if r.get("rating") not in (1, 2, 3, 4, 5):
            raise HTTPException(400, "rating must be 1-5")
        row = {"id": r["id"], "rating": r["rating"], "heard": r.get("heard", "matched"), "note": r.get("note", ""), "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
        with LOCK:
            open(f"{DATA}/ratings.jsonl", "a").write(json.dumps(row) + "\n")
        return row

    @app.post("/api/request")
    def request_clip(r: dict):
        if not render_up():
            raise HTTPException(503, "render server :8056 is not running: eval/forge/dev_server.sh start GHOST-NOTE")
        try:
            return make_pair(int(r.get("seed", -1)) if int(r.get("seed", -1)) >= 0 else int(time.time()) % 100000, r.get("preset", "cleanest"),
                             float(r.get("latch_scale", 1.0)), r.get("dora_strength"), r.get("steps"), source="requested")
        except Exception as ex:
            raise HTTPException(500, str(ex)[:300])

    @app.get("/api/export")
    def export():
        return FileResponse(f"{DATA}/ratings.jsonl", media_type="text/plain")

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=0, help="render this many seeds (764 and 1337 first) with the 'cleanest' preset")
    ap.add_argument("--preset", default="cleanest")
    ap.add_argument("--port", type=int, default=8058)
    a = ap.parse_args()
    if a.batch:
        seeds = [764, 1337] + list(range(3001, 3001 + a.batch - 2))
        for i, s in enumerate(seeds):
            t0 = time.time()
            e = make_pair(s, a.preset)
            print(f"[{i + 1}/{len(seeds)}] seed {s}  d_rms {e['d_rms_db']:+.1f} dB  d_crest {e['d_crest']:+.2f}  ({time.time() - t0:.0f}s)", flush=True)
        json.dump({"purpose": "64 seeds of the punch DoRA render, original vs bass+body RMS steering ('cleanest' preset), for Kim's 1-5 ratings of the improvement in overall sound quality (2026-10-14).",
                   "hypothesis": "Steering rounds the sound (less coarseness, bass restored) at most seeds; seed 764 and 1337 looked very different.",
                   "recipe": {"preset": a.preset, "prompt": load_presets()['_base']['prompt'] if 'prompt' in load_presets()['_base'] else 'see presets.json', "steps": 30}, "result": None, "kim_feedback": None},
                  open(f"{DATA}/run_meta.json", "w"), indent=1)
        print("BATCH DONE")
    else:
        serve(a.port)
