#!/usr/bin/env python3
"""latch_sa3_sweep_render.py — the LatCH equivalent of model_matrix's gain x
prompt grid (Kim ask 2026-07-19: "a big DoRA-page for the FiLM/LatCH models,
sweeping through the hyperparameters"). This is the LatCH half; onset_eval.html
already IS that page for the FiLM/control adapters (gain x density grid, live
since before this campaign) — not duplicated here.

Sweeps every scalar SA3-medium LatCH head (stable-audio-3/latch_weights_sa3_medium/
*_best.pt) across a gain (rho=mu) ladder deliberately chosen to SHOW the known
non-uniform response (MASTER §5: energy heads operate ~512, gain 128 is a
documented dead zone, activation/hpcp/kurtosis heads are dead at any weight) —
the ladder [64, 128, 512, 2048, 8192] straddles that finding rather than hiding
it, plus a shared gain=0 baseline per prompt.

EXCLUDED from this sweep (12-d/384-d vector heads, not the scalar-target shape
this grid renders): hpcp, same_chroma — the latter has its own dedicated lane
(eval/chroma384_eval.py, chroma384_LUMI_README.md). Target value per head =
std_mean + 1.5*std_std from the checkpoint's own corpus statistics (metadata
already carries them) — a consistent "push toward the high tail" direction.

Two-stage pipeline (measurement needs mir-venv librosa/essentia/madmom, GPU
needs the SA3 venv — same split as onset_eval.py's sibling scripts):
  1. THIS script (SA3 venv, GPU): renders every cell, writes wav +
     latch_sweep_manifest.json (job metadata only, no measurement).
  2. latch_sa3_sweep_measure.py (mir venv, CPU): measures achieved features.
  3. Misc/build_latch_sa3_matrix_page.py: builds the listening page.

Frames rule (Kim direct 2026-07-13): T=512 (47.56s), a 256-frame multiple.

Run (SA3 venv):
  FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 \
  MIOPEN_FIND_MODE=2 ./stable-audio-3/.venv/bin/python eval/latch_sa3_sweep_render.py
"""
import json
import os
import sys
import time

os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")

HERE = os.path.dirname(os.path.abspath(__file__))
SAO = os.path.dirname(HERE)
HEADS_DIR = os.path.join(SAO, "stable-audio-3", "latch_weights_sa3_medium")
OUT_DIR = "/run/media/kim/Mantu/sa3_control_runs/latch_sa3_sweep_20260719"
STAGE = os.path.join(os.path.expanduser("~"), "evals_aac", "latch_sa3_sweep")

GAIN_LADDER = [64.0, 128.0, 512.0, 2048.0, 8192.0]   # straddles the known dead zone (128) + operating point (512)
STEPS = 24
CFG = 7.0
DURATION_SEC = 47.56          # T=512 @ 10.767 fps — 256-frame-multiple rule
EXCLUDE_HEADS = {"hpcp", "same_chroma"}               # vector-shaped heads, separate lanes

PROMPTS = [
    {"id": "p0", "text": "aggressive upbeat goa trance", "seed": 1234},
    {"id": "p1", "text": "mid 90s ambient, experimental, soundscape dark mood, 123 bpm", "seed": 5678},
]


def clip_name(head: str, gain, prompt_id: str) -> str:
    g = "base" if gain == 0 else f"g{int(gain)}"
    return f"{head}__{g}__{prompt_id}.wav"


def main():
    import torch
    from stable_audio_3 import StableAudioModel

    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(STAGE, exist_ok=True)

    head_files = sorted(f for f in os.listdir(HEADS_DIR) if f.endswith("_best.pt"))
    heads = []
    for f in head_files:
        feat = f[len("latch_sa3_"):-len("_best.pt")]
        if feat in EXCLUDE_HEADS:
            continue
        ck = torch.load(os.path.join(HEADS_DIR, f), map_location="cpu", weights_only=False)
        meta = {k: ck[k] for k in ck if k != "state_dict" and k != "averaged_state_dict"}
        std_mean = float(meta.get("std_mean", 0.0))
        std_std = float(meta.get("std_std", 1.0)) or 1.0
        target = std_mean + 1.5 * std_std
        heads.append({"feature": feat, "ckpt": os.path.join(HEADS_DIR, f),
                      "std_mean": std_mean, "std_std": std_std, "target": target,
                      "measurable": feat not in ("onset_envelope_drums", "rms_drums")})
    print(f"[latch-sweep] {len(heads)} scalar heads (excluded: {sorted(EXCLUDE_HEADS)})")
    for h in heads:
        print(f"  {h['feature']:26s} target={h['target']:+.3f} "
              f"(mean={h['std_mean']:.3f} std={h['std_std']:.3f}) "
              f"{'' if h['measurable'] else '[render-only, needs stem separation]'}")

    manifest_path = os.path.join(OUT_DIR, "latch_sweep_manifest.json")
    manifest = json.load(open(manifest_path)) if os.path.exists(manifest_path) else {"cells": []}
    done = {c["clip"] for c in manifest["cells"]}

    model = StableAudioModel.from_pretrained("medium-base", device="cuda")

    # baseline cells (no guidance), shared across all heads — one render per prompt
    for p in PROMPTS:
        name = clip_name("baseline", 0, p["id"])
        if name in done:
            continue
        t0 = time.time()
        audio = model.generate(prompt=p["text"], duration=DURATION_SEC, steps=STEPS,
                               cfg_scale=CFG, seed=p["seed"])
        _save(audio, model, os.path.join(OUT_DIR, name))
        manifest["cells"].append({"clip": name, "head": "baseline", "gain": 0,
                                  "prompt_id": p["id"], "prompt": p["text"],
                                  "target": None, "elapsed": round(time.time() - t0, 1)})
        json.dump(manifest, open(manifest_path, "w"), indent=1)
        print(f"[baseline] {name} ({time.time()-t0:.1f}s)")

    for h in heads:
        for gain in GAIN_LADDER:
            for p in PROMPTS:
                name = clip_name(h["feature"], gain, p["id"])
                if name in done:
                    continue
                t0 = time.time()
                audio = model.generate(
                    prompt=p["text"], duration=DURATION_SEC, steps=STEPS, cfg_scale=CFG,
                    seed=p["seed"],
                    latch_configs=[{"model_path": h["ckpt"], "kind": "constant",
                                    "value": h["target"], "weight": 1.0}],
                    latch_hparams={"rho": gain, "mu": gain})
                _save(audio, model, os.path.join(OUT_DIR, name))
                manifest["cells"].append({
                    "clip": name, "head": h["feature"], "gain": gain,
                    "prompt_id": p["id"], "prompt": p["text"], "target": h["target"],
                    "std_mean": h["std_mean"], "std_std": h["std_std"],
                    "measurable": h["measurable"], "elapsed": round(time.time() - t0, 1)})
                json.dump(manifest, open(manifest_path, "w"), indent=1)
                print(f"[{h['feature']}/g{int(gain)}/{p['id']}] {name} ({time.time()-t0:.1f}s)")

    run_meta = {
        "purpose": ("LatCH steering hyperparameter sweep (Kim ask 2026-07-19): every "
                   "scalar SA3-medium LatCH head across a gain ladder chosen to show "
                   "the documented non-uniform response, not just the good setting."),
        "hypothesis": ("Energy-family heads (rms_energy_*, spectral_*) steer strongly "
                      "near gain~512-2048; activation heads (beat/downbeat) and "
                      "hardness/onset_envelope respond weakly or not at all, per the "
                      "2026-06-28 14-head sweep finding this grid re-verifies at scale."),
        "recipe": {"gain_ladder": GAIN_LADDER, "steps": STEPS, "cfg": CFG,
                  "duration_sec": DURATION_SEC, "model": "medium-base (no adapter)",
                  "target_rule": "std_mean + 1.5*std_std (push-high direction), per-head from ckpt metadata"},
        "excluded_heads": sorted(EXCLUDE_HEADS),
        "result": None, "kim_feedback": None,
    }
    json.dump(run_meta, open(os.path.join(OUT_DIR, "run_meta.json"), "w"), indent=2)
    print(f"\n[latch-sweep] DONE. {len(manifest['cells'])} cells -> {OUT_DIR}")


def _save(audio, model, path):
    import numpy as np
    import soundfile as sf
    a = audio.cpu().float().numpy() if hasattr(audio, "cpu") else np.asarray(audio)
    if a.ndim == 3:
        a = a[0]
    if a.shape[0] in (1, 2):
        a = a.T
    peak = max(1e-9, float(abs(a).max()))
    if peak > 1:
        a = a / peak
    sf.write(path, a, model.model.sample_rate)


if __name__ == "__main__":
    sys.exit(main())
