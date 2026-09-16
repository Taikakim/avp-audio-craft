#!/usr/bin/env python
"""hf_latch_bracket.py — Kim 2026-09-16: brackets the rms_energy_air LatCH head's
gain and end_pct on ONE flagged clip (dora128adj_avp_8ep ep6, kl_0 prompt, seed 1000,
post-trained medium, 8 steps/cfg1 -- matching the original render's exact config for
a fair before/after) before doing anything at corpus scale. Kim: never had time to
properly evaluate this head; wants to try end_pct as late as 0.7 (guidance active
from t=0, not delayed) based on his own experience that early-guidance helped with
older density heads, contrary to the original Stability paper's convention.

Target: the head's OWN std_mean (-32.9611 dB, its training-corpus average) -- NOT
yet the "average of Kim's 42 unflagged clips" he actually asked for, which needs the
exact same feature extractor the head was trained on (not on hand right now).
Flagged explicitly as a simplification for this first bracket pass.
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import json
from pathlib import Path

import numpy as np
from stable_audio_3 import StableAudioModel

FPS = 44100 / 4096

HF_HEAD = "/home/kim/Projects/SAO/stable-audio-3/latch_weights_sa3_medium/latch_sa3_rms_energy_air_best.pt"
HF_TARGET_DB = -32.9611
CKPT = "/run/media/kim/Mantu/sa3_lora_runs/dora128adj_avp_8ep/epoch=6-step=2093.weights.ckpt"
PROMPT = ("This track is a high-energy psytrance piece that blends classic Goa-trance "
          "hypnotic loops with the relentless drive of modern techno. Built around a "
          "pounding 4/4 kick, the production is polished and high-fidelity, employing a "
          "wide stereo field and dynamic panning of its signature elements.")
SEED = 1000
STEPS = 8
CFG = 1.0
DURATION = 48.0

GAINS = [2.0, 8.0, 32.0, 64.0]
START_PCTS = [0.0, 0.2, 0.4]
END_PCT = 1.0
# round 1 (128/512/2048 x end_pct 0.7/1.0) came back with every guided clip sounding
# IDENTICAL to the others but all strongly (over-)damped vs baseline -- gain 128 was
# already saturating. This round: much smaller gains, plus start_pct (delayed onset)
# instead of varying end_pct further (0.7 vs 1.0 showed zero difference last round).


def main():
    out_dir = Path("/tmp/hf_latch_bracket")
    out_dir.mkdir(parents=True, exist_ok=True)

    print("[load] model (medium, post-trained)", flush=True)
    model = StableAudioModel.from_pretrained("medium", device="cuda")
    model.load_lora([CKPT])
    sr = model.model.sample_rate

    base_path = out_dir / "baseline_no_guidance.wav"
    if not base_path.exists():
        print("[gen] baseline (no HF guidance)", flush=True)
        out = model.generate(prompt=PROMPT, duration=DURATION, steps=STEPS, cfg_scale=CFG,
                              seed=SEED, batch_size=1)
        import torch
        from sa3_control.audio_io import save_audio
        save_audio(str(base_path), out[0].float().cpu(), sr)

    import torch
    from sa3_control.audio_io import save_audio
    for gain in GAINS:
        for start_pct in START_PCTS:
            tag = f"gain{int(gain)}_start{int(start_pct*100)}"
            out_path = out_dir / f"{tag}.wav"
            if out_path.exists():
                print(f"[skip] {tag}", flush=True)
                continue
            print(f"[gen] {tag}", flush=True)
            # target_raw needs a [C, T] array (a per-frame trajectory), not a bare
            # scalar -- a constant target is np.full over the latent length, same
            # pattern chain_outpaint_xfade_a2a.py already uses. Bare-float caused an
            # IndexError inside _latch_guided_generate on the first attempt.
            n_frames = round(DURATION * FPS)
            hf_target = np.full((1, n_frames), HF_TARGET_DB, dtype=np.float32)
            out = model.generate(
                prompt=PROMPT, duration=DURATION, steps=STEPS, cfg_scale=CFG,
                seed=SEED, batch_size=1,
                latch_configs=[{"model_path": HF_HEAD, "target_raw": hf_target,
                                 "weight": 1.0, "start_pct": start_pct, "end_pct": END_PCT}],
                latch_hparams={"rho": gain, "mu": gain},
            )
            save_audio(str(out_path), out[0].float().cpu(), sr)

    (out_dir / "run_meta.json").write_text(json.dumps({
        "purpose": "bracket rms_energy_air LatCH gain x end_pct on one flagged-harsh "
                   "clip before any corpus-scale HF-damping pass. Target = head's own "
                   "std_mean (-32.9611dB), NOT yet the 42-unflagged-clip average Kim "
                   "actually asked for (needs the head's exact training feature extractor).",
        "ckpt": CKPT, "prompt": PROMPT, "seed": SEED, "steps": STEPS, "cfg": CFG,
        "gains": GAINS, "start_pcts": START_PCTS, "end_pct": END_PCT, "hf_target_db": HF_TARGET_DB,
        "kim_feedback": None,
    }, indent=2))
    print("[all done]", flush=True)


if __name__ == "__main__":
    main()
