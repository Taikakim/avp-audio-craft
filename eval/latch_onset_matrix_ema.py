#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-15)
"""latch_onset_matrix_ema.py -- target x gain matrix for the onset LatCH head, EMA vs online weights.

WHY. The early-budget bracket listening verdict (2026-10-15, latch_early_budget run_meta kim_feedback): the default
alpha weighting over the full window 0-1 is the cleanest; gain 512 is quite okay, 2048 not impossible; the effect is
noticeable and, most importantly, TRANSPARENT (the musical matter stays, unlike the FiLM adapter, which drags in the
training-set style). Flat weighting and early-only windows push loudness up into distortion. This matrix maps that
one setting finely: requested density 0..12 onsets/s x gains 32..4096, for the E04 recipe retrained with EMA so the
EMA and the online (Schedule-Free averaged) weights come from ONE trajectory and the same epoch.

Fixed: medium-base, euler 50, cfg 7, 20 s, "psytrance, 140 bpm", guide_schedule alpha, window 0-1, seeds 1234 + 77.
Measured per clip: onsets/s (librosa onset_detect, as latch_onset_eval.py). Non-finite renders are not written.
Output: Mantu2/sa3_control_runs/latch_onset_matrix_ema_20261015/<weights>/<id>.wav + cells.jsonl + run_meta.json.
RUN (hold the GPU lock): ROCR_VISIBLE_DEVICES=0 SAO/.venv/bin/python eval/latch_onset_matrix_ema.py --ema <pt> --online <pt> [--dry]
"""
import argparse
import json
import os
import sys
import time

os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")

OUT = "/run/media/kim/Mantu/sa3_control_runs/latch_onset_matrix_ema_20261015"
PROMPT, BPM, CFG, DUR, STEPS = "psytrance, 140 bpm", 140.0, 7.0, 20.0, 50
SEEDS = (1234, 77)
TARGETS = tuple(range(0, 13))
GAINS = (32, 64, 128, 256, 384, 512, 768, 1024, 1280, 1560, 2048, 4096)


def cells():
    out = [dict(weights="base", seed=s, gain=0, req=None, id=f"base_s{s}") for s in SEEDS]
    for w in ("ema", "online"):
        for s in SEEDS:
            for g in GAINS:
                for r in TARGETS:
                    out.append(dict(weights=w, seed=s, gain=g, req=r, id=f"{w}_s{s}_g{g}_r{r}"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ema", required=True)
    ap.add_argument("--online", required=True)
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    ck = {"ema": a.ema, "online": a.online}
    jl = f"{OUT}/cells.jsonl"
    done = {json.loads(l)["id"] for l in open(jl) if l.strip()} if os.path.exists(jl) else set()
    todo = [c for c in cells() if c["id"] not in done]
    print(f"[matrix] {len(todo)} cells to render ({len(done)} already done)", flush=True)
    if a.dry:
        return 0
    import librosa
    import numpy as np
    import soundfile as sf
    import torch
    from stable_audio_3 import StableAudioModel
    os.makedirs(OUT, exist_ok=True)
    meta_p = f"{OUT}/run_meta.json"
    if not os.path.exists(meta_p):
        ep = {k: torch.load(v, map_location="cpu", weights_only=False) for k, v in ck.items()}
        json.dump({"purpose": __doc__.split("Fixed:")[0].strip(),
                   "hypothesis": "With alpha weighting over 0-1 the onset head steers transparently; the matrix locates the usable gain range and whether EMA weights steer more cleanly than the online (SF-averaged) weights.",
                   "checkpoints": {k: {"path": v, "epoch": ep[k].get("epoch"), "ema": ep[k].get("ema"), "val_loss": ep[k].get("val_loss")} for k, v in ck.items()},
                   "training": {"recipe": "Phase E E04 (onset_per_beat_ts, modular optimiser shampoo, lr 1e-2, batch 32, 20 epochs, radial brake 0.8, escape velocity) + --ema-halflife-epochs 0.5 --save-online --save-every-epoch",
                                "dataset": "Kosmos/latents_goa_bigset (goa corpus, SA3 latents), val 5% grouped by relpath",
                                "script": "eval/run_latch_onset_matrix_ema.sh"},
                   "eval": {"prompt": PROMPT, "bpm_for_conversion": BPM, "cfg": CFG, "duration": DUR, "steps": STEPS, "sampler": "euler",
                            "model": "medium-base", "guide_schedule": "alpha", "window": [0.0, 1.0], "seeds": SEEDS,
                            "targets_onsets_per_s": TARGETS, "gains": GAINS},
                   "related": ["eval/latch_early_budget_bracket.py", "Mantu2/sa3_control_runs/latch_early_budget_20261015/run_meta.json"],
                   "result": None, "kim_feedback": None}, open(meta_p, "w"), indent=1)

    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    sr = model.model.sample_rate
    for c in todo:
        kw = dict(prompt=PROMPT, duration=DUR, steps=STEPS, cfg_scale=CFG, seed=c["seed"], sampler_type="euler")
        if c["gain"]:
            kw["latch_configs"] = [{"model_path": ck[c["weights"]], "kind": "constant", "value": c["req"] * 60.0 / BPM,
                                    "weight": 1.0, "start_pct": 0.0, "end_pct": 1.0}]
            kw["latch_hparams"] = {"rho": float(c["gain"]), "mu": float(c["gain"]), "guide_schedule": "alpha"}
        t0 = time.time()
        x = model.generate(**kw)
        x = x.cpu().float().numpy() if hasattr(x, "cpu") else np.asarray(x)
        while x.ndim > 2:
            x = x[0]
        if not np.isfinite(x).all():
            print(f"  NONFINITE {c['id']} -- not written", flush=True)
            continue
        os.makedirs(f"{OUT}/{c['weights']}", exist_ok=True)
        pk = float(np.abs(x).max()) or 1e-9
        sf.write(f"{OUT}/{c['weights']}/{c['id']}.wav", (x / pk * 0.8913 if pk > 1 else x).T, sr)
        y = x.mean(0)
        c.update(onsets=round(len(librosa.onset.onset_detect(y=y, sr=sr, units="time")) / (len(y) / sr), 3),
                 secs=round(time.time() - t0, 1))
        with open(jl, "a") as f:
            f.write(json.dumps(c) + "\n")
        print(f"  {c['id']}: {c['onsets']} on/s ({c['secs']}s)", flush=True)
    print("DONE", flush=True)
    os._exit(0)  # skip interpreter teardown: the SA3 process aborts there ("corrupted double-linked list", rc 134)


if __name__ == "__main__":
    sys.exit(main())
