#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-15)
"""latch_early_budget_bracket.py -- does LatCH guidance steer ONSETS once it gets a real early budget?

WHY. TFG's per-step weight s(t) = alpha_t / sum(alpha_t), alpha = 1 - sigma (LatCH paper 2603.04366
Eq. 3, from TFG), puts ~0.2% of the guidance budget in the first 20% of steps and ~62% in the last 20%.
Every onset-head eval so far (Phase E grids, latch_onset_compare) used the full window 0-1 with that
shape, i.e. guided almost only AFTER rhythm/arrangement are fixed. Listening verdict 2026-10-15:
"the LATCH heads barely change the sound, except where it collapses". Hypothesis: the onset heads were
never given an early budget; energy/timbre heads work because what they steer can still change late.
Also bracketed (project direction 2026-10-15): the sigma-schedule SHAPE, warped toward the early,
high-noise steps, which by ear has a large effect on the post-trained model.

LEGS (all 20 s, cfg 7, prompt "psytrance, 140 bpm", seeds 1234 + 77):
  A  base, euler 50: onset head E04 x guide_schedule {alpha, flat} x window end {0.2, 0.4, 1.0}
     x gain {32,128,512,2048} x request {2, 10} onsets/s.
  B  base, euler 50: sigma shape {flux a=3, logsnr rho=2} (model default = leg A) x flat
     x window {0.2, 1.0} x gain {128, 512} x request {2, 10}; unguided baseline per shape.
  C  base, euler 50: air head A2 (E6 retrain) x {alpha, flat} x window {0.4, 1.0} x gain {512,2048,8192,24000}
     x air target {-10, -55} dB (head mean -33, std 26).
  D  post-trained medium, pingpong 24: onset head E04 x {alpha, flat} x window {0.2, 1.0}
     x gain {128, 512, 2048} x request {2, 10} x shape {model, flux a=3}; one seed.
Every cell gets its unguided baseline (same leg, model, shape, seed) for the disintegration gate.

Measured per clip, inline: onsets/s (librosa onset_detect, = latch_onset_eval.py) and air-band level
(dB RMS above 2.5 kHz). A non-finite render is NOT written (cell stays missing; resume re-renders).
Output: Mantu2/sa3_control_runs/latch_early_budget_20261015/<leg>/<cell>.wav + cells.jsonl + run_meta.json.
RUN (hold the GPU lock first): ROCR_VISIBLE_DEVICES=0 SAO/.venv/bin/python eval/latch_early_budget_bracket.py [--legs A,B,C,D] [--dry]
"""
import argparse
import json
import os
import sys
import time

os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

OUT = "/run/media/kim/Mantu2/sa3_control_runs/latch_early_budget_20261015"
ONSET = "/run/media/kim/Mantu2/latch_sweep/modular_2026-09-30/phaseE/E04_b32_ep20/latch_sa3_onset_per_beat_ts_best.pt"
AIR = "/home/kim/Projects/SAO/stable-audio-3/latch_weights_sa3_medium/latch_sa3_rms_energy_air_a2_best.pt"
PROMPT, BPM, CFG, DUR = "psytrance, 140 bpm", 140.0, 7.0, 20.0
SEEDS = (1234, 77)


def cells(legs):
    """Every render as a dict; 'gain' 0 = unguided baseline."""
    out = []

    def base(leg, model, steps, shape, seed):
        out.append(dict(leg=leg, model=model, steps=steps, shape=shape, seed=seed, head=None, gain=0))

    def g(leg, model, steps, shape, seed, head, req, gs, end, gain):
        out.append(dict(leg=leg, model=model, steps=steps, shape=shape, seed=seed, head=head, req=req,
                        sched=gs, start=0.0, end=end, gain=gain))

    for s in SEEDS:
        if "A" in legs:
            base("A", "medium-base", 50, "model", s)
            for gs in ("alpha", "flat"):
                for end in (0.2, 0.4, 1.0):
                    for gain in (32, 128, 512, 2048):
                        for req in (2, 10):
                            g("A", "medium-base", 50, "model", s, "onset", req, gs, end, gain)
        if "B" in legs:
            for shape in ("flux3", "logsnr_rho2"):
                base("B", "medium-base", 50, shape, s)
                for end in (0.2, 1.0):
                    for gain in (128, 512):
                        for req in (2, 10):
                            g("B", "medium-base", 50, shape, s, "onset", req, "flat", end, gain)
        if "C" in legs:
            base("C", "medium-base", 50, "model", s)
            for gs in ("alpha", "flat"):
                for end in (0.4, 1.0):
                    for gain in (512, 2048, 8192, 24000):
                        for req in (-10, -55):
                            g("C", "medium-base", 50, "model", s, "air", req, gs, end, gain)
    if "D" in legs:
        s = SEEDS[0]
        for shape in ("model", "flux3"):
            base("D", "medium", 24, shape, s)
            for gs in ("alpha", "flat"):
                for end in (0.2, 1.0):
                    for gain in (128, 512, 2048):
                        for req in (2, 10):
                            g("D", "medium", 24, shape, s, "onset", req, gs, end, gain)
    for c in out:
        c["id"] = cell_id(c)
    return out


def cell_id(c):
    b = f"{c['leg']}_{c['shape']}_s{c['seed']}"
    if not c["gain"]:
        return b + "__base"
    return b + f"__{c['head']}_{c['sched']}_w{c['end']:g}_g{c['gain']}_r{c['req']:g}"


def shift_for(shape, steps):
    if shape == "model":
        return None
    if shape == "flux3":
        from stable_audio_3.inference.distribution_shift import FluxDistributionShift
        return FluxDistributionShift(alpha_min=3.0, alpha_max=3.0)
    if shape == "logsnr_rho2":
        from forge import schedule as fs
        return fs.ArraySchedule(fs.sigmas(fs.parse_spec({"shape": "logsnr", "rho": 2.0}), steps, 1.0))
    raise ValueError(shape)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--legs", default="A,B,C,D")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    todo = cells(set(a.legs.split(",")))
    done = set()
    jl = f"{OUT}/cells.jsonl"
    if os.path.exists(jl):
        done = {json.loads(l)["id"] for l in open(jl) if l.strip()}
    todo = [c for c in todo if c["id"] not in done]
    print(f"[bracket] {len(todo)} cells to render ({len(done)} already done)", flush=True)
    if a.dry:
        from collections import Counter
        print(Counter(c["leg"] for c in todo))
        return 0
    import librosa
    import numpy as np
    import soundfile as sf
    import torch
    from stable_audio_3 import StableAudioModel
    os.makedirs(OUT, exist_ok=True)
    json.dump({"purpose": __doc__.split("LEGS")[0].strip(),
               "hypothesis": "Onset guidance fails because TFG's alpha-weighted s(t) leaves the early steps (where rhythm is decided) almost unguided; a flat or early window, and a sigma schedule that spends more steps at high noise, should let the onset head change the groove.",
               "heads": {"onset": "Phase E E04_b32_ep20 (onset_per_beat_ts), see EXPERIMENTS E5", "air": "rms_energy_air_a2 (GHOST-NOTE retrain under the modular optimizer, EXPERIMENTS E6; the old production head glitches at high gain)"},
               "eval": {"prompt": PROMPT, "bpm_for_conversion": BPM, "cfg": CFG, "duration": DUR, "seeds": SEEDS},
               "related": ["eval/latch_early_budget_bracket.py", "stable_audio_3/inference/latch_guided.py::_window_scale",
                           "eval/latch_onset_eval.py", "papers 2603.04366 (LatCH, Eq. 3)"],
               "result": None, "kim_feedback": None}, open(f"{OUT}/run_meta.json", "w"), indent=1)

    def onsets(y, sr):
        return len(librosa.onset.onset_detect(y=y, sr=sr, units="time")) / (len(y) / sr)

    def air_db(y, sr):
        S = np.abs(librosa.stft(y, n_fft=2048)) ** 2
        f = librosa.fft_frequencies(sr=sr, n_fft=2048)
        return float(10 * np.log10(S[f >= 2500].sum(0).mean() / 2048 + 1e-12))

    model, cur = None, None
    for c in sorted(todo, key=lambda c: (c["model"] != "medium-base", c["leg"], c["shape"], c["seed"])):
        if c["model"] != cur:
            del model
            torch.cuda.empty_cache()
            model, cur = StableAudioModel.from_pretrained(c["model"], device="cuda"), c["model"]
            sr = model.model.sample_rate
        kw = dict(prompt=PROMPT, duration=DUR, steps=c["steps"], cfg_scale=CFG, seed=c["seed"],
                  sampler_type="euler" if c["model"] == "medium-base" else "pingpong")
        sh = shift_for(c["shape"], c["steps"])
        if sh is not None:
            kw["dist_shift"] = sh
        if c["gain"]:
            ck = ONSET if c["head"] == "onset" else AIR
            val = c["req"] * 60.0 / BPM if c["head"] == "onset" else float(c["req"])
            kw["latch_configs"] = [{"model_path": ck, "kind": "constant", "value": val, "weight": 1.0,
                                    "start_pct": c["start"], "end_pct": c["end"]}]
            kw["latch_hparams"] = {"rho": float(c["gain"]), "mu": float(c["gain"]), "guide_schedule": c["sched"]}
        t0 = time.time()
        x = model.generate(**kw)
        x = x.cpu().float().numpy() if hasattr(x, "cpu") else np.asarray(x)
        while x.ndim > 2:
            x = x[0]
        if not np.isfinite(x).all():
            print(f"  NONFINITE {c['id']} -- not written", flush=True)
            continue
        os.makedirs(f"{OUT}/{c['leg']}", exist_ok=True)
        pk = float(np.abs(x).max()) or 1e-9
        sf.write(f"{OUT}/{c['leg']}/{c['id']}.wav", (x / pk * 0.8913 if pk > 1 else x).T, sr)
        y = x.mean(0)
        c.update(onsets=round(onsets(y, sr), 3), air_db=round(air_db(y, sr), 2), secs=round(time.time() - t0, 1))
        with open(jl, "a") as f:
            f.write(json.dumps(c) + "\n")
        print(f"  {c['id']}: {c['onsets']} on/s, air {c['air_db']} dB ({c['secs']}s)", flush=True)
    print("DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
