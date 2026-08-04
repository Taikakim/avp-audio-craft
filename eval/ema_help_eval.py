"""ema_help_eval.py — did EMA retraining actually improve control? (Kim ask 2026-07-19,
"EMA-help good to go"). The measured verdict the skewness win demands — not assumed.

For each of the 7 retrained medium/dead heads, render the SHIPPED head vs its ema20 vs ema40
retrain, same prompt/seed, across the steering-gain band, and measure the ACHIEVED target
feature with the same direct raw-feature extractor the training target was built from
(reuses latch_sa3_sweep_measure's logic). EMA helped iff |measured − target| shrinks (or the
measured value moves further toward target) vs the shipped head.

Only continuous-feature heads get a "helped?" verdict; the two genuinely-dead activation heads
(beat/downbeat) are rendered for completeness but flagged non-measurable-as-steering.

Run (SA3 venv, GPU): FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE .venv/bin/python eval/ema_help_eval.py
Then measure (mir venv): mir/bin/python eval/latch_sa3_sweep_measure.py --root ema_help_20260719
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")

import json
import time
from pathlib import Path

SAO = Path(__file__).resolve().parent.parent
SHIPPED = SAO / "stable-audio-3" / "latch_weights_sa3_medium"
EMA = Path("/run/media/kim/Mantu/sa3_control_runs/latch_ema_retrain_20260719")
OUT = Path("/run/media/kim/Mantu/sa3_control_runs/ema_help_20260719"); OUT.mkdir(parents=True, exist_ok=True)

HEADS = ["hpcp", "spectral_kurtosis", "beat_activation", "downbeat_activation",
         "onset_envelope", "rms_energy_body", "rms_energy_air"]
GAINS = [512.0, 2048.0, 8192.0]
PROMPT = "aggressive upbeat goa trance"
SEED = 1234
STEPS = 24
CFG = 7.0
DURATION = 23.79           # 256 frames


def variants(feat):
    """(tag, ckpt_path) for shipped + ema20 + ema40, skipping any that don't exist."""
    out = [("shipped", SHIPPED / f"latch_sa3_{feat}_best.pt")]
    for arm, ep in (("ema20", 20), ("ema40", 40)):
        p = EMA / f"{feat}_{arm}" / f"latch_sa3_{feat}_ep{ep}.pt"
        out.append((arm, p))
    return [(t, p) for t, p in out if p.exists()]


def main():
    import torch
    from stable_audio_3 import StableAudioModel
    from sa3_control.audio_io import save_audio
    import sys
    sys.path.insert(0, str(SAO / "control"))
    SR = 44100

    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    manifest = []
    for feat in HEADS:
        for tag, ckpt in variants(feat):
            ck = torch.load(str(ckpt), map_location="cpu", weights_only=False)
            meta = {k: ck[k] for k in ck if k not in ("state_dict", "averaged_state_dict")}
            target = float(meta.get("std_mean", 0.0)) + 1.5 * (float(meta.get("std_std", 1.0)) or 1.0)
            for gain in GAINS:
                name = f"{feat}__{tag}__g{int(gain)}.wav"
                if (OUT / name).exists():
                    continue
                t0 = time.time()
                audio = model.generate(prompt=PROMPT, duration=DURATION, steps=STEPS, cfg_scale=CFG,
                                       seed=SEED,
                                       latch_configs=[{"model_path": str(ckpt), "kind": "constant",
                                                       "value": target, "weight": 1.0}],
                                       latch_hparams={"rho": gain, "mu": gain})
                save_audio(str(OUT / name), audio[0].float().cpu(), SR)
                manifest.append({"clip": name, "feature": feat, "variant": tag, "gain": gain,
                                 "target": target})
                print(f"[{feat}/{tag}/g{int(gain)}] ({time.time()-t0:.1f}s)")
    (OUT / "ema_help_manifest.json").write_text(json.dumps(manifest, indent=1))
    print(f"[ema-help] {len(manifest)} renders -> {OUT}. Now measure with latch_sa3_sweep_measure (mir venv).")


if __name__ == "__main__":
    main()
