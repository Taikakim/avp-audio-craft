#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-15)
"""punch_air_film_matrix.py -- the 2026-10-09 "cleanest" punch combo + the air-band LatCH head (gain x target) + FiLM on top.

WHY. Project direction 2026-10-15: try the punch example with both of its active LatCH heads (rms_energy_bass,
rms_energy_body) plus the retrained air head and the FiLM density adapter on top. G's punch_air page tested the air
head at one target (-10 dB) and two weights (24k/32k) and found gain moves brightness more than the target value, with
the new head overshooting the original's brightness at 24k/32k. This maps the air head's gain x target on the full combo,
with and without FiLM (E7's sweet spot: gain 1.0), so the combination is heard as a whole.

Client of :8056 /generate. Base payload = the rating server's "cleanest" preset (punch_rating_20261014/presets.json:
prompt, DoRA subloss_v3sel_k5_s2 ep19 @ 0.51, bass -10.0 dB @ 8448 + body -4.29 dB @ 11417.6, rho 5913.6, mu 5068.8,
gamma 0.25, n_iter 8, euler 30, cfg 9, 48 s). Air slot appended exactly as G's cleanest_a2g24 (same gain semantics:
server weight = slot gain / slot-1 gain, times the preset's explicit rho/mu). Seeds 764 (the example's) + 3050.
Grid: A2 air head: gain {4k, 8k, 12k, 16k, 24k, 32k} x target {-40, -30, -20, -10} dB x FiLM {off, gain 1.0 @ 6/s};
old production air head: same gains x targets, FiLM off (reference: its high-gain glitches started the retrain);
references: cleanest alone and cleanest + FiLM.
Output: Mantu2/sa3_control_runs/punch_air_film_matrix_20261015/<id>.wav, cells.jsonl, run_meta.json.
RUN: SAO/.venv/bin/python eval/punch_air_film_matrix.py render [--dry]
"""
import argparse
import copy
import json
import os
import shutil
import sys
import time

OUT = "/run/media/kim/Mantu2/sa3_control_runs/punch_air_film_matrix_20261015"
PRESETS = "/run/media/kim/Mantu2/sa3_control_runs/punch_rating_20261014/presets.json"
SERVER = "http://127.0.0.1:8056"
A2 = "/home/kim/Projects/SAO/stable-audio-3/latch_weights_sa3_medium/latch_sa3_rms_energy_air_a2_best.pt"
SEEDS = (764, 3050)
GAINS = (4000, 8000, 12000, 16000, 24000, 32000)
TARGETS = (-40.0, -30.0, -20.0, -10.0)
FILM = {"gain": 1.0, "value": 6.0}


def cells():
    out = []
    for s in SEEDS:
        for film in (False, True):
            out.append(dict(seed=s, head=None, gain=0, target=None, film=film, id=f"s{s}__punch{'_film' if film else ''}"))
            for g in GAINS:
                for t in TARGETS:
                    out.append(dict(seed=s, head="a2", gain=g, target=t, film=film,
                                    id=f"s{s}__a2_g{g // 1000}k_t{int(t)}{'_film' if film else ''}"))
        for g in GAINS:
            for t in TARGETS:
                out.append(dict(seed=s, head="old", gain=g, target=t, film=False, id=f"s{s}__old_g{g // 1000}k_t{int(t)}"))
    return out


def payload(c, base, film_ckpt):
    p = copy.deepcopy(base)
    p["seed"] = c["seed"]
    if c["head"] == "a2":
        p["latch"].append({"head": "rms_energy_air_a2", "path": A2, "kind": "constant", "value": c["target"],
                           "gain": float(c["gain"]), "start_pct": 0.0, "end_pct": 1.0})
    elif c["head"] == "old":
        p["latch"].append({"head": "rms_energy_air", "kind": "constant", "value": c["target"],
                           "gain": float(c["gain"]), "start_pct": 0.0, "end_pct": 1.0})
    if c["film"]:
        p["film"] = {"ckpt": film_ckpt, **FILM}
    return p


def render(a):
    import librosa
    import numpy as np
    import requests
    jl = f"{OUT}/cells.jsonl"
    done = {json.loads(l)["id"] for l in open(jl) if l.strip()} if os.path.exists(jl) else set()
    todo = [c for c in cells() if c["id"] not in done]
    print(f"[punch_air_film] {len(todo)} cells to render ({len(done)} done)", flush=True)
    if a.dry:
        return 0
    presets = json.load(open(PRESETS))
    base = (presets.get("presets", presets))["cleanest"]
    info = requests.get(f"{SERVER}/info", timeout=10).json()
    film_ckpt = (info.get("film_default") or {}).get("ckpt")
    os.makedirs(OUT, exist_ok=True)
    if not os.path.exists(f"{OUT}/run_meta.json"):
        json.dump({"purpose": __doc__.split("Client of")[0].strip(),
                   "hypothesis": "With the full punch combo, the retrained air head has a usable gain x target region that restores brightness without overshoot or glitches, and FiLM 1.0 on top keeps the density control without breaking it.",
                   "base_preset": {"source": PRESETS, "name": "cleanest", "payload_minus_prompt": {k: v for k, v in base.items() if k != "prompt"}},
                   "grid": {"seeds": SEEDS, "air_gains": GAINS, "air_targets_db": TARGETS, "film_on_top": FILM,
                            "heads": {"a2": A2, "old": "rms_energy_air (server registry, production AdamW head)"}},
                   "film_ckpt": film_ckpt,
                   "related": ["EXPERIMENTS E6 (air retrain, GHOST-NOTE)", "EXPERIMENTS E7 (LatCH x FiLM)",
                               "Misc/build_punch_air_page.py", "/home/kim/Music/latch/combo/punch/cleanest-20261009-143711-gen"],
                   "result": None, "kim_feedback": None}, open(f"{OUT}/run_meta.json", "w"), indent=1)
    for c in todo:
        t0 = time.time()
        while True:
            try:
                r = requests.post(f"{SERVER}/generate", json=payload(c, base, film_ckpt), timeout=1800)
                break
            except requests.exceptions.ConnectionError:
                print(f"  {time.strftime('%H:%M')} server unreachable, retrying in 120 s", flush=True)
                time.sleep(120)
        res = r.json()
        if r.status_code != 200 or res.get("status") != "ok" or not res.get("files"):
            print(f"  FAIL {c['id']}: {r.status_code} {str(res)[:300]}", flush=True)
            continue
        dst = f"{OUT}/{c['id']}.wav"
        shutil.copyfile(res["files"][0], dst)
        y, sr = librosa.load(dst, sr=None, mono=True)
        S = np.abs(librosa.stft(y, n_fft=2048)) ** 2
        f = librosa.fft_frequencies(sr=sr, n_fft=2048)
        c.update(onsets=round(len(librosa.onset.onset_detect(y=y, sr=sr, units="time")) / (len(y) / sr), 3),
                 air_db=round(float(10 * np.log10(S[f >= 2500].sum(0).mean() / 2048 + 1e-12)), 2),
                 centroid_hz=round(float(librosa.feature.spectral_centroid(S=np.sqrt(S), sr=sr).mean()), 1),
                 secs=round(time.time() - t0, 1))
        with open(jl, "a") as fh:
            fh.write(json.dumps(c) + "\n")
        print(f"  {c['id']}: {c['onsets']} on/s, air {c['air_db']} dB, centroid {c['centroid_hz']} Hz ({c['secs']}s)", flush=True)
    print("DONE", flush=True)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=("render",))
    ap.add_argument("--dry", action="store_true")
    return render(ap.parse_args())


if __name__ == "__main__":
    sys.exit(main())
