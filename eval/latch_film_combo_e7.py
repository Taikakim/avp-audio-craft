#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-15)
"""latch_film_combo_e7.py -- EXPERIMENTS E7: onset LatCH x FiLM density adapter, density vs character drift.

WHY. LatCH onset guidance (alpha weighting, window 0-1) is transparent but narrow (~5.5-9.3 onsets/s, listening
verdict 2026-10-15: "the musical matter stays intact"); the FiLM density adapter has the range but drags in the
training-set style. Question: does combining them buy range without the style leak? Kill (E7 spec): if "both" is
not better than max(FiLM-only, LatCH-only) on density-vs-drift, the combination adds nothing at these gains.

A thin CLIENT of the render server :8056 /generate (film + latch payloads compose there; INFERENCE-SURFACE rule),
not a new guidance driver. Contexts:
  base   medium-base, no DoRA, "psytrance, 140 bpm", euler 50, cfg 7, 20 s, seeds 1234 + 77 (today's eval context)
  punch  the 2026-10-09 "cleanest" punch example's prompt + DoRA (subloss_v3sel_k5_s2 ep19, strength 0.51), euler 30,
         cfg 9, 48 s, seeds 764 (the example's) + 3050 -- per project direction 2026-10-15. The example's bass/body
         LatCH slots are NOT included: only prompt, model and settings.
Grid per context x seed: FiLM gain {off, 0.5, 1.0, 1.75} x LatCH gain {off, 512, 2048} x density {3, 6, 9} onsets/s
(FiLM value = density; LatCH constant target = density in onsets per beat at the prompt's bpm); the off/off cell is
the unguided base render, rendered once.
Readouts: (a) onsets/s (librosa onset_detect, as every onset eval today); (b) CHARACTER DRIFT = 1 - cos(CLAP audio
embedding, same context+seed base render), plus the two bases' mutual distance as the seed-noise reference (`clap`
step, CPU). PQ + the disintegration gate come from clip_metrics(_audiobox) on the encoded m4a.
Output: Mantu2/sa3_control_runs/latch_film_combo_e7_20261015/<ctx>/<id>.wav, cells.jsonl, clap.json, run_meta.json.
RUN: SAO/.venv/bin/python eval/latch_film_combo_e7.py render   (server must be up)
     SAO/.venv/bin/python eval/latch_film_combo_e7.py clap     (CPU)
"""
import argparse
import json
import os
import shutil
import sys
import time

OUT = "/run/media/kim/Mantu2/sa3_control_runs/latch_film_combo_e7_20261015"
SERVER = "http://127.0.0.1:8056"
HEAD = "/run/media/kim/Mantu2/latch_sweep/modular_2026-09-30/phaseE/E04ema_b32_ep20/latch_sa3_onset_per_beat_ts_best.pt"
PUNCH_PROMPT = ("90s psytrance, mystical aggressive goa trance,hypnotic, energetic, 143 bpm, the music consists of  "
                "polivoks and korg analog leads and enigmatic organics pads. the bassline is a beefy moog snappy saw wave "
                "16ths bass, and the drums have classic 909 kick and open hihat sounds. under everything  roland 303 style "
                "distorted resonant acid riffs play syncopated rhythms.")
PUNCH_DORA = ("/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/runs/subloss_tgate_modes/"
              "subloss_v3sel_k5_s2/epoch=19-step=27000.ckpt")
CONTEXTS = {
    "base": dict(prompt="psytrance, 140 bpm", bpm=140.0, steps=50, cfg=7.0, duration=20.0, seeds=(1234, 77),
                 dora={"name": "none", "strength": 1.0}),
    "punch": dict(prompt=PUNCH_PROMPT, bpm=143.0, steps=30, cfg=9.0, duration=48.0, seeds=(764, 3050),
                  dora={"ckpt_path": PUNCH_DORA, "strength": 0.51}),
    # Added 2026-10-15 for the plan's AUDIT-THE-INSTRUMENT rule: both contexts above are psytrance/goa, so FiLM's goa
    # style leak would barely register in CLAP drift there. A far-from-goa genre makes the leak visible and tests
    # whether the drift meter can see it at all.
    "house": dict(prompt="deep house, 122 bpm, warm chords, soulful, laid back groove", bpm=122.0, steps=50, cfg=7.0,
                  duration=20.0, seeds=(1234, 77), dora={"name": "none", "strength": 1.0}),
}
FILM_GAINS = (0.0, 0.5, 1.0, 1.75)
LATCH_GAINS = (0, 512, 2048)
DENSITIES = (3, 6, 9)


def cells():
    out = []
    for ctx, C in CONTEXTS.items():
        for s in C["seeds"]:
            out.append(dict(ctx=ctx, seed=s, film=0.0, latch=0, dens=None, id=f"{ctx}_s{s}__base"))
            for fg in FILM_GAINS:
                for lg in LATCH_GAINS:
                    if not fg and not lg:
                        continue
                    for d in DENSITIES:
                        out.append(dict(ctx=ctx, seed=s, film=fg, latch=lg, dens=d,
                                        id=f"{ctx}_s{s}__film{fg:g}_latch{lg}_d{d}"))
    return out


def payload(c, film_ckpt):
    C = CONTEXTS[c["ctx"]]
    p = {"prompt": C["prompt"], "duration": C["duration"], "steps": C["steps"], "cfg_scale": C["cfg"],
         "seed": c["seed"], "sampler_type": "euler", "apg_scale": 1.0, "dora": dict(C["dora"])}
    if c["film"]:
        p["film"] = {"ckpt": film_ckpt, "value": float(c["dens"]), "gain": float(c["film"])}
    if c["latch"]:
        p["latch"] = [{"path": HEAD, "head": "onset_per_beat_e04ema", "kind": "constant",
                       "value": c["dens"] * 60.0 / C["bpm"], "gain": float(c["latch"]),
                       "start_pct": 0.0, "end_pct": 1.0}]
    return p


def render(a):
    import librosa
    import requests
    jl = f"{OUT}/cells.jsonl"
    done = {json.loads(l)["id"] for l in open(jl) if l.strip()} if os.path.exists(jl) else set()
    todo = [c for c in cells() if c["id"] not in done]
    print(f"[e7] {len(todo)} cells to render ({len(done)} done)", flush=True)
    if a.dry:
        return 0
    info = requests.get(f"{SERVER}/info", timeout=10).json()
    film_ckpt = (info.get("film_default") or {}).get("ckpt")
    if not film_ckpt:
        sys.exit("[e7] server /info has no film_default ckpt")
    os.makedirs(OUT, exist_ok=True)
    if not os.path.exists(f"{OUT}/run_meta.json"):
        json.dump({"purpose": __doc__.split("A thin CLIENT")[0].strip(),
                   "hypothesis": "LatCH + FiLM together reach a wider density range than LatCH alone at less character drift than FiLM alone.",
                   "kill": "both <= max(FiLM-only, LatCH-only) on density-vs-drift -> go to E8/E9",
                   "contexts": {k: {kk: vv for kk, vv in v.items()} for k, v in CONTEXTS.items()},
                   "grid": {"film_gain": FILM_GAINS, "latch_gain": LATCH_GAINS, "density": DENSITIES},
                   "heads": {"latch": HEAD, "film": film_ckpt},
                   "related": ["EXPERIMENTS E7", "eval/latch_onset_matrix_ema.py",
                               "/home/kim/Music/latch/combo/punch/cleanest-20261009-143711-gen/result.json (punch context source)"],
                   "result": None, "kim_feedback": None}, open(f"{OUT}/run_meta.json", "w"), indent=1)
    for c in todo:
        t0 = time.time()
        while True:   # the server is GHOST-NOTE's and comes and goes between their jobs: wait, don't die
            try:
                r = requests.post(f"{SERVER}/generate", json=payload(c, film_ckpt), timeout=1800)
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


def clap_embedder():
    """-> emb(path): unit-norm CLAP audio embedding (laion 630k+audioset, HTSAT-tiny, CPU). Shared with E8."""
    import numpy as np
    import torch
    import librosa
    argv, sys.argv = sys.argv, [sys.argv[0]]   # laion_clap parses argv at import (see clap_score.py)
    try:
        import laion_clap
    finally:
        sys.argv = argv
    model = laion_clap.CLAP_Module(enable_fusion=False, amodel="HTSAT-tiny", device="cpu")
    _load, _lsd = torch.load, model.model.load_state_dict
    torch.load = lambda *aa, **kk: _load(*aa, **{**kk, "weights_only": False})
    model.model.load_state_dict = lambda sd, strict=True: _lsd(sd, strict=False)
    try:
        model.load_ckpt(model_id=1)
    finally:
        torch.load, model.model.load_state_dict = _load, _lsd
    model.eval()

    def emb(path):
        wav, _ = librosa.load(path, sr=48000, mono=True)
        with torch.no_grad():
            try:
                e = model.get_audio_embedding_from_data(x=torch.from_numpy(wav).float().unsqueeze(0), use_tensor=True)
                e = e.float().cpu().numpy()
            except TypeError:
                e = np.asarray(model.get_audio_embedding_from_data(x=wav[None, :].astype(np.float32)))
        v = e[0]
        return v / (np.linalg.norm(v) + 1e-9)

    return emb


def clap(a):
    """Character drift: 1 - cos(CLAP audio embedding) to the same context+seed base render."""
    emb = clap_embedder()
    rows = [json.loads(l) for l in open(f"{OUT}/cells.jsonl") if l.strip()]
    E = {c["id"]: emb(f"{OUT}/{c['ctx']}/{c['id']}.wav") for c in rows}
    base = {(c["ctx"], c["seed"]): c["id"] for c in rows if c["dens"] is None}
    drift = {c["id"]: round(float(1 - E[c["id"]] @ E[base[(c["ctx"], c["seed"])]]), 4)
             for c in rows if (c["ctx"], c["seed"]) in base}
    ref = {}
    for ctx in CONTEXTS:
        ids = [v for (cx, _), v in base.items() if cx == ctx]
        if len(ids) == 2:
            ref[ctx] = round(float(1 - E[ids[0]] @ E[ids[1]]), 4)
    json.dump({"drift": drift, "seed_reference": ref,
               "meaning": "drift = 1 - cosine(CLAP audio emb, same context+seed unguided base); seed_reference = the two base seeds' mutual distance"},
              open(f"{OUT}/clap.json", "w"), indent=1)
    print(f"[e7] clap: {len(drift)} drifts, seed reference {ref}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=("render", "clap"))
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    return render(a) if a.step == "render" else clap(a)


if __name__ == "__main__":
    sys.exit(main())
