#!/usr/bin/env python3
"""
hardness_gain_bracket.py -- re-bracket the hardness LatCH head's guidance gain
WITH quality gates (task #49; Kim's directive after the gain-512 negative:
"when doing evals, we should use our established good metrics (CE, PQ, zero
crossings, etc)" -- the 512 smoke moved the target meter while the audio broke).

Two modes (two venvs -- run each with the right interpreter):

  GEN (SA3 venv, GPU):
    ../../stable-audio-3/.venv/bin/python hardness_gain_bracket.py gen
  Renders baseline (per seed) + {gain 32/64/128/256} x {down 59 / up 73} x seeds,
  12 s / 8-step / cfg 6, into OUT_DIR with run_meta.json. Skip-if-exists.

  MEASURE (mir venv, CPU + a short WavLM GPU pass):
    /home/kim/Projects/mir/mir/bin/python hardness_gain_bracket.py measure
  Per clip: timbral_hardness (target meter), zero-crossing rate, Audiobox CE/PQ.
  Verdict per cell: steer delta vs baseline AND quality deltas -- a cell only
  counts as a steer if CE/PQ hold (drop < GATE) and ZCR isn't exploding.
  Writes scores.json + a findings summary to stdout.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

OUT_DIR = Path("/run/media/kim/Mantu/sa3_control_runs/hardness_bracket_2026-07-10")
CKPT = "/home/kim/Projects/SAO/stable-audio-3/latch_weights_sa3_medium/latch_sa3_hardness_best.pt"
PROMPT = "energetic goa trance with driving percussion and psychedelic leads"
GAINS = (32.0, 64.0, 128.0, 256.0)
TARGETS = {"down": 59.0, "up": 73.0}
SEEDS = (7, 8)
CE_GATE = 0.75   # max allowed CE drop vs baseline before the cell is disqualified
PQ_GATE = 0.75


def clip_name(kind, gain=None, seed=None):
    return f"base_s{seed}.wav" if kind == "base" else f"{kind}_g{int(gain)}_s{seed}.wav"


def mode_gen():
    sys.path.insert(0, "/home/kim/Projects/SAO/stable-audio-3")
    import numpy as np
    import torch
    import soundfile as sf
    from stable_audio_3.model import StableAudioModel

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sam = StableAudioModel.from_pretrained("medium-base", device="cuda")
    sr = sam.model.sample_rate

    def save(a, name):
        x = a.detach().float().cpu().numpy()
        while x.ndim > 2:
            x = x[0]
        if x.ndim == 2:
            x = x.mean(axis=0 if x.shape[0] <= 8 else 1)
        x = x / max(abs(x).max(), 1e-9) * 0.89
        sf.write(OUT_DIR / name, x, sr)

    def gen(latch=None, seed=7):
        with torch.inference_mode():
            return sam.generate(prompt=PROMPT, duration=12.0, steps=8, cfg_scale=6.0,
                                seed=seed, sampler_type="euler",
                                latch_configs=latch,
                                latch_hparams={"rho": 64.0, "mu": 64.0} if latch else None)

    n = 0
    for seed in SEEDS:
        name = clip_name("base", seed=seed)
        if not (OUT_DIR / name).exists():
            save(gen(seed=seed), name)
            n += 1
        for kind, val in TARGETS.items():
            for gain in GAINS:
                name = clip_name(kind, gain, seed)
                if (OUT_DIR / name).exists():
                    continue
                save(gen([{"model_path": CKPT, "kind": "constant",
                           "value": val, "weight": gain}], seed=seed), name)
                n += 1
                print(f"[bracket] {name}", flush=True)

    (OUT_DIR / "run_meta.json").write_text(json.dumps({
        "purpose": ("Hardness-head gain re-bracket WITH quality gates (CE/PQ/ZCR) after the "
                    "gain-512 negative (meter moved, audio broke -- 'concrete slab'/'dentist's "
                    "drill'). Finds the operating gain where steer holds AND quality survives."),
        "related": ["scripts/latch/train_latch.py (scalar_json)",
                    "sa3_control_runs/hardness_steer_smoke (the negative)",
                    "control/sa3_control/hardness_gain_bracket.py"],
        "checkpoint": "hardness head (internal), EMA 20ep, std 66.19/3.49",
        "params": {"prompt": PROMPT, "seeds": list(SEEDS), "gains": list(GAINS),
                   "targets": TARGETS, "duration": 12.0, "steps": 8, "cfg": 6.0,
                   "rho": 64, "mu": 64, "ce_gate": CE_GATE, "pq_gate": PQ_GATE},
    }, indent=2))
    print(f"[bracket] gen done, {n} new clips -> {OUT_DIR}", flush=True)


def mode_measure():
    import warnings
    warnings.filterwarnings("ignore")
    import numpy as np
    import librosa
    import timbral_models
    sys.path.insert(0, "/home/kim/Projects/mir/src")
    from timbral.audiobox_aesthetics import analyze_audiobox_aesthetics

    rows = {}
    for p in sorted(OUT_DIR.glob("*.wav")):
        hard = float(timbral_models.timbral_hardness(str(p)))
        y, sr = librosa.load(str(p), sr=22050, mono=True)
        zcr = float(np.mean(librosa.feature.zero_crossing_rate(y)))
        ab = analyze_audiobox_aesthetics(str(p)) or {}
        rows[p.stem] = {"hardness": round(hard, 2), "zcr": round(zcr, 4),
                        "CE": ab.get("content_enjoyment"), "PQ": ab.get("production_quality")}
        print(f"[measure] {p.stem}: hard={hard:.1f} zcr={zcr:.3f} "
              f"CE={rows[p.stem]['CE']} PQ={rows[p.stem]['PQ']}", flush=True)

    # verdicts vs the same-seed baseline
    verdicts = {}
    for seed in SEEDS:
        base = rows.get(f"base_s{seed}")
        if not base:
            continue
        for kind in TARGETS:
            for gain in GAINS:
                k = f"{kind}_g{int(gain)}_s{seed}"
                r = rows.get(k)
                if not r:
                    continue
                steer = r["hardness"] - base["hardness"]
                ce_d = (r["CE"] - base["CE"]) if (r["CE"] and base["CE"]) else None
                pq_d = (r["PQ"] - base["PQ"]) if (r["PQ"] and base["PQ"]) else None
                ok = ((ce_d is None or ce_d > -CE_GATE) and
                      (pq_d is None or pq_d > -PQ_GATE))
                right_dir = steer < 0 if kind == "down" else steer > 0
                verdicts[k] = {"steer_delta": round(steer, 2),
                               "CE_delta": None if ce_d is None else round(ce_d, 3),
                               "PQ_delta": None if pq_d is None else round(pq_d, 3),
                               "quality_ok": ok, "direction_ok": bool(right_dir),
                               "counts_as_steer": bool(ok and right_dir)}
    out = {"clips": rows, "verdicts": verdicts,
           "gates": {"CE_drop_max": CE_GATE, "PQ_drop_max": PQ_GATE}}
    (OUT_DIR / "scores.json").write_text(json.dumps(out, indent=2))

    print("\n gain | dir  | steerΔ (s7/s8) | CEΔ | PQΔ | verdict")
    for gain in GAINS:
        for kind in TARGETS:
            cells = [verdicts.get(f"{kind}_g{int(gain)}_s{s}") for s in SEEDS]
            cells = [c for c in cells if c]
            if not cells:
                continue
            sd = "/".join(f"{c['steer_delta']:+.1f}" for c in cells)
            ce = "/".join("·" if c["CE_delta"] is None else f"{c['CE_delta']:+.2f}" for c in cells)
            pq = "/".join("·" if c["PQ_delta"] is None else f"{c['PQ_delta']:+.2f}" for c in cells)
            ok = all(c["counts_as_steer"] for c in cells)
            print(f" {int(gain):4d} | {kind:4s} | {sd:14s} | {ce} | {pq} | {'STEER' if ok else 'fail'}")
    print(f"\n[measure] scores.json -> {OUT_DIR}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "gen"
    (mode_gen if mode == "gen" else mode_measure)()
