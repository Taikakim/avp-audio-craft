#!/usr/bin/env python
"""interval_cfg_ab.py — interval-CFG mid-band recovery A/B (task #26, Kim-scheduled
2026-07-19 via F; gap-audit win #2, Kynkaanniemi et al. adapted to SA3 flow-t units).

Hypothesis: CFG applied at EVERY step is most mode-collapsing in the a2a mid-noise band
(nl .40-.55 — the measured melodic-movement U-shape dip, W 2026-07-08); NARROWING
cfg_interval to drop guidance at the high-noise/early steps should lift the dip.

CRITICAL UNIT NOTE (the make-or-break caveat from the gap audit): SA3's sampler uses
sigma = t in [0,1] (dit.py:456,479 — guidance fires iff interval[0] <= t <= interval[1]),
NOT the paper's EDM sigma scale. Paper numbers (0.19, 1.61) must NOT be pasted. High
noise = t near 1, so "drop guidance early/high-noise" = UPPER bound < 1. Arms sweep the
upper bound per F's brief: (0.0,0.7) and (0.1,0.8) vs default (0,1). Bonus: an excluded
step falls through to a single _forward (dit.py:479->628) — the narrowed arms are
CHEAPER, not just different.

Conditions matched to W's E1 pilot / a2a_kaikkialla_newstack ladder (same track, ckpt,
prompt, steps, cfg, seed 1234 + one extra seed): T=1024 segment (95.108 s, frames rule,
local-render-safe — full 378 s windows are LUMI-only post-07-21) starting at 60 s.
Baselines for the long-form U-shape = matched slices of the EXISTING unguided ladder
renders (no re-render needed).

Run (SA3 venv, GPU, hold SAO/.gpu.lock):
  FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE .venv/bin/python eval/interval_cfg_ab.py
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
import json
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "control"))
from sa3_control.audio_io import save_audio  # noqa: E402
from stable_audio_3 import StableAudioModel  # noqa: E402

TRACK = "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/avp-flac/009 goddess guerrilla (2006)/Aavepyora - Goddess Guerilla - Kaikki-Alla.flac"
CKPT = "/run/media/kim/Mantu/sa3_lora_runs/dora16_goa_newstack_8ep/epoch=3-step=5400.weights.ckpt"
OUT = Path("/run/media/kim/Mantu/sa3_control_runs/interval_cfg_ab")
PROMPT, STEPS, CFG = "aggressive upbeat goa trance", 24, 6.0
SEG_START = 60.0
T_FRAMES = 1024                      # frames rule: multiples of 256; 95.108 s
NLS = [0.40, 0.475, 0.55, 0.70]      # the dip band + the overshoot point
INTERVALS = {"full": (0.0, 1.0), "hi07": (0.0, 0.7), "band0108": (0.1, 0.8)}
SEEDS = [1234, 4242]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    model.load_lora([CKPT])
    cdm = model.model
    ds = cdm.pretransform.downsampling_ratio
    sr_model = cdm.sample_rate
    dur = T_FRAMES * ds / sr_model            # exactly T=1024 worth of audio
    budget = T_FRAMES * ds

    audio, sr = sf.read(TRACK, dtype="float32", always_2d=True)
    audio = audio.T
    seg = audio[:, int(SEG_START * sr): int((SEG_START + dur) * sr)]
    a = torch.tensor(seg)
    mdtype = next(cdm.model.parameters()).dtype

    renders = []
    for seed in SEEDS:
        for nl in NLS:
            for iname, ival in INTERVALS.items():
                tag = f"nl{int(nl*1000):03d}_{iname}_s{seed}"
                wp = OUT / f"{tag}.wav"
                if wp.exists():
                    print(f"[skip] {tag}", flush=True)
                    renders.append(tag)
                    continue
                t0 = time.time()
                lat = model.generate(prompt=PROMPT, duration=dur, steps=STEPS,
                                     cfg_scale=CFG, seed=seed, batch_size=1,
                                     sample_size=budget,
                                     init_audio=(sr, a), init_noise_level=nl,
                                     cfg_interval=ival, return_latents=True)
                np.save(OUT / f"{tag}.z0.npy", lat.float().cpu().numpy())
                y = cdm.pretransform.decode(lat.to(mdtype))
                save_audio(wp, y[0].float().cpu(), sr_model, normalize=True)
                renders.append(tag)
                print(f"[done] {tag} {time.time()-t0:.0f}s", flush=True)

    (OUT / "run_meta.json").write_text(json.dumps({
        "hypothesis": "Kynkaanniemi interval-CFG adapted to SA3 flow-t: guidance-everywhere is "
                      "most mode-collapsing in the a2a mid-noise band (the nl .40-.55 melodic-"
                      "movement dip, -20% chroma flux); narrowing cfg_interval to exclude the "
                      "high-noise early steps (upper bound .7/.8 in t-units, NOT paper EDM sigmas) "
                      "lifts the dip at matched prompt adherence. Also expects no harm at nl .70 "
                      "(the overshoot point).",
        "track": Path(TRACK).name, "segment_start_s": SEG_START, "duration_s": dur,
        "frames_T": T_FRAMES, "checkpoint": CKPT, "prompt": PROMPT,
        "steps": STEPS, "cfg": CFG, "seeds": SEEDS, "noise_levels": NLS,
        "intervals": {k: list(v) for k, v in INTERVALS.items()},
        "interval_semantics": "guidance fires iff interval[0] <= t <= interval[1]; sigma=t in [0,1], high noise = t~1 (dit.py:479)",
        "baselines": "matched 60-155s slices of sa3_lora_runs/a2a_kaikkialla_newstack (unguided full-track ladder, same ckpt/prompt/seed/steps/cfg)",
        "readout": "melodic_movement_ladder metrics (chroma_flux/pc_trans_rate/pc_entropy/pc_active) adapted to the 95s clips; W co-scores per the task spec",
        "renders": renders, "result": None, "kim_feedback": None}, indent=2))
    print(f"[all done] {len(renders)} renders -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
