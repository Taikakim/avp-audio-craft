#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-15)
"""latch_film_e8.py -- EXPERIMENTS E8: timestep-gated FiLM (full strength early, faded out for the low-noise tail),
optionally with alpha-weighted LatCH late.

WHY. FiLM has density range but leaks the training-set style; rhythm/layout is committed at high noise, timbre and
character at low noise. If FiLM acts only while sigma is high, it should set the density and leave the character to
the base model. Kill (E8 spec): CLAP drift unchanged at matched density -> the leak is not where the gate cuts.
The gate list also says WHERE in the schedule the leak enters.

Client of :8056 (server film payload gains sigma_min / sigma_max / fade -- eval/film_schedule.py). Same contexts,
seeds and unguided renders as E7 (eval/latch_film_combo_e7.py), so E7's FiLM-only cells are this test's ungated
(sigma_min 0) arm and drift is measured against E7's base renders. Contexts: base (psytrance) and house (far from
goa, where the leak should show). Grid per context x seed: FiLM gain {1.0, 1.75} x gate sigma_min {0.8, 0.6, 0.4}
(FiLM on for sigma >= gate, linear fade over 0.1 below it) x density {3, 6, 9}; plus FiLM 1.75 gated at 0.6 +
LatCH 512 (alpha 0-1, the transparent setting) x density.
Output: Mantu2/sa3_control_runs/latch_film_e8_20261015/<ctx>/<id>.wav, cells.jsonl, clap.json, run_meta.json.
RUN: SAO/.venv/bin/python eval/latch_film_e8.py render ; sat-venv python eval/latch_film_e8.py clap
"""
import argparse
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import latch_film_combo_e7 as e7  # noqa: E402

OUT = "/run/media/kim/Mantu2/sa3_control_runs/latch_film_e8_20261015"
CTXS = ("base", "house")
FILM_GAINS = (1.0, 1.75)
GATES = (0.8, 0.6, 0.4)
FADE = 0.1
DENSITIES = e7.DENSITIES


def cells():
    out = []
    for ctx in CTXS:
        for s in e7.CONTEXTS[ctx]["seeds"]:
            for fg in FILM_GAINS:
                for gt in GATES:
                    for d in DENSITIES:
                        out.append(dict(ctx=ctx, seed=s, film=fg, gate=gt, latch=0, dens=d,
                                        id=f"{ctx}_s{s}__film{fg:g}_gate{gt:g}_d{d}"))
            for d in DENSITIES:
                out.append(dict(ctx=ctx, seed=s, film=1.75, gate=0.6, latch=512, dens=d,
                                id=f"{ctx}_s{s}__film1.75_gate0.6_latch512_d{d}"))
    return out


def payload(c, film_ckpt):
    p = e7.payload({**c, "film": c["film"], "latch": c["latch"]}, film_ckpt)
    p["film"].update({"sigma_min": float(c["gate"]), "sigma_max": 1.0, "fade": FADE})
    return p


def render(a):
    import librosa
    import requests
    jl = f"{OUT}/cells.jsonl"
    done = {json.loads(l)["id"] for l in open(jl) if l.strip()} if os.path.exists(jl) else set()
    todo = [c for c in cells() if c["id"] not in done]
    print(f"[e8] {len(todo)} cells to render ({len(done)} done)", flush=True)
    if a.dry:
        return 0
    info = requests.get(f"{e7.SERVER}/info", timeout=10).json()
    if not info.get("film_schedule"):
        sys.exit("[e8] the running :8056 predates the FiLM gain schedule (no /info film_schedule) -- it would ignore "
                 "the gate silently. Restart the server, then re-run.")
    film_ckpt = (info.get("film_default") or {}).get("ckpt")
    os.makedirs(OUT, exist_ok=True)
    if not os.path.exists(f"{OUT}/run_meta.json"):
        json.dump({"purpose": __doc__.split("Client of")[0].strip(),
                   "hypothesis": "FiLM gated to the high-noise steps keeps most of its density range at clearly lower CLAP drift than ungated FiLM (E7 FiLM-only cells).",
                   "kill": "drift unchanged at matched density",
                   "contexts": {k: dict(e7.CONTEXTS[k]) for k in CTXS},
                   "grid": {"film_gain": FILM_GAINS, "gate_sigma_min": GATES, "fade": FADE, "density": DENSITIES,
                            "plus": "film 1.75 gate 0.6 + LatCH 512 alpha 0-1"},
                   "heads": {"latch": e7.HEAD, "film": film_ckpt},
                   "reference": "E7 run (latch_film_combo_e7_20261015): ungated FiLM-only cells + unguided base renders",
                   "related": ["EXPERIMENTS E8", "eval/film_schedule.py", "eval/tests/test_film_schedule.py"],
                   "result": None, "kim_feedback": None}, open(f"{OUT}/run_meta.json", "w"), indent=1)
    for c in todo:
        t0 = time.time()
        while True:
            try:
                r = requests.post(f"{e7.SERVER}/generate", json=payload(c, film_ckpt), timeout=1800)
                break
            except requests.exceptions.ConnectionError:
                print(f"  {time.strftime('%H:%M')} server unreachable, retrying in 120 s", flush=True)
                time.sleep(120)
        res = r.json()
        if r.status_code != 200 or res.get("status") != "ok" or not res.get("files"):
            print(f"  FAIL {c['id']}: {r.status_code} {str(res)[:300]}", flush=True)
            continue
        os.makedirs(f"{OUT}/{c['ctx']}", exist_ok=True)
        dst = f"{OUT}/{c['ctx']}/{c['id']}.wav"
        shutil.copyfile(res["files"][0], dst)
        y, sr = librosa.load(dst, sr=None, mono=True)
        c.update(onsets=round(len(librosa.onset.onset_detect(y=y, sr=sr, units="time")) / (len(y) / sr), 3),
                 secs=round(time.time() - t0, 1))
        with open(jl, "a") as f:
            f.write(json.dumps(c) + "\n")
        print(f"  {c['id']}: {c['onsets']} on/s ({c['secs']}s)", flush=True)
    print("DONE", flush=True)
    return 0


def clap(a):
    """Drift vs E7's unguided base render of the same context + seed (same CLAP model as E7)."""
    emb = e7.clap_embedder()
    rows = [json.loads(l) for l in open(f"{OUT}/cells.jsonl") if l.strip()]
    base = {}
    for ctx in CTXS:
        for s in e7.CONTEXTS[ctx]["seeds"]:
            p = f"{e7.OUT}/{ctx}/{ctx}_s{s}__base.wav"
            if os.path.exists(p):
                base[(ctx, s)] = emb(p)
    drift = {c["id"]: round(float(1 - emb(f"{OUT}/{c['ctx']}/{c['id']}.wav") @ base[(c["ctx"], c["seed"])]), 4)
             for c in rows if (c["ctx"], c["seed"]) in base}
    json.dump({"drift": drift, "meaning": "1 - cosine(CLAP audio emb, E7's unguided base of the same context+seed)"},
              open(f"{OUT}/clap.json", "w"), indent=1)
    print(f"[e8] clap: {len(drift)} drifts")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=("render", "clap"))
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    return render(a) if a.step == "render" else clap(a)


if __name__ == "__main__":
    sys.exit(main())
