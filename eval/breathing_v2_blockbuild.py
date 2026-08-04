#!/usr/bin/env python
"""breathing_v2_blockbuild.py — beat-aligned prompt-arc a2a with per-layer staggered LoRA
(Kim's v2 design, 2026-07-12).

v1 problems Kim heard (breathing.html): galloping beats (independent SDEdit re-renders
disagree on rhythm phase; 5s wall-clock crossfades overlap misaligned kick grids) and
abrupt section changes (20s strength staircase + prompts with no shared spine).

v2 fixes:
- windows and crossfades aligned to MEASURE boundaries from the .DOWNBEATS sidecar
  (window 12 measures, hop 8 -> 4-measure ~6.7s equal-power crossfades on beat multiples);
- prompts from eval/prompts_arc_v2_blockbuild.json: constant mood/genre/production PREFIX,
  section suffixes that build the arrangement out of SHARED elements (Kim's block design);
- finer strength staircase (one step per 8 measures instead of 20s), same per-layer
  stagger (shallow structure leads, deep timbre lags);
- one fixed seed for every window and section (1234, as v1).

Run (SA3 venv, GPU): FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE .venv/bin/python \
    eval/breathing_v2_blockbuild.py --nl 0.6 --out-dir <dir>
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "control"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sa3_control.audio_io import save_audio                     # noqa: E402
from stable_audio_3 import StableAudioModel                     # noqa: E402
from layered_lora_a2a import lora_layers, set_layered_strength  # noqa: E402

SRC = Path("/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/avp-analyzed/"
           "Aavepyora - Goddess Guerilla - Kaikki-Alla")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--track", default=str(SRC / "full_mix.flac"))
    ap.add_argument("--beats", default=str(SRC / "Aavepyora - Goddess Guerilla - Kaikki-Alla.DOWNBEATS"))
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--prompts-json", default=str(Path(__file__).parent / "prompts_arc_v2_blockbuild.json"))
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--nl", type=float, default=0.6)
    ap.add_argument("--window-measures", type=int, default=12)
    ap.add_argument("--hop-measures", type=int, default=8)
    ap.add_argument("--spread", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--steps", type=int, default=24)
    ap.add_argument("--cfg-scale", type=float, default=6.0)
    ap.add_argument("--dist-shift", choices=["default", "flux"], default="default",
                    help="sampling schedule: default=model LogSNR, flux=FluxDistributionShift "
                         "(style-authority end of the faithfulness fader; Kim 2026-07-13)")
    ap.add_argument("--tag", default="v2")
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    import torch
    audio, sr = sf.read(args.track, dtype="float32", always_2d=True)
    audio = audio.T
    dur = audio.shape[1] / sr
    db = [float(x) for x in Path(args.beats).read_text().split()]
    prompts = json.load(open(args.prompts_json))
    n_meas = len(db)

    # measure-aligned windows: [db[m], db[m+W]] hopped by H; final window runs to EOF
    wins = []
    m = 0
    while True:
        lo = db[m]
        hi_m = m + args.window_measures
        if hi_m >= n_meas:
            wins.append((lo, dur, m))
            break
        wins.append((lo, db[hi_m], m))
        m += args.hop_measures
    n = len(wins)

    def section_for(mid_meas):
        return prompts[min(len(prompts) - 1, int(mid_meas / n_meas * len(prompts)))]

    dshift = None
    if args.dist_shift == "flux":
        from stable_audio_3.inference.distribution_shift import FluxDistributionShift
        dshift = FluxDistributionShift()
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    model.load_lora([args.ckpt])
    layers, n_depths = lora_layers(model)
    ds = model.model.pretransform.downsampling_ratio
    print(f"[v2] {n} windows ({args.window_measures}M/hop{args.hop_measures}M), "
          f"{len(layers)} LoRA params/{n_depths} depths, nl={args.nl}", flush=True)

    pieces = []
    for k, (lo, hi, m0) in enumerate(wins):
        t = k / max(n - 1, 1)
        set_layered_strength(layers, t, args.spread)
        chunk = audio[:, int(lo * sr):int(hi * sr)]
        cdur = chunk.shape[1] / sr
        budget = int(np.ceil((cdur + 8.0) * sr / ds)) * ds
        pr = section_for(m0 + args.window_measures / 2)
        out = model.generate(prompt=pr, duration=cdur, steps=args.steps,
                             cfg_scale=args.cfg_scale, seed=args.seed, batch_size=1,
                             sample_size=budget, init_audio=(sr, torch.tensor(chunk)),
                             init_noise_level=float(args.nl), dist_shift=dshift)
        pieces.append((lo, out[0].float().cpu().numpy()[:, :chunk.shape[1]]))
        print(f"[w{k:02d}] meas {m0}-{m0+args.window_measures} t={t:.2f} :: {pr[len(pr)-60:]}", flush=True)

    # equal-power crossfade at measure-aligned overlaps
    total = np.zeros((2, audio.shape[1]), dtype=np.float32)
    wsum = np.zeros(audio.shape[1], dtype=np.float32)
    for lo, piece in pieces:
        s = int(lo * sr)
        L = piece.shape[1]
        env = np.ones(L, dtype=np.float32)
        fade = min(int((db[1] - db[0]) * (args.window_measures - args.hop_measures) * sr), L // 2)
        if fade > 0:
            ramp = np.sin(np.linspace(0, np.pi / 2, fade)) ** 2
            env[:fade] = ramp
            env[-fade:] = ramp[::-1]
        total[:, s:s + L] += piece * env
        wsum[s:s + L] += env
    total /= np.maximum(wsum, 1e-6)

    save_audio(args.out_dir / f"blockbuild_{args.tag}.wav", torch.tensor(total), sr, normalize=True)
    (args.out_dir / "run_meta.json").write_text(json.dumps(
        {"purpose": "breathing v2 (Kim's design 2026-07-12): shared-prefix block-building "
                    "prompt arc + MEASURE-ALIGNED windows/crossfades (galloping-beat fix) + "
                    "finer per-layer staggered strength staircase. Fixed seed everywhere.",
         "track": Path(args.track).name, "ckpt": args.ckpt, "nl": args.nl,
         "window_measures": args.window_measures, "hop_measures": args.hop_measures,
         "crossfade": "equal-power over (window-hop) measures, boundaries on downbeats",
         "spread": args.spread, "seed": args.seed, "steps": args.steps,
         "cfg_scale": args.cfg_scale, "n_windows": n, "dist_shift": args.dist_shift,
         "prompts": prompts, "prompts_json": args.prompts_json,
         "script": "SAO/eval/breathing_v2_blockbuild.py"}, indent=2))
    print("[done]", flush=True)


if __name__ == "__main__":
    main()
