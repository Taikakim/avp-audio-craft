#!/usr/bin/env python3
# Owner: GHOST-NOTE (created 2026-10-14)
"""latch_onset_eval.py -- the onset_eval.html measurement, but for LatCH density HEADS instead of the FiLM control adapter.

WHY (Kim 2026-10-14: "create a comparison with the same targets as onset_eval.html ... how do the gain and target amounts compare to what we are now using?").
control/sa3_control/onset_eval.py asks the FiLM adapter for a raw onset DENSITY (onsets/s) 2,4,6,8,10 at adapter strengths (gain) and MEASURES the rendered onsets/s
with librosa. The Phase E heads are trained on onsets PER BEAT, so each requested density d (on/s) is converted to the head's unit at the prompt's tempo:
    opb_target = d * 60 / BPM          (BPM = 140, the page's prompt says "140 bpm")
and the measured value is the SAME function (librosa.onset.onset_detect, onsets / duration). Everything else is the page's setup: prompt "psytrance, 140 bpm",
seed 1234, cfg 7, 50 steps, 20 s, euler, medium-base. The guidance gain (rho = mu) replaces the adapter strength; they are different mechanisms and different scales.
Output per arm = a directory in control/onset_eval.py's own format (onset_eval.json list of {gain, requested, measured}; clips onset_g<gain>_d<density>.wav;
run_meta.json), so the existing page tooling can read it. gain 0 = unguided, one render, listed against every density.
RUN: ROCR_VISIBLE_DEVICES=0 SAO/.venv/bin/python eval/latch_onset_eval.py [--arms E01,E05] [--gains 128,512,2048,8192]
"""
import argparse
import json
import os
import sys
import time

os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")

PHASE = "/run/media/kim/Mantu/latch_sweep/modular_2026-09-30/phaseE"
OUT = "/run/media/kim/Mantu/sa3_control_runs"
FEATURE = "onset_per_beat_ts"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="")
    ap.add_argument("--gains", default="128,512,2048,8192")
    ap.add_argument("--densities", default="2,4,6,8,10")
    ap.add_argument("--prompt", default="psytrance, 140 bpm")
    ap.add_argument("--bpm", type=float, default=140.0)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--steps", type=int, default=50)
    ap.add_argument("--cfg", type=float, default=7.0)
    ap.add_argument("--duration", type=float, default=20.0)
    a = ap.parse_args()
    import librosa
    import numpy as np
    import soundfile as sf
    import torch
    from stable_audio_3 import StableAudioModel
    dens = [float(x) for x in a.densities.split(",")]
    gains = [float(x) for x in a.gains.split(",")]
    arms = [l.split("\t")[0] for l in open(f"{PHASE}/SUMMARY.tsv").read().splitlines() if l.strip()]
    arms = [r for r in arms if not a.arms or any(r.startswith(p) for p in a.arms.split(","))]
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    sr = model.model.sample_rate

    def render(**kw):
        return model.generate(prompt=a.prompt, duration=a.duration, steps=a.steps, cfg_scale=a.cfg, seed=a.seed, sampler_type="euler", **kw)

    def to_np(x):
        x = x.cpu().float().numpy() if hasattr(x, "cpu") else np.asarray(x)
        while x.ndim > 2:
            x = x[0]
        return x

    def onset_density(x):
        y = x.mean(0) if x.ndim > 1 and x.shape[0] <= 2 else x
        on = librosa.onset.onset_detect(y=y, sr=sr, units="time")
        return len(on) / (len(y) / sr)

    def save(path, x):
        pk = max(1e-9, float(abs(x).max()))
        sf.write(path, (x / pk * 0.8913 if pk > 1 else x).T, sr)

    base = to_np(render())
    base_od = onset_density(base)
    print(f"[latch-onset-eval] unguided: {base_od:.2f} onsets/s", flush=True)
    for arm in arms:
        ck = f"{PHASE}/{arm}/latch_sa3_{FEATURE}_best.pt"
        if not os.path.exists(ck):
            print("MISSING", ck)
            continue
        meta = torch.load(ck, map_location="cpu", weights_only=False)
        d_out = f"{OUT}/onset_eval_latchE_{arm}"
        os.makedirs(d_out, exist_ok=True)
        rows = []
        for d in dens:
            save(f"{d_out}/onset_g0_d{d:g}.wav", base)
            rows.append({"gain": 0.0, "requested": d, "measured": base_od})
        for g in gains:
            line = []
            for d in dens:
                tgt = d * 60.0 / a.bpm
                t0 = time.time()
                x = to_np(render(latch_configs=[{"model_path": ck, "kind": "constant", "value": tgt, "weight": 1.0}], latch_hparams={"rho": g, "mu": g}))
                od = onset_density(x)
                save(f"{d_out}/onset_g{g:g}_d{d:g}.wav", x)
                rows.append({"gain": g, "requested": d, "measured": od})
                line.append(od)
            r = np.corrcoef(dens, line)[0, 1] if len(set(line)) > 1 else 0.0
            print(f"  {arm} g{g:g} | " + "  ".join(f"d{d:g}->{m:.1f}" for d, m in zip(dens, line)) + f" | corr {r:+.2f}", flush=True)
        json.dump(rows, open(f"{d_out}/onset_eval.json", "w"), indent=2)
        json.dump({"purpose": "LatCH density head (Phase E, onset_per_beat_ts) measured the way onset_eval.html measures the FiLM adapter: requested onsets/s -> opb target at 140 bpm, measured with librosa onset_detect.",
                   "hypothesis": "A head trained on onsets-per-beat should follow a density request; gain is the guidance rho=mu, not the adapter strength.",
                   "eval": {"prompt": a.prompt, "gains": a.gains, "densities": a.densities, "seed": a.seed, "cfg": a.cfg, "duration": a.duration, "steps": a.steps, "bpm_for_conversion": a.bpm},
                   "arm": arm, "epoch": meta.get("epoch"), "val_loss": meta.get("val_loss"), "std_mean": meta.get("std_mean"), "std_std": meta.get("std_std"),
                   "related": ["control/sa3_control/onset_eval.py", "eval/latch_onset_eval.py", "EXPERIMENTS.md E5"], "result": None, "kim_feedback": None},
                  open(f"{d_out}/run_meta.json", "w"), indent=2)
    print("DONE")


if __name__ == "__main__":
    sys.exit(main())
