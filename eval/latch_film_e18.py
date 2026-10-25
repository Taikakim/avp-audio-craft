#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-25)
"""latch_film_e18.py -- EXPERIMENTS E18: smooth hand-off schedule, FiLM early -> crossfade -> LatCH -> exp fade to unguided.

WHY. In the GUI, LatCH guidance that switches off suddenly sounds bad. Under the default alpha weighting a LatCH window's
per-step weight RISES toward its end, so a hard end_pct < 1 stops the guide at its strongest step. The proposal: FiLM
(wide range) for the first ~20% of steps, crossfade into LatCH (transparent), LatCH to ~80%, then an exponential fade
to plain sampling. Kill (E18): (4) not better than (5) on range vs drift AND (3) does not remove the step that (2) has.
If only (3) helps, the finding is "taper the window" and the FiLM hand-over is not needed.

Arms per context x seed x density {3, 6, 9} (all LatCH at gain 512 on the E7 onset head, FiLM at gain 1.0, 50 steps):
  film      FiLM only, constant (positive control)
  A1        LatCH window 0-1, alpha (the clean reference)
  A2        LatCH 0-0.8, hard end (reproduces the sudden off)
  A3        LatCH 0-1 with an exp fade over 0.8-1 (= A2's weights up to 0.8 plus a tail; plateau normalisation)
  A4a/A4b   FiLM full 0-0.2, crossfade 0.2-0.4 (linear / raised-cosine) into LatCH, LatCH 0.4-0.8, exp fade 0.8-1
  A4c       no LatCH plateau: FiLM full 0-0.2, raised-cosine crossfade over 0.2-0.8, exp fade 0.8-1
  A5        FiLM 1.0 + LatCH 512, constant, full window (the E7 incumbent)
plus one unguided render per context x seed (the drift reference) and arm 6 per context x seed: LatCH 512 0-1 with a
real crop's onsets-per-beat curve (target_raw) vs a constant at that curve's mean.
Notes: the hand-off happens in DENOISING time, not audio time, so there is no seam at a point in the clip; what can
change is clip-wide texture (HF, flatness, CE) -> clip_metrics + the disintegration gate + a listening card, next to
density and CLAP drift. Windows in step fractions; FiLM uses the server's step window (film_schedule.step_envelope),
which is the LatCH window's envelope step for step, so a linear / cosine crossfade sums to 1 on every step. A window's
LatCH weights are normalised over its plateau (latch_guided._window_scale), so shorter plateaus (A2, A4) carry a
higher per-step weight than A1 at the same gain, as before; A4c has no plateau and is normalised over its whole window.
All renders on the biggoa DoRA finetune (standing default for LatCH evals); E7 used the base model.
RUN: SAO/.venv/bin/python eval/latch_film_e18.py render   (server :8056 up with the E18 fades: /info "fades")
     sat-venv python eval/latch_film_e18.py clap           (CPU)
"""
import argparse
import glob
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import latch_film_combo_e7 as e7  # noqa: E402

OUT = "/run/media/kim/Mantu/sa3_control_runs/latch_film_e18_20261025"
FT = ("/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/runs/subloss_k24/subloss_k24_biggoa_t512_bf16_s1/"
      "epoch=63-step=12480.ckpt")
BIGSET = "/run/media/kim/Kosmos/latents/latents_goa_bigset"
CTXS = ("base", "house")
DENSITIES = e7.DENSITIES
LG, FG = 512.0, 1.0
FPS = 44100 / 4096

# per arm: FiLM dict (None = off; {} = constant) and LatCH window dict (None = off)
ARMS = {
    "film": ({}, None),
    "A1": (None, dict(start_pct=0.0, end_pct=1.0)),
    "A2": (None, dict(start_pct=0.0, end_pct=0.8)),
    "A3": (None, dict(start_pct=0.0, end_pct=1.0, fade_out_pct=0.2, fade_shape="exp")),
    "A4a": (dict(start_pct=0.0, end_pct=0.4, fade_out_pct=0.2, fade_shape="linear"),
            dict(start_pct=0.2, end_pct=1.0, fade_in_pct=0.2, fade_out_pct=0.2, fade_shape="linear")),
    "A4b": (dict(start_pct=0.0, end_pct=0.4, fade_out_pct=0.2, fade_shape="cosine"),
            dict(start_pct=0.2, end_pct=1.0, fade_in_pct=0.2, fade_out_pct=0.2, fade_shape="cosine")),
    "A4c": (dict(start_pct=0.0, end_pct=0.8, fade_out_pct=0.6, fade_shape="cosine"),
            dict(start_pct=0.2, end_pct=1.0, fade_in_pct=0.6, fade_out_pct=0.2, fade_shape="cosine")),
    "A5": ({}, dict(start_pct=0.0, end_pct=1.0)),
}


def real_curve(seconds):
    """The most varied `seconds`-long window of onsets-per-beat among the first 400 bigset crops (deterministic), among
    windows that stay inside the range the constant arms ask for (<= 4 onsets/beat, ~9.3 onsets/s at 140 BPM): the
    unconstrained pick ran 0.6-8 per beat, a glitch section far outside what the head was asked anywhere else; and never
    below 0.5 per beat (the next pick was a track fading to silence at a crop end)."""
    import numpy as np
    n = int(round(seconds * FPS))
    best = None
    for p in sorted(glob.glob(f"{BIGSET}/*.TIMESERIES.npz"))[:400]:
        z = np.load(p)
        v, ok = z["onset_per_beat_ts"], z["valid_ts"] > 0.5
        for a in range(0, int(ok.sum()) - n, n // 2):
            w = v[a:a + n]
            # inside the range, never near-silent (the next best pick was a track fading out at a crop end)
            if w.max() > 4.0 or w.min() < 0.5:
                continue
            if best is None or w.std() > best[0]:
                best = (float(w.std()), os.path.basename(p), a, w.astype(float).tolist())
    return {"crop": best[1], "start_frame": best[2], "std": round(best[0], 4), "curve": best[3]}


def cells():
    out = []
    for ctx in CTXS:
        for s in e7.CONTEXTS[ctx]["seeds"]:
            out.append(dict(ctx=ctx, seed=s, arm="unguided", dens=None, id=f"{ctx}_s{s}__unguided"))
            for arm in ARMS:
                for d in DENSITIES:
                    out.append(dict(ctx=ctx, seed=s, arm=arm, dens=d, id=f"{ctx}_s{s}__{arm}_d{d}"))
            for arm in ("A6curve", "A6const"):
                out.append(dict(ctx=ctx, seed=s, arm=arm, dens=None, id=f"{ctx}_s{s}__{arm}"))
    return out


def payload(c, film_ckpt, curve):
    C = e7.CONTEXTS[c["ctx"]]
    p = {"prompt": C["prompt"], "duration": C["duration"], "steps": C["steps"], "cfg_scale": C["cfg"],
         "seed": c["seed"], "sampler_type": "euler", "apg_scale": 1.0, "dora": {"ckpt_path": FT, "strength": 1.0}}
    if c["arm"] == "unguided":
        return p
    slot = {"path": e7.HEAD, "head": "onset_per_beat_e04ema", "gain": LG}
    if c["arm"] in ("A6curve", "A6const"):
        slot.update(start_pct=0.0, end_pct=1.0)
        if c["arm"] == "A6curve":
            slot["target_raw"] = [curve["curve"]]
        else:
            slot.update(kind="constant", value=sum(curve["curve"]) / len(curve["curve"]))
        p["latch"] = [slot]
        return p
    film, win = ARMS[c["arm"]]
    if film is not None:
        p["film"] = {"ckpt": film_ckpt, "value": float(c["dens"]), "gain": FG, **film}
        if film:
            p["film"]["steps"] = C["steps"]
    if win is not None:
        p["latch"] = [{**slot, "kind": "constant", "value": c["dens"] * 60.0 / C["bpm"], **win}]
    return p


def render(a):
    import librosa
    import requests
    jl = f"{OUT}/cells.jsonl"
    done = {json.loads(l)["id"] for l in open(jl) if l.strip()} if os.path.exists(jl) else set()
    todo = [c for c in cells() if c["id"] not in done]
    print(f"[e18] {len(todo)} cells to render ({len(done)} done)", flush=True)
    os.makedirs(OUT, exist_ok=True)
    cpath = f"{OUT}/real_curve.json"
    if not os.path.exists(cpath):
        json.dump(real_curve(e7.CONTEXTS["base"]["duration"]), open(cpath, "w"))
    curve = json.load(open(cpath))
    if a.dry:
        for c in todo[:12]:
            print(c["id"], json.dumps(payload(c, "<film>", curve))[:400])
        return 0
    info = requests.get(f"{e7.SERVER}/info", timeout=10).json()
    if not info.get("fades"):
        sys.exit("[e18] the running :8056 predates the E18 fades (no /info 'fades') -- it would ignore the fade keys "
                 "silently. Restart the server, then re-run.")
    film_ckpt = (info.get("film_default") or {}).get("ckpt")
    if not os.path.exists(f"{OUT}/run_meta.json"):
        json.dump({"purpose": __doc__.split("RUN:")[0].strip(),
                   "hypothesis": "A tapered end (A3) removes the texture change of a hard LatCH stop (A2); the full hand-off "
                                 "(A4) reaches FiLM-like density range at less CLAP drift than the constant FiLM+LatCH "
                                 "incumbent (A5).",
                   "kill": "A4 not better than A5 on range vs drift AND A3 does not remove the step A2 has -> the hand-off "
                           "is not needed; if only A3 helps, the finding is 'taper the window'.",
                   "arms": {k: {"film": v[0], "latch": v[1]} for k, v in ARMS.items()},
                   "gains": {"latch": LG, "film": FG}, "densities": DENSITIES,
                   "contexts": {k: dict(e7.CONTEXTS[k]) for k in CTXS}, "finetune": FT,
                   "heads": {"latch": e7.HEAD, "film": film_ckpt},
                   "arm6": {k: v for k, v in curve.items() if k != "curve"},
                   "related": ["EXPERIMENTS E18", "eval/film_schedule.py (step_envelope)",
                               "stable_audio_3/inference/latch_guided.py (_window_scale fades)",
                               "eval/tests/test_latch_window_fades.py", "eval/tests/test_film_schedule.py",
                               "eval/latch_film_combo_e7.py (contexts, CLAP meter)"],
                   "result": None, "kim_feedback": None}, open(f"{OUT}/run_meta.json", "w"), indent=1)
    for c in todo:
        t0 = time.time()
        while True:
            try:
                r = requests.post(f"{e7.SERVER}/generate", json=payload(c, film_ckpt, curve), timeout=1800)
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
                 server_seed=res.get("seed"), warnings=res.get("warnings") or [], secs=round(time.time() - t0, 1))
        with open(jl, "a") as f:
            f.write(json.dumps(c) + "\n")
        print(f"  {c['id']}: {c['onsets']} on/s ({c['secs']}s)", flush=True)
    print("DONE", flush=True)
    return 0


def clap(a):
    """Drift = 1 - cos(CLAP) to this run's unguided render of the same context + seed; seed reference as in E7."""
    emb = e7.clap_embedder()
    rows = [json.loads(l) for l in open(f"{OUT}/cells.jsonl") if l.strip()]
    E = {c["id"]: emb(f"{OUT}/{c['ctx']}/{c['id']}.wav") for c in rows}
    base = {(c["ctx"], c["seed"]): c["id"] for c in rows if c["arm"] == "unguided"}
    drift = {c["id"]: round(float(1 - E[c["id"]] @ E[base[(c["ctx"], c["seed"])]]), 4)
             for c in rows if (c["ctx"], c["seed"]) in base}
    ref = {}
    for ctx in CTXS:
        ids = [v for (cx, _), v in base.items() if cx == ctx]
        if len(ids) == 2:
            ref[ctx] = round(float(1 - E[ids[0]] @ E[ids[1]]), 4)
    json.dump({"drift": drift, "seed_reference": ref,
               "meaning": "drift = 1 - cosine(CLAP audio emb, same context+seed unguided render on the finetune)"},
              open(f"{OUT}/clap.json", "w"), indent=1)
    print(f"[e18] clap: {len(drift)} drifts, seed reference {ref}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=("render", "clap"))
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    return render(a) if a.step == "render" else clap(a)


if __name__ == "__main__":
    sys.exit(main())
