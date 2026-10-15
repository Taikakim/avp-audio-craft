#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-15)
"""latch_guide_anchor_test.py -- does the trajectory anchor stop LatCH from pushing loudness into distortion?

WHY. Listening verdict on latch_early_budget (2026-10-15): flat weighting over 0-1 "pushes up also the volume,
leading to clipping and distortion with the higher weights"; early-only windows "distort loudly"; alpha 0-1 is the
clean one. The per-edit rescale (guide_rescale, latch_guide_rescale_test.py) was NEGATIVE: each edit barely changes
the latent std; the inflation (final std 2-5 vs ~1.1 unguided) builds through the model's later steps. New opt-in
latch_hparams["guide_anchor"] = s0 (latch_guided._anchor_std): after EVERY step the state is capped at the healthy
std sqrt(((1-t)*s0)^2 + t^2) for its t -- a ceiling, normal states untouched. Question: at s0 1.2 / 1.4, do the
distorting settings stay at the unguided level and sound clean, how much onset spread survives, and is the clean
alpha 0-1 setting left alone?

Grid: onset head E04 (Phase E), medium-base euler 50, cfg 7, 20 s, "psytrance, 140 bpm", seeds 1234 + 77;
{alpha 0-1, flat 0-1, alpha 0-0.2, flat 0-0.2} x gain {512, 2048, 4096} x anchor s0 {0 (off), 1.2, 1.4} x request
{2, 10} onsets/s, plus one unguided clip per seed. Measured per clip: onsets/s, final latent std, RAW decoded peak
and RMS dBFS (before any normalisation).
Output: Mantu2/sa3_control_runs/latch_guide_anchor_20261015/<id>.wav + cells.jsonl + run_meta.json.
RUN (hold the GPU lock): ROCR_VISIBLE_DEVICES=0 SAO/.venv/bin/python eval/latch_guide_anchor_test.py [--dry]
"""
import argparse
import json
import os
import sys
import time

os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")

OUT = "/run/media/kim/Mantu2/sa3_control_runs/latch_guide_anchor_20261015"
ONSET = "/run/media/kim/Mantu2/latch_sweep/modular_2026-09-30/phaseE/E04_b32_ep20/latch_sa3_onset_per_beat_ts_best.pt"
PROMPT, BPM, CFG, DUR, STEPS = "psytrance, 140 bpm", 140.0, 7.0, 20.0, 50
SEEDS = (1234, 77)
CONFIGS = (("alpha", 1.0), ("flat", 1.0), ("alpha", 0.2), ("flat", 0.2))
GAINS = (512, 2048, 4096)
ANCHORS = (0.0, 1.2, 1.4)
REQS = (2, 10)


def cells():
    out = [dict(seed=s, gain=0, id=f"base_s{s}") for s in SEEDS]
    for sched, end in CONFIGS:
        for g in GAINS:
            for an in ANCHORS:
                for s in SEEDS:
                    for r in REQS:
                        out.append(dict(seed=s, sched=sched, end=end, gain=g, anchor=an, req=r,
                                        id=f"{sched}_w{end:g}_g{g}_anc{an:g}_s{s}_r{r}"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    jl = f"{OUT}/cells.jsonl"
    done = {json.loads(l)["id"] for l in open(jl) if l.strip()} if os.path.exists(jl) else set()
    todo = [c for c in cells() if c["id"] not in done]
    print(f"[anchor] {len(todo)} cells to render ({len(done)} already done)", flush=True)
    if a.dry:
        return 0
    import librosa
    import numpy as np
    import soundfile as sf
    import torch
    from stable_audio_3 import StableAudioModel
    os.makedirs(OUT, exist_ok=True)
    if not os.path.exists(f"{OUT}/run_meta.json"):
        json.dump({"purpose": __doc__.split("Grid:")[0].strip(),
                   "hypothesis": "Capping the state's std at its healthy per-sigma level after every step removes the loudness push (raw RMS and final latent std stay near the unguided clip) while keeping most of the onset spread, and leaves the clean alpha 0-1 setting unchanged.",
                   "head": {"path": ONSET, "what": "Phase E E04_b32_ep20 onset_per_beat_ts (modular optimiser, no EMA)"},
                   "eval": {"prompt": PROMPT, "bpm_for_conversion": BPM, "cfg": CFG, "duration": DUR, "steps": STEPS,
                            "sampler": "euler", "model": "medium-base", "seeds": SEEDS, "configs": CONFIGS,
                            "gains": GAINS, "anchors_s0": ANCHORS, "requests_onsets_per_s": REQS},
                   "related": ["stable_audio_3/inference/latch_guided.py::_anchor_std",
                               "tests/test_latch_multi_guided.py (guide_anchor tests)",
                               "Mantu2/sa3_control_runs/latch_guide_rescale_20261015/run_meta.json (negative per-edit rescale)",
                               "Mantu2/sa3_control_runs/latch_early_budget_20261015/run_meta.json (kim_feedback)"],
                   "result": None, "kim_feedback": None}, open(f"{OUT}/run_meta.json", "w"), indent=1)

    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    sr = model.model.sample_rate
    n = int(DUR * sr)
    for c in todo:
        kw = dict(prompt=PROMPT, duration=DUR, steps=STEPS, cfg_scale=CFG, seed=c["seed"], sampler_type="euler",
                  return_latents=True)
        if c["gain"]:
            kw["latch_configs"] = [{"model_path": ONSET, "kind": "constant", "value": c["req"] * 60.0 / BPM,
                                    "weight": 1.0, "start_pct": 0.0, "end_pct": c["end"]}]
            kw["latch_hparams"] = {"rho": float(c["gain"]), "mu": float(c["gain"]), "guide_schedule": c["sched"],
                                   "guide_anchor": c["anchor"]}
        t0 = time.time()
        z = model.generate(**kw)
        if not torch.isfinite(z).all():
            print(f"  NONFINITE {c['id']} -- not written", flush=True)
            continue
        pt = model.model.pretransform  # the guided path's own decode (model.py), applied to every cell alike
        with torch.no_grad():
            x = pt.decode(z.detach().type(next(pt.parameters()).dtype)).float()[0, :, :n].cpu().numpy()
        pk = float(np.abs(x).max()) or 1e-9
        rms_db = float(20 * np.log10(np.sqrt((x ** 2).mean()) + 1e-12))
        sf.write(f"{OUT}/{c['id']}.wav", (x / pk * 0.8913 if pk > 1 else x).T, sr)
        y = x.mean(0)
        c.update(onsets=round(len(librosa.onset.onset_detect(y=y, sr=sr, units="time")) / (len(y) / sr), 3),
                 latent_std=round(float(z.float().std()), 4), raw_peak=round(pk, 3), raw_rms_db=round(rms_db, 2),
                 secs=round(time.time() - t0, 1))
        with open(jl, "a") as f:
            f.write(json.dumps(c) + "\n")
        print(f"  {c['id']}: {c['onsets']} on/s, z std {c['latent_std']}, peak {c['raw_peak']}, rms {c['raw_rms_db']} dB",
              flush=True)
    print("DONE", flush=True)
    os._exit(0)  # skip interpreter teardown (the SA3 process aborts there, rc 134)


if __name__ == "__main__":
    sys.exit(main())
